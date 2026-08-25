from __future__ import annotations

from freerouter.planning import (
    POOL_ALIAS,
    deployment_id,
    diff,
    direct_alias,
    is_managed,
    plan_deployments,
)
from freerouter.state import HealthStatus
from tests.conftest import make_health, make_provider, make_state

ENV = {"DEMO_API_KEY": "secret"}


def test_healthy_models_get_the_pool_the_provider_and_the_direct_alias() -> None:
    # Given
    provider = make_provider()
    state = make_state(make_health(status=HealthStatus.HEALTHY))

    # When
    plan = plan_deployments([provider], state, ENV)

    # Then
    assert {entry.alias for entry in plan} == {POOL_ALIAS, "demo-free", "fr/demo/alpha"}
    assert all(entry.litellm_model == "openai/alpha" for entry in plan)
    assert all(entry.api_base == "https://demo.example/v1" for entry in plan)
    assert all(entry.api_key_env == "DEMO_API_KEY" for entry in plan)


def test_unverified_and_quarantined_models_stay_out_of_the_shared_pool() -> None:
    # Given
    provider = make_provider()
    state = make_state(
        make_health(model_id="new"),
        make_health(model_id="broken", status=HealthStatus.QUARANTINED),
    )

    # When
    aliases = {entry.alias for entry in plan_deployments([provider], state, ENV)}

    # Then
    assert aliases == {"fr/demo/new", "fr/demo/broken"}
    assert POOL_ALIAS not in aliases


def test_a_provider_missing_a_templated_variable_plans_nothing() -> None:
    # Given
    provider = make_provider(
        api_base="https://demo.example/${DEMO_ACCOUNT_ID}/v1",
        extra_credentials=["DEMO_ACCOUNT_ID"],
    )
    state = make_state(make_health(status=HealthStatus.HEALTHY))

    # When
    plan = plan_deployments([provider], state, ENV)

    # Then
    assert plan == ()


def test_retired_providers_are_never_planned() -> None:
    # Given
    provider = make_provider(status="retired")
    state = make_state(make_health(status=HealthStatus.HEALTHY))

    # When / Then
    assert plan_deployments([provider], state, ENV) == ()


def test_deployment_ids_are_stable_and_recognisable() -> None:
    # Given / When
    first = deployment_id("demo", "alpha", POOL_ALIAS)
    second = deployment_id("demo", "alpha", POOL_ALIAS)
    other = deployment_id("demo", "alpha", "demo-free")

    # Then
    assert first == second
    assert first != other
    assert is_managed(first)
    assert not is_managed("some-user-model")


def test_diff_adds_missing_and_removes_stale_without_touching_user_models() -> None:
    # Given
    provider = make_provider()
    state = make_state(make_health(status=HealthStatus.HEALTHY))
    desired = plan_deployments([provider], state, ENV)
    stale = deployment_id("demo", "removed-model", POOL_ALIAS)
    current = [stale, "user-owned-deployment"]

    # When
    to_add, to_delete = diff(desired, current)

    # Then
    assert len(to_add) == len(desired)
    assert to_delete == (stale,)


def test_diff_is_idempotent_once_applied() -> None:
    # Given
    provider = make_provider()
    state = make_state(make_health(status=HealthStatus.HEALTHY))
    desired = plan_deployments([provider], state, ENV)

    # When
    to_add, to_delete = diff(desired, [entry.deployment_id for entry in desired])

    # Then
    assert to_add == ()
    assert to_delete == ()


def test_payload_marks_the_deployment_free_and_traceable() -> None:
    # Given
    provider = make_provider(limits={"rpm": 20})
    state = make_state(make_health(status=HealthStatus.HEALTHY))
    entry = next(e for e in plan_deployments([provider], state, ENV) if e.alias == POOL_ALIAS)

    # When
    payload = entry.payload()

    # Then
    assert payload["model_name"] == POOL_ALIAS
    assert payload["litellm_params"] == {
        "model": "openai/alpha",
        "api_key": "os.environ/DEMO_API_KEY",
        "api_base": "https://demo.example/v1",
        "rpm": 20,
    }
    assert payload["model_info"] == {
        "id": entry.deployment_id,
        "input_cost_per_token": 0,
        "output_cost_per_token": 0,
        "cache_creation_input_token_cost": 0,
        "cache_read_input_token_cost": 0,
        "freerouter_provider": "demo",
        "freerouter_tier": "free",
    }


def test_direct_alias_keeps_the_platform_model_id_addressable() -> None:
    assert direct_alias("openrouter", "z-ai/glm-5.2:free") == "fr/openrouter/z-ai/glm-5.2:free"


def test_changing_request_parameters_forces_the_deployment_to_be_replaced() -> None:
    """改了平台请求参数，线上部署必须跟着换，不能悄悄留着旧配置。"""
    # Given
    state = make_state(make_health(status=HealthStatus.HEALTHY))
    before = plan_deployments([make_provider()], state, ENV)
    after = plan_deployments(
        [make_provider(extra_params={"enable_thinking": False})], state, ENV
    )

    # When
    to_add, to_delete = diff(after, [entry.deployment_id for entry in before])

    # Then
    assert len(to_add) == len(after)
    assert len(to_delete) == len(before)


def test_per_model_rules_override_the_provider_default() -> None:
    # Given a provider whose thinking-only variant must not receive the flag
    provider = make_provider(
        extra_params={"enable_thinking": False},
        extra_params_overrides=[
            {"match": ["*-thinking"], "params": {"enable_thinking": None}}
        ],
        discovery={"mode": "static", "models": ["base", "big-thinking"]},
    )
    state = make_state(
        make_health(model_id="base", status=HealthStatus.HEALTHY),
        make_health(model_id="big-thinking", status=HealthStatus.HEALTHY),
    )

    # When
    plan = {e.model_id: dict(e.extra_params) for e in plan_deployments([provider], state, ENV)}

    # Then
    assert plan["base"] == {"enable_thinking": False}
    assert plan["big-thinking"] == {}


def test_request_parameters_reach_the_litellm_payload() -> None:
    # Given
    provider = make_provider(extra_params={"enable_thinking": False})
    state = make_state(make_health(status=HealthStatus.HEALTHY))

    # When
    payload = next(iter(plan_deployments([provider], state, ENV))).payload()

    # Then
    params = payload["litellm_params"]
    assert isinstance(params, dict)
    assert params["enable_thinking"] is False
