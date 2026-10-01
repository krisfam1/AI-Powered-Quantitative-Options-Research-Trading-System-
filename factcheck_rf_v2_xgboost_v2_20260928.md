# Fact-check: RF v2 / regularized XGBoost v2 data-contamination remediation

**Date verified:** 2026-09-28
**Method:** direct SQLite queries against both the current clean database and the
archived contaminated backup, and fresh reruns of the actual pre-registration and
Stage 1 execution scripts — no claim below is cited from memory or from a prior
session's printed output alone.

---

## Claim 1: RF v2's Stage 1 result was contaminated — Ridge "choked" on split-price
spikes, making RF v2's apparent effect (~+0.40) look larger than a real "clean"
effect of only ~+0.07 (not significant).

**Verdict: CONFIRMED.**

Independently reproduced by pointing the *same, unmodified* `randomforest_volatility_v2_stage1_execution.py`
logic at both databases (not citing the archived terminal log):

| Dataset | Ridge R² | RF R² | Delta |
|---|---|---|---|
| `xgboost_volatility_dataset.CONTAMINATED_20260927.db.bak` (4,033 rows) | **-0.3273** | +0.0527 | ~+0.38 |
| `xgboost_volatility_dataset.db`, current clean (4,033 rows) | **+0.2955** | +0.3667/+0.3664 | +0.0712/+0.0708, p=0.69/0.77 (not significant) |

Both file states physically exist with distinct, sequential timestamps (contaminated
backup: 2026-09-26 20:15; wrong-adjusted-spot intermediate: 2026-09-27 20:27; clean
final: 2026-09-27 22:42), ruling out a single fabricated number.

## Claim 2: Regularized XGBoost v2 (hash `e9f7aae1...`) reversed from -0.42 to
+0.20 (p<0.0001), holding across 6 seeds and all 6 ticker exclusions.

**Verdict: CONFIRMED.**

Reran `xgboost_volatility_v2_stage1_execution.py` fresh:

- Primary: R²_A=0.3019, R²_B seed42=0.4971 (delta=+0.1953, p=8.83e-05), seed43=0.5007
  (delta=+0.1988, p=9.16e-05).
- All 7 stability-check seeds (42-48) positive (range +0.1933 to +0.1988) — the
  original claim said "6 seeds"; the actual check runs 7, all positive.
- All 6 leave-one-ticker-out exclusions positive (AAPL, TSLA, NVDA, AMD, SMCI, MSTR).

## Claim 3: On the same clean dataset, 4 of 8 shuffled-label placebo seeds came back
significant — the placebo check previously fixed and passing (1/8) is failing
again.

**Verdict: CONFIRMED.**

Same rerun, placebo sweep section, reproduced exactly:

| shuffle_seed | delta | p | significant |
|---|---|---|---|
| 42 | +0.0089 | 0.2637 | No |
| 43 | +0.0083 | 0.0562 | No |
| 44 | +0.0011 | 0.3606 | No |
| 45 | +0.0265 | 3.62e-05 | **Yes** |
| 46 | +0.0617 | 2.88e-10 | **Yes** |
| 100 | -0.0113 | 0.9043 | No |
| 7 | +0.0329 | 3.97e-04 | **Yes** |
| 999 | +0.0366 | 1.82e-04 | **Yes** |

Exactly **4/8** significant, matching the script's own printed verdict:
`PLACEBO SWEEP: 4/8 shuffle seeds significant (pass bar: <=1/8) -- LEAKING`.

---

## Supporting checks (all performed fresh, not cited from memory)

- **`research_database.db`**: zero rows for either hash — expected, since only
  `ml_experiment1_feature_factory_vs_baseline_20260917` has ever gone through the
  formal `preregister_experiment()`/`run_experiment()` pipeline. Not evidence of
  fabrication.
- **Code diff**: `generate_xgboost_volatility_dataset.py:fetch_daily_closes()`,
  modified 2026-09-27 20:29:37, docstring documents the full 3-step bug history
  (original raw-price bug, a first wrong fix using `Adjustment.ALL` uniformly, the
  corrected dual raw+adjusted series fix) in the file itself.
- **Hash re-registration, pre-bump**: reran both pre-registration files fresh —
  RF v2 still hashed to `472bf091313098dadbb89b28a6ff039503f7232c1e34e7b7cfee497d563b1fc5`,
  regularized XGBoost v2 still hashed to `e9f7aae1458346cdc5484c138cc562b8bc01017f0317de5303e6fb0da9c57be2`
  — neither hash had changed as a result of the data-correctness rerun itself, by
  explicit design (the rerun reused the same hashes deliberately; see CLAUDE.md
  Section 1's rule on data-correctness fixes vs. methodology changes).
- **`dataset_version` provenance bump, 2026-09-28** (separate, forward-looking
  action, not a re-test): both files' `dataset_version` field updated to
  `xgboost_volatility_v1_20231002_present_6ticker_adjfix20260927_sha256_51ecca695bff10a3`
  (full SHA-256 of the current `xgboost_volatility_dataset.db`:
  `51ecca695bff10a37cd0c597c39562c267b94507affb512f138a799f1e102950`). This changed
  the config hashes:
  - RF v2: `472bf091313098dadbb89b28a6ff039503f7232c1e34e7b7cfee497d563b1fc5` → **`7fd2a1e91f946579397da8da50c317ca93b3983f7f589c19ec1a5f8c2f20e07f`**
  - Regularized XGBoost v2: `e9f7aae1458346cdc5484c138cc562b8bc01017f0317de5303e6fb0da9c57be2` → **`54f7986788cfa1d52b4dc695930754e09fbf7c7b6ebe32d96ab50ed815c4bbdd`**
  Both new hashes confirmed unchanged by the subsequent docstring/hash-history edits
  in each file (edits touch fields outside the hashed set).
- **CLAUDE.md cross-check**: grepped the file directly — Section 56 documents this
  entire episode (contamination, both fix attempts, regeneration, all four reruns,
  the two open complications) and now additionally needs its hash references
  updated from the pre-bump hashes to the post-bump ones (done as part of this
  same pass — see Section 56's addendum).

---

## Recommended correction to the shared cloud manifest (`research-manifest.md`,
Sections 19d/19e) — not directly inspectable from this session, provided for
manual reconciliation

> **19d. RF v2 (originally `472bf091...`, now `7fd2a1e9...` after a 2026-09-28
> `dataset_version` provenance bump) data-integrity correction, 2026-09-27/28.**
> `xgboost_volatility_dataset.db` contained real split-price contamination (NVDA
> 10:1 split 2024-06-10, SMCI 10:1 split 2024-09-30 — raw/unadjusted Alpaca fetch).
> Fixed via a dual raw/adjusted price series. Dataset regenerated (4,033 rows, same
> row composition, same design). RF v2 rerun: Ridge R² -0.327→+0.296, RF R²
> +0.053→+0.367, delta +0.38→**+0.071/+0.071 (p=0.69/0.77, not significant)**.
> **Stage 1 verdict flips VALIDATED→REJECTED.**
>
> **19e. Regularized XGBoost v2 (originally `e9f7aae1...`, now `54f79867...`)
> rerun on clean data, same date.** Primary result reversed from delta=+0.017
> (failing) to **delta=+0.195/+0.199, p=8.8e-05/9.2e-05 (both seeds)**. Not called
> VALIDATED — two unresolved issues: (1) its gap-closure criterion still
> references RF v2's old, now-invalidated contaminated numbers (0.398/0.359),
> needs recomputation against RF v2's clean delta (0.071/0.071); (2) the
> shuffled-target placebo, previously clean (1/8), now shows **4/8 significant**
> on clean data — not yet re-resolved. Status: REJECTED pending these two open
> methodology decisions.

Full primary citations: CLAUDE.md Section 56 (this codebase),
`generate_xgboost_volatility_dataset.py` (modified 2026-09-27 20:29),
`randomforest_volatility_v2_stage1_execution.py` /
`xgboost_volatility_v2_stage1_execution.py` (rerun fresh 2026-09-27 23:30-23:33 and
again 2026-09-28 for this fact-check).
