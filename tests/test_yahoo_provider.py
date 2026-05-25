from __future__ import annotations

from datetime import date

from espp.adapters.yahoo_provider import YahooFinanceMarketDataProvider


class _FakeResponse:
    def __init__(self, payload: dict, status_code: int = 200) -> None:
        self._payload = payload
        self.status_code = status_code

    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict:
        return self._payload


class _FakeSession:
    def __init__(self, payload: dict, status_code: int = 200) -> None:
        self.payload = payload
        self.status_code = status_code

    def get(self, url: str, params: dict, timeout: int) -> _FakeResponse:  # noqa: ARG002
        return _FakeResponse(self.payload, self.status_code)


def test_yahoo_provider_returns_first_available_close() -> None:
    payload = {
        "chart": {
            "result": [
                {
                    "timestamp": [1735776000, 1735862400],
                    "indicators": {
                        "quote": [
                            {
                                "close": [525.0, 530.0],
                            }
                        ]
                    },
                }
            ],
            "error": None,
        }
    }
    provider = YahooFinanceMarketDataProvider(session=_FakeSession(payload), use_yfinance=False)
    price = provider.get_price("UNH", date(2025, 1, 2))
    assert price == 525.0


def test_yahoo_provider_bulk_lookup_returns_next_available_day() -> None:
    payload = {
        "chart": {
            "result": [
                {
                    "timestamp": [1735776000, 1735862400, 1736121600],
                    "indicators": {
                        "quote": [
                            {
                                "close": [525.0, 530.0, 531.0],
                            }
                        ]
                    },
                }
            ],
            "error": None,
        }
    }
    provider = YahooFinanceMarketDataProvider(session=_FakeSession(payload), use_yfinance=False)
    prices = provider.get_prices_on_or_after(
        "UNH",
        [date(2025, 1, 2), date(2025, 1, 4)],
    )
    assert prices[date(2025, 1, 2)] == 525.0
    assert prices[date(2025, 1, 4)] == 531.0


def test_yahoo_provider_bulk_lookup_returns_previous_available_day() -> None:
    payload = {
        "chart": {
            "result": [
                {
                    "timestamp": [1735603200, 1735776000],
                    "indicators": {
                        "quote": [
                            {
                                "close": [520.0, 525.0],
                            }
                        ]
                    },
                }
            ],
            "error": None,
        }
    }
    provider = YahooFinanceMarketDataProvider(session=_FakeSession(payload), use_yfinance=False)
    prices = provider.get_prices_on_or_before("UNH", [date(2025, 1, 1)])
    assert prices[date(2025, 1, 1)] == 520.0





