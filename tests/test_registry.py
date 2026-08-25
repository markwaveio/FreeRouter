from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest
from pydantic import ValidationError

from freerouter.errors import RegistryError
from freerouter.registry import (
    DiscoveryMode,
    ProviderStatus,
    credentials_for,
    expand_env,
    load_providers,
    matches_any,
    select_models,
)
from tests.conftest import make_provider

PROVIDERS_DIR = Path(__file__).resolve().parent.parent / "providers"


def test_every_shipped_provider_file_is_valid() -> None:
    # Given / When
    providers = load_providers(PROVIDERS_DIR)

    # Then
    assert len(providers) >= 20
    assert len({provider.provider_id for provider in providers}) == len(providers)
    for provider in providers:
        assert provider.free_basis, provider.provider_id
        assert provider.free_basis_checked >= date(2026, 1, 1), provider.provider_id


def test_github_models_is_recorded_as_retired() -> None:
    # Given
    providers = {p.provider_id: p for p in load_providers(PROVIDERS_DIR)}

    # When
    github = providers["github-models"]

    # Then
    assert github.status is ProviderStatus.RETIRED
    assert github.retired_on == date(2026, 7, 30)
    assert not github.routable


def test_invalid_provider_file_names_the_path(tmp_path: Path) -> None:
    # Given
    _ = (tmp_path / "broken.yaml").write_text("id: broken\n", encoding="utf-8")

    # When / Then
    with pytest.raises(RegistryError, match=r"broken\.yaml"):
        _ = load_providers(tmp_path)


def test_expand_env_returns_none_when_a_variable_is_missing() -> None:
    # Given
    template = "https://api.example/${ACCOUNT}/models"

    # When / Then
    assert expand_env(template, {"ACCOUNT": "abc"}) == "https://api.example/abc/models"
    assert expand_env(template, {"ACCOUNT": "  "}) is None
    assert expand_env(template, {}) is None


def test_credentials_require_every_declared_variable() -> None:
    # Given
    provider = make_provider(extra_credentials=["DEMO_ACCOUNT_ID"])

    # When / Then
    assert credentials_for(provider, {"DEMO_API_KEY": "k"}) == {}
    assert credentials_for(provider, {"DEMO_API_KEY": "k", "DEMO_ACCOUNT_ID": "a"}) == {
        "DEMO_API_KEY": "k",
        "DEMO_ACCOUNT_ID": "a",
    }


def test_pattern_matching_ignores_case() -> None:
    assert matches_any("Qwen/Qwen3-VL-8B", ["*-vl-*"])
    assert not matches_any("Qwen/Qwen3-8B", ["*-vl-*"])


def test_select_models_reports_what_the_cap_dropped() -> None:
    # Given
    ids = ["m5", "m1", "m3", "m2", "m4", "skip-me"]

    # When
    kept, dropped = select_models(ids, allow=["m*"], deny=["m4"], limit=3)

    # Then
    assert kept == ("m1", "m2", "m3")
    assert dropped == ("m5",)


def test_listing_without_free_evidence_is_rejected() -> None:
    # Given a reseller-shaped provider that would treat its whole catalog as free
    # When / Then
    with pytest.raises(ValidationError, match="whole_catalog_is_free") as caught:
        _ = make_provider(discovery={"mode": "listing", "url": "https://x/y", "auth": "bearer"})

    message = str(caught.value)
    assert "demo" in message
    assert "every model the platform sells would be treated as free" in message


def test_listing_is_accepted_with_either_kind_of_evidence() -> None:
    # Given / When / Then
    named = make_provider(
        discovery={"mode": "listing", "url": "https://x/y", "auth": "bearer", "allow": ["free-*"]}
    )
    whole = make_provider(
        discovery={
            "mode": "listing",
            "url": "https://x/y",
            "auth": "bearer",
            "whole_catalog_is_free": True,
        }
    )
    assert named.discovery.allow == ("free-*",)
    assert whole.discovery.whole_catalog_is_free


def test_no_shipped_listing_provider_trusts_a_whole_reseller_catalog() -> None:
    # Given
    providers = load_providers(PROVIDERS_DIR)

    # Then every listing provider states why its catalog is free
    for provider in providers:
        if provider.discovery.mode is DiscoveryMode.LISTING:
            evidence = provider.discovery.allow or provider.discovery.whole_catalog_is_free
            assert evidence, provider.provider_id


def test_b_ai_only_routes_the_models_its_promotion_names() -> None:
    # Given B.AI resells GPT, Claude and Gemini through the same catalog
    providers = {p.provider_id: p for p in load_providers(PROVIDERS_DIR)}

    # When
    b_ai = providers["b-ai"]

    # Then
    assert b_ai.discovery.allow == ("deepseek-v4-flash", "deepseek-v4-flash-vision-exp")
    assert not b_ai.discovery.whole_catalog_is_free
    for family in ("gpt-*", "claude-*", "gemini-*"):
        assert family in b_ai.discovery.deny


CYCLES_PER_DAY = 4  # 默认 FREEROUTER_REFRESH_INTERVAL=21600 秒
MAX_PROBE_SHARE = 0.25


def test_no_provider_spends_its_daily_quota_on_health_probes() -> None:
    """探测是体检，不能反过来把额度用光。

    每轮探测上限 x 每天轮数，不得超过平台公布日额度的 25%。这条在 CI 里跑，
    改大 max_per_cycle 或改小 rpd 时会立刻失败。
    """
    # Given
    providers = load_providers(PROVIDERS_DIR)

    # Then
    for provider in providers:
        if not provider.probe.enabled or provider.status is not ProviderStatus.ACTIVE:
            continue
        quota = provider.limits.rpd
        if quota is None:
            continue
        per_day = provider.probe.max_per_cycle * CYCLES_PER_DAY
        assert per_day <= quota * MAX_PROBE_SHARE, (
            f"{provider.provider_id}: 每天探测 {per_day} 次，"
            f"占日额度 {quota} 的 {per_day / quota:.0%}，超过 {MAX_PROBE_SHARE:.0%} 上限"
        )


ROUTING_MODULES = ("discovery.py", "planning.py", "probe.py", "refresh.py", "traffic.py")


def test_referral_links_cannot_influence_routing() -> None:
    """返利不能影响技术判断，这条用结构保证而不是靠承诺。

    邀请链接只允许出现在注册表定义和文档生成里。发现、规划、探测、刷新这几个
    决定「哪个平台进来、哪个模型进池」的模块，一旦引用了 referral 字段就失败。
    """
    # Given
    package = PROVIDERS_DIR.parent / "freerouter"

    # Then
    for name in ROUTING_MODULES:
        source = (package / name).read_text(encoding="utf-8")
        assert "referral" not in source, f"{name} 引用了 referral 字段，返利不得参与路由决策"


def test_a_referral_link_without_disclosure_is_rejected() -> None:
    # Given / When / Then
    with pytest.raises(ValidationError, match="referral_note"):
        _ = make_provider(referral_url="https://demo.example/i/CODE")

    disclosed = make_provider(
        referral_url="https://demo.example/i/CODE",
        referral_note="双方各得 2000 万 tokens",
    )
    assert disclosed.referral_note


def test_shipped_referral_links_all_state_the_benefit() -> None:
    # Given
    providers = load_providers(PROVIDERS_DIR)

    # Then
    for provider in providers:
        if provider.referral_url:
            assert provider.referral_note, provider.provider_id
            assert provider.console_url, f"{provider.provider_id} 必须同时提供无返利的官网入口"
