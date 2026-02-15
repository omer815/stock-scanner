import json
import time

from google import genai
from google.genai import types
from PIL import Image

from config import GEMINI_API_KEY, BATCH_SIZE, GEMINI_RATE_LIMIT_DELAY
from models import ScanResult

PROMPT_TEMPLATE = """Role: You are a Senior Technical Analyst specializing in price action and volume spread analysis (VSA). Your goal is to identify high-probability bullish entries based on the provided candlestick charts and supplementary data.

You are provided with a daily candlestick chart image.

Chart legend:
- Yellow line = SMA 50 (short-term trend)
- Cyan line = SMA 150 (long-term trend)
- Bottom panel = Volume bars

Additional context for {ticker}:

Weekly data summary:
{weekly_summary}

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

Analysis Framework:
Strictly evaluate the charts for the following criteria:

Structural Shifts:
- Reversals: Identify "Change of Character" (ChoCh)—e.g., a higher high following a prolonged downtrend. Look for Double Bottoms, Inverse Head & Shoulders, or falling wedges.
- SMA 150 Interaction: Prioritize setups where price recovers the SMA 150 and holds it as new support (the "Flip").

Moving Average Analysis:
- SMA 50/150 Relationship: Note whether the SMA 50 is above or below the SMA 150 (bullish vs bearish alignment). Identify Golden Cross (SMA 50 crossing above SMA 150) or Death Cross (SMA 50 crossing below SMA 150).
- Price vs SMAs: Assess whether price is above both SMAs (strong uptrend), between them (transitional), or below both (downtrend).
- SMA 50 as Dynamic Support/Resistance: On pullbacks in an uptrend, check if SMA 50 acts as support.

Momentum & Breakouts:
- Identify "Volatility Contraction" (VCP) patterns.
- Look for breakouts from definitive horizontal resistance or Ascending Triangles.
- Candlestick Confirmation: Require a strong close (minimal upper wick) on breakout candles.

Volume Integrity:
- Accumulation: Volume must be > 20-period average on up-bars during the breakout.
- VSA: Look for "Volume Dry-up" (low volume pullbacks) indicating a lack of selling pressure.

Darvas Box:
- Identify Darvas box formations — new highs followed by tight consolidation. Breakout above box top with volume = bullish.

Consolidation/VCP:
- Assess volatility contraction via ATR compression. Tight consolidation after an uptrend = potential breakout setup.

Sector Context:
- Is the sector outperforming the market? Stocks in strong sectors have higher probability.

Earnings Risk:
- If earnings within 14 days, flag as higher risk regardless of setup quality.

News Catalyst:
- Assess if recent headlines suggest positive/negative catalysts.

Watchlist Tier Classification:
- "Ready Now" — Actionable: confirmed breakout or reversal with volume confirmation
- "Setting Up" — Watch: pattern forming but needs trigger (e.g. consolidating near resistance)
- "Not Yet" — No setup present or stock in downtrend

Output Constraints:
- Selectivity: Set bullish_signal to true only if the price is above the SMA 150 OR shows a confirmed reversal pattern at a major support level.
- Risk/Reward: stop_loss should be placed below the most recent swing low or the SMA 50/150.
- Tone: Objective, data-driven, and skeptical.

Respond in this exact JSON format:
{{
  "bullish_signal": boolean,
  "confidence_score": "0-100",
  "market_structure": "Uptrend/Downtrend/Consolidation",
  "patterns_detected": ["List specific patterns"],
  "technical_triggers": {{
    "entry_zone": "Price range",
    "stop_loss": "Specific price",
    "target_1": "Next resistance level"
  }},
  "volume_analysis": "Describe the volume relationship to price action",
  "sma_analysis": "Describe the SMA 50/150 relationship, crossovers, and price position relative to both SMAs",
  "reasoning": "A concise professional synthesis of the evidence.",
  "watchlist_tier": "Ready Now / Setting Up / Not Yet",
  "darvas_box": "Description of Darvas box status from chart",
  "consolidation": "Consolidation assessment from chart and ATR data",
  "news_sentiment": "Bullish/Bearish/Neutral with brief reasoning"
}}"""


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
                    temperature=0.2,
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


def analyze_stock(daily_img_path: str, context_data: dict, ticker: str) -> ScanResult:
    """Send daily chart image and context data to Gemini and parse the response."""
    client = _build_client()
    daily_img = Image.open(daily_img_path)

    sector_data = context_data.get("sector_performance", {})
    sector_info = (
        f"{sector_data.get('sector', 'Unknown')} sector, "
        f"ETF {sector_data.get('etf', 'N/A')}: "
        f"1M return {sector_data.get('1m_return', 0)}%, "
        f"3M return {sector_data.get('3m_return', 0)}%"
    )

    news_headlines = context_data.get("news_headlines", [])
    news_info = "\n".join(f"- {h}" for h in news_headlines) if news_headlines else "No recent headlines"

    prompt_text = PROMPT_TEMPLATE.format(
        ticker=ticker,
        weekly_summary=json.dumps(context_data.get("weekly_summary", {}), indent=2),
        sector_info=sector_info,
        institutional_info=context_data.get("institutional_summary", "N/A"),
        earnings_info=context_data.get("earnings_proximity", "N/A"),
        news_info=news_info,
        darvas_info=context_data.get("darvas_box", "N/A"),
        consolidation_info=context_data.get("consolidation", "N/A"),
        sector_heatmap=context_data.get("sector_heatmap", "N/A"),
    )

    response = _call_gemini_with_retry(client, [daily_img, prompt_text])

    try:
        data = json.loads(response.text)
    except (json.JSONDecodeError, ValueError) as e:
        print(f"  Failed to parse Gemini response for {ticker}: {e}")
        return ScanResult(ticker=ticker, reasoning="Failed to parse Gemini response", chart_path=daily_img_path)

    return ScanResult(
        ticker=ticker,
        bullish_signal=bool(data.get("bullish_signal", False)),
        confidence_score=int(data.get("confidence_score", 0)),
        market_structure=data.get("market_structure", ""),
        patterns=data.get("patterns_detected", []),
        technical_triggers=data.get("technical_triggers", {}),
        volume_analysis=data.get("volume_analysis", ""),
        sma_analysis=data.get("sma_analysis", ""),
        reasoning=data.get("reasoning", ""),
        chart_path=daily_img_path,
        sector=context_data.get("sector_performance", {}).get("sector", ""),
        sector_performance=sector_info,
        institutional_summary=context_data.get("institutional_summary", ""),
        earnings_proximity=context_data.get("earnings_proximity", ""),
        news_sentiment=data.get("news_sentiment", ""),
        watchlist_tier=data.get("watchlist_tier", "Not Yet"),
        darvas_box=data.get("darvas_box", ""),
        consolidation=data.get("consolidation", ""),
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
                results.append(ScanResult(ticker=ticker, reasoning=f"Error: {e}", chart_path=daily_img))
            # Rate limiting between each call
            time.sleep(GEMINI_RATE_LIMIT_DELAY)
        # Extra delay between batches
        if i + BATCH_SIZE < len(stocks):
            print("  Waiting between batches...")
            time.sleep(5)
    return results
