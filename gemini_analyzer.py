import json
import time

from google import genai
from google.genai import types
from PIL import Image

from config import GEMINI_API_KEY, BATCH_SIZE
from models import ScanResult

PROMPT_TEMPLATE = """Role: You are a Senior Technical Analyst specializing in price action and volume spread analysis (VSA). Your goal is to identify high-probability bullish entries based on the provided candlestick chart (inclusive of SMA 150 and Volume).

Additional context - Weekly data summary for {ticker}:
{weekly_summary}

Analysis Framework:
Strictly evaluate the chart for the following criteria:

Structural Shifts:
- Reversals: Identify "Change of Character" (ChoCh)—e.g., a higher high following a prolonged downtrend. Look for Double Bottoms, Inverse Head & Shoulders, or falling wedges.
- SMA 150 Interaction: Prioritize setups where price recovers the SMA 150 and holds it as new support (the "Flip").

Momentum & Breakouts:
- Identify "Volatility Contraction" (VCP) patterns.
- Look for breakouts from definitive horizontal resistance or Ascending Triangles.
- Candlestick Confirmation: Require a strong close (minimal upper wick) on breakout candles.

Volume Integrity:
- Accumulation: Volume must be > 20-period average on up-bars during the breakout.
- VSA: Look for "Volume Dry-up" (low volume pullbacks) indicating a lack of selling pressure.

Output Constraints:
- Selectivity: Set bullish_signal to true only if the price is above the SMA 150 OR shows a confirmed reversal pattern at a major support level.
- Risk/Reward: stop_loss should be placed below the most recent swing low or the SMA 150.
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
  "reasoning": "A concise professional synthesis of the evidence."
}}"""


def _build_client() -> genai.Client:
    return genai.Client(api_key=GEMINI_API_KEY)


def analyze_stock(image_path: str, weekly_summary: dict, ticker: str) -> ScanResult:
    """Send chart image + weekly summary to Gemini and parse the response."""
    client = _build_client()
    img = Image.open(image_path)

    prompt_text = PROMPT_TEMPLATE.format(
        ticker=ticker,
        weekly_summary=json.dumps(weekly_summary, indent=2),
    )

    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=[img, prompt_text],
        config=types.GenerateContentConfig(
            temperature=0.2,
            response_mime_type="application/json",
        ),
    )

    try:
        data = json.loads(response.text)
    except (json.JSONDecodeError, ValueError) as e:
        print(f"  Failed to parse Gemini response for {ticker}: {e}")
        return ScanResult(ticker=ticker, reasoning="Failed to parse Gemini response", chart_path=image_path)

    return ScanResult(
        ticker=ticker,
        bullish_signal=bool(data.get("bullish_signal", False)),
        confidence_score=int(data.get("confidence_score", 0)),
        market_structure=data.get("market_structure", ""),
        patterns=data.get("patterns_detected", []),
        technical_triggers=data.get("technical_triggers", {}),
        volume_analysis=data.get("volume_analysis", ""),
        reasoning=data.get("reasoning", ""),
        chart_path=image_path,
    )


def analyze_batch(stocks: list[tuple[str, str, dict]]) -> list[ScanResult]:
    """Analyze a list of (image_path, ticker, weekly_summary) in batches."""
    results = []
    for i in range(0, len(stocks), BATCH_SIZE):
        batch = stocks[i:i + BATCH_SIZE]
        for image_path, ticker, weekly_summary in batch:
            print(f"  Analyzing {ticker}...")
            try:
                result = analyze_stock(image_path, weekly_summary, ticker)
                results.append(result)
            except Exception as e:
                print(f"  Error analyzing {ticker}: {e}")
                results.append(ScanResult(ticker=ticker, reasoning=f"Error: {e}", chart_path=image_path))
        # Rate limiting between batches
        if i + BATCH_SIZE < len(stocks):
            print("  Waiting between batches...")
            time.sleep(5)
    return results
