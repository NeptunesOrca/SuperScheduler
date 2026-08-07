from datetime import datetime, timedelta
from time_management import parse_datetime, TimeUnits, increment_datetime, guess_unit

class Recurrence:
    def __init__(self, date : datetime, duration : float, useDateAsStart : bool = True, units=TimeUnits.DAYS):
        self.start : datetime
        self.end : datetime
        self.duration = duration
        self.units : TimeUnits = units
        if useDateAsStart:
            self.start = date
            self.end = increment_datetime(self.start, self.duration, self.units)
        else:
            self.end = date
            self.start = increment_datetime(self.end, -self.duration, self.units)

    def isExpired(self) -> bool:
        return datetime.now() > self.end
    
    @classmethod
    def from_dict(cls, payload:dict) -> Recurrence:
        return cls(
            # Field   | Value                             | Default
            date =     parse_datetime(payload["start"]),
            duration =  payload.get("duration", 0),
            useDateAsStart = True, # always use date as start for serialization, deserialization always stores it in the same way
            units = TimeUnits(payload.get("units", TimeUnits.SECONDS.value)) # if units aren't saved, then assume seconds as it was saved before units existed
        )
    
    def to_dict(self) -> dict:
        # only provide the start date, end date will be calculated
        return {
            "start" : self.start.isoformat(),
            "duration": int(self.duration),
            "units": self.units
        }

def serialize_recurrence_or_none(value : Recurrence | None):
    if not value:
        return None
    return value.to_dict()


def deserialize_recurrence_or_none(input: str | dict) -> Recurrence | None:
    if type(input) is dict:
        return Recurrence.from_dict(input)
    return None
