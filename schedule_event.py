import json
import uuid
from dataclasses import dataclass, field
from datetime import datetime

import wx
import wx.adv

from time_management import parse_datetime

@dataclass
class ScheduleEvent:
    title: str
    start: datetime
    end: datetime
    source: str = "local"
    event_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    description: str = ""

    @classmethod
    def from_dict(cls, payload: dict) -> "ScheduleEvent":
        return cls(
            event_id=payload.get("event_id", str(uuid.uuid4())),
            title=payload.get("title", "Untitled"),
            start=parse_datetime(payload["start"]),
            end=parse_datetime(payload["end"]),
            source=payload.get("source", "local"),
            description=payload.get("description", ""),
        )

    def to_dict(self) -> dict:
        return {
            "event_id": self.event_id,
            "title": self.title,
            "start": self.start.isoformat(),
            "end": self.end.isoformat(),
            "source": self.source,
            "description": self.description,
        }


