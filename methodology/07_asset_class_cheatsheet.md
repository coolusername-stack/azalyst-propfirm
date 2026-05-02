# Asset Class Settings — Quick Reference Cheatsheet

> Bernd Skorupinski Blueprint Trading System — File 7 of 7

---

This file provides the **EXACT settings** to use for each asset class. Different assets require different indicator configurations — using the wrong settings will produce incorrect analysis.

---

## FOREX

**Pairs**: EUR/USD, GBP/USD, USD/JPY, AUD/USD, USD/CAD, USD/CHF, NZD/USD

| Setting | Value |
|---------|-------|
| HTF | Weekly |
| LTF | Daily |
| COT Group | Non-Commercials (Large Speculators) |
| COT Method | DIVERGENCE — price vs COT index |
| COT Lookback | **26 weeks** (audit correction — Hybrid AI default is 26w; 52w was equities-specific, not forex-specific) |
| Valuation ROC | 10 |
| Valuation References | DXY (Dollar Index) only |
| Seasonality Lookbacks | 5yr, 10yr, 15yr |
| Cross-Check | ALWAYS check opposing currency COT |
| Inverted Pairs | 6J → USD/JPY, 6C → USD/CAD, 6S → USD/CHF (futures inverted vs spot) |
| Position Sizing | Standard: 1% risk |
| Typical Zone Height | 30-80 pips |

### Forex Notes

- Most liquid asset class with the tightest zones — **ideal for beginners**.
- COT method is **divergence-based**: look for price making new highs while COT positioning declines (or vice versa).
- Always check the **opposing currency's COT** as a cross-reference. For EUR/USD, check both 6E (Euro) and DX (Dollar Index) positioning.
- Inverted pairs require special attention: when COT shows 6J bullish (JPY strengthening), the SPOT USD/JPY goes **DOWN**.

---

## COMMODITIES — Precious Metals

**Instruments**: Gold (GC / XAU/USD), Silver (SI / XAG/USD), Platinum (PL)

### Gold (GC / XAU/USD)

| Setting | Value |
|---------|-------|
| HTF | Weekly |
| LTF | Daily |
| COT Group | Commercials (primary) + Retailers (contrarian confirmation) |
| COT Method | Trade WITH Commercials. Contrarian on Retailers. |
| COT Lookback | 52 weeks |
| Valuation ROC | 10 |
| Valuation References | DXY + Bonds (ZB) + Gold (GC) |
| Seasonality Lookbacks | 5yr, 10yr, 15yr |
| 156-week extreme | YES — strongest COT signal for commodities |
| Combined COT signal | Gold + Silver combined COT net-long as PM group signal |

**Gold Asymmetric Directional Override (CW42-PMs)**: When COT AND Seasonality are BOTH bullish for Gold, REFUSE short positions regardless of Valuation reading. Gold's safe-haven demand can overwhelm standard valuation signals during certain market conditions. Only short Gold when COT is bearish OR Seasonality is bearish — not just Valuation alone.

### Silver (SI / XAG/USD)

| Setting | Value |
|---------|-------|
| HTF | Weekly |
| LTF | Daily |
| COT Group | Commercials (primary) + Retailers (contrarian) |
| COT Method | Trade WITH Commercials. Contrarian on Retailers. |
| COT Lookback | 52 weeks |
| Valuation ROC | 10 |
| Valuation References | DXY + **@VD** (Bonds — use @VD ticker, NOT @US) + GC (Gold) |
| Seasonality Lookbacks | 5yr, 10yr, 15yr |

### Platinum (PL)

| Setting | Value |
|---------|-------|
| HTF | Weekly |
| LTF | Daily |
| COT Group | Commercials (primary) + Retailers (contrarian) |
| COT Method | Trade WITH Commercials. Contrarian on Retailers. |
| COT Lookback | 52 weeks |
| Valuation ROC | 10 |
| Valuation References | **DXY + Gold (GC) ONLY** — NO Bonds reference for Platinum |
| Seasonality Lookbacks | 5yr, 10yr, 15yr |

### Precious Metals Notes

- Wider zones and bigger moves compared to forex.
- Gold is the "safe haven" benchmark — correlates inversely with USD and positively with bonds during risk-off.
- **156-week COT extreme** is the strongest signal available for commodities. When Commercials reach 156-week extreme positioning, pay close attention.
- **Gold + Silver Combined COT**: Use the combined net-long position of both GC and SI as a PM-group signal. When both are at commercial extremes, conviction is highest.
- Trade **WITH** Commercials: when Commercials are heavily long, that is bullish. When Commercials are heavily short, that is bearish.
- Trade **AGAINST** Retailers: when Retailers are heavily long, that is bearish (contrarian signal). When Retailers are heavily short, that is bullish.
- **Retailer directional-alignment veto for PMs**: If Retailers are on the SAME SIDE as your proposed trade (even below extreme threshold), VETO the trade. Precious Metals has the strictest retailer-contrarian rule of all asset classes.

---

## COMMODITIES — Energy

**Instruments**: WTI Crude Oil (CL), Natural Gas (NG)

### WTI Crude Oil (CL)

| Setting | Value |
|---------|-------|
| HTF | Weekly |
| LTF | Daily |
| COT Group | Commercials |
| COT Method | Trade WITH Commercials |
| COT Lookback | 52 weeks |
| Valuation ROC | 10 |
| Valuation References | DXY + Bonds (ZB) + Gold (GC) |
| Seasonality Lookbacks | 5yr, 10yr, 15yr |

### Natural Gas (NG) — Special Settings

| Setting | Value |
|---------|-------|
| HTF | Weekly |
| LTF | Daily |
| COT Group | Commercials |
| COT Method | Trade WITH Commercials |
| COT Lookback | 52 weeks |
| Valuation ROC | 10 |
| Valuation References | DXY + Bonds (ZB) + Gold (GC) |
| **ZigZag % (Weekly)** | **15%** (override from default 3%) — NG is extremely volatile; standard ZigZag generates too many false pivots |
| **Seasonality Lookbacks** | **10yr + 5yr only** (NOT 15yr) — 15-year NG seasonality data is unreliable; both 10yr and 5yr must agree |
| **Counter-candle suppression** | Isolated single counter-direction candles within a trend are suppressed from influencing trend detection. NG whipsaws frequently with one-candle spikes — do not treat an isolated doji or reversal candle as a trend change unless confirmed by subsequent candles |

### Energy Notes

- **High volatility** — wider stops are needed compared to forex and precious metals.
- Natural Gas (NG) is **extremely volatile** and can produce very wide zones. Position size accordingly (may need to reduce to 0.5% risk).
- Energy prices are influenced by geopolitical events, OPEC decisions, and weather patterns — these are NOT part of the Blueprint system analysis, but be aware they can cause extreme moves.
- Same COT method as precious metals: trade WITH Commercials.
- Seasonality is particularly relevant for energy — heating/cooling seasons create reliable patterns.

## COMMODITIES — Soft Commodities (Agricultural)

**Instruments**: Cotton (CT), Corn (ZC), Soybeans (ZS), Wheat (ZW)

| Setting | Value |
|---------|-------|
| HTF | Weekly |
| LTF | Daily |
| **COT Group** | **Non-Commercials (Large Speculators)** — NOT Commercials |
| **COT Method** | **DIVERGENCE** — same as Forex, not "trade with" |
| **COT Lookback** | **26 weeks** — shorter cycle than hard commodities |
| **COT Weighting** | COT > Seasonality > Valuation (COT is dominant for ags) |
| Valuation ROC | 10 |
| Valuation References | DXY + Bonds (ZB) + Gold (GC) |
| Seasonality Lookbacks | 5yr, 10yr, 15yr |

### Soft Commodities Notes
- Agricultural markets are dominated by the crop calendar (planting/harvest). COT positioning reflects this cycle reliably.
- **COT hierarchy**: COT carries more weight than Seasonality or Valuation for soft commodities. A strong COT divergence can override a moderate seasonal headwind.
- Cotton daily Valuation: use standard commodity references (DXY + ZB + GC).
- Corn + Cotton: can form correlated pairs when USD is the dominant driver. Check for same-direction setups reinforcing each other.

---

## EQUITY INDICES

**Instruments**: S&P 500 (ES / SPX), Nasdaq 100 (NQ / NDX), Dow Jones (YM / DJI), Russell 2000 (RTY / RUT)

| Setting | Value |
|---------|-------|
| HTF | Weekly (or Daily for shorter-term setups) |
| LTF | Daily (or 4H for shorter-term setups) |
| Additional LTF | 720-min (12H) and 960-min (16H) also valid for equity indices |
| COT Group | Non-Commercials |
| COT Method | DIVERGENCE |
| COT Lookback | 26 weeks |
| Valuation ROC | **10** (Pine Script default `Length=10` per CampusValuationTool source). Dual-ROC is a CHART OVERLAY practice (run two indicator instances at different lengths simultaneously): daily overlay = ROC 10 + ROC 13; weekly overlay = ROC 13 + ROC 30. Both lines must agree direction or signal is neutral. |
| Valuation References | Interest Rates (ZN / ZB) + Bonds + **DXY** (Dollar Index — YES for equity indices) |
| Valuation Priority | **PRIMARY / LEADING indicator AND hard prerequisite gate** — "Rule number one: valuation" |
| Valuation Hard Gate | If Valuation STRONGLY opposes trade direction → VETO regardless of other factors |
| Seasonality Lookbacks | 5yr, 10yr, 15yr |
| Zone drawing | **RTH (Regular Trading Hours) only** for intraday equity index zones — pre/post-market wicks excluded |
| Preferred timeframes | Daily + 4H for standard setups |
| Prop firm challenge | Weekly TF **NOT recommended** — use Daily/4H to manage drawdown limits |

### Equity Index Notes

- **Valuation is the MOST important fundamental** for equities AND is a HARD PREREQUISITE gate. Bernd: "Rule number one — valuation" (CW38, CW39). If Valuation strongly contradicts the proposed direction, the trade is VETOED.
- **AUDIT CORRECTION**: Equity indices DO use DXY as a Valuation reference. CampusValuationTool_V2 confirmed showing @BUS (bonds) + @GC (Gold) + @$XY (DXY) for AAPL, YMN, and NQ across three separate sessions (CW42-Idx, CW43-Idx, CW51). Previous documentation stating "NO Dollar" was incorrect.
- COT lookback is shorter for equities: **26 weeks** instead of 52 weeks.
- Valuation indicator parameter `Length=10` (Pine Script default per CampusValuationTool source). "Dual-ROC" is a chart-overlay practice — run two separate indicator instances at different lengths and require both to agree direction (daily: 10+13; weekly: 13+30). It is NOT a single-instance parameter override. (Phase 7 audit correction — earlier docs claimed Length=13 for equities; that was a misreading. Empirically validated: AMZN/META/NVDA give wrong-vs-Bernd readings at Length=13; Length=10 matches.)
- **DOW COT reliability**: Dow Jones COT data is more reliable and less noisy than S&P 500 or Nasdaq COT data. When indices disagree on COT signal, Dow COT carries more weight.
- Shorter timeframe combinations (Daily HTF / 4H LTF) can be used for more frequent setups, but the weekly/daily combination remains the standard.
- Equity indices have a natural long-term upward bias — counter-trend (short) trades require MUCH stronger fundamental confirmation. Only short when "really overvalued" (CW18).
- **Treasury Bond Gate**: Before entering equity index SHORT setups, check that Treasury Bond (ZB/ZN) is at or approaching a supply zone. Bond demand zone active = risk-off signal = higher conviction equity short.
- **RTY Leading Indicator**: Russell 2000 (RTY) often leads large-cap indices (ES/NQ) by 1-2 sessions. Use RTY directional signals as early confirmation.
- **Prop firm challenge accounts**: Do NOT use weekly TF — daily loss limits and drawdown rules of prop firm challenges are incompatible with the wide stops required at weekly zones. Use Daily + 4H setups instead.

### Individual Stock Notes (within Equity section)
- **Parent index prerequisite**: Index must be at a valid zone AND fundamentally aligned BEFORE analysing individual constituent stocks. Index-level Valuation gates individual stock entries.
- **AAPL + MSFT dual-gate**: For Nasdaq/tech stocks, BOTH Apple and Microsoft must independently pass the full qualifier scan before other stocks are analysed. They are the two bellwether stocks — if neither is at a zone, the sector isn't ready.
- **Mega-cap basket scan (Phase 6, Ch 153)**: Extend the AAPL+MSFT dual-gate to the full top-7+ mega-caps (AAPL, MSFT, GOOG, META, AMZN, NFLX, TSLA, NVDA). For NQ direction calls, require ≥4/8 aligned with bias.
- **Trade-the-constituents fallback (Phase 6, Ch 153)**: When the index has no tradable zone but mega-caps are aligned and at zones, trade the constituent stocks directly.
- **NASDAQ gap-fill extended to YM/ES**: Before taking directional trade on NQ, ES, or YM, check for unfilled daily price gaps between current price and target zone. Gap levels act as speed bumps and price magnets. Applies equally to all three major US indices.
- **Stocks are more demanding (Phase 6, Ch 186)**: Bernd: *"stocks are always tricky… not the best zone right"* — stock zone qualifications are stricter than index/futures. Demand stronger composite scores (≥6.5) and prefer trading the index futures over the stock when uncertain.

### Spot-vs-Futures Cross-Confirmation (Phase 6, Ch 182)

When trading **spot** instruments (XAUUSD, EURUSD, GBPUSD, etc.) instead of their **futures** equivalents (GC, 6E, 6B), confirm the formation on the **futures chart** before executing. Bernd: *"XAUUSD looks for some brokers very bad"* — broker spot charts can show distorted candle formations vs the centralized futures market.

| Spot symbol | Futures equivalent | Use for |
|-------------|---------------------|---------|
| XAUUSD | GC=F | Zone confirmation; spot for execution |
| EURUSD | 6E=F (inverse) | Bias confirmation via COT; spot for execution |
| GBPUSD | 6B=F (inverse) | Bias confirmation via COT; spot for execution |
| BTCUSD | BTC=F | COT confirmation; spot for execution |

**Rule**: If the spot zone exists but the futures zone does not (or vice versa), defer the trade. Both charts should agree on the formation before execution.

---

## UNIVERSAL RULES (All Asset Classes)

These rules apply to **every asset class** without exception.

| Rule | Value |
|------|-------|
| Risk per trade | 1% (max 2% for highest conviction) |
| Minimum R:R | 1:2 |
| Max concurrent positions | 2-3 uncorrelated |
| **Equity basket exception** | NQ + ES + YM aligned = treat as basket; total 3% risk split ≤3 positions |
| Breakeven trigger | Half-T1 preferred (50% of distance to T1); T1 (1R) as conservative fallback |
| Partial profit | 50% at T2 (2R) — NON-NEGOTIABLE |
| **Stop formula — LTF entries** | -33% Fibonacci extension beyond distal |
| **Stop formula — HTF weekly income entries** | Distal line ONLY (no -33% extension) |
| Zone base maximum | 6 candles |
| Departure gate | Leg-out body >= 70% of total candle range |
| Valuation prerequisite | Valuation HARD GATE must pass before 3/5 vote |
| Consensus requirement | 3 out of 5 biases must align (4/5 for counter-trend) |
| Counter-trend max target | T2 (2R) — HARD CEILING. No trailing, no moon-shooting. |
| Daily loss limit | 5% of account → stop trading for the day |
| Consecutive loss limit | 3 losses → pause and review |
| High-impact events (CPI/NFP) | Reduce risk to 0.5% or skip |

## CALENDAR & TIMING RULES

| Event | Rule |
|-------|------|
| **US Federal Holidays** | Two-session gate: avoid the Friday before AND the Monday of a US federal holiday. Low liquidity = unreliable zone behaviour |
| **Thanksgiving week** | COT data freshness suppressed — institutional positioning freezes. Treat COT from prior week as stale. Skip new entries. |
| **Christmas week** | Same as Thanksgiving — low liquidity, stale COT, avoid new entries |
| **October seasonal low window** | High-conviction demand entry window = trading days 9-14 (approx. calendar Oct 10-19). Strong historical demand for equity indices in this window. |
| **February inflection point** | After 12th trading day of February — watch for directional shift. President's Day often anchors a mid-month turning point. |
| **March election-year peak** | Trading days 3-4 of March in election years = historical top formation window. Anticipate supply zone activity. |
| **Valuation monitoring cadence** | Weekly: update directional bias. Daily morning: go/no-go gate check before session open. |
| **Monday candle / Tuesday entry** | For weekly-income setups, the Monday candle provides the directional signal; Tuesday is preferred entry session. |

---

## FUTURES-TO-FUNDED MAPPING (Complete)

Use this table to translate between futures symbols (used for COT data) and funded/spot symbols (used for charting and execution).

| Futures Symbol | Funded/Spot Symbol | Inverted? | Notes |
|---------------|-------------------|-----------|-------|
| 6E | EUR/USD | No | Euro |
| 6B | GBP/USD | No | British Pound |
| 6J | USD/JPY | **YES** | Futures = JPY/USD, spot = USD/JPY |
| 6A | AUD/USD | No | Australian Dollar |
| 6C | USD/CAD | **YES** | Futures = CAD/USD, spot = USD/CAD |
| 6S | USD/CHF | **YES** | Futures = CHF/USD, spot = USD/CHF |
| 6N | NZD/USD | No | New Zealand Dollar |
| GC | XAU/USD | No | Gold |
| SI | XAG/USD | No | Silver |
| HG | Copper | No | Copper |
| CL | WTI Crude | No | Crude Oil |
| NG | Natural Gas | No | Natural Gas |
| ES | SPX / S&P 500 | No | S&P 500 Index |
| NQ | NDX / Nasdaq 100 | No | Nasdaq 100 Index |
| YM | DJI / Dow 30 | No | Dow Jones Industrial |
| RTY | RUT / Russell 2000 | No | Russell 2000 Small Cap |
| ZB | US 30yr Bond | No | 30-Year Treasury Bond |
| ZN | US 10yr Note | No | 10-Year Treasury Note |
| ZW | Wheat | No | Wheat |
| ZC | Corn | No | Corn |
| ZS | Soybeans | No | Soybeans |

### Inversion Rules for Trading

For inverted pairs (6J, 6C, 6S), you must **flip the bias** when translating from COT/futures analysis to spot chart execution:

| COT/Futures Signal | Spot Chart Action |
|-------------------|-------------------|
| 6J COT = Bullish (JPY strengthening) | USD/JPY = **SELL** (price goes DOWN) |
| 6J COT = Bearish (JPY weakening) | USD/JPY = **BUY** (price goes UP) |
| 6C COT = Bullish (CAD strengthening) | USD/CAD = **SELL** (price goes DOWN) |
| 6C COT = Bearish (CAD weakening) | USD/CAD = **BUY** (price goes UP) |
| 6S COT = Bullish (CHF strengthening) | USD/CHF = **SELL** (price goes DOWN) |
| 6S COT = Bearish (CHF weakening) | USD/CHF = **BUY** (price goes UP) |

**Critical**: Forgetting to account for inversion is one of the most common mistakes. Always double-check the direction when working with 6J, 6C, or 6S.

---

## QUICK LOOKUP TABLE: Settings by Asset Class

| Setting | Forex | Precious Metals | Energy | Soft Commodities | Equity Indices |
|---------|-------|----------------|--------|-----------------|---------------|
| HTF | Weekly | Weekly | Weekly | Weekly | Weekly (or Daily) |
| LTF | Daily | Daily | Daily | Daily | Daily (or 4H) |
| COT Group | Non-Commercials | Commercials + Retailers | Commercials | **Non-Commercials** | Non-Commercials |
| COT Method | Divergence | With Commercials | With Commercials | **Divergence** | Divergence |
| COT Lookback | **26 weeks** | 52 weeks | 52 weeks | **26 weeks** | 26 weeks |
| Valuation ROC | 10 | 10 | 10 | 10 | **10** (dual overlay: 10+13 daily, 13+30 weekly — both must agree) |
| Valuation Refs | DXY | DXY + ZB + GC | DXY + ZB + GC | DXY + ZB + GC | ZN/ZB + **DXY** |
| 156-wk Extreme | No | YES | No | No | No |
| Dollar Reference | YES | YES | YES | YES | **YES** (corrected) |
| NG ZigZag % | — | — | **15% (weekly)** | — | — |
| NG Seasonality | — | — | **10yr+5yr only** | — | — |
| Platinum exception | — | DXY+GC only (no ZB) | — | — | — |
| Valuation Gate | Standard 3/5 | Standard 3/5 | Standard 3/5 | COT dominant | **HARD PREREQUISITE** |
