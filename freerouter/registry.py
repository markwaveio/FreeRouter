from __future__ import annotations

import os
import re
from datetime import date
from enum import StrEnum
from fnmatch import fnmatchcase
from pathlib import Path
from typing import TYPE_CHECKING, ClassVar, Final

import yaml
from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

from freerouter.errors import (
    ListingWithoutFreeEvidenceError,
    ReferralWithoutDisclosureError,
    RegistryError,
)

if TYPE_CHECKING:
    from collections.abc import Iterable, Mapping, Sequence

ENV_PLACEHOLDER: Final = re.compile(r"\$\{([A-Z0-9_]+)\}")
DEFAULT_PROVIDERS_DIR: Final = Path("providers")


class DiscoveryMode(StrEnum):
    PRICED_CATALOG = "priced_catalog"
    LISTING = "listing"
    STATIC = "static"


class AuthMode(StrEnum):
    NONE = "none"
    BEARER = "bearer"
    QUERY_KEY = "query_key"


class ProviderStatus(StrEnum):
    ACTIVE = "active"
    PAUSED = "paused"
    RETIRED = "retired"
    WATCH = "watch"


class Tier(StrEnum):
    FREE = "free"
    TRIAL = "trial"
    OFFER = "offer"


class Limits(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(frozen=True, extra="forbid")

    rpm: int | None = None
    rpd: int | None = None
    note: str | None = None


class Offer(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(frozen=True, extra="forbid")

    starts_on: date | None = None
    ends_on: date | None = None
    note: str | None = None


class Discovery(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(frozen=True, extra="forbid")

    mode: DiscoveryMode
    url: str | None = None
    auth: AuthMode = AuthMode.NONE
    items_path: str = "data"
    id_path: str = "id"
    id_strip_prefix: str | None = None
    prompt_price_path: str | None = None
    price_value_path: str = "value"
    completion_price_path: str | None = None
    input_modalities_path: str | None = None
    output_modalities_path: str | None = None
    require_text_io: bool = False
    whole_catalog_is_free: bool = False
    deny_output_modalities: tuple[str, ...] = ()
    allow: tuple[str, ...] = ()
    deny: tuple[str, ...] = ()
    models: tuple[str, ...] = ()
    extra_models: tuple[str, ...] = ()


class ExtraParamsRule(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(frozen=True, extra="forbid")

    match: tuple[str, ...]
    params: dict[str, str | int | float | bool | None] = Field(default_factory=dict)


class ProbeSettings(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(frozen=True, extra="forbid")

    enabled: bool = True
    max_per_cycle: int = 6
    max_tokens: int = 16
    prompt: str = "ping"


class Provider(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(
        frozen=True,
        extra="forbid",
        populate_by_name=True,
    )

    provider_id: str = Field(alias="id")
    name: str
    name_zh: str
    status: ProviderStatus = ProviderStatus.ACTIVE
    tier: Tier = Tier.FREE
    region: str = "global"
    credential: str | None = None
    extra_credentials: tuple[str, ...] = ()
    litellm_prefix: str
    api_base: str | None = None
    docs_url: str
    console_url: str | None = None
    referral_url: str | None = None
    referral_note: str | None = None
    referral_requires_payment: bool = False
    summary: str | None = None
    free_basis: str
    free_basis_checked: date
    max_models: int = 20
    extra_params: dict[str, str | int | float | bool] = Field(default_factory=dict)
    extra_params_overrides: tuple[ExtraParamsRule, ...] = ()
    limits: Limits = Field(default_factory=Limits)
    offer: Offer = Field(default_factory=Offer)
    discovery: Discovery
    probe: ProbeSettings = Field(default_factory=ProbeSettings)
    retired_on: date | None = None
    retirement_note: str | None = None

    @model_validator(mode="after")
    def _referral_must_state_the_benefit(self) -> Provider:
        """Refuse an undisclosed referral link.

        A referral link that does not say what both sides get is not disclosure.
        Requiring the note here means every generated document can print it, so a
        reader always sees the arrangement rather than an unmarked URL.
        """
        if self.referral_url and not self.referral_note:
            raise ReferralWithoutDisclosureError(provider_id=self.provider_id)
        return self

    @model_validator(mode="after")
    def _listing_needs_free_evidence(self) -> Provider:
        """Refuse a listing provider that treats an entire catalog as free by default.

        Aggregators resell paid models through the same ``/models`` endpoint, so an
        empty allow list would silently route Claude or GPT as if it were free. The
        author must either name the free models or state that the whole catalog is
        on the free tier.
        """
        listing = self.discovery.mode is DiscoveryMode.LISTING
        if listing and not self.discovery.allow and not self.discovery.whole_catalog_is_free:
            raise ListingWithoutFreeEvidenceError(provider_id=self.provider_id)
        return self

    @property
    def alias(self) -> str:
        """Return the per-provider group alias, for example ``groq-free``."""
        return f"{self.provider_id}-free"

    @property
    def routable(self) -> bool:
        """Report whether this provider may contribute deployments to the pool."""
        return self.status is ProviderStatus.ACTIVE


def load_providers(directory: Path = DEFAULT_PROVIDERS_DIR) -> tuple[Provider, ...]:
    """Load and validate every ``*.yaml`` provider definition in ``directory``."""
    providers: list[Provider] = []
    for path in sorted(directory.glob("*.yaml")):
        try:
            with path.open(encoding="utf-8") as handle:
                providers.append(Provider.model_validate(yaml.safe_load(handle)))
        except (ValidationError, yaml.YAMLError) as error:
            raise RegistryError(path=str(path), reason=str(error)) from error
    return tuple(providers)


def expand_env(template: str, env: Mapping[str, str]) -> str | None:
    """Substitute ``${VAR}`` placeholders, returning None when a variable is unset."""
    missing: list[str] = []

    def replace(match: re.Match[str]) -> str:
        name = match.group(1)
        value = env.get(name, "").strip()
        if not value:
            missing.append(name)
        return value

    expanded = ENV_PLACEHOLDER.sub(replace, template)
    return None if missing else expanded


def credentials_for(provider: Provider, env: Mapping[str, str] | None = None) -> dict[str, str]:
    """Collect the provider's credential values, or an empty dict when any is missing."""
    source = os.environ if env is None else env
    required = [provider.credential] if provider.credential else []
    required.extend(provider.extra_credentials)
    resolved: dict[str, str] = {}
    for name in required:
        value = source.get(name, "").strip()
        if not value:
            return {}
        resolved[name] = value
    return resolved


def resolve_extra_params(provider: Provider, model_id: str) -> dict[str, str | int | float | bool]:
    """Resolve the request parameters one model needs on top of the provider defaults.

    Platform quirks are rarely uniform: on ModelScope some models return an empty
    body unless thinking is disabled, while the thinking-only variants reject that
    same parameter. A rule whose value is null drops the key entirely, which is how
    a model opts out of a provider-wide default.
    """
    resolved: dict[str, str | int | float | bool | None] = dict(provider.extra_params)
    for rule in provider.extra_params_overrides:
        if matches_any(model_id, rule.match):
            resolved.update(rule.params)
    return {name: value for name, value in resolved.items() if value is not None}


def matches_any(model_id: str, patterns: Sequence[str]) -> bool:
    """Report whether ``model_id`` matches any glob pattern, ignoring case."""
    lowered = model_id.lower()
    return any(fnmatchcase(lowered, pattern.lower()) for pattern in patterns)


def select_models(
    model_ids: Iterable[str],
    *,
    allow: Sequence[str],
    deny: Sequence[str],
    limit: int,
) -> tuple[tuple[str, ...], tuple[str, ...]]:
    """Apply allow, deny, and the per-provider cap.

    Returns the kept ids and the ids dropped by the cap so callers can log the
    truncation instead of hiding it.
    """
    filtered = sorted(
        {
            model_id
            for model_id in model_ids
            if (not allow or matches_any(model_id, allow)) and not matches_any(model_id, deny)
        }
    )
    return tuple(filtered[:limit]), tuple(filtered[limit:])
