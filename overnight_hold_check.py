from dotenv import load_dotenv
load_dotenv()

"""
Overnight-hold safety check for options positions.

Before market close, evaluates whether it looks safe to hold a position
overnight using two real, checkable signals:
  1. News sentiment -- recent negative or unusually high-volume news
  2. Volatility spike -- current ATR meaningfully elevated vs. recent normal

HONEST LIMITATION: this does NOT check for upcoming earnings announcements,
since we don't have access to an earnings calendar data source. Earnings
are the single biggest real overnight gap-risk factor for options, and
this check cannot detect them. Treat this as a partial safeguard only.
"""

import backtest_engine as be
from datetime import datetime, timezone, timedelta


def check_overnight_hold_safety(ticker: str, option_type: str = "call") -> dict:
    reasons = []
    safe = True

    now = datetime.now(timezone.utc)

    try:
        news_start = now - timedelta(hours=24)
        news_items = be.get_news_for_ticker(ticker, news_start, now)
        news_positive_or_neutral = be.check_news_sentiment(news_items, now, lookback_hours=24)

        # Negative news is a real risk for a CALL (bullish bet), but is
        # actually FAVORABLE for a PUT (bearish bet) -- direction matters.
        if option_type == "call" and not news_positive_or_neutral:
            safe = False
            reasons.append("recent news sentiment is negative (risk for a call)")
        elif option_type == "put" and not news_positive_or_neutral:
            reasons.append("recent news sentiment is negative (favorable for this put, not flagged as risk)")
    except Exception as exc:
        reasons.append("news check unavailable: " + str(exc))

    try:
        bars = be.get_historical_bars(ticker, now - timedelta(days=10), now)
        if len(bars) > 20:
            current_atr = be.calculate_atr(bars, len(bars) - 1)
            recent_atrs = [be.calculate_atr(bars, i) for i in range(len(bars) - 20, len(bars) - 1)]
            recent_atrs = [a for a in recent_atrs if a > 0]
            if recent_atrs:
                avg_atr = sum(recent_atrs) / len(recent_atrs)
                if avg_atr > 0 and current_atr > avg_atr * 1.75:
                    safe = False
                    reasons.append(
                        "volatility spike -- current ATR is " +
                        str(round(current_atr / avg_atr, 2)) + "x the recent average"
                    )
    except Exception as exc:
        reasons.append("volatility check unavailable: " + str(exc))

    if not reasons:
        reasons.append("no elevated risk signals detected")

    return {"safe": safe, "reasons": reasons}


if __name__ == "__main__":
    for ticker in ["AAPL", "TSLA", "NVDA", "AMD", "SMCI", "MSTR"]:
        result = check_overnight_hold_safety(ticker)
        status = "SAFE" if result["safe"] else "NOT SAFE"
        print(ticker + ": " + status + " -- " + "; ".join(result["reasons"]))