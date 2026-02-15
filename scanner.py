#!/usr/bin/env python3
"""Stock Scanner - Analyzes charts for bullish setups using Gemini Vision API."""

import argparse
import csv
import json
import sys
from dataclasses import asdict

from data_fetcher import (
    fetch_stock_data, get_weekly_summary,
    get_sector_performance, get_institutional_ownership,
    get_earnings_date, get_news_headlines,
    detect_darvas_box, detect_consolidation,
)
from chart_generator import generate_chart
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


def build_sector_heatmap(sector_data_list: list[dict]) -> str:
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
        return "No sector data available"

    # Average 1-month return per sector, sorted by performance
    sector_avg = {}
    for sector, returns in sector_returns.items():
        sector_avg[sector] = round(sum(returns) / len(returns), 2)

    sorted_sectors = sorted(sector_avg.items(), key=lambda x: x[1], reverse=True)

    lines = ["Sector Heatmap (1M avg return):"]
    for rank, (sector, avg_ret) in enumerate(sorted_sectors, 1):
        indicator = "+" if avg_ret >= 0 else ""
        lines.append(f"  {rank}. {sector}: {indicator}{avg_ret}%")

    return "\n".join(lines)


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

    # Phase 1: Fetch data, generate charts, gather enrichment data
    stock_contexts = []  # list of (daily_chart, ticker, context_data)
    all_sector_data = []

    for stock in stocks:
        ticker = stock["ticker"]
        exchange = stock["exchange"]
        print(f"\n[{ticker}] Fetching data...")
        df = fetch_stock_data(ticker, exchange)
        if df is None or df.empty:
            print(f"[{ticker}] Skipping - no data")
            continue

        print(f"[{ticker}] Generating chart...")
        daily_chart = generate_chart(ticker, df)

        print(f"[{ticker}] Computing weekly summary...")
        weekly_summary = get_weekly_summary(df)

        print(f"[{ticker}] Fetching sector performance...")
        sector_perf = get_sector_performance(ticker)
        all_sector_data.append(sector_perf)

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
        }

        stock_contexts.append((daily_chart, ticker, context_data))

    if not stock_contexts:
        print("\nNo stocks to analyze.")
        sys.exit(1)

    # Phase 2: Build sector heatmap and inject into all contexts
    sector_heatmap = build_sector_heatmap(all_sector_data)
    print(f"\n{sector_heatmap}")

    for _, _, context_data in stock_contexts:
        context_data["sector_heatmap"] = sector_heatmap

    # Phase 3: Analyze with Gemini
    print(f"\nAnalyzing {len(stock_contexts)} stocks with Gemini...")
    results = analyze_batch(stock_contexts)

    # Phase 4: Summary grouped by watchlist tier
    tier_groups = {"Ready Now": [], "Setting Up": [], "Not Yet": []}
    for r in results:
        tier = r.watchlist_tier if r.watchlist_tier in tier_groups else "Not Yet"
        tier_groups[tier].append(r)

    print(f"\n{'='*60}")
    for tier_name in ["Ready Now", "Setting Up", "Not Yet"]:
        tier_results = tier_groups[tier_name]
        if tier_results:
            print(f"\n=== {tier_name.upper()} ===")
            for r in tier_results:
                signal = "BULLISH" if r.bullish_signal else "---"
                print(f"  {r.ticker:8s} {signal:8s} confidence={r.confidence_score:3d}  {r.market_structure}")

    bullish_count = sum(1 for r in results if r.bullish_signal)
    print(f"\n{'='*60}")
    print(f"Total: {bullish_count}/{len(results)} bullish signals")
    print(f"Ready Now: {len(tier_groups['Ready Now'])} | Setting Up: {len(tier_groups['Setting Up'])} | Not Yet: {len(tier_groups['Not Yet'])}")
    print(f"{'='*60}")

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
