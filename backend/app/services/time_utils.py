import calendar
from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo

IST = ZoneInfo("Asia/Kolkata")


def get_current_ist_datetime() -> datetime:
    """Current timestamp in IST (Asia/Kolkata)."""
    return datetime.now(timezone.utc).astimezone(IST)


def get_current_ist_date() -> date:
    """Current date in IST."""
    return get_current_ist_datetime().date()


def get_current_month_str() -> str:
    """Current month in IST as 'YYYY-MM'."""
    return get_current_ist_date().strftime("%Y-%m")


def get_previous_month_str(month_str: str) -> str:
    """Given 'YYYY-MM', returns the previous month as 'YYYY-MM'."""
    year, month = map(int, month_str.split("-"))
    if month == 1:
        return f"{year - 1:04d}-12"
    return f"{year:04d}-{month - 1:02d}"


def get_month_date_range(month_str: str) -> tuple[date, date]:
    """Returns (start_date, end_date) for a given 'YYYY-MM' string."""
    year, month = map(int, month_str.split("-"))
    num_days = calendar.monthrange(year, month)[1]
    return date(year, month, 1), date(year, month, num_days)


def clamp_day_to_month(year: int, month: int, day: int) -> int:
    """Clamp day (1-31) to the maximum days available in the given year/month (FR-049)."""
    max_days = calendar.monthrange(year, month)[1]
    return min(day, max_days)
