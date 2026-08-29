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

set "PYCMD="
if exist "%~dp0.venv\Scripts\python.exe" (
  set "PYCMD=%~dp0.venv\Scripts\python.exe"
) else (
  where py >nul 2>&1
  if not errorlevel 1 (
    py -c "" >nul 2>&1
    if not errorlevel 1 set "PYCMD=py"
  )
  if not defined PYCMD (
    where python >nul 2>&1
    if not errorlevel 1 (
      python -c "" >nul 2>&1
      if not errorlevel 1 set "PYCMD=python"
    )
  )
)
if not defined PYCMD (
  echo ERROR: no Python found -- neither .venv\Scripts\python.exe nor py/python on PATH.
  echo Vantage needs Python to run its launcher.
  exit /b 1
)

if "%*"=="" (
  "%PYCMD%" "%~dp0scripts\gui.py"
  exit /b !errorlevel!
)

if /i "%~1"=="--help" goto :usage
if /i "%~1"=="-h"     goto :usage
if /i "%~1"=="/?"     goto :usage

"%PYCMD%" "%~dp0scripts\vantage_native.py" %*
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
