"""Monthly / Quarterly / Yearly roadmap.

Per Hybrid AI Module 3 (HAI 1:56:13) and Funded Trader monthly outlooks
(FT 02.12.2023 [0:00:32]): the roadmap is a TIMING-OVERLAY that tells you
WHEN to be a buyer/seller across the year. It is NOT a signal generator;
it is a filter that suppresses counter-roadmap entries and amplifies
aligned ones.

Components combined per Bernd's process:
    1. Long-term seasonality (5y/10y/15y) -- already calculated by
       BP_indicators.Seasonality
    2. Presidential cycle (4-year, equities only)
    3. Sannial / decennial cycle (10-year, equities only)
    4. COT positioning (commercials extreme alignment)

Static cycle tables come from Stock Trader's Almanac data referenced in
the Funded Trader sessions. They are best-effort reconstructions; expose
to the user for override.

Usage:
    from BP_roadmap import build_monthly_roadmap, filter_signal_by_roadmap
    rm = build_monthly_roadmap('ES=F', 'equity_indices', date(2026, 5, 1),
                               cycle_year_in_pres_cycle=3, seasonality_bias='bullish',
                               cot_bias='bullish')
    signal = filter_signal_by_roadmap(signal, rm)
"""

from dataclasses import dataclass, field, asdict
from datetime import date
from typing import Dict, List, Optional


# =====================================================================
# Static cycle tables (Stock Trader's Almanac references in FT sessions)
# =====================================================================

# Presidential cycle: month-by-month bias for stocks (S&P 500 average, 1950-).
# Index 0 = post-election (year 1), 1 = mid-term, 2 = pre-election, 3 = election.
# 12-element list per year: bias for January..December where +1=bullish, 0=neutral, -1=bearish.
# Pre-election years (year 3) are historically the most bullish across all 12 months.
PRESIDENTIAL_CYCLE_BIAS: Dict[int, List[int]] = {
    1: [-1,  0,  0, +1, +1,  0,  0, -1, -1,  0, +1, +1],  # post-election
    2: [ 0, -1, -1,  0, +1,  0, -1, -1, -1,  0,  0, +1],  # mid-term
    3: [+1, +1, +1, +1, +1, +1,  0,  0, +1, +1, +1, +1],  # pre-election (best year)
    0: [ 0,  0,  0, +1, +1,  0, -1, -1,  0, +1, +1,  0],  # election year (volatile)
}

# Sannial decennial cycle bias for equities (last digit of year).
# 1, 5, 9 historically poor; 3, 7, 8 historically strong.
SANNIAL_CYCLE_BIAS: Dict[int, int] = {
    0: 0, 1: -1, 2: 0, 3: +1, 4: 0, 5: -1, 6: 0, 7: +1, 8: +1, 9: -1,
}


# =====================================================================
# Data model
# =====================================================================

@dataclass
class RoadmapEntry:
    """A roadmap forecast for one (asset, period)."""
    asset: str
    asset_class: str
    granularity: str               # 'yearly' | 'quarterly' | 'monthly'
    period_start: str              # ISO date
    period_end: str                # ISO date
    bias: str                      # 'buy' | 'sell' | 'neutral'
    confidence: float              # 0.0 - 1.0
    components: Dict[str, str] = field(default_factory=dict)
    note: str = ''

    def to_dict(self) -> Dict:
        return asdict(self)


# =====================================================================
# Construction
# =====================================================================

def _is_equity(asset_class: str) -> bool:
    return asset_class in ('equities', 'equity_indices')


def cycle_year_in_pres_cycle(year: int) -> int:
    """Year-in-cycle relative to US presidential elections.
       2024 = election (0), 2025 = post (1), 2026 = mid (2), 2027 = pre (3).
       Adjust the anchor if needed -- the textbook uses 1992 as a known election year.
    """
    return (year - 1992) % 4


def _month_bias_components(
    asset_class: str,
    target_year: int,
    target_month: int,
    seasonality_bias: str,
    cot_bias: str,
    cot_strength: str = 'normal',
) -> Dict[str, str]:
    """Compute the per-component biases for a given month."""
    components: Dict[str, str] = {}

    # 1. Seasonality (already calculated upstream)
    components['seasonality'] = seasonality_bias

    # 2. Presidential cycle (equities only)
    if _is_equity(asset_class):
        cycle_year = cycle_year_in_pres_cycle(target_year)
        pres_table = PRESIDENTIAL_CYCLE_BIAS.get(cycle_year, [0]*12)
        pres_score = pres_table[target_month - 1]
        components['presidential'] = (
            'bullish' if pres_score > 0 else 'bearish' if pres_score < 0 else 'neutral'
        )
    else:
        components['presidential'] = 'n/a'

    # 3. Sannial / decennial cycle (equities)
    if _is_equity(asset_class):
        sann_score = SANNIAL_CYCLE_BIAS.get(target_year % 10, 0)
        components['sannial'] = (
            'bullish' if sann_score > 0 else 'bearish' if sann_score < 0 else 'neutral'
        )
    else:
        components['sannial'] = 'n/a'

    # 4. COT positioning (passed in)
    components['cot'] = cot_bias
    components['cot_strength'] = cot_strength

    return components


def build_monthly_roadmap(
    asset: str,
    asset_class: str,
    target_month: date,
    seasonality_bias: str = 'neutral',
    cot_bias: str = 'neutral',
    cot_strength: str = 'normal',
) -> RoadmapEntry:
    """Build a monthly roadmap entry for an asset.

    Args:
        asset:           e.g. 'ES=F', 'GC=F'
        asset_class:     e.g. 'equity_indices', 'commodities', 'forex', ...
        target_month:    first-of-month date for the period
        seasonality_bias / cot_bias: 'bullish' | 'bearish' | 'neutral'
                          (computed upstream by BP_indicators)
        cot_strength:    'strong' | 'normal' | 'none' from COTIndex.get_bias

    Returns RoadmapEntry with combined bias and confidence.
    """
    from calendar import monthrange

    components = _month_bias_components(
        asset_class, target_month.year, target_month.month,
        seasonality_bias, cot_bias, cot_strength,
    )

    # Voting: collect directional components only
    votes = [v for k, v in components.items()
             if k != 'cot_strength' and v in ('bullish', 'bearish', 'neutral')]
    bull = sum(1 for v in votes if v == 'bullish')
    bear = sum(1 for v in votes if v == 'bearish')
    total_votes = len([v for v in votes if v != 'neutral']) or 1

    # Strong COT alone can flip the bias even if other inputs are neutral
    strong_cot = (cot_strength == 'strong' and cot_bias != 'neutral')

    if bull >= 2 and bull > bear:
        bias = 'buy'
    elif bear >= 2 and bear > bull:
        bias = 'sell'
    elif strong_cot:
        bias = 'buy' if cot_bias == 'bullish' else 'sell'
    else:
        bias = 'neutral'

    confidence = max(bull, bear) / max(total_votes, 1)
    if strong_cot:
        confidence = max(confidence, 0.75)

    last_day = monthrange(target_month.year, target_month.month)[1]
    return RoadmapEntry(
        asset=asset,
        asset_class=asset_class,
        granularity='monthly',
        period_start=target_month.replace(day=1).isoformat(),
        period_end=target_month.replace(day=last_day).isoformat(),
        bias=bias,
        confidence=round(confidence, 2),
        components=components,
        note=(
            'Auto-generated from seasonality + presidential + sannial + COT. '
            'Override via user dashboard for bespoke calls.'
        ),
    )


def filter_signal_by_roadmap(
    signal: Dict, roadmap: RoadmapEntry,
) -> Dict:
    """Apply roadmap as a filter on a generated signal.

    - Same direction as roadmap: confidence boosted, signal tagged 'aligned'.
    - Opposite to roadmap (and roadmap not neutral): signal suppressed.
    - Roadmap neutral: signal passes through unchanged.

    Mutates and returns `signal`.
    """
    sig_dir = signal.get('direction', '')
    rm_bias = roadmap.bias
    if rm_bias == 'neutral' or sig_dir not in ('long', 'short'):
        signal['roadmap'] = roadmap.to_dict()
        signal['roadmap_aligned'] = None
        return signal

    aligned = (sig_dir == 'long' and rm_bias == 'buy') or \
              (sig_dir == 'short' and rm_bias == 'sell')

    signal['roadmap'] = roadmap.to_dict()
    signal['roadmap_aligned'] = aligned
    if not aligned:
        # Don't drop the signal outright -- mark it for the user to decide.
        # Bernd does take counter-roadmap trades in extreme location +
        # high-conviction COT, but they are reduced size.
        signal['roadmap_warning'] = (
            f'Counter to {roadmap.granularity} roadmap ({rm_bias}). '
            f'Consider reducing position size or skipping.'
        )
    return signal
