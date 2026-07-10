import uuid
from dataclasses import dataclass, field
from datetime import datetime

from time_management import serialize_datetime_or_none, parse_datetime_or_none
from reoccurance import Reoccurrance, serialize_reoccurance_or_none, deserialize_reoccurance_or_none

@dataclass
class TaskItem:
    reoccurance : Reoccurrance | None
    task_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    title: str = ""
    done: bool = False
    due: datetime | None = None
    priority: int = 0

    @classmethod
    def from_dict(cls, payload: dict) -> "TaskItem":
        return cls(
            # Field       | Value                                     | Default
            reoccurance=    deserialize_reoccurance_or_none(payload["reoccurance"]),
            task_id=        payload.get("task_id",                      str(uuid.uuid4())),
            title=          payload.get("title",                        "Untitled task"),
            done=           payload.get("done",                         False),
            due=            parse_datetime_or_none(payload.get("due", "None")),
            priority=       payload.get("priority",                     0),
        )

    def to_dict(self) -> dict:
        return {
            "reoccurance": serialize_reoccurance_or_none(self.reoccurance),
            "task_id": self.task_id,
            "title": self.title,
            "done": self.done,
            "due": serialize_datetime_or_none(self.due),
            "priority": self.priority
        }