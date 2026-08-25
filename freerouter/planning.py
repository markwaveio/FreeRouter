from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import TYPE_CHECKING, Final

from freerouter.registry import expand_env, resolve_extra_params

if TYPE_CHECKING:
    from collections.abc import Iterable, Mapping, Sequence

    from freerouter.registry import Provider
    from freerouter.state import HealthState
    from freerouter.transport import JsonValue

POOL_ALIAS: Final = "free-router"
DIRECT_NAMESPACE: Final = "fr"
MANAGED_PREFIX: Final = "fr-"
DEPLOYMENT_ID_CHARS: Final = 16


@dataclass(frozen=True, slots=True)
class Deployment:
    deployment_id: str
    alias: str
    provider_id: str
    model_id: str
    litellm_model: str
    tier: str
    api_base: str | None = None
    api_key_env: str | None = None
    rpm: int | None = None
    extra_params: tuple[tuple[str, JsonValue], ...] = ()

    def payload(self) -> dict[str, JsonValue]:
        """Render the LiteLLM ``/model/new`` request body for this deployment."""
        params: dict[str, JsonValue] = {"model": self.litellm_model}
        if self.api_key_env:
            params["api_key"] = f"os.environ/{self.api_key_env}"
        if self.api_base:
            params["api_base"] = self.api_base
        if self.rpm:
            params["rpm"] = self.rpm
        params.update(dict(self.extra_params))
        info: dict[str, JsonValue] = {
            "id": self.deployment_id,
            "input_cost_per_token": 0,
            "output_cost_per_token": 0,
            "cache_creation_input_token_cost": 0,
            "cache_read_input_token_cost": 0,
            "freerouter_provider": self.provider_id,
            "freerouter_tier": self.tier,
        }
        return {"model_name": self.alias, "litellm_params": params, "model_info": info}


def direct_alias(provider_id: str, model_id: str) -> str:
    """Build the always-addressable alias for one model, for example ``fr/groq/llama-3.1-8b``."""
    return f"{DIRECT_NAMESPACE}/{provider_id}/{model_id}"


def deployment_id(provider_id: str, model_id: str, alias: str, fingerprint: str = "") -> str:
    """Derive a stable id from the deployment's whole desired configuration.

    The fingerprint has to cover every field that ends up in ``litellm_params``, not
    just the model's identity. Otherwise editing a provider's request parameters
    leaves the id unchanged, the reconciler sees no difference, and the live
    deployment silently keeps serving the old configuration.
    """
    material = f"{provider_id}|{model_id}|{alias}|{fingerprint}"
    digest = hashlib.sha256(material.encode()).hexdigest()
    return f"{MANAGED_PREFIX}{digest[:DEPLOYMENT_ID_CHARS]}"


def is_managed(candidate: str) -> bool:
    """Report whether a LiteLLM deployment id belongs to FreeRouter."""
    return candidate.startswith(MANAGED_PREFIX)


def _build(provider: Provider, model_id: str, alias: str, api_base: str | None) -> Deployment:
    """Assemble one deployment record for a provider, model and alias."""
    litellm_model = f"{provider.litellm_prefix}/{model_id}"
    extra = tuple(sorted(resolve_extra_params(provider, model_id).items()))
    fingerprint = "|".join(
        [
            litellm_model,
            api_base or "",
            provider.credential or "",
            str(provider.limits.rpm or ""),
            repr(extra),
        ]
    )
    return Deployment(
        deployment_id=deployment_id(provider.provider_id, model_id, alias, fingerprint),
        alias=alias,
        provider_id=provider.provider_id,
        model_id=model_id,
        litellm_model=litellm_model,
        tier=provider.tier.value,
        api_base=api_base,
        api_key_env=provider.credential,
        rpm=provider.limits.rpm,
        extra_params=extra,
    )


def plan_provider(
    provider: Provider,
    state: HealthState,
    env: Mapping[str, str],
) -> tuple[Deployment, ...]:
    """Plan every deployment FreeRouter wants for one provider."""
    api_base = expand_env(provider.api_base, env) if provider.api_base else None
    if provider.api_base and api_base is None:
        return ()

    deployments: list[Deployment] = []
    for health in sorted(state.models.values(), key=lambda item: item.model_id):
        if health.provider != provider.provider_id:
            continue
        aliases = [direct_alias(provider.provider_id, health.model_id)]
        if health.poolable:
            aliases.extend([POOL_ALIAS, provider.alias])
        deployments.extend(_build(provider, health.model_id, alias, api_base) for alias in aliases)
    return tuple(deployments)


def plan_deployments(
    providers: Sequence[Provider],
    state: HealthState,
    env: Mapping[str, str],
) -> tuple[Deployment, ...]:
    """Plan the full desired deployment set across every routable provider."""
    planned: list[Deployment] = []
    for provider in providers:
        if provider.routable:
            planned.extend(plan_provider(provider, state, env))
    return tuple(planned)


def diff(
    desired: Iterable[Deployment],
    current: Iterable[str],
) -> tuple[tuple[Deployment, ...], tuple[str, ...]]:
    """Compute which deployments to add and which managed ids to delete."""
    wanted = {deployment.deployment_id: deployment for deployment in desired}
    live = {candidate for candidate in current if is_managed(candidate)}
    to_add = tuple(wanted[key] for key in sorted(wanted.keys() - live))
    to_delete = tuple(sorted(live - wanted.keys()))
    return to_add, to_delete
