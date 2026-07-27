import uuid
import wx

from conditional_panel import ConditionalPanel
from datetime_panels import DateEntryCtrl, DurationSelector

from time_management import *
from recurrence import Recurrence
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
        super().__init__(parent, title=title, size=(420, 330)) #type:ignore
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
        self.description_input = wx.TextCtrl(panel, style=wx.TE_MULTILINE, size=(-1, 70)) #type:ignore
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

def format_recurrence_summary(recurrence: Recurrence | None) -> str:
    """Format a recurrence object as a human-readable summary."""
    if not recurrence:
        return "No recurrence"
    
    start_str = recurrence.start.strftime("%b %d, %Y at %H:%M")
    end_str = recurrence.end.strftime("%b %d, %Y at %H:%M")
    duration_hours = recurrence.duration.total_seconds() / 3600
    
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
        super().__init__(parent, title=title, size=(450, 380)) #type:ignore
        self.task = task
        self.current_recurrence = task.recurrence

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
        if task.due:
            self.due_date_input.SetValue(task.due.date())
        else:
            # Default to today
            self.due_date_input.SetValue(date.today())

        # Due Date Panel
        due_date_buttons = wx.Panel(panel)
        due_buttons_sizer = wx.BoxSizer(wx.HORIZONTAL)
        self.add_due_date_button = wx.Button(due_date_buttons, label="Add Due Date")
        #self.due_date_conditional_panel = ConditionalPanel(panel, due_date_buttons, self.due_date_input)
        self.delete_due_date_button = wx.Button(due_date_buttons, label="Remove Due Date")

        due_buttons_sizer.Add(self.add_due_date_button, 0, wx.ALIGN_CENTER_VERTICAL, 5)
        due_buttons_sizer.Add(self.delete_due_date_button, 0, wx.ALIGN_CENTER_VERTICAL, 5)
        due_date_buttons.SetSizer(due_buttons_sizer)

        #self.due_date_conditional_panel.set(not hasDueDate)
        hasDueDate = bool(task.due is not None)
        self.add_due_date_button.Enable(not hasDueDate)
        self.delete_due_date_button.Enable(hasDueDate)
        self.due_date_input.Enable(hasDueDate)

        self.add_due_date_button.Bind(wx.EVT_BUTTON, self.on_add_due_date)
        self.delete_due_date_button.Bind(wx.EVT_BUTTON, self.on_remove_due_date)

        # Recurrence Panels
        recur_button_panel = wx.Panel(panel)
        recur_button_panel_sizer = wx.BoxSizer(wx.HORIZONTAL)
        self.add_recurrence_button = wx.Button(recur_button_panel, label="Add Recurrence")
        self.delete_recurrence_button = wx.Button(recur_button_panel, label="Remove Recurrence")
        self.recurrence_duration = DurationSelector(panel, prefix_text="Every")

        hasRecurrence = bool(self.task.recurrence is not None)
        self.add_recurrence_button.Enable(not hasRecurrence)
        self.delete_recurrence_button.Enable(hasRecurrence)
        self.recurrence_duration.Enable(hasRecurrence)

        recur_button_panel_sizer.Add(self.add_recurrence_button, 0, wx.ALIGN_CENTER_VERTICAL,5)
        recur_button_panel_sizer.Add(self.delete_recurrence_button, 0, wx.ALIGN_CENTER_VERTICAL,5)
        recur_button_panel.SetSizer(recur_button_panel_sizer)
        
        self.add_recurrence_button.Bind(wx.EVT_BUTTON, self.on_add_reccurrence)
        self.delete_recurrence_button.Bind(wx.EVT_BUTTON, self.on_delete_recurrence)

        # Add rows to form
        rows = [
            ("Title", self.title_input),
            ("Priority (0-10)", self.priority_input),
            ("Due Date", due_date_buttons),
            ("", self.due_date_input),
            ("Reccurence", recur_button_panel),
            ("", self.recurrence_duration)
        ]

        for label, control in rows:
            if label:
                form.Add(wx.StaticText(panel, label=label), 0, wx.ALIGN_CENTER_VERTICAL)
                #print(label) # can uncomment for testing
            else:
                form.Add(wx.StaticText(panel, label=""), 0, wx.ALIGN_CENTER_VERTICAL)
            form.Add(control, 1, wx.EXPAND | wx.ALIGN_CENTER_VERTICAL)

        # OK and Cancel buttons
        buttons = wx.StdDialogButtonSizer()
        ok_button = wx.Button(panel, wx.ID_OK)
        cancel_button = wx.Button(panel, wx.ID_CANCEL)
        buttons.AddButton(ok_button)
        buttons.AddButton(cancel_button)
        buttons.Realize()

        # Assemble main sizer
        sizer.Add(form, 0, wx.ALL | wx.EXPAND, 16)
        sizer.Add(buttons, 0, wx.ALL | wx.EXPAND, 12)
        panel.SetSizer(sizer)

    def on_add_due_date(self, event : wx.CommandEvent) -> None:
        self.task.due = datetime.today()
        self.add_due_date_button.Disable()
        self.due_date_input.Enable()
        self.delete_due_date_button.Enable()

    def on_remove_due_date(self, event: wx.CommandEvent) -> None:
        self.task.due = None
        self.add_due_date_button.Enable()
        self.due_date_input.Disable()
        self.delete_due_date_button.Disable()

    def on_add_reccurrence(self, event : wx.CommandEvent) -> None:
        # Create recurrence, using due date if it exists and creation date if not
        recurrdate = self.task.due
        recurrAtEnd = True
        if not recurrdate:
            recurrAtEnd = False
            recurrdate = self.task.created
        self.task.recurrence = Recurrence(recurrdate, self.recurrence_duration.GetTimedelta(), useDateAsStart=not recurrAtEnd)

        # Disable add, enable edit and delete UI
        self.add_recurrence_button.Disable()
        self.recurrence_duration.Enable()
        self.delete_recurrence_button.Enable()
    '''
    def on_edit_recurrence(self, event: wx.Event) -> None:
        dialog = ReoccurranceDialog(self, "Edit Task Recurrence", self.current_recurrence, allowStartChange=True)
        try:
            if dialog.ShowModal() != wx.ID_OK:
                return
            try:
                self.current_recurrence = dialog.get_recurrence()
                self.recurrence_summary.SetLabel(format_recurrence_summary(self.current_recurrence))
                self.delete_recurrence_button.Enable(self.current_recurrence is not None)
            except ValueError as exc:
                wx.MessageBox(str(exc), "Recurrence needs a fix", wx.OK | wx.ICON_WARNING)
        finally:
            dialog.Destroy()
    '''

    def on_delete_recurrence(self, event: wx.Event) -> None:
        # Remove recurrence
        self.task.recurrence = None
        
        # Enable add, disable delete and duration UI
        self.add_recurrence_button.Enable()
        self.delete_recurrence_button.Disable()
        self.recurrence_duration.Disable()

    def get_task(self) -> TaskItem:
        """Get the edited task."""
        title = self.title_input.GetValue().strip()
        if not title:
            raise ValueError("Title is required.")

        self.task.priority = self.priority_input.GetValue()

        due = None
        if self.task.due:
            due_date = self.due_date_input.GetValue()
            due = datetime.combine(due_date, datetime.min.time()).replace(tzinfo=local_tz())
            self.task.due = due

        return self.task


