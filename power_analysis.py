"""
Power analysis helper for pre-registrations (CLAUDE.md Section 1 convention, 2026-10-01).

Every new pre-registration file should carry a module-level POWER_ANALYSIS dict built
with this module, kept OUTSIDE the ExperimentConfig so it never changes a config hash.

Method: Fisher-z approximation for a one-sided test of a Pearson correlation.
    power = Phi( atanh(|r|) * sqrt(N - 3) - z_(1 - alpha) )
It treats observations as independent. For day-clustered designs, use the number of
independent clusters (days) as N for a conservative figure; an upper bound uses the
raw observation count.
"""
import math
from statistics import NormalDist

_N = NormalDist()


def power_one_sided(r: float, n: int, alpha: float) -> float:
    return _N.cdf(math.atanh(abs(r)) * math.sqrt(n - 3) - _N.inv_cdf(1 - alpha))


def n_for_power(r: float, alpha: float, power: float = 0.80) -> int:
    z = _N.inv_cdf(1 - alpha) + _N.inv_cdf(power)
    return math.ceil((z / math.atanh(abs(r))) ** 2 + 3)


def mde_r(n: int, alpha: float, power: float = 0.80) -> float:
    """Minimum |r| detectable with the given power at sample size n."""
    z = _N.inv_cdf(1 - alpha) + _N.inv_cdf(power)
    return math.tanh(z / math.sqrt(n - 3))


def power_table(n: int, alpha: float, rs=(0.15, 0.20, 0.25), computed="", note="") -> dict:
    return {
        "method": "Fisher-z approximation, one-sided Pearson correlation (independent observations)",
        "computed": computed,
        "n": n,
        "alpha_one_sided": alpha,
        "power_at_r": {f"{r:.2f}": round(power_one_sided(r, n, alpha), 3) for r in rs},
        "mde_r_at_80pct_power": round(mde_r(n, alpha), 3),
        "n_needed_for_80pct_power": {f"{r:.2f}": n_for_power(r, alpha) for r in rs},
        "note": note,
    }


if __name__ == "__main__":
    a = 0.05 / 3
    for n in (100, 200, 389, 530, 600):
        print(n, {f"{r}": round(power_one_sided(r, n, a), 3) for r in (0.15, 0.20, 0.25)}, "MDE80:", round(mde_r(n, a), 3))
    print("N for 80% power:", {r: n_for_power(r, a) for r in (0.15, 0.20, 0.25)})
