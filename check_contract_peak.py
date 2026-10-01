from dotenv import load_dotenv
load_dotenv()

import os
import sys
from massive import RESTClient
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

api_key = os.environ.get("MASSIVE_API_KEY")
client = RESTClient(api_key)


def check_contract_peak(contract_symbol: str, entry_premium: float, date_str: str):
    """
    Check the real intraday peak for an options contract on a specific date.

    contract_symbol: without the "O:" prefix, e.g. "TSLA260831P00345000"
    entry_premium: your actual entry price, for calculating gain %
    date_str: "YYYY-MM-DD" format, e.g. "2026-08-26"
    """
    symbol = "O:" + contract_symbol

    print("Fetching real minute data for " + symbol + " on " + date_str + "...\n")

    try:
        aggs = []
        for a in client.list_aggs(
            ticker=symbol,
            multiplier=1,
            timespan="minute",
            from_=date_str,
            to=date_str,
            limit=50000,
        ):
            aggs.append(a)
    except Exception as exc:
        print("FAILED: " + str(exc))
        print("(This usually means the date is too recent -- try again in a day or two.)")
        return

    print("Total bars found: " + str(len(aggs)) + "\n")

    if not aggs:
        print("No data returned for this date.")
        return

    peak_price = 0.0
    peak_time = None

    for bar in aggs:
        if bar.close > peak_price:
            peak_price = bar.close
            peak_time = bar.timestamp

    peak_pct = (peak_price - entry_premium) / entry_premium * 100
    peak_dt_utc = datetime.fromtimestamp(peak_time / 1000, tz=timezone.utc)
    peak_dt_et = peak_dt_utc.astimezone(ZoneInfo("America/New_York"))

    print("Entry premium: $" + str(entry_premium))
    print("PEAK price: $" + str(round(peak_price, 2)))
    print("Peak gain: " + str(round(peak_pct, 1)) + "%")
    print("Peak time (ET): " + peak_dt_et.strftime("%Y-%m-%d %I:%M %p ET"))
    print("Peak time (UTC): " + str(peak_dt_utc))


if __name__ == "__main__":
    check_contract_peak(
        contract_symbol="TSLA260831P00345000",
        entry_premium=4.30,
        date_str="2026-08-26",
    )