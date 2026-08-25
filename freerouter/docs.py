from __future__ import annotations

import re
from typing import TYPE_CHECKING, Final

from freerouter.registry import ProviderStatus, Tier, load_providers

if TYPE_CHECKING:
    from collections.abc import Sequence
    from pathlib import Path

    from freerouter.registry import Provider

REFERRAL_MARK: Final = "†"
BEGIN: Final = "<!-- BEGIN GENERATED: {name} — 由 make docs 生成，请勿手改 -->"
END: Final = "<!-- END GENERATED: {name} -->"
ENV_BEGIN: Final = "# ── BEGIN GENERATED: {name} — 由 make docs 生成，请勿手改 ──"
ENV_END: Final = "# ── END GENERATED: {name} ──"

TIER_TITLES: Final = {
    Tier.FREE: "永久免费层（长期可用）",
    Tier.TRIAL: "新用户赠送额度（有有效期）",
    Tier.OFFER: "限时活动（随时可能调整）",
}


def read_env_file(path: Path) -> dict[str, str]:
    """Read a `.env` file into a mapping, ignoring comments and blank lines.

    The CLI runs on the host where the project's `.env` is not exported, so reading
    it directly is what makes `freerouter keys` report the project's real state
    rather than whatever happens to be in the operator's shell.
    """
    if not path.exists():
        return {}
    values: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        name, separator, value = stripped.partition("=")
        if separator:
            values[name.strip()] = value.strip().strip("\"'")
    return values


def signup_url(provider: Provider) -> str | None:
    """Return the link a reader should follow to get a key, referral first."""
    return provider.referral_url or provider.console_url


def _signup_cell(provider: Provider) -> str:
    """Render the sign-up cell, always keeping a plain link beside a referral one."""
    if provider.referral_url and provider.console_url:
        invited = f"[**注册**{REFERRAL_MARK}]({provider.referral_url})"
        return f"{invited} · [官网]({provider.console_url})"
    target = signup_url(provider)
    return f"[**注册**]({target})" if target else "-"


def _row(provider: Provider) -> str:
    """Render one provider as a README table row."""
    limits = provider.limits.note or ""
    rate = "、".join(
        part
        for part in (
            f"{provider.limits.rpm} RPM" if provider.limits.rpm else "",
            f"{provider.limits.rpd} 次/天" if provider.limits.rpd else "",
        )
        if part
    )
    cells = [
        f"[{provider.name_zh}]({provider.docs_url})",
        "国内" if provider.region == "cn" else "国际",
        provider.summary or summarize(provider.free_basis, 44),
        rate or limits[:24] or "见官网",
        _signup_cell(provider),
    ]
    return f"| {' | '.join(cells)} |"


def summarize(text: str, limit: int) -> str:
    """Shorten a description at a punctuation boundary rather than mid-word."""
    first = text.split("；", maxsplit=1)[0].split("。", maxsplit=1)[0].strip()
    if len(first) <= limit:
        return first
    head = first[:limit]
    for mark in ("，", "、", " "):
        cut = head.rfind(mark)
        if cut >= limit // 2:
            return head[:cut] + "…"
    return head + "…"


def _inactive_line(provider: Provider) -> str:
    """Render one tracked-but-not-routed provider as a bullet."""
    reason = provider.retirement_note or provider.free_basis
    return f"- **{provider.name_zh}**（`{provider.status.value}`）：{reason}"


def _signup_row(provider: Provider) -> str:
    """Render one provider as a row of the top-of-README sign-up table."""
    rate = "、".join(
        part
        for part in (
            f"{provider.limits.rpm} RPM" if provider.limits.rpm else "",
            f"{provider.limits.rpd} 次/天" if provider.limits.rpd else "",
        )
        if part
    )
    button = f"[**立即注册 →**{REFERRAL_MARK}]({provider.referral_url})"
    cells = [
        f"**{provider.name_zh}**",
        provider.summary or summarize(provider.free_basis, 34),
        rate or "见官网",
        "注册即得" if not provider.referral_requires_payment else "奖励需首充",
        button,
    ]
    return f"| {' | '.join(cells)} |"


def render_signup_table(providers: Sequence[Provider]) -> str:
    """Render the sign-up block that opens the README.

    Only platforms whose link is a referral appear here, cheapest commitment first,
    and the disclosure sits in the same block rather than further down the page.
    """
    invited = sorted(
        (p for p in providers if p.referral_url and p.status is ProviderStatus.ACTIVE),
        key=lambda item: (item.referral_requires_payment, item.provider_id),
    )
    if not invited:
        return "填任意一个平台的 Key 就能跑起来，完整清单见[下方平台表格](#已接入的平台)。"

    others = sum(
        1
        for p in providers
        if p.status is ProviderStatus.ACTIVE and p.credential and not p.referral_url
    )
    notes = [f"> - **{p.name_zh}**：{p.referral_note}" for p in invited if p.referral_note]
    disclosure = f"> {REFERRAL_MARK} **这些是邀请链接**，通过它注册会产生平台奖励："
    alternative = (
        f"> 不想走返利就用[官网直达入口](#已接入的平台)，注册流程完全一样；"
        f"那张表里还有另外 {others} 家不带邀请链接的平台。"
        f"返利不影响任何技术判断，见[说明](#挂自己的邀请链接)。"
    )
    return "\n".join(
        [
            "**填任意一个平台的 Key 就能跑起来。** 下面几家注册即用、不要信用卡：",
            "",
            "| 平台 | 免费什么 | 限额 | 奖励 | |",
            "|---|---|---|---|---|",
            *[_signup_row(provider) for provider in invited],
            "",
            disclosure,
            ">",
            *notes,
            ">",
            alternative,
        ]
    )


def render_platform_tables(providers: Sequence[Provider]) -> str:
    """Render the README platform tables, grouped by how the free tier works."""
    blocks: list[str] = []
    for tier, title in TIER_TITLES.items():
        rows = [
            _row(provider)
            for provider in providers
            if provider.tier is tier and provider.status is ProviderStatus.ACTIVE
        ]
        if not rows:
            continue
        blocks.extend(
            [
                f"### {title}",
                "",
                "| 平台 | 区域 | 免费什么 | 限额 | |",
                "|---|---|---|---|---|",
                *rows,
                "",
            ]
        )

    inactive = [p for p in providers if p.status is not ProviderStatus.ACTIVE]
    if inactive:
        blocks.extend(["### 已跟踪但不路由", ""])
        blocks.extend(
            _inactive_line(provider) for provider in inactive
        )
        blocks.append("")

    notes = [
        f"> - **{provider.name_zh}**：{provider.referral_note}"
        for provider in providers
        if provider.referral_url
    ]
    if notes:
        lead = f"> {REFERRAL_MARK} 标记的是邀请链接，通过它注册**你和维护者双方都会拿到平台奖励**："
        tail = (
            "> 旁边的「官网」是无返利直达入口，两个都能用，注册流程一样。"
            "返利不影响任何技术判断，见[下方说明](#挂自己的邀请链接)。"
        )
        blocks.extend([lead, ">", *notes, ">", tail, ""])
    return "\n".join(blocks).rstrip() + "\n"


def render_env_keys(providers: Sequence[Provider]) -> str:
    """Render the provider-key block of `.env.example`, each with where to get it."""
    lines: list[str] = []
    for tier, title in TIER_TITLES.items():
        group = [
            provider
            for provider in providers
            if provider.tier is tier
            and provider.status is ProviderStatus.ACTIVE
            and provider.credential
        ]
        if not group:
            continue
        lines.extend(["", f"# ── {title} ──"])
        for provider in group:
            target = signup_url(provider)
            mark = "（邀请链接，双方都有奖励）" if provider.referral_url else ""
            lines.append("")
            blurb = provider.summary or summarize(provider.free_basis, 52)
            lines.append(f"# {provider.name_zh}：{blurb}")
            if target:
                lines.append(f"#   注册领 Key: {target}{mark}")
            lines.append(f"{provider.credential}=")
            lines.extend(f"{extra}=" for extra in provider.extra_credentials)
    return "\n".join(lines)


def inject(text: str, name: str, body: str, *, begin: str, end: str) -> str:
    """Replace the content between two generated-block markers."""
    start_marker = begin.format(name=name)
    end_marker = end.format(name=name)
    pattern = re.compile(
        f"{re.escape(start_marker)}.*?{re.escape(end_marker)}",
        re.DOTALL,
    )
    replacement = f"{start_marker}\n\n{body.strip()}\n\n{end_marker}"
    if not pattern.search(text):
        return text
    return pattern.sub(lambda _: replacement, text)


def sync(providers_dir: Path, readme: Path, env_example: Path) -> tuple[str, ...]:
    """Regenerate the platform tables in the README and the key list in `.env.example`."""
    providers = sorted(load_providers(providers_dir), key=lambda item: item.provider_id)
    updated: list[str] = []

    for path, name, body, begin, end in (
        (readme, "signup", render_signup_table(providers), BEGIN, END),
        (readme, "platforms", render_platform_tables(providers), BEGIN, END),
        (env_example, "provider-keys", render_env_keys(providers), ENV_BEGIN, ENV_END),
    ):
        original = path.read_text(encoding="utf-8")
        rewritten = inject(original, name, body, begin=begin, end=end)
        if rewritten != original:
            _ = path.write_text(rewritten, encoding="utf-8")
            updated.append(str(path))
    return tuple(updated)
