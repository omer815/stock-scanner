from dataclasses import dataclass, field


@dataclass
class ScanResult:
    ticker: str
    bullish_signal: bool = False
    confidence_score: int = 0
    market_structure: str = ""
    patterns: list[str] = field(default_factory=list)
    technical_triggers: dict = field(default_factory=dict)
    volume_analysis: str = ""
    reasoning: str = ""
    chart_path: str = ""
