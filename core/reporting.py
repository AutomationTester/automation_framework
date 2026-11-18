"""
Allure integration helpers - steps and attachments for the Allure report.

Framework code calls these helpers instead of importing allure directly, so everything keeps
working (the calls simply do nothing) on a machine where allure-pytest is not installed.
"""
import functools
from contextlib import nullcontext
from pathlib import Path

try:
    import allure
except ImportError:  # allure-pytest not installed -> reporting becomes a no-op
    allure = None


def step(title):
    """Use as:  with step("Calculate 7 + 8"): ...   -> shows as a step in the Allure report."""
    return allure.step(title) if allure else nullcontext()


def step_method(title):
    """Decorator version:  @step_method("Save the file")  on a page-object method."""
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            with step(title):
                return func(*args, **kwargs)
        return wrapper
    return decorator


def attach_text(text, name):
    if allure and text:
        allure.attach(text, name=name, attachment_type=allure.attachment_type.TEXT)


def attach_png(path, name="screenshot"):
    if allure and path and Path(path).exists():
        allure.attach.file(str(path), name=name, attachment_type=allure.attachment_type.PNG)
