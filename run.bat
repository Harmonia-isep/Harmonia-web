@echo off
REM Harmonia launcher for Windows. Sets everything up the first time, then just
REM starts the server on every run after that. Safe to run repeatedly.
REM
REM Double-click this file, or run:  run.bat

setlocal enabledelayedexpansion
cd /d "%~dp0"

set "PORT=8000"
if not "%HARMONIA_PORT%"=="" set "PORT=%HARMONIA_PORT%"
set "VENV=.venv"
set "STAMP=%VENV%\.harmonia-deps"

REM ---------------------------------------------------------------------------
REM Find Python. The py launcher is preferred, since it is what the python.org
REM installer provides and it resolves versions properly.
REM ---------------------------------------------------------------------------
set "PY_CMD="
where py >nul 2>&1
if %ERRORLEVEL% EQU 0 set "PY_CMD=py -3"
if not defined PY_CMD (
    where python >nul 2>&1
    if !ERRORLEVEL! EQU 0 set "PY_CMD=python"
)
if not defined PY_CMD goto :no_python

%PY_CMD% -c "import sys; sys.exit(0 if sys.version_info >= (3, 11) else 1)" >nul 2>&1
if %ERRORLEVEL% NEQ 0 goto :old_python

REM ---------------------------------------------------------------------------
REM Virtual environment. Created once.
REM ---------------------------------------------------------------------------
if exist "%VENV%\Scripts\python.exe" (
    echo   ok virtual environment already exists
) else (
    echo ==^> Creating a virtual environment in %VENV%
    %PY_CMD% -m venv "%VENV%"
    if !ERRORLEVEL! NEQ 0 goto :venv_failed
    echo   ok created
)

set "PY=%VENV%\Scripts\python.exe"

REM ---------------------------------------------------------------------------
REM Dependencies. Reinstalled only when pyproject.toml actually changes, so a
REM second run does not sit through pip resolving scipy again.
REM ---------------------------------------------------------------------------
set "SUM="
for /f "delims=" %%h in ('"%PY%" -c "import hashlib,pathlib;print(hashlib.sha256(pathlib.Path('pyproject.toml').read_bytes()).hexdigest())"') do set "SUM=%%h"

set "OLDSUM="
if exist "%STAMP%" (
    for /f "delims=" %%s in (%STAMP%) do set "OLDSUM=%%s"
)

if "%SUM%"=="%OLDSUM%" (
    echo   ok dependencies already installed
) else (
    echo ==^> Installing Python dependencies ^(this takes a few minutes the first time^)
    "%PY%" -m pip install --upgrade pip >nul
    "%PY%" -m pip install -e .
    if !ERRORLEVEL! NEQ 0 goto :pip_failed
    >"%STAMP%" echo !SUM!
    echo   ok installed
)

REM ---------------------------------------------------------------------------
REM Database. `upgrade head` is idempotent and quick, so it always runs: that is
REM what keeps an existing install working after a version bump.
REM ---------------------------------------------------------------------------
echo ==^> Applying database migrations
"%PY%" -m alembic upgrade head
if %ERRORLEVEL% NEQ 0 goto :alembic_failed
echo   ok database ready

REM ---------------------------------------------------------------------------
REM Frontend. Built once. Delete frontend\build to force a rebuild.
REM ---------------------------------------------------------------------------
if exist "frontend\build\index.html" (
    echo   ok frontend already built
) else (
    where npm >nul 2>&1
    if !ERRORLEVEL! NEQ 0 goto :no_node

    for /f "delims=" %%v in ('node -e "const [a,b]=process.versions.node.split('.').map(Number);process.stdout.write((a>22||(a===22&&b>=12)||(a===20&&b>=19)||(a===21))?'yes':'no')"') do set "NODE_OK=%%v"
    if not "!NODE_OK!"=="yes" goto :old_node

    echo ==^> Building the web interface ^(first run only^)
    pushd frontend
    call npm install
    if !ERRORLEVEL! NEQ 0 ( popd & goto :build_failed )
    call npm run build
    if !ERRORLEVEL! NEQ 0 ( popd & goto :build_failed )
    popd
    if not exist "frontend\build\index.html" goto :build_failed
    echo   ok built
)

REM ---------------------------------------------------------------------------
REM Open the browser, then start the server in this window.
REM ---------------------------------------------------------------------------
echo.
echo ==^> Starting Harmonia on http://127.0.0.1:%PORT%
echo     Press Ctrl+C to stop.
echo.

start "" /b cmd /c "timeout /t 4 /nobreak >nul & start "" http://127.0.0.1:%PORT%"

"%PY%" -m uvicorn --factory backend.main:create_app --host 127.0.0.1 --port %PORT%
goto :eof

REM ---------------------------------------------------------------------------
REM Failures. Say what to install, not what threw.
REM ---------------------------------------------------------------------------
:no_python
echo.
echo Error: Python is not installed, or is not on your PATH.
echo.
echo Harmonia needs Python 3.11 or newer.
echo   Download it from https://www.python.org/downloads/
echo   During installation, tick "Add python.exe to PATH".
echo.
pause
exit /b 1

:old_python
echo.
echo Error: your Python is too old.
echo.
echo Harmonia needs Python 3.11 or newer.
echo   Download a newer one from https://www.python.org/downloads/
echo.
pause
exit /b 1

:venv_failed
echo.
echo Error: could not create the virtual environment in %VENV%.
echo The output above says why.
echo.
pause
exit /b 1

:pip_failed
echo.
echo Error: installing the Python dependencies failed.
echo The output above says why.
echo.
pause
exit /b 1

:alembic_failed
echo.
echo Error: database migrations failed.
echo The output above says why.
echo.
pause
exit /b 1

:no_node
echo.
echo Error: the web interface has not been built yet, and Node.js is not installed.
echo.
echo Harmonia needs Node.js 20.19+ or 22.12+ to build the interface, once.
echo   Download it from https://nodejs.org/
echo.
echo You only need Node for this build step. It is not needed to run
echo Harmonia afterwards.
echo.
pause
exit /b 1

:old_node
echo.
echo Error: your Node.js is too old to build the interface.
echo.
echo Harmonia needs Node.js 20.19+ or 22.12+.
echo   Download a newer one from https://nodejs.org/
echo.
pause
exit /b 1

:build_failed
echo.
echo Error: building the web interface failed.
echo The output above says why.
echo.
pause
exit /b 1
