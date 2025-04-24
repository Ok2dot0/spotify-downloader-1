#!/usr/bin/env python3
"""
Spotify Album Downloader and Burner

This script allows you to search for songs or albums on Spotify,
display them with details, and
then download them using spotdl and burn them to a CD/DVD.
"""

import os
import sys
import argparse
import json
import tempfile
import shutil
import time
import re
import requests
from io import BytesIO
from PIL import Image
import subprocess
import msvcrt  # For Windows key detection
import dotenv
import threading
import queue
import logging
from functools import partial
from concurrent.futures import ThreadPoolExecutor
from colorama import init, Fore, Back, Style
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.layout import Layout
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TimeRemainingColumn
from rich.prompt import Confirm, Prompt, IntPrompt
from rich import box
import spotipy
from spotipy.oauth2 import SpotifyClientCredentials
from unittest.mock import MagicMock  # For tests

# Import pywin32 for IMAPI2 only on Windows
if sys.platform == "win32" or sys.platform == "win64":
    try:
        import win32com.client
        import pythoncom
        from win32com.client import constants
        import comtypes
        import win32api
        WINDOWS_IMAPI_AVAILABLE = True
    except ImportError:
        WINDOWS_IMAPI_AVAILABLE = False
else:
    WINDOWS_IMAPI_AVAILABLE = False

# Initialize colorama for cross-platform colored terminal output
init()
console = Console()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("spotify_burner.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("spotify_burner")

# Load environment variables from .env file
dotenv.load_dotenv()

# Constants
DEFAULT_OUTPUT_DIR = os.path.join(os.path.expanduser("~"), "Music", "SpotifyDownloads")
CONFIG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.json")
VERSION = "2.0.0"  # Updated version number

# Application state
app_state = {
    "download_queue": queue.Queue(),
    "current_downloads": 0,
    "max_concurrent_downloads": 3  # Default concurrent downloads
}

class SpotifyBurner:
    def __init__(self):
        """Initialize the SpotifyBurner application."""
        self.spotify = None
        self.config = self.load_config()
        self.download_dir = self.config.get("download_dir", DEFAULT_OUTPUT_DIR)
        self.dvd_drive = self.config.get("dvd_drive", None)
        self.max_threads = self.config.get("max_threads", 3)
        self.audio_format = self.config.get("audio_format", "mp3")
        self.bitrate = self.config.get("bitrate", "320k")
        self.theme = self.config.get("theme", "default")
        self.burn_method = self.config.get("burn_method", "windows_native")
        # Prepare burn settings with defaults merged with user config
        defaults = {
            "cdburnerxp_path": "C:\\Program Files\\CDBurnerXP\\cdbxpcmd.exe",
            "speed": None,
            "verify": True,
            "eject": True
        }
        user_burn = self.config.get("burn_settings", {}) or {}
        self.burn_settings = {**defaults, **user_burn}
        self.metadata_settings = self.config.get("metadata_settings", {
            "save_album_art": True,
            "embed_lyrics": False,
            "overwrite_metadata": True
        })
        self.download_queue = queue.Queue()
        self.download_threads = []
        self.stop_threads = False
        app_state["max_concurrent_downloads"] = self.max_threads
        
        # Set up the download thread pool
        self.executor = ThreadPoolExecutor(max_workers=self.max_threads)
        
        # Initialize theme
        self.apply_theme(self.theme)
        
    def load_config(self):
        """Load configuration from config file or create default."""
        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, 'r') as f:
                    return json.load(f)
            except json.JSONDecodeError:
                logger.error("Config file is corrupted. Using defaults.")
                console.print("[bold red]Error: Config file is corrupted. Using defaults.[/bold red]")
                return {}
        return {}

    def save_config(self):
        """Save current configuration to config file."""
        config = {
            "download_dir": self.download_dir,
            "dvd_drive": self.dvd_drive,
            "max_threads": self.max_threads,
            "audio_format": self.audio_format,
            "bitrate": self.bitrate,
            "theme": self.theme,
            "burn_method": self.burn_method,
            "burn_settings": self.burn_settings,
            "metadata_settings": self.metadata_settings
        }
        
        try:
            os.makedirs(os.path.dirname(CONFIG_FILE), exist_ok=True)
            with open(CONFIG_FILE, 'w') as f:
                json.dump(config, f, indent=4)
            logger.info("Configuration saved successfully.")
        except Exception as e:
            logger.error(f"Error saving configuration: {e}")
            console.print(f"[bold red]Error saving configuration: {e}[/bold red]")

    def apply_theme(self, theme_name):
        """Apply the selected theme.
        
        Sets the appropriate color scheme based on the selected theme.
        
        Args:
            theme_name: Name of the theme to apply (default, dark, light)
        """
        # Theme definitions
        themes = {
            "default": {
                "main_color": "cyan",
                "accent_color": "green", 
                "warning_color": "yellow",
                "error_color": "red",
                "success_color": "green",
                "header_style": "bold blue",
                "border_style": "cyan",
                "box_type": box.ROUNDED
            },
            "dark": {
                "main_color": "blue", 
                "accent_color": "cyan",
                "warning_color": "yellow",
                "error_color": "red",
                "success_color": "green",
                "header_style": "bold cyan",
                "border_style": "blue",
                "box_type": box.HEAVY
            },
            "light": {
                "main_color": "magenta",
                "accent_color": "blue",
                "warning_color": "orange3",
                "error_color": "red",
                "success_color": "green",
                "header_style": "bold magenta",
                "border_style": "magenta",
                "box_type": box.SQUARE
            }
        }
        
        # Set the theme - if not found, use default
        if theme_name not in themes:
            theme_name = "default"
            
        theme = themes[theme_name]
            
        # Store the theme colors in the app state for easy access
        app_state["theme"] = {
            "main": theme["main_color"],
            "accent": theme["accent_color"],
            "warning": theme["warning_color"],
            "error": theme["error_color"],
            "success": theme["success_color"],
            "header": theme["header_style"],
            "border": theme["border_style"],
            "box": theme["box_type"]
        }
        
        self.theme = theme_name
        logger.info(f"Applied theme: {theme_name}")

    def initialize_spotify(self):
        """Initialize the Spotify API client."""
        # Try to get credentials from environment variables
        client_id = os.getenv("SPOTIPY_CLIENT_ID")
        client_secret = os.getenv("SPOTIPY_CLIENT_SECRET")
        
        # If not found, prompt the user
        if not client_id or not client_secret:
            console.print("[yellow]Spotify API credentials not found in environment variables.[/yellow]")
            console.print("[bold]Please set up your Spotify API credentials:[/bold]")
            console.print("1. Go to https://developer.spotify.com/dashboard/")
            console.print("2. Create an app and get your Client ID and Client Secret")
            console.print("3. Enter them below or add to .env file for future use")
            
            if not client_id:
                client_id = input(Fore.GREEN + "Enter your Spotify Client ID: " + Style.RESET_ALL)
            if not client_secret:
                client_secret = input(Fore.GREEN + "Enter your Spotify Client Secret: " + Style.RESET_ALL)
            
            # Save to .env file if user wants
            if Confirm.ask("Save credentials to .env file for future use?"):
                with open(".env", "w") as f:
                    f.write(f"SPOTIPY_CLIENT_ID={client_id}\n")
                    f.write(f"SPOTIPY_CLIENT_SECRET={client_secret}\n")
                console.print("[green]Credentials saved to .env file[/green]")
        
        try:
            client_credentials_manager = SpotifyClientCredentials(
                client_id=client_id, client_secret=client_secret
            )
            self.spotify = spotipy.Spotify(client_credentials_manager=client_credentials_manager)
            # Test the connection
            self.spotify.search("test", limit=1)
            logger.info("Spotify API connection successful")
            return True
        except spotipy.SpotifyException as e:
            logger.error(f"Error connecting to Spotify API: {e}")
            console.print(f"[bold red]Error connecting to Spotify API: {e}[/bold red]")
            return False
        except Exception as e:
            logger.error(f"Unexpected error connecting to Spotify API: {e}")
            console.print(f"[bold red]Unexpected error: {e}[/bold red]")
            return False

    def search_and_download(self):
        """Search for and download music from Spotify."""
        console.clear()
        
        # Show search header
        console.print("[bold cyan]SEARCH AND DOWNLOAD MUSIC[bold cyan]")
        console.print("=" * 50)
        
        # Get search query
        query = Prompt.ask("Enter song or album name to search")
        if not query:
            return
        
        # Search for music
        selection = self.search_music(query)
        if not selection:
            self.wait_for_keypress()
            return
        
        # Display detailed information and get tracks
        tracks = self.display_music_info(selection)
        
        # Get album URL for more efficient album downloads
        album_url = None
        if selection["type"] == "album":
            album_url = selection["item"]["external_urls"].get("spotify")
        
        # Confirm download
        if not Confirm.ask("\nDo you want to download these tracks?"):
            return
        
        # Create album-specific directory for the download
        output_dir = None
        if selection["type"] == "album":
            # Create directory with "Artist - Album" format
            album_name = selection["item"]["name"]
            artist_name = selection["item"]["artists"][0]["name"]
            album_dir = f"{artist_name} - {album_name}"
            output_dir = os.path.join(self.download_dir, album_dir)
        else:
            # For single tracks, use the parent album info if available
            track = selection["item"]
            if "album" in track:
                album_name = track["album"]["name"]
                artist_name = track["artists"][0]["name"]
                album_dir = f"{artist_name} - {album_name}"
                output_dir = os.path.join(self.download_dir, album_dir)
        
        # Download tracks
        success = self.download_tracks(tracks, output_dir, album_url)
        
        if not success:
            console.print("[red]Download failed or was incomplete![red]")
            self.wait_for_keypress()
            return
        
        # Enhance metadata
        self.enhance_download_metadata(selection, output_dir)
        
        # Ask about burning
        if Confirm.ask("\nDo you want to burn these tracks to CD/DVD?"):
            self.burn_to_disc(output_dir, self.dvd_drive)
        
        self.wait_for_keypress()

    def detect_optical_drives(self):
        """Detect optical drives on the system."""
        drives = []
        
        # Windows-specific code to detect optical drives
        if sys.platform == "win32" or sys.platform == "win64":
            if WINDOWS_IMAPI_AVAILABLE:
                try:
                    # Initialize COM for this thread
                    pythoncom.CoInitialize()
                    
                    # Create IMAPI2 disc master
                    disc_master = win32com.client.Dispatch("IMAPI2.MsftDiscMaster2")
                    disc_recorder = win32com.client.Dispatch("IMAPI2.MsftDiscRecorder2")
                    
                    # Enumerate all disc recorders
                    for i in range(disc_master.Count):
                        unique_id = disc_master.Item(i)
                        disc_recorder.InitializeDiscRecorder(unique_id)
                        
                        # Get the drive letter
                        drive_letter = disc_recorder.VolumePathNames(0)
                        drives.append(drive_letter)
                        
                        logger.info(f"Found optical drive: {drive_letter}")
                        
                except Exception as e:
                    logger.error(f"Error detecting optical drives via IMAPI2: {e}")
                    # Fallback to the standard method
                    drives = self._detect_optical_drives_fallback()
                finally:
                    # Clean up COM
                    pythoncom.CoUninitialize()
            else:
                # Use fallback if pywin32 is not available
                drives = self._detect_optical_drives_fallback()
        else:
            # For Unix-based systems
            if os.path.exists('/dev/cdrom'):
                drives.append('/dev/cdrom')
            if os.path.exists('/dev/dvd'):
                drives.append('/dev/dvd')
        
        return drives
        
    def _detect_optical_drives_fallback(self):
        """Fallback method to detect optical drives using standard Windows API."""
        drives = []
        
        # Windows-specific code to detect optical drives
        if sys.platform == "win32" or sys.platform == "win64":
            # Import ctypes within the method to avoid import issues on non-Windows platforms
            import ctypes
            
            for drive in range(ord('A'), ord('Z')+1):
                drive_letter = chr(drive) + ':'
                try:
                    drive_type = ctypes.windll.kernel32.GetDriveTypeW(drive_letter)
                    # DRIVE_CDROM = 5
                    if drive_type == 5:
                        drives.append(drive_letter)
                        logger.info(f"Found optical drive (fallback): {drive_letter}")
                except Exception as e:
                    logger.debug(f"Error checking drive {drive_letter}: {e}")
                    pass
                    
        return drives

    def burn_to_disc(self, source_dir, drive=None):
        """Burn files to CD/DVD using CDBurnerXP command-line.
        
        Args:
            source_dir: Directory containing files to burn
            drive: Drive letter to burn to
            
        Returns:
            bool: True if burning was successful, False otherwise
        """
        logger.info(f"Starting automatic disc burning process for {source_dir}")
        console.print("[bold cyan]Starting automatic disc burning process...[/bold cyan]")
        
        # Non-Windows platform checks
        if sys.platform != "win32" and sys.platform != "win64":
            logger.error("CD/DVD burning is only supported on Windows")
            console.print("[red]Automated CD/DVD burning is only supported on Windows.[red]")
            
            # For non-Windows, we have to use manual instructions
            self.show_manual_burn_instructions(source_dir)
            return False
        
        # Use CDBurnerXP command-line for burning; fall back to default if not set
        default_exe = "C:\\Program Files\\CDBurnerXP\\cdbxpcmd.exe"
        cdburnerxp_path = self.burn_settings.get("cdburnerxp_path") or default_exe
        if not os.path.exists(cdburnerxp_path):
            logger.error(f"CDBurnerXP not found at {cdburnerxp_path}")
            console.print(f"[bold red]Error: CDBurnerXP not found at {cdburnerxp_path}[/bold red]")
            self.show_manual_burn_instructions(source_dir)
            return False
        try:
            # Prepare disc label
            dir_name = os.path.basename(source_dir)
            # Use only album name (after ' - ')
            if ' - ' in dir_name:
                disc_label = dir_name.split(' - ', 1)[1]
            else:
                disc_label = dir_name or f"SpotifyMusic_{time.strftime('%Y%m%d')}"
            disc_label = re.sub(r'[^\w\s-]', '', disc_label).strip()
            disc_label = disc_label[:16] if len(disc_label) > 16 else disc_label
            # Detect and select drive
            optical_drives = self.detect_optical_drives()
            if not optical_drives:
                logger.error("No optical drives detected for burning")
                console.print("[bold red]Error: No optical drives detected[/bold red]")
                self.show_manual_burn_instructions(source_dir)
                return False
            selected_drive = (drive or optical_drives[0]).replace(':', '')
            # Determine burn action and source folder based on content
            video_ts = os.path.join(source_dir, 'VIDEO_TS')
            # Check for VIDEO_TS folder for DVD-Video
            if os.path.isdir(video_ts):
                action = '--burn-video'
                burn_folder = video_ts
            else:
                # Check if folder contains only audio files
                audio_exts = ('.mp3', '.wav', '.ogg', '.flac', '.m4a', '.aac')
                files = [f for f in os.listdir(source_dir) if os.path.isfile(os.path.join(source_dir, f))]
                if files and all(f.lower().endswith(audio_exts) for f in files):
                    action = '--burn-audio'
                    burn_folder = source_dir
                else:
                    action = '--burn-data'
                    burn_folder = source_dir
            # Build CLI arguments
            cmd = [
                cdburnerxp_path,
                action,
                f'-device:{selected_drive}',
                f'-folder:"{burn_folder}"',
                f'-name:{disc_label}'
            ]
            # Add audio-specific mode
            if action == '--burn-audio':
                cmd.append('-dao')  # Disc-at-once for gapless
            # Add speed if configured
            if self.burn_settings.get("speed"):
                cmd.append(f'-speed:{self.burn_settings.get("speed")}')
            if self.burn_settings.get("verify"):
                cmd.append('-verify')
            if self.burn_settings.get("eject"):
                cmd.append('-eject')
            # Finalize disc
            cmd.append('-close')
            console.print("[cyan]Launching CDBurnerXP burning process...[/cyan]")
            logger.info(f"Executing CDBurnerXP command: {' '.join(cmd)}")
            # Run and capture output
            process = subprocess.run(cmd, capture_output=True, text=True)
            if process.returncode == 0:
                console.print("[green]Burn completed successfully![/green]")
                logger.info("Burn completed successfully")
                return True
            else:
                error_msg = process.stderr or process.stdout or "Unknown error"
                logger.error(f"Error during burn process: {error_msg}")
                console.print(f"[bold red]Error during burn: {error_msg}[/bold red]")
                self.show_manual_burn_instructions(source_dir)
                return False
        except Exception as e:
            logger.error(f"Error during burn process: {e}")
            console.print(f"[bold red]Error during burn process: {e}[bold red]")
            self.show_manual_burn_instructions(source_dir)
            return False

    def show_manual_burn_instructions(self, source_dir):
        """Display manual instructions for burning files to CD/DVD."""
        console.print("\n[bold cyan]Manual CD/DVD Burning Instructions[bold cyan]")
        console.print("=" * 50)
        console.print(f"Your downloaded files are located in:\n[bold]{source_dir}[bold]\n")
        
        if sys.platform == "win32" or sys.platform == "win64":
            console.print("[bold]Windows Instructions:[bold]")
            console.print("1. Insert a blank CD/DVD into your drive")
            console.print("2. Open File Explorer and navigate to the download folder")
            console.print("3. Select all files you want to burn")
            console.print("4. Right-click and select 'Send to' → 'DVD RW Drive'")
            console.print("5. In the Windows disc burning wizard, enter a disc title")
            console.print("6. Click 'Next' and follow the on-screen instructions")
        
        elif sys.platform == "darwin":  # macOS
            console.print("[bold]macOS Instructions:[bold]")
            console.print("1. Insert a blank CD/DVD into your drive")
            console.print("2. Open Finder and navigate to the download folder")
            console.print("3. Select all files you want to burn")
            console.print("4. Right-click and select 'Burn [items] to Disc'")
            console.print("5. Follow the on-screen instructions")
        
        else:  # Linux
            console.print("[bold]Linux Instructions:[bold]")
            console.print("1. Insert a blank CD/DVD into your drive")
            console.print("2. Use a burning application like Brasero, K3b, or Xfburn")
            console.print("3. Create a new audio CD project")
            console.print("4. Add the music files from the download folder")
            console.print("5. Start the burning process and follow the application's instructions")
        
        # Wait for user acknowledgment
        self.wait_for_keypress("Press any key to continue...")

    def show_header(self):
        """Display the application header."""
        header = """
[bold cyan]╔══════════════════════════════════════════════════════════════════════╗[bold cyan]
[bold cyan]║                                                                      ║[bold cyan]
[bold cyan]║      [bold white]SPOTIFY ALBUM DOWNLOADER AND BURNER v{VERSION}[bold white]                  ║[bold cyan]
[bold cyan]║                                                                      ║[bold cyan]
[bold cyan]╚══════════════════════════════════════════════════════════════════════╝[bold cyan]
        """.format(VERSION=VERSION)
        
        console.print(header)
        console.print("[bold]Search, download, and burn your favorite music![bold]\n")

    def show_main_menu(self):
        """Display the main menu and handle user input."""
        while True:
            console.clear()
            self.show_header()
            
            # Create options table
            table = Table(show_header=False, box=box.SIMPLE_HEAD, show_edge=False)
            table.add_column("Key", style="cyan", justify="right")
            table.add_column("Option", style="white")
            
            table.add_row("[1]", "[bold green]Manage Existing Albums[bold green] - Play, burn or delete your downloaded albums")
            table.add_row("[2]", "[bold cyan]Search & Download[bold cyan] - Find and download new music from Spotify")
            table.add_row("[3]", "[bold magenta]Video Management[bold magenta] - Download and manage videos")
            table.add_row("[4]", "[bold yellow]Settings[bold yellow] - Configure download and burning options")
            table.add_row("[5]", "[bold blue]About[bold blue] - Information about this application")
            table.add_row("[Q]", "[bold red]Exit[bold red] - Quit the application")
            
            console.print(table)
            console.print()
            
            choice = Prompt.ask(
                "Select an option",
                choices=["1", "2", "3", "4", "5", "Q", "q"],
                default="2"
            ).upper()
            
            if choice == "1":
                self.show_existing_albums()
            elif choice == "2":
                self.search_and_download()
            elif choice == "3":
                self.show_video_menu()
            elif choice == "4":
                self.manage_settings()
            elif choice == "5":
                self.about_app()
            elif choice == "Q":
                console.print("[bold green]Thank you for using Spotify Album Downloader and Burner![bold green]")
                return

    def show_existing_albums(self):
        """Display existing albums and provide options to manage them."""
        albums = self.scan_existing_albums()
        
        if not albums:
            console.print("[yellow]No albums found in your download directory.[/yellow]")
            self.wait_for_keypress("Press any key to return to the main menu...")
            return False
            
        while True:
            console.clear()
            console.print(f"\n[bold green]Found {len(albums)} existing albums:[bold green]")
            
            # Create a table to display the albums
            table = Table(title="Your Music Library", show_header=True, header_style="bold blue", box=box.ROUNDED)
            table.add_column("#", style="dim", width=4)
            table.add_column("Album", style="cyan")
            table.add_column("Artist", style="green")
            table.add_column("Tracks", justify="right")
            table.add_column("Size (MB)", justify="right")
            table.add_column("Date Added", justify="right")
            
            # Add rows to the table
            for i, album in enumerate(albums):
                table.add_row(
                    str(i + 1),
                    album['name'],
                    album['artist'],
                    str(album['tracks']),
                    str(album['size']),
                    album['date']
                )
            
            console.print(table)
            
            # Provide options to manage albums
            console.print("\n[bold]Album Management Options:[bold]")
            console.print("[1] [cyan]Play album[cyan] (opens in default player)")
            console.print("[2] [green]Burn album to CD/DVD[green]")
            console.print("[3] [blue]Burn multiple albums to CD/DVD[blue]")
            console.print("[4] [red]Delete album[red]")
            console.print("[5] [yellow]Return to main menu[yellow]")
            
            choice = Prompt.ask("Enter your choice", choices=["1", "2", "3", "4", "5"], default="5")
                
            if choice == "1":  # Play album
                album_index = self.prompt_for_album_number(albums) - 1
                if 0 <= album_index < len(albums):
                    self.play_album(albums[album_index]['path'])
                    self.wait_for_keypress("Press any key to continue...")
                    
            elif choice == "2":  # Burn single album
                album_index = self.prompt_for_album_number(albums) - 1
                if 0 <= album_index < len(albums):
                    self.burn_to_disc(albums[album_index]['path'], self.dvd_drive)
                    self.wait_for_keypress("Press any key to continue...")
            
            elif choice == "3":  # Burn multiple albums
                nums = self.prompt_for_album_numbers(albums)
                selected = [albums[n-1]['path'] for n in nums]
                temp_dir = tempfile.mkdtemp()
                for p in selected:
                    shutil.copytree(p, os.path.join(temp_dir, os.path.basename(p)))
                self.burn_to_disc(temp_dir, self.dvd_drive)
                shutil.rmtree(temp_dir, ignore_errors=True)
                self.wait_for_keypress("Press any key to continue...")
            
            elif choice == "4":  # Delete album
                album_index = self.prompt_for_album_number(albums) - 1
                if 0 <= album_index < len(albums):
                    if Confirm.ask(f"Are you sure you want to delete '{albums[album_index]['name']}'?"):
                        self.delete_album(albums[album_index]['path'])
                        # Refresh the album list
                        albums = self.scan_existing_albums()
                        if not albums:
                            # No more albums left
                            console.print("[yellow]No more albums in your library.[yellow]")
                            self.wait_for_keypress("Press any key to return to the main menu...")
                            return False
                        
            elif choice == "5":  # Return to main menu
                return True

    def scan_existing_albums(self):
        """Scan the download directory for existing albums.
        
        Returns:
            list: A list of dictionaries with album information
        """
        console.print("[bold blue]Scanning for existing albums...[bold blue]")
        
        # Make sure the download directory exists
        if not os.path.exists(self.download_dir):
            os.makedirs(self.download_dir, exist_ok=True)
            console.print(f"[yellow]Created new download directory: {self.download_dir}[yellow]")
            return []
            
        # Get all subdirectories in the download directory
        albums = []
        
        try:
            # Walk through the download directory to find all subdirectories (albums)
            subdirs = [d for d in os.listdir(self.download_dir) 
                      if os.path.isdir(os.path.join(self.download_dir, d))]
            
            if not subdirs:
                console.print("[yellow]No existing albums found.[yellow]")
                return []
                
            # Process each subdirectory as a potential album
            for album_dir in subdirs:
                album_path = os.path.join(self.download_dir, album_dir)
                
                # Count the number of audio files in the directory
                audio_files = [f for f in os.listdir(album_path) 
                              if f.lower().endswith(('.mp3', '.flac', '.ogg', '.m4a', '.wav'))]
                
                if not audio_files:
                    continue  # Skip directories without audio files
                
                # Get the creation date of the directory
                try:
                    created_date = time.strftime('%Y-%m-%d', 
                                                time.localtime(os.path.getctime(album_path)))
                except:
                    created_date = "Unknown"
                
                # Attempt to extract artist name and album name from directory name
                parts = album_dir.split(' - ', 1)
                if len(parts) > 1:
                    artist = parts[0]
                    title = parts[1]
                else:
                    artist = "Unknown"
                    title = album_dir
                
                # Calculate total size
                total_size = sum(os.path.getsize(os.path.join(album_path, f)) 
                                for f in os.listdir(album_path) 
                                if os.path.isfile(os.path.join(album_path, f)))
                
                # Convert to MB with 2 decimal places
                size_mb = round(total_size / (1024 * 1024), 2)
                
                albums.append({
                    'name': title,
                    'artist': artist,
                    'path': album_path,
                    'tracks': len(audio_files),
                    'date': created_date,
                    'size': size_mb
                })
                
            # Sort albums by date (newest first)
            albums.sort(key=lambda x: x['date'], reverse=True)
            
            logger.info(f"Found {len(albums)} albums in {self.download_dir}")
            return albums
            
        except Exception as e:
            logger.error(f"Error scanning for albums: {e}")
            console.print(f"[red]Error scanning for albums: {e}[red]")
            return []

    def wait_for_keypress(self, message="Press any key to continue..."):
        """Wait for any key to be pressed."""
        console.print(f"\n{message}", style="bold yellow")
        
        if sys.platform == "win32" or sys.platform == "win64":
            msvcrt.getch()  # Windows
        else:
            input()  # Unix-based systems (Enter key)

    def prompt_for_album_number(self, albums):
        """Prompt user to select an album number."""
        while True:
            try:
                album_num = int(Prompt.ask(f"Enter album number [1-{len(albums)}]"))
                if 1 <= album_num <= len(albums):
                    return album_num
                else:
                    console.print(f"[red]Please enter a number between 1 and {len(albums)}[/red]")
            except ValueError:
                console.print("[red]Please enter a valid number[/red]")

    def prompt_for_album_numbers(self, albums):
        """Prompt user to select one or multiple album numbers."""
        while True:
            input_str = Prompt.ask(f"Enter album numbers separated by commas [1-{len(albums)}]")
            try:
                nums = [int(x.strip()) for x in input_str.split(',')]
                if all(1 <= n <= len(albums) for n in nums):
                    return list(dict.fromkeys(nums))
                else:
                    console.print(f"[red]Numbers must be between 1 and {len(albums)}[/red]")
            except ValueError:
                console.print("[red]Please enter valid numbers separated by commas[/red]")

    def prompt_for_video_urls(self):
        """Prompt user to enter one or multiple video URLs separated by commas."""
        input_str = Prompt.ask("Enter video URLs separated by commas")
        return [url.strip() for url in input_str.split(',') if url.strip()]

    def filter_videos_by_type(self, videos):
        """Filter video list by audio-only, video-only, or both."""
        console.print("\n[bold]Filter by type:[/bold]")
        console.print("[1] Audio only")
        console.print("[2] Video only")
        console.print("[3] Both")
        choice = Prompt.ask("Select type filter", choices=["1","2","3"], default="3")
        audio_ext = ['.m4a', '.mp3', '.opus']
        video_ext = ['.mp4', '.mkv', '.webm', '.avi', '.mov', '.flv']
        if choice == '1':
            videos = [v for v in videos if os.path.splitext(v['name'])[1].lower() in audio_ext]
        elif choice == '2':
            videos = [v for v in videos if os.path.splitext(v['name'])[1].lower() in video_ext]
        return videos

    def filter_videos_by_extension(self, videos):
        """Filter video list by file extension."""
        exts = sorted({os.path.splitext(v['name'])[1].lower() for v in videos})
        if not exts:
            return videos
        console.print("\n[bold]Filter by extension:[/bold]")
        choices = exts + ["All"]
        choice = Prompt.ask("Select extension or All", choices=choices, default="All")
        if choice != "All":
            videos = [v for v in videos if os.path.splitext(v['name'])[1].lower() == choice]
        return videos

    def filter_videos_by_resolution(self, videos):
        """Filter video list by resolution and FPS."""
        resos = set()
        fps_set = set()
        for v in videos:
            name = v['name']
            # resolution patterns
            m = re.search(r'(\d{3,4}x\d{3,4})', name)
            if m:
                resos.add(m.group(1))
            # '360p' style
            for m2 in re.findall(r'(\d{3,4}p)', name):
                resos.add(m2)
            # fps patterns
            m3 = re.search(r'(\d{2,3})fps', name)
            if m3:
                fps_set.add(m3.group(1))
        # filter by resolution
        if resos:
            console.print("\n[bold]Filter by resolution:[/bold]")
            res_choices = sorted(resos) + ["All"]
            choice = Prompt.ask("Select resolution or All", choices=res_choices, default="All")
            if choice != "All":
                videos = [v for v in videos if choice in v['name']]
        # filter by fps
        if fps_set:
            console.print("\n[bold]Filter by FPS:[/bold]")
            fps_choices = sorted(fps_set) + ["All"]
            choice = Prompt.ask("Select FPS or All", choices=fps_choices, default="All")
            if choice != "All":
                videos = [v for v in videos if f"{choice}fps" in v['name']]
        return videos

    def filter_formats_by_type(self, formats):
        """Filter format list by audio-only, video-only, or both."""
        console.print("\n[bold]Format type filter:[/bold]")
        console.print("[1] Audio only")
        console.print("[2] Video only")
        console.print("[3] Both")
        choice = Prompt.ask("Select format type", choices=["1","2","3"], default="3")
        if choice == '1': return [(c,d) for c,d in formats if 'audio only' in d]
        if choice == '2': return [(c,d) for c,d in formats if 'video only' in d]
        return formats

    def filter_formats_by_extension(self, formats):
        """Filter format list by file extension (first word in description)."""
        exts = sorted({d.split()[0] for _,d in formats})
        console.print("\n[bold]Extension filter:[/bold]")
        console.print("All / " + ", ".join(exts))
        choice = Prompt.ask("Select extension or All", choices=exts + ["All"], default="All")
        if choice != 'All': formats = [(c,d) for c,d in formats if d.split()[0]==choice]
        return formats

    def filter_formats_by_resolution(self, formats):
        """Filter format list by resolution and fps."""
        resos = set(); fps_set = set()
        for _,desc in formats:
            # resolution patterns
            m = re.search(r'(\d{3,4}x\d{3,4}|\d{3,4}p)', desc)
            if m: resos.add(m.group(1))
            m2 = re.search(r'(\d{2,3})fps', desc)
            if m2: fps_set.add(m2.group(1))
        if resos:
            console.print("\n[bold]Resolution filter:[/bold] "+ ", ".join(sorted(resos)) + ", All")
            choice = Prompt.ask("Select resolution or All", choices=sorted(resos)+["All"], default="All")
            if choice!='All': formats=[(c,d) for c,d in formats if choice in d]
        if fps_set:
            console.print("\n[bold]FPS filter:[/bold] "+ ", ".join(sorted(fps_set)) + ", All")
            choice = Prompt.ask("Select FPS or All", choices=sorted(fps_set)+["All"], default="All")
            if choice!='All': formats=[(c,d) for c,d in formats if choice+'fps' in d]
        return formats

    def download_videos(self, urls):
        """Download videos using yt-dlp into a Videos subdirectory, letting user pick format."""
        videos_dir = os.path.join(self.download_dir, "Videos")
        os.makedirs(videos_dir, exist_ok=True)
        downloaded = []
        for url in urls:
            console.print(f"[magenta]Fetching available formats for: {url}[/magenta]")
            proc = subprocess.run(["yt-dlp", "-F", url], capture_output=True, text=True)
            output = proc.stdout or proc.stderr
            all_formats = []
            for line in output.splitlines():
                parts = line.split(None, 3)
                if parts and parts[0].isdigit():
                    all_formats.append((parts[0], ' '.join(parts[1:])))
            # hierarchical filtering submenus
            fmts = self.filter_formats_by_type(all_formats)
            fmts = self.filter_formats_by_extension(fmts)
            fmts = self.filter_formats_by_resolution(fmts)
            if not fmts:
                console.print("[yellow]No formats match filters; showing all formats[/yellow]")
                fmts = all_formats
            # prompt from filtered list
            table = Table(title="Available Formats", show_header=True, header_style="bold cyan", box=box.SIMPLE)
            table.add_column("Code", style="yellow", width=6)
            table.add_column("Description", style="white", max_width=60, overflow="fold")
            for code,desc in fmts:
                table.add_row(code, desc)
            console.print(table)
            choices = [code for code,_ in fmts]
            fmt = Prompt.ask("Select format code to download", choices=choices)
            console.print(f"[magenta]Downloading video: {url}[/magenta]")
            cmd = ["yt-dlp", "-f", fmt, "-o", os.path.join(videos_dir, "%(title)s.%(ext)s"), url]
            try:
                process = subprocess.run(cmd, capture_output=True, text=True)
                if process.returncode == 0:
                    console.print(f"[green]Downloaded: {url}[/green]")
                    downloaded.append(url)
                else:
                    console.print(f"[red]Error downloading {url}: {process.stderr or process.stdout}[/red]")
            except Exception as e:
                console.print(f"[red]Exception downloading {url}: {e}[/red]")
        return downloaded

    def scan_existing_videos(self):
        """Scan the Videos subdirectory for downloaded video files."""
        videos_dir = os.path.join(self.download_dir, "Videos")
        if not os.path.exists(videos_dir):
            return []
        items = []
        for f in os.listdir(videos_dir):
            full = os.path.join(videos_dir, f)
            if os.path.isfile(full) and f.lower().endswith(('.mp4', '.mkv', '.webm', '.avi', '.mov', '.flv')):
                size_mb = round(os.path.getsize(full) / (1024 * 1024), 2)
                items.append({'name': f, 'path': full, 'size': size_mb})
        return items

    def play_video(self, video_path):
        """Open a video file with the default system handler."""
        console.print(f"[bold]Playing video:[/bold] {video_path}")
        try:
            if sys.platform == "win32":
                os.startfile(video_path)
            elif sys.platform == "darwin":
                subprocess.run(["open", video_path])
            else:
                subprocess.run(["xdg-open", video_path])
        except Exception as e:
            console.print(f"[red]Error playing video: {e}[/red]")

    def show_video_menu(self):
        """Sub-menu for downloading and managing videos."""
        while True:
            console.clear()
            console.print("\n[bold magenta]Video Management Menu[bold magenta]")
            console.print("[1] [cyan]Download videos from URLs[/cyan]")
            console.print("[2] [green]Manage existing videos[/green]")
            console.print("[3] [yellow]Return to main menu[/yellow]")
            choice = Prompt.ask("Enter your choice", choices=["1", "2", "3"], default="3")
            if choice == "1":
                urls = self.prompt_for_video_urls()
                self.download_videos(urls)
                self.wait_for_keypress()
            elif choice == "2":
                # scan and apply filters
                videos = self.scan_existing_videos()
                videos = self.filter_videos_by_type(videos)
                videos = self.filter_videos_by_extension(videos)
                videos = self.filter_videos_by_resolution(videos)
                if not videos:
                    console.print("[yellow]No videos match your criteria.[/yellow]")
                    self.wait_for_keypress()
                    continue
                while True:
                    console.clear()
                    console.print(f"\n[bold green]Found {len(videos)} videos:[bold green]")
                    table = Table(title="Your Video Library", show_header=True, header_style="bold blue", box=box.ROUNDED)
                    table.add_column("#", style="dim", width=4)
                    table.add_column("Video", style="cyan")
                    table.add_column("Size (MB)", justify="right")
                    for i, vid in enumerate(videos):
                        table.add_row(str(i+1), vid['name'], str(vid['size']))
                    console.print(table)
                    console.print("\n[bold]Video Management Options:[bold]")
                    console.print("[1] [cyan]Play video(s)[/cyan]")
                    console.print("[2] [green]Burn selected videos[/green]")
                    console.print("[3] [red]Delete selected videos[/red]")
                    console.print("[4] [yellow]Return to video menu[/yellow]")
                    sub = Prompt.ask("Enter your choice", choices=["1", "2", "3", "4"], default="4")
                    if sub == "1":
                        nums = self.prompt_for_album_numbers(videos)
                        for n in nums:
                            self.play_video(videos[n-1]['path'])
                        self.wait_for_keypress()
                    elif sub == "2":
                        nums = self.prompt_for_album_numbers(videos)
                        selected = [videos[n-1]['path'] for n in nums]
                        temp_dir = tempfile.mkdtemp()
                        for p in selected:
                            shutil.copy(p, temp_dir)
                        self.burn_to_disc(temp_dir, self.dvd_drive)
                        shutil.rmtree(temp_dir, ignore_errors=True)
                        self.wait_for_keypress()
                    elif sub == "3":
                        nums = sorted(self.prompt_for_album_numbers(videos), reverse=True)
                        for n in nums:
                            try:
                                os.remove(videos[n-1]['path'])
                                console.print(f"[green]Deleted: {videos[n-1]['name']}[/green]")
                            except Exception as e:
                                logger.error(f"Error deleting video {videos[n-1]['path']}: {e}")
                                console.print(f"[red]Error deleting {videos[n-1]['name']}: {e}[/red]")
                        videos = self.scan_existing_videos()
                        if not videos:
                            console.print("[yellow]No more videos.[/yellow]")
                            self.wait_for_keypress()
                            break
                    elif sub == "4":
                        break

    def manage_settings(self):
        """Manage application settings including CDBurnerXP options."""
        while True:
            console.clear()
            self.show_header()
            table = Table(title="Application Settings", show_header=True, box=box.ROUNDED)
            table.add_column("#", style="cyan", justify="right")
            table.add_column("Setting", style="white")
            table.add_column("Current Value", style="green")
            table.add_row("1", "Download Directory", self.download_dir)
            table.add_row("2", "Optical Drive", self.dvd_drive or "Auto-detect")
            table.add_row("3", "Audio Format", self.audio_format)
            table.add_row("4", "Audio Bitrate", self.bitrate)
            table.add_row("5", "Maximum Threads", str(self.max_threads))
            table.add_row("6", "CDBurnerXP Path", self.burn_settings.get("cdburnerxp_path"))
            table.add_row("7", "Burning Speed", str(self.burn_settings.get("speed") or "Auto"))
            table.add_row("8", "Verify After Burning", "Yes" if self.burn_settings.get("verify") else "No")
            table.add_row("9", "Eject After Burning", "Yes" if self.burn_settings.get("eject") else "No")
            table.add_row("10", "Theme", self.theme)
            console.print(table)
            console.print()
            choice = Prompt.ask(
                "Select setting to change ([bold]B[/bold] to go back)",
                choices=[str(i) for i in range(1,11)] + ["B","b"], default="B"
            ).upper()
            if choice == "B":
                self.save_config()
                break
            elif choice == "1":
                self.download_dir = Prompt.ask("Enter download directory", default=self.download_dir)
            elif choice == "2":
                self.dvd_drive = Prompt.ask("Enter drive letter (e.g. E:)", default=self.dvd_drive or "") or None
            elif choice == "3":
                self.audio_format = Prompt.ask("Enter audio format", default=self.audio_format)
            elif choice == "4":
                self.bitrate = Prompt.ask("Enter audio bitrate", default=self.bitrate)
            elif choice == "5":
                self.max_threads = IntPrompt.ask("Enter maximum download threads (1-10)", choices=range(1,11), default=self.max_threads)
            elif choice == "6":
                self.burn_settings["cdburnerxp_path"] = Prompt.ask(
                    "Enter CDBurnerXP executable path", 
                    default=self.burn_settings.get("cdburnerxp_path")
                )
            elif choice == "7":
                speed = Prompt.ask("Enter burning speed (number or 'Auto')", default=str(self.burn_settings.get("speed") or "Auto"))
                self.burn_settings["speed"] = None if speed.lower() == "auto" else speed
            elif choice == "8":
                self.burn_settings["verify"] = Confirm.ask("Verify disc after burning?", default=self.burn_settings.get("verify"))
            elif choice == "9":
                self.burn_settings["eject"] = Confirm.ask("Eject disc after burning?", default=self.burn_settings.get("eject"))
            elif choice == "10":
                # Theme selection
                theme = Prompt.ask("Select theme", choices=["default","dark","light"], default=self.theme)
                self.apply_theme(theme)

    def about_app(self):
        """Display information about the application."""
        console.clear()
        console.print(Panel(
            f"[bold white]Spotify Album Downloader and Burner v{VERSION}[/bold white]\n"
            f"[bold]Theme:[/bold] {self.theme}\n"
            f"[bold]Download Directory:[/bold] {self.download_dir}\n"
            f"[bold]Max Threads:[/bold] {self.max_threads}\n"
            f"[bold]Format:[/bold] {self.audio_format} @ {self.bitrate}",
            title="About", box=app_state["theme"]["box"],
            border_style=app_state["theme"]["border"]
        ))
        self.wait_for_keypress()

    def run(self, query=None):
        """Run the application with optional command line query.
        
        Args:
            query: Optional search query
        
        Returns:
            int: Exit code (0 for success, 1 for error)
        """
        try:
            # Show the app header
            self.show_header()
            
            # Initialize Spotify API
            if not self.initialize_spotify():
                return 1
                
            if query:
                # Direct mode with query - go straight to search
                selection = self.search_music(query)
                if not selection:
                    return 1
                    
                # Display detailed information and get tracks
                tracks = self.display_music_info(selection)
                
                # Get album URL for more efficient album downloads
                album_url = None
                if selection["type"] == "album":
                    album_url = selection["item"]["external_urls"].get("spotify")
                
                # Confirm download
                if not Confirm.ask("\nDo you want to download these tracks?"):
                    return 0
                
                # Create album-specific directory for the download
                output_dir = None
                if selection["type"] == "album":
                    album_name = selection["item"]["name"]
                    artist_name = selection["item"]["artists"][0]["name"]
                    album_dir = f"{artist_name} - {album_name}"
                    output_dir = os.path.join(self.download_dir, album_dir)
                
                # Download tracks
                if not self.download_tracks(tracks, output_dir, album_url):
                    console.print("[red]Download failed or incomplete![/red]")
                    return 1
                
                # Enhance metadata
                self.enhance_download_metadata(selection, output_dir)
                
                # Ask about burning
                if Confirm.ask("\nDo you want to burn these tracks to CD/DVD?"):
                    if not self.burn_to_disc(output_dir, self.dvd_drive):
                        self.show_manual_burn_instructions(output_dir)
                
                console.print("\n[bold green]Process completed successfully![bold green]")
                return 0
            else:
                # Interactive mode - show the main menu
                self.show_main_menu()
                return 0
                
        except KeyboardInterrupt:
            console.print("\n[yellow]Operation cancelled by user.[/yellow]")
            return 0
        except Exception as e:
            logger.error(f"Unexpected error: {e}")
            console.print(f"[bold red]An unexpected error occurred: {e}[bold red]")
            return 1

def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Spotify Album Downloader and Burner - Search, download, and burn music from Spotify."
    )
    parser.add_argument(
        "query", nargs="?", help="Song or album name to search for (optional)"
    )
    parser.add_argument(
        "-o", "--output", help="Custom output directory for downloads"
    )
    parser.add_argument(
        "--drive", help="Specify CD/DVD drive letter (Windows only)"
    )
    parser.add_argument(
        "-t", "--threads", type=int, help="Maximum number of download threads (1-10)"
    )
    parser.add_argument(
        "--version", action="version", version=f"Spotify Album Downloader and Burner v{VERSION}"
    )
    parser.add_argument(
        "--format", choices=["mp3", "flac", "ogg", "m4a", "opus", "wav"],
        help="Audio format for downloads"
    )
    parser.add_argument(
        "--bitrate", choices=["128k", "192k", "256k", "320k", "best"],
        help="Audio bitrate for downloads"
    )
    
    args = parser.parse_args()
    
    # Check for pywin32 availability on Windows and show a warning if missing
    if (sys.platform == "win32" or sys.platform == "win64") and not WINDOWS_IMAPI_AVAILABLE:
        console.print("[yellow]Warning: pywin32 is not installed. Some CD/DVD burning features will be limited.[/yellow]")
        console.print("[yellow]Install pywin32 for full functionality: pip install pywin32[/yellow]")
    
    app = SpotifyBurner()
    
    # Override config with command line arguments
    if args.output:
        app.download_dir = args.output
    if args.drive:
        app.dvd_drive = args.drive
    if args.threads and 1 <= args.threads <= 10:
        app.max_threads = args.threads
        app_state["max_concurrent_downloads"] = args.threads
    if args.format:
        app.audio_format = args.format
    if args.bitrate:
        app.bitrate = args.bitrate
    
    # Run the app
    try:
        return app.run(args.query)
    finally:
        # Clean up resources when application exits
        if hasattr(app, 'executor') and app.executor:
            app.executor.shutdown(wait=False)


if __name__ == "__main__":
    sys.exit(main())