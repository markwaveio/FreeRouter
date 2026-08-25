from __future__ import annotations

from pathlib import Path

from freerouter.docs import (
    BEGIN,
    END,
    ENV_BEGIN,
    ENV_END,
    inject,
    read_env_file,
    render_env_keys,
    render_platform_tables,
    render_signup_table,
    signup_url,
    summarize,
)
from freerouter.registry import load_providers
from tests.conftest import make_provider

ROOT = Path(__file__).resolve().parent.parent

REFERRED = {
    "console_url": "https://demo.example/keys",
    "referral_url": "https://demo.example/i/CODE",
    "referral_note": "双方各得 2000 万 tokens",
}


def test_the_referral_link_is_what_a_reader_is_sent_to() -> None:
    assert signup_url(make_provider(**REFERRED)) == "https://demo.example/i/CODE"
    assert signup_url(make_provider(console_url="https://demo.example/keys")) == (
        "https://demo.example/keys"
    )
    assert signup_url(make_provider()) is None


def test_the_readme_table_marks_a_referral_and_keeps_the_plain_link() -> None:
    # When
    table = render_platform_tables([make_provider(**REFERRED)])

    # Then
    assert "[**注册**†](https://demo.example/i/CODE)" in table
    assert "[官网](https://demo.example/keys)" in table
    assert "双方各得 2000 万 tokens" in table
    assert "你和维护者双方都会拿到平台奖励" in table


def test_a_platform_without_a_referral_gets_one_plain_button() -> None:
    # When
    table = render_platform_tables([make_provider(console_url="https://demo.example/keys")])

    # Then
    assert "[**注册**](https://demo.example/keys)" in table
    assert "†" not in table


def test_retired_platforms_are_listed_but_never_get_a_sign_up_button() -> None:
    # Given
    retired = make_provider(
        status="retired",
        retirement_note="平台已下线",
        console_url="https://demo.example/keys",
    )

    # When
    table = render_platform_tables([retired])

    # Then
    assert "已跟踪但不路由" in table
    assert "平台已下线" in table
    assert "[**注册**]" not in table


def test_env_example_tells_the_reader_where_each_key_comes_from() -> None:
    # When
    block = render_env_keys([make_provider(**REFERRED)])

    # Then
    assert "DEMO_API_KEY=" in block
    assert "注册领 Key: https://demo.example/i/CODE（邀请链接，双方都有奖励）" in block


def test_env_example_includes_every_extra_credential() -> None:
    # Given
    provider = make_provider(extra_credentials=["DEMO_ACCOUNT_ID"])

    # When
    block = render_env_keys([provider])

    # Then
    assert "DEMO_API_KEY=" in block
    assert "DEMO_ACCOUNT_ID=" in block


def test_injection_replaces_only_the_generated_block() -> None:
    # Given
    document = "\n".join(
        [
            "# 标题",
            "手写的段落，不能被动到。",
            BEGIN.format(name="platforms"),
            "旧内容",
            END.format(name="platforms"),
            "后面也是手写的。",
        ]
    )

    # When
    rewritten = inject(document, "platforms", "新内容", begin=BEGIN, end=END)

    # Then
    assert "手写的段落，不能被动到。" in rewritten
    assert "后面也是手写的。" in rewritten
    assert "新内容" in rewritten
    assert "旧内容" not in rewritten


def test_a_document_without_markers_is_left_alone() -> None:
    assert inject("没有标记", "platforms", "新内容", begin=BEGIN, end=END) == "没有标记"


def test_env_file_is_read_without_leaking_comments_or_quotes(tmp_path: Path) -> None:
    # Given
    path = tmp_path / ".env"
    _ = path.write_text(
        '# 注释\n\nA_KEY=plain\nB_KEY="quoted"\nEMPTY=\nnot a pair\n',
        encoding="utf-8",
    )

    # When
    values = read_env_file(path)

    # Then
    assert values == {"A_KEY": "plain", "B_KEY": "quoted", "EMPTY": ""}


def test_a_missing_env_file_is_not_an_error(tmp_path: Path) -> None:
    assert read_env_file(tmp_path / "nope") == {}


def test_generated_blocks_in_the_repo_are_up_to_date() -> None:
    """改了 providers/ 但忘了 make docs，README 和 .env.example 会跟注册表脱节。"""
    # Given
    providers = sorted(load_providers(ROOT / "providers"), key=lambda item: item.provider_id)

    # Then
    for path, name, body, begin, end in (
        (ROOT / "README.md", "platforms", render_platform_tables(providers), BEGIN, END),
        (ROOT / ".env.example", "provider-keys", render_env_keys(providers), ENV_BEGIN, ENV_END),
    ):
        original = path.read_text(encoding="utf-8")
        assert inject(original, name, body, begin=begin, end=end) == original, (
            f"{path.name} 的生成块过期了，运行 make docs"
        )


def test_every_routable_platform_offers_a_way_to_get_a_key() -> None:
    # Given
    providers = load_providers(ROOT / "providers")

    # Then
    for provider in providers:
        if provider.routable and provider.credential:
            reason = f"{provider.provider_id} 缺少 console_url，读者不知道去哪注册"
            assert signup_url(provider), reason


def test_summaries_are_cut_at_a_punctuation_boundary() -> None:
    # Given a description longer than the limit
    text = (
        "模型目录返回的 prompt 与 completion 全部价格规则为 0，"
        "输入输出都含 text，且输出模态不含 audio"
    )

    # When
    short = summarize(text, 44)

    # Then
    assert len(short) <= 45
    assert short.endswith("…")
    assert not short.endswith("且输…")


def test_a_short_description_is_left_intact() -> None:
    assert summarize("很短的说明", 44) == "很短的说明"


def test_only_the_first_clause_is_kept() -> None:
    assert summarize("第一句；第二句不要", 44) == "第一句"


def test_the_signup_block_leads_with_the_lowest_commitment() -> None:
    # Given one platform whose reward needs a top-up and one that does not
    paid = make_provider(
        id="paid",
        name_zh="需充值平台",
        referral_url="https://paid.example/i/X",
        referral_note="首充后双方各得 $5",
        referral_requires_payment=True,
        console_url="https://paid.example/keys",
    )
    free = make_provider(
        id="free",
        name_zh="注册即得平台",
        referral_url="https://free.example/i/Y",
        referral_note="双方各得 tokens",
        console_url="https://free.example/keys",
    )

    # When
    block = render_signup_table([paid, free])

    # Then
    assert block.index("注册即得平台") < block.index("需充值平台")
    assert "注册即得" in block
    assert "奖励需首充" in block


def test_the_signup_block_carries_its_own_disclosure() -> None:
    # Given
    provider = make_provider(
        referral_url="https://demo.example/i/CODE",
        referral_note="双方各得 2000 万 tokens",
        console_url="https://demo.example/keys",
    )

    # When
    block = render_signup_table([provider])

    # Then
    assert "**这些是邀请链接**" in block
    assert "双方各得 2000 万 tokens" in block
    assert "不想走返利就用" in block


def test_platforms_without_a_referral_never_appear_in_the_signup_block() -> None:
    # Given
    plain = make_provider(console_url="https://demo.example/keys")

    # When
    block = render_signup_table([plain])

    # Then
    assert "立即注册" not in block
    assert "完整清单" in block


def test_the_reader_facing_summary_wins_over_the_technical_free_basis() -> None:
    # Given
    provider = make_provider(
        summary="人话说明",
        free_basis="目录返回的 pricing.prompt 与 pricing.completion 同时为 0",
        referral_url="https://demo.example/i/CODE",
        referral_note="双方各得 tokens",
        console_url="https://demo.example/keys",
    )

    # When
    block = render_signup_table([provider])

    # Then
    assert "人话说明" in block
    assert "pricing.prompt" not in block
