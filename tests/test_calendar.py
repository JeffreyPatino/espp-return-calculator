from datetime import date

from espp.core.business_calendar import BusinessCalendar


def test_roll_forward_weekend_to_monday() -> None:
    cal = BusinessCalendar()
    assert cal.roll_forward(date(2026, 5, 23)) == date(2026, 5, 25)


def test_add_business_days_skips_holiday() -> None:
    cal = BusinessCalendar(holidays={date(2026, 1, 1)})
    result = cal.add_business_days(date(2025, 12, 31), 1)
    assert result == date(2026, 1, 2)


def test_roll_backward_weekend_to_friday() -> None:
    cal = BusinessCalendar()
    assert cal.roll_backward(date(2026, 5, 24)) == date(2026, 5, 22)


