from pathlib import Path

from core.capability import load_capability
from core.contracts import ModelEndpoint
from tests.fixtures.mock_endpoint import MockEndpoint


def test_mock_endpoint_satisfies_protocol() -> None:
    endpoint: ModelEndpoint = MockEndpoint("mock")
    assert endpoint.health().ok


def test_capability_loads_eval_path() -> None:
    capability = load_capability(Path("profiles/capabilities/phi-classification.yaml"))
    assert capability.eval_set.exists()
    assert capability.acceptance.min_accuracy == 0.9
