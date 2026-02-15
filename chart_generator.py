import os

import mplfinance as mpf
import pandas as pd

from config import SMA_PERIOD, CHART_DIR


def generate_chart(ticker: str, df: pd.DataFrame) -> str:
    """Generate a candlestick chart with SMA 150 and volume, saved as PNG."""
    sma = df["Close"].rolling(window=SMA_PERIOD).mean()
    sma_plot = mpf.make_addplot(sma, color="cyan", width=1.5, label=f"SMA {SMA_PERIOD}")

    filename = f"{ticker.replace('.', '_')}.png"
    filepath = os.path.join(CHART_DIR, filename)

    mpf.plot(
        df,
        type="candle",
        style="nightclouds",
        title=f"{ticker} - Daily",
        volume=True,
        addplot=sma_plot,
        savefig=dict(fname=filepath, dpi=150, bbox_inches="tight"),
        figscale=1.3,
        warn_too_much_data=10000,
    )

    return filepath
