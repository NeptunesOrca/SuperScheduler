import uuid
import wx

from conditional_panel import ConditionalPanel
from date_entry_ctrl import DateEntryCtrl

from time_management import *
from reccurance import Reccurrance
from schedule_event import ScheduleEvent
from task_item import TaskItem

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
        self.date_input = DateEntryCtrl(panel)
        selected_day = event.start.date() if event else initial_day
        selected_hour = event.start.hour if event else initial_hour
        selected_minute = event.start.minute if event else initial_minute
        end_hour = event.end.hour if event else min(initial_hour + 1, 23)
        end_minute = event.end.minute if event else initial_minute
        linked_task_id = str(event.linkedTaskID) if (event and event.linkedTaskID is not None) else "None"
        # display for linked task id (read-only)
        linked_task_label = wx.StaticText(panel, label=linked_task_id)
        self.date_input.SetValue(selected_day)
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

        event_date = self.date_input.GetValue()
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
            self.start_date_input = DateEntryCtrl(panel, initial_start.date())
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

        start_date = self.start_date_input.GetValue()
        start_time = parse_time_text(self.start_time_input.GetValue())
        start_dt = datetime.combine(start_date, start_time).replace(tzinfo=local_tz())
        duration = timedelta(hours=self.duration_hours.GetValue(), minutes=self.duration_minutes.GetValue())
        if duration <= timedelta(0):
            raise ValueError("Duration must be greater than zero.")

        return Reccurrance(start_dt, duration)


def format_recurrence_summary(reccurance: Reccurrance | None) -> str:
    """Format a recurrence object as a human-readable summary."""
    if not reccurance:
        return "No recurrence"
    
    start_str = reccurance.start.strftime("%b %d, %Y at %H:%M")
    end_str = reccurance.end.strftime("%b %d, %Y at %H:%M")
    duration_hours = reccurance.duration.total_seconds() / 3600
    
    if duration_hours == int(duration_hours):
        duration_str = f"{int(duration_hours)} hour{'s' if duration_hours != 1 else ''}"
    else:
        minutes = int((duration_hours % 1) * 60)
        hours = int(duration_hours)
        duration_str = f"{hours}h {minutes}m"
    
    return f"{start_str} to {end_str} ({duration_str} duration)"


class TaskDialog(wx.Dialog):
    def __init__(
        self,
        parent: wx.Window,
        title: str,
        task: TaskItem,
    ):
        super().__init__(parent, title=title, size=(450, 380))
        self.task = task
        self.current_recurrence = task.reccurance

        panel = wx.Panel(self)
        sizer = wx.BoxSizer(wx.VERTICAL)
        form = wx.FlexGridSizer(rows=0, cols=2, vgap=10, hgap=12)
        form.AddGrowableCol(1, 1)

        # Title
        self.title_input = wx.TextCtrl(panel)
        if task:
            self.title_input.SetValue(task.title)

        # Priority
        self.priority_input = wx.SpinCtrl(panel, min=0, max=10, initial=task.priority if task else 0)

        # Due Date
        self.due_date_input = DateEntryCtrl(panel)
        if task and task.due:
            self.due_date_input.SetValue(task.due.date())
        else:
            # Default to today
            self.due_date_input.SetValue(date.today())

        # Due Date Panel
        hasDueDate = bool(task.due is not None)
        init_due_date = None
        if hasDueDate:
            init_due_date = task.due.date()
        self.due_date_panel = wx.BoxSizer()
        self.due_date_input = DateEntryCtrl(panel, init_due_date)
        button_panel = wx.Panel(panel)
        self.add_due_date_button = wx.Button(button_panel, label="Add Due Date")
        self.due_date_conditional_panel = ConditionalPanel(panel, button_panel, self.due_date_input)
        self.delete_due_date_button = wx.Button(panel, label="Remove Due Date")
        self.delete_due_date_button.Enable(hasDueDate)

        self.due_date_panel.Add(self.due_date_conditional_panel)
        self.due_date_panel.Add(self.delete_due_date_button)

        self.add_due_date_button.Bind(wx.EVT_BUTTON, self.on_add_due_date)
        self.delete_due_date_button.Bind(wx.EVT_BUTTON, self.on_remove_due_date)

        # Add rows to form
        rows = [
            ("Title", self.title_input),
            ("Priority (0-10)", self.priority_input),
            ("Due Date", self.due_date_panel),
        ]

        for label, control in rows:
            if label:
                form.Add(wx.StaticText(panel, label=label), 0, wx.ALIGN_CENTER_VERTICAL)
            else:
                form.Add(wx.StaticText(panel, label=""), 0)
            form.Add(control, 1, wx.EXPAND)

        # Recurrence section
        recurrence_label = wx.StaticText(panel, label="Recurrence")
        recurrence_label_font = recurrence_label.GetFont()
        recurrence_label_font.MakeBold()
        recurrence_label.SetFont(recurrence_label_font)

        # Recurrence summary display
        self.recurrence_summary = wx.StaticText(
            panel,
            label=format_recurrence_summary(self.current_recurrence),
            style=wx.ALIGN_LEFT
        )
        summary_font = self.recurrence_summary.GetFont()
        summary_font.MakeItalic()
        self.recurrence_summary.SetFont(summary_font)

        # Recurrence buttons sizer
        recurrence_buttons_sizer = wx.BoxSizer(wx.HORIZONTAL)
        self.edit_recurrence_button = wx.Button(panel, label="Edit/Add Recurrence")
        self.delete_recurrence_button = wx.Button(panel, label="Delete Recurrence")
        self.delete_recurrence_button.Enable(self.current_recurrence is not None)

        self.edit_recurrence_button.Bind(wx.EVT_BUTTON, self.on_edit_recurrence)
        self.delete_recurrence_button.Bind(wx.EVT_BUTTON, self.on_delete_recurrence)

        recurrence_buttons_sizer.Add(self.edit_recurrence_button, 1, wx.EXPAND | wx.RIGHT, 8)
        recurrence_buttons_sizer.Add(self.delete_recurrence_button, 1, wx.EXPAND)

        # OK and Cancel buttons
        buttons = wx.StdDialogButtonSizer()
        ok_button = wx.Button(panel, wx.ID_OK)
        cancel_button = wx.Button(panel, wx.ID_CANCEL)
        buttons.AddButton(ok_button)
        buttons.AddButton(cancel_button)
        buttons.Realize()

        # Assemble main sizer
        sizer.Add(form, 0, wx.ALL | wx.EXPAND, 16)
        sizer.Add(recurrence_label, 0, wx.LEFT | wx.RIGHT | wx.TOP, 16)
        sizer.Add(self.recurrence_summary, 0, wx.LEFT | wx.RIGHT, 16)
        sizer.Add(recurrence_buttons_sizer, 0, wx.LEFT | wx.RIGHT | wx.TOP, 16)
        sizer.Add(buttons, 0, wx.ALL | wx.EXPAND, 12)

        panel.SetSizer(sizer)

    def on_add_due_date(self, event : wx.CommandEvent) -> None:
        self.task.due = datetime.today()
        self.due_date_conditional_panel.set(False)
        self.delete_due_date_button.Enable()

    def on_remove_due_date(self, event: wx.CommandEvent) -> None:
        self.task.due = None
        self.delete_due_date_button.Disable()
        self.due_date_conditional_panel.set(True)

    def on_edit_recurrence(self, event: wx.Event) -> None:
        dialog = ReoccurranceDialog(self, "Edit Task Recurrence", self.current_recurrence, allowStartChange=True)
        try:
            if dialog.ShowModal() != wx.ID_OK:
                return
            try:
                self.current_recurrence = dialog.get_reccurance()
                self.recurrence_summary.SetLabel(format_recurrence_summary(self.current_recurrence))
                self.delete_recurrence_button.Enable(self.current_recurrence is not None)
            except ValueError as exc:
                wx.MessageBox(str(exc), "Recurrence needs a fix", wx.OK | wx.ICON_WARNING)
        finally:
            dialog.Destroy()

    def on_delete_recurrence(self, event: wx.Event) -> None:
        self.current_recurrence = None
        self.recurrence_summary.SetLabel(format_recurrence_summary(None))
        self.delete_recurrence_button.Enable(False)

    def get_task(self) -> TaskItem:
        """Get the edited task."""
        title = self.title_input.GetValue().strip()
        if not title:
            raise ValueError("Title is required.")

        priority = self.priority_input.GetValue()

        due = None
        if self.has_due_date_checkbox.IsChecked():
            due_date = self.due_date_input.GetValue()
            due = datetime.combine(due_date, datetime.min.time()).replace(tzinfo=local_tz())

        task_id = self.task.task_id if self.task else str(uuid.uuid4())
        done = self.task.done if self.task else False

        return TaskItem(
            task_id=task_id,
            title=title,
            done=done,
            due=due,
            priority=priority,
            reccurance=self.current_recurrence,
        )


