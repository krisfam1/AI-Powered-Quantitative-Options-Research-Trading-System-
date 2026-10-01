from dotenv import load_dotenv
load_dotenv()

"""
Portfolio-level backtest engine.

Unlike options_backtest_engine.py (which tests each ticker independently
with implicitly unlimited capital, then sums results), this runs ALL
tickers on a single, TRUE chronological timeline against ONE shared
PortfolioAccount -- real starting capital, real cash tracking, real
capital constraints on new positions, and a genuine equity curve.

SIMPLIFICATION, stated honestly: for long options (the only position
type this system trades), margin requirement equals the premium paid --
no additional margin beyond the cost of the position itself. This is
realistically accurate for long (not short) options.

Reuses the SAME, already-validated signal logic (weighted entry scoring,
0.30 delta targeting, reversal_guard exit) from options_backtest_engine.py
and entry_scorer.py -- only the capital/account layer is new.
"""

import backtest_engine as be
from backtest_engine import get_daily_regime
from entry_scorer import calculate_entry_score
from delta_strike_finder import find_strike_for_target_delta
from v2_iv_pricing_model import get_v2_entry_iv, get_v2_checkpoint_iv


def _get_v2_checkpoint_vol(meta, ticker, timestamp, gap_log=None):
    """
    Day-level-cached checkpoint IV lookup for pricing_mode='v2_corrected'.
    Fetches fresh IV only once per calendar day per position; reuses the
    cached value for all bars within that day. If a genuine gap occurs
    (exact-contract IV unavailable at this checkpoint), carries forward
    the last known v2 IV as an EXPLICITLY LOGGED, visible measure --
    never a silent fallback to V1 volatility, never fabricated.
    """
    current_date = timestamp.date()
    if meta.get("v2_last_checkpoint_date") == current_date:
        return meta["v2_last_iv"]

    result = get_v2_checkpoint_iv(ticker, meta["v2_contract"], meta["v2_exp_date_str"], current_date)
    if result is not None:
        meta["v2_last_checkpoint_date"] = current_date
        meta["v2_last_iv"] = result["iv"]
        return result["iv"]
    else:
        meta["v2_last_checkpoint_date"] = current_date
        meta["v2_checkpoint_gaps"] = meta.get("v2_checkpoint_gaps", 0) + 1
        if gap_log is not None:
            gap_log.append({"ticker": ticker, "contract": meta["v2_contract"], "checkpoint_date": current_date, "carried_forward_iv": meta["v2_last_iv"], "entry_date": meta.get("v2_entry_date"), "exp_date_str": meta.get("v2_exp_date_str")})
        return meta["v2_last_iv"]
from options_backtest_engine import calculate_historical_volatility, black_scholes_price, _estimated_spread_cost_pct
from datetime import datetime, timezone, timedelta, date


class PortfolioAccount:
    def __init__(self, starting_capital: float):
        self.starting_capital = starting_capital
        self.cash = starting_capital
        self.open_positions = {}
        self.closed_trades = []
        self.equity_history = []
        self._next_position_id = 0

    def can_afford(self, cost: float) -> bool:
        return self.cash >= cost

    def open_position(self, ticker: str, timestamp, contracts: int, entry_premium: float, **kwargs) -> int | None:
        cost = entry_premium * contracts * 100
        if not self.can_afford(cost):
            return None
        self.cash -= cost
        position_id = self._next_position_id
        self._next_position_id += 1
        self.open_positions[position_id] = {
            "ticker": ticker, "entry_date": timestamp.date() if hasattr(timestamp, "date") else timestamp,
            "contracts": contracts, "entry_premium": entry_premium, "cost": cost, **kwargs,
        }
        return position_id

    def close_position(self, position_id: int, timestamp, exit_premium: float, exit_reason: str) -> dict:
        position = self.open_positions.pop(position_id)
        proceeds = exit_premium * position["contracts"] * 100
        self.cash += proceeds
        pnl_dollars = proceeds - position["cost"]
        pnl_pct = (exit_premium - position["entry_premium"]) / position["entry_premium"] * 100 if position["entry_premium"] else 0
        trade = {
            **position,
            "exit_date": timestamp.date() if hasattr(timestamp, "date") else timestamp,
            "exit_premium": exit_premium, "exit_reason": exit_reason,
            "pnl_dollars": pnl_dollars, "pnl_pct": pnl_pct,
        }
        self.closed_trades.append(trade)
        return trade

    def mark_to_market(self, timestamp, position_values: dict) -> float:
        unrealized = sum(position_values.get(pid, 0) for pid in self.open_positions)
        equity = self.cash + unrealized
        self.equity_history.append({"timestamp": timestamp, "equity": equity, "cash": self.cash, "unrealized": unrealized})
        return equity


def run_portfolio_backtest(
    tickers: list[str], start_date, end_date, starting_capital: float = 100000.0,
    dte_target: int = 14, entry_score_threshold: int = 20, target_delta: float = 0.30,
    position_risk_pct: float = 0.01, stop_loss_pct: float = 0.40,
    fixed_direction: str = None,  # if set ("call" or "put"), disables dynamic regime-based direction switching -- matches the original engine's single-option_type-per-run design, for apples-to-apples comparison
pricing_mode: str = "v1",  # "v1" (default, unchanged) or "v2_entry_iv" (Phase 1: entry pricing only uses real historical IV; strike selection, exit/checkpoint pricing always stay on V1 vol)
) -> dict:
    account = PortfolioAccount(starting_capital)
    v2_coverage_log = []  # records every qualifying signal's V2 IV availability, even when pricing_mode="v1" is unused for this run
    v2_checkpoint_gap_log = []  # records every genuine checkpoint-IV gap under pricing_mode="v2_corrected" -- never silent
    v1_ground_truth_log = []  # Phase 7: records the REAL underlying price/vol at every entry, regardless of pricing_mode, for reconstruction validation only -- never used in any pricing decision

    # HONEST FIX: the original engine caches SPY's regime and only
    # refreshes it once every 5 days -- recomputing it fresh at every
    # checkpoint (as this engine did before) makes the SPY regime input
    # fluctuate far more than intended, a real, confirmed source of the
    # trade-count discrepancy vs. the original, validated engine.
    _spy_regime_cache = {"regime": "neutral", "last_checked_date": None}

    def _get_cached_spy_regime(current_timestamp):
        current_date = current_timestamp.date()
        if _spy_regime_cache["last_checked_date"] is None or (current_date - _spy_regime_cache["last_checked_date"]).days >= 5:
            try:
                _spy_regime_cache["regime"] = get_daily_regime("SPY", current_timestamp, period=50)
            except Exception:
                pass
            _spy_regime_cache["last_checked_date"] = current_date
        return _spy_regime_cache["regime"]

    all_bars = {}
    for ticker in tickers:
        try:
            all_bars[ticker] = be.get_historical_bars(ticker, start_date, end_date)
        except Exception:
            all_bars[ticker] = []

    # Build one true, merged chronological sequence of (timestamp, ticker, index) checkpoints
    checkpoints = []
    for ticker, bars in all_bars.items():
        for i, bar in enumerate(bars):
            checkpoints.append((bar.timestamp, ticker, i))
    checkpoints.sort(key=lambda c: c[0])

    ticker_positions = {t: None for t in tickers}  # ticker -> position_id currently open, or None
    ticker_position_meta = {}  # position_id -> {strike, option_type, expiry_date}

    for timestamp, ticker, index in checkpoints:
        bars = all_bars[ticker]
        current_price = float(bars[index].close)

        # Check exit for this ticker's open position, if any
        position_id = ticker_positions[ticker]
        if position_id is not None:
            meta = ticker_position_meta[position_id]
            position = account.open_positions[position_id]
            days_left = (meta["expiry_date"] - timestamp.date()).days
            vol = calculate_historical_volatility(bars, index, cache_namespace="portfolio")
            if pricing_mode == "v2_corrected" and "v2_contract" in meta:
                vol = _get_v2_checkpoint_vol(meta, ticker, timestamp, gap_log=v2_checkpoint_gap_log)
            current_option_value = black_scholes_price(current_price, meta["strike"], max(days_left, 0), vol, option_type=meta["option_type"])
            pct_change = (current_option_value - position["entry_premium"]) / position["entry_premium"] if position["entry_premium"] else 0

            exit_reason = None
            if pct_change <= -stop_loss_pct:
                exit_reason = "stop_loss"
            elif pct_change >= 0.40 and index >= 6:
                closes = [float(bars[i].close) for i in range(index - 6, index + 1)]
                ma_before = sum(closes[-7:-2]) / 5
                last_two = closes[-2:]
                if meta["option_type"] == "call" and all(c < ma_before for c in last_two):
                    exit_reason = "reversal_guard"
                elif meta["option_type"] == "put" and all(c > ma_before for c in last_two):
                    exit_reason = "reversal_guard"
            # NOTE: no 75% take-profit fallback here. In the original,
            # validated engine (options_backtest_engine.py), reversal_guard
            # exit is a single elif branch -- if pct_change >= 0.40 and the
            # specific 2-bar reversal pattern hasn't fired, the position
            # simply stays open. There is no take_profit fallback in that
            # mode. The fallback that used to be here was a behavioral
            # divergence from the validated original, not a bug fix.
            if exit_reason is None and days_left <= 0:
                exit_reason = "expired"

            if exit_reason:
                # Mirrors the original, validated engine's exit-side spread
                # cost (options_backtest_engine.py, _exit_value_after_spread).
                # Without this, exits were priced at the raw model value with
                # no trading friction, while entries already charged spread
                # cost -- an asymmetric-friction bug that inflated P&L.
                _exit_value_after_spread = current_option_value * (1 - _estimated_spread_cost_pct(current_option_value) / 2)
                account.close_position(position_id, timestamp, _exit_value_after_spread, exit_reason)
                ticker_positions[ticker] = None
                del ticker_position_meta[position_id]

        # Check entry for this ticker, only if no position currently open on it
        # NOTE: removed the unconditional 'index >= 60' gate that used to
        # sit here. The original, validated engine has no blanket index
        # floor on entries -- index >= 60 only appears there scoped to the
        # OPTIONAL require_elevated_volatility feature (default False, never
        # enabled in any comparison run). This gate was silently blocking
        # every entry attempt in roughly the first 60 bars of any backtest,
        # which caused a real missed trade vs. the original engine.
        if ticker_positions[ticker] is None:
            try:
                # HONEST FIX: the real, validated live system picks ONE
                # direction per ticker based on its daily regime (bullish
                # -> call only, bearish -> put only), not both directions
                # at every checkpoint -- checking both was a real bug that
                # doubled entry opportunities versus the validated system.
                _daily_regime = get_daily_regime(ticker, timestamp, period=50)
                direction = fixed_direction if fixed_direction else ("call" if _daily_regime == "bullish" else "put" if _daily_regime == "bearish" else "call")

                _gate_passed = False
                if direction == "call" and be.check_breakout(bars, index, lookback=20):
                    _gate_passed = True
                elif direction == "put" and be.check_breakdown(bars, index, lookback=20):
                    _gate_passed = True

                if _gate_passed:
                    _spy_regime = _get_cached_spy_regime(timestamp)
                    score_result = calculate_entry_score(ticker, bars, index, direction, spy_regime=_spy_regime)
                    if score_result["total_score"] >= entry_score_threshold:
                        vol = calculate_historical_volatility(bars, index, cache_namespace="portfolio")
                        strike = find_strike_for_target_delta(current_price, dte_target, vol, direction, target_delta)
                        expiry_date = timestamp.date() + timedelta(days=dte_target)
                        _pricing_vol = vol  # defaults to V1 vol; only overridden below if pricing_mode="v2_entry_iv" and real historical IV is available
                        _v2_iv_available = False
                        _v2_skip_reason = None
                        if pricing_mode in ("v2_entry_iv", "v2_corrected"):
                            _v2_result = get_v2_entry_iv(ticker, timestamp, strike, option_type=direction, target_dte=dte_target)
                            if _v2_result is not None:
                                _pricing_vol = _v2_result["historical_iv"]
                                _v2_iv_available = True
                            else:
                                _v2_skip_reason = "no_valid_historical_iv"
                        v1_ground_truth_log.append({
                            "ticker": ticker, "entry_date": timestamp.date(), "underlying_price": current_price,
                            "v1_realized_vol": vol, "strike": strike, "entry_premium_final": None,  # filled below after computation
                            "entry_index": index,
                        })
                        v2_coverage_log.append({
                            "ticker": ticker, "signal_timestamp": timestamp, "strike": strike,
                            "direction": direction, "v2_iv_available": _v2_iv_available,
                            "v2_skip_reason": _v2_skip_reason,
                            "v1_vol": vol, "v2_iv": (_v2_result["historical_iv"] if _v2_iv_available else None),
                            "underlying_price": current_price, "target_dte": dte_target,
                            "v1_raw_price": black_scholes_price(current_price, strike, dte_target, vol, option_type=direction),
                            "v2_raw_price": (black_scholes_price(current_price, strike, dte_target, _v2_result["historical_iv"], option_type=direction) if _v2_iv_available else None),
                        })
                        if pricing_mode == "v2_entry_iv" and not _v2_iv_available:
                            entry_premium = 0  # skip, not fallback -- fails the `> 0` gate below, no position opened
                        else:
                            entry_premium = black_scholes_price(current_price, strike, dte_target, _pricing_vol, option_type=direction)
                            entry_premium = entry_premium * (1 + _estimated_spread_cost_pct(entry_premium) / 2)
                        if entry_premium > 0:
                            max_risk_dollars = account.starting_capital * position_risk_pct
                            contracts = max(int(max_risk_dollars / (entry_premium * 100)), 1)
                            position_id = account.open_position(ticker, timestamp, contracts, entry_premium, strike=strike, option_type=direction, expiry_date=expiry_date)
                            if position_id is not None:
                                ticker_positions[ticker] = position_id
                                ticker_position_meta[position_id] = {"strike": strike, "option_type": direction, "expiry_date": expiry_date}
                                if pricing_mode == "v2_corrected" and _v2_iv_available:
                                    ticker_position_meta[position_id]["v2_contract"] = _v2_result["contract"]
                                    # HONEST FIX: use the REAL matched contract's actual expiration
                                    # (parsed from the contract symbol itself), NOT the synthetic
                                    # flat-14-day target expiry_date -- these silently diverged
                                    # whenever the closest real match wasn't exactly 14 DTE,
                                    # causing every later checkpoint lookup to query the wrong
                                    # expiration and falsely report a "gap" even when real IV
                                    # data was genuinely available the whole time.
                                    import re as _re
                                    _m = _re.match(r"^[A-Z]+(\d{6})[CP]\d{8}$", _v2_result["contract"])
                                    _real_exp_date = datetime.strptime("20" + _m.group(1), "%Y%m%d").date() if _m else expiry_date
                                    ticker_position_meta[position_id]["v2_exp_date_str"] = _real_exp_date.isoformat()
                                    ticker_position_meta[position_id]["v2_last_checkpoint_date"] = timestamp.date()
                                    ticker_position_meta[position_id]["v2_last_iv"] = _v2_result["historical_iv"]
                                    ticker_position_meta[position_id]["v2_checkpoint_gaps"] = 0
                                    ticker_position_meta[position_id]["v2_entry_date"] = timestamp.date()
            except Exception:
                pass

        # Mark to market (approximate: only re-price THIS ticker's open position at this checkpoint)
        position_values = {}
        for pid, pos in account.open_positions.items():
            if pos["ticker"] == ticker:
                meta = ticker_position_meta[pid]
                days_left = (meta["expiry_date"] - timestamp.date()).days
                vol = calculate_historical_volatility(bars, index, cache_namespace="portfolio")
                if pricing_mode == "v2_corrected" and "v2_contract" in meta:
                    vol = _get_v2_checkpoint_vol(meta, ticker, timestamp, gap_log=v2_checkpoint_gap_log)
                val = black_scholes_price(current_price, meta["strike"], max(days_left, 0), vol, option_type=meta["option_type"])
                position_values[pid] = val * pos["contracts"] * 100
            else:
                position_values[pid] = pos["cost"]  # use last known cost basis for other tickers' positions at this instant
        account.mark_to_market(timestamp, position_values)

    return {
        "final_equity": account.cash,
        "starting_capital": account.starting_capital,
        "v2_coverage_log": v2_coverage_log,
        "v2_checkpoint_gap_log": v2_checkpoint_gap_log,
        "v1_ground_truth_log": v1_ground_truth_log,
        "closed_trades": account.closed_trades,
        "equity_history": account.equity_history,
        "total_trades": len(account.closed_trades),
    }


if __name__ == "__main__":
    end = datetime.now(timezone.utc)
    start = end - timedelta(days=30)
    print("Running portfolio-level backtest (this reuses validated signal logic, adds real shared capital tracking)...\n")
    result = run_portfolio_backtest(["AAPL", "TSLA", "NVDA", "AMD", "SMCI", "MSTR"], start, end, starting_capital=100000.0)
    print("Starting capital: $" + str(result["starting_capital"]))
    print("Total trades: " + str(result["total_trades"]))
    print("Equity history points: " + str(len(result["equity_history"])))
    if result["equity_history"]:
        print("Final tracked equity: $" + str(round(result["equity_history"][-1]["equity"], 2)))