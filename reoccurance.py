from dataclasses import dataclass, field
from datetime import datetime, timedelta
from time_management import parse_datetime

@dataclass
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
            duration =  payload.get("duration",             timedelta())
        )
    
    def to_dict(self) -> dict:
        return {
            "start" : self.start.isoformat(),
            "duration": self.duration
        }