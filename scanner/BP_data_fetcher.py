"""Data fetching module - Yahoo Finance for price data, CFTC for COT data."""

import time
import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
import logging

logger = logging.getLogger(__name__)

# Real CFTC Socrata endpoint (legacy futures-only report).
# Field names returned here match the keys the parser expects.
CFTC_URL = "https://publicreporting.cftc.gov/resource/6dca-aqww.json"

# When a futures contract is unreachable on yfinance, fall back to a liquid
# ETF/index proxy that tracks the same underlying. Used only for price action;
# COT is still keyed off the futures CFTC code.
FUTURES_PROXY = {
    "ES=F": "SPY",
    "NQ=F": "QQQ",
    "YM=F": "DIA",
    "ZB=F": "TLT",
    "ZN=F": "IEF",
    "GC=F": "GLD",
    "SI=F": "SLV",
    "CL=F": "USO",
    "NG=F": "UNG",
    "6E=F": "FXE",
    "6B=F": "FXB",
    "6J=F": "FXY",
    "6A=F": "FXA",
    "6C=F": "FXC",
    "6S=F": "FXF",
    "DX-Y.NYB": "UUP",
}


class DataFetcher:
    """Fetches OHLCV data from Yahoo Finance and COT data from CFTC."""

    def __init__(self):
        self._cot_cache: Dict[str, pd.DataFrame] = {}
        # Cache OHLCV by (symbol, interval, period) so repeat calls within one
        # scan (valuation refs reused across symbols) don't hammer Yahoo.
        self._ohlcv_cache: Dict[Tuple[str, str, str], pd.DataFrame] = {}

    def fetch_ohlcv(
        self,
        symbol: str,
        interval: str = "1d",
        period: str = "2y",
        start: Optional[str] = None,
        end: Optional[str] = None,
        retries: int = 3,
    ) -> pd.DataFrame:
        """
        Fetch OHLCV data from Yahoo Finance with retry-with-backoff and
        an in-memory cache. If the primary symbol returns nothing (rate limit,
        delisted future contract, etc.) and a proxy is registered, retry the
        proxy automatically.

        Returns:
            DataFrame with columns: timestamp, open, high, low, close, volume.
            Empty DataFrame when no data is available after all retries.
        """
        cache_key = (symbol, interval, period or f"{start}:{end}")
        if cache_key in self._ohlcv_cache:
            return self._ohlcv_cache[cache_key].copy()

        df = self._fetch_one(symbol, interval, period, start, end, retries)
        if df.empty and symbol in FUTURES_PROXY:
            proxy = FUTURES_PROXY[symbol]
            logger.warning(f"{symbol} unreachable, falling back to proxy {proxy}")
            df = self._fetch_one(proxy, interval, period, start, end, retries)

        if not df.empty:
            self._ohlcv_cache[cache_key] = df.copy()
        return df

    def _fetch_one(
        self,
        symbol: str,
        interval: str,
        period: Optional[str],
        start: Optional[str],
        end: Optional[str],
        retries: int,
    ) -> pd.DataFrame:
        backoff = 1.5
        for attempt in range(retries):
            try:
                ticker = yf.Ticker(symbol)
                if start and end:
                    df = ticker.history(start=start, end=end, interval=interval, auto_adjust=False)
                else:
                    df = ticker.history(period=period, interval=interval, auto_adjust=False)

                if df is None or df.empty:
                    if attempt < retries - 1:
                        time.sleep(backoff ** attempt)
                        continue
                    logger.warning(f"No data returned for {symbol} ({interval})")
                    return pd.DataFrame()

                df = df[['Open', 'High', 'Low', 'Close', 'Volume']]
                df.columns = ['open', 'high', 'low', 'close', 'volume']
                df.index.name = 'timestamp'
                df.reset_index(inplace=True)
                return df
            except Exception as e:
                if attempt < retries - 1:
                    time.sleep(backoff ** attempt)
                    continue
                logger.error(f"Error fetching {symbol} ({interval}): {e}")
                return pd.DataFrame()
        return pd.DataFrame()

    def fetch_multi_timeframe(
        self,
        symbol: str,
        timeframes: List[str] = ["1wk", "1d", "4h"]
    ) -> Dict[str, pd.DataFrame]:
        """Fetch data for multiple timeframes."""
        results = {}
        for tf in timeframes:
            if tf in ['1mo', '1wk']:
                period = '10y'
            elif tf == '1d':
                period = '5y'
            elif tf in ('60m', '30m', '15m', '5m', '1m'):
                # Yahoo hard limit: 1h data only available for last 730 days.
                # Use 729d to stay safely within the window.
                period = '729d'
            else:
                period = '2y'

            df = self.fetch_ohlcv(symbol, interval=tf, period=period)
            if not df.empty:
                results[tf] = df

        return results

    def fetch_cot_data(self, cftc_code: str = "") -> pd.DataFrame:
        """
        Fetch COT (Commitment of Traders) data from the CFTC public dataset.
        Falls back to simulated data only if the live API fails -- a warning
        is always logged when simulation is used so callers can tell.

        When `cftc_code` is empty (symbol has no COT report -- e.g. forex
        crosses, individual stocks, XRP), return an empty DataFrame so the
        rules engine treats COT bias as `neutral` instead of pulling Gold COT
        as a Wrong Default.
        """
        if not cftc_code:
            return pd.DataFrame()
        if cftc_code in self._cot_cache:
            return self._cot_cache[cftc_code]

        try:
            import requests

            params = {
                "$where": f"cftc_contract_market_code='{cftc_code}'",
                "$order": "report_date_as_yyyy_mm_dd DESC",
                "$limit": 260,  # ~5 years of weekly reports
            }
            resp = requests.get(CFTC_URL, params=params, timeout=20)

            if resp.status_code == 200:
                data = resp.json()
                if data:
                    records = []
                    for entry in data:
                        records.append({
                            'date':         entry.get('report_date_as_yyyy_mm_dd'),
                            'comm_long':    int(float(entry.get('comm_positions_long_all', 0) or 0)),
                            'comm_short':   int(float(entry.get('comm_positions_short_all', 0) or 0)),
                            'noncomm_long': int(float(entry.get('noncomm_positions_long_all', 0) or 0)),
                            'noncomm_short':int(float(entry.get('noncomm_positions_short_all', 0) or 0)),
                            'nonrep_long':  int(float(entry.get('nonrept_positions_long_all', 0) or 0)),
                            'nonrep_short': int(float(entry.get('nonrept_positions_short_all', 0) or 0)),
                        })
                    df = pd.DataFrame(records)
                    df['date'] = pd.to_datetime(df['date'])
                    df.set_index('date', inplace=True)
                    df.sort_index(inplace=True)
                    self._cot_cache[cftc_code] = df
                    logger.info(f"COT live data loaded for {cftc_code}: {len(df)} weeks")
                    return df
                logger.warning(f"CFTC returned empty result for {cftc_code}")
            else:
                logger.warning(f"CFTC HTTP {resp.status_code} for {cftc_code}")

        except Exception as e:
            logger.warning(f"CFTC API fetch failed for {cftc_code}: {e}")

        logger.warning(f"COT for {cftc_code}: USING SIMULATED DATA (live fetch failed)")
        df = self._simulate_cot_data(cftc_code)
        self._cot_cache[cftc_code] = df
        return df

    def _simulate_cot_data(self, cftc_code: str, periods: int = 260) -> pd.DataFrame:
        """Generate realistic simulated COT data for development purposes."""
        np.random.seed(hash(cftc_code) % (2**31))
        dates = pd.date_range(end=datetime.now(), periods=periods, freq='W-FRI')
        n = len(dates)

        comm_long = np.zeros(n)
        comm_short = np.zeros(n)
        noncomm_long = np.zeros(n)
        noncomm_short = np.zeros(n)

        base = abs(hash(cftc_code)) % 100000 + 50000
        comm_long[0] = base
        comm_short[0] = base * np.random.uniform(0.7, 1.3)
        noncomm_long[0] = base * np.random.uniform(0.3, 0.6)
        noncomm_short[0] = base * np.random.uniform(0.3, 0.6)

        for i in range(1, n):
            comm_long[i] = comm_long[i-1] + np.random.randn() * base * 0.05
            comm_short[i] = comm_short[i-1] + np.random.randn() * base * 0.05
            noncomm_long[i] = noncomm_long[i-1] + np.random.randn() * base * 0.03
            noncomm_short[i] = noncomm_short[i-1] + np.random.randn() * base * 0.03

            comm_long[i] = comm_long[i] * 0.98 + base * 0.02
            comm_short[i] = comm_short[i] * 0.98 + base * 0.02

        comm_long = np.maximum(comm_long, 0)
        comm_short = np.maximum(comm_short, 0)
        noncomm_long = np.maximum(noncomm_long, 0)
        noncomm_short = np.maximum(noncomm_short, 0)

        total = (comm_long + comm_short + noncomm_long + noncomm_short) * np.random.uniform(0.3, 0.5)
        nonrep_long = total * np.random.uniform(0.4, 0.6)
        nonrep_short = total - nonrep_long

        df = pd.DataFrame({
            'comm_long':     comm_long.astype(int),
            'comm_short':    comm_short.astype(int),
            'noncomm_long':  noncomm_long.astype(int),
            'noncomm_short': noncomm_short.astype(int),
            'nonrep_long':   nonrep_long.astype(int),
            'nonrep_short':  nonrep_short.astype(int),
        }, index=dates)

        return df

    def fetch_seasonality_reference(
        self,
        symbol: str,
        lookback_years: int = 15
    ) -> pd.DataFrame:
        """Fetch long-term historical data for seasonality calculation."""
        df = self.fetch_ohlcv(symbol, interval='1d', period=f'{lookback_years}y')
        return df


def get_cftc_code(symbol: str) -> str:
    """Map Yahoo Finance / spot ticker to CFTC commodity code.

    Spot Fundingpips-style tickers (EURUSD=X, BTC-USD, XAUUSD, etc.) are
    mapped to their underlying futures COT code so the COT layer keeps
    working when the OHLCV chart is the broker spot symbol.
    """
    mapping = {
        # ── Futures (canonical) ───────────────────────────────────────
        'GC=F':  '088691',  # Gold
        'SI=F':  '084691',  # Silver
        'HG=F':  '085692',  # Copper
        'PL=F':  '076651',  # Platinum
        'PA=F':  '075651',  # Palladium
        'CL=F':  '067651',  # Crude Oil WTI
        'NG=F':  '023651',  # Natural Gas
        'RB=F':  '111659',  # RBOB Gasoline
        'HO=F':  '022651',  # Heating Oil
        'ES=F':  '13874A',  # S&P 500
        'YM=F':  '124603',  # Dow Jones
        'NQ=F':  '209742',  # Nasdaq 100
        'RTY=F': '239742',  # Russell 2000
        '6E=F':  '099741',  # Euro FX
        '6B=F':  '096742',  # GBP
        '6J=F':  '097741',  # JPY
        '6A=F':  '232741',  # AUD
        '6C=F':  '090741',  # CAD
        '6S=F':  '092741',  # CHF
        '6N=F':  '112741',  # NZD
        'ZB=F':  '020601',  # 30Y Bond
        'ZN=F':  '043602',  # 10Y Note
        'ZC=F':  '002602',  # Corn
        'ZW=F':  '001602',  # Wheat
        'ZS=F':  '005602',  # Soybeans
        'CT=F':  '033661',  # Cotton
        'KC=F':  '083731',  # Coffee
        'SB=F':  '080732',  # Sugar
        'CC=F':  '073732',  # Cocoa
        'BTC=F': '133741',  # Bitcoin (CME futures)
        'ETH=F': '146021',  # Ether (CME futures)
        'DX=F':  '098662',  # US Dollar Index (opposing-currency cross-check)

        # ── Spot Fundingpips-style mappings to futures COT ────────────
        # Forex majors (spot=USD on right side -> direct mapping)
        'EURUSD=X': '099741',  # = 6E
        'GBPUSD=X': '096742',  # = 6B
        'AUDUSD=X': '232741',  # = 6A
        'NZDUSD=X': '112741',  # = 6N
        # Forex inverted spot (spot=USD on left, futures=XXX/USD)
        # Same COT code; the rules engine cross-check handles the directional flip
        'USDJPY=X': '097741',  # = 6J (inverted)
        'USDCAD=X': '090741',  # = 6C (inverted)
        'USDCHF=X': '092741',  # = 6S (inverted)
        # Forex crosses -- no direct COT, fall through to default
        # (rules engine derives bias from each leg's COT separately)

        # Metals spot
        'XAUUSD':   '088691',  # = GC
        'XAUUSD=X': '088691',
        'XAGUSD':   '084691',  # = SI
        'XAGUSD=X': '084691',

        # Crypto spot (CME bitcoin/ether futures COT)
        'BTC-USD': '133741',  # = BTC
        'ETH-USD': '146021',  # = ETH
        # XRP-USD, LTC-USD: no CFTC reportable -> defaults

        # Cash equity indices (use futures COT proxy)
        '^GSPC': '13874A',  # = ES
        '^DJI':  '124603',  # = YM
        '^IXIC': '209742',  # = NQ
        '^RUT':  '239742',  # = RTY

        # Brent crude (separate CFTC reportable from WTI)
        'BZ=F':  '06765T',  # ICE Brent crude
    }
    # Return empty string for unmapped symbols (forex crosses, individual
    # stocks without single-name COT, XRP, etc). Empty -> fetcher returns
    # empty DataFrame -> rules engine treats COT as neutral and bias is
    # derived from Valuation/Seasonality/Location/Trend only.
    return mapping.get(symbol, '')
