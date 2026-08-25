from __future__ import annotations

from dataclasses import dataclass

from typing_extensions import override


@dataclass(frozen=True, slots=True)
class RegistryError(RuntimeError):
    path: str
    reason: str

    @override
    def __str__(self) -> str:
        return f"invalid provider file {self.path}: {self.reason}"


@dataclass(frozen=True, slots=True)
class GatewayError(RuntimeError):
    action: str
    status: int
    body: str

    @override
    def __str__(self) -> str:
        return f"LiteLLM {self.action} returned HTTP {self.status}: {self.body[:200]}"


@dataclass(frozen=True, slots=True)
class MissingMasterKeyError(RuntimeError):
    @override
    def __str__(self) -> str:
        return "Set LITELLM_MASTER_KEY before running the FreeRouter refresher"


@dataclass(frozen=True, slots=True)
class UnsupportedUrlError(ValueError):
    url: str

    @override
    def __str__(self) -> str:
        return f"only http and https URLs are allowed, got {self.url!r}"


@dataclass(frozen=True, slots=True)
class ListingWithoutFreeEvidenceError(ValueError):
    provider_id: str

    @override
    def __str__(self) -> str:
        return (
            f"{self.provider_id}: listing discovery needs either a non-empty `allow` list "
            "or `whole_catalog_is_free: true`. Without one of them every model the platform "
            "sells would be treated as free."
        )


@dataclass(frozen=True, slots=True)
class ReferralWithoutDisclosureError(ValueError):
    provider_id: str

    @override
    def __str__(self) -> str:
        return (
            f"{self.provider_id}: `referral_url` requires `referral_note` describing what "
            "both sides receive. An undisclosed referral link must not ship."
        )
