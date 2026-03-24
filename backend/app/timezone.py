"""Colombia timezone helpers (UTC-5)."""
from datetime import datetime, timezone, timedelta

COL_TZ = timezone(timedelta(hours=-5))


def col_now() -> datetime:
    """Current time in Colombia."""
    return datetime.now(COL_TZ)


def date_range_col(date_str: str) -> tuple[str, str]:
    """Convert a YYYY-MM-DD date to start/end timestamps in Colombia timezone.

    Returns ISO strings with timezone offset that Supabase can compare
    against TIMESTAMPTZ columns correctly.
    """
    return (
        f"{date_str}T00:00:00-05:00",
        f"{date_str}T23:59:59-05:00",
    )
