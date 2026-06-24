import json
from pathlib import Path

from schedule_event import ScheduleEvent
from task_item import TaskItem

class AppStorage:
    def __init__(self, path: Path):
        self.path = path

    def load(self) -> tuple[list[ScheduleEvent], list[TaskItem]]:
        if not self.path.exists():
            return [], []

        with self.path.open("r", encoding="utf-8") as file:
            payload = json.load(file)

        events = [ScheduleEvent.from_dict(item) for item in payload.get("events", [])]
        tasks = [TaskItem.from_dict(item) for item in payload.get("tasks", [])]
        return events, tasks

    def save(self, events: list[ScheduleEvent], tasks: list[TaskItem]) -> None:
        payload = {
            "events": [event.to_dict() for event in events if event.source == "local"],
            "tasks": [task.to_dict() for task in tasks],
        }
        with self.path.open("w", encoding="utf-8") as file:
            json.dump(payload, file, indent=2)