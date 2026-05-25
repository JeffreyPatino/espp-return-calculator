"""Service for running recurring ESPP purchase/sale simulations over multiple years."""

from __future__ import annotations

from dataclasses import replace
from datetime import date, timedelta

from espp.domain.models import BacktestReport, EsppScenario, RecurringPlanConfig
from espp.ports.market_data import MarketDataProvider
from espp.services.scenario_service import ScenarioService


MARCH_RAISE_MONTH = 3
BENCHMARK_TICKER = "SPY"
ALLOWED_START_MONTHS_BY_FREQUENCY: dict[int, tuple[int, ...]] = {
    1: (1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12),
    3: (1, 4, 7, 10),
    6: (1, 7),
}
FREQUENCY_LABELS: dict[int, str] = {
    1: "Monthly",
    3: "Quarterly",
    6: "Semi Annual",
}
MONTH_LABELS: dict[int, str] = {
    1: "January",
    2: "February",
    3: "March",
    4: "April",
    5: "May",
    6: "June",
    7: "July",
    8: "August",
    9: "September",
    10: "October",
    11: "November",
    12: "December",
}
PAY_INTERVAL_DAYS: dict[str, int] = {
    "weekly": 7,
    "biweekly": 14,
}


class BacktestService:
    """Creates recurring ESPP cycles and computes both per-cycle and overall portfolio returns."""

    def __init__(self, scenario_service: ScenarioService | None = None) -> None:
        self.scenario_service = scenario_service or ScenarioService()

    def run_recurring_plan(self, config: RecurringPlanConfig, provider: MarketDataProvider) -> BacktestReport:
        if config.purchase_frequency_months not in {1, 3, 6}:
            raise ValueError("purchase_frequency_months must be one of: 1 (monthly), 3 (quarterly), 6 (semiannual)")
        if config.starting_salary <= 0:
            raise ValueError("starting_salary must be positive")
        if not 0 < config.espp_allocation_pct <= 1:
            raise ValueError("espp_allocation_pct must be in (0, 1]")
        if config.annual_salary_growth_pct <= -1:
            raise ValueError("annual_salary_growth_pct must be greater than -1")
        if config.pay_frequency not in PAY_INTERVAL_DAYS:
            raise ValueError("pay_frequency must be either 'weekly' or 'biweekly'")
        if config.first_purchase_date.day != 1:
            raise ValueError("first_purchase_date must be the first day of a month")
        if config.last_purchase_date.day != 1:
            raise ValueError("last_purchase_date must be the first day of a month")
        if config.last_purchase_date < config.first_purchase_date:
            raise ValueError("last_purchase_date must be on or after first_purchase_date")

        allowed_start_months = ALLOWED_START_MONTHS_BY_FREQUENCY[config.purchase_frequency_months]
        allowed_month_names = ", ".join(MONTH_LABELS[month] for month in allowed_start_months)
        frequency_name = FREQUENCY_LABELS[config.purchase_frequency_months]
        if config.first_purchase_date.month not in allowed_start_months:
            raise ValueError(
                f"First ESPP Purchase month must be one of: {allowed_month_names} for {frequency_name} frequency."
            )
        if config.last_purchase_date.month not in allowed_start_months:
            raise ValueError(
                f"Last ESPP Purchase month must be one of: {allowed_month_names} for {frequency_name} frequency."
            )

        cycle_dates: list[tuple[date, date, date, date, date, list[date]]] = []
        boundary_date = config.first_purchase_date

        while boundary_date <= config.last_purchase_date:
            purchase_date = self._purchase_date_from_boundary(boundary_date)
            period_start = self._add_months(boundary_date, -config.purchase_frequency_months)
            delivery_date = self.scenario_service.calendar.add_business_days(
                purchase_date,
                config.settlement_lag_business_days,
            )
            # Recurring backtests assume sale at first availability after settlement.
            sale_date = delivery_date

            reference_date = self._resolve_reference_date(config, boundary_date)
            pay_dates = self._paycheck_dates(period_start, purchase_date, config.pay_frequency)
            if not pay_dates:
                pay_dates = [purchase_date]
            cycle_dates.append((boundary_date, purchase_date, delivery_date, sale_date, reference_date, pay_dates))

            boundary_date = self._add_months(boundary_date, config.purchase_frequency_months)

        if not cycle_dates:
            raise ValueError("No cycles were generated for the provided configuration")

        trade_dates = [purchase_date for _, purchase_date, _, _, _, _ in cycle_dates]
        trade_dates.extend(delivery_date for _, _, delivery_date, _, _, _ in cycle_dates)
        trade_dates.extend(sale_date for _, _, _, sale_date, _, _ in cycle_dates)

        benchmark_dates: list[date] = []
        for _, _, _, sale_date, _, pay_dates in cycle_dates:
            benchmark_dates.extend(pay_dates)
            benchmark_dates.append(sale_date)

        bulk_after_getter = getattr(provider, "get_prices_on_or_after", None)
        bulk_before_getter = getattr(provider, "get_prices_on_or_before", None)

        bulk_after_prices: dict[date, float] | None = None
        if callable(bulk_after_getter):
            bulk_after_prices = bulk_after_getter(config.ticker, trade_dates)

        reference_dates = [reference_date for _, _, _, _, reference_date, _ in cycle_dates]
        bulk_reference_prices: dict[date, float] | None = None
        if callable(bulk_before_getter):
            bulk_reference_prices = bulk_before_getter(config.ticker, reference_dates)

        benchmark_after_prices: dict[date, float] | None = None
        if callable(bulk_after_getter):
            benchmark_after_prices = bulk_after_getter(BENCHMARK_TICKER, benchmark_dates)

        cycles = []
        for boundary_date, purchase_date, delivery_date, sale_date, reference_date, pay_dates in cycle_dates:
            contribution_amount = self._cycle_contribution_amount(config, boundary_date)
            contribution_per_paycheck = contribution_amount / len(pay_dates)

            if bulk_after_prices is not None and bulk_reference_prices is not None:
                reference_price = bulk_reference_prices[reference_date]
                delivery_price = bulk_after_prices[delivery_date]
                sale_price = bulk_after_prices[sale_date]
            else:
                get_before = getattr(provider, "get_price_on_or_before", None)
                if callable(get_before):
                    reference_price = get_before(config.ticker, reference_date)
                else:
                    reference_price = provider.get_price(config.ticker, reference_date)
                delivery_price = provider.get_price(config.ticker, delivery_date)
                sale_price = provider.get_price(config.ticker, sale_date)

            if benchmark_after_prices is not None:
                benchmark_sale_price = benchmark_after_prices[sale_date]
                benchmark_shares = sum(contribution_per_paycheck / benchmark_after_prices[pd] for pd in pay_dates)
            else:
                benchmark_sale_price = provider.get_price(BENCHMARK_TICKER, sale_date)
                benchmark_shares = sum(contribution_per_paycheck / provider.get_price(BENCHMARK_TICKER, pd) for pd in pay_dates)

            benchmark_invested = contribution_per_paycheck * len(pay_dates)
            benchmark_sale_proceeds = benchmark_shares * benchmark_sale_price
            benchmark_total_pnl = benchmark_sale_proceeds - benchmark_invested
            benchmark_return_pct = benchmark_total_pnl / benchmark_invested if benchmark_invested else 0.0

            scenario = EsppScenario(
                ticker=config.ticker,
                reference_price=reference_price,
                discount_rate=config.discount_rate,
                contribution_amount=contribution_amount,
                purchase_date=purchase_date,
                delivery_date=delivery_date,
                sale_date=sale_date,
                delivery_price=delivery_price,
                sale_price=sale_price,
                fees=0.0,
            )
            result = self.scenario_service.compute(scenario)
            cycles.append(
                replace(
                    result,
                    reference_date=reference_date,
                    benchmark_invested=benchmark_invested,
                    benchmark_sale_proceeds=benchmark_sale_proceeds,
                    benchmark_total_pnl=benchmark_total_pnl,
                    benchmark_return_pct=benchmark_return_pct,
                )
            )

        total_invested = sum(cycle.contribution_amount for cycle in cycles)
        total_sale_proceeds = sum(cycle.sale_proceeds for cycle in cycles)
        total_pnl = total_sale_proceeds - total_invested
        realized_return_pct = total_pnl / total_invested
        # Annualize by cycle cadence because capital is tied up per offering period, not continuously for the full span.
        cycles_per_year = 12 / config.purchase_frequency_months
        avg_annual_return_pct = (1 + realized_return_pct) ** cycles_per_year - 1

        benchmark_total_invested = sum(cycle.benchmark_invested or 0.0 for cycle in cycles)
        benchmark_total_sale_proceeds = sum(cycle.benchmark_sale_proceeds or 0.0 for cycle in cycles)
        benchmark_total_pnl = benchmark_total_sale_proceeds - benchmark_total_invested
        benchmark_realized_return_pct = (
            benchmark_total_pnl / benchmark_total_invested if benchmark_total_invested else 0.0
        )
        benchmark_avg_annual_return_pct = (1 + benchmark_realized_return_pct) ** cycles_per_year - 1

        return BacktestReport(
            ticker=config.ticker,
            start_date=cycles[0].purchase_date,
            end_date=cycles[-1].sale_date,
            cycles=cycles,
            total_invested=total_invested,
            total_sale_proceeds=total_sale_proceeds,
            total_pnl=total_pnl,
            realized_return_pct=realized_return_pct,
            avg_annual_return_pct=avg_annual_return_pct,
            benchmark_ticker=BENCHMARK_TICKER,
            benchmark_total_invested=benchmark_total_invested,
            benchmark_total_sale_proceeds=benchmark_total_sale_proceeds,
            benchmark_total_pnl=benchmark_total_pnl,
            benchmark_realized_return_pct=benchmark_realized_return_pct,
            benchmark_avg_annual_return_pct=benchmark_avg_annual_return_pct,
        )

    def _add_months(self, base: date, months: int) -> date:
        year = base.year + (base.month - 1 + months) // 12
        month = (base.month - 1 + months) % 12 + 1
        day = min(base.day, self._days_in_month(year, month))
        return date(year, month, day)

    def _days_in_month(self, year: int, month: int) -> int:
        if month == 12:
            next_month = date(year + 1, 1, 1)
        else:
            next_month = date(year, month + 1, 1)
        return (next_month - date(year, month, 1)).days

    def _resolve_reference_date(self, config: RecurringPlanConfig, boundary_date: date) -> date:
        period_start = self._add_months(boundary_date, -config.purchase_frequency_months)
        return self.scenario_service.calendar.roll_backward(period_start)

    def _cycle_contribution_amount(self, config: RecurringPlanConfig, boundary_date: date) -> float:
        # Raises are applied annually in the configured raise month; contribution then scales for later cycles.
        raise_count = self._raise_count(config, boundary_date)
        annual_salary = config.starting_salary * ((1 + config.annual_salary_growth_pct) ** raise_count)
        cycle_fraction = config.purchase_frequency_months / 12.0
        return annual_salary * config.espp_allocation_pct * cycle_fraction

    def _raise_count(self, config: RecurringPlanConfig, boundary_date: date) -> int:
        first_raise_year = config.first_purchase_date.year
        first_raise_date = date(first_raise_year, MARCH_RAISE_MONTH, 1)
        if config.first_purchase_date >= first_raise_date:
            first_raise_year += 1

        raises = boundary_date.year - first_raise_year
        current_raise_date = date(boundary_date.year, MARCH_RAISE_MONTH, 1)
        if boundary_date >= current_raise_date:
            raises += 1
        return max(0, raises)

    def _purchase_date_from_boundary(self, boundary_date: date) -> date:
        # Each boundary (e.g., Jan 1/Jul 1) represents the purchase for the period immediately before it.
        period_end = boundary_date - timedelta(days=1)
        return self.scenario_service.calendar.roll_backward(period_end)

    def _paycheck_dates(self, period_start: date, purchase_date: date, pay_frequency: str) -> list[date]:
        interval_days = PAY_INTERVAL_DAYS[pay_frequency]
        dates: list[date] = []
        current = period_start
        while current <= purchase_date:
            dates.append(current)
            current += timedelta(days=interval_days)
        return dates