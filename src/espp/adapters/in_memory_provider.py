"""Simple in-memory market data provider useful for tests and local demos."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Iterable


@dataclass
class InMemoryMarketDataProvider:
    """Maps (ticker, date) to prices for deterministic scenario evaluation."""

    prices: dict[tuple[str, date], float]

    def get_price(self, ticker: str, on_date: date) -> float:
        key = (ticker, on_date)
        if key not in self.prices:
            raise KeyError(f"Missing price for {ticker} on {on_date.isoformat()}")
        return self.prices[key]

    def get_price_on_or_before(self, ticker: str, on_date: date) -> float:
        matching_dates = [dt for sym, dt in self.prices if sym == ticker and dt <= on_date]
        if not matching_dates:
            raise KeyError(f"Missing price for {ticker} on or before {on_date.isoformat()}")
        closest = max(matching_dates)
        return self.prices[(ticker, closest)]

    def get_prices_on_or_after(self, ticker: str, target_dates: Iterable[date]) -> dict[date, float]:
        result: dict[date, float] = {}
        ticker_dates = sorted(dt for sym, dt in self.prices if sym == ticker)
        for target in target_dates:
            candidates = [dt for dt in ticker_dates if dt >= target]
            if not candidates:
                raise KeyError(f"Missing price for {ticker} on or after {target.isoformat()}")
            result[target] = self.prices[(ticker, candidates[0])]
        return result

    def get_prices_on_or_before(self, ticker: str, target_dates: Iterable[date]) -> dict[date, float]:
        result: dict[date, float] = {}
        ticker_dates = sorted(dt for sym, dt in self.prices if sym == ticker)
        for target in target_dates:
            candidates = [dt for dt in ticker_dates if dt <= target]
            if not candidates:
                raise KeyError(f"Missing price for {ticker} on or before {target.isoformat()}")
            result[target] = self.prices[(ticker, candidates[-1])]
        return result


