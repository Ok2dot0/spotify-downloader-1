@echo off
setlocal EnableDelayedExpansion

REM Set SCRIPT_DIR to the directory where this batch script is located.
set "SCRIPT_DIR=%~dp0"
pushd "%SCRIPT_DIR%"

REM Define the main application directory and components
set "APP_DIR=%SCRIPT_DIR%spotify-downloader-1"
set "WINPYTHON_DIR=%APP_DIR%\WinPython"
set "CDBURNER_DIR=%APP_DIR%\CDBurnerXP"
set "GIT_PORTABLE_DIR=%SCRIPT_DIR%PortableGit"
set "GIT_PORTABLE_EXE=%GIT_PORTABLE_DIR%\bin\git.exe"

REM Initialize variables for detection
set "PYTHON_CMD="
set "PYTHON_ENV_BAT="
set "CDBURNER_EXE="
set "NEEDS_INSTALLATION=0"

echo ===== Spotify Album Downloader and Burner - Launcher =====
echo.
echo Checking installation status...

REM Check if main application exists
if not exist "%APP_DIR%\spotify_burner.py" (
    echo - Application files: MISSING
    set "NEEDS_INSTALLATION=1"
) else (
    echo - Application files: FOUND
)

REM Check for Python installation
if exist "%WINPYTHON_DIR%" (
    for /r "%WINPYTHON_DIR%" %%F in (python.exe) do (
        if not defined PYTHON_CMD (
            if exist "%%F" (
                set "PYTHON_CMD=%%F"
                set "TEMP_PYTHON_DIR=%%~dpF"
                set "TEMP_PYTHON_DIR=!TEMP_PYTHON_DIR:~0,-1!"
                for %%P in ("!TEMP_PYTHON_DIR!") do set "TEMP_PYTHON_DIR=%%~dpP"
                set "TEMP_PYTHON_DIR=!TEMP_PYTHON_DIR:~0,-1!"
                set "PYTHON_ENV_BAT=!TEMP_PYTHON_DIR!\scripts\env.bat"
            )
        )
    )
)

if defined PYTHON_CMD (
    echo - WinPython: FOUND ^(!PYTHON_CMD!^)
) else (
    echo - WinPython: MISSING
    set "NEEDS_INSTALLATION=1"
)

REM Check for CDBurnerXP
if exist "%CDBURNER_DIR%" (
    for /r "%CDBURNER_DIR%" %%F in (cdbxpp.exe cdbxpcmd.exe) do (
        if not defined CDBURNER_EXE (
            if exist "%%F" (
                set "CDBURNER_EXE=%%F"
            )
        )
    )
)

if defined CDBURNER_EXE (
    echo - CDBurnerXP: FOUND ^(!CDBURNER_EXE!^)
) else (
    echo - CDBurnerXP: MISSING
    set "NEEDS_INSTALLATION=1"
)

echo.

REM Decide whether to install or run
if %NEEDS_INSTALLATION%==1 (
    echo Some components are missing. Starting installation process...
    echo.
    echo IMPORTANT: For best results, run this script from a user-writable directory 
    echo ^(e.g., your Desktop or Documents folder, or a dedicated folder like C:\Tools^).
    echo If you encounter permission errors during setup ^(e.g., "Failed to create directory",
    echo "Failed to extract", "Failed to download"^), please try moving the script's
    echo entire folder to such a location and run it again.
    echo.
    echo This will install:
    echo 1. Clone the Spotify Downloader repository ^(if not present^)
    echo 2. Download and install WinPython ^(if not present^)
    echo 3. Download and install CDBurnerXP ^(if not present^)
    echo 4. Set up the application and launch it
    echo.
    pause
    goto :install_components
) else (
    echo All components found! Launching application...
    goto :launch_application
)

:install_components
echo.
echo ===== INSTALLATION MODE =====

REM Define URLs and components
set "REPO_URL=https://github.com/Ok2dot0/spotify-downloader-1.git"
set "GIT_PORTABLE_URL=https://github.com/git-for-windows/git/releases/download/v2.49.0.windows.1/PortableGit-2.49.0-64-bit.7z.exe"
set "GIT_PORTABLE_7Z=%SCRIPT_DIR%PortableGit-2.49.0-64-bit.7z.exe"

set WINPYTHON_DOWNLOAD_URL=https://github.com/winpython/winpython/releases/download/15.3.20250425final/Winpython64-3.13.3.0dot.zip
set "WINPYTHON_ZIP_FILENAME=Winpython64-3.13.3.0dot.zip"
set "WINPYTHON_ZIP_FULL_PATH=%APP_DIR%\%WINPYTHON_ZIP_FILENAME%"

set CDBURNER_DOWNLOAD_URL=https://archive.org/download/cdburnerxp-4.5.8.7128-portable-version-windows-x86-64/CDBurnerXP-x64-4.5.8.7128.zip
set "CDBURNER_ZIP_FILENAME=cdbxp_setup_4.5.8.7128_x64.zip"
set "CDBURNER_ZIP_FULL_PATH=%APP_DIR%\%CDBURNER_ZIP_FILENAME%"

REM Download portable Git if not present
if not exist "%GIT_PORTABLE_EXE%" (
    echo.
    echo ===== Downloading Portable Git =====
    echo.
    echo Downloading portable Git from %GIT_PORTABLE_URL%
    echo This may take a few minutes depending on your internet connection...
    powershell -Command "& {[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12; Invoke-WebRequest -Uri '%GIT_PORTABLE_URL%' -OutFile '%GIT_PORTABLE_7Z%'}"
    if errorlevel 1 (
        echo ERROR: Failed to download portable Git. Check your internet connection.
        echo The repository cloning will be skipped.
        goto :skip_git_operations
    ) else (
        echo Portable Git downloaded successfully!
        
        REM Extract the 7z.exe self-extracting archive
        echo Extracting portable Git...
        if not exist "%GIT_PORTABLE_DIR%" mkdir "%GIT_PORTABLE_DIR%"
        
        REM Use the 7z.exe file to extract itself
        "%GIT_PORTABLE_7Z%" -o"%GIT_PORTABLE_DIR%" -y
        if errorlevel 1 (
            echo ERROR: Failed to extract portable Git using self-extractor.
            echo Trying alternative extraction method...
            
            REM Try using PowerShell with System.IO.Compression
            powershell -Command "& {Add-Type -AssemblyName System.IO.Compression.FileSystem; try { [System.IO.Compression.ZipFile]::ExtractToDirectory('%GIT_PORTABLE_7Z%', '%GIT_PORTABLE_DIR%') } catch { Write-Host 'PowerShell extraction failed' }}"
            
            if not exist "%GIT_PORTABLE_EXE%" (
                echo ERROR: All extraction methods failed.
                echo Please manually extract %GIT_PORTABLE_7Z% to %GIT_PORTABLE_DIR%
                goto :skip_git_operations
            )
        )
        
        REM Clean up the downloaded file
        if exist "%GIT_PORTABLE_7Z%" del "%GIT_PORTABLE_7Z%"
        
        if exist "%GIT_PORTABLE_EXE%" (
            echo Portable Git extraction completed successfully!
        ) else (
            echo ERROR: Git executable not found after extraction.
            goto :skip_git_operations
        )
    )
) else (
    echo Found existing portable Git: %GIT_PORTABLE_EXE%
)

REM Clone or update the repository using portable Git
if exist "%APP_DIR%\.git" (
    echo Repository already exists. Updating...
    pushd "%APP_DIR%"
    "%GIT_PORTABLE_EXE%" pull origin main
    if errorlevel 1 (
        echo Failed to update repository. Continuing with existing files...
    )
    popd
) else (
    if exist "%APP_DIR%" (
        echo Directory exists but is not a git repository. Skipping clone...
    ) else (
        echo Cloning repository using portable Git...
        "%GIT_PORTABLE_EXE%" clone "%REPO_URL%" "%APP_DIR%"
        if errorlevel 1 (
            echo Failed to clone repository. Creating directory structure...
            mkdir "%APP_DIR%"
        ) else (
            echo Repository cloned successfully!
        )
    )
)

:skip_git_operations

REM For testing purposes, copy files from parent directory if they exist
if not exist "%APP_DIR%\spotify_burner.py" (
    if exist "%SCRIPT_DIR%..\spotify_burner.py" (
        echo Copying application files from parent directory for testing...
        xcopy "%SCRIPT_DIR%..\*.py" "%APP_DIR%\" /Y >nul 2>&1
        xcopy "%SCRIPT_DIR%..\*.json" "%APP_DIR%\" /Y >nul 2>&1
        xcopy "%SCRIPT_DIR%..\*.txt" "%APP_DIR%\" /Y >nul 2>&1
        xcopy "%SCRIPT_DIR%..\*.md" "%APP_DIR%\" /Y >nul 2>&1
    )
)

echo.
echo ===== Installing WinPython =====

REM Check if WinPython already exists and find Python executable
if exist "%WINPYTHON_DIR%" (
    echo Found existing WinPython directory. Searching for Python executable...
    
    REM Search for python.exe in the WinPython directory
    for /r "%WINPYTHON_DIR%" %%F in (python.exe) do (
        if not defined PYTHON_CMD (
            if exist "%%F" (
                set "PYTHON_CMD=%%F"
                set "TEMP_PYTHON_DIR=%%~dpF"
                set "TEMP_PYTHON_DIR=!TEMP_PYTHON_DIR:~0,-1!"
                for %%P in ("!TEMP_PYTHON_DIR!") do set "TEMP_PYTHON_DIR=%%~dpP"
                set "TEMP_PYTHON_DIR=!TEMP_PYTHON_DIR:~0,-1!"
                set "PYTHON_ENV_BAT=!TEMP_PYTHON_DIR!\scripts\env.bat"
                
                echo Found Python: !PYTHON_CMD!
                echo Environment script: !PYTHON_ENV_BAT!
            )
        )
    )
)

REM If Python not found, download and install WinPython
if not defined PYTHON_CMD (
    echo.
    echo WinPython not found. Proceeding with download and setup...
    
    if not exist "%WINPYTHON_DIR%" (
        mkdir "%WINPYTHON_DIR%"
        if errorlevel 1 (
            echo ERROR: Failed to create directory %WINPYTHON_DIR%. Check permissions.
            pause
            exit /b 1
        )
    )
    
    echo Downloading WinPython from %WINPYTHON_DOWNLOAD_URL%
    echo This may take several minutes depending on your internet connection...
    powershell -Command "& {[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12; Invoke-WebRequest -Uri '%WINPYTHON_DOWNLOAD_URL%' -OutFile '%WINPYTHON_ZIP_FULL_PATH%'}"
    if errorlevel 1 (
        echo ERROR: Failed to download WinPython. Check your internet connection.
        pause
        exit /b 1
    )
    
    echo Extracting WinPython...
    echo This may take a few minutes...
    powershell -Command "& {Expand-Archive -Path '%WINPYTHON_ZIP_FULL_PATH%' -DestinationPath '%WINPYTHON_DIR%' -Force}"
    if errorlevel 1 (
        echo ERROR: Failed to extract WinPython.
        pause
        exit /b 1
    )
    
    echo Cleaning up WinPython installer...
    if exist "%WINPYTHON_ZIP_FULL_PATH%" del "%WINPYTHON_ZIP_FULL_PATH%"
    
    REM Search for python.exe after extraction
    echo Searching for Python executable after installation...
    for /r "%WINPYTHON_DIR%" %%F in (python.exe) do (
        if not defined PYTHON_CMD (
            if exist "%%F" (
                set "PYTHON_CMD=%%F"
                set "TEMP_PYTHON_DIR=%%~dpF"
                set "TEMP_PYTHON_DIR=!TEMP_PYTHON_DIR:~0,-1!"
                for %%P in ("!TEMP_PYTHON_DIR!") do set "TEMP_PYTHON_DIR=%%~dpP"
                set "TEMP_PYTHON_DIR=!TEMP_PYTHON_DIR:~0,-1!"
                set "PYTHON_ENV_BAT=!TEMP_PYTHON_DIR!\scripts\env.bat"
                
                echo Found Python after installation: !PYTHON_CMD!
            )
        )
    )
    
    if not defined PYTHON_CMD (
        echo ERROR: Could not find Python executable after installation.
        pause
        exit /b 1
    )
    
    echo WinPython installation completed successfully!
)

echo.
echo ===== Installing CDBurnerXP =====

REM Find CDBurnerXP executable
if exist "%CDBURNER_DIR%" (
    echo Found existing CDBurnerXP directory. Searching for executable...
    for /r "%CDBURNER_DIR%" %%F in (cdbxpp.exe cdbxpcmd.exe) do (
        if not defined CDBURNER_EXE (
            if exist "%%F" (
                set "CDBURNER_EXE=%%F"
                echo Found CDBurnerXP: !CDBURNER_EXE!
            )
        )
    )
)

REM If CDBurnerXP not found, download and install it
if not defined CDBURNER_EXE (
    echo.
    echo CDBurnerXP not found. Proceeding with download and setup...
    
    if not exist "%CDBURNER_DIR%" (
        mkdir "%CDBURNER_DIR%"
        if errorlevel 1 (
            echo ERROR: Failed to create directory %CDBURNER_DIR%. Check permissions.
            pause
            exit /b 1
        )
    )
    
    REM First try to copy from parent directory if available (for testing)
    if exist "%SCRIPT_DIR%..\CDBurnerXP" (
        echo Found existing CDBurnerXP in parent directory. Copying for testing...
        xcopy "%SCRIPT_DIR%..\CDBurnerXP\*" "%CDBURNER_DIR%\" /E /I /Y >nul 2>&1
        if not errorlevel 1 (
            echo Successfully copied CDBurnerXP from parent directory.
            goto :find_cdburner_after_copy
        )
    )
    
    echo Downloading CDBurnerXP from %CDBURNER_DOWNLOAD_URL%
    echo This may take a few minutes depending on your internet connection...
    powershell -Command "& {[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12; Invoke-WebRequest -Uri '%CDBURNER_DOWNLOAD_URL%' -OutFile '%CDBURNER_ZIP_FULL_PATH%'}"
    if errorlevel 1 (
        echo ERROR: Failed to download CDBurnerXP. Check your internet connection.
        echo Trying alternative download method...
        set "ALT_CDBURNER_URL=https://www.cdburnerxp.se/downloadget.php?file=cdbxp_setup_4.5.8.7128_x64.zip"
        powershell -Command "& {[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12; Invoke-WebRequest -Uri '!ALT_CDBURNER_URL!' -OutFile '%CDBURNER_ZIP_FULL_PATH%'}"
        
        if errorlevel 1 (
            echo ERROR: All download attempts failed.
            echo Please manually download CDBurnerXP and extract it to: %CDBURNER_DIR%
            pause
            exit /b 1
        )
    )
    
    echo Extracting CDBurnerXP...
    powershell -Command "& {Expand-Archive -Path '%CDBURNER_ZIP_FULL_PATH%' -DestinationPath '%CDBURNER_DIR%' -Force}"
    if errorlevel 1 (
        echo ERROR: Failed to extract CDBurnerXP.
        pause
        exit /b 1
    )
    
    echo Cleaning up CDBurnerXP installer...
    if exist "%CDBURNER_ZIP_FULL_PATH%" del "%CDBURNER_ZIP_FULL_PATH%"
    
    :find_cdburner_after_copy
    REM Search for CDBurnerXP executable after extraction or copy
    echo Searching for CDBurnerXP executable after installation...
    for /r "%CDBURNER_DIR%" %%F in (cdbxpp.exe cdbxpcmd.exe) do (
        if not defined CDBURNER_EXE (
            if exist "%%F" (
                set "CDBURNER_EXE=%%F"
                echo Found CDBurnerXP after installation: !CDBURNER_EXE!
            )
        )
    )
    
    if not defined CDBURNER_EXE (
        echo ERROR: Could not find CDBurnerXP executable after installation.
        pause
        exit /b 1
    )
    
    echo CDBurnerXP installation completed successfully!
)

REM Set up portable directories
set "PORTABLE_DIR=%APP_DIR%\PortableData"
set "DOWNLOADS_DIR=%PORTABLE_DIR%\Downloads"
set "MUSIC_DIR=%PORTABLE_DIR%\Music"
set "PORTABLE_CONFIG_FILE=%PORTABLE_DIR%\config.json"

REM Create directories if needed
if not exist "%PORTABLE_DIR%" mkdir "%PORTABLE_DIR%"
if not exist "%DOWNLOADS_DIR%" mkdir "%DOWNLOADS_DIR%"
if not exist "%MUSIC_DIR%" mkdir "%MUSIC_DIR%"

REM Copy default config if portable one doesn't exist
if exist "%APP_DIR%\config.json" (
    if not exist "%PORTABLE_CONFIG_FILE%" (
        echo Creating portable configuration...
        copy "%APP_DIR%\config.json" "%PORTABLE_CONFIG_FILE%" >nul
    )
)

REM Set environment variables for Python scripts
set "SPOTIFY_DOWNLOADER_CONFIG=%PORTABLE_CONFIG_FILE%"
set "SPOTIFY_DOWNLOADER_PORTABLE=1"
set "DOTENV_PATH=%PORTABLE_DIR%\.env"
set "CDBURNERXP_PATH=%CDBURNER_EXE%"

REM Setup .env if needed
if not exist "%DOTENV_PATH%" (
    echo Creating default .env file...
    echo SPOTIPY_CLIENT_ID=your_client_id_here> "%DOTENV_PATH%"
    echo SPOTIPY_CLIENT_SECRET=your_client_secret_here>> "%DOTENV_PATH%"
    echo.
    echo NOTICE: The .env file requires your Spotify API credentials.
    echo You can edit %DOTENV_PATH% to add your credentials later.
)

REM Install Python requirements if requirements.txt exists
if exist "%APP_DIR%\requirements.txt" (
    echo Installing Python requirements...
    "%PYTHON_CMD%" -m pip install -r "%APP_DIR%\requirements.txt"
    if errorlevel 1 (
        echo WARNING: Some Python packages failed to install. The application may not work correctly.
    )
)

echo.
echo ===== Installation Complete =====
echo Installation completed successfully! Now launching application...
echo.

:launch_application
echo.
echo ===== LAUNCHING APPLICATION =====

REM Make sure we have all the required variables set for launch mode
if not defined PYTHON_CMD (
    REM Re-detect Python if we're in launch-only mode
    for /r "%WINPYTHON_DIR%" %%F in (python.exe) do (
        if not defined PYTHON_CMD (
            if exist "%%F" (
                set "PYTHON_CMD=%%F"
                set "TEMP_PYTHON_DIR=%%~dpF"
                set "TEMP_PYTHON_DIR=!TEMP_PYTHON_DIR:~0,-1!"
                for %%P in ("!TEMP_PYTHON_DIR!") do set "TEMP_PYTHON_DIR=%%~dpP"
                set "TEMP_PYTHON_DIR=!TEMP_PYTHON_DIR:~0,-1!"
                set "PYTHON_ENV_BAT=!TEMP_PYTHON_DIR!\scripts\env.bat"
            )
        )
    )
)

if not defined CDBURNER_EXE (
    REM Re-detect CDBurnerXP if we're in launch-only mode
    for /r "%CDBURNER_DIR%" %%F in (cdbxpp.exe cdbxpcmd.exe) do (
        if not defined CDBURNER_EXE (
            if exist "%%F" (
                set "CDBURNER_EXE=%%F"
            )
        )
    )
)

REM Set up environment variables
set "PORTABLE_DIR=%APP_DIR%\PortableData"
set "PORTABLE_CONFIG_FILE=%PORTABLE_DIR%\config.json"
set "DOTENV_PATH=%PORTABLE_DIR%\.env"
set "SPOTIFY_DOWNLOADER_CONFIG=%PORTABLE_CONFIG_FILE%"
set "SPOTIFY_DOWNLOADER_PORTABLE=1"
set "CDBURNERXP_PATH=%CDBURNER_EXE%"

echo Activating Python environment...
if exist "%PYTHON_ENV_BAT%" (
    call "%PYTHON_ENV_BAT%" >nul 2>&1
)

echo.
echo Configuration:
echo   Application Directory: %APP_DIR%
echo   Python: %PYTHON_CMD%
echo   Config: %PORTABLE_CONFIG_FILE%
echo   Music Directory: %PORTABLE_DIR%\Music
echo   CDBurnerXP: %CDBURNER_EXE%
echo   Environment File: %DOTENV_PATH%
echo.

if exist "%APP_DIR%\spotify_burner.py" (
    echo Starting Spotify Album Downloader and Burner...
    echo.
    
    REM Launch the application with the portable Python environment
    pushd "%APP_DIR%"
    "%PYTHON_CMD%" "spotify_burner.py"
    popd
    
    echo.
    echo Application has closed. Press any key to exit.
    pause
) else (
    echo ERROR: Main application file ^(spotify_burner.py^) not found in %APP_DIR%
    echo Please ensure the application files are present.
    echo.
    pause
)

popd
endlocal
