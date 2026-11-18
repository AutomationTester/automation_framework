"""
BaseWindow - parent class for all window objects (the desktop version of the Page Object Model).

Each application window gets its own class (CalculatorPage, NotepadPage ...) that inherits from
BaseWindow. Tests talk only to those classes - never to pywinauto directly - so when the UI changes
only one class has to be fixed.
"""
from pywinauto import Desktop

from core.logger import get_logger
from core.waits import wait_until
from utils.screenshot import take_screenshot


class BaseWindow:
    def __init__(self, config):
        self.config = config
        self.app_timeout = config["timeouts"]["app_start"]
        self.element_timeout = config["timeouts"]["element"]
        self.log = get_logger(f"pages.{type(self).__name__}")
        self.desktop = Desktop(backend="uia")
        self.window = None

    # ---------- window level ----------
    def connect(self, **criteria):
        """Attach to a top-level window, e.g. connect(title="Calculator"), and wait until it is visible."""
        self.log.info("Waiting for window %s", criteria)
        self.window = self.desktop.window(**criteria)
        self.window.wait("visible", timeout=self.app_timeout)
        return self

    def is_open(self):
        return self.window is not None and self.window.exists(timeout=0)

    def title(self):
        return self.window.window_text()

    def focus(self):
        self.window.set_focus()

    def press_keys(self, keys):
        """Send a keyboard shortcut to the window, e.g. '^s' (Ctrl+S). Syntax: pywinauto type_keys."""
        self.log.debug("Keys %s", keys)
        self.window.type_keys(keys)

    # ---------- control level ----------
    def find(self, **criteria):
        """Return a control inside the window, waiting until it exists. Prefer auto_id over title/index."""
        control = self.window.child_window(**criteria)
        control.wait("exists", timeout=self.element_timeout)
        return control

    def click(self, **criteria):
        """Click a control. invoke() uses UI Automation (no mouse needed); fall back to a real mouse click."""
        control = self.find(**criteria)
        self.log.debug("Click %s", criteria)
        try:
            control.invoke()
        except Exception:
            control.click_input()

    def read_text(self, **criteria):
        return self.find(**criteria).window_text()

    def wait_for_text(self, expected, timeout=None, **criteria):
        """Wait until the control's text contains `expected` (synchronization instead of sleep)."""
        return wait_until(lambda: expected in self.read_text(**criteria),
                          timeout=timeout or self.element_timeout,
                          message=f"text '{expected}' in {criteria}")

    def screenshot(self, name):
        return take_screenshot(name)
