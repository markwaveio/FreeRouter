from __future__ import annotations

import logging
import os
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from datetime import timedelta
from pathlib import Path
from typing import TYPE_CHECKING, Final

from freerouter.discovery import discover
from freerouter.errors import GatewayError, MissingMasterKeyError
from freerouter.gateway import Gateway
from freerouter.notify import send
from freerouter.planning import diff, plan_deployments
from freerouter.probe import probe_one, probe_targets
from freerouter.registry import load_providers
from freerouter.state import (
    Event,
    EventKind,
    HealthState,
    HealthStatus,
    ProbeOutcome,
    append_events,
    load_state,
    observe,
    record_probe,
    save_state,
    state_key,
    utcnow,
)
from freerouter.traffic import latest_observations

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence
    from datetime import date, datetime

    from freerouter.discovery import DiscoveryResult
    from freerouter.registry import Provider

LOGGER: Final = logging.getLogger("freerouter")

DEFAULT_INTERVAL: Final = 21600.0
DEFAULT_RECHECK_HOURS: Final = 24.0
DEFAULT_THRESHOLD: Final = 3
DEFAULT_OFFER_WARN_DAYS: Final = 14
DEFAULT_READY_TIMEOUT: Final = 300.0
DEFAULT_WORKERS: Final = 4
MIN_INTERVAL: Final = 300.0


def _number(env: Mapping[str, str], name: str, fallback: float) -> float:
    """Read a numeric environment variable, falling back when unset or malformed."""
    try:
        return float(env.get(name, "").strip() or fallback)
    except ValueError:
        LOGGER.warning("%s is not a number; using %s", name, fallback)
        return fallback


@dataclass(frozen=True, slots=True)
class Settings:
    master_key: str
    providers_dir: Path = Path("/app/providers")
    state_dir: Path = Path("/app/state")
    gateway_url: str = "http://litellm:4000"
    interval: float = DEFAULT_INTERVAL
    recheck_after: timedelta = timedelta(hours=DEFAULT_RECHECK_HOURS)
    threshold: int = DEFAULT_THRESHOLD
    webhook: str | None = None
    offer_warn_days: int = DEFAULT_OFFER_WARN_DAYS
    ready_timeout: float = DEFAULT_READY_TIMEOUT
    workers: int = DEFAULT_WORKERS

    @property
    def state_path(self) -> Path:
        """Return the path of the persisted health state."""
        return self.state_dir / "health.json"

    @property
    def changelog_path(self) -> Path:
        """Return the path of the append-only change log."""
        return self.state_dir / "changelog.jsonl"

    @classmethod
    def from_env(cls, env: Mapping[str, str] | None = None) -> Settings:
        """Build settings from the process environment."""
        source = os.environ if env is None else env
        master_key = source.get("LITELLM_MASTER_KEY", "").strip()
        if not master_key:
            raise MissingMasterKeyError
        return cls(
            master_key=master_key,
            providers_dir=Path(source.get("FREEROUTER_PROVIDERS_DIR", "/app/providers")),
            state_dir=Path(source.get("FREEROUTER_STATE_DIR", "/app/state")),
            gateway_url=source.get("FREEROUTER_GATEWAY_URL", "http://litellm:4000").rstrip("/"),
            interval=max(
                MIN_INTERVAL, _number(source, "FREEROUTER_REFRESH_INTERVAL", DEFAULT_INTERVAL)
            ),
            recheck_after=timedelta(
                hours=_number(source, "FREEROUTER_RECHECK_HOURS", DEFAULT_RECHECK_HOURS)
            ),
            threshold=int(_number(source, "FREEROUTER_FAILURE_THRESHOLD", DEFAULT_THRESHOLD)),
            webhook=source.get("FREEROUTER_NOTIFY_WEBHOOK", "").strip() or None,
            offer_warn_days=int(
                _number(source, "FREEROUTER_OFFER_WARN_DAYS", DEFAULT_OFFER_WARN_DAYS)
            ),
            ready_timeout=_number(source, "FREEROUTER_READY_TIMEOUT", DEFAULT_READY_TIMEOUT),
            workers=max(1, int(_number(source, "FREEROUTER_PROBE_WORKERS", DEFAULT_WORKERS))),
        )


@dataclass(frozen=True, slots=True)
class CycleContext:
    """Everything one cycle's stages share besides the gateway and the state."""

    now: datetime
    settings: Settings
    verified: frozenset[str] = frozenset()


@dataclass(frozen=True, slots=True)
class CycleReport:
    discovered: int = 0
    healthy: int = 0
    quarantined: int = 0
    probed: int = 0
    added: int = 0
    deleted: int = 0
    verified_by_traffic: int = 0
    events: tuple[Event, ...] = ()
    errors: tuple[str, ...] = field(default=())

    def summary(self) -> str:
        """Render a one-line operator summary of the cycle."""
        return (
            f"discovered={self.discovered} healthy={self.healthy} "
            f"quarantined={self.quarantined} traffic-verified={self.verified_by_traffic} "
            f"probed={self.probed} "
            f"added={self.added} deleted={self.deleted} "
            f"events={len(self.events)} errors={len(self.errors)}"
        )


NOTIFIABLE: Final = frozenset(
    {
        EventKind.ADDED,
        EventKind.REMOVED,
        EventKind.QUARANTINED,
        EventKind.REVIVED,
        EventKind.PROVIDER_ERROR,
        EventKind.OFFER_EXPIRING,
        EventKind.OFFER_EXPIRED,
    }
)


def _discover_all(
    providers: Sequence[Provider],
    env: Mapping[str, str],
    workers: int,
) -> tuple[tuple[Provider, DiscoveryResult], ...]:
    """Query every provider's catalog concurrently."""

    def run(provider: Provider) -> tuple[Provider, DiscoveryResult]:
        return provider, discover(provider, env)

    with ThreadPoolExecutor(max_workers=workers) as pool:
        return tuple(pool.map(run, providers))


def _ingest(
    state: HealthState,
    pairs: Sequence[tuple[Provider, DiscoveryResult]],
    now: datetime,
) -> tuple[HealthState, list[Event]]:
    """Fold discovery results into the health state, deduplicating provider errors."""
    events: list[Event] = []
    errors = dict(state.provider_errors)
    for provider, result in pairs:
        name = provider.provider_id
        if result.skipped is not None:
            # A skipped provider is one that is not configured at all — no credential,
            # paused, or retired. Its models must leave the pool. A provider whose
            # catalog merely failed is handled below and keeps everything it had.
            LOGGER.info("skip %s: %s", name, result.skipped)
            state, dropped = observe(state, name, (), now)
            events.extend(dropped)
            continue
        if result.error is not None:
            if errors.get(name) != result.error:
                events.append(
                    Event(kind=EventKind.PROVIDER_ERROR, provider=name, detail=result.error)
                )
            errors[name] = result.error
            LOGGER.warning("%s discovery failed: %s", name, result.error)
            continue
        _ = errors.pop(name, None)
        if result.dropped_by_cap:
            LOGGER.warning(
                "%s: max_models=%d reached, %d models not routed (%s)",
                name,
                provider.max_models,
                len(result.dropped_by_cap),
                ", ".join(result.dropped_by_cap[:5]),
            )
        state, seen = observe(state, name, result.models, now)
        events.extend(seen)
    return state.model_copy(update={"provider_errors": errors}), events


def apply_plan(
    gateway: Gateway,
    providers: Sequence[Provider],
    state: HealthState,
    env: Mapping[str, str],
) -> tuple[int, int, list[str]]:
    """Reconcile the proxy's live deployments with the plan, without restarting it."""
    errors: list[str] = []
    try:
        current = gateway.managed_ids()
    except GatewayError as error:
        return 0, 0, [str(error)]

    to_add, to_delete = diff(plan_deployments(providers, state, env), current)
    added = 0
    for deployment in to_add:
        try:
            gateway.add(deployment)
        except GatewayError as error:
            errors.append(str(error))
        else:
            added += 1

    deleted = 0
    for identifier in to_delete:
        try:
            gateway.delete(identifier)
        except GatewayError as error:
            errors.append(str(error))
        else:
            deleted += 1
    return added, deleted, errors


def observe_traffic(
    gateway: Gateway,
    providers: Sequence[Provider],
    state: HealthState,
    env: Mapping[str, str],
    context: CycleContext,
) -> tuple[HealthState, list[Event], frozenset[str]]:
    """Fold real request outcomes into health, so traffic replaces synthetic probes.

    Every model a user actually exercised is already verified for free. Returning
    those keys lets the probe stage skip them and spend its small quota budget on
    the models nobody has tested.
    """
    routes = {
        deployment.deployment_id: state_key(deployment.provider_id, deployment.model_id)
        for deployment in plan_deployments(providers, state, env)
    }
    try:
        entries = gateway.spend_logs(state.last_traffic_seen or context.now - timedelta(days=1))
    except GatewayError as error:
        LOGGER.warning("could not read the call log, falling back to probes: %s", error)
        return state, [], frozenset()

    observed = latest_observations(entries, routes, state.last_traffic_seen)
    models = dict(state.models)
    events: list[Event] = []
    for key, observation in observed.items():
        health = models.get(key)
        if health is None:
            continue
        updated, event = record_probe(
            health,
            observation.outcome,
            observation.detail,
            observation.at,
            threshold=context.settings.threshold,
        )
        models[key] = updated
        if event is not None:
            events.append(event)

    if observed:
        LOGGER.info("real traffic verified %d models; no probe needed for them", len(observed))
    return (
        state.model_copy(update={"models": models, "last_traffic_seen": context.now}),
        events,
        frozenset(observed),
    )


def _probe_provider(
    gateway: Gateway,
    provider: Provider,
    targets: Sequence[str],
) -> tuple[str, tuple[tuple[str, ProbeOutcome, str], ...]]:
    """Probe one provider's selected models sequentially to respect its rate limit."""
    outcomes: list[tuple[str, ProbeOutcome, str]] = []
    for model_id in targets:
        outcome, detail = probe_one(gateway, provider, model_id)
        LOGGER.info("probe %s/%s -> %s", provider.provider_id, model_id, outcome.value)
        outcomes.append((model_id, outcome, detail))
    return provider.provider_id, tuple(outcomes)


def _probe_all(
    gateway: Gateway,
    providers: Sequence[Provider],
    state: HealthState,
    context: CycleContext,
) -> tuple[HealthState, list[Event], int]:
    """Probe every provider's due models and fold the outcomes into the state."""
    plans = [
        (provider, targets)
        for provider in providers
        if (
            targets := probe_targets(
                state,
                provider,
                context.now,
                recheck_after=context.settings.recheck_after,
                verified_by_traffic=context.verified,
            )
        )
    ]
    if not plans:
        return state, [], 0

    def run(
        item: tuple[Provider, Sequence[str]],
    ) -> tuple[str, tuple[tuple[str, ProbeOutcome, str], ...]]:
        return _probe_provider(gateway, item[0], item[1])

    with ThreadPoolExecutor(max_workers=context.settings.workers) as pool:
        results = tuple(pool.map(run, plans))

    events: list[Event] = []
    models = dict(state.models)
    probed = 0
    for name, outcomes in results:
        for model_id, outcome, detail in outcomes:
            probed += 1
            health = models.get(state_key(name, model_id))
            if health is None:
                continue
            updated, event = record_probe(
                health, outcome, detail, context.now, threshold=context.settings.threshold
            )
            models[updated.key] = updated
            if event is not None:
                events.append(event)
    return state.model_copy(update={"models": models}), events, probed


def _offer_stage(remaining: int, warn_days: int) -> str:
    """Bucket an offer's remaining days into a notification stage."""
    if remaining < 0:
        return "expired"
    return "expiring" if remaining <= warn_days else "ok"


def _offer_events(
    providers: Sequence[Provider],
    state: HealthState,
    today: date,
    warn_days: int,
) -> tuple[HealthState, list[Event]]:
    """Emit one event per offer whose expiry stage changed since the last cycle."""
    stages = dict(state.offers)
    events: list[Event] = []
    for provider in providers:
        ends_on = provider.offer.ends_on
        if ends_on is None:
            _ = stages.pop(provider.provider_id, None)
            continue
        stage = _offer_stage((ends_on - today).days, warn_days)
        if stages.get(provider.provider_id) == stage:
            continue
        stages[provider.provider_id] = stage
        note = provider.offer.note or provider.name_zh
        if stage == "expired":
            events.append(
                Event(
                    kind=EventKind.OFFER_EXPIRED,
                    provider=provider.provider_id,
                    detail=f"限时活动已于 {ends_on} 结束：{note}",
                )
            )
        elif stage == "expiring":
            events.append(
                Event(
                    kind=EventKind.OFFER_EXPIRING,
                    provider=provider.provider_id,
                    detail=f"限时活动 {ends_on} 到期（剩 {(ends_on - today).days} 天）：{note}",
                )
            )
    return state.model_copy(update={"offers": stages}), events


def run_cycle(settings: Settings, env: Mapping[str, str] | None = None) -> CycleReport:
    """Run one full discover, probe, reconcile and notify cycle."""
    source = os.environ if env is None else env
    now = utcnow()
    providers = load_providers(settings.providers_dir)
    routable = [provider for provider in providers if provider.routable]
    gateway = Gateway(base_url=settings.gateway_url, master_key=settings.master_key)

    state = load_state(settings.state_path)
    state, events = _ingest(state, _discover_all(routable, source, settings.workers), now)

    first_added, first_deleted, first_errors = apply_plan(gateway, providers, state, source)

    context = CycleContext(now=now, settings=settings)
    state, traffic_events, verified = observe_traffic(gateway, providers, state, source, context)
    events.extend(traffic_events)

    probing = CycleContext(now=now, settings=settings, verified=verified)
    state, probe_events, probed = _probe_all(gateway, routable, state, probing)
    events.extend(probe_events)
    final_added, final_deleted, final_errors = apply_plan(gateway, providers, state, source)

    state, offer_events = _offer_events(providers, state, now.date(), settings.offer_warn_days)
    events.extend(offer_events)

    save_state(state, settings.state_path, now)
    append_events(settings.changelog_path, events, now)

    notifiable = [event for event in events if event.kind in NOTIFIABLE]
    failure = send(settings.webhook, "FreeRouter 免费模型池变更", notifiable)
    errors = [*first_errors, *final_errors, *([failure] if failure else [])]

    return CycleReport(
        discovered=len(state.models),
        healthy=sum(1 for h in state.models.values() if h.status is HealthStatus.HEALTHY),
        quarantined=sum(1 for h in state.models.values() if h.status is HealthStatus.QUARANTINED),
        probed=probed,
        verified_by_traffic=len(verified),
        added=first_added + final_added,
        deleted=first_deleted + final_deleted,
        events=tuple(events),
        errors=tuple(errors),
    )
