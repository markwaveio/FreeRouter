from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING

from freerouter.state import ProbeOutcome
from freerouter.traffic import latest_observations

if TYPE_CHECKING:
    from freerouter.transport import JsonValue

ROUTES = {"fr-aaa": "demo::alpha", "fr-bbb": "demo::beta"}
T0 = datetime(2026, 8, 25, 10, 0, tzinfo=UTC)
T1 = datetime(2026, 8, 25, 11, 0, tzinfo=UTC)


def _entry(
    deployment: str,
    when: datetime,
    status: str = "success",
    *,
    code: str = "",
    message: str = "",
    tags: list[JsonValue] | None = None,
) -> JsonValue:
    return {
        "model_id": deployment,
        "startTime": when.isoformat(),
        "status": status,
        "request_tags": tags or [],
        "metadata": {"error_information": {"error_code": code, "error_message": message}},
    }


def test_a_successful_call_counts_as_a_health_check() -> None:
    # When
    observed = latest_observations([_entry("fr-aaa", T0)], ROUTES, None)

    # Then
    assert observed["demo::alpha"].outcome is ProbeOutcome.OK


def test_real_failures_are_classified_the_same_way_probes_are() -> None:
    # Given LiteLLM records the upstream status code and message
    entries = [
        _entry("fr-aaa", T0, "failure", code="429", message="rate limit"),
        _entry("fr-bbb", T0, "failure", code="404", message="model not found"),
    ]

    # When
    observed = latest_observations(entries, ROUTES, None)

    # Then
    assert observed["demo::alpha"].outcome is ProbeOutcome.THROTTLED
    assert observed["demo::beta"].outcome is ProbeOutcome.MISSING


def test_only_the_newest_outcome_per_model_is_kept() -> None:
    # Given a model that failed and then recovered
    entries = [
        _entry("fr-aaa", T0, "failure", code="500", message="boom"),
        _entry("fr-aaa", T1),
    ]

    # When
    observed = latest_observations(entries, ROUTES, None)

    # Then
    assert observed["demo::alpha"].outcome is ProbeOutcome.OK
    assert observed["demo::alpha"].at == T1


def test_the_watermark_stops_one_failure_being_counted_every_cycle() -> None:
    # Given an entry already folded in on an earlier cycle
    entries = [_entry("fr-aaa", T0, "failure", code="500", message="boom")]

    # When
    assert latest_observations(entries, ROUTES, None)
    replayed = latest_observations(entries, ROUTES, T0)

    # Then
    assert replayed == {}


def test_freerouter_own_probes_are_not_double_counted() -> None:
    # Given the refresher's probe already went through record_probe
    entries = [_entry("fr-aaa", T0, tags=["freerouter-probe"])]

    # When / Then
    assert latest_observations(entries, ROUTES, None) == {}


def test_deployments_freerouter_does_not_manage_are_ignored() -> None:
    # Given traffic to a model the user added themselves
    entries = [_entry("user-owned-deployment", T0)]

    # When / Then
    assert latest_observations(entries, ROUTES, None) == {}


def test_malformed_records_never_break_a_cycle() -> None:
    # Given
    entries: list[JsonValue] = [
        {"model_id": "fr-aaa"},
        {"startTime": T0.isoformat()},
        {"model_id": "fr-aaa", "startTime": "not-a-date"},
        "nonsense",
        None,
    ]

    # When / Then
    assert latest_observations(entries, ROUTES, None) == {}
