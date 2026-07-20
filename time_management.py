from datetime import date, datetime, time, timedelta

import wx

def local_tz():
    return datetime.now().astimezone().tzinfo

def serialize_datetime_or_none(value : datetime | None) -> str:
    if not value:
        return "None"
    return value.isoformat()

def parse_datetime_or_none(value: str) -> datetime | None:
    if value == "None":
        return None
    return parse_datetime(value)

def parse_datetime(value: str) -> datetime:
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=local_tz())
    return parsed

def start_of_week(day: date | None = None) -> date:
    current = day or date.today()
    return current - timedelta(days=current.weekday())


def wxdate_to_date(value: wx.DateTime) -> date:
    return date(value.GetYear(), value.GetMonth() + 1, value.GetDay())

def parse_time_text(raw_value: str) -> time:
    for fmt in ("%H:%M", "%I:%M %p", "%I:%M%p"):
        try:
            return datetime.strptime(raw_value.strip(), fmt).time()
        except ValueError:
            pass
    raise ValueError("Use HH:MM, such as 09:30 or 17:00.")

def parse_date_text(raw_value: str) -> date:
    value = raw_value.strip()
    if not value:
        raise ValueError("Date is required.")

    for fmt in ("%Y-%m-%d", "%m/%d/%Y", "%m-%d-%Y", "%B %d, %Y", "%b %d, %Y", "%Y/%m/%d", "%d/%m/%Y"):
        try:
            return datetime.strptime(value, fmt).date()
        except ValueError:
            continue

    raise ValueError("Use a date like YYYY-MM-DD or MM/DD/YYYY.")

def rounded_quarter_hour(minute: int) -> int:
    accurate_minute = min(59, max(0, minute % 60)) # ensures minute is between 0 and 59
    return accurate_minute - (accurate_minute % 15)
def round_datetime_to_quarter_hour(time : datetime) -> datetime:
    minute = time.minute
    rounded_minute = rounded_quarter_hour(minute)
    return time.replace(minute=rounded_minute, second=0, microsecond=0)

def minutes_to_hour(minutes: int) -> int:
    return min(23, max(0, minutes // 60))