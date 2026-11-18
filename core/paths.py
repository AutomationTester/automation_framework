"""Well-known folders of the framework, resolved relative to this file (works from any working directory)."""
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CONFIG_DIR = ROOT / "config"
TEST_DATA_DIR = ROOT / "test_data"
LOG_DIR = ROOT / "logs"
REPORT_DIR = ROOT / "reports"
SCREENSHOT_DIR = ROOT / "screenshots"
TOOLS_DIR = ROOT / "tools"
