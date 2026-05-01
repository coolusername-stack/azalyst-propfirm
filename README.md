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
5. For each of the ~77 symbols:
   - Fetches OHLCV from Yahoo Finance (HTF + LTF)
   - Fetches COT data from CFTC public API
   - Runs the 7-step Blueprint process (zones, qualifiers, fundamentals, entry trigger)
   - If a signal: submits to the paper trader
6. Updates open positions (BE moves, T2 partials, stop-outs)
7. Writes `data/scan_results.json` + `data/paper_trader_state.json` + `data/scan_history.json`
8. Commits and pushes those three files back to the repo
9. Pages auto-redeploys; dashboard reflects new signals + P&L

Total wall time per scan: ~4–6 min for 77 symbols.

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
