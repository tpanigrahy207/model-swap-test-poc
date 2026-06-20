from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path
from typing import Any

from rich.console import Console
from rich.table import Table

from core.capability import capability_to_dict
from core.contracts import CandidateScore, SwapTestReport


def report_to_dict(report: SwapTestReport) -> dict[str, Any]:
    return {
        "capability": capability_to_dict(report.capability),
        "incumbent": report.incumbent_name,
        "incumbent_score": _score_to_dict(report.incumbent_score)
        if report.incumbent_score
        else None,
        "overall_verdict": report.overall_verdict,
        "blocking_reasons": report.blocking_reasons,
        "asset_checks": [asdict(check) for check in report.asset_checks],
        "candidate_scores": [_score_to_dict(score) for score in report.candidate_scores],
    }


def _score_to_dict(score: CandidateScore) -> dict[str, Any]:
    return {
        "endpoint_name": score.endpoint_name,
        "verdict": score.verdict,
        "available": score.available,
        "accuracy": score.accuracy,
        "accuracy_delta_vs_incumbent": score.accuracy_delta_vs_incumbent,
        "sample_size": score.sample_size,
        "accuracy_ci_95": [score.accuracy_ci_low, score.accuracy_ci_high],
        "significance_note": score.significance_note,
        "critical_recall": score.critical_recall,
        "critical_support": score.critical_support,
        "critical_false_negative_count": score.critical_false_negative_count,
        "recovery_window_minutes": score.recovery_window_minutes,
        "eval_cost_usd": score.eval_cost_usd,
        "total_tokens": score.total_tokens,
        "cost_delta_vs_incumbent": score.cost_delta_vs_incumbent,
        "blocking_reasons": score.blocking_reasons,
        "gaps": score.gaps,
        "eval_results": [asdict(result) for result in score.eval_results],
    }


def write_json_report(report: SwapTestReport, path: Path) -> None:
    path.write_text(json.dumps(report_to_dict(report), indent=2, sort_keys=True) + "\n")


def render_report(report: SwapTestReport, console: Console | None = None) -> None:
    out = console or Console()
    out.print(f"[bold]Capability:[/bold] {report.capability.name}")
    out.print(f"[bold]Overall verdict:[/bold] {report.overall_verdict}")
    if report.blocking_reasons:
        out.print("[bold]Blocking reasons:[/bold] " + "; ".join(report.blocking_reasons))
    out.print()

    assets = Table(title="Asset Completeness")
    assets.add_column("Asset")
    assets.add_column("Status")
    assets.add_column("Reason")
    for check in report.asset_checks:
        assets.add_row(check.name, check.status.upper(), check.reason)
    out.print(assets)

    candidates = Table(title="Candidate Qualification")
    candidates.add_column("Endpoint")
    candidates.add_column("Role")
    candidates.add_column("Verdict")
    candidates.add_column("Accuracy (95% CI)")
    candidates.add_column("Δ acc")
    candidates.add_column("Critical recall")
    candidates.add_column("Eval cost")
    candidates.add_column("Blocking reasons / gaps")

    scores = []
    if report.incumbent_score is not None:
        scores.append((report.incumbent_score, "incumbent"))
    scores.extend((score, "candidate") for score in report.candidate_scores)
    for score, role in scores:
        _add_score_row(candidates, score, role)
    out.print(candidates)

    for score, _ in scores:
        if score.significance_note:
            out.print(f"[yellow]⚠ {score.endpoint_name}:[/yellow] {score.significance_note}")

    out.print(
        "[dim]Incumbent is requalified on the same eval set; Δ acc is the candidate's quality "
        "regression against that measured baseline.[/dim]"
    )
    out.print(
        "[dim]Critical recall is caught/total on the capability's critical class. "
        "Eval cost is measured spend for this run; recovery window omitted for width.[/dim]"
    )


def _add_score_row(table: Table, score: CandidateScore, role: str) -> None:
    reasons = score.blocking_reasons + score.gaps
    if not score.available:
        table.add_row(score.endpoint_name, role, score.verdict, "—", "—", "—", "—",
                      "; ".join(reasons) if reasons else "none")
        return

    accuracy = f"{score.accuracy:.2f} [{score.accuracy_ci_low:.2f}-{score.accuracy_ci_high:.2f}]"
    if score.accuracy_delta_vs_incumbent is None:
        delta = "baseline"
    else:
        delta = f"{score.accuracy_delta_vs_incumbent:+.2f}"
    if score.critical_support:
        caught = score.critical_support - score.critical_false_negative_count
        recall = f"{caught}/{score.critical_support} ({score.critical_recall:.2f})"
    else:
        recall = "n/a"
    table.add_row(
        score.endpoint_name,
        role,
        score.verdict,
        accuracy,
        delta,
        recall,
        f"${score.eval_cost_usd:.4f}",
        "; ".join(reasons) if reasons else "none",
    )
