"""Production calendar for RU, KZ, BY — 2026, 40-hour / 5-day week.

Official sources:
    RU — https://www.consultant.ru/law/ref/calendar/proizvodstvennye/2026/
    KZ — https://egov.kz/cms/ru/articles/balance_2026
    BY — https://rabota.by/calendar (2026)

Functions
---------
get_working_days(country, year, month) -> int
get_expected_hours(country, year, month) -> float
"""

from __future__ import annotations

# Values taken directly from the official production calendars.
# Key = (working_days, norm_hours_40h_week)
# Hours may differ from days*8 because of shortened pre-holiday days.

_CALENDAR_2026: dict[str, dict[int, tuple[int, float]]] = {
    "RU": {
        1:  (15, 120.0),
        2:  (19, 152.0),
        3:  (21, 168.0),
        4:  (22, 175.0),
        5:  (19, 151.0),
        6:  (21, 167.0),
        7:  (23, 184.0),
        8:  (21, 168.0),
        9:  (22, 176.0),
        10: (22, 176.0),
        11: (20, 159.0),
        12: (22, 176.0),
    },
    "KZ": {
        1:  (19, 152.0),
        2:  (20, 160.0),
        3:  (18, 144.0),
        4:  (22, 176.0),
        5:  (17, 136.0),
        6:  (22, 176.0),
        7:  (22, 176.0),
        8:  (20, 160.0),
        9:  (22, 176.0),
        10: (21, 168.0),
        11: (21, 168.0),
        12: (22, 176.0),
    },
    "BY": {
        1:  (19, 151.0),
        2:  (20, 160.0),
        3:  (22, 176.0),
        4:  (21, 166.0),
        5:  (20, 159.0),
        6:  (22, 176.0),
        7:  (22, 175.0),
        8:  (21, 168.0),
        9:  (22, 176.0),
        10: (22, 176.0),
        11: (21, 167.0),
        12: (22, 174.0),
    },
}

_VALID_COUNTRIES = set(_CALENDAR_2026.keys())


def get_working_days(country: str, year: int, month: int) -> int:
    """Return the number of working days for *country* in *year*/*month*."""
    country = country.upper()
    if country not in _VALID_COUNTRIES:
        raise ValueError(
            f"Unsupported country '{country}'. Supported: {sorted(_VALID_COUNTRIES)}"
        )
    if year != 2026:
        raise ValueError("Only year 2026 is supported in this version.")
    if month < 1 or month > 12:
        raise ValueError(f"Invalid month: {month}")

    return _CALENDAR_2026[country][month][0]


def get_expected_hours(country: str, year: int, month: int) -> float:
    """Return the official norm of working hours (40-hour week, 5-day)."""
    country = country.upper()
    if country not in _VALID_COUNTRIES:
        raise ValueError(
            f"Unsupported country '{country}'. Supported: {sorted(_VALID_COUNTRIES)}"
        )
    if year != 2026:
        raise ValueError("Only year 2026 is supported in this version.")
    if month < 1 or month > 12:
        raise ValueError(f"Invalid month: {month}")

    return _CALENDAR_2026[country][month][1]
