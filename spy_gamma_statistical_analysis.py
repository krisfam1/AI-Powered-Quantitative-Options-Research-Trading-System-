from dotenv import load_dotenv
load_dotenv()

"""
Real, computed statistical correlation engine for SPY gamma trades.

Unlike a prompt-based AI review (which just reads a list and eyeballs
patterns), this computes ACTUAL statistics: for every gamma_context
factor, the real win rate and average P&L for trades that had that
factor present vs. trades that didn't. This genuinely gets more
statistically meaningful as more real trades accumulate -- unlike a
trained ML model, it doesn't need huge sample sizes to start being
useful, and there's no "black box" -- every number is a real,
verifiable calculation.
"""

import json
import sqlite3


def _get_spy_gamma_trades() -> list[dict]:
    with sqlite3.connect("options_trades.db") as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            "SELECT * FROM options_trades WHERE trade_id LIKE 'spy-gamma-%' AND exit_date IS NOT NULL"
        ).fetchall()

    trades = []
    for r in rows:
        gamma_context = {}
        if r["gamma_context"]:
            try:
                gamma_context = json.loads(r["gamma_context"])
            except Exception:
                pass
        trades.append({
            "trade_id": r["trade_id"],
            "pnl_pct": r["pnl_pct"],
            "pnl_dollars": r["pnl_dollars"],
            "exit_reason": r["exit_reason"],
            "gamma_context": gamma_context,
        })
    return trades


def compute_factor_statistics(trades: list[dict]) -> dict:
    """
    For each real feature (regime, each confluence bonus, each tranche
    type), computes real win rate and avg P&L for trades WITH that
    feature vs trades WITHOUT it.
    """
    if not trades:
        return {}

    stats = {}

    def _compute_group_stats(group: list[dict]) -> dict:
        if not group:
            return {"count": 0, "win_rate": None, "avg_pnl_pct": None}
        wins = [t for t in group if t["pnl_dollars"] > 0]
        return {
            "count": len(group),
            "win_rate": round(len(wins) / len(group) * 100, 1),
            "avg_pnl_pct": round(sum(t["pnl_pct"] for t in group) / len(group), 1),
        }

    # Regime
    for regime_val in ["negative", "positive", "neutral"]:
        with_regime = [t for t in trades if t["gamma_context"].get("regime") == regime_val]
        if with_regime:
            stats["regime=" + regime_val] = _compute_group_stats(with_regime)

    # Tranche type
    for tranche_val in ["A", "B", "C", "RUNNER"]:
        with_tranche = [t for t in trades if t["gamma_context"].get("tranche") == tranche_val]
        if with_tranche:
            stats["tranche=" + tranche_val] = _compute_group_stats(with_tranche)

    # Confluence bonuses (charm pin, daily S/R level) -- present vs absent
    all_bonus_texts = set()
    for t in trades:
        for b in t["gamma_context"].get("confluence_bonuses", []):
            all_bonus_texts.add(b)

    for bonus_text in all_bonus_texts:
        with_bonus = [t for t in trades if bonus_text in t["gamma_context"].get("confluence_bonuses", [])]
        without_bonus = [t for t in trades if bonus_text not in t["gamma_context"].get("confluence_bonuses", [])]
        stats["WITH: " + bonus_text] = _compute_group_stats(with_bonus)
        stats["WITHOUT: " + bonus_text] = _compute_group_stats(without_bonus)


    _bucket_by_greeks(trades, stats)

    # Zero vs one vs multiple confluence bonuses
    for n_bonuses in [0, 1, 2]:
        matching = [t for t in trades if len(t["gamma_context"].get("confluence_bonuses", [])) == n_bonuses]
        if matching:
            stats[str(n_bonuses) + " confluence bonus(es)"] = _compute_group_stats(matching)

    return stats


def _bucket_by_greeks(trades: list[dict], stats: dict) -> None:
    """Adds delta (fixed buckets) and gamma/charm (dynamic terciles) bucketing, in-place."""
    def _group_stats(group):
        if not group:
            return None
        wins = [t for t in group if t["pnl_dollars"] > 0]
        return {
            "count": len(group),
            "win_rate": round(len(wins) / len(group) * 100, 1),
            "avg_pnl_pct": round(sum(t["pnl_pct"] for t in group) / len(group), 1),
        }

    with_delta = [t for t in trades if t["gamma_context"].get("delta") is not None]
    delta_ranges = [(0.20, 0.30), (0.30, 0.40), (0.40, 0.50), (0.50, 1.01)]
    for lo, hi in delta_ranges:
        matching = [t for t in with_delta if lo <= abs(t["gamma_context"]["delta"]) < hi]
        if matching:
            label = "delta_" + str(lo) + "-" + str(hi if hi < 1 else "1.0+")
            s = _group_stats(matching)
            if s:
                stats[label] = s

    for greek_name in ["gamma", "charm"]:
        with_greek = [t for t in trades if t["gamma_context"].get(greek_name) is not None]
        if len(with_greek) >= 3:
            sorted_trades = sorted(with_greek, key=lambda t: abs(t["gamma_context"][greek_name]))
            n = len(sorted_trades)
            third = max(n // 3, 1)
            low = sorted_trades[:third]
            mid = sorted_trades[third:2*third]
            high = sorted_trades[2*third:]
            for label, group in [("low", low), ("mid", mid), ("high", high)]:
                s = _group_stats(group)
                if s:
                    stats[greek_name + "_" + label] = s


if __name__ == "__main__":
    trades = _get_spy_gamma_trades()
    print("Total closed SPY gamma trades: " + str(len(trades)))

    if not trades:
        print("No trades yet -- no statistics to compute.")
    else:
        stats = compute_factor_statistics(trades)
        print("\nReal, computed statistics by factor:\n")
        for factor, s in stats.items():
            print("  " + factor + ": n=" + str(s["count"]) + ", win_rate=" + str(s["win_rate"]) + "%, avg_pnl=" + str(s["avg_pnl_pct"]) + "%")
