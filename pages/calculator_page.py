"""Window object for Windows 11 Calculator (a UWP / WinUI app - automated with the 'uia' backend)."""
import subprocess

from core.base_window import BaseWindow
from core.reporting import attach_text, step, step_method
from core.waits import wait_until

# Locators live in ONE place. auto_ids were found with Accessibility Insights / print_control_identifiers().
DIGIT_BUTTONS = {str(d): f"num{d}Button" for d in range(10)}
OPERATOR_BUTTONS = {
    "+": "plusButton",
    "-": "minusButton",
    "*": "multiplyButton",
    "/": "divideButton",
}
DECIMAL_BUTTON = "decimalSeparatorButton"
NEGATE_BUTTON = "negateButton"
EQUALS_BUTTON = "equalButton"
CLEAR_BUTTON = "clearButton"
RESULT_TEXT = "CalculatorResults"


class CalculatorPage(BaseWindow):
    @step_method("Open Calculator")
    def open(self):
        settings = self.config["calculator"]
        self.log.info("Launching Calculator")
        # calc.exe is only a launcher that exits at once, so we connect by window title
        # instead of keeping a handle to the process. Every launch opens ANOTHER window,
        # so reuse one that is already open - two windows would make the locator ambiguous.
        if not self.desktop.window(title=settings["window_title"]).exists(timeout=1):
            subprocess.Popen(settings["launch_cmd"])
        self.connect(title=settings["window_title"])
        self.clear()
        return self

    def clear(self):
        self.click(auto_id=CLEAR_BUTTON, control_type="Button")

    def enter_number(self, number):
        text = str(number)
        negative = text.startswith("-")
        for ch in text.lstrip("-"):
            auto_id = DECIMAL_BUTTON if ch == "." else DIGIT_BUTTONS[ch]
            self.click(auto_id=auto_id, control_type="Button")
        if negative:
            self.click(auto_id=NEGATE_BUTTON, control_type="Button")

    def press_operator(self, operator):
        if operator not in OPERATOR_BUTTONS:
            raise ValueError(f"Unsupported operator '{operator}'. Use one of {list(OPERATOR_BUTTONS)}")
        self.click(auto_id=OPERATOR_BUTTONS[operator], control_type="Button")

    def press_equals(self):
        self.click(auto_id=EQUALS_BUTTON, control_type="Button")

    def display_text(self):
        """Raw display, e.g. 'Display is 1,234.5' or 'Cannot divide by zero'."""
        return self.read_text(auto_id=RESULT_TEXT)

    @property
    def result(self):
        """Displayed value as a float. Raises ValueError for messages like 'Cannot divide by zero'."""
        text = self.display_text().replace("Display is", "").replace(",", "").strip()
        return float(text)

    def calculate(self, a, operator, b):
        """Full flow: clear, a, operator, b, '=' - returns the displayed result."""
        with step(f"Calculate {a} {operator} {b}"):
            self.log.info("Calculate %s %s %s", a, operator, b)
            with step("Clear the display"):
                self.clear()
                wait_until(lambda: self.display_text().endswith(" 0"), timeout=self.element_timeout,
                           message="display to reset to 0")
            with step(f"Enter {a}, press '{operator}', enter {b}, press '='"):
                self.enter_number(a)
                self.press_operator(operator)
                self.enter_number(b)
                self.press_equals()
            with step("Read the result"):
                value = self.result
                attach_text(self.display_text(), "Calculator display")
            self.log.info("Result = %s", value)
            return value

    @step_method("Close Calculator")
    def close(self):
        if self.is_open():
            self.log.info("Closing Calculator")
            self.window.close()
