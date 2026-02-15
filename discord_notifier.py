import json

import requests

from config import DISCORD_WEBHOOK_URL
from models import ScanResult


def send_to_discord(results: list[ScanResult]) -> None:
    """Send bullish signals to Discord via webhook."""
    if not DISCORD_WEBHOOK_URL:
        print("Discord webhook URL not configured, skipping notifications.")
        return

    bullish = [r for r in results if r.bullish_signal]
    if not bullish:
        _send_message("Stock Scanner completed. No bullish signals detected.")
        return

    _send_message(f"Stock Scanner found **{len(bullish)}** bullish signal(s):")

    for result in bullish:
        embed = _build_embed(result)
        payload = {"embeds": [embed]}

        # Attach chart image if available
        if result.chart_path:
            with open(result.chart_path, "rb") as f:
                files = {"file": (f"{result.ticker}_chart.png", f, "image/png")}
                payload_data = {"payload_json": json.dumps(payload)}
                resp = requests.post(DISCORD_WEBHOOK_URL, data=payload_data, files=files, timeout=30)
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

    return {
        "title": f"Bullish Signal: {result.ticker}",
        "color": 0x00FF00,
        "fields": [
            {"name": "Confidence", "value": f"{result.confidence_score}/100", "inline": True},
            {"name": "Structure", "value": result.market_structure, "inline": True},
            {"name": "Patterns", "value": ", ".join(result.patterns) or "None", "inline": False},
            {"name": "Entry Zone", "value": str(entry), "inline": True},
            {"name": "Stop Loss", "value": str(stop), "inline": True},
            {"name": "Target", "value": str(target), "inline": True},
            {"name": "Volume", "value": result.volume_analysis or "N/A", "inline": False},
            {"name": "Reasoning", "value": result.reasoning[:1024] or "N/A", "inline": False},
        ],
        "image": {"url": "attachment://file.png"} if result.chart_path else {},
    }
