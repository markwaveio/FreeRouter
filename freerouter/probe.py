from __future__ import annotations

from typing import TYPE_CHECKING, Final

from freerouter.planning import direct_alias
from freerouter.state import HealthStatus, ProbeOutcome
from freerouter.transport import (
    HTTP_FORBIDDEN,
    HTTP_NOT_FOUND,
    HTTP_PAYMENT_REQUIRED,
    HTTP_TOO_MANY_REQUESTS,
    HTTP_UNAUTHORIZED,
    as_items,
    as_text,
    dig,
)

if TYPE_CHECKING:
    from collections.abc import Collection, Mapping
    from datetime import datetime, timedelta

    from freerouter.gateway import Gateway
    from freerouter.registry import Provider
    from freerouter.state import HealthState
    from freerouter.transport import Response

MAX_DETAIL: Final = 200

STATUS_OUTCOMES: Final[Mapping[int, ProbeOutcome]] = {
    HTTP_UNAUTHORIZED: ProbeOutcome.AUTH,
    HTTP_PAYMENT_REQUIRED: ProbeOutcome.EXHAUSTED,
    HTTP_FORBIDDEN: ProbeOutcome.AUTH,
    HTTP_NOT_FOUND: ProbeOutcome.MISSING,
    HTTP_TOO_MANY_REQUESTS: ProbeOutcome.THROTTLED,
}

KEYWORD_OUTCOMES: Final[tuple[tuple[ProbeOutcome, tuple[str, ...]], ...]] = (
    (
        ProbeOutcome.MISSING,
        (
            "model_not_found",
            "not found",
            "does not exist",
            "no such model",
            "unknown model",
            "decommissioned",
            "has been deprecated",
            "no longer available",
            "已下线",
            "不存在",
        ),
    ),
    (
        ProbeOutcome.EXHAUSTED,
        (
            "insufficient",
            "quota",
            "out of credit",
            "balance",
            "exceeded your current",
            "余额",
            "额度",
        ),
    ),
    (
        ProbeOutcome.THROTTLED,
        ("rate limit", "rate_limit", "too many requests", "请求过于频繁", "限流"),
    ),
    (
        ProbeOutcome.AUTH,
        ("invalid api key", "unauthorized", "authentication", "invalid token", "鉴权"),
    ),
)


def _keyword_outcome(text: str) -> ProbeOutcome | None:
    """Infer an outcome from the error text when the status code is not decisive."""
    lowered = text.lower()
    for outcome, needles in KEYWORD_OUTCOMES:
        if any(needle in lowered for needle in needles):
            return outcome
    return None


ERROR_PATHS: Final = ("error.message", "message", "detail", "msg")


def _detail(response: Response) -> str:
    """Pull the upstream error message out of the JSON body when there is one.

    Reading the decoded JSON rather than the raw bytes keeps non-ASCII messages
    intact even when the platform returns them as escaped unicode sequences.
    """
    payload = response.json()
    for path in ERROR_PATHS:
        message = as_text(dig(payload, path))
        if message:
            return " ".join(message.split())[:MAX_DETAIL]
    return " ".join(response.text.split())[:MAX_DETAIL]


def outcome_for(status: int, detail: str) -> ProbeOutcome:
    """Classify one upstream failure from its status code and message.

    Shared by the active probe and by passive observation of real traffic, so a
    model is judged the same way whether FreeRouter tested it or a user did.
    """
    return STATUS_OUTCOMES.get(status) or _keyword_outcome(detail) or ProbeOutcome.TRANSIENT


def classify(response: Response) -> tuple[ProbeOutcome, str]:
    """Turn one probe response into an outcome and a short human-readable reason."""
    detail = _detail(response)
    if response.ok:
        if as_items(dig(response.json(), "choices")):
            return ProbeOutcome.OK, "ok"
        return ProbeOutcome.TRANSIENT, f"200 但没有返回 choices: {detail}"
    return outcome_for(response.status, detail), f"HTTP {response.status}: {detail}"


def probe_one(gateway: Gateway, provider: Provider, model_id: str) -> tuple[ProbeOutcome, str]:
    """Send one real completion through the proxy and classify the result."""
    alias = direct_alias(provider.provider_id, model_id)
    return classify(gateway.chat(alias, provider.probe.prompt, provider.probe.max_tokens))


def probe_targets(
    state: HealthState,
    provider: Provider,
    now: datetime,
    *,
    recheck_after: timedelta,
    verified_by_traffic: Collection[str] = (),
) -> tuple[str, ...]:
    """Choose which of a provider's models to probe this cycle, newest and riskiest first.

    Real traffic is the cheapest health signal there is: a model that answered a
    user request needs no synthetic probe. Only three cases still need one — a model
    nobody has verified yet, a quarantined model whose backoff has expired, and a
    healthy model that has gone quiet long enough to have become stale. The
    per-provider cap then bounds even that, so verification never becomes the
    reason a free quota runs out.
    """
    if not provider.probe.enabled:
        return ()

    unknown: list[str] = []
    due: list[str] = []
    stale: list[str] = []
    for health in state.models.values():
        if health.provider != provider.provider_id or health.key in verified_by_traffic:
            continue
        if health.status is HealthStatus.UNKNOWN:
            unknown.append(health.model_id)
        elif health.status is HealthStatus.QUARANTINED:
            if health.retry_after is None or health.retry_after <= now:
                due.append(health.model_id)
        elif health.last_ok is None or now - health.last_ok >= recheck_after:
            stale.append(health.model_id)

    ordered = [*sorted(unknown), *sorted(due), *sorted(stale)]
    return tuple(ordered[: provider.probe.max_per_cycle])
