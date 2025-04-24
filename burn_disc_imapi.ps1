#!/usr/bin/env pwsh
<#
.SYNOPSIS
    Automates the CD/DVD burning process using IMAPI2.
.DESCRIPTION
    This script uses the Windows Image Mastering API (IMAPI2) to automatically burn files 
    from a specified source directory to an optical disc (CD/DVD).
    It handles drive detection, media checks, file system creation, and the burn process.
.PARAMETER SourceDir
    Directory containing the files to burn. The contents of this directory will be burned.
.PARAMETER DriveLetterOnly
    Optional drive letter (without colon, e.g., "E") of the target optical drive. 
    If not specified, the script attempts to find the first available recorder.
.PARAMETER DiscLabel
    Optional label for the disc. Limited to 16 characters for compatibility. 
    If not specified, the source directory name is used.
.PARAMETER EjectAfterBurn
    Optional switch. If specified, the disc will be ejected after a successful burn.
.EXAMPLE
    .\burn_disc_imapi.ps1 -SourceDir "C:\Music\Album To Burn" -DriveLetterOnly "E" -DiscLabel "My Music Mix" -EjectAfterBurn
.EXAMPLE
    .\burn_disc_imapi.ps1 -SourceDir "D:\BackupFiles"
.NOTES
    Requires Windows 7 or later.
    Run PowerShell as Administrator if you encounter permission issues, especially with drive access.
    Try running in both standard PowerShell and PowerShell (x86) if you encounter COM registration errors (REGDB_E_CLASSNOTREG).
    Ensure the 'IMAPI v2.0 Burning Support' Windows feature is enabled.
    Version: 2.1 (IMAPI2 Implementation - Fixes Applied)
    Author: Spotify Burner Team (Revised by AI)
    Date: April 22, 2025 
#>

param (
    [Parameter(Mandatory=$true)]
    [string]$SourceDir,

    [Parameter(Mandatory=$false)]
    [string]$DriveLetterOnly,

    [Parameter(Mandatory=$false)]
    [string]$DiscLabel,
    
    [Parameter(Mandatory=$false)]
    [switch]$EjectAfterBurn
)

#region Helper Functions for Output
function Write-ColorOutput($ForegroundColor) {
    $fc = $host.UI.RawUI.ForegroundColor
    $host.UI.RawUI.ForegroundColor = $ForegroundColor
    if ($args) { Write-Output $args } else { $input | Write-Output }
    $host.UI.RawUI.ForegroundColor = $fc
}
function Write-Success($message) { Write-ColorOutput Green $message }
function Write-Info($message)    { Write-ColorOutput Cyan $message }
function Write-Warning($message) { Write-ColorOutput Yellow $message }
function Write-Error($message)   { Write-ColorOutput Red $message }
#endregion

#region Script Body

# Display banner
Write-Host ""
Write-Info "==========================================="
Write-Info "      AUTOMATED DISC BURNER (IMAPI2)      "
Write-Info "==========================================="
Write-Host ""

# --- Validation ---
if (-not (Test-Path -Path $SourceDir -PathType Container)) {
    Write-Error "Source directory not found: $SourceDir"
    exit 1
}

# --- IMAPI2 Objects ---
$discMaster = $null
$discRecorder = $null # This will hold the *chosen* recorder COM object
$discFormatData = $null
$fileSystemImage = $null
$progressLink = $null
$tempDir = $null # Define $tempDir early for cleanup
$rootItem = $null # Define rootItem early for cleanup

try {
    # --- Drive Detection and Selection ---
    Write-Info "Detecting optical drives..."
    $discMaster = New-Object -ComObject IMAPI2.MsftDiscMaster2
    if (-not $discMaster) {
        Write-Error "Failed to create DiscMaster2 COM object. Ensure IMAPI2 features are available and PowerShell architecture (x86/x64) is correct."
        exit 1
    }

    if ($discMaster.Count -eq 0) {
        Write-Error "No optical drives detected by IMAPI."
        exit 1
    }

    $targetRecorderID = $null
    $availableDrives = @()

    foreach ($recorderId in $discMaster) {
        # Create a temporary recorder object for each iteration
        $recorder = $null # Ensure it's null at the start of the loop iteration
        try {
            $recorder = New-Object -ComObject IMAPI2.MsftDiscRecorder2
            $recorder.InitializeDiscRecorder($recorderId)
            $driveLetter = $recorder.VolumePathNames | Select-Object -First 1 # Get the first drive letter associated
            $availableDrives += "$($recorder.VendorId) $($recorder.ProductId) ($driveLetter)"
            
            if (-not [string]::IsNullOrEmpty($DriveLetterOnly)) {
                # User specified a drive letter
                if ($driveLetter -match "^$([regex]::Escape($DriveLetterOnly)):") {
                    $targetRecorderID = $recorderId
                    # Assign the *valid* recorder object to $discRecorder
                    $discRecorder = $recorder 
                    # ***** IMPORTANT: Prevent $recorder from being released in finally block below for THIS iteration *****
                    $recorder = $null # Set the temp variable to null so finally doesn't release the chosen object
                    Write-Info "Selected specified drive: $driveLetter ($($discRecorder.VendorId) $($discRecorder.ProductId))"
                    break # Exit the loop once the specified drive is found and assigned
                }
            } elseif (-not $targetRecorderID) {
                # Auto-select the first available drive
                $targetRecorderID = $recorderId
                # Assign the *valid* recorder object to $discRecorder
                $discRecorder = $recorder 
                # ***** IMPORTANT: Prevent $recorder from being released in finally block below for THIS iteration *****
                $recorder = $null # Set the temp variable to null so finally doesn't release the chosen object
                Write-Info "Auto-selected first available drive: $driveLetter ($($discRecorder.VendorId) $($discRecorder.ProductId))"
                # Don't break yet for auto-select, continue loop to list all drives
            }
        } catch {
            # Use ${recorderId} here for correct parsing
            Write-Warning "Could not initialize or query recorder ID ${recorderId}: $($_.Exception.Message)" 
        } finally {
            # *** Corrected Finally Block ***
            # Release the temporary recorder COM object *only if* it still exists 
            # (meaning it wasn't the chosen one and wasn't nulled out above).
            if ($recorder -ne $null) {
                # Uncomment the next line for debugging if needed:
                # Write-Host "DEBUG: Releasing temporary recorder object iteration for $(try{$recorder.VolumePathNames[0]}catch{'unknown ID'})" 
                [System.Runtime.InteropServices.Marshal]::ReleaseComObject($recorder) | Out-Null
                $recorder = $null # Ensure it's null after release
            } 
        }
    } # End foreach recorderId loop

    if (-not $targetRecorderID -or $discRecorder -eq $null) {
        if (-not [string]::IsNullOrEmpty($DriveLetterOnly)) {
            Write-Error "Specified drive letter '$DriveLetterOnly' not found among available/functional optical recorders."
        } else {
            Write-Error "Could not select a functional optical drive for auto-selection."
        }
        Write-Info "Available drives found by IMAPI:"
        $availableDrives | ForEach-Object { Write-Info "  - $_" }
        exit 1
    }
    
    # --- Disc Label ---
    if ([string]::IsNullOrEmpty($DiscLabel)) {
        $DiscLabel = (Get-Item $SourceDir).Name
    }
    # Clean up label for ISO9660 compatibility (IMAPI might be more flexible, but good practice)
    $DiscLabel = $DiscLabel -replace '[^\w\s-]', ''
    if ($DiscLabel.Length -gt 16) {
        $DiscLabel = $DiscLabel.Substring(0, 16)
    }
    Write-Info "Using Disc Label: $DiscLabel"

    # --- Create Temporary Directory and Add Info File ---
    # It's often safer to burn from a temp location, especially if adding generated files.
    $tempDir = [System.IO.Path]::Combine([System.IO.Path]::GetTempPath(), "BurnStaging_$([DateTime]::Now.ToString('yyyyMMdd_HHmmss'))")
    Write-Info "Creating temporary staging directory: $tempDir"
    New-Item -ItemType Directory -Path $tempDir -Force | Out-Null
    
    Write-Info "Copying files from '$SourceDir' to staging area..."
    Copy-Item -Path "$SourceDir\*" -Destination $tempDir -Recurse -Force -ErrorAction Stop
    
    # Add the track/album info text file
    $infoFilePath = Join-Path -Path $tempDir -ChildPath "Album_Info.txt"
    $infoContent = "Album: $DiscLabel`r`nSource: $SourceDir`r`nBurned by Automated Burner on $([DateTime]::Now.ToString('yyyy-MM-dd HH:mm:ss'))"
    Set-Content -Path $infoFilePath -Value $infoContent -Encoding UTF8
    Write-Info "Added info file: $infoFilePath"
    
    # --- Media Check ---
    Write-Info "Checking media in drive $($discRecorder.VolumePathNames[0])..."
    # Attempt to create the Filesystem Image Data object
    try {
        $discFormatData = New-Object -ComObject IMAPI2FS.MsftDiscFormat2Data -ErrorAction Stop
    } catch {
        Write-Error "Failed to create MsftDiscFormat2Data COM object."
        Write-Error "Error Details: $($_.Exception.Message)"
        Write-Error "This often indicates a COM registration issue (REGDB_E_CLASSNOTREG)."
        Write-Error "Troubleshooting:"
        Write-Error " 1. Try running this script in the *other* PowerShell architecture (x86 vs x64)."
        Write-Error " 2. Ensure 'IMAPI v2.0 Burning Support' Windows feature is enabled (Control Panel -> Programs -> Turn Windows features on or off)."
        Write-Error " 3. Run 'sfc /scannow' as Administrator to check system files."
        exit 1 # Exit here if the essential COM object can't be created
    }

    $discFormatData.Recorder = $discRecorder # Use the validated $discRecorder object
    $discFormatData.ClientName = "PowerShell Burner Script" # Identify the client

    if (-not $discFormatData.IsRecorderSupported($discRecorder)) {
         Write-Error "The selected recorder is not supported by MsftDiscFormat2Data."
         exit 1
    }
    if (-not $discFormatData.IsCurrentMediaSupported($discRecorder)) {
        Write-Error "The media in the selected recorder is not supported by MsftDiscFormat2Data."
        exit 1
    }

    $mediaType = $discFormatData.CurrentPhysicalMediaType
    Write-Info "Media type detected: $mediaType"

    # Check if media is blank (0x1 = FsiMediaUnknown, 0x2 = FsiMediaCdRom...)
    # IMAPI_MEDIA_STATE flags: https://learn.microsoft.com/en-us/windows/win32/api/imapi2fs/ne-imapi2fs-imapi_media_state
    $mediaState = $null
    try {
        $mediaState = $discFormatData.MediaHeuristicallyBlank
    } catch {
        Write-Warning "Could not heuristically determine if media is blank. Checking status flags instead. Error: $($_.Exception.Message)"
    }
    
    $isMediaBlank = $false
    if ($mediaState -ne $null -and $mediaState -eq $true) {
        $isMediaBlank = $true
        Write-Info "Media appears to be blank."
    } else {
         # Check specific media states if heuristic fails or reports not blank
         $mediaStates = $discFormatData.CurrentMediaStatus
         # Corrected check using IMAPI2.IMAPI_MEDIA_STATE enum values (might need IMAPI2 interop assembly loaded implicitly or explicitly)
         # Assuming common values: Blank = 1
         if (($mediaStates -band 1)) { # Check if IMAPI_MEDIA_STATE_BLANK bit is set
             $isMediaBlank = $true
             Write-Info "Media status indicates blank or empty writable disc."
         } else {
             Write-Warning "Media does not appear to be blank (Status Flags: $mediaStates). Overwriting may fail or is not supported."
             Write-Warning "Attempting to continue, but burn may fail if media is not appendable/rewriteable and contains data."
             # Optionally, add a confirmation prompt here
             # $confirm = Read-Host "Media not blank. Continue anyway? (y/n)"
             # if ($confirm -ne 'y') { exit 1 }
         }
    }
    
    # --- Create File System Image ---
    Write-Info "Creating file system image from content in: $tempDir"
    $fileSystemImage = New-Object -ComObject IMAPI2FS.MsftFileSystemImage
    $fileSystemImage.VolumeName = $DiscLabel
    
    # Choose file systems (Joliet for long names + compatibility, ISO9660 as base)
    # Use FsiFileSystems enum - PowerShell might need explicit values if enum isn't loaded
    # FsiFileSystems.FsiFileSystemJoliet = 2
    # FsiFileSystems.FsiFileSystemISO9660 = 1
    $fileSystemImage.FileSystemsToCreate = (2 -bor 1) # Joliet and ISO9660
    
    # Set free media blocks for calculation
    $fileSystemImage.FreeMediaBlocks = $discFormatData.FreeSectorsOnMedia
    
    # Add the contents of the temporary directory to the image root
    $rootItem = $fileSystemImage.Root
    $rootItem.AddTree($tempDir, $false) # $false = do not include directory itself, only its content

    # Validate image size against media capacity
    $imageSize = $fileSystemImage.UsedBlocks 
    $availableSize = $discFormatData.FreeSectorsOnMedia # Or TotalSectorsOnMedia if overwriting
    Write-Info "Image size: $imageSize blocks. Available on media: $availableSize blocks."
    if ($imageSize -gt $availableSize) {
        Write-Error "Content size ($imageSize blocks) exceeds available space on media ($availableSize blocks)."
        exit 1
    }

    # Create the result stream
    $resultStream = $fileSystemImage.CreateResultImage().ImageStream
    if (-not $resultStream) {
        Write-Error "Failed to create the result image stream."
        exit 1
    }

    # --- Setup Burn Progress Monitoring ---
    Write-Info "Setting up burn progress monitoring..."
    $progressLink = New-Object -ComObject IMAPI2FS.MsftDiscFormat2Data_Events # Event sink
    $action = [scriptblock]{
        param([object]$object, [object]$progress) # Parameters are typically (sender, eventArgs)
        # The eventArgs object ($progress) should be of type IDiscFormat2DataEventArgs
        # https://learn.microsoft.com/en-us/windows/win32/api/imapi2/nn-imapi2-idiscformat2dataevents
        try { # Wrap progress update in try/catch as COM events can sometimes fail
            $elapsed = $progress.ElapsedTime
            $remaining = $progress.RemainingTime
            $totalSectors = $progress.TotalSectorsToWrite
            $writtenSectors = $progress.WrittenSectors
            $percent = 0
            if ($totalSectors -gt 0) {
                $percent = [math]::Round(($writtenSectors / $totalSectors * 100), 0)
            }
            # Map CurrentAction enum to string if possible, otherwise show number
            # https://learn.microsoft.com/en-us/windows/win32/api/imapi2/ne-imapi2-imapi_format2_data_write_action
            $actionText = switch ($progress.CurrentAction) {
                0 { "Verifying media" }
                1 { "Formatting media" }
                2 { "Initializing hardware" }
                3 { "Calibrating power" }
                4 { "Writing data" }
                5 { "Finalizing media" }
                6 { "Flushing cache" }
                7 { "Closing media" }
                default { "Unknown Action $($progress.CurrentAction)" }
            }

            Write-Progress -Activity "Burning Disc '$DiscLabel'" `
                           -Status "$actionText ($percent% Complete)" `
                           -PercentComplete $percent `
                           -CurrentOperation "Writing sector $writtenSectors of $totalSectors" `
                           -SecondsRemaining (if($remaining -lt 0 -or $remaining -gt 1000000) {$null} else {$remaining}) # Handle large/negative values
            # Optional: Update console title
            # $host.UI.RawUI.WindowTitle = "Burning - $percent%"
        } catch {
            Write-Warning "Error during progress update: $($_.Exception.Message)"
        }
    }
    # Ensure the event registration uses the correct COM event interface
    Register-ObjectEvent -InputObject $discFormatData -EventName Update -SourceIdentifier BurnProgress -Action $action | Out-Null

    # --- Burn the Disc ---
    Write-Host ""
    Write-Success "Starting the burn process... This may take several minutes."
    Write-Info "PLEASE DO NOT INTERRUPT THE PROCESS OR REMOVE THE DISC."
    
    # Configure write options (optional)
    $discFormatData.ForceMediaToBeClosed = $true # Close the disc after writing (makes it read-only on most systems)
    
    # Start the write operation
    $discFormatData.Write($resultStream)

    # --- Completion ---
    Write-Progress -Activity "Burning Disc '$DiscLabel'" -Completed
    Write-Host "" # Newline after progress bar
    Write-Success "Burn process completed successfully!"

    # --- Eject Disc (Optional) ---
    if ($EjectAfterBurn) {
        Write-Info "Ejecting the disc..."
        try {
            # Ensure $discRecorder is still valid before ejecting
            if ($discRecorder -ne $null) {
                $discRecorder.EjectMedia()
                Write-Success "Disc ejected."
            } else {
                Write-Warning "Disc Recorder object was null, cannot eject."
            }
        } catch {
             Write-Warning "Failed to eject disc automatically: $($_.Exception.Message)"
        }
    }

} catch {
    # --- Error Handling ---
    Write-Progress -Activity "Burning Disc '$DiscLabel'" -Completed -ErrorAction SilentlyContinue # Clear progress bar on error
    Write-Host ""
    Write-Error "An error occurred during the burning process:"
    # Check if it's the specific COM registration error from earlier check
    if ($_.Exception.Message -like '*80040154*') {
        Write-Error "Error Details: $($_.Exception.Message)"
        Write-Error "This confirms a COM registration issue (REGDB_E_CLASSNOTREG)."
        Write-Error "Troubleshooting:"
        Write-Error " 1. Try running this script in the *other* PowerShell architecture (x86 vs x64)."
        Write-Error " 2. Ensure 'IMAPI v2.0 Burning Support' Windows feature is enabled (Control Panel -> Programs -> Turn Windows features on or off)."
        Write-Error " 3. Run 'sfc /scannow' as Administrator to check system files."
    } else {
        # General error message
        Write-Error $_.Exception.ToString() # More detailed exception info
        if ($_.Exception.InnerException) {
            Write-Error "Inner Exception: $($_.Exception.InnerException.ToString())"
        }
    }
    # You can add checks for specific HRESULT error codes here if needed
    # Example: if ($_.Exception.HResult -eq -1062599935) { Write-Error "Error: Media might not be blank (0xC0AA0301)." }

    exit 1

} finally {
    # --- Cleanup ---
    Write-Info "Cleaning up resources..."
    # Unregister progress event
    Get-EventSubscriber -SourceIdentifier BurnProgress -ErrorAction SilentlyContinue | Unregister-Event -ErrorAction SilentlyContinue
    
    # Release COM objects in reverse order of creation - CRITICAL! Use Write-Host for debugging release.
    if ($progressLink -ne $null) { 
        # Write-Host "Releasing progressLink..." -ForegroundColor DarkGray
        [System.Runtime.InteropServices.Marshal]::ReleaseComObject($progressLink) | Out-Null 
        $progressLink = $null
    }
    if ($resultStream -ne $null) { 
        # Write-Host "Releasing resultStream..." -ForegroundColor DarkGray
        [System.Runtime.InteropServices.Marshal]::ReleaseComObject($resultStream) | Out-Null 
        $resultStream = $null
    }
    if ($rootItem -ne $null) { # Release the root item COM object too
        # Write-Host "Releasing rootItem..." -ForegroundColor DarkGray
        [System.Runtime.InteropServices.Marshal]::ReleaseComObject($rootItem) | Out-Null 
        $rootItem = $null
    }
    if ($fileSystemImage -ne $null) { 
        # Write-Host "Releasing fileSystemImage..." -ForegroundColor DarkGray
        [System.Runtime.InteropServices.Marshal]::ReleaseComObject($fileSystemImage) | Out-Null 
        $fileSystemImage = $null
    }
    if ($discFormatData -ne $null) { 
        # Write-Host "Releasing discFormatData..." -ForegroundColor DarkGray
        [System.Runtime.InteropServices.Marshal]::ReleaseComObject($discFormatData) | Out-Null 
        $discFormatData = $null
    }
    # $discRecorder holds the *chosen* recorder; release it here.
    if ($discRecorder -ne $null) { 
        # Write-Host "Releasing chosen discRecorder..." -ForegroundColor DarkGray
        [System.Runtime.InteropServices.Marshal]::ReleaseComObject($discRecorder) | Out-Null 
        $discRecorder = $null
    } 
    # $discMaster is the top-level object.
    if ($discMaster -ne $null) { 
        # Write-Host "Releasing discMaster..." -ForegroundColor DarkGray
        [System.Runtime.InteropServices.Marshal]::ReleaseComObject($discMaster) | Out-Null 
        $discMaster = $null
    }

    # Remove temporary directory
    if ($tempDir -ne $null -and (Test-Path $tempDir)) {
        Write-Info "Removing temporary directory: $tempDir"
        Remove-Item -Path $tempDir -Recurse -Force -ErrorAction SilentlyContinue
    }
     
    $host.UI.RawUI.WindowTitle = "" # Reset window title if it was changed
    Write-Info "Cleanup complete."
}

#endregion

Write-Success "Script finished."
exit 0