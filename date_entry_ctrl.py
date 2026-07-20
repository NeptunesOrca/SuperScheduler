import wx
import wx.adv
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