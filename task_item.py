import uuid
from dataclasses import dataclass, field
from datetime import datetime

from time_management import parse_datetime

@dataclass
class TaskItem:
    title: str
    due: datetime
    done: bool = False
    task_id: str = field(default_factory=lambda: str(uuid.uuid4()))

    @classmethod
    def from_dict(cls, payload: dict) -> "TaskItem":
        return cls(
            task_id=payload.get("task_id", str(uuid.uuid4())),
            title=payload.get("title", "Untitled task"),
            done=payload.get("done", False),
            due=parse_datetime(payload["due"]),
        )

    def to_dict(self) -> dict:
        return {
            "task_id": self.task_id,
            "title": self.title,
            "done": self.done,
            "due": self.due.isoformat()
        }