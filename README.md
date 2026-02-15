# Stock Scanner

A modular Python stock scanner that analyzes candlestick charts for bullish setups using Gemini Vision API. Generates charts with SMA 150 and volume, sends them to Gemini 2.5 Flash for technical analysis, and optionally notifies a Discord channel with results.

## Features

- Fetches 1 year of daily OHLCV data via yfinance
- Generates candlestick charts with SMA 150 overlay and volume panel
- Analyzes charts using Gemini 2.5 Flash vision for bullish setups (price action, VSA, structural shifts)
- Outputs structured JSON results with confidence scores, patterns, entry/stop/target levels
- Optional Discord webhook notifications for bullish signals
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

Results are saved as JSON with the following structure per ticker:

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
  "reasoning": "...",
  "chart_path": "charts/TGT.png"
}
```

Charts are saved to the `charts/` directory as PNG files.

## GitHub Actions

The included workflow (`.github/workflows/stock_scanner.yml`) runs every Sunday at 6pm UTC. Add `GEMINI_API_KEY` and `DISCORD_WEBHOOK_URL` as repository secrets.

You can also trigger it manually via the Actions tab (workflow_dispatch).

## Project Structure

```
├── scanner.py              # CLI entry point
├── data_fetcher.py         # yfinance data fetching + weekly summary
├── chart_generator.py      # Candlestick chart generation (mplfinance)
├── gemini_analyzer.py      # Gemini API integration + analysis prompt
├── discord_notifier.py     # Discord webhook notifications
├── models.py               # ScanResult dataclass
├── config.py               # Configuration & env vars
├── requirements.txt        # Python dependencies
├── stocks.csv              # Input tickers
└── .github/workflows/
    └── stock_scanner.yml   # Weekly scheduled workflow
```
