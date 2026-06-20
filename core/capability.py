from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field, model_validator

from core.contracts import AcceptanceCriteria, CapabilityDefinition


class AcceptanceConfig(BaseModel):
    min_accuracy: float = Field(ge=0.0, le=1.0)
    zero_critical_false_negatives: bool = False


class CapabilityConfig(BaseModel):
    id: str
    name: str
    description: str
    system_prompt: str
    prompt_template: str
    eval_set: str
    labels: list[str] = Field(min_length=2)
    critical_label: str
    critical_terms: list[str] = Field(default_factory=list)
    critical_false_negative_reason: str = "false negatives on the critical class"
    acceptance: AcceptanceConfig
    max_recovery_window_minutes: float = Field(gt=0)
    declared_integration_overhead_minutes: float = Field(ge=0)
    fallback_procedure: str = ""
    tool_contracts: list[dict[str, str]] = Field(default_factory=list)
    policy_constraints: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def _critical_label_is_known(self) -> CapabilityConfig:
        if self.critical_label not in self.labels:
            raise ValueError(
                f"critical_label {self.critical_label!r} must be one of labels {self.labels}"
            )
        return self


def _repo_root(path: Path) -> Path:
    """Walk upward from the capability file to the repo root (marked by pyproject.toml)."""
    for parent in path.resolve().parents:
        if (parent / "pyproject.toml").exists():
            return parent
    return path.resolve().parent


def load_capability(path: Path) -> CapabilityDefinition:
    data = yaml.safe_load(path.read_text()) or {}
    if not isinstance(data, dict):
        raise ValueError(f"Capability file {path} must contain a YAML mapping.")
    config = CapabilityConfig.model_validate(data)
    eval_path = (_repo_root(path) / config.eval_set).resolve()
    return CapabilityDefinition(
        capability_id=config.id,
        name=config.name,
        description=config.description,
        system_prompt=config.system_prompt,
        prompt_template=config.prompt_template,
        eval_set=eval_path,
        labels=tuple(config.labels),
        critical_label=config.critical_label,
        critical_terms=tuple(t.lower() for t in config.critical_terms),
        critical_false_negative_reason=config.critical_false_negative_reason,
        acceptance=AcceptanceCriteria(
            min_accuracy=config.acceptance.min_accuracy,
            zero_critical_false_negatives=config.acceptance.zero_critical_false_negatives,
        ),
        max_recovery_window_minutes=config.max_recovery_window_minutes,
        declared_integration_overhead_minutes=config.declared_integration_overhead_minutes,
        fallback_procedure=config.fallback_procedure,
        tool_contracts=config.tool_contracts,
        policy_constraints=config.policy_constraints,
    )


def capability_to_dict(capability: CapabilityDefinition) -> dict[str, Any]:
    return {
        "id": capability.capability_id,
        "name": capability.name,
        "description": capability.description,
        "eval_set": str(capability.eval_set),
        "labels": list(capability.labels),
        "critical_label": capability.critical_label,
        "critical_terms": list(capability.critical_terms),
        "critical_false_negative_reason": capability.critical_false_negative_reason,
        "acceptance": {
            "min_accuracy": capability.acceptance.min_accuracy,
            "zero_critical_false_negatives": (
                capability.acceptance.zero_critical_false_negatives
            ),
        },
        "max_recovery_window_minutes": capability.max_recovery_window_minutes,
        "declared_integration_overhead_minutes": (
            capability.declared_integration_overhead_minutes
        ),
        "fallback_procedure": capability.fallback_procedure,
        "tool_contracts": capability.tool_contracts,
        "policy_constraints": capability.policy_constraints,
    }
