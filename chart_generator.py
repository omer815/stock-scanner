import os

import mplfinance as mpf
import pandas as pd

from config import SMA_SLOW, SMA_FAST, CHART_DIR


def _get_ticker_dir(ticker: str) -> str:
    """Get or create per-ticker chart directory."""
    ticker_dir = os.path.join(CHART_DIR, ticker.replace(".", "_"))
    os.makedirs(ticker_dir, exist_ok=True)
    return ticker_dir


def _make_sma_plots(df: pd.DataFrame) -> list:
    """Create SMA addplot overlays for a given dataframe."""
    sma_slow = df["Close"].rolling(window=SMA_SLOW).mean()
    sma_fast = df["Close"].rolling(window=SMA_FAST).mean()
    return [
        mpf.make_addplot(sma_slow, color="cyan", width=1.5, label=f"SMA {SMA_SLOW}"),
        mpf.make_addplot(sma_fast, color="yellow", width=1.2, label=f"SMA {SMA_FAST}"),
    ]


def generate_chart(ticker: str, df: pd.DataFrame) -> str:
    """Generate a 5-year candlestick chart with SMA 50, SMA 150 and volume, saved as PNG."""
    ticker_dir = _get_ticker_dir(ticker)
    filepath = os.path.join(ticker_dir, "daily_5y.png")

    mpf.plot(
        df,
        type="candle",
        style="nightclouds",
        title=f"{ticker} - Daily (5Y)",
        volume=True,
        addplot=_make_sma_plots(df),
        savefig=dict(fname=filepath, dpi=150, bbox_inches="tight"),
        figscale=1.3,
        warn_too_much_data=10000,
    )

    return filepath


def generate_yearly_chart(ticker: str, df: pd.DataFrame) -> str:
    """Generate a 1-year candlestick chart with SMA 50, SMA 150 and volume, saved as PNG."""
    df_1y = df.tail(252)
    ticker_dir = _get_ticker_dir(ticker)
    filepath = os.path.join(ticker_dir, "daily_1y.png")

    mpf.plot(
        df_1y,
        type="candle",
        style="nightclouds",
        title=f"{ticker} - Daily (1Y)",
        volume=True,
        addplot=_make_sma_plots(df_1y),
        savefig=dict(fname=filepath, dpi=150, bbox_inches="tight"),
        figscale=1.3,
        warn_too_much_data=10000,
    )

    return filepath


