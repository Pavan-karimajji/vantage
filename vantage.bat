@echo off
setlocal EnableExtensions EnableDelayedExpansion
cd /d "%~dp0"

REM Vantage entry point.
REM   vantage.bat                -> the LAUNCHER GUI (scripts\gui.py), which
REM                                 picks the recording and the plug-in root,
REM                                 validates them, and shows the command it
REM                                 will run before running it. Builds a
REM                                 scripts\vantage_native.py command.
REM   vantage.bat <args...>      -> scripts\vantage_native.py -- the real
REM                                 vantage_app.exe (WP-34, SM-11).
REM
REM No "--legacy" mode any more. The retiring Python scene/render/player
REM implementation it used to route to (scripts\vantage.py, scripts\gui.py's
REM own Qt-based viewer) is deleted (SM-12, modules/viz/docs/
REM VIZ_Sync_Plan_v0.1.md). A bare replay (no --pipeline) and
REM --preset/--at/--workspace/--version have no native equivalent yet --
REM scripts\vantage_native.py's own top note names this gap plainly rather
REM than a fallback pretending to cover it.
REM
REM The launcher is Tkinter (stdlib) on purpose -- it must start on any
REM install with no extra installed at all, instead of dying with an
REM ImportError on the one screen whose job is getting you running.

REM PT-45 (python_tool_envs_plan.md PR-7, D10): Vantage runs from sim's own
REM declared tool environment, .venv-sim-win32 (python_envs: sim:sim) --
REM never modules\sim\.venv and never a global `py -3`, whose site-packages
REM nobody controls. setup decides whether that environment is usable
REM (--check-only never installs anything); on a refusal its own
REM Reason / Fix / Run is shown and nothing starts.
set "SIM_ENV_PY=%~dp0.venv-sim-win32\Scripts\python.exe"
set "ENVCHECK_LOG=%TEMP%\vantage_envcheck_%RANDOM%%RANDOM%.txt"
call "%~dp0setup.bat" --python-envs-only --python-env sim:sim --check-only > "%ENVCHECK_LOG%" 2>&1
set "ENVCHECK_RC=!errorlevel!"
if not "!ENVCHECK_RC!"=="0" (
  type "%ENVCHECK_LOG%"
  del "%ENVCHECK_LOG%" >nul 2>&1
  echo Vantage not started: sim's Python environment sim:sim is not ready ^(see Reason / Fix / Run above^).
  exit /b 1
)
del "%ENVCHECK_LOG%" >nul 2>&1
if not exist "%SIM_ENV_PY%" (
  echo Reason: setup reported sim:sim ready, but %SIM_ENV_PY% does not exist.
  echo Fix:    recreate sim's environment with setup, then retry.
  echo Run:    cd /d "%~dp0" ^&^& setup.bat --python-env sim:sim
  exit /b 1
)
REM Quotes embedded IN the value (not wrapped around %PYCMD% at the call
REM site below): the lesson from the old PATH fallback still holds -- a bare,
REM PATH-resolved name like `py` must reach CreateProcess unquoted (quoting it
REM makes PowerShell's own child-process invocation fail to create the
REM process, verified live; cmd.exe alone tolerates it), while a real path
REM that might contain spaces, like this env's python.exe, needs its quotes.
set "PYCMD="%SIM_ENV_PY%""

REM A bare command name must reach CreateProcess UNQUOTED -- see the comment
REM on PYCMD above. `%PYCMD%` is deliberately not wrapped in quotes here.
if "%*"=="" (
  %PYCMD% "%~dp0scripts\gui.py"
  exit /b !errorlevel!
)

if /i "%~1"=="--help" goto :usage
if /i "%~1"=="-h"     goto :usage
if /i "%~1"=="/?"     goto :usage

%PYCMD% "%~dp0scripts\vantage_native.py" %*
exit /b %errorlevel%

:usage
echo Usage: vantage.bat                      ^(no arguments^) open the launcher GUI
echo        vantage.bat [recording.mcap] [--plugin-root ^<root^>] [--project NAME]
echo                    [--pipeline ^<pipeline.yaml^> --search ^<dll dir^> --config ^<config path^>]
echo.
echo   e.g. vantage.bat ..\df\tests\carla_testruns\aeb\aeb_canonical_10mps_30m.mcap
echo          --pipeline ..\df\sim\pipelines\df_only.yaml
echo          --search ..\df\build-sil-vs2026\src\platform\df_sil\Release
echo          --config ..\df\build-sil-vs2026\src\platform\df_sil\Release\config
echo          --plugin-root ..\df\build-sil_viz-vs2026\src\platform\df_viz\Release
echo.
echo   This drives the real vantage_app.exe ^(WP-34^). --plugin-root wants a
echo   component's own DEPLOYED VIZ build directory here ^(e.g.
echo   ..\df\build-sil_viz-vs2026\src\platform\df_viz\Release, carrying
echo   df_viz.dll^) -- NOT the SIL/compute build ^(df_sil.dll has no viz ABI to
echo   load and the window never paints^). The launcher GUI's own plug-in-root
echo   check tells you which kind you picked before you launch.
echo   --preset/--at/--workspace/--version and a bare recording with no
echo   --pipeline have no native equivalent yet and refuse with a named
echo   error; see scripts\vantage_native.py's own top note.
exit /b 0
