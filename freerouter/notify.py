from __future__ import annotations

from typing import TYPE_CHECKING, Final

from freerouter.transport import request

if TYPE_CHECKING:
    from collections.abc import Sequence

    from freerouter.state import Event
    from freerouter.transport import JsonValue

MAX_LINES: Final = 30
MAX_CHARS: Final = 1800
NOTIFY_TIMEOUT: Final = 15.0


def render(title: str, events: Sequence[Event]) -> str:
    """Render a change summary, truncating long bursts instead of flooding the channel."""
    lines = [event.as_text() for event in events[:MAX_LINES]]
    if len(events) > MAX_LINES:
        lines.append(f"…以及另外 {len(events) - MAX_LINES} 条变更")
    body = "\n".join([title, *lines])
    return body if len(body) <= MAX_CHARS else f"{body[:MAX_CHARS]}…"


def build_payload(url: str, text: str) -> JsonValue:
    """Shape the webhook body for the destination that ``url`` points at."""
    host = url.lower()
    if "open.feishu.cn" in host or "larksuite.com" in host:
        return {"msg_type": "text", "content": {"text": text}}
    if "qyapi.weixin.qq.com" in host or "oapi.dingtalk.com" in host:
        return {"msgtype": "text", "text": {"content": text}}
    if "hooks.slack.com" in host:
        return {"text": text}
    if "discord.com/api/webhooks" in host or "discordapp.com/api/webhooks" in host:
        return {"content": text}
    return {"text": text}


def send(url: str | None, title: str, events: Sequence[Event]) -> str | None:
    """Post a change summary to the configured webhook, returning an error string on failure."""
    if not url or not events:
        return None
    response = request(
        url,
        method="POST",
        payload=build_payload(url, render(title, events)),
        timeout=NOTIFY_TIMEOUT,
    )
    if response.ok:
        return None
    return f"webhook HTTP {response.status}: {response.text[:160]}"
