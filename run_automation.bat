@echo off
REM ============================================================================
REM  run_automation.bat - runs the Desktop & CLI automation framework
REM
REM  Double-click          -> asks which application to test (Enter = default)
REM  run_automation.bat --app excel
REM  run_automation.bat --app all -m smoke --open
REM  run_automation.bat --app notepad --env qa --no-pdf
REM
REM  All arguments are passed straight to run_tests.py.
REM  Exit code = pytest's exit code (0 = all tests passed).
REM ============================================================================
setlocal

pushd "%~dp0." || (
    echo Could not open the project folder: "%~dp0"
    pause
    exit /b 1
)

REM Pick a stable Python (pre-release versions such as 3.15 have no prebuilt
REM wheels, so PyYAML etc. fail to install). Override with: set PYTHON=...
if not defined PYTHON (
    for %%V in (3.13 3.12 3.11 3.10) do (
        if not defined PYTHON (
            py -%%V -c "import sys" >nul 2>&1 && set "PYTHON=py -%%V"
        )
    )
)
if not defined PYTHON set "PYTHON=python"

%PYTHON% -c "import sys" >nul 2>&1
if errorlevel 1 (
    echo Python was not found. Install Python 3.10-3.13 and try again.
    popd
    pause
    exit /b 1
)

REM Install dependencies on first run / when PyYAML etc. are missing
%PYTHON% -c "import yaml, pytest" >nul 2>&1
if errorlevel 1 (
    echo Installing dependencies from requirements.txt ...
    %PYTHON% -m pip install -r "%~dp0requirements.txt"
    if errorlevel 1 (
        echo Dependency installation failed.
        popd
        pause
        exit /b 1
    )
)

%PYTHON% run_tests.py %*
set "RESULT=%ERRORLEVEL%"

popd

echo.
if "%RESULT%"=="0" (
    echo ===== ALL TESTS PASSED =====
) else (
    echo ===== TESTS FAILED  ^(exit code %RESULT%^) =====
)

REM Keep the window open when started by double-click (no arguments)
if "%~1"=="" pause

endlocal & exit /b %RESULT%
