from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from adapters.anthropic_endpoint import AnthropicEndpoint
from adapters.mock_endpoint import MockEndpoint
from adapters.ollama_endpoint import OllamaEndpoint
from core.contracts import ModelEndpoint


def load_endpoint_profile(path: Path) -> dict[str, dict[str, Any]]:
    data = yaml.safe_load(path.read_text()) or {}
    endpoints = data.get("endpoints")
    if not isinstance(endpoints, dict):
        raise ValueError(f"Profile {path} must contain an endpoints mapping.")
    return {str(key): value for key, value in endpoints.items()}


def build_endpoint(endpoint_id: str, profile: dict[str, dict[str, Any]]) -> ModelEndpoint:
    if endpoint_id not in profile:
        available = ", ".join(sorted(profile))
        raise ValueError(f"Unknown endpoint '{endpoint_id}'. Available: {available}")
    config = profile[endpoint_id]
    adapter = str(config["adapter"])
    if adapter == "mock":
        return MockEndpoint(name=endpoint_id, latency_ms=float(config.get("latency_ms", 20)))
    if adapter == "mock_degraded":
        return MockEndpoint(
            name=endpoint_id,
            degraded=True,
            latency_ms=float(config.get("latency_ms", 20)),
        )
    if adapter == "anthropic":
        return AnthropicEndpoint(
            name=endpoint_id,
            model=str(config["model"]),
            api_key_env=str(config.get("api_key_env", "ANTHROPIC_API_KEY")),
            timeout_seconds=float(config.get("timeout_seconds", 45)),
            price_per_1k_input=float(config.get("price_per_1k_input", 0.0)),
            price_per_1k_output=float(config.get("price_per_1k_output", 0.0)),
        )
    if adapter == "ollama":
        return OllamaEndpoint(
            name=endpoint_id,
            model=str(config["model"]),
            host_env=str(config.get("host_env", "OLLAMA_HOST")),
            default_host=str(config.get("default_host", "http://localhost:11434")),
            timeout_seconds=float(config.get("timeout_seconds", 120)),
            price_per_1k_input=float(config.get("price_per_1k_input", 0.0)),
            price_per_1k_output=float(config.get("price_per_1k_output", 0.0)),
        )
    raise ValueError(f"Unsupported adapter '{adapter}' for endpoint '{endpoint_id}'.")
