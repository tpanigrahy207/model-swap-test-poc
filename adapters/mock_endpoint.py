from __future__ import annotations

import time

from core.contracts import CompletionResult, EndpointHealth


class MockEndpoint:
    def __init__(self, name: str, degraded: bool = False, latency_ms: float = 20.0) -> None:
        self._name = name
        self.degraded = degraded
        self.latency_ms = latency_ms

    @property
    def name(self) -> str:
        return self._name

    def health(self) -> EndpointHealth:
        return EndpointHealth(ok=True, detail="deterministic local mock")

    def complete(self, prompt: str, system: str, **kwargs: object) -> CompletionResult:
        del system, kwargs
        start = time.perf_counter()
        label = self._classify(prompt)
        elapsed_ms = ((time.perf_counter() - start) * 1000) + self.latency_ms
        return CompletionResult(text=label, latency_ms=elapsed_ms)

    def _classify(self, prompt: str) -> str:
        text = prompt.lower()
        if "fake patient" in text or "demo-0000" in text:
            return "NO_PHI"
        direct_markers = (
            "dob",
            "mrn",
            "555-",
            "@example.test",
            "policy id",
            "maya ellison",
            "jordan patel",
            "lena ortiz",
            "nora chen",
            "samira woods",
            "carlos rivera",
        )
        indirect_markers = ("room 412b", "only pediatric transplant patient")
        if self.degraded and any(marker in text for marker in ("maya ellison", "jordan patel")):
            return "NO_PHI"
        if any(marker in text for marker in direct_markers + indirect_markers):
            return "CONTAINS_PHI"
        return "NO_PHI"
