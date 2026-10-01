from dotenv import load_dotenv
load_dotenv()

"""
SPY gamma/charm day-trading bot.

Entirely separate strategy from the main confluence-based system, trading
ONLY SPY, using ONLY gamma/charm/level-derived signals -- reusing the
existing gamma_landscape, gamma_gradient, charm_landscape, and
daily_levels tools built earlier.

DAY TRADING CONSTRAINT: positions must close same-day, no overnight hold,
given SPY's high liquidity and to avoid gap risk on an experimental,
forward-test-only strategy.

HONEST LIMITATION: cannot be backtested (no historical open-interest
data). Pure live forward-test from day one, same discipline as the
standalone gamma forward-test logger. Shares the main account, but is
completely separately tracked via the "spy-gamma-" trade_id prefix --
SPY never appears in the main bot's ticker list, so all SPY trades are
unambiguously this strategy.
"""

import os
import sqlite3
from datetime import datetime, timezone, date
from alpaca.trading.client import TradingClient
from alpaca.trading.requests import MarketOrderRequest as OptMarketOrderRequest
from alpaca.trading.enums import OrderSide as OptOrderSide, TimeInForce as OptTimeInForce

import backtest_engine as be
from gamma_regime import calculate_net_gamma_regime
from gamma_landscape import build_gamma_landscape, find_gamma_walls
from gamma_gradient import calculate_gamma_gradient, find_steepest_gradient_zones
from charm_landscape import build_charm_landscape, find_charm_pins
from daily_levels import extract_daily_levels
from options_data import get_options_chain
import options_trade_log

api_key = os.environ.get("ALPACA_API_KEY")
secret_key = os.environ.get("ALPACA_SECRET_KEY")
_trading_client = TradingClient(api_key, secret_key, paper=True)

SPY_GAMMA_SHADOW_MODE = True

WALL_PROXIMITY_PCT = 0.010
CHARM_PROXIMITY_PCT = 0.010
LEVEL_PROXIMITY_PCT = 0.010
STOP_LOSS_PCT = 0.45
TAKE_PROFIT_PCT = 0.75
POSITION_RISK_PCT = 0.01
DTE_TARGET = 5


def check_spy_gamma_signal() -> dict:
    ticker = "SPY"
    now = datetime.now(timezone.utc)

    try:
        from datetime import timedelta
        bars = be.get_historical_bars(ticker, now - timedelta(days=5), now)
        current_price = float(bars[-1].close)
    except Exception as exc:
        return {"signal_fired": False, "note": "could not fetch current price: " + str(exc)}

    try:
        regime_result = calculate_net_gamma_regime(ticker, current_price)
    except Exception as exc:
        return {"signal_fired": False, "note": "regime check failed: " + str(exc)}

    if regime_result["regime"] != "negative":
        return {"signal_fired": False, "note": "regime is " + regime_result["regime"] + ", not negative -- no signal"}

    try:
        gamma_landscape = build_gamma_landscape(ticker, current_price)
        walls = find_gamma_walls(gamma_landscape, top_n=5)
        gradients = calculate_gamma_gradient(gamma_landscape)
        steep_zones = find_steepest_gradient_zones(gradients, top_n=5)
    except Exception as exc:
        return {"signal_fired": False, "note": "gamma landscape/gradient fetch failed: " + str(exc)}

    confirmed_wall = None
    for wall in walls:
        distance = abs(wall["strike"] - current_price) / current_price
        if distance <= WALL_PROXIMITY_PCT:
            for zone in steep_zones:
                if zone["strike_range"][0] <= wall["strike"] <= zone["strike_range"][1]:
                    confirmed_wall = wall["strike"]
                    break
            if confirmed_wall:
                break

    if confirmed_wall is None:
        return {"signal_fired": False, "note": "no gamma wall within " + str(WALL_PROXIMITY_PCT*100) + "% confirmed by a steep gradient zone"}

    confluence_notes = []
    try:
        charm_landscape = build_charm_landscape(ticker, current_price)
        pins = find_charm_pins(charm_landscape, top_n=5)
        for pin in pins:
            if abs(pin["strike"] - confirmed_wall) / confirmed_wall <= CHARM_PROXIMITY_PCT:
                confluence_notes.append("charm pin confirms this level")
                break
    except Exception:
        pass

    try:
        levels = extract_daily_levels(ticker)
        for level, touches in levels.get("significant_levels", []):
            if abs(level - confirmed_wall) / confirmed_wall <= LEVEL_PROXIMITY_PCT:
                confluence_notes.append("daily S/R level (" + str(touches) + " touches) confirms this level")
                break
    except Exception:
        pass

    option_type = "call" if current_price > confirmed_wall else "put"

    note = (
        ticker + ": negative regime, price $" + str(round(current_price, 2)) +
        " near confirmed gamma wall $" + str(confirmed_wall) +
        " (gradient-confirmed) -- " + option_type + " signal"
    )
    if confluence_notes:
        note += " | bonus confluence: " + "; ".join(confluence_notes)

    return {
        "signal_fired": True,
        "ticker": ticker,
        "option_type": option_type,
        "current_price": current_price,
        "wall_price": confirmed_wall,
        "regime": regime_result["regime"],
        "confluence_bonuses": confluence_notes,
        "note": note,
    }


if __name__ == "__main__":
    print("Checking SPY gamma/charm day-trade signal...\n")
    result = check_spy_gamma_signal()
    print(result["note"])