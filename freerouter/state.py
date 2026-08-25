from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from enum import StrEnum
from typing import TYPE_CHECKING, ClassVar, Final

from pydantic import BaseModel, ConfigDict, Field, ValidationError

if TYPE_CHECKING:
    from collections.abc import Iterable, Sequence
    from pathlib import Path

STATE_VERSION: Final = 1
DEFAULT_THRESHOLD: Final = 3
BACKOFF_BASE: Final = timedelta(minutes=30)
BACKOFF_CAP: Final = timedelta(hours=12)
QUOTA_BACKOFF: Final = timedelta(hours=1)
MAX_BACKOFF_STEPS: Final = 8
MAX_ERROR_CHARS: Final = 220


class HealthStatus(StrEnum):
    UNKNOWN = "unknown"
    HEALTHY = "healthy"
    QUARANTINED = "quarantined"


class ProbeOutcome(StrEnum):
    OK = "ok"
    THROTTLED = "throttled"
    MISSING = "missing"
    EXHAUSTED = "exhausted"
    AUTH = "auth"
    TRANSIENT = "transient"


class EventKind(StrEnum):
    ADDED = "added"
    REMOVED = "removed"
    QUARANTINED = "quarantined"
    REVIVED = "revived"
    PROVIDER_ERROR = "provider_error"
    OFFER_EXPIRING = "offer_expiring"
    OFFER_EXPIRED = "offer_expired"


@dataclass(frozen=True, slots=True)
class Event:
    kind: EventKind
    provider: str
    detail: str
    model_id: str | None = None

    def as_line(self, at: datetime) -> str:
        """Render the event as one JSON Lines record."""
        return json.dumps(
            {
                "ts": at.isoformat(),
                "event": self.kind.value,
                "provider": self.provider,
                "model": self.model_id,
                "detail": self.detail,
            },
            ensure_ascii=False,
        )

    def as_text(self) -> str:
        """Render the event as one human-readable line."""
        target = f"{self.provider}/{self.model_id}" if self.model_id else self.provider
        return f"[{self.kind.value}] {target} — {self.detail}"


class ModelHealth(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(frozen=True, extra="ignore")

    provider: str
    model_id: str
    status: HealthStatus = HealthStatus.UNKNOWN
    consecutive_failures: int = 0
    first_seen: datetime
    last_seen: datetime
    last_ok: datetime | None = None
    last_probe: datetime | None = None
    last_outcome: ProbeOutcome | None = None
    last_error: str | None = None
    retry_after: datetime | None = None

    @property
    def key(self) -> str:
        """Return the stable state key for this model."""
        return state_key(self.provider, self.model_id)

    @property
    def poolable(self) -> bool:
        """Report whether the model may join the shared free-router pool."""
        return self.status is HealthStatus.HEALTHY


class HealthState(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(frozen=True, extra="ignore")

    version: int = STATE_VERSION
    updated_at: datetime | None = None
    models: dict[str, ModelHealth] = Field(default_factory=dict)
    last_traffic_seen: datetime | None = None
    offers: dict[str, str] = Field(default_factory=dict)
    provider_errors: dict[str, str] = Field(default_factory=dict)


def state_key(provider_id: str, model_id: str) -> str:
    """Build the stable state key for a provider and model pair."""
    return f"{provider_id}::{model_id}"


def load_state(path: Path) -> HealthState:
    """Read the health state file, returning an empty state when it is absent or invalid."""
    if not path.exists():
        return HealthState()
    try:
        return HealthState.model_validate_json(path.read_bytes())
    except (ValidationError, OSError):
        return HealthState()


def save_state(state: HealthState, path: Path, now: datetime) -> None:
    """Write the health state file atomically."""
    path.parent.mkdir(parents=True, exist_ok=True)
    stamped = state.model_copy(update={"updated_at": now})
    temporary = path.with_suffix(f"{path.suffix}.tmp")
    _ = temporary.write_text(
        stamped.model_dump_json(indent=2, exclude_none=False),
        encoding="utf-8",
    )
    _ = temporary.replace(path)


def append_events(path: Path, events: Sequence[Event], now: datetime) -> None:
    """Append events to the JSON Lines changelog."""
    if not events:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        for event in events:
            _ = handle.write(f"{event.as_line(now)}\n")


def observe(
    state: HealthState,
    provider_id: str,
    model_ids: Iterable[str],
    now: datetime,
) -> tuple[HealthState, tuple[Event, ...]]:
    """Reconcile one provider's discovered models against the stored state."""
    discovered = set(model_ids)
    models = dict(state.models)
    events: list[Event] = []

    for model_id in sorted(discovered):
        key = state_key(provider_id, model_id)
        existing = models.get(key)
        if existing is None:
            models[key] = ModelHealth(
                provider=provider_id, model_id=model_id, first_seen=now, last_seen=now
            )
            events.append(
                Event(
                    kind=EventKind.ADDED,
                    provider=provider_id,
                    model_id=model_id,
                    detail="新发现",
                )
            )
        else:
            models[key] = existing.model_copy(update={"last_seen": now})

    for key, health in sorted(state.models.items()):
        if health.provider == provider_id and health.model_id not in discovered:
            del models[key]
            events.append(
                Event(
                    kind=EventKind.REMOVED,
                    provider=provider_id,
                    model_id=health.model_id,
                    detail="平台目录已不再提供",
                )
            )

    return state.model_copy(update={"models": models}), tuple(events)


def _backoff(failures: int, threshold: int, outcome: ProbeOutcome) -> timedelta:
    """Compute how long a quarantined model waits before the next probe."""
    if outcome is ProbeOutcome.EXHAUSTED:
        return QUOTA_BACKOFF
    steps = min(max(0, failures - threshold), MAX_BACKOFF_STEPS)
    return min(BACKOFF_BASE * (1 << steps), BACKOFF_CAP)


def record_probe(
    health: ModelHealth,
    outcome: ProbeOutcome,
    detail: str,
    now: datetime,
    *,
    threshold: int = DEFAULT_THRESHOLD,
) -> tuple[ModelHealth, Event | None]:
    """Fold one probe result into a model's health, returning any status-change event."""
    if outcome is ProbeOutcome.THROTTLED:
        updated = health.model_copy(
            update={"last_probe": now, "last_outcome": outcome, "last_error": detail}
        )
        return updated, None

    if outcome is ProbeOutcome.OK:
        updated = health.model_copy(
            update={
                "status": HealthStatus.HEALTHY,
                "consecutive_failures": 0,
                "last_probe": now,
                "last_ok": now,
                "last_outcome": outcome,
                "last_error": None,
                "retry_after": None,
            }
        )
        if health.status is HealthStatus.QUARANTINED:
            return updated, Event(
                kind=EventKind.REVIVED,
                provider=health.provider,
                model_id=health.model_id,
                detail="探测恢复正常，重新加入池",
            )
        return updated, None

    failures = health.consecutive_failures + 1
    effective = 1 if outcome is ProbeOutcome.MISSING else threshold
    quarantined = failures >= effective
    updated = health.model_copy(
        update={
            "status": HealthStatus.QUARANTINED if quarantined else health.status,
            "consecutive_failures": failures,
            "last_probe": now,
            "last_outcome": outcome,
            "last_error": detail[:MAX_ERROR_CHARS],
            "retry_after": now + _backoff(failures, effective, outcome) if quarantined else None,
        }
    )
    if quarantined and health.status is not HealthStatus.QUARANTINED:
        return updated, Event(
            kind=EventKind.QUARANTINED,
            provider=health.provider,
            model_id=health.model_id,
            detail=f"{outcome.value}: {detail[:120]}",
        )
    return updated, None


def clear_quarantine(state: HealthState, provider_id: str | None = None) -> tuple[HealthState, int]:
    """Reset failure counts and backoff so the next cycle re-probes those models.

    Use after fixing the underlying cause — a credential, an account binding, a
    platform quirk — instead of waiting out an exponential backoff that is now
    measuring a problem that no longer exists.
    """
    models = dict(state.models)
    reset = 0
    for key, health in state.models.items():
        if provider_id is not None and health.provider != provider_id:
            continue
        if health.status is HealthStatus.HEALTHY and health.consecutive_failures == 0:
            continue
        models[key] = health.model_copy(
            update={
                "status": HealthStatus.UNKNOWN,
                "consecutive_failures": 0,
                "retry_after": None,
                "last_error": None,
            }
        )
        reset += 1
    return state.model_copy(update={"models": models}), reset


def utcnow() -> datetime:
    """Return the current time in UTC."""
    return datetime.now(tz=UTC)
