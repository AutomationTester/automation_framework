"""Run command-line programs and capture everything a test needs to validate them."""
import subprocess
import time
from dataclasses import dataclass

from core.logger import get_logger
from core.reporting import attach_text, step

log = get_logger("cli")


@dataclass
class CommandResult:
    command: list
    returncode: int
    stdout: str
    stderr: str
    duration: float

    @property
    def ok(self):
        return self.returncode == 0


def run_command(cmd, timeout=30, cwd=None, input_text=None):
    """
    Run `cmd` (a list, e.g. ["python", "--version"]) without a shell.
    Never raises for a non-zero exit code - the test decides what is a failure.
    Raises subprocess.TimeoutExpired if the command hangs longer than `timeout`.
    """
    command_text = " ".join(map(str, cmd))
    log.info("RUN: %s", command_text)
    with step(f"Run: {command_text}"):
        start = time.monotonic()
        proc = subprocess.run(
            [str(c) for c in cmd], capture_output=True, text=True,
            timeout=timeout, cwd=cwd, input=input_text, encoding="utf-8", errors="replace",
        )
        result = CommandResult(cmd, proc.returncode, proc.stdout, proc.stderr, time.monotonic() - start)
        log.debug("rc=%s duration=%.2fs\nSTDOUT:\n%s\nSTDERR:\n%s",
                  result.returncode, result.duration, result.stdout, result.stderr)
        attach_text(f"exit code: {result.returncode}\nduration : {result.duration:.2f}s", "exit code")
        attach_text(result.stdout, "stdout")
        attach_text(result.stderr, "stderr")
    return result
