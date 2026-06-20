from __future__ import annotations

import math


def wilson_interval(successes: int, total: int, z: float = 1.96) -> tuple[float, float]:
    """Wilson score 95% confidence interval for a binomial proportion.

    Preferred over the normal approximation at small sample sizes, which is exactly
    the regime an eval-driven swap test lives in. Returns (low, high), clamped to
    [0, 1]. An empty sample returns the full [0, 1] interval (maximum uncertainty).
    """
    if total <= 0:
        return (0.0, 1.0)
    phat = successes / total
    denom = 1 + z**2 / total
    center = (phat + z**2 / (2 * total)) / denom
    margin = (z / denom) * math.sqrt(phat * (1 - phat) / total + z**2 / (4 * total**2))
    return (max(0.0, center - margin), min(1.0, center + margin))
