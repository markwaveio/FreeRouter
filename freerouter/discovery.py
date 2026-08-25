from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from freerouter.registry import (
    AuthMode,
    DiscoveryMode,
    ProviderStatus,
    credentials_for,
    expand_env,
    select_models,
)
from freerouter.transport import (
    as_items,
    as_price,
    as_strings,
    as_text,
    dig,
    request,
)

if TYPE_CHECKING:
    from collections.abc import Mapping

    from freerouter.registry import Discovery, Provider
    from freerouter.transport import JsonValue

TEXT_MODALITY = "text"


@dataclass(frozen=True, slots=True)
class DiscoveryResult:
    provider_id: str
    models: tuple[str, ...] = ()
    dropped_by_cap: tuple[str, ...] = ()
    skipped: str | None = None
    error: str | None = None

    @property
    def usable(self) -> bool:
        """Report whether the provider produced a routable model list."""
        return self.skipped is None and self.error is None


def _is_zero_price(value: JsonValue, value_path: str) -> bool | None:
    """Decide whether a price field is zero, returning None when it is unreadable."""
    if isinstance(value, list):
        if not value:
            return None
        rates = [
            as_price(dig(item, value_path)) if isinstance(item, dict) else as_price(item)
            for item in value
        ]
        if any(rate is None for rate in rates):
            return None
        return all(rate == 0 for rate in rates)
    price = as_price(value)
    return None if price is None else price == 0


def _is_free(item: JsonValue, discovery: Discovery) -> bool:
    """Apply the zero-price rule to one catalog entry."""
    if discovery.prompt_price_path is None or discovery.completion_price_path is None:
        return False
    prompt = _is_zero_price(dig(item, discovery.prompt_price_path), discovery.price_value_path)
    completion = _is_zero_price(
        dig(item, discovery.completion_price_path), discovery.price_value_path
    )
    return prompt is True and completion is True


def _is_text_model(item: JsonValue, discovery: Discovery) -> bool:
    """Apply the modality rules so media generators never enter a chat-completion pool.

    A zero prompt and completion price does not make a model free when it also
    bills per generated second or image, so any model that can emit a denied
    output modality is rejected even when its token prices are zero.
    """
    if discovery.input_modalities_path is None or discovery.output_modalities_path is None:
        return True
    outputs = as_strings(dig(item, discovery.output_modalities_path))
    if any(modality in outputs for modality in discovery.deny_output_modalities):
        return False
    if not discovery.require_text_io:
        return True
    inputs = as_strings(dig(item, discovery.input_modalities_path))
    return TEXT_MODALITY in inputs and TEXT_MODALITY in outputs


def _model_ids(payload: JsonValue, discovery: Discovery) -> tuple[str, ...]:
    """Extract the candidate model ids from a catalog payload."""
    collected: list[str] = []
    for item in as_items(dig(payload, discovery.items_path)):
        model_id = as_text(dig(item, discovery.id_path))
        if model_id is None:
            continue
        if discovery.id_strip_prefix and model_id.startswith(discovery.id_strip_prefix):
            model_id = model_id[len(discovery.id_strip_prefix) :]
        if discovery.mode is DiscoveryMode.PRICED_CATALOG and not _is_free(item, discovery):
            continue
        if not _is_text_model(item, discovery):
            continue
        collected.append(model_id)
    return tuple(collected)


def _catalog_request(
    discovery: Discovery,
    secrets: Mapping[str, str],
    credential: str | None,
) -> tuple[str, dict[str, str]] | None:
    """Build the catalog URL and headers, or None when the URL cannot be resolved."""
    if discovery.url is None:
        return None
    url = expand_env(discovery.url, secrets)
    if url is None:
        return None
    key = secrets.get(credential or "", "")
    headers: dict[str, str] = {}
    if discovery.auth is AuthMode.BEARER and key:
        headers["Authorization"] = f"Bearer {key}"
    if discovery.auth is AuthMode.QUERY_KEY and key:
        separator = "&" if "?" in url else "?"
        url = f"{url}{separator}key={key}"
    return url, headers


def _skip_reason(
    provider: Provider,
    secrets: Mapping[str, str],
    *,
    require_credentials: bool,
) -> str | None:
    """Return why the provider must be skipped this cycle, or None to proceed."""
    if provider.status is ProviderStatus.RETIRED:
        return "retired"
    if not provider.routable:
        return provider.status.value
    if require_credentials and provider.credential and not secrets:
        return "missing " + ", ".join([provider.credential, *provider.extra_credentials])
    return None


def _finish(
    provider: Provider,
    model_ids: tuple[str, ...],
) -> tuple[tuple[str, ...], tuple[str, ...]]:
    """Apply allow, deny and the cap, then append the always-on extra models."""
    kept, dropped = select_models(
        model_ids,
        allow=provider.discovery.allow,
        deny=provider.discovery.deny,
        limit=provider.max_models,
    )
    return tuple(sorted(set(kept) | set(provider.discovery.extra_models))), dropped


def _discover_static(provider: Provider) -> DiscoveryResult:
    """Resolve a hand-maintained model list without contacting the platform."""
    kept, dropped = _finish(provider, provider.discovery.models)
    return DiscoveryResult(provider_id=provider.provider_id, models=kept, dropped_by_cap=dropped)


def _discover_catalog(provider: Provider, secrets: Mapping[str, str]) -> DiscoveryResult:
    """Resolve the model list from the platform's live catalog endpoint."""
    resolved = _catalog_request(provider.discovery, secrets, provider.credential)
    if resolved is None:
        return DiscoveryResult(
            provider_id=provider.provider_id, error="catalog URL could not be resolved"
        )

    url, headers = resolved
    response = request(url, headers=headers)
    if not response.ok:
        return DiscoveryResult(
            provider_id=provider.provider_id,
            error=f"catalog HTTP {response.status}: {response.text[:160]}",
        )

    kept, dropped = _finish(provider, _model_ids(response.json(), provider.discovery))
    if not kept:
        return DiscoveryResult(
            provider_id=provider.provider_id,
            dropped_by_cap=dropped,
            error="catalog returned no models matching the free-model rules",
        )
    return DiscoveryResult(provider_id=provider.provider_id, models=kept, dropped_by_cap=dropped)


def discover(
    provider: Provider,
    env: Mapping[str, str] | None = None,
    *,
    require_credentials: bool = True,
) -> DiscoveryResult:
    """Resolve the current free-model list for one provider."""
    secrets = credentials_for(provider, env)
    reason = _skip_reason(provider, secrets, require_credentials=require_credentials)
    if reason is not None:
        return DiscoveryResult(provider_id=provider.provider_id, skipped=reason)
    if provider.discovery.mode is DiscoveryMode.STATIC:
        return _discover_static(provider)
    return _discover_catalog(provider, secrets)
