"""Synchronization helpers: poll for a condition instead of time.sleep(), and retry flaky steps."""
import functools
import time

from core.logger import get_logger

log = get_logger("waits")


class WaitTimeoutError(Exception):
    pass


def wait_until(condition, timeout=10, interval=0.5, message="condition"):
    """
    Call `condition()` until it returns a truthy value or `timeout` seconds pass.
    Returns the truthy value. Exceptions raised by `condition` count as "not yet".
    """
    end = time.monotonic() + timeout
    last_error = None
    while True:
        try:
            result = condition()
            if result:
                return result
        except Exception as e:  # the element may not exist yet
            last_error = e
        if time.monotonic() >= end:
            detail = f" (last error: {last_error})" if last_error else ""
            raise WaitTimeoutError(f"Timed out after {timeout}s waiting for {message}{detail}")
        time.sleep(interval)


def retry(times=3, delay=1.0, backoff=2.0, exceptions=(Exception,)):
    """
    Decorator: re-run the function if it raises one of `exceptions`.
    Waits delay, delay*backoff, delay*backoff^2 ... between attempts (exponential backoff).
    """
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            wait = delay
            for attempt in range(1, times + 1):
                try:
                    return func(*args, **kwargs)
                except exceptions as e:
                    if attempt == times:
                        log.error("%s failed after %d attempts: %s", func.__name__, times, e)
                        raise
                    log.warning("%s attempt %d/%d failed: %s - retrying in %.1fs",
                                func.__name__, attempt, times, e, wait)
                    time.sleep(wait)
                    wait *= backoff
        return wrapper
    return decorator
