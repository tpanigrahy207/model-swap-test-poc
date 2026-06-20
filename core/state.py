from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path

from core.contracts import RouteRecord


class JsonlEnterpriseState:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def record(self, route_record: RouteRecord) -> None:
        with self.path.open("a") as handle:
            handle.write(json.dumps(asdict(route_record), sort_keys=True) + "\n")

    def query(self, capability_id: str | None = None) -> list[RouteRecord]:
        if not self.path.exists():
            return []
        records: list[RouteRecord] = []
        with self.path.open() as handle:
            for line in handle:
                data = json.loads(line)
                if capability_id is not None and data["capability_id"] != capability_id:
                    continue
                records.append(
                    RouteRecord(
                        capability_id=str(data["capability_id"]),
                        eval_id=str(data["eval_id"]),
                        endpoint_name=str(data["endpoint_name"]),
                        expected=str(data["expected"]),
                        observed=str(data["observed"]),
                        passed=bool(data["passed"]),
                        latency_ms=float(data["latency_ms"]),
                    )
                )
        return records
