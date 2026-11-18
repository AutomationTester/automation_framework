"""Full-screen screenshots for failure evidence. Returns None where no display exists (e.g. Linux CI)."""
from datetime import datetime

from core.paths import SCREENSHOT_DIR


def take_screenshot(name):
    try:
        from PIL import ImageGrab
        image = ImageGrab.grab()
    except Exception:
        return None
    SCREENSHOT_DIR.mkdir(exist_ok=True)
    safe_name = "".join(c if c.isalnum() or c in "-_" else "_" for c in name)
    path = SCREENSHOT_DIR / f"{safe_name}_{datetime.now():%Y%m%d_%H%M%S}.png"
    image.save(path)
    return path
