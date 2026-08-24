import json

import pytest

from freerouter_config import (
    NoProviderConfiguredError,
    ProxyConfig,
    build_config,
    discover_free_model_ids,
)


def test_discovers_only_zero_price_text_models() -> None:
    # Given
    payload = json.dumps(
        {
            "data": [
                {
                    "id": "provider/free-text",
                    "input_modalities": ["text"],
                    "output_modalities": ["text"],
                    "pricings": {
                        "prompt": [{"value": 0}],
                        "completion": [{"value": 0}],
                    },
                },
                {
                    "id": "provider/paid-text",
                    "input_modalities": ["text"],
                    "output_modalities": ["text"],
                    "pricings": {
                        "prompt": [{"value": 0}],
                        "completion": [{"value": 0.01}],
                    },
                },
                {
                    "id": "provider/free-image",
                    "input_modalities": ["image"],
                    "output_modalities": ["image"],
                    "pricings": {
                        "prompt": [{"value": 0}],
                        "completion": [{"value": 0}],
                    },
                },
                {
                    "id": "provider/unknown-price",
                    "input_modalities": ["text"],
                    "output_modalities": ["text"],
                },
            ]
        }
    ).encode()

    # When
    model_ids = discover_free_model_ids(payload)

    # Then
    assert model_ids == ("provider/free-text",)


def test_builds_provider_and_unified_aliases() -> None:
    # Given
    base_config = ProxyConfig.model_validate(
        {
            "model_list": [
                {
                    "model_name": "custom-model",
                    "litellm_params": {"model": "openai/custom-model"},
                }
            ],
            "general_settings": {"master_key": "os.environ/LITELLM_MASTER_KEY"},
            "router_settings": {"routing_strategy": "simple-shuffle"},
        }
    )

    # When
    config = build_config(
        base_config=base_config,
        zenmux_model_ids=("provider/free-a", "provider/free-b"),
        openrouter_enabled=True,
    )

    # Then
    routes = {(entry.model_name, entry.litellm_params.model) for entry in config.model_list}
    assert routes == {
        ("custom-model", "openai/custom-model"),
        ("free-router", "openrouter/openrouter/free"),
        ("openrouter-free", "openrouter/openrouter/free"),
        ("free-router", "openai/provider/free-a"),
        ("zenmux-free", "openai/provider/free-a"),
        ("free-router", "openai/provider/free-b"),
        ("zenmux-free", "openai/provider/free-b"),
    }


def test_rejects_configuration_without_a_free_provider() -> None:
    # Given
    base_config = ProxyConfig.model_validate(
        {
            "general_settings": {"master_key": "os.environ/LITELLM_MASTER_KEY"},
            "router_settings": {"routing_strategy": "simple-shuffle"},
        }
    )

    # When / Then
    with pytest.raises(NoProviderConfiguredError):
        _ = build_config(
            base_config=base_config,
            zenmux_model_ids=(),
            openrouter_enabled=False,
        )
