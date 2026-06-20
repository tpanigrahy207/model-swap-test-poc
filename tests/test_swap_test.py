from pathlib import Path

from adapters.mock_endpoint import MockEndpoint
from core.capability import load_capability
from core.contracts import CompletionResult, EndpointHealth
from core.state import JsonlEnterpriseState
from core.swap_test import run_swap_test, validate_assets

CAPABILITY_PATH = Path("profiles/capabilities/phi-classification.yaml")


class DownEndpoint:
    """Endpoint that fails its health check; should never be scored."""

    def __init__(self, name: str) -> None:
        self._name = name
        self.completes = 0

    @property
    def name(self) -> str:
        return self._name

    def health(self) -> EndpointHealth:
        return EndpointHealth(ok=False, detail="connection refused")

    def complete(self, prompt: str, system: str, **kwargs: object) -> CompletionResult:
        self.completes += 1
        return CompletionResult(text="NO_PHI", latency_ms=1.0)


def test_mock_candidate_passes(tmp_path: Path) -> None:
    capability = load_capability(Path("profiles/capabilities/phi-classification.yaml"))
    report = run_swap_test(
        capability=capability,
        incumbent=MockEndpoint("mock"),
        candidates=[MockEndpoint("mock")],
        state=JsonlEnterpriseState(tmp_path / "routes.jsonl"),
    )
    assert report.overall_verdict == "SWAPPABLE"
    assert report.candidate_scores[0].accuracy == 1.0
    assert report.incumbent_score is not None
    assert report.candidate_scores[0].accuracy_delta_vs_incumbent == 0.0
    records = JsonlEnterpriseState(tmp_path / "routes.jsonl").query(capability.capability_id)
    # 16 incumbent baseline records + 16 candidate records.
    assert len(records) == 32


def test_degraded_candidate_fails() -> None:
    capability = load_capability(Path("profiles/capabilities/phi-classification.yaml"))
    report = run_swap_test(
        capability=capability,
        incumbent=MockEndpoint("mock"),
        candidates=[MockEndpoint("mock-degraded", degraded=True)],
        state=JsonlEnterpriseState(Path("/tmp/model-swap-test-routes.jsonl")),
    )
    assert report.overall_verdict == "NOT_SWAPPABLE"
    assert "false negatives on direct identifiers" in report.candidate_scores[0].blocking_reasons


def test_missing_eval_set_is_hard_failure(tmp_path: Path) -> None:
    capability = load_capability(Path("profiles/capabilities/phi-classification.yaml"))
    missing = tmp_path / "missing.jsonl"
    altered = type(capability)(
        capability_id=capability.capability_id,
        name=capability.name,
        description=capability.description,
        system_prompt=capability.system_prompt,
        prompt_template=capability.prompt_template,
        eval_set=missing,
        labels=capability.labels,
        critical_label=capability.critical_label,
        critical_terms=capability.critical_terms,
        critical_false_negative_reason=capability.critical_false_negative_reason,
        acceptance=capability.acceptance,
        max_recovery_window_minutes=capability.max_recovery_window_minutes,
        declared_integration_overhead_minutes=capability.declared_integration_overhead_minutes,
        fallback_procedure=capability.fallback_procedure,
        tool_contracts=capability.tool_contracts,
        policy_constraints=capability.policy_constraints,
    )
    checks = validate_assets(altered)
    report = run_swap_test(
        capability=altered,
        incumbent=MockEndpoint("mock"),
        candidates=[MockEndpoint("mock")],
        state=JsonlEnterpriseState(tmp_path / "routes.jsonl"),
    )
    assert any(check.status == "fail" for check in checks)
    assert report.overall_verdict == "NOT_SWAPPABLE"
    assert report.candidate_scores[0].eval_results == []


def test_score_reports_sample_size_and_confidence(tmp_path: Path) -> None:
    capability = load_capability(CAPABILITY_PATH)
    report = run_swap_test(
        capability=capability,
        incumbent=MockEndpoint("mock"),
        candidates=[MockEndpoint("mock-degraded", degraded=True)],
        state=JsonlEnterpriseState(tmp_path / "routes.jsonl"),
    )
    score = report.candidate_scores[0]
    assert score.sample_size == 16
    assert score.accuracy_ci_low < score.accuracy < score.accuracy_ci_high
    # 0.88 vs a 0.90 bar at n=16 is not statistically conclusive.
    assert score.significance_note is not None


def test_critical_recall_is_surfaced(tmp_path: Path) -> None:
    capability = load_capability(CAPABILITY_PATH)
    report = run_swap_test(
        capability=capability,
        incumbent=MockEndpoint("mock"),
        candidates=[MockEndpoint("mock-degraded", degraded=True)],
        state=JsonlEnterpriseState(tmp_path / "routes.jsonl"),
    )
    assert report.incumbent_score is not None
    assert report.incumbent_score.critical_recall == 1.0
    degraded = report.candidate_scores[0]
    # The degraded mock drops two direct-identifier cases.
    assert degraded.critical_support > 0
    assert degraded.critical_recall is not None
    assert degraded.critical_recall < 1.0


def test_unavailable_candidate_is_not_scored_as_quality_failure(tmp_path: Path) -> None:
    capability = load_capability(CAPABILITY_PATH)
    down = DownEndpoint("ollama-local")
    report = run_swap_test(
        capability=capability,
        incumbent=MockEndpoint("mock"),
        candidates=[down],
        state=JsonlEnterpriseState(tmp_path / "routes.jsonl"),
    )
    score = report.candidate_scores[0]
    assert score.available is False
    assert down.completes == 0
    assert any("unavailable" in reason for reason in score.blocking_reasons)
    assert not any("accuracy below threshold" in reason for reason in score.blocking_reasons)


def test_unavailable_incumbent_aborts_before_scoring(tmp_path: Path) -> None:
    capability = load_capability(CAPABILITY_PATH)
    report = run_swap_test(
        capability=capability,
        incumbent=DownEndpoint("mock"),
        candidates=[MockEndpoint("mock")],
        state=JsonlEnterpriseState(tmp_path / "routes.jsonl"),
    )
    assert report.overall_verdict == "NOT_SWAPPABLE"
    assert any("incumbent endpoint unavailable" in reason for reason in report.blocking_reasons)
