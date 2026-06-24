from datetime import date, datetime, time, timedelta

import wx
import wx.adv

def local_tz():
    return datetime.now().astimezone().tzinfo

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