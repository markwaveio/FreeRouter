from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any

from freerouter.discovery import discover
from freerouter.transport import Response
from tests.conftest import make_provider

if TYPE_CHECKING:
    from collections.abc import Mapping

    import pytest

PRICED_CATALOG = {
    "data": [
        {
            "id": "vendor/free-text",
            "pricing": {"prompt": "0", "completion": "0"},
            "architecture": {"input_modalities": ["text"], "output_modalities": ["text"]},
        },
        {
            "id": "vendor/cheap-text",
            "pricing": {"prompt": "0", "completion": "0.000001"},
            "architecture": {"input_modalities": ["text"], "output_modalities": ["text"]},
        },
        {
            "id": "vendor/free-music",
            "pricing": {"prompt": "0", "completion": "0"},
            "architecture": {
                "input_modalities": ["text"],
                "output_modalities": ["text", "audio"],
            },
        },
        {
            "id": "vendor/no-price",
            "architecture": {"input_modalities": ["text"], "output_modalities": ["text"]},
        },
    ]
}

PRICED_DISCOVERY: dict[str, Any] = {
    "mode": "priced_catalog",
    "url": "https://vendor.example/models",
    "auth": "none",
    "items_path": "data",
    "id_path": "id",
    "prompt_price_path": "pricing.prompt",
    "completion_price_path": "pricing.completion",
    "input_modalities_path": "architecture.input_modalities",
    "output_modalities_path": "architecture.output_modalities",
    "require_text_io": True,
    "deny_output_modalities": ["audio", "image", "video"],
}


def _stub(monkeypatch: pytest.MonkeyPatch, payload: object, status: int = 200) -> list[str]:
    seen: list[str] = []

    def fake_request(url: str, **_: object) -> Response:
        seen.append(url)
        return Response(status=status, body=json.dumps(payload).encode())

    monkeypatch.setattr("freerouter.discovery.request", fake_request)
    return seen


def test_priced_catalog_keeps_only_zero_price_text_only_models(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Given
    _ = _stub(monkeypatch, PRICED_CATALOG)
    provider = make_provider(discovery=PRICED_DISCOVERY)

    # When
    result = discover(provider, {"DEMO_API_KEY": "k"})

    # Then
    assert result.models == ("vendor/free-text",)


def test_extra_models_bypass_the_cap_and_the_allow_list(monkeypatch: pytest.MonkeyPatch) -> None:
    # Given
    _ = _stub(monkeypatch, PRICED_CATALOG)
    discovery: dict[str, Any] = {**PRICED_DISCOVERY, "extra_models": ["vendor/meta-route"]}
    provider = make_provider(discovery=discovery, max_models=1)

    # When
    result = discover(provider, {"DEMO_API_KEY": "k"})

    # Then
    assert set(result.models) == {"vendor/free-text", "vendor/meta-route"}


def test_listing_mode_applies_allow_and_deny(monkeypatch: pytest.MonkeyPatch) -> None:
    # Given
    payload = {"data": [{"id": name} for name in ("a-instruct", "a-embed", "b-instruct")]}
    _ = _stub(monkeypatch, payload)
    provider = make_provider(
        discovery={
            "mode": "listing",
            "url": "https://vendor.example/models",
            "auth": "bearer",
            "allow": ["*instruct*"],
            "deny": ["b-*"],
        }
    )

    # When
    result = discover(provider, {"DEMO_API_KEY": "k"})

    # Then
    assert result.models == ("a-instruct",)


def test_query_key_auth_appends_the_key_to_the_url(monkeypatch: pytest.MonkeyPatch) -> None:
    # Given
    seen = _stub(monkeypatch, {"models": [{"name": "models/gemini-9-flash"}]})
    provider = make_provider(
        credential="GEMINI_API_KEY",
        discovery={
            "mode": "listing",
            "url": "https://g.example/v1beta/models",
            "auth": "query_key",
            "whole_catalog_is_free": True,
            "items_path": "models",
            "id_path": "name",
            "id_strip_prefix": "models/",
        },
    )

    # When
    result = discover(provider, {"GEMINI_API_KEY": "secret"})

    # Then
    assert result.models == ("gemini-9-flash",)
    assert seen == ["https://g.example/v1beta/models?key=secret"]


def test_provider_without_credentials_is_skipped_not_failed() -> None:
    # Given
    provider = make_provider()

    # When
    result = discover(provider, {})

    # Then
    assert result.skipped == "missing DEMO_API_KEY"
    assert result.error is None
    assert not result.usable


def test_retired_provider_never_contacts_the_network() -> None:
    # Given
    provider = make_provider(status="retired", credential=None)

    # When
    result = discover(provider, {})

    # Then
    assert result.skipped == "retired"


def test_catalog_http_error_is_reported_without_clearing_the_pool(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Given
    _ = _stub(monkeypatch, {"error": "boom"}, status=503)
    provider = make_provider(discovery=PRICED_DISCOVERY)

    # When
    result = discover(provider, {"DEMO_API_KEY": "k"})

    # Then
    assert result.models == ()
    assert result.error is not None
    assert "503" in result.error
    assert not result.usable


def test_unresolvable_url_template_is_an_error(monkeypatch: pytest.MonkeyPatch) -> None:
    # Given
    _ = _stub(monkeypatch, {})
    provider = make_provider(
        extra_credentials=["DEMO_ACCOUNT_ID"],
        discovery={
            "mode": "listing",
            "url": "https://vendor.example/${DEMO_ACCOUNT_ID}/models",
            "auth": "bearer",
            "whole_catalog_is_free": True,
        },
    )

    # When
    result = discover(provider, {"DEMO_API_KEY": "k"}, require_credentials=False)

    # Then
    assert result.models == ()
    assert result.error == "catalog URL could not be resolved"


def _resolvable_mapping() -> Mapping[str, str]:
    return {"DEMO_API_KEY": "k"}


def test_static_mode_needs_no_network() -> None:
    # Given
    provider = make_provider()

    # When
    result = discover(provider, _resolvable_mapping())

    # Then
    assert result.models == ("alpha", "beta")
