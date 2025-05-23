@echo off
REM EnableDelayedExpansion allows for variable expansion within loops using !var! syntax,
REM which is crucial for correctly handling paths and choices found/made within loops.
setlocal EnableDelayedExpansion

echo.
echo IMPORTANT: For best results, run this script from a user-writable directory 
echo (e.g., your Desktop or Documents folder, or a dedicated folder like C:\Tools).
echo If you encounter permission errors during setup (e.g., "Failed to create directory",
echo "Failed to extract", "Failed to download"), please try moving the script's
echo entire folder to such a location and run it again.
echo.

echo ===== Spotify Album Downloader and Burner (Fixed Edition) =====
echo.
echo ===== Checking Prerequisites and Initial Setup =====
echo.

REM Set SCRIPT_DIR to the directory where this batch script is located.
REM %~dp0 expands to the drive and path of the current batch script.
set "SCRIPT_DIR=%~dp0"
echo Setting up files and preparing installations from the repository at: %SCRIPT_DIR%
cd /d "%SCRIPT_DIR%"

REM --- Initial Dynamic Paths ---
REM Define base directories for WinPython and CDBurnerXP relative to the script's location.
REM These will be used for checking existing installations and for new installations.
set "WINPYTHON_DIR=%SCRIPT_DIR%WinPython"
set "CDBURNER_DIR=%SCRIPT_DIR%CDBurnerXP"

REM --- Component URLs and ZIP filenames ---
REM These URLs point to specific versions of WinPython and CDBurnerXP.
REM NOTE: These URLs may become outdated. If downloads fail, check for newer versions
REM on their respective project pages and update these URLs.
set "WINPYTHON_DOWNLOAD_URL=https://github.com/winpython/winpython/releases/download/15.3.20250425final/Winpython64-3.13.3.0dot.zip"
set "WINPYTHON_ZIP_FILENAME=Winpython64-3.13.3.0dot.zip"
set "WINPYTHON_ZIP_FULL_PATH=%SCRIPT_DIR%%WINPYTHON_ZIP_FILENAME%"

REM 1. Correct CDBurnerXP Download URL
set "CDBURNER_DOWNLOAD_URL=https://archive.org/download/cdburnerxp-4.5.8.7128-portable-version-windows-x86-64/CDBURNERXP-x64-4.5.8.7128.zip"
set "CDBURNER_ZIP_FILENAME=CDBURNERXP-x64-4.5.8.7128.zip"
set "CDBURNER_ZIP_FULL_PATH=%SCRIPT_DIR%%CDBURNER_ZIP_FILENAME%"

REM --- Dynamic Python Path Detection & Setup ---
REM Initialize variables for Python command and environment script path.
set "PYTHON_CMD="
set "PYTHON_ENV_BAT="

REM 4. Idempotency: Try to find an existing valid Python setup first
REM This section checks if a WinPython distribution already exists in the WINPYTHON_DIR.
if exist "%WINPYTHON_DIR%" (
    set "FOUND_PYTHON_EXE_PRECHECK="
    REM Search recursively for python.exe within the existing WinPython directory.
    for /r "%WINPYTHON_DIR%" %%F in (python.exe) do (
        if not defined FOUND_PYTHON_EXE_PRECHECK (
            REM Basic check to ensure it's likely from a WinPython-like structure by checking if "python" is in the path.
            echo "%%~dpF" | findstr /I /L /C:"python" >nul
            if not errorlevel 1 (
                 set "TEMP_PYTHON_CMD_PRECHECK=%%F"
                 REM Construct the path to the 'env.bat' script, typically found in 'scripts' subdir of WinPython.
                 for %%P in ("!TEMP_PYTHON_CMD_PRECHECK!") do set "TEMP_PYTHON_BASE_DIR_PRECHECK=%%~dpP.."
                 set "TEMP_PYTHON_ENV_BAT_PRECHECK=!TEMP_PYTHON_BASE_DIR_PRECHECK!\scripts\env.bat"
                 if exist "!TEMP_PYTHON_ENV_BAT_PRECHECK!" (
                     set "PYTHON_CMD=!TEMP_PYTHON_CMD_PRECHECK!"
                     set "PYTHON_ENV_BAT=!TEMP_PYTHON_ENV_BAT_PRECHECK!"
                     set "FOUND_PYTHON_EXE_PRECHECK=1"
                     echo Found existing WinPython installation. Skipping download and setup.
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
    echo.
    echo --------------------------------------------------------------------
    echo.
    echo --- WinPython Installation ---
    echo WinPython not found. Proceeding with download and setup...
    
    if not exist "%WINPYTHON_DIR%" (
        mkdir "%WINPYTHON_DIR%"
        if errorlevel 1 (
            echo ERROR: Failed to create directory %WINPYTHON_DIR%. Check permissions.
            echo Ensure you are running this script from a user-writable location.
            pause
            exit /b 1
        )
    )
    
    echo Downloading WinPython from %WINPYTHON_DOWNLOAD_URL%
    REM Use PowerShell to download the file, attempting to bypass older TLS issues by setting SecurityProtocol to Tls12.
    powershell -Command "& {[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12; Invoke-WebRequest -Uri '%WINPYTHON_DOWNLOAD_URL%' -OutFile '%WINPYTHON_ZIP_FULL_PATH%'}"
    REM 2. Add ErrorLevel Checks
    if errorlevel 1 (
        echo ERROR: Failed to download WinPython. PowerShell exit code: %errorlevel%
        echo Please check your internet connection and try again. If the problem persists, the download URL may be outdated or the server might be temporarily unavailable.
        pause
        exit /b 1
    )
    if not exist "%WINPYTHON_ZIP_FULL_PATH%" (
        echo ERROR: WinPython ZIP file not found after download attempt. This might indicate a partial download.
        echo Please check your internet connection and available disk space.
        pause
        exit /b 1
    )
    
    echo WinPython Download complete. Extracting...
    REM Use PowerShell to extract the archive.
    powershell -Command "& {Expand-Archive -Path '%WINPYTHON_ZIP_FULL_PATH%' -DestinationPath '%WINPYTHON_DIR%' -Force}"
    REM 2. Add ErrorLevel Checks
    if errorlevel 1 (
        echo ERROR: Failed to extract WinPython. PowerShell exit code: %errorlevel%
        echo This could be due to a corrupted download or insufficient disk space/permissions.
        echo Try deleting the WinPython folder and '%WINPYTHON_ZIP_FULL_PATH%' if it exists, then run the script again.
        pause
        exit /b 1
    )
    if exist "%WINPYTHON_ZIP_FULL_PATH%" del "%WINPYTHON_ZIP_FULL_PATH%"
    
    REM 3. Robust Python Path Detection (Search for python.exe after extraction)
    set "FOUND_PYTHON_EXE_POST_EXTRACT="
    REM Search recursively for python.exe within the newly extracted WinPython directory.
    for /r "%WINPYTHON_DIR%" %%F in (python.exe) do (
        if not defined FOUND_PYTHON_EXE_POST_EXTRACT (
            REM Basic check for plausible Python path (ensures "python" is in the path).
            echo "%%~dpF" | findstr /I /L /C:"python" >nul
            if not errorlevel 1 (
                 set "PYTHON_CMD=%%F"
                 REM Determine the base directory of Python to find the 'env.bat' script.
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
        echo This indicates a problem with the WinPython package or the extraction process.
        echo Try deleting the %WINPYTHON_DIR% and running the script again. If the issue persists, the WinPython package might be corrupted or incomplete.
        pause
        exit /b 1
    )
    if not exist "!PYTHON_ENV_BAT!" (
        echo ERROR: Python env.bat not found at expected path !PYTHON_ENV_BAT!.
        echo Searched relative to !PYTHON_CMD!. Check WinPython package structure.
        echo This file is crucial for activating the Python environment. The WinPython package might be incomplete or structured differently.
        pause
        exit /b 1
    )
    echo WinPython downloaded and configured successfully.
)
echo.
echo --------------------------------------------------------------------
echo.

REM Final verification for Python paths (should be set by now)
REM These checks ensure that critical Python paths are defined and valid before proceeding.
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
REM 4. Idempotency: Search for existing cdbxpp.exe or cdbxpcmd.exe in CDBURNER_DIR.
if exist "%CDBURNER_DIR%" (
    REM Recursively search for CDBurnerXP executables.
    for /r "%CDBURNER_DIR%" %%F in (cdbxpp.exe cdbxpcmd.exe) do (
        if not defined CDBURNER_EXE if exist "%%F" (
            set "CDBURNER_EXE=%%F"
        )
    )
)

if not defined CDBURNER_EXE (
    echo.
    echo --------------------------------------------------------------------
    echo.
    echo --- CDBurnerXP Installation ---
    echo CDBurnerXP not found. Proceeding with download and setup...
    if not exist "%CDBURNER_DIR%" (
        mkdir "%CDBURNER_DIR%"
        if errorlevel 1 (
            echo ERROR: Failed to create directory %CDBURNER_DIR%. Check permissions.
            echo Ensure you are running this script from a user-writable location.
            pause
            exit /b 1
        )
    )
    
    echo Downloading CDBurnerXP from %CDBURNER_DOWNLOAD_URL%
    REM Use PowerShell to download, ensuring TLS 1.2 for compatibility.
    powershell -Command "& {[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12; Invoke-WebRequest -Uri '%CDBURNER_DOWNLOAD_URL%' -OutFile '%CDBURNER_ZIP_FULL_PATH%'}"
    REM 2. Add ErrorLevel Checks
    if errorlevel 1 (
        echo ERROR: Failed to download CDBurnerXP. PowerShell exit code: %errorlevel%
        echo Please check your internet connection and try again. If the problem persists, the download URL may be outdated or the server might be temporarily unavailable.
        pause
        exit /b 1
    )
    if not exist "%CDBURNER_ZIP_FULL_PATH%" (
        echo ERROR: CDBurnerXP ZIP file not found after download attempt. This might indicate a partial download.
        echo Please check your internet connection and available disk space.
        pause
        exit /b 1
    )
    
    echo CDBurnerXP Download complete. Extracting...
    REM Use PowerShell to extract the archive.
    powershell -Command "& {Expand-Archive -Path '%CDBURNER_ZIP_FULL_PATH%' -DestinationPath '%CDBURNER_DIR%' -Force}"
    REM 2. Add ErrorLevel Checks
    if errorlevel 1 (
        echo ERROR: Failed to extract CDBurnerXP. PowerShell exit code: %errorlevel%
        echo This could be due to a corrupted download or insufficient disk space/permissions.
        echo Try deleting the CDBurnerXP folder and '%CDBURNER_ZIP_FULL_PATH%' if it exists, then run the script again.
        pause
        exit /b 1
    )
    if exist "%CDBURNER_ZIP_FULL_PATH%" del "%CDBURNER_ZIP_FULL_PATH%"
    
    REM Search again after extraction to confirm executable presence.
    set "FOUND_CDB_EXE_AFTER_EXTRACT="
    for /r "%CDBURNER_DIR%" %%F in (cdbxpp.exe cdbxpcmd.exe) do (
        if not defined FOUND_CDB_EXE_AFTER_EXTRACT if exist "%%F" (
            set "CDBURNER_EXE=%%F"
            set "FOUND_CDB_EXE_AFTER_EXTRACT=1"
        )
    )
    if not defined FOUND_CDB_EXE_AFTER_EXTRACT (
        echo ERROR: Failed to find cdbxpp.exe or cdbxpcmd.exe in %CDBURNER_DIR% after extraction.
        echo This indicates a problem with the CDBurnerXP package or the extraction process.
        echo Try deleting the %CDBURNER_DIR% and running the script again. If the issue persists, the CDBurnerXP package might be corrupted or incomplete.
        pause
        exit /b 1
    )
    echo CDBurnerXP downloaded and set up successfully: !CDBURNER_EXE!
) else (
    echo Found existing CDBurnerXP: !CDBURNER_EXE!. Skipping download.
)
echo.
echo --------------------------------------------------------------------
echo.

REM Activate Python environment. >nul 2>&1 suppresses output from the env script.
call "!PYTHON_ENV_BAT!" >nul 2>&1
if errorlevel 1 (
    echo WARNING: Calling PYTHON_ENV_BAT returned an error code: %errorlevel%.
    echo Python environment might be incomplete.
)

echo --- Python Environment Setup ---
REM Update pip to ensure the latest version is used for package installations.
echo Updating pip...
"!PYTHON_CMD!" -m pip install --upgrade pip
REM 2. Add ErrorLevel Checks
if errorlevel 1 (
    echo ERROR: Failed to upgrade pip. Pip exit code: %errorlevel%
    echo This may be due to network issues or repository problems. Check your internet connection.
    echo If the problem persists, you might need to manually check the Python installation or report this issue.
    pause
    exit /b 1
)
echo Pip updated successfully.

REM Check if requirements.txt exists, create if not
REM 5. General Script Improvements: Creation of requirements.txt
REM If requirements.txt is missing, create a default one with essential packages.
if not exist "%SCRIPT_DIR%requirements.txt" (
    echo requirements.txt not found in %SCRIPT_DIR%. Creating a default one...
    (
        echo spotipy
        echo spotdl
        echo rich
        echo colorama
        echo python-dotenv
    ) > "%SCRIPT_DIR%requirements.txt"
) else (
    echo Found %SCRIPT_DIR%requirements.txt. Proceeding with package installation.
)

REM Install required packages from requirements.txt.
echo Installing required Python packages from %SCRIPT_DIR%requirements.txt...
"!PYTHON_CMD!" -m pip install -r "%SCRIPT_DIR%requirements.txt"
REM 2. Add ErrorLevel Checks
if errorlevel 1 (
    echo ERROR: Failed to install Python packages from requirements.txt. Pip exit code: %errorlevel%
    echo This may be due to network issues, problems with package definitions in requirements.txt, or conflicts.
    echo Check your internet connection and the contents of requirements.txt.
    echo You can try running '\"!PYTHON_CMD!" -m pip install -r "%SCRIPT_DIR%requirements.txt\"' manually in a command prompt after this script exits.
    pause
    exit /b 1
)
echo Required Python packages installed successfully.
echo.
echo --------------------------------------------------------------------
echo.

echo ===== Configuration Setup =====
echo.
REM Set up directories for portable data, downloads, music, and the config file path.
REM PORTABLE_DIR is the root for all application-specific user data.
set "PORTABLE_DIR=%SCRIPT_DIR%PortableData"
set "DOWNLOADS_DIR=%PORTABLE_DIR%\Downloads"
set "MUSIC_DIR=%PORTABLE_DIR%\Music"
set "PORTABLE_CONFIG_FILE=%PORTABLE_DIR%\config.json"

REM Create directories if needed, with error checking for permissions.
if exist "%PORTABLE_DIR%" (
    echo PortableData directory already exists: %PORTABLE_DIR%
) else (
    echo Creating PortableData directory: %PORTABLE_DIR%...
    mkdir "%PORTABLE_DIR%"
    if errorlevel 1 (
        echo ERROR: Failed to create directory %PORTABLE_DIR%.
        echo Please check permissions in %SCRIPT_DIR% or run from a user-writable location.
        pause
        exit /b 1
    )
)

if exist "%DOWNLOADS_DIR%" (
    echo Downloads directory already exists: %DOWNLOADS_DIR%
) else (
    echo Creating missing directory %DOWNLOADS_DIR%...
    mkdir "%DOWNLOADS_DIR%"
    if errorlevel 1 (
        echo ERROR: Failed to create directory %DOWNLOADS_DIR%.
        echo Please check permissions in %PORTABLE_DIR%.
        pause
        exit /b 1
    )
)
if exist "%MUSIC_DIR%" (
    echo Music directory already exists: %MUSIC_DIR%
) else (
    echo Creating missing directory %MUSIC_DIR%...
    mkdir "%MUSIC_DIR%"
    if errorlevel 1 (
        echo ERROR: Failed to create directory %MUSIC_DIR%.
        echo Please check permissions in %PORTABLE_DIR%.
        pause
        exit /b 1
    )
)


REM Copy default config if portable one doesn't exist, with error checking.
if exist "%SCRIPT_DIR%config.json" (
    if not exist "%PORTABLE_CONFIG_FILE%" (
        echo Creating portable configuration (%PORTABLE_CONFIG_FILE%) from default (%SCRIPT_DIR%config.json).
        copy "%SCRIPT_DIR%config.json" "%PORTABLE_CONFIG_FILE%" >nul
        if errorlevel 1 (
            echo ERROR: Failed to copy config.json to %PORTABLE_CONFIG_FILE%.
            echo Please check permissions in %PORTABLE_DIR% and ensure %SCRIPT_DIR%config.json exists.
            pause
            exit /b 1
        )
    ) else (
        echo Portable configuration file %PORTABLE_CONFIG_FILE% already exists. Skipping creation from default.
    )
) else (
    echo Default config.json not found in script directory (%SCRIPT_DIR%config.json).
    echo A portable config.json will be created by the application if needed, or you can create one manually at %PORTABLE_CONFIG_FILE%.
)

REM Update config with dynamic music directory
REM 5. General Script Improvements: Robust handling of inline Python script
REM This block creates and runs a temporary Python script to update 'download_dir' in the config.json.
if exist "%PORTABLE_CONFIG_FILE%" (
    echo Updating configuration for download directory to: %MUSIC_DIR%
    set "TEMP_PYTHON_UPDATE_SCRIPT=%SCRIPT_DIR%__temp_update_cfg.py"
    REM Generate the temporary Python script.
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
    REM Check if the temporary script was created successfully.
    if errorlevel 1 (
        echo ERROR: Failed to create temporary Python script at "!TEMP_PYTHON_UPDATE_SCRIPT!".
        echo Please check permissions in %SCRIPT_DIR%.
        pause
        exit /b 1
    )
    "!PYTHON_CMD!" "!TEMP_PYTHON_UPDATE_SCRIPT!"
    if errorlevel 1 ( 
        echo WARNING: Failed to update download_dir in config.json using Python script. Error code: %errorlevel%
    )
    if exist "!TEMP_PYTHON_UPDATE_SCRIPT!" del "!TEMP_PYTHON_UPDATE_SCRIPT!"
)

REM Setup environment variables for Python scripts
REM SPOTIFY_DOWNLOADER_CONFIG points to the portable config file.
REM SPOTIFY_DOWNLOADER_PORTABLE indicates the script is running in portable mode.
REM DOTENV_PATH points to the portable .env file.
REM CDBURNERXP_PATH provides the Python script with the path to CDBurnerXP.
set "SPOTIFY_DOWNLOADER_CONFIG=%PORTABLE_CONFIG_FILE%"
set "SPOTIFY_DOWNLOADER_PORTABLE=1"
set "DOTENV_PATH=%PORTABLE_DIR%\.env"
set "CDBURNERXP_PATH=!CDBURNER_EXE!"

REM Setup .env if needed, with error checking for file operations.
if not exist "%DOTENV_PATH%" (
    if exist "%SCRIPT_DIR%.env.sample" (
        copy "%SCRIPT_DIR%.env.sample" "%DOTENV_PATH%" >nul
        if errorlevel 1 (
            echo ERROR: Failed to copy .env.sample to %DOTENV_PATH%.
            echo Please check permissions in %PORTABLE_DIR%.
            pause
            exit /b 1
        )
        echo Copied .env.sample to %DOTENV_PATH%.
    ) else (
        echo Creating default .env file in %DOTENV_PATH%...
        (
            echo SPOTIPY_CLIENT_ID=your_client_id_here
            echo SPOTIPY_CLIENT_SECRET=your_client_secret_here
        )> "%DOTENV_PATH%"
        if errorlevel 1 (
            echo ERROR: Failed to create default .env file at %DOTENV_PATH%.
            echo Please check permissions in %PORTABLE_DIR%.
            pause
            exit /b 1
        )
    )
    echo.
    echo The .env file (%DOTENV_PATH%) requires your Spotify API credentials.
    echo You need to set SPOTIPY_CLIENT_ID and SPOTIPY_CLIENT_SECRET.
    echo You can get these from the Spotify Developer Dashboard (https://developer.spotify.com/dashboard/).
) else (
    echo .env file already exists at %DOTENV_PATH%. Skipping creation.
)

REM Update config with CDBurnerXP path using the Python script (if update_cdburnerxp_path.py exists)
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
echo --------------------------------------------------------------------
echo.

REM Post-Setup Menu: Allows user to edit config files, proceed, or exit.
:post_setup_menu
echo.
echo --- Optional Next Steps ---
echo 1. Edit Spotify API Keys (.env file at %DOTENV_PATH%)
echo 2. Edit Application Configuration (config.json at %PORTABLE_CONFIG_FILE%)
echo 3. Continue to Launch Application
echo 4. Exit Script
echo 5. Show Help/More Information
echo.
set "MENU_CHOICE="
set /p "MENU_CHOICE=Enter your choice (1-5): "

if "!MENU_CHOICE!"=="1" (
    REM Open .env file for editing and loop back to menu.
    echo Opening %DOTENV_PATH%...
    start "" "%DOTENV_PATH%"
    echo Please save your changes and close the editor to return here.
    pause
    goto post_setup_menu
)
if "!MENU_CHOICE!"=="2" (
    REM Open config.json for editing and loop back to menu.
    echo Opening %PORTABLE_CONFIG_FILE%...
    start "" "%PORTABLE_CONFIG_FILE%"
    echo Please save your changes and close the editor to return here.
    pause
    goto post_setup_menu
)
if "!MENU_CHOICE!"=="3" (
    REM Proceed to launch the main Python application.
    echo Proceeding to launch application...
    goto launch_application
)
if "!MENU_CHOICE!"=="4" (
    REM Exit the batch script.
    echo Exiting script.
    goto :eof
)
if "!MENU_CHOICE!"=="5" (
    REM Display help information and loop back to menu.
    call :show_help_info
    pause
    goto post_setup_menu
)
echo Invalid choice. Please try again.
goto post_setup_menu

REM Subroutine to display help information about configuration files and paths.
:show_help_info
echo.
echo --- Help / More Information ---
echo.
echo [ .env File ]
echo   Purpose: Stores your Spotify API credentials.
echo   Required: SPOTIPY_CLIENT_ID and SPOTIPY_CLIENT_SECRET.
echo   How to get: Create an app on the Spotify Developer Dashboard.
echo   Location: %DOTENV_PATH%
echo.
echo [ config.json File ]
echo   Purpose: Stores application settings.
echo   Location: %PORTABLE_CONFIG_FILE%
echo   Key Settings: You can configure 'dvd_drive', 'audio_format', 
echo               'bitrate', 'theme', etc.
echo               'download_dir' is automatically set to %MUSIC_DIR%.
echo.
echo [ Download Locations ]
echo   Music: %MUSIC_DIR%
echo   Videos: %PORTABLE_DIR%\Videos (if applicable)
echo.
echo [ Important ]
echo   After editing .env or config.json, make sure to SAVE the file
echo   before closing the editor.
echo.
echo -----------------------------
goto :eof

REM Label to jump to for launching the application.
:launch_application
echo.
echo --------------------------------------------------------------------
echo.
echo ===== Finalizing Setup and Launching =====
echo.
REM 5. General Script Improvements: More informative echo messages
echo Starting Spotify Album Downloader and Burner...
echo.
echo --- Setup Summary ---
echo Script Directory: %SCRIPT_DIR%
echo WinPython Path: !PYTHON_CMD!
echo CDBurnerXP Path: !CDBURNER_EXE!
echo Python Packages: Installed from %SCRIPT_DIR%requirements.txt
echo Main Configuration File: %SPOTIFY_DOWNLOADER_CONFIG%
echo Environment Variables File: %DOTENV_PATH%
echo Music Download Directory: %MUSIC_DIR%
echo Portable Data Directory: %PORTABLE_DIR%
echo --- End of Summary ---
echo.
echo All setup steps completed.
echo.
echo Launching main application...
echo.

"!PYTHON_CMD!" "%SCRIPT_DIR%spotify_burner.py"

echo.
echo Spotify Album Downloader and Burner has exited.
pause
endlocal
