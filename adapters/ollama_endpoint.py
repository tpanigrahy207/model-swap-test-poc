from __future__ import annotations

import os
import time

import httpx

from core.contracts import CompletionResult, EndpointHealth


class OllamaEndpoint:
    def __init__(
        self,
        name: str,
        model: str,
        host_env: str,
        default_host: str,
        timeout_seconds: float = 120,
        price_per_1k_input: float = 0.0,
        price_per_1k_output: float = 0.0,
    ) -> None:
        self._name = name
        self.model = model
        self.host = os.getenv(host_env, default_host).rstrip("/")
        self.timeout_seconds = timeout_seconds
        self.price_per_1k_input = price_per_1k_input
        self.price_per_1k_output = price_per_1k_output

    @property
    def name(self) -> str:
        return self._name

    def health(self) -> EndpointHealth:
        try:
            response = httpx.get(f"{self.host}/api/tags", timeout=5)
            response.raise_for_status()
        except httpx.HTTPError as exc:
            return EndpointHealth(ok=False, detail=str(exc))
        return EndpointHealth(ok=True, detail="local service reachable")

    def complete(self, prompt: str, system: str, **kwargs: object) -> CompletionResult:
        del kwargs
        start = time.perf_counter()
        response = httpx.post(
            f"{self.host}/api/generate",
            json={
                "model": self.model,
                "system": system,
                "prompt": prompt,
                "stream": False,
                "options": {"temperature": 0},
            },
            timeout=self.timeout_seconds,
        )
        response.raise_for_status()
        elapsed_ms = (time.perf_counter() - start) * 1000
        data = response.json()
        input_tokens = int(data.get("prompt_eval_count", 0))
        output_tokens = int(data.get("eval_count", 0))
        cost_usd = (
            input_tokens / 1000 * self.price_per_1k_input
            + output_tokens / 1000 * self.price_per_1k_output
        )
        return CompletionResult(
            text=str(data.get("response", "")),
            latency_ms=elapsed_ms,
            raw=data,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cost_usd=cost_usd,
        )
