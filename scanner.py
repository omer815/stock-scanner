#!/usr/bin/env python3
"""Stock Scanner - Analyzes charts for bullish setups using Gemini Vision API."""

import argparse
import csv
import json
import sys
import textwrap
import time
from dataclasses import asdict

# ANSI color codes
RESET = "\033[0m"
BOLD = "\033[1m"
DIM = "\033[2m"
GREEN = "\033[32m"
YELLOW = "\033[33m"
RED = "\033[31m"
CYAN = "\033[36m"
MAGENTA = "\033[35m"
WHITE = "\033[97m"
BG_GREEN = "\033[42m"
BG_YELLOW = "\033[43m"
BG_RED = "\033[41m"

from data_fetcher import (
    fetch_stock_data, get_weekly_summary,
    get_sector_performance, get_institutional_ownership,
    get_earnings_date, get_news_headlines,
    detect_darvas_box, detect_consolidation,
    get_all_sector_performances, compute_technical_summary,
    get_price_history_table,
)
from chart_generator import generate_all_charts
from gemini_analyzer import analyze_stock
from discord_notifier import send_to_discord
from config import GEMINI_RATE_LIMIT_DELAY
from models import ScanResult

BOX_WIDTH = 72


def read_stocks_csv(path: str) -> list[dict]:
    """Read ticker/exchange pairs from CSV file."""
    stocks = []
    with open(path, newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            ticker = row.get("ticker", "").strip()
            exchange = row.get("exchange", "").strip()
            if ticker:
                stocks.append({"ticker": ticker, "exchange": exchange})
    return stocks


def write_results_json(results: list[ScanResult], path: str) -> None:
    """Write scan results to JSON."""
    data = [asdict(r) for r in results]
    with open(path, "w") as f:
        json.dump(data, f, indent=2)


def build_sector_heatmap(sector_data_list: list[dict]) -> tuple[str, str]:
    """Build a sector heatmap summary string from collected sector data."""
    sector_returns = {}
    for data in sector_data_list:
        sector = data.get("sector", "Unknown")
        ret_1m = data.get("1m_return", 0.0)
        if sector != "Unknown":
            if sector not in sector_returns:
                sector_returns[sector] = []
            sector_returns[sector].append(ret_1m)

    if not sector_returns:
        return "No sector data available", "No sector data available"

    sector_avg = {}
    for sector, returns in sector_returns.items():
        sector_avg[sector] = round(sum(returns) / len(returns), 2)

    sorted_sectors = sorted(sector_avg.items(), key=lambda x: x[1], reverse=True)

    plain_lines = ["Sector Heatmap (1M return):"]
    for rank, (sector, avg_ret) in enumerate(sorted_sectors, 1):
        indicator = "+" if avg_ret > 0 else ""
        plain_lines.append(f"  {rank}. {sector:25s} {indicator}{avg_ret}%")
    plain_text = "\n".join(plain_lines)

    ansi_lines = [f"{BOLD}{CYAN}Sector Heatmap (1M avg return):{RESET}"]
    for rank, (sector, avg_ret) in enumerate(sorted_sectors, 1):
        if avg_ret > 0:
            color = GREEN
            indicator = "+"
        elif avg_ret < 0:
            color = RED
            indicator = ""
        else:
            color = DIM
            indicator = ""
        ansi_lines.append(f"  {DIM}{rank}.{RESET} {sector:25s} {color}{indicator}{avg_ret}%{RESET}")
    ansi_text = "\n".join(ansi_lines)

    return plain_text, ansi_text


# ─── CLI Display Helpers ───────────────────────────────────────────────

def _conf_bar(conf: int) -> str:
    """Build a visual confidence bar like [████████░░]."""
    filled = conf // 10
    empty = 10 - filled
    return f"[{'█' * filled}{'░' * empty}]"


def _conf_color(conf: int) -> str:
    if conf >= 70:
        return GREEN + BOLD
    elif conf >= 40:
        return YELLOW
    return RED


def _structure_color(structure: str) -> str:
    s = structure.lower()
    if "stage 2" in s or "uptrend" in s or "advancing" in s:
        return GREEN
    elif "stage 4" in s or "downtrend" in s or "declining" in s:
        return RED
    elif "reversal" in s or "choch" in s:
        return CYAN
    return YELLOW


def _sentiment_str(news_sentiment) -> str:
    """Format news sentiment (can be dict or string)."""
    if isinstance(news_sentiment, dict):
        overall = news_sentiment.get("overall", "Neutral")
        reasoning = news_sentiment.get("reasoning", "")
        text = f"{overall}: {reasoning}" if reasoning else overall
    else:
        text = str(news_sentiment) if news_sentiment else "N/A"
        overall = text

    if isinstance(news_sentiment, dict):
        o = overall.lower()
    else:
        o = text.lower()

    if "bullish" in o:
        return f"{GREEN}{text}{RESET}"
    elif "bearish" in o:
        return f"{RED}{text}{RESET}"
    return f"{DIM}{text}{RESET}"


def _earnings_risk_str(earnings_risk) -> str:
    """Format earnings risk with color coding."""
    if isinstance(earnings_risk, dict):
        days = earnings_risk.get("days_until", "N/A")
        level = earnings_risk.get("risk_level", "N/A")
        impact = earnings_risk.get("impact", "")
        text = f"{days} days ({level})"
        if impact:
            text += f" — {impact}"
    else:
        text = str(earnings_risk) if earnings_risk else "N/A"
        level = text

    level_str = str(level).upper()
    if level_str in ("LOW",):
        return f"{GREEN}{text}{RESET}"
    elif level_str in ("MEDIUM",):
        return f"{YELLOW}{text}{RESET}"
    elif level_str in ("HIGH", "CRITICAL"):
        return f"{RED}{text}{RESET}"
    return f"{DIM}{text}{RESET}"


def _rr_color(rr_str: str) -> str:
    """Color the risk/reward ratio string."""
    try:
        ratio = float(rr_str.split(":")[0])
        if ratio >= 3:
            return GREEN
        elif ratio >= 2:
            return YELLOW
        return RED
    except (ValueError, IndexError):
        return DIM


def _pct_color(text: str) -> str:
    """Color a percentage string (green for +, red for -)."""
    if text.startswith("+") or (text and text[0].isdigit()):
        return GREEN
    elif text.startswith("-"):
        return RED
    return DIM


def _box_top():
    return f"  {DIM}┌{'─' * BOX_WIDTH}┐{RESET}"


def _box_bottom():
    return f"  {DIM}└{'─' * BOX_WIDTH}┘{RESET}"


def _box_sep():
    return f"  {DIM}├{'─' * BOX_WIDTH}┤{RESET}"


def _box_line(content: str):
    """Print a line inside the box. Content should already have ANSI codes."""
    return f"  {DIM}│{RESET} {content}"


def _wrap_box_lines(text: str, prefix: str = "", indent: int = 2) -> list[str]:
    """Wrap long text to fit within the box, returning multiple _box_line() calls."""
    max_width = BOX_WIDTH - indent - len(prefix)
    if max_width < 20:
        max_width = 50
    wrapped = textwrap.wrap(text, width=max_width)
    lines = []
    for i, line in enumerate(wrapped):
        if i == 0 and prefix:
            lines.append(_box_line(f"{prefix}{line}"))
        else:
            lines.append(_box_line(f"{' ' * (len(prefix))}{line}" if prefix else f"{'  ' * (indent > 0)}{line}"))
    return lines


def _safe_dict_get(obj, key, default="N/A"):
    """Safely get from a dict or return default for non-dict."""
    if isinstance(obj, dict):
        return obj.get(key, default)
    return default


def display_result(r: ScanResult):
    """Display a single stock result in a rich box-drawing layout."""
    lines = []
    lines.append(_box_top())

    # Header: Ticker, signal, confidence
    if r.bullish_signal:
        signal = f"{GREEN}{BOLD}██ BULLISH ██{RESET}"
    else:
        signal = f"{DIM}---{RESET}"

    conf = r.confidence_score
    cc = _conf_color(conf)
    bar = _conf_bar(conf)
    lines.append(_box_line(
        f"{BOLD}{WHITE}{r.ticker:14s}{RESET} {signal}   "
        f"conf: {cc}{conf}{RESET} {cc}{bar}{RESET}"
    ))

    # Market structure
    sc = _structure_color(r.market_structure)
    lines.append(_box_line(f"{'':14s} {sc}{r.market_structure}{RESET}"))

    # Stage 2 analysis (if available)
    s2 = r.stage_2_analysis
    if s2 and isinstance(s2, dict) and s2.get("phase", "N/A") != "N/A":
        phase = s2.get("phase", "N/A")
        sma_spread = s2.get("sma_spread_pct", "N/A")
        price_ext = s2.get("price_extension_from_sma150_pct", "N/A")
        weeks = s2.get("weeks_since_stage_2_entry", "N/A")

        # Color code by phase
        if "early" in phase.lower():
            phase_color = GREEN + BOLD
        elif "mid" in phase.lower():
            phase_color = YELLOW
        elif "late" in phase.lower():
            phase_color = RED
        else:
            phase_color = DIM

        lines.append(_box_line(
            f"{'':14s} {phase_color}{phase}{RESET}   "
            f"SMA Spread: {sma_spread}%   Price ext: {price_ext}%   Weeks: {weeks}"
        ))

    lines.append(_box_sep())

    # Price status line
    cps = r.current_price_status
    if cps:
        price = _safe_dict_get(cps, "price", "N/A")
        chg_1m = str(_safe_dict_get(cps, "change_1m_pct", "N/A"))
        chg_3m = str(_safe_dict_get(cps, "change_3m_pct", "N/A"))
        dist_high = str(_safe_dict_get(cps, "distance_from_52w_high_pct", "N/A"))
        lines.append(_box_line(
            f"Price: {BOLD}{WHITE}${price}{RESET}    "
            f"1M: {_pct_color(chg_1m)}{chg_1m}%{RESET}    "
            f"3M: {_pct_color(chg_3m)}{chg_3m}%{RESET}    "
            f"52wH: {_pct_color('-' + dist_high)}-{dist_high}%{RESET}"
        ))

    # Sector
    sector_s = r.sector_strength
    if sector_s and isinstance(sector_s, dict):
        sec_name = sector_s.get("sector", r.sector or "N/A")
        vs_spy = sector_s.get("vs_spy", "N/A")
        rotation = sector_s.get("rotation_trend", "")
        vs_color = GREEN if "outperform" in str(vs_spy).lower() else (RED if "underperform" in str(vs_spy).lower() else DIM)
        sector_line = f"Sector: {CYAN}{sec_name}{RESET} ({vs_color}{vs_spy}{RESET})"
        if rotation:
            sector_line += f" — {rotation}"
        lines.append(_box_line(sector_line))
    elif r.sector:
        lines.append(_box_line(f"Sector: {CYAN}{r.sector}{RESET}"))

    # Earnings + Sentiment
    earnings_str = _earnings_risk_str(r.earnings_risk if r.earnings_risk else r.earnings_proximity)
    sentiment_s = _sentiment_str(r.news_sentiment)
    lines.append(_box_line(f"Earnings: {earnings_str}   Sentiment: {sentiment_s}"))

    lines.append(_box_line(""))

    # Pattern details
    pd_ = r.pattern_details
    if pd_ and isinstance(pd_, dict):
        pat_name = pd_.get("primary_pattern", "None")
        quality = pd_.get("quality_score", "N/A")
        status = pd_.get("status", "N/A")
        lines.append(_box_line(
            f"Pattern: {MAGENTA}{pat_name}{RESET} (Quality: {quality}/10) — {status}"
        ))
    if r.patterns:
        lines.append(_box_line(f"Patterns: {MAGENTA}{', '.join(r.patterns)}{RESET}"))

    # Last breakout
    lb = r.last_breakout
    if lb and isinstance(lb, dict) and lb.get("date", "N/A") != "N/A":
        lb_date = lb.get("date", "N/A")
        lb_price = lb.get("price", "N/A")
        lb_vol = lb.get("volume_confirmation", "N/A")
        lb_success = lb.get("success", "N/A")
        lb_desc = lb.get("description", "")
        success_s = str(lb_success)
        if "successful" in success_s.lower():
            sc = GREEN
        elif "failed" in success_s.lower():
            sc = RED
        elif "progress" in success_s.lower():
            sc = YELLOW
        else:
            sc = DIM
        lb_line = (
            f"Last Breakout: {CYAN}{lb_date}{RESET} @ {BOLD}{WHITE}${lb_price}{RESET}  "
            f"Vol: {lb_vol}  {sc}{success_s}{RESET}"
        )
        lines.append(_box_line(lb_line))
        if lb_desc:
            lines.append(_box_line(f"  {DIM}{lb_desc}{RESET}"))

    # R/R and entry/stop/targets
    triggers = r.technical_triggers
    if triggers:
        rr = triggers.get("risk_reward_ratio", "N/A")
        entry = triggers.get("entry_zone", "N/A")
        stop = triggers.get("stop_loss", "N/A")
        t1 = triggers.get("target_1", "N/A")
        t2 = triggers.get("target_2", "")
        t3 = triggers.get("target_3", "")
        rr_c = _rr_color(str(rr))
        trigger_line = (
            f"R/R: {rr_c}{BOLD}{rr}{RESET}   "
            f"Entry: {GREEN}{entry}{RESET}   "
            f"Stop: {RED}{stop}{RESET}   "
            f"T1: {CYAN}{t1}{RESET}"
        )
        if t2:
            trigger_line += f"   T2: {CYAN}{t2}{RESET}"
        if t3:
            trigger_line += f"   T3: {CYAN}{t3}{RESET}"
        lines.append(_box_line(trigger_line))

    lines.append(_box_line(""))

    # Key levels
    kl = r.key_levels
    if kl and isinstance(kl, dict):
        support = kl.get("support", [])
        resistance = kl.get("resistance", [])
        if support:
            lines.append(_box_line(f"Support: {GREEN}{', '.join(str(s) for s in support)}{RESET}"))
        if resistance:
            lines.append(_box_line(f"Resistance: {RED}{', '.join(str(s) for s in resistance)}{RESET}"))

    lines.append(_box_line(""))

    # Catalysts
    if r.catalysts:
        for cat in r.catalysts:
            lines.append(_box_line(f"{GREEN}+ {cat}{RESET}"))

    # Red flags
    if r.red_flags:
        for flag in r.red_flags:
            lines.append(_box_line(f"{RED}⚠ {flag}{RESET}"))
    else:
        lines.append(_box_line(f"{DIM}⚠ None{RESET}"))

    lines.append(_box_line(""))

    # Action plan
    if r.action_plan:
        lines.append(_box_line(f"{BOLD}{WHITE}➤ {r.action_plan}{RESET}"))

    # Reasoning (full, wrapped)
    if r.reasoning:
        lines.append(_box_line(""))
        for ln in _wrap_box_lines(r.reasoning, prefix=f"{DIM}Reasoning: {RESET}"):
            lines.append(ln)

    # Volume analysis
    if r.volume_analysis:
        lines.append(_box_line(""))
        for ln in _wrap_box_lines(r.volume_analysis, prefix=f"{DIM}Volume: {RESET}"):
            lines.append(ln)

    # SMA analysis
    if r.sma_analysis:
        for ln in _wrap_box_lines(r.sma_analysis, prefix=f"{DIM}SMAs: {RESET}"):
            lines.append(ln)

    # Stage 2 assessment
    s2 = r.stage_2_analysis
    if s2 and isinstance(s2, dict) and s2.get("assessment"):
        assessment = s2.get("assessment", "")
        gc_date = s2.get("golden_cross_date", "N/A")
        if gc_date != "N/A":
            for ln in _wrap_box_lines(f"Golden Cross: {gc_date} — {assessment}", prefix=f"{DIM}Stage 2: {RESET}"):
                lines.append(ln)
        else:
            for ln in _wrap_box_lines(assessment, prefix=f"{DIM}Stage 2: {RESET}"):
                lines.append(ln)

    # Price action quality
    if r.price_action_quality:
        for ln in _wrap_box_lines(r.price_action_quality, prefix=f"{DIM}Price Action: {RESET}"):
            lines.append(ln)

    # Multi-timeframe confirmation
    mtf = r.multi_timeframe_confirmation
    if mtf and isinstance(mtf, dict):
        alignment = mtf.get("alignment", "N/A")
        weekly = mtf.get("weekly_trend", "N/A")
        monthly = mtf.get("monthly_trend", "N/A")
        daily = mtf.get("daily_setup", "N/A")
        lines.append(_box_line(""))
        lines.append(_box_line(
            f"{DIM}Timeframes:{RESET} Weekly: {weekly} | Monthly: {monthly} | Alignment: {BOLD}{alignment}{RESET}"
        ))
        if daily and daily != "N/A":
            for ln in _wrap_box_lines(str(daily), prefix=f"{DIM}  Daily: {RESET}"):
                lines.append(ln)

    # Institutional activity
    ia = r.institutional_activity
    if ia and isinstance(ia, dict):
        own_pct = ia.get("ownership_pct", "N/A")
        trend = ia.get("trend", "N/A")
        notable = ia.get("notable", "")
        ia_line = f"{DIM}Institutional:{RESET} {own_pct} ownership, trend: {trend}"
        if notable:
            ia_line += f" — {notable}"
        lines.append(_box_line(ia_line))

    # Darvas box details
    db = r.darvas_box
    if db and isinstance(db, dict):
        db_status = db.get("status", "None")
        if db_status.lower() != "none":
            db_top = db.get("box_top", "N/A")
            db_bot = db.get("box_bottom", "N/A")
            db_range = db.get("range_pct", "N/A")
            db_weeks = db.get("weeks_forming", "N/A")
            lines.append(_box_line(
                f"{DIM}Darvas:{RESET} {MAGENTA}Top: {db_top} | Bot: {db_bot} | Range: {db_range}% | "
                f"Weeks: {db_weeks} | Status: {db_status}{RESET}"
            ))
    elif db and isinstance(db, str) and "none" not in db.lower():
        lines.append(_box_line(f"{DIM}Darvas:{RESET} {MAGENTA}{db}{RESET}"))

    # Consolidation details
    consol = r.consolidation
    if consol and isinstance(consol, dict):
        atr_trend = consol.get("atr_trend", "N/A")
        vcp = consol.get("vcp_stages", "N/A")
        depth = consol.get("base_depth_pct", "N/A")
        length = consol.get("base_length_weeks", "N/A")
        quality = consol.get("base_quality", "N/A")
        lines.append(_box_line(
            f"{DIM}Consolidation:{RESET} ATR: {atr_trend} | VCP stages: {vcp} | "
            f"Depth: {depth}% | Length: {length}w | Quality: {quality}/10"
        ))
    elif consol and isinstance(consol, str):
        lines.append(_box_line(f"{DIM}Consolidation:{RESET} {consol}"))

    # Watchlist tier reasoning
    if r.watchlist_tier_reasoning:
        lines.append(_box_line(""))
        lines.append(_box_line(f"{DIM}Tier Reasoning:{RESET}"))
        for ln in r.watchlist_tier_reasoning.split("\n"):
            ln = ln.strip()
            if ln:
                lines.append(_box_line(f"  {ln}"))

    lines.append(_box_bottom())
    lines.append("")

    print("\n".join(lines))


# ─── Main ──────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Stock Scanner - Bullish Setup Detector")
    parser.add_argument("csv_file", help="Path to stocks CSV file (columns: ticker, exchange)")
    parser.add_argument("--no-discord", action="store_true", help="Skip Discord notifications")
    parser.add_argument("--output", default="results.json", help="Output JSON path (default: results.json)")
    args = parser.parse_args()

    # Read input
    stocks = read_stocks_csv(args.csv_file)
    if not stocks:
        print("No stocks found in CSV file.")
        sys.exit(1)
    print(f"Loaded {len(stocks)} stocks from {args.csv_file}")

    # Fetch stable sector heatmap (all 11 sectors, independent of stock list)
    print("\nFetching sector heatmap for all sectors...")
    all_sector_data = get_all_sector_performances()
    sector_heatmap, sector_heatmap_display = build_sector_heatmap(all_sector_data)
    print(f"\n{sector_heatmap_display}")

    # Process each ticker end-to-end: fetch → charts → enrich → analyze
    results = []

    for idx, stock in enumerate(stocks):
        ticker = stock["ticker"]
        exchange = stock["exchange"]
        print(f"\n[{ticker}] ({idx + 1}/{len(stocks)}) Fetching data...")
        df = fetch_stock_data(ticker, exchange)
        if df is None or df.empty:
            print(f"[{ticker}] Skipping - no data")
            continue

        # Small delay between data fetches to avoid overwhelming yfinance DNS/cache
        time.sleep(1)

        print(f"[{ticker}] Computing technical summary...")
        tech_summary = compute_technical_summary(df)

        print(f"[{ticker}] Generating charts (5Y, 3Y, 1Y, 3M)...")
        chart_paths = generate_all_charts(ticker, df, tech_summary)

        print(f"[{ticker}] Computing weekly summary...")
        weekly_summary = get_weekly_summary(df)

        print(f"[{ticker}] Computing price history table...")
        price_history = get_price_history_table(df)

        print(f"[{ticker}] Fetching sector performance...")
        sector_perf = get_sector_performance(ticker)

        print(f"[{ticker}] Fetching institutional ownership...")
        inst_summary = get_institutional_ownership(ticker)

        print(f"[{ticker}] Checking earnings date...")
        earnings = get_earnings_date(ticker)

        print(f"[{ticker}] Fetching news headlines...")
        news = get_news_headlines(ticker)

        print(f"[{ticker}] Detecting Darvas box...")
        darvas = detect_darvas_box(df)

        print(f"[{ticker}] Detecting consolidation...")
        consol = detect_consolidation(df)

        context_data = {
            "weekly_summary": weekly_summary,
            "price_history": price_history,
            "sector_performance": sector_perf,
            "institutional_summary": inst_summary,
            "earnings_proximity": earnings,
            "news_headlines": news,
            "darvas_box": darvas,
            "consolidation": consol,
            "chart_path_1y": chart_paths["1y"],
            "chart_path_3y": chart_paths["3y"],
            "chart_path_3m": chart_paths["3m"],
            "technical_summary": tech_summary,
            "sector_heatmap": sector_heatmap,
        }

        # Analyze with Gemini immediately
        print(f"[{ticker}] Analyzing with Gemini...")
        try:
            result = analyze_stock(chart_paths["5y"], context_data, ticker)
            results.append(result)
        except Exception as e:
            print(f"[{ticker}] Error analyzing: {e}")
            results.append(ScanResult(
                ticker=ticker, reasoning=f"Error: {e}",
                chart_path=chart_paths["5y"],
                chart_path_1y=chart_paths.get("1y", ""),
                chart_path_3y=chart_paths.get("3y", ""),
                chart_path_3m=chart_paths.get("3m", ""),
            ))

        # Rate limit delay between tickers
        if idx < len(stocks) - 1:
            time.sleep(GEMINI_RATE_LIMIT_DELAY)

    if not results:
        print("\nNo stocks to analyze.")
        sys.exit(1)

    # Summary grouped by watchlist tier
    tier_groups = {"Ready Now": [], "Setting Up": [], "Not Yet": []}
    for r in results:
        tier = r.watchlist_tier if r.watchlist_tier in tier_groups else "Not Yet"
        tier_groups[tier].append(r)

    print(f"\n{BOLD}{WHITE}{'═' * 76}{RESET}")
    print(f"{BOLD}{WHITE}  SCAN RESULTS{RESET}")
    print(f"{BOLD}{WHITE}{'═' * 76}{RESET}")

    tier_styles = {
        "Ready Now": (BG_GREEN, GREEN, "READY NOW"),
        "Setting Up": (BG_YELLOW, YELLOW, "SETTING UP"),
        "Not Yet": (BG_RED, RED, "NOT YET"),
    }

    for tier_name in ["Ready Now", "Setting Up", "Not Yet"]:
        tier_results = tier_groups[tier_name]
        if not tier_results:
            continue
        bg, fg, label = tier_styles[tier_name]
        print(f"\n  {bg}{BOLD} {label} {RESET}  {DIM}({len(tier_results)} stocks){RESET}\n")

        for r in tier_results:
            display_result(r)

    bullish_count = sum(1 for r in results if r.bullish_signal)
    print(f"{BOLD}{WHITE}{'═' * 76}{RESET}")
    print(f"  {BOLD}Total: {GREEN}{bullish_count}{RESET}{BOLD}/{len(results)} bullish signals{RESET}")
    print(f"  {GREEN}Ready Now: {len(tier_groups['Ready Now'])}{RESET} | "
          f"{YELLOW}Setting Up: {len(tier_groups['Setting Up'])}{RESET} | "
          f"{RED}Not Yet: {len(tier_groups['Not Yet'])}{RESET}")
    print(f"{BOLD}{WHITE}{'═' * 76}{RESET}")

    # Write results
    write_results_json(results, args.output)
    print(f"\nResults saved to {args.output}")

    # Discord
    if not args.no_discord:
        print("\nSending to Discord...")
        send_to_discord(results)
    else:
        print("\nDiscord notifications skipped (--no-discord)")


if __name__ == "__main__":
    main()
