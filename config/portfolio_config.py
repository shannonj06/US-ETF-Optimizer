
from dataclasses import dataclass

@dataclass
class PortfolioConfig:
    min_weight:              float = 0.01
    max_weight:              float = 0.25
    max_weight_high_yield:   float = 0.35
    yield_top_quantile:      float = 0.75
    correlation_threshold:   float = 0.85
    max_style_concentration: float = 0.75   # max 3 out of 4 ETFs same style
    min_etfs_per_style:      int   = 1      # at least 1 style represented


PORTFOLIO_CONFIG = PortfolioConfig()    