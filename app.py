from __future__ import annotations

import calendar
import uuid
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Callable

import wx
import wx.adv

from time_management import local_tz, parse_datetime, start_of_week, wxdate_to_date, parse_time_text
from schedule_event import ScheduleEvent
from task_item import TaskItem
from serialization import AppStorage
from google_calendar_client import GoogleCalendarClient

APP_TITLE = "SuperScheduler"
DATA_FILE = Path(__file__).with_name("superscheduler_data.json")
CREDENTIALS_FILE = Path(__file__).with_name("credentials.json")
TOKEN_FILE = Path(__file__).with_name("token.json")
TASK_PANEL_LEFT = "left"
TASK_PANEL_RIGHT = "right"
TASK_PANEL_MIN_WIDTH = 260
TASK_PANEL_DEFAULT_WIDTH = 300
VIEW_WEEK = "week"
VIEW_MONTH = "month"

class EventDialog(wx.Dialog):
    def __init__(
        self,
        parent: wx.Window,
        title: str,
        initial_day: date,
        initial_hour: int = 9,
        initial_minute: int = 0,
        google_enabled: bool = False,
        event: ScheduleEvent | None = None,
        event_title : str | None = None
    ):
        super().__init__(parent, title=title, size=(420, 330))
        self.google_enabled = google_enabled
        self.event = event

        panel = wx.Panel(self)
        sizer = wx.BoxSizer(wx.VERTICAL)
        form = wx.FlexGridSizer(rows=0, cols=2, vgap=10, hgap=12)
        form.AddGrowableCol(1, 1)

        self.title_input = wx.TextCtrl(panel)
        self.date_input = wx.adv.DatePickerCtrl(panel)
        selected_day = event.start.date() if event else initial_day
        selected_hour = event.start.hour if event else initial_hour
        selected_minute = event.start.minute if event else initial_minute
        end_hour = event.end.hour if event else min(initial_hour + 1, 23)
        end_minute = event.end.minute if event else initial_minute
        linked_task_id = str(event.linkedTaskID) if (event and event.linkedTaskID is not None) else "None"
        # display for linked task id (read-only)
        linked_task_label = wx.StaticText(panel, label=linked_task_id)
        self.date_input.SetValue(wx.DateTime.FromDMY(selected_day.day, selected_day.month - 1, selected_day.year))
        self.start_input = wx.TextCtrl(panel, value=f"{initial_hour:02d}:{initial_minute:02d}")
        self.start_input.SetValue(event.start.strftime("%H:%M") if event else f"{selected_hour:02d}:{selected_minute:02d}")
        self.end_input = wx.TextCtrl(panel, value=f"{end_hour:02d}:{end_minute:02d}")
        if event:
            self.end_input.SetValue(event.end.strftime("%H:%M"))
        self.description_input = wx.TextCtrl(panel, style=wx.TE_MULTILINE, size=(-1, 70))
        self.google_checkbox = wx.CheckBox(panel, label="Add to Google Calendar")
        self.google_checkbox.Enable(google_enabled and event is None)
        if event:
            self.title_input.SetValue(event.title)
            self.description_input.SetValue(event.description)
            if event.source == "google":
                self.google_checkbox.SetLabel("Google Calendar event")
                self.google_checkbox.SetValue(True)
        elif event_title:
            self.title_input.SetValue(event_title)

        rows = [
            ("Title", self.title_input),
            ("Date", self.date_input),
            ("Starts", self.start_input),
            ("Ends", self.end_input),
            ("Notes", self.description_input),
            ("", self.google_checkbox),
            ("Linked Task", linked_task_label),
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
                event_id=self.event.event_id if self.event else str(uuid.uuid4()),
                title=event_title,
                start=start_dt,
                end=end_dt,
                source=self.event.source if self.event else "local",
                description=self.description_input.GetValue().strip(),
                linkedTaskID=self.event.linkedTaskID if self.event else None,
            ),
            self.google_checkbox.IsChecked() and self.google_enabled,
        )


class ScheduleCanvas(wx.ScrolledWindow):
    def __init__(
        self,
        parent: wx.Window,
        on_new_event: Callable[[date, int, int, str], None | ScheduleEvent],
        on_edit_event: Callable[[ScheduleEvent], None],
        on_event_changed: Callable[[ScheduleEvent, datetime, datetime], bool],
        on_delete_event: Callable[[ScheduleEvent], None],
    ):
        super().__init__(parent, style=wx.BORDER_NONE | wx.VSCROLL | wx.HSCROLL)
        self.SetBackgroundStyle(wx.BG_STYLE_PAINT)
        self.SetScrollRate(10, 10)
        self.week_start = start_of_week()
        self.events: list[ScheduleEvent] = []
        self.on_new_event = on_new_event
        self.on_edit_event = on_edit_event
        self.on_event_changed = on_event_changed
        self.on_delete_event = on_delete_event
        self.header_height = 58
        self.time_width = 72
        self.row_height = 58
        self.day_width = 150
        self.edge_margin = 8
        self.snap_minutes = 15
        self.min_duration_minutes = 15
        self.pending_drag_event: ScheduleEvent | None = None
        self.pending_drag_mode = ""
        self.pending_drag_pos: tuple[int, int] | None = None
        self.drag_started = False
        self.drag_original_start: datetime | None = None
        self.drag_original_end: datetime | None = None
        self.drag_anchor_offset_minutes = 0
        self.preview_task: TaskItem | None = None
        self.preview_day_index: int = 0
        self.preview_start_minutes: int = 0
        self.preview_duration_minutes: int = 60
        self.Bind(wx.EVT_PAINT, self.on_paint)
        self.Bind(wx.EVT_SIZE, self.on_size)
        self.Bind(wx.EVT_LEFT_DCLICK, self.on_double_click)
        self.Bind(wx.EVT_LEFT_DOWN, self.on_left_down)
        self.Bind(wx.EVT_LEFT_UP, self.on_left_up)
        self.Bind(wx.EVT_MOTION, self.on_motion)
        self.Bind(wx.EVT_RIGHT_DOWN, self.on_right_down)

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
        selected_event = self.hit_test_event(x, y)
        if selected_event:
            self.clear_drag_state()
            self.on_edit_event(selected_event)
            return

        if x < self.time_width or y < self.header_height:
            return
        day_index = min(6, max(0, (x - self.time_width) // self.day_width))
        hour = min(23, max(0, (y - self.header_height) // self.row_height))
        self.on_new_event(self.week_start + timedelta(days=day_index), hour, 0, "New Event")

    def hit_test_event(self, x: int, y: int) -> ScheduleEvent | None:
        result = self.hit_test_event_part(x, y)
        return result[0] if result else None

    def hit_test_event_part(self, x: int, y: int) -> tuple[ScheduleEvent, str] | None:
        for rect, event in reversed(self.get_event_rects()):
            if rect.Contains(x, y):
                if y <= rect.GetTop() + self.edge_margin:
                    return event, "resize-start"
                if y >= rect.GetBottom() - self.edge_margin:
                    return event, "resize-end"
                return event, "move"
        return None

    def on_left_down(self, event: wx.MouseEvent) -> None:
        x, y = self.CalcUnscrolledPosition(event.GetPosition())
        hit_result = self.hit_test_event_part(x, y)
        if hit_result:
            selected_event, mode = hit_result
            self.pending_drag_event = selected_event
            self.pending_drag_mode = mode
            self.pending_drag_pos = (x, y)
            self.drag_original_start = selected_event.start
            self.drag_original_end = selected_event.end
            self.drag_anchor_offset_minutes = max(0, self.minutes_from_datetime(selected_event.start, y))
        event.Skip()

    def on_motion(self, event: wx.MouseEvent) -> None:
        x, y = self.CalcUnscrolledPosition(event.GetPosition())
        if self.pending_drag_event and event.LeftIsDown():
            self.maybe_start_drag(x, y)
            if self.drag_started:
                self.update_drag_preview(x, y)
                return

        if not event.LeftIsDown():
            self.update_cursor(x, y)
        event.Skip()

    def set_task_preview(self, task: TaskItem | None, screen_pos: wx.Point | None) -> None:
        if task is None or screen_pos is None:
            self.preview_task = None
            self.Refresh()
            return

        client_pt = self.ScreenToClient(screen_pos)
        if not self.GetClientRect().Contains(client_pt):
            self.preview_task = None
            self.Refresh()
            return

        x, y = self.CalcUnscrolledPosition(client_pt)
        if x < self.time_width or y < self.header_height:
            self.preview_task = None
            self.Refresh()
            return

        self.preview_task = task
        self.preview_day_index = self.day_index_from_x(x)
        self.preview_start_minutes = self.floor_to_grid(self.minutes_from_y(y))
        self.Refresh()

    def on_left_up(self, event: wx.MouseEvent) -> None:
        if self.drag_started and self.pending_drag_event and self.drag_original_start and self.drag_original_end:
            if self.HasCapture():
                self.ReleaseMouse()
            selected_event = self.pending_drag_event
            original_start = self.drag_original_start
            original_end = self.drag_original_end
            changed = selected_event.start != original_start or selected_event.end != original_end
            if changed and not self.on_event_changed(selected_event, original_start, original_end):
                selected_event.start = original_start
                selected_event.end = original_end
            self.Refresh()
        self.clear_drag_state()
        if self.preview_task is not None:
            self.preview_task = None
            self.Refresh()
        event.Skip()

    def on_right_down(self, event: wx.MouseEvent) -> None:
        x, y = self.CalcUnscrolledPosition(event.GetPosition())
        selected_event = self.hit_test_event(x, y)

        if self.HasCapture():
            self.ReleaseMouse()
        self.clear_drag_state()

        day_index = self.day_index_from_x(x)
        hour = min(23, max(0, self.minutes_from_y(y) // 60))
        click_day = self.week_start + timedelta(days=day_index)

        menu = wx.Menu()
        edit_id = wx.Window.NewControlId()
        new_id = wx.Window.NewControlId()
        delete_id = wx.Window.NewControlId()
        menu.Append(new_id, "New event")
        menu.Bind(wx.EVT_MENU, lambda _event: self.on_new_event(click_day, hour, 0, "New Event"), id=new_id)
        
        if selected_event:
            menu.AppendSeparator()
            menu.Append(edit_id, "Edit event")
            menu.Append(delete_id, "Delete event")        
            menu.Bind(wx.EVT_MENU, lambda _event: self.on_edit_event(selected_event), id=edit_id)
            menu.Bind(wx.EVT_MENU, lambda _event: self.on_delete_event(selected_event), id=delete_id)
        self.PopupMenu(menu)
        menu.Destroy()

    def maybe_start_drag(self, x: int, y: int) -> None:
        if self.drag_started or not self.pending_drag_pos:
            return
        start_x, start_y = self.pending_drag_pos
        if abs(x - start_x) < 4 and abs(y - start_y) < 4:
            return
        self.drag_started = True
        if not self.HasCapture():
            self.CaptureMouse()

    def update_drag_preview(self, x: int, y: int) -> None:
        if not self.pending_drag_event or not self.drag_original_start or not self.drag_original_end:
            return

        selected_event = self.pending_drag_event
        if self.pending_drag_mode == "move":
            duration = self.drag_original_end - self.drag_original_start
            day_index = self.day_index_from_x(x)
            start_minutes = self.minutes_from_y(y) - self.drag_anchor_offset_minutes
            start_minutes = self.snap_to_grid(start_minutes)
            max_start_minutes = (24 * 60) - max(self.min_duration_minutes, int(duration.total_seconds() // 60))
            start_minutes = min(max(0, start_minutes), max(0, max_start_minutes))
            selected_event.start = self.datetime_from_grid(day_index, start_minutes)
            selected_event.end = selected_event.start + duration
        elif self.pending_drag_mode == "resize-start":
            day_index = (self.drag_original_start.date() - self.week_start).days
            start_minutes = self.snap_to_grid(self.minutes_from_y(y))
            new_start = self.datetime_from_grid(day_index, max(0, start_minutes))
            latest_start = selected_event.end - timedelta(minutes=self.min_duration_minutes)
            selected_event.start = min(new_start, latest_start)
        elif self.pending_drag_mode == "resize-end":
            day_index = (self.drag_original_start.date() - self.week_start).days
            end_minutes = self.snap_to_grid(self.minutes_from_y(y))
            new_end = self.datetime_from_grid(day_index, min(24 * 60, end_minutes))
            earliest_end = selected_event.start + timedelta(minutes=self.min_duration_minutes)
            selected_event.end = max(new_end, earliest_end)

        self.Refresh()

    def update_cursor(self, x: int, y: int) -> None:
        hit_result = self.hit_test_event_part(x, y)
        if not hit_result:
            self.SetCursor(wx.Cursor(wx.CURSOR_ARROW))
            return
        _selected_event, mode = hit_result
        if mode.startswith("resize"):
            self.SetCursor(wx.Cursor(wx.CURSOR_SIZENS))
        else:
            self.SetCursor(wx.Cursor(wx.CURSOR_HAND))

    def clear_drag_state(self) -> None:
        self.pending_drag_event = None
        self.pending_drag_mode = ""
        self.pending_drag_pos = None
        self.drag_started = False
        self.drag_original_start = None
        self.drag_original_end = None
        self.drag_anchor_offset_minutes = 0

    def day_index_from_x(self, x: int) -> int:
        return min(6, max(0, (x - self.time_width) // self.day_width))

    def minutes_from_y(self, y: int) -> int:
        raw_minutes = int((y - self.header_height) / self.row_height * 60)
        return min(24 * 60, max(0, raw_minutes))

    def snap_to_grid(self, minutes: int) -> int:
        return int(round(minutes / self.snap_minutes) * self.snap_minutes)

    def floor_to_grid(self, minutes: int) -> int:
        return minutes - (minutes % self.snap_minutes)

    def datetime_from_grid(self, day_index: int, minutes: int) -> datetime:
        event_day = self.week_start + timedelta(days=day_index)
        return datetime.combine(event_day, datetime.min.time()).replace(tzinfo=local_tz()) + timedelta(minutes=minutes)

    def minutes_since_midnight(self, value: datetime) -> int:
        return value.hour * 60 + value.minute

    def minutes_from_datetime(self, start_value: datetime, y: int) -> int:
        clicked_minutes = self.minutes_from_y(y)
        return self.snap_to_grid(clicked_minutes - self.minutes_since_midnight(start_value))

    def get_event_rects(self) -> list[tuple[wx.Rect, ScheduleEvent]]:
        event_rects = []
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
            event_rects.append((wx.Rect(x, y, width, height), event))

        return event_rects

    def on_paint(self, _event: wx.PaintEvent) -> None:
        dc = wx.AutoBufferedPaintDC(self)
        self.PrepareDC(dc)
        dc.SetBackground(wx.Brush(wx.Colour("#f7f8fb")))
        dc.Clear()

        self.draw_headers(dc)
        self.draw_grid(dc)
        self.draw_events(dc)
        self.draw_task_preview(dc)

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
        for rect, event in self.get_event_rects():
            x = rect.GetX()
            y = rect.GetY()
            width = rect.GetWidth()
            height = rect.GetHeight()
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

    def draw_task_preview(self, dc: wx.DC) -> None:
        if self.preview_task is None:
            return

        width = self.day_width - 12
        height = max(40, int(self.row_height) - 6)
        x = self.time_width + self.preview_day_index * self.day_width + 6
        y = self.header_height + int(self.preview_start_minutes / 60 * self.row_height) + 3
        label_text = self.preview_task.title
        duration_text = f"{self.preview_duration_minutes} min"

        border_colour = wx.Colour(97, 160, 85)
        fill_colour = wx.Colour(97, 160, 85, 80)
        text_colour = wx.Colour(255, 255, 255)

        dc.SetPen(wx.Pen(border_colour, 1))
        dc.SetBrush(wx.Brush(fill_colour))
        dc.DrawRoundedRectangle(x, y, width, height, 6)

        title_font = wx.Font(8, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_BOLD)
        meta_font = wx.Font(7, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_NORMAL)

        dc.SetFont(title_font)
        dc.SetTextForeground(text_colour)
        dc.DrawText(label_text, x + 8, y + 6)

        dc.SetFont(meta_font)
        dc.DrawText(duration_text, x + 8, y + 23)


class MonthCalendarCanvas(wx.ScrolledWindow):
    def __init__(
        self,
        parent: wx.Window,
        on_new_event: Callable[[date, int], None],
        on_edit_event: Callable[[ScheduleEvent], None],
        on_delete_event: Callable[[ScheduleEvent], None],
    ):
        super().__init__(parent, style=wx.BORDER_NONE | wx.VSCROLL)
        self.SetBackgroundStyle(wx.BG_STYLE_PAINT)
        self.SetScrollRate(10, 10)
        today = date.today()
        self.month_start = date(today.year, today.month, 1)
        self.events: list[ScheduleEvent] = []
        self.on_new_event = on_new_event
        self.on_edit_event = on_edit_event
        self.on_delete_event = on_delete_event
        self.header_height = 42
        self.cell_width = 142
        self.cell_height = 112
        self.day_names = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
        self.Bind(wx.EVT_PAINT, self.on_paint)
        self.Bind(wx.EVT_SIZE, self.on_size)
        self.Bind(wx.EVT_LEFT_DCLICK, self.on_double_click)
        self.Bind(wx.EVT_RIGHT_DOWN, self.on_right_down)

    def set_month(self, month_start: date) -> None:
        self.month_start = date(month_start.year, month_start.month, 1)
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
        available_width = max(self.GetClientSize().width, 0)
        self.cell_width = max(118, available_width // 7)
        self.cell_height = max(96, (max(self.GetClientSize().height, 620) - self.header_height) // 6)
        self.SetVirtualSize((self.cell_width * 7, self.header_height + self.cell_height * 6))

    def on_double_click(self, event: wx.MouseEvent) -> None:
        x, y = self.CalcUnscrolledPosition(event.GetPosition())
        selected_event = self.hit_test_event(x, y)
        if selected_event:
            self.on_edit_event(selected_event)
            return

        selected_day = self.day_from_position(x, y)
        if selected_day:
            self.on_new_event(selected_day, 9)

    def on_right_down(self, event: wx.MouseEvent) -> None:
        x, y = self.CalcUnscrolledPosition(event.GetPosition())
        selected_day = self.day_from_position(x, y)
        selected_event = self.hit_test_event(x, y)
        if not selected_day and not selected_event:
            event.Skip()
            return

        menu = wx.Menu()
        new_id = wx.Window.NewControlId()
        menu.Append(new_id, "New event")
        menu.Bind(wx.EVT_MENU, lambda _event: self.on_new_event(selected_day or date.today(), 9), id=new_id)
        if selected_event:
            edit_id = wx.Window.NewControlId()
            delete_id = wx.Window.NewControlId()
            menu.AppendSeparator()
            menu.Append(edit_id, "Edit event")
            menu.Append(delete_id, "Delete event")
            menu.Bind(wx.EVT_MENU, lambda _event: self.on_edit_event(selected_event), id=edit_id)
            menu.Bind(wx.EVT_MENU, lambda _event: self.on_delete_event(selected_event), id=delete_id)

        self.PopupMenu(menu)
        menu.Destroy()

    def day_from_position(self, x: int, y: int) -> date | None:
        if y < self.header_height:
            return None
        column = min(6, max(0, x // self.cell_width))
        row = min(5, max(0, (y - self.header_height) // self.cell_height))
        return self.first_visible_day() + timedelta(days=row * 7 + column)

    def first_visible_day(self) -> date:
        return self.month_start - timedelta(days=self.month_start.weekday())

    def hit_test_event(self, x: int, y: int) -> ScheduleEvent | None:
        for rect, event in reversed(self.get_event_rects()):
            if rect.Contains(x, y):
                return event
        return None

    def get_event_rects(self) -> list[tuple[wx.Rect, ScheduleEvent]]:
        rects = []
        first_day = self.first_visible_day()
        last_day = first_day + timedelta(days=42)
        visible_counts: dict[date, int] = {}

        for event in sorted(self.events, key=lambda item: item.start):
            event_day = event.start.date()
            if event_day < first_day or event_day >= last_day:
                continue

            count = visible_counts.get(event_day, 0)
            visible_counts[event_day] = count + 1
            if count >= 4:
                continue

            offset = (event_day - first_day).days
            column = offset % 7
            row = offset // 7
            x = column * self.cell_width + 6
            y = self.header_height + row * self.cell_height + 30 + count * 20
            rects.append((wx.Rect(x, y, self.cell_width - 12, 17), event))

        return rects

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
        dc.DrawRectangle(0, 0, self.cell_width * 7, self.header_height)

        header_font = wx.Font(9, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_BOLD)
        dc.SetFont(header_font)
        dc.SetTextForeground(wx.Colour("#222733"))
        for column, day_name in enumerate(self.day_names):
            x = column * self.cell_width
            dc.DrawText(day_name, x + 10, 13)

    def draw_grid(self, dc: wx.DC) -> None:
        first_day = self.first_visible_day()
        today = date.today()
        day_font = wx.Font(9, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_BOLD)
        outside_font = wx.Font(9, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_NORMAL)

        for row in range(6):
            for column in range(7):
                current_day = first_day + timedelta(days=row * 7 + column)
                x = column * self.cell_width
                y = self.header_height + row * self.cell_height
                fill = wx.Colour("#ffffff") if current_day.month == self.month_start.month else wx.Colour("#f0f2f6")
                if current_day == today:
                    fill = wx.Colour("#fff7df")

                dc.SetPen(wx.Pen(wx.Colour("#d7dbe3"), 1))
                dc.SetBrush(wx.Brush(fill))
                dc.DrawRectangle(x, y, self.cell_width, self.cell_height)
                dc.SetFont(day_font if current_day.month == self.month_start.month else outside_font)
                dc.SetTextForeground(wx.Colour("#222733") if current_day.month == self.month_start.month else wx.Colour("#858c99"))
                dc.DrawText(str(current_day.day), x + 10, y + 8)

    def draw_events(self, dc: wx.DC) -> None:
        title_font = wx.Font(7, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_NORMAL)
        dc.SetFont(title_font)
        event_counts = self.count_events_by_day()

        for rect, event in self.get_event_rects():
            fill = wx.Colour("#d9ecff") if event.source == "google" else wx.Colour("#e9f6e8")
            border = wx.Colour("#5797d7") if event.source == "google" else wx.Colour("#61a765")
            dc.SetPen(wx.Pen(border, 1))
            dc.SetBrush(wx.Brush(fill))
            dc.DrawRoundedRectangle(rect.GetX(), rect.GetY(), rect.GetWidth(), rect.GetHeight(), 4)
            clip = wx.DCClipper(dc, rect.GetX() + 4, rect.GetY() + 2, rect.GetWidth() - 8, rect.GetHeight() - 4)
            dc.SetTextForeground(wx.Colour("#20242d"))
            dc.DrawText(f"{event.start.strftime('%H:%M')} {event.title}", rect.GetX() + 5, rect.GetY() + 2)
            del clip

        self.draw_overflow_counts(dc, event_counts)

    def draw_task_preview(self, dc: wx.DC) -> None:
        if self.preview_task is None:
            return

        width = self.day_width - 12
        height = max(28, int(self.row_height) - 6)
        x = self.time_width + self.preview_day_index * self.day_width + 6
        y = self.header_height + int(self.preview_start_minutes / 60 * self.row_height) + 3
        colour = wx.Colour(97, 160, 85, 96)
        try:
            gc = wx.GraphicsContext.Create(dc)
            brush = gc.CreateBrush(wx.Brush(colour))
            gc.SetBrush(brush)
            gc.SetPen(wx.Pen(wx.Colour(97, 160, 85), 1))
            gc.DrawRoundedRectangle(x, y, width, height, 6)
        except Exception:
            dc.SetPen(wx.Pen(wx.Colour(97, 160, 85), 1))
            dc.SetBrush(wx.Brush(wx.Colour(200, 230, 200)))
            dc.DrawRoundedRectangle(x, y, width, height, 6)

    def count_events_by_day(self) -> dict[date, int]:
        counts: dict[date, int] = {}
        first_day = self.first_visible_day()
        last_day = first_day + timedelta(days=42)
        for event in self.events:
            event_day = event.start.date()
            if first_day <= event_day < last_day:
                counts[event_day] = counts.get(event_day, 0) + 1
        return counts

    def draw_overflow_counts(self, dc: wx.DC, event_counts: dict[date, int]) -> None:
        overflow_font = wx.Font(7, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_BOLD)
        dc.SetFont(overflow_font)
        dc.SetTextForeground(wx.Colour("#5f6776"))
        first_day = self.first_visible_day()
        for current_day, count in event_counts.items():
            if count <= 4:
                continue
            offset = (current_day - first_day).days
            column = offset % 7
            row = offset // 7
            x = column * self.cell_width + 10
            y = self.header_height + row * self.cell_height + 112
            dc.DrawText(f"+{count - 4} more", x, min(y, self.header_height + (row + 1) * self.cell_height - 18))


class TaskPanel(wx.Panel):
    def __init__(
        self,
        parent: wx.Window,
        on_change: Callable[[], None],
        on_create_event_from_task: Callable[[TaskItem, date | None, int | None], None] | None = None,
        on_drop_task_to_schedule: Callable[[TaskItem, wx.Point], None] | None = None,
        on_task_preview_move: Callable[[TaskItem | None, wx.Point | None], None] | None = None,
    ):
        super().__init__(parent)
        self.tasks: list[TaskItem] = []
        self.on_change = on_change
        self.on_create_event_from_task = on_create_event_from_task
        self.on_drop_task_to_schedule = on_drop_task_to_schedule
        self.on_task_preview_move = on_task_preview_move
        self.dragged_task: TaskItem | None = None

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
        self.task_list.Bind(wx.EVT_LEFT_DOWN, self.on_task_begin_drag)
        self.task_list.Bind(wx.EVT_LEFT_UP, self.on_task_drop)
        self.task_list.Bind(wx.EVT_MOTION, self.on_task_drag_motion)
        self.task_list.Bind(wx.EVT_LEFT_DCLICK, self.on_task_double_click)
        self.task_list.Bind(wx.EVT_LEFT_DOWN, self.on_task_left_click)
        self.task_list.Bind(wx.EVT_CONTEXT_MENU, self.on_task_right_click)

    def on_task_begin_drag(self, event: wx.MouseEvent) -> None:
        selection = self.task_list.GetSelection()
        if selection != wx.NOT_FOUND and selection < len(self.tasks):
            self.dragged_task = self.tasks[selection]
            if not self.task_list.HasCapture():
                self.task_list.CaptureMouse()
            if self.on_task_preview_move is not None:
                self.on_task_preview_move(self.dragged_task, wx.GetMousePosition())
        event.Skip()

    def on_task_drag_motion(self, event: wx.MouseEvent) -> None:
        if self.dragged_task is not None and event.LeftIsDown() and self.on_task_preview_move is not None:
            self.on_task_preview_move(self.dragged_task, wx.GetMousePosition())
        event.Skip()

    def on_task_drop(self, event: wx.MouseEvent) -> None:
        if self.dragged_task is not None and self.on_drop_task_to_schedule is not None:
            self.on_drop_task_to_schedule(self.dragged_task, wx.GetMousePosition())
        self.dragged_task = None
        if self.on_task_preview_move is not None:
            self.on_task_preview_move(None, None)
        try:
            if self.task_list.HasCapture():
                self.task_list.ReleaseMouse()
        except wx.wxAssertionError:
            pass
        event.Skip()

    def on_task_double_click(self, event: wx.MouseEvent) -> None:
        selection = self.task_list.GetSelection()
        if selection != wx.NOT_FOUND and self.on_create_event_from_task is not None:
            self.on_create_event_from_task(self.tasks[selection], None, None)
        event.Skip()

    def on_task_left_click(self, event: wx.MouseEvent) -> None:
        event.Skip()

    def on_task_right_click(self, event: wx.ContextMenuEvent) -> None:
        menu = wx.Menu()
        self.task_list.PopupMenu(menu, event.GetPosition())

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
        self.current_month = date.today().replace(day=1)
        self.current_view = VIEW_WEEK
        self.task_panel_side = TASK_PANEL_RIGHT
        self.task_panel_width = TASK_PANEL_DEFAULT_WIDTH

        self.build_ui()
        self.refresh_title()
        self.refresh_schedule()

    def getEventByID(self, event_id: str) -> ScheduleEvent | None:
        for event in self.local_events + self.google_events:
            if event.event_id == event_id:
                return event
        return None
    
    def getTaskByID(self, task_id: str) -> TaskItem | None:
        for task in self.tasks:
            if task.task_id == task_id:
                return task
        return None

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

        self.body = wx.SplitterWindow(root, style=wx.SP_LIVE_UPDATE)
        self.calendar_panel = wx.Panel(self.body)
        calendar_sizer = wx.BoxSizer(wx.VERTICAL)
        self.schedule = ScheduleCanvas(
            self.calendar_panel,
            self.new_event_dialog,
            self.open_existing_event_dialog,
            self.handle_event_drag_changed,
            self.delete_event,
        )
        self.month_calendar = MonthCalendarCanvas(
            self.calendar_panel,
            self.new_event_dialog,
            self.open_existing_event_dialog,
            self.delete_event,
        )
        calendar_sizer.Add(self.schedule, 1, wx.EXPAND)
        calendar_sizer.Add(self.month_calendar, 1, wx.EXPAND)
        self.calendar_panel.SetSizer(calendar_sizer)
        self.month_calendar.Hide()
        self.task_panel = TaskPanel(
            self.body,
            self.save,
            self.create_event_from_task,
            self.handle_task_drop_to_schedule,
            self.schedule.set_task_preview,
        )
        self.task_panel.set_tasks(self.tasks)
        self.body.SplitVertically(self.calendar_panel, self.task_panel, sashPosition=880)
        self.body.SetMinimumPaneSize(TASK_PANEL_MIN_WIDTH)

        root_sizer.Add(toolbar, 0, wx.ALL | wx.EXPAND, 10)
        root_sizer.Add(self.body, 1, wx.LEFT | wx.RIGHT | wx.BOTTOM | wx.EXPAND, 10)
        root.SetSizer(root_sizer)

        previous_button.Bind(wx.EVT_BUTTON, lambda _event: self.change_period(-1))
        today_button.Bind(wx.EVT_BUTTON, lambda _event: self.set_today())
        next_button.Bind(wx.EVT_BUTTON, lambda _event: self.change_period(1))
        new_button.Bind(wx.EVT_BUTTON, lambda _event: self.new_event_dialog(date.today(), 9))
        sync_button.Bind(wx.EVT_BUTTON, lambda _event: self.sync_google())
        connect_button.Bind(wx.EVT_BUTTON, lambda _event: self.connect_google())

        menubar = wx.MenuBar()
        file_menu = wx.Menu()
        file_menu.Append(wx.ID_NEW, "New event\tCtrl+N")
        file_menu.Append(wx.ID_SAVE, "Save\tCtrl+S")
        file_menu.AppendSeparator()
        file_menu.Append(wx.ID_EXIT, "Exit")
        menubar.Append(file_menu, "File")
        view_menu = wx.Menu()
        self.week_view_id = wx.NewIdRef()
        self.month_view_id = wx.NewIdRef()
        self.task_panel_left_id = wx.NewIdRef()
        self.task_panel_right_id = wx.NewIdRef()
        view_menu.AppendRadioItem(self.week_view_id, "Week view")
        view_menu.AppendRadioItem(self.month_view_id, "Month view")
        view_menu.Check(self.week_view_id, True)
        view_menu.AppendSeparator()
        view_menu.AppendRadioItem(self.task_panel_left_id, "Task panel on left")
        view_menu.AppendRadioItem(self.task_panel_right_id, "Task panel on right")
        view_menu.Check(self.task_panel_right_id, True)
        menubar.Append(view_menu, "View")
        self.SetMenuBar(menubar)
        self.Bind(wx.EVT_MENU, lambda _event: self.new_event_dialog(date.today(), 9), id=wx.ID_NEW)
        self.Bind(wx.EVT_MENU, lambda _event: self.save(), id=wx.ID_SAVE)
        self.Bind(wx.EVT_MENU, lambda _event: self.Close(), id=wx.ID_EXIT)
        self.Bind(wx.EVT_MENU, lambda _event: self.set_calendar_view(VIEW_WEEK), id=self.week_view_id)
        self.Bind(wx.EVT_MENU, lambda _event: self.set_calendar_view(VIEW_MONTH), id=self.month_view_id)
        self.Bind(wx.EVT_MENU, lambda _event: self.set_task_panel_side(TASK_PANEL_LEFT), id=self.task_panel_left_id)
        self.Bind(wx.EVT_MENU, lambda _event: self.set_task_panel_side(TASK_PANEL_RIGHT), id=self.task_panel_right_id)
        self.Bind(wx.EVT_CLOSE, self.on_close)

    def set_calendar_view(self, view_name: str) -> None:
        if view_name == self.current_view:
            return

        self.current_view = view_name
        if view_name == VIEW_MONTH:
            self.current_month = date(self.current_week.year, self.current_week.month, 1)
            self.schedule.Hide()
            self.month_calendar.Show()
        else:
            self.current_week = start_of_week(self.current_month)
            self.month_calendar.Hide()
            self.schedule.Show()

        menubar = self.GetMenuBar()
        menubar.Check(self.week_view_id, view_name == VIEW_WEEK)
        menubar.Check(self.month_view_id, view_name == VIEW_MONTH)
        self.calendar_panel.Layout()
        self.refresh_schedule()

    def set_task_panel_side(self, side: str) -> None:
        if side == self.task_panel_side:
            return

        self.remember_task_panel_width()
        self.task_panel_side = side
        self.body.Unsplit()
        panel_width = self.clamp_task_panel_width(self.task_panel_width)

        if side == TASK_PANEL_LEFT:
            self.body.SplitVertically(self.task_panel, self.calendar_panel, sashPosition=panel_width)
        else:
            self.body.SplitVertically(
                self.calendar_panel,
                self.task_panel,
                sashPosition=self.body.GetClientSize().width - panel_width,
            )

        menubar = self.GetMenuBar()
        menubar.Check(self.task_panel_left_id, side == TASK_PANEL_LEFT)
        menubar.Check(self.task_panel_right_id, side == TASK_PANEL_RIGHT)
        self.body.Layout()

    def remember_task_panel_width(self) -> None:
        client_width = self.body.GetClientSize().width
        sash_position = self.body.GetSashPosition()
        if self.task_panel_side == TASK_PANEL_LEFT:
            panel_width = sash_position
        else:
            panel_width = client_width - sash_position
        self.task_panel_width = self.clamp_task_panel_width(panel_width)

    def clamp_task_panel_width(self, panel_width: int) -> int:
        client_width = self.body.GetClientSize().width
        maximum_width = max(TASK_PANEL_MIN_WIDTH, client_width - TASK_PANEL_MIN_WIDTH)
        return min(max(TASK_PANEL_MIN_WIDTH, panel_width), maximum_width)

    def refresh_title(self) -> None:
        if self.current_view == VIEW_MONTH:
            self.week_label.SetLabel(self.current_month.strftime("%B %Y"))
            return

        week_end = self.current_week + timedelta(days=6)
        self.week_label.SetLabel(f"{self.current_week.strftime('%b %d')} - {week_end.strftime('%b %d, %Y')}")

    def refresh_schedule(self) -> None:
        all_events = self.local_events + self.google_events
        self.schedule.set_week(self.current_week)
        self.schedule.set_events(all_events)
        self.month_calendar.set_month(self.current_month)
        self.month_calendar.set_events(all_events)
        self.refresh_title()

    def set_week(self, week_start_value: date) -> None:
        self.current_week = week_start_value
        self.current_month = date(week_start_value.year, week_start_value.month, 1)
        self.refresh_schedule()
        if self.google_client.is_connected():
            self.sync_google(show_success=False)

    def change_week(self, delta_weeks: int) -> None:
        self.set_week(self.current_week + timedelta(days=delta_weeks * 7))

    def set_today(self) -> None:
        if self.current_view == VIEW_MONTH:
            self.set_month(date.today().replace(day=1))
        else:
            self.set_week(start_of_week())

    def change_period(self, delta: int) -> None:
        if self.current_view == VIEW_MONTH:
            self.set_month(self.shift_month(self.current_month, delta))
        else:
            self.change_week(delta)

    def set_month(self, month_start_value: date) -> None:
        self.current_month = date(month_start_value.year, month_start_value.month, 1)
        self.current_week = start_of_week(self.current_month)
        self.refresh_schedule()
        if self.google_client.is_connected():
            self.sync_google(show_success=False)

    @staticmethod
    def shift_month(month_start_value: date, delta_months: int) -> date:
        month_index = month_start_value.month - 1 + delta_months
        year = month_start_value.year + month_index // 12
        month = month_index % 12 + 1
        _weekday, days_in_month = calendar.monthrange(year, month)
        return date(year, month, min(month_start_value.day, days_in_month))

    def create_event_from_task(self, task: TaskItem, initial_day: date | None = None, initial_hour: int | None = None, initial_minute: int = 0) -> None:
        if initial_day is None:
            initial_day = date.today()
        if initial_hour is None:
            initial_hour = datetime.now().hour
        event = self.new_event_dialog(initial_day, initial_hour, initial_minute = initial_minute, eventTitle = task.title)
        if event is not None:
            event.linkedTaskID = task.task_id

    def handle_task_drop_to_schedule(self, task: TaskItem, screen_pos: wx.Point) -> None:
        if not self.schedule.IsShown():
            return

        schedule_pos = self.schedule.ScreenToClient(screen_pos)
        if not self.schedule.GetClientRect().Contains(schedule_pos):
            return

        unscrolled_pos = self.schedule.CalcUnscrolledPosition(schedule_pos)
        day_index = self.schedule.day_index_from_x(unscrolled_pos.x)
        minutes = self.schedule.minutes_from_y(unscrolled_pos.y)
        hour = min(23, max(0, minutes // 60))
        accurate_minute = min(59, max(0, minutes % 60))
        approximate_minute = accurate_minute - (accurate_minute % 15)
        target_day = self.schedule.week_start + timedelta(days=day_index)
        self.create_event_from_task(task, target_day, hour, approximate_minute)

    def new_event_dialog(self, initial_day: date, initial_hour: int, initial_minute: int = 0, eventTitle: str = "New Event") -> None | ScheduleEvent:
        dialog = EventDialog(
            self,
            title="Create New Event",
            initial_day=initial_day,
            initial_hour=initial_hour,
            initial_minute=initial_minute,
            google_enabled=self.google_client.is_connected(),
            event_title=eventTitle
        )
        try:
            if dialog.ShowModal() != wx.ID_OK:
                return None
            try:
                event, add_to_google = dialog.get_event()
            except ValueError as exc:
                wx.MessageBox(str(exc), "Event needs a fix", wx.OK | wx.ICON_WARNING)
                return None

            if add_to_google:
                try:
                    created = self.google_client.create_event(event)
                    self.google_events.append(created)
                except Exception as exc:
                    wx.MessageBox(str(exc), "Google Calendar error", wx.OK | wx.ICON_ERROR)
                    return None
            else:
                self.local_events.append(event)
            self.save()
            self.refresh_schedule()
            return event
        finally:
            dialog.Destroy()

    def open_existing_event_dialog(self, selected_event: ScheduleEvent) -> None:
        dialog = EventDialog(
            self,
            "Edit event",
            initial_day=selected_event.start.date(),
            initial_hour=selected_event.start.hour,
            google_enabled=self.google_client.is_connected(),
            event=selected_event,
        )
        try:
            if dialog.ShowModal() != wx.ID_OK:
                return
            try:
                edited_event, _add_to_google = dialog.get_event()
            except ValueError as exc:
                wx.MessageBox(str(exc), "Event needs a fix", wx.OK | wx.ICON_WARNING)
                return

            if selected_event.source == "google":
                try:
                    edited_event.source = "google"
                    self.google_client.update_event(edited_event)
                    self.replace_event(self.google_events, edited_event)
                except Exception as exc:
                    wx.MessageBox(str(exc), "Google Calendar error", wx.OK | wx.ICON_ERROR)
                    return
            else:
                edited_event.source = "local"
                self.replace_event(self.local_events, edited_event)

            self.save()
            self.refresh_schedule()
        finally:
            dialog.Destroy()

    @staticmethod
    def replace_event(events: list[ScheduleEvent], edited_event: ScheduleEvent) -> None:
        for index, event in enumerate(events):
            if event.event_id == edited_event.event_id:
                events[index] = edited_event
                return

    def handle_event_drag_changed(
        self,
        selected_event: ScheduleEvent,
        _original_start: datetime,
        _original_end: datetime,
    ) -> bool:
        if selected_event.source == "google":
            try:
                self.google_client.update_event(selected_event)
            except Exception as exc:
                wx.MessageBox(str(exc), "Google Calendar error", wx.OK | wx.ICON_ERROR)
                return False
        else:
            selected_event.source = "local"

        self.save()
        self.refresh_schedule()
        return True

    def delete_event(self, selected_event: ScheduleEvent) -> None:
        response = wx.MessageBox(
            f"Delete '{selected_event.title}'?",
            "Delete event",
            wx.YES_NO | wx.NO_DEFAULT | wx.ICON_WARNING,
            self,
        )
        if response != wx.YES:
            return

        if selected_event.source == "google":
            try:
                self.google_client.delete_event(selected_event)
            except Exception as exc:
                wx.MessageBox(str(exc), "Google Calendar error", wx.OK | wx.ICON_ERROR)
                return
            self.google_events = [
                event for event in self.google_events if event.event_id != selected_event.event_id
            ]
        else:
            self.local_events = [
                event for event in self.local_events if event.event_id != selected_event.event_id
            ]

        self.save()
        self.refresh_schedule()

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
