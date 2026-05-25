"""Streamlit UI for running recurring ESPP backtest analyses.

This module provides a lightweight, modern interface over the existing services so users can run
simulations without CLI arguments. It intentionally keeps business logic in service classes and only
handles form input, orchestration, and visual presentation.
"""

from __future__ import annotations

from datetime import date

import pandas as pd
import streamlit as st

from espp.adapters.yahoo_provider import YahooFinanceMarketDataProvider
from espp.domain.models import RecurringPlanConfig
from espp.services.backtest_service import BacktestService


MONTH_OPTIONS = [
    ("January", 1),
    ("February", 2),
    ("March", 3),
    ("April", 4),
    ("May", 5),
    ("June", 6),
    ("July", 7),
    ("August", 8),
    ("September", 9),
    ("October", 10),
    ("November", 11),
    ("December", 12),
]
ALLOWED_START_MONTHS_BY_FREQUENCY = {
    1: (1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12),
    3: (1, 4, 7, 10),
    6: (1, 7),
}


# ----- UI setup ---------------------------------------------------------------

st.set_page_config(page_title="ESPP Return Calculator", page_icon="chart_with_upwards_trend", layout="wide")


def _render_header() -> None:
    st.title("ESPP Return Calculator")
    st.caption("Model realized ESPP outcomes with settlement lag, salary growth, and historical market prices.")


# ----- Formatting helpers -----------------------------------------------------


def _as_pct(value: float) -> str:
    return f"{value * 100:.2f}%"


def _as_money(value: float) -> str:
    return f"${value:,.2f}"


def _parse_money_input(value: str) -> float:
    cleaned = value.replace(",", "").strip()
    if not cleaned:
        raise ValueError("Starting Salary is required")
    salary = float(cleaned)
    if salary < 1_000:
        raise ValueError("Starting Salary must be at least 1,000")
    return salary


def _boundary_picker(label: str, key_prefix: str, allowed_month_numbers: tuple[int, ...]) -> date | None:
    st.caption(label)
    month_labels = [name for name, month in MONTH_OPTIONS if month in allowed_month_numbers]
    month_col, year_col = st.columns([2, 1])
    selected_month_label = month_col.selectbox(
        "Month",
        options=["Select month..."] + month_labels,
        index=0,
        key=f"{key_prefix}_month",
    )

    current_year = date.today().year
    year_options = list(range(current_year - 20, current_year + 11))
    selected_year = year_col.selectbox(
        "Year",
        options=["Select year..."] + year_options,
        index=0,
        key=f"{key_prefix}_year",
    )

    if selected_month_label == "Select month..." or selected_year == "Select year...":
        return None

    selected_month = dict(MONTH_OPTIONS)[selected_month_label]
    return date(int(selected_year), selected_month, 1)


def _cycle_frame(cycles: list, include_benchmark: bool) -> pd.DataFrame:
    rows = []
    for idx, cycle in enumerate(cycles, start=1):
        espp_return = cycle.realized_return_pct or 0.0
        row = {
            "Cycle": idx,
            "Reference Date": cycle.reference_date,
            "Purchase Date": cycle.purchase_date,
            "Delivery Date": cycle.delivery_date,
            "Invested": cycle.contribution_amount,
            "Reference Price": cycle.reference_price,
            "Purchase Price": cycle.purchase_price,
            "Sale Price": cycle.sale_price,
            "PnL": cycle.total_pnl,
            "ESPP Return %": espp_return * 100,
        }
        if include_benchmark:
            benchmark_return = cycle.benchmark_return_pct or 0.0
            row["S&P Return %"] = benchmark_return * 100
            row["Cycle Winner"] = "ESPP" if espp_return >= benchmark_return else "S&P"
        rows.append(row)
    return pd.DataFrame(rows)


# ----- Backtest view ----------------------------------------------------------


def _render_backtest_tab() -> None:
    st.subheader("Recurring Backtest")
    st.write("Use boundary dates (first of month). Each boundary represents the offering period leading up to that date.")

    frequency_options = {
        "Monthly": 1,
        "Quarterly": 3,
        "Semi Annual": 6,
    }
    frequency_label = st.selectbox("Purchase Frequency", options=list(frequency_options.keys()), index=2)
    selected_frequency_months = frequency_options[frequency_label]
    allowed_month_numbers = ALLOWED_START_MONTHS_BY_FREQUENCY[selected_frequency_months]

    c1, c2, c3 = st.columns(3)
    ticker = c1.text_input("Ticker", value="UNH").upper().strip()
    discount_rate_pct = c2.number_input("Discount Rate (%)", min_value=0, max_value=99, value=10, step=1)
    settlement_lag = c3.number_input("Settlement Lag (Business Days)", min_value=0, max_value=30, value=5, step=1)

    c4, c5, c6 = st.columns(3)
    salary_input = c4.text_input("Starting Salary", value="")
    espp_allocation_pct = c5.number_input("ESPP Allocation (%)", min_value=0, max_value=100, value=10, step=1)
    salary_growth_pct = c6.number_input("Annual Salary Growth (%)", min_value=-50, max_value=100, value=3, step=1)

    c7, c8 = st.columns(2)
    with c7:
        first_purchase = _boundary_picker(
            "First ESPP Purchase",
            key_prefix="first_boundary",
            allowed_month_numbers=allowed_month_numbers,
        )
    with c8:
        last_purchase = _boundary_picker(
            "Last ESPP Purchase",
            key_prefix="last_boundary",
            allowed_month_numbers=allowed_month_numbers,
        )

    st.markdown("Optional Benchmark")
    compare_to_benchmark = st.checkbox("Compare vs S&P 500", value=False)
    pay_frequency = "biweekly"
    if compare_to_benchmark:
        pay_frequency_options = {"Weekly": "weekly", "Biweekly": "biweekly"}
        pay_frequency_label = st.selectbox(
            "Paycheck Frequency (used only for S&P 500 comparison)",
            options=list(pay_frequency_options.keys()),
            index=1,
        )
        pay_frequency = pay_frequency_options[pay_frequency_label]

    submitted = st.button("Run Backtest", use_container_width=True)
    if not submitted:
        return

    try:
        salary = _parse_money_input(salary_input)
        if first_purchase is None or last_purchase is None:
            raise ValueError("Please select both month and year for First/Last ESPP Purchase")
        config = RecurringPlanConfig(
            ticker=ticker,
            discount_rate=float(discount_rate_pct) / 100.0,
            starting_salary=salary,
            espp_allocation_pct=float(espp_allocation_pct) / 100.0,
            first_purchase_date=first_purchase,
            last_purchase_date=last_purchase,
            purchase_frequency_months=frequency_options[frequency_label],
            pay_frequency=pay_frequency,
            settlement_lag_business_days=int(settlement_lag),
            annual_salary_growth_pct=float(salary_growth_pct) / 100.0,
        )

        with st.spinner("Fetching data and calculating..."):
            report = BacktestService().run_recurring_plan(config, YahooFinanceMarketDataProvider())
    except Exception as exc:  # pragma: no cover - UI presentation path
        st.error(str(exc))
        return

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Total Invested", _as_money(report.total_invested))
    m2.metric("Total Proceeds", _as_money(report.total_sale_proceeds))
    m3.metric("Total PnL", _as_money(report.total_pnl))
    m4.metric("Portfolio Return", _as_pct(report.realized_return_pct))

    m5, m6 = st.columns(2)
    m5.metric("Annualized Return (Cycle-Based)", _as_pct(report.avg_annual_return_pct))
    m6.metric("Cycles", str(len(report.cycles)))

    if compare_to_benchmark:
        st.markdown("### ESPP vs S&P (same contribution timing)")
        delta_proceeds = report.total_sale_proceeds - report.benchmark_total_sale_proceeds
        return_edge = report.realized_return_pct - report.benchmark_realized_return_pct
        winning_cycles = sum(
            1 for cycle in report.cycles if cycle.realized_return_pct >= (cycle.benchmark_return_pct or 0.0)
        )
        win_rate = winning_cycles / len(report.cycles) if report.cycles else 0.0

        b1, b2, b3, b4 = st.columns(4)
        b1.metric("If You Used ESPP", _as_money(report.total_sale_proceeds), delta=f"Return {_as_pct(report.realized_return_pct)}")
        b2.metric(
            f"If You Bought {report.benchmark_ticker}",
            _as_money(report.benchmark_total_sale_proceeds),
            delta=f"Return {_as_pct(report.benchmark_realized_return_pct)}",
        )
        b3.metric("ESPP Advantage", _as_money(delta_proceeds), delta=f"{_as_pct(return_edge)} return points")
        b4.metric("Cycles ESPP Won", f"{winning_cycles}/{len(report.cycles)}", delta=_as_pct(win_rate))

        st.caption(
            "Benchmark method: each paycheck contribution in the period is invested into SPY on that paycheck date, "
            "then sold on the same day your ESPP shares are sold."
        )
        st.caption(
            f"Cycle-based annualized view: ESPP {_as_pct(report.avg_annual_return_pct)} vs "
            f"{report.benchmark_ticker} {_as_pct(report.benchmark_avg_annual_return_pct)}"
        )

    frame = _cycle_frame(report.cycles, include_benchmark=compare_to_benchmark)
    st.line_chart(frame.set_index("Cycle")["PnL"])
    format_map = {
        "Invested": "${:,.2f}",
        "Reference Price": "${:,.2f}",
        "Purchase Price": "${:,.2f}",
        "Sale Price": "${:,.2f}",
        "PnL": "${:,.2f}",
        "ESPP Return %": "{:.2f}%",
    }
    if compare_to_benchmark:
        format_map["S&P Return %"] = "{:.2f}%"
    st.dataframe(frame.style.format(format_map), use_container_width=True)



def main() -> None:
    _render_header()
    _render_backtest_tab()


if __name__ == "__main__":
    main()


