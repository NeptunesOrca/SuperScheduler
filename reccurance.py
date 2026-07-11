from datetime import datetime, timedelta
from time_management import parse_datetime

class Reccurrance:
    def __init__(self, date : datetime, duration : timedelta, useDateAsStart : bool = True):
        self.start : datetime
        self.end : datetime
        self.duration = duration
        if useDateAsStart:
            self.start = date
            self.end = date + duration
        else:
            self.end = date
            self.start = date - duration


    def isExpired(self) -> bool:
        return datetime.now() > self.end
    
    @classmethod
    def from_dict(cls, payload:dict) -> Reccurrance:
        return cls(
            # Field   | Value                             | Default
            date =     parse_datetime(payload["start"]),
            duration =  timedelta(seconds=payload.get("duration", 0))
            # use date as start
        )
    
    def to_dict(self) -> dict:
        # only provide the start date, end date will be calculated
        return {
            "start" : self.start.isoformat(),
            "duration": int(self.duration.total_seconds())
        }

def serialize_reccurance_or_none(value : Reccurrance | None):
    if not value:
        return None
    return value.to_dict()


def deserialize_reccurance_or_none(input: str | dict) -> Reccurrance | None:
    if type(input) is dict:
        return Reccurrance.from_dict(input)
    return None
