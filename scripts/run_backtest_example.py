"""Tiny local runner for recurring-plan backtest without external APIs."""

import argparse
from datetime import date

from espp.adapters.in_memory_provider import InMemoryMarketDataProvider
from espp.domain.models import RecurringPlanConfig
from espp.services.backtest_service import BacktestService


def main() -> None:
    parser = argparse.ArgumentParser(description="Run a tiny in-memory ESPP backtest example")
    parser.add_argument("--salary", type=float, required=True, help="Starting annual salary for the demo run")
    args = parser.parse_args()

    ticker = "UNH"
    prices = {
        (ticker, date(2024, 12, 31)): 99.0,
        (ticker, date(2025, 6, 30)): 100.0,
        (ticker, date(2025, 7, 1)): 101.0,
        (ticker, date(2025, 12, 31)): 110.0,
        (ticker, date(2026, 1, 1)): 111.0,
    }

    report = BacktestService().run_recurring_plan(
        RecurringPlanConfig(
            ticker=ticker,
            discount_rate=0.10,
            starting_salary=args.salary,
            espp_allocation_pct=0.10,
            first_purchase_date=date(2025, 1, 1),
            last_purchase_date=date(2025, 7, 1),
            purchase_frequency_months=6,
            settlement_lag_business_days=1,
        ),
        InMemoryMarketDataProvider(prices),
    )
    print(report)


if __name__ == "__main__":
    main()







