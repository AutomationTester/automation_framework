"""
Shared fixtures and hooks. pytest loads this file automatically before running tests in this folder.

  --env dev|qa                 choose the environment from config/config.yaml (or set TEST_ENV)
  --app calculator|notepad|excel|cli|all
                               choose the application under test (or set TEST_APP; default: default_app
                               in config.yaml). Only the tests marked for that application are run.
  calculator / notepad / excel ready-to-use window objects, always cleaned up after the test
  desktop screenshots          after each passing or failing test body, saved and embedded in HTML
                               and attached to the Allure report
  allure environment           writes allure-results/environment.properties (env, OS, Python, host)
"""
import base64
import platform
import socket
import sys
from pathlib import Path

import pytest

from core.config_reader import SUPPORTED_APPS, get_app, get_config
from core.logger import get_logger, setup_logging
from core.reporting import attach_png
from utils.screenshot import take_screenshot

log = get_logger("tests")


def pytest_addoption(parser):
    parser.addoption("--env", default=None, help="environment from config/config.yaml, e.g. dev or qa")
    parser.addoption("--app", default=None, choices=SUPPORTED_APPS,
                     help="application under test (default: TEST_APP or default_app in config.yaml)")


def pytest_configure(config):
    settings = get_config(config.getoption("--env"))
    setup_logging(settings["log_level"])
    log.info("Environment: %s", settings["env"])
    config.selected_app = get_app(config.getoption("--app"))
    log.info("Application under test: %s", config.selected_app)


def pytest_report_header(config):
    return f"application under test: {config.selected_app}  (change with --app)"


def pytest_sessionfinish(session):
    # Written at the END: --clean-alluredir empties the folder at the start of the run.
    config = session.config
    _write_allure_environment(config, get_config(config.getoption("--env")))


def _write_allure_environment(config, settings):
    """environment.properties -> the 'Environment' section of the Allure report (and of the PDF)."""
    results_dir = getattr(config.option, "allure_report_dir", None)
    if not results_dir:
        return  # Allure not enabled for this run
    results_dir = Path(results_dir)
    results_dir.mkdir(parents=True, exist_ok=True)
    info = {
        "Environment": settings["env"],
        "OS": f"{platform.system()} {platform.release()} ({platform.version()})",
        "Python": platform.python_version(),
        "Host": socket.gethostname(),
        "Application": config.selected_app,
        "Element.Timeout": f"{settings['timeouts']['element']}s",
    }
    lines = [f"{key}={value}" for key, value in info.items()]
    (results_dir / "environment.properties").write_text("\n".join(lines) + "\n", encoding="utf-8")


def pytest_collection_modifyitems(config, items):
    """1) Keep only the tests of the selected application.  2) Skip desktop tests on non-Windows."""
    app = config.selected_app
    if app != "all":
        selected = [item for item in items if app in item.keywords]
        deselected = [item for item in items if app not in item.keywords]
        if deselected:
            config.hook.pytest_deselected(items=deselected)
            items[:] = selected

    if sys.platform == "win32":
        return
    skip = pytest.mark.skip(reason="desktop tests need a Windows desktop session")
    for item in items:
        if "desktop" in item.keywords:
            item.add_marker(skip)


# ---------------- fixtures ----------------
@pytest.fixture(scope="session")
def config(request):
    return get_config(request.config.getoption("--env"))


@pytest.fixture(scope="module")
def calculator(config):
    """One Calculator window shared by all tests in a module (starting it is slow)."""
    from pages.calculator_page import CalculatorPage  # imported here: pywinauto exists only on Windows

    page = CalculatorPage(config).open()
    yield page
    page.close()


@pytest.fixture
def notepad(config, tmp_path):
    """A Notepad tab on a brand-new empty file that belongs to this test only."""
    from pages.notepad_page import NotepadPage

    test_file = tmp_path / "automation_note.txt"
    test_file.write_text("", encoding="utf-8")
    page = NotepadPage(config).open_file(test_file)
    yield page
    page.close_tab()


@pytest.fixture(scope="module")
def excel_app(config):
    """One separate Excel instance per test module (starting Excel is slow). Never touches the user's Excel."""
    from pages.excel_page import ExcelPage

    page = ExcelPage(config)
    try:
        page.open()
    except Exception as error:  # Excel not installed / COM not registered
        pytest.skip(f"Microsoft Excel is not available on this machine: {error}")
    yield page
    page.quit()


@pytest.fixture
def excel(excel_app):
    """A fresh, empty workbook for each test - closed without saving afterwards."""
    excel_app.new_workbook()
    yield excel_app
    excel_app.close_workbook()


# ---------------- desktop screenshots ----------------
@pytest.hookimpl(hookwrapper=True, tryfirst=True)
def pytest_runtest_makereport(item, call):
    outcome = yield
    report = outcome.get_result()
    if report.when != "call" or report.skipped or "desktop" not in item.keywords:
        return
    settings = get_config(item.config.getoption("--env"))
    if report.failed and not settings["screenshots_on_failure"]:
        return
    if report.passed and not settings.get("screenshots_on_pass", False):
        return

    path = take_screenshot(item.name)
    if path is None:
        return
    log.info("Screenshot saved (%s): %s", report.outcome, path)
    attach_png(path, "screenshot on failure" if report.failed else "screenshot after pass")

    html_plugin = item.config.pluginmanager.getplugin("html")
    if html_plugin is not None:  # pytest-html installed -> embed the image in the report
        encoded = base64.b64encode(path.read_bytes()).decode()
        report.extras = getattr(report, "extras", []) + [html_plugin.extras.png(encoded)]
