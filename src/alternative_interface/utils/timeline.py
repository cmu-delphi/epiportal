"""Calendar helpers for building chart timelines.

Epidata reports ``time_value`` as YYYYWW for weekly signals and YYYYMMDD for
daily ones; the ``_key`` helpers produce those same integer forms so API rows
can be matched against a generated timeline.
"""

from datetime import datetime, timedelta

from epiweeks import Week


def epiweeks_in_date_range(start_date_str: str, end_date_str: str):
    start_date = datetime.strptime(start_date_str, "%Y-%m-%d").date()
    end_date = datetime.strptime(end_date_str, "%Y-%m-%d").date()
    if end_date < start_date:
        start_date, end_date = end_date, start_date

    start_week = Week.fromdate(start_date)
    end_week = Week.fromdate(end_date)

    weeks = []
    seen = set()
    d = start_week.startdate()
    while d <= end_week.enddate():
        w = Week.fromdate(d)
        key = (w.year, w.week)
        if key not in seen:
            weeks.append(w)
            seen.add(key)
        d += timedelta(days=7)
    return weeks


def _epiweek_key(w: Week) -> int:
    # Matches API time_value format YYYYWW, e.g. 202032
    return w.year * 100 + w.week


def _epiweek_label(w: Week) -> str:
    return f"{w.year}-W{w.week:02d}"


def _day_key(d: datetime.date) -> int:
    # Matches API time_value format YYYYMMDD, e.g. 20240115
    return d.year * 10000 + d.month * 100 + d.day


def _day_label(d: datetime.date) -> str:
    return d.strftime("%Y-%m-%d")


def days_in_date_range(start_date_str: str, end_date_str: str):
    """Generate all days in the date range."""
    start_date = datetime.strptime(start_date_str, "%Y-%m-%d").date()
    end_date = datetime.strptime(end_date_str, "%Y-%m-%d").date()
    if end_date < start_date:
        start_date, end_date = end_date, start_date

    days = []
    d = start_date
    while d <= end_date:
        days.append(d)
        d += timedelta(days=1)
    return days
