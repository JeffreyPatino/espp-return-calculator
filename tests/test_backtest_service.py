from datetime import date

import pytest

from espp.adapters.in_memory_provider import InMemoryMarketDataProvider
from espp.domain.models import RecurringPlanConfig
from espp.services.backtest_service import BacktestService


def _with_benchmark_prices(prices: dict[tuple[str, date], float], *, ticker: str) -> dict[tuple[str, date], float]:
    merged = dict(prices)
    for (sym, dt), value in list(prices.items()):
        if sym == ticker:
            merged[("SPY", dt)] = value
    return merged


def test_run_recurring_plan_returns_cycle_breakdown_and_overall_metrics() -> None:
    ticker = "UNH"
    prices = {
        (ticker, date(2024, 6, 28)): 98.0,
        (ticker, date(2024, 12, 31)): 99.0,
        (ticker, date(2025, 1, 1)): 100.0,
        (ticker, date(2025, 6, 30)): 100.0,
        (ticker, date(2025, 7, 1)): 101.0,
    }
    provider = InMemoryMarketDataProvider(prices=_with_benchmark_prices(prices, ticker=ticker))
    config = RecurringPlanConfig(
        ticker=ticker,
        discount_rate=0.10,
        starting_salary=12000.0,
        espp_allocation_pct=0.10,
        first_purchase_date=date(2025, 1, 1),
        last_purchase_date=date(2025, 7, 1),
        purchase_frequency_months=6,
        settlement_lag_business_days=1,
    )

    report = BacktestService().run_recurring_plan(config, provider)

    assert len(report.cycles) == 2
    assert report.total_invested == pytest.approx(1200.0)
    assert report.total_sale_proceeds > report.total_invested
    assert report.total_pnl > 0
    assert report.realized_return_pct > 0
    assert report.avg_annual_return_pct > 0
    assert report.benchmark_ticker == "SPY"


def test_period_start_reference_uses_on_or_before_anchor_date() -> None:
    ticker = "UNH"
    prices = {
        # Jan 1, 2022 is Saturday, so purchase for boundary Jan 1 is Dec 31, 2021.
        (ticker, date(2021, 7, 1)): 95.0,
        (ticker, date(2021, 12, 31)): 100.0,
        (ticker, date(2022, 6, 30)): 120.0,
        (ticker, date(2022, 7, 7)): 125.0,
        (ticker, date(2022, 1, 7)): 110.0,
    }
    provider = InMemoryMarketDataProvider(prices=_with_benchmark_prices(prices, ticker=ticker))
    config = RecurringPlanConfig(
        ticker=ticker,
        discount_rate=0.10,
        starting_salary=12000.0,
        espp_allocation_pct=0.10,
        first_purchase_date=date(2022, 1, 1),
        last_purchase_date=date(2022, 7, 1),
        purchase_frequency_months=6,
        settlement_lag_business_days=5,
    )

    report = BacktestService().run_recurring_plan(config, provider)
    cycle = report.cycles[0]
    assert cycle.purchase_date == date(2021, 12, 31)
    assert cycle.reference_date == date(2021, 7, 1)
    assert cycle.reference_price == pytest.approx(95.0)


def test_invalid_purchase_frequency_is_rejected() -> None:
    provider = InMemoryMarketDataProvider(prices={})
    config = RecurringPlanConfig(
        ticker="UNH",
        discount_rate=0.10,
        starting_salary=100000.0,
        espp_allocation_pct=0.10,
        first_purchase_date=date(2025, 1, 1),
        last_purchase_date=date(2025, 7, 1),
        purchase_frequency_months=2,
        settlement_lag_business_days=1,
    )

    with pytest.raises(ValueError, match="purchase_frequency_months"):
        BacktestService().run_recurring_plan(config, provider)


def test_first_purchase_date_must_be_first_of_month() -> None:
    provider = InMemoryMarketDataProvider(prices={})
    config = RecurringPlanConfig(
        ticker="UNH",
        discount_rate=0.10,
        starting_salary=100000.0,
        espp_allocation_pct=0.10,
        first_purchase_date=date(2025, 1, 2),
        last_purchase_date=date(2025, 7, 1),
        purchase_frequency_months=6,
        settlement_lag_business_days=1,
    )

    with pytest.raises(ValueError, match="first_purchase_date"):
        BacktestService().run_recurring_plan(config, provider)


def test_last_purchase_date_must_be_first_of_month() -> None:
    provider = InMemoryMarketDataProvider(prices={})
    config = RecurringPlanConfig(
        ticker="UNH",
        discount_rate=0.10,
        starting_salary=100000.0,
        espp_allocation_pct=0.10,
        first_purchase_date=date(2025, 1, 1),
        last_purchase_date=date(2025, 7, 2),
        purchase_frequency_months=6,
        settlement_lag_business_days=1,
    )

    with pytest.raises(ValueError, match="last_purchase_date"):
        BacktestService().run_recurring_plan(config, provider)


def test_quarterly_cycle_start_month_must_align_to_quarter_boundaries() -> None:
    provider = InMemoryMarketDataProvider(prices={})
    config = RecurringPlanConfig(
        ticker="UNH",
        discount_rate=0.10,
        starting_salary=100000.0,
        espp_allocation_pct=0.10,
        first_purchase_date=date(2025, 2, 1),
        last_purchase_date=date(2025, 7, 1),
        purchase_frequency_months=3,
        settlement_lag_business_days=1,
    )

    with pytest.raises(ValueError, match="First ESPP Purchase month"):
        BacktestService().run_recurring_plan(config, provider)


def test_salary_growth_applies_after_march_raise_for_next_cycles() -> None:
    ticker = "UNH"
    prices = {
        (ticker, date(2020, 12, 31)): 98.0,
        (ticker, date(2021, 6, 30)): 99.0,
        (ticker, date(2021, 7, 7)): 101.0,
        (ticker, date(2021, 12, 31)): 100.0,
        (ticker, date(2022, 1, 7)): 101.0,
        (ticker, date(2022, 6, 30)): 100.0,
        (ticker, date(2022, 7, 7)): 101.0,
        (ticker, date(2022, 12, 30)): 100.0,
        (ticker, date(2023, 1, 6)): 101.0,
    }
    provider = InMemoryMarketDataProvider(prices=_with_benchmark_prices(prices, ticker=ticker))
    config = RecurringPlanConfig(
        ticker=ticker,
        discount_rate=0.10,
        starting_salary=100000.0,
        espp_allocation_pct=0.10,
        annual_salary_growth_pct=0.03,
        first_purchase_date=date(2021, 7, 1),
        last_purchase_date=date(2023, 1, 1),
        purchase_frequency_months=6,
        settlement_lag_business_days=5,
    )

    report = BacktestService().run_recurring_plan(config, provider)

    assert report.cycles[0].contribution_amount == pytest.approx(5000.0)
    assert report.cycles[1].contribution_amount == pytest.approx(5000.0)
    assert report.cycles[2].contribution_amount == pytest.approx(5150.0)
    assert report.cycles[3].contribution_amount == pytest.approx(5150.0)


def test_cycle_based_annualization_for_semiannual_cadence() -> None:
    ticker = "UNH"
    prices = {
        (ticker, date(2024, 6, 28)): 90.0,
        (ticker, date(2024, 12, 31)): 100.0,
        (ticker, date(2025, 6, 30)): 90.0,
        (ticker, date(2025, 7, 1)): 100.0,
    }
    provider = InMemoryMarketDataProvider(prices=_with_benchmark_prices(prices, ticker=ticker))
    config = RecurringPlanConfig(
        ticker=ticker,
        discount_rate=0.10,
        starting_salary=12000.0,
        espp_allocation_pct=0.10,
        first_purchase_date=date(2025, 1, 1),
        last_purchase_date=date(2025, 7, 1),
        purchase_frequency_months=6,
        settlement_lag_business_days=1,
    )

    report = BacktestService().run_recurring_plan(config, provider)

    # 11.11% per 6-month cycle annualized with two cycles/year -> ~23.46%.
    assert report.realized_return_pct == pytest.approx(1 / 9)
    assert report.avg_annual_return_pct == pytest.approx((1 + (1 / 9)) ** 2 - 1)
















