#!/usr/bin/env python3
"""Stock Scanner - Analyzes charts for bullish setups using Gemini Vision API."""

import argparse
import csv
import sys

from data_fetcher import fetch_stock_data, get_weekly_summary
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


def write_results_csv(results: list[ScanResult], path: str) -> None:
    """Write scan results to CSV."""
    fieldnames = [
        "ticker", "bullish_signal", "confidence_score", "market_structure",
        "patterns", "entry_zone", "stop_loss", "target_1",
        "volume_analysis", "reasoning",
    ]
    with open(path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for r in results:
            triggers = r.technical_triggers
            writer.writerow({
                "ticker": r.ticker,
                "bullish_signal": r.bullish_signal,
                "confidence_score": r.confidence_score,
                "market_structure": r.market_structure,
                "patterns": "; ".join(r.patterns),
                "entry_zone": triggers.get("entry_zone", ""),
                "stop_loss": triggers.get("stop_loss", ""),
                "target_1": triggers.get("target_1", ""),
                "volume_analysis": r.volume_analysis,
                "reasoning": r.reasoning,
            })


def main():
    parser = argparse.ArgumentParser(description="Stock Scanner - Bullish Setup Detector")
    parser.add_argument("csv_file", help="Path to stocks CSV file (columns: ticker, exchange)")
    parser.add_argument("--no-discord", action="store_true", help="Skip Discord notifications")
    parser.add_argument("--output", default="results.csv", help="Output CSV path (default: results.csv)")
    args = parser.parse_args()

    # Read input
    stocks = read_stocks_csv(args.csv_file)
    if not stocks:
        print("No stocks found in CSV file.")
        sys.exit(1)
    print(f"Loaded {len(stocks)} stocks from {args.csv_file}")

    # Fetch data and generate charts
    analysis_queue = []  # list of (image_path, ticker, weekly_summary)
    for stock in stocks:
        ticker = stock["ticker"]
        exchange = stock["exchange"]
        print(f"\n[{ticker}] Fetching data...")
        df = fetch_stock_data(ticker, exchange)
        if df is None or df.empty:
            print(f"[{ticker}] Skipping - no data")
            continue

        print(f"[{ticker}] Generating chart...")
        chart_path = generate_chart(ticker, df)

        print(f"[{ticker}] Computing weekly summary...")
        weekly_summary = get_weekly_summary(df)

        analysis_queue.append((chart_path, ticker, weekly_summary))

    if not analysis_queue:
        print("\nNo stocks to analyze.")
        sys.exit(1)

    # Analyze with Gemini
    print(f"\nAnalyzing {len(analysis_queue)} stocks with Gemini...")
    results = analyze_batch(analysis_queue)

    # Summary
    bullish_count = sum(1 for r in results if r.bullish_signal)
    print(f"\n{'='*50}")
    print(f"Results: {bullish_count}/{len(results)} bullish signals")
    for r in results:
        signal = "BULLISH" if r.bullish_signal else "---"
        print(f"  {r.ticker:8s} {signal:8s} confidence={r.confidence_score:3d}  {r.market_structure}")
    print(f"{'='*50}")

    # Write results
    write_results_csv(results, args.output)
    print(f"\nResults saved to {args.output}")

    # Discord
    if not args.no_discord:
        print("\nSending to Discord...")
        send_to_discord(results)
    else:
        print("\nDiscord notifications skipped (--no-discord)")


if __name__ == "__main__":
    main()
