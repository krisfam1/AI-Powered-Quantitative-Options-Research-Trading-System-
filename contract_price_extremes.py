from dotenv import load_dotenv
load_dotenv()

import os
from massive import RESTClient
from datetime import datetime, timezone, date, timedelta
from zoneinfo import ZoneInfo

api_key = os.environ.get("MASSIVE_API_KEY")
client = RESTClient(api_key)

ET = ZoneInfo("America/New_York")


def get_contract_price_extremes(contract_symbol: str, entry_date: str, exit_date: str = None) -> dict:
    """
    Find the real high and low price for an options contract between entry_date
    and exit_date (or today, if the position is still open).

    Returns UTC and ET timestamps for both the peak and trough, plus the actual
    price values -- pulled from real historical minute-bar data (Massive API).

    HONEST LIMITATION: the free tier has a rolling data delay, so very recent
    dates (typically the last 1-2 days) may not be available yet.
    """
    if exit_date is None:
        exit_date = date.today().isoformat()

    try:
        aggs = []
        for a in client.list_aggs(
            ticker="O:" + contract_symbol,
            multiplier=1,
            timespan="minute",
            from_=entry_date,
            to=exit_date,
            limit=50000,
        ):
            aggs.append(a)
    except Exception as exc:
        return {"error": str(exc)}

    if not aggs:
        return {"error": "no data returned"}

    peak_price = 0.0
    peak_time = None
    trough_price = float("inf")
    trough_time = None

    for bar in aggs:
        if bar.close > peak_price:
            peak_price = bar.close
            peak_time = bar.timestamp
        if bar.close < trough_price:
            trough_price = bar.close
            trough_time = bar.timestamp

    peak_dt_utc = datetime.fromtimestamp(peak_time / 1000, tz=timezone.utc)
    peak_dt_et = peak_dt_utc.astimezone(ET)
    trough_dt_utc = datetime.fromtimestamp(trough_time / 1000, tz=timezone.utc)
    trough_dt_et = trough_dt_utc.astimezone(ET)

    return {
        "peak_price": round(peak_price, 2),
        "peak_time_utc": peak_dt_utc.isoformat(),
        "peak_time_et": peak_dt_et.strftime("%Y-%m-%d %I:%M %p ET"),
        "trough_price": round(trough_price, 2),
        "trough_time_utc": trough_dt_utc.isoformat(),
        "trough_time_et": trough_dt_et.strftime("%Y-%m-%d %I:%M %p ET"),
        "bars_analyzed": len(aggs),
    }


if __name__ == "__main__":
    result = get_contract_price_extremes("AAPL260831P00305000", "2026-08-25", "2026-08-25")
    for k, v in result.items():
        print(k + ": " + str(v))