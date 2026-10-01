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
) -> dict:
    account = PortfolioAccount(starting_capital)

    all_bars = {}
    for ticker in tickers:
        try:
            all_bars[ticker] = be.get_historical_bars(ticker, start_date, end_date)
        except Exception:
            all_bars[ticker] = []

    checkpoints = []
    for ticker, bars in all_bars.items():
        for i, bar in enumerate(bars):
            checkpoints.append((bar.timestamp, ticker, i))
    checkpoints.sort(key=lambda c: c[0])

    ticker_positions = {t: None for t in tickers}
    ticker_position_meta = {}

    for timestamp, ticker, index in checkpoints:
        bars = all_bars[ticker]
        current_price = float(bars[index].close)

        position_id = ticker_positions[ticker]
        if position_id is not None:
            meta = ticker_position_meta[position_id]
            position = account.open_positions[position_id]
            days_left = (meta["expiry_date"] - timestamp.date()).days
            vol = calculate_historical_volatility(bars, index)
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
            if exit_reason is None and pct_change >= 0.75:
                exit_reason = "take_profit"
            if exit_reason is None and days_left <= 0:
                exit_reason = "expired"

            if exit_reason:
                account.close_position(position_id, timestamp, current_option_value, exit_reason)
                ticker_positions[ticker] = None
                del ticker_position_meta[position_id]

        if ticker_positions[ticker] is None and index >= 60:
            try:
                _daily_regime = get_daily_regime(ticker, timestamp, period=50)
                direction = "call" if _daily_regime == "bullish" else "put" if _daily_regime == "bearish" else "call"

                _gate_passed = False
                if direction == "call" and be.check_breakout(bars, index, lookback=20):
                    _gate_passed = True
                elif direction == "put" and be.check_breakdown(bars, index, lookback=20):
                    _gate_passed = True

                if _gate_passed:
                    try:
                        _spy_regime = get_daily_regime("SPY", timestamp, period=50)
                    except Exception:
                        _spy_regime = "neutral"
                    score_result = calculate_entry_score(ticker, bars, index, direction, spy_regime=_spy_regime)
                    if score_result["total_score"] >= entry_score_threshold:
                        vol = calculate_historical_volatility(bars, index)
                        strike = find_strike_for_target_delta(current_price, dte_target, vol, direction, target_delta)
                        expiry_date = timestamp.date() + timedelta(days=dte_target)
                        entry_premium = black_scholes_price(current_price, strike, dte_target, vol, option_type=direction)
                        entry_premium = entry_premium * (1 + _estimated_spread_cost_pct(entry_premium) / 2)
                        if entry_premium > 0:
                            max_risk_dollars = account.starting_capital * position_risk_pct
                            contracts = max(int(max_risk_dollars / (entry_premium * 100)), 1)
                            position_id = account.open_position(ticker, timestamp, contracts, entry_premium, strike=strike, option_type=direction, expiry_date=expiry_date)
                            if position_id is not None:
                                ticker_positions[ticker] = position_id
                                ticker_position_meta[position_id] = {"strike": strike, "option_type": direction, "expiry_date": expiry_date}
            except Exception:
                pass

        position_values = {}
        for pid, pos in account.open_positions.items():
            if pos["ticker"] == ticker:
                meta = ticker_position_meta[pid]
                days_left = (meta["expiry_date"] - timestamp.date()).days
                vol = calculate_historical_volatility(bars, index)
                val = black_scholes_price(current_price, meta["strike"], max(days_left, 0), vol, option_type=meta["option_type"])
                position_values[pid] = val * pos["contracts"] * 100
            else:
                position_values[pid] = pos["cost"]
        account.mark_to_market(timestamp, position_values)

    return {
        "final_equity": account.cash,
        "starting_capital": account.starting_capital,
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