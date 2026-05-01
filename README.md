# Azalyst Propfirm

Hourly cloud-hosted Bernd Skorupinski Blueprint trading-system scanner with a
Fundingpips-style $100k paper-trading account. Generates trade signals
(entry / SL / TP) you can copy to your real Fundingpips challenge.

## What this is

| Component | Where it runs | What it does |
|-----------|----------------|--------------|
| **Scanner** | GitHub Actions, hourly cron | Runs the 7-step Blueprint process across ~77 Fundingpips-tradable symbols, opens paper trades, manages SL/TP, commits state back to the repo |
| **Dashboard** | GitHub Pages (static HTML) | Displays signals, open positions, trade history, account P&L, and the Fundingpips Trading Objectives panel (Max Daily Loss / Max Loss progress bars) |
| **Paper trader** | Inside the scanner | $100k account, $5k max daily loss, $10k max total loss. Trades that would breach either limit are blocked — same as the real Fundingpips account |

## Folder layout

```
Azalyst Propfirm/
├── .github/workflows/
│   ├── scan.yml         hourly market scan + commit results
│   └── pages.yml        deploy dashboard to GitHub Pages on push
├── scanner/             Python scanner (BP_*.py + run_scanner.py)
│   ├── BP_config.yaml   watchlist + prop firm rules + qualifier weights
│   ├── BP_*.py          all methodology modules (zones, qualifiers, COT, …)
│   ├── run_scanner.py   entry point (CI-aware via --ci flag)
│   └── requirements.txt
├── dashboard/
│   └── dashboard.html   static dashboard (fetches ../data/scan_results.json)
├── data/                state files, written each scan and committed back
│   ├── scan_results.json     latest signals + positions + account
│   ├── paper_trader_state.json   persistent paper-account state
│   └── scan_history.json     per-scan summaries (long-term log)
├── index.html           top-level redirect → dashboard/
└── README.md
```

## Push to GitHub (Gemini-friendly steps)

If you're asking Gemini (or any AI) to push this folder to GitHub, give it
these instructions verbatim:

> Treat this folder as a self-contained git repo. Do all of the following:
>
> 1. `git init` inside this folder
> 2. `git add .` and `git commit -m "Initial commit: Azalyst Propfirm"`
> 3. Create a new GitHub repo (public is fine; private uses Actions minutes)
>    using `gh repo create azalyst-propfirm --public --source=. --push`
>    (or set up a remote and push manually with `git remote add origin …` +
>    `git branch -M main` + `git push -u origin main`)
> 4. In the GitHub UI: **Settings → Pages → Build and deployment → Source: GitHub Actions**
> 5. In **Settings → Actions → General → Workflow permissions**, set
>    **"Read and write permissions"** so the scan workflow can commit back
> 6. Trigger the first scan manually: **Actions tab → "Scan markets (hourly)" → Run workflow**
> 7. After the first scan succeeds, the dashboard is live at:
>    `https://<your-github-username>.github.io/<repo-name>/`

## What runs each hour

1. GitHub Actions runner spins up Ubuntu + Python 3.11
2. Installs `requirements.txt` (yfinance, pandas, numpy, pyyaml, requests)
3. Reads `scanner/BP_config.yaml` for watchlist + prop firm rules
4. Loads previous `data/paper_trader_state.json` so positions persist
5. For each of the ~77 symbols, runs **TWO strategy passes** (per Bernd's
   methodology: weekly bias + daily entry refinement OR daily bias + 60m entry):
   - **weekly pass**: HTF=1wk, LTF=1d (multi-day swing setups)
   - **daily pass**: HTF=1d, LTF=60m (intraday-to-day setups, comp-friendly)
   - Crypto symbols run **daily-only** (weekly bars on crypto are too few/volatile per audit)
   - Each pass: fetch OHLCV + COT + Valuation + Seasonality, run 7-step process
   - If a signal: submits to the paper trader (tagged with `strategy` field)
6. Updates open positions (BE moves, T2 partials, stop-outs)
7. Writes `data/scan_results.json` + `data/paper_trader_state.json` + `data/scan_history.json`
8. Commits and pushes those three files back to the repo
9. Pages auto-redeploys; dashboard reflects new signals + P&L

Total wall time per scan: ~10–12 min for 77 symbols × dual strategies (66 symbols × 2 passes + 11 crypto × 1 pass = 143 passes).

## Fundingpips paper-trader rules (configured in `BP_config.yaml`)

```yaml
prop_firm:
  enabled: true
  account_size: 100000.0
  max_daily_loss_usd: 5000.0     # 5% of $100k
  max_total_loss_usd: 10000.0    # 10% of $100k
  daily_reset_hour_utc: 22       # 17:00 NY = 22:00 UTC
```

The paper trader:
- Tracks **today's starting equity** (resets at the configured hour)
- **Blocks any new trade** whose risk would push today's loss above $5,000
- **Blocks any new trade** if total loss is already at or below $10,000
- Latches a `breached` flag if either limit is breached → **dashboard shows "BREACHED" pill** and no further trades open until you reset by deleting `data/paper_trader_state.json`

## How to use the signals on real Fundingpips

The dashboard shows each open signal with:
- **Symbol** (broker-style: EURUSD, XAUUSD, BTCUSD, …)
- **Direction** (LONG / SHORT)
- **Entry price**
- **Stop-loss price** (Fib -33 % below the zone distal, or distal-only for HTF weekly trades)
- **Targets**: T1 (1R), T2 (2R), T3 (3R), and price-action targets

Open your Fundingpips MT5 / cTrader / Match-Trader, place a pending order at
the displayed entry, set the stop and TP1/TP2/TP3 levels exactly as shown.
The paper trader uses the same risk size, so its P&L tracks what you would
have made on the real challenge.

## Local testing (optional)

You can also run the scanner locally before pushing:

```bash
cd scanner
pip install -r requirements.txt
python run_scanner.py            # opens local dashboard at http://127.0.0.1:8765
# or
python run_scanner.py --ci       # CI-style: writes data/, no server, no browser
```

## What's NOT here (intentional)

- **No live broker integration** — this generates signals only; you place
  trades manually on Fundingpips. That's the whole point: validate the
  system on a paper account before risking the real challenge.
- **No notifications service** — the dashboard refreshes every 30s when
  open. If you want push notifications, add a separate webhook on the
  scan workflow (Discord, Telegram, etc.).
- **No live tick** — position management resolves at scan frequency
  (hourly). Same as the original local scanner.

## ARCHITECTURE — How a trade decision is made

This section documents every gate the system passes through, with citations to the methodology spec (so a Bernd-trained trader can verify it and so a future AI agent can trace the decision logic).

### Data sources (per scan)

| Source | Provides | Used for | Spec |
|--------|----------|----------|------|
| Yahoo Finance (`yfinance`) | OHLCV candles per symbol, multiple timeframes | All TA: zone detection, candle classification, trend pivots, location Fib | — |
| CFTC public dataset | Weekly Commitment of Traders (commercials, non-commercials, retailers; longs+shorts) | COT Index + COT Report | `methodology/03_fundamentals.md` — COT |
| yfinance reference symbols | DXY, ZN, ZB, GC, ^TNX (daily OHLCV) | Valuation rate-of-change | `methodology/03_fundamentals.md` — Valuation §"Settings by Asset Class" |
| yfinance long history | 15y daily history per symbol | Seasonality 5y/10y/15y backdrop | `methodology/03_fundamentals.md` — Seasonality |
| `BP_roadmap.py` static tables | Presidential cycle, sannial decennial bias | Monthly Roadmap timing overlay | `methodology/03_fundamentals.md` — Roadmap |
| `BP_calendar.py` | US Federal holidays, CPI/NFP/FOMC dates | Two-session gate, news suppression | `methodology/06_seven_step_process.md` — Calendar Gates |

### The 7-step pipeline (per symbol, per strategy pass)

```
                   ┌─────────────────────────────────────────────────┐
                   │  ENTRY POINT: scan_symbol(sym, strategy, htf, ltf) │
                   └──────────────┬──────────────────────────────────┘
                                  ▼
┌─── STEP 1: MARKET SELECTION ───┐
│   Symbol + asset_class read    │   methodology/06 §"STEP 1"
│   from BP_config.yaml watchlist │
└──────────────┬─────────────────┘
               ▼
┌─── STEP 2: HTF TECHNICAL ANALYSIS ─────────────────────────────────────┐
│  (a) Detect HTF zones (provisional, no trend yet)                       │
│  (b) Compute Location % via Fib 33/66 across HTF zones                  │
│      ≤33% → bullish · 33-67% → equilibrium · ≥67% → bearish             │
│  (c) Compute Trend via ZigZag % pivots (3 swing high + 3 swing low,     │
│      RIGHT-to-LEFT). Phase 6: pivot-break flips trend label.            │
│  (d) Re-detect HTF zones WITH trend context (so Q5/Q6 fire only on      │
│      counter-trend setups).                                             │
└──────────────┬──────────────────────────────────────────────────────────┘
               ▼
┌─── STEP 3: FUNDAMENTAL CONFIRMATION ──────────────────────────────────┐
│  (a) COT Index per asset-class lookback (26w / 52w) + 156w extreme    │
│      Group focus per class:                                            │
│        Forex/Equities    : Non-Commercials divergence                  │
│        Commodities/Energ.: Commercials WITH (≥80 bullish, ≤20 bear)    │
│        Precious Metals   : Retailers CONTRARIAN                        │
│        Soft Ag (Cotton/Grains): Non-Commercials 26w                    │
│  (b) Cross-category COT (smart-vs-dumb confluence boosts to 'strong'; │
│      commercial regime-flip detector ≥40pt in ≤3 weeks — Phase 6)     │
│  (c) Forex: opposing-currency DXY cross-check                          │
│  (d) Valuation per-asset references (Phase 4+5 P1 corrected):          │
│        Forex            : DXY only                                     │
│        Equity Indices   : DXY + ZN + ZB                                │
│        Equities (stocks): DXY + ZN + ZB                                │
│        Commodities      : DXY + Gold + ZB                              │
│        Precious Metals  : DXY + Gold + ZB (default)                    │
│        Platinum         : DXY + Gold ONLY (no Bonds)                   │
│        Energies         : DXY + Gold + ZB                              │
│        Crypto           : DXY only                                     │
│      ROC: 10 default, 13 equities, per-symbol override                 │
│      Bias = composite vs 4-state thresholds (±75)                      │
│  (e) Seasonality multi-lookback 5y/10y/15y:                            │
│      All three must AGREE. Slope must actively TURN (not just be       │
│      positive). Strength tier: strong/moderate/none.                   │
│  (f) Monthly Roadmap (Presidential × Sannial cycle)                    │
└──────────────┬──────────────────────────────────────────────────────────┘
               ▼
┌─── BIAS SYNTHESIS RULE (HARD GATES) ──────────────────────────────────┐
│  (1) Valuation HARD PREREQUISITE GATE ("Rule Number One"):            │
│      strongly opposing direction → VETO                                │
│  (2) 3/5 vote (Location, Trend, COT, Valuation, Seasonality):         │
│      ≥3 for normal, ≥4 for counter-trend / counter-roadmap            │
│  (3) Class-conditional retailer veto:                                 │
│      PMs: hard veto if retailers same side                            │
│      others: reduce size 25-50%                                       │
└──────────────┬──────────────────────────────────────────────────────────┘
               ▼
┌─── STEP 4: LTF ZONE DETECTION ────────────────────────────────────────┐
│  (a) Detect LTF zones (DBR, RBR, RBD, DBD)                             │
│  (b) Score 6 qualifiers + LOL bonus (each 0-10):                       │
│       Q1 Departure (30%) — leg-out body ≥70% else INVALID              │
│       Q2 Base Duration (10%) — 1-2 best, 7+ INVALID                    │
│       Q3 Freshness (15%) — wider/preferred split                       │
│            >25% PENETRATION → Q3=0, INVALIDATED (Phase 6 P1)           │
│       Q4 Originality (15%) — original=10, non-original=5, FLIP=12      │
│       Q5 Profit Margin (10%) — counter-trend gate; skipped on trend    │
│       Q6 Arrival (10%) — counter-trend gate; skipped on trend          │
│       LOL (10%, max +5) — HTF+LTF zone stacking                        │
│       Composite weighted, ≥4.0 to keep                                 │
│  (c) BB/SB containment filter (Big Brother / Small Brother):           │
│      LTF zone must fit INSIDE same-direction HTF zone.                 │
│      CONTAINMENT, NOT multi-TF stacking (Phase 6 P1 clarification).    │
│  (d) Speed-bump detection (opposing zones in path)                     │
│  (e) Rank by composite, take BEST zone                                 │
└──────────────┬──────────────────────────────────────────────────────────┘
               ▼
┌─── DECISION MATRIX (HARD REJECTS) ────────────────────────────────────┐
│  Zone direction must MATCH bias consensus                              │
│  demand@expensive → NO ACTION; supply@cheap → NO ACTION                │
│  equilibrium + sideways trend → NO ACTION                              │
│  (Phase 6 P2: equilibrium permits LTF level-to-level swing trades      │
│   with reduced size + T2 cap)                                          │
└──────────────┬──────────────────────────────────────────────────────────┘
               ▼
┌─── EQUITY-INDEX SHORT CROSS-ASSET GATE (Phase 6 P1) ──────────────────┐
│  if asset_class=='equities' AND direction=='short':                    │
│    REQUIRE BOTH:                                                       │
│      (a) retailers extreme bullish (COT)                              │
│      (b) bond ROC actively turning negative                            │
│    fail either → VETO                                                  │
└──────────────┬──────────────────────────────────────────────────────────┘
               ▼
┌─── STEP 5: ENTRY TRIGGER ─────────────────────────────────────────────┐
│  Candlestick pattern at zone (one of 6):                               │
│    Hammer / Bullish Engulfing (demand)                                 │
│    Shooting Star / Hanging Man / Bearish Engulfing (supply)            │
│    Head & Shoulders / Inverse H&S                                      │
│  Pattern requires at_swing_low/high (trend-context guard).             │
│  No pattern → only allow if current candle is INSIDE the zone.         │
│  Otherwise WAIT (rule #4: never anticipate).                           │
└──────────────┬──────────────────────────────────────────────────────────┘
               ▼
┌─── STEP 6: TRADE MANAGEMENT ──────────────────────────────────────────┐
│  Entry options (E1-E4) — recommend best R:R that fills:                │
│    E1 proximal limit / E2 midpoint / E3a LTF zone / E3b stop-buy /     │
│    E3c throwback strap / E4 trendline break                            │
│  Stop:                                                                 │
│    Mode 1 (LTF/pattern): distal -33% Fib                               │
│    Mode 2 (HTF weekly income): distal-only, no -33% extension          │
│    Liquidity-aware override: above ATH if shorting near ATH (Phase 6)  │
│  Targets: T1=1R, T2=2R, T3=3R + price-action zones (Phase 6)           │
│  Position size:                                                        │
│    risk_amount = 1% × $100k = $1,000 (standard)                        │
│    risk_amount = 0.5% = $500 (counter-trend / anticipatory)            │
│    equity basket: 3% total across NQ/ES/YM aligned                     │
│  R:R minimum 1:2; if entry yields <1:2 → slide entry toward midpoint   │
│    (capped at E2)                                                      │
└──────────────┬──────────────────────────────────────────────────────────┘
               ▼
┌─── STEP 7: ROADMAP + CALENDAR FILTERS ────────────────────────────────┐
│  Monthly roadmap match (presidential + sannial)                        │
│  US Federal holiday: 2-session gate                                    │
│  Thanksgiving/Christmas: COT freshness suppressed                      │
│  CPI/NFP/FOMC same day: reduce size to 0.5% or wait                    │
│  Counter-roadmap: warning, not auto-rejected                           │
└──────────────┬──────────────────────────────────────────────────────────┘
               ▼
┌─── PROP-FIRM GUARDRAIL (LAST GATE) ───────────────────────────────────┐
│  PaperTrader.submit_signal() final checks:                             │
│    today's loss + this trade's risk > $5,000     → REJECT              │
│    total loss already ≥ $10,000 (account_blown)  → REJECT              │
│    open positions ≥ 3                            → REJECT              │
│    breach detected                               → REJECT              │
│  All pass → open paper trade with computed entry/stop/targets          │
└──────────────┬──────────────────────────────────────────────────────────┘
               ▼
       ┌──────────────────────┐
       │  SIGNAL FIRES        │
       │  → Discord (with @ping)
       │  → scan_results.json │
       │  → dashboard         │
       └──────────────────────┘
```

### After a signal fires (every subsequent scan tick)

```
PaperTrader.update_positions() runs:

  For each open position:
    if hit half-T1 (default) or T1: move stop to BREAKEVEN
    if hit T2 (2R):                 close 50%, begin trailing
    if hit T3 (3R):                 close remainder (with-trend)
                                     full close (counter-trend HARD CEILING)
    if stop hit:                    close at stop
    apply zone-based trailing where possible; fallback 1R-step
    daily reset rolls today_starting_equity at 22:00 UTC
```

### Rule-by-rule verification table

| Rule from Bernd's videos | Code location | Status |
|--------------------------|---------------|--------|
| Indecisive base (body ≤ 50%) | `BP_zone_detector._is_indecisive` | ✅ |
| Explosive leg-out (body ≥ 70%) OR gap | `_find_leg_out` (Phase 6 gap) | ✅ |
| 4 formations (DBR, RBR, RBD, DBD) + flip = 12 | `_score_zone` originality | ✅ |
| Proximal at body extremes / distal at wick extremes | `_score_zone` | ✅ |
| 6 qualifiers + LOL composite weighted | `_score_zone` qualifier_weights | ✅ |
| Q1 hard-fail if leg-out indecisive | `_find_leg_out` returns None | ✅ |
| Q3 25% penetration HARD invalidates | `_is_zone_invalidated_25pct` | ✅ Phase 6 |
| BB/SB containment NOT stacking | `has_big_brother_coverage` | ✅ Phase 6 |
| Speed-bump detection | `detect_speed_bumps` | ✅ |
| ZigZag % trend (R→L pivots) | `_zigzag_pivots` | ✅ |
| Pivot-break flips trend | `detect_trend_reversal` | ✅ Phase 6 |
| Location Fib 33/66 across HTF zones | `_analyze_htf` | ✅ |
| COT 26w / 52w by asset class | `COT_LOOKBACK_BY_CLASS` | ✅ |
| 156w extreme overlay | `COTIndex.extreme_lookback` | ✅ |
| Retailers contrarian for PMs | `get_bias` asset-class branch | ✅ |
| Forex DXY opposing-currency cross-check | `_analyze_fundamentals` | ✅ |
| Valuation refs per asset class | `VALUATION_REFS` map | ✅ Phase 4+5 P1 corrected |
| Valuation as HARD prerequisite gate | `valuation_passes_gate` | ✅ Phase 4+5 |
| Dual-ROC for equities | `cycle_per_symbol` config | ✅ |
| Seasonality 5y/10y/15y must agree | `Seasonality.calculate_multi` | ✅ |
| Slope must actively TURN | `seasonality_bias` w/ prior_slopes | ✅ |
| 3/5 votes (Location/Trend/COT/Val/Seas) | `_bias_consensus` | ✅ |
| Counter-trend/roadmap needs 4/5 | bias_consensus override | ✅ |
| -33% Fib stop (LTF) / distal-only (HTF weekly) | two-mode in `build_entry_options` | ✅ |
| Half-target breakeven | `breakeven_at_half_target` | ✅ |
| 2R partial 50%, 3R close-or-trail | `update_positions` | ✅ |
| Counter-trend hard close at T2 | direction-aware exit | ✅ Phase 4+5 |
| Equity basket 3% aggregate | basket-mode sizing | ✅ |
| Bond rollover + retailer extreme for equity shorts | `_equity_index_short_cross_asset_gate` | ✅ Phase 6 |
| Set-and-forget (no stop touch <1R) | `update_positions` early-tighten guard | ✅ |
| Holiday two-session gate | `BP_calendar.py` | ✅ |
| Mega-cap basket scan for NQ bias | spec'd, ready to wire | 🟡 |
| Stock dual-TF Valuation gate | spec'd, ready to wire | 🟡 |
| Liquidity-aware stop above ATH | helper documented, not auto-applied | 🟡 |
| Multi-bar pattern repetition | helper documented, not auto-applied | 🟡 |
| Bullish-Seasonality blocks Val-overvalued shorts | spec'd, not yet wired | 🟡 |
| Wait-for-N-COT-updates (defer pre-extreme) | spec'd, not yet wired | 🟡 |
| Commercial regime-flip detector | spec'd, not yet wired | 🟡 |

### What's specifically NOT enforced (P3 deferred — manual judgment)

These are visual/qualitative rules from the videos where Bernd doesn't quantify a deterministic threshold:

- Wick-over-wick big-brother substitute (no quantified threshold)
- Per-metal ranking (Pt > Au ≈ Ag > Pd) — visual ordering only
- Gold net-long zero-line crossing — visual rule, no number
- Retail contrarian threshold for non-PM classes — qualitative
- Volume confirmation for energy zones — "no volume = not institutional" but no threshold
- Adjusted vs unadjusted chart preference — directional, no rule
- Trap-area / institutional trap zones at HTF highs — qualitative
- Position-size splitting across E1+E2+E3 — visual demo, no exact ratio

These remain manual chart-reading decisions on top of the automated signal.

### Audit traceability

Every audit-derived rule has a `Phase 4+5` or `Phase 6` marker in the code/spec citing the corpus chapter where Bernd states it. Run this to find them:

```bash
grep -rn "Phase 4+5\|Phase 6" methodology/ scanner/
```

Full audit reports live in `audit/`:
- `PHASE_4_5_FINAL_REPORT.md` — 156-PDF audit (HAI + OTC + FT 2023)
- `PHASE_6_FINDINGS.md` — 21-chapter audit (2024 Practical Application + Beginner Breakout + Monthly Roadmaps)
- `GAPS_MASTER_LOG.md` — all P1/P2/P3 items with priorities

---

## Methodology source of truth

All trading logic comes from the Bernd Skorupinski Blueprint methodology
audited across 177 lessons (156 PDFs in Phase 4+5 + 21 chapters in Phase 6).
The methodology spec lives in the parent project's `methodology/` and
`SKILL.md`. The scanner here is the executable interpretation of that spec.

## Repo visibility

- **Public repo**: scan results + simulated trade history are publicly viewable.
  Free unlimited Actions minutes. Recommended for an experiment.
- **Private repo**: results stay private. 2,000 Actions minutes / month free —
  77-symbol scan ≈ 5 min, so ~400 hourly runs / month → about 17 days
  before you exhaust free minutes. Hourly during market hours only is
  more realistic.
