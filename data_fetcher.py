import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime

from config import DATA_LOOKBACK, SECTOR_ETF_MAP


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


def get_sector_performance(ticker_symbol: str) -> dict:
    """Get sector info and ETF performance for a ticker."""
    try:
        ticker = yf.Ticker(ticker_symbol)
        info = ticker.info
        sector = info.get("sector", "Unknown")
    except Exception:
        return {"sector": "Unknown", "etf": "N/A", "1m_return": 0.0, "3m_return": 0.0}

    etf_symbol = SECTOR_ETF_MAP.get(sector)
    if not etf_symbol:
        return {"sector": sector, "etf": "N/A", "1m_return": 0.0, "3m_return": 0.0}

    try:
        etf_df = yf.download(etf_symbol, period="6mo", progress=False)
        if isinstance(etf_df.columns, pd.MultiIndex):
            etf_df.columns = etf_df.columns.get_level_values(0)

        if len(etf_df) < 2:
            return {"sector": sector, "etf": etf_symbol, "1m_return": 0.0, "3m_return": 0.0}

        latest = float(etf_df["Close"].iloc[-1])

        # 1-month return (~21 trading days)
        idx_1m = min(21, len(etf_df) - 1)
        close_1m = float(etf_df["Close"].iloc[-idx_1m - 1])
        ret_1m = round((latest / close_1m - 1) * 100, 2)

        # 3-month return (~63 trading days)
        idx_3m = min(63, len(etf_df) - 1)
        close_3m = float(etf_df["Close"].iloc[-idx_3m - 1])
        ret_3m = round((latest / close_3m - 1) * 100, 2)

        return {"sector": sector, "etf": etf_symbol, "1m_return": ret_1m, "3m_return": ret_3m}
    except Exception:
        return {"sector": sector, "etf": etf_symbol, "1m_return": 0.0, "3m_return": 0.0}


def get_institutional_ownership(ticker_symbol: str) -> str:
    """Get institutional ownership summary."""
    try:
        ticker = yf.Ticker(ticker_symbol)

        # Major holders percentage
        major = ticker.major_holders
        if major is not None and not major.empty:
            holders_pct = major.to_string(index=False, header=False)
        else:
            holders_pct = "N/A"

        # Top 5 institutional holders
        inst = ticker.institutional_holders
        if inst is not None and not inst.empty:
            top5 = inst.head(5)
            holder_lines = []
            for _, row in top5.iterrows():
                name = row.get("Holder", "Unknown")
                shares = row.get("Shares", 0)
                holder_lines.append(f"  {name}: {shares:,.0f} shares")
            inst_str = "\n".join(holder_lines)
        else:
            inst_str = "No institutional holder data"

        return f"Major holders:\n{holders_pct}\n\nTop institutional holders:\n{inst_str}"
    except Exception as e:
        return f"Institutional data unavailable: {e}"


def get_earnings_date(ticker_symbol: str) -> str:
    """Get next earnings date and days until."""
    try:
        ticker = yf.Ticker(ticker_symbol)
        earnings = ticker.get_earnings_dates(limit=4)
        if earnings is None or earnings.empty:
            return "No upcoming earnings found"

        now = datetime.now()
        for date in earnings.index:
            dt = date.to_pydatetime().replace(tzinfo=None)
            if dt > now:
                days = (dt - now).days
                return f"Next earnings in {days} days ({dt.strftime('%Y-%m-%d')})"

        return "No upcoming earnings found"
    except Exception:
        return "No upcoming earnings found"


def get_news_headlines(ticker_symbol: str) -> list[str]:
    """Get recent news headlines for a ticker."""
    try:
        ticker = yf.Ticker(ticker_symbol)
        news = ticker.news
        if not news:
            return []
        headlines = []
        for item in news[:10]:
            title = item.get("title", "")
            if title:
                headlines.append(title)
        return headlines
    except Exception:
        return []


def get_all_sector_performances() -> list[dict]:
    """Fetch 1M return for all 11 sector ETFs, independent of the stock list."""
    etf_symbols = list(SECTOR_ETF_MAP.values())
    sector_to_etf = {v: k for k, v in SECTOR_ETF_MAP.items()}

    try:
        df = yf.download(etf_symbols, period="6mo", progress=False)
        if df.empty:
            return []
    except Exception:
        return []

    results = []
    for etf in etf_symbols:
        sector = sector_to_etf[etf]
        try:
            if isinstance(df.columns, pd.MultiIndex):
                close = df["Close"][etf].dropna()
            else:
                close = df["Close"].dropna()

            if len(close) < 2:
                results.append({"sector": sector, "etf": etf, "1m_return": 0.0})
                continue

            latest = float(close.iloc[-1])
            idx_1m = min(21, len(close) - 1)
            close_1m = float(close.iloc[-idx_1m - 1])
            ret_1m = round((latest / close_1m - 1) * 100, 2)
            results.append({"sector": sector, "etf": etf, "1m_return": ret_1m})
        except Exception:
            results.append({"sector": sector, "etf": etf, "1m_return": 0.0})

    return results


def compute_technical_summary(df: pd.DataFrame) -> dict:
    """Compute key technical data for text-based AI consumption."""
    close = float(df["Close"].iloc[-1])
    sma50 = float(df["Close"].rolling(50).mean().iloc[-1])
    sma150 = float(df["Close"].rolling(150).mean().iloc[-1])

    return {
        "current_close": round(close, 2),
        "sma_50": round(sma50, 2),
        "sma_150": round(sma150, 2),
        "price_vs_sma50": "above" if close > sma50 else "below",
        "price_vs_sma150": "above" if close > sma150 else "below",
        "sma50_vs_sma150": "above (bullish)" if sma50 > sma150 else "below (bearish)",
        "sma50_sma150_spread_pct": round((sma50 / sma150 - 1) * 100, 2),
        "price_to_sma50_pct": round((close / sma50 - 1) * 100, 2),
        "price_to_sma150_pct": round((close / sma150 - 1) * 100, 2),
    }


def detect_darvas_box(df: pd.DataFrame) -> str:
    """Detect Darvas box pattern in recent price action."""
    if len(df) < 20:
        return "Darvas box: none (insufficient data)"

    recent = df.tail(20)
    highs = recent["High"].values
    lows = recent["Low"].values
    closes = recent["Close"].values

    # Find the highest high (box top)
    box_top_idx = np.argmax(highs)
    box_top = float(highs[box_top_idx])

    # Check for 3+ days after the high where high doesn't exceed box top
    days_after = len(highs) - box_top_idx - 1
    if days_after < 3:
        return "Darvas box: none (new high too recent)"

    # Check if highs after box_top_idx stay below box_top
    subsequent_highs = highs[box_top_idx + 1:]
    days_contained = 0
    for h in subsequent_highs:
        if h <= box_top:
            days_contained += 1
        else:
            return "Darvas box: none (high exceeded)"

    if days_contained < 3:
        return "Darvas box: none (insufficient consolidation)"

    # Box bottom = lowest low during consolidation period
    consolidation_lows = lows[box_top_idx + 1:]
    box_bottom = float(np.min(consolidation_lows))

    # Check current status
    current_close = float(closes[-1])
    if current_close > box_top:
        status = "breakout"
    elif current_close >= box_bottom:
        status = "within"
    else:
        status = "breakdown"

    return f"Darvas box: top=${box_top:.2f}, bottom=${box_bottom:.2f}, status={status}"


def detect_consolidation(df: pd.DataFrame, window: int = 20) -> str:
    """Detect consolidation via ATR compression."""
    if len(df) < 50:
        return "No consolidation (insufficient data)"

    # ATR(14)
    high = df["High"]
    low = df["Low"]
    close = df["Close"]

    tr = pd.concat([
        high - low,
        (high - close.shift(1)).abs(),
        (low - close.shift(1)).abs(),
    ], axis=1).max(axis=1)

    atr_14 = tr.rolling(14).mean()

    current_atr = float(atr_14.iloc[-1])
    avg_atr_50 = float(atr_14.tail(50).mean())

    if avg_atr_50 == 0:
        return "No consolidation (zero ATR)"

    atr_ratio = round(current_atr / avg_atr_50, 2)

    # Range compression over window
    recent = df.tail(window)
    highest = float(recent["High"].max())
    lowest = float(recent["Low"].min())
    avg_close = float(recent["Close"].mean())
    range_pct = round((highest - lowest) / avg_close * 100, 2) if avg_close > 0 else 0

    if atr_ratio < 0.5:
        return f"Tight consolidation ({window} days, ATR ratio: {atr_ratio}, range: {range_pct}%)"
    elif atr_ratio < 0.75:
        return f"Moderate consolidation ({window} days, ATR ratio: {atr_ratio}, range: {range_pct}%)"
    else:
        return f"No consolidation (ATR ratio: {atr_ratio}, range: {range_pct}%)"
