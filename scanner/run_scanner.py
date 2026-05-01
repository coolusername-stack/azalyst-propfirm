"""
Blueprint Market Scanner -- Scans global markets through the 7-step process
and auto paper-trades valid signals.

Usage:
    python run_scanner.py            # Full scan with dashboard auto-open
    python run_scanner.py --no-open  # Scan only, skip browser launch
"""

import sys
import os
import json
import yaml
import logging
import webbrowser
import traceback
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from dataclasses import asdict

# ---------------------------------------------------------------------------
# Path setup
# ---------------------------------------------------------------------------
SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))

from BP_data_fetcher import DataFetcher, get_cftc_code
from BP_rules_engine import RulesEngine
from BP_paper_trader import PaperTrader

# ---------------------------------------------------------------------------
# ANSI colour helpers (Windows 10+ supports ANSI in cmd/powershell)
# ---------------------------------------------------------------------------
RESET  = "\033[0m"
BOLD   = "\033[1m"
RED    = "\033[91m"
GREEN  = "\033[92m"
YELLOW = "\033[93m"
CYAN   = "\033[96m"
MAGENTA = "\033[95m"
DIM    = "\033[90m"

# Enable ANSI escape codes on Windows
if sys.platform == "win32":
    try:
        import ctypes
        kernel32 = ctypes.windll.kernel32
        kernel32.SetConsoleMode(kernel32.GetStdHandle(-11), 7)
    except Exception:
        pass

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
LOG_FILE = SCRIPT_DIR / "scanner.log"
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.FileHandler(LOG_FILE, encoding="utf-8"),
        logging.StreamHandler(sys.stdout),
    ],
)
logger = logging.getLogger("scanner")

# ---------------------------------------------------------------------------
# Full watchlist
# ---------------------------------------------------------------------------
FULL_WATCHLIST: List[Dict] = [
    # Forex
    {"symbol": "6E=F", "name": "EUR/USD (Euro FX)",          "asset_class": "forex"},
    {"symbol": "6B=F", "name": "GBP/USD (British Pound)",    "asset_class": "forex"},
    {"symbol": "6J=F", "name": "USD/JPY (Japanese Yen)",     "asset_class": "forex"},
    {"symbol": "6A=F", "name": "AUD/USD (Australian Dollar)", "asset_class": "forex"},
    {"symbol": "6C=F", "name": "USD/CAD (Canadian Dollar)",  "asset_class": "forex"},
    {"symbol": "6S=F", "name": "USD/CHF (Swiss Franc)",      "asset_class": "forex"},
    # Precious Metals
    {"symbol": "GC=F", "name": "Gold",                       "asset_class": "precious_metals"},
    {"symbol": "SI=F", "name": "Silver",                     "asset_class": "precious_metals"},
    # Energy
    {"symbol": "CL=F", "name": "Crude Oil WTI",              "asset_class": "energies"},
    {"symbol": "NG=F", "name": "Natural Gas",                "asset_class": "energies"},
    # Equity Indices
    {"symbol": "ES=F", "name": "S&P 500 E-mini",            "asset_class": "equity_indices"},
    {"symbol": "NQ=F", "name": "Nasdaq 100 E-mini",         "asset_class": "equity_indices"},
    {"symbol": "YM=F", "name": "Dow Jones E-mini",          "asset_class": "equity_indices"},
    # Bonds / Interest Rates
    {"symbol": "ZB=F", "name": "30Y US Bond",               "asset_class": "interest_rates"},
    {"symbol": "ZN=F", "name": "10Y US Note",               "asset_class": "interest_rates"},
]

# ---------------------------------------------------------------------------
# Timeframe mapping per income strategy
# ---------------------------------------------------------------------------
STRATEGY_TIMEFRAMES = {
    "monthly": {"htf": "1mo", "ltf": "1wk"},
    "weekly":  {"htf": "1wk", "ltf": "1d"},
    "daily":   {"htf": "1d",  "ltf": "60m"},
    "intraday": {"htf": "60m", "ltf": "15m"},
}

# ---------------------------------------------------------------------------
# Valuation reference symbols by asset class -- methodology/03_fundamentals.md
# "Settings by Asset Class" table (Phase 4+5 P1 corrections applied):
#
#   Forex            : DXY only                     (ROC 10)
#   Equity Indices   : DXY + 10Y Note + 30Y Bond    (ROC 13/30 dual; P1: DXY ADDED)
#   Equities (stocks): same as Equity Indices       (per-stock dual-TF gate)
#   Commodities      : DXY + Gold + 30Y Bond        (ROC 10)
#   Precious Metals  : DXY + Gold + 30Y Bond        (default; Silver/Copper/Palladium)
#   Platinum         : DXY + Gold ONLY              (no Bonds -- per spec)
#                       use VALUATION_REFS_PER_SYMBOL override below
#   Energies         : DXY + Gold + 30Y Bond        (ROC 10)
#   Interest Rates   : 10Y Note proxy
#   Crypto           : DXY only                     (best-effort; spec is sparse)
#
# Per-symbol overrides (e.g. Platinum) take precedence over the asset-class
# default. yfinance tickers used: DX-Y.NYB = DXY, ZN=F = 10Y Note, ZB=F = 30Y Bond,
# GC=F = Gold (also acts as Silver bonds proxy when @VD isn't available).
# ---------------------------------------------------------------------------
VALUATION_REFS = {
    "forex":           ["DX-Y.NYB"],
    "equity_indices":  ["DX-Y.NYB", "ZN=F", "ZB=F"],
    "equities":        ["DX-Y.NYB", "ZN=F", "ZB=F"],
    "commodities":     ["DX-Y.NYB", "GC=F", "ZB=F"],
    "precious_metals": ["DX-Y.NYB", "GC=F", "ZB=F"],
    "energies":        ["DX-Y.NYB", "GC=F", "ZB=F"],
    "interest_rates":  ["^TNX"],
    "crypto":          ["DX-Y.NYB"],
}

# Per-symbol overrides where the asset-class default doesn't apply.
# Per methodology/03_fundamentals.md "Platinum Valuation = DXY + Gold only".
VALUATION_REFS_PER_SYMBOL = {
    "PL=F": ["DX-Y.NYB", "GC=F"],   # Platinum: no Bonds
}

# ---------------------------------------------------------------------------
# Output file paths
# ---------------------------------------------------------------------------
# Repo layout for the Azalyst Propfirm package:
#   <repo>/scanner/      -- this file + BP_*.py modules
#   <repo>/dashboard/    -- static dashboard.html (deployed to GitHub Pages)
#   <repo>/data/         -- scan_results.json + paper_trader_state.json
#                            committed back by GitHub Actions on each run.
# An override `AZALYST_DATA_DIR` env var lets local runs (or CI) point the
# state files anywhere. Falls back to <repo>/data/ then to SCRIPT_DIR.
_REPO_ROOT = SCRIPT_DIR.parent
_DATA_DIR_DEFAULT = _REPO_ROOT / "data"
DATA_DIR = Path(os.environ.get("AZALYST_DATA_DIR") or str(_DATA_DIR_DEFAULT))
DATA_DIR.mkdir(parents=True, exist_ok=True)

SCAN_RESULTS_FILE   = DATA_DIR / "scan_results.json"
SCAN_HISTORY_FILE   = DATA_DIR / "scan_history.json"
PAPER_STATE_FILE    = DATA_DIR / "paper_trader_state.json"
DASHBOARD_FILE      = _REPO_ROOT / "dashboard" / "dashboard.html"


# ===================================================================
# Helper: load / save paper trader state for persistence
# ===================================================================

def load_paper_trader_state(trader: PaperTrader) -> None:
    """Restore paper trader state from disk if a save file exists."""
    if not PAPER_STATE_FILE.exists():
        logger.info("No previous paper trader state found -- starting fresh.")
        return
    try:
        with open(PAPER_STATE_FILE, "r", encoding="utf-8") as f:
            state = json.load(f)

        trader.balance           = state.get("balance", trader.balance)
        trader.initial_balance   = state.get("initial_balance", trader.initial_balance)
        trader.closed_pnl_total  = state.get("closed_pnl_total", 0.0)
        trader.total_trades      = state.get("total_trades", 0)
        trader.winning_trades    = state.get("winning_trades", 0)
        trader.losing_trades     = state.get("losing_trades", 0)
        trader.peak_balance      = state.get("peak_balance", trader.balance)
        trader.max_drawdown_pct  = state.get("max_drawdown_pct", 0.0)
        trader.daily_pnl         = state.get("daily_pnl", 0.0)
        trader.daily_trades      = state.get("daily_trades", 0)
        trader.zone_memory       = state.get("zone_memory", {})

        logger.info(
            f"Restored paper trader state: balance=${trader.balance:,.2f}, "
            f"trades={trader.total_trades}, PnL=${trader.closed_pnl_total:,.2f}"
        )
    except Exception as exc:
        logger.warning(f"Could not load paper trader state: {exc}")


def save_paper_trader_state(trader: PaperTrader) -> None:
    """Persist paper trader state to disk."""
    state = {
        "balance":          trader.balance,
        "initial_balance":  trader.initial_balance,
        "closed_pnl_total": trader.closed_pnl_total,
        "total_trades":     trader.total_trades,
        "winning_trades":   trader.winning_trades,
        "losing_trades":    trader.losing_trades,
        "peak_balance":     trader.peak_balance,
        "max_drawdown_pct": trader.max_drawdown_pct,
        "daily_pnl":        trader.daily_pnl,
        "daily_trades":     trader.daily_trades,
        "zone_memory":      trader.zone_memory,
        "saved_at":         datetime.now().isoformat(),
    }
    with open(PAPER_STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=2)
    logger.info(f"Paper trader state saved to {PAPER_STATE_FILE}")


# ===================================================================
# Helper: JSON-safe serialisation (handles datetime, numpy, etc.)
# ===================================================================

def json_safe(obj):
    """Make an object JSON-serialisable."""
    if isinstance(obj, datetime):
        return obj.isoformat()
    if isinstance(obj, Path):
        return str(obj)
    if hasattr(obj, "item"):  # numpy scalar
        return obj.item()
    if hasattr(obj, "tolist"):  # numpy array
        return obj.tolist()
    if hasattr(obj, "__dict__"):
        return {k: json_safe(v) for k, v in obj.__dict__.items()}
    if isinstance(obj, dict):
        return {k: json_safe(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [json_safe(i) for i in obj]
    return obj


# ===================================================================
# Core: scan a single symbol
# ===================================================================

def build_indicator_series(
    engine: RulesEngine,
    asset_class: str,
    price_df,
    cot_df,
    val_refs: Dict,
    seasonal_df,
) -> Dict:
    """Compute the COT / Valuation / Seasonality timeseries that the dashboard
    plots. Each entry mirrors the data the rules engine already calculates --
    we just expose it for visualization so the user can verify the indicators
    are firing correctly.
    """
    import pandas as pd

    series: Dict = {
        "asset_class":              asset_class,
        "cot_index":                [],   # normalized 0-100 (3 lines)
        "cot_index_extreme":        [],   # 156-week extreme overlay (3 lines)
        "cot_report":               [],   # raw position counts (signed)
        "valuation_refs":           {},   # per-reference series, e.g. {DXY: [...], ZB=F: [...]}
        "seasonality":              [],   # 15y main series (kept for back-compat)
        "seasonality_multi":        {},   # {5: [...], 10: [...], 15: [...]}
        "seasonality_current_bin":  None,
    }

    # Use the same asset-class-tuned engines that _analyze_fundamentals uses
    # so the dashboard charts reflect what actually drove the bias decision.
    cot_engine, val_engine = engine._indicators_for_class(asset_class)
    from BP_indicators import COTReport
    cot_report_engine = COTReport()

    # ---- COT Index (last 156 weeks ~ 3 years) ----
    try:
        if cot_df is not None and not cot_df.empty:
            cot_calc = cot_engine.calculate(cot_df).tail(156)
            for idx, row in cot_calc.iterrows():
                date_s = str(idx.date()) if hasattr(idx, "date") else str(idx)
                series["cot_index"].append({
                    "date":        date_s,
                    "commercials": _safe_float(row.get("commercials_index")),
                    "large_specs": _safe_float(row.get("large_specs_index")),
                    "small_specs": _safe_float(row.get("small_specs_index")),
                })
                series["cot_index_extreme"].append({
                    "date":        date_s,
                    "commercials": _safe_float(row.get("comm_net_extreme")),
                    "large_specs": _safe_float(row.get("lspec_net_extreme")),
                    "small_specs": _safe_float(row.get("sspec_net_extreme")),
                })
    except Exception as e:
        logger.warning(f"build cot series failed: {e}")

    # ---- COT Report (raw positions, last 104 weeks) ----
    try:
        if cot_df is not None and not cot_df.empty:
            rep = cot_report_engine.calculate(cot_df).tail(104)
            for idx, row in rep.iterrows():
                series["cot_report"].append({
                    "date":           str(idx.date()) if hasattr(idx, "date") else str(idx),
                    "comm_net":       _safe_float(row.get("comm_net")),
                    "lspec_net":      _safe_float(row.get("lspec_net")),
                    "sspec_net":      _safe_float(row.get("sspec_net")),
                })
    except Exception as e:
        logger.warning(f"build cot report failed: {e}")

    # ---- Valuation per-reference (3 separate lines per textbook Pine Script) ----
    try:
        if val_refs:
            val_calc = val_engine.calculate(price_df, val_refs)
            if not val_calc.empty:
                tail = val_calc.tail(100)
                for ref_name in val_refs.keys():
                    col = f"valuation_{ref_name}"
                    if col not in tail.columns:
                        continue
                    pts = []
                    for idx, row in tail.iterrows():
                        v = row.get(col)
                        if pd.notna(v):
                            pts.append({
                                "date":  str(idx.date()) if hasattr(idx, "date") else str(idx),
                                "value": float(v),
                            })
                    if pts:
                        series["valuation_refs"][ref_name] = pts
    except Exception as e:
        logger.warning(f"build valuation series failed: {e}")

    # ---- Seasonality multi-lookback (5y / 10y / 15y) ----
    try:
        if seasonal_df is not None and not seasonal_df.empty:
            multi = engine.seasonality.calculate_multi(seasonal_df, timeframe="weekly")
            for years, seas in multi.items():
                series["seasonality_multi"][str(years)] = [
                    {"bin": int(r["bin"]), "value": float(r["seasonal_value"])}
                    for _, r in seas.iterrows()
                ]
            # Keep the 15y series in the legacy slot so older dashboard JS
            # versions still find it.
            if 15 in multi:
                series["seasonality"] = series["seasonality_multi"]["15"]
            elif multi:
                series["seasonality"] = next(iter(series["seasonality_multi"].values()))
            series["seasonality_current_bin"] = int(
                engine.seasonality.get_current_bin(price_df, "weekly")
            )
    except Exception as e:
        logger.warning(f"build seasonality series failed: {e}")

    return series


def _safe_float(v) -> Optional[float]:
    import math
    try:
        f = float(v)
        if math.isnan(f) or math.isinf(f):
            return None
        return round(f, 2)
    except (TypeError, ValueError):
        return None


def scan_symbol(
    symbol_info: Dict,
    fetcher: DataFetcher,
    engine: RulesEngine,
    htf: str,
    ltf: str,
    strategy: str,
) -> Optional[Dict]:
    """
    Run the full 7-step process on one symbol.
    Returns a signal dict or None.
    """
    sym  = symbol_info["symbol"]
    name = symbol_info["name"]
    ac   = symbol_info["asset_class"]

    logger.info(f"--- Scanning {sym} ({name}) [{ac}] ---")

    out = {"signal": None, "indicators": None}

    # 1. Fetch OHLCV for HTF + LTF
    ohlcv = fetcher.fetch_multi_timeframe(sym, timeframes=[htf, ltf])
    if htf not in ohlcv or ltf not in ohlcv:
        logger.warning(f"[{sym}] Insufficient price data -- skipped.")
        return out

    # 2. Fetch COT data
    # `cot_symbol` is an optional override on the watchlist entry: when the
    # OHLCV ticker is a spot/CFD symbol that has no direct COT report (e.g.
    # EURUSD=X), the entry can map it to the underlying futures (e.g. 6E=F)
    # so we still get COT bias. Falls back to the OHLCV symbol when absent.
    cot_lookup_sym = symbol_info.get("cot_symbol", sym)
    cftc_code = get_cftc_code(cot_lookup_sym)
    cot_df = fetcher.fetch_cot_data(cftc_code)

    # 2b. For forex pairs: fetch USD Index COT for the opposing-currency
    # cross-check. The rules engine compares EUR-side bias against
    # inverted USD-side bias and demotes to neutral on disagreement.
    opposing_cot_df = None
    if ac == 'forex':
        opposing_cot_df = fetcher.fetch_cot_data(get_cftc_code('DX=F'))

    # 3. Fetch valuation reference symbols (cached in DataFetcher across calls,
    #    so the dollar/bond series is downloaded once per scan, not 15 times)
    val_refs: Dict = {}
    # Per-symbol Valuation refs override (e.g. Platinum) takes precedence
    # over the asset-class default.
    ref_symbols = VALUATION_REFS_PER_SYMBOL.get(sym) or VALUATION_REFS.get(ac, ["DX-Y.NYB"])
    for ref_sym in ref_symbols:
        ref_df = fetcher.fetch_ohlcv(ref_sym, interval=ltf, period="5y")
        if not ref_df.empty:
            val_refs[ref_sym] = ref_df

    # 4. Fetch seasonality data
    seasonal_df = fetcher.fetch_seasonality_reference(sym, lookback_years=15)

    # 5. Run the seven-step process
    signal = engine.run_seven_step_process(
        symbol=sym,
        ohlcv_data=ohlcv,
        cot_df=cot_df,
        valuation_refs=val_refs,
        seasonal_df=seasonal_df,
        htf=htf,
        ltf=ltf,
        income_strategy=strategy,
        asset_class=ac,
        opposing_cot_df=opposing_cot_df,
    )

    if signal:
        signal["asset_class"] = ac
        signal["display_name"] = name
        out["signal"] = signal

    # 6. Build indicator timeseries for the dashboard (always, even when no signal)
    out["indicators"] = build_indicator_series(
        engine, ac, ohlcv[htf], cot_df, val_refs, seasonal_df
    )

    return out


# ===================================================================
# Core: scan all markets
# ===================================================================

def scan_all_markets(
    config: Dict,
    watchlist: Optional[List[Dict]] = None,
) -> Dict:
    """
    Scan every symbol in the watchlist through the 7-step process.
    Auto paper-trades valid signals.

    Returns a results dict ready for JSON serialisation.
    """
    scan_start = datetime.now()

    # Resolve strategy list. Two ways the user can drive timeframes:
    #   1. Per-symbol `strategies: ['weekly', 'daily']` field on each
    #      watchlist entry (highest priority).
    #   2. Global `default_strategies` list in BP_config.yaml -- applied
    #      when an entry has no override.
    #   3. Legacy `active_strategy` (single-pass mode) -- used when both
    #      of the above are absent.
    default_strategies = config.get("default_strategies") or [
        config.get("active_strategy", "weekly")
    ]

    if watchlist is None:
        watchlist = FULL_WATCHLIST

    fetcher = DataFetcher()
    engine  = RulesEngine(config)
    trader  = PaperTrader(config)

    # Restore persisted paper trader state
    load_paper_trader_state(trader)

    # Reset daily stats if new day
    today = datetime.now().strftime("%Y-%m-%d")
    if trader.current_date != today:
        trader.reset_daily_stats()
        trader.current_date = today

    signals: List[Dict] = []
    errors:  List[Dict] = []
    auto_traded = 0
    ohlcv_cache: Dict[str, Dict[str, List[Dict]]] = {}
    zones_by_symbol: Dict[str, List[Dict]] = {}
    indicators_by_symbol: Dict[str, Dict] = {}

    total = len(watchlist)
    # Total scan passes = sum of strategies-per-symbol (drives ETA + log)
    total_passes = sum(
        len(sym.get("strategies") or default_strategies)
        for sym in watchlist
    )
    print()
    print(f"{BOLD}{CYAN}{'=' * 60}{RESET}")
    print(f"{BOLD}{CYAN}  Blueprint Market Scanner{RESET}")
    print(f"{BOLD}{CYAN}  Default strategies: {default_strategies}  |  Total passes: {total_passes}{RESET}")
    print(f"{BOLD}{CYAN}  Watchlist: {total} symbols  |  {scan_start.strftime('%Y-%m-%d %H:%M:%S')}{RESET}")
    print(f"{BOLD}{CYAN}{'=' * 60}{RESET}")
    print()

    pass_idx = 0
    for idx, sym_info in enumerate(watchlist, 1):
        sym  = sym_info["symbol"]
        name = sym_info["name"]
        # Per-symbol strategy override -- crypto entries pin to ['daily']
        symbol_strategies = sym_info.get("strategies") or default_strategies

        for strategy in symbol_strategies:
            pass_idx += 1
            tf = STRATEGY_TIMEFRAMES.get(strategy, STRATEGY_TIMEFRAMES["weekly"])
            htf, ltf = tf["htf"], tf["ltf"]
            progress = f"[{pass_idx}/{total_passes}]"

            print(f"  {DIM}{progress}{RESET}  Scanning {BOLD}{sym}{RESET} "
                  f"({name}) on {strategy} ({htf}/{ltf})...", end="", flush=True)

            try:
                # Cache OHLCV so the dashboard can chart even without a
                # live API. We dedupe by (symbol, tf_label) so the same
                # daily series isn't re-fetched on the second strategy pass.
                for tf_label in (htf, ltf):
                    if (ohlcv_cache.get(sym) or {}).get(tf_label) is not None:
                        continue
                    df_tf = fetcher.fetch_ohlcv(
                        sym,
                        interval=tf_label,
                        period="10y" if tf_label in ("1mo", "1wk") else "5y",
                    )
                    if not df_tf.empty:
                        tail = df_tf.tail(300).copy()
                        tail["timestamp"] = tail["timestamp"].astype(str)
                        ohlcv_cache.setdefault(sym, {})[tf_label] = tail.to_dict(orient="records")

                scan_out = scan_symbol(sym_info, fetcher, engine, htf, ltf, strategy)
                signal = scan_out.get("signal")
                if scan_out.get("indicators"):
                    # Last strategy's indicators win for the dashboard panel
                    indicators_by_symbol[sym] = scan_out["indicators"]

                if signal:
                    # Tag the signal with which timeframe pass produced it
                    signal["strategy"] = strategy
                    signals.append(signal)
                    print(f"  {GREEN}SIGNAL: {signal['direction'].upper()} ({strategy}){RESET}")

                    # Auto paper-trade the signal
                    pos_id = trader.submit_signal(signal)
                    if pos_id:
                        auto_traded += 1
                        signal["paper_trade_id"] = pos_id
                        print(f"           {MAGENTA}-> Paper trade opened: {pos_id}{RESET}")
                    else:
                        signal["paper_trade_id"] = None
                        print(f"           {YELLOW}-> Signal valid but paper trade rejected (limits){RESET}")
                else:
                    print(f"  {DIM}no signal{RESET}")

            except Exception as exc:
                print(f"  {RED}ERROR: {exc}{RESET}")
                logger.error(f"[{sym}/{strategy}] Scan error: {traceback.format_exc()}")
                errors.append({"symbol": sym, "strategy": strategy, "error": str(exc)})

    scan_end = datetime.now()
    elapsed = (scan_end - scan_start).total_seconds()

    # Build the results payload
    account_summary = trader.get_account_summary()
    open_positions  = trader.get_open_positions()
    trade_history   = trader.get_trade_history(limit=100)

    results = {
        "scan_time":         scan_start.isoformat(),
        "scan_duration_sec": round(elapsed, 1),
        "strategy":          strategy,
        "htf":               htf,
        "ltf":               ltf,
        "watchlist_scanned": total,
        "signals_found":     len(signals),
        "auto_traded":       auto_traded,
        "signals":           json_safe(signals),
        "errors":            errors,
        "account":           json_safe(account_summary),
        "positions":         json_safe(open_positions),
        "trade_history":     json_safe(trade_history),
        "ohlcv_cache":       ohlcv_cache,
        "indicators":        indicators_by_symbol,
    }

    # Save paper trader state for next run
    save_paper_trader_state(trader)

    return results


# ===================================================================
# File I/O: save results + append history
# ===================================================================

def save_results(results: Dict) -> None:
    """Write scan_results.json (overwrite) and append to scan_history.json."""

    # 1. Current scan results (dashboard reads this)
    with open(SCAN_RESULTS_FILE, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, default=str)
    logger.info(f"Scan results saved to {SCAN_RESULTS_FILE}")

    # 2. Append to history log
    history_entry = {
        "scan_time":        results["scan_time"],
        "strategy":         results["strategy"],
        "watchlist_scanned": results["watchlist_scanned"],
        "signals_found":    results["signals_found"],
        "auto_traded":      results["auto_traded"],
        "account_balance":  results["account"].get("balance", 0),
        "closed_pnl":       results["account"].get("closed_pnl", 0),
        "win_rate":         results["account"].get("win_rate", 0),
        "total_trades":     results["account"].get("total_trades", 0),
        "signals_summary": [
            {
                "symbol":    s.get("symbol"),
                "direction": s.get("direction"),
                "entry":     s.get("entry_price"),
                "composite": s.get("qualifier_scores", {}).get("composite", 0),
            }
            for s in results.get("signals", [])
        ],
    }

    history: List[Dict] = []
    if SCAN_HISTORY_FILE.exists():
        try:
            with open(SCAN_HISTORY_FILE, "r", encoding="utf-8") as f:
                history = json.load(f)
            if not isinstance(history, list):
                history = []
        except (json.JSONDecodeError, Exception):
            history = []

    history.append(history_entry)

    with open(SCAN_HISTORY_FILE, "w", encoding="utf-8") as f:
        json.dump(history, f, indent=2, default=str)
    logger.info(f"Scan history appended to {SCAN_HISTORY_FILE} ({len(history)} entries)")


# ===================================================================
# Console summary
# ===================================================================

def print_summary(results: Dict) -> None:
    """Print a nicely formatted console summary."""
    print()
    print(f"{BOLD}{CYAN}{'=' * 60}{RESET}")
    print(f"{BOLD}{CYAN}  SCAN COMPLETE{RESET}")
    print(f"{BOLD}{CYAN}{'=' * 60}{RESET}")
    print()

    # Scan stats
    print(f"  {BOLD}Scan Time:{RESET}       {results['scan_time']}")
    print(f"  {BOLD}Duration:{RESET}        {results['scan_duration_sec']}s")
    print(f"  {BOLD}Symbols Scanned:{RESET} {results['watchlist_scanned']}")
    print(f"  {BOLD}Signals Found:{RESET}   {results['signals_found']}")
    print(f"  {BOLD}Auto Traded:{RESET}     {results['auto_traded']}")
    print()

    # Signals table
    signals = results.get("signals", [])
    if signals:
        print(f"  {BOLD}{GREEN}--- SIGNALS ---{RESET}")
        print(f"  {'Symbol':<10} {'Dir':<6} {'Entry':<12} {'Stop':<12} {'T1':<12} {'Score':<6}")
        print(f"  {'-'*58}")
        for s in signals:
            direction = s.get("direction", "?")
            color = GREEN if direction == "long" else RED
            targets = s.get("targets", [0, 0, 0])
            t1 = targets[0] if targets else 0
            composite = s.get("qualifier_scores", {}).get("composite", 0)
            print(
                f"  {s.get('symbol','?'):<10} "
                f"{color}{direction.upper():<6}{RESET} "
                f"{s.get('entry_price',0):<12.4f} "
                f"{s.get('stop_price',0):<12.4f} "
                f"{t1:<12.4f} "
                f"{composite:<6.1f}"
            )
        print()
    else:
        print(f"  {YELLOW}No signals generated this scan.{RESET}")
        print()

    # Account summary
    acct = results.get("account", {})
    balance = acct.get("balance", 0)
    pnl     = acct.get("closed_pnl", 0)
    wr      = acct.get("win_rate", 0)
    trades  = acct.get("total_trades", 0)
    dd      = acct.get("max_drawdown_pct", 0)
    open_p  = acct.get("open_positions", 0)

    pnl_color = GREEN if pnl >= 0 else RED

    print(f"  {BOLD}--- ACCOUNT ---{RESET}")
    print(f"  Balance:       ${balance:>12,.2f}")
    print(f"  Closed PnL:    {pnl_color}${pnl:>12,.2f}{RESET}")
    print(f"  Win Rate:      {wr:>11.1f}%")
    print(f"  Total Trades:  {trades:>12}")
    print(f"  Max Drawdown:  {dd:>11.2f}%")
    print(f"  Open Positions:{open_p:>12}")
    print()

    # Errors
    errors = results.get("errors", [])
    if errors:
        print(f"  {RED}--- ERRORS ({len(errors)}) ---{RESET}")
        for e in errors:
            print(f"  {RED}  {e['symbol']}: {e['error']}{RESET}")
        print()

    print(f"{BOLD}{CYAN}{'=' * 60}{RESET}")
    print()


# ===================================================================
# Main entry point
# ===================================================================

def main():
    """Main scanner entry point."""
    print()
    print(f"{BOLD}{CYAN}============================================{RESET}")
    print(f"{BOLD}{CYAN}  Blueprint Trading System - Market Scanner{RESET}")
    print(f"{BOLD}{CYAN}============================================{RESET}")
    print()

    # ---- Load config ----
    config_path = SCRIPT_DIR / "BP_config.yaml"
    if not config_path.exists():
        print(f"{RED}ERROR: Config file not found at {config_path}{RESET}")
        sys.exit(1)

    with open(config_path, "r", encoding="utf-8") as f:
        config = yaml.safe_load(f)

    logger.info(f"Config loaded from {config_path}")

    # ---- Determine watchlist ----
    # Default: read watchlist from BP_config.yaml (so user edits land in scans).
    # `--full-watchlist` falls back to the in-code FULL_WATCHLIST baseline
    # (futures-only set), and `--config-only` is kept as an alias.
    if "--full-watchlist" in sys.argv:
        watchlist = FULL_WATCHLIST
        logger.info(f"Using in-code FULL_WATCHLIST ({len(watchlist)} symbols)")
    else:
        watchlist = config.get("watchlist") or FULL_WATCHLIST
        source = "BP_config.yaml" if config.get("watchlist") else "FULL_WATCHLIST (config empty)"
        logger.info(f"Using watchlist from {source} ({len(watchlist)} symbols)")

    # ---- Detect CI mode ----
    # `--ci` (or env AZALYST_CI=1) skips the localhost server + browser launch.
    # Used by GitHub Actions where there's no display and we just want the
    # scan output written to disk, then committed back to the repo.
    ci_mode = "--ci" in sys.argv or os.environ.get("AZALYST_CI") == "1"

    # ---- Start the dashboard server FIRST so the user has something to look at
    # while the scan runs. The server runs in a background thread; the new scan
    # results land on disk when scan_all_markets() finishes, and the user can
    # hit Refresh in the dashboard to see them. In CI mode we skip both.
    server_thread = None
    if ci_mode:
        logger.info("CI mode: skipping localhost server + browser launch")
    elif "--no-open" not in sys.argv and DASHBOARD_FILE.exists():
        if "--no-serve" in sys.argv:
            dashboard_path = str(DASHBOARD_FILE)
            print(f"  Opening dashboard (file://): {dashboard_path}")
            print(f"  {YELLOW}NOTE: file:// blocks JSON fetch in modern browsers.{RESET}")
            if sys.platform == "win32":
                os.startfile(dashboard_path)
            else:
                webbrowser.open(DASHBOARD_FILE.as_uri())
        else:
            # Serve from the repo root so /dashboard/dashboard.html can fetch
            # /data/scan_results.json with relative paths -- mirrors the
            # GitHub Pages layout exactly.
            server_thread = _start_server_in_background(_REPO_ROOT, port=8765,
                                                        open_path="/dashboard/dashboard.html")

    # ---- Run scan ----
    try:
        results = scan_all_markets(config, watchlist)
    except Exception as exc:
        logger.error(f"Fatal scan error: {traceback.format_exc()}")
        print(f"\n{RED}FATAL ERROR: {exc}{RESET}")
        if server_thread is not None:
            server_thread.shutdown()
        sys.exit(1)

    # ---- Save results ----
    save_results(results)

    # ---- Print summary ----
    print_summary(results)

    print(f"  {DIM}Log file: {LOG_FILE}{RESET}")
    print()

    # ---- Block until Ctrl-C so the dashboard server stays up ----
    if server_thread is not None:
        print(f"  {GREEN}Refresh the dashboard tab to see the latest scan.{RESET}")
        print(f"  {DIM}Press Ctrl-C in this window to stop the server.{RESET}")
        try:
            server_thread.serve_until_interrupted()
        except KeyboardInterrupt:
            print(f"\n  {DIM}Dashboard server stopped.{RESET}")


class _DashboardServer:
    """Background HTTP server for the dashboard. The server runs in a worker
    thread immediately so the browser can paint stale-but-real data while the
    scan is in progress; the main thread blocks at the end via
    serve_until_interrupted() to keep the server alive.
    """

    def __init__(self, server, thread):
        self._server = server
        self._thread = thread

    def shutdown(self):
        try:
            self._server.shutdown()
        except Exception:
            pass
        self._server.server_close()

    def serve_until_interrupted(self):
        try:
            while self._thread.is_alive():
                self._thread.join(timeout=0.5)
        except KeyboardInterrupt:
            self.shutdown()
            raise


def _start_server_in_background(serve_dir: Path, port: int = 8765,
                                 open_path: str = "/dashboard.html"):
    """Bind a localhost HTTP server and open the dashboard. Returns a
    _DashboardServer handle, or None on bind failure.
    `open_path` is the URL path to launch in the browser (relative to serve_dir).
    """
    import http.server
    import socketserver
    import functools
    import threading

    class _QuietHandler(http.server.SimpleHTTPRequestHandler):
        def log_message(self, *args, **kwargs):
            return

        def end_headers(self):
            self.send_header("Cache-Control", "no-store")
            super().end_headers()

    handler = functools.partial(_QuietHandler, directory=str(serve_dir))
    socketserver.TCPServer.allow_reuse_address = True

    chosen_port = port
    server = None
    for _ in range(10):
        try:
            server = socketserver.TCPServer(("127.0.0.1", chosen_port), handler)
            break
        except OSError:
            chosen_port += 1
    if server is None:
        print(f"  {RED}Could not bind a local port near {port}. Open dashboard manually.{RESET}")
        return None

    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()

    url = f"http://127.0.0.1:{chosen_port}{open_path}"
    print(f"  {GREEN}Dashboard live at {url}{RESET}")
    print(f"  {DIM}(scan is running in this window -- dashboard shows previous results until it finishes){RESET}")
    try:
        webbrowser.open(url)
    except Exception:
        pass

    return _DashboardServer(server, thread)


if __name__ == "__main__":
    main()
