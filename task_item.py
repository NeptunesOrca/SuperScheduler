import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta
import copy

from time_management import serialize_datetime_or_none, parse_datetime_or_none, parse_datetime
from recurrence import Recurrence, serialize_recurrence_or_none, deserialize_recurrence_or_none

@dataclass
class TaskItem:
    task_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    created: datetime = field(default_factory=lambda: datetime.now())
    title: str = ""
    done: bool = False
    due: datetime | None = None
    priority: int = 0
    recurrence : Recurrence | None = None

    def copy(self, handleRecurrence : bool = True, copyFresh = True) -> "TaskItem":
        '''
        Creates a unique copy of the TaskItem, with a few automatic handling options

        Parameters
        ----------
        handleRecurrence : bool, default True
            If True, automatically handles recurrances, such that the copied task will bump its Recurrance forward
            (that is, the copied start date will be directly after the end date of the original, with the same duration).
            If the original TaskItem has a due date, it will also be bumped forward by the Recurrance duration.
            If the original TaskItem has no Recurrance, will be ignored.
            If False, the copied task will retain the original Recurrence and due date, if applicable.
        
        copyFresh : bool, default True
            If True, the copied task will always have its done attribute set to False.
            If False, the copied task will retain the done value of the original.

        '''
        copied = copy.deepcopy(self)
        copied.task_id = str(uuid.uuid4())
        if copyFresh:
            copied.done = False
        if handleRecurrence and (self.recurrence is not None):
            copied = copy.deepcopy(self)
            oldRecurrance = self.recurrence
            copied.recurrence = Recurrence(oldRecurrance.end+timedelta(days=1), oldRecurrance.duration)
            if self.due is not None:
                copied.due = self.due + self.recurrence.duration
        return copied

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
            recurrence=    deserialize_recurrence_or_none(payload.get("recurrence", "None")),
        )

    def to_dict(self) -> dict:
        return {
            "task_id": self.task_id,
            "created": self.created.isoformat(),
            "title": self.title,
            "done": self.done,
            "due": serialize_datetime_or_none(self.due),
            "priority": self.priority,
            "recurrence": serialize_recurrence_or_none(self.recurrence),
        }