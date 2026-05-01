# Phase 6 Audit — 2024 Practical Application + Beginner Breakout + Monthly Roadmaps

**Date**: 2026-05-01
**Scope**: 21 chapters from `Chapter_PDFs_With_Transcript/` not present in original 156-PDF audit
**Method**: 3 parallel general-purpose agents, each auditing one logical bucket against current methodology

## Source chapters audited

### Bucket A — Monthly Roadmaps 2024 (3 chapters)
- Ch 153: 02.01.2024 — JANUARY Monthly Roadmap (Equity Indices)
- Ch 155: 03.02.2024 — FEBRUARY Monthly Roadmap (Equity Indices)
- Ch 156: 03.03.2024 — MARCH Monthly Roadmap (Equity Indices)

### Bucket B — Practical Application series (7 chapters)
- Ch 170: 03.04.2024 — Seasonality
- Ch 171: 04.03.2024 — Zoning Process
- Ch 172: 05.03.2024 — Location
- Ch 173: 05.03.2024 — Valuation
- Ch 174: 06.03.2024 — Direction
- Ch 175: 07.03.2024 — LTF Entries
- Ch 177: 11.03.2024 — Zoning Process (second session)

### Bucket C — Beginner Breakout Room (11 chapters)
- Ch 169, 176, 178–186 (Jan–Feb 2024 Q&A sessions)

## Findings summary

- **3 P1 corrections** (rule contradictions / new hard rules)
- **~30 P2 additions** (new rules / nuances / clarifications)
- **0 fundamental misrepresentations** — current methodology is structurally correct

---

## P1 Corrections (apply to methodology + code)

### P1-1: Zone consumption threshold = 25% penetration invalidates zone
**Source**: Ch 184 — *"the bottom zone is taking out because the zone is was tested more than 25%"*

**Current state**: Methodology has retest formula `Q3 = 10/(retests+1)` for shallow tests but no hard penetration threshold for invalidation.

**Fix**: Add explicit invalidation rule. A zone with >25% penetration into its range = INVALIDATED (Q3 = 0, do not trade). The retest formula applies only to tests that did NOT exceed 25% penetration.

**Files**: `methodology/02_zone_qualifiers.md` (Q3 Freshness), `Propfirm Trading Dashboard/BP_zone_detector.py` (`_count_retests_split` should differentiate >25% from <=25% tests).

---

### P1-2: Big Brother / Small Brother is CONTAINMENT, not multi-TF stacking
**Source**: Ch 182 — student asks about stacking weekly+daily coverage; Bernd: *"That's not how it works… you have to pick"*

**Current state**: `BP_zone_detector.has_big_brother_coverage()` correctly checks containment, but methodology docs may read as if you stack both. Risk of misinterpretation.

**Fix**: Clarify in methodology that BB/SB is a containment check (LTF zone fits INSIDE HTF zone of same direction) on a single trade — you pick ONE primary HTF, then refine downward. You do NOT draw zones on every TF and add them up.

**Files**: `methodology/01_zone_detection.md` (BB/SB section), `methodology/06_seven_step_process.md`.

---

### P1-3: Equity-index short requires bond ROC actively rolling negative (not just positioned)
**Source**: Ch 156 — *"right now I just don't see the short coming. Retailers are getting more and more bullish on the weekly… we need the help of other Treasury bonds [to roll over]"*

**Current state**: CLAUDE.md documents "Treasury Bond gate before equity index short setups" but treats it as a positioning check.

**Fix**: Tighten gate — bonds must be actively rolling over (ROC turning from positive toward negative on the relevant lookback), not merely net-long-positioned. Combined with retailer-extreme rule.

**Files**: `methodology/03_fundamentals.md` (equity short subsection), `Propfirm Trading Dashboard/BP_rules_engine.py` (cross-asset gate logic).

---

## P2 Additions

### Zone & Drawing
- **Gaps function as explosive leg-outs** (Ch 171 — *"a gap, you can usually a gap"*). Add to leg-out classification rules.
- **Discretionary candle inclusion when overlapping HTF/LTF** (Ch 171, 177). When a candle could be classified either way, both interpretations are valid — document this explicitly.
- **Mark single last candle as fallback** (Ch 178). When no formation exists, mark the last candle as a reference level.
- **Mandatory "price on proximal" annotation** (Ch 182). Practical hygiene rule.

### Qualifiers / Zone Refinement
- **Preferred-version touch as active entry trigger** (Ch 156). Q3's wider/preferred distinction promoted from scoring to entry-gating: wait for preferred-version touch, not just wider-version touch.
- **Trade-upper-area-only LOL sub-option** (Ch 177). When LOL spans wide range and full-range R:R < 2:1, trade only the upper area for supply (or lower for demand) to recover R:R.
- **Refinement = delete-and-restart on LTF, not annotation overlay** (Ch 184).
- **Refinement 3-way trade-off explicit** (Ch 175): tighter stop raises R:R BUT lowers fill probability AND raises stop-out probability.

### Fundamentals — COT
- **COT Report (raw counts) inspection BEFORE COT Index** every roadmap session (Ch 155). Add sequencing note.
- **Wait-for-N-COT-updates gate** when setup is forming pre-extreme (Ch 155 — *"two more updates on COT data"*). Defer entry 1–2 weekly releases when index trajectory is fast but threshold not yet reached.
- **Commercial regime-flip detector** (Ch 155 — *"super bullish to all of a sudden, super bearish… really indicative to something bigger"*). ≥40-point COT index swing in ≤3 weeks = leading reversal signal.
- **Retailer disagreement = soft warning for non-PM** (Ch 176). Confirms PM-only hard veto; for other classes, retailer mismatch is reduce-size warning.

### Fundamentals — Valuation
- **Top-7 mega-cap Valuation basket scan as NQ bias engine** (Ch 153). Extends AAPL+MSFT dual-gate to {AAPL, MSFT, GOOG, META, AMZN, NFLX, TSLA, NVDA}; require ≥4/7 undervalued for NQ long bias.
- **Stock long requires both long-term AND short-term Valuation undervalued** (Ch 153 — *"close to being undervalued long term and short term"*). Dual-timeframe alignment for individual stocks.
- **Daily Valuation as EXIT signal even on weekly trades** (Ch 173). When LTF Valuation prints overvalued/undervalued against trade direction, treat as exit warning.
- **Bond-induced Valuation freeze caveat** (Ch 156). When equity Valuation reads neutral but bond reference is rallying in lockstep with equities, the reading is uninformative — weight reduced.
- **Bullish Seasonality blocks Valuation-overvalued shorts** (Ch 173). Mirror rule for longs. Seasonality dampens Valuation extremes when they conflict.

### Fundamentals — Seasonality
- **Per-asset Seasonality calibration** (Ch 170). Empirically test 5/10/15y per instrument; the "all three agree" rule is the strict signal, individual-lookback comparison is the calibration step.
- **Forward projection 30–150 bars** (Ch 170 — *"I just project 30 days in the future"*). Soften "150 bars forward" to "30–150 (per-trader preference)".
- **Index–constituent Seasonality conflict resolution** (Ch 170). When parent index seasonality contradicts constituent-stock zone setups, treat as vote-degradation factor.

### Trend / Direction
- **Pivot-break = explicit trend-reversal trigger** (Ch 174). A confirmed close beyond the most recent opposing pivot flips trend label.

### Entries
- **Entry can slide along proximal toward midpoint to achieve required R:R** (Ch 183). Sanctioned technique; capped at midpoint (E2).
- **Order placement asymmetry** (Ch 179). Entry buffered slightly inside zone for fill, stop adjusted symmetrically.
- **Multi-bar pattern repetition strengthens signal** (Ch 181 — two consecutive weekly hanging man).
- **LTF retracement appearance under bullish seasonality** (Ch 179). Set realistic LTF expectations: seasonality entries appear as retracements on 15m, not impulses.

### Trade Management
- **Stop above all-time high (not just zone distal) for shorts near ATH** (Ch 180). Liquidity-aware stop.
- **Long-term hold quantified**: up to 2 years / 4 weekly candles / 20 daily candles (Ch 185).
- **LTF opposing zone (when entered on HTF) = trade-management signal, NOT profit target** (Ch 186). Triggers BE move / partial close, not exit.
- **Multi-target hierarchy includes "price action zones" as target #4** (Ch 169) — opposing zones can be targets beyond fixed R-multiples.
- **Set-and-forget discipline**: don't touch stop until ≥1.5R achieved (Ch 181).
- **Mid-equilibrium LTF level-to-level swing trades sanctioned** (Ch 182). Soften "equilibrium = no-trade" — HTF equilibrium permits LTF range trades between intermediate levels.

### Asset class
- **Spot vs futures cross-confirmation** (Ch 182). When trading spot (e.g. XAUUSD), confirm formation on futures (GC) — broker spot charts may differ.
- **Stocks more demanding** (Ch 186 — *"stocks are always tricky"*). Reaffirms stock-specific caution.

### Roadmap / process
- **"Trade the constituents not the index" fallback** (Ch 153). When index has no tradable zone but mega-cap constituents are aligned, trade constituents directly.

---

## P3 Deferred (insufficient quantification)

- "Trap area" / institutional trap zones at HTF weekly highs (mentioned but not quantified)
- Number 4 target = "price action" beyond R-multiples (Ch 169) — context too fuzzy
- Adjusted vs unadjusted chart preference for zone anchor (mentioned but no decision rule)

---

## Confirmations (rules already correct — strengthened by new corpus)

Across all 21 chapters, these were confirmed as already correctly implemented:
- 6-qualifier framework (Q1–Q6) + LOL
- 33% Fibonacci stop convention (LTF entries)
- Indecisive base candle = body < 50% range
- 6-pivot right-to-left trend method
- Big Brother / Small Brother containment principle (already in code)
- Set-and-forget / 1:2 minimum R:R
- Equity Valuation references include DXY (CW42-Idx etc.)
- COT V2 two-band approach (26w + 156w)
- Multi-lookback Seasonality requiring all three to agree (strict)
- Equity basket 3% aggregate risk cap
- AAPL + MSFT parent-index gate (extended to top-7 in P2)
- Trend pillar gates counter-trend entries
- LOL stacking importance
