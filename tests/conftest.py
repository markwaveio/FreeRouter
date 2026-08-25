from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from freerouter.registry import Provider
from freerouter.state import HealthState, ModelHealth

NOW = datetime(2026, 8, 25, 12, 0, tzinfo=UTC)


def make_provider(**overrides: Any) -> Provider:
    base: dict[str, Any] = {
        "id": "demo",
        "name": "Demo",
        "name_zh": "演示平台",
        "litellm_prefix": "openai",
        "api_base": "https://demo.example/v1",
        "credential": "DEMO_API_KEY",
        "docs_url": "https://demo.example/docs",
        "free_basis": "测试用",
        "free_basis_checked": "2026-08-25",
        "discovery": {"mode": "static", "models": ["alpha", "beta"]},
    }
    base.update(overrides)
    return Provider.model_validate(base)


def make_health(**overrides: Any) -> ModelHealth:
    base: dict[str, Any] = {
        "provider": "demo",
        "model_id": "alpha",
        "first_seen": NOW,
        "last_seen": NOW,
    }
    base.update(overrides)
    return ModelHealth.model_validate(base)


def make_state(*healths: ModelHealth) -> HealthState:
    return HealthState(models={health.key: health for health in healths})
