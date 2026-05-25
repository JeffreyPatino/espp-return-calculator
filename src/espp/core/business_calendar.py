"""Business-day calendar helpers for settlement lag and date rolling behavior."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, timedelta


@dataclass
class BusinessCalendar:
    """Weekend/holiday aware utility used to model settlement and sale dates."""

    holidays: set[date] = field(default_factory=set)

    def is_business_day(self, value: date) -> bool:
        return value.weekday() < 5 and value not in self.holidays

    def roll_forward(self, value: date) -> date:
        current = value
        while not self.is_business_day(current):
            current += timedelta(days=1)
        return current

    def roll_backward(self, value: date) -> date:
        current = value
        while not self.is_business_day(current):
            current -= timedelta(days=1)
        return current

    def add_business_days(self, start: date, days: int) -> date:
        if days < 0:
            raise ValueError("days must be non-negative")
        current = start
        added = 0
        while added < days:
            current += timedelta(days=1)
            if self.is_business_day(current):
                added += 1
        return current


