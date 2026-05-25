"""Application service that orchestrates date handling, pricing, and return computation."""

from __future__ import annotations

from dataclasses import replace
from datetime import date

from espp.core.business_calendar import BusinessCalendar
from espp.core.returns import (
    annualized_return,
    compute_effective_cost_basis_per_share,
    compute_purchase_price,
    xirr,
)
from espp.domain.models import EsppScenario, ReturnBreakdown
from espp.ports.market_data import MarketDataProvider


class ScenarioService:
    """Computes realized return metrics for one ESPP purchase/delivery/sale sequence."""

    def __init__(self, calendar: BusinessCalendar | None = None) -> None:
        self.calendar = calendar or BusinessCalendar()

    def resolve_dates(self, scenario: EsppScenario) -> EsppScenario:
        purchase_date = self.calendar.roll_forward(scenario.purchase_date)
        delivery_date = self.calendar.roll_forward(scenario.delivery_date)
        sale_date = self.calendar.roll_forward(scenario.sale_date)
        return replace(
            scenario,
            purchase_date=purchase_date,
            delivery_date=delivery_date,
            sale_date=sale_date,
        )

    def compute(self, scenario: EsppScenario, provider: MarketDataProvider | None = None) -> ReturnBreakdown:
        resolved = self.resolve_dates(scenario)
        if resolved.sale_date <= resolved.purchase_date:
            raise ValueError("sale_date must be after purchase_date")

        delivery_price = resolved.delivery_price
        sale_price = resolved.sale_price
        if provider is not None:
            delivery_price = provider.get_price(resolved.ticker, resolved.delivery_date)
            sale_price = provider.get_price(resolved.ticker, resolved.sale_date)

        purchase_price = compute_purchase_price(resolved.reference_price, resolved.discount_rate)
        shares = resolved.contribution_amount / purchase_price
        basis_per_share = compute_effective_cost_basis_per_share(
            resolved.contribution_amount,
            shares,
            resolved.fees,
        )

        discount_benefit = shares * (resolved.reference_price - purchase_price)
        lag_gain_loss = shares * (delivery_price - purchase_price)
        hold_gain_loss = shares * (sale_price - delivery_price)

        sale_proceeds = shares * sale_price - resolved.fees
        total_pnl = sale_proceeds - resolved.contribution_amount
        realized_return_pct = total_pnl / resolved.contribution_amount
        annualized_pct = annualized_return(realized_return_pct, resolved.purchase_date, resolved.sale_date)

        cashflows: list[tuple[date, float]] = [
            (resolved.purchase_date, -resolved.contribution_amount),
            (resolved.sale_date, sale_proceeds),
        ]
        xirr_pct = xirr(cashflows)

        return ReturnBreakdown(
            ticker=resolved.ticker,
            purchase_date=resolved.purchase_date,
            delivery_date=resolved.delivery_date,
            sale_date=resolved.sale_date,
            reference_date=resolved.purchase_date,
            contribution_amount=resolved.contribution_amount,
            shares=shares,
            reference_price=resolved.reference_price,
            purchase_price=purchase_price,
            delivery_price=delivery_price,
            sale_price=sale_price,
            effective_cost_basis_per_share=basis_per_share,
            discount_benefit=discount_benefit,
            lag_gain_loss=lag_gain_loss,
            hold_gain_loss=hold_gain_loss,
            sale_proceeds=sale_proceeds,
            total_pnl=total_pnl,
            realized_return_pct=realized_return_pct,
            annualized_return_pct=annualized_pct,
            xirr_pct=xirr_pct,
        )




