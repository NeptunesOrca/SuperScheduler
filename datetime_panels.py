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

class DurationSelector(wx.Panel):
    UNITS = ["minutes", "hours", "days", "weeks", "months"] # At some point I should probably make this more generalizable or something

    def __init__(self, parent, default_value=1, default_unit="days"):
        super().__init__(parent)

        self.spin = wx.SpinCtrl(self, min=1, max=999999, initial=default_value)
        self.unit_choice = wx.Choice(self, choices=self.UNITS)

        unit_index = self.UNITS.index(default_unit) if default_unit in self.UNITS else 0
        self.unit_choice.SetSelection(unit_index)

        sizer = wx.BoxSizer(wx.HORIZONTAL)
        sizer.Add(self.spin, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 5)
        sizer.Add(self.unit_choice, 0, wx.ALIGN_CENTER_VERTICAL)
        self.SetSizer(sizer)

    def GetValue(self):
        """Returns (amount, unit_string)."""
        return self.spin.GetValue(), self.UNITS[self.unit_choice.GetSelection()]

    def SetValue(self, amount, unit):
        self.spin.SetValue(amount)
        if unit in self.UNITS:
            self.unit_choice.SetSelection(self.UNITS.index(unit))

    def GetTimedelta(self) -> timedelta:
        """Returns a datetime.timedelta approximation (months treated as 30 days)."""
        amount, unit = self.GetValue()
        if unit == "minutes":
            return timedelta(minutes=amount)
        elif unit == "hours":
            return timedelta(hours=amount)
        elif unit == "days":
            return timedelta(days=amount)
        elif unit == "weeks":
            return timedelta(weeks=amount)
        elif unit == "months":
            return timedelta(days=amount * 30)
        else:
            return timedelta()