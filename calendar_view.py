from __future__ import annotations

import calendar
import uuid
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Callable

import wx

from time_management import local_tz, parse_datetime, start_of_week, wxdate_to_date, parse_time_text
from schedule_event import ScheduleEvent
from task_item import TaskItem
from serialization import AppStorage

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
            #self.on_new_event(selected_day, 9)
            ## currently creates new events, instead want to switch to the day view for that day
            pass

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
