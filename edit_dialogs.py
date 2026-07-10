import uuid
import wx
import wx.adv

from time_management import *
from reccurance import Reccurrance
from schedule_event import ScheduleEvent

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
            if event.isGoogleLinked:
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
                isGoogleLinked=self.event.isGoogleLinked if self.event else False,
                description=self.description_input.GetValue().strip(),
                linkedTaskID=self.event.linkedTaskID if self.event else None,
            ),
            self.google_checkbox.IsChecked() and self.google_enabled,
        )


class ReoccurranceDialog(wx.Dialog):
    def __init__(self, parent: wx.Window, title: str, reccurance: Reccurrance | None = None, allowStartChange = False):
        super().__init__(parent, title=title, size=(380, 280))

        panel = wx.Panel(self)
        sizer = wx.BoxSizer(wx.VERTICAL)
        form = wx.FlexGridSizer(rows=0, cols=2, vgap=10, hgap=12)
        form.AddGrowableCol(1, 1)

        initial_start = reccurance.start if reccurance else datetime.now().replace(minute=0, second=0, microsecond=0)
        initial_duration = reccurance.duration if reccurance else timedelta(hours=1)

        self.enabled_checkbox = wx.CheckBox(panel, label="Enable recurrence")
        self.enabled_checkbox.SetValue(reccurance is not None)
        self.enabled_checkbox.Bind(wx.EVT_CHECKBOX, self.on_toggle_enabled)

        self.start_date_input = None
        self.start_time_input = None
        if allowStartChange:
            self.start_date_input = wx.adv.DatePickerCtrl(panel)
            self.start_date_input.SetValue(wx.DateTime.FromDMY(initial_start.day, initial_start.month - 1, initial_start.year))
            self.start_time_input = wx.TextCtrl(panel, value=initial_start.strftime("%H:%M"))
        else:
            self.start_date_input = wx.StaticText(panel, label=initial_start.strftime("%A %Y-%M-%d"))
            self.start_time_input = wx.StaticText(panel, label=initial_start.strftime("%H:%M"))
        
        self.duration_hours = wx.SpinCtrl(panel, min=0, max=23, initial=initial_duration.seconds // 3600)
        self.duration_minutes = wx.SpinCtrl(panel, min=0, max=59, initial=(initial_duration.seconds % 3600) // 60)

        rows = [
            ("Enabled", self.enabled_checkbox),
            ("Start date", self.start_date_input),
            ("Start time", self.start_time_input),
            ("Duration hours", self.duration_hours),
            ("Duration minutes", self.duration_minutes),
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

        self.set_controls_enabled(reccurance is not None)

    def set_controls_enabled(self, enabled: bool) -> None:
        self.start_date_input.Enable(enabled)
        self.start_time_input.Enable(enabled)
        self.duration_hours.Enable(enabled)
        self.duration_minutes.Enable(enabled)

    def on_toggle_enabled(self, event: wx.CommandEvent) -> None:
        self.set_controls_enabled(self.enabled_checkbox.IsChecked())

    def get_reccurance(self) -> Reccurrance | None:
        if not self.enabled_checkbox.IsChecked():
            return None

        start_date = wxdate_to_date(self.start_date_input.GetValue())
        start_time = parse_time_text(self.start_time_input.GetValue())
        start_dt = datetime.combine(start_date, start_time).replace(tzinfo=local_tz())
        duration = timedelta(hours=self.duration_hours.GetValue(), minutes=self.duration_minutes.GetValue())
        if duration <= timedelta(0):
            raise ValueError("Duration must be greater than zero.")

        return Reccurrance(start_dt, duration)


