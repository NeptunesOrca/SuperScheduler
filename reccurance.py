from datetime import datetime, timedelta
from time_management import parse_datetime

class Reccurrance:
    def __init__(self, start : datetime, duration : timedelta):
        self.start = start
        self.duration = duration
        self.end = start + duration

    def isExpired(self) -> bool:
        return datetime.now() > self.end
    
    @classmethod
    def from_dict(cls, payload:dict) -> Reccurrance:
        return cls(
            # Field   | Value                             | Default
            start =     parse_datetime(payload["start"]),
            duration =  timedelta(seconds=payload.get("duration", 0))
        )
    
    def to_dict(self) -> dict:
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
