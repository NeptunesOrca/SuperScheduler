from datetime import datetime, timedelta
from time_management import parse_datetime

class Reoccurrance:
    def __init__(self, start : datetime, duration : timedelta):
        self.start = start
        self.duration = duration
        self.end = start + duration

    def isExpired(self) -> bool:
        return datetime.now() > self.end
    
    @classmethod
    def from_dict(cls, payload:dict) -> Reoccurrance:
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

def serialize_reoccurance_or_none(value : Reoccurrance | None):
    if not value:
        return None
    return value.to_dict()


def deserialize_reoccurance_or_none(input: str | dict) -> Reoccurrance | None:
    if type(input) is dict:
        return Reoccurrance.from_dict(input)
    return None
