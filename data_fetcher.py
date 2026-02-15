import yfinance as yf
import pandas as pd

from config import DATA_LOOKBACK


def fetch_stock_data(ticker: str, exchange: str = "") -> pd.DataFrame | None:
    """Fetch 1 year of daily OHLCV data for a ticker."""
    symbol = f"{ticker}.{exchange}" if exchange else ticker
    try:
        df = yf.download(symbol, period=DATA_LOOKBACK, progress=False)
        if df.empty:
            print(f"  No data returned for {symbol}")
            return None
        # Flatten multi-level columns if present
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
        return df
    except Exception as e:
        print(f"  Error fetching {symbol}: {e}")
        return None


def get_weekly_summary(df: pd.DataFrame) -> dict:
    """Compute key weekly stats from daily data."""
    weekly = df.resample("W").agg({
        "Open": "first",
        "High": "max",
        "Low": "min",
        "Close": "last",
        "Volume": "sum",
    }).dropna()

    latest_close = float(df["Close"].iloc[-1])
    avg_weekly_volume = int(weekly["Volume"].tail(20).mean())
    high_52w = float(df["High"].max())
    low_52w = float(df["Low"].min())

    # 4-week trend: compare last close to close 4 weeks ago
    if len(weekly) >= 5:
        close_4w_ago = float(weekly["Close"].iloc[-5])
        trend = "Up" if latest_close > close_4w_ago else "Down"
    else:
        trend = "Insufficient data"

    return {
        "latest_close": round(latest_close, 2),
        "avg_weekly_volume": avg_weekly_volume,
        "4_week_trend": trend,
        "distance_from_52w_high": f"{round((1 - latest_close / high_52w) * 100, 1)}%",
        "distance_from_52w_low": f"{round((latest_close / low_52w - 1) * 100, 1)}%",
        "52w_high": round(high_52w, 2),
        "52w_low": round(low_52w, 2),
    }
