"""Configuration-driven execution: load settings for the selected environment from config/config.yaml."""
import os
from functools import lru_cache

import yaml

from core.paths import CONFIG_DIR


@lru_cache(maxsize=None)
def _load_file():
    with open(CONFIG_DIR / "config.yaml", encoding="utf-8") as f:
        return yaml.safe_load(f)


def get_config(env=None):
    """
    Return the settings dict for one environment.

    Priority: explicit `env` argument  >  TEST_ENV environment variable  >  default_env in the file.
    """
    data = _load_file()
    env = env or os.environ.get("TEST_ENV") or data["default_env"]
    try:
        settings = dict(data["environments"][env])
    except KeyError:
        raise ValueError(f"Unknown environment '{env}'. Available: {list(data['environments'])}") from None
    settings["env"] = env
    return settings


# Applications the framework can test. Each name is also a pytest marker (see pytest.ini).
SUPPORTED_APPS = ["calculator", "notepad", "excel", "cli", "all"]


def get_app(app=None):
    """
    Return which application to test.

    Priority: explicit `app` argument (--app)  >  TEST_APP environment variable  >  default_app in the file.
    """
    app = (app or os.environ.get("TEST_APP") or _load_file().get("default_app", "all")).strip().lower()
    if app not in SUPPORTED_APPS:
        raise ValueError(f"Unknown application '{app}'. Choose one of: {', '.join(SUPPORTED_APPS)}")
    return app
