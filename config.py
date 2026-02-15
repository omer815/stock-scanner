import os

from dotenv import load_dotenv

load_dotenv()

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
DISCORD_WEBHOOK_URL = os.environ.get("DISCORD_WEBHOOK_URL", "")

SMA_PERIOD = 150
DATA_LOOKBACK = "1y"
BATCH_SIZE = 10
CHART_DIR = os.path.join(os.path.dirname(__file__), "charts")

os.makedirs(CHART_DIR, exist_ok=True)
