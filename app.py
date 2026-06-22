from __future__ import annotations

import json
import uuid
from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta
from pathlib import Path
from typing import Callable

import wx
import wx.adv


APP_TITLE = "SuperScheduler"
DATA_FILE = Path(__file__).with_name("superscheduler_data.json")
CREDENTIALS_FILE = Path(__file__).with_name("credentials.json")
TOKEN_FILE = Path(__file__).with_name("token.json")
GOOGLE_SCOPES = ["https://www.googleapis.com/auth/calendar.events"]


def local_tz():
    return datetime.now().astimezone().tzinfo


def parse_datetime(value: str) -> datetime:
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=local_tz())
    return parsed


def start_of_week(day: date | None = None) -> date:
    current = day or date.today()
    return current - timedelta(days=current.weekday())


def wxdate_to_date(value: wx.DateTime) -> date:
    return date(value.GetYear(), value.GetMonth() + 1, value.GetDay())


def parse_time_text(raw_value: str) -> time:
    for fmt in ("%H:%M", "%I:%M %p", "%I:%M%p"):
        try:
            return datetime.strptime(raw_value.strip(), fmt).time()
        except ValueError:
            pass
    raise ValueError("Use HH:MM, such as 09:30 or 17:00.")


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


@dataclass
class TaskItem:
    title: str
    done: bool = False
    due: str = ""
    task_id: str = field(default_factory=lambda: str(uuid.uuid4()))

    @classmethod
    def from_dict(cls, payload: dict) -> "TaskItem":
        return cls(
            task_id=payload.get("task_id", str(uuid.uuid4())),
            title=payload.get("title", "Untitled task"),
            done=payload.get("done", False),
            due=payload.get("due", ""),
        )

    def to_dict(self) -> dict:
        return {
            "task_id": self.task_id,
            "title": self.title,
            "done": self.done,
            "due": self.due,
        }


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


class GoogleCalendarClient:
    def __init__(self, credentials_path: Path, token_path: Path):
        self.credentials_path = credentials_path
        self.token_path = token_path
        self.service = None

    def connect(self):
        try:
            from google.auth.transport.requests import Request
            from google.oauth2.credentials import Credentials
            from google_auth_oauthlib.flow import InstalledAppFlow
            from googleapiclient.discovery import build
        except ImportError as exc:
            raise RuntimeError(
                "Google Calendar packages are not installed. Run: pip install -r requirements.txt"
            ) from exc

        credentials = None
        if self.token_path.exists():
            credentials = Credentials.from_authorized_user_file(str(self.token_path), GOOGLE_SCOPES)

        if not credentials or not credentials.valid:
            if credentials and credentials.expired and credentials.refresh_token:
                credentials.refresh(Request())
            else:
                if not self.credentials_path.exists():
                    raise RuntimeError(
                        "Missing credentials.json. Create a Google OAuth desktop client and place "
                        "the downloaded file next to app.py."
                    )
                flow = InstalledAppFlow.from_client_secrets_file(str(self.credentials_path), GOOGLE_SCOPES)
                credentials = flow.run_local_server(port=0)

            self.token_path.write_text(credentials.to_json(), encoding="utf-8")

        self.service = build("calendar", "v3", credentials=credentials)
        return self.service

    def is_connected(self) -> bool:
        return self.service is not None

    def list_events(self, week_start: date) -> list[ScheduleEvent]:
        service = self.service or self.connect()
        start_dt = datetime.combine(week_start, time.min).replace(tzinfo=local_tz())
        end_dt = start_dt + timedelta(days=7)

        result = (
            service.events()
            .list(
                calendarId="primary",
                timeMin=start_dt.isoformat(),
                timeMax=end_dt.isoformat(),
                singleEvents=True,
                orderBy="startTime",
            )
            .execute()
        )

        events = []
        for item in result.get("items", []):
            start_payload = item.get("start", {})
            end_payload = item.get("end", {})
            raw_start = start_payload.get("dateTime") or start_payload.get("date")
            raw_end = end_payload.get("dateTime") or end_payload.get("date")
            if not raw_start or not raw_end:
                continue

            start_value = self._parse_google_time(raw_start)
            end_value = self._parse_google_time(raw_end)
            events.append(
                ScheduleEvent(
                    event_id=item.get("id", str(uuid.uuid4())),
                    title=item.get("summary", "Untitled"),
                    start=start_value,
                    end=end_value,
                    source="google",
                    description=item.get("description", ""),
                )
            )
        return events

    def create_event(self, event: ScheduleEvent) -> ScheduleEvent:
        service = self.service or self.connect()
        body = {
            "summary": event.title,
            "description": event.description,
            "start": {"dateTime": event.start.isoformat()},
            "end": {"dateTime": event.end.isoformat()},
        }
        created = service.events().insert(calendarId="primary", body=body).execute()
        event.event_id = created.get("id", event.event_id)
        event.source = "google"
        return event

    @staticmethod
    def _parse_google_time(raw_value: str) -> datetime:
        if "T" not in raw_value:
            parsed_date = date.fromisoformat(raw_value)
            return datetime.combine(parsed_date, time.min).replace(tzinfo=local_tz())
        return parse_datetime(raw_value.replace("Z", "+00:00")).astimezone(local_tz())


class EventDialog(wx.Dialog):
    def __init__(
        self,
        parent: wx.Window,
        title: str,
        initial_day: date,
        initial_hour: int = 9,
        google_enabled: bool = False,
    ):
        super().__init__(parent, title=title, size=(420, 330))
        self.google_enabled = google_enabled

        panel = wx.Panel(self)
        sizer = wx.BoxSizer(wx.VERTICAL)
        form = wx.FlexGridSizer(rows=0, cols=2, vgap=10, hgap=12)
        form.AddGrowableCol(1, 1)

        self.title_input = wx.TextCtrl(panel)
        self.date_input = wx.adv.DatePickerCtrl(panel)
        self.date_input.SetValue(wx.DateTime.FromDMY(initial_day.day, initial_day.month - 1, initial_day.year))
        self.start_input = wx.TextCtrl(panel, value=f"{initial_hour:02d}:00")
        self.end_input = wx.TextCtrl(panel, value=f"{min(initial_hour + 1, 23):02d}:00")
        self.description_input = wx.TextCtrl(panel, style=wx.TE_MULTILINE, size=(-1, 70))
        self.google_checkbox = wx.CheckBox(panel, label="Add to Google Calendar")
        self.google_checkbox.Enable(google_enabled)

        rows = [
            ("Title", self.title_input),
            ("Date", self.date_input),
            ("Starts", self.start_input),
            ("Ends", self.end_input),
            ("Notes", self.description_input),
            ("", self.google_checkbox),
        ]
        for label, control in rows:
            form.Add(wx.StaticText(panel, label=label), 0, wx.ALIGN_CENTER_VERTICAL)
            form.Add(control, 1, wx.EXPAND)

        buttons = wx.StdDialogButtonSizer()
        ok_button = wx.Button(panel, wx.ID_OK)
        cancel_button = wx.Button(panel, wx.ID_CANCEL)
        buttons.AddButton(ok_button)
        buttons.AddButton(cancel_button)
        buttons.Realize()

        sizer.Add(form, 1, wx.ALL | wx.EXPAND, 16)
        sizer.Add(buttons, 0, wx.ALL | wx.EXPAND, 12)
        panel.SetSizer(sizer)

    def get_event(self) -> tuple[ScheduleEvent, bool]:
        event_title = self.title_input.GetValue().strip()
        if not event_title:
            raise ValueError("Title is required.")

        event_date = wxdate_to_date(self.date_input.GetValue())
        start_value = parse_time_text(self.start_input.GetValue())
        end_value = parse_time_text(self.end_input.GetValue())
        start_dt = datetime.combine(event_date, start_value).replace(tzinfo=local_tz())
        end_dt = datetime.combine(event_date, end_value).replace(tzinfo=local_tz())
        if end_dt <= start_dt:
            end_dt += timedelta(days=1)

        return (
            ScheduleEvent(
                title=event_title,
                start=start_dt,
                end=end_dt,
                description=self.description_input.GetValue().strip(),
            ),
            self.google_checkbox.IsChecked() and self.google_enabled,
        )


class ScheduleCanvas(wx.ScrolledWindow):
    def __init__(self, parent: wx.Window, on_new_event: Callable[[date, int], None]):
        super().__init__(parent, style=wx.BORDER_NONE | wx.VSCROLL | wx.HSCROLL)
        self.SetBackgroundStyle(wx.BG_STYLE_PAINT)
        self.SetScrollRate(10, 10)
        self.week_start = start_of_week()
        self.events: list[ScheduleEvent] = []
        self.on_new_event = on_new_event
        self.header_height = 58
        self.time_width = 72
        self.row_height = 58
        self.day_width = 150
        self.Bind(wx.EVT_PAINT, self.on_paint)
        self.Bind(wx.EVT_SIZE, self.on_size)
        self.Bind(wx.EVT_LEFT_DCLICK, self.on_double_click)

    def set_week(self, week_start: date) -> None:
        self.week_start = week_start
        self.update_virtual_size()
        self.Refresh()

    def set_events(self, events: list[ScheduleEvent]) -> None:
        self.events = events
        self.Refresh()

    def on_size(self, event: wx.SizeEvent) -> None:
        self.update_virtual_size()
        self.Refresh()
        event.Skip()

    def update_virtual_size(self) -> None:
        available_width = max(self.GetClientSize().width - self.time_width, 0)
        self.day_width = max(142, available_width // 7)
        self.SetVirtualSize((self.time_width + self.day_width * 7, self.header_height + self.row_height * 24 + 12))

    def on_double_click(self, event: wx.MouseEvent) -> None:
        x, y = self.CalcUnscrolledPosition(event.GetPosition())
        if x < self.time_width or y < self.header_height:
            return
        day_index = min(6, max(0, (x - self.time_width) // self.day_width))
        hour = min(23, max(0, (y - self.header_height) // self.row_height))
        self.on_new_event(self.week_start + timedelta(days=day_index), hour)

    def on_paint(self, _event: wx.PaintEvent) -> None:
        dc = wx.AutoBufferedPaintDC(self)
        self.PrepareDC(dc)
        dc.SetBackground(wx.Brush(wx.Colour("#f7f8fb")))
        dc.Clear()

        self.draw_headers(dc)
        self.draw_grid(dc)
        self.draw_events(dc)

    def draw_headers(self, dc: wx.DC) -> None:
        dc.SetPen(wx.Pen(wx.Colour("#d7dbe3"), 1))
        dc.SetBrush(wx.Brush(wx.Colour("#ffffff")))
        dc.DrawRectangle(0, 0, self.time_width + self.day_width * 7, self.header_height)

        label_font = wx.Font(10, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_BOLD)
        small_font = wx.Font(8, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_NORMAL)
        for day_index in range(7):
            current_day = self.week_start + timedelta(days=day_index)
            x = self.time_width + day_index * self.day_width
            dc.DrawLine(x, 0, x, self.header_height + self.row_height * 24)
            dc.SetFont(label_font)
            dc.SetTextForeground(wx.Colour("#222733"))
            dc.DrawText(current_day.strftime("%a"), x + 10, 10)
            dc.SetFont(small_font)
            dc.SetTextForeground(wx.Colour("#5f6776"))
            dc.DrawText(current_day.strftime("%b %d"), x + 10, 31)

    def draw_grid(self, dc: wx.DC) -> None:
        time_font = wx.Font(8, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_NORMAL)
        dc.SetFont(time_font)
        dc.SetTextForeground(wx.Colour("#717887"))

        for hour in range(25):
            y = self.header_height + hour * self.row_height
            dc.SetPen(wx.Pen(wx.Colour("#e2e5eb"), 1))
            dc.DrawLine(self.time_width, y, self.time_width + self.day_width * 7, y)
            if hour < 24:
                dc.DrawText(f"{hour:02d}:00", 16, y + 6)

        dc.SetPen(wx.Pen(wx.Colour("#d7dbe3"), 1))
        dc.DrawLine(self.time_width, 0, self.time_width, self.header_height + self.row_height * 24)
        for day_index in range(8):
            x = self.time_width + day_index * self.day_width
            dc.DrawLine(x, self.header_height, x, self.header_height + self.row_height * 24)

    def draw_events(self, dc: wx.DC) -> None:
        title_font = wx.Font(8, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_BOLD)
        meta_font = wx.Font(7, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_NORMAL)
        week_end = self.week_start + timedelta(days=7)

        for event in sorted(self.events, key=lambda item: item.start):
            if event.end.date() < self.week_start or event.start.date() >= week_end:
                continue

            day_index = (event.start.date() - self.week_start).days
            if day_index < 0 or day_index > 6:
                continue

            minutes_from_midnight = event.start.hour * 60 + event.start.minute
            duration_minutes = max(30, int((event.end - event.start).total_seconds() // 60))
            x = self.time_width + day_index * self.day_width + 6
            y = self.header_height + int(minutes_from_midnight / 60 * self.row_height) + 3
            width = self.day_width - 12
            height = max(28, int(duration_minutes / 60 * self.row_height) - 6)
            fill = wx.Colour("#d9ecff") if event.source == "google" else wx.Colour("#e9f6e8")
            border = wx.Colour("#5797d7") if event.source == "google" else wx.Colour("#61a765")

            dc.SetPen(wx.Pen(border, 1))
            dc.SetBrush(wx.Brush(fill))
            dc.DrawRoundedRectangle(x, y, width, height, 6)

            clip = wx.DCClipper(dc, x + 6, y + 4, width - 12, height - 8)
            dc.SetFont(title_font)
            dc.SetTextForeground(wx.Colour("#20242d"))
            dc.DrawText(event.title, x + 8, y + 5)
            dc.SetFont(meta_font)
            dc.SetTextForeground(wx.Colour("#455063"))
            dc.DrawText(f"{event.start.strftime('%H:%M')} - {event.end.strftime('%H:%M')}", x + 8, y + 21)
            del clip


class TaskPanel(wx.Panel):
    def __init__(self, parent: wx.Window, on_change: Callable[[], None]):
        super().__init__(parent)
        self.tasks: list[TaskItem] = []
        self.on_change = on_change

        sizer = wx.BoxSizer(wx.VERTICAL)
        header = wx.StaticText(self, label="Tasks")
        header.SetFont(wx.Font(12, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_BOLD))

        self.task_input = wx.TextCtrl(self, style=wx.TE_PROCESS_ENTER)
        self.task_input.SetHint("New task")
        self.task_list = wx.CheckListBox(self)
        add_button = wx.Button(self, label="Add")
        delete_button = wx.Button(self, label="Delete selected")

        sizer.Add(header, 0, wx.LEFT | wx.RIGHT | wx.TOP, 12)
        sizer.Add(self.task_input, 0, wx.ALL | wx.EXPAND, 12)
        sizer.Add(add_button, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM | wx.EXPAND, 12)
        sizer.Add(self.task_list, 1, wx.LEFT | wx.RIGHT | wx.BOTTOM | wx.EXPAND, 12)
        sizer.Add(delete_button, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM | wx.EXPAND, 12)
        self.SetSizer(sizer)

        add_button.Bind(wx.EVT_BUTTON, self.add_task)
        delete_button.Bind(wx.EVT_BUTTON, self.delete_selected)
        self.task_input.Bind(wx.EVT_TEXT_ENTER, self.add_task)
        self.task_list.Bind(wx.EVT_CHECKLISTBOX, self.toggle_task)

    def set_tasks(self, tasks: list[TaskItem]) -> None:
        self.tasks = tasks
        self.refresh()

    def refresh(self) -> None:
        self.task_list.Clear()
        for index, task in enumerate(self.tasks):
            label = task.title if not task.due else f"{task.title}  ({task.due})"
            self.task_list.Append(label)
            self.task_list.Check(index, task.done)

    def add_task(self, _event: wx.Event) -> None:
        title = self.task_input.GetValue().strip()
        if not title:
            return
        self.tasks.append(TaskItem(title=title))
        self.task_input.Clear()
        self.refresh()
        self.on_change()

    def delete_selected(self, _event: wx.Event) -> None:
        selection = self.task_list.GetSelection()
        if selection == wx.NOT_FOUND:
            return
        del self.tasks[selection]
        self.refresh()
        self.on_change()

    def toggle_task(self, event: wx.CommandEvent) -> None:
        index = event.GetSelection()
        self.tasks[index].done = self.task_list.IsChecked(index)
        self.on_change()


class SchedulerFrame(wx.Frame):
    def __init__(self):
        super().__init__(None, title=APP_TITLE, size=(1180, 760))
        self.storage = AppStorage(DATA_FILE)
        self.local_events, self.tasks = self.storage.load()
        self.google_client = GoogleCalendarClient(CREDENTIALS_FILE, TOKEN_FILE)
        self.google_events: list[ScheduleEvent] = []
        self.current_week = start_of_week()

        self.build_ui()
        self.refresh_title()
        self.refresh_schedule()

    def build_ui(self) -> None:
        root = wx.Panel(self)
        root_sizer = wx.BoxSizer(wx.VERTICAL)
        toolbar = wx.BoxSizer(wx.HORIZONTAL)

        previous_button = wx.Button(root, label="<")
        today_button = wx.Button(root, label="Today")
        next_button = wx.Button(root, label=">")
        new_button = wx.Button(root, label="New event")
        sync_button = wx.Button(root, label="Sync Google")
        connect_button = wx.Button(root, label="Connect Google")
        self.week_label = wx.StaticText(root, label="")
        self.week_label.SetFont(wx.Font(11, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_BOLD))

        toolbar.Add(previous_button, 0, wx.RIGHT, 6)
        toolbar.Add(today_button, 0, wx.RIGHT, 6)
        toolbar.Add(next_button, 0, wx.RIGHT, 14)
        toolbar.Add(self.week_label, 1, wx.ALIGN_CENTER_VERTICAL)
        toolbar.Add(new_button, 0, wx.RIGHT, 6)
        toolbar.Add(sync_button, 0, wx.RIGHT, 6)
        toolbar.Add(connect_button, 0)

        body = wx.SplitterWindow(root, style=wx.SP_LIVE_UPDATE)
        self.schedule = ScheduleCanvas(body, self.open_event_dialog)
        self.task_panel = TaskPanel(body, self.save)
        self.task_panel.set_tasks(self.tasks)
        body.SplitVertically(self.schedule, self.task_panel, sashPosition=880)
        body.SetMinimumPaneSize(260)

        root_sizer.Add(toolbar, 0, wx.ALL | wx.EXPAND, 10)
        root_sizer.Add(body, 1, wx.LEFT | wx.RIGHT | wx.BOTTOM | wx.EXPAND, 10)
        root.SetSizer(root_sizer)

        previous_button.Bind(wx.EVT_BUTTON, lambda _event: self.change_week(-1))
        today_button.Bind(wx.EVT_BUTTON, lambda _event: self.set_week(start_of_week()))
        next_button.Bind(wx.EVT_BUTTON, lambda _event: self.change_week(1))
        new_button.Bind(wx.EVT_BUTTON, lambda _event: self.open_event_dialog(date.today(), 9))
        sync_button.Bind(wx.EVT_BUTTON, lambda _event: self.sync_google())
        connect_button.Bind(wx.EVT_BUTTON, lambda _event: self.connect_google())

        menubar = wx.MenuBar()
        file_menu = wx.Menu()
        file_menu.Append(wx.ID_NEW, "New event\tCtrl+N")
        file_menu.Append(wx.ID_SAVE, "Save\tCtrl+S")
        file_menu.AppendSeparator()
        file_menu.Append(wx.ID_EXIT, "Exit")
        menubar.Append(file_menu, "File")
        self.SetMenuBar(menubar)
        self.Bind(wx.EVT_MENU, lambda _event: self.open_event_dialog(date.today(), 9), id=wx.ID_NEW)
        self.Bind(wx.EVT_MENU, lambda _event: self.save(), id=wx.ID_SAVE)
        self.Bind(wx.EVT_MENU, lambda _event: self.Close(), id=wx.ID_EXIT)
        self.Bind(wx.EVT_CLOSE, self.on_close)

    def refresh_title(self) -> None:
        week_end = self.current_week + timedelta(days=6)
        self.week_label.SetLabel(f"{self.current_week.strftime('%b %d')} - {week_end.strftime('%b %d, %Y')}")

    def refresh_schedule(self) -> None:
        all_events = self.local_events + self.google_events
        self.schedule.set_week(self.current_week)
        self.schedule.set_events(all_events)
        self.refresh_title()

    def set_week(self, week_start_value: date) -> None:
        self.current_week = week_start_value
        self.refresh_schedule()
        if self.google_client.is_connected():
            self.sync_google(show_success=False)

    def change_week(self, delta_weeks: int) -> None:
        self.set_week(self.current_week + timedelta(days=delta_weeks * 7))

    def open_event_dialog(self, initial_day: date, initial_hour: int) -> None:
        dialog = EventDialog(
            self,
            "New event",
            initial_day=initial_day,
            initial_hour=initial_hour,
            google_enabled=self.google_client.is_connected(),
        )
        try:
            if dialog.ShowModal() != wx.ID_OK:
                return
            try:
                event, add_to_google = dialog.get_event()
            except ValueError as exc:
                wx.MessageBox(str(exc), "Event needs a fix", wx.OK | wx.ICON_WARNING)
                return

            if add_to_google:
                try:
                    created = self.google_client.create_event(event)
                    self.google_events.append(created)
                except Exception as exc:
                    wx.MessageBox(str(exc), "Google Calendar error", wx.OK | wx.ICON_ERROR)
                    return
            else:
                self.local_events.append(event)
            self.save()
            self.refresh_schedule()
        finally:
            dialog.Destroy()

    def connect_google(self) -> None:
        try:
            self.google_client.connect()
            self.sync_google(show_success=False)
            wx.MessageBox("Google Calendar connected.", APP_TITLE, wx.OK | wx.ICON_INFORMATION)
        except Exception as exc:
            wx.MessageBox(str(exc), "Google Calendar setup", wx.OK | wx.ICON_WARNING)

    def sync_google(self, show_success: bool = True) -> None:
        try:
            self.google_events = self.google_client.list_events(self.current_week)
            self.refresh_schedule()
            if show_success:
                wx.MessageBox("Google Calendar synced.", APP_TITLE, wx.OK | wx.ICON_INFORMATION)
        except Exception as exc:
            wx.MessageBox(str(exc), "Google Calendar sync", wx.OK | wx.ICON_WARNING)

    def save(self) -> None:
        self.storage.save(self.local_events, self.tasks)

    def on_close(self, event: wx.CloseEvent) -> None:
        self.save()
        event.Skip()


class SchedulerApp(wx.App):
    def OnInit(self) -> bool:
        frame = SchedulerFrame()
        frame.Show()
        return True


if __name__ == "__main__":
    app = SchedulerApp(False)
    app.MainLoop()
