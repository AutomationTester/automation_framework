"""CLI tests for tools/sysinfo_cli.py - no GUI, so they run on Windows, Linux and macOS (and in CI)."""
import json
import sys

import allure
import pytest

from core.cli_runner import run_command
from core.paths import TOOLS_DIR
from utils.data_reader import read_yaml

TOOL = [sys.executable, str(TOOLS_DIR / "sysinfo_cli.py")]
CASES = read_yaml("cli_cases.yaml")

pytestmark = [pytest.mark.cli, allure.epic("CLI automation"), allure.feature("sysinfo_cli tool")]


@pytest.fixture
def run_tool(config):
    """Run the tool with the command timeout from config.yaml."""
    def _run(*args):
        return run_command([*TOOL, *args], timeout=config["cli"]["command_timeout"])
    return _run


@pytest.mark.smoke
@allure.story("Output format")
@allure.severity(allure.severity_level.BLOCKER)
@allure.title("info --json returns valid JSON with correct values")
def test_info_json_is_valid(run_tool):
    result = run_tool("info", "--json")
    assert result.ok, result.stderr
    data = json.loads(result.stdout)
    assert data["python"] == ".".join(map(str, sys.version_info[:3]))
    assert data["cpu_count"] >= 1


@pytest.mark.regression
@allure.story("Exit-code contract (YAML data)")
@allure.severity(allure.severity_level.CRITICAL)
@allure.title("CLI case: {case[name]}")
@pytest.mark.parametrize("case", CASES, ids=[c["name"] for c in CASES])
def test_cli_cases_from_yaml(run_tool, case):
    result = run_tool(*case["args"])
    assert result.returncode == case["expected_rc"], f"stdout={result.stdout!r} stderr={result.stderr!r}"
    if "stdout_contains" in case:
        assert case["stdout_contains"] in result.stdout
    if "stderr_contains" in case:
        assert case["stderr_contains"] in result.stderr


@pytest.mark.regression
@allure.story("Log analysis")
@allure.severity(allure.severity_level.NORMAL)
@allure.title("count --pattern ERROR finds 2 matches in a log file")
def test_count_pattern_in_log(run_tool, tmp_path):
    log_file = tmp_path / "app.log"
    log_file.write_text("INFO start\nERROR db down\nINFO retry\nERROR timeout\n", encoding="utf-8")
    result = run_tool("count", str(log_file), "--pattern", "ERROR")
    assert result.ok
    assert result.stdout.strip() == "matches: 2"


@pytest.mark.regression
@allure.story("Performance")
@allure.severity(allure.severity_level.MINOR)
@allure.title("Tool answers --version in under 5 seconds")
def test_tool_is_fast(run_tool):
    result = run_tool("--version")
    assert result.duration < 5, f"took {result.duration:.1f}s"
