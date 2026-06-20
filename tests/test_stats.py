from core.stats import wilson_interval


def test_wilson_interval_brackets_point_estimate() -> None:
    low, high = wilson_interval(14, 16)
    assert low < 0.875 < high
    # At n=16 the interval is wide enough to straddle a 0.90 acceptance bar.
    assert high > 0.90


def test_wilson_interval_perfect_score_is_not_certain() -> None:
    # 16/16 still cannot prove >0.90 at 95% confidence — the lower bound sits below it.
    low, high = wilson_interval(16, 16)
    assert high == 1.0
    assert low < 0.90


def test_wilson_interval_empty_sample_is_maximally_uncertain() -> None:
    assert wilson_interval(0, 0) == (0.0, 1.0)
