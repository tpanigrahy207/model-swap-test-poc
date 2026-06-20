from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal, Protocol

Verdict = Literal["SWAPPABLE", "SWAPPABLE_WITH_GAPS", "NOT_SWAPPABLE"]
AssetStatus = Literal["pass", "flag", "fail"]


@dataclass(frozen=True)
class CompletionResult:
    text: str
    latency_ms: float
    raw: dict[str, Any] = field(default_factory=dict)
    # Usage and cost are measured at the adapter boundary (refreshable), so core/ can
    # sum them without knowing any provider's token accounting or price list.
    input_tokens: int = 0
    output_tokens: int = 0
    cost_usd: float = 0.0


@dataclass(frozen=True)
class EndpointHealth:
    ok: bool
    detail: str


@dataclass(frozen=True)
class ClassifiedRequest:
    input_text: str
    purpose: str
    data_classification: str


@dataclass(frozen=True)
class PolicyDecision:
    decision: Literal["allow", "deny", "require_human"]
    reason: str


@dataclass(frozen=True)
class RouteRecord:
    capability_id: str
    eval_id: str
    endpoint_name: str
    expected: str
    observed: str
    passed: bool
    latency_ms: float


@dataclass(frozen=True)
class EvalResult:
    eval_id: str
    input_text: str
    expected: str
    observed: str
    passed: bool
    rationale: str
    latency_ms: float
    input_tokens: int = 0
    output_tokens: int = 0
    cost_usd: float = 0.0


@dataclass(frozen=True)
class EvalExample:
    eval_id: str
    input_text: str
    expected: str
    rationale: str


@dataclass(frozen=True)
class AcceptanceCriteria:
    min_accuracy: float
    zero_critical_false_negatives: bool


@dataclass(frozen=True)
class CapabilityDefinition:
    capability_id: str
    name: str
    description: str
    system_prompt: str
    prompt_template: str
    eval_set: Path
    # The capability — not core — owns its label space and what "critical miss" means.
    # core/ stays model- and domain-agnostic: it never hardcodes PHI or any label.
    labels: tuple[str, ...]
    critical_label: str
    critical_terms: tuple[str, ...]
    critical_false_negative_reason: str
    acceptance: AcceptanceCriteria
    max_recovery_window_minutes: float
    declared_integration_overhead_minutes: float
    fallback_procedure: str
    tool_contracts: list[dict[str, str]]
    policy_constraints: list[str]


@dataclass(frozen=True)
class AssetCheck:
    name: str
    status: AssetStatus
    reason: str


@dataclass(frozen=True)
class CandidateScore:
    endpoint_name: str
    verdict: Verdict
    accuracy: float
    critical_false_negative_count: int
    recovery_window_minutes: float
    blocking_reasons: list[str]
    gaps: list[str]
    eval_results: list[EvalResult]
    # Quality regression against the incumbent baseline. None for the incumbent itself.
    accuracy_delta_vs_incumbent: float | None = None
    # Whether the endpoint answered the health check; a False here means the verdict is
    # an availability failure, not a quality failure.
    available: bool = True
    # Sample size and a Wilson 95% CI on accuracy: at eval-scale n, a point estimate
    # alone is misleading, so the interval travels with every score.
    sample_size: int = 0
    accuracy_ci_low: float = 0.0
    accuracy_ci_high: float = 0.0
    # Set when the sample is too small to separate this candidate from the threshold
    # or the incumbent — i.e. the verdict should not be over-read.
    significance_note: str | None = None
    # Recall on the capability's critical class (caught / total). None when the eval
    # set contains no critical examples.
    critical_recall: float | None = None
    critical_support: int = 0
    # Measured spend for this eval run and its regression vs the incumbent baseline.
    eval_cost_usd: float = 0.0
    total_tokens: int = 0
    cost_delta_vs_incumbent: float | None = None


@dataclass(frozen=True)
class SwapTestReport:
    capability: CapabilityDefinition
    incumbent_name: str
    incumbent_score: CandidateScore | None
    asset_checks: list[AssetCheck]
    candidate_scores: list[CandidateScore]
    overall_verdict: Verdict
    blocking_reasons: list[str]


class ModelEndpoint(Protocol):
    @property
    def name(self) -> str:
        ...

    def complete(self, prompt: str, system: str, **kwargs: object) -> CompletionResult:
        ...

    def health(self) -> EndpointHealth:
        ...


class PolicyGate(Protocol):
    def evaluate(self, request: ClassifiedRequest) -> PolicyDecision:
        ...


class EnterpriseState(Protocol):
    def record(self, route_record: RouteRecord) -> None:
        ...

    def query(self, capability_id: str | None = None) -> list[RouteRecord]:
        ...


class CapabilityProvider(Protocol):
    def get(self) -> CapabilityDefinition:
        ...
