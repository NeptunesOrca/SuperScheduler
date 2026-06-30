import json
import uuid
from dataclasses import dataclass, field
from datetime import datetime

import wx
import wx.adv

from time_management import parse_datetime
from task_item import TaskItem

@dataclass
class ScheduleEvent:
    title: str
    start: datetime
    end: datetime
    source: str = "local"
    event_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    description: str = ""
    linkedTaskID: int | None = None

    @classmethod
    def from_dict(cls, payload: dict) -> "ScheduleEvent":
        return cls(
            event_id=payload.get("event_id", str(uuid.uuid4())),
            title=payload.get("title", "Untitled"),
            start=parse_datetime(payload["start"]),
            end=parse_datetime(payload["end"]),
            source=payload.get("source", "local"),
            description=payload.get("description", ""),
            linkedTaskID=payload.get("linked_task_id") if payload.get("linked_task") else None
        )

    def to_dict(self) -> dict:
        return {
            "event_id": self.event_id,
            "title": self.title,
            "start": self.start.isoformat(),
            "end": self.end.isoformat(),
            "source": self.source,
            "description": self.description,
            "linked_task_id": self.linkedTaskID
        }


