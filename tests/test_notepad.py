"""Notepad tests: type text, save, and verify both the editor and the file on disk."""
import allure
import pytest

from utils.data_reader import read_json

CASES = read_json("notepad_data.json")

pytestmark = [pytest.mark.desktop, pytest.mark.notepad, allure.epic("Desktop automation"), allure.feature("Notepad")]


@pytest.mark.smoke
@allure.story("Type and save")
@allure.severity(allure.severity_level.BLOCKER)
@allure.title("Typed text is saved to disk")
def test_type_and_save(notepad):
    notepad.type_text("Automation says hello")
    notepad.save()
    assert notepad.saved_content() == "Automation says hello"


@pytest.mark.regression
@allure.story("Data-driven text (JSON)")
@allure.severity(allure.severity_level.CRITICAL)
@allure.title("{case[test_id]}: text is saved exactly")
@pytest.mark.parametrize("case", CASES, ids=[c["test_id"] for c in CASES])
def test_text_is_saved_exactly(notepad, case):
    notepad.type_text(case["text"])
    assert notepad.text == case["text"]
    notepad.save()
    # Notepad may save line breaks as \r\n - compare after normalising.
    assert notepad.saved_content().replace("\r\n", "\n") == case["text"]
