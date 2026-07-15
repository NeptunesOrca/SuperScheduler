import uuid
from dataclasses import dataclass, field
from datetime import datetime

from time_management import serialize_datetime_or_none, parse_datetime_or_none, parse_datetime
from reccurance import Reccurrance, serialize_reccurance_or_none, deserialize_reccurance_or_none

@dataclass
class TaskItem:
    task_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    created: datetime = field(default_factory=lambda: datetime.now())
    title: str = ""
    done: bool = False
    due: datetime | None = None
    priority: int = 0
    reccurance : Reccurrance | None = None

    @classmethod
    def from_dict(cls, payload: dict) -> "TaskItem":
        return cls(
            # Field       | Value                                     | Default
            task_id=        payload.get("task_id",                      str(uuid.uuid4())),
            created=        parse_datetime(payload.get("created",       datetime.now().isoformat())),
            title=          payload.get("title",                        "Untitled task"),
            done=           payload.get("done",                         False),
            due=            parse_datetime_or_none(payload.get("due", "None")),
            priority=       payload.get("priority",                     0),
            reccurance=    deserialize_reccurance_or_none(payload.get("reccurance", "None")),
        )

    def to_dict(self) -> dict:
        return {
            "task_id": self.task_id,
            "created": self.created.isoformat(),
            "title": self.title,
            "done": self.done,
            "due": serialize_datetime_or_none(self.due),
            "priority": self.priority,
            "reccurance": serialize_reccurance_or_none(self.reccurance),
        }