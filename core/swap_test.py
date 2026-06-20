from __future__ import annotations

from dataclasses import replace

from core.contracts import (
    AssetCheck,
    CandidateScore,
    CapabilityDefinition,
    EnterpriseState,
    EvalResult,
    ModelEndpoint,
    SwapTestReport,
    Verdict,
)
from core.evaluator import evaluate_endpoint
from core.stats import wilson_interval


def validate_assets(capability: CapabilityDefinition) -> list[AssetCheck]:
    checks: list[AssetCheck] = []
    if capability.eval_set.exists() and capability.eval_set.stat().st_size > 0:
        checks.append(AssetCheck("eval set", "pass", "eval evidence is present"))
    else:
        checks.append(
            AssetCheck("eval set", "fail", "eval set missing; cannot requalify substitute")
        )

    if capability.acceptance.min_accuracy > 0:
        checks.append(AssetCheck("acceptance criteria", "pass", "quality threshold is defined"))
    else:
        checks.append(AssetCheck("acceptance criteria", "fail", "minimum accuracy is not defined"))

    if capability.fallback_procedure.strip():
        checks.append(AssetCheck("fallback procedure", "pass", "fallback path is declared"))
    else:
        checks.append(AssetCheck("fallback procedure", "flag", "fallback path is not declared"))

    if capability.tool_contracts:
        checks.append(AssetCheck("tool contracts", "pass", "tool boundary is declared"))
    else:
        checks.append(AssetCheck("tool contracts", "flag", "tool boundary is not declared"))

    if capability.policy_constraints:
        checks.append(AssetCheck("policy constraints", "pass", "policy constraints are declared"))
    else:
        checks.append(
            AssetCheck("policy constraints", "flag", "policy constraints are not declared")
        )

    return checks


def has_blocking_asset_failure(checks: list[AssetCheck]) -> bool:
    return any(check.status == "fail" for check in checks)


def score_candidate(
    capability: CapabilityDefinition,
    endpoint: ModelEndpoint,
    state: EnterpriseState,
    baseline_accuracy: float | None = None,
) -> CandidateScore:
    results = evaluate_endpoint(capability, endpoint, state)
    total = len(results)
    passed = sum(1 for result in results if result.passed)
    accuracy = passed / total if total else 0.0
    ci_low, ci_high = wilson_interval(passed, total)

    critical_support, critical_caught = _critical_population(capability, results)
    critical_false_negative_count = critical_support - critical_caught
    critical_recall = critical_caught / critical_support if critical_support else None

    eval_cost_usd = sum(result.cost_usd for result in results)
    total_tokens = sum(result.input_tokens + result.output_tokens for result in results)

    threshold = capability.acceptance.min_accuracy
    blocking_reasons: list[str] = []
    gaps: list[str] = []

    if accuracy < threshold:
        blocking_reasons.append(f"accuracy below threshold ({accuracy:.2f} < {threshold:.2f})")
    if capability.acceptance.zero_critical_false_negatives and critical_false_negative_count:
        blocking_reasons.append(capability.critical_false_negative_reason)

    eval_runtime_minutes = sum(result.latency_ms for result in results) / 1000 / 60
    recovery_window_minutes = (
        eval_runtime_minutes + capability.declared_integration_overhead_minutes
    )
    if recovery_window_minutes > capability.max_recovery_window_minutes:
        gaps.append(
            "estimated recovery window exceeds declared maximum "
            f"({recovery_window_minutes:.1f} > {capability.max_recovery_window_minutes:.1f} min)"
        )

    if blocking_reasons:
        verdict: Verdict = "NOT_SWAPPABLE"
    elif gaps:
        verdict = "SWAPPABLE_WITH_GAPS"
    else:
        verdict = "SWAPPABLE"

    return CandidateScore(
        endpoint_name=endpoint.name,
        verdict=verdict,
        accuracy=accuracy,
        critical_false_negative_count=critical_false_negative_count,
        recovery_window_minutes=recovery_window_minutes,
        blocking_reasons=blocking_reasons,
        gaps=gaps,
        eval_results=results,
        accuracy_delta_vs_incumbent=(
            None if baseline_accuracy is None else accuracy - baseline_accuracy
        ),
        available=True,
        sample_size=total,
        accuracy_ci_low=ci_low,
        accuracy_ci_high=ci_high,
        significance_note=_significance_note(
            accuracy, ci_low, ci_high, threshold, baseline_accuracy, total
        ),
        critical_recall=critical_recall,
        critical_support=critical_support,
        eval_cost_usd=eval_cost_usd,
        total_tokens=total_tokens,
    )


def _unavailable_score(endpoint: ModelEndpoint, detail: str) -> CandidateScore:
    """A score for an endpoint that failed its health check.

    Distinguishing 'unavailable' from a low accuracy keeps the harness from reporting
    an infrastructure outage as a quality failure.
    """
    return CandidateScore(
        endpoint_name=endpoint.name,
        verdict="NOT_SWAPPABLE",
        accuracy=0.0,
        critical_false_negative_count=0,
        recovery_window_minutes=0.0,
        blocking_reasons=[f"endpoint unavailable: {detail}"],
        gaps=[],
        eval_results=[],
        available=False,
    )


def run_swap_test(
    capability: CapabilityDefinition,
    incumbent: ModelEndpoint,
    candidates: list[ModelEndpoint],
    state: EnterpriseState,
) -> SwapTestReport:
    checks = validate_assets(capability)
    if has_blocking_asset_failure(checks):
        reasons = [check.reason for check in checks if check.status == "fail"]
        return SwapTestReport(
            capability=capability,
            incumbent_name=incumbent.name,
            incumbent_score=None,
            asset_checks=checks,
            candidate_scores=[
                CandidateScore(
                    endpoint_name=candidate.name,
                    verdict="NOT_SWAPPABLE",
                    accuracy=0.0,
                    critical_false_negative_count=0,
                    recovery_window_minutes=0.0,
                    blocking_reasons=reasons,
                    gaps=[],
                    eval_results=[],
                )
                for candidate in candidates
            ],
            overall_verdict="NOT_SWAPPABLE",
            blocking_reasons=reasons,
        )

    # Pre-flight: a swap test is only meaningful if the endpoints actually answer.
    # If the incumbent is down we cannot establish a baseline, so we stop before
    # producing numbers that would look like a quality verdict.
    incumbent_health = incumbent.health()
    if not incumbent_health.ok:
        reason = f"incumbent endpoint unavailable: {incumbent_health.detail}"
        return SwapTestReport(
            capability=capability,
            incumbent_name=incumbent.name,
            incumbent_score=_unavailable_score(incumbent, incumbent_health.detail),
            asset_checks=checks,
            candidate_scores=[_unavailable_score(c, "incumbent baseline unavailable")
                              for c in candidates],
            overall_verdict="NOT_SWAPPABLE",
            blocking_reasons=[reason],
        )

    # Requalify the incumbent on the same eval set first: every candidate is judged
    # against this measured baseline, not just the static acceptance threshold.
    incumbent_score = score_candidate(capability, incumbent, state)
    candidate_scores: list[CandidateScore] = []
    for candidate in candidates:
        health = candidate.health()
        if not health.ok:
            candidate_scores.append(_unavailable_score(candidate, health.detail))
            continue
        candidate_scores.append(
            score_candidate(
                capability, candidate, state, baseline_accuracy=incumbent_score.accuracy
            )
        )
    candidate_scores = [
        _with_cost_delta(score, incumbent_score) for score in candidate_scores
    ]
    overall = _overall_verdict(candidate_scores)
    blocking = [] if overall != "NOT_SWAPPABLE" else _merge_blocking(candidate_scores)
    return SwapTestReport(
        capability=capability,
        incumbent_name=incumbent.name,
        incumbent_score=incumbent_score,
        asset_checks=checks,
        candidate_scores=candidate_scores,
        overall_verdict=overall,
        blocking_reasons=blocking,
    )


def _critical_population(
    capability: CapabilityDefinition, results: list[EvalResult]
) -> tuple[int, int]:
    """Return (support, caught) for the capability's critical class.

    The critical class is defined by the contract — the label that must never be
    missed and the rationale terms marking its high-stakes subset — so core/ never
    needs to know the domain. 'support' is how many critical examples the eval set
    contains; 'caught' is how many the endpoint labelled correctly.
    """
    support = 0
    caught = 0
    for result in results:
        if result.expected != capability.critical_label:
            continue
        if not any(term in result.rationale.lower() for term in capability.critical_terms):
            continue
        support += 1
        if result.observed == capability.critical_label:
            caught += 1
    return support, caught


def _significance_note(
    accuracy: float,
    ci_low: float,
    ci_high: float,
    threshold: float,
    baseline_accuracy: float | None,
    n: int,
) -> str | None:
    """Flag verdicts the sample is too small to support with confidence.

    Two cases worth surfacing: the accuracy point estimate falls on one side of the
    threshold but its 95% interval straddles it, and the gap to the incumbent sits
    inside that same interval. Either way the verdict should not be over-read.
    """
    if n == 0:
        return None
    notes: list[str] = []
    if ci_low <= threshold <= ci_high:
        notes.append(
            f"accuracy {accuracy:.2f} is within the margin of error of the {threshold:.2f} "
            f"threshold (95% CI {ci_low:.2f}-{ci_high:.2f}, n={n})"
        )
    if baseline_accuracy is not None and ci_low <= baseline_accuracy <= ci_high:
        notes.append(
            f"difference from incumbent ({baseline_accuracy:.2f}) is not significant at n={n}"
        )
    if not notes:
        return None
    return "; ".join(notes) + " — collect more eval examples to confirm"


def _with_cost_delta(score: CandidateScore, incumbent: CandidateScore) -> CandidateScore:
    if not score.available:
        return score
    return replace(score, cost_delta_vs_incumbent=score.eval_cost_usd - incumbent.eval_cost_usd)


def _overall_verdict(scores: list[CandidateScore]) -> Verdict:
    verdicts = [score.verdict for score in scores]
    if "SWAPPABLE" in verdicts:
        return "SWAPPABLE"
    if "SWAPPABLE_WITH_GAPS" in verdicts:
        return "SWAPPABLE_WITH_GAPS"
    return "NOT_SWAPPABLE"


def _merge_blocking(scores: list[CandidateScore]) -> list[str]:
    return list(dict.fromkeys(reason for score in scores for reason in score.blocking_reasons))
