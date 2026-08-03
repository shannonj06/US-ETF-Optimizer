"""Data-access layer for the Cash Analysis feature.

Repositories isolate the rest of the app from *where* market data comes from
(currently Yahoo Finance via yfinance). Both the price and dividend repositories
read from a single cached, tz-normalized history frame per ticker, so a full
analysis makes at most one external request per ticker regardless of how many
tables and charts consume the result.
"""

from .market_data_repository import MarketDataRepository
from .dividend_repository import DividendRepository

__all__ = ["MarketDataRepository", "DividendRepository"]
