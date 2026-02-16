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
    sma_analysis: str = ""
    stage_2_analysis: dict = field(default_factory=dict)
    reasoning: str = ""
    chart_path: str = ""
    chart_path_1y: str = ""
    chart_path_3y: str = ""
    chart_path_3m: str = ""
    sector: str = ""
    sector_performance: str = ""
    institutional_summary: str = ""
    earnings_proximity: str = ""
    news_sentiment: str = ""
    watchlist_tier: str = ""
    darvas_box: str = ""
    consolidation: str = ""
    # New fields for expanded analysis
    current_price_status: dict = field(default_factory=dict)
    pattern_details: dict = field(default_factory=dict)
    price_action_quality: str = ""
    watchlist_tier_reasoning: str = ""
    sector_strength: dict = field(default_factory=dict)
    institutional_activity: dict = field(default_factory=dict)
    earnings_risk: dict = field(default_factory=dict)
    key_levels: dict = field(default_factory=dict)
    red_flags: list[str] = field(default_factory=list)
    catalysts: list[str] = field(default_factory=list)
    multi_timeframe_confirmation: dict = field(default_factory=dict)
    last_breakout: dict = field(default_factory=dict)
    action_plan: str = ""
