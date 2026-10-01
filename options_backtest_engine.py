from dotenv import load_dotenv
load_dotenv()

import math
from datetime import date, datetime, timedelta, timezone
import backtest_engine as be
from options_pricing import black_scholes_price
from dynamic_options_thresholds import calculate_dynamic_thresholds
from options_trailing_stop import update_trailing_stop


def _estimated_spread_cost_pct(option_price: float) -> float:
    """
    ESTIMATE, not real market data -- models round-trip bid-ask spread cost
    as a percentage of price, scaled inversely with price (cheaper options
    have proportionally wider spreads). Used only as a sensitivity test,
    not a validated cost model.
    """
    if option_price >= 5.0:
        return 0.02
    elif option_price >= 2.0:
        return 0.04
    elif option_price >= 1.0:
        return 0.07
    else:
        return 0.12


_volatility_series_cache = {}


def _vol_cache_key(bars: list, cache_namespace: str = "default"):
    """Content-based cache key -- avoids the real risk of Python's id()
    being reused after garbage collection, which could silently return
    a completely wrong, stale cached series for a different bars list.

    HONEST FIX: now includes cache_namespace, so different engines
    (e.g. the original engine vs. the portfolio engine) never share a
    cache entry even when computing on identical bars data. This closes
    a real cross-engine isolation gap discovered during the 11-vs-30
    forensic investigation -- confirmed NOT the cause of that specific
    discrepancy (which was a date-window artifact), but a real,
    separate isolation flaw worth fixing before trusting any future
    cross-engine comparison."""
    if not bars:
        return None
    return (cache_namespace, bars[0].timestamp, bars[-1].timestamp, len(bars))


def _precompute_hybrid_volatility_series(bars: list, lookback_days: int = 20) -> list:
    """
    Builds the full smoothed volatility series for a bars array in one
    pass. HYBRID METHODOLOGY (validated for stability, not tuned for
    profitability -- see Volatility_Methodology_Proposal.md and the
    real stability comparison in compare_vol_stability.py):

    Base estimate: daily-bar historical volatility (standard, textbook
    methodology), recomputed once per trading day using real daily
    closes -- far less noisy than 5-minute closes.

    Smoothing: the day-to-day transition is further blended gradually
    via EWMA (lambda=0.90), so volatility never jumps suddenly even at
    day boundaries.

    CONFIRMED via direct testing: max single-step jump 4.1% (vs. 35.3%
    for daily-bar alone, 424.5% for EWMA-on-raw-returns alone), zero
    bars out of 6,920 tested showing a >10% jump. Directly resolves the
    confirmed real bug (AAPL 2026-08-13, 98.5% option-value swing in a
    single 5-minute bar with the underlying barely moving).

    HONEST LIMITATION: this remains a real, principled ESTIMATE derived
    from actual historical stock prices -- NOT real market-implied
    volatility. See Advanced_Options_System_Roadmap.md for full
    documentation. All results using this function should be treated as
    synthetic research/logic-testing data, not evidence of real-world
    option-market performance, until real historical IV data is
    available.
    """
    daily_closes = {}
    for b in bars:
        d = b.timestamp.date()
        daily_closes[d] = float(b.close)
    daily_dates_sorted = sorted(daily_closes.keys())

    def _daily_bar_vol(current_date):
        day_position = daily_dates_sorted.index(current_date) if current_date in daily_dates_sorted else 0
        if day_position < lookback_days:
            return 0.30
        recent_dates = daily_dates_sorted[day_position - lookback_days:day_position]
        closes = [daily_closes[d] for d in recent_dates]
        rets = [math.log(closes[i] / closes[i - 1]) for i in range(1, len(closes)) if closes[i - 1] > 0]
        if len(rets) < 2:
            return 0.30
        mean_r = sum(rets) / len(rets)
        var = sum((r - mean_r) ** 2 for r in rets) / (len(rets) - 1)
        return max(math.sqrt(var) * math.sqrt(252), 0.10)

    series = []
    hybrid_vol = None
    last_date = None
    lam_daily = 0.90
    for b in bars:
        current_date = b.timestamp.date()
        daily_target = _daily_bar_vol(current_date)
        if hybrid_vol is None:
            hybrid_vol = daily_target
        elif current_date != last_date:
            hybrid_vol = lam_daily * hybrid_vol + (1 - lam_daily) * daily_target
        last_date = current_date
        series.append(hybrid_vol)

    return series


def calculate_historical_volatility(bars: list, current_index: int, lookback: int = 60, cache_namespace: str = "default") -> float:
    """
    Estimate volatility using the validated hybrid methodology (see
    _precompute_hybrid_volatility_series docstring for full detail and
    validation results). SYNTHETIC ESTIMATE, not real market IV -- see
    Advanced_Options_System_Roadmap.md.

    Signature backward-compatible: existing call sites (which don't
    pass cache_namespace) continue to use "default" unchanged. The
    `lookback` parameter is accepted for backward compatibility but is
    not used by the new methodology, which uses a fixed 20-trading-day
    daily-bar window internally instead.

    cache_namespace: pass a distinct value (e.g. "portfolio") from a
    different engine to guarantee true cache isolation, even when both
    engines compute on identical bars data.
    """
    key = _vol_cache_key(bars, cache_namespace)
    if key not in _volatility_series_cache:
        _volatility_series_cache[key] = _precompute_hybrid_volatility_series(bars)

    series = _volatility_series_cache[key]
    if current_index < len(series):
        return series[current_index]
    return 0.30


def run_options_backtest(
    ticker: str,
    start_date,
    end_date,
    dte_target: int = 14,
    strike_offset_pct: float = 0.0,  # 0.0 = at-the-money
    option_type: str = "call",
    stop_loss_pct: float = 0.40,   # close if option loses 40% of its value
    take_profit_pct: float = 0.75,  # close if option gains 75%
    account_equity: float = 100_000.0,
    risk_pct: float = 0.01,
    use_dynamic_thresholds: bool = False,  # flat thresholds validated as the stronger approach
    exit_mode: str = "auto",  # "auto" = existing behavior, "hybrid" = flat stop + trailing profit past take_profit_pct
    exclude_first_n_minutes: int = 0,  # skip entries within N minutes of market open (9:30 AM ET)
    entry_mode: str = "binary",  # "binary" = existing AND-gate, "weighted" = scored entry
    entry_score_threshold: float = 60.0,  # min score (0-100) required when entry_mode="weighted"
    require_elevated_volatility: bool = False,  # only enter when realized vol is above its own 60-bar trailing median
    target_delta: float = None,  # if set, overrides strike_offset_pct with delta-based strike selection
    adaptive_delta: bool = False,  # if True, scales target_delta by entry score conviction (overrides target_delta)
    require_entry_confirmation: bool = False,  # require breakout to hold for 2 consecutive bars before entering
    require_close_strength: bool = False,  # require the triggering bar to close in the strong part of its own range
    apply_spread_cost: bool = False,  # ESTIMATED, not real data -- models bid-ask spread cost
    collect_features: bool = False,  # opt-in: captures full ML feature vector at each entry, zero effect on existing behavior otherwise
) -> dict:
    """Simulate an options strategy using Black-Scholes-estimated pricing on real stock price history."""
    bars = be.get_historical_bars(ticker, start_date, end_date)
    if not bars:
        print(f"No bars for {ticker}")
        return {}

    trades = []
    _spy_regime = "neutral"
    _spy_regime_last_checked_date = None

    def _refresh_spy_regime_if_needed(current_timestamp):
        nonlocal _spy_regime, _spy_regime_last_checked_date
        current_date = current_timestamp.date()
        if _spy_regime_last_checked_date is None or (current_date - _spy_regime_last_checked_date).days >= 5:
            try:
                _spy_regime = be.get_daily_regime("SPY", current_timestamp, period=50)
            except Exception:
                pass
            _spy_regime_last_checked_date = current_date

    open_position = None

    for index, bar in enumerate(bars):
        timestamp = bar.timestamp
        stock_price = float(bar.close)

        if open_position is not None:
            days_left = (open_position["expiry_date"] - timestamp.date()).days
            vol = calculate_historical_volatility(bars, index)
            current_option_value = black_scholes_price(
                stock_price, open_position["strike"], max(days_left, 0), vol, option_type=option_type
            )

            entry_value = open_position["entry_premium"]
            pct_change = (current_option_value - entry_value) / entry_value if entry_value > 0 else 0

            trail_state = update_trailing_stop(
                entry_value, current_option_value,
                open_position.get("peak_value", entry_value),
                open_position.get("trailing_active", False),
            )
            open_position["peak_value"] = trail_state["peak_value"]
            open_position["trailing_active"] = trail_state["trailing_active"]

            if exit_mode == "locked_hybrid" and open_position.get("peak_value", entry_value) >= entry_value * 1.50:
                open_position["breakeven_locked"] = True

            exit_reason = None
            if exit_mode == "locked_hybrid" and open_position.get("breakeven_locked") and pct_change <= 0.0:
                exit_reason = "breakeven_lock"
            elif pct_change <= -open_position["stop_loss_pct"]:
                exit_reason = "stop_loss"
            elif exit_mode == "reversal_guard" and pct_change >= 0.40 and index >= 6:
                _closes = [float(bars[i].close) for i in range(index - 6, index + 1)]
                _last_two = _closes[-2:]
                _ma_before = sum(_closes[-7:-2]) / 5
                if option_type == "call" and all(c < _ma_before for c in _last_two):
                    exit_reason = "reversal_guard"
                elif option_type == "put" and all(c > _ma_before for c in _last_two):
                    exit_reason = "reversal_guard"
            elif exit_mode == "time_decay" and days_left <= 10:
                try:
                    from time_decay_exit import check_time_decay_exit
                    _decay_result = check_time_decay_exit(ticker, bars, index, option_type, open_position["strike"], days_left, current_option_value)
                    if _decay_result["should_exit"]:
                        exit_reason = "time_decay"
                except Exception:
                    pass
            elif exit_mode == "reversal_guard_plus_decay":
                if pct_change >= 0.40 and index >= 6:
                    _closes = [float(bars[i].close) for i in range(index - 6, index + 1)]
                    _last_two = _closes[-2:]
                    _ma_before = sum(_closes[-7:-2]) / 5
                    if option_type == "call" and all(c < _ma_before for c in _last_two):
                        exit_reason = "reversal_guard"
                    elif option_type == "put" and all(c > _ma_before for c in _last_two):
                        exit_reason = "reversal_guard"
                if exit_reason is None and days_left <= 10:
                    try:
                        from time_decay_exit import check_time_decay_exit
                        _decay_result = check_time_decay_exit(ticker, bars, index, option_type, open_position["strike"], days_left, current_option_value)
                        if _decay_result["should_exit"]:
                            exit_reason = "time_decay"
                    except Exception:
                        pass
            elif (use_dynamic_thresholds or exit_mode in ("hybrid", "locked_hybrid")) and trail_state["trailing_active"] and current_option_value <= trail_state["trailing_stop_price"]:
                exit_reason = "trailing_stop"
            elif not use_dynamic_thresholds and exit_mode not in ("hybrid", "locked_hybrid") and pct_change >= open_position["take_profit_pct"]:
                exit_reason = "take_profit"
            elif days_left <= 0:
                exit_reason = "expired"

            if exit_reason:
                _exit_value_after_spread = current_option_value
                if apply_spread_cost:
                    _exit_value_after_spread = current_option_value * (1 - _estimated_spread_cost_pct(current_option_value) / 2)
                pnl_dollars = (_exit_value_after_spread - entry_value) * open_position["contracts"] * 100
                trades.append({
                    "entry_date": open_position["entry_date"],
                    "exit_date": timestamp.date(),
                    "entry_premium": entry_value,
                    "exit_premium": current_option_value,
                    "pnl_dollars": pnl_dollars,
                    "pnl_pct": pct_change * 100,
                    "exit_reason": exit_reason,
                    "entry_features": open_position.get("entry_features"),
                })
                open_position = None

        if open_position is None:
            if entry_mode == "weighted":
                # MANDATORY: real breakout/breakdown confirmation required, same
                # as the original binary system -- the weighted score then
                # determines which of THESE genuinely confirmed setups are
                # strong enough, rather than letting volume alone substitute
                # for a real breakout.
                if option_type == "call" and not be.check_breakout(bars, index, lookback=20):
                    continue
                if option_type == "put" and not be.check_breakdown(bars, index, lookback=20):
                    continue

                if require_entry_confirmation and index >= 1:
                    _prev_qualified_w = False
                    if option_type == "call":
                        _prev_qualified_w = be.check_breakout(bars, index - 1, lookback=20)
                    else:
                        _prev_qualified_w = be.check_breakdown(bars, index - 1, lookback=20)
                    if not _prev_qualified_w:
                        continue

                if require_close_strength:
                    _bar_high = float(bars[index].high)
                    _bar_low = float(bars[index].low)
                    _bar_close = float(bars[index].close)
                    _bar_range = _bar_high - _bar_low
                    if _bar_range > 0:
                        _close_position = (_bar_close - _bar_low) / _bar_range
                        if option_type == "call" and _close_position < 0.70:
                            continue
                        if option_type == "put" and _close_position > 0.30:
                            continue

                _refresh_spy_regime_if_needed(timestamp)
                from entry_scorer import calculate_entry_score
                _score_result = calculate_entry_score(ticker, bars, index, option_type, spy_regime=_spy_regime)
                if _score_result["total_score"] < entry_score_threshold:
                    continue
            else:
                if option_type == "call" and not be.check_breakout(bars, index, lookback=20):
                    continue
                if option_type == "put" and not be.check_breakdown(bars, index, lookback=20):
                    continue
                rv = be.calculate_relative_volume(bars, index)
                if rv < 1.5:
                    continue

                if require_entry_confirmation and index >= 1:
                    _prev_qualified = False
                    if option_type == "call":
                        _prev_qualified = be.check_breakout(bars, index - 1, lookback=20)
                    else:
                        _prev_qualified = be.check_breakdown(bars, index - 1, lookback=20)
                    if not _prev_qualified:
                        continue

            if require_elevated_volatility and index >= 60:
                _current_vol = calculate_historical_volatility(bars, index)
                _recent_vols = [calculate_historical_volatility(bars, i) for i in range(index - 60, index)]
                _recent_vols = [v for v in _recent_vols if v > 0]
                if _recent_vols:
                    _median_vol = sorted(_recent_vols)[len(_recent_vols) // 2]
                    if _current_vol < _median_vol:
                        continue

            if exclude_first_n_minutes > 0:
                from zoneinfo import ZoneInfo
                _et_time = timestamp.astimezone(ZoneInfo("America/New_York"))
                _market_open_minutes = (_et_time.hour - 9) * 60 + (_et_time.minute - 30)
                if 0 <= _market_open_minutes < exclude_first_n_minutes:
                    continue

            if adaptive_delta:
                from delta_strike_finder import find_strike_for_target_delta
                _vol_for_strike = calculate_historical_volatility(bars, index)
                _score_for_delta = _score_result["total_score"] if entry_mode == "weighted" else 50
                if _score_for_delta >= 80:
                    _adaptive_target = 0.20
                elif _score_for_delta >= 60:
                    _adaptive_target = 0.30
                elif _score_for_delta >= 40:
                    _adaptive_target = 0.35
                else:
                    _adaptive_target = 0.45
                strike = find_strike_for_target_delta(stock_price, dte_target, _vol_for_strike, option_type, _adaptive_target)
            elif target_delta is not None:
                from delta_strike_finder import find_strike_for_target_delta
                _vol_for_strike = calculate_historical_volatility(bars, index)
                strike = find_strike_for_target_delta(stock_price, dte_target, _vol_for_strike, option_type, target_delta)
            else:
                strike = round(stock_price * (1 + strike_offset_pct), 2)
            expiry_date = timestamp.date() + timedelta(days=dte_target)
            vol = calculate_historical_volatility(bars, index)
            entry_premium = black_scholes_price(stock_price, strike, dte_target, vol, option_type=option_type)
            if apply_spread_cost:
                entry_premium = entry_premium * (1 + _estimated_spread_cost_pct(entry_premium) / 2)


            if exit_mode in ("hybrid", "locked_hybrid"):
                thresholds = {"stop_loss_pct": stop_loss_pct, "take_profit_pct": take_profit_pct}
            elif use_dynamic_thresholds:
                thresholds = calculate_dynamic_thresholds(
                    ticker, bars, index, stock_price, strike, dte_target, vol, option_type=option_type
                )
            else:
                thresholds = {"stop_loss_pct": stop_loss_pct, "take_profit_pct": take_profit_pct}
            if entry_premium <= 0:
                continue

            max_risk_dollars = account_equity * risk_pct
            contracts = max(int(max_risk_dollars / (entry_premium * 100)), 1)

            open_position = {
                "entry_date": timestamp.date(),
                "expiry_date": expiry_date,
                "strike": strike,
                "entry_premium": entry_premium,
                "stop_loss_pct": thresholds["stop_loss_pct"],
                "take_profit_pct": thresholds["take_profit_pct"],
                "contracts": contracts,
            }

            if collect_features:
                try:
                    from feature_extraction import extract_features
                    open_position["entry_features"] = extract_features(ticker, bars, index, option_type, strike, dte_target)
                except Exception:
                    open_position["entry_features"] = None

    total_trades = len(trades)
    wins = [t for t in trades if t["pnl_dollars"] > 0]
    losses = [t for t in trades if t["pnl_dollars"] < 0]
    win_rate = (len(wins) / total_trades * 100) if total_trades else 0
    net_pnl = sum(t["pnl_dollars"] for t in trades)

    print(f"\n{ticker} options backtest: {total_trades} trades")
    print(f"Win rate: {win_rate:.1f}%  Net P&L: ${net_pnl:.2f}")
    return {"total_trades": total_trades, "win_rate": win_rate, "net_pnl_dollars": net_pnl, "trades": trades}


if __name__ == "__main__":
    end = datetime.now(timezone.utc)
    start = end - timedelta(days=30)
    result = run_options_backtest("AAPL", start, end, dte_target=14)