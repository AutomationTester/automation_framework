"""Windows 11 Notepad automation in a dedicated window with a test-owned file."""
import subprocess
from pathlib import Path

import win32gui

from core.base_window import BaseWindow
from core.reporting import attach_text, step_method
from core.waits import wait_until

EDITOR = {"control_type": "Document"}
# Characters that pywinauto type_keys treats as special - they must be wrapped in braces.
_SPECIAL_KEYS = set("+^%~(){}[]")


def _escape_for_type_keys(text):
    escaped = "".join("{" + ch + "}" if ch in _SPECIAL_KEYS else ch for ch in text)
    return escaped.replace("\r\n", "\n").replace("\n", "{ENTER}")


class NotepadPage(BaseWindow):
    def __init__(self, config):
        super().__init__(config)
        self.file_path = None
        self._hwnd = None

    def _notepad_handles(self):
        return {window.handle for window in self.desktop.windows(class_name="Notepad")}

    @staticmethod
    def _tab_names(window):
        return sorted(tab.window_text().removesuffix(". Unmodified.")
                      for tab in window.descendants(control_type="TabItem"))

    def _require_test_tab(self):
        if self.title().removeprefix("*") != f"{self.file_path.name} - Notepad":
            raise RuntimeError("The test file is no longer the active Notepad tab")

    @step_method("Open our own file in Notepad")
    def open_file(self, path):
        """Open an EXISTING file that the test owns (create it first, e.g. in pytest's tmp_path)."""
        self.file_path = Path(path)
        if not self.file_path.exists():
            raise FileNotFoundError(f"Create the file before opening it: {self.file_path}")
        # A file argument can open in a user's existing window. Open a blank window first.
        existing = self._notepad_handles()
        subprocess.Popen([self.config["notepad"]["launch_cmd"]])
        handles = wait_until(lambda: self._notepad_handles() - existing, timeout=self.app_timeout,
                             message="a new Notepad window")
        if len(handles) != 1:
            raise RuntimeError("Cannot identify a dedicated Notepad window")
        hwnd, = handles
        self.connect(handle=hwnd)
        self._hwnd = hwnd
        if self.title() != "Untitled - Notepad" or self._tab_names(self.window) != ["Untitled"]:
            # Notepad restored a previous session (e.g. on a CI agent). Leave those tabs alone and
            # work in a fresh tab of our own.
            self.log.warning("Notepad restored earlier tabs %s; opening a new tab", self._tab_names(self.window))
            self.press_keys("^n")
            wait_until(lambda: self.title() == "Untitled - Notepad", timeout=self.app_timeout,
                       message="a new empty Notepad tab")

        self.log.info("Opening %s in Notepad", self.file_path)
        self.press_keys("^o")
        dialog = self.find(class_name="#32770", control_type="Window")
        dialog.child_window(auto_id="1148", control_type="Edit").set_edit_text(str(self.file_path))
        dialog.child_window(auto_id="1", control_type="Button").click()
        wait_until(lambda: self.title() == f"{self.file_path.name} - Notepad", timeout=self.app_timeout,
                   message="our file to open in the dedicated Notepad window")
        return self

    @property
    def text(self):
        """Current editor content. Notepad uses '\\r' line breaks internally - normalised to '\\n'."""
        return self.read_text(**EDITOR).replace("\r\n", "\n").replace("\r", "\n")

    @step_method("Type text into the editor")
    def type_text(self, text):
        self._require_test_tab()
        editor = self.find(**EDITOR)
        editor.set_focus()
        before = self.text
        self.log.info("Typing %d characters", len(text))
        # A small pause between keys - without it Notepad can drop characters.
        editor.type_keys(_escape_for_type_keys(text), with_spaces=True, pause=0.05)
        wait_until(lambda: self.text == before + text, timeout=self.element_timeout,
                   message="typed text to appear in the editor")

    def is_modified(self):
        return self.title().startswith("*")

    @step_method("Save with Ctrl+S")
    def save(self):
        self._require_test_tab()
        self.log.info("Saving %s", self.file_path.name)
        self.press_keys("^s")
        wait_until(lambda: not self.is_modified(), timeout=self.element_timeout,
                   message="Notepad to finish saving")

    @step_method("Read the saved file from disk")
    def saved_content(self):
        """What is really on disk - the strongest proof that 'save' worked."""
        content = self.file_path.read_text(encoding="utf-8")
        attach_text(content, f"{self.file_path.name} (on disk)")
        return content

    @step_method("Close the test Notepad window")
    def close(self):
        if self._hwnd is None or not win32gui.IsWindow(self._hwnd):
            return
        title = self.title()
        file_title = f"{self.file_path.name} - Notepad"
        if title == f"*{file_title}":
            self.save()
        allowed_tabs = {"Untitled", self.file_path.name}
        tabs = self._tab_names(self.window)
        if not tabs or len(tabs) != len(set(tabs)) or not allowed_tabs.issuperset(tabs):
            # Restored tabs belong to someone else: close only our own tab, keep the window.
            self.log.warning("Notepad window has other tabs; closing only the test tab")
            if self.title().removeprefix("*") == file_title:
                self.press_keys("^w")
            return
        self.log.info("Closing the test Notepad window")
        self.window.close()
        wait_until(lambda: not win32gui.IsWindow(self._hwnd), timeout=self.element_timeout,
                   message="the test Notepad window to close")
