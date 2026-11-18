"""
run_tests.py - one command: choose the application, run pytest, build the Allure HTML and PDF reports.

    python run_tests.py                         # ASKS which application to test (Enter = default)
    python run_tests.py --app excel             # no question: test Excel only
    python run_tests.py --app all -m smoke      # smoke tests of every application
    python run_tests.py --app notepad --env qa --open
    python run_tests.py --no-prompt             # never ask - use TEST_APP / default_app from config.yaml

Applications: calculator | notepad | excel | cli | all
If no --app is given and nobody can answer (CI, scheduled task, piped input), the framework
starts with its default set-up: TEST_APP environment variable, else default_app in config/config.yaml.

Outputs:
    allure-results/          raw results written by allure-pytest during the run
    allure-report/index.html interactive Allure report (single file)   <- needs Node.js (npx allure)
    reports/test_report.pdf  printable PDF report                      <- tools/allure_pdf_report.py
    reports/report.html      pytest-html report

The exit code is pytest's, so CI still fails when tests fail even though reports are built.
"""
import os
import shutil
import subprocess
import sys
import webbrowser
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from core.config_reader import SUPPORTED_APPS, get_app  # noqa: E402

OWN_FLAGS = {"--open", "--no-pdf", "--no-allure", "--no-prompt"}
APP_MENU = {
    "calculator": "Windows Calculator  (UI automation - pywinauto)",
    "notepad": "Windows Notepad     (UI automation - pywinauto, own temp file)",
    "excel": "Microsoft Excel     (COM automation - separate Excel instance)",
    "cli": "sysinfo_cli tool    (command-line automation, no GUI)",
    "all": "All applications",
}


def extract_app(args):
    """Remove '--app X' / '--app=X' from args. Returns (app or None, remaining args)."""
    app, rest, i = None, [], 0
    while i < len(args):
        if args[i] == "--app" and i + 1 < len(args):
            app, i = args[i + 1], i + 2
            continue
        if args[i].startswith("--app="):
            app = args[i].split("=", 1)[1]
        else:
            rest.append(args[i])
        i += 1
    return app, rest


def can_ask_user():
    """Only prompt when a person is at the keyboard - never in CI or when input is piped."""
    return sys.stdin.isatty() and not os.environ.get("CI")


def ask_for_app(default):
    print("\nWhich application do you want to test?")
    for number, (name, description) in enumerate(APP_MENU.items(), 1):
        marker = "  <- default" if name == default else ""
        print(f"  {number}. {name:<11} {description}{marker}")
    names = list(APP_MENU)
    while True:
        try:
            answer = input(f"Enter a number or name [Enter = {default}]: ").strip().lower()
        except EOFError:        # input closed - behave like pressing Enter
            answer = ""
        if not answer:
            return default
        if answer.isdigit() and 1 <= int(answer) <= len(names):
            return names[int(answer) - 1]
        if answer in names:
            return answer
        print(f"  '{answer}' is not valid - choose 1-{len(names)} or one of: {', '.join(names)}")


def choose_app(cli_app, allow_prompt):
    if cli_app:                               # 1. given on the command line
        return get_app(cli_app)
    default = get_app()                       # 2. TEST_APP env var or default_app in config.yaml
    if allow_prompt and can_ask_user():       # 3. ask the person running the script
        return ask_for_app(default)
    print(f"No --app given - using the default set-up: {default}")
    return default


def run_pytest(app, pytest_args):
    cmd = [sys.executable, "-m", "pytest", "--app", app, *pytest_args,
           "--html=reports/report.html", "--self-contained-html"]
    print(">>", " ".join(cmd))
    return subprocess.call(cmd, cwd=ROOT)


def build_allure_html():
    npx = shutil.which("npx")
    if npx is None:
        print("!! Node.js/npx not found - skipping the Allure HTML report (install Node.js LTS, then `npm install`).")
        return None
    cmd = [npx, "--yes", "allure", "generate", "allure-results", "--clean"]
    print(">>", " ".join(cmd))
    if subprocess.call(cmd, cwd=ROOT) != 0:
        print("!! Allure report generation failed")
        return None
    return ROOT / "allure-report" / "index.html"


def build_pdf(app):
    title = f"Desktop & CLI Automation - Test Report ({app})"
    cmd = [sys.executable, str(ROOT / "tools" / "allure_pdf_report.py"), "--title", title]
    print(">>", " ".join(cmd))
    subprocess.call(cmd, cwd=ROOT)


def main():
    cli_app, args = extract_app(sys.argv[1:])
    if cli_app and cli_app.lower() not in SUPPORTED_APPS:
        print(f"Unknown application '{cli_app}'. Choose one of: {', '.join(SUPPORTED_APPS)}")
        return 2
    app = choose_app(cli_app, allow_prompt="--no-prompt" not in args)
    print(f"\n=== Application under test: {app} ===\n")

    pytest_args = [a for a in args if a not in OWN_FLAGS]
    exit_code = run_pytest(app, pytest_args)
    if not any((ROOT / "allure-results").glob("*-result.json")):
        print("!! No Allure results (no tests selected?) - reports not built.")
        return exit_code

    report = None if "--no-allure" in args else build_allure_html()
    if "--no-pdf" not in args:
        build_pdf(app)

    print("\nReports:")
    if report:
        print(f"  Allure : {report}")
    if "--no-pdf" not in args:
        print(f"  PDF    : {ROOT / 'reports' / 'test_report.pdf'}")
    print(f"  HTML   : {ROOT / 'reports' / 'report.html'}")
    if report and "--open" in args:
        webbrowser.open(report.as_uri())
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
