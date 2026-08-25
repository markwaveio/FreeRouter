from __future__ import annotations

from datetime import date
from typing import TYPE_CHECKING

from freerouter.watch import (
    CatalogSnapshot,
    ProviderSnapshot,
    build_snapshot,
    content_changed,
    diff_snapshots,
    refresh_catalog,
    render_markdown,
    watchable,
)
from tests.conftest import make_provider

if TYPE_CHECKING:
    from pathlib import Path

TODAY = date(2026, 8, 25)


def _snapshot(**models: tuple[str, ...]) -> CatalogSnapshot:
    return CatalogSnapshot(
        generated_on=TODAY,
        providers={
            name: ProviderSnapshot(
                name_zh=name,
                status="active",
                tier="free",
                region="cn",
                docs_url="https://example.com",
                limits="20 RPM",
                models=ids,
            )
            for name, ids in models.items()
        },
    )


def test_ci_can_refresh_public_catalogs_and_static_lists_only() -> None:
    assert watchable(make_provider(), {})
    assert watchable(
        make_provider(
            discovery={
                "mode": "listing",
                "url": "https://x/y",
                "auth": "none",
                "whole_catalog_is_free": True,
            }
        ),
        {},
    )
    assert not watchable(
        make_provider(
            discovery={
                "mode": "listing",
                "url": "https://x/y",
                "auth": "bearer",
                "whole_catalog_is_free": True,
            }
        ),
        {},
    )
    assert not watchable(make_provider(status="retired"), {})


def test_providers_ci_cannot_reach_keep_their_previous_models() -> None:
    # Given
    provider = make_provider(
        discovery={
            "mode": "listing",
            "url": "https://x/y",
            "auth": "bearer",
            "whole_catalog_is_free": True,
        }
    )
    previous = _snapshot(demo=("kept-model",))

    # When
    current = build_snapshot([provider], previous, TODAY, {})

    # Then
    assert current.providers["demo"].models == ("kept-model",)
    assert current.providers["demo"].note == "需要凭证，CI 未刷新"


def test_diff_reports_additions_removals_and_status_changes() -> None:
    # Given
    previous = _snapshot(demo=("a", "b"), old=("x",))
    current = _snapshot(demo=("b", "c"), fresh=("z",))

    # When
    lines = diff_snapshots(previous, current)

    # Then
    joined = "\n".join(lines)
    assert "**demo** 新增：c" in joined
    assert "**demo** 消失：a" in joined
    assert "**fresh**：新增平台" in joined
    assert "**old**：已从 registry 移除" in joined


def test_first_run_reports_the_initial_snapshot() -> None:
    assert diff_snapshots(None, _snapshot(demo=("a",))) == ("- 首次生成快照，收录 1 个平台",)


def test_markdown_lists_every_provider_and_its_models() -> None:
    # When
    text = render_markdown(_snapshot(demo=("a", "b")))

    # Then
    assert "# FreeRouter 免费模型目录" in text
    assert "最后变更：2026-08-25" in text
    assert "| [demo](https://example.com) | free | cn | active | 20 RPM | 2 | - |" in text
    assert "- `a`" in text


def test_refresh_catalog_writes_both_files(tmp_path: Path) -> None:
    # Given
    providers_dir = tmp_path / "providers"
    providers_dir.mkdir()
    _ = (providers_dir / "demo.yaml").write_text(
        """
id: demo
name: Demo
name_zh: 演示平台
litellm_prefix: openai
docs_url: https://demo.example
free_basis: 测试
free_basis_checked: 2026-08-25
discovery:
  mode: static
  models: [alpha]
""",
        encoding="utf-8",
    )
    snapshot_path = tmp_path / "catalog/snapshot.json"
    markdown_path = tmp_path / "catalog/FREE-MODELS.md"

    # When
    changes = refresh_catalog(providers_dir, snapshot_path, markdown_path, TODAY)

    # Then
    assert changes == ("- 首次生成快照，收录 1 个平台",)
    assert "alpha" in markdown_path.read_text(encoding="utf-8")
    assert snapshot_path.exists()

    # When run again with no upstream change
    before = snapshot_path.read_bytes()
    assert refresh_catalog(providers_dir, snapshot_path, markdown_path, date(2026, 9, 1)) == ()
    assert snapshot_path.read_bytes() == before


def test_metadata_only_changes_still_get_written() -> None:
    """改了限额或注册链接但模型没变，目录也要跟着更新。"""
    # Given
    previous = _snapshot(demo=("a",))
    current = _snapshot(demo=("a",))
    changed = current.model_copy(
        update={
            "providers": {
                "demo": current.providers["demo"].model_copy(update={"limits": "60 RPM"})
            }
        }
    )

    # Then
    assert not content_changed(previous, current)
    assert content_changed(previous, changed)
    assert diff_snapshots(previous, changed) == (
        "- 平台元数据更新（限额、活动日期或注册链接等），免费模型列表未变",
    )


def test_a_referral_link_is_always_disclosed_next_to_a_plain_one() -> None:
    # Given
    snapshot = _snapshot(demo=("a",))
    entry = snapshot.providers["demo"].model_copy(
        update={
            "console_url": "https://demo.example/keys",
            "referral_url": "https://demo.example/i/CODE",
            "referral_note": "双方各得 2000 万 tokens",
        }
    )
    with_referral = snapshot.model_copy(update={"providers": {"demo": entry}})

    # When
    text = render_markdown(with_referral)

    # Then
    assert "[官网](https://demo.example/keys)" in text
    assert "[邀请链接†](https://demo.example/i/CODE)" in text
    assert "双方各得 2000 万 tokens" in text
    assert "旁边的「官网」是无返利的直达入口" in text
    assert "返利不影响任何技术判断" in text


def test_a_catalog_without_referrals_says_so_plainly() -> None:
    # When
    text = render_markdown(_snapshot(demo=("a",)))

    # Then
    assert "不含任何邀请或返利链接" in text
