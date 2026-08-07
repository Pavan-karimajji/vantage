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
  echo   e.g. vantage.bat C:\path\to\run.mcap --plugin-root ..\df
  echo   e.g. vantage.bat C:\path\to\run.mcap --pipeline my_pipeline.yaml --search C:\path\to\dlls
  echo.
  echo   --plugin-root: point it at the component's SOURCE CHECKOUT ^(e.g. ..\df^),
  echo   not a built library directory ^(e.g. ..\df\build-sil-vs2026\...\Release^) --
  echo   df's own bsd.py still reads its calibration relative to itself and crashes
  echo   under the built-directory copy ^(a real, scoped, documented gap in df, not
  echo   here^). See sim_learn.md section 5 if this changes.
)

"%PYCMD%" "%~dp0scripts\vantage.py" %*
exit /b %errorlevel%
