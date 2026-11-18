"""One logger for the whole run: console (INFO+) and a per-run log file (DEBUG+ by default)."""
import logging
from datetime import datetime

from core.paths import LOG_DIR

_FORMAT = "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"
_ROOT_NAME = "automation"
_configured = False


def setup_logging(level="INFO", keep_last=10):
    """Create logs/automation_<timestamp>.log and keep only the newest `keep_last` log files."""
    global _configured
    if _configured:
        return
    LOG_DIR.mkdir(exist_ok=True)
    # Log file management: delete the oldest files so that, with the new one, only `keep_last` remain.
    old_logs = sorted(LOG_DIR.glob("automation_*.log"))
    for old in old_logs[:max(0, len(old_logs) - (keep_last - 1))]:
        old.unlink(missing_ok=True)

    log_file = LOG_DIR / f"automation_{datetime.now():%Y%m%d_%H%M%S}.log"
    root = logging.getLogger(_ROOT_NAME)
    root.setLevel(logging.DEBUG)

    file_handler = logging.FileHandler(log_file, encoding="utf-8")
    file_handler.setLevel(level)
    file_handler.setFormatter(logging.Formatter(_FORMAT))

    console = logging.StreamHandler()
    console.setLevel(logging.INFO)
    console.setFormatter(logging.Formatter("%(levelname)-8s %(message)s"))

    root.addHandler(file_handler)
    root.addHandler(console)
    _configured = True
    root.info("Log file: %s", log_file)


def get_logger(name):
    """Child logger, e.g. get_logger('pages.calculator') -> 'automation.pages.calculator'."""
    return logging.getLogger(f"{_ROOT_NAME}.{name}")
