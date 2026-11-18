"""
Excel tests (COM automation). They reuse test_data/calculator_data.csv, so the SAME test data
verifies two different applications: Calculator (UI) and Excel (formulas).
"""
import allure
import pytest

from utils.data_reader import read_csv

CASES = read_csv("calculator_data.csv")

pytestmark = [pytest.mark.desktop, pytest.mark.excel,
              allure.epic("Desktop automation"), allure.feature("Excel")]


@pytest.mark.smoke
@allure.story("Formulas")
@allure.severity(allure.severity_level.BLOCKER)
@allure.title("SUM formula adds a column of numbers")
def test_sum_formula(excel):
    for row, value in enumerate([10, 20, 30], start=1):
        excel.write(f"E{row}", value)
    excel.write_formula("E4", "=SUM(E1:E3)")
    assert excel.read("E4") == 60


@pytest.mark.regression
@allure.story("Data-driven formulas (same CSV as Calculator)")
@allure.severity(allure.severity_level.CRITICAL)
@allure.title("{case[test_id]}: Excel computes {case[num1]} {case[operator]} {case[num2]} = {case[expected]}")
@pytest.mark.parametrize("case", CASES, ids=[c["test_id"] for c in CASES])
def test_formula_from_csv(excel, case):
    result = excel.calculate(case["num1"], case["operator"], case["num2"])
    assert result == pytest.approx(float(case["expected"]))


@pytest.mark.regression
@allure.story("Error handling")
@allure.severity(allure.severity_level.NORMAL)
@allure.title("Division by zero shows #DIV/0!")
def test_divide_by_zero_shows_error(excel):
    excel.write("A1", 5)
    excel.write("B1", 0)
    excel.write_formula("C1", "=A1/B1")
    assert excel.read_text("C1") == "#DIV/0!"


@pytest.mark.regression
@allure.story("Save and re-open")
@allure.severity(allure.severity_level.CRITICAL)
@allure.title("Saved .xlsx keeps the data and formula results")
def test_save_and_reopen(excel, tmp_path):
    excel.write_row(1, ["Item", "Qty", "Price", "Total"])
    excel.write_row(2, ["Pen", 3, 12.5])
    excel.write_formula("D2", "=B2*C2")
    saved = excel.save_as(tmp_path / "order.xlsx")

    assert saved.exists() and saved.stat().st_size > 0
    assert excel.read_saved_value(saved, "D2") == 37.5
