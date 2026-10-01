# Step 2: Target Design Comparison — Broader-Universe ML Volatility Hypothesis

**Date: 2026-09-29. Comparison and recommendation only — no target selected, no preregistration written, no hash computed, no code written. Builds on the Step 1 feasibility audit (`broader_universe_feasibility_report.md`), approved 2026-09-29 with the full 59-ticker universe (existing 6 + all 53 candidates that passed feasibility). Does not touch RF v1/v2, XGBoost v1, or regularized XGBoost v2 (CLAUDE.md Section 58, permanently closed).**

Three candidate target constructions are compared, all built on the same underlying base quantity (forward realized volatility of the underlying, the one target class with a real surviving signal in this project's history — CLAUDE.md Section 33/45): a same-date cross-sectional rank/percentile, a same-date cross-sectional z-score, and a relative-to-own-history transform. This comparison exists specifically because of CLAUDE.md Section 58's finding — a model predicting *raw* forward realized volatility across this project's 6-ticker (soon 59-ticker) universe can score R²≈0.50 purely by memorizing each ticker's own historical average, with zero real options-feature signal. Any target chosen here must be evaluated against that failure mode explicitly, not just against ordinary regression diagnostics.

---

## 1. Definitions

- **A — Same-date cross-sectional rank/percentile.** For each date *t*, take all tickers with a valid raw forward-realized-vol reading that day (*N_t* of them), rank ticker *i* from lowest (1) to highest (*N_t*) volatility, and normalize to a percentile `rank_i / N_t` ∈ (0, 1].
- **B — Same-date cross-sectional z-score.** For each date *t*: `z_i = (raw_i − mean_t) / std_t`, where `mean_t`/`std_t` are computed across the *N_t* tickers observed that day.
- **C — Relative-to-own-history.** For each ticker *i* independently: `z_i,t = (raw_i,t − trailing_mean_i) / trailing_std_i`, where the trailing mean/std are computed from that same ticker's own historical window strictly before *t* (a fixed lookback, e.g. 252 trading days, chosen and locked before any result is computed).

All three operate on the **same underlying raw quantity** (e.g., 20-day forward realized vol) — this comparison is about the *transform*, not a different base measurement.

---

## 2. Criterion-by-criterion comparison

### 2.1 Economic interpretation

| | A (rank) | B (z-score) | C (own-history) |
|---|---|---|---|
| Question answered | "Is this ticker's forward vol unusually high/low **relative to its peers today**?" | Same as A, but with magnitude: "**how many cross-sectional sigmas** from today's peer average?" | "Is this ticker's forward vol unusually high/low **relative to its own typical regime**?" |
| Natural strategy mapping | Dispersion / relative-value vol trading (long vol on cross-sectionally cheap names, short on rich ones) | Same as A | Single-name vol-regime timing (buy/sell vol on *this* name based on *its own* history) |

A and B are the same *kind* of economic statement (cross-sectional relative value); C is a categorically different question (own-regime timing). This is the single largest fork in the comparison — see Section 3 for why it matters more than it might first appear.

### 2.2 Statistical properties

- **A**: Marginal distribution is ~uniform on (0,1] by construction (ties aside) — this is a genuine, non-trivial advantage: it is **stationary across calendar time by construction**, immune to secular shifts in the market's overall vol regime (e.g., a structurally calmer 2024 vs. a more turbulent 2026 — a real concern over a ~3-year window). Only relative ORDER is preserved; the day's absolute dispersion (tight vs. wide cross-section) is discarded.
- **B**: Continuous, roughly Gaussian-ish if the raw variable is roughly log-normal within a date. Removes the same market-wide level shift A does, but the *shape* of the cross-section (not just its mean/scale) still varies date to date, and one date's z-scores are coupled together through a shared, small-sample mean/std estimate (see 2.4).
- **C**: Continuous, real-valued, retains full magnitude. Requires each ticker's own trailing distribution to be well-estimated *before* the observation is usable — a genuinely different kind of statistical dependency (temporal, per-ticker) than A/B's (cross-sectional, same-day).

### 2.3 Cross-sectional comparability

- **A and B**: By construction, directly apples-to-apples across tickers **on the same date** — a rank of "top decile today" or a z-score of "+1.5σ today" means the identical thing for AAPL or SMCI on that date.
- **C**: Numerically on a common (standardized) scale, but the *reference distribution differs per ticker* — a "+2σ" reading for AAPL (typically calm) and a "+2σ" reading for MSTR (typically turbulent) represent very different absolute vol levels and, arguably, different real-world conditions. Comparable in units, not in meaning.

### 2.4 Outlier sensitivity

This project has a specific, documented history of extreme-outlier contamination (unadjusted stock splits — CLAUDE.md Section 56 — and a real idiosyncratic vol spike, the SMCI 2024 accounting-scandal cluster) that materially damaged prior experiments on this exact dataset family. This criterion should be weighted more heavily than it would be in a generic ML design.

- **A (rank)**: **Most robust of the three.** An extreme outlier simply becomes "the max rank that day" — bounded, does not distort any other ticker's rank that day.
- **B (z-score)**: **Least robust.** The cross-sectional std is estimated from a small same-day sample (historically N=6; even at the full 59-ticker universe, single-digit-to-low-dozens on any given date once missing data is accounted for). A single extreme value inflates that day's std estimate and **compresses every other ticker's z-score toward zero on that same date** — a real, mechanical contamination-transmission channel from one ticker's bad day onto every other ticker's target value that day, even though nothing changed for them. A median/MAD-based ("modified z-score") variant would partially mitigate this but is a design choice not yet made.
- **C (own-history)**: A ticker's own extreme history can distort *its own* future baseline for an extended period (e.g., SMCI's own trailing mean/std staying elevated for months after its 2024 turmoil, per Section 56) — a real, but strictly *contained* risk (doesn't leak into other tickers' targets the way B's does).

### 2.5 Missing-data requirements

- **A and B**: Require the cross-section to be reasonably well-populated on a given date to be well-defined — a date where several of the 59 tickers have gaps (EODHD/Alpaca coverage gaps, some real per the Step 1 report) changes every remaining ticker's rank/z-score that day. Practically requires either dropping thin-coverage dates or accepting a varying, sometimes small, effective *N_t*. Newer, IPO-limited tickers (ARM, RIVN, LCID, SOFI, COIN, PLTR, AFRM — Step 1 report) will be under-represented in the cross-section for the earliest part of the window, shrinking effective daily coverage exactly when the panel is otherwise widest in name count.
- **C**: Fully independent of other tickers' same-day coverage — a gap for ticker Y never affects ticker X's target. But it imposes its **own** cost: each ticker needs a sufficient trailing burn-in window before its *first* usable observation, which is a real and disclosed tax on precisely the newest, most data-constrained tickers from the Step 1 report (e.g., ARM's 762-day history would lose a full lookback window's worth of usable dates at the very start, worse proportionally than for the full-depth tickers).

### 2.6 ML suitability

- **A**: Well-suited to regression (percentile as continuous 0–1) or a learning-to-rank objective. Discards magnitude — two dates with identical rank orderings but very different absolute dispersion (a calm day vs. a stressed day) look identical to the model, which may throw away real, economically meaningful information.
- **B**: Standard continuous regression target, retains magnitude, directly compatible with this project's existing MSE/MAE/Wilcoxon evaluation machinery with no adaptation.
- **C**: Same as B — continuous, magnitude-preserving, and the single closest match to what the four already-closed experiments (Sections 45/46/48/51) already did, minimizing methodological novelty in the modeling step itself (novelty is concentrated entirely in the target transform).

### 2.7 Ability to prevent ticker-average memorization — the decisive criterion given Section 58

- **A and B**: **Do not structurally solve the problem.** If a ticker (e.g., MSTR) is *persistently* more volatile than its peers, it will *persistently* rank near the top / show a persistently positive same-day z-score. "Which ticker is this" remains a real, learnable predictor of the *typical* rank or z-score sign unless ticker identity is explicitly controlled for — meaning the mandatory ticker-fixed-effects baseline (CLAUDE.md Section 1's new rule, Section 58) is still **required**, not optional, under either of these targets. This is a real, disclosed limitation, not a fatal one — the control already exists and is proven (`analyze_ticker_fixed_effects.py`).
- **C**: **Structurally solves the problem by construction, not merely by an added control.** The target is *already* a deviation from that ticker's own historical average — a "ticker-only baseline" (predict this ticker's own historical average of the *target itself*) is identically ~0 for every ticker, since there is no persistent per-ticker mean left in the quantity being predicted. Section 58's entire failure mode cannot arise in this form. (A smaller, second-order risk remains: a model could still learn that some tickers have systematically *larger deviations* from their own mean than others — i.e., ticker-level heteroskedasticity even after centering — so the ticker-fixed-effects baseline check should still be run as a matter of discipline, but the stakes are categorically smaller than for A/B.)

### 2.8 Evaluation implications

- **Splitting**: All three still support a chronological (not random) train/val/test split by date — no change to the project's existing discipline. C additionally requires the split boundary to sit strictly after each ticker's own burn-in window closes.
- **Clustering for significance tests**: For A/B, same-date observations across tickers are *mechanically linked* (they share a common cross-sectional reference) — day-clustering, already this project's standing practice for Monte Carlo controls (Phase 6, GEX experiments), becomes **necessary, not just conservative**, for any permutation-based test on these targets. C's observations are comparatively closer to independent across tickers on a given date (each built from its own separate history), reducing but not eliminating the same-day-clustering concern (market-wide co-movement still exists).
- **Placebo/shuffle design**: This needs fresh design work regardless of target choice — the shuffled-target placebo used for A/B should permute ticker labels **within** a date (preserving the cross-sectional structure, scrambling which ticker got which rank/z-score) rather than shuffling across time, which is a different construction than anything already built in this project. For C, a placebo closer to the existing designs (shuffling the demeaned target across observations) remains meaningful, but the "ticker-only baseline" comparator needs to be redefined (predicting ~0, or a naive persistence/AR(1)-style forecast, rather than "this ticker's historical mean of the raw target," which is degenerate under C).

---

## 3. A tension worth surfacing explicitly, not just noting in passing

**Two of the criteria pull in opposite directions, and this is the real crux of the decision:**

- **The entire reason Step 1 built a 59-ticker universe was to escape the "thin cross-sectional breadth" limitation this project's own roadmap had already flagged** (CLAUDE.md Section 6 item 8 / Section 38: cross-sectional/relative-value work was rated "partially realistic... universe breadth is the bigger practical constraint" at 6 tickers). **Targets A and B are the only two that actually use that investment** — they produce a genuinely cross-sectional signal that a 59-ticker universe makes meaningfully more powerful than a 6-ticker one ever could. Target C does not benefit from cross-sectional breadth at all; it would work identically well (or poorly) with 6 tickers or 590, since it never compares tickers to each other.
- **But this project has zero execution infrastructure for a relative-value / dispersion strategy.** The Step-1-adjacent stat-arb feasibility survey (Section 38) confirmed directly: "no cointegration-testing tool, no spread-construction logic, no pairs-selection infrastructure" exists anywhere in this codebase. Every live and backtest execution path built in this project (V1, `portfolio_backtest.py`, all three live bots) is a **single-ticker entry/exit decision** — none of them can act on "ticker X is cheap relative to ticker Y today." A validated A/B-style signal would need an entirely new execution layer built before it could ever be traded. A validated C-style signal, by contrast, maps directly onto the single-ticker execution machinery this project has already built and paper-validated — a positive result could, in principle, be operationalized with no new execution infrastructure at all.

Neither side of this tradeoff is a mistake in either direction — it is a genuine fork between "use the new infrastructure fully, but need to build execution machinery later" and "get a result that's immediately actionable with what already exists, but leave the breadth investment underused."

---

## 4. Summary table

| Criterion | A (rank) | B (z-score) | C (own-history) |
|---|---|---|---|
| Economic interpretation | Cross-sectional relative value | Cross-sectional relative value (+ magnitude) | Single-name regime timing |
| Statistical stability over time | Strongest (stationary by construction) | Moderate | Depends on lookback choice |
| Cross-sectional comparability | Strong (order only) | Strong (+ magnitude) | Weak (different reference per ticker) |
| Outlier robustness | **Strongest** | **Weakest** (contaminates other tickers same-day) | Contained (own-ticker only) |
| Missing-data sensitivity | Needs full cross-section same-day | Needs full cross-section same-day (worse: small-N std) | Needs per-ticker burn-in only |
| ML suitability | Loses magnitude | Full magnitude, standard | Full magnitude, standard, closest to existing pipeline |
| Solves Section 58 memorization | No — needs the existing mandatory control | No — needs the existing mandatory control | **Yes, structurally, by construction** |
| Leverages the new 59-ticker breadth | **Yes, fully** | **Yes, fully** | No — breadth is irrelevant to this target |
| Maps to existing execution infrastructure | No — needs new relative-value/dispersion infrastructure (none exists) | No — same gap | **Yes — directly, zero new infrastructure** |

---

## 5. Recommendation

Both real considerations point in different directions, and reasonable people could land on either — this is presented as a recommendation, not a decision.

**On balance, I lean toward C (relative-to-own-history)**, primarily because:
1. It is the only one of the three that **structurally** eliminates the exact, hard-won, empirically-confirmed failure mode this project just spent real effort diagnosing (Section 58) — not via an added-on control, but by the target's own definition. Given how decisive and costly that finding was (it silently invalidated what had briefly looked like this project's strongest ML result, RF v2), I weight this criterion above the others.
2. It maps directly onto execution infrastructure this project has already built, tested, and paper-validated — a real result would not be stranded waiting on a whole new execution layer, unlike A/B.
3. Its downsides (own-history contamination from a ticker's own past extreme events, per-ticker burn-in cost on the newest tickers, weaker cross-ticker comparability of meaning) are real but manageable with disclosed design choices (a robust trailing statistic, a locked lookback window, and honest reporting of which tickers lose the most history to burn-in).

**The strongest argument against this recommendation, stated plainly**: choosing C means the 59-ticker Step 1 investment mostly just buys "more single-name observations," not the cross-sectional richness that was the original, explicit motivation for expanding the universe in the first place. If the real long-term intent behind this track is eventually to pursue genuine cross-sectional/relative-value trading (Section 6 item 8, Section 38), A or B would be the more purposeful choice, and the execution-infrastructure gap would simply become a real, disclosed, future-work item rather than a reason to avoid the cross-sectional framing now.

No target has been selected. Awaiting explicit direction before any preregistration work begins.
