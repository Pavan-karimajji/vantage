@echo off
setlocal EnableExtensions
cd /d "%~dp0"

REM Vantage entry point.
REM   vantage.bat                -> the LAUNCHER GUI (scripts\gui.py), which
REM                                 picks the recording and the plug-in root,
REM                                 validates them, and shows the command it
REM                                 will run before running it.
REM   vantage.bat <args...>      -> straight through to scripts\vantage.py,
REM                                 untouched. Every script, CI job and
REM                                 documented command line keeps working.
REM
REM The launcher is Tkinter (stdlib) on purpose -- it must start on an install
REM with no "viewer" extra so it can SAY so, instead of dying with an
REM ImportError on the one screen whose job is getting you running.

set "PYCMD="
if exist "%~dp0.venv\Scripts\python.exe" (
  set "PYCMD=%~dp0.venv\Scripts\python.exe"
) else (
  where py >nul 2>&1
  if not errorlevel 1 (
    set "PYCMD=py"
  ) else (
    where python >nul 2>&1
    if not errorlevel 1 set "PYCMD=python"
  )
)
if not defined PYCMD (
  echo ERROR: no Python found -- neither .venv\Scripts\python.exe nor py/python on PATH.
  echo Vantage needs PySide6 ^(the "viewer" extra^): pip install -e ".[viewer,figures]"
  exit /b 1
)

if "%~1"=="" (
  "%PYCMD%" "%~dp0scripts\gui.py"
  exit /b %errorlevel%
)

if /i "%~1"=="--help" goto :usage
if /i "%~1"=="-h"     goto :usage
if /i "%~1"=="/?"     goto :usage

"%PYCMD%" "%~dp0scripts\vantage.py" %*
exit /b %errorlevel%

:usage
echo Usage: vantage.bat                      ^(no arguments^) open the launcher GUI
echo        vantage.bat [recording.mcap] [--plugin-root ^<root^>] [--project NAME] [--preset NAME] [--at SECONDS]
echo                    [--pipeline ^<pipeline.yaml^> --search ^<dll dir^> --config ^<config path^>]
echo.
echo   e.g. vantage.bat ..\df\tests\carla_testruns\bsd\bsd_ego_lane_exit.mcap --plugin-root ..\df
echo.
echo   --plugin-root: a component's SOURCE CHECKOUT ^(e.g. ..\df^) is the
echo   verified-working form today. The deployed copy beside a built DLL
echo   ^(..\df\build-sil-vs2026\src\platform\df_sil\Release^) is what R-SIM-20
echo   asks for and currently crashes bsd.zone with a SWALLOWED error, leaving
echo   an EMPTY layer tree and no message ^(AR-61, open^). The launcher GUI
echo   inspects whichever root you pick and tells you which kind it is BEFORE
echo   you launch -- that is what it is for.
exit /b 0
