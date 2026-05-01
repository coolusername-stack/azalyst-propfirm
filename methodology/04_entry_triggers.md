# Entry Triggers — Candlestick Patterns at Zones

## CRITICAL RULE

**Candlestick patterns are ONLY valid when they form AT a qualified supply or demand zone.** A hammer in the middle of nowhere is noise. A hammer at a fresh, high-scoring demand zone is a trade trigger.

If a pattern forms outside of any zone's proximal-to-distal range, **ignore it completely**.

---

## Pattern + Zone Alignment Rules

| Pattern | Valid At | Signal |
|---------|---------|--------|
| Hammer | DEMAND zone only | Bullish — long entry |
| Bullish Engulfing | DEMAND zone only | Bullish — long entry |
| Inverse Head & Shoulders | DEMAND zone only | Bullish — long entry |
| Shooting Star | SUPPLY zone only | Bearish — short entry |
| Hanging Man | SUPPLY zone only | Bearish — short entry |
| Bearish Engulfing | SUPPLY zone only | Bearish — short entry |
| Head & Shoulders | SUPPLY zone only | Bearish — short entry |

### Zone Contact Validation

```python
def pattern_at_zone(pattern, zones):
    """
    Check if a candlestick pattern formed within a qualified zone.
    
    Args:
        pattern: detected pattern with high, low, candle data
        zones: list of active qualified zones
    
    Returns:
        Zone object if pattern touches a zone, None otherwise
    """
    for zone in zones:
        if not zone.is_valid:
            continue
        
        if zone.zone_type == "demand":
            # Pattern low must touch or penetrate the zone
            if pattern.low <= zone.proximal and pattern.low >= zone.distal:
                return zone
        else:  # supply
            # Pattern high must touch or penetrate the zone
            if pattern.high >= zone.proximal and pattern.high <= zone.distal:
                return zone
    
    return None  # Pattern not at any zone — IGNORE
```

---

## Pattern Detection Formulas

### Hammer (Bullish — at DEMAND Zone)

A single candle with a small body near the top and a long lower wick, showing rejection of lower prices.

```python
def detect_hammer(candle):
    """
    Detect a hammer candlestick pattern.
    
    Geometry:
    - Small body (top 30% of range)
    - Long lower wick (>= 2x body)
    - Little to no upper wick (<= 10% of range)
    - Green (close > open) preferred but not required
    
    Returns:
        dict with valid flag and metadata
    """
    body = abs(candle.close - candle.open)
    range_size = candle.high - candle.low
    
    if range_size == 0:
        return {"valid": False}
    
    body_pct = body / range_size
    lower_wick = min(candle.open, candle.close) - candle.low
    upper_wick = candle.high - max(candle.open, candle.close)
    
    valid = (
        body_pct <= 0.30 and                    # Small body
        lower_wick >= 2 * body and               # Long lower wick (2x+ body)
        upper_wick <= 0.10 * range_size and      # Tiny or no upper wick
        body > 0                                  # Not a pure doji
    )
    
    is_bullish_body = candle.close >= candle.open  # Green preferred
    
    return {
        "valid": valid,
        "pattern": "hammer",
        "signal": "bullish",
        "valid_at": "demand",
        "body_pct": body_pct,
        "lower_wick_ratio": lower_wick / body if body > 0 else 0,
        "bullish_body": is_bullish_body,
        "pattern_high": candle.high,
        "pattern_low": candle.low
    }
```

---

### Shooting Star (Bearish — at SUPPLY Zone)

A single candle with a small body near the bottom and a long upper wick, showing rejection of higher prices. Mirror image of the hammer.

```python
def detect_shooting_star(candle):
    """
    Detect a shooting star candlestick pattern.
    
    Geometry:
    - Small body (bottom 30% of range)
    - Long upper wick (>= 2x body)
    - Little to no lower wick (<= 10% of range)
    - Red (close < open) preferred but not required
    """
    body = abs(candle.close - candle.open)
    range_size = candle.high - candle.low
    
    if range_size == 0:
        return {"valid": False}
    
    body_pct = body / range_size
    upper_wick = candle.high - max(candle.open, candle.close)
    lower_wick = min(candle.open, candle.close) - candle.low
    
    valid = (
        body_pct <= 0.30 and                    # Small body
        upper_wick >= 2 * body and               # Long upper wick (2x+ body)
        lower_wick <= 0.10 * range_size and      # Tiny or no lower wick
        body > 0                                  # Not a pure doji
    )
    
    is_bearish_body = candle.close <= candle.open  # Red preferred
    
    return {
        "valid": valid,
        "pattern": "shooting_star",
        "signal": "bearish",
        "valid_at": "supply",
        "body_pct": body_pct,
        "upper_wick_ratio": upper_wick / body if body > 0 else 0,
        "bearish_body": is_bearish_body,
        "pattern_high": candle.high,
        "pattern_low": candle.low
    }
```

---

### Hanging Man (Bearish — at SUPPLY Zone)

**SAME geometry as a Hammer** but appears at a SUPPLY zone instead of a demand zone. Context changes the meaning entirely.

```python
def detect_hanging_man(candle):
    """
    Detect a hanging man candlestick pattern.
    
    Identical geometry to hammer:
    - Small body near top
    - Long lower wick (>= 2x body)
    - Tiny upper wick
    
    BUT appears at a SUPPLY zone = BEARISH signal.
    The long lower wick shows buying pressure failed to hold.
    """
    body = abs(candle.close - candle.open)
    range_size = candle.high - candle.low
    
    if range_size == 0:
        return {"valid": False}
    
    body_pct = body / range_size
    lower_wick = min(candle.open, candle.close) - candle.low
    upper_wick = candle.high - max(candle.open, candle.close)
    
    valid = (
        body_pct <= 0.30 and
        lower_wick >= 2 * body and
        upper_wick <= 0.10 * range_size and
        body > 0
    )
    
    return {
        "valid": valid,
        "pattern": "hanging_man",
        "signal": "bearish",
        "valid_at": "supply",  # Same shape as hammer but at supply = bearish
        "body_pct": body_pct,
        "pattern_high": candle.high,
        "pattern_low": candle.low
    }
```

---

### Bullish Engulfing (at DEMAND Zone)

A two-candle pattern where the second (bullish) candle completely engulfs the first (bearish) candle's body.

```python
def detect_bullish_engulfing(prev_candle, curr_candle):
    """
    Detect a bullish engulfing pattern.
    
    Requirements:
    1. Previous candle must be bearish (red)
    2. Current candle must be bullish (green)
    3. Current candle opens at or below previous close
    4. Current candle closes above previous open (engulfs body)
    5. Current candle takes out prior low
    """
    prev = prev_candle
    curr = curr_candle
    
    valid = (
        prev.close < prev.open and            # Prior candle is bearish
        curr.close > curr.open and             # Current candle is bullish
        curr.open <= prev.close and            # Opens at/below prior close
        curr.close > prev.open and             # Closes above prior open (engulfs body)
        curr.low <= prev.low                   # Takes out prior low (liquidity grab)
    )
    
    return {
        "valid": valid,
        "pattern": "bullish_engulfing",
        "signal": "bullish",
        "valid_at": "demand",
        "pattern_high": max(prev.high, curr.high),
        "pattern_low": min(prev.low, curr.low),
        "engulfing_candle": curr,
        "engulfed_candle": prev
    }
```

---

### Bearish Engulfing (at SUPPLY Zone)

A two-candle pattern where the second (bearish) candle completely engulfs the first (bullish) candle's body.

```python
def detect_bearish_engulfing(prev_candle, curr_candle):
    """
    Detect a bearish engulfing pattern.
    
    Requirements:
    1. Previous candle must be bullish (green)
    2. Current candle must be bearish (red)
    3. Current candle opens at or above previous close
    4. Current candle closes below previous open (engulfs body)
    5. Current candle takes out prior high
    """
    prev = prev_candle
    curr = curr_candle
    
    valid = (
        prev.close > prev.open and            # Prior candle is bullish
        curr.close < curr.open and             # Current candle is bearish
        curr.open >= prev.close and            # Opens at/above prior close
        curr.close < prev.open and             # Closes below prior open (engulfs body)
        curr.high >= prev.high                 # Takes out prior high (liquidity grab)
    )
    
    return {
        "valid": valid,
        "pattern": "bearish_engulfing",
        "signal": "bearish",
        "valid_at": "supply",
        "pattern_high": max(prev.high, curr.high),
        "pattern_low": min(prev.low, curr.low),
        "engulfing_candle": curr,
        "engulfed_candle": prev
    }
```

---

### Head & Shoulders (Trend Reversal — Bearish at SUPPLY)

A three-peak structure where the middle peak (head) is the highest, flanked by two lower peaks (shoulders). The neckline connects the two troughs between the peaks.

```python
def detect_head_and_shoulders(candle_data, lookback=20):
    """
    Detect Head & Shoulders pattern.
    
    Structure:
    - Left shoulder: first peak
    - Head: middle peak (highest)
    - Right shoulder: third peak (approximately equal to left shoulder)
    - Neckline: line connecting the two troughs
    - Break below neckline = bearish confirmation
    
    Returns:
        dict with pattern details or None
    """
    peaks = find_swing_highs(candle_data[-lookback:])
    troughs = find_swing_lows(candle_data[-lookback:])
    
    if len(peaks) < 3 or len(troughs) < 2:
        return None
    
    left_shoulder = peaks[-3]
    head = peaks[-2]
    right_shoulder = peaks[-1]
    trough_1 = troughs[-2]
    trough_2 = troughs[-1]
    
    # Head must be highest
    if not (head["value"] > left_shoulder["value"] and 
            head["value"] > right_shoulder["value"]):
        return None
    
    # Shoulders should be approximately equal (within 5% of head height)
    head_height = head["value"] - min(trough_1["value"], trough_2["value"])
    shoulder_diff = abs(left_shoulder["value"] - right_shoulder["value"])
    if shoulder_diff > 0.05 * head_height:
        return None  # Shoulders too asymmetric
    
    # Calculate neckline
    neckline_slope = ((trough_2["value"] - trough_1["value"]) / 
                      (trough_2["index"] - trough_1["index"]))
    neckline_at_current = trough_2["value"] + neckline_slope * (
        len(candle_data) - 1 - trough_2["index"])
    
    # Check for neckline break
    current_close = candle_data[-1].close
    neckline_broken = current_close < neckline_at_current
    
    return {
        "valid": True,
        "pattern": "head_and_shoulders",
        "signal": "bearish",
        "valid_at": "supply",
        "left_shoulder": left_shoulder,
        "head": head,
        "right_shoulder": right_shoulder,
        "neckline_value": neckline_at_current,
        "neckline_broken": neckline_broken,
        "pattern_high": head["value"],
        "pattern_low": min(trough_1["value"], trough_2["value"])
    }
```

### Inverse Head & Shoulders (Bullish at DEMAND)

Exact mirror: three troughs with the middle (head) being the lowest. Break above the neckline = bullish.

```python
def detect_inverse_head_and_shoulders(candle_data, lookback=20):
    """
    Mirror of H&S: three troughs, middle lowest.
    Break above neckline = bullish confirmation.
    """
    troughs = find_swing_lows(candle_data[-lookback:])
    peaks = find_swing_highs(candle_data[-lookback:])
    
    if len(troughs) < 3 or len(peaks) < 2:
        return None
    
    left_shoulder = troughs[-3]
    head = troughs[-2]
    right_shoulder = troughs[-1]
    peak_1 = peaks[-2]
    peak_2 = peaks[-1]
    
    # Head must be lowest
    if not (head["value"] < left_shoulder["value"] and 
            head["value"] < right_shoulder["value"]):
        return None
    
    neckline_slope = ((peak_2["value"] - peak_1["value"]) / 
                      (peak_2["index"] - peak_1["index"]))
    neckline_at_current = peak_2["value"] + neckline_slope * (
        len(candle_data) - 1 - peak_2["index"])
    
    current_close = candle_data[-1].close
    neckline_broken = current_close > neckline_at_current
    
    return {
        "valid": True,
        "pattern": "inverse_head_and_shoulders",
        "signal": "bullish",
        "valid_at": "demand",
        "neckline_value": neckline_at_current,
        "neckline_broken": neckline_broken,
        "pattern_high": max(peak_1["value"], peak_2["value"]),
        "pattern_low": head["value"]
    }
```

---

## Entry Options — Full Set (E1 through E4)

All zones support the following entry strategies. E1–E3 are the three textbook-sanctioned options (OTC L7). E3b, E3c, and E4 are sub-types and advanced options identified in the Funded Trader corpus.

### E1: Proximal Limit Order (~99% Fill Rate)

Place a stop order slightly beyond the pattern's extreme. Highest fill probability but worst entry price.

```python
def entry_option_1(pattern, zone, tick_size=0.0001):
    """
    E1: Limit order at or slightly beyond proximal line.
    ~99% fill rate. Worst entry price.
    
    Args:
        pattern: detected pattern dict
        zone: the qualified zone
        tick_size: minimum price increment for the instrument
    """
    buffer = 2 * tick_size  # Small buffer beyond extreme
    
    if pattern["signal"] == "bullish":
        entry = pattern["pattern_high"] + buffer    # Buy stop above high
        stop = calculate_stop_long(pattern)
    else:
        entry = pattern["pattern_low"] - buffer     # Sell stop below low
        stop = calculate_stop_short(pattern)
    
    return {"entry": entry, "stop": stop, "option": 1, "fill_probability": 0.99}
```

### E2: Midpoint / Within Pattern Range (~50% Fill Rate)

Place a limit order within the pattern's range for a better entry price. May not fill if price does not retrace.

```python
def entry_option_2(pattern, zone):
    """
    E2: Limit order at midpoint of zone (or pattern range).
    ~50% fill rate. Better entry price.
    """
    pattern_range = pattern["pattern_high"] - pattern["pattern_low"]
    
    if pattern["signal"] == "bullish":
        # Enter at 50% of pattern range (midpoint)
        entry = pattern["pattern_low"] + 0.50 * pattern_range
        stop = calculate_stop_long(pattern)
    else:
        entry = pattern["pattern_high"] - 0.50 * pattern_range
        stop = calculate_stop_short(pattern)
    
    return {"entry": entry, "stop": stop, "option": 2, "fill_probability": 0.50}
```

### Entry-Sliding for Required R:R (Phase 6, Ch 183)

If the proximal entry yields R:R below the 1:2 minimum, the entry can **slide deeper into the zone** (toward distal) until R:R ≥ 2 — capped at the **midpoint (E2)**. Bernd: *"Show me your profit margin… we could move our entry to the downside till we have the 4:1 on your level"*.

```python
def slide_entry_for_rrr(zone, target, stop, min_rrr=2.0, direction="long"):
    """
    Slide entry from proximal toward midpoint until R:R >= min_rrr.
    Capped at midpoint (deeper than that = use E2 outright).
    Returns (entry_price, achieved_rrr) or (None, None) if even midpoint fails.
    """
    midpoint = (zone.proximal + zone.distal) / 2
    if direction == "long":
        # Demand: distal < proximal; sliding entry DOWN gets closer to stop, but more reward distance
        for fraction in [0.0, 0.10, 0.20, 0.30, 0.40, 0.50]:
            entry = zone.proximal - fraction * (zone.proximal - zone.distal)
            risk = entry - stop
            reward = target - entry
            if risk > 0 and reward / risk >= min_rrr:
                return entry, reward / risk
        return None, None
    else:
        for fraction in [0.0, 0.10, 0.20, 0.30, 0.40, 0.50]:
            entry = zone.proximal + fraction * (zone.distal - zone.proximal)
            risk = stop - entry
            reward = entry - target
            if risk > 0 and reward / risk >= min_rrr:
                return entry, reward / risk
        return None, None
```

This is a **sanctioned technique**, not a workaround — sliding past the midpoint is not allowed (use E3a/E3b/E3c instead at that point).

### Order Placement Asymmetry — Buffer for Fill (Phase 6, Ch 179)

Practical execution micro-rule: place entry **slightly inside** the proximal (a few ticks) to maximise fill probability, and adjust the stop **symmetrically** the same distance. Bernd: *"a little bit higher to be sure to be filled and the same plus and minus for your stop loss"*.

```python
def buffered_entry_and_stop(proximal, distal_or_stop, tick_size, buffer_ticks=2, direction="long"):
    """
    Buffer entry inside the zone for fill, shift stop symmetrically.
    Net R:R is unchanged; only fill rate improves.
    """
    buf = buffer_ticks * tick_size
    if direction == "long":
        return proximal + buf, distal_or_stop + buf  # both shifted up by `buf`
    return proximal - buf, distal_or_stop - buf
```

Net R:R is unchanged because both entry and stop shift in the same direction by the same amount; only fill probability improves.

### Multi-Bar Pattern Repetition — Strengthened Signal (Phase 6, Ch 181)

A **single** reversal candle (e.g. one weekly hanging man) is a standard signal. **Two or more** consecutive same-direction reversal candles on the same HTF zone amplify the signal — *"closed as a hanging man again for a second week in a row"*.

```python
def consecutive_reversal_strength(candles, pattern_fn, lookback=3):
    """
    Count consecutive same-direction reversal candles at the zone.
    Returns 1 (single bar = standard), 2+ (strengthened distribution/accumulation).
    """
    count = 0
    for c in reversed(candles[-lookback:]):
        if pattern_fn(c):
            count += 1
        else:
            break
    return count
```

Treat **count ≥ 2** as a confidence multiplier on the entry — sized 25% larger or skip-tier upgraded to standard-tier (the institutions are pushing back at the same level repeatedly = more conviction).

### Seasonality Entries Appear as LTF Retracements (Phase 6, Ch 179)

Set realistic LTF expectations: when a **seasonality-driven** entry triggers on the daily, the 15-minute chart will show it as a **retracement**, not an impulse. Bernd: *"if we have a seasonality buying point on the chart, the 15 minutes will never look like this — it is also retracement"*.

This means:
- Don't expect explosive LTF leg-out signals when entering on seasonality alignment.
- Use LTF entries (E3a) at small retracement zones, not impulsive breakouts.
- The "feel" is slower than zone-trigger entries — accept that.

### E3a: Lower Timeframe Zone Entry (BEST R:R — RECOMMENDED)

Drop to a lower timeframe, find a zone WITHIN the pattern's price range, and enter at that LTF zone's proximal. Much tighter stop = dramatically better reward-to-risk.

```python
def entry_option_3a(pattern, zone, ltf_zones):
    """
    E3a: Lower timeframe zone entry (zone refinement).
    Best R:R. Recommended approach.
    
    Find a qualifying zone on a lower timeframe that exists
    within the pattern's price range AND is contained inside the HTF zone.
    
    Args:
        pattern: detected pattern on the entry timeframe
        zone: the HTF qualified zone
        ltf_zones: zones detected on a lower timeframe
    """
    # Find LTF zones within the pattern's price range
    candidates = []
    for ltf_zone in ltf_zones:
        if not ltf_zone.is_valid:
            continue
        
        if pattern["signal"] == "bullish" and ltf_zone.zone_type == "demand":
            # LTF demand zone must be within pattern range
            if (ltf_zone.proximal <= pattern["pattern_high"] and 
                ltf_zone.distal >= pattern["pattern_low"]):
                candidates.append(ltf_zone)
        
        elif pattern["signal"] == "bearish" and ltf_zone.zone_type == "supply":
            if (ltf_zone.proximal >= pattern["pattern_low"] and 
                ltf_zone.distal <= pattern["pattern_high"]):
                candidates.append(ltf_zone)
    
    if not candidates:
        return None  # No LTF zone found — fall back to Option 1 or 2
    
    # Pick the best-scoring LTF zone
    best = max(candidates, key=lambda z: z.composite_score)
    
    if pattern["signal"] == "bullish":
        entry = best.proximal
        stop = best.distal - 0.33 * abs(best.proximal - best.distal)
    else:
        entry = best.proximal
        stop = best.distal + 0.33 * abs(best.distal - best.proximal)
    
    return {
        "entry": entry,
        "stop": stop,
        "option": 3,
        "ltf_zone": best,
        "fill_probability": 0.40,
        "note": "Best R:R — much tighter stop via LTF zone"
    }
```

---

### E3b: Stop-Buy Above Hammer High

A more conservative confirmation entry. Instead of entering at zone proximal, place a **stop-buy order one tick above the hammer high**. The order only triggers if price continues in the expected direction after forming the hammer — avoiding fills on hammers that immediately reverse.

```python
def entry_option_3b(hammer_pattern, zone, tick_size):
    """
    E3b: Stop-buy above hammer high.
    
    Used when: a hammer has formed inside the demand zone, but you want
    confirmation that momentum is indeed upward before committing.
    Lower fill rate than E1/E2 but much higher confidence.
    
    Args:
        hammer_pattern: detected hammer with pattern_high (top of candle)
        zone: demand zone where hammer formed
        tick_size: instrument minimum price increment
    
    Returns:
        Entry dict with stop-buy order details
    """
    entry = hammer_pattern["pattern_high"] + tick_size  # One tick above hammer high
    stop = hammer_pattern["pattern_low"] - 0.33 * (
        hammer_pattern["pattern_high"] - hammer_pattern["pattern_low"]
    )
    return {
        "entry": entry, 
        "stop": stop, 
        "option": "E3b",
        "order_type": "stop_buy",    # Only fills if price moves UP through entry
        "fill_probability": 0.45,    # Lower than E1, higher than E3a
        "note": "Stop-buy above hammer high — directional confirmation required before fill"
    }
```

### E3c: Throwback Strap (Return-After-Impulse Entry)

A high-conviction sub-type of pattern confirmation. Price must first LEAVE the zone (initial impulse away), then RETURN toward the zone, then RESUME the original direction. This two-phase movement confirms that the zone held institutional interest.

```
Phase 1: Price enters zone and makes initial impulse AWAY from zone (confirms zone is active)
Phase 2: Price pulls back toward zone (throwback — tests zone again)
Phase 3: Price resumes original direction (the "strap" — confirms the zone held)
Entry: at the re-resumption, after Phase 3 candle forms
```

```python
def detect_throwback_strap(zone, price_history, min_impulse_pct=0.5):
    """
    E3c: Detect Throwback Strap setup.
    
    Requires three-phase price movement at the zone.
    Most conservative entry — lowest fill rate, highest conviction.
    
    Args:
        zone: the qualified demand/supply zone
        price_history: recent OHLCV bars
        min_impulse_pct: minimum % of zone height for Phase 1 impulse to count
    
    Returns:
        dict with setup status and entry level, or None if not yet set up
    """
    # Phase 1: initial impulse away from zone (>=50% of zone height traveled)
    zone_height = abs(zone.proximal - zone.distal)
    impulse_threshold = zone.proximal + (min_impulse_pct * zone_height)  # for demand
    
    phases_confirmed = check_throwback_phases(price_history, zone, impulse_threshold)
    
    if phases_confirmed:
        return {
            "valid": True,
            "entry": zone.proximal,     # Re-enter at proximal on Phase 3 resumption
            "stop": zone.distal,        # Stop at distal (HTF weekly income mode)
            "option": "E3c",
            "fill_probability": 0.20,   # Very low — requires specific price action
            "note": "Throwback Strap — highest conviction, lowest fill rate"
        }
    return None
```

### E4: Trendline Break Entry

Used primarily for stock reversals where no clean single-candle pattern forms. Draw a descending trendline connecting the swing highs (for demand/long setups) or an ascending trendline connecting swing lows (for supply/short setups). Enter on the break and close above/below the trendline.

```python
def entry_option_4_trendline(candle_data, zone, direction):
    """
    E4: Trendline break entry.
    
    For demand zones: draw descending trendline across recent swing highs.
    Entry when price closes ABOVE the trendline.
    
    For supply zones: draw ascending trendline across recent swing lows.
    Entry when price closes BELOW the trendline.
    
    Best for: individual stock reversals; also valid for index reversals
    when no hammer/engulfing forms cleanly.
    
    Args:
        candle_data: OHLCV history
        zone: the qualified zone
        direction: "long" or "short"
    
    Returns:
        entry signal dict or None if no trendline break
    """
    swing_points = find_swing_highs(candle_data) if direction == "long" else find_swing_lows(candle_data)
    
    if len(swing_points) < 2:
        return None
    
    # Fit trendline through most recent 2+ swing points
    trendline_level = calculate_trendline_at_current(swing_points, len(candle_data))
    current = candle_data[-1]
    
    if direction == "long" and current.close > trendline_level:
        return {
            "entry": current.close,
            "stop": zone.distal - 0.33 * (zone.proximal - zone.distal),
            "option": "E4",
            "trigger": "trendline_break_above",
            "fill_probability": 0.60,
            "note": "Trendline break — confirmed momentum reversal"
        }
    elif direction == "short" and current.close < trendline_level:
        return {
            "entry": current.close,
            "stop": zone.distal + 0.33 * (zone.proximal - zone.distal),
            "option": "E4",
            "trigger": "trendline_break_below",
            "fill_probability": 0.60,
            "note": "Trendline break — confirmed momentum reversal"
        }
    return None
```

---

## Stop Loss Formula — Two Modes

The stop loss placement depends on the ENTRY TIMEFRAME, not the zone timeframe.

### Mode 1: LTF / Pattern Entries (Default) — -33% Fibonacci

For pattern-confirmation entries (E1, E2, E3a, E3b, E3c, E4):

```
# For LONG entries (demand zone):
pattern_range = pattern_high - pattern_low
stop = pattern_low - 0.33 * pattern_range

# For SHORT entries (supply zone):
pattern_range = pattern_high - pattern_low
stop = pattern_high + 0.33 * pattern_range
```

### Mode 2: HTF Weekly Income Entries — Distal Line Only

**AUDIT CORRECTION (CW43-Idx)**: When entering directly at the HTF weekly zone proximal (not a LTF refinement entry), use the DISTAL LINE as the stop — no -33% extension. This achieves 4:1 R:R on the weekly timeframe. Adding -33% to a weekly zone distal pushes the stop so far that R:R becomes unacceptable.

```
# HTF weekly income trade stop (demand zone):
stop = zone.distal  # Exactly at distal — no extension

# HTF weekly income trade stop (supply zone):  
stop = zone.distal  # Exactly at distal — no extension
```

### Implementation

```python
def calculate_stop(pattern_or_zone, entry_mode="ltf_pattern", direction="long"):
    """
    Calculate stop loss based on entry mode.
    
    Args:
        pattern_or_zone: the pattern dict or zone object
        entry_mode: "ltf_pattern" (default, -33% Fib) or "htf_weekly" (distal only)
        direction: "long" or "short"
    
    Returns:
        float: stop price
    """
    if entry_mode == "htf_weekly":
        # Distal line only — no extension
        return pattern_or_zone.distal
    
    else:  # ltf_pattern (default)
        if hasattr(pattern_or_zone, 'pattern_high'):
            high = pattern_or_zone["pattern_high"]
            low = pattern_or_zone["pattern_low"]
        else:
            high = pattern_or_zone.proximal
            low = pattern_or_zone.distal
        
        pattern_range = high - low
        if direction == "long":
            return low - 0.33 * pattern_range
        else:
            return high + 0.33 * pattern_range
```

### Why -33% for LTF Entries?

The -33% extension (Fib -33 on the zone drawing) accounts for:
- Institutional stop hunts that sweep beyond visible extremes
- Hidden orders placed just outside the apparent support/resistance
- Provides buffer against false breakouts while keeping risk manageable

### Why Distal-Only for HTF Weekly Entries?

Weekly zones are inherently much wider than LTF zones. Adding 33% beyond the weekly distal creates a stop so far from entry that the R:R becomes 1:1 or worse. Bernd confirmed (CW43-Idx) that weekly income trades achieve 4:1 R:R using the distal as the exact stop — no buffer needed because the weekly distal already incorporates institutional stop-hunt territory within the zone's wide range.

---

## Complete Entry Pipeline

```python
def generate_entry_signal(candle_data, active_zones, ltf_zones=None):
    """
    Complete entry signal generation pipeline.
    
    1. Detect candlestick patterns on current candle(s)
    2. Check if pattern is at a qualified zone
    3. Generate entry options with stops
    
    Args:
        candle_data: OHLCV data for the entry timeframe
        active_zones: list of qualified, active zones
        ltf_zones: optional lower-timeframe zones for Option 3
    
    Returns:
        list of entry signals
    """
    signals = []
    current = candle_data[-1]
    previous = candle_data[-2] if len(candle_data) >= 2 else None
    
    # --- Single-candle patterns ---
    
    # Hammer (bullish at demand)
    hammer = detect_hammer(current)
    if hammer["valid"]:
        zone = pattern_at_zone(hammer, [z for z in active_zones if z.zone_type == "demand"])
        if zone:
            signals.append(build_signal(hammer, zone, "long", ltf_zones))
    
    # Shooting Star (bearish at supply)
    star = detect_shooting_star(current)
    if star["valid"]:
        zone = pattern_at_zone(star, [z for z in active_zones if z.zone_type == "supply"])
        if zone:
            signals.append(build_signal(star, zone, "short", ltf_zones))
    
    # Hanging Man (bearish at supply — same geometry as hammer)
    hanging = detect_hanging_man(current)
    if hanging["valid"]:
        zone = pattern_at_zone(hanging, [z for z in active_zones if z.zone_type == "supply"])
        if zone:
            signals.append(build_signal(hanging, zone, "short", ltf_zones))
    
    # --- Two-candle patterns ---
    
    if previous:
        # Bullish Engulfing (at demand)
        bull_eng = detect_bullish_engulfing(previous, current)
        if bull_eng["valid"]:
            zone = pattern_at_zone(bull_eng, [z for z in active_zones if z.zone_type == "demand"])
            if zone:
                signals.append(build_signal(bull_eng, zone, "long", ltf_zones))
        
        # Bearish Engulfing (at supply)
        bear_eng = detect_bearish_engulfing(previous, current)
        if bear_eng["valid"]:
            zone = pattern_at_zone(bear_eng, [z for z in active_zones if z.zone_type == "supply"])
            if zone:
                signals.append(build_signal(bear_eng, zone, "short", ltf_zones))
    
    # --- Multi-candle patterns ---
    
    # Head & Shoulders (bearish at supply)
    hs = detect_head_and_shoulders(candle_data)
    if hs and hs["valid"] and hs["neckline_broken"]:
        zone = pattern_at_zone(hs, [z for z in active_zones if z.zone_type == "supply"])
        if zone:
            signals.append(build_signal(hs, zone, "short", ltf_zones))
    
    # Inverse H&S (bullish at demand)
    ihs = detect_inverse_head_and_shoulders(candle_data)
    if ihs and ihs["valid"] and ihs["neckline_broken"]:
        zone = pattern_at_zone(ihs, [z for z in active_zones if z.zone_type == "demand"])
        if zone:
            signals.append(build_signal(ihs, zone, "long", ltf_zones))
    
    return signals


def build_signal(pattern, zone, direction, ltf_zones=None):
    """
    Build a complete entry signal with all three entry options.
    """
    opt1 = entry_option_1(pattern, zone)
    opt2 = entry_option_2(pattern, zone)
    opt3 = entry_option_3(pattern, zone, ltf_zones) if ltf_zones else None
    
    # Calculate R:R for each option
    target = zone.profit_target  # From zone qualifier Q5
    
    for opt in [opt1, opt2, opt3]:
        if opt:
            risk = abs(opt["entry"] - opt["stop"])
            reward = abs(target - opt["entry"]) if target else None
            opt["risk"] = risk
            opt["reward"] = reward
            opt["rr_ratio"] = round(reward / risk, 2) if risk > 0 and reward else None
    
    return {
        "pattern": pattern["pattern"],
        "signal": pattern["signal"],
        "direction": direction,
        "zone": {
            "type": zone.zone_type,
            "formation": zone.formation,
            "proximal": zone.proximal,
            "distal": zone.distal,
            "composite_score": zone.composite_score
        },
        "option_1": opt1,
        "option_2": opt2,
        "option_3": opt3,
        "recommended": "option_3" if opt3 else "option_1"
    }
```

---

## Quick Reference Summary

| Pattern | Candles | Zone | Signal | Key Validation |
|---------|---------|------|--------|----------------|
| Hammer | 1 | Demand | Bullish | body <= 30%, lower wick >= 2x body |
| Shooting Star | 1 | Supply | Bearish | body <= 30%, upper wick >= 2x body |
| Hanging Man | 1 | Supply | Bearish | Same as hammer, different context |
| Bullish Engulfing | 2 | Demand | Bullish | Green engulfs red, takes out prior low |
| Bearish Engulfing | 2 | Supply | Bearish | Red engulfs green, takes out prior high |
| Head & Shoulders | Multi | Supply | Bearish | 3 peaks, middle highest, neckline break |
| Inverse H&S | Multi | Demand | Bullish | 3 troughs, middle lowest, neckline break |

| Entry Option | Fill Rate | R:R Quality | Method |
|-------------|-----------|-------------|--------|
| E1 (Proximal) | ~99% | Lowest | Limit at zone proximal |
| E2 (Midpoint) | ~50% | Medium | Limit within pattern range |
| E3a (LTF Zone) | ~40% | **Best** | LTF zone within HTF zone (zone refinement) |
| E3b (Stop-Buy) | ~45% | High | Stop-buy order 1 tick above hammer high |
| E3c (Throwback Strap) | ~20% | Highest | Two-phase return-after-impulse confirmation |
| E4 (Trendline Break) | ~60% | High | Trendline break confirmation entry |

| Stop Mode | When | Formula | Reason |
|-----------|------|---------|--------|
| **LTF Pattern** (default) | E1, E2, E3a, E3b, E3c, E4 | `low - 0.33 * range` / `high + 0.33 * range` | Fib -33 extension covers hidden orders |
| **HTF Weekly Income** | Direct entry at weekly zone proximal | `zone.distal` (no extension) | Preserves 4:1 R:R on weekly timeframe |
