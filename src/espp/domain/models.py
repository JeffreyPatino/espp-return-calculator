"""Domain models for ESPP scenario inputs and computed return outputs."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date


@dataclass(frozen=True)
class EsppScenario:
    """Input data needed to evaluate one ESPP purchase/delivery/sale sequence."""

    ticker: str
    reference_price: float
    discount_rate: float
    contribution_amount: float
    purchase_date: date
    delivery_date: date
    sale_date: date
    delivery_price: float
    sale_price: float
    fees: float = 0.0


@dataclass(frozen=True)
class ReturnBreakdown:
    """Detailed result containing each return component and annualized metrics."""

    ticker: str
    purchase_date: date
    delivery_date: date
    sale_date: date
    reference_date: date
    contribution_amount: float
    shares: float
    reference_price: float
    purchase_price: float
    delivery_price: float
    sale_price: float
    effective_cost_basis_per_share: float
    discount_benefit: float
    lag_gain_loss: float
    hold_gain_loss: float
    sale_proceeds: float
    total_pnl: float
    realized_return_pct: float
    annualized_return_pct: float
    xirr_pct: float
    benchmark_invested: float | None = None
    benchmark_sale_proceeds: float | None = None
    benchmark_total_pnl: float | None = None
    benchmark_return_pct: float | None = None


@dataclass(frozen=True)
class RecurringPlanConfig:
    """Configuration for simulating repeated ESPP purchases over a date range."""

    ticker: str
    discount_rate: float
    starting_salary: float
    espp_allocation_pct: float
    # Cycle start anchor date (for example Jan 1 or Jul 1), not the end-of-period purchase date.
    first_purchase_date: date
    # Final cycle start anchor date (for example Jan 1 or Jul 1).
    last_purchase_date: date
    purchase_frequency_months: int
    settlement_lag_business_days: int
    pay_frequency: str = "biweekly"
    annual_salary_growth_pct: float = 0.0


@dataclass(frozen=True)
class BacktestReport:
    """Aggregate report with per-cycle breakdown and portfolio-level return metrics."""

    ticker: str
    start_date: date
    end_date: date
    cycles: list[ReturnBreakdown]
    total_invested: float
    total_sale_proceeds: float
    total_pnl: float
    realized_return_pct: float
    avg_annual_return_pct: float
    benchmark_ticker: str
    benchmark_total_invested: float
    benchmark_total_sale_proceeds: float
    benchmark_total_pnl: float
    benchmark_realized_return_pct: float
    benchmark_avg_annual_return_pct: float











