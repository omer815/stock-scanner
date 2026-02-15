import os

from dotenv import load_dotenv

load_dotenv()

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
DISCORD_WEBHOOK_URL = os.environ.get("DISCORD_WEBHOOK_URL", "")

SMA_SLOW = 150
SMA_FAST = 50
DATA_LOOKBACK = "5y"
BATCH_SIZE = 10
GEMINI_RATE_LIMIT_DELAY = 4
CHART_DIR = os.path.join(os.path.dirname(__file__), "charts")

os.makedirs(CHART_DIR, exist_ok=True)

SECTOR_ETF_MAP = {
    "Technology": "XLK",
    "Healthcare": "XLV",
    "Financial Services": "XLF",
    "Consumer Cyclical": "XLY",
    "Consumer Defensive": "XLP",
    "Industrials": "XLI",
    "Energy": "XLE",
    "Utilities": "XLU",
    "Real Estate": "XLRE",
    "Communication Services": "XLC",
    "Basic Materials": "XLB",
}
