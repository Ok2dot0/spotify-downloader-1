import os
import shutil
import subprocess
import logging
import sys
import json
from pathlib import Path

# Configure basic logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def check_spotdl_installed():
    """Check if spotdl is available in PATH."""
    try:
        result = subprocess.run(
            ["spotdl", "--version"],
            text=True,
            capture_output=True,
            check=False
        )
        if result.returncode == 0:
            return True, result.stdout.strip()
        else:
            return False, f"spotdl check failed with error: {result.stderr.strip()}"
    except Exception as e:
        return False, f"Error checking spotdl: {str(e)}"

def get_spotdl_settings():
    """Load spotdl settings from file."""
    settings_file = os.path.join("config", "spotdl_settings.json")
    default_settings = {
        "format": "mp3",
        "bitrate": "auto",
        "output": "{title}.{output-ext}",
        "lyrics": ["genius"],
        "audio": ["youtube"],
        "generate_lrc": False,
        "sponsor_block": False,
        "playlist_numbering": False,
        "threads": 4,
        "genius_token": "",
        "m3u": False,
        "m3u_name": "{list[0]}.m3u8",
        "overwrite": "skip",
        "restrict": "none",
        "user_auth": False,
        "headless": True
    }
    
    try:
        if os.path.exists(settings_file):
            with open(settings_file, "r") as f:
                return json.load(f)
    except Exception:
        logger.error(f"Error loading spotdl settings from {settings_file}, using defaults")
        
    return default_settings

# Use subprocess to call spotdl command-line tool instead of the Python API
def download_track(track_id: str, output_directory: str):
    """
    Downloads a single track using its Spotify ID to the specified directory.
    Uses the spotdl command-line tool via subprocess.
    
    Args:
        track_id: The Spotify ID of the track.
        output_directory: The directory where the track should be saved.
    """
    try:
        # Ensure the output directory exists
        os.makedirs(output_directory, exist_ok=True)
        
        # First check if spotdl is properly installed
        spotdl_installed, message = check_spotdl_installed()
        if not spotdl_installed:
            print(f"    [red]ERROR: spotdl is not properly installed: {message}[/]")
            print("    [yellow]Try installing spotdl with: pip install spotdl[/]")
            return False

        # Construct the Spotify track URL
        track_url = f"https://open.spotify.com/track/{track_id}"
        print(f"    Attempting to download: {track_id}")
        
        # Use Path to ensure proper paths on all platforms
        output_path = Path(output_directory).resolve()
        
        # Get user settings
        settings = get_spotdl_settings()
        
        # Basic command structure
        cmd = ["spotdl", "download"]
        
        # Add format option
        if settings.get("format"):
            cmd.extend(["--format", settings["format"]])
        
        # Add bitrate option if not set to auto
        if settings.get("bitrate") and settings["bitrate"] != "auto":
            cmd.extend(["--bitrate", settings["bitrate"]])
            
        # Add threads option
        if settings.get("threads", 0) > 0:
            cmd.extend(["--threads", str(settings["threads"])])

        # Add lyrics providers
        if settings.get("lyrics") and isinstance(settings["lyrics"], list) and settings["lyrics"]:
            cmd.extend(["--lyrics", " ".join(settings["lyrics"])])

        # Add genius token if present
        if settings.get("genius_token"):
            cmd.extend(["--genius-access-token", settings["genius_token"]])
            
        # Add audio providers
        if settings.get("audio") and isinstance(settings["audio"], list) and settings["audio"]:
            cmd.extend(["--audio", " ".join(settings["audio"])])

        # Add output template
        if settings.get("output"):
            cmd.extend(["--output", f"{output_path}/{settings['output']}"])
        else:
            cmd.extend(["--output", str(output_path)])
            
        # Add overwrite option
        if settings.get("overwrite") in ["skip", "metadata", "force"]:
            cmd.extend(["--overwrite", settings["overwrite"]])
            
        # Add restrict option
        if settings.get("restrict") in ["strict", "ascii", "none"]:
            cmd.extend(["--restrict", settings["restrict"]])
        
        # Add boolean options
        if settings.get("generate_lrc", False):
            cmd.append("--generate-lrc")
        
        if settings.get("sponsor_block", False):
            cmd.append("--sponsor-block")
            
        if settings.get("playlist_numbering", False):
            cmd.append("--playlist-numbering")
            
        if settings.get("dont_filter_results", False):
            cmd.append("--dont-filter-results")
            
        if settings.get("only_verified_results", False):
            cmd.append("--only-verified-results")
            
        if settings.get("scan_for_songs", False):
            cmd.append("--scan-for-songs")
            
        if settings.get("skip_explicit", False):
            cmd.append("--skip-explicit")
            
        if settings.get("force_update_metadata", False):
            cmd.append("--force-update-metadata")
            
        if settings.get("create_skip_file", False):
            cmd.append("--create-skip-file")
            
        if settings.get("respect_skip_file", False):
            cmd.append("--respect-skip-file")
            
        # Add ffmpeg options
        if settings.get("ffmpeg") and settings["ffmpeg"] != "ffmpeg":
            cmd.extend(["--ffmpeg", settings["ffmpeg"]])
            
        if settings.get("ffmpeg_args"):
            cmd.extend(["--ffmpeg-args", settings["ffmpeg_args"]])
            
        # Add Spotify options
        if settings.get("user_auth", False):
            cmd.append("--user-auth")
            
        if settings.get("no_cache", False):
            cmd.append("--no-cache")
            
        if settings.get("headless", True):
            cmd.append("--headless")
            
        if settings.get("use_cache_file", False):
            cmd.append("--use-cache-file")
            
        if settings.get("cache_path"):
            cmd.extend(["--cache-path", settings["cache_path"]])
            
        if settings.get("max_retries", 0) > 0:
            cmd.extend(["--max-retries", str(settings["max_retries"])])
            
        # Add YouTube-DL args
        if settings.get("yt_dlp_args"):
            cmd.extend(["--yt-dlp-args", settings["yt_dlp_args"]])
            
        # Add proxy if set
        if settings.get("proxy"):
            cmd.extend(["--proxy", settings["proxy"]])
        
        # Add the track URL last
        cmd.append(track_url)
        
        # Display command for debugging
        print(f"    Running: {' '.join(cmd)}")
        
        # Run the command and capture output
        process = subprocess.run(
            cmd,
            text=True,
            capture_output=True
        )
        
        # Check if the command was successful
        if process.returncode == 0:
            print(f"    [green]Download successful![/]")
            return True
        else:
            print(f"    [red]Download failed with error code {process.returncode}[/]")
            print(f"    Error details: {process.stderr.strip()}")
            
            # If error contains 'command not found'
            if "not recognized as" in process.stderr or "command not found" in process.stderr:
                print("    [yellow]spotdl command not found in PATH. Please install it with:[/]")
                print("    [yellow]pip install spotdl[/]")
                print("    [yellow]and ensure it's in your PATH environment variable.[/]")
            
            return False
            
    except Exception as e:
        print(f"    [bold red]Error during download: {e}[/]")
        logger.exception(f"Error downloading track {track_id}")
        return False

# Copy existing tracks to new playlist folders if already downloaded
def copy_existing_track(track_name, source_folder, destination_folder):
    source_path = os.path.join(source_folder, f"{track_name}.mp3")
    destination_path = os.path.join(destination_folder, f"{track_name}.mp3")
    shutil.copy2(source_path, destination_path)
