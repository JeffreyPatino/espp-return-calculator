"""Port definition for market data providers used by the scenario service."""

from __future__ import annotations

from datetime import date
from typing import Protocol


class MarketDataProvider(Protocol):
    """Provider contract for loading ticker prices on specific dates."""

    def get_price(self, ticker: str, on_date: date) -> float:
        """Return the price for ticker on the given date, or raise if unavailable."""

