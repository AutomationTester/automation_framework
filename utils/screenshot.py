"""Full-screen screenshots for failure evidence. Returns None where no display exists (e.g. Linux CI)."""
from datetime import datetime

from core.logger import get_logger
from core.paths import SCREENSHOT_DIR

log = get_logger("screenshot")


def take_screenshot(name):
    safe_name = "".join(c if c.isalnum() or c in "-_" else "_" for c in name)
    path = SCREENSHOT_DIR / f"{safe_name}_{datetime.now():%Y%m%d_%H%M%S_%f}.png"
    try:
        from PIL import ImageGrab

        image = ImageGrab.grab()
    except (ImportError, OSError) as error:
        log.warning("Could not capture screenshot for %s: %s", name, error)
        return None
    try:
        SCREENSHOT_DIR.mkdir(exist_ok=True)
        image.save(path)
    except OSError as error:
        log.warning("Could not save screenshot to %s: %s", path, error)
        return None
    return path
