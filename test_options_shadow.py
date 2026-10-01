from dotenv import load_dotenv
load_dotenv()

from live_options_trader import check_signal_and_trade_options
from main import LIVE_TICKERS

for ticker in LIVE_TICKERS:
    print(f"\nChecking {ticker}...")
    result = check_signal_and_trade_options(ticker)
    print(f"  Signal fired: {result['signal_fired']}")
    print(f"  Note: {result['note']}")