from __future__ import annotations

import json
from datetime import timedelta

from freerouter.probe import classify, probe_targets
from freerouter.state import HealthStatus, ProbeOutcome
from freerouter.transport import Response
from tests.conftest import NOW, make_health, make_provider, make_state

OK_BODY = json.dumps({"choices": [{"message": {"content": "ok"}}]}).encode()


def _error(status: int, message: str) -> Response:
    body = json.dumps({"error": {"message": message}}, ensure_ascii=False).encode()
    return Response(status=status, body=body)


def test_a_real_completion_counts_as_healthy() -> None:
    assert classify(Response(status=200, body=OK_BODY))[0] is ProbeOutcome.OK


def test_a_200_without_choices_is_treated_as_transient() -> None:
    assert classify(Response(status=200, body=b"{}"))[0] is ProbeOutcome.TRANSIENT


def test_status_codes_map_to_outcomes() -> None:
    assert classify(_error(429, "slow down"))[0] is ProbeOutcome.THROTTLED
    assert classify(_error(401, "nope"))[0] is ProbeOutcome.AUTH
    assert classify(_error(402, "pay"))[0] is ProbeOutcome.EXHAUSTED
    assert classify(_error(404, "gone"))[0] is ProbeOutcome.MISSING


def test_wrapped_upstream_errors_are_read_from_the_message() -> None:
    outcome, detail = classify(_error(400, "The model `x` does not exist"))
    assert outcome is ProbeOutcome.MISSING
    assert detail == "HTTP 400: The model `x` does not exist"
    assert classify(_error(500, "Insufficient balance"))[0] is ProbeOutcome.EXHAUSTED
    assert classify(_error(500, "rate limit reached"))[0] is ProbeOutcome.THROTTLED
    assert classify(_error(400, "该模型已下线"))[0] is ProbeOutcome.MISSING
    escaped = Response(status=400, body=json.dumps({"error": {"message": "该模型已下线"}}).encode())
    assert classify(escaped)[0] is ProbeOutcome.MISSING


def test_a_network_failure_is_transient_not_fatal() -> None:
    assert classify(Response(status=0, body=b"connection refused"))[0] is ProbeOutcome.TRANSIENT


def test_never_probed_models_come_first_then_due_quarantines_then_stale() -> None:
    # Given
    provider = make_provider(probe={"max_per_cycle": 3})
    healthy = HealthStatus.HEALTHY
    out = HealthStatus.QUARANTINED
    state = make_state(
        make_health(model_id="stale", status=healthy, last_ok=NOW - timedelta(days=3)),
        make_health(model_id="fresh", status=healthy, last_ok=NOW),
        make_health(model_id="due", status=out, retry_after=NOW - timedelta(hours=1)),
        make_health(model_id="waiting", status=out, retry_after=NOW + timedelta(hours=5)),
        make_health(model_id="new"),
    )

    # When
    targets = probe_targets(state, provider, NOW, recheck_after=timedelta(hours=24))

    # Then
    assert targets == ("new", "due", "stale")


def test_the_per_provider_cap_bounds_probe_traffic() -> None:
    # Given
    provider = make_provider(probe={"max_per_cycle": 2})
    state = make_state(*(make_health(model_id=f"m{index}") for index in range(10)))

    # When
    targets = probe_targets(state, provider, NOW, recheck_after=timedelta(hours=24))

    # Then
    assert len(targets) == 2


def test_probing_can_be_disabled_per_provider() -> None:
    # Given
    provider = make_provider(probe={"enabled": False})
    state = make_state(make_health())

    # When / Then
    assert probe_targets(state, provider, NOW, recheck_after=timedelta(hours=24)) == ()


def test_models_verified_by_real_traffic_are_not_probed_again() -> None:
    """真实调用已经证明模型可用，再花额度探测一遍是浪费。"""
    # Given
    provider = make_provider(probe={"max_per_cycle": 5})
    state = make_state(
        make_health(model_id="used-by-traffic"),
        make_health(model_id="never-touched"),
    )

    # When
    targets = probe_targets(
        state,
        provider,
        NOW,
        recheck_after=timedelta(hours=24),
        verified_by_traffic={"demo::used-by-traffic"},
    )

    # Then
    assert targets == ("never-touched",)


def test_staleness_is_measured_from_the_last_success_not_the_last_attempt() -> None:
    # Given a model probed recently but whose last success is old
    provider = make_provider(probe={"max_per_cycle": 5})
    state = make_state(
        make_health(
            model_id="tried-but-never-succeeded",
            status=HealthStatus.HEALTHY,
            last_probe=NOW,
            last_ok=NOW - timedelta(days=5),
        )
    )

    # When
    targets = probe_targets(state, provider, NOW, recheck_after=timedelta(hours=24))

    # Then
    assert targets == ("tried-but-never-succeeded",)
