# /// script
# requires-python = ">=3.11"
# dependencies = ["pydantic>=2.11,<3", "PyYAML>=6.0,<7"]
# ///
# ─── How to run ───
# uv run freerouter_config.py

from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass
from decimal import Decimal
from http.client import HTTPSConnection
from pathlib import Path
from typing import ClassVar

import yaml
from pydantic import BaseModel, ConfigDict, Field, ValidationError
from typing_extensions import override

ZENMUX_HOST = "zenmux.ai"
ZENMUX_MODELS_PATH = "/api/v1/models"
ZENMUX_API_BASE = "https://zenmux.ai/api/v1"
OPENROUTER_FREE_MODEL = "openrouter/openrouter/free"
BASE_CONFIG_PATH = Path("/app/config/litellm-config.yaml")
GENERATED_CONFIG_PATH = Path("/app/runtime/freerouter-config.yaml")
AUTO_MODEL_NAMES = frozenset({"free-router", "openrouter-free", "zenmux-free"})
LOGGER = logging.getLogger("freerouter")


HTTP_OK = 200


class PricingRate(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(frozen=True, extra="ignore")

    value: Decimal


class ModelPricing(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(frozen=True, extra="ignore")

    prompt: tuple[PricingRate, ...] = ()
    completion: tuple[PricingRate, ...] = ()


class ZenMuxModel(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(frozen=True, extra="ignore")

    model_id: str = Field(alias="id")
    input_modalities: tuple[str, ...] = ()
    output_modalities: tuple[str, ...] = ()
    pricings: ModelPricing = Field(default_factory=ModelPricing)


class ZenMuxCatalog(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(frozen=True, extra="ignore")

    data: tuple[ZenMuxModel, ...]


class LiteLLMParams(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(frozen=True, extra="allow")

    model: str
    api_key: str | None = None
    api_base: str | None = None


class ModelInfo(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(frozen=True, extra="allow")

    input_cost_per_token: Decimal | None = None
    output_cost_per_token: Decimal | None = None
    cache_creation_input_token_cost: Decimal | None = None
    cache_read_input_token_cost: Decimal | None = None


class ModelDeployment(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(frozen=True, extra="allow")

    model_name: str
    litellm_params: LiteLLMParams
    model_info: ModelInfo | None = None


class GeneralSettings(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(frozen=True, extra="allow")

    master_key: str


class RouterSettings(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(frozen=True, extra="allow")

    routing_strategy: str


class ProxyConfig(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(frozen=True, extra="allow")

    model_list: tuple[ModelDeployment, ...] = ()
    general_settings: GeneralSettings
    router_settings: RouterSettings


@dataclass(frozen=True, slots=True)
class NoProviderConfiguredError(RuntimeError):
    @override
    def __str__(self) -> str:
        return "Set ZENMUX_API_KEY or OPENROUTER_API_KEY before starting FreeRouter"


@dataclass(frozen=True, slots=True)
class ZenMuxApiError(RuntimeError):
    status: int
    body: str

    @override
    def __str__(self) -> str:
        return f"ZenMux model catalog returned HTTP {self.status}: {self.body}"


@dataclass(frozen=True, slots=True)
class EmptyZenMuxPoolError(RuntimeError):
    @override
    def __str__(self) -> str:
        return "ZenMux returned no text models with zero input and output price"


def discover_free_model_ids(payload: bytes) -> tuple[str, ...]:
    catalog = ZenMuxCatalog.model_validate_json(payload)
    model_ids = (
        model.model_id
        for model in catalog.data
        if "text" in model.input_modalities
        and "text" in model.output_modalities
        and model.pricings.prompt
        and model.pricings.completion
        and all(rate.value == 0 for rate in model.pricings.prompt)
        and all(rate.value == 0 for rate in model.pricings.completion)
    )
    return tuple(sorted(set(model_ids)))


def zero_price_model_info() -> ModelInfo:
    return ModelInfo(
        input_cost_per_token=Decimal(0),
        output_cost_per_token=Decimal(0),
        cache_creation_input_token_cost=Decimal(0),
        cache_read_input_token_cost=Decimal(0),
    )


def build_config(
    *,
    base_config: ProxyConfig,
    zenmux_model_ids: tuple[str, ...],
    openrouter_enabled: bool,
) -> ProxyConfig:
    if not zenmux_model_ids and not openrouter_enabled:
        raise NoProviderConfiguredError

    deployments = [
        deployment
        for deployment in base_config.model_list
        if deployment.model_name not in AUTO_MODEL_NAMES
    ]
    if openrouter_enabled:
        deployments.extend(
            ModelDeployment(
                model_name=model_name,
                litellm_params=LiteLLMParams(
                    model=OPENROUTER_FREE_MODEL,
                    api_key="os.environ/OPENROUTER_API_KEY",
                ),
                model_info=zero_price_model_info(),
            )
            for model_name in ("free-router", "openrouter-free")
        )

    deployments.extend(
        ModelDeployment(
            model_name=model_name,
            litellm_params=LiteLLMParams(
                model=f"openai/{model_id}",
                api_key="os.environ/ZENMUX_API_KEY",
                api_base=ZENMUX_API_BASE,
            ),
            model_info=zero_price_model_info(),
        )
        for model_id in zenmux_model_ids
        for model_name in ("free-router", "zenmux-free")
    )

    return base_config.model_copy(update={"model_list": tuple(deployments)})


def fetch_zenmux_model_ids(api_key: str) -> tuple[str, ...]:
    connection = HTTPSConnection(ZENMUX_HOST, timeout=45)
    try:
        connection.request(
            "GET",
            ZENMUX_MODELS_PATH,
            headers={"Authorization": f"Bearer {api_key}"},
        )
        response = connection.getresponse()
        payload = response.read()
    finally:
        connection.close()

    if response.status != HTTP_OK:
        raise ZenMuxApiError(status=response.status, body=payload.decode(errors="replace")[:300])

    model_ids = discover_free_model_ids(payload)
    if not model_ids:
        raise EmptyZenMuxPoolError
    return model_ids


def load_base_config(path: Path) -> ProxyConfig:
    with path.open(encoding="utf-8") as config_file:
        return ProxyConfig.model_validate(yaml.safe_load(config_file))


def write_config(config: ProxyConfig, path: Path) -> None:
    serialized = config.model_dump(mode="json", exclude_none=True, by_alias=True)
    _ = path.write_text(
        yaml.safe_dump(serialized, allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )


def start_proxy(config_path: Path) -> None:
    os.execv(
        "/app/docker/prod_entrypoint.sh",
        [
            "/app/docker/prod_entrypoint.sh",
            "--config",
            str(config_path),
            "--port",
            "4000",
        ],
    )


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s freerouter: %(message)s")
    try:
        base_config = load_base_config(BASE_CONFIG_PATH)
        zenmux_api_key = os.environ.get("ZENMUX_API_KEY", "").strip()
        openrouter_enabled = bool(os.environ.get("OPENROUTER_API_KEY", "").strip())
        zenmux_model_ids = fetch_zenmux_model_ids(zenmux_api_key) if zenmux_api_key else ()
        config = build_config(
            base_config=base_config,
            zenmux_model_ids=zenmux_model_ids,
            openrouter_enabled=openrouter_enabled,
        )
        write_config(config, GENERATED_CONFIG_PATH)
    except (
        EmptyZenMuxPoolError,
        json.JSONDecodeError,
        NoProviderConfiguredError,
        OSError,
        ValidationError,
        yaml.YAMLError,
        ZenMuxApiError,
    ):
        LOGGER.exception("startup failed")
        return 1

    LOGGER.info(
        "configured aliases with %d ZenMux zero-price models; OpenRouter enabled=%s",
        len(zenmux_model_ids),
        openrouter_enabled,
    )
    start_proxy(GENERATED_CONFIG_PATH)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
