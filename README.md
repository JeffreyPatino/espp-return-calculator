# ESPP Return Calculator

A Python project to model realized Employee Stock Purchase Plan (ESPP) returns with real-world timing effects.

This repository is intentionally built as a production-style engineering project: clear domain modeling, testable business logic, clean layering, and practical trade-off documentation.

## Why I Built This

Most ESPP calculators overstate outcomes by ignoring timing details (reference pricing, business-day settlement, and recurring contribution cadence). I wanted a tool that answers a practical question:

"Was participating in ESPP better than investing the same paycheck contributions in the S&P 500 over the same periods?"

## Product Goals

- Accurate recurring ESPP backtests across multi-year ranges
- Transparent assumptions and deterministic calculations
- User-friendly UX (Streamlit) plus automation-friendly CLI
- Comparable benchmark scenario with the same contribution timing

## MVP scope

- Deterministic pricing via a pluggable market data interface
- Yahoo Finance provider for real historical close prices
- Business-day aware settlement modeling with configurable holidays
- CLI and web UI for recurring historical backtests
- S&P 500 benchmark comparison using paycheck-level contributions (SPY proxy)
- Unit tests for calendar and return math

## Architecture (Quick View)

- `src/espp/domain/models.py`: typed dataclasses for config, cycle output, and portfolio report
- `src/espp/services/backtest_service.py`: recurring cycle generation, orchestration, benchmark modeling
- `src/espp/services/scenario_service.py`: single-cycle financial calculation workflow
- `src/espp/core/returns.py`: pricing/return math primitives
- `src/espp/core/business_calendar.py`: business-day rolls and settlement-date logic
- `src/espp/adapters/yahoo_provider.py`: Yahoo Finance adapter (bulk + fallback)
- `src/espp/interfaces/cli.py`: CLI entrypoint
- `src/espp/interfaces/streamlit_app.py`: Streamlit UI

## Quick start

**Try it online:** [https://espp-return-calculator.streamlit.app](https://espp-return-calculator.streamlit.app)

Or run locally:

```bash
cd "/Users/jeffrey.patino@optum.com/Library/CloudStorage/OneDrive-UHG/Documents/Side Projects/GitHub/espp-return-calculator"
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
pytest
```

Launch the web UI:

```bash
streamlit run src/espp/interfaces/streamlit_app.py
```

Run the CLI:

```bash
espp-calc --help
```

Run a 5-year recurring ESPP backtest with Yahoo Finance (example: UNH):

```bash
espp-calc \
  backtest-yahoo \
  --ticker UNH \
  --discount-rate 0.10 \
  --salary <YOUR_SALARY> \
  --espp-allocation-pct 0.10 \
  --annual-salary-growth-pct 0.03 \
  --pay-frequency biweekly \
  --first-purchase-date 2021-07-01 \
  --last-purchase-date 2026-01-01 \
  --purchase-frequency-months 6 \
  --settlement-lag-business-days 5
```

## What The App Computes

- Per cycle:
  - reference date/price
  - discounted purchase price
  - shares purchased
  - realized PnL and realized return
- Portfolio level:
  - total invested, proceeds, PnL, realized return
  - cycle-cadence annualized return (instead of calendar-span CAGR)
- Optional benchmark:
  - paycheck-split SPY contributions over the same period
  - benchmark return and side-by-side outcome vs ESPP

Recurring backtests always use period-start reference pricing and use the close on the last business day on or before cycle start.
Cycle start months are derived from cadence: monthly uses every month, quarterly uses Jan/Apr/Jul/Oct, and semiannual uses Jan/Jul.
Use `--first-purchase-date` and `--last-purchase-date` as boundary anchors (typically Jan 1 / Jul 1), both on the first day of a month. Each boundary represents the offering period leading up to that [...]
Recurring backtests assume shares are sold immediately at delivery (no fixed hold-days parameter).
Salary raises are modeled as taking effect each March.

This prints:

- overall portfolio metrics (total invested, total proceeds, total PnL, realized return, cycle-based annualized return)
- S&P 500 benchmark metrics with the same contribution schedule
- per-cycle breakdown (purchase date, delivery date, sale date, reference date, buy/sell prices, PnL, return)

## Key Engineering Decisions

- **Domain-first modeling**: business concepts are explicit dataclasses (`RecurringPlanConfig`, `ReturnBreakdown`, `BacktestReport`).
- **Separation of concerns**: interfaces, adapters, core math, and orchestration are cleanly separated.
- **Deterministic tests**: `InMemoryMarketDataProvider` keeps tests fast and stable.
- **Business-day correctness**: purchase/settlement behavior respects market calendars.
- **Annualization fix**: switched from naive elapsed-time annualization to cadence-aware annualization.
- **Benchmark fairness**: benchmark invests the same paycheck cadence and exits on matching sale dates.

## Lessons Learned

- Real financial tools fail quietly if date semantics are ambiguous; naming and constraints matter as much as formulas.
- UX choices (friendly labels, constrained month pickers, optional benchmark flow) materially reduce user error.
- External market data APIs require resilient adapter strategies (bulk fetch, retries, fallback paths).
- Explainability beats raw metrics: users understand "ESPP advantage in dollars" faster than abstract return fields.

## Trade-offs and Limitations

- Uses Yahoo Finance data; availability/rate limits can vary.
- Benchmark uses `SPY` as S&P 500 proxy.
- Raises are modeled in March for simplicity.
- Tax treatment and transaction fees are intentionally excluded from current calculations.

## Engineering Takeaways

Notable areas this project emphasizes:

- translating ambiguous business rules into robust code
- incremental refactoring while keeping behavior stable
- designing for testability and iteration speed
- balancing correctness, UX clarity, and delivery pragmatism

## Project layout

- `src/espp/domain/models.py`: domain input and result models
- `src/espp/core/business_calendar.py`: weekend/holiday logic
- `src/espp/core/returns.py`: financial calculation primitives
- `src/espp/services/backtest_service.py`: recurring-plan backtest orchestration
- `src/espp/adapters/yahoo_provider.py`: Yahoo Finance market data adapter
- `src/espp/interfaces/cli.py`: command line interface
- `src/espp/interfaces/streamlit_app.py`: Streamlit web UI
- `tests/`: unit tests
