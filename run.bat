@echo off
REM Harmonia launcher for Windows. Sets everything up the first time, then just
REM starts the server on every run after that. Safe to run repeatedly.
REM
REM Double-click this file, or run:  run.bat
REM
REM Two rules hold everywhere below, because breaking either one is how the
REM first version of this script reported success while doing nothing:
REM
REM   1. Every external command is followed by an errorlevel check that stops
REM      the script. A step that fails must never fall through to the next one.
REM   2. No `for /f`. A `for /f` whose command begins with a quote is mis-parsed
REM      by cmd, and it fails silently: the loop body never runs and the target
REM      variable is left empty. Output is captured through a file instead, and
REM      version gates are read from exit codes rather than from captured text.
REM
REM The flow is deliberately linear, using goto rather than nested parentheses,
REM so that plain %ERRORLEVEL% is always the code of the command just run.

setlocal
cd /d "%~dp0"

set "PORT=8000"
if not "%HARMONIA_PORT%"=="" set "PORT=%HARMONIA_PORT%"
set "VENV=.venv"
set "STAMP=%VENV%\.harmonia-deps"
set "PY=%VENV%\Scripts\python.exe"
set "ALEMBIC=%VENV%\Scripts\alembic.exe"
set "UVICORN=%VENV%\Scripts\uvicorn.exe"
set "TMPOUT=%TEMP%\harmonia-launcher-%RANDOM%%RANDOM%.tmp"

REM ---------------------------------------------------------------------------
REM Find Python. The py launcher is preferred, since it is what the python.org
REM installer provides and it resolves versions properly.
REM
REM `where` only proves that a name resolves. On a stock Windows install both
REM `py` and `python` can resolve to a Microsoft Store stub that is not Python,
REM so each candidate has to actually run before it is accepted.
REM ---------------------------------------------------------------------------
set "PY_CMD="
where py >nul 2>&1
if %ERRORLEVEL% NEQ 0 goto :try_python
py -3 -c "import sys" >nul 2>&1
if %ERRORLEVEL% NEQ 0 goto :try_python
set "PY_CMD=py -3"
goto :check_python

:try_python
where python >nul 2>&1
if %ERRORLEVEL% NEQ 0 goto :no_python
python -c "import sys" >nul 2>&1
if %ERRORLEVEL% NEQ 0 goto :no_python
set "PY_CMD=python"

:check_python
%PY_CMD% -c "import sys; sys.exit(0 if sys.version_info >= (3, 11) else 1)" >nul 2>&1
if %ERRORLEVEL% NEQ 0 goto :old_python

%PY_CMD% -c "import venv" >nul 2>&1
if %ERRORLEVEL% NEQ 0 goto :no_venv_module

REM ---------------------------------------------------------------------------
REM Virtual environment. Created once.
REM ---------------------------------------------------------------------------
if exist "%PY%" goto :venv_ready

echo ==^> Creating a virtual environment in %VENV%
%PY_CMD% -m venv "%VENV%"
if %ERRORLEVEL% NEQ 0 goto :venv_failed
REM venv can report success and still leave no interpreter behind, which is what
REM a file-syncing client holding a lock on the folder looks like. Check.
if not exist "%PY%" goto :venv_failed
echo   ok created
goto :deps

:venv_ready
echo   ok virtual environment already exists

REM ---------------------------------------------------------------------------
REM Dependencies. Reinstalled only when pyproject.toml actually changes, so a
REM second run does not sit through pip resolving scipy again.
REM ---------------------------------------------------------------------------
:deps
"%PY%" -c "import hashlib,pathlib,sys;sys.stdout.write(hashlib.sha256(pathlib.Path('pyproject.toml').read_bytes()).hexdigest())" >"%TMPOUT%"
if %ERRORLEVEL% NEQ 0 goto :hash_failed
set "SUM="
set /p SUM=<"%TMPOUT%"
del "%TMPOUT%" >nul 2>&1
REM An empty SUM would compare equal to an empty OLDSUM and silently claim the
REM dependencies were already installed. Refuse to continue without a hash.
if not defined SUM goto :hash_failed

set "OLDSUM="
if exist "%STAMP%" set /p OLDSUM=<"%STAMP%"

if "%SUM%"=="%OLDSUM%" goto :deps_ready

echo ==^> Installing Python dependencies ^(this takes a few minutes the first time^)
"%PY%" -m pip install --upgrade pip >nul
if %ERRORLEVEL% NEQ 0 goto :pip_failed
"%PY%" -m pip install -e .
if %ERRORLEVEL% NEQ 0 goto :pip_failed
REM The stamp is written only after pip actually succeeded, so an install that
REM was interrupted is retried next run rather than skipped.
>"%STAMP%" echo %SUM%
if %ERRORLEVEL% NEQ 0 goto :stamp_failed
echo   ok installed
goto :migrate

:deps_ready
echo   ok dependencies already installed

REM ---------------------------------------------------------------------------
REM Database. `upgrade head` is idempotent and quick, so it always runs: that is
REM what keeps an existing install working after a version bump.
REM
REM This calls the console script rather than `python -m alembic`. Both work
REM when alembic is installed, but `-m` reports a missing alembic as
REM   'alembic' is a package and cannot be directly executed
REM because this repository has its own alembic\ migrations directory, which is
REM the only candidate left when the real package is absent. That message sends
REM you looking at the wrong thing.
REM ---------------------------------------------------------------------------
:migrate
echo ==^> Applying database migrations
if not exist "%ALEMBIC%" goto :alembic_missing
"%ALEMBIC%" upgrade head
if %ERRORLEVEL% NEQ 0 goto :alembic_failed
echo   ok database ready

REM ---------------------------------------------------------------------------
REM Frontend. Built once. Delete frontend\build to force a rebuild.
REM ---------------------------------------------------------------------------
if exist "frontend\build\index.html" goto :frontend_ready

where npm >nul 2>&1
if %ERRORLEVEL% NEQ 0 goto :no_node
where node >nul 2>&1
if %ERRORLEVEL% NEQ 0 goto :no_node

REM Version gate by exit code. Capturing "yes" or "no" from node would make a
REM node that crashed indistinguishable from a node that is too old.
node -e "const v=process.versions.node.split('.').map(Number);process.exit((v[0]>22||(v[0]===22&&v[1]>=12)||v[0]===21||(v[0]===20&&v[1]>=19))?0:1)"
if %ERRORLEVEL% NEQ 0 goto :old_node

echo ==^> Building the web interface ^(first run only^)
pushd frontend
if %ERRORLEVEL% NEQ 0 goto :build_failed
call npm install
if %ERRORLEVEL% NEQ 0 goto :build_failed_in_frontend
call npm run build
if %ERRORLEVEL% NEQ 0 goto :build_failed_in_frontend
popd
if not exist "frontend\build\index.html" goto :build_failed
echo   ok built
goto :serve

:frontend_ready
echo   ok frontend already built

REM ---------------------------------------------------------------------------
REM Open the browser, then start the server in this window.
REM ---------------------------------------------------------------------------
:serve
if not exist "%UVICORN%" goto :uvicorn_missing

echo.
echo ==^> Starting Harmonia on http://127.0.0.1:%PORT%
echo     Press Ctrl+C to stop.
echo.

REM Wait for the port to answer, then open the browser. The previous version
REM slept a fixed four seconds with `timeout`, which cannot work here: under
REM `start /b` there is no console for it to read from, and on any machine with
REM Git for Windows on PATH the name resolves to GNU timeout, which takes
REM different arguments. Either way it failed, and the browser opened at once
REM against a port with nothing behind it.
start "" /b "%PY%" -c "import socket,sys,time,webbrowser;p=int(sys.argv[1]);c=lambda:socket.socket().connect_ex(('127.0.0.1',p))==0;any(c() or time.sleep(1) for _ in range(60)) and webbrowser.open('http://127.0.0.1:'+sys.argv[1])" %PORT%

"%UVICORN%" --factory backend.main:create_app --host 127.0.0.1 --port %PORT%
set "CODE=%ERRORLEVEL%"
if not "%CODE%"=="0" goto :server_failed
endlocal
exit /b 0

REM ---------------------------------------------------------------------------
REM Failures. Say what to install, not what threw. Every one of these pauses,
REM because the documented way to start Harmonia is to double-click this file,
REM and a window that closes on its own tells you nothing.
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

:no_venv_module
echo.
echo Error: Python is installed but the 'venv' module is missing.
echo.
echo This usually means a partial or trimmed installation. Reinstalling Python
echo from https://www.python.org/downloads/ restores it.
echo.
pause
exit /b 1

:venv_failed
echo.
echo Error: could not create the virtual environment in %VENV%.
echo The output above says why.
echo.
echo If this folder is inside OneDrive, Dropbox or another syncing folder, the
echo sync client can hold files open while the environment is being written.
echo Moving the project somewhere local, such as %%USERPROFILE%%\Harmonia-web,
echo is the reliable fix.
echo.
pause
exit /b 1

:hash_failed
del "%TMPOUT%" >nul 2>&1
echo.
echo Error: could not read pyproject.toml to decide whether the dependencies
echo need installing.
echo.
echo Check that you are running this script from inside the Harmonia folder and
echo that pyproject.toml is present next to it.
echo.
pause
exit /b 1

:pip_failed
echo.
echo Error: installing the Python dependencies failed.
echo The output above says why.
echo.
echo If this folder is inside OneDrive, Dropbox or another syncing folder, the
echo sync client can lock files mid-install. Moving the project somewhere local,
echo such as %%USERPROFILE%%\Harmonia-web, is the reliable fix.
echo.
pause
exit /b 1

:stamp_failed
echo.
echo Error: the dependencies installed, but the marker file %STAMP% could not
echo be written.
echo.
echo Harmonia would still run, but without that file it reinstalls everything on
echo every start, so it is worth fixing. The usual cause is a read-only folder
echo or a sync client holding the file open.
echo.
pause
exit /b 1

:alembic_missing
echo.
echo Error: alembic is not installed in %VENV%.
echo.
echo The dependency install did not complete. Delete the %VENV% folder and run
echo this script again to redo it from scratch.
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

:build_failed_in_frontend
popd

:build_failed
echo.
echo Error: building the web interface failed.
echo The output above says why.
echo.
pause
exit /b 1

:uvicorn_missing
echo.
echo Error: uvicorn is not installed in %VENV%.
echo.
echo The dependency install did not complete. Delete the %VENV% folder and run
echo this script again to redo it from scratch.
echo.
pause
exit /b 1

:server_failed
echo.
echo Error: the server stopped with exit code %CODE%.
echo The output above says why.
echo.
echo The most common cause is that port %PORT% is already in use, often by an
echo earlier Harmonia that is still running. Set HARMONIA_PORT to pick another:
echo   set HARMONIA_PORT=8080
echo   run.bat
echo.
pause
exit /b 1
