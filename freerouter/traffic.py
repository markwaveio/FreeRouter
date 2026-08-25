from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Final

from freerouter.gateway import PROBE_TAG
from freerouter.probe import outcome_for
from freerouter.state import ProbeOutcome
from freerouter.transport import as_strings, as_text, dig

if TYPE_CHECKING:
    from collections.abc import Iterable, Mapping

    from freerouter.transport import JsonValue

MAX_DETAIL: Final = 200
SUCCESS_STATUS: Final = "success"


@dataclass(frozen=True, slots=True)
class Observation:
    deployment_id: str
    at: datetime
    outcome: ProbeOutcome
    detail: str


def _parse_time(value: str | None) -> datetime | None:
    """Parse a LiteLLM log timestamp, treating a naive value as UTC."""
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)


def _observation(entry: JsonValue) -> Observation | None:
    """Turn one spend-log record into a health observation, or None if unusable."""
    deployment_id = as_text(dig(entry, "model_id"))
    at = _parse_time(as_text(dig(entry, "startTime")))
    if deployment_id is None or at is None:
        return None
    if PROBE_TAG in as_strings(dig(entry, "request_tags")):
        return None

    if as_text(dig(entry, "status")) == SUCCESS_STATUS:
        return Observation(
            deployment_id=deployment_id, at=at, outcome=ProbeOutcome.OK, detail="真实调用成功"
        )

    error = dig(entry, "metadata.error_information")
    code = as_text(dig(error, "error_code")) or ""
    message = " ".join((as_text(dig(error, "error_message")) or "").split())[:MAX_DETAIL]
    status = int(code) if code.isdigit() else 0
    return Observation(
        deployment_id=deployment_id,
        at=at,
        outcome=outcome_for(status, message),
        detail=f"真实调用失败 HTTP {status or '?'}: {message}",
    )


def latest_observations(
    entries: Iterable[JsonValue],
    routes: Mapping[str, str],
    since: datetime | None,
) -> dict[str, Observation]:
    """Fold the call log into at most one observation per managed model.

    ``routes`` maps a deployment id to a state key. Entries at or before ``since``
    are ignored so a failure recorded once is never counted again on a later cycle.
    """
    newest: dict[str, Observation] = {}
    for entry in entries:
        observed = _observation(entry)
        if observed is None or (since is not None and observed.at <= since):
            continue
        key = routes.get(observed.deployment_id)
        if key is None:
            continue
        current = newest.get(key)
        if current is None or observed.at > current.at:
            newest[key] = observed
    return newest
