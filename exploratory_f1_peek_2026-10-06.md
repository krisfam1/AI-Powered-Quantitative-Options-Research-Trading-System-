# F1 exploratory peek, 2026-10-06 — EXPLORATORY, 20% POWER, NOT A VERDICT

One-time look at the F1 earnings dataset (`earnings_event_dataset.db`), approved by the user on 2026-10-06. Not a trial: no registration, hash, ledger row, verdict or tier, and it does not use the hypothesis slot. Run once. Definitions are the study's: S = AvgEA4 − IM; r_mid; r_net at c = 0.5 and 1.0; top quintile per ISO week; week-blocked resampling (10,000 draws, seed 42; permutation p for seeds 42 and 43).

**These 1,199 events have now been looked at. Any future use of them is not blind.**

## (a) Signal vs event straddle return — EXPLORATORY, 20% POWER, NOT A VERDICT

| Statistic | Value |
| --- | --- |
| Spearman ρ(S, r_mid) | **+0.020** |
| Week-blocked bootstrap 95% interval | −0.029 to +0.074 |
| One-sided p (week-blocked permutation, seeds 42 / 43) | 0.318 / 0.330 |

## (b) Top quintile of S, mean r_net — EXPLORATORY, 20% POWER, NOT A VERDICT

| Cost level | Mean r_net | Week-block bootstrap 95% interval |
| --- | --- | --- |
| c = 0.5 | +2.8% | −5.6% to +12.5% |
| c = 1.0 | −1.1% | −9.4% to +8.5% |

## (c) All events, mean r_net (baseline) — EXPLORATORY, 20% POWER, NOT A VERDICT

| Cost level | Mean r_net | Week-block bootstrap 95% interval |
| --- | --- | --- |
| c = 0.5 | −2.3% | −6.2% to +1.9% |
| c = 1.0 | −6.4% | −10.2% to −2.2% |

## (d) Events used and exit fallback — EXPLORATORY, 20% POWER, NOT A VERDICT

- Events used: **1,199** (147 ISO weeks; 303 in the per-week top quintile).
- Intrinsic exit fallback used: **354** events.
    - 155 had no exit quote rows (the count reported before the peek).
    - 199 had exit rows without a valid two-sided quote (bid or ask missing, or ask < bid); the script treated these as missing quotes.
    - This was decided in the script before the run and is reported as is; no re-run.

## (e) Power — EXPLORATORY, 20% POWER, NOT A VERDICT

About 20% power at ρ = 0.07 (α = 0.05/14, 1,199 events, design effect 1.6). The smallest effect detectable with 80% power is ρ ≈ 0.13.

Script: `f1_peek.py` (written in the session scratchpad; committed unchanged to the repo root in `45af241`), SHA-256 `AFECD553D1A5DC338F22A5E8C6D7ABFBD083840CF0E9D472916F15F3E1E99680`. It opens the database read-only and doesn't import modules that load `.env`.
