from __future__ import annotations

import json
from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console

from adapters.factory import build_endpoint, load_endpoint_profile
from core.capability import load_capability
from core.scorecard import render_report, report_to_dict, write_json_report
from core.state import JsonlEnterpriseState
from core.swap_test import has_blocking_asset_failure, run_swap_test, validate_assets

app = typer.Typer(no_args_is_help=True)
console = Console()
ROOT = Path(__file__).resolve().parent
DEFAULT_PROFILE = ROOT / "profiles" / "models.profile.yaml"
DEFAULT_STATE = ROOT / ".mst-state" / "routes.jsonl"


@app.command(name="list")
def list_command() -> None:
    """List configured endpoints and capabilities."""
    profile = load_endpoint_profile(DEFAULT_PROFILE)
    console.print("[bold]Endpoints[/bold]")
    for endpoint_id, config in sorted(profile.items()):
        console.print(f"- {endpoint_id} ({config.get('adapter')})")
    console.print("\n[bold]Capabilities[/bold]")
    for path in sorted((ROOT / "profiles" / "capabilities").glob("*.yaml")):
        capability = load_capability(path)
        console.print(f"- {capability.capability_id}: {capability.name}")


@app.command()
def validate(capability_path: Annotated[Path, typer.Argument(exists=True)]) -> None:
    """Run asset completeness checks without model calls."""
    capability = load_capability(capability_path)
    checks = validate_assets(capability)
    for check in checks:
        console.print(f"{check.status.upper():<5} {check.name}: {check.reason}")
    if has_blocking_asset_failure(checks):
        raise typer.Exit(code=2)


@app.command()
def run(
    capability_path: Annotated[Path, typer.Argument(exists=True)],
    incumbent: Annotated[
        str,
        typer.Option("--incumbent", help="Endpoint id for current endpoint."),
    ],
    candidate: Annotated[
        list[str],
        typer.Option("--candidate", help="Endpoint id for substitute candidate. Repeatable."),
    ],
    json_output: Annotated[
        bool,
        typer.Option("--json", help="Print JSON instead of rich tables."),
    ] = False,
    profile_path: Annotated[Path, typer.Option("--profile", exists=True)] = DEFAULT_PROFILE,
    state_path: Annotated[Path, typer.Option("--state")] = DEFAULT_STATE,
) -> None:
    """Run the full Model-Swap Test."""
    if not candidate:
        raise typer.BadParameter("At least one --candidate is required.")
    capability = load_capability(capability_path)
    profile = load_endpoint_profile(profile_path)
    incumbent_endpoint = build_endpoint(incumbent, profile)
    candidate_endpoints = [build_endpoint(endpoint_id, profile) for endpoint_id in candidate]
    report = run_swap_test(
        capability=capability,
        incumbent=incumbent_endpoint,
        candidates=candidate_endpoints,
        state=JsonlEnterpriseState(state_path),
    )
    write_json_report(report, ROOT / f"{capability.capability_id}.report.json")
    if json_output:
        console.print(json.dumps(report_to_dict(report), indent=2, sort_keys=True))
    else:
        render_report(report, console)
    if report.overall_verdict == "NOT_SWAPPABLE":
        raise typer.Exit(code=1)
