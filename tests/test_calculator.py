"""Calculator tests: a smoke test plus data-driven tests read from test_data/calculator_data.csv."""
import allure
import pytest

from utils.data_reader import read_csv

CASES = read_csv("calculator_data.csv")

# every test in this file needs the Windows desktop; Allure groups them under Desktop > Calculator
pytestmark = [pytest.mark.desktop, pytest.mark.calculator, allure.epic("Desktop automation"), allure.feature("Calculator")]


@pytest.mark.smoke
@allure.story("Basic arithmetic")
@allure.severity(allure.severity_level.BLOCKER)
@allure.title("Addition 7 + 8 = 15")
def test_addition(calculator):
    assert calculator.calculate(7, "+", 8) == 15


@pytest.mark.regression
@allure.story("Data-driven arithmetic (CSV)")
@allure.severity(allure.severity_level.CRITICAL)
@allure.title("{case[test_id]}: {case[num1]} {case[operator]} {case[num2]} = {case[expected]}")
@pytest.mark.parametrize("case", CASES, ids=[c["test_id"] for c in CASES])
def test_calculator_from_csv(calculator, case):
    result = calculator.calculate(case["num1"], case["operator"], case["num2"])
    assert result == pytest.approx(float(case["expected"])), f"{case['test_id']}: got {result}"


@pytest.mark.regression
@allure.story("Error handling")
@allure.severity(allure.severity_level.NORMAL)
@allure.title("Division by zero shows an error message")
def test_divide_by_zero_shows_message(calculator):
    calculator.clear()
    calculator.enter_number(5)
    calculator.press_operator("/")
    calculator.enter_number(0)
    calculator.press_equals()
    assert "Cannot divide by zero" in calculator.display_text()
    calculator.clear()
