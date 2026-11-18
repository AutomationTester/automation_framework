"""
Window object for Windows 11 Notepad.

REAL-WORLD LESSON: Windows 11 Notepad restores the user's previous tabs and opens new files as tabs
in the same window. A test must never type into "whatever Notepad is open" - it could be someone's
real document. So this class only ever works on a file the test created itself, and closes only
that tab (Ctrl+W), never the whole window.
"""
import re
import subprocess
from pathlib import Path

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

    @step_method("Open our own file in Notepad")
    def open_file(self, path):
        """Open an EXISTING file that the test owns (create it first, e.g. in pytest's tmp_path)."""
        self.file_path = Path(path)
        if not self.file_path.exists():
            raise FileNotFoundError(f"Create the file before opening it: {self.file_path}")
        self.log.info("Opening %s in Notepad", self.file_path)
        subprocess.Popen([self.config["notepad"]["launch_cmd"], str(self.file_path)])
        # The title starts with '*' once the file has unsaved changes.
        self.connect(title_re=rf"\*?{re.escape(self.file_path.name)} - Notepad")
        return self

    @property
    def text(self):
        """Current editor content. Notepad uses '\\r' line breaks internally - normalised to '\\n'."""
        return self.read_text(**EDITOR).replace("\r\n", "\n").replace("\r", "\n")

    @step_method("Type text into the editor")
    def type_text(self, text):
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

    @step_method("Close only our tab (Ctrl+W)")
    def close_tab(self):
        """Close only our own tab. Saves first so no 'Do you want to save?' dialog can block the run."""
        if not self.is_open():
            return
        if self.is_modified():
            self.save()
        self.log.info("Closing tab %s", self.file_path.name)
        self.focus()
        self.press_keys("^w")
        wait_until(lambda: not self.is_open(), timeout=self.element_timeout,
                   message="our Notepad tab to close")
