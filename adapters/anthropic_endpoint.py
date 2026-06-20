from __future__ import annotations

import os
import time
from typing import Any

from core.contracts import CompletionResult, EndpointHealth


class AnthropicEndpoint:
    def __init__(
        self,
        name: str,
        model: str,
        api_key_env: str,
        timeout_seconds: float = 45,
        price_per_1k_input: float = 0.0,
        price_per_1k_output: float = 0.0,
    ) -> None:
        self._name = name
        self.model = model
        self.api_key_env = api_key_env
        self.timeout_seconds = timeout_seconds
        self.price_per_1k_input = price_per_1k_input
        self.price_per_1k_output = price_per_1k_output

    @property
    def name(self) -> str:
        return self._name

    def health(self) -> EndpointHealth:
        if not os.getenv(self.api_key_env):
            return EndpointHealth(ok=False, detail=f"missing {self.api_key_env}")
        return EndpointHealth(ok=True, detail="api key configured")

    def complete(self, prompt: str, system: str, **kwargs: object) -> CompletionResult:
        del kwargs
        try:
            from anthropic import Anthropic  # type: ignore[import-not-found]
        except ImportError as exc:
            raise RuntimeError(
                'Install the optional dependency with pip install -e ".[anthropic]".'
            ) from exc
        api_key = os.getenv(self.api_key_env)
        if not api_key:
            raise RuntimeError(f"{self.api_key_env} is not set.")
        client = Anthropic(api_key=api_key, timeout=self.timeout_seconds)
        start = time.perf_counter()
        message = client.messages.create(
            model=self.model,
            max_tokens=16,
            temperature=0,
            system=system,
            messages=[{"role": "user", "content": prompt}],
        )
        elapsed_ms = (time.perf_counter() - start) * 1000
        payload = message.model_dump()
        text = _extract_text(payload)
        usage = payload.get("usage", {}) or {}
        input_tokens = int(usage.get("input_tokens", 0))
        output_tokens = int(usage.get("output_tokens", 0))
        cost_usd = (
            input_tokens / 1000 * self.price_per_1k_input
            + output_tokens / 1000 * self.price_per_1k_output
        )
        return CompletionResult(
            text=text,
            latency_ms=elapsed_ms,
            raw=payload,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cost_usd=cost_usd,
        )


def _extract_text(payload: dict[str, Any]) -> str:
    chunks: list[str] = []
    for item in payload.get("content", []):
        if isinstance(item, dict) and item.get("type") == "text":
            chunks.append(str(item.get("text", "")))
    return "\n".join(chunks)
