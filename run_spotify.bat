@echo off
setlocal enabledelayedexpansion

REM Get the directory where this batch file is located
set "SCRIPT_DIR=%~dp0"
cd /d "%SCRIPT_DIR%"

echo.
echo ===== Spotify Album Downloader and Burner (Portable Edition) =====
echo.

REM Setup WinPython directory structure
set "WINPYTHON_DIR=%SCRIPT_DIR%WinPython"
set "WINPYTHON_INSTALLER_PATH=%WINPYTHON_DIR%\winpython_installer.exe"
set "PYTHON_TARGET_DIR=%WINPYTHON_DIR%\WPy64-31011"
set "PYTHON_CMD=%PYTHON_TARGET_DIR%\python.exe"
set "PYTHON_ENV_BAT=%PYTHON_TARGET_DIR%\scripts\env.bat"


if exist "%PYTHON_CMD%" (
    echo "Using existing WinPython installation"
) else (
    echo "WinPython not found. Attempting to download and set up WinPython."

    if not exist "%WINPYTHON_DIR%" mkdir "%WINPYTHON_DIR%"
    
    echo Downloading WinPython package...
    REM Ensure the target directory for the installer executable exists
    if not exist "%WINPYTHON_DIR%" mkdir "%WINPYTHON_DIR%"
    powershell -Command "& {$ProgressPreference='SilentlyContinue'; Invoke-WebRequest -Uri 'https://github.com/winpython/winpython/releases/download/5.3.20230318/Winpython64-3.10.11.0dot.exe' -OutFile '%WINPYTHON_INSTALLER_PATH%'}"
    
    if not exist "%WINPYTHON_INSTALLER_PATH%" (
        echo ERROR: WinPython download failed. Please check your internet connection and the URL.
        pause
        exit /b 1
    )
    
    echo Extracting WinPython (this may take a few minutes)...
    REM Ensure the target directory for extraction exists
    REM The -o parameter of the WinPython installer specifies where its contents are extracted.
    REM If WPy64-31011 is the desired folder name for the python installation, it should be the target.
    if not exist "%PYTHON_TARGET_DIR%" mkdir "%PYTHON_TARGET_DIR%"
    start /wait "" "%WINPYTHON_INSTALLER_PATH%" -y -o"%PYTHON_TARGET_DIR%"
    
    if exist "%WINPYTHON_INSTALLER_PATH%" del "%WINPYTHON_INSTALLER_PATH%"
    
    if not exist "%PYTHON_CMD%" (
        echo ERROR: WinPython extraction failed or Python executable not found at expected location: %PYTHON_CMD%
        echo Please check the WinPython installer behavior and script paths.
        pause
        exit /b 1
    )
    echo WinPython setup complete.
)

REM Activate WinPython environment
if not exist "%PYTHON_ENV_BAT%" (
    echo ERROR: WinPython environment script not found: %PYTHON_ENV_BAT%
    pause
    exit /b 1
)
call "%PYTHON_ENV_BAT%" >nul 2>&1
echo WinPython environment activated.

REM Create portable directories
set "PORTABLE_DIR=%SCRIPT_DIR%PortableData"
set "DOWNLOADS_DIR=%PORTABLE_DIR%\Downloads"
set "MUSIC_DIR=%PORTABLE_DIR%\Music"

if not exist "%PORTABLE_DIR%" mkdir "%PORTABLE_DIR%"
if not exist "%DOWNLOADS_DIR%" mkdir "%DOWNLOADS_DIR%"
if not exist "%MUSIC_DIR%" mkdir "%MUSIC_DIR%"

REM Prepare paths for Python -c commands (escape backslashes)
set "ESCAPED_PORTABLE_CONFIG_PATH=%PORTABLE_DIR:\=\\%\\config.json"
set "ESCAPED_MUSIC_DIR=%MUSIC_DIR:\=\\%"
set "ESCAPED_CDBURNERXP_PATH=%DOWNLOADS_DIR:\=\\%\\CDBurnerXP\\cdbxpcmd.exe"

REM Create and update portable config
set "PORTABLE_CONFIG_FILE=%PORTABLE_DIR%\config.json"

if exist "config.json" (
    if not exist "%PORTABLE_CONFIG_FILE%" (
        echo Creating portable configuration from template...
        copy config.json "%PORTABLE_CONFIG_FILE%" >nul
    )
    
    REM Update paths in portable config only if it exists
    if exist "%PORTABLE_CONFIG_FILE%" (
        echo Updating download directory in portable config...
        python -c "import json; cfg_path='%ESCAPED_PORTABLE_CONFIG_PATH%'; data=None; with open(cfg_path, 'r') as f: data=json.load(f); data['download_dir']='%ESCAPED_MUSIC_DIR%'; with open(cfg_path, 'w') as f: json.dump(data, f, indent=4);"
        if %errorlevel% neq 0 ( echo WARNING: Failed to update download_dir in config.json & pause )
    ) else (
        echo WARNING: Portable config file not found at %PORTABLE_CONFIG_FILE%. Cannot update paths.
    )
) else (
    echo WARNING: Base config.json not found in script directory. Portable config might be incomplete or missing.
)

REM Setup CDBurnerXP
if not exist "%DOWNLOADS_DIR%\CDBurnerXP\cdbxpcmd.exe" (
    echo Downloading portable CDBurnerXP...
    
    powershell -Command "& {$ProgressPreference='SilentlyContinue'; Invoke-WebRequest -Uri 'https://archive.org/download/cdburnerxp-4.5.8.7128-portable-version-windows-x86-64/CDBurnerXP-x64-4.5.8.7128.zip' -OutFile '%DOWNLOADS_DIR%\CDBurnerXP.zip'}"
    
    if not exist "%DOWNLOADS_DIR%\CDBurnerXP.zip" (
        echo ERROR: CDBurnerXP download failed.
        pause
    ) else (
        echo Extracting CDBurnerXP...
        powershell -Command "Expand-Archive -Path '%DOWNLOADS_DIR%\CDBurnerXP.zip' -DestinationPath '%DOWNLOADS_DIR%\CDBurnerXP' -Force"
        del "%DOWNLOADS_DIR%\CDBurnerXP.zip"
        
        REM Update CDBurnerXP path in config only if config file and CDBurnerXP exist
        if exist "%PORTABLE_CONFIG_FILE%" (
            if exist "%DOWNLOADS_DIR%\CDBurnerXP\cdbxpcmd.exe" (
                echo Updating CDBurnerXP path in portable config...
                python -c "import json; cfg_path='%ESCAPED_PORTABLE_CONFIG_PATH%'; data=None; with open(cfg_path, 'r') as f: data=json.load(f); data.setdefault('burn_settings', {})['cdburnerxp_path']='%ESCAPED_CDBURNERXP_PATH%'; with open(cfg_path, 'w') as f: json.dump(data, f, indent=4);"
                if %errorlevel% neq 0 ( echo WARNING: Failed to update cdburnerxp_path in config.json & pause )
            ) else (
                echo WARNING: CDBurnerXP command not found after extraction. Path not updated in config.
            )
        ) else (
            echo WARNING: Portable config file not found. CDBurnerXP path not updated.
        )
    )
)

REM Check and install required packages
if exist "requirements.txt" (
    echo Checking required packages...
    python -m pip install -r requirements.txt
    if %errorlevel% neq 0 (
        echo WARNING: Some packages may not have installed correctly from requirements.txt.
        echo Please ensure 'spotipy', 'pywin32', and 'comtypes' are installable/installed for full functionality.
        pause
    ) else (
        echo Required packages check/installation complete.
    )
) else (
    echo WARNING: requirements.txt not found. Skipping package installation.
    echo Ensure 'spotipy', 'pywin32', and 'comtypes' are installed manually in the WinPython env if needed.
    pause
)

REM Setup environment variables file
if not exist "%PORTABLE_DIR%\.env" (
    if exist ".env" (
        copy ".env" "%PORTABLE_DIR%\.env" >nul
        echo Using existing Spotify API credentials.
    ) else (
        echo Creating default .env file
        echo SPOTIPY_CLIENT_ID=your_client_id> "%PORTABLE_DIR%\.env"
        echo SPOTIPY_CLIENT_SECRET=your_client_secret>> "%PORTABLE_DIR%\.env"
        echo # You'll need to edit this file with your Spotify API credentials>> "%PORTABLE_DIR%\.env"
        echo Default .env created. Please edit %PORTABLE_DIR%\.env with your Spotify API credentials.
    )
)

REM Set environment variables for the application
set "SPOTIFY_DOWNLOADER_CONFIG=%PORTABLE_CONFIG_FILE%"
set "SPOTIFY_DOWNLOADER_PORTABLE=1"
set "DOTENV_PATH=%PORTABLE_DIR%\.env"

echo.
echo Starting Spotify Album Downloader and Burner
echo (If you see a 'Terminal size too small' error, please enlarge your terminal window and re-run)
echo.

REM Run the application
python spotify_burner.py --config "%PORTABLE_CONFIG_FILE%" %*

echo.
echo Spotify Album Downloader and Burner has exited.
pause