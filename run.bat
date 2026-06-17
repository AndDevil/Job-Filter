@echo off
:: Change directory to the folder where this batch file is located
cd /d "%~dp0"

echo ====================================================================
echo             Personal Job Aggregator & Tracker Runner                
echo ====================================================================
echo Working Directory: %CD%

:: Check if venv directory exists
if not exist "venv\" (
    echo [INFO] Virtual environment 'venv' not found. Creating it...
    python -m venv venv
    if errorlevel 1 (
        echo [ERROR] Failed to create virtual environment. Make sure Python is installed and added to PATH.
        pause
        exit /b 1
    )
    echo [INFO] Virtual environment created successfully.
    
    echo [INFO] Activating virtual environment...
    call venv\Scripts\activate.bat
    
    echo [INFO] Upgrading pip...
    python -m pip install --upgrade pip
    
    echo [INFO] Installing required dependencies...
    pip install -r requirements.txt
) else (
    echo [INFO] Activating virtual environment...
    call venv\Scripts\activate.bat
)

echo.
echo [INFO] Executing the job aggregation and scoring pipeline...
python job_pipeline.py
if errorlevel 1 (
    echo [WARNING] The pipeline script completed with warnings or errors.
)

echo.
set /p launch_dash="Launch tracker dashboard? (y/n): "
if /i "%launch_dash%"=="y" (
    echo [INFO] Launching Streamlit dashboard...
    streamlit run dashboard.py
) else (
    echo [INFO] Exiting runner.
)

echo.
echo ====================================================================
echo                       Aggregator Runner Finished                    
echo ====================================================================
pause
