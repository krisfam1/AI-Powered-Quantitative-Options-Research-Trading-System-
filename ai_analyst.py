"""AI-powered wealth management research team using Claude."""

import os
from typing import Any

import anthropic

_SYSTEM_PROMPT = """You are a senior wealth management research desk. Your team comprises:

  • A technical analyst — reads price action, trend, volume, momentum
  • A news analyst — assesses headline sentiment and market-moving catalysts
  • A quantitative analyst — interprets backtest and signal statistics
  • A portfolio manager — synthesises everything into a clear, actionable view

Tone: direct, data-grounded, professional. Cite specific numbers. Flag risks clearly.
Keep each section tight — this is an internal research desk, not a retail report."""


def _make_client() -> anthropic.Anthropic:
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise RuntimeError("ANTHROPIC_API_KEY must be set")
    return anthropic.Anthropic(api_key=api_key)


def _ask(prompt: str, max_tokens: int = 1024) -> str:
    """Send a single-turn message to Claude and return the text response."""
    client = _make_client()
    response = client.messages.create(
        model="claude-opus-4-5",
        max_tokens=max_tokens,
        system=_SYSTEM_PROMPT,
        messages=[{"role": "user", "content": prompt}],
    )
    return response.content[0].text


def research_ticker(
    ticker: str,
    bars: list[Any],
    news_articles: list[Any],
    backtest_stats: dict[str, float] | None = None,
) -> str:
    """Generate a wealth management research brief for a single ticker.

    Parameters
    ----------
    ticker:
        Stock symbol, e.g. "AAPL".
    bars:
        List of bar objects from the Alpaca data client (daily or intraday).
    news_articles:
        List of news article objects returned by the Alpaca news client.
    backtest_stats:
        Optional dict of aggregated stats from run_backtest / run_multi_ticker_backtest.
    """
    # --- Price action summary ---
    if bars:
        recent = bars[-15:]
        bar_lines = [
            f"  {b.timestamp.date()}  O={float(b.open):.2f}  H={float(b.high):.2f}"
            f"  L={float(b.low):.2f}  C={float(b.close):.2f}  Vol={float(b.volume):,.0f}"
            for b in recent
        ]
        first_close = float(bars[0].close)
        last_close = float(bars[-1].close)
        period_return = (last_close - first_close) / first_close * 100
        price_block = (
            f"Period: {bars[0].timestamp.date()} → {bars[-1].timestamp.date()}  "
            f"({period_return:+.2f}% return)\n"
            f"Last {len(recent)} bars:\n" + "\n".join(bar_lines)
        )
    else:
        price_block = "No price data available."

    # --- News summary ---
    if news_articles:
        news_lines = [
            f"  [{a.created_at.date()}] {a.headline}  (source: {a.source})"
            for a in news_articles
        ]
        news_block = "\n".join(news_lines)
    else:
        news_block = "No recent news available."

    # --- Backtest stats ---
    if backtest_stats and backtest_stats.get("total_trades", 0) > 0:
        stats_block = (
            f"  Trades:    {int(backtest_stats['total_trades'])}\n"
            f"  Win rate:  {backtest_stats['win_rate']:.1f}%\n"
            f"  Avg win:   {backtest_stats['average_win_pct']:.2f}%\n"
            f"  Avg loss:  {backtest_stats['average_loss_pct']:.2f}%\n"
            f"  Net P&L:   {backtest_stats['net_pnl_pct']:.2f}%"
        )
    else:
        stats_block = "No backtest data available for this ticker."

    prompt = f"""
Prepare a research brief for {ticker}.

── PRICE ACTION ──────────────────────────────────────
{price_block}

── RECENT NEWS ───────────────────────────────────────
{news_block}

── BREAKOUT SIGNAL BACKTEST (5-min, 90-day, vol-confirmed) ──
{stats_block}

Structure your brief under exactly these four headers:
1. PRICE ACTION — key technical observations, trend, momentum, notable volume
2. NEWS SENTIMENT — dominant themes, overall sentiment (bullish / bearish / mixed), key catalysts
3. SIGNAL QUALITY — what the backtest stats reveal about the breakout strategy on this ticker
4. OUTLOOK — risk/reward, key levels, position bias, anything the desk should watch
""".strip()

    return _ask(prompt, max_tokens=1200)


def diagnose_and_suggest(
    history: list[dict],
) -> dict:
    """Diagnose backtest failures and suggest config changes for the next iteration.

    Parameters
    ----------
    history:
        List of iteration records, each containing:
        ``{iteration, config, overall_stats, per_ticker_stats}``.

    Returns
    -------
    dict with keys:
        diagnosis        — plain-text analysis of what is failing and why
        config_changes   — flat dict of parameter changes to apply next
        iteration_theme  — one-line label for the change being tested
        expected_impact  — brief prediction of effect on win rate / P&L
    """
    import json

    def _fmt_stats(s: dict) -> str:
        return (
            f"trades={int(s['total_trades'])}  "
            f"win_rate={s['win_rate']:.1f}%  "
            f"avg_win={s['average_win_pct']:.2f}%  "
            f"avg_loss={s['average_loss_pct']:.2f}%  "
            f"net_pnl={s['net_pnl_pct']:.2f}%"
        )

    history_blocks: list[str] = []
    for entry in history:
        it = entry["iteration"]
        cfg = entry["config"]
        overall = entry["overall_stats"]
        per_ticker = entry.get("per_ticker_stats", {})

        ticker_lines = "\n".join(
            f"    {t}: {_fmt_stats(s)}" for t, s in per_ticker.items()
        )

        cfg_summary = (
            f"mode={cfg.get('mode')}  "
            f"rv_threshold={cfg.get('relative_volume_threshold', 1.5)}  "
            f"rv_bars={cfg.get('rv_confirmation_bars', 1)}  "
            f"breakout_lookback={cfg.get('breakout_lookback', 20)}  "
            f"time_window={'ON' if cfg.get('use_time_window') else 'OFF'}  "
            f"vwap_trend={'ON' if cfg.get('use_vwap_trend') else 'OFF'}  "
            f"atr_pct={'ON' if cfg.get('use_atr_percentile') else 'OFF'}"
        )
        if cfg.get("mode") == "atr":
            cfg_summary += (
                f"  stop={cfg.get('atr_stop_multiplier')}×ATR"
                f"  target={cfg.get('atr_target_multiplier')}×ATR"
                f"  trail_trigger={cfg.get('atr_trail_trigger')}×ATR"
                f"  trail_dist={cfg.get('atr_trail_distance')}×ATR"
            )

        history_blocks.append(
            f"Iteration {it}:\n"
            f"  Config: {cfg_summary}\n"
            f"  Overall: {_fmt_stats(overall)}\n"
            f"  Per-ticker:\n{ticker_lines}"
        )

    history_text = "\n\n".join(history_blocks)

    tunable_params = """{
  "mode": "fixed_pct" | "atr",
  "atr_stop_multiplier": float,
  "atr_target_multiplier": float,
  "atr_trail_trigger": float,
  "atr_trail_distance": float,
  "stop_loss_pct": float,          // only for fixed_pct mode
  "take_profit_pct": float,        // only for fixed_pct mode
  "relative_volume_threshold": float,
  "rv_confirmation_bars": int,
  "breakout_lookback": int,
  "use_time_window": bool,
  "time_windows": [["HH:MM","HH:MM"], ...],   // ET 24h pairs
  "use_vwap_trend": bool,
  "vwap_lookback": int,
  "use_atr_percentile": bool,
  "atr_percentile_min": float,     // 0–100
  "atr_percentile_lookback": int
}"""

    prompt = f"""
You are the quantitative portfolio manager in our research desk.
We are running an iterative backtest optimization loop targeting an 80% win rate.

Below is the full iteration history so far:

{history_text}

Your task:
1. Diagnose WHY the current win rate is below 80%. Be specific: which tickers drag performance, what exit/entry problems are visible in the numbers (high avg loss, low trade count, frequent eod closes, etc.).
2. Propose concrete parameter changes for the NEXT iteration. Choose changes that address the root cause, not cosmetic tweaks.
3. Change at most 3-4 parameters per iteration so causation is clear.

Tunable parameters (JSON keys and types):
{tunable_params}

IMPORTANT: Your response MUST end with a JSON block between ```json and ``` markers containing ONLY the parameters to change (not the full config). Include these four keys inside the JSON:
  "diagnosis"        — string, 2-4 sentence summary of root cause
  "config_changes"   — object of parameter name → new value (only changed params)
  "iteration_theme"  — string, ≤8 words describing the change, e.g. "Tighten stops + VWAP filter on"
  "expected_impact"  — string, 1-2 sentences predicting effect on win rate / P&L

Example JSON:
```json
{{
  "diagnosis": "Win rate is low because stops are too wide relative to ATR, allowing trades to trend against position before hitting target. TSLA and NVDA in particular show large avg losses.",
  "config_changes": {{
    "atr_stop_multiplier": 1.0,
    "use_vwap_trend": true
  }},
  "iteration_theme": "Tighten stops + VWAP filter on",
  "expected_impact": "Reducing stop width cuts loss magnitude; VWAP filter should remove counter-trend entries, raising win rate by 10-15 pp."
}}
```
""".strip()

    def _parse(text: str) -> dict:
        import re
        match = re.search(r"```json\s*(.*?)```", text, re.DOTALL)
        if not match:
            raise ValueError("No JSON block found in Claude response")
        block = match.group(1).strip()
        return json.loads(block)

    raw = _ask(prompt, max_tokens=1600)

    try:
        result = _parse(raw)
    except (ValueError, json.JSONDecodeError):
        # Retry once with a stricter reminder
        retry_prompt = (
            prompt
            + "\n\nYour previous response did not contain a valid ```json ... ``` block. "
            "Please restate your diagnosis and end with valid JSON in the required format."
        )
        raw = _ask(retry_prompt, max_tokens=1600)
        result = _parse(raw)

    # Ensure required keys exist
    result.setdefault("diagnosis", "No diagnosis provided.")
    result.setdefault("config_changes", {})
    result.setdefault("iteration_theme", "—")
    result.setdefault("expected_impact", "—")
    return result


def compare_strategies(
    tickers: list[str],
    comparison: dict[str, dict[str, float]],
) -> str:
    """Ask Claude to interpret the multi-strategy backtest and recommend next steps.

    Parameters
    ----------
    tickers:
        The universe of tickers tested.
    comparison:
        Mapping of strategy variant name → stats dict
        (keys: total_trades, win_rate, average_win_pct, average_loss_pct, net_pnl_pct).
    """
    rows = "\n".join(
        f"  {name:<12}  trades={int(s['total_trades'])}  "
        f"win_rate={s['win_rate']:.1f}%  "
        f"avg_win={s['average_win_pct']:.2f}%  "
        f"avg_loss={s['average_loss_pct']:.2f}%  "
        f"net_pnl={s['net_pnl_pct']:.2f}%"
        for name, s in comparison.items()
    )

    prompt = f"""
We ran a 90-day intraday breakout + relative-volume strategy
across {', '.join(tickers)} with three exit variants:

{rows}

Exit logic:
  fixed_pct  — fixed 1 % stop, 2 % target; no trailing
  atr_tight  — 1.5× ATR stop, 2.5× ATR target; trailing fires at 1× ATR gain, trails 1.5× ATR
  atr_loose  — 1.5× ATR stop, 2.5× ATR target; trailing fires at 2× ATR gain, trails 2.0× ATR

As the desk's quantitative portfolio manager, respond under these four headers:
1. INTERPRETATION — what these numbers reveal about signal quality vs exit logic
2. BEST APPROACH — which variant to run and why; specific parameter tweaks you'd try first
3. SIGNAL IMPROVEMENTS — filters, conditions, or timeframe changes likely to raise win rate or P&L
4. LIVE RISK ASSESSMENT — execution risks, regime sensitivity, position sizing, what to monitor
""".strip()

    return _ask(prompt, max_tokens=1400)
