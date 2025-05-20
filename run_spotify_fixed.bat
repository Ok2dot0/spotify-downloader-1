@echo off
setlocal

echo ===== Spotify Album Downloader and Burner (Fixed Edition) =====

set "SCRIPT_DIR=%~dp0"
cd /d "%SCRIPT_DIR%"

REM Set paths correctly
set "WINPYTHON_DIR=%SCRIPT_DIR%WinPython"
set "PYTHON_VERSION_SUBDIR=WPy64-31330"
set "PYTHON_TARGET_DIR=%WINPYTHON_DIR%\%PYTHON_VERSION_SUBDIR%"
set "PYTHON_CMD=%PYTHON_TARGET_DIR%\python\python.exe"
set "PYTHON_ENV_BAT=%PYTHON_TARGET_DIR%\scripts\env.bat"
set "WINPYTHON_DOWNLOAD_URL=https://github.com/winpython/winpython/releases/download/15.3.20250425final/Winpython64-3.13.3.0dot.zip"
set "WINPYTHON_ZIP=%SCRIPT_DIR%Winpython64-3.13.3.0dot.zip"

REM Check if WinPython exists, download if not
if not exist "%PYTHON_CMD%" (
    echo WinPython not found. Attempting to download and install...
    
    REM Create WinPython directory if it doesn't exist
    if not exist "%WINPYTHON_DIR%" mkdir "%WINPYTHON_DIR%"
    
    REM Download WinPython using PowerShell
    echo Downloading WinPython from %WINPYTHON_DOWNLOAD_URL%
    powershell -Command "& {[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12; Invoke-WebRequest -Uri '%WINPYTHON_DOWNLOAD_URL%' -OutFile '%WINPYTHON_ZIP%'}"
    
    if not exist "%WINPYTHON_ZIP%" (
        echo Failed to download WinPython.
        pause
        exit /b 1
    )
    
    echo Download complete. Extracting...
    
    REM Extract using PowerShell
    powershell -Command "& {Expand-Archive -Path '%WINPYTHON_ZIP%' -DestinationPath '%WINPYTHON_DIR%' -Force}"
    
    REM Clean up the zip file
    if exist "%WINPYTHON_ZIP%" del "%WINPYTHON_ZIP%"
    
    REM Verify extraction was successful
    if exist "%PYTHON_CMD%" (
        echo WinPython successfully installed.
    ) else (
        echo Failed to extract WinPython properly.
        echo Please download and install WinPython manually.
        pause
        exit /b 1
    )
)

REM Verify Python exists
if exist "%PYTHON_CMD%" (
    echo Python found: %PYTHON_CMD%
) else (
    echo ERROR: Python not found at %PYTHON_CMD%
    echo Installation failed. Please check your installation.
    pause
    exit /b 1
)

REM Activate Python environment
call "%PYTHON_ENV_BAT%" >nul 2>&1

REM Update pip
echo Updating pip...
"%PYTHON_CMD%" -m pip install --upgrade pip


REM Install required packages
echo Installing required packages...
"%PYTHON_CMD%" -m pip install -r requirements.txt


REM Set up directories
set "PORTABLE_DIR=%SCRIPT_DIR%PortableData"
set "DOWNLOADS_DIR=%PORTABLE_DIR%\Downloads"
set "MUSIC_DIR=%PORTABLE_DIR%\Music"
set "PORTABLE_CONFIG_FILE=%PORTABLE_DIR%\config.json"

REM Create directories if needed
if not exist "%PORTABLE_DIR%" mkdir "%PORTABLE_DIR%"
if not exist "%DOWNLOADS_DIR%" mkdir "%DOWNLOADS_DIR%"
if not exist "%MUSIC_DIR%" mkdir "%MUSIC_DIR%"

REM Copy config if needed
if exist "config.json" if not exist "%PORTABLE_CONFIG_FILE%" (
    echo Creating portable configuration
    copy config.json "%PORTABLE_CONFIG_FILE%" >nul
)

REM Update config
if exist "%PORTABLE_CONFIG_FILE%" (
    echo Updating configuration
    "%PYTHON_CMD%" -c "import json; cfg=r'%PORTABLE_CONFIG_FILE%'; music_dir=r'%MUSIC_DIR%'; f = open(cfg, 'r'); data=json.load(f); f.close(); data['download_dir']=music_dir; f = open(cfg, 'w'); json.dump(data,f,indent=4); f.close()"
)

REM Setup environment variables
set "SPOTIFY_DOWNLOADER_CONFIG=%PORTABLE_CONFIG_FILE%"
set "SPOTIFY_DOWNLOADER_PORTABLE=1"
set "DOTENV_PATH=%PORTABLE_DIR%\.env"

REM Setup .env if needed
if not exist "%PORTABLE_DIR%\.env" (
    if exist ".env" (
        copy ".env" "%PORTABLE_DIR%\.env" >nul
        echo Using existing Spotify API credentials.
    ) else (
        echo Creating default .env file
        (
            echo SPOTIPY_CLIENT_ID=your_client_id
            echo SPOTIPY_CLIENT_SECRET=your_client_secret
        )> "%PORTABLE_DIR%\.env"
        echo Please edit %PORTABLE_DIR%\.env with your Spotify API credentials.
    )
)

echo.
echo Starting Spotify Album Downloader and Burner...
echo.

"%PYTHON_CMD%" spotify_burner.py

echo.
echo Spotify Album Downloader and Burner has exited.
pause
