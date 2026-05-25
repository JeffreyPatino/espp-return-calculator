"""CLI entrypoint for recurring ESPP backtesting."""

from __future__ import annotations

import argparse
from datetime import date

from espp.adapters.yahoo_provider import YahooFinanceMarketDataProvider
from espp.domain.models import BacktestReport
from espp.domain.models import RecurringPlanConfig
from espp.services.backtest_service import BacktestService


def _parse_date(value: str) -> date:
    return date.fromisoformat(value)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Calculate recurring ESPP backtest return metrics")
    subparsers = parser.add_subparsers(dest="command", required=True)

    backtest = subparsers.add_parser("backtest-yahoo", help="Run recurring ESPP backtest with Yahoo Finance prices")
    backtest.add_argument("--ticker", required=True)
    backtest.add_argument("--discount-rate", type=float, required=True)
    backtest.add_argument("--salary", type=float, required=True, help="Starting annual base salary")
    backtest.add_argument(
        "--espp-allocation-pct",
        type=float,
        required=True,
        help="Portion of salary contributed to ESPP (decimal, for example 0.10)",
    )
    backtest.add_argument(
        "--annual-salary-growth-pct",
        type=float,
        default=0.03,
        help="Expected annual salary growth (decimal, for example 0.03)",
    )
    backtest.add_argument(
        "--first-purchase-date",
        type=_parse_date,
        required=True,
        help="First boundary date (typically Jan 1 or Jul 1) for the period leading up to that date",
    )
    backtest.add_argument(
        "--last-purchase-date",
        type=_parse_date,
        required=True,
        help="Last boundary date (typically Jan 1 or Jul 1) for the period leading up to that date",
    )
    backtest.add_argument(
        "--purchase-frequency-months",
        type=int,
        choices=[1, 3, 6],
        default=6,
        help="Allowed cadence in months: 1 (monthly), 3 (quarterly), or 6 (semiannual)",
    )
    backtest.add_argument(
        "--pay-frequency",
        choices=["weekly", "biweekly"],
        default="biweekly",
        help="Paycheck cadence used to model S&P 500 benchmark contributions",
    )
    backtest.add_argument("--settlement-lag-business-days", type=int, default=5)
    return parser


def _print_backtest_report(report: BacktestReport) -> None:
    delta_proceeds = report.total_sale_proceeds - report.benchmark_total_sale_proceeds
    return_edge = report.realized_return_pct - report.benchmark_realized_return_pct
    winning_cycles = sum(
        1 for cycle in report.cycles if cycle.realized_return_pct >= (cycle.benchmark_return_pct or 0.0)
    )

    print(f"Ticker: {report.ticker}")
    print(f"Period: {report.start_date.isoformat()} to {report.end_date.isoformat()}")
    print(f"Cycles: {len(report.cycles)}")
    print(f"Total invested: {report.total_invested:.2f}")
    print(f"Total sale proceeds: {report.total_sale_proceeds:.2f}")
    print(f"Total PnL: {report.total_pnl:.2f}")
    print(f"Portfolio realized return: {report.realized_return_pct * 100:.2f}%")
    print(f"Annualized return from cycle cadence (approx): {report.avg_annual_return_pct * 100:.2f}%")
    print(f"\nESPP vs S&P 500 benchmark ({report.benchmark_ticker}) with same paycheck timing:")
    print(f"If ESPP: final value {report.total_sale_proceeds:.2f} (return {report.realized_return_pct * 100:.2f}%)")
    print(
        f"If {report.benchmark_ticker}: final value {report.benchmark_total_sale_proceeds:.2f} "
        f"(return {report.benchmark_realized_return_pct * 100:.2f}%)"
    )
    print(f"ESPP advantage: {delta_proceeds:.2f} ({return_edge * 100:.2f} return points)")
    print(f"Cycles ESPP won: {winning_cycles}/{len(report.cycles)}")
    print(
        f"Cycle-based annualized: ESPP {report.avg_annual_return_pct * 100:.2f}% vs "
        f"{report.benchmark_ticker} {report.benchmark_avg_annual_return_pct * 100:.2f}%"
    )
    print("\nPer-cycle breakdown:")
    for idx, cycle in enumerate(report.cycles, start=1):
        benchmark_return = cycle.benchmark_return_pct or 0.0
        winner = "ESPP" if cycle.realized_return_pct >= benchmark_return else report.benchmark_ticker
        print(
            f"{idx:02d}. purchase={cycle.purchase_date} delivery={cycle.delivery_date} sale={cycle.sale_date} "
            f"ref_date={cycle.reference_date} ref={cycle.reference_price:.2f} "
            f"invested={cycle.contribution_amount:.2f} buy={cycle.purchase_price:.2f} sell={cycle.sale_price:.2f} "
            f"pnl={cycle.total_pnl:.2f} espp_return={cycle.realized_return_pct * 100:.2f}% "
            f"sp_return={benchmark_return * 100:.2f}% winner={winner}"
        )


def main() -> None:
    args = build_parser().parse_args()
    if args.command == "backtest-yahoo":
        config = RecurringPlanConfig(
            ticker=args.ticker,
            discount_rate=args.discount_rate,
            starting_salary=args.salary,
            espp_allocation_pct=args.espp_allocation_pct,
            first_purchase_date=args.first_purchase_date,
            last_purchase_date=args.last_purchase_date,
            purchase_frequency_months=args.purchase_frequency_months,
            pay_frequency=args.pay_frequency,
            settlement_lag_business_days=args.settlement_lag_business_days,
            annual_salary_growth_pct=args.annual_salary_growth_pct,
        )
        provider = YahooFinanceMarketDataProvider()
        report = BacktestService().run_recurring_plan(config, provider)
        _print_backtest_report(report)
        return


if __name__ == "__main__":
    main()













