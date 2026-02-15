import os

import mplfinance as mpf
import pandas as pd

from config import SMA_SLOW, SMA_FAST, CHART_DIR


def generate_chart(ticker: str, df: pd.DataFrame) -> str:
    """Generate a candlestick chart with SMA 50, SMA 150 and volume, saved as PNG."""
    sma_slow = df["Close"].rolling(window=SMA_SLOW).mean()
    sma_fast = df["Close"].rolling(window=SMA_FAST).mean()

    plots = [
        mpf.make_addplot(sma_slow, color="cyan", width=1.5, label=f"SMA {SMA_SLOW}"),
        mpf.make_addplot(sma_fast, color="yellow", width=1.2, label=f"SMA {SMA_FAST}"),
    ]

    filename = f"{ticker.replace('.', '_')}.png"
    filepath = os.path.join(CHART_DIR, filename)

    mpf.plot(
        df,
        type="candle",
        style="nightclouds",
        title=f"{ticker} - Daily",
        volume=True,
        addplot=plots,
        savefig=dict(fname=filepath, dpi=150, bbox_inches="tight"),
        figscale=1.3,
        warn_too_much_data=10000,
    )

    return filepath


