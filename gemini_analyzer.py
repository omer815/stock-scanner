import json
import time

from google import genai
from google.genai import types
from PIL import Image

from config import GEMINI_API_KEY, BATCH_SIZE, GEMINI_RATE_LIMIT_DELAY
from models import ScanResult

PROMPT_TEMPLATE = """Role: You are a Senior Technical Analyst specializing in price action, volume spread analysis (VSA), and multi-timeframe analysis. Your goal is to identify high-probability bullish entries based on the provided candlestick charts, price history data, and supplementary context.

You are provided with four daily candlestick chart images:
1. 5-year overview (full history)
2. 3-year intermediate view
3. 1-year zoomed view
4. 3-month short-term detail

Chart legend (all charts):
- Green candles = up days, Red candles = down days
- Yellow line = SMA 50 (short-term trend)
- Cyan line = SMA 150 (long-term trend)
- Bottom panel = Volume bars (green = up day, red = down day)
- Light gray gridlines for price reference
- Chart title shows current Close, SMA 50, and SMA 150 exact values
- SMAs are pre-computed on the full 5Y dataset, so values are consistent across all timeframe views

Additional context for {ticker}:

Weekly data summary:
{weekly_summary}

Price history (last 90 trading days):
{price_history}

Sector context:
{sector_info}

Institutional ownership:
{institutional_info}

Earnings:
{earnings_info}

Recent headlines:
{news_info}

Darvas box analysis:
{darvas_info}

Consolidation analysis:
{consolidation_info}

Sector heatmap context:
{sector_heatmap}

Technical data (exact values — use these rather than estimating from the chart):
{technical_summary}

Analysis Framework — Evaluate ALL of the following systematically:

1. Current Price Status:
   - Where is price relative to key SMAs, 52-week high/low?
   - Calculate 1-month and 3-month price change from the price history table.
   - Is price extended or at a reasonable entry point?
   - IDEAL: Price recently broke above SMA 150, within 5-10% of the breakout level (not overextended)

2. Market Structure (Stan Weinstein Stages) — PRIORITIZE EARLY STAGE 2:
   - Stage 1 (Basing): Price oscillating around flat SMA 150
   - Stage 2 (Advancing): Price above rising SMA 150, SMA 50 above SMA 150
     * EARLY Stage 2: Recently crossed above SMA 150, SMA 50 just crossed above SMA 150 (Golden Cross within last 4-8 weeks), price still near the breakout level (not extended)
     * MID Stage 2: Price well above SMA 150, established uptrend
     * LATE Stage 2: Price far from SMA 150, potentially overextended
   - Stage 3 (Topping): Price struggling at highs, SMA 150 flattening
   - Stage 4 (Declining): Price below declining SMA 150
   - Stage 1→2 Transition: Identify Change of Character (ChoCh) — e.g., first higher high after prolonged downtrend, price breaking above declining SMA 150 for the first time

3. Pattern Recognition:
   - Identify specific patterns: Cup & Handle, VCP, Ascending Triangle, Double Bottom, Inverse H&S, Falling Wedge, Bull Flag, Flat Base, High Tight Flag
   - Rate pattern quality (1-10) based on textbook characteristics
   - Assess pattern completion percentage and expected breakout zone

4. Moving Average Analysis — FOCUS ON EARLY STAGE 2 CHARACTERISTICS:
   - SMA 50/150 relationship: Golden Cross, Death Cross, spread %
     * IDEAL: Recent Golden Cross (SMA 50 crossed above SMA 150 within last 4-8 weeks)
     * Narrow spread between SMA 50 and SMA 150 (0-5%) indicates early Stage 2
     * Wide spread (>10%) may indicate late Stage 2 or overextension
   - Price vs SMAs: above both (strong), between (transitional), below both (weak)
   - SMA 50 as dynamic support/resistance on pullbacks
   - SMA slope direction and acceleration
   - SMA 150 turning from flat/declining to rising is a key Stage 1→2 transition signal

5. Volume Integrity:
   - Accumulation vs Distribution days (count high-volume up vs down days in last 20 bars)
   - Volume on breakout attempts vs pullbacks
   - Volume Dry-Up: low volume pullbacks indicating lack of selling pressure
   - Average volume trend (expanding or contracting)

6. Darvas Box Analysis:
   - Confirm or refine the provided Darvas box data using the charts
   - Identify box top, bottom, range %, weeks forming, breakout status

7. Consolidation / VCP Analysis:
   - ATR compression trend from the provided data
   - Count VCP contractions (T1, T2, T3 etc.)
   - Base depth and length relative to prior advance
   - Rate base quality (1-10)

8. Multi-Timeframe Confirmation:
   - 5Y chart: Long-term trend direction, major support/resistance levels
   - 3Y chart: Intermediate trend, base formations
   - 1Y chart: Current setup context, recent pattern development
   - 3M chart: Short-term price action quality, entry timing
   - Do all timeframes align for a bullish thesis?

9. Key Levels:
   - Identify 2-3 support levels with reasoning (SMA, swing low, prior resistance turned support)
   - Identify 2-3 resistance levels with reasoning (prior high, round number, measured move target)

10. Risk/Reward Calculation:
    - Entry zone: specific price range for entry
    - Stop loss: below nearest swing low or key SMA
    - Target 1: nearest resistance (conservative)
    - Target 2: measured move target (moderate)
    - Target 3: major resistance or extension (aggressive)
    - Calculate R/R ratio for Target 1

11. Sector Strength:
    - Is the sector outperforming or underperforming SPY?
    - Sector rotation context — is money flowing into or out of this sector?

12. Earnings Risk Assessment:
    - Days until next earnings
    - Risk level: LOW (>30 days), MEDIUM (14-30 days), HIGH (7-14 days), CRITICAL (<7 days)
    - Impact on trade management

13. News & Sentiment:
    - Analyze provided headlines for catalysts
    - Overall sentiment: Bullish, Bearish, or Neutral
    - Any material news that changes the technical picture?

14. Red Flags:
    - List any concerns: distribution days, failed breakouts, earnings risk, bearish divergences, overhead supply, declining volume on advances, etc.

15. Catalysts:
    - List positive factors: accumulation, sector strength, pattern completion, institutional buying, positive news, etc.

16. Last Breakout:
    - Identify the most recent breakout attempt from the charts and price history
    - When did it occur (approximate date)? At what price level?
    - Was volume above average on the breakout day/candle?
    - Did the breakout succeed (price held above), fail (price fell back), or is it still in progress?

Watchlist Tier Classification — PRIORITIZE EARLY STAGE 2 SETUPS:
- "Ready Now" — Actionable early Stage 2:
  * Price recently broke above SMA 150 (within last 4-8 weeks) OR confirmed breakout from consolidation above both SMAs
  * SMA 50 above SMA 150 with narrow spread (0-8%), indicating fresh Golden Cross
  * Volume confirmation on breakout
  * Price NOT overextended (within 5-15% of SMA 150)
  * R/R >= 3:1, no earnings within 7 days
  * Base formation visible on 3Y/1Y charts before the Stage 2 entry
- "Setting Up" — Watch for Stage 1→2 transition:
  * Currently in late Stage 1 (basing), SMA 150 flattening or starting to turn up
  * Price consolidating near/above SMA 150 but SMA 50 not yet above SMA 150
  * Pattern forming (VCP, Cup & Handle) but needs breakout trigger
  * OR mid-Stage 2 pullback to SMA 50 support, waiting for bounce
- "Not Yet" — No setup present, stock in downtrend, late Stage 2 overextension, or too many red flags

Reference Examples:
- Stocks like TGT, PTEN, PG, ADM are examples of the type of bullish setups to look for.

Output Constraints:
- Selectivity: Set bullish_signal to true only if:
  * EARLY Stage 2 (recently crossed above SMA 150, narrow SMA spread) OR
  * Confirmed Stage 1→2 transition with volume OR
  * Early/mid Stage 2 pullback to SMA 50 support with bounce signal
  * AVOID late Stage 2 overextensions (price >15% above SMA 150 with wide SMA spread >10%)
- Risk/Reward: stop_loss should be placed below the most recent swing low or the SMA 50/150.
- Tone: Objective, data-driven, and skeptical. Favor EARLY Stage 2 setups over established trends. Provide thorough reasoning.

Respond in this exact JSON format:
{{
  "bullish_signal": boolean,
  "confidence_score": "0-100",
  "market_structure": "Early Stage 2 / Mid Stage 2 / Late Stage 2 / Stage 1 (Basing) / Stage 1→2 Transition / Stage 3 (Topping) / Stage 4 (Declining)",
  "current_price_status": {{
    "price": "current price",
    "change_1m_pct": "1-month % change",
    "change_3m_pct": "3-month % change",
    "distance_from_52w_high_pct": "% below 52-week high",
    "distance_from_52w_low_pct": "% above 52-week low"
  }},
  "patterns_detected": ["List specific patterns"],
  "pattern_details": {{
    "primary_pattern": "Name of main pattern",
    "quality_score": "1-10",
    "completion_pct": "percentage complete",
    "status": "Forming / Complete / Breaking Out / Failed"
  }},
  "technical_triggers": {{
    "entry_zone": "Price range",
    "stop_loss": "Specific price",
    "target_1": "Next resistance level",
    "target_2": "Measured move target",
    "target_3": "Major resistance / extension target",
    "risk_reward_ratio": "X.X:1 based on entry midpoint to target_1 vs stop"
  }},
  "volume_analysis": "Detailed description of volume behavior — accumulation/distribution days, volume on breakouts vs pullbacks, dry-up patterns",
  "sma_analysis": "Detailed description of SMA 50/150 relationship, crossovers, slope, price position relative to both SMAs, dynamic support/resistance behavior. Include SMA 50/150 spread % and whether it indicates Early/Mid/Late Stage 2.",
  "stage_2_analysis": {{
    "phase": "Early / Mid / Late / N/A (if not in Stage 2)",
    "golden_cross_date": "Approximate date of SMA 50 crossing above SMA 150, or N/A",
    "weeks_since_stage_2_entry": "Number of weeks since Stage 2 began, or N/A",
    "sma_spread_pct": "Percentage spread between SMA 50 and SMA 150",
    "price_extension_from_sma150_pct": "Percentage distance of price above SMA 150",
    "assessment": "Brief assessment: Is this an ideal early Stage 2 entry, or is it overextended?"
  }},
  "price_action_quality": "Describe candlestick patterns, higher highs/higher lows structure, close quality (near highs vs middle vs near lows), gap behavior",
  "reasoning": "A thorough professional synthesis of ALL evidence. This should be 3-5 sentences minimum covering the key technical picture, Stage 2 phase, pattern context, volume confirmation, and risk factors. EMPHASIZE whether this is an early Stage 2 setup.",
  "watchlist_tier": "Ready Now / Setting Up / Not Yet",
  "watchlist_tier_reasoning": "Explain which criteria are met and which are not for the assigned tier. Use checkmarks for met and X for unmet.",
  "darvas_box": {{
    "box_top": "price or N/A",
    "box_bottom": "price or N/A",
    "range_pct": "percentage range or N/A",
    "weeks_forming": "number or N/A",
    "status": "Within / Breakout / Breakdown / None"
  }},
  "consolidation": {{
    "atr_trend": "Contracting / Expanding / Stable",
    "vcp_stages": "number of contractions or N/A",
    "base_depth_pct": "percentage depth from high to low of base",
    "base_length_weeks": "number of weeks",
    "base_quality": "1-10"
  }},
  "sector_strength": {{
    "sector": "sector name",
    "vs_spy": "Outperforming / Underperforming / In-line",
    "rotation_trend": "Money flowing in / out / neutral"
  }},
  "institutional_activity": {{
    "ownership_pct": "percentage or N/A",
    "trend": "Increasing / Decreasing / Stable / N/A",
    "notable": "Any notable insider or institutional activity"
  }},
  "earnings_risk": {{
    "days_until": "number or N/A",
    "risk_level": "LOW / MEDIUM / HIGH / CRITICAL",
    "impact": "Brief description of impact on trade management"
  }},
  "news_sentiment": {{
    "overall": "Bullish / Bearish / Neutral",
    "reasoning": "Brief explanation based on headlines"
  }},
  "key_levels": {{
    "support": ["$X.XX (reason)", "$X.XX (reason)"],
    "resistance": ["$X.XX (reason)", "$X.XX (reason)"]
  }},
  "red_flags": ["List of concerns, empty array if none"],
  "catalysts": ["List of positive factors"],
  "multi_timeframe_confirmation": {{
    "weekly_trend": "Bullish / Bearish / Neutral",
    "monthly_trend": "Bullish / Bearish / Neutral",
    "daily_setup": "Description of daily timeframe setup",
    "alignment": "All aligned / Mostly aligned / Mixed / Conflicting"
  }},
  "last_breakout": {{
    "date": "approximate date of the most recent breakout attempt (YYYY-MM-DD or N/A)",
    "price": "price level at breakout or N/A",
    "volume_confirmation": "Yes / No / Partial — was volume above average on the breakout day?",
    "success": "Successful / Failed / In Progress / N/A",
    "description": "Brief description of what broke out and outcome"
  }},
  "action_plan": "Specific trade instruction: entry price/range, stop loss with % risk, first target with R/R ratio. One clear sentence."
}}"""


def _format_technical_summary(tech_summary: dict | None) -> str:
    """Format technical summary dict as readable text for the prompt."""
    if not tech_summary:
        return "N/A"
    close = tech_summary["current_close"]
    sma50 = tech_summary["sma_50"]
    sma150 = tech_summary["sma_150"]
    p_sma50 = tech_summary["price_to_sma50_pct"]
    p_sma150 = tech_summary["price_to_sma150_pct"]
    spread = tech_summary["sma50_sma150_spread_pct"]
    alignment = "bullish" if spread > 0 else "bearish"
    return (
        f"Price: ${close} | SMA 50: ${sma50} | SMA 150: ${sma150}\n"
        f"Price vs SMA 50: {p_sma50:+.1f}% ({tech_summary['price_vs_sma50']}) | "
        f"Price vs SMA 150: {p_sma150:+.1f}% ({tech_summary['price_vs_sma150']})\n"
        f"SMA 50 vs SMA 150: {spread:+.1f}% ({alignment} alignment)"
    )


def _validate_result(data: dict, tech_summary: dict | None) -> dict:
    """Sanity-check Gemini output against known technical data."""
    if not tech_summary:
        return data

    price_below_sma150 = tech_summary["price_vs_sma150"] == "below"
    sma50_below_sma150 = tech_summary["sma50_vs_sma150"].startswith("below")
    confidence = int(data.get("confidence_score", 0))

    # Rule 1: Price below SMA 150 with no reversal pattern → cap confidence
    patterns = [p.lower() for p in data.get("patterns_detected", [])]
    reversal_keywords = ["double bottom", "inverse head", "falling wedge", "choch", "change of character", "reversal"]
    has_reversal = any(kw in p for p in patterns for kw in reversal_keywords)

    if price_below_sma150 and not has_reversal and confidence > 40:
        data["confidence_score"] = 40
        data["reasoning"] = f"[Adjusted: confidence capped at 40 — price below SMA 150 with no reversal pattern] {data.get('reasoning', '')}"

    # Rule 2: Death cross (SMA50 < SMA150) + no reversal → cannot be "Ready Now"
    if sma50_below_sma150 and not has_reversal and data.get("watchlist_tier") == "Ready Now":
        data["watchlist_tier"] = "Setting Up"
        data["reasoning"] = f"[Adjusted: downgraded from Ready Now — SMA 50 below SMA 150] {data.get('reasoning', '')}"

    # Rule 3: Price > 15% above SMA 50 → flag as extended, cap confidence at 60
    price_to_sma50 = tech_summary.get("price_to_sma50_pct", 0)
    if price_to_sma50 > 15 and confidence > 60:
        data["confidence_score"] = 60
        data["reasoning"] = f"[Adjusted: confidence capped at 60 — price extended {price_to_sma50}% above SMA 50] {data.get('reasoning', '')}"

    return data


def _build_client() -> genai.Client:
    return genai.Client(api_key=GEMINI_API_KEY)


def _call_gemini_with_retry(client, contents, max_retries=3):
    """Call Gemini API with exponential backoff on rate limit errors."""
    backoff_delays = [10, 30, 60]
    for attempt in range(max_retries + 1):
        try:
            response = client.models.generate_content(
                model="gemini-2.5-flash",
                contents=contents,
                config=types.GenerateContentConfig(
                    temperature=0.0,
                    response_mime_type="application/json",
                ),
            )
            return response
        except Exception as e:
            error_str = str(e)
            if "429" in error_str and attempt < max_retries:
                wait = backoff_delays[attempt]
                print(f"  Rate limited, waiting {wait}s (attempt {attempt + 1}/{max_retries})...")
                time.sleep(wait)
            else:
                raise


def _safe_str(value) -> str:
    """Convert a value to string, handling dicts/lists gracefully."""
    if isinstance(value, (dict, list)):
        return json.dumps(value)
    return str(value) if value else ""


def analyze_stock(daily_img_path: str, context_data: dict, ticker: str) -> ScanResult:
    """Send daily chart images and context data to Gemini and parse the response."""
    client = _build_client()
    daily_img_5y = Image.open(daily_img_path)

    # Load all available chart images
    chart_path_3y = context_data.get("chart_path_3y", "")
    chart_path_1y = context_data.get("chart_path_1y", "")
    chart_path_3m = context_data.get("chart_path_3m", "")

    daily_img_3y = Image.open(chart_path_3y) if chart_path_3y else None
    daily_img_1y = Image.open(chart_path_1y) if chart_path_1y else None
    daily_img_3m = Image.open(chart_path_3m) if chart_path_3m else None

    sector_data = context_data.get("sector_performance", {})
    sector_info = (
        f"{sector_data.get('sector', 'Unknown')} sector, "
        f"ETF {sector_data.get('etf', 'N/A')}: "
        f"1M return {sector_data.get('1m_return', 0)}%, "
        f"3M return {sector_data.get('3m_return', 0)}%"
    )

    news_headlines = context_data.get("news_headlines", [])
    news_info = "\n".join(f"- {h}" for h in news_headlines) if news_headlines else "No recent headlines"

    tech_summary = context_data.get("technical_summary")
    prompt_text = PROMPT_TEMPLATE.format(
        ticker=ticker,
        weekly_summary=json.dumps(context_data.get("weekly_summary", {}), indent=2),
        price_history=context_data.get("price_history", "N/A"),
        sector_info=sector_info,
        institutional_info=context_data.get("institutional_summary", "N/A"),
        earnings_info=context_data.get("earnings_proximity", "N/A"),
        news_info=news_info,
        darvas_info=context_data.get("darvas_box", "N/A"),
        consolidation_info=context_data.get("consolidation", "N/A"),
        sector_heatmap=context_data.get("sector_heatmap", "N/A"),
        technical_summary=_format_technical_summary(tech_summary),
    )

    # Send all chart images: 5Y, 3Y, 1Y, 3M
    contents = [daily_img_5y]
    if daily_img_3y:
        contents.append(daily_img_3y)
    if daily_img_1y:
        contents.append(daily_img_1y)
    if daily_img_3m:
        contents.append(daily_img_3m)
    contents.append(prompt_text)

    response = _call_gemini_with_retry(client, contents)

    try:
        data = json.loads(response.text)
    except (json.JSONDecodeError, ValueError) as e:
        print(f"  Failed to parse Gemini response for {ticker}: {e}")
        return ScanResult(
            ticker=ticker, reasoning="Failed to parse Gemini response",
            chart_path=daily_img_path, chart_path_1y=chart_path_1y,
            chart_path_3y=chart_path_3y, chart_path_3m=chart_path_3m,
        )

    data = _validate_result(data, tech_summary)

    return ScanResult(
        ticker=ticker,
        bullish_signal=bool(data.get("bullish_signal", False)),
        confidence_score=int(data.get("confidence_score", 0)),
        market_structure=data.get("market_structure", ""),
        patterns=data.get("patterns_detected", []),
        technical_triggers=data.get("technical_triggers", {}),
        volume_analysis=data.get("volume_analysis", ""),
        sma_analysis=data.get("sma_analysis", ""),
        stage_2_analysis=data.get("stage_2_analysis", {}),
        reasoning=data.get("reasoning", ""),
        chart_path=daily_img_path,
        chart_path_1y=chart_path_1y,
        chart_path_3y=chart_path_3y,
        chart_path_3m=chart_path_3m,
        sector=context_data.get("sector_performance", {}).get("sector", ""),
        sector_performance=sector_info,
        institutional_summary=context_data.get("institutional_summary", ""),
        earnings_proximity=context_data.get("earnings_proximity", ""),
        news_sentiment=data.get("news_sentiment", ""),
        watchlist_tier=data.get("watchlist_tier", "Not Yet"),
        darvas_box=data.get("darvas_box", ""),
        consolidation=data.get("consolidation", ""),
        current_price_status=data.get("current_price_status", {}),
        pattern_details=data.get("pattern_details", {}),
        price_action_quality=data.get("price_action_quality", ""),
        watchlist_tier_reasoning=data.get("watchlist_tier_reasoning", ""),
        sector_strength=data.get("sector_strength", {}),
        institutional_activity=data.get("institutional_activity", {}),
        earnings_risk=data.get("earnings_risk", {}),
        key_levels=data.get("key_levels", {}),
        red_flags=data.get("red_flags", []),
        catalysts=data.get("catalysts", []),
        multi_timeframe_confirmation=data.get("multi_timeframe_confirmation", {}),
        last_breakout=data.get("last_breakout", {}),
        action_plan=data.get("action_plan", ""),
    )


def analyze_batch(stocks: list[tuple[str, str, dict]]) -> list[ScanResult]:
    """Analyze a list of (daily_img, ticker, context_data) in batches."""
    results = []
    for i in range(0, len(stocks), BATCH_SIZE):
        batch = stocks[i:i + BATCH_SIZE]
        for daily_img, ticker, context_data in batch:
            print(f"  Analyzing {ticker}...")
            try:
                result = analyze_stock(daily_img, context_data, ticker)
                results.append(result)
            except Exception as e:
                print(f"  Error analyzing {ticker}: {e}")
                results.append(ScanResult(
                    ticker=ticker, reasoning=f"Error: {e}",
                    chart_path=daily_img, chart_path_1y=context_data.get("chart_path_1y", ""),
                    chart_path_3y=context_data.get("chart_path_3y", ""),
                    chart_path_3m=context_data.get("chart_path_3m", ""),
                ))
            # Rate limiting between each call
            time.sleep(GEMINI_RATE_LIMIT_DELAY)
        # Extra delay between batches
        if i + BATCH_SIZE < len(stocks):
            print("  Waiting between batches...")
            time.sleep(5)
    return results
