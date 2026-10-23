@echo off
setlocal
where python >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python 3.11 or newer is required. Install Python and enable its PATH option. 1>&2
    if "%~1"=="" pause
    exit /b 2
)
if not "%~1"=="" goto run
pushd "%~dp0" || exit /b 1
python "%~dp0findname.py"
set "result=%errorlevel%"
popd
echo.
pause
exit /b %result%
:run
python "%~dp0findname.py" %*
exit /b %errorlevel%
