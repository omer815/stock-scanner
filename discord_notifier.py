import json

import requests

from config import DISCORD_WEBHOOK_URL
from models import ScanResult


def send_to_discord(results: list[ScanResult]) -> None:
    """Send Ready Now and Setting Up signals to Discord via webhook."""
    if not DISCORD_WEBHOOK_URL:
        print("Discord webhook URL not configured, skipping notifications.")
        return

    actionable = [r for r in results if r.watchlist_tier in ("Ready Now", "Setting Up")]
    if not actionable:
        _send_message("Stock Scanner completed. No actionable signals detected.")
        return

    ready = [r for r in actionable if r.watchlist_tier == "Ready Now"]
    setting_up = [r for r in actionable if r.watchlist_tier == "Setting Up"]
    _send_message(
        f"Stock Scanner found **{len(ready)}** Ready Now and "
        f"**{len(setting_up)}** Setting Up signal(s):"
    )

    for result in actionable:
        embed = _build_embed(result)
        payload = {"embeds": [embed]}

        # Attach chart images (1-year as main embed image, 5-year as additional attachment)
        if result.chart_path_1y or result.chart_path:
            files = {}
            if result.chart_path_1y:
                f_1y = open(result.chart_path_1y, "rb")
                files["file"] = (f"{result.ticker}_1y.png", f_1y, "image/png")
            if result.chart_path:
                f_5y = open(result.chart_path, "rb")
                key = "file2" if "file" in files else "file"
                files[key] = (f"{result.ticker}_5y.png", f_5y, "image/png")
            payload_data = {"payload_json": json.dumps(payload)}
            resp = requests.post(DISCORD_WEBHOOK_URL, data=payload_data, files=files, timeout=30)
            for f_obj in files.values():
                f_obj[1].close()
        else:
            resp = requests.post(DISCORD_WEBHOOK_URL, json=payload, timeout=30)

        if resp.status_code not in (200, 204):
            print(f"  Discord error for {result.ticker}: {resp.status_code} {resp.text}")
        else:
            print(f"  Sent {result.ticker} to Discord")


def _send_message(content: str) -> None:
    resp = requests.post(DISCORD_WEBHOOK_URL, json={"content": content}, timeout=30)
    if resp.status_code not in (200, 204):
        print(f"  Discord error: {resp.status_code} {resp.text}")


def _build_embed(result: ScanResult) -> dict:
    triggers = result.technical_triggers
    entry = triggers.get("entry_zone", "N/A")
    stop = triggers.get("stop_loss", "N/A")
    target = triggers.get("target_1", "N/A")

    # Color coding by tier
    if result.watchlist_tier == "Ready Now":
        color = 0x00FF00  # Green
        tier_label = "Ready Now"
    else:
        color = 0xFFFF00  # Yellow
        tier_label = "Setting Up"

    return {
        "title": f"{tier_label}: {result.ticker}",
        "color": color,
        "fields": [
            {"name": "Watchlist Tier", "value": tier_label, "inline": True},
            {"name": "Confidence", "value": f"{result.confidence_score}/100", "inline": True},
            {"name": "Structure", "value": result.market_structure, "inline": True},
            {"name": "Sector", "value": result.sector_performance or "N/A", "inline": False},
            {"name": "Earnings", "value": result.earnings_proximity or "N/A", "inline": True},
            {"name": "News Sentiment", "value": result.news_sentiment or "N/A", "inline": True},
            {"name": "Patterns", "value": ", ".join(result.patterns) or "None", "inline": False},
            {"name": "Entry Zone", "value": str(entry), "inline": True},
            {"name": "Stop Loss", "value": str(stop), "inline": True},
            {"name": "Target", "value": str(target), "inline": True},
            {"name": "Volume", "value": result.volume_analysis or "N/A", "inline": False},
            {"name": "Reasoning", "value": result.reasoning[:1024] or "N/A", "inline": False},
        ],
        "image": {"url": f"attachment://{result.ticker}_1y.png"} if result.chart_path_1y else (
            {"url": f"attachment://{result.ticker}_5y.png"} if result.chart_path else {}
        ),
    }
