"""
Blueprint Trading Dashboard - Main FastAPI Application
========================================================
Entry point for the backend server.
Serves REST API and WebSocket for the frontend dashboard.
"""

import asyncio
import json
import logging
import yaml
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional
from contextlib import asynccontextmanager

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
import uvicorn

from BP_data_fetcher import DataFetcher
from BP_indicators import COTIndex, Valuation, Seasonality
from BP_zone_detector import ZoneDetector
from BP_rules_engine import RulesEngine
from BP_paper_trader import PaperTrader
from BP_calendar import get_calendar

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
logger = logging.getLogger(__name__)

# --- Configuration ---

def load_config() -> dict:
    config_path = Path(__file__).parent / "BP_config.yaml"
    if not config_path.exists():
        logger.warning("config.yaml not found, using defaults")
        return {}
    with open(config_path) as f:
        return yaml.safe_load(f)

CONFIG = load_config()

# --- Global State ---

class AppState:
    def __init__(self):
        self.config = CONFIG
        self.data_fetcher = DataFetcher()
        self.paper_trader = PaperTrader(CONFIG)
        self.rules_engine = RulesEngine(CONFIG)
        self.signals: List[Dict] = []
        self.latest_prices: Dict[str, Dict] = {}
        self.last_scan: Optional[datetime] = None
        self.connected_websockets: List[WebSocket] = []
        self.zones_cache: Dict[str, List[Dict]] = {}
        self.cot_cache: Dict[str, any] = {}

state = AppState()


# --- WebSocket Manager ---

async def broadcast(data: dict):
    disconnected = []
    for ws in state.connected_websockets:
        try:
            await ws.send_json(data)
        except:
            disconnected.append(ws)
    for ws in disconnected:
        state.connected_websockets.remove(ws)


# --- Lifespan ---

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting Blueprint Trading Dashboard...")
    yield
    logger.info("Shutting down...")


# --- FastAPI App ---

app = FastAPI(title="Blueprint Trading Dashboard", version="1.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# --- REST API Endpoints ---

@app.get("/")
async def root():
    return {"service": "Blueprint Trading Dashboard", "status": "running"}


@app.get("/api/watchlist")
async def get_watchlist():
    return CONFIG.get('watchlist', [])


@app.get("/api/ohlcv/{symbol}")
async def get_ohlcv(symbol: str, timeframe: str = "1d", period: str = "2y"):
    df = state.data_fetcher.fetch_ohlcv(symbol, interval=timeframe, period=period)
    if df.empty:
        raise HTTPException(status_code=404, detail=f"No data for {symbol} ({timeframe})")
    return df.to_dict(orient='records')


@app.get("/api/ohlcv/{symbol}/multi")
async def get_multi_tf(symbol: str, timeframes: str = "1wk,1d"):
    tfs = timeframes.split(",")
    result = {}
    for tf in tfs:
        df = state.data_fetcher.fetch_ohlcv(symbol, interval=tf.strip(), period="5y" if tf.strip() in ['1wk','1mo'] else "2y")
        if not df.empty:
            result[tf.strip()] = df.to_dict(orient='records')
    return {"symbol": symbol, "timeframes": result}


@app.get("/api/zones/{symbol}")
async def get_zones(symbol: str):
    if symbol in state.zones_cache:
        return {"symbol": symbol, "zones": state.zones_cache[symbol]}

    htf_data = state.data_fetcher.fetch_ohlcv(symbol, interval="1wk", period="5y")
    ltf_data = state.data_fetcher.fetch_ohlcv(symbol, interval="1d", period="2y")

    zd = ZoneDetector(CONFIG.get('zone_detection', {}))
    htf_zones = zd.detect_zones(htf_data, symbol, "1wk") if not htf_data.empty else []
    ltf_zones = zd.detect_zones(ltf_data, symbol, "1d") if not ltf_data.empty else []
    ltf_zones = zd.align_multi_timeframe(htf_zones, ltf_zones)

    all_zones = htf_zones + ltf_zones
    all_zones.sort(key=lambda z: z['composite_score'], reverse=True)

    state.zones_cache[symbol] = all_zones
    return {"symbol": symbol, "zones": all_zones}


@app.get("/api/indicators/{symbol}")
async def get_indicators(symbol: str):
    from BP_data_fetcher import get_cftc_code
    cot_df = state.data_fetcher.fetch_cot_data(get_cftc_code(symbol))
    price_df = state.data_fetcher.fetch_ohlcv(symbol, interval="1wk", period="5y")

    cot_idx = COTIndex()
    cot_result = cot_idx.calculate(cot_df) if not cot_df.empty else None

    return {
        "symbol": symbol,
        "cot_index": cot_result.tail(10).to_dict(orient='records') if cot_result is not None else []
    }


@app.get("/api/calendar")
async def get_calendar_summary():
    """Return upcoming economic events and blackout status."""
    return get_calendar().upcoming_summary()


@app.get("/api/account")
async def get_account():
    summary = state.paper_trader.get_account_summary()
    positions = state.paper_trader.get_open_positions()
    history = state.paper_trader.get_trade_history(50)
    return {
        "account": summary,
        "positions": positions,
        "trade_history": history
    }


@app.post("/api/scan")
async def trigger_scan():
    """Manually trigger a full scan for all watchlist symbols."""
    watchlist = CONFIG.get('watchlist', [])
    new_signals = []

    from BP_data_fetcher import get_cftc_code

    for item in watchlist:
        symbol = item.get('symbol', '')
        asset_class = item.get('asset_class', 'commodities')
        if not symbol:
            continue

        try:
            logger.info(f"Scanning {symbol}...")
            ohlcv = state.data_fetcher.fetch_multi_timeframe(symbol, ["1wk", "1d"])

            if '1wk' not in ohlcv or '1d' not in ohlcv:
                continue

            cot_df = state.data_fetcher.fetch_cot_data(get_cftc_code(symbol))
            opposing_cot_df = (
                state.data_fetcher.fetch_cot_data(get_cftc_code('DX=F'))
                if asset_class == 'forex' else None
            )

            # Per-asset-class valuation references (textbook OTC 2025 Module 3
            # Lesson 3): equities EXCLUDE the dollar; forex uses DXY only;
            # commodities use the full triplet.
            ASSET_VAL_REFS = {
                'forex':           ['DX-Y.NYB'],
                'precious_metals': ['DX-Y.NYB', 'ZB=F'],
                'energies':        ['DX-Y.NYB', 'GC=F', 'ZB=F'],
                'equity_indices':  ['^TNX', 'ZB=F'],
                'equities':        ['^TNX', 'ZB=F'],
                'interest_rates':  ['^TNX'],
            }
            refs = ASSET_VAL_REFS.get(asset_class, ['DX-Y.NYB', 'GC=F', 'ZB=F'])
            val_refs = {}
            for ref in refs:
                rdf = state.data_fetcher.fetch_ohlcv(ref, interval="1wk", period="5y")
                if not rdf.empty:
                    val_refs[ref] = rdf

            seasonal_df = state.data_fetcher.fetch_ohlcv(symbol, interval="1d", period="15y")

            signal = state.rules_engine.run_seven_step_process(
                symbol=symbol,
                ohlcv_data=ohlcv,
                cot_df=cot_df,
                valuation_refs=val_refs,
                seasonal_df=seasonal_df,
                htf='1wk',
                ltf='1d',
                income_strategy='weekly',
                asset_class=asset_class,
                opposing_cot_df=opposing_cot_df,
            )

            if signal:
                new_signals.append(signal)
                pos_id = state.paper_trader.submit_signal(signal)
                if pos_id:
                    signal['position_id'] = pos_id

        except Exception as e:
            logger.error(f"Error scanning {symbol}: {e}")

    state.signals = new_signals
    state.last_scan = datetime.now()

    # Also update zone cache
    state.zones_cache = {}

    await broadcast({"event": "scan_complete", "signals": new_signals, "count": len(new_signals)})

    return {"signals": new_signals, "count": len(new_signals), "time": state.last_scan.isoformat()}


@app.post("/api/positions/close/{pos_id}")
async def close_position(pos_id: str):
    if pos_id in state.paper_trader.positions:
        pos = state.paper_trader.positions[pos_id]
        pos.status = "closed"
        pos.close_time = datetime.now()
        state.paper_trader.trade_history.append(pos)
        del state.paper_trader.positions[pos_id]
        return {"status": "closed", "position_id": pos_id}
    raise HTTPException(status_code=404, detail="Position not found")


@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    await ws.accept()
    state.connected_websockets.append(ws)
    try:
        while True:
            data = await ws.receive_json()
            if data.get("action") == "scan":
                await trigger_scan()
            elif data.get("action") == "get_state":
                account = state.paper_trader.get_account_summary()
                await ws.send_json({
                    "event": "state_update",
                    "account": account,
                    "signals": state.signals[-10:]
                })
    except WebSocketDisconnect:
        state.connected_websockets.remove(ws)


# --- Static Files (Frontend) ---

frontend_path = Path(__file__).parent.parent / "frontend"
if frontend_path.exists():
    app.mount("/dashboard", StaticFiles(directory=str(frontend_path), html=True), name="dashboard")


# --- Main ---

if __name__ == "__main__":
    host = CONFIG.get('api', {}).get('host', '0.0.0.0')
    port = CONFIG.get('api', {}).get('port', 8000)
    uvicorn.run("BP_main:app", host=host, port=port, reload=True)