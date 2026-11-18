# automation_framework

A small, production-style automation framework for **Windows desktop apps** and **command-line tools**. It's built with PyTest and a page-object design (one class per app window).
It is used on Days 4 and 5 of the course and is the base for the mini project.

## Architecture

```
            tests/  (WHAT to test)          test_calculator.py  test_notepad.py  test_cli.py
               |   fixtures + hooks                      |
               v                                         v
          tests/conftest.py  ---- --env ---->  core/config_reader.py  <-- config/config.yaml
               |
     +---------+-----------+-----------------------+
     v                     v                       v
  pages/  (HOW - UI)    core/cli_runner.py      utils/data_reader.py  <-- test_data/*.csv|json|yaml
  CalculatorPage        (HOW - CLI)             utils/screenshot.py
  NotepadPage              |
     |                     v
     v                  tools/sysinfo_cli.py  (CLI app under test)
  core/base_window.py  -- pywinauto (UIA) --> Calculator / Notepad
  core/waits.py (wait_until, @retry)    core/logger.py --> logs/automation_<time>.log
```

| Folder | Responsibility |
|---|---|
| `config/` | Environment settings (`dev`, `qa`): timeouts, retries, log level, app launch commands |
| `core/` | Framework engine: config, logging, waits/retry, `BaseWindow`, CLI runner, paths |
| `pages/` | One class per application: `CalculatorPage`, `NotepadPage`, `ExcelPage`. Locators live **only** here |
| `utils/` | Helpers: CSV/JSON/YAML readers, screenshots |
| `tools/` | `sysinfo_cli.py`, the command-line application under test |
| `test_data/` | Data for data-driven tests |
| `tests/` | Test cases + `conftest.py` (fixtures, `--env`, desktop screenshots) |
| `run_tests.py` | One command: pytest + Allure HTML + PDF |
| `allurerc.mjs` | Allure 3 report settings (name, single file, grouping, history) |
| `tools/allure_pdf_report.py` | Converts Allure results into a PDF report |
| `logs/ reports/ screenshots/ allure-results/ allure-report/` | Generated at run time (git-ignored) |

## Run

On Windows, double-click `run_automation.bat` to choose an application, or run it from PowerShell:

```powershell
.\run_automation.bat --app excel --env qa
```

For direct pytest commands, start in the project root:

```bash
python -m pip install -r requirements.txt
# Install Node.js LTS for Allure 3; npx downloads the generator on first use.

pytest                                  # everything
pytest -m smoke                         # quick critical checks
pytest -m cli --env qa                  # CLI tests with QA settings (works on Linux too)
pytest -m "desktop and not regression"  # desktop smoke only
pytest -k calculator                    # by name
pytest --html=reports/report.html --self-contained-html   # HTML report
```

`TEST_ENV=qa pytest` works as an alternative to `--env qa` (PowerShell: `$env:TEST_ENV="qa"; pytest`).

## Choosing the application under test

```bash
python run_tests.py                       # ASKS: 1 calculator  2 notepad  3 excel  4 cli  5 all  (Enter = default)
python run_tests.py --app excel           # no question - opens Excel, runs only the Excel tests
python run_tests.py --app calculator -m smoke --env qa
pytest --app notepad                      # same selection directly in pytest
```

| Priority | Source |
|---|---|
| 1 | `--app` on the command line |
| 2 | `TEST_APP` environment variable |
| 3 | `default_app` in `config/config.yaml` (**`all`**). This default is also used when nobody can answer the question (CI, scheduled runs, piped input) |

| App | Tests | How it is automated |
|---|---|---|
| `calculator` | 8 | pywinauto (UI Automation), `pages/calculator_page.py` |
| `notepad` | 4 | pywinauto, works only on its own temp file, `pages/notepad_page.py` |
| `excel` | 9 | COM (`win32com`), **separate Excel instance**, `pages/excel_page.py`. Skipped if Excel is not installed |
| `cli` | 9 | `subprocess`, `core/cli_runner.py` + `tools/sysinfo_cli.py` |

Each test file has an application marker (`pytest.mark.excel` ...). `conftest.py` keeps only the tests of the selected application.

## Reports: pytest-html, Allure and PDF

**One command** runs the tests and builds all three reports (pytest options pass through):

```bash
python run_tests.py                        # all tests + all reports
python run_tests.py -m smoke --env qa      # any pytest selection
python run_tests.py -m cli --open          # also open the Allure report in the browser
```

| Report | File | Built by | Best for |
|---|---|---|---|
| **Allure** | `allure-report/index.html` (single file) | `npx allure generate allure-results --clean` (Allure 3, Node.js, **no Java**) | Interactive analysis: steps, attachments, grouping by epic/feature/story, severity, history/trends |
| **PDF** | `reports/test_report.pdf` | `python tools/allure_pdf_report.py` | Sharing and sign-off: summary + pie chart, results by feature, all tests, failures with trace/steps/screenshot, steps of every test |
| pytest-html | `reports/report.html` | `--html=...` | Quick single-page view |

**How it fits together**

```
pytest  --(allure-pytest, enabled in pytest.ini: --alluredir=allure-results)-->  allure-results/*.json
                                                                                  |            |
                                     npx allure generate allure-results --clean   |            |  python tools/allure_pdf_report.py
                                                                                  v            v
                                                               allure-report/index.html    reports/test_report.pdf
```

- **Labels**: tests use `@allure.epic / feature / story / severity / title` (see `tests/test_calculator.py`).
- **Steps**: page objects and the CLI runner record steps through `core/reporting.py` (`step`, `@step_method`, `attach_text`, `attach_png`). If `allure-pytest` is missing, these helpers do nothing, so the framework still runs.
- **Attachments**: CLI stdout/stderr/exit code, the Calculator display, the saved Notepad file, and full-screen PNGs from passing and failing desktop tests. Screenshots are taken after the test body, before fixtures close the app. They are saved in `screenshots/` and attached to pytest-html and Allure; the PDF still shows only failure screenshots. To restore failure-only capture, set `screenshots_on_pass: false` for the relevant environment in `config/config.yaml`.
- **Jenkins desktop runs**: Run the agent in a signed-in, unlocked Windows desktop session. To download standalone PNGs from a build, archive `screenshots/*.png` from the Jenkins workspace.
- **Local Excel runs**: With `excel.visible: true`, the automation asks Windows to bring the test workbook to the foreground. CI (including Jenkins) does not take focus. If Windows denies the request, the run logs a warning and continues.
- **Environment**: `conftest.py` writes `allure-results/environment.properties` (env, OS, Python, host).
- **History**: `allurerc.mjs` keeps `allure-history/history.jsonl`, so the report shows trends across runs.
- **PDF options**: `--title "Sprint 42 regression"`, `--details failed` (shorter PDF), `--results DIR`, `--output FILE`.

Manual commands (from the project root, with Node.js LTS installed):

```bash
npx --yes allure generate allure-results --clean  # replace the generated allure-report/
npx --yes allure open                     # serve and open it
python tools/allure_pdf_report.py          # build reports/test_report.pdf
```

The Allure configuration exports a plain object, so no local npm package or
`npm install` is required. `npx` downloads and caches the Allure CLI separately;
it does not make the `allure` package available for imports from `allurerc.mjs`.

> Why a separate PDF tool? The Allure report is an interactive web app with no "Export to PDF" option. Printing it from the browser only captures the first screen. The PDF tool reads the same `allure-results` data, so both reports always agree.

## Rules for the desktop tests

- Keep the desktop **unlocked** and don't touch the mouse or keyboard while desktop tests run.
- Windows 11 Notepad can restore previous tabs or reuse an open window. Tests first open a separate blank window, then open a temporary file in it. The fixture closes only that test window and leaves pre-existing windows alone.
- The tests close Calculator when they finish.
- Excel runs in its **own** instance (`DispatchEx`). Your open workbooks are never touched, and the instance is always quit, or its own process stopped, at the end.
- On Linux/macOS, desktop tests are **skipped** automatically.

## Extending

1. **New window:** create `pages/<app>_page.py` with a class that inherits `BaseWindow`, and keep its locators at the top of the file.
2. **New fixture:** add it to `tests/conftest.py`, with `yield` so cleanup always runs.
3. **New data:** add a file to `test_data/` and use it with `read_csv/read_json/read_yaml` plus `@pytest.mark.parametrize`.
4. **New settings:** add the keys to **every** environment in `config/config.yaml`.
