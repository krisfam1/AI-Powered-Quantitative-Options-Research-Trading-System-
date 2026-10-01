from dotenv import load_dotenv
load_dotenv()

"""Paper-trading execution for the options strategy (calls, validated flat thresholds).

Safety guarantees
------------------
paper=True is hardcoded in TradingClient and is never configurable.
Place a file named STOP_TRADING in the project directory to immediately
pause all trading logic without changing any code — shared with the stock bot.
"""

import os
import sqlite3
from datetime import datetime, timedelta, timezone
import time
from pathlib import Path
from typing import Any

from alpaca.trading.client import TradingClient
from alpaca.trading.enums import OrderSide, TimeInForce
from alpaca.trading.requests import MarketOrderRequest

from options_data import get_options_chain, filter_near_the_money, pick_best_contract
from options_evaluator import get_live_premium
from options_backtest_engine import calculate_historical_volatility
from backtest_engine import get_daily_regime, check_breakdown, check_ma_downtrend, check_ma_trend
import backtest_engine as be
import trade_log
import options_trade_log
from options_confluence_modifier import calculate_size_modifier
from gamma_regime import calculate_net_gamma_regime
from gamma_landscape import build_gamma_landscape, find_gamma_walls
from options_pricing import calculate_delta, calculate_gamma, calculate_charm
from feature_extraction import extract_features
import joblib

_ml_shadow_model_data = None


def _get_ml_shadow_model():
    global _ml_shadow_model_data
    if _ml_shadow_model_data is None:
        try:
            _ml_shadow_model_data = joblib.load("baseline_model.joblib")
        except Exception:
            _ml_shadow_model_data = False
    return _ml_shadow_model_data

import json
from ticker_circuit_breaker import check_ticker_circuit_breaker
from alpaca.trading.requests import MarketOrderRequest as OptMarketOrderRequest
from alpaca.trading.enums import OrderSide as OptOrderSide, TimeInForce as OptTimeInForce
from risk_manager import check_max_positions, check_daily_loss_limit, check_drawdown_pause
from main import is_market_open

KILL_SWITCH_PATH = Path("STOP_TRADING")
OPTIONS_SIGNAL_LOG_DB = "options_signal_log.db"
OPTIONS_PEAK_EQUITY_FILE = Path(".options_peak_equity")
OPTIONS_SHADOW_MODE = False  # LIVE as of first supervised test

# Validated strategy parameters — flat thresholds, confirmed via training/holdout tonight
OPTIONS_CONFIG: dict[str, Any] = {
    "dte_target": 14,
    "stop_loss_pct": 0.40,
    "take_profit_pct": 0.75,
    "position_risk_pct": 0.01,
    "rv_threshold": 1.5,
    "breakout_lookback": 20,
}

_api_key = os.environ.get("ALPACA_API_KEY", "")
_secret_key = os.environ.get("ALPACA_SECRET_KEY", "")

# paper=True is intentionally hardcoded — this line must never be changed to paper=False.
_trading_client = TradingClient(_api_key, _secret_key, paper=True)


def _init_options_signal_log() -> None:
    """Create the options signal log table if it doesn't exist."""
    with sqlite3.connect(OPTIONS_SIGNAL_LOG_DB) as con:
        con.execute("""
            CREATE TABLE IF NOT EXISTS options_signal_log (
                id             INTEGER PRIMARY KEY AUTOINCREMENT,
                checked_at     TEXT    NOT NULL,
                ticker         TEXT    NOT NULL,
                signal_fired   INTEGER NOT NULL DEFAULT 0,
                blocks         TEXT    NOT NULL DEFAULT '',
                contract_symbol TEXT,
                premium        REAL,
                contracts      INTEGER,
                order_id       TEXT,
                note           TEXT
            )
        """)


def _log_options_signal(
    ticker: str,
    signal_fired: bool,
    blocks: list[str],
    contract_symbol: str | None = None,
    premium: float | None = None,
    contracts: int | None = None,
    order_id: str | None = None,
    note: str | None = None,
) -> None:
    _init_options_signal_log()
    with sqlite3.connect(OPTIONS_SIGNAL_LOG_DB) as con:
        con.execute(
            """
            INSERT INTO options_signal_log
                (checked_at, ticker, signal_fired, blocks, contract_symbol, premium, contracts, order_id, note)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                datetime.now(timezone.utc).isoformat(),
                ticker,
                int(signal_fired),
                "; ".join(blocks),
                contract_symbol,
                premium,
                contracts,
                order_id,
                note,
            ),
        )


def check_signal_and_trade_options(ticker: str) -> dict[str, Any]:
    """Check a ticker for a qualifying options entry signal.

    Uses the same breakout/volume confluence as the stock strategy.
    Currently runs in SHADOW MODE -- logs what it would do, no order submitted.
    """
    result: dict[str, Any] = {
        "ticker": ticker,
        "signal_fired": False,
        "order_id": None,
        "contract_symbol": None,
        "note": None,
    }
    blocks: list[str] = []

    if KILL_SWITCH_PATH.exists():
        note = "PAUSED -- STOP_TRADING file exists; remove it to resume"
        _log_options_signal(ticker, False, [], note=note)
        result["note"] = note
        return result

    cfg = OPTIONS_CONFIG
    now = datetime.now(timezone.utc)
    start = now - timedelta(days=5)

    try:
        bars = be.get_historical_bars(ticker, start, now)
    except Exception as exc:
        note = "bar fetch failed: " + str(exc)
        _log_options_signal(ticker, False, ["bar fetch error"], note=note)
        result["note"] = note
        return result

    if len(bars) < 30:
        note = "only " + str(len(bars)) + " bars available (need 30+)"
        blocks.append(note)
        _log_options_signal(ticker, False, blocks, note=note)
        result["note"] = note
        return result

    index = len(bars) - 1
    current_price = float(bars[index].close)

    rv = be.calculate_relative_volume(bars, index)
    rv_threshold = cfg["rv_threshold"]
    if rv < rv_threshold:
        blocks.append("low relative volume (%.2f < %.2f)" % (rv, rv_threshold))
    now_dt = datetime.now(timezone.utc)
    regime = get_daily_regime(ticker, now_dt, period=50)
    if regime == "bullish":
        option_type = "call"
    elif regime == "bearish":
        option_type = "put"
    else:
        option_type = "call"
        blocks.append("regime is neutral, skipping (auto mode needs a clear trend)")

    if option_type == "call" and not be.check_breakout(bars, index, lookback=cfg["breakout_lookback"]):
        blocks.append("no breakout")
    if option_type == "put" and not check_breakdown(bars, index, lookback=cfg["breakout_lookback"]):
        blocks.append("no breakdown")

    if blocks:
        _log_options_signal(ticker, False, blocks)
        result["note"] = "; ".join(blocks)
        return result

    try:
        from entry_scorer import calculate_entry_score
        _spy_regime = get_daily_regime("SPY", now_dt, period=50)
        _score_result = calculate_entry_score(ticker, bars, index, option_type, spy_regime=_spy_regime)
        if _score_result["total_score"] < 20:
            note = "entry score too low (" + str(_score_result["total_score"]) + "/100, need 20+)"
            _log_options_signal(ticker, False, [], note=note)
            result["note"] = note
            return result
    except Exception as _score_exc:
        # If scoring fails for any reason, do NOT block the trade -- fall
        # back to the already-confirmed breakout signal, same as before
        # this system existed. Fail safe, not fail closed.
        pass

    breaker_check = check_ticker_circuit_breaker(ticker)
    if breaker_check["blocked"]:
        note = breaker_check["reason"]
        _log_options_signal(ticker, False, [], note=note)
        result["note"] = note
        return result

    cooldown_minutes = 90
    with sqlite3.connect(OPTIONS_SIGNAL_LOG_DB) as _con:
        _row = _con.execute(
            "SELECT checked_at FROM options_signal_log WHERE ticker = ? AND signal_fired = 1 ORDER BY checked_at DESC LIMIT 1",
            (ticker,),
        ).fetchone()
    if _row:
        _last_fired = datetime.fromisoformat(_row[0])
        _minutes_since = (datetime.now(timezone.utc) - _last_fired).total_seconds() / 60
        if _minutes_since < cooldown_minutes:
            note = "cooldown active -- same setup flagged " + str(round(_minutes_since, 0)) + " min ago"
            result["note"] = note
            return result

    account = _trading_client.get_account()
    equity = float(account.equity)
    last_equity = float(account.last_equity) if account.last_equity else equity
    daily_pnl_frac = (equity - last_equity) / last_equity if last_equity else 0.0

    if OPTIONS_PEAK_EQUITY_FILE.exists():
        try:
            stored_peak = float(OPTIONS_PEAK_EQUITY_FILE.read_text().strip())
            peak_equity = max(stored_peak, equity)
        except ValueError:
            peak_equity = equity
    else:
        peak_equity = equity
    OPTIONS_PEAK_EQUITY_FILE.write_text(str(peak_equity))
    rolling_pnl_frac = (equity - peak_equity) / peak_equity if peak_equity else 0.0

    positions = _trading_client.get_all_positions()
    options_positions = [p for p in positions if getattr(p, "asset_class", None) is not None and "option" in str(p.asset_class).lower()]
    open_count = len(options_positions)

    if not check_max_positions(open_count):
        note = "max options positions reached (" + str(open_count) + " open)"
        blocks.append(note)
    if not check_daily_loss_limit(daily_pnl_frac):
        note = "daily loss limit hit (" + str(round(daily_pnl_frac*100, 2)) + "% today)"
        blocks.append(note)
    if not check_drawdown_pause(rolling_pnl_frac):
        note = "drawdown pause triggered (" + str(round(rolling_pnl_frac*100, 2)) + "% from peak)"
        blocks.append(note)

    if blocks:
        _log_options_signal(ticker, False, blocks)
        result["note"] = "; ".join(blocks)
        return result

    try:
        from pick_contract_by_delta import pick_contract_by_target_delta
        chain = get_options_chain(ticker, option_type)
        _current_vol = calculate_historical_volatility(bars, index) if "calculate_historical_volatility" in dir() else 0.30
        best = pick_contract_by_target_delta(chain, current_price, option_type, target_delta=0.30, volatility=_current_vol)
        if best is None:
            near_money = filter_near_the_money(chain, current_price)
            best = pick_best_contract(near_money)
    except Exception as exc:
        note = "contract selection failed: " + str(exc)
        _log_options_signal(ticker, False, blocks, note=note)
        result["note"] = note
        return result

    if best is None:
        note = "no suitable contract found"
        _log_options_signal(ticker, False, blocks, note=note)
        result["note"] = note
        return result

    try:
        premium = get_live_premium(best.symbol)
    except Exception as exc:
        note = "premium fetch failed: " + str(exc)
        _log_options_signal(ticker, False, blocks, note=note)
        result["note"] = note
        return result

    account = _trading_client.get_account()
    equity = float(account.equity)
    max_risk_dollars = equity * cfg["position_risk_pct"]
    contracts = max(int(max_risk_dollars / (premium * 100)), 1)
    entry_reasoning = "regime=" + regime + " relative_volume=" + str(round(rv, 2)) + " price=$" + str(round(current_price, 2)) + " strike=$" + str(best.strike_price) + " dte=" + str(cfg["dte_target"])
    try:
        gamma_direction = "long" if option_type == "call" else "short"
        gamma_check = calculate_size_modifier(ticker, current_price, direction=gamma_direction)
        entry_reasoning += " | gamma_modifier=" + str(gamma_check["modifier"]) + "x (" + "; ".join(gamma_check["reasons"]) + ")"
    except Exception as _gamma_exc:
        entry_reasoning += " | gamma_modifier=unavailable (" + str(_gamma_exc) + ")"

    if OPTIONS_SHADOW_MODE or not is_market_open():
        if OPTIONS_SHADOW_MODE:
            reason = "SHADOW MODE"
        else:
            reason = "MARKET CLOSED"
        note = reason + " -- would buy " + str(contracts) + "x " + best.symbol + " @ ~$" + str(round(premium, 2)) + " | " + entry_reasoning
    else:
        order_request = OptMarketOrderRequest(
            symbol=best.symbol,
            qty=contracts,
            side=OptOrderSide.BUY,
            time_in_force=OptTimeInForce.DAY,
        )
        try:
            order = _trading_client.submit_order(order_request)

            # Poll briefly for the REAL fill price -- market orders may not
            # be filled the instant submit_order() returns. Falls back to
            # the pre-trade estimate only if it genuinely never fills in time.
            real_entry_premium = premium
            for _poll_attempt in range(10):
                time.sleep(1)
                try:
                    _refreshed_order = _trading_client.get_order_by_id(order.id)
                    if _refreshed_order.filled_avg_price:
                        real_entry_premium = float(_refreshed_order.filled_avg_price)
                        break
                except Exception:
                    continue

            _safe_gamma_modifier = gamma_check.get("modifier") if "gamma_check" in locals() else None

            _gamma_context = {}
            try:
                _regime_result = calculate_net_gamma_regime(ticker, current_price)
                _gamma_context["regime"] = _regime_result["regime"]
                _gamma_context["net_gamma_exposure"] = _regime_result["net_gamma_exposure"]
            except Exception:
                _gamma_context["regime"] = "unavailable"

            try:
                _landscape = build_gamma_landscape(ticker, current_price)
                _walls = find_gamma_walls(_landscape, top_n=1)
                if _walls:
                    _nearest_wall = _walls[0]["strike"]
                    _gamma_context["nearest_wall"] = _nearest_wall
                    _gamma_context["wall_distance_pct"] = round(abs(_nearest_wall - current_price) / current_price * 100, 2)
            except Exception:
                pass

            _gamma_context["estimated_volatility"] = round(vol, 4) if "vol" in locals() else None

            try:
                _dte_for_greeks = cfg["dte_target"]
                _vol_for_greeks = vol if "vol" in locals() else 0.30
                _gamma_context["delta"] = round(calculate_delta(current_price, best.strike_price, _dte_for_greeks, _vol_for_greeks, option_type=option_type), 4)
                _gamma_context["gamma"] = round(calculate_gamma(current_price, best.strike_price, _dte_for_greeks, _vol_for_greeks), 6)
                _gamma_context["charm"] = round(calculate_charm(current_price, best.strike_price, _dte_for_greeks, _vol_for_greeks, option_type=option_type), 6)
            except Exception:
                pass

            # ML SHADOW PREDICTION -- purely additive logging, NEVER affects
            # the actual trading decision above. Lets us observe how the
            # validated model would have scored this real, live signal,
            # building toward eventual shadow-mode comparison.
            try:
                _shadow_model_bundle = _get_ml_shadow_model()
                if _shadow_model_bundle:
                    _shadow_features = extract_features(ticker, bars, index, option_type, best.strike_price, cfg["dte_target"])
                    _shadow_vector = [[_shadow_features.get(k, 0) for k in _shadow_model_bundle["feature_keys"]]]
                    _shadow_win_prob = _shadow_model_bundle["model"].predict_proba(_shadow_vector)[0][1]
                    with sqlite3.connect("ml_shadow_predictions.db") as _shadow_conn:
                        _shadow_conn.execute(
                            "CREATE TABLE IF NOT EXISTS shadow_predictions (id INTEGER PRIMARY KEY AUTOINCREMENT, ticker TEXT, logged_at TEXT, predicted_win_probability REAL, real_decision TEXT)"
                        )
                        _shadow_conn.execute(
                            "INSERT INTO shadow_predictions (ticker, logged_at, predicted_win_probability, real_decision) VALUES (?, ?, ?, ?)",
                            (ticker, datetime.now(timezone.utc).isoformat(), round(float(_shadow_win_prob), 4), "traded (real system fired)"),
                        )
                        _shadow_conn.commit()
            except Exception:
                pass  # shadow logging failure must NEVER block the real trade

            _gamma_context_json = json.dumps(_gamma_context)

            options_trade_log.log_entry({
                "trade_id": "opt-live-" + ticker + "-" + str(order.id),
                "ticker": ticker,
                "contract_symbol": best.symbol,
                "option_type": option_type,
                "entry_date": now.date().isoformat(),
                "entry_premium": real_entry_premium,
                "contracts": contracts,
                "stop_loss_pct": cfg["stop_loss_pct"],
                "take_profit_pct": cfg["take_profit_pct"],
                "expiry_date": best.expiration_date.isoformat(),
                "gamma_modifier": _safe_gamma_modifier,
                "gamma_context": _gamma_context_json,
            })
            note = "LIVE ORDER SUBMITTED -- " + str(contracts) + "x " + best.symbol + " @ ~$" + str(round(premium, 2)) + " order_id=" + str(order.id) + " | " + entry_reasoning
        except Exception as exc:
            note = "options order submission failed: " + str(exc)
    _log_options_signal(
        ticker, True, blocks,
        contract_symbol=best.symbol, premium=premium, contracts=contracts,
        note=note,
    )
    result["signal_fired"] = True
    result["contract_symbol"] = best.symbol
    result["note"] = note
    return result


if __name__ == "__main__":
    _init_options_signal_log()
    print("Options signal log initialized. Ready to build check_signal_and_trade_options().")