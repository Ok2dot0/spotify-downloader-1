@echo off
setlocal EnableDelayedExpansion

echo ===== Spotify Album Downloader and Burner (Fixed Edition) =====

set "SCRIPT_DIR=%~dp0"
cd /d "%SCRIPT_DIR%"

REM --- Initial Dynamic Paths ---
set "WINPYTHON_DIR=%SCRIPT_DIR%WinPython"
set "CDBURNER_DIR=%SCRIPT_DIR%CDBurnerXP"

REM --- Component URLs and ZIP filenames ---
set "WINPYTHON_DOWNLOAD_URL=https://github.com/winpython/winpython/releases/download/15.3.20250425final/Winpython64-3.13.3.0dot.zip"
set "WINPYTHON_ZIP_FILENAME=Winpython64-3.13.3.0dot.zip"
set "WINPYTHON_ZIP_FULL_PATH=%SCRIPT_DIR%%WINPYTHON_ZIP_FILENAME%"

REM 1. Correct CDBurnerXP Download URL
set "CDBURNER_DOWNLOAD_URL=https://archive.org/download/cdburnerxp-4.5.8.7128-portable-version-windows-x86-64/CDBURNERXP-x64-4.5.8.7128.zip"
set "CDBURNER_ZIP_FILENAME=CDBURNERXP-x64-4.5.8.7128.zip"
set "CDBURNER_ZIP_FULL_PATH=%SCRIPT_DIR%%CDBURNER_ZIP_FILENAME%"

REM --- Dynamic Python Path Detection & Setup ---
set "PYTHON_CMD="
set "PYTHON_ENV_BAT="

REM 4. Idempotency: Try to find an existing valid Python setup first
if exist "%WINPYTHON_DIR%" (
    set "FOUND_PYTHON_EXE_PRECHECK="
    for /r "%WINPYTHON_DIR%" %%F in (python.exe) do (
        if not defined FOUND_PYTHON_EXE_PRECHECK (
            REM Basic check to ensure it's likely from a WinPython-like structure
            echo "%%~dpF" | findstr /I /L /C:"python" >nul
            if not errorlevel 1 (
                 set "TEMP_PYTHON_CMD_PRECHECK=%%F"
                 for %%P in ("!TEMP_PYTHON_CMD_PRECHECK!") do set "TEMP_PYTHON_BASE_DIR_PRECHECK=%%~dpP.."
                 set "TEMP_PYTHON_ENV_BAT_PRECHECK=!TEMP_PYTHON_BASE_DIR_PRECHECK!\scripts\env.bat"
                 if exist "!TEMP_PYTHON_ENV_BAT_PRECHECK!" (
                     set "PYTHON_CMD=!TEMP_PYTHON_CMD_PRECHECK!"
                     set "PYTHON_ENV_BAT=!TEMP_PYTHON_ENV_BAT_PRECHECK!"
                     set "FOUND_PYTHON_EXE_PRECHECK=1"
                     echo Found existing valid Python installation.
                     echo   PYTHON_CMD: !PYTHON_CMD!
                     echo   PYTHON_ENV_BAT: !PYTHON_ENV_BAT!
                 )
            )
        )
    )
)

REM If Python not found or verified, proceed with full setup
REM 3. Robust Python Path Detection (PYTHON_VERSION_SUBDIR removed)
if not defined PYTHON_CMD (
    echo WinPython not found or not fully configured. Attempting to download and set up...
    
    if not exist "%WINPYTHON_DIR%" mkdir "%WINPYTHON_DIR%"
    
    echo Downloading WinPython from %WINPYTHON_DOWNLOAD_URL%
    powershell -Command "& {[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12; Invoke-WebRequest -Uri '%WINPYTHON_DOWNLOAD_URL%' -OutFile '%WINPYTHON_ZIP_FULL_PATH%'}"
    REM 2. Add ErrorLevel Checks
    if errorlevel 1 (
        echo ERROR: Failed to download WinPython. PowerShell exit code: %errorlevel%
        pause
        exit /b 1
    )
    if not exist "%WINPYTHON_ZIP_FULL_PATH%" (
        echo ERROR: WinPython ZIP file not found after download attempt.
        pause
        exit /b 1
    )
    
    echo WinPython Download complete. Extracting...
    powershell -Command "& {Expand-Archive -Path '%WINPYTHON_ZIP_FULL_PATH%' -DestinationPath '%WINPYTHON_DIR%' -Force}"
    REM 2. Add ErrorLevel Checks
    if errorlevel 1 (
        echo ERROR: Failed to extract WinPython. PowerShell exit code: %errorlevel%
        pause
        exit /b 1
    )
    if exist "%WINPYTHON_ZIP_FULL_PATH%" del "%WINPYTHON_ZIP_FULL_PATH%"
    
    REM 3. Robust Python Path Detection (Search for python.exe)
    set "FOUND_PYTHON_EXE_POST_EXTRACT="
    for /r "%WINPYTHON_DIR%" %%F in (python.exe) do (
        if not defined FOUND_PYTHON_EXE_POST_EXTRACT (
            REM Basic check for plausible Python path
            echo "%%~dpF" | findstr /I /L /C:"python" >nul
            if not errorlevel 1 (
                 set "PYTHON_CMD=%%F"
                 for %%P in ("!PYTHON_CMD!") do set "PYTHON_BASE_DIR=%%~dpP.."
                 set "PYTHON_ENV_BAT=!PYTHON_BASE_DIR!\scripts\env.bat"
                 set "FOUND_PYTHON_EXE_POST_EXTRACT=1"
                 echo Found Python after extraction:
                 echo   PYTHON_CMD: !PYTHON_CMD!
                 echo   PYTHON_ENV_BAT: !PYTHON_ENV_BAT!
            )
        )
    )
    if not defined FOUND_PYTHON_EXE_POST_EXTRACT (
        echo ERROR: python.exe not found in %WINPYTHON_DIR% after extraction.
        pause
        exit /b 1
    )
    if not exist "!PYTHON_ENV_BAT!" (
        echo ERROR: Python env.bat not found at expected path !PYTHON_ENV_BAT!.
        echo Searched relative to !PYTHON_CMD!. Check WinPython package structure.
        pause
        exit /b 1
    )
    echo WinPython successfully configured.
)

REM Final verification for Python paths (should be set by now)
if not defined PYTHON_CMD (
    echo CRITICAL ERROR: Python command (PYTHON_CMD) could not be determined after setup attempt.
    pause
    exit /b 1
)
if not exist "!PYTHON_CMD!" (
    echo CRITICAL ERROR: PYTHON_CMD points to a non-existent file: !PYTHON_CMD!
    pause
    exit /b 1
)
if not defined PYTHON_ENV_BAT (
    echo CRITICAL ERROR: Python environment script (PYTHON_ENV_BAT) could not be determined.
    pause
    exit /b 1
)
if not exist "!PYTHON_ENV_BAT!" (
    echo CRITICAL ERROR: PYTHON_ENV_BAT points to a non-existent file: !PYTHON_ENV_BAT!
    pause
    exit /b 1
)

REM --- CDBurnerXP Setup ---
set "CDBURNER_EXE="
REM 4. Idempotency: Search for existing cdbxpp.exe or cdbxpcmd.exe
if exist "%CDBURNER_DIR%" (
    for /r "%CDBURNER_DIR%" %%F in (cdbxpp.exe cdbxpcmd.exe) do (
        if not defined CDBURNER_EXE if exist "%%F" (
            set "CDBURNER_EXE=%%F"
        )
    )
)

if not defined CDBURNER_EXE (
    echo CDBurnerXP not found. Attempting to download and extract...
    if not exist "%CDBURNER_DIR%" mkdir "%CDBURNER_DIR%"
    
    echo Downloading CDBurnerXP from %CDBURNER_DOWNLOAD_URL%
    powershell -Command "& {[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12; Invoke-WebRequest -Uri '%CDBURNER_DOWNLOAD_URL%' -OutFile '%CDBURNER_ZIP_FULL_PATH%'}"
    REM 2. Add ErrorLevel Checks
    if errorlevel 1 (
        echo ERROR: Failed to download CDBurnerXP. PowerShell exit code: %errorlevel%
        pause
        exit /b 1
    )
    if not exist "%CDBURNER_ZIP_FULL_PATH%" (
        echo ERROR: CDBurnerXP ZIP file not found after download attempt.
        pause
        exit /b 1
    )
    
    echo CDBurnerXP Download complete. Extracting...
    powershell -Command "& {Expand-Archive -Path '%CDBURNER_ZIP_FULL_PATH%' -DestinationPath '%CDBURNER_DIR%' -Force}"
    REM 2. Add ErrorLevel Checks
    if errorlevel 1 (
        echo ERROR: Failed to extract CDBurnerXP. PowerShell exit code: %errorlevel%
        pause
        exit /b 1
    )
    if exist "%CDBURNER_ZIP_FULL_PATH%" del "%CDBURNER_ZIP_FULL_PATH%"
    
    REM Search again after extraction
    set "FOUND_CDB_EXE_AFTER_EXTRACT="
    for /r "%CDBURNER_DIR%" %%F in (cdbxpp.exe cdbxpcmd.exe) do (
        if not defined FOUND_CDB_EXE_AFTER_EXTRACT if exist "%%F" (
            set "CDBURNER_EXE=%%F"
            set "FOUND_CDB_EXE_AFTER_EXTRACT=1"
        )
    )
    if not defined FOUND_CDB_EXE_AFTER_EXTRACT (
        echo ERROR: Failed to find cdbxpp.exe or cdbxpcmd.exe in %CDBURNER_DIR% after extraction.
        pause
        exit /b 1
    )
    echo CDBurnerXP successfully set up: !CDBURNER_EXE!
) else (
    echo CDBurnerXP found: !CDBURNER_EXE!
)

REM Activate Python environment
call "!PYTHON_ENV_BAT!" >nul 2>&1
if errorlevel 1 (
    echo WARNING: Calling PYTHON_ENV_BAT returned an error code: %errorlevel%.
    echo Python environment might be incomplete.
)

REM Update pip
echo Updating pip...
"!PYTHON_CMD!" -m pip install --upgrade pip
REM 2. Add ErrorLevel Checks
if errorlevel 1 (
    echo ERROR: Failed to upgrade pip. Pip exit code: %errorlevel%
    pause
    exit /b 1
)

REM Check if requirements.txt exists, create if not
REM 5. General Script Improvements: Creation of requirements.txt
if not exist "%SCRIPT_DIR%requirements.txt" (
    echo Creating requirements.txt in %SCRIPT_DIR% ...
    (
        echo spotipy
        echo spotdl
        echo rich
        echo colorama
        echo python-dotenv
    ) > "%SCRIPT_DIR%requirements.txt"
)

REM Install required packages
echo Installing required packages from %SCRIPT_DIR%requirements.txt...
"!PYTHON_CMD!" -m pip install -r "%SCRIPT_DIR%requirements.txt"
REM 2. Add ErrorLevel Checks
if errorlevel 1 (
    echo ERROR: Failed to install Python packages from requirements.txt. Pip exit code: %errorlevel%
    pause
    exit /b 1
)

REM Set up directories
set "PORTABLE_DIR=%SCRIPT_DIR%PortableData"
set "DOWNLOADS_DIR=%PORTABLE_DIR%\Downloads"
set "MUSIC_DIR=%PORTABLE_DIR%\Music"
set "PORTABLE_CONFIG_FILE=%PORTABLE_DIR%\config.json"

REM Create directories if needed
if not exist "%PORTABLE_DIR%" mkdir "%PORTABLE_DIR%"
if not exist "%DOWNLOADS_DIR%" mkdir "%DOWNLOADS_DIR%"
if not exist "%MUSIC_DIR%" mkdir "%MUSIC_DIR%"

REM Copy default config if portable one doesn't exist
if exist "%SCRIPT_DIR%config.json" if not exist "%PORTABLE_CONFIG_FILE%" (
    echo Creating portable configuration from default.
    copy "%SCRIPT_DIR%config.json" "%PORTABLE_CONFIG_FILE%" >nul
)

REM Update config with dynamic music directory
REM 5. General Script Improvements: Robust handling of inline Python script
if exist "%PORTABLE_CONFIG_FILE%" (
    echo Updating configuration for download directory to: %MUSIC_DIR%
    set "TEMP_PYTHON_UPDATE_SCRIPT=%SCRIPT_DIR%__temp_update_cfg.py"
    (
        echo import json
        echo import os
        echo cfg_path=os.environ['PORTABLE_CONFIG_FILE']
        echo music_path=os.environ['MUSIC_DIR'].replace('\\', '\\\\') # Escape backslashes for JSON string
        echo data=None
        echo print(f'Updating config file: {cfg_path}')
        echo print(f'Setting download_dir to: {music_path}')
        echo try:
        echo     with open(cfg_path, 'r+', encoding='utf-8') as f:
        echo         data=json.load(f)
        echo         data['download_dir']=music_path
        echo         f.seek(0)
        echo         json.dump(data,f,indent=4)
        echo         f.truncate()
        echo     print('Config updated successfully.')
        echo except Exception as e:
        echo     print(f'Error updating config: {e}')
        echo     import sys
        echo     sys.exit(1)
    ) > "!TEMP_PYTHON_UPDATE_SCRIPT!"
    "!PYTHON_CMD!" "!TEMP_PYTHON_UPDATE_SCRIPT!"
    if errorlevel 1 ( 
        echo WARNING: Failed to update download_dir in config.json using Python script. Error code: %errorlevel%
    )
    if exist "!TEMP_PYTHON_UPDATE_SCRIPT!" del "!TEMP_PYTHON_UPDATE_SCRIPT!"
)

REM Setup environment variables for Python scripts
set "SPOTIFY_DOWNLOADER_CONFIG=%PORTABLE_CONFIG_FILE%"
set "SPOTIFY_DOWNLOADER_PORTABLE=1"
set "DOTENV_PATH=%PORTABLE_DIR%\.env"
set "CDBURNERXP_PATH=!CDBURNER_EXE!"

REM Setup .env if needed
if not exist "%DOTENV_PATH%" (
    if exist "%SCRIPT_DIR%.env" (
        copy "%SCRIPT_DIR%.env" "%DOTENV_PATH%" >nul
        echo Copied existing .env to PortableData directory.
    ) else (
        echo Creating default .env file in %DOTENV_PATH%
        (
            echo SPOTIPY_CLIENT_ID=your_client_id_here
            echo SPOTIPY_CLIENT_SECRET=your_client_secret_here
        )> "%DOTENV_PATH%"
        echo Please edit %DOTENV_PATH% with your Spotify API credentials.
    )
)

REM Update config with CDBurnerXP path using the Python script
if exist "%PORTABLE_CONFIG_FILE%" (
    if exist "%SCRIPT_DIR%update_cdburnerxp_path.py" (
        echo Updating configuration with CDBurnerXP path: !CDBURNER_EXE!
        "!PYTHON_CMD!" "%SCRIPT_DIR%update_cdburnerxp_path.py"
        if errorlevel 1 (
            echo WARNING: Failed to update config with CDBurnerXP path via Python script. Error code: %errorlevel%
            echo Script might not use the correct burner.
        )
    ) else (
        echo WARNING: update_cdburnerxp_path.py script not found. Cannot update CDBurnerXP path in config automatically.
    )
)

echo.
REM 5. General Script Improvements: More informative echo messages
echo Starting Spotify Album Downloader and Burner...
echo Python Command: !PYTHON_CMD!
echo Config File: %SPOTIFY_DOWNLOADER_CONFIG%
echo CDBurnerXP Path: %CDBURNERXP_PATH%
echo.

"!PYTHON_CMD!" "%SCRIPT_DIR%spotify_burner.py"

echo.
echo Spotify Album Downloader and Burner has exited.
pause
endlocal
```
