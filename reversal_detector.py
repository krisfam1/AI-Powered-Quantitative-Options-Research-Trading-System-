from dotenv import load_dotenv
load_dotenv()

"""
Reversal detector for profitable open positions.

Once a position shows meaningful unrealized profit, this checks whether
the underlying stock's short-term momentum has turned against the
position's direction -- a real, detectable early-warning signal, distinct
from a pure trailing-stop (which only reacts to price, not to underlying
trend structure).

Design: uses a short (5-bar) moving average on the underlying. If price
crosses back against the position's direction relative to that average
while in meaningful profit, flags a likely reversal.
"""

import backtest_engine as be
from datetime import datetime, timezone, timedelta


def check_reversal_signal(ticker: str, option_type: str, profit_pct: float, reversal_threshold: float = 0.40) -> dict:
    """
    Returns {"reversal_detected": bool, "reason": str}.

    Only actively checks once profit_pct exceeds reversal_threshold (default 40%),
    since this is meant to protect meaningful gains, not react to small moves.
    """
    if profit_pct < reversal_threshold:
        return {"reversal_detected": False, "reason": "profit below threshold, not checking yet"}

    now = datetime.now(timezone.utc)
    bars = be.get_historical_bars(ticker, now - timedelta(hours=3), now)

    if len(bars) < 7:
        return {"reversal_detected": False, "reason": "not enough recent bars to evaluate"}

    closes = [float(b.close) for b in bars]

    last_two = closes[-2:]
    ma_before_last_two = sum(closes[-7:-2]) / 5

    if option_type == "call":
        if all(c < ma_before_last_two for c in last_two):
            return {
                "reversal_detected": True,
                "reason": ticker + " price held below its 5-bar average ($" + str(round(ma_before_last_two, 2)) + ") for 2 consecutive bars while position is +" + str(round(profit_pct * 100, 1)) + "% -- sustained reversal signal",
            }
    else:
        if all(c > ma_before_last_two for c in last_two):
            return {
                "reversal_detected": True,
                "reason": ticker + " price held above its 5-bar average ($" + str(round(ma_before_last_two, 2)) + ") for 2 consecutive bars while position is +" + str(round(profit_pct * 100, 1)) + "% -- sustained reversal signal",
            }

    return {"reversal_detected": False, "reason": "no sustained reversal signal detected"}


if __name__ == "__main__":
    result = check_reversal_signal("TSLA", "put", 0.70)
    print(result)