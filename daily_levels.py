from dotenv import load_dotenv
load_dotenv()

import backtest_engine as be
from datetime import datetime, timezone, timedelta


def extract_daily_levels(ticker: str, lookback_days: int = 20) -> dict:
    """
    Extract key daily support/resistance levels from recent price history.

    Returns the recent high, recent low, and the most significant intermediate
    levels based on how many times price reacted near them (touches).
    """
    end = datetime.now(timezone.utc)
    start = end - timedelta(days=lookback_days + 10)

    daily_bars = be.get_historical_bars(ticker, start, end)
    if not daily_bars:
        return {}

    highs = [float(b.high) for b in daily_bars[-lookback_days:]]
    lows = [float(b.low) for b in daily_bars[-lookback_days:]]
    closes = [float(b.close) for b in daily_bars[-lookback_days:]]

    recent_high = max(highs)
    recent_low = min(lows)
    current_price = closes[-1] if closes else 0.0

    # Find levels where price touched multiple times (within a small tolerance band)
    all_prices = highs + lows
    tolerance = (recent_high - recent_low) * 0.01  # 1% of the range

    clusters = []  # list of [sum_of_prices, count] for running-average clustering
    for price in sorted(all_prices):
        matched = False
        for cluster in clusters:
            cluster_avg = cluster[0] / cluster[1]
            if abs(price - cluster_avg) <= tolerance:
                cluster[0] += price
                cluster[1] += 1
                matched = True
                break
        if not matched:
            clusters.append([price, 1])

    touch_counts = {cluster[0] / cluster[1]: cluster[1] for cluster in clusters}

    significant_levels = sorted(
        [(level, count) for level, count in touch_counts.items() if count >= 3],
        key=lambda x: x[1],
        reverse=True
    )

    return {
        "current_price": current_price,
        "recent_high": recent_high,
        "recent_low": recent_low,
        "significant_levels": significant_levels[:5],
    }


if __name__ == "__main__":
    ticker = "AAPL"
    levels = extract_daily_levels(ticker)
    print(f"Daily levels for {ticker}:")
    print(f"  Current price: ${levels['current_price']:.2f}")
    print(f"  Recent high (20d): ${levels['recent_high']:.2f}")
    print(f"  Recent low (20d): ${levels['recent_low']:.2f}")
    print(f"  Significant levels (touched 3+ times):")
    for level, count in levels['significant_levels']:
        print(f"    ${level:.2f} — touched {count} times")