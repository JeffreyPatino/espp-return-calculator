"""Yahoo Finance market data provider for retrieving daily close prices by date."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
import time
from typing import Iterable

import requests
import yfinance as yf


@dataclass
class YahooFinanceMarketDataProvider:
    """Loads ticker prices from Yahoo Finance chart API and returns close on or after a target date."""

    base_url: str = "https://query1.finance.yahoo.com/v8/finance/chart"
    session: requests.Session | None = None
    use_yfinance: bool = True
    max_retries: int = 5
    backoff_seconds: float = 0.75

    def _to_unix(self, value: date) -> int:
        return int(datetime(value.year, value.month, value.day, tzinfo=timezone.utc).timestamp())

    def _get_session(self) -> requests.Session:
        if self.session is None:
            self.session = requests.Session()
            # A browser-like user agent reduces anonymous throttling on Yahoo endpoints.
            self.session.headers.update(
                {
                    "User-Agent": (
                        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                        "AppleWebKit/537.36 (KHTML, like Gecko) "
                        "Chrome/125.0.0.0 Safari/537.36"
                    )
                }
            )
        return self.session

    def _fetch_chart_payload(self, ticker: str, period1: int, period2: int) -> dict:
        session = self._get_session()
        last_error: Exception | None = None

        for attempt in range(self.max_retries):
            response = session.get(
                f"{self.base_url}/{ticker}",
                params={
                    "interval": "1d",
                    "period1": period1,
                    "period2": period2,
                    "events": "history",
                },
                timeout=30,
            )
            if response.status_code == 429 and attempt < self.max_retries - 1:
                wait_seconds = self.backoff_seconds * (2**attempt)
                time.sleep(wait_seconds)
                continue
            try:
                response.raise_for_status()
                return response.json()
            except requests.RequestException as exc:
                last_error = exc
                if attempt < self.max_retries - 1:
                    wait_seconds = self.backoff_seconds * (2**attempt)
                    time.sleep(wait_seconds)
                    continue
                raise

        if last_error is not None:
            raise last_error
        raise ValueError("Failed to fetch Yahoo Finance chart payload")

    def _parse_points(self, payload: dict, ticker: str) -> list[tuple[date, float]]:
        chart = payload.get("chart", {})
        error = chart.get("error")
        if error is not None:
            description = error.get("description", "unknown error")
            raise ValueError(f"Yahoo Finance API error for {ticker}: {description}")

        result = chart.get("result") or []
        if not result:
            raise ValueError(f"Yahoo Finance returned no data for {ticker}")

        timestamps = result[0].get("timestamp") or []
        indicators = result[0].get("indicators", {})
        quotes = indicators.get("quote") or []
        closes = quotes[0].get("close") if quotes else []

        points: list[tuple[date, float]] = []
        for ts, close in zip(timestamps, closes, strict=False):
            if close is None:
                continue
            point_date = datetime.fromtimestamp(ts, tz=timezone.utc).date()
            points.append((point_date, float(close)))
        return points

    def _fetch_points_with_yfinance(self, ticker: str, start_date: date, end_date: date) -> list[tuple[date, float]]:
        # yfinance end date is exclusive, so add one day to include the requested final date.
        history = yf.download(
            tickers=ticker,
            start=start_date.isoformat(),
            end=(end_date + timedelta(days=1)).isoformat(),
            interval="1d",
            progress=False,
            auto_adjust=False,
            threads=False,
        )
        if history.empty:
            return []

        points: list[tuple[date, float]] = []
        close_series = history["Close"]
        if hasattr(close_series, "columns"):
            # yfinance may return a DataFrame with ticker-level columns even for one ticker.
            close_series = close_series.iloc[:, 0]
        for idx, close in close_series.items():
            if close is None:
                continue
            value = float(close)
            if value != value:  # NaN guard without importing math.
                continue
            points.append((idx.date(), value))
        return points

    def _load_points(self, ticker: str, start_date: date, end_date: date) -> list[tuple[date, float]]:
        points: list[tuple[date, float]] = []
        if self.use_yfinance:
            points = self._fetch_points_with_yfinance(ticker, start_date, end_date)
        if not points:
            period1 = self._to_unix(start_date)
            period2 = self._to_unix(end_date)
            payload = self._fetch_chart_payload(ticker, period1, period2)
            points = self._parse_points(payload, ticker)
        if not points:
            raise ValueError(f"No trading-day close found for {ticker}")
        return points

    def get_prices_on_or_after(self, ticker: str, target_dates: Iterable[date]) -> dict[date, float]:
        unique_dates = sorted(set(target_dates))
        if not unique_dates:
            raise ValueError("target_dates must not be empty")

        start_date = unique_dates[0]
        end_date = unique_dates[-1] + timedelta(days=21)

        points = self._load_points(ticker, start_date, end_date)

        result: dict[date, float] = {}
        point_idx = 0
        for target in unique_dates:
            while point_idx < len(points) and points[point_idx][0] < target:
                point_idx += 1
            if point_idx >= len(points):
                raise ValueError(f"No trading-day close found for {ticker} on/after {target.isoformat()}")
            result[target] = points[point_idx][1]
        return result

    def get_prices_on_or_before(self, ticker: str, target_dates: Iterable[date]) -> dict[date, float]:
        unique_dates = sorted(set(target_dates))
        if not unique_dates:
            raise ValueError("target_dates must not be empty")

        start_date = unique_dates[0] - timedelta(days=21)
        end_date = unique_dates[-1]
        points = self._load_points(ticker, start_date, end_date)

        result: dict[date, float] = {}
        point_idx = 0
        last_known_price: float | None = None
        for target in unique_dates:
            while point_idx < len(points) and points[point_idx][0] <= target:
                last_known_price = points[point_idx][1]
                point_idx += 1
            if last_known_price is None:
                raise ValueError(f"No trading-day close found for {ticker} on/before {target.isoformat()}")
            result[target] = last_known_price
        return result

    def get_price_on_or_before(self, ticker: str, on_date: date) -> float:
        return self.get_prices_on_or_before(ticker, [on_date])[on_date]

    def get_price(self, ticker: str, on_date: date) -> float:
        return self.get_prices_on_or_after(ticker, [on_date])[on_date]