"""
Rules Engine - Implements the Seven-Step Decision Process.
From DELIVERABLE_2_STRATEGY_RULEBOOK, sections A-H.
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Optional, Tuple
from datetime import datetime
import logging

from BP_indicators import COTIndex, Valuation, Seasonality
from BP_zone_detector import ZoneDetector
from BP_patterns import PatternDetector, PatternType, TradeDirection
from BP_roadmap import build_monthly_roadmap, filter_signal_by_roadmap
from BP_calendar import get_calendar, BlackoutStatus

logger = logging.getLogger(__name__)


class BiasSignal:
    BULLISH = 'bullish'
    BEARISH = 'bearish'
    NEUTRAL = 'neutral'


# Per-asset-class indicator parameters per the Hybrid AI course defaults
# (HAI 1:19:59 "weeks look back, 156... and the 26") with the Funded Trader
# commodity override (FT 02.03.2024 [0:15:38] "52 weeks... whole planting
# and harvesting season"). Equities use ROC=13 on Valuation (longer/smoother
# per OTC L8); commodities use ROC=10.
COT_LOOKBACK_BY_CLASS = {
    'forex':           26,   # Hybrid AI default
    'commodities':     52,   # Funded Trader override -- planting/harvest cycle
    'energies':        52,   # crude/nat-gas have seasonal supply cycles
    'precious_metals': 52,   # mining/import cycles
    'equity_indices':  26,
    'equities':        26,
    'interest_rates':  26,
}

# Pine Script (CampusValuationTool) default Length is 10 across the board.
# A previous version of these docs claimed equities should use 13 ("Dual-ROC
# for Equities"), but the Pine Script source the user shared confirms the
# indicator runs ONE ROC at the default Length=10 -- "dual-ROC" was an
# overlay practice (running two instances of the indicator on the same
# chart with different Length values), not a parameter override on a
# single instance. Tested: with Length=13 our values for META/NVDA/AMZN
# came out wildly more bearish than Bernd's verbal reading; Length=10
# produced readings consistent with his commentary.
VALUATION_LENGTH_BY_CLASS = {
    'forex':           10,
    'commodities':     10,
    'energies':        10,
    'precious_metals': 10,
    'equity_indices':  10,
    'equities':        10,
    'interest_rates':  10,
}


class RulesEngine:
    """
    Seven-Step Decision Process for trade signal generation.
    """

    def __init__(self, config: Dict):
        self.config = config
        self.risk_config = config.get('risk', {})
        self.stop_config = config.get('stop_loss', {})

        # Initialize indicator engines
        cot_cfg = config.get('cot', {})
        val_cfg = config.get('valuation', {})
        seas_cfg = config.get('seasonality', {})

        self.cot_index = COTIndex(
            lookback_weeks=cot_cfg.get('lookback_weeks', 26),
            upper_extreme=cot_cfg.get('upper_extreme', 80),
            lower_extreme=cot_cfg.get('lower_extreme', 20)
        )

        self.valuation = Valuation(
            length=val_cfg.get('length', 10),
            rescale_length=val_cfg.get('rescale_length', 100),
            overvalued=val_cfg.get('overvalued_threshold', 75),
            undervalued=val_cfg.get('undervalued_threshold', -75)
        )

        self.seasonality = Seasonality(
            lookback_years=seas_cfg.get('lookback_years', 15),
            bias_lookahead_bars=seas_cfg.get('bias_lookahead_bars', 20)
        )

        self.zone_detector = ZoneDetector(config.get('zone_detection', {}))
        self.pattern_detector = PatternDetector(config)

    def run_seven_step_process(
        self,
        symbol: str,
        ohlcv_data: Dict[str, pd.DataFrame],
        cot_df: pd.DataFrame,
        valuation_refs: Dict[str, pd.DataFrame],
        seasonal_df: pd.DataFrame,
        htf: str = '1wk',
        ltf: str = '1d',
        income_strategy: str = 'weekly',
        asset_class: str = 'commodities',
        opposing_cot_df: Optional[pd.DataFrame] = None,
        prefer_midpoint_entry: bool = False,
    ) -> Optional[Dict]:
        """
        Execute the full Seven-Step Decision Process.

        Steps:
        1. Market Selection (already done - symbol passed in)
        2. HTF Technical Analysis (location, trend)
        3. Fundamental Confirmation (COT, Valuation, Seasonality)
        4. LTF Zone Identification (zone detection + qualifiers)
        5. Entry Trigger (candlestick patterns)
        6. Trade Management (stop, targets, sizing)
        7. Review & Refine (signal confidence)

        Returns:
            Trade signal dict or None if conditions not met
        """

        htf_df = ohlcv_data.get(htf)
        ltf_df = ohlcv_data.get(ltf)

        if htf_df is None or htf_df.empty:
            logger.warning(f"No {htf} data for {symbol}")
            return None
        if ltf_df is None or ltf_df.empty:
            logger.warning(f"No {ltf} data for {symbol}")
            return None

        # == STEP 4 (early): detect HTF zones first so Location uses zone distals ==
        # First pass without trend so we can derive trend from the data, then
        # we re-score later with trend context.
        htf_zones_provisional = self.zone_detector.detect_zones(htf_df, symbol, htf)

        # == STEP 2: HTF Technical Analysis (uses zone distals when available) ==
        ht_bias = self._analyze_htf(htf_df, htf_zones_provisional)
        trend = ht_bias['trend']
        logger.info(f"[{symbol}] HTF Bias: location={ht_bias['location']}, trend={trend}")

        # Re-score HTF zones with trend context so Q5/Q6 are skipped on
        # trend-aligned setups (textbook rule).
        htf_zones = self.zone_detector.detect_zones(htf_df, symbol, htf, trend=trend)

        # == STEP 3: Fundamental Confirmation ==
        fund_bias = self._analyze_fundamentals(
            cot_df, htf_df, valuation_refs, seasonal_df, asset_class,
            opposing_cot_df=opposing_cot_df,
            symbol=symbol,
        )
        logger.info(f"[{symbol}] Fundamentals: COT={fund_bias['cot']}, Val={fund_bias['valuation']}, Seas={fund_bias['seasonality']}")

        # == STEP 4: LTF Zone Detection + multi-timeframe alignment ==
        ltf_zones = self.zone_detector.detect_zones(ltf_df, symbol, ltf, trend=trend)
        ltf_zones = self.zone_detector.align_multi_timeframe(htf_zones, ltf_zones)
        # Big Brother / Small Brother filter (OTC 2025 L3): tag LTF zones
        # with their HTF parent. Strict mode is opt-in via config since
        # Bernd does take some "no-big-brother" trades when the LTF zone is
        # a clean RBR/DBD with high qualifier scores.
        require_bb = bool(self.config.get('require_big_brother', False))
        ltf_zones = self.zone_detector.filter_by_big_brother(
            ltf_zones, htf_zones, require_coverage=require_bb,
        )
        ranked_zones = self.zone_detector.rank_zones(ltf_zones, min_score=4.0)

        if not ranked_zones:
            logger.info(f"[{symbol}] No qualified zones found")
            return None

        best_zone = ranked_zones[0]
        logger.info(f"[{symbol}] Best zone: {best_zone['zone_type']} at {best_zone['proximal']:.2f}, score={best_zone['composite_score']:.1f}")

        # == Consensus Bias Check ==
        biases = {
            'location': ht_bias['location'],
            'trend': ht_bias['trend'],
            'cot': fund_bias['cot'],
            'valuation': fund_bias['valuation'],
            'seasonality': fund_bias['seasonality']
        }

        consensus = self._bias_consensus(biases, income_strategy, asset_class=asset_class)
        if consensus == 'hold':
            logger.info(f"[{symbol}] Bias consensus insufficient for trade")
            return None

        # Zone direction must match consensus
        zone_dir = 'long' if best_zone['zone_type'] == 'demand' else 'short'
        if (zone_dir == 'long' and consensus == 'bearish') or (zone_dir == 'short' and consensus == 'bullish'):
            logger.info(f"[{symbol}] Zone direction {zone_dir} conflicts with consensus {consensus}")
            return None

        # Phase 6 P1 (Ch 156): equity-index shorts require BOTH retailer-extreme
        # AND Treasury Bond ROC actively rolling negative (not merely positioned).
        # Bernd: "we need the help of other Treasury bonds [to roll over]".
        if zone_dir == 'short' and asset_class == 'equities':
            gate_ok, gate_reason = self._equity_index_short_cross_asset_gate(
                symbol=symbol,
                cot_df=cot_df,
                valuation_refs=valuation_refs,
            )
            if not gate_ok:
                logger.info(f"[{symbol}] Equity-index short cross-asset gate: {gate_reason}")
                return None

        # OTC L5 Decision Matrix (frames 57, 1484): Action = f(zone_type, location, trend)
        # The matrix labels "demand-at-expensive" and "supply-at-cheap" as
        # ANTICIPATORY / COUNTER-TREND setups. Per Hybrid AI Module 4 these
        # are still tradeable -- just with reduced size (0.5% risk) and
        # stronger Valuation alignment required. So we hard-reject only
        # when Valuation does NOT explicitly agree with the zone direction;
        # otherwise we allow the trade and mark it as anticipatory below.
        location  = ht_bias['location']
        in_equil  = ht_bias.get('in_equilibrium', False)
        zone_type = best_zone['zone_type']
        val_bias  = fund_bias.get('valuation', 'neutral')

        # Demand zone at expensive location: needs Valuation bullish to fire
        if zone_type == 'demand' and location == 'bearish':
            if val_bias != 'bullish':
                logger.info(f"[{symbol}] Decision matrix: demand at expensive location AND Val not bullish -> no action")
                return None
            logger.info(f"[{symbol}] Anticipatory reversal: demand at expensive + Val bullish (reduced size)")

        # Supply zone at cheap location: needs Valuation bearish to fire
        if zone_type == 'supply' and location == 'bullish':
            if val_bias != 'bearish':
                logger.info(f"[{symbol}] Decision matrix: supply at cheap location AND Val not bearish -> no action")
                return None
            logger.info(f"[{symbol}] Anticipatory reversal: supply at cheap + Val bearish (reduced size)")

        # Equilibrium + sideways trend on either zone = genuinely no edge
        if in_equil and trend == 'sideways':
            logger.info(f"[{symbol}] Decision matrix: equilibrium + sideways -> no edge, skip")
            return None

        # == STEP 5: Entry Trigger (a candlestick pattern at the zone is required) ==
        pattern_signal = self._check_entry_pattern(ltf_df, best_zone)
        if pattern_signal is None:
            # Fall back to a "zone limit" entry only when the most recent
            # candle is sitting inside the zone -- otherwise the trade is
            # premature and we wait. This honours rule #4 ("never anticipate").
            last = ltf_df.iloc[-1]
            zone_dir_str = best_zone['zone_type']
            in_zone = (
                zone_dir_str == 'demand'
                and last['low']  <= best_zone['proximal']
                and last['low']  >= best_zone['distal']
            ) or (
                zone_dir_str == 'supply'
                and last['high'] >= best_zone['proximal']
                and last['high'] <= best_zone['distal']
            )
            if not in_zone:
                logger.info(f"[{symbol}] Price has not arrived at zone yet -- no signal")
                return None

            # Entry style per textbook Ch 6:
            #   Entry 1 (proximal):  limit at proximal -- always fills, deeper drawdown
            #   Entry 2 (midpoint):  limit at 50% of zone -- better R:R, may miss
            # Default = proximal; flip to midpoint when prefer_midpoint_entry.
            zone_height = abs(best_zone['proximal'] - best_zone['distal'])
            if zone_dir_str == 'demand':
                entry = (best_zone['proximal'] + best_zone['distal']) / 2.0 if prefer_midpoint_entry else best_zone['proximal']
                stop = best_zone['distal'] - 0.33 * zone_height
                direction = 'long'
            else:
                entry = (best_zone['proximal'] + best_zone['distal']) / 2.0 if prefer_midpoint_entry else best_zone['proximal']
                stop = best_zone['distal'] + 0.33 * zone_height
                direction = 'short'
            targets = self._calculate_targets(entry, stop, direction)
        else:
            entry = pattern_signal['entry_price']
            stop = pattern_signal['stop_price']
            direction = 'long' if pattern_signal['direction'] == TradeDirection.LONG else 'short'
            targets = [
                pattern_signal['target_r1'],
                pattern_signal['target_r2'],
                pattern_signal['target_r3']
            ]

        # == STEP 6: Trade Management ==
        # Determine trade context for position-size adjustment.
        # Anticipatory = reversal at extreme location. Counter-trend = zone
        # against HTF trend. Both reduce risk per HAI Module 4 + OTC L5.
        is_with_trend = bool(best_zone.get('with_trend'))
        if not is_with_trend and trend != 'sideways':
            trade_context = 'counter_trend'
        elif in_equil and trend != 'sideways':
            trade_context = 'anticipatory'
        else:
            trade_context = 'standard'
        position_size = self._calculate_position_size(entry, stop, trade_context)

        r_mult_targets = [self.stop_config.get('breakeven_at_r', 1.0),
                         self.stop_config.get('partial_take_r', 2.0),
                         self.stop_config.get('full_take_r', 3.0)]

        # Three textbook entry options (OTC 2025 L7) so the user can pick
        # E1/E2/E3 based on R:R math. The auto-selected entry above remains
        # the default; entry_options are exposed so the dashboard can show
        # all choices side-by-side.
        primary_target = targets[1] if len(targets) >= 2 else targets[0]
        entry_options = self.build_entry_options(best_zone, primary_target, pattern_signal)
        recommended   = self.recommend_entry_option(entry_options, min_rr=2.0)

        # Auto-refine: per OTC L7 frame 1420 + Hybrid AI Mod 6 L6, when the
        # primary entry's R:R is below the methodology threshold, attempt
        # to drill the timeframe ladder for a tighter zone contained inside
        # the HTF zone. The refined zone (if found) replaces the entry as
        # the recommended path.
        refined_zone = None
        if recommended.get('rr', 0) < 2.0:
            try:
                refined_zone = self.refine_zone(
                    best_zone, primary_target, ohlcv_data,
                    income_strategy=income_strategy, min_rr=2.0,
                )
                if refined_zone is not None:
                    refined_options = self.build_entry_options(
                        refined_zone, primary_target, pattern_signal,
                    )
                    refined_rec = self.recommend_entry_option(refined_options, min_rr=2.0)
                    if refined_rec['rr'] > recommended['rr']:
                        logger.info(
                            f"[{symbol}] Refined entry boosted R:R "
                            f"{recommended['rr']:.2f} -> {refined_rec['rr']:.2f}"
                        )
                        entry_options = refined_options
                        recommended   = refined_rec
                        # Update the primary entry/stop to reflect refinement
                        entry = refined_rec['entry']
                        stop  = refined_rec['stop']
                        targets = self._calculate_targets(entry, stop, direction)
            except Exception as e:
                logger.warning(f"Auto-refine failed: {e}")

        # Speed-bump check: opposing zones in the path between current price
        # and entry. Per OTC L6, a qualified opposing zone in the return
        # path will likely stall the trade. We flag but don't auto-reject.
        current_price = float(ltf_df['close'].iloc[-1])
        speed_bumps = self.zone_detector.detect_speed_bumps(
            ltf_zones, best_zone, current_price,
        )
        speed_bump_blocking = self.zone_detector.has_blocking_speed_bump(
            ltf_zones, best_zone, current_price, min_score=5.0,
        )

        # ================================================================
        # Economic Calendar / News Blackout check (audit gap #4)
        # High-impact events (CPI, FOMC, NFP, ECB, BoE) within +/-2h
        # -> reduce risk to 0.5%. Holidays -> full skip.
        # ================================================================
        calendar = get_calendar()
        blackout = calendar.check_blackout()
        calendar_blackout = blackout.to_dict()
        if blackout.in_blackout:
            logger.info(
                f"[{symbol}] Calendar blackout active: {blackout.reason} "
                f"(risk_multiplier={blackout.risk_multiplier})"
            )
            if blackout.risk_multiplier == 0.0:
                return None
            if blackout.risk_multiplier < 1.0:
                position_size *= blackout.risk_multiplier
                logger.info(
                    f"[{symbol}] Calendar blackout: "
                    f"position_size reduced to {position_size:.4f}"
                )

        signal = {
            'symbol': symbol,
            'direction': direction,
            'entry_price': round(entry, 6),
            'stop_price': round(stop, 6),
            'targets': [round(t, 6) for t in targets],
            'entry_options': entry_options,
            'recommended_entry': recommended['label'],
            'speed_bumps': [{'id': sb['id'], 'proximal': sb['proximal'],
                              'distal': sb['distal'], 'score': sb['composite_score']}
                             for sb in speed_bumps[:3]],
            'calendar_blackout': calendar_blackout,
            'speed_bump_warning': speed_bump_blocking,
            'has_big_brother': bool(best_zone.get('has_big_brother')),
            'big_brother_id':  best_zone.get('big_brother_id'),
            'trade_context': trade_context,   # standard / counter_trend / anticipatory
            'zone_id': best_zone['id'],
            'income_strategy': income_strategy,
            'risk_amount': round(abs(entry - stop) * position_size, 2),
            'position_size': round(position_size, 4),
            'r_multiple_targets': r_mult_targets,
            'bias_consensus': biases,
            'qualifier_scores': {
                'departure': best_zone['departure_score'],
                'base_duration': best_zone['base_duration_score'],
                'freshness': best_zone['freshness_score'],
                'originality': best_zone['originality_score'],
                'profit_margin': best_zone['profit_margin_score'],
                'arrival': best_zone['arrival_score'],
                'level_on_top': best_zone['level_on_top_score'],
                'composite': best_zone['composite_score']
            },
            'timestamp': datetime.now().isoformat(),
            'htf': htf,
            'ltf': ltf
        }

        # Monthly roadmap filter (HAI Mod 3 + FT monthly outlooks): tag the
        # signal with the timing-overlay forecast for the current month.
        # Counter-roadmap signals get a warning but aren't auto-rejected.
        try:
            today = datetime.now().date()
            roadmap = build_monthly_roadmap(
                asset=symbol,
                asset_class=asset_class,
                target_month=today,
                seasonality_bias=fund_bias['seasonality'],
                cot_bias=fund_bias['cot'],
                cot_strength=fund_bias.get('cot_strength', 'normal'),
            )
            signal = filter_signal_by_roadmap(signal, roadmap)
        except Exception as e:
            logger.warning(f"Roadmap filter failed: {e}")

        logger.info(f"[{symbol}] SIGNAL: {direction} at {entry:.2f}, stop={stop:.2f}, targets={[round(t,2) for t in targets]}")
        return signal

    def _analyze_htf(
        self, df: pd.DataFrame, htf_zones: Optional[List[Dict]] = None
    ) -> Dict[str, str]:
        """Step 2: HTF Technical Analysis - Location and Trend.

        Location is the proper Blueprint Fib: from the most recent qualified
        demand zone distal (Fib 0) up to the most recent qualified supply zone
        distal (Fib 100). Falls back to the lookback-range approximation only
        when no zones exist yet.
        """
        if 'close' not in df.columns or len(df) < 50:
            return {'location': 'neutral', 'trend': 'sideways'}

        closes = df['close'].values
        highs  = df['high'].values
        lows   = df['low'].values
        current = closes[-1]

        # ---- Preferred: use detected HTF zone distals ----
        range_min = range_max = None
        if htf_zones:
            demand_zones = [z for z in htf_zones if z['zone_type'] == 'demand']
            supply_zones = [z for z in htf_zones if z['zone_type'] == 'supply']
            if demand_zones and supply_zones:
                # Most recent of each (highest origin_index)
                d = max(demand_zones, key=lambda z: z['origin_index'])
                s = max(supply_zones, key=lambda z: z['origin_index'])
                range_min = d['distal']
                range_max = s['distal']

        # ---- Fallback: lookback range ----
        if range_min is None or range_max is None or range_max <= range_min:
            lookback_len = min(200, len(closes))
            range_min = lows[-lookback_len:].min()
            range_max = highs[-lookback_len:].max()

        range_span = range_max - range_min
        location_pct = 50 if range_span <= 0 else (current - range_min) / range_span * 100

        if location_pct <= 33:
            location = 'bullish'
        elif location_pct >= 67:
            location = 'bearish'
        else:
            location = 'neutral'

        trend = self._determine_trend(highs, lows)
        # Per OTC Lesson 3 frames 1887-1901: equilibrium location (33-66%)
        # is "no big brother" territory and degrades zone quality even with
        # HTF coverage. Returned as `location_pct` for downstream scoring.
        return {
            'location': location, 'trend': trend,
            'location_pct': round(location_pct, 1),
            'in_equilibrium': 33 < location_pct < 67,
        }

    def _determine_trend(self, highs: np.ndarray, lows: np.ndarray) -> str:
        """Identify trend using ZigZag pivots (Hybrid AI methodology).

        Per Bernd's course: a pivot is confirmed when price reverses by at
        least the ZigZag percentage from the most recent extreme. The
        previous 5-bar swing rule was over-sensitive on noisy charts.

        ZigZag percentages by timeframe (Hybrid AI defaults):
          Weekly  : ~5%
          Daily   : ~3%
          4H      : ~2%
          1H      : ~1%

        We default to 3% (daily) which is the most common LTF for the
        weekly-income strategy. Override via config.zigzag_percent.
        """
        n = min(200, len(highs))
        if n < 10:
            return 'sideways'

        zz_pct = float(self.config.get('zigzag_percent', 3.0)) / 100.0
        h = highs[-n:]
        l = lows[-n:]

        pivots = self._zigzag_pivots(h, l, zz_pct)
        if len(pivots) < 4:
            return 'sideways'

        # Separate by type and take most recent 3 of each
        swing_highs = [(i, p) for i, p, t in pivots if t == 'H'][-3:]
        swing_lows  = [(i, p) for i, p, t in pivots if t == 'L'][-3:]

        if len(swing_highs) < 2 or len(swing_lows) < 2:
            return 'sideways'

        hh_vals = [p for _, p in swing_highs]
        ll_vals = [p for _, p in swing_lows]

        higher_highs = all(hh_vals[i] > hh_vals[i-1] for i in range(1, len(hh_vals)))
        higher_lows  = all(ll_vals[i] > ll_vals[i-1] for i in range(1, len(ll_vals)))
        lower_highs  = all(hh_vals[i] < hh_vals[i-1] for i in range(1, len(hh_vals)))
        lower_lows   = all(ll_vals[i] < ll_vals[i-1] for i in range(1, len(ll_vals)))

        # OTC Lesson 4 frames 378/466: pivot requirements are ASYMMETRIC.
        # Uptrend = higher LOWS are mandatory ("Required: 2x HL"); higher
        # highs are optional ("not necessarily required"). Downtrend = lower
        # HIGHS are mandatory; lower lows optional. Bernd shows that price
        # can carve a sideways top while higher lows still rise = still an
        # uptrend if HLs are intact.
        if higher_lows:
            return 'uptrend'
        if lower_highs:
            return 'downtrend'
        # Strict-symmetric fallback (legacy): only call out the trend if
        # both legs confirm. Otherwise sideways.
        if higher_highs and higher_lows:
            return 'uptrend'
        if lower_highs and lower_lows:
            return 'downtrend'
        return 'sideways'

    def _zigzag_pivots(self, h: np.ndarray, l: np.ndarray, pct: float) -> List[Tuple[int, float, str]]:
        """ZigZag pivot detection: a pivot is confirmed when price reverses
        by `pct` from the running extreme. Returns chronological list of
        (index, price, 'H'|'L') tuples.
        """
        n = len(h)
        if n < 2:
            return []
        pivots: List[Tuple[int, float, str]] = []
        # Seed direction from first 2 bars
        last_pivot_idx = 0
        last_pivot_val = h[0]
        last_pivot_type = 'H'  # provisional
        # Track extremes since last pivot
        max_idx, max_val = 0, h[0]
        min_idx, min_val = 0, l[0]
        direction = 0  # 0=undetermined, 1=up, -1=down

        for i in range(1, n):
            if h[i] > max_val:
                max_idx, max_val = i, h[i]
            if l[i] < min_val:
                min_idx, min_val = i, l[i]

            if direction >= 0:
                # Looking for a downside reversal from max_val
                if max_val > 0 and (max_val - l[i]) / max_val >= pct:
                    # Confirm a high pivot at max_idx
                    pivots.append((max_idx, max_val, 'H'))
                    last_pivot_idx, last_pivot_val, last_pivot_type = max_idx, max_val, 'H'
                    direction = -1
                    min_idx, min_val = i, l[i]
            if direction <= 0:
                if min_val > 0 and (h[i] - min_val) / min_val >= pct:
                    pivots.append((min_idx, min_val, 'L'))
                    last_pivot_idx, last_pivot_val, last_pivot_type = min_idx, min_val, 'L'
                    direction = 1
                    max_idx, max_val = i, h[i]
        return pivots

    def _indicators_for_class(
        self, asset_class: str, symbol: Optional[str] = None,
    ):
        """Build COT and Valuation engines tuned for the symbol's asset class.

        Per Hybrid AI Mod 3 + Funded Trader live trades:
          - COT: 26w default (Hybrid AI), 52w override for commodities
            (planting/harvest cycle). 156w extreme overlay always on.
          - Valuation ROC ("cycle"): asset-class default (10 / 13) with
            optional per-symbol override from `valuation.cycle_per_symbol`
            in BP_config.yaml. Bernd's "30-day cycle" / "10-day cycle"
            are simply different ROC periods on the same indicator
            (HAI 1:53:38). Per-symbol cheat-sheet style.
        """
        cot_lookback = COT_LOOKBACK_BY_CLASS.get(
            asset_class, self.cot_index.lookback_weeks
        )
        val_length = VALUATION_LENGTH_BY_CLASS.get(
            asset_class, self.valuation.length
        )
        # Per-symbol override (e.g. AAPL=30 daily, NDX=10 daily)
        cycle_overrides = self.config.get('valuation', {}).get('cycle_per_symbol', {}) or {}
        if symbol and symbol in cycle_overrides:
            override = cycle_overrides[symbol]
            if isinstance(override, int):
                val_length = override
            elif isinstance(override, dict):
                val_length = override.get('roc', val_length)

        cot = COTIndex(
            lookback_weeks=cot_lookback,
            upper_extreme=self.cot_index.upper_extreme,
            lower_extreme=self.cot_index.lower_extreme,
        )
        val = Valuation(
            length=val_length,
            rescale_length=self.valuation.rescale_length,
            overvalued=self.valuation.overvalued,
            undervalued=self.valuation.undervalued,
        )
        return cot, val

    def _analyze_fundamentals(
        self,
        cot_df: pd.DataFrame,
        price_df: pd.DataFrame,
        valuation_refs: Dict[str, pd.DataFrame],
        seasonal_df: pd.DataFrame,
        asset_class: str = 'commodities',
        opposing_cot_df: Optional[pd.DataFrame] = None,
        symbol: Optional[str] = None,
    ) -> Dict[str, str]:
        """Step 3: COT, Valuation, Seasonality bias (asset-class aware).

        For forex, an opposing-currency COT (e.g. USD when trading EUR/USD)
        can be passed in -- the EUR-side bias must agree with the inverted
        USD-side bias before we accept it. This honours rule #17 from the
        Blueprint non-negotiables.
        """
        cot_engine, val_engine = self._indicators_for_class(asset_class, symbol=symbol)

        cot_bias = 'neutral'
        cot_strength = 'none'
        cot_cross = None
        if cot_df is not None and not cot_df.empty:
            try:
                cot_calculated = cot_engine.calculate(cot_df)
                cot_bias, cot_strength = cot_engine.get_bias(
                    cot_calculated, asset_class=asset_class, return_strength=True,
                )
                # Cross-category relationship: producer-vs-retailer (smart vs
                # dumb money) and funds-vs-commercials. Per Bernd's teaching,
                # when commercials and retailers are at OPPOSITE extremes
                # simultaneously, that's the highest-conviction signal --
                # promote to strong even if single-category bias was neutral.
                cot_cross = cot_engine.cross_category_signal(cot_calculated)
                if cot_cross.get('extreme_confluence'):
                    smart = cot_cross['smart_vs_dumb']  # 'bullish' or 'bearish'
                    if cot_bias == 'neutral':
                        cot_bias = smart
                    elif cot_bias != smart:
                        # Single-category bias contradicts smart-vs-dumb -> trust
                        # the relational pattern (more reliable per Bernd).
                        logger.info(
                            f"COT smart-vs-dumb ({smart}) overrides single-category ({cot_bias})"
                        )
                        cot_bias = smart
                    cot_strength = 'strong'
                    logger.info(f"COT cross-category extreme confluence: {smart}")
                # For forex, cross-check the opposing currency. Per HAI Mod 3
                # L1 Part 3 (frames 728-983 EUR/USD non-commercial example):
                #   - Both sides agree (inverted) -> DOUBLE CONFIRMED, boost to 'strong'
                #   - One side neutral -> single bias (current strength)
                #   - Both same direction (not inverted) -> CONFLICTING, demote to neutral
                if asset_class == 'forex' and opposing_cot_df is not None and not opposing_cot_df.empty:
                    opp = cot_engine.calculate(opposing_cot_df)
                    opp_bias = cot_engine.get_bias(opp, asset_class='forex')
                    inverted = {'bullish': 'bearish', 'bearish': 'bullish', 'neutral': 'neutral'}[opp_bias]
                    if cot_bias != 'neutral' and opp_bias != 'neutral':
                        if cot_bias == inverted:
                            # Both sides agree directionally -> double confirmation
                            cot_strength = 'strong'
                            logger.info(
                                f"COT double-confirmed via opposing currency (this={cot_bias} "
                                f"opposing-inverted={inverted}); strength=strong"
                            )
                        else:
                            # Both sides in same direction -> conflicting, demote
                            logger.info(
                                f"COT cross-check conflict (this={cot_bias} "
                                f"opposing-inverted={inverted}); demoting to neutral"
                            )
                            cot_bias = 'neutral'
                            cot_strength = 'none'
                if cot_bias != 'neutral':
                    logger.info(f"COT bias={cot_bias} strength={cot_strength}")
            except Exception as e:
                logger.warning(f"COT calculation failed: {e}")

        val_bias = 'neutral'
        if valuation_refs:
            try:
                val_df = val_engine.calculate(price_df, valuation_refs)
                val_bias = val_engine.get_bias(val_df)
            except Exception as e:
                logger.warning(f"Valuation calculation failed: {e}")

        seas_bias = 'neutral'
        if seasonal_df is not None and not seasonal_df.empty:
            try:
                # Use multi-lookback (5y/10y/15y all-must-agree) per textbook
                multi = self.seasonality.calculate_multi(seasonal_df, timeframe='weekly')
                if multi:
                    current_bin = self.seasonality.get_current_bin(price_df, 'weekly')
                    seas_bias = self.seasonality.get_bias_multi(multi, current_bin)
            except Exception as e:
                logger.warning(f"Seasonality calculation failed: {e}")

        return {
            'cot': cot_bias,
            'cot_strength': cot_strength,
            'cot_cross': cot_cross,                # smart_vs_dumb, funds_vs_commercials, extreme_confluence
            'valuation': val_bias,
            'seasonality': seas_bias,
        }

    def _equity_index_short_cross_asset_gate(
        self,
        symbol: str,
        cot_df: Optional[pd.DataFrame],
        valuation_refs: Optional[Dict[str, pd.DataFrame]],
        bond_lookback: int = 13,
    ) -> Tuple[bool, str]:
        """Phase 6 P1 (Ch 156): equity-index shorts require BOTH retailer-extreme
        bullish AND Treasury Bond ROC actively rolling from positive toward
        negative. Either signal alone is insufficient.

        Bernd: "right now I just don't see the short coming. Retailers are
        getting more and more bullish on the weekly... we need the help of
        other Treasury bonds [to roll over]."

        Returns (allowed, reason).
        """
        # FIX Bug 3: COTIndex.calculate is an INSTANCE method, not a static.
        # The original code called COTIndex.calculate(cot_df, lookback_weeks=26, group='retailers')
        # which raises TypeError. Build a proper instance and call it correctly.
        retailers_extreme = False
        if cot_df is not None and not cot_df.empty:
            from BP_indicators import COTIndex
            _cot_engine = COTIndex(lookback_weeks=26, upper_extreme=80, lower_extreme=20)
            cot_calc = _cot_engine.calculate(cot_df)
            if not cot_calc.empty and 'small_specs_index' in cot_calc.columns:
                latest = cot_calc['small_specs_index'].iloc[-1]
                retailers_extreme = bool(latest >= 80)

        # 2. Bond ROC rolling-over check
        bond_rolling = False
        bond_now = bond_prev = None
        if valuation_refs:
            bond_df = valuation_refs.get('ZB') or valuation_refs.get('US') or valuation_refs.get('VD')
            if bond_df is not None and not bond_df.empty and len(bond_df) >= bond_lookback + 5:
                close = bond_df['close']
                # rate-of-change in % vs n bars ago
                roc = (close / close.shift(bond_lookback) - 1) * 100
                bond_now = roc.iloc[-1]
                bond_prev = roc.iloc[-3] if len(roc) > 3 else None
                if bond_now is not None and bond_prev is not None:
                    bond_rolling = bool(bond_now < 0 and bond_prev > 0)

        if retailers_extreme and bond_rolling:
            return True, f"OK -- retailers extreme bullish AND bonds rolling over (ROC {bond_prev:.2f}->{bond_now:.2f})"
        if retailers_extreme:
            return False, "WAIT -- retailers extreme but bonds not yet rolling over"
        if bond_rolling:
            return False, "WAIT -- bonds rolling over but retailers not yet extreme"
        return False, "VETO -- neither retailer-extreme nor bond-rollover signals active"

    def _bias_consensus(
        self, biases: Dict[str, str], income_strategy: str,
        asset_class: Optional[str] = None,
    ) -> str:
        """Synthesize biases into a final directional call.

        For futures (5 votes available — Location, Trend, COT, Valuation,
        Seasonality), the textbook 3-of-5 rule applies.

        For individual stocks (no CFTC COT data, and Bernd's monthly
        roadmaps treat stocks as Valuation-driven per Phase 6 audit),
        Valuation is the primary driver and we never short stocks
        directly. Bernd: "if valuation is undervalued, look for a demand
        zone to buy" — Location/Fib position is NOT part of his stock
        decision tree the way it is for futures.
        """
        val = biases.get('valuation', 'neutral')
        trend = biases.get('trend', 'sideways')

        # Normalise trend's vocabulary ('uptrend'/'downtrend'/'sideways')
        # to the consensus vocabulary ('bullish'/'bearish'/'neutral').
        # This was a silent bug: the trend vote was being ignored entirely
        # because it never matched the literal 'bullish'/'bearish' strings,
        # so what looked like a 5-vote rule was effectively a 4-vote rule.
        normalized = {}
        for k, v in biases.items():
            if v == 'uptrend':
                normalized[k] = 'bullish'
            elif v == 'downtrend':
                normalized[k] = 'bearish'
            elif v == 'sideways':
                normalized[k] = 'neutral'
            else:
                normalized[k] = v

        bullish = sum(1 for v in normalized.values() if v == 'bullish')
        bearish = sum(1 for v in normalized.values() if v == 'bearish')
        # Phase 8 H1 fix: trend contributes to bullish/bearish counts
        # ('uptrend' normalises to 'bullish'). When the safety gate later asks
        # whether non-trend evidence is strong enough to OVERRIDE the trend,
        # it needs a tally that excludes the trend itself -- otherwise the
        # gate's `bullish == 0` clause is mathematically unreachable in any
        # uptrend and shorts can never fire.
        bullish_excl_trend = sum(1 for k, v in normalized.items()
                                 if k != 'trend' and v == 'bullish')
        bearish_excl_trend = sum(1 for k, v in normalized.items()
                                 if k != 'trend' and v == 'bearish')

        # ---- Stocks: Valuation-driven, long-only path -----------------
        # Per Phase 6 audit + CW42-Idx + monthly roadmap process, Bernd
        # treats individual stocks differently from futures:
        #   - NEVER short individual stocks (he uses index futures for that)
        #   - Long when Valuation undervalued, regardless of Fib location
        #   - Trend must not strongly contradict (no longs in clear
        #     downtrend on the analyzed timeframe)
        if asset_class == 'equities':
            if val == 'bullish' and trend != 'downtrend':
                return 'bullish'
            return 'hold'

        # ---- Futures: standard 3-of-N consensus ------------------------
        # SAFETY GATE for prop firm trading: never fire counter-trend signals.
        # Fighting the prevailing trend is the fastest way to blow a daily-loss
        # limit. Bernd does take counter-trend "anticipatory" setups but only
        # with extreme-conviction signals (e.g. fresh 156w COT extreme + zone
        # at extreme location); a mechanical 3-of-5 is not enough to justify
        # fighting the trend on a $100k prop account.
        candidate = None
        if bullish >= 3 and bearish == 0:
            candidate = 'bullish'
        elif bearish >= 3 and bullish == 0:
            candidate = 'bearish'
        elif bullish >= 3 and bullish > bearish:
            candidate = 'bullish'
        elif bearish >= 3 and bearish > bullish:
            candidate = 'bearish'

        # Soft path: Valuation strongly aligned + 1 supporting vote
        if candidate is None:
            if val == 'bullish' and bearish == 0 and bullish >= 2:
                candidate = 'bullish'
            elif val == 'bearish' and bullish == 0 and bearish >= 2:
                candidate = 'bearish'

        if candidate is None:
            return 'hold'

        # Trend safety gate: don't go SHORT in an uptrend or LONG in a downtrend
        # unless non-trend consensus is overwhelming. Old code checked
        # `bullish == 0` against the full tally -- which INCLUDES the trend
        # vote -- making the gate unreachable in any uptrend (bullish >= 1
        # always). Phase 8 H1 fix: check non-trend tally only.
        # Threshold of 3-of-4 non-trend (was 4-of-5 with trend included)
        # preserves the original "overwhelming counter-trend signal" intent
        # without the impossibility bug.
        if candidate == 'bearish' and trend == 'uptrend':
            if bearish_excl_trend >= 3 and bullish_excl_trend == 0:
                return 'bearish'  # overwhelming counter-trend signal
            return 'hold'
        if candidate == 'bullish' and trend == 'downtrend':
            if bullish_excl_trend >= 3 and bearish_excl_trend == 0:
                return 'bullish'
            return 'hold'

        return candidate

    def _check_entry_pattern(self, df: pd.DataFrame, zone: Dict) -> Optional[Dict]:
        """Step 5: Check for candlestick pattern at the zone."""
        zone_type = zone['zone_type']
        proximal = zone['proximal']
        distal = zone['distal']

        # Look at the most recent candles
        for i in range(len(df) - 1, max(0, len(df) - 20), -1):
            candle = df.iloc[i]
            if zone_type == 'demand':
                if candle['low'] <= proximal and candle['low'] >= distal:
                    pattern = self.pattern_detector.detect(df, i, 'demand')
                    if pattern:
                        return pattern
            else:
                if candle['high'] >= proximal and candle['high'] <= distal:
                    pattern = self.pattern_detector.detect(df, i, 'supply')
                    if pattern:
                        return pattern
        return None

    def _calculate_targets(self, entry: float, stop: float, direction: str) -> List[float]:
        """Calculate R-multiple targets."""
        risk = abs(entry - stop)
        if direction == 'long':
            return [entry + risk, entry + 2 * risk, entry + 3 * risk]
        return [entry - risk, entry - 2 * risk, entry - 3 * risk]

    def build_entry_options(
        self,
        zone: Dict,
        target: float,
        pattern_signal: Optional[Dict] = None,
    ) -> List[Dict]:
        """Build the three textbook entry options (OTC 2025 Lesson 7).

        E1 (Proximal)     — limit at proximal, highest fill probability,
                             may have shallower R:R because price often
                             penetrates deeper before reversing.
        E2 (Zone/Midpoint) — limit at 50% of zone, better R:R, fills less
                             often (~50% of the time).
        E3 (Confirmation)  — entry on candlestick pattern that fired inside
                             the zone, lowest fill prob, highest confidence.

        ALL three use the same -33% Fibonacci stop measured from the zone
        distal -- that's the textbook rule. Returns a list of dicts the
        caller can present to the user; the caller picks whichever has
        the best R:R that meets minimum.
        """
        proximal = zone['proximal']
        distal   = zone['distal']
        zone_height = abs(proximal - distal)
        is_demand = zone['zone_type'] == 'demand'
        sign = +1 if is_demand else -1
        stop = distal - sign * 0.33 * zone_height
        direction = 'long' if is_demand else 'short'
        midpoint = (proximal + distal) / 2.0

        def rr(entry):
            risk = abs(entry - stop)
            return abs(target - entry) / risk if risk > 0 else 0.0

        options = [
            {
                'label':      'E1',
                'name':       'Proximal',
                'entry':      round(proximal, 6),
                'stop':       round(stop, 6),
                'direction':  direction,
                'fill_prob':  'high',
                'rr':         round(rr(proximal), 2),
                'note':       'Limit at proximal. Always fills, deeper drawdown possible.',
            },
            {
                'label':      'E2',
                'name':       'Zone (midpoint)',
                'entry':      round(midpoint, 6),
                'stop':       round(stop, 6),
                'direction':  direction,
                'fill_prob':  'medium',
                'rr':         round(rr(midpoint), 2),
                'note':       'Limit at 50% of zone. Better R:R, may not fill on shallow retraces.',
            },
        ]

        if pattern_signal is not None:
            options.append({
                'label':      'E3',
                'name':       f"Confirmation ({pattern_signal.get('pattern_type', 'pattern')})",
                'entry':      round(pattern_signal['entry_price'], 6),
                'stop':       round(pattern_signal['stop_price'], 6),
                'direction':  direction,
                'fill_prob':  'low',
                'rr':         round(rr(pattern_signal['entry_price']), 2),
                'note':       'Wait for candlestick confirmation in zone. Highest confidence.',
            })

        return options

    def recommend_entry_option(
        self, options: List[Dict], min_rr: float = 2.0,
    ) -> Dict:
        """Pick the highest-fill-prob option that meets min R:R; if none
        meet, fall back to the option with the best R:R.
        """
        qualifying = [o for o in options if o['rr'] >= min_rr]
        if not qualifying:
            return max(options, key=lambda o: o['rr'])
        order = {'high': 0, 'medium': 1, 'low': 2}
        return min(qualifying, key=lambda o: order.get(o['fill_prob'], 9))

    # Timeframe drill-down ladder per income strategy (OTC 2025 L3, HAI Mod 6 L6)
    REFINE_LADDER = {
        'monthly':  ['1mo', '1wk', '1d'],
        'weekly':   ['1wk', '1d', '4h', '60m'],
        'daily':    ['1d', '4h', '60m', '30m'],
        'intraday': ['4h', '60m', '30m', '15m'],
    }

    def refine_zone(
        self,
        htf_zone: Dict,
        target: float,
        ohlcv_by_tf: Dict[str, 'pd.DataFrame'],
        income_strategy: str = 'weekly',
        min_rr: float = 2.0,
        max_drill_levels: int = 3,
    ) -> Optional[Dict]:
        """Drill down the timeframe ladder to find a tighter zone CONTAINED
        within the HTF zone (per OTC 2025 L7-L8 + HAI Mod 6 L6).

        Refinement is triggered when the HTF zone's R:R to `target` is below
        `min_rr`. Each refined candidate must:
          1. share direction with the HTF zone
          2. fit entirely inside the HTF zone's price range (containment)
          3. independently pass qualifier checks (composite >= 6.0)

        Returns the deepest valid refined zone dict (with extra `parent_id`
        and `refined_from` fields), or None if no refinement found.

        Stop placement uses LTF distal -33% by default. Caller can override
        with HTF distal for more conservative protection.
        """
        ladder = self.REFINE_LADDER.get(income_strategy, self.REFINE_LADDER['weekly'])
        if htf_zone['timeframe'] not in ladder:
            return None
        htf_idx = ladder.index(htf_zone['timeframe'])
        candidates_levels = ladder[htf_idx + 1 : htf_idx + 1 + max_drill_levels]

        htf_lo = min(htf_zone['proximal'], htf_zone['distal'])
        htf_hi = max(htf_zone['proximal'], htf_zone['distal'])

        best: Optional[Dict] = None
        for tf in candidates_levels:
            df_tf = ohlcv_by_tf.get(tf)
            if df_tf is None or df_tf.empty:
                continue
            ltf_zones = self.zone_detector.detect_zones(
                df_tf, htf_zone['symbol'], tf,
            )
            for z in ltf_zones:
                if z['zone_type'] != htf_zone['zone_type']:
                    continue
                z_lo = min(z['proximal'], z['distal'])
                z_hi = max(z['proximal'], z['distal'])
                if not (z_lo >= htf_lo and z_hi <= htf_hi):
                    continue
                if z['composite_score'] < 6.0:
                    continue
                # Stop = LTF distal -33% (textbook default)
                zh = abs(z['proximal'] - z['distal'])
                sign = +1 if z['zone_type'] == 'demand' else -1
                stop = z['distal'] - sign * 0.33 * zh
                risk = abs(z['proximal'] - stop)
                rr   = abs(target - z['proximal']) / risk if risk > 0 else 0.0
                if rr < min_rr:
                    continue
                # Track the best (highest R:R) candidate
                if best is None or rr > best['_rr']:
                    refined = dict(z)
                    refined['parent_id']    = htf_zone['id']
                    refined['refined_from'] = htf_zone['timeframe']
                    refined['refined_stop'] = round(stop, 6)
                    refined['_rr']          = rr
                    best = refined

        if best is not None:
            best.pop('_rr', None)
            logger.info(
                f"[{htf_zone['symbol']}] zone refined {htf_zone['timeframe']}->{best['timeframe']} "
                f"score={best['composite_score']:.1f} entry={best['proximal']:.4f}"
            )
        return best

    # ------------------------------------------------------------------
    # Zone-quality grade — visually confirmed in frame_001154 (CW10
    # student trade-review popup, "10 out of 10" rating). Five binary
    # checks, 2 points each. NOTE: this is ZONE QUALITY only, not the
    # full trade grade — fundamentals stack on top of this. A zone can
    # be 10/10 structurally and still lack COT/Valuation alignment.
    # ------------------------------------------------------------------
    @staticmethod
    def zone_quality_grade(zone: Dict) -> Dict:
        """5-item zone-quality checklist from the visually-verified popup.

        Returns dict with keys: grade, score, checklist (per-item bool),
        where grade ∈ {'10/10', '8-9/10', '5-7/10', '<5/10'}.
        """
        # 1) Layout: decisive leg-out (Q1 Departure passing => decisive)
        decisive_layout = bool(zone.get('q1_score', 0) >= 7)
        # 2) Freshness: zone never preferred-tested
        is_fresh = bool(zone.get('q3_score', 0) >= 8)
        # 3) Base duration: 1-2 candle base
        base_count = zone.get('base_candle_count') or zone.get('base_count') or 0
        base_short = base_count <= 2 and base_count >= 1
        # 4) Big Brother / Small Brother match
        has_big_brother = bool(zone.get('has_big_brother', False))
        # 5) CF Direction: clean arrival / departure (Q6 Arrival or
        #    'with_trend' alignment).
        clean_arrival = bool(zone.get('q6_score', 0) >= 7 or zone.get('with_trend', False))

        checklist = {
            'layout_decisive':  decisive_layout,
            'fresh':            is_fresh,
            'base_duration':    base_short,
            'big_brother':      has_big_brother,
            'cf_direction':     clean_arrival,
        }
        score = 2 * sum(checklist.values())  # 0..10
        if score >= 10:
            grade = '10/10'
        elif score >= 8:
            grade = '8-9/10'
        elif score >= 5:
            grade = '5-7/10'
        else:
            grade = '<5/10'
        return {'grade': grade, 'score': score, 'checklist': checklist}

    # ------------------------------------------------------------------
    # Action-matrix tier grading — stage-1 text-confirmed (OTC L4 slide,
    # Bernd: "this is our action matrix to simplify everything"). Hard
    # rejection of the "No Action" cell is already done elsewhere; this
    # method emits the soft-tier grade so position size can scale.
    # ------------------------------------------------------------------
    @staticmethod
    def action_matrix_grade(
        zone_type: str, location: str, trend: str,
    ) -> str:
        """Returns 'best' | 'good' | 'acceptable' | 'reject'.

        location ∈ {'very_cheap','cheap','equilibrium','expensive','very_expensive'}
        trend    ∈ {'uptrend','downtrend','sideways'}
        zone_type∈ {'demand','supply'}
        """
        z = zone_type.lower()
        loc = location.lower()
        tr = trend.lower()
        # Demand setups
        if z == 'demand':
            if loc in ('cheap', 'very_cheap') and tr == 'uptrend':
                return 'best'
            if tr == 'uptrend':
                return 'good'                    # trend aligned, location not extreme
            if loc in ('cheap', 'very_cheap') and tr == 'sideways':
                return 'acceptable'              # location aligned, trend sideways
            return 'reject'
        # Supply setups
        if z == 'supply':
            if loc in ('expensive', 'very_expensive') and tr == 'downtrend':
                return 'best'
            if tr == 'downtrend':
                return 'good'
            if loc in ('expensive', 'very_expensive') and tr == 'sideways':
                return 'acceptable'
            return 'reject'
        return 'reject'

    # Position-size multiplier per action-matrix tier (counter to risk_pct
    # reduction for counter-trend; this multiplier scales the BASE risk).
    ACTION_TIER_SIZE_FACTOR = {
        'best':       1.0,
        'good':       0.75,
        'acceptable': 0.5,
        'reject':     0.0,
    }

    # ------------------------------------------------------------------
    # Correlation-aware exposure caps (HAI 1:19:29 + Funded 0:16:46).
    # When an open position exists in any group, new signals on
    # other members of the same group are rejected (or downgraded
    # depending on caller policy).
    # ------------------------------------------------------------------
    DEFAULT_CORRELATED_GROUPS = [
        # Forex — heavy USD-correlated
        ['EURUSD', 'GBPUSD', 'AUDUSD', 'NZDUSD', 'USDCHF'],   # USD axis
        ['EURUSD', 'EURGBP', 'EURJPY', 'EURCHF'],             # EUR axis
        ['USDCHF', 'EURCHF', 'GBPCHF'],                       # CHF axis
        # Equity indices
        ['ES=F', 'NQ=F', 'YM=F', 'RTY=F', 'SPY', 'QQQ'],
        # Precious metals
        ['GC=F', 'SI=F', 'GLD', 'SLV'],
        # Energy
        ['CL=F', 'NG=F', 'USO', 'UNG'],
    ]

    def is_correlated_to_open(
        self, candidate_symbol: str, open_symbols: List[str],
    ) -> Optional[List[str]]:
        """Return the offending peer symbols if `candidate_symbol` is in any
        correlated group with any currently-open symbol; else None.
        """
        groups = self.config.get('correlated_groups', self.DEFAULT_CORRELATED_GROUPS)
        s = candidate_symbol.upper().replace('/', '')
        norm_open = [o.upper().replace('/', '') for o in open_symbols]
        offenders: List[str] = []
        for grp in groups:
            grp_u = [g.upper().replace('/', '') for g in grp]
            if s in grp_u:
                offenders.extend([o for o in norm_open if o != s and o in grp_u])
        return offenders or None

    def _calculate_position_size(
        self, entry: float, stop: float, trade_context: str = 'standard',
    ) -> float:
        """Calculate position size based on fixed fractional risk.

        Context-adjusted (HAI Module 4 + OTC L5 Decision Matrix):
          - 'standard' / with-trend setups : full risk (default 1%)
          - 'counter_trend'                : reduced (0.5% default)
          - 'anticipatory'                 : reduced (0.5% default)
        """
        balance = self.risk_config.get('account_balance', 100000)
        risk_pct = self.risk_config.get('risk_per_trade_pct', 1.0) / 100
        if trade_context in ('counter_trend', 'anticipatory'):
            reduced_pct = self.risk_config.get('reduced_risk_pct', risk_pct * 50) / 100
            # Allow either an absolute pct (e.g., 0.5) or a multiplier
            if reduced_pct < 0.05:  # treat as fraction-of-risk multiplier
                risk_pct *= reduced_pct * 100
            else:
                risk_pct = reduced_pct
        risk_amount = balance * risk_pct
        stop_distance = abs(entry - stop)
        if stop_distance == 0:
            return 0
        return risk_amount / stop_distance
