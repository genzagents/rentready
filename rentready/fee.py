"""The landlord database fee as the service charges it, from the official guidance published 29 October 2026
(gov.uk "Register your rental property service: guidance for landlords", "Calculating the fee"):

    (fee / year_length) * (remaining_days - free_days), rounded down to the penny

fee £65; year_length the days between the previous and next renewal date (365 or 366); remaining_days the days
until the next renewal date; free_days the days before 15 November 2027 (nobody is charged for those). Every
property takes the renewal date of the landlord's first property: one year from the day it was registered."""
from __future__ import annotations

from datetime import date
from fractions import Fraction
from typing import Optional

FEE = 65
CHARGING_STARTS = date(2027, 11, 15)
GUIDANCE = "https://www.gov.uk/guidance/register-your-rental-property-service-guidance-for-landlords"


def add_year(d: date, years: int = 1) -> date:
    try:
        return d.replace(year=d.year + years)
    except ValueError:  # 29 February
        return d.replace(year=d.year + years, day=28)


def renewal_date(first: date) -> date:
    return add_year(first)


def first_payment(registered: date, first: Optional[date] = None) -> float:
    """What one property costs when registered on `registered`, for a landlord whose first property was
    registered on `first` (the same day if omitted). Pays up to the next renewal date, then £65 a year."""
    first = first or registered
    if registered < first:
        raise ValueError("a later property cannot be registered before the first one")
    renewal = renewal_date(first)
    while renewal <= registered:
        renewal = add_year(renewal)
    year_length = (renewal - add_year(renewal, -1)).days
    remaining = (renewal - registered).days
    free = min(remaining, max(0, (CHARGING_STARTS - registered).days))
    pence = Fraction(FEE * 100, year_length) * (remaining - free)
    return int(pence) / 100  # rounded down, as the guidance says
