from dataclasses import dataclass, field
from datetime import datetime, timedelta

@dataclass
class Reoccurrance:
    def __init__(self, start : datetime, duration : timedelta):
        self.start = start
        self.duration = duration
        self.end = start + duration

    def isExpired(self) -> bool:
        return datetime.now() > self.end