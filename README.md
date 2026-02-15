# Stock Scanner

A modular Python stock scanner that analyzes candlestick charts for bullish setups using Gemini Vision API. Generates 5-year and 1-year daily charts with SMA 50/150 and volume, sends them to Gemini 2.5 Flash for technical analysis, and optionally notifies a Discord channel with results.

## Features

- Fetches 5 years of daily OHLCV data via yfinance
- Generates two candlestick charts per stock: 5-year overview and 1-year zoomed view
- Charts include SMA 50 (yellow), SMA 150 (cyan), and volume bars
- Analyzes both charts using Gemini 2.5 Flash vision (price action, VSA, structural shifts, Darvas box, VCP)
- Enriched context: sector heatmap, institutional ownership, earnings proximity, news headlines
- Three-tier watchlist classification: Ready Now / Setting Up / Not Yet
- Colored terminal output grouped by watchlist tier
- Structured JSON results with confidence scores, patterns, entry/stop/target levels
- Discord webhook notifications with both chart images attached
- GitHub Actions workflow for weekly automated scans

## Setup

```bash
cd stock_scanner
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

Create a `.env` file with your API keys:

```
GEMINI_API_KEY=your_gemini_api_key
DISCORD_WEBHOOK_URL=your_discord_webhook_url  # optional
```

## Usage

```bash
source venv/bin/activate

# Basic run (no Discord)
python scanner.py stocks.csv --no-discord

# With Discord notifications
python scanner.py stocks.csv

# Custom output path
python scanner.py stocks.csv --output my_results.json --no-discord
```

### Arguments

| Argument | Description |
|---|---|
| `csv_file` | Path to CSV file with `ticker,exchange` columns |
| `--no-discord` | Skip Discord notifications |
| `--output` | Output JSON path (default: `results.json`) |

## Input Format

`stocks.csv` — one ticker per row:

```csv
ticker,exchange
AAPL,
MSFT,
TGT,
TEVA,TA
```

Leave `exchange` empty for US stocks. Use exchange suffix (e.g. `TA` for Tel Aviv) for international tickers.

## Output

Results are saved as JSON. Each ticker produces:

```json
{
  "ticker": "TGT",
  "bullish_signal": true,
  "confidence_score": 85,
  "market_structure": "Uptrend",
  "patterns": ["Change of Character", "SMA 150 Flip"],
  "technical_triggers": {
    "entry_zone": "110.00-115.00",
    "stop_loss": "105.00",
    "target_1": "125.93"
  },
  "volume_analysis": "...",
  "sma_analysis": "...",
  "reasoning": "...",
  "chart_path": "charts/TGT/daily_5y.png",
  "chart_path_1y": "charts/TGT/daily_1y.png",
  "sector": "Consumer Defensive",
  "sector_performance": "...",
  "institutional_summary": "...",
  "earnings_proximity": "Next earnings in 45 days (2025-05-21)",
  "news_sentiment": "Neutral",
  "watchlist_tier": "Ready Now",
  "darvas_box": "Darvas box: top=$130.00, bottom=$125.00, status=within",
  "consolidation": "Tight consolidation (20 days, ATR ratio: 0.45, range: 3.2%)"
}
```

Charts are saved to per-ticker folders under `charts/` (e.g. `charts/TGT/daily_5y.png`, `charts/TGT/daily_1y.png`).

## Architecture

```
stocks.csv
    │
    ▼
┌──────────────────────────────────────────────────────────┐
│  scanner.py (orchestrator)                               │
│                                                          │
│  1. Load tickers from CSV                                │
│  2. Fetch sector heatmap (all 11 S&P sectors)            │
│                                                          │
│  ┌─── Per ticker loop ────────────────────────────────┐  │
│  │                                                    │  │
│  │  data_fetcher.py                                   │  │
│  │  ├── fetch_stock_data()    → 5Y daily OHLCV       │  │
│  │  ├── get_weekly_summary()  → stats (52w H/L, etc) │  │
│  │  ├── get_sector_performance() → sector ETF 1M/3M  │  │
│  │  ├── get_institutional_ownership() → top holders   │  │
│  │  ├── get_earnings_date()   → next earnings         │  │
│  │  ├── get_news_headlines()  → recent news           │  │
│  │  ├── detect_darvas_box()   → box pattern           │  │
│  │  └── detect_consolidation()→ ATR compression       │  │
│  │                                                    │  │
│  │  chart_generator.py                                │  │
│  │  ├── generate_chart()         → charts/T/5y.png   │  │
│  │  └── generate_yearly_chart()  → charts/T/1y.png   │  │
│  │                                                    │  │
│  └────────────────────────────────────────────────────┘  │
│                                                          │
│  3. Batch analyze with Gemini                            │
│     gemini_analyzer.py                                   │
│     └── analyze_batch()                                  │
│         └── analyze_stock() per ticker                   │
│             sends: [5Y chart, 1Y chart, prompt+context]  │
│             receives: structured JSON analysis            │
│                          │                               │
│                          ▼                               │
│                     ScanResult (models.py)                │
│                                                          │
│  4. Output results                                       │
│     ├── Terminal: colored tier-grouped summary            │
│     ├── JSON: results.json                               │
│     └── Discord: discord_notifier.py                     │
│         └── send_to_discord()                            │
│             embeds 1Y chart + attaches 5Y chart          │
└──────────────────────────────────────────────────────────┘
```

### Pipeline Steps

1. **Sector heatmap** — Fetches 1-month returns for all 11 S&P sector ETFs (single batch download via `get_all_sector_performances()`)
2. **Per-stock data collection** — For each ticker:
   - Fetch 5Y daily OHLCV via yfinance
   - Generate 5-year and 1-year candlestick charts (SMA 50/150 + volume)
   - Compute weekly summary stats (52w high/low, 4-week trend, avg volume)
   - Fetch sector ETF performance (1M/3M returns)
   - Fetch institutional ownership (major holders + top 5 institutions)
   - Check next earnings date
   - Fetch recent news headlines
   - Detect Darvas box pattern
   - Detect consolidation via ATR compression
3. **Gemini analysis** — Send both chart images + enriched context to Gemini 2.5 Flash (batched with rate limiting and exponential backoff on 429s)
4. **Results output** — Color-coded terminal summary grouped by tier + JSON file
5. **Discord notifications** — Send Ready Now and Setting Up results with both chart images attached

### Data Flow

```
yfinance API ──→ data_fetcher.py ──→ raw OHLCV + enrichment data
                                          │
                                          ├──→ chart_generator.py ──→ PNG chart files
                                          │
                                          └──→ gemini_analyzer.py ──→ ScanResult
                                                     │                     │
                                          Gemini 2.5 Flash API             │
                                                                           ├──→ results.json
                                                                           ├──→ terminal output
                                                                           └──→ discord_notifier.py ──→ Discord webhook
```

## Gemini Prompt

The prompt instructs Gemini to act as a Senior Technical Analyst evaluating:
- Structural shifts (ChoCh, reversal patterns, SMA 150 flip)
- Moving average analysis (SMA 50/150 relationship, golden/death cross)
- Momentum & breakouts (VCP, horizontal resistance, ascending triangles)
- Volume integrity (accumulation, VSA, volume dry-up)
- Darvas box formations
- Consolidation/VCP via ATR compression
- Sector context and earnings risk
- News catalyst assessment

Reference examples (TGT, PTEN, PG, ADM) calibrate the model's expectations for bullish setups.

Output is structured JSON with `temperature=0.0` and `response_mime_type="application/json"`.

## Configuration

All configuration lives in `config.py`:

| Setting | Default | Description |
|---|---|---|
| `GEMINI_API_KEY` | env var | Google Gemini API key |
| `DISCORD_WEBHOOK_URL` | env var | Discord webhook URL (optional) |
| `SMA_SLOW` | 150 | Slow moving average period |
| `SMA_FAST` | 50 | Fast moving average period |
| `DATA_LOOKBACK` | `"5y"` | yfinance data period |
| `BATCH_SIZE` | 10 | Stocks per Gemini batch |
| `GEMINI_RATE_LIMIT_DELAY` | 4 | Seconds between Gemini calls |
| `CHART_DIR` | `charts/` | Chart output directory |

Sector ETF mapping covers all 11 S&P sectors (XLK, XLV, XLF, XLY, XLP, XLI, XLE, XLU, XLRE, XLC, XLB).

## Discord Notifications

Only "Ready Now" and "Setting Up" tickers are sent. Each message includes:
- Embed with tier, confidence, structure, sector, earnings, patterns, entry/stop/target, reasoning
- 1-year chart as the main embedded image
- 5-year chart as an additional file attachment

## GitHub Actions

The included workflow (`.github/workflows/stock_scanner.yml`) runs every Sunday at 6pm UTC. Add `GEMINI_API_KEY` and `DISCORD_WEBHOOK_URL` as repository secrets.

You can also trigger it manually via the Actions tab (workflow_dispatch).

## Project Structure

```
stock_scanner/
├── scanner.py              # CLI entry point, orchestrates the full pipeline
├── data_fetcher.py         # yfinance data fetching, weekly stats, sector/institutional/earnings/news, Darvas box, consolidation detection
├── chart_generator.py      # Candlestick chart generation (5Y + 1Y) via mplfinance
├── gemini_analyzer.py      # Gemini API integration, analysis prompt template, batch processing
├── discord_notifier.py     # Discord webhook notifications with dual chart attachments
├── models.py               # ScanResult dataclass (all fields for JSON output)
├── config.py               # Configuration constants & env vars (SMAs, batch size, sector ETF map)
├── requirements.txt        # Python dependencies
├── stocks.csv              # Input tickers (ticker,exchange)
├── .env                    # API keys (not committed)
├── charts/                 # Generated chart PNGs organized by ticker subfolder
│   └── {TICKER}/
│       ├── daily_5y.png
│       └── daily_1y.png
├── results.json            # Scan output (not committed)
└── .github/workflows/
    └── stock_scanner.yml   # Weekly scheduled workflow
```
