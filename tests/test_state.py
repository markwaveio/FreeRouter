from __future__ import annotations

from datetime import timedelta
from typing import TYPE_CHECKING

from freerouter.state import (
    EventKind,
    HealthState,
    HealthStatus,
    ProbeOutcome,
    append_events,
    clear_quarantine,
    load_state,
    observe,
    record_probe,
    save_state,
)
from tests.conftest import NOW, make_health, make_state

if TYPE_CHECKING:
    from pathlib import Path


def test_observe_adds_new_models_and_drops_vanished_ones() -> None:
    # Given
    state = make_state(make_health(model_id="alpha"), make_health(model_id="gone"))

    # When
    updated, events = observe(state, "demo", ["alpha", "fresh"], NOW)

    # Then
    assert set(updated.models) == {"demo::alpha", "demo::fresh"}
    kinds = {(event.kind, event.model_id) for event in events}
    assert (EventKind.ADDED, "fresh") in kinds
    assert (EventKind.REMOVED, "gone") in kinds


def test_observe_leaves_other_providers_alone() -> None:
    # Given
    state = make_state(make_health(provider="other", model_id="keep"))

    # When
    updated, events = observe(state, "demo", ["alpha"], NOW)

    # Then
    assert "other::keep" in updated.models
    assert all(event.provider == "demo" for event in events)


def test_repeated_failures_quarantine_then_a_success_revives() -> None:
    # Given
    health = make_health()

    # When
    for _ in range(2):
        health, event = record_probe(health, ProbeOutcome.TRANSIENT, "boom", NOW, threshold=3)
        assert event is None
    health, event = record_probe(health, ProbeOutcome.TRANSIENT, "boom", NOW, threshold=3)

    # Then
    assert health.status is HealthStatus.QUARANTINED
    assert not health.poolable
    assert event is not None
    assert event.kind is EventKind.QUARANTINED
    assert health.retry_after == NOW + timedelta(minutes=30)

    # When
    health, event = record_probe(health, ProbeOutcome.OK, "ok", NOW, threshold=3)

    # Then
    assert health.status is HealthStatus.HEALTHY
    assert health.consecutive_failures == 0
    assert event is not None
    assert event.kind is EventKind.REVIVED


def test_a_missing_model_is_quarantined_on_the_first_failure() -> None:
    # Given
    health = make_health(status=HealthStatus.HEALTHY)

    # When
    health, event = record_probe(health, ProbeOutcome.MISSING, "404 model not found", NOW)

    # Then
    assert health.status is HealthStatus.QUARANTINED
    assert event is not None
    assert event.kind is EventKind.QUARANTINED


def test_rate_limiting_is_not_counted_as_a_failure() -> None:
    # Given
    health = make_health(status=HealthStatus.HEALTHY)

    # When
    health, event = record_probe(health, ProbeOutcome.THROTTLED, "429", NOW)

    # Then
    assert health.status is HealthStatus.HEALTHY
    assert health.consecutive_failures == 0
    assert event is None


def test_quota_exhaustion_retries_within_the_hour() -> None:
    # Given
    health = make_health(status=HealthStatus.HEALTHY)

    # When
    health, _ = record_probe(health, ProbeOutcome.EXHAUSTED, "no credit", NOW, threshold=1)

    # Then
    assert health.retry_after == NOW + timedelta(hours=1)


def test_backoff_grows_but_stays_capped() -> None:
    # Given
    health = make_health()

    # When
    for _ in range(20):
        health, _ = record_probe(health, ProbeOutcome.TRANSIENT, "boom", NOW, threshold=1)

    # Then
    assert health.retry_after == NOW + timedelta(hours=12)


def test_state_round_trips_through_disk(tmp_path: Path) -> None:
    # Given
    state = make_state(make_health(status=HealthStatus.HEALTHY))
    path = tmp_path / "health.json"

    # When
    save_state(state, path, NOW)
    loaded = load_state(path)

    # Then
    assert loaded.models["demo::alpha"].status is HealthStatus.HEALTHY
    assert loaded.updated_at == NOW


def test_corrupt_state_file_falls_back_to_empty(tmp_path: Path) -> None:
    # Given
    path = tmp_path / "health.json"
    _ = path.write_text("not json", encoding="utf-8")

    # When
    loaded = load_state(path)

    # Then
    assert loaded == HealthState()


def test_changelog_is_append_only(tmp_path: Path) -> None:
    # Given
    path = tmp_path / "changelog.jsonl"
    _, events = observe(HealthState(), "demo", ["alpha"], NOW)

    # When
    append_events(path, events, NOW)
    append_events(path, events, NOW)

    # Then
    assert len(path.read_text(encoding="utf-8").strip().splitlines()) == 2


def test_recheck_clears_quarantine_and_backoff() -> None:
    """根因修好后，不该继续等一个已经不成立的退避。"""
    # Given
    state = make_state(
        make_health(model_id="broken", status=HealthStatus.QUARANTINED,
                    consecutive_failures=5, retry_after=NOW + timedelta(hours=12),
                    last_error="旧的报错"),
        make_health(model_id="fine", status=HealthStatus.HEALTHY),
    )

    # When
    updated, reset = clear_quarantine(state)

    # Then
    assert reset == 1
    broken = updated.models["demo::broken"]
    assert broken.status is HealthStatus.UNKNOWN
    assert broken.consecutive_failures == 0
    assert broken.retry_after is None
    assert broken.last_error is None
    assert updated.models["demo::fine"].status is HealthStatus.HEALTHY


def test_recheck_can_target_one_platform() -> None:
    # Given
    state = make_state(
        make_health(provider="a", model_id="x", status=HealthStatus.QUARANTINED),
        make_health(provider="b", model_id="y", status=HealthStatus.QUARANTINED),
    )

    # When
    updated, reset = clear_quarantine(state, "a")

    # Then
    assert reset == 1
    assert updated.models["a::x"].status is HealthStatus.UNKNOWN
    assert updated.models["b::y"].status is HealthStatus.QUARANTINED


def test_recheck_also_resets_a_healthy_model_that_is_accumulating_failures() -> None:
    # Given a model still in the pool but already failing twice
    state = make_state(
        make_health(status=HealthStatus.HEALTHY, consecutive_failures=2)
    )

    # When
    updated, reset = clear_quarantine(state)

    # Then
    assert reset == 1
    assert updated.models["demo::alpha"].consecutive_failures == 0
