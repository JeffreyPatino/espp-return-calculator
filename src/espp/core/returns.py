"""Core return formulas for ESPP discount, lag drift, hold drift, and annualization."""

from __future__ import annotations

import math
from datetime import date


def compute_purchase_price(reference_price: float, discount_rate: float) -> float:
    if reference_price <= 0:
        raise ValueError("reference_price must be positive")
    if not 0 <= discount_rate < 1:
        raise ValueError("discount_rate must be in [0, 1)")
    return reference_price * (1 - discount_rate)


def compute_effective_cost_basis_per_share(contribution_amount: float, shares: float, fees: float = 0.0) -> float:
    if contribution_amount <= 0:
        raise ValueError("contribution_amount must be positive")
    if shares <= 0:
        raise ValueError("shares must be positive")
    return (contribution_amount + fees) / shares


def annualized_return(realized_return_pct: float, start_date: date, end_date: date) -> float:
    days = (end_date - start_date).days
    if days <= 0:
        raise ValueError("end_date must be after start_date")
    return (1 + realized_return_pct) ** (365.0 / days) - 1


def xirr(cashflows: list[tuple[date, float]], *, max_iter: int = 100, tolerance: float = 1e-7) -> float:
    if len(cashflows) < 2:
        raise ValueError("xirr requires at least two cashflows")

    if len(cashflows) == 2:
        ordered = sorted(cashflows, key=lambda row: row[0])
        (start_date, start_amount), (end_date, end_amount) = ordered
        years = (end_date - start_date).days / 365.0
        if years <= 0:
            raise ValueError("xirr requires increasing cashflow dates")
        if start_amount < 0 < end_amount:
            return (end_amount / -start_amount) ** (1 / years) - 1

    first_date = min(cf_date for cf_date, _ in cashflows)
    normalized = [((cf_date - first_date).days / 365.0, amount) for cf_date, amount in cashflows]

    def npv_for_log_rate(log_rate: float) -> float:
        total = 0.0
        for years, amount in normalized:
            exponent = -years * log_rate
            if exponent > 700:
                term = float("inf") if amount > 0 else float("-inf")
            elif exponent < -700:
                term = 0.0
            else:
                term = amount * math.exp(exponent)
            total += term
        return total

    low_log_rate, high_log_rate = -10.0, 10.0
    f_low = npv_for_log_rate(low_log_rate)
    f_high = npv_for_log_rate(high_log_rate)

    while f_low * f_high > 0 and low_log_rate > -200:
        low_log_rate -= 10
        f_low = npv_for_log_rate(low_log_rate)
    while f_low * f_high > 0 and high_log_rate < 200:
        high_log_rate += 10
        f_high = npv_for_log_rate(high_log_rate)

    if f_low * f_high > 0:
        raise ValueError("xirr root could not be bracketed")

    for _ in range(max_iter):
        mid = (low_log_rate + high_log_rate) / 2
        f_mid = npv_for_log_rate(mid)
        if abs(f_mid) < tolerance:
            return math.exp(mid) - 1
        if f_low * f_mid < 0:
            high_log_rate = mid
            f_high = f_mid
        else:
            low_log_rate = mid
            f_low = f_mid

    return math.exp((low_log_rate + high_log_rate) / 2) - 1



