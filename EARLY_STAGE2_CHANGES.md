# Early Stage 2 Prioritization — Changes Summary

## Overview
Modified the stock scanner to **prioritize early Stage 2 setups** over established trends or overextended stocks. The scanner now identifies stocks just transitioning from Stage 1 (basing) to Stage 2 (advancing), with emphasis on fresh Golden Crosses and narrow SMA spreads.

## Key Concept: Early vs Mid vs Late Stage 2

### Early Stage 2 (IDEAL)
- Price recently broke above SMA 150 (within last 4-8 weeks)
- SMA 50 just crossed above SMA 150 (Golden Cross within last 4-8 weeks)
- Narrow SMA spread: 0-8% between SMA 50 and SMA 150
- Price NOT overextended: within 5-15% of SMA 150
- Base formation visible on 3Y/1Y charts before entry

### Mid Stage 2
- Price well above SMA 150
- Established uptrend
- SMA spread widening (8-15%)
- May still be tradeable on pullbacks to SMA 50

### Late Stage 2 (AVOID)
- Price far from SMA 150 (>15%)
- Wide SMA spread (>10%)
- Risk of Stage 3 topping or sharp pullback

## Changes Made

### 1. gemini_analyzer.py

#### Market Structure Section (Lines 67-76)
- Added **EARLY/MID/LATE Stage 2** classification
- Emphasized Stage 1→2 Transition detection
- Golden Cross timing tracking (within last 4-8 weeks)
- Price extension metrics (not overextended = within 5-15% of SMA 150)

#### Current Price Status (Lines 62-65)
- Added ideal criteria: price recently broke above SMA 150, within 5-10% of breakout

#### Moving Average Analysis (Lines 79-90)
- Focus on recent Golden Cross (4-8 weeks)
- SMA spread % as indicator:
  - 0-5% = early Stage 2
  - 5-10% = transitioning
  - >10% = late Stage 2 or overextended
- SMA 150 slope change detection (flat/declining → rising)

#### Watchlist Tier Classification (Lines 154-167)
**"Ready Now" criteria updated:**
- Price recently broke above SMA 150 (within last 4-8 weeks) OR confirmed breakout
- SMA 50 above SMA 150 with narrow spread (0-8%)
- Volume confirmation on breakout
- Price NOT overextended (within 5-15% of SMA 150)
- R/R >= 3:1, no earnings within 7 days
- Base formation visible before Stage 2 entry

**"Setting Up" criteria updated:**
- Late Stage 1 (basing), SMA 150 flattening or turning up
- Price near/above SMA 150 but SMA 50 not yet above SMA 150
- OR mid-Stage 2 pullback to SMA 50 support

**"Not Yet" now includes:**
- Late Stage 2 overextension

#### Output Constraints (Lines 172-179)
- Set bullish_signal to true ONLY for:
  - Early Stage 2 (recently crossed above SMA 150, narrow SMA spread)
  - Confirmed Stage 1→2 transition with volume
  - Early/mid Stage 2 pullback to SMA 50 support with bounce signal
- **AVOID** late Stage 2 overextensions (price >15% above SMA 150 with wide SMA spread >10%)

#### JSON Output Format (Lines 181-221)
- Updated `market_structure` field to include: "Early Stage 2 / Mid Stage 2 / Late Stage 2 / Stage 1→2 Transition"
- Added new `stage_2_analysis` object:
  ```json
  "stage_2_analysis": {
    "phase": "Early / Mid / Late / N/A",
    "golden_cross_date": "Approximate date or N/A",
    "weeks_since_stage_2_entry": "Number of weeks or N/A",
    "sma_spread_pct": "Percentage spread between SMA 50 and 150",
    "price_extension_from_sma150_pct": "Percentage distance above SMA 150",
    "assessment": "Brief assessment of Stage 2 phase suitability"
  }
  ```
- Updated `sma_analysis` prompt to include SMA spread % and Early/Mid/Late indication
- Updated `reasoning` prompt to emphasize Stage 2 phase

### 2. models.py

#### ScanResult Dataclass (Line 14)
- Added `stage_2_analysis: dict = field(default_factory=dict)` field after `sma_analysis`

### 3. gemini_analyzer.py (analyze_stock function)

#### Line 437
- Added `stage_2_analysis=data.get("stage_2_analysis", {})` to ScanResult initialization

### 4. scanner.py (display_result function)

#### Lines 262-281
- Display Stage 2 phase prominently below market structure
- Color-coded by phase:
  - **Early Stage 2**: Green + Bold
  - **Mid Stage 2**: Yellow
  - **Late Stage 2**: Red
- Shows: phase, SMA spread %, price extension %, weeks since entry

#### Lines 428-438
- Display Stage 2 assessment in detailed section
- Shows Golden Cross date and assessment text

## Testing

Run the scanner with your stock list:
```bash
venv/bin/python scanner.py stocks.csv --no-discord
```

Expected behavior:
- Stocks in **Early Stage 2** should score higher confidence and appear in "Ready Now" tier
- Stocks with narrow SMA spreads (0-8%) should be flagged as early Stage 2
- Stocks far from SMA 150 (>15%) with wide SMA spread (>10%) should be downgraded or flagged as overextended
- Stage 2 phase will be visible in the box display below the market structure line
- Reasoning will emphasize whether it's an early Stage 2 setup

## Example Output

```
  ┌────────────────────────────────────────────────────────────────────────┐
  │ AAPL           ██ BULLISH ██   conf: 85 [████████░░]
  │                Early Stage 2
  │                Early   SMA Spread: 3.2%   Price ext: 7.1%   Weeks: 5
  ├────────────────────────────────────────────────────────────────────────┤
  │ Price: $185.42    1M: +12.3%    3M: +18.5%    52wH: -8.2%
  ...
```

## Benefits

1. **Higher quality entries**: Catches stocks at the beginning of trends, not the end
2. **Better risk/reward**: Entry near SMA 150 with clear stop placement
3. **Reduced false positives**: Filters out overextended stocks that appear bullish but are due for pullback
4. **Clear metrics**: SMA spread % and weeks since Stage 2 entry provide objective criteria
5. **Follows Weinstein methodology**: Aligns with Stan Weinstein's Stage Analysis principles

## Next Steps

After running the scanner:
1. Review "Ready Now" tier — should be early Stage 2 setups
2. Check "Setting Up" tier — should be late Stage 1 or Stage 1→2 transitions
3. Verify overextended stocks are downgraded or flagged
4. Adjust thresholds if needed (e.g., SMA spread % cutoffs)
