# Blueprint Trading System — Gaps Master Log
**Audit date**: 2026-04-29 | **PDFs audited**: 156/156 ✅ COMPLETE | **Sessions**: 6

---

## PRIORITY 1 — CLAUDE.md corrections / high-confidence additions

| Gap | Source | Action needed |
|-----|---------|---------------|
| Soft commodities (Cotton, grains) use NonCommercials 26w COT — NOT Commercials 52w | CW02 | Update `COT_LOOKBACK_BY_CLASS`; add soft-commodity subgroup |
| ZigZag % = 15 for @NG weekly (default is 3.0 daily) | FT Signals 22.02.2024 | Add `zigzag_percent_by_symbol: {NG=F: {weekly: 15.0}}` to BP_config |
| Refinement ladder includes 720-min and 960-min (between daily and weekly) | CW12, CW01 | Extend `refine_zone()` ladder; also add 40m between 60m and 30m for equity index symbols (CW05) |
| Dual-ROC check for equities: ROC=13 + ROC=10 (daily) / ROC=13 + ROC=30 (weekly) — both must agree | CW12, CW11, CW39 | Add `equity_roc_by_timeframe: {daily: [13, 10], weekly: [13, 30]}` to BP_config; dual-ROC agreement check to `BP_indicators.py` |
| Seasonality: slope must actively TURN positive — not just be bullish | CW10 | Add `slope_phase` field to `get_bias_multi()` |
| ~~Bitcoin: Seasonality is primary fundamental gate (no COT)~~ CONTRADICTED — Bitcoin uses BOTH COT and Seasonality; four-line COT panel (same structure as other assets) confirmed visually | CW19 (original), CW25 (contradicts), CW42-Idx (contradicts) | Remove crypto-seasonality-only exception; add `crypto` asset class to `_indicators_for_class()` using non-commercial COT + seasonality (26w lookback, no opposing-currency cross-check) |
| RTH-only zone drawing for intraday equity index zones | CW02 | Add `rth_only: true` option to zone detector |
| Platinum Valuation = DXY + Gold only (no Bonds) — contradicts blanket Commodities rule | CW41 | Update `07_asset_class_cheatsheet.md` + per-symbol overrides |
| Silver Valuation bonds reference is `@VD` (same as Gold), NOT `@US` — corrects CW40 per-PDF finding | CW43-PMs | Update `valuation.references_per_symbol` in BP_config: `SI=F → ["@VD","@GC","@DXY"]`; update `07_asset_class_cheatsheet.md` |
| @NG Seasonality uses 10y+5y only (not standard 5/10/15y) | CW02 | Add per-symbol seasonality lookback config |
| Equity/index Valuation INCLUDES DXY (@$XY) — contradicts documented "Stocks: NO Dollar" rule; `CampusValuationTool_V2` on AAPL, YMN, and NQ all show three references: @BUS/@US (bonds) + @GC (Gold) + @$XY (DXY). Multi-session visual confirmation. | CW42-Idx GAP-2, CW43-Idx GAP-8, CW51 GAP-1 | Update `VALUATION_REFS` for `stocks` and `equity_indices` to include DXY; individual equities use `[ZB, GC, DXY]`; index futures may differ from individual stocks — add `refs_per_symbol` override dict |
| HTF weekly-zone stop = DISTAL LINE only (no -33% extension) — deliberate exception to Rule #8; Bernd uses distal as stop on weekly demand/supply zones to achieve 4:1 R:R at 3% risk. The -33% extension applies to LTF/intraday refinement entries only | CW43-Idx GAP-5 | Add `stop_method: distal_only \| fib_minus33` to entry options; default `fib_minus33` for daily/4H; default `distal_only` for weekly zone entries. Document in `05_trade_management.md` as HTF exception to Rule #8 |
| Valuation as hard personal veto on directional trades: shorts require Valuation overvalued (≥+75); longs require Valuation undervalued (≤-75); this is stricter than the 3/5 minimum consensus rule | CW39, CW38 | Add `valuation_hard_gate: true` option to `BP_rules_engine.py`; document in `06_seven_step_process.md` as directional prerequisite (CW38 corroborates: "rule number one, valuation" stated twice) |

---

## PRIORITY 2 — Operational rules not yet in CLAUDE.md

### Zone detection & entry

| Gap | Source | Action needed |
|-----|---------|---------------|
| "Nest Egg" law: pristine far-below-market HTF demand zone gates all intermediate zones | CW01, CW19 | Add `detect_nest_egg_zones()` to `BP_zone_detector.py` |
| Nest egg zones escalate to "must play" mandatory status on return visit — non-optional when price revisits after original skip | CW07 | Add `is_nest_egg_mandatory: true` flag when zone has not been tested since formation AND price has moved away and returned |
| Inter-index nest egg ranking: when nest egg exists on @NQ but not @YM/@ES, deprioritise non-nest-egg index entries within `{NQ/ES/YM}` correlated group | CW05 | Add `deprioritised_by_nest_egg: true` to signals for lower-ranked correlated-group entries; rank by Q3 freshness tier within group |
| "Trap area" = 3+ stacked same-direction zones trapping counter-trend traders; distinct from LOL stacking (same direction, not mixed) | CW07 | Add `trap_area_count` field to zone signals; flag when 3+ same-direction zones stack above supply or below demand |
| Trendline-break entry (E4): stop-buy above descending trendline breakout, used for stock reversals at demand zones | CW13 | Document E4 in `04_entry_triggers.md`; add `trendline_break` entry type to `build_entry_options()` |
| E3 entry sub-type: "long above the hammer candle" = stop-buy at hammer HIGH + 1 tick (E3b), not entry at candle close (E3a) | CW13 | Add `entry_sub_type: close\|above_high` to E3; default E3b for daily/4H |
| "Throwback Strap" entry sub-type: price must first impulse away from zone (≥0.5× zone height), form a mini-base, then return to proximal — distinct from simple E3 pattern at zone arrival | CW05 | Model as E3c in `build_entry_options()`; gate: first_impulse detected + mini-base formed + second touch within zone |
| "Blind buy" anticipatory entry three-condition trigger: COT at historic extreme + Valuation approaching threshold (within ~15 pts) + zone fully fresh | CW43-Idx | Document conditions for `trade_context: 'anticipatory'` in `BP_rules_engine.py`; currently the field exists but qualifying conditions are undocumented |
| Valuation near-zero three-state reading: "around the mean" is an explicit state ("some space to upside/downside"), not just neutral | CW43-Idx | Add `valuation_state: strong_bullish \| mild_bullish \| neutral \| mild_bearish \| strong_bearish` to Valuation output using thresholds: ≤-75=strong_bullish, -75 to 0=mild_bullish, 0 to +75=mild_bearish, ≥+75=strong_bearish |
| Valuation "below the mean" (0 line) as intermediate mild-bullish qualifier — four-state model, not binary ±75 threshold; "below the mean" = long setups still acceptable at reduced weight | CW16 | Same as above — implement four-state model in `get_valuation_strength()` |
| Re-entry on same fundamental setup via refined LTF zone after stop-out — intact thesis + stop-out → find next refined zone → re-enter with stop below all zone levels | CW43-PMs | Add `build_reentry_signal()` to `BP_rules_engine.py` |
| "Novice trap": H&S / double-top forming inside zone → boost composite score | CW45 | Add `novice_trap_pattern` bonus to zone composite |
| H&S as chart-level directional confirmation signal (not just entry trigger) — Bernd circles H&S on NVDA daily as independent bearish bias, not tied to zone entry | CW43-Idx | Add `hs_directional_bias` flag to signal output; currently `BP_patterns.py` H&S detection only triggers entries |

### COT rules

| Gap | Source | Action needed |
|-----|---------|---------------|
| "Dot D" check: final 4-panel simultaneous daily view of all indices before trade week | CW03 | Add step to seven-step process |
| @RTY as leading indicator: if RTY bounces first → higher conviction on all index longs | CW03 | Add `rtty_relative_strength` to index signal output |
| COT zero-line crossing gate applies to ALL precious metals (not just Gold) | CW41 | Update PMs section in `03_fundamentals.md` |
| Gold trade-duration qualifier: normal COT = tactical; 156w extreme = structural | CW37 | Add `position_type: tactical\|structural` to Gold signals |
| Small-specs COT excluded for non-USD currency crosses | CW36 | Add currency-pair-aware COT class filtering |
| "Retail top" relative-peak COT pattern for Forex — retailers at 52w or multi-year COT high AND price at yearly high = higher-conviction bearish than absolute ≥80 threshold alone | CW52 | Add `is_historical_extreme(threshold=0.95)` to `COTIndex`; emit `retail_top: true` flag on Forex signals |
| Retailers net-short = directional-alignment veto for intended short even at non-extreme readings; contrarian rule extends beyond PMs to any asset where retail direction matches planned trade direction | CW38 | Add `cot_directional_alignment_warning` flag to `BP_rules_engine`; extend `retailer_contrarian_signal()` to emit direction flag beyond 20/80 extremes; hard veto for PMs, soft warning for other asset classes |
| "Short term CUT" flag — first entry into a fresh 26w COT extreme (price just crossed threshold) is higher conviction than a sustained extreme; needs `cot_short_term_first_extreme: true` flag | CW07 | Compare current COT index vs prior-week value; flag when index crossed the 80/20 threshold within last 1-2 weeks |
| COT RAW indicator displays two values: current net absolute position + period-over-period change (not just the net position) | CW43-Idx | Add `net_change` field to `COTReport` class output; `net_change = current_net - prior_week_net` |
| COT accuracy is instrument-specific — Dow more reliable than S&P/NASDAQ for futures COT analysis | Feb-Roadmap | Add `cot_reliability_tier: high\|medium\|low` per symbol to `BP_config.yaml`; surface in signal output |
| COT weighting hierarchy for agricultural commodities: COT > Seasonality > Valuation (Valuation least important for ags) | CW10-2024 | Add `fundamentals_priority_order` per asset class to `BP_config.yaml`; use to weight bias consensus for ag commodities |
| Coffee COT — Retailers category unreliable due to sub-threshold commercial participants (CFTC threshold exclusion creates noise) | CW10-2024 | Add `cot_category_override: commercials_only` for Coffee (`KC=F`) in BP_config; suppress small-spec readings for KC |
| Gold+Silver combined COT ticker shown in CW51 — Bernd analyzes PM COT as a group (combined Gold+Silver net position) not just individually | CW51 | Add combined-PM COT composite signal to `BP_indicators.py`; expose `pm_group_cot_bias` on Gold/Silver signals |
| Commercials going "super bearish" in early February = leading setup signal for March (4-6 week commercial flip lag) | Feb-Roadmap | Document commercial flip lag in `03_fundamentals.md`; add `cot_commercial_flip_lag_weeks: 4` to BP_config |
| Retail COT intra-week "big spikes" at weekly extremes = timing signal, not sustained position | Mar-Roadmap | Add `cot_weekly_spike_warning` boolean to signal; flag when retail COT moved >15 pts in current week vs prior |
| Holiday-week COT data delay gate — COT arrives Dec 30 during Christmas week; treat as conditional entry gate, not stale data to trade on | CW52 | Add `COTFetcher.is_data_fresh(max_age_days=10)`; add `cot_freshness: fresh\|stale\|pending` to signal; add CFTC holiday delay schedule to `BP_calendar.py` |
| Thanksgiving week as explicit low-liquidity / no-COT week: scan suppression; similar gate as Christmas week | CW48 | Add Thanksgiving to CFTC holiday delay schedule in `BP_calendar.py`; apply same `cot_freshness` gate |

### Valuation rules

| Gap | Source | Action needed |
|-----|---------|---------------|
| Valuation extreme beyond ±100 = conviction amplifier ("I've never seen this") — add `valuation_strength='extreme'` tier above standard 'strong' | CW43-PMs | Add `get_valuation_strength()` to `BP_indicators.py`; add `valuation_strength` field to signal output |
| Valuation zero-line crossing = intermediate early warning (not just ±75 threshold) | CW09 | Add `valuation_zero_crossing` field to signal output |
| Valuation monitoring cadence — "once per week + per day in the morning": weekly check sets bias; daily morning check is a go/no-go gate before entry execution | CW42-Idx | Add `ValuationMonitor` class with `check_daily_morning()` and `check_weekly_outlook()` methods; daily morning Valuation recheck prevents stale-bias entries |
| Index-level Valuation gates individual stock entries — when parent indices are at/above ±75 Valuation threshold, individual stock demand entries are held off even if stock's own Valuation is neutral | CW25 | Add `index_valuation_gate_stocks(parent_indices=['NQ', 'ES'])` check to `BP_rules_engine.py` |
| AAPL + MSFT as "gate stocks" for entire stock universe scan — if both are overvalued, terminate stock scan early; both must clear before scanning other equities | CW42-Idx | Add `STOCK_GATE_SYMBOLS = ['AAPL', 'MSFT']` to config; add early-exit logic to stock scan loop |
| Individual stock Valuation "long term vs short term" dual-gate: LT (weekly Valuation) must agree with ST (daily Valuation) before entry; single-timeframe Valuation agreement insufficient | Jan-Roadmap | Add `valuation_timeframe_agreement: {weekly: bias, daily: bias}` to stock signals; require both to agree |

### Seasonality & roadmap

| Gap | Source | Action needed |
|-----|---------|---------------|
| Seasonality: slope must actively TURN positive — not just be bullish | CW10 | Add `slope_phase` field to `get_bias_multi()` |
| Per-asset preferred seasonality lookback: Gold prefers 15y; 10y = disagreement check | CW37 | Add `preferred_seasonality_lookback` per asset to BP_config |
| Calendar-level gate: wait for seasonal monthly low before entering demand zone | CW19 | Add `seasonal_monthly_low_gate` boolean on signals |
| December calendar events: Santa Claus Rally (Dec 22–2nd Jan, +1.3% avg); week after Triple Witching bullish 31/41y; NASDAQ bearish last trading day 17/23y | CW49 Monthly | Add static dict to `BP_roadmap.py` |
| Per-index pre-election December ranks: NASDAQ #2 avg +4.2%, DJIA #3 avg +2.7% | CW49 Monthly | Add to `BP_roadmap.py` per-index seasonal rank tables |
| Presidential / pre-election cycle applied to Platinum (and precious metals broadly) — Year 3 pre-election cycle predicts October seasonal low for PMs | CW39 | Add PMs to presidential cycle scope in `build_monthly_roadmap()`; document Year 3 Q4 = PMs October dip → Q4 rally |
| October seasonal low window — intra-month timing: seasonal bottom forms in trading days 9-14 of October (calendar ~Oct 10-19); high-conviction buy qualifier when Valuation is also undervalued during this window | CW42-Idx | Add `OCTOBER_SEASONAL_LOW_WINDOW = {'start_trading_day': 9, 'end_trading_day': 14}` to `BP_roadmap.py`; emit `seasonal_monthly_low_gate` with extra strength when price is in window |
| February intra-month timing: "after the 12th trading day" inflection point; pre-election year February shows a distinct directional turn after trading day 12 | Feb-Roadmap | Add `FEBRUARY_INFLECTION_TRADING_DAY = 12` to `BP_roadmap.py` per-month timing rules |
| President's Day as intra-month timing anchor for February — market behaviour changes around President's Day; treat as a week-of-holiday caution window | Feb-Roadmap | Add President's Day to `BP_calendar.py` and `BP_roadmap.py` timing logic |
| March election-year intra-month timing: peak momentum on trading days 3-4; thereafter corrective into month end | Mar-Roadmap | Add `MARCH_ELECTION_YEAR_PEAK_DAY = {'start': 3, 'end': 4}` to `BP_roadmap.py` |
| Election year NQ outperforms Dow/S&P — per-index divergence in Year 0 January; not just directional bias but relative ranking | Jan-Roadmap | Add per-index divergence tracking to `build_monthly_roadmap()` for Year 0 |
| Sector-level seasonality inheritance (BABA inherits AMZN seasonality) | CW23 | Add `get_seasonality_by_sector_proxy()` |
| Intraweek arc: Mon momentum → Thu exhaustion at supply → Fri pullback | CW17 | Add `intraweek_phase` field; medium confidence |
| Gold seasonal timing — seasonal low bottoms in early March; rally phase into mid-April | CW10-2024 | Add to Gold static seasonal annotations in `BP_roadmap.py` |

### Trade management & position sizing

| Gap | Source | Action needed |
|-----|---------|---------------|
| Zone-based targets preferred over R-multiples (R-multiples = fallback only) | CW41 | Add `build_zone_targets()` to `BP_rules_engine.py` |
| 80% profit margin target heuristic (not 100% to distal of opposing zone) | CW36, CW42-PMs | Update zone-based target calculation; add `profit_target.zone_to_zone_pct: 0.80` to BP_config |
| Year-end PM risk-split rule: Oct–Dec seasonal window → split 1% risk across ≤3 PM positions (~0.33% each) instead of concentrating (exception to Rule #12) | CW43-PMs | Add `year_end_pm_window` config block to `BP_config.yaml`; add mode flag in `BP_rules_engine.py` |
| Equity basket total risk budget = 3% split across correlated indices + stocks — when equities strongly align, activate `equity_basket_mode`; risk per trade = 0.03 × balance / n_trades (not 0.01 each) | CW44 | Add `equity_basket_mode` flag to `BP_rules_engine`; compute split risk when flag active |
| Unadjusted continuous futures roll-gap as additional price target | CW37 | Add `roll_gap_targets` to futures signal output |
| Stop at structural pivot for extreme commodity zones (override -33% Fib at decade-lows) | CW04 | Document as exception to Rule #8 in `05_trade_management.md` |
| Counter-trend trade target ceiling: maximum 1:2 or 1:1 R:R — "don't try to hold it to the moon" | LIVE May | Add `max_rr_counter_trend: 2.0` to BP_config; enforce hard exit at T2 for counter-trend `trade_context` |
| Safety-first deeper demand preference: when Valuation is elevated (above zero but not yet ±75), prefer the deeper/lower demand zone over the nearest proximal zone | LIVE May | Add `prefer_deeper_demand_when_elevated_valuation: true` option to zone selection logic |
| Palladium extraordinary COT extreme → position size reduction (not avoidance) | CW49 Ag | Add to PM-specific trade management rules |
| Explicit prohibition on stop movement before reaching target — stronger than set-and-forget; stop must NOT be adjusted before T1 is hit | CW07 | Document in `05_trade_management.md` as a hard rule; add enforcement comment to `BP_paper_trader.py` |
| CPI / high-impact calendar event → reduced_risk_pct trigger (same as counter-trend/anticipatory positions) | CW07 | Add economic-calendar awareness to `BP_calendar.py`; trigger `reduced_risk_pct: 0.5` on signal when entry is within 24h of CPI/NFP/FOMC |
| Two-mode stop placement: standard -33% Fib vs "laid-back" wider buffer for weekly income traders who prefer distance over precision | CW07 | Add `stop_mode: standard \| laid_back` to BP_config; `laid_back` = distal - 0.5× zone height (wider buffer) |
| Prop firm challenge/eval account: weekly timeframe NOT recommended — use daily/4H; weekly holding times exceed typical challenge drawdown windows | CW10-2024 | Document in `07_asset_class_cheatsheet.md` under risk management; add `account_type: challenge` config option that enforces daily/4H strategy tier |
| "Nine pros, one con" extended factor tally — Bernd counts ALL sub-factors across all 5 pillars as individual votes; highest-conviction tier requires ≥8-9 pros and ≤1 con | CW44 | Add `pros_cons_tally` dict to signal output extending `bias_count`; document "picture perfect" quality tier |

### Cross-asset & multi-instrument rules

| Gap | Source | Action needed |
|-----|---------|---------------|
| Index correlation groups: {NQ/ES/YM} = 1 group; {RTY} = separate | CW12 | Add `CORRELATED_GROUPS` to `BP_rules_engine.py` |
| Cross-index relative Valuation for index selection (most undervalued wins) | CW04 | Add `select_by_relative_valuation()` for equity signals |
| Parent-index sequential prerequisite for individual stock entries — NQ must confirm before Apple/tech stocks; index drives stock, not vice versa | CW52 | Add `parent_index_check(symbol)` to `BP_rules_engine.py`; mapping: tech stocks → NQ, broad market → ES |
| NASDAQ gap-fill prerequisite before tech stock demand zone entries | CW06, CW04 | Add `nasdaq_gap_fill_required` check for equity stock signals |
| NASDAQ gap-fill prerequisite extends to @YM and @ES — when NQ has an open gap, hold off YM and ES entries until NQ gap resolves; sequential entry order within correlated group | CW44 | Extend `gap_fill_prerequisite` flag to YM and ES signals when NQ has open gap |
| NQ-specific weekly gaps: NASDAQ has prominent weekly gap structure used as targets/magnets; Dow (YM) explicitly does NOT have the same weekly gap structure | CW16 | Add per-instrument `gap_fill_applicable` flag to config: `True` for NQ, `False` for YM |
| AAPL as sector proxy for NQ zone corroboration | CW09 | Add cross-asset zone corroboration logic |
| "Months to weekly starts" temporal handoff: LTF zone must form AFTER price enters HTF zone | CW12 | Add timestamp check to `has_big_brother_coverage()` |
| Weekly "mini-gap" above price = directional continuation confirmation | CW09 | Add weekly gap detection to `BP_indicators.py` |
| Daily mini-gap cluster (3+) running into supply = elevated bearish conviction | CW17 | Add `daily_gap_cluster_at_supply` boolean flag |
| Precious metals inter-asset directional correlation — Gold/Silver/Palladium move in tandem; agreement across 2 of 3 PMs boosts bias confidence | CW07 | Add `pm_group_alignment` composite signal; flag when ≥2 of {GC, SI, PA} share same fundamental direction |
| Gold asymmetric directional override: when both COT and Seasonality are bullish on Gold, refuse to short even if Valuation is overvalued | CW42-PMs | Add `bias_override.GC=F.refuse_short_when: [cot_bullish, seasonal_bullish]` to config; hard veto on Gold shorts when dual COT+Seasonal bullish |
| Treasury Bond (@US+) as cross-asset gate for equity shorts — Bernd opens bond analysis to confirm bond demand is being tested before proceeding to equity short setups | CW43-Idx | Add `bond_demand_gate` check to equity short signal generation; `ZB=F` demand zone confluence required |
| Bitcoin Valuation uses unique reference asset set (partial label: `$BUS`, `$DXY`, `$BDX`) — not equity or commodity defaults | CW13 | Add crypto row to `07_asset_class_cheatsheet.md`; add `crypto` class to `_indicators_for_class()`; mark TBD |

### Calendar & market structure

| Gap | Source | Action needed |
|-----|---------|---------------|
| Monday candle / Tuesday entry timing rule: after a bullish weekly candle closes, wait for Monday's daily candle to complete, then enter Tuesday with stop below Monday's low | CW42-PMs | Add `entry_timing.weekly_income.wait_for_monday_candle: true` config flag; add Tuesday-entry gate to `BP_rules_engine` |
| US federal holiday entry gate: on the Friday before and Monday of a US market holiday, Bernd is "not necessarily willing" to enter new positions — soft two-session block | CW25 | Add NYSE holiday calendar to `BP_calendar.py`; add `holiday_warning: true` on signals falling within the two-session holiday window |
| First week of a new month statistically strong for equity indices — general intra-month calendar pattern | CW18 | Add `FIRST_WEEK_MONTH_BULLISH_EQUITIES = True` note to `BP_roadmap.py` month-start bias |
| "Weekly trap area" as additional conviction signal for demand zone bounces: false breakdown of weekly lows before demand zone bounce confirms institutional absorption | LIVE May | Add `weekly_trap_area` boolean to signals when price briefly violated prior weekly low before recovering to demand zone |
| Adjusted vs unadjusted futures chart discrepancy as zone-drawing rule: use unadjusted level as the canonical zone anchor; adjusted level as visual reference only | CW48, Mar-Roadmap | Add `zone_draw_chart: adjusted \| unadjusted` to `BP_config.yaml`; document in `01_zone_detection.md` that zones should be drawn on unadjusted continuous contract |
| "Only short when REALLY overvalued" explicit index short wait rule — even at ±75, Bernd will wait for a "really" strong overvaluation reading before entering index shorts | CW18 | Add `short_requires_extreme_valuation: true` flag for equity index signals; require `valuation_strength: 'strong'` (not just `'bullish'`) before generating short signals on equity indices |
| Q1-end portfolio rebalancing as contextual risk in late March — institutional rebalancing creates atypical volatility; reduces conviction for new entries in final trading days of March | Mar-Roadmap | Add `Q1_REBALANCING_CAUTION_WINDOW = {'month': 3, 'final_trading_days': 3}` to `BP_calendar.py` |

### Asset-class specific

| Gap | Source | Action needed |
|-----|---------|---------------|
| @NG double-bottom entry filter: wait for secondary test before entering spike-down zones | CW03 | Add to `07_asset_class_cheatsheet.md` Energies section |
| @NG isolated counter-candle suppression: for @NG in extended directional runs (5+ weekly candles same direction), a single opposite-direction candle is statistical noise — suppress trend-change signals | CW05 | Add `ng_min_counter_candles: 2` to BP_config @NG block; require 2 consecutive counter-direction candles before acknowledging trend change on @NG weekly |
| @NG statistical caveat — "statistically it cannot be read every single week" — one green week in multi-week red run is expected | CW05 | Same as above |
| Palladium February seasonal timing: expect bounce in February | CW04 | Add to `07_asset_class_cheatsheet.md` PMs section |
| Year-end PM risk-split rule: Oct–Dec seasonal window → split 1% risk across ≤3 PM positions | CW43-PMs | (See Trade Management section above) |
| Platinum Valuation uses DXY + Gold only (no Bonds) | CW41 | (See P1 section above) |
| Platinum preferred over Gold/Silver for PM entry when COT blocks Gold+Silver — if Gold and Silver COT are both against direction, Platinum becomes the preferred PM entry vehicle | CW51 | Add `pm_fallback_ranking: [PA, PT, SI, GC]` logic when primary PM COT blocked; expose `preferred_pm_entry` on PM group signals |
| Cotton (@CT) daily Valuation gate required — Cotton daily chart must show undervaluation gate before entry (in addition to weekly COT) | CW51 | Add per-symbol Valuation timeframe requirements; `CT=F` requires daily Valuation confirmation |
| Corn (ZC) and Cotton (CT) reviewed as an agricultural pair — inter-ag correlation used for conviction | CW51 | Add `AGRICULTURAL_PAIRS = {('ZC=F', 'CT=F'): 'grain_soft_pair'}` to `BP_rules_engine.py` |
| Crude Oil Valuation: Crude seasonality often shows a flat/unclear pattern ("fruit oil" comment) — flat seasonality on Crude = no-edge signal; skip if seasonality is inconclusive | CW51 | Add `seasonal_no_edge_threshold: flat_slope_pct: 0.1` for CL=F; emit `no_edge: true` on signal when Crude seasonality slope is below threshold |
| @RTY COT uses IWM-linked data plus Large Speculators (hedge funds) divergence from commercials as the primary signal | CW48 | Update `BP_config.yaml` RTY asset_class settings; use large-spec COT for RTY signals; add `rtty_cot_source: IWM_linked` note |
| Gold seasonal timing — seasonal low bottoms in early March; rally phase into mid-April expected | CW10-2024 | Add to Gold static seasonal annotations in `BP_roadmap.py` |
| Swiss Market Index (SMI) tracked as a European index alongside US indices — Bernd monitors SMI as a European macro proxy | CW18 | Add SMI to monitoring universe documentation in `07_asset_class_cheatsheet.md` |

---

## PRIORITY 3 — Deferred (corpus too sparse / visual-only / unquantified)

| Gap | Source | Reason deferred |
|-----|---------|-----------------|
| Campus Algo Forecast indicator (params 15/100/False/False/False) | CW36, CW01 | Proprietary; insufficient corpus to document parameters |
| Multi-week directional-run exhaustion heuristic | CW23 | Not quantified |
| Palladium 100-week COT lookback | CW45 | Single occurrence, low confidence |
| Bi-weekly (2W) chart in commodity MTF stack | CW04 | OCR ambiguity, not confirmed |
| roadmap_next_month_caution flag (last strongly-bullish month → caution on new longs) | CW14 | Single occurrence |
| Per-metal ranking: Platinum > Gold ≈ Silver > Palladium | Multiple | Visual-only; partially corroborated by CW51 Platinum fallback gap but still not quantified |
| Valuation single-reference isolation technique (turning off all but one reference to backtest independently or compare cross-metal relative valuation) | CW42-PMs | Analytical workflow only; no automation needed |
| YMN crisis year exclusion from COT normalization (2007-2009, 2020 excluded from lookback range) | CW43-Idx | Complex outlier handling; single occurrence; visual confirmation only |
| NQ downside-distance labeling to next demand cluster as explicit risk quantification step | CW42-Idx | Informational output; not a blocking rule; `speed_bumps[]` partially covers this |
| Coffee COT raw net data visual backtest before index calculation | CW10-2024 | Analytical workflow step; not automatable without corpus rule |
| February per-index election-year seasonal rank table (specific % per index) | Feb-Roadmap | Visual-only; data partially covered by existing `PRESIDENTIAL_CYCLE_BIAS` tables |
| Q1-end rebalancing atypical volatility (contextual awareness) | Mar-Roadmap | Soft contextual note; not a hard gate; added to calendar gap above as low-weight flag |
| Retail short trap filter ("too obvious = suspect") for individual stock short setups | CW43-Idx | Qualitative/subjective; no quantification provided |

---

## KEY CONTRADICTIONS DISCOVERED

| Contradiction | Session A | Session B | Resolution |
|---------------|-----------|-----------|------------|
| Bitcoin COT usage | CW19: "no COT, seasonality primary gate" | CW25, CW42-Idx: four-line COT panel visually confirmed on Bitcoin charts | Bitcoin DOES use COT. CW19 interpretation was wrong. Updated in P1. |
| Equity Valuation references | CLAUDE.md: "Stocks = Interest Rates + Bonds, NO Dollar" | CW42-Idx, CW43-Idx, CW51: @$XY (DXY) visible as 3rd reference on AAPL, YMN, NQ Valuation panels | DXY appears to be included in equity Valuation. Multi-session visual confirmation. Updated in P1. |
| Stop calculation rule | CLAUDE.md Rule #8: "ALWAYS use -33% Fibonacci for stops" | CW43-Idx: weekly income entries use distal as stop (no -33% extension) to achieve 4:1 R:R | HTF weekly entries use distal-only stop; -33% applies to LTF/refined entries. Updated in P1. |
| Valuation vote weight | CLAUDE.md: Valuation = 1 of 5 pillar votes | CW38, CW39: "rule number one, valuation" stated twice; hard veto language | Valuation is a directional prerequisite, not just one vote. Updated in P1. |

---

## STATUS

| Category | Total | Done | Left |
|----------|-------|------|------|
| HAI | 52 | 52 ✓ | 0 |
| OTC | 27 | 27 ✓ | 0 |
| FT Signals | 29 | 29 ✓ | 0 |
| FT Weekly Outlook | 51+1dup | 51 ✓ | 0 |
| **TOTAL** | **156** | **156 ✓** | **0** |

**Audit complete 2026-04-29.** All 156 PDFs audited across 6 sessions.
