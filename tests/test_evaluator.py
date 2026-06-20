from core.evaluator import normalize_label

LABELS = ("CONTAINS_PHI", "NO_PHI")


def test_normalize_label_extracts_known_label() -> None:
    assert normalize_label("The answer is CONTAINS_PHI.", LABELS) == "CONTAINS_PHI"
    assert normalize_label("no_phi", LABELS) == "NO_PHI"
    assert normalize_label("unclear", LABELS) == "UNPARSEABLE"
