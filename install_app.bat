@echo off
:: Change directory to the folder where this batch file is located
cd /d "%~dp0"

echo ====================================================================
echo             Personal Job Aggregator Background Installer            
echo ====================================================================
echo.

:: 1. Check for Administrator privileges
net session >nul 2>&1
if %errorLevel% neq 0 (
    echo [ERROR] This installer must be run as Administrator.
    echo Please right-click install_app.bat and select "Run as Administrator".
    echo.
    pause
    exit /b 1
)
echo [SUCCESS] Administrator privileges verified.

:: 2. Initialize/Restore Virtual Environment
echo [INFO] Verifying virtual environment...
if not exist "venv\Scripts\activate.bat" (
    if exist "venv\" (
        echo [INFO] Incomplete/corrupt virtual environment found. Cleaning it up...
        rmdir /s /q venv
    )
    echo [INFO] Creating virtual environment (venv)...
    python -m venv venv
    if errorlevel 1 (
        echo [ERROR] Failed to create virtual environment.
        pause
        exit /b 1
    )
)

:: 3. Install/Upgrade requirements
echo [INFO] Installing required dependencies (this may take a minute, running silently)...
call venv\Scripts\activate.bat
python -m pip install --upgrade pip --quiet
pip install -r requirements.txt --quiet
if errorlevel 1 (
    echo [WARNING] Standard requirements installation failed. Attempting Python 3.14+ compatibility installation...
    pip install --no-deps python-jobspy --quiet
    pip install pandas requests streamlit plotly jobhive-py[parquet] numpy beautifulsoup4 markdownify regex tls-client --quiet
)
echo [SUCCESS] Dependencies verified and installed.

:: 4. Copy Dashboard script to User Startup Folder
echo [INFO] Copying dashboard script to Windows Startup folder...
set "STARTUP_DIR=%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup"
if not exist "%STARTUP_DIR%" (
    mkdir "%STARTUP_DIR%"
)
copy /y "%~dp0run_dashboard_silent.vbs" "%STARTUP_DIR%\" >nul
if errorlevel 1 (
    echo [ERROR] Failed to copy run_dashboard_silent.vbs to Startup folder.
) else (
    echo [SUCCESS] Dashboard script copied to Startup folder.
)

:: 5. Register Scheduled Tasks in Task Scheduler
echo [INFO] Registering daily job scraper task (daily at 8:00 AM)...
schtasks /create /tn "JobScraper_Daily" /tr "wscript.exe \"%~dp0run_scraper_silent.vbs\"" /sc daily /st 08:00 /rl highest /f >nul
if errorlevel 1 (
    echo [ERROR] Failed to register JobScraper_Daily task.
) else (
    echo [SUCCESS] Registered JobScraper_Daily task.
)

echo [INFO] Registering startup job scraper task (runs on boot with 2-minute delay)...
schtasks /create /tn "JobScraper_Startup" /tr "wscript.exe \"%~dp0run_scraper_silent.vbs\"" /sc onstart /delay 0002:00 /ru SYSTEM /f >nul
if errorlevel 1 (
    echo [ERROR] Failed to register JobScraper_Startup task.
) else (
    echo [SUCCESS] Registered JobScraper_Startup task.
)

:: 6. Launch current dashboard in background
echo [INFO] Starting the dashboard runner in the background now...
wscript.exe "%~dp0run_dashboard_silent.vbs"
echo [SUCCESS] Streamlit dashboard launched. You can access it at http://localhost:8501

echo.
echo ====================================================================
echo                Background Installer Setup Completed Successfully    
echo ====================================================================
pause
