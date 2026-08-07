@echo off
setlocal EnableExtensions
cd /d "%~dp0"

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
  echo No recording given -- opening Vantage's own start page ^(recent files, Open Recording..., Probe a Library...^).
  echo Usage: vantage.bat [recording.mcap] [--plugin-root ^<component checkout^>] [--project NAME] [--preset NAME] [--at SECONDS]
  echo                    [--pipeline ^<pipeline.yaml^> --search ^<dll dir^> --config ^<config path^>]
  echo   e.g. vantage.bat C:\path\to\run.mcap --plugin-root ..\df\build-sil-vs2026\src\platform\df_sil\Release
  echo   e.g. vantage.bat C:\path\to\run.mcap --pipeline my_pipeline.yaml --search C:\path\to\dlls
  echo.
  echo   --plugin-root: point it at the component's BUILT LIBRARY DIRECTORY
  echo   ^(e.g. ..\df\build-sil-vs2026\src\platform\df_sil\Release^, which carries
  echo   both sim\ and config\^) -- the deployed copy, per R-SIM-20. A source
  echo   checkout ^(e.g. ..\df^) also still works, since that is where a plug-in
  echo   is authored. Fixed 2026-08-07 ^(AR-55^): a driving function's own
  echo   calibration reader used to read its own source tree unconditionally,
  echo   which crashed under the built-directory copy -- it now reads the SAME
  echo   config\ bundle the SUT was packed with. See sim_learn.md section 5.
)

"%PYCMD%" "%~dp0scripts\vantage.py" %*
exit /b %errorlevel%
