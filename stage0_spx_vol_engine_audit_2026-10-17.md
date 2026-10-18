# SPX volatility-state engine: Stage 0 data audit (2026-10-17)

**What this is:** the data audit the user approved on 2026-10-17 for the design in `spx_vol_state_engine_design_v1.md`. It covers counts, dates and data quality only.

**What this is not:** a test. No relationship between series, no forecast and no target was computed or looked at, for any years. The only cross-series checks are which dates exist in each series, and Cboe's SPX close against Yahoo's SPX close (the same series from two sources). No hypothesis slot was used. The search ledger is started, with 0 rows.

- **Raw data:** `data_snapshots/spx_vol_engine/` (303 files, 246 MB). `manifest.json` gives the source URL, download time, size and SHA-256 of every file.
- **Audit output:** `data_snapshots/spx_vol_engine/stage0_audit.json`.
- **Scripts:** in `spx_vol/` (`stage0_fetch.py`, `stage0_eodhd_check.py`, `stage0_eodhd_check2.py`, `stage0_audit.py`, `stage0_manifest.py`, `search_ledger.py`). They are not committed; only docs and the requirements file are, as instructed.
- **Environment:** `spx_vol/.venv`, a new virtual environment that is ignored by git, with versions pinned in `spx_vol/requirements_spx_vol.txt`. The system Python and the bots were not touched.
- **Search ledger:** `spx_vol/store/spx_vol.db`, table `search_ledger`. It is append-only (triggers block UPDATE and DELETE) and has 0 rows.
- **Reference calendar:** NYSE sessions from the Yahoo `^GSPC` dates, 2000-01-03 → 2026-10-16 (6,738 sessions). "Gaps" below means reference sessions missing from a series.
- **Blocks used for counts:** development 2004–2016, validation 2017–2020, locked 2021 onward.

---

## 1. Bottom line

1. **Usable from 2004:** SPX (close, and daily OHLC with a caveat), VIX, SKEW and the full VIX futures curve. All four are complete over the development block.
2. **The full stand-in vector starts on 2008-01-02**, when VIX6M begins. VVIX is regular from 2006-06. Adding VIX3M (starts 2009-09-18) or VIX9D (starts 2011-01-04) pushes the start past the 2008 crisis.
   - **Recommendation:** take the term structure from the VIX futures curve, which runs from 2004, rather than VIX3M or VIX9D.
3. **EODHD has no SPX, SPXW or VIX options at all**, only ETFs such as SPY. That took 4 of the 20 allowed requests, with no quota error.
4. **Missing, with no free source:** the SPX option surface (ATM IV at fixed maturities, 25-delta put and call IV, put − call IV) and SPX intraday bars.
5. **Two of the six libraries didn't install.** hmmlearn and ruptures have no build for Python 3.14 and need a C++ compiler. That blocks the HMM and change-point methods as designed. Options are in Section 5.
6. **SPX opens from 2004 to 2006 are mostly stale** (the open equals the previous close on 246 of 252 days in 2004). The open-based volatility estimators (Garman–Klass, Rogers–Satchell, Yang–Zhang) can't use SPX in those years. Parkinson (high/low) and close-to-close can.

---

## 2. Series by series

Step numbers refer to the 12 steps in the spec and design: 1 data, 2 exploratory analysis, 3 stationarity and breaks, 4 regimes, 5 single-variable anomalies, 6 multivariate anomalies, 7 analogs, 8 predictive tests, 9 walk-forward, 10 ensemble, 11 stress tests, 12 live report.

### 2.1 SPX and SPY prices

| Series | Source | First → last | Rows (dev / val / locked) | Gaps | Daily? Units | Quirks | Steps |
| --- | --- | --- | --- | --- | --- | --- | --- |
| SPX close | Cboe `SPX_History.csv` | 1975-01-02 → 2026-10-16 | 13,057 (3,273 / 1,007 / 1,454) | 0 | Daily close only; index points | **Agrees with Yahoo on 5,734 common dates since 2004.** Only 2 dates differ by more than 0.1% (2019-02-28 and 2021-08-11; at most 0.28%). Which source wins gets decided in Stage 1. | 1–12 (close-to-close RV, returns) |
| SPX OHLC | Yahoo chart API `^GSPC` | 2000-01-03 → 2026-10-16 | 6,738 (3,273 / 1,007 / 1,454) | 0 | Daily; index points; no volume meaning for an index | **Stale opens**, where the open equals the previous close: 2004: 246, 2005: 242, 2006: 107, 2007: 39, 2011: 23, 2012: 63, 2013: 66, and 0–4 in other years. No high < low, and no close outside high–low. The share of days with both a real upper and lower wick rises from ~0.6–0.7 before 2017 to 0.8–0.9 after, which suggests the intraday range was recorded more coarsely in earlier years. | 1–3. Parkinson from 2004. Open-based estimators from ~2008, or on SPY. |
| SPY OHLC, adjusted close | Yahoo chart API `SPY` | 2000-01-03 → 2026-10-16 | 6,738 (3,273 / 1,007 / 1,454) | 0 | Daily; dollars; volume present | 108 dividends, 0 splits. Only 50 stale opens since 2004, so SPY can stand in for SPX in the open-based estimators. Raw prices are not dividend-adjusted, so use adjusted closes for returns. | 1–3 (RV estimator comparison) |

**About the Yahoo data:** it is free to read but governed by Yahoo's terms; for research use only, not for redistribution. Stooq, the other free source tried, blocked automated download behind a JavaScript check, so it was skipped.

### 2.2 Cboe volatility indexes

| Series | First → last | Rows (dev / val / locked) | Gaps | Units | Quirks | Steps |
| --- | --- | --- | --- | --- | --- | --- |
| VIX | 1990-01-02 → 2026-10-16 | 9,296 (3,274 / 1,007 / 1,487) | 0 | Daily OHLC; annualized vol points (%) | **Published on 34 days when NYSE was closed:** 2004-06-11 (the Reagan national day of mourning), and US holidays 2022–2026 (5–8 a year, from Cboe's extended trading hours). Those rows get dropped to the NYSE calendar. There are 506 close-only rows (O = H = L = C); the only one after 2003 is the 2004-06-11 row. | 1–12 |
| VIX9D | 2011-01-04 → 2026-10-16 | 3,970 (1,509 / 1,007 / 1,454) | 0 | Same | Close-only rows until 2013-11-15 (722 rows) | Extended vector only (from 2011) |
| VIX3M | 2009-09-18 → 2026-10-16 | 4,296 (1,835 / 1,007 / 1,454) | 0 | Same | Clean OHLC. The 2026-10-02 snapshot had the same start, 4,285 rows. **The older VXV history (2007–2009) isn't in this file.** Trial #13 already looked at VIX3M/VIX, so that relationship can't be confirmatory. | Extended vector only (from 2009-09) |
| VIX6M | 2008-01-02 → 2026-10-16 | 4,728 (2,267 / 1,007 / 1,454) | 0 | Same | Close-only until 2013-11-26 (1,488 rows). One row has high < low (2019-07-05). | Core vector (sets its 2008 start) |
| VIX1Y | 2007-01-03 → 2026-10-16 | 4,973 (2,512 / 1,007 / 1,454) | 6 (Columbus and Veterans Day, 2007–2009) | Same | Close-only until 2018-03-13. One row has high < low (2018-12-03). | Optional |
| VIX1D | 2022-05-13 → 2026-10-16 | 1,111 (0 / 0 / 1,111) | 0 | Same | **Entirely inside the locked years, so it can't be used for development.** Eleven large one-day moves that reversed the next day, probably real for a one-day index. | None (excluded) |
| VVIX | 2006-03-06 → 2026-10-16 | 5,127 (2,666 / 1,007 / 1,454) | 61 (59 in Mar–May 2006, one each in 2010 and 2013) | Daily close only; vol-of-VIX points | **Sparse until 2006-06-01.** Two suspect prints: 2006-03-15 (15.71; the first row, 2006-03-06, is 71.73) and 2006-11-13. Use from 2006-06 onward. | Core vector |
| SKEW | 1990-01-02 → 2026-10-16 | 9,250 (3,272 / 1,004 / 1,453) | 15 (8 in 2000, 2 in 2003, and single days in 2011, 2017, 2018, 2019 and 2024) | Daily close only; index level (100 = normal tails) | It measures how fat the SPX tail is, not 25-delta skew, so it's a weaker stand-in for skew. | Core vector |

### 2.3 VIX futures (Cboe Futures Exchange)

- **Coverage:** 274 monthly contracts, trading 2004-03-26 → 2026-10-16, 47,746 contract-day rows.
- **Sources:** 2004–2013 expiries come from the old archive (`CFE_<month><yy>_VX.csv`); 2013 onward from the current per-contract files.
- **Completeness:** every NYSE session from 2004-03-26 has at least 3 contracts with a positive settlement (median 9, maximum 12). Every session has a contract at least 150 days from expiry, so the design's 30–150-day constant-maturity curve can be built for the whole period.

**Quirks to handle in Stage 1:**
1. **Prices before 2007-03-26 are 10× VIX** (the old VBI basis): median settlement 152.9 before, against 20.5 after. Divide by 10.
2. **2013 expiries exist in both formats.** The current-format files start only on 2013-01-02 and have zero settlements early on, which left 95 sessions with no settlement until the archive 2013 files were added. Rule: one row per contract and date, preferring the current file when its settlement is positive. That dropped 1,427 duplicate rows.
3. **Month gaps in 2004–2005:** no Dec 2004, Apr 2005, Jul 2005 or Sep 2005 contracts. The curve interpolates over wider maturity gaps in those years.
4. **Placeholder rows:** 364 have a missing or zero settlement, 2,282 have a zero open, and 445 have high < low, mostly listing-day placeholders. Use the settlement price only.
5. **Roll jumps:** a raw front/second-month series (VX1, VX2) jumps at each of the ~270 expiries. The constant-maturity curve avoids that. The size of the jumps was deliberately not measured.
6. **Expiry date** is approximated by each contract's last trade date. The real final settlement is a special opening quotation on the expiry morning.
7. **Recent and weekly contracts:** nine unexpired contracts will keep changing. Weekly VX futures (2015+) weren't downloaded and aren't needed.

### 2.4 The historicaldata.net sample (quality look only)

The free sample is SPX/SPXW, SPY, TSLA and KO options, 2022-07-01 → 2022-12-30. It was a direct download with no login or payment. **These dates are in the locked years, so only counts and completeness were checked**, and no values were examined.

| Underlying | Rows | Expiries | Bid present | Two-sided | Crossed (bid > ask) | IV and delta present | Same-day expiry rows |
| --- | --- | --- | --- | --- | --- | --- | --- |
| SPX | 845,643 | 25 | 96.3% | 96.3% | 0 | 87.4% | 4,868 |
| SPXW | 1,635,844 | 163 | 93.6% | 93.6% | 0 | 86.2% | 49,458 |
| SPY | 1,086,492 | 119 | 92.4% | 92.4% | 0 | 82.3% | 28,216 |

- **IV status:** `iv_flag` marks why IV is missing (codes 2, 3, 5 and 6; code 6 on every same-day expiry).
- **Snapshot timing:** `quote_time` is empty throughout. The README says that field only exists from August 2026, so the 2022 quotes are untimed end-of-day snapshots.
- **What this shows:** the paid full archive would provide the SPX surface the design lacks (25-delta and term-structure IV, from bid/ask with greeks). Nothing was bought.
- **Licence:** the sample's `LICENSE.txt` governs its use, so it isn't for redistribution.

### 2.5 EODHD coverage check (read-only)

- **Underlyings:** the endpoint lists 7,003. None of SPX, SPXW, VIX, XSP or VIXW is among them. The near matches are all ETFs or ETNs: SPXL, SPXS, SPXU, SPXC, SPXE, SPXN, SPXT, SPXV, USPX, UVIX, SVIX, VIXM, VIXY. SPY is listed.
- **Direct queries** for 2026-10-15: SPX returned HTTP 200 with 0 records, and VIX returned **HTTP 404** (not found).
- **Requests:** 4 in total, no quota error. The responses were 200, 200, 200 and 404, the 404 being the VIX query. Logs: `data_snapshots/spx_vol_engine/eodhd_check/`; the token isn't stored.
- *Corrected 2026-10-17 after the compliance audit (`spx_vol_engine_compliance_audit_2026-10-17.md`, Part E). This section originally said "no quota or error response" and that both queries "returned 0 records". The conclusion, that EODHD has no SPX, SPXW or VIX options, is unchanged.*

### 2.6 Already in the repo, not downloaded again

Treasury bill rates, 2007 onward (`data_snapshots/vrp_timing_20261002/`). 2004–2006 rates weren't in the approved download list.

---

## 3. When each vector can start

| Vector | Series | Starts | Development rows | Contains 2008? |
| --- | --- | --- | --- | --- |
| **Core (recommended)** | SPX OHLC/close, VIX, VIX6M, VVIX, SKEW, VIX futures curve | 2008-01-02 | 2,267 sessions (2008–2016) | Yes |
| Core without VIX6M | Same, minus VIX6M | 2006-06-01 | ~2,660 | Yes |
| Futures-only term structure | SPX, VIX, SKEW, VIX futures | 2004-03-26 | ~3,210 | Yes |
| Extended | Core + VIX3M + VIX9D | 2011-01-04 | 1,509 | **No** |

Validation (2017–2020) has 1,007 sessions and the locked block (2021 onward) 1,454 for every vector.

---

## 4. What is missing and what each gap blocks

| Missing | What it blocks | Stand-in or way around | How to get it |
| --- | --- | --- | --- |
| **SPX option surface:** ATM IV at fixed maturities, 25-delta put and call IV, put − call IV, SPX options term structure | The design's "IV − RV" built from options, "skew relative to ATM IV", "put IV − call IV" and the options term structure. Those relationships are dropped. | VIX family for 30-day ATM-like variance; VIX futures and VIX6M for term structure; SKEW for the tail | Paid only: the historicaldata.net full archive, ORATS, OptionMetrics, Cboe DataShop. Not on EODHD. |
| **SPX intraday bars** | Realized variance from intraday returns, and the planned scoring of daily estimators against intraday RV (design §3.1) | **Design change needed in Stage 2:** compare estimators by how well each one forecasts future close-to-close variance. SPY 5-minute bars from Alpaca (2016 onward) are a possible later add, but that needs a broker data call, which Stage 0 didn't allow. | Alpaca SPY bars, with approval; SPX intraday is paid |
| **Clean SPX opens, 2004–2007** | Garman–Klass, Rogers–Satchell and Yang–Zhang on SPX before ~2008 | SPY opens (only 50 stale since 2004); Parkinson and close-to-close on SPX | — |
| **VIX3M before 2009-09-18; VIX9D before 2011** | An extended vector covering 2008 | Term structure from the futures curve | Older VXV history not found in Cboe's free files |
| **VVIX before 2006-06** | Nothing, since the core vector starts in 2008 anyway | — | — |
| **VIX1D in the development years** | Nothing in the design depends on it | Excluded | Doesn't exist before 2022-05 |
| **hmmlearn, ruptures** | HMM regimes and PELT change-points (steps 3–4) as designed | statsmodels `MarkovRegression` does Markov switching; GMM and clustering are in scikit-learn | Decision in Section 5 |
| **T-bill rates, 2004–2006** | Excess returns before 2007, if a step needs them | Start excess-return work in 2007 | Treasury's free CSVs (needs approval; not in the Stage 0 list) |

---

## 5. Decisions for the user before Stage 1

1. **Which vector?** Core from 2008, keeping 2008 in development (recommended), or futures-only from 2004.
2. **The library gap.** Choose one:
   - **(a)** install Python 3.12 alongside 3.14 and rebuild `spx_vol/.venv` on it; hmmlearn and ruptures publish 3.12 builds (*verify*);
   - **(b)** install Microsoft C++ Build Tools and compile them;
   - **(c)** drop them, using statsmodels Markov switching for regimes and a small hand-written change-point method.
3. **The RV estimator comparison design change** (Section 4, row 2).
4. **Whether to add SPY 5-minute bars from Alpaca later** (a read-only data call, needing approval).

## 6. Rules kept

- No values, relationships, forecasts or targets were computed, for any years. The locked-year sample was counted only.
- No existing data or database was modified. `.env` was read only by `python-dotenv` inside the EODHD check script, and never printed.
- No broker calls. 4 EODHD requests, no strategy runs, nothing purchased.
- The bots, the registry, `hypothesis_ledger.csv` and the open experiments were not touched.
