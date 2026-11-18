"""Read test data files from test_data/ (or any path). Used for data-driven / parametrized tests."""
import csv
import json
from pathlib import Path

import yaml

from core.paths import TEST_DATA_DIR


def _resolve(file_name):
    path = Path(file_name)
    return path if path.is_absolute() else TEST_DATA_DIR / path


def read_csv(file_name):
    """List of dicts, one per row. All values are strings - convert them in the test."""
    with open(_resolve(file_name), newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def read_json(file_name):
    with open(_resolve(file_name), encoding="utf-8") as f:
        return json.load(f)


def read_yaml(file_name):
    with open(_resolve(file_name), encoding="utf-8") as f:
        return yaml.safe_load(f)
