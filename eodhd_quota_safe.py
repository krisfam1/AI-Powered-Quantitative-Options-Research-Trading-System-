"""
eodhd_quota_safe.py

Drop-in fix for the 59-ticker backfill script's missing backoff logic.

What went wrong last time (per research-manifest.md, Section 24):
the backfill hit EODHD's daily quota (HTTP 429) partway through ticker #9,
then spent ~7 more hours re-hitting the same wall on every remaining
candidate, logging each as a "retriable failure" -- and the script still
printed "RUN COMPLETE" / exited 0 at the end, even though only 9/59
tickers were actually processed.

This module fixes both problems:
  1. STOPS THE WHOLE RUN immediately on the first 429 -- no retries,
     no continuing to the next ticker, nothing. Per the explicit decision
     already recorded in the manifest: assume the worst case (failed
     calls DO count against the quota), so don't burn any more of it.
  2. Makes it structurally impossible to log "COMPLETE" on a partial run --
     the run summary distinguishes FINISHED from STOPPED_ON_QUOTA and
     records exactly which tickers were done, so resuming is trivial.

How to integrate into your existing backfill script:

    from eodhd_quota_safe import QuotaExceededError, safe_get, BackfillRunGuard

    guard = BackfillRunGuard(total_tickers=len(ticker_list))

    for ticker in ticker_list:
        if ticker in already_done_tickers:      # your existing resume/skip check
            continue
        try:
            resp = safe_get(url, params=params)   # replace your raw requests.get(...) calls with this
            # ... process resp, save rows to your DB as before ...
            guard.mark_done(ticker)
        except QuotaExceededError as e:
            guard.stop_on_quota(ticker, e)
            break   # stop the whole loop immediately -- do not continue to next ticker

    guard.print_summary()   # prints FINISHED or STOPPED_ON_QUOTA, never a false "COMPLETE"

Replace every raw `requests.get(...)` call in the backfill (both the
underlying-price fetches and the options-chain fetches) with `safe_get(...)`
so a 429 anywhere in the pipeline is caught, not just in one code path.

NOTE added during integration review (2026-09-30): in
generate_broader_universe_volatility_dataset.py specifically, underlying
prices are fetched via the Alpaca SDK (StockHistoricalDataClient), not a
raw requests.get() -- there is no second EODHD call site to swap there.
The only raw EODHD call in that script already goes through
gex_data_loader.py:_fetch_raw_chain_paginated(), which itself does a plain
resp.raise_for_status() with no internal retry -- so wiring safe_get() in
underneath it would not change behavior at that call site, since the
script's own QuotaExhaustedError fix (added and validated overnight
2026-09-29/30) already stops the run immediately on 429 with no retry --
functionally equivalent to this module's contract. Not swapped in for
that reason; kept here, saved to disk, for reference/future use rather
than wired into the current script. See CLAUDE.md Section 60 for the
full comparison.
"""

from __future__ import annotations

import sys
import time
import requests
from dataclasses import dataclass, field


class QuotaExceededError(Exception):
    """Raised the moment EODHD returns HTTP 429. Never caught-and-retried
    internally -- the whole backfill run must stop when this is raised."""

    def __init__(self, url: str, status_code: int, body_snippet: str):
        self.url = url
        self.status_code = status_code
        self.body_snippet = body_snippet
        super().__init__(
            f"EODHD quota exceeded (HTTP {status_code}) calling {url}. "
            f"Response snippet: {body_snippet[:200]!r}"
        )


def safe_get(url: str, params: dict | None = None, timeout: int = 20) -> requests.Response:
    """
    Wrapper around requests.get() for all EODHD calls.

    - On HTTP 429: raises QuotaExceededError immediately. No retry, no
      backoff-and-continue. The caller's loop must stop on this.
    - On other non-2xx statuses: raises requests.HTTPError as normal
      (these are real bugs/bad-request issues, not quota issues, and
      should surface normally rather than being swallowed).
    - On success: returns the Response object, same as requests.get().
    """
    resp = requests.get(url, params=params, timeout=timeout)

    if resp.status_code == 429:
        raise QuotaExceededError(url=url, status_code=429, body_snippet=resp.text)

    resp.raise_for_status()
    return resp


@dataclass
class BackfillRunGuard:
    """
    Tracks real per-ticker progress through a run and makes it impossible
    to report a false "complete" when the run actually stopped early.
    """

    total_tickers: int
    started_at: float = field(default_factory=time.time)
    completed_tickers: list[str] = field(default_factory=list)
    stopped_reason: str | None = None
    stopped_on_ticker: str | None = None

    def mark_done(self, ticker: str) -> None:
        self.completed_tickers.append(ticker)
        print(f"[{len(self.completed_tickers)}/{self.total_tickers}] done: {ticker}")

    def stop_on_quota(self, ticker: str, err: QuotaExceededError) -> None:
        self.stopped_on_ticker = ticker
        self.stopped_reason = str(err)
        print(
            f"\nSTOPPING RUN -- quota exceeded while processing {ticker!r} "
            f"({len(self.completed_tickers)}/{self.total_tickers} tickers completed).\n"
            f"Reason: {err}\n"
            f"Not continuing to remaining tickers. Resume later starting from {ticker!r}.",
            file=sys.stderr,
        )

    def print_summary(self) -> None:
        elapsed = time.time() - self.started_at
        n_done = len(self.completed_tickers)
        if self.stopped_reason is None and n_done == self.total_tickers:
            print(f"\nRUN STATUS: FINISHED -- {n_done}/{self.total_tickers} tickers, {elapsed:.0f}s elapsed.")
        elif self.stopped_reason is not None:
            print(
                f"\nRUN STATUS: STOPPED_ON_QUOTA -- {n_done}/{self.total_tickers} tickers completed, "
                f"{elapsed:.0f}s elapsed. Stopped at {self.stopped_on_ticker!r}. "
                f"This is NOT a completed run -- do not treat it as one."
            )
        else:
            # Loop ended without hitting the total and without a quota error --
            # some other bug. Flag it loudly rather than staying silent.
            print(
                f"\nRUN STATUS: INCOMPLETE_UNKNOWN_REASON -- {n_done}/{self.total_tickers} tickers "
                f"completed, {elapsed:.0f}s elapsed, no quota error recorded. Investigate before "
                f"assuming this run did what you expected."
            )
