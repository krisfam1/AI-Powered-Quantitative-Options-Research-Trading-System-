from dotenv import load_dotenv
load_dotenv()

"""
Real, computed statistical correlation engine for the main options bot's
trades. Mirrors spy_gamma_statistical_analysis.py's approach: actual
calculated win rates and average P&L per real factor, not AI-eyeballed
pattern reading. Excludes spy-gamma- trades (those have their own,
separate analysis system).
"""

import json
import sqlite3


def _get_main_bot_trades() -> list[dict]:
    with sqlite3.connect("options_trades.db") as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            "SELECT * FROM options_trades WHERE trade_id NOT LIKE 'spy-gamma-%' AND exit_date IS NOT NULL"
        ).fetchall()

    trades = []
    for r in rows:
        gamma_context = {}
        if r["gamma_context"]:
            try:
                gamma_context = json.loads(r["gamma_context"])
            except Exception:
                pass

        same_day = r["entry_date"] == r["exit_date"]

        gamma_modifier = r["gamma_modifier"]
        if gamma_modifier is None:
            modifier_bucket = "unknown"
        elif gamma_modifier > 1.0:
            modifier_bucket = "sized_up"
        elif gamma_modifier < 1.0:
            modifier_bucket = "sized_down"
        else:
            modifier_bucket = "neutral"

        trades.append({
            "trade_id": r["trade_id"],
            "ticker": r["ticker"],
            "option_type": r["option_type"],
            "exit_reason": r["exit_reason"],
            "pnl_pct": r["pnl_pct"],
            "pnl_dollars": r["pnl_dollars"],
            "same_day": same_day,
            "gamma_regime": gamma_context.get("regime"),
            "modifier_bucket": modifier_bucket,
            "gamma_context": gamma_context,
        })
    return trades


def compute_main_bot_statistics(trades: list[dict]) -> dict:
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

    # Option type
    for opt_type in ["call", "put"]:
        matching = [t for t in trades if t["option_type"] == opt_type]
        if matching:
            stats["option_type=" + opt_type] = _compute_group_stats(matching)

    # Hold duration
    same_day = [t for t in trades if t["same_day"]]
    swing = [t for t in trades if not t["same_day"]]
    if same_day:
        stats["hold=same_day"] = _compute_group_stats(same_day)
    if swing:
        stats["hold=swing"] = _compute_group_stats(swing)

    # Exit reason
    exit_reasons = set(t["exit_reason"] for t in trades if t["exit_reason"])
    for reason in exit_reasons:
        matching = [t for t in trades if t["exit_reason"] == reason]
        stats["exit_reason=" + reason] = _compute_group_stats(matching)

    # Ticker
    tickers = set(t["ticker"] for t in trades)
    for ticker in tickers:
        matching = [t for t in trades if t["ticker"] == ticker]
        stats["ticker=" + ticker] = _compute_group_stats(matching)

    # Gamma regime (only for trades where this was captured)
    for regime_val in ["negative", "positive", "neutral"]:
        matching = [t for t in trades if t["gamma_regime"] == regime_val]
        if matching:
            stats["gamma_regime=" + regime_val] = _compute_group_stats(matching)


    _bucket_by_greeks(trades, stats)

    # Gamma modifier bucket
    for bucket in ["sized_up", "neutral", "sized_down"]:
        matching = [t for t in trades if t["modifier_bucket"] == bucket]
        if matching:
            stats["gamma_modifier=" + bucket] = _compute_group_stats(matching)

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
    trades = _get_main_bot_trades()
    print("Total closed main-bot trades: " + str(len(trades)))

    if not trades:
        print("No trades yet -- no statistics to compute.")
    else:
        stats = compute_main_bot_statistics(trades)
        print("\nReal, computed statistics by factor:\n")
        for factor, s in stats.items():
            print("  " + factor + ": n=" + str(s["count"]) + ", win_rate=" + str(s["win_rate"]) + "%, avg_pnl=" + str(s["avg_pnl_pct"]) + "%")
