import os
import sys
import subprocess
import platform
from pathlib import Path

def check_pip():
    """Check if pip is installed."""
    try:
        subprocess.run([sys.executable, "-m", "pip", "--version"], 
                      check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        return True
    except subprocess.CalledProcessError:
        return False

def install_requirements():
    """Install required packages."""
    print("Installing required packages...")
    try:
        subprocess.run([sys.executable, "-m", "pip", "install", "-r", "requirements.txt"], 
                      check=True)
        print("Requirements installed successfully.")
    except subprocess.CalledProcessError as e:
        print(f"Error installing requirements: {e}")
        return False
    return True

def check_spotdl():
    """Check if spotdl is installed and install it if needed."""
    print("Checking for spotdl...")
    try:
        subprocess.run(["spotdl", "--version"], 
                      check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        print("spotdl is already installed.")
        return True
    except (subprocess.CalledProcessError, FileNotFoundError):
        print("spotdl not found. Installing...")
        try:
            subprocess.run([sys.executable, "-m", "pip", "install", "spotdl"], 
                          check=True)
            print("spotdl installed successfully.")
            return True
        except subprocess.CalledProcessError as e:
            print(f"Error installing spotdl: {e}")
            return False

def setup_config_directory():
    """Set up the config directory."""
    config_dir = Path("config")
    if not config_dir.exists():
        config_dir.mkdir()
        print("Created config directory.")
    
    # Create default settings file if it doesn't exist
    settings_file = config_dir / "spotdl_settings.json"
    if not settings_file.exists():
        import json
        default_settings = {
            "format": "mp3",
            "bitrate": "auto",
            "output": "{title}.{output-ext}",
            "lyrics": "genius",
            "audio": "youtube",
            "generate_lrc": False,
            "sponsor_block": False,
            "playlist_numbering": False
        }
        with open(settings_file, "w") as f:
            json.dump(default_settings, f, indent=4)
        print("Created default settings file.")
    
    # Create or update config/settings.ini if needed
    settings_ini = config_dir / "settings.ini"
    if not settings_ini.exists():
        with open(settings_ini, "w") as f:
            f.write("""[DEFAULT]
CLIENT_ID = ce35becc8d5140bbab7842e02bff1628
CLIENT_SECRET = b25da51933084f388684c4ba4e02ea00
REDIRECT_URI = http://127.0.0.1:8080

[SETTINGS]
DOWNLOAD_LIKED = True
UPDATE_FREQUENCY = daily
DOWNLOAD_LOCATION = data/
""")
        print("Created settings.ini file.")

def main():
    print("Setting up Spotify Downloader...")
    
    # Check for pip
    if not check_pip():
        print("Error: pip not installed or not working properly.")
        return
    
    # Install requirements
    if not install_requirements():
        return
    
    # Check for spotdl
    if not check_spotdl():
        return
    
    # Set up config directory
    setup_config_directory()
    
    print("\nSetup complete! You can now run the application with:")
    print("  python -m src.tui")

if __name__ == "__main__":
    main()
