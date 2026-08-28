@echo off
setlocal EnableExtensions EnableDelayedExpansion
cd /d "%~dp0"

REM Vantage entry point.
REM   vantage.bat                -> the LAUNCHER GUI (scripts\gui.py), which
REM                                 picks the recording and the plug-in root,
REM                                 validates them, and shows the command it
REM                                 will run before running it. Builds a
REM                                 NATIVE (scripts\vantage_native.py) command
REM                                 by default; a checkbox switches it to the
REM                                 legacy Python viewer.
REM   vantage.bat <args...>      -> scripts\vantage_native.py -- the real
REM                                 vantage_app.exe (WP-34, SM-11), not the
REM                                 retiring Python scene/render/player
REM                                 (SM-12). Same argument grammar as before
REM                                 (vantage_native.py reuses vantage.py's own
REM                                 build_parser()); an arg/mode the native
REM                                 host genuinely cannot serve refuses with a
REM                                 named error, never a silent drop.
REM   vantage.bat --legacy [args...] -> straight through to scripts\gui.py /
REM                                 scripts\vantage.py, exactly as before this
REM                                 pass. SM-12's deletion of the Python
REM                                 scene/render/player implementation is a
REM                                 separate, later, separately-gated decision
REM                                 -- this flag is what keeps it reachable
REM                                 until then.
REM
REM The launcher is Tkinter (stdlib) on purpose -- it must start on an install
REM with no "viewer" extra so it can SAY so, instead of dying with an
REM ImportError on the one screen whose job is getting you running.

set "PYCMD="
if exist "%~dp0.venv\Scripts\python.exe" (
  REM Quotes embedded IN the value (not wrapped around %PYCMD% at the call
  REM site below) -- a bare command name like `py` must reach CreateProcess
  REM unquoted (quoting a bare, PATH-resolved name like "py" makes PowerShell's
  REM own child-process invocation fail to create the process, verified live;
  REM cmd.exe alone tolerates it, PowerShell does not), while a real path
  REM that might contain spaces (this venv one) still needs its own quotes.
  set "PYCMD="%~dp0.venv\Scripts\python.exe""
) else (
  where py >nul 2>&1
  if not errorlevel 1 (
    py -3 -c "" >nul 2>&1
    if not errorlevel 1 set "PYCMD=py -3"
  )
  REM Fallback to unversioned py/python only if -3 isn't resolvable -- prefer
  REM -3 because PowerShell's own child-process invocation of a bare,
  REM unversioned `py <script>.py` can fail (CreateProcess error) on machines
  REM where it works fine from a real cmd.exe window; `py -3` sidesteps
  REM py.exe's own auto-select path entirely and has been verified to work
  REM from both.
  if not defined PYCMD (
    where py >nul 2>&1
    if not errorlevel 1 (
      py -c "" >nul 2>&1
      if not errorlevel 1 set "PYCMD=py"
    )
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
  echo Vantage needs Python to run its launcher. --legacy additionally needs PySide6
  echo ^(the "viewer" extra^): pip install -e ".[viewer,figures]"
  exit /b 1
)

REM `shift` does NOT remove an argument from `%*` in this cmd.exe (verified
REM live) -- so `--legacy` is stripped out of a %*-derived REST string
REM instead. Delayed expansion (!REST!, not %REST%) is required here: a
REM `%REST:~...%` substring op on an UNDEFINED variable inside a chained
REM `if ... if ... set` errors at PARSE time regardless of which branch
REM would actually run (verified live, the "syntax of the command is
REM incorrect" failure) -- delayed expansion defers the substitution to
REM execution time, after the guarding `if`s have already short-circuited.
set "REST=%*"
set "LEGACY="
if /i "%~1"=="--legacy" (
  set "LEGACY=1"
  set "REST=!REST:*--legacy=!"
)

if "!REST!"=="" (
  if defined LEGACY (
    %PYCMD% "%~dp0scripts\gui.py" --legacy
  ) else (
    %PYCMD% "%~dp0scripts\gui.py"
  )
  exit /b !errorlevel!
)

if defined LEGACY (set "FIRSTREAL=%~2") else (set "FIRSTREAL=%~1")
if /i "!FIRSTREAL!"=="--help" goto :usage
if /i "!FIRSTREAL!"=="-h"     goto :usage
if /i "!FIRSTREAL!"=="/?"     goto :usage

if defined LEGACY (
  %PYCMD% "%~dp0scripts\vantage.py" !REST!
) else (
  %PYCMD% "%~dp0scripts\vantage_native.py" !REST!
)
exit /b %errorlevel%

:usage
echo Usage: vantage.bat                      ^(no arguments^) open the launcher GUI
echo        vantage.bat [recording.mcap] [--plugin-root ^<root^>] [--project NAME]
echo                    [--pipeline ^<pipeline.yaml^> --search ^<dll dir^> --config ^<config path^>]
echo        vantage.bat --legacy [args...]    same grammar, routed to the retiring
echo                                           Python viewer instead ^(SM-12, gated
echo                                           separately -- see modules/sim/CLAUDE.md^)
echo.
echo   e.g. vantage.bat ..\df\tests\carla_testruns\aeb\aeb_canonical_10mps_30m.mcap
echo          --pipeline ..\df\sim\pipelines\df_only.yaml
echo          --search ..\df\build-sil-vs2026\src\platform\df_sil\Release
echo          --config ..\df\build-sil-vs2026\src\platform\df_sil\Release\config
echo          --plugin-root ..\df\build-sil_viz-vs2026\src\platform\df_viz\Release
echo.
echo   By default this drives the real vantage_app.exe ^(WP-34^), not the Python
echo   scene/render/player. --plugin-root wants a component's own DEPLOYED VIZ
echo   build directory here ^(e.g. ..\df\build-sil_viz-vs2026\src\platform\df_viz\
echo   Release, carrying df_viz.dll^) -- NOT the SIL/compute build ^(df_sil.dll
echo   has no viz ABI to load and the window never paints^). The launcher GUI's
echo   own plug-in-root check tells you which kind you picked before you launch.
echo   --preset/--at/--workspace/--version and a bare recording with no
echo   --pipeline have no native equivalent yet and refuse with a named error
echo   pointing at --legacy; see scripts\vantage_native.py's own top note.
exit /b 0
