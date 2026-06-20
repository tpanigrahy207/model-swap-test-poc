from __future__ import annotations

import json
import re
from pathlib import Path

from core.contracts import (
    CapabilityDefinition,
    EnterpriseState,
    EvalExample,
    EvalResult,
    ModelEndpoint,
    RouteRecord,
)

UNPARSEABLE = "UNPARSEABLE"


def load_eval_set(path: Path, labels: tuple[str, ...]) -> list[EvalExample]:
    examples: list[EvalExample] = []
    with path.open() as handle:
        for line_number, line in enumerate(handle, start=1):
            stripped = line.strip()
            if not stripped:
                continue
            data = json.loads(stripped)
            examples.append(
                EvalExample(
                    eval_id=str(data["id"]),
                    input_text=str(data["input"]),
                    expected=str(data["expected"]),
                    rationale=str(data.get("rationale", "")),
                )
            )
            if examples[-1].expected not in labels:
                raise ValueError(f"Unsupported expected label at {path}:{line_number}")
    return examples


def normalize_label(text: str, labels: tuple[str, ...]) -> str:
    upper = text.upper()
    for label in labels:
        if re.search(rf"\b{re.escape(label)}\b", upper):
            return label
    return UNPARSEABLE


def evaluate_endpoint(
    capability: CapabilityDefinition,
    endpoint: ModelEndpoint,
    state: EnterpriseState,
) -> list[EvalResult]:
    examples = load_eval_set(capability.eval_set, capability.labels)
    results: list[EvalResult] = []
    for example in examples:
        prompt = capability.prompt_template.format(input=example.input_text)
        completion = endpoint.complete(prompt=prompt, system=capability.system_prompt)
        observed = normalize_label(completion.text, capability.labels)
        passed = observed == example.expected
        result = EvalResult(
            eval_id=example.eval_id,
            input_text=example.input_text,
            expected=example.expected,
            observed=observed,
            passed=passed,
            rationale=example.rationale,
            latency_ms=completion.latency_ms,
            input_tokens=completion.input_tokens,
            output_tokens=completion.output_tokens,
            cost_usd=completion.cost_usd,
        )
        results.append(result)
        state.record(
            RouteRecord(
                capability_id=capability.capability_id,
                eval_id=example.eval_id,
                endpoint_name=endpoint.name,
                expected=example.expected,
                observed=observed,
                passed=passed,
                latency_ms=completion.latency_ms,
            )
        )
    return results
