from __future__ import annotations

import os
from datetime import date
from pathlib import Path
from typing import TYPE_CHECKING, ClassVar, Final

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from freerouter.discovery import discover
from freerouter.registry import (
    AuthMode,
    DiscoveryMode,
    ProviderStatus,
    credentials_for,
    load_providers,
)

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence

    from freerouter.registry import Provider

DEFAULT_SNAPSHOT: Final = Path("catalog/snapshot.json")
DEFAULT_MARKDOWN: Final = Path("catalog/FREE-MODELS.md")
MAX_LISTED_MODELS: Final = 40
REFERRAL_MARK: Final = "†"


class ProviderSnapshot(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(frozen=True, extra="ignore")

    name_zh: str
    status: str
    tier: str
    region: str
    docs_url: str
    limits: str
    offer_ends_on: date | None = None
    console_url: str | None = None
    referral_url: str | None = None
    referral_note: str | None = None
    models: tuple[str, ...] = ()
    note: str | None = None


class CatalogSnapshot(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(frozen=True, extra="ignore")

    version: int = 1
    generated_on: date
    providers: dict[str, ProviderSnapshot] = Field(default_factory=dict)


def _limits_text(provider: Provider) -> str:
    """Render a provider's published rate limits as one short string."""
    parts = [
        f"{provider.limits.rpm} RPM" if provider.limits.rpm else "",
        f"{provider.limits.rpd} RPD" if provider.limits.rpd else "",
        provider.limits.note or "",
    ]
    return " / ".join(part for part in parts if part) or "见官方文档"


def watchable(provider: Provider, env: Mapping[str, str]) -> bool:
    """Report whether CI can refresh this provider without a credential it does not have."""
    if provider.status is ProviderStatus.RETIRED:
        return False
    if provider.discovery.mode is DiscoveryMode.STATIC:
        return True
    if provider.discovery.auth is AuthMode.NONE:
        return True
    return bool(credentials_for(provider, env))


def load_snapshot(path: Path) -> CatalogSnapshot | None:
    """Read the committed snapshot, returning None when it is missing or unreadable."""
    if not path.exists():
        return None
    try:
        return CatalogSnapshot.model_validate_json(path.read_bytes())
    except (ValidationError, OSError):
        return None


def build_snapshot(
    providers: Sequence[Provider],
    previous: CatalogSnapshot | None,
    today: date,
    env: Mapping[str, str] | None = None,
) -> CatalogSnapshot:
    """Refresh every catalog CI can reach, carrying forward the rest unchanged."""
    source = os.environ if env is None else env
    carried = previous.providers if previous else {}
    entries: dict[str, ProviderSnapshot] = {}
    for provider in providers:
        base = ProviderSnapshot(
            name_zh=provider.name_zh,
            status=provider.status.value,
            tier=provider.tier.value,
            region=provider.region,
            docs_url=provider.docs_url,
            limits=_limits_text(provider),
            offer_ends_on=provider.offer.ends_on,
            console_url=provider.console_url,
            referral_url=provider.referral_url,
            referral_note=provider.referral_note,
        )
        if not watchable(provider, source):
            previous_entry = carried.get(provider.provider_id)
            note = "需要凭证，CI 未刷新" if provider.status is not ProviderStatus.RETIRED else None
            entries[provider.provider_id] = base.model_copy(
                update={
                    "models": (
                        previous_entry.models if previous_entry else provider.discovery.models
                    ),
                    "note": provider.retirement_note if provider.retired_on else note,
                }
            )
            continue
        result = discover(provider, source, require_credentials=False)
        entries[provider.provider_id] = base.model_copy(
            update={"models": result.models, "note": result.error or result.skipped}
        )
    return CatalogSnapshot(generated_on=today, providers=entries)


def content_changed(previous: CatalogSnapshot | None, current: CatalogSnapshot) -> bool:
    """Compare two snapshots ignoring the generation date.

    Without this a daily run would rewrite the files every day just to bump a date,
    and a registry edit that touches only limits or sign-up links would never be
    written at all.
    """
    if previous is None:
        return True
    return previous.providers != current.providers


def diff_snapshots(previous: CatalogSnapshot | None, current: CatalogSnapshot) -> tuple[str, ...]:
    """Describe what changed between two snapshots, as markdown bullet lines."""
    if previous is None:
        return (f"- 首次生成快照，收录 {len(current.providers)} 个平台",)

    lines: list[str] = []
    for name, entry in sorted(current.providers.items()):
        before = previous.providers.get(name)
        if before is None:
            lines.append(f"- **{name}**：新增平台（{len(entry.models)} 个免费模型）")
            continue
        added = sorted(set(entry.models) - set(before.models))
        removed = sorted(set(before.models) - set(entry.models))
        if added:
            lines.append(f"- **{name}** 新增：{', '.join(added)}")
        if removed:
            lines.append(f"- **{name}** 消失：{', '.join(removed)}")
        if before.status != entry.status:
            lines.append(f"- **{name}** 状态：{before.status} → {entry.status}")
    lines.extend(
        f"- **{name}**：已从 registry 移除"
        for name in sorted(set(previous.providers) - set(current.providers))
    )
    if not lines and content_changed(previous, current):
        lines.append("- 平台元数据更新（限额、活动日期或注册链接等），免费模型列表未变")
    return tuple(lines)


def _signup_cell(entry: ProviderSnapshot) -> str:
    """Render the sign-up links, always offering the plain one alongside a referral."""
    plain = f"[官网]({entry.console_url})" if entry.console_url else "-"
    if not entry.referral_url:
        return plain
    return f"{plain} · [邀请链接{REFERRAL_MARK}]({entry.referral_url})"


def _table_row(entry: ProviderSnapshot) -> str:
    """Render one provider as a markdown table row."""
    ends = entry.offer_ends_on.isoformat() if entry.offer_ends_on else "-"
    cells = [
        f"[{entry.name_zh}]({entry.docs_url})",
        entry.tier,
        entry.region,
        entry.status,
        entry.limits,
        str(len(entry.models)),
        ends,
        _signup_cell(entry),
    ]
    return f"| {' | '.join(cells)} |"


def _referral_disclosure(snapshot: CatalogSnapshot) -> list[str]:
    """Spell out every referral arrangement, or say plainly that there are none."""
    referrals = [
        (entry.name_zh, entry.referral_note or "")
        for _, entry in sorted(snapshot.providers.items())
        if entry.referral_url
    ]
    if not referrals:
        return ["", "本目录中的注册链接均为平台官网直达，不含任何邀请或返利链接。"]

    intro = f"标了 {REFERRAL_MARK} 的是邀请链接，通过它注册，你和本项目维护者双方都会获得平台奖励："
    lines = ["", f"### {REFERRAL_MARK} 关于邀请链接", "", intro, ""]
    lines.extend(f"- **{name}**：{note}" for name, note in referrals)
    lines.extend(
        [
            "",
            "旁边的「官网」是无返利的直达入口，两个都能用，注册流程完全一样。",
            "",
            "**返利不影响任何技术判断。** 一个平台能不能进 `providers/`、",
            "一个模型能不能进 `free-router` 池，只取决于该平台 `free_basis` 字段写明的免费依据",
            "和真实探测结果；排序按平台 id 字母序，与有无返利无关。",
            "这一点有测试守着（见 `tests/test_registry.py`）。",
        ]
    )
    return lines


def render_markdown(snapshot: CatalogSnapshot) -> str:
    """Render the human-readable free-model catalog."""
    generated = snapshot.generated_on.isoformat()
    source = "`.github/workflows/watch-free-models.yml`"
    header = [
        "# FreeRouter 免费模型目录",
        "",
        f"最后变更：{generated}（由 {source} 自动生成，请勿手改）",
        "",
        "| 平台 | 类型 | 区域 | 状态 | 已知限额 | 免费模型数 | 活动到期 | 注册 |",
        "|---|---|---|---|---|---|---|---|",
    ]
    rows = [_table_row(entry) for _, entry in sorted(snapshot.providers.items())]

    details = [*_referral_disclosure(snapshot), "", "## 各平台当前免费模型", ""]
    for name, entry in sorted(snapshot.providers.items()):
        details.append(f"### {entry.name_zh} (`{name}`)")
        details.append("")
        if entry.note:
            details.append(f"> {entry.note}")
            details.append("")
        if not entry.models:
            details.append("_当前没有可路由的免费模型。_")
        else:
            details.extend(f"- `{model}`" for model in entry.models[:MAX_LISTED_MODELS])
            if len(entry.models) > MAX_LISTED_MODELS:
                details.append(f"- …另有 {len(entry.models) - MAX_LISTED_MODELS} 个")
        details.append("")
    return "\n".join([*header, *rows, *details]) + "\n"


def refresh_catalog(
    providers_dir: Path,
    snapshot_path: Path = DEFAULT_SNAPSHOT,
    markdown_path: Path = DEFAULT_MARKDOWN,
    today: date | None = None,
    env: Mapping[str, str] | None = None,
) -> tuple[str, ...]:
    """Refresh the committed catalog files and return the change summary lines.

    The files are rewritten only when something actually changed, so a daily CI
    run does not produce a pull request whose only diff is the generation date.
    """
    providers = load_providers(providers_dir)
    previous = load_snapshot(snapshot_path)
    current = build_snapshot(
        providers, previous, today or date.today(), env  # noqa: DTZ011 - CI runs in UTC
    )
    if not content_changed(previous, current):
        return ()
    changes = diff_snapshots(previous, current)

    snapshot_path.parent.mkdir(parents=True, exist_ok=True)
    _ = snapshot_path.write_text(current.model_dump_json(indent=2), encoding="utf-8")
    markdown_path.parent.mkdir(parents=True, exist_ok=True)
    _ = markdown_path.write_text(render_markdown(current), encoding="utf-8")
    return changes
