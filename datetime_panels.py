import wx
import wx.adv
import datetime
from time_management import *

class DateEntryCtrl(wx.Panel):
    def __init__(self, parent: wx.Window, value: date | None = None):
        super().__init__(parent)

        self.text_input = wx.TextCtrl(self)
        self.calendar_input = wx.adv.DatePickerCtrl(self, style=wx.adv.DP_DROPDOWN)
        self.text_input.Bind(wx.EVT_TEXT, self.on_text_changed)
        self.calendar_input.Bind(wx.adv.EVT_DATE_CHANGED, self.on_calendar_changed)
        self._set_value(value)

        sizer = wx.BoxSizer(wx.HORIZONTAL)
        sizer.Add(self.text_input, 1, wx.EXPAND | wx.RIGHT, 6)
        sizer.Add(self.calendar_input, 0, wx.EXPAND)
        self.SetSizer(sizer)

    def _set_value(self, value: date | None) -> None:
        if value is None:
            self.text_input.SetValue("")
            today = date.today()
            self.calendar_input.SetValue(wx.DateTime.FromDMY(today.day, today.month - 1, today.year))
            return

        self.text_input.SetValue(value.strftime("%Y-%m-%d"))
        self.calendar_input.SetValue(wx.DateTime.FromDMY(value.day, value.month - 1, value.year))

    def SetValue(self, value: date | None) -> None:
        self._set_value(value)

    def on_text_changed(self, event: wx.CommandEvent) -> None:
        text_value = self.text_input.GetValue().strip()
        if not text_value:
            return
        try:
            parsed_date = parse_date_text(text_value)
        except ValueError:
            return
        self.calendar_input.SetValue(wx.DateTime.FromDMY(parsed_date.day, parsed_date.month - 1, parsed_date.year))

    def on_calendar_changed(self, event: wx.CommandEvent) -> None:
        selected_date = wxdate_to_date(self.calendar_input.GetValue())
        self.text_input.SetValue(selected_date.strftime("%Y-%m-%d"))

    def GetValue(self) -> date:
        text_value = self.text_input.GetValue().strip()
        if text_value:
            return parse_date_text(text_value)
        return wxdate_to_date(self.calendar_input.GetValue())

    def Enable(self, enable: bool = True):
        res = super().Enable(enable)
        self.text_input.Enable(enable)
        self.calendar_input.Enable(enable)
        return res

    def Disable(self):
        return self.Enable(False)


class DurationSelector(wx.Panel):
    UNITS = list(TimeUnits.__members__.keys())

    def __init__(self, parent, default_value=1, default_unit=TimeUnits.DAYS, prefix_text: str = ""):
        super().__init__(parent)

        self.amount = wx.SpinCtrl(self, min=1, max=999999, initial=default_value)
        self.unit_choice = wx.Choice(self, choices=self.UNITS)
        self.prefix = wx.StaticText(self, label= prefix_text)

        unit_index = self.UNITS.index(default_unit.name) if default_unit.name in self.UNITS else 0
        self.unit_choice.SetSelection(unit_index)

        sizer = wx.BoxSizer(wx.HORIZONTAL)
        sizer.Add(self.prefix, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 5)
        sizer.Add(self.amount, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 5)
        sizer.Add(self.unit_choice, 0, wx.ALIGN_CENTER_VERTICAL)
        self.SetSizer(sizer)

    def GetValue(self):
        """Returns (amount, TimeUnits)."""
        units = TimeUnits[self.UNITS[self.unit_choice.GetSelection()]]
        return self.amount.GetValue(), units

    def SetValue(self, amount, unit : TimeUnits):
        self.amount.SetValue(amount)
        if unit.name in self.UNITS:
            self.unit_choice.SetSelection(self.UNITS.index(unit.name))

    def GetApproximateTimedelta(self) -> timedelta:
        """Returns a datetime.timedelta approximation (months treated as 30 days, years treated as 365 days)."""
        amount, unit = self.GetValue()
        if unit == TimeUnits.SECONDS.name:
            return timedelta(seconds=amount)
        elif unit == TimeUnits.MINUTES.name:
            return timedelta(minutes=amount)
        elif unit == TimeUnits.HOURS.name:
            return timedelta(hours=amount)
        elif unit == TimeUnits.DAYS.name:
            return timedelta(days=amount)
        elif unit == TimeUnits.WEEKS.name:
            return timedelta(weeks=amount)
        elif unit == TimeUnits.MONTHS.name:
            return timedelta(days=amount * 30)
        elif unit == TimeUnits.YEARS.name:
            return timedelta(days=amount * 365)
        else:
            return timedelta()