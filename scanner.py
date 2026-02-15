#!/usr/bin/env python3
"""Stock Scanner - Analyzes charts for bullish setups using Gemini Vision API."""

import argparse
import csv
import json
import sys
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
)
from chart_generator import generate_chart, generate_yearly_chart
from gemini_analyzer import analyze_batch
from discord_notifier import send_to_discord
from models import ScanResult


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
    """Build a sector heatmap summary string from collected sector data.

    Returns (plain_text, ansi_formatted) tuple. Plain text is for Gemini prompt,
    ANSI formatted is for terminal display.
    """
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

    # Average 1-month return per sector, sorted by performance
    sector_avg = {}
    for sector, returns in sector_returns.items():
        sector_avg[sector] = round(sum(returns) / len(returns), 2)

    sorted_sectors = sorted(sector_avg.items(), key=lambda x: x[1], reverse=True)

    # Plain text version for Gemini
    plain_lines = ["Sector Heatmap (1M return):"]
    for rank, (sector, avg_ret) in enumerate(sorted_sectors, 1):
        indicator = "+" if avg_ret > 0 else ""
        plain_lines.append(f"  {rank}. {sector:25s} {indicator}{avg_ret}%")
    plain_text = "\n".join(plain_lines)

    # ANSI colored version for terminal
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

    # Phase 1: Fetch data, generate charts, gather enrichment data
    stock_contexts = []  # list of (daily_chart, ticker, context_data)

    for stock in stocks:
        ticker = stock["ticker"]
        exchange = stock["exchange"]
        print(f"\n[{ticker}] Fetching data...")
        df = fetch_stock_data(ticker, exchange)
        if df is None or df.empty:
            print(f"[{ticker}] Skipping - no data")
            continue

        print(f"[{ticker}] Computing technical summary...")
        tech_summary = compute_technical_summary(df)

        print(f"[{ticker}] Generating charts...")
        daily_chart = generate_chart(ticker, df, tech_summary)
        daily_chart_1y = generate_yearly_chart(ticker, df, tech_summary)

        print(f"[{ticker}] Computing weekly summary...")
        weekly_summary = get_weekly_summary(df)

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
            "sector_performance": sector_perf,
            "institutional_summary": inst_summary,
            "earnings_proximity": earnings,
            "news_headlines": news,
            "darvas_box": darvas,
            "consolidation": consol,
            "chart_path_1y": daily_chart_1y,
            "technical_summary": tech_summary,
        }

        stock_contexts.append((daily_chart, ticker, context_data))

    if not stock_contexts:
        print("\nNo stocks to analyze.")
        sys.exit(1)

    # Inject stable sector heatmap into all contexts
    for _, _, context_data in stock_contexts:
        context_data["sector_heatmap"] = sector_heatmap

    # Phase 2: Analyze with Gemini
    print(f"\nAnalyzing {len(stock_contexts)} stocks with Gemini...")
    results = analyze_batch(stock_contexts)

    # Phase 3: Summary grouped by watchlist tier
    tier_groups = {"Ready Now": [], "Setting Up": [], "Not Yet": []}
    for r in results:
        tier = r.watchlist_tier if r.watchlist_tier in tier_groups else "Not Yet"
        tier_groups[tier].append(r)

    print(f"\n{BOLD}{WHITE}{'='*70}{RESET}")
    print(f"{BOLD}{WHITE}  SCAN RESULTS{RESET}")
    print(f"{BOLD}{WHITE}{'='*70}{RESET}")

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
        print(f"\n  {bg}{BOLD} {label} {RESET}  {DIM}({len(tier_results)} stocks){RESET}")
        print(f"  {DIM}{'-'*66}{RESET}")

        for r in tier_results:
            # Ticker and signal
            if r.bullish_signal:
                signal = f"{GREEN}{BOLD}BULLISH{RESET}"
            else:
                signal = f"{DIM}---{RESET}"

            # Confidence with color
            conf = r.confidence_score
            if conf >= 70:
                conf_str = f"{GREEN}{BOLD}{conf}{RESET}"
            elif conf >= 40:
                conf_str = f"{YELLOW}{conf}{RESET}"
            else:
                conf_str = f"{RED}{conf}{RESET}"

            # Structure with color
            structure = r.market_structure
            if "uptrend" in structure.lower():
                struct_str = f"{GREEN}{structure}{RESET}"
            elif "downtrend" in structure.lower():
                struct_str = f"{RED}{structure}{RESET}"
            else:
                struct_str = f"{YELLOW}{structure}{RESET}"

            print(f"  {BOLD}{WHITE}{r.ticker:8s}{RESET} {signal:>20s}  "
                  f"conf={conf_str:>15s}  {struct_str}")

            # Sector + earnings on next line
            sector = r.sector or "N/A"
            earnings = r.earnings_proximity or "N/A"
            print(f"  {DIM}         sector: {RESET}{CYAN}{sector}{RESET}  "
                  f"{DIM}| earnings: {RESET}{earnings}")

            # News sentiment + consolidation
            sentiment = r.news_sentiment or "N/A"
            if "bullish" in sentiment.lower():
                sent_str = f"{GREEN}{sentiment}{RESET}"
            elif "bearish" in sentiment.lower():
                sent_str = f"{RED}{sentiment}{RESET}"
            else:
                sent_str = f"{DIM}{sentiment}{RESET}"
            print(f"  {DIM}         sentiment: {RESET}{sent_str}  "
                  f"{DIM}| {RESET}{r.consolidation or 'N/A'}")

            # Darvas box
            if r.darvas_box and "none" not in r.darvas_box.lower():
                print(f"  {DIM}         darvas: {RESET}{MAGENTA}{r.darvas_box}{RESET}")

            # Entry/Stop/Target
            triggers = r.technical_triggers
            if triggers:
                entry = triggers.get("entry_zone", "")
                stop = triggers.get("stop_loss", "")
                target = triggers.get("target_1", "")
                if entry or stop or target:
                    print(f"  {DIM}         entry: {RESET}{GREEN}{entry}{RESET}  "
                          f"{DIM}stop: {RESET}{RED}{stop}{RESET}  "
                          f"{DIM}target: {RESET}{CYAN}{target}{RESET}")

            # Reasoning
            if r.reasoning:
                print(f"  {DIM}         {r.reasoning}{RESET}")

            print()

    bullish_count = sum(1 for r in results if r.bullish_signal)
    print(f"{BOLD}{WHITE}{'='*70}{RESET}")
    print(f"  {BOLD}Total: {GREEN}{bullish_count}{RESET}{BOLD}/{len(results)} bullish signals{RESET}")
    print(f"  {GREEN}Ready Now: {len(tier_groups['Ready Now'])}{RESET} | "
          f"{YELLOW}Setting Up: {len(tier_groups['Setting Up'])}{RESET} | "
          f"{RED}Not Yet: {len(tier_groups['Not Yet'])}{RESET}")
    print(f"{BOLD}{WHITE}{'='*70}{RESET}")

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
