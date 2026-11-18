"""
Window object for Microsoft Excel - automated through COM (pywin32), the standard way to drive Office.

Why COM and not clicking cells with pywinauto?
  * Excel's grid is not made of normal UI controls - clicking cell B3 by coordinates is fragile.
  * COM talks to Excel's own object model (Application > Workbook > Worksheet > Range): fast and exact.
  * We still check the real Excel WINDOW once (win32gui), to prove the UI really appeared (hybrid approach).

REAL-WORLD SAFETY RULE (same idea as Notepad):
  DispatchEx() starts a NEW, separate Excel process. The user's own open workbooks live in a different
  Excel instance and are never touched. quit() closes only our instance.
"""
import os
from pathlib import Path

from core.logger import get_logger
from core.reporting import attach_text, step_method
from core.waits import wait_until

XL_OPEN_XML_WORKBOOK = 51  # FileFormat code for .xlsx


class ExcelPage:
    def __init__(self, config):
        self.config = config
        self.visible = config["excel"]["visible"]
        self.timeout = config["timeouts"]["app_start"]
        self.log = get_logger("pages.ExcelPage")
        self.app = None
        self.pid = None
        self.workbook = None
        self.sheet = None

    # ---------- application ----------
    @step_method("Start a separate Excel instance")
    def open(self):
        import win32com.client  # Windows-only imports, done lazily
        import win32process

        self.log.info("Starting a new Excel instance (visible=%s)", self.visible)
        self.app = win32com.client.DispatchEx("Excel.Application")
        self.app.Visible = self.visible
        self.app.DisplayAlerts = False        # no "Save changes?" pop-ups can block the run
        # Remember OUR process id: if a normal quit fails, we stop exactly this process - nothing else.
        self.pid = win32process.GetWindowThreadProcessId(self.app.Hwnd)[1]
        self.log.info("Excel version %s started (pid %s)", self.app.Version, self.pid)
        return self

    @step_method("Create a new workbook")
    def new_workbook(self):
        self.workbook = self.app.Workbooks.Add()
        self.sheet = self.workbook.Worksheets(1)
        self.log.info("New workbook: %s", self.workbook.Name)
        if self.visible:
            self._verify_window_visible()
            if not (os.environ.get("CI") or os.environ.get("JENKINS_URL")):
                self._bring_to_foreground()
        return self

    def _bring_to_foreground(self):
        import pywintypes
        import win32con
        import win32gui

        hwnd = self.app.Hwnd
        try:
            if win32gui.IsIconic(hwnd):
                win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
            if win32gui.GetForegroundWindow() != hwnd:
                win32gui.SetForegroundWindow(hwnd)
        except pywintypes.error as error:
            self.log.warning("Could not bring Excel to the foreground: %s", error)
            return
        if win32gui.GetForegroundWindow() != hwnd:
            self.log.warning("Windows did not bring Excel to the foreground")

    def _verify_window_visible(self):
        """
        UI-level check: OUR Excel window is really on screen and shows OUR workbook.

        Uses win32gui (pywin32) on the window handle Excel reports. Note: do NOT import pywinauto in the
        same process as win32com Office objects - pywinauto switches COM to a different threading mode
        and the Excel object then fails with "Object is not connected to server".
        """
        import win32gui

        hwnd = self.app.Hwnd
        title = self.workbook.Name
        wait_until(lambda: win32gui.IsWindowVisible(hwnd) and title in win32gui.GetWindowText(hwnd),
                   timeout=self.timeout, message=f"Excel window showing '{title}'")
        self.log.info("Excel window is visible: %r", win32gui.GetWindowText(hwnd))

    # ---------- cells ----------
    def write(self, cell, value):
        self.sheet.Range(cell).Value = value

    def write_formula(self, cell, formula):
        self.sheet.Range(cell).Formula = formula

    def read(self, cell):
        return self.sheet.Range(cell).Value

    def read_text(self, cell):
        """What the user SEES in the cell (e.g. '#DIV/0!' or '1,234.50')."""
        return self.sheet.Range(cell).Text

    @step_method("Write a row of values")
    def write_row(self, row, values, start_col="A"):
        for offset, value in enumerate(values):
            self.write(f"{chr(ord(start_col) + offset)}{row}", value)

    @step_method("Calculate with an Excel formula")
    def calculate(self, a, operator, b):
        """Put a and b in A1/B1, the formula =A1<op>B1 in C1, and return Excel's result."""
        self.write("A1", float(a))
        self.write("B1", float(b))
        self.write_formula("C1", f"=A1{operator}B1")
        value = self.read("C1")
        attach_text(f"A1={a}  B1={b}  C1: =A1{operator}B1  ->  {self.read_text('C1')}", "Excel cells")
        self.log.info("Excel: %s %s %s = %s", a, operator, b, value)
        return value

    # ---------- files ----------
    @step_method("Save the workbook as .xlsx")
    def save_as(self, path):
        path = Path(path).resolve()
        self.workbook.SaveAs(str(path), FileFormat=XL_OPEN_XML_WORKBOOK)
        wait_until(path.exists, timeout=self.timeout, message=f"{path.name} to be written")
        self.log.info("Saved %s", path)
        return path

    @step_method("Re-open the saved file and read a cell")
    def read_saved_value(self, path, cell):
        """
        Proof that the data was really saved: close our workbook, open the FILE again (read-only), read the cell.
        (After SaveAs our open workbook IS that file - opening it again would just return the same workbook.)
        """
        path = Path(path).resolve()
        if self.workbook is not None and Path(self.workbook.FullName).resolve() == path:
            self.close_workbook()
        workbook = self.app.Workbooks.Open(str(path), ReadOnly=True)
        try:
            return workbook.Worksheets(1).Range(cell).Value
        finally:
            workbook.Close(SaveChanges=False)

    @step_method("Close our workbook")
    def close_workbook(self):
        if self.workbook is not None:
            self.workbook.Close(SaveChanges=False)
            self.workbook = self.sheet = None

    @step_method("Quit our Excel instance")
    def quit(self):
        if self.app is None:
            return
        try:
            for workbook in list(self.app.Workbooks):   # only workbooks of OUR instance
                workbook.Close(SaveChanges=False)
            self.app.Quit()
            self.log.info("Excel instance closed")
        except Exception as error:
            # Failure recovery: never leave a hidden EXCEL.EXE behind - stop only the process WE started.
            self.log.warning("Normal Excel quit failed (%s) - stopping our process %s", error, self.pid)
            self._terminate_own_process()
        finally:
            self.app = None   # drop the COM reference so the EXCEL.EXE process can exit

    def _terminate_own_process(self):
        import win32api
        import win32con

        try:
            handle = win32api.OpenProcess(win32con.PROCESS_TERMINATE, False, self.pid)
            win32api.TerminateProcess(handle, 1)
            win32api.CloseHandle(handle)
        except Exception as error:
            self.log.error("Could not stop Excel process %s: %s", self.pid, error)
