import wx

class ConditionalPanel(wx.Panel):
    def __init__(self, parent, a_panel : wx.Panel | None = None, b_panel : wx.Panel | None = None, orientation : int = wx.HORIZONTAL):
        super().__init__(parent)

        # Panel internal features
        self._panel_a : wx.Panel = wx.Panel(self)
        self._panel_b : wx.Panel = wx.Panel(self)
        self._show_A = True  # internal boolean state
        self.sizer = wx.BoxSizer(orientation)

        # Create/attach panels
        if a_panel is None:
            self._make_panel(True)
        else:
            self.SetPanelA(a_panel)
        if b_panel is None:
            self._make_panel(False)
        else:
            self.SetPanelB(b_panel)

        self.SetSizer(self.sizer)
        self._update_visibility()

    def SetPanelA(self, new_panel):
        self.SetPanel(new_panel, True)
    
    def SetPanelB(self, new_panel):
        self.SetPanel(new_panel, False)

    def SetPanel(self, new_panel, setA : bool):
        if new_panel.GetParent() is not self:
            new_panel.Reparent(self)
        
        if setA:
            self.sizer.Detach(self._panel_a)
            self._panel_a = new_panel
            self.sizer.Add(self._panel_a, 1, wx.EXPAND | wx.ALL, 5)
        else:
            self.sizer.Detach(self._panel_b)
            self._panel_b = new_panel
            self.sizer.Add(self._panel_b, 1, wx.EXPAND | wx.ALL, 5)

    def _make_panel(self, makeA:bool):
        p = wx.Panel(self)
        self.SetPanel(p, makeA)

    def _update_visibility(self):
        self._panel_a.Show(self._show_A)
        self._panel_b.Show(not self._show_A)
        self.sizer.Layout()   # re-flow the sizer for the newly shown/hidden panel

    def toggle(self):
        """Flip the internal boolean and refresh which panel is shown."""
        self._show_A = not self._show_A
        self._update_visibility()

    def set_state(self, show_first: bool):
        """Explicitly set which panel should be visible."""
        self._show_A = show_first
        self._update_visibility()