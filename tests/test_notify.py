from __future__ import annotations

from freerouter.notify import build_payload, render
from freerouter.state import Event, EventKind

EVENTS = (
    Event(kind=EventKind.ADDED, provider="groq", model_id="llama-9", detail="新发现"),
    Event(kind=EventKind.QUARANTINED, provider="groq", model_id="old-1", detail="missing: 404"),
)


def test_feishu_and_wecom_get_their_native_shapes() -> None:
    assert build_payload("https://open.feishu.cn/open-apis/bot/v2/hook/x", "t") == {
        "msg_type": "text",
        "content": {"text": "t"},
    }
    assert build_payload("https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=x", "t") == {
        "msgtype": "text",
        "text": {"content": "t"},
    }


def test_slack_discord_and_generic_shapes() -> None:
    assert build_payload("https://hooks.slack.com/services/x", "t") == {"text": "t"}
    assert build_payload("https://discord.com/api/webhooks/1/x", "t") == {"content": "t"}
    assert build_payload("https://example.com/hook", "t") == {"text": "t"}


def test_render_lists_every_change_with_its_target() -> None:
    # When
    text = render("变更", EVENTS)

    # Then
    assert "groq/llama-9" in text
    assert "[quarantined] groq/old-1" in text


def test_render_truncates_a_flood_instead_of_spamming() -> None:
    # Given
    many = tuple(
        Event(kind=EventKind.ADDED, provider="p", model_id=f"m{index}", detail="新发现")
        for index in range(100)
    )

    # When
    text = render("变更", many)

    # Then
    assert "另外 70 条变更" in text
    assert len(text) <= 1801
