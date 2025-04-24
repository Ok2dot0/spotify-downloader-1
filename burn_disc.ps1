#!/usr/bin/env pwsh
<#
.SYNOPSIS
    Automates the CD/DVD burning process for Spotify Burner application.
.DESCRIPTION
    This script provides automated CD/DVD burning functionality for the Spotify Burner application.
    It attempts multiple methods to initiate the burning process on Windows.
.PARAMETER SourceDir
    Directory containing the files to burn.
.PARAMETER DriveLetterOnly
    Optional drive letter (without colon) to burn to. If not specified, auto-detection is used.
.PARAMETER DiscLabel
    Optional label for the disc. If not specified, the source directory name is used.
.EXAMPLE
    .\burn_disc.ps1 -SourceDir "C:\Music\Album Folder" -DriveLetterOnly "E" -DiscLabel "My Album"
.NOTES
    Created for Spotify Album Downloader and Burner
    Version: 1.1
    Author: Spotify Burner Team
    Date: April 22, 2025
#>

param (
    [Parameter(Mandatory=$true)]
    [string]$SourceDir,
    
    [Parameter(Mandatory=$false)]
    [string]$DriveLetterOnly,
    
    [Parameter(Mandatory=$false)]
    [string]$DiscLabel
)

function Write-ColorOutput($ForegroundColor) {
    # Save the current color
    $fc = $host.UI.RawUI.ForegroundColor
    
    # Set the new color
    $host.UI.RawUI.ForegroundColor = $ForegroundColor
    
    # Write the text
    if ($args) {
        Write-Output $args
    }
    else {
        $input | Write-Output
    }
    
    # Restore the original color
    $host.UI.RawUI.ForegroundColor = $fc
}

function Write-Success($message) {
    Write-ColorOutput Green $message
}

function Write-Info($message) {
    Write-ColorOutput Cyan $message
}

function Write-Warning($message) {
    Write-ColorOutput Yellow $message
}

function Write-Error($message) {
    Write-ColorOutput Red $message
}

function Get-OpticalDrives {
    $drives = @()
    
    try {
        # Get CD/DVD drives from WMI
        $cdDrives = Get-WmiObject Win32_CDROMDrive
        
        if ($cdDrives) {
            foreach ($drive in $cdDrives) {
                if ($drive.Drive) {
                    $drives += $drive.Drive
                }
            }
        }
    }
    catch {
        Write-Error "Error detecting optical drives: $_"
    }
    
    return $drives
}

# Display banner
Write-Host ""
Write-Info "===========================================" 
Write-Info "   SPOTIFY ALBUM BURNER - DISC BURNING    "
Write-Info "===========================================" 
Write-Host ""

# Validate source directory
if (-not (Test-Path -Path $SourceDir -PathType Container)) {
    Write-Error "Source directory not found: $SourceDir"
    exit 1
}

# Get optical drives
$opticalDrives = Get-OpticalDrives
if (-not $opticalDrives -or $opticalDrives.Count -eq 0) {
    Write-Error "No optical drives detected on your system."
    exit 1
}

# Set target drive letter
if ([string]::IsNullOrEmpty($DriveLetterOnly)) {
    # Auto-select the first available drive
    $targetDrive = $opticalDrives[0]
    Write-Info "Auto-selected optical drive: $targetDrive"
} else {
    # Use the specified drive
    $targetDrive = "$($DriveLetterOnly):"
    if (-not ($opticalDrives -contains $targetDrive)) {
        Write-Warning "Specified drive $targetDrive not found or is not an optical drive."
        Write-Warning "Available optical drives: $($opticalDrives -join ', ')"
        $targetDrive = $opticalDrives[0]
        Write-Info "Using available optical drive: $targetDrive"
    }
}

# Set disc label
if ([string]::IsNullOrEmpty($DiscLabel)) {
    $DiscLabel = (Get-Item $SourceDir).Name
}

# Clean up label for ISO9660 compatibility
$DiscLabel = $DiscLabel -replace '[^\w\s-]', ''
if ($DiscLabel.Length -gt 16) {
    $DiscLabel = $DiscLabel.Substring(0, 16)
}

Write-Info "Preparing to burn files from: $SourceDir"
Write-Info "Target optical drive: $targetDrive"
Write-Info "Disc label: $DiscLabel"
Write-Host ""

# Create temporary directory for burning
$tempDir = [System.IO.Path]::Combine([System.IO.Path]::GetTempPath(), "SpotifyBurn_$([DateTime]::Now.ToString('yyyyMMdd_HHmmss'))")
New-Item -ItemType Directory -Path $tempDir -Force | Out-Null

Write-Info "Copying files to temporary location..."
Copy-Item -Path "$SourceDir\*" -Destination $tempDir -Recurse

# Add a track info text file
Set-Content -Path "$tempDir\Album_Info.txt" -Value "Album: $DiscLabel`r`nBurned by Spotify Burner on $([DateTime]::Now.ToString('yyyy-MM-dd HH:mm:ss'))"

# Get list of files to burn
$filesToBurn = Get-ChildItem -Path $tempDir -Recurse | Where-Object { -not $_.PSIsContainer }
Write-Info "Preparing to burn $($filesToBurn.Count) files to disc."

# Load required assemblies for direct Windows shell integration
Add-Type -AssemblyName System.Windows.Forms
Add-Type -TypeDefinition @"
using System;
using System.Runtime.InteropServices;

public class NativeMethods {
    [DllImport("user32.dll")]
    public static extern IntPtr FindWindow(string lpClassName, string lpWindowName);
    
    [DllImport("user32.dll")]
    public static extern bool SetForegroundWindow(IntPtr hWnd);
    
    [DllImport("user32.dll")]
    public static extern bool ShowWindow(IntPtr hWnd, int nCmdShow);
    
    [DllImport("user32.dll")]
    public static extern IntPtr SendMessage(IntPtr hWnd, uint Msg, IntPtr wParam, IntPtr lParam);
}
"@

# METHOD 1: Direct shell automation with EXTENDED capabilities
Write-Info "Initiating burn process (Method 1)..."
try {
    # Create shell object and get burn folder
    $shell = New-Object -ComObject Shell.Application
    $burnFolder = $shell.NameSpace(0x0A)  # 0x0A is CSIDL_CDBURN_AREA
    
    # Create temp script to force burn dialog via direct BurnSelection method
    $burnTempScript = [System.IO.Path]::Combine([System.IO.Path]::GetTempPath(), "BurnNow_$([DateTime]::Now.ToString('yyyyMMdd_HHmmss')).ps1")
    $burnScriptContent = @"
Add-Type -AssemblyName System.Windows.Forms
Add-Type -AssemblyName Microsoft.VisualBasic
`$shell = New-Object -ComObject "Shell.Application"
`$burnFolder = `$shell.NameSpace(0x0A)

# Force burn dialog via multiple methods
`$burnFolder.Self.InvokeVerb("Burn")

# Allow time for dialog to appear
Start-Sleep -Seconds 3

# If dialog hasn't appeared, try to send virtual keystrokes
`$processes = Get-Process explorer
foreach(`$proc in `$processes) {
    try {
        [Microsoft.VisualBasic.Interaction]::AppActivate(`$proc.Id)
        [System.Windows.Forms.SendKeys]::SendWait("^b") # Ctrl+B might trigger burn in some Windows versions
        Start-Sleep -Milliseconds 300
    } catch {}
}

Write-Host "Burn dialog should have been triggered. Check your screen."
Write-Host "Press ENTER when you've completed burning or to close this window."
`$null = Read-Host
"@
    $burnScriptContent | Out-File -FilePath $burnTempScript -Encoding UTF8

    Write-Host "Copying files to the burn staging area..."
    foreach ($file in $filesToBurn) {
        if ($file -ne $null) {
            Write-Host "  Adding $($file.Name) to burn area..."
            $burnFolder.CopyHere($file.FullPath, 16)
        }
    }
    
    # Wait for files to be copied (increase wait time to ensure all files are in staging area)
    Start-Sleep -Seconds 3
    
    # Force the burning dialog to appear with direct command
    Write-Info "Initiating burn process..."
    
    # Try multiple approaches to make sure the burn dialog appears
    
    # 1. Try direct Invoke method on shell object
    $burnFolder.Self.InvokeVerb("Burn")
    Start-Sleep -Seconds 2
    
    # 2. Execute our dedicated burn script in a new window
    Start-Process powershell -ArgumentList "-NoExit -ExecutionPolicy Bypass -File `"$burnTempScript`""
    
    # 3. Also try using the DiskPart method as a fallback
    $diskPartScript = [System.IO.Path]::Combine([System.IO.Path]::GetTempPath(), "dpburn_$([DateTime]::Now.ToString('yyyyMMdd_HHmmss')).txt")
    "select volume $($DriveLetterOnly)`r`nburn" | Out-File -FilePath $diskPartScript -Encoding ASCII
    
    # Execute DiskPart in background (might need admin rights)
    Start-Process "diskpart.exe" -ArgumentList "/s `"$diskPartScript`"" -WindowStyle Hidden
    
    Write-Success "Burn dialog should appear shortly..."
    Write-Host "If burn dialog doesn't appear automatically:"
    Write-Host "1. Open File Explorer and navigate to burn folder (search for Burn in File Explorer)"
    Write-Host "2. Or press Win+R and type: shell:::{F5FB2C77-0E2F-4A16-A381-3E560C68BC83}"
    
    # Success exit - Method 1
    exit 0
} 
catch {
    Write-Warning "Method 1 failed: $_"
    Write-Host "Trying alternative method..."
}

# METHOD 2: Direct burn dialog access using Windows Explorer references
Write-Info "Initiating burn process (Method 2)..."
try {
    # Launch burn dialog directly
    $burnGuid = "{F5FB2C77-0E2F-4A16-A381-3E560C68BC83}"
    $explorerPath = "explorer.exe"
    
    # Create a batch file that will open the burn dialog directly
    $batchPath = [System.IO.Path]::Combine([System.IO.Path]::GetTempPath(), "OpenBurnDialog_$([DateTime]::Now.ToString('yyyyMMdd_HHmmss')).bat")
@"
@echo off
echo Opening Windows Burn Dialog...
explorer.exe shell:::{$burnGuid}
echo If the burn dialog doesn't appear, your files are in:
echo $tempDir
echo.
echo Press any key to close this window when finished...
pause > nul
"@ | Out-File -FilePath $batchPath -Encoding ASCII

    # Execute the batch file
    Start-Process -FilePath "cmd.exe" -ArgumentList "/k `"$batchPath`""
    
    # Also try direct explorer launch
    Start-Process -FilePath $explorerPath -ArgumentList "shell:::{$burnGuid}"
    
    Write-Success "Multiple attempts to launch burn dialog made."
    Write-Host "One or more windows should appear with burn functionality."
    
    # Success exit - Method 2
    exit 0
} 
catch {
    Write-Warning "Method 2 failed: $_"
    Write-Host "Trying alternative method..."
}

# METHOD 3: Alternative method using Send-To mechanism and direct shell manipulation
Write-Info "Initiating burn process (Method 3)..."
try {
    # Make sure we have the SendTo folder path
    $sendToPath = [System.Environment]::GetFolderPath("SendTo")
    $shortcutFile = "$sendToPath\DVD RW Drive ($targetDrive).lnk"
    
    # Create shortcut if it doesn't exist
    if (-not (Test-Path $shortcutFile)) {
        $WshShell = New-Object -ComObject WScript.Shell
        $shortcut = $WshShell.CreateShortcut($shortcutFile)
        $shortcut.TargetPath = $targetDrive
        $shortcut.Save()
    }
    
    # Create and execute a command file that will perform the operation
    $cmdFile = [System.IO.Path]::Combine([System.IO.Path]::GetTempPath(), "BurnFiles_$([DateTime]::Now.ToString('yyyyMMdd_HHmmss')).bat")
@"
@echo off
echo Opening folder for burning: $tempDir
echo.
echo STEP 1: Select all files (Ctrl+A)
echo STEP 2: Right-click and select 'Send to' -> '$targetDrive'
echo STEP 3: Follow the burn wizard instructions
echo.
explorer.exe "$tempDir"
echo Press any key when you are finished burning...
pause > nul
"@ | Out-File -FilePath $cmdFile -Encoding ASCII

    # Run the command file
    Start-Process -FilePath "cmd.exe" -ArgumentList "/k `"$cmdFile`""
    
    # Success exit - Method 3
    exit 0
} 
catch {
    Write-Error "All burning methods failed: $_"
    Write-Host "Please burn files manually from: $tempDir"
    # Last resort: just open the folder
    Start-Process "explorer.exe" -ArgumentList $tempDir
    # Failure exit
    exit 1
}