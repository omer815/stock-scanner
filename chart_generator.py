import os

import mplfinance as mpf
import pandas as pd

from config import SMA_SLOW, SMA_FAST, CHART_DIR

# Light theme with green/red volume bars for AI readability
_MARKET_COLORS = mpf.make_marketcolors(
    up="green", down="red",
    volume={"up": "green", "down": "red"},
)
_STYLE = mpf.make_mpf_style(
    base_mpf_style="classic",
    marketcolors=_MARKET_COLORS,
    gridstyle="-",
    gridcolor="#e0e0e0",
)


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


def _build_title(ticker: str, label: str, tech_summary: dict | None) -> str:
    """Build chart title with optional technical data annotation."""
    if tech_summary:
        close = tech_summary["current_close"]
        sma50 = tech_summary["sma_50"]
        sma150 = tech_summary["sma_150"]
        return f"{ticker} | Close: ${close} | SMA50: ${sma50} | SMA150: ${sma150}"
    return f"{ticker} - Daily ({label})"


def generate_chart(ticker: str, df: pd.DataFrame, tech_summary: dict = None) -> str:
    """Generate a 5-year candlestick chart with SMA 50, SMA 150 and volume, saved as PNG."""
    ticker_dir = _get_ticker_dir(ticker)
    filepath = os.path.join(ticker_dir, "daily_5y.png")

    mpf.plot(
        df,
        type="candle",
        style=_STYLE,
        title=_build_title(ticker, "5Y", tech_summary),
        volume=True,
        addplot=_make_sma_plots(df),
        savefig=dict(fname=filepath, dpi=200, bbox_inches="tight"),
        figscale=1.3,
        warn_too_much_data=10000,
    )

    return filepath


def generate_yearly_chart(ticker: str, df: pd.DataFrame, tech_summary: dict = None) -> str:
    """Generate a 1-year candlestick chart with SMA 50, SMA 150 and volume, saved as PNG."""
    df_1y = df.tail(252)
    ticker_dir = _get_ticker_dir(ticker)
    filepath = os.path.join(ticker_dir, "daily_1y.png")

    mpf.plot(
        df_1y,
        type="candle",
        style=_STYLE,
        title=_build_title(ticker, "1Y", tech_summary),
        volume=True,
        addplot=_make_sma_plots(df_1y),
        savefig=dict(fname=filepath, dpi=200, bbox_inches="tight"),
        figscale=1.5,
        warn_too_much_data=10000,
    )

    return filepath


