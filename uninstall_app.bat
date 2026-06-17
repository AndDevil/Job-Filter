@echo off
:: Change directory to the folder where this batch file is located
cd /d "%~dp0"

echo ====================================================================
echo             Personal Job Aggregator Background Uninstaller          
echo ====================================================================
echo.

:: 1. Check for Administrator privileges
net session >nul 2>&1
if %errorLevel% neq 0 (
    echo [ERROR] This uninstaller must be run as Administrator.
    echo Please right-click uninstall_app.bat and select "Run as Administrator".
    echo.
    pause
    exit /b 1
)
echo [SUCCESS] Administrator privileges verified.

:: 2. Delete Windows Scheduled Tasks
echo [INFO] Deleting JobScraper_Daily task...
schtasks /delete /tn "JobScraper_Daily" /f >nul 2>&1
if errorlevel 1 (
    echo [WARNING] JobScraper_Daily task did not exist or could not be deleted.
) else (
    echo [SUCCESS] Deleted JobScraper_Daily task.
)

echo [INFO] Deleting JobScraper_Startup task...
schtasks /delete /tn "JobScraper_Startup" /f >nul 2>&1
if errorlevel 1 (
    echo [WARNING] JobScraper_Startup task did not exist or could not be deleted.
) else (
    echo [SUCCESS] Deleted JobScraper_Startup task.
)

:: 3. Remove script from Startup Folder
echo [INFO] Removing dashboard script from Startup folder...
set "STARTUP_DIR=%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup"
if exist "%STARTUP_DIR%\run_dashboard_silent.vbs" (
    del /f /q "%STARTUP_DIR%\run_dashboard_silent.vbs" >nul
    echo [SUCCESS] Removed run_dashboard_silent.vbs from Startup folder.
) else (
    echo [INFO] run_dashboard_silent.vbs was not found in Startup folder.
)

:: 4. Terminate background processes
echo [INFO] Terminating active aggregator and dashboard background processes...

:: Terminate process listening on port 8501 (Streamlit server)
set "PORT_KILLED=0"
for /f "tokens=5" %%a in ('netstat -aon ^| findstr :8501 ^| findstr LISTENING') do (
    echo [INFO] Killing process on port 8501 (PID %%a)...
    taskkill /f /pid %%a >nul 2>&1
    set "PORT_KILLED=1"
)
if "%PORT_KILLED%"=="1" (
    echo [SUCCESS] Terminated processes running on port 8501.
) else (
    echo [INFO] No active processes found on port 8501.
)

:: Double check and kill any residual pythonw.exe instances running job scripts
powershell -Command "Get-CimInstance Win32_Process -Filter \"Name = 'pythonw.exe' and (CommandLine LIKE '%%job_pipeline.py%%' or CommandLine LIKE '%%dashboard.py%%')\" | Invoke-CimMethod -MethodName Terminate" >nul 2>&1
echo [SUCCESS] Terminated any residual scraper/dashboard processes.

echo.
echo ====================================================================
echo                Background Uninstaller Completed Successfully      
echo ====================================================================
pause
