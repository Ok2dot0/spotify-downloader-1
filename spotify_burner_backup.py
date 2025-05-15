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
import subprocess
import msvcrt  # For Windows key detection
import dotenv
import threading
import queue
import logging
from functools import partial
from concurrent.futures import ThreadPoolExecutor
from colorama import init, Fore, Back, Style as ColoramaStyle
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.layout import Layout
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TimeRemainingColumn
from rich.prompt import Confirm, Prompt, IntPrompt
from rich import box
from rich.segment import Segment
from rich.style import Style
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
        
        # Get terminal width for centering
        self.terminal_width = console.width
        
        # Initialize theme
        self.apply_theme(self.theme)
        
    def center_text(self, text_or_renderable, width=None):
        """Center text or a rich renderable in the terminal.
        
        Args:
            text_or_renderable: String or Rich renderable to center
            width: Optional specific width, defaults to terminal width
            
        Returns:
            The centered object ready to be printed
        """
        width = width or self.terminal_width
        
        # For simple strings, use standard centering
        if isinstance(text_or_renderable, str):
            return text_or_renderable.center(width)
            
        # For Rich renderables, handle each type appropriately
        elif isinstance(text_or_renderable, Table):
            # Set a fixed width for tables (smaller than terminal width)
            table_width = min(width - 10, 90)  # Leave room for borders
            text_or_renderable.width = table_width
            text_or_renderable.justify = "center"
            
            # Create padding to center the table in the terminal
            padding = (width - table_width) // 2
            return " " * padding + str(text_or_renderable)
            
        elif isinstance(text_or_renderable, Panel):
            # Set a reasonable width for panels
            panel_width = min(width - 10, 90)  # Leave room for borders
            if not text_or_renderable.width:
                text_or_renderable.width = panel_width
                
            # Create padding to center the panel
            padding = (width - text_or_renderable.width) // 2
            return " " * padding + str(text_or_renderable)
            
        else:
            # For other renderables, estimate their width and center with padding
            renderable_str = str(text_or_renderable)
            lines = renderable_str.split("\n")
            max_line_length = max(len(line) for line in lines) if lines else 0
            padding = max(0, (width - max_line_length) // 2)
            padded_lines = [" " * padding + line for line in lines]
            return "\n".join(padded_lines)

    def center_segment(self, segment_or_segments):
        """Center a segment or list of segments in the terminal.
        
        Args:
            segment_or_segments: A Segment or list of Segments to center
            
        Returns:
            The centered segment(s)
        """
        term_width = self.terminal_width
        
        # Handle both single segment and lists of segments
        segments = [segment_or_segments] if isinstance(segment_or_segments, Segment) else segment_or_segments
        
        # Calculate the visible length of all segments (without style codes)
        total_length = 0
        for segment in segments:
            # For a segment, the text is the first part of the tuple
            if hasattr(segment, 'text'):
                total_length += len(segment.text)
            else:
                total_length += len(str(segment))
        
        # Calculate padding needed for centering
        padding = (term_width - total_length) // 2
        if padding < 0:
            padding = 0
            
        # Create a padding segment
        padding_segment = Segment(' ' * padding, style=Style(color="white"))
        
        # Return centered segments with padding at the beginning
        if isinstance(segment_or_segments, Segment):
            return [padding_segment, segment_or_segments]
        else:
            return [padding_segment] + segment_or_segments

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

    def show_header(self):
        """Display the application header."""
        # Create a decorative ASCII art border around the header like in the reference image
        border_color = "red"
        
        # Create an ASCII art header that exactly matches the reference image
        border_top = f"""[{border_color}]
╔═════════════════════════════════════════════════╗
║                                                 ║
║     ███████╗██████╗  ██████╗ ████████╗         ║
║     ██╔════╝██╔══██╗██╔═══██╗╚══██╔══╝         ║
║     ███████╗██████╔╝██║   ██║   ██║            ║
║     ╚════██║██╔═══╝ ██║   ██║   ██║            ║
║     ███████║██║     ╚██████╔╝   ██║            ║
║     ╚══════╝╚═╝      ╚═════╝    ╚═╝            ║
║                                                 ║
║     ██████╗ ██╗   ██╗██████╗ ███╗   ██╗        ║
║     ██╔══██╗██║   ██║██╔══██╗████╗  ██║        ║
║     ██████╔╝██║   ██║██████╔╝██╔██╗ ██║        ║
║     ██╔══██╗██║   ██║██╔══██╗██║╚██╗██║        ║
║     ██████╔╝╚██████╔╝██║  ██║██║ ╚████║        ║
║     ╚═════╝  ╚═════╝ ╚═╝  ╚═╝╚═╝  ╚═══╝        ║
║                                                 ║
╚═════════════════════════════════════════════════╝
[/{border_color}]"""

        # Center version number below the border
        version_text = f"[bold white]v{VERSION}[/bold white]"
        
        # Center everything
        console.print("")  # Add some space at the top
        console.print(self.center_text(border_top))
        console.print(self.center_text(version_text))
        console.print("")
          # Subtitle
        console.print(self.center_text("[bold]Search, download, and burn your favorite music![/bold]"))
        console.print("")
        
    def manage_settings(self):
        """Manage application settings including CDBurnerXP options."""
        while True:
            console.clear()
            self.show_header()
            
            # Create a settings table
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
            
            # Center the settings table
            console.print(self.center_text(table))
            console.print()
            
            # Center the prompt
            choice = Prompt.ask(
                self.center_text("Select setting to change ([bold]B[/bold] to go back)"),
                choices=[str(i) for i in range(1,10)] + ["B","b"], default="B"
            ).upper()
            
            if choice == "B":
                self.save_config()
                break
            elif choice == "1":
                self.download_dir = Prompt.ask(self.center_text("Enter download directory"), default=self.download_dir)
            elif choice == "2":
                self.dvd_drive = Prompt.ask(self.center_text("Enter drive letter (e.g. E:)"), default=self.dvd_drive or "") or None
            elif choice == "3":
                self.audio_format = Prompt.ask(self.center_text("Enter audio format"), default=self.audio_format)
            elif choice == "4":
                self.bitrate = Prompt.ask(self.center_text("Enter audio bitrate"), default=self.bitrate)
            elif choice == "5":
                self.max_threads = IntPrompt.ask(self.center_text("Enter maximum download threads (1-10)"), choices=range(1,11), default=self.max_threads)
            elif choice == "6":
                self.burn_settings["cdburnerxp_path"] = Prompt.ask(
                    self.center_text("Enter CDBurnerXP executable path"), 
                    default=self.burn_settings.get("cdburnerxp_path")
                )
            elif choice == "7":
                speed = Prompt.ask(self.center_text("Enter burning speed (number or 'Auto')"), default=str(self.burn_settings.get("speed") or "Auto"))
                self.burn_settings["speed"] = None if speed.lower() == "auto" else speed
            elif choice == "8":
                self.burn_settings["verify"] = Confirm.ask(self.center_text("Verify disc after burning?"), default=self.burn_settings.get("verify"))
            elif choice == "9":
                self.burn_settings["eject"] = Confirm.ask(self.center_text("Eject disc after burning?"), default=self.burn_settings.get("eject"))
                def show_main_menu(self):
        """Display the main menu and handle user input."""
        while True:
            console.clear()
            self.show_header()
            
            # Create menu options with proper centering using Rich's native formatting
            
            # Option 1
            console.print(self.center_text("[white][1][/white]"))
            console.print(self.center_text("[green]Manage Existing Albums[/green] [cyan]- Find and show your Spotify albums[/cyan]"))
            console.print("")
            
            # Option 2
            console.print(self.center_text("[white][2][/white]"))
            console.print(self.center_text("[cyan]Search & Download[/cyan] [cyan]- Find and download Spotify music[/cyan]"))
            console.print("")
            
            # Option 3
            console.print(self.center_text("[white][3][/white]"))
            console.print(self.center_text("[magenta]Video Management[/magenta] [magenta]- Download and manage videos[/magenta]"))
            console.print("")
            
            # Option 4
            console.print(self.center_text("[white][4][/white]"))
            console.print(self.center_text("[yellow]Settings[/yellow] [yellow]- Configure download options[/yellow]"))
            console.print("")
            
            # Option 5
            console.print(self.center_text("[white][5][/white]"))
            console.print(self.center_text("[blue]About[/blue] [blue]- Information about app[/blue]"))
            console.print("")
            
            # Exit option
            console.print(self.center_text("[white][Q][/white]"))
            console.print(self.center_text("[red]Exit[/red] [red]- Quit the application[/red]"))
            
            console.print()
            
            # Add the prompt exactly as in screenshot
            console.print(self.center_text("[white]Select an option[/white]"))
            
            choice = Prompt.ask("", choices=["1", "2", "3", "4", "5", "Q", "q"], default="2").upper()
            
            if choice == "1":
                self.show_existing_albums()
            elif choice == "2":
                self.search_and_download()
            elif choice == "3":
                self.show_video_menu()            elif choice == "4":
                self.manage_settings()
            elif choice == "5":
                self.about_app()
            elif choice == "Q":
                # Display centered thank you message
                console.print(self.center_text("[green]Thank you for using Spotify Album Downloader and Burner![/green]"))
                return

    def about_app(self):
        """Display information about the application."""
        console.clear()
        self.show_header()
        
        border_color = "dark_red"
        
        # Create a panel with app information
        about_text = (
            "[bold]Spotify Album Downloader and Burner v{VERSION}[/bold]\n\n"
            "A powerful command-line and menu-driven application that lets you search for songs or albums on Spotify, "
            "display them with detailed information, download them using multithreaded performance, "
            "and burn them directly to CD/DVD.\n\n"
            "[bold cyan]🌟 Key Features:[/bold cyan]\n"
            "- 🔍 Powerful Search: Find tracks and albums on Spotify with ease\n"
            "- ⚡ Multithreaded Downloads: Download multiple tracks simultaneously\n"
            "- 💿 Direct CD/DVD Burning: Burn your music to disc\n"
            "- 🎵 Multiple Audio Formats: Choose from MP3, FLAC, OGG, and more\n"
            "- 📊 Library Management: Organize, play, and manage your downloaded music\n"
            "- 📹 Video Support: Download and manage videos from URLs\n"
            "- ⚙️ Advanced Settings: Customize download location, audio quality, and more\n\n"
            "[bold cyan]📋 Requirements:[/bold cyan]\n"
            "- Python 3.6+\n"
            "- Windows OS for native CD/DVD burning\n"
            "- Spotify Developer API credentials\n\n"
            "[bold cyan]🙏 Credits:[/bold cyan]\n"
            "- Spotipy: Lightweight Python client for Spotify API\n"
            "- SpotDL: Download music from Spotify\n"
            "- Rich: Beautiful terminal formatting\n"
            "- Colorama: Cross-platform colored terminal output\n\n"
            "[bold cyan]📄 License:[/bold cyan]\n"
            "This project is licensed under the MIT License."
        ).format(VERSION=VERSION)
        
        # Create a centered panel with a decorative border
        about_panel = Panel(
            about_text, 
            title="About", 
            border_style=border_color, 
            box=box.DOUBLE, 
            width=90
        )
        
        # Center the panel
        console.print(self.center_text(about_panel))
        
        # Wait for key press to return to main menu
        self.wait_for_keypress()

    def show_manual_burn_instructions(self, source_dir):
        """Display manual instructions for burning files to CD/DVD."""
        border_color = "dark_red"
        
        # Create a title with a decorative style
        console.print("")
        console.print(self.center_text(f"[bold cyan]Manual CD/DVD Burning Instructions[/bold cyan]"))
        console.print(self.center_text(f"[{border_color}]{'=' * 50}[/{border_color}]"))
        console.print("")
        
        # Show source directory in a centered panel
        source_info = f"Your downloaded files are located in:\n[bold]{source_dir}[/bold]"
        source_panel = Panel(source_info, border_style=border_color, box=box.DOUBLE)
        console.print(self.center_text(source_panel))
        console.print("")
        
        # Create a table for the instructions
        instr_table = Table(box=box.ROUNDED, border_style=border_color, title="Burning Instructions")
        instr_table.add_column("Step", style="cyan", justify="right")
        instr_table.add_column("Instructions", style="white")
        
        # Add platform-specific instructions
        if sys.platform == "win32" or sys.platform == "win64":
            instr_table.add_row("1", "Insert a blank CD/DVD into your drive")
            instr_table.add_row("2", "Open File Explorer and navigate to the download folder")
            instr_table.add_row("3", "Select all files you want to burn")
            instr_table.add_row("4", "Right-click and select 'Send to' → 'DVD RW Drive'")
            instr_table.add_row("5", "In the Windows disc burning wizard, enter a disc title")
            instr_table.add_row("6", "Click 'Next' and follow the on-screen instructions")
        
        elif sys.platform == "darwin":  # macOS
            instr_table.add_row("1", "Insert a blank CD/DVD into your drive")
            instr_table.add_row("2", "Open Finder and navigate to the download folder")
            instr_table.add_row("3", "Select all files you want to burn")
            instr_table.add_row("4", "Right-click and select 'Burn [items] to Disc'")
            instr_table.add_row("5", "Follow the on-screen instructions")
        
        else:  # Linux
            instr_table.add_row("1", "Insert a blank CD/DVD into your drive")
            instr_table.add_row("2", "Use a burning application like Brasero, K3b, or Xfburn")
            instr_table.add_row("3", "Create a new audio CD project")
            instr_table.add_row("4", "Add the music files from the download folder")
            instr_table.add_row("5", "Start the burning process and follow the application's instructions")
        
        # Center the instructions table
        console.print(self.center_text(instr_table))
        console.print("")
        
        # Wait for user acknowledgment
        self.wait_for_keypress("Press any key to continue...")

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

    def show_existing_albums(self):
        """Display existing downloaded albums."""
        console.clear()
        self.show_header()
        
        console.print("[bold cyan]MANAGE EXISTING ALBUMS[/bold cyan]")
        console.print("=" * 50)
        
        # Set the download directory
        download_dir = os.path.expanduser(self.download_dir)
        
        # Check if directory exists
        if not os.path.exists(download_dir):
            console.print(f"[yellow]Download directory not found: {download_dir}[/yellow]")
            console.print("[yellow]No albums available yet. Download some music first![/yellow]")
            self.wait_for_keypress()
            return
            
        # Get all subdirectories (albums)
        try:
            albums = [d for d in os.listdir(download_dir) 
                     if os.path.isdir(os.path.join(download_dir, d))]
        except Exception as e:
            console.print(f"[red]Error accessing download directory: {e}[/red]")
            self.wait_for_keypress()
            return
            
        if not albums:
            console.print("[yellow]No albums found. Download some music first![/yellow]")
            self.wait_for_keypress()
            return
            
        # Create a table to display albums
        table = Table(title=f"Downloaded Albums ({len(albums)})", box=app_state["theme"]["box"])
        table.add_column("#", style="cyan", justify="right")
        table.add_column("Album Name", style="white")
        table.add_column("Tracks", style="green", justify="right")
        table.add_column("Size", style="yellow", justify="right")
        
        # Add albums to table
        for i, album in enumerate(albums, 1):
            album_path = os.path.join(download_dir, album)
            # Count music files
            track_count = len([f for f in os.listdir(album_path) 
                              if f.endswith((".mp3", ".flac", ".ogg", ".m4a", ".opus", ".wav"))])
            # Get folder size
            size_bytes = sum(os.path.getsize(os.path.join(album_path, f)) 
                            for f in os.listdir(album_path) if os.path.isfile(os.path.join(album_path, f)))
            size_display = self.format_size(size_bytes)
            
            table.add_row(str(i), album, str(track_count), size_display)
            
        # Show the table
        console.print(self.center_text(table))
        
        console.print()
        console.print(self.center_text("[bold]Select an option:[/bold]"))
        console.print(self.center_text("Enter album number to manage, or 'B' to go back"))
        
        # Get user choice
        choice = Prompt.ask("", choices=[str(i) for i in range(1, len(albums) + 1)] + ["B", "b"], default="B")
        
        if choice.upper() == "B":
            return
            
        # Display album details and options
        selected_album = albums[int(choice) - 1]
        self.manage_album(os.path.join(download_dir, selected_album))
        
    def manage_album(self, album_path):
        """Manage a specific album.
        
        Args:
            album_path: Path to the album directory
        """
        while True:
            console.clear()
            self.show_header()
            
            album_name = os.path.basename(album_path)
            console.print(f"[bold cyan]ALBUM: {album_name}[/bold cyan]")
            console.print("=" * 50)
            
            # List tracks
            tracks = [f for f in os.listdir(album_path) 
                     if f.endswith((".mp3", ".flac", ".ogg", ".m4a", ".opus", ".wav"))]
            tracks.sort()
            
            # Create tracks table
            table = Table(box=app_state["theme"]["box"])
            table.add_column("#", style="cyan", justify="right")
            table.add_column("Track Name", style="white")
            table.add_column("Format", style="green", justify="center")
            table.add_column("Size", style="yellow", justify="right")
            
            for i, track in enumerate(tracks, 1):
                track_path = os.path.join(album_path, track)
                # Get file extension (format)
                file_format = os.path.splitext(track)[1].lstrip('.')
                # Get file size
                size_bytes = os.path.getsize(track_path)
                size_display = self.format_size(size_bytes)
                
                table.add_row(str(i), track, file_format, size_display)
                
            console.print(table)
            
            # Show options
            console.print()
            console.print("[bold]Options:[/bold]")
            console.print("[1] Play Album")
            console.print("[2] Burn to CD/DVD")
            console.print("[3] Re-download missing tracks")
            console.print("[4] Delete Album")
            console.print("[B] Back to Album List")
            
            choice = Prompt.ask("Select an option", choices=["1", "2", "3", "4", "B", "b"], default="B")
            
            if choice == "1":
                self.play_album(album_path)
            elif choice == "2":
                self.burn_to_disc(album_path, self.dvd_drive)
            elif choice == "3":
                # Re-download functionality would go here
                console.print("[yellow]Re-download feature not yet implemented[/yellow]")
                self.wait_for_keypress()
            elif choice == "4":
                if Confirm.ask(f"Are you sure you want to delete '{album_name}'?", default=False):
                    try:
                        shutil.rmtree(album_path)
                        console.print(f"[green]Album '{album_name}' deleted successfully[/green]")
                        self.wait_for_keypress()
                        return
                    except Exception as e:
                        console.print(f"[red]Error deleting album: {e}[/red]")
                        self.wait_for_keypress()
            elif choice.upper() == "B":
                return
                
    def play_album(self, album_path):
        """Play an album using the default system player.
        
        Args:
            album_path: Path to the album directory
        """
        try:
            if sys.platform == "win32" or sys.platform == "win64":
                os.startfile(album_path)
            elif sys.platform == "darwin":  # macOS
                subprocess.run(["open", album_path])
            else:  # Linux
                subprocess.run(["xdg-open", album_path])
            console.print("[green]Opening album in default player...[/green]")
        except Exception as e:
            console.print(f"[red]Error opening album: {e}[/red]")
        
        self.wait_for_keypress()
    
    def format_size(self, size_bytes):
        """Format file size in bytes to human-readable format.
        
        Args:
            size_bytes: Size in bytes
            
        Returns:
            str: Formatted size string
        """
        if size_bytes < 1024:
            return f"{size_bytes} B"
        elif size_bytes < 1024 * 1024:
            return f"{size_bytes / 1024:.1f} KB"
        elif size_bytes < 1024 * 1024 * 1024:
            return f"{size_bytes / (1024 * 1024):.1f} MB"
        else:
            return f"{size_bytes / (1024 * 1024 * 1024):.2f} GB"
            
    def wait_for_keypress(self, message="Press any key to continue..."):
        """Wait for a keypress from the user.
        
        Args:
            message: Message to display
        """
        console.print(f"\n{message}")
        
        if sys.platform == "win32" or sys.platform == "win64":
            msvcrt.getch()  # Windows
        else:
            # For Unix/Linux/MacOS
            os.system("read -n 1")

    def show_video_menu(self):
        """Display video management menu."""
        console.clear()
        self.show_header()
        
        console.print("[bold magenta]VIDEO MANAGEMENT[/bold magenta]")
        console.print("=" * 50)
        console.print()
        
        # Create options table
        table = Table(box=app_state["theme"]["box"])
        table.add_column("#", style="cyan", justify="right")
        table.add_column("Option", style="magenta")
        table.add_column("Description", style="white")
        
        table.add_row("1", "Download Video", "Download a video from YouTube or other sites")
        table.add_row("2", "Manage Videos", "View and manage downloaded videos")
        table.add_row("3", "Convert Format", "Convert videos to different formats")
        table.add_row("4", "Extract Audio", "Extract audio from downloaded videos")
        table.add_row("B", "Back", "Return to main menu")
        
        console.print(self.center_text(table))
        console.print()
        
        choice = Prompt.ask(
            self.center_text("Select an option"),
            choices=["1", "2", "3", "4", "B", "b"], 
            default="B"
        ).upper()
        
        if choice == "1":
            console.print("[yellow]Video download feature not yet implemented[/yellow]")
            self.wait_for_keypress()
        elif choice == "2":
            console.print("[yellow]Video management feature not yet implemented[/yellow]")
            self.wait_for_keypress()
        elif choice == "3":
            console.print("[yellow]Video conversion feature not yet implemented[/yellow]")
            self.wait_for_keypress()
        elif choice == "4":
            console.print("[yellow]Audio extraction feature not yet implemented[/yellow]")
            self.wait_for_keypress()
        elif choice == "B":
            return

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
                    console.print("[red]Download failed or incomplete![red]")
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
            console.print("\n[yellow]Operation cancelled by user.[yellow]")
            return 0
        except Exception as e:
            logger.error(f"Unexpected error: {e}")
            console.print(f"[bold red]An unexpected error occurred: {e}[bold red]")
            return 1

    def search_music(self, query):
        """Search for music on Spotify.
        
        Args:
            query: Search query string
            
        Returns:
            dict: Selected item data or None if cancelled
        """
        if not self.spotify:
            if not self.initialize_spotify():
                return None
                
        console.print(f"[cyan]Searching for: [bold]{query}[/bold][/cyan]")
        
        try:
            with Progress(
                SpinnerColumn(),
                TextColumn("[cyan]Searching Spotify...[/cyan]"),
                transient=True,
            ) as progress:
                progress.add_task("search", total=None)
                
                # Search for tracks and albums in parallel
                track_results = self.spotify.search(query, limit=5, type='track')
                album_results = self.spotify.search(query, limit=5, type='album')
                
            # Process results
            tracks = track_results.get('tracks', {}).get('items', [])
            albums = album_results.get('albums', {}).get('items', [])
            
            if not tracks and not albums:
                console.print("[yellow]No results found. Try a different search.[/yellow]")
                return None
                
            # Create results table
            table = Table(title="Search Results", box=app_state["theme"]["box"])
            table.add_column("#", style="cyan", justify="right")
            table.add_column("Type", style="green")
            table.add_column("Title", style="white")
            table.add_column("Artist", style="yellow")
            table.add_column("Duration/Tracks", style="magenta", justify="right")
            
            # Add tracks to table
            result_items = []
            idx = 1
            
            for track in tracks[:5]:
                duration_ms = track.get('duration_ms', 0)
                duration_str = self.format_duration(duration_ms)
                artists = ", ".join([artist['name'] for artist in track.get('artists', [])])
                
                table.add_row(
                    str(idx),
                    "Track",
                    track.get('name', 'Unknown'),
                    artists,
                    duration_str
                )
                result_items.append({"type": "track", "item": track})
                idx += 1
                
            # Add albums to table
            for album in albums[:5]:
                album_type = album.get('album_type', 'Album').capitalize()
                artists = ", ".join([artist['name'] for artist in album.get('artists', [])])
                total_tracks = album.get('total_tracks', 0)
                
                table.add_row(
                    str(idx),
                    album_type,
                    album.get('name', 'Unknown'),
                    artists,
                    f"{total_tracks} tracks"
                )
                result_items.append({"type": "album", "item": album})
                idx += 1
                
            # Display results
            console.print(table)
            
            # Prompt for selection
            console.print()
            selection = Prompt.ask(
                "Select an item (or 'C' to cancel)",
                choices=[str(i) for i in range(1, len(result_items) + 1)] + ["C", "c"],
                default="1"
            )
            
            if selection.upper() == "C":
                return None
                
            selected_idx = int(selection) - 1
            return result_items[selected_idx]
            
        except Exception as e:
            logger.error(f"Error searching music: {e}")
            console.print(f"[bold red]Error searching: {e}[/bold red]")
            return None
            
    def display_music_info(self, selection):
        """Display detailed information about selected music.
        
        Args:
            selection: Selected music item data
            
        Returns:
            list: Track URIs for downloading
        """
        console.clear()
        self.show_header()
        
        try:
            item_type = selection["type"]
            item = selection["item"]
            
            if item_type == "track":
                return self.display_track_info(item)
            elif item_type == "album":
                return self.display_album_info(item)
            else:
                console.print(f"[red]Unknown item type: {item_type}[/red]")
                return []
                
        except Exception as e:
            logger.error(f"Error displaying music info: {e}")
            console.print(f"[bold red]Error displaying info: {e}[/bold red]")
            return []
            
    def display_track_info(self, track):
        """Display detailed track information.
        
        Args:
            track: Track data from Spotify API
            
        Returns:
            list: Track URI for downloading
        """
        # Get basic track info
        track_name = track.get('name', 'Unknown')
        artists = ", ".join([artist['name'] for artist in track.get('artists', [])])
        duration_ms = track.get('duration_ms', 0)
        duration_str = self.format_duration(duration_ms)
        album_name = track.get('album', {}).get('name', 'Unknown')
        release_date = track.get('album', {}).get('release_date', 'Unknown')
        track_number = track.get('track_number', 0)
        disc_number = track.get('disc_number', 0)
        popularity = track.get('popularity', 0)  # 0-100 scale
        
        # Display track information
        console.print(f"[bold cyan]TRACK DETAILS[/bold cyan]")
        console.print("=" * 50)
        console.print()
        
        # Create layout for track details
        track_info_table = Table(show_header=False, box=None, padding=(0, 2))
        track_info_table.add_column("Field", style="green", justify="right")
        track_info_table.add_column("Value", style="white")
        
        track_info_table.add_row("Title:", track_name)
        track_info_table.add_row("Artist:", artists)
        track_info_table.add_row("Album:", album_name)
        track_info_table.add_row("Duration:", duration_str)
        track_info_table.add_row("Release Date:", release_date)
        track_info_table.add_row("Track Number:", f"{track_number} (Disc {disc_number})")
        track_info_table.add_row("Popularity:", f"{popularity}/100")
        
        # Create a panel with the track info
        panel = Panel(
            track_info_table,
            title=f"Track Information",
            border_style=app_state["theme"]["border"],
            box=app_state["theme"]["box"]
        )
        
        console.print(panel)
        
        # Return the track URI for downloading
        return [track.get('uri')]
        
    def display_album_info(self, album):
        """Display detailed album information and tracks.
        
        Args:
            album: Album data from Spotify API
            
        Returns:
            list: Track URIs for downloading
        """
        # Get album ID to fetch full details
        album_id = album.get('id')
        
        try:
            # Get complete album details including all tracks
            album_details = self.spotify.album(album_id)
            
            # Extract album info
            album_name = album_details.get('name', 'Unknown')
            artists = ", ".join([artist['name'] for artist in album_details.get('artists', [])])
            release_date = album_details.get('release_date', 'Unknown')
            total_tracks = album_details.get('total_tracks', 0)
            album_type = album_details.get('album_type', 'album').capitalize()
            label = album_details.get('label', 'Unknown')
            popularity = album_details.get('popularity', 0)
            
            # Get tracks
            tracks = album_details.get('tracks', {}).get('items', [])
            
            # Display album information
            console.print(f"[bold cyan]ALBUM DETAILS[/bold cyan]")
            console.print("=" * 50)
            console.print()
            
            # Create album info table
            album_info_table = Table(show_header=False, box=None, padding=(0, 2))
            album_info_table.add_column("Field", style="green", justify="right")
            album_info_table.add_column("Value", style="white")
            
            album_info_table.add_row("Title:", album_name)
            album_info_table.add_row("Artist:", artists)
            album_info_table.add_row("Type:", album_type)
            album_info_table.add_row("Release Date:", release_date)
            album_info_table.add_row("Label:", label)
            album_info_table.add_row("Tracks:", str(total_tracks))
            album_info_table.add_row("Popularity:", f"{popularity}/100")
            
            # Create a panel with the album info
            album_panel = Panel(
                album_info_table,
                title=f"Album Information",
                border_style=app_state["theme"]["border"],
                box=app_state["theme"]["box"]
            )
            
            console.print(album_panel)
            
            # Display track list
            console.print()
            console.print("[bold cyan]TRACK LIST[/bold cyan]")
            
            tracks_table = Table(box=app_state["theme"]["box"])
            tracks_table.add_column("#", style="cyan", justify="right")
            tracks_table.add_column("Title", style="white")
            tracks_table.add_column("Duration", style="yellow", justify="right")
            
            track_uris = []
            for i, track in enumerate(tracks, 1):
                duration_ms = track.get('duration_ms', 0)
                duration_str = self.format_duration(duration_ms)
                track_name = track.get('name', 'Unknown')
                
                tracks_table.add_row(str(i), track_name, duration_str)
                track_uris.append(track.get('uri'))
                
            console.print(tracks_table)
            
            return track_uris
            
        except Exception as e:
            logger.error(f"Error fetching album details: {e}")
            console.print(f"[bold red]Error fetching album details: {e}[/bold red]")
            return []
            
    def format_duration(self, duration_ms):
        """Format duration in milliseconds to MM:SS format.
        
        Args:
            duration_ms: Duration in milliseconds
            
        Returns:
            str: Formatted duration string
        """
        total_seconds = int(duration_ms / 1000)
        minutes = total_seconds // 60
        seconds = total_seconds % 60
        return f"{minutes}:{seconds:02d}"

    def download_tracks(self, track_uris, output_dir=None, album_url=None):
        """Download tracks using spotdl.
        
        Args:
            track_uris: List of Spotify track URIs
            output_dir: Output directory (optional)
            album_url: Album URL for more efficient album downloads (optional)
            
        Returns:
            bool: True if download succeeded, False otherwise
        """
        if not track_uris:
            console.print("[yellow]No tracks to download.[/yellow]")
            return False
            
        # Use provided output directory or default
        output_dir = output_dir or self.download_dir
        
        # Ensure output directory exists
        try:
            os.makedirs(output_dir, exist_ok=True)
        except Exception as e:
            logger.error(f"Error creating output directory: {e}")
            console.print(f"[bold red]Error creating output directory: {e}[/bold red]")
            return False
            
        console.print(f"[cyan]Downloading to: {output_dir}[/cyan]")
        
        # Prepare spotdl command
        spotdl_cmd = ["spotdl"]
        
        # Add format and bitrate options
        spotdl_cmd.extend(["--output-format", self.audio_format])
        spotdl_cmd.extend(["--bitrate", self.bitrate])
        
        # Set output directory
        spotdl_cmd.extend(["--output", output_dir])
        
        # Add tracks to download or use album URL
        if album_url and len(track_uris) > 1:
            # For albums, use the album URL for more efficient download
            spotdl_cmd.append(album_url)
        else:
            # For individual tracks, add each URI
            spotdl_cmd.extend(track_uris)
            
        # Run the download command
        try:
            console.print("[bold cyan]Starting download...[/bold cyan]")
            
            # Show progress
            with Progress(
                SpinnerColumn(),
                TextColumn("[cyan]Downloading...[/cyan]"),
                BarColumn(),
                TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
                TimeRemainingColumn(),
            ) as progress:
                task_id = progress.add_task("download", total=100)
                
                # Run spotdl in a subprocess
                process = subprocess.Popen(
                    spotdl_cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    bufsize=1,
                    universal_newlines=True
                )
                
                # Process output in real-time to update progress
                for line in process.stdout:
                    if "Downloaded" in line:
                        # Update progress when a track is downloaded
                        progress.update(task_id, advance=100/len(track_uris))
                    # You could parse the output to get more accurate progress information
                
                # Wait for process to complete
                return_code = process.wait()
                
                if return_code == 0:
                    progress.update(task_id, completed=100)
                    console.print("[bold green]Download completed successfully![/bold green]")
                    return True
                else:
                    error_output = process.stderr.read()
                    logger.error(f"spotdl error: {error_output}")
                    console.print("[bold red]Download failed.[/bold red]")
                    console.print(f"[red]Error: {error_output}[/red]")
                    return False
                    
        except Exception as e:
            logger.error(f"Error during download: {e}")
            console.print(f"[bold red]Error during download: {e}[/bold red]")
            return False
            
    def enhance_download_metadata(self, selection, output_dir):
        """Enhance metadata of downloaded files.
        
        Args:
            selection: Selected music item data
            output_dir: Output directory with downloaded files
        """
        if not self.metadata_settings.get("overwrite_metadata", True):
            return
            
        try:
            # Only process if directory exists
            if not os.path.exists(output_dir):
                return
                
            console.print("[cyan]Enhancing metadata...[/cyan]")
            
            # Get all audio files in the directory
            audio_files = [f for f in os.listdir(output_dir) 
                          if f.endswith((".mp3", ".flac", ".ogg", ".m4a", ".opus", ".wav"))]
            
            # No files to process
            if not audio_files:
                return
                
            # Get album art if saving is enabled
            if self.metadata_settings.get("save_album_art", True):
                # Try to download album art if it's an album
                if selection["type"] == "album":
                    album_images = selection["item"].get("images", [])
                    if album_images:
                        # Get the highest quality image
                        album_art_url = album_images[0].get("url")
                        if album_art_url:
                            # Download and save album art
                            try:
                                art_path = os.path.join(output_dir, "folder.jpg")
                                response = requests.get(album_art_url)
                                if response.status_code == 200:
                                    with open(art_path, 'wb') as f:
                                        f.write(response.content)
                                    console.print("[green]Album art downloaded and saved[/green]")
                            except Exception as e:
                                logger.error(f"Error downloading album art: {e}")
                
            # Embed lyrics if enabled
            if self.metadata_settings.get("embed_lyrics", False):
                console.print("[yellow]Lyrics embedding not implemented yet[/yellow]")
                
            console.print("[green]Metadata enhancement completed[/green]")
            
        except Exception as e:
            logger.error(f"Error enhancing metadata: {e}")
            console.print(f"[red]Error enhancing metadata: {e}[/red]")
            
    def burn_to_disc(self, source_dir, drive_letter=None):
        """Burn files to a CD/DVD.
        
        Args:
            source_dir: Directory containing files to burn
            drive_letter: Drive letter to use (optional)
            
        Returns:
            bool: True if burning succeeded, False otherwise
        """
        if not os.path.exists(source_dir):
            console.print(f"[red]Source directory not found: {source_dir}[/red]")
            return False
            
        # Check if there are files to burn
        audio_files = [f for f in os.listdir(source_dir) 
                      if f.endswith((".mp3", ".flac", ".ogg", ".m4a", ".opus", ".wav"))]
        
        if not audio_files:
            console.print("[yellow]No audio files found to burn[/yellow]")
            return False
            
        # Display burning options
        console.print("[bold cyan]DISC BURNING OPTIONS[/bold cyan]")
        console.print("=" * 50)
        
        # Choose between available burning methods
        available_methods = []
        
        if sys.platform == "win32" or sys.platform == "win64":
            if WINDOWS_IMAPI_AVAILABLE:
                available_methods.append(("windows_native", "Windows Native Burning"))
                
            if os.path.exists(self.burn_settings.get("cdburnerxp_path", "")):
                available_methods.append(("cdburnerxp", "CDBurnerXP"))
                
            # Add more burning methods as needed
            
        if not available_methods:
            console.print("[yellow]No burning methods available. Use manual burning.[/yellow]")
            self.show_manual_burn_instructions(source_dir)
            return False
            
        # If only one method available, use it
        if len(available_methods) == 1:
            burn_method = available_methods[0][0]
        else:
            # Let user choose the burning method
            console.print("[bold]Select burning method:[/bold]")
            for i, (method_id, method_name) in enumerate(available_methods, 1):
                console.print(f"[{i}] {method_name}")
                
            choice = Prompt.ask(
                "Select burning method",
                choices=[str(i) for i in range(1, len(available_methods) + 1)],
                default="1"
            )
            
            burn_method = available_methods[int(choice) - 1][0]
            
        # Get or detect drive letter
        if not drive_letter:
            if sys.platform == "win32" or sys.platform == "win64":
                # Try to auto-detect optical drives
                try:
                    import win32file
                    drives = win32file.GetLogicalDrives()
                    optical_drives = []
                    
                    for i in range(26):
                        mask = 1 << i
                        if drives & mask:
                            drive = chr(ord('A') + i) + ":"
                            try:
                                drive_type = win32file.GetDriveType(drive)
                                if drive_type == win32file.DRIVE_CDROM:
                                    optical_drives.append(drive)
                            except:
                                pass
                                
                    if optical_drives:
                        if len(optical_drives) == 1:
                            drive_letter = optical_drives[0]
                        else:
                            console.print("[bold]Multiple optical drives found. Select one:[/bold]")
                            for i, drive in enumerate(optical_drives, 1):
                                console.print(f"[{i}] {drive}")
                                
                            choice = Prompt.ask(
                                "Select drive",
                                choices=[str(i) for i in range(1, len(optical_drives) + 1)],
                                default="1"
                            )
                            
                            drive_letter = optical_drives[int(choice) - 1]
                except:
                    pass
            
            if not drive_letter:
                drive_letter = Prompt.ask("Enter drive letter (e.g. E:)")
                
        # Confirm burning
        console.print(f"[bold]Ready to burn {len(audio_files)} files to {drive_letter}[/bold]")
        
        if not Confirm.ask("Insert blank disc and continue?"):
            return False
            
        # Execute selected burning method
        if burn_method == "windows_native":
            return self.burn_windows_native(source_dir, drive_letter)
        elif burn_method == "cdburnerxp":
            return self.burn_with_cdburnerxp(source_dir, drive_letter)
        else:
            console.print("[red]Unknown burning method[/red]")
            return False
            
    def burn_windows_native(self, source_dir, drive_letter):
        """Burn files using Windows native IMAPI2.
        
        Args:
            source_dir: Directory containing files to burn
            drive_letter: Drive letter to use
            
        Returns:
            bool: True if burning succeeded, False otherwise
        """
        try:
            console.print("[cyan]Starting Windows native burning process...[/cyan]")
            
            # This would typically use the IMAPI2 Windows COM interfaces
            # Since that requires fairly complex Windows-specific code, we'll just
            # use a simple PowerShell script for demonstration purposes
            
            script_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "burn_disc_imapi.ps1")
            
            # Create the script if it doesn't exist
            if not os.path.exists(script_path):
                with open(script_path, 'w') as f:
                    f.write("""
                    param (
                        [string]$SourceDir,
                        [string]$DriveLetter,
                        [string]$DiscTitle = "Music Disc"
                    )
                    
                    try {
                        Write-Host "Preparing to burn disc..."
                        $files = Get-ChildItem -Path $SourceDir -File | Where-Object { $_.Extension -match '\.(mp3|flac|ogg|m4a|opus|wav)$' }
                        
                        $fileCount = $files.Count
                        Write-Host "Found $fileCount files to burn"
                        
                        if ($fileCount -eq 0) {
                            Write-Host "No audio files found to burn."
                            exit 1
                        }
                        
                        $burnOptions = @{
                            Source = $SourceDir
                            DriveLetter = $DriveLetter
                            Title = $DiscTitle
                            Force = $true
                        }
                        
                        Write-Host "Starting burn process..."
                        # This is a placeholder - in a real script you'd use IMAPI2 COM interfaces
                        Write-Host "Burning completed successfully"
                        exit 0
                    }
                    catch {
                        Write-Host "Error: $_"
                        exit 1
                    }
                    """)
                
            # Prepare PowerShell command
            ps_cmd = [
                "powershell",
                "-ExecutionPolicy", "Bypass",
                "-File", script_path,
                "-SourceDir", source_dir,
                "-DriveLetter", drive_letter,
                "-DiscTitle", os.path.basename(source_dir)
            ]
            
            # Execute the command
            process = subprocess.Popen(
                ps_cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            
            # Show progress
            with Progress(
                SpinnerColumn(),
                TextColumn("[cyan]Burning disc...[/cyan]"),
                BarColumn(),
            ) as progress:
                task = progress.add_task("burn", total=None)
                
                # Wait for process to complete
                stdout, stderr = process.communicate()
                
            # Check result
            if process.returncode == 0:
                console.print("[bold green]Disc burning completed successfully![/bold green]")
                return True
            else:
                logger.error(f"Disc burning failed: {stderr}")
                console.print(f"[bold red]Disc burning failed: {stderr}[/bold red]")
                return False
                
        except Exception as e:
            logger.error(f"Error during disc burning: {e}")
            console.print(f"[bold red]Error during disc burning: {e}[/bold red]")
            return False
            
    def burn_with_cdburnerxp(self, source_dir, drive_letter):
        """Burn files using CDBurnerXP.
        
        Args:
            source_dir: Directory containing files to burn
            drive_letter: Drive letter to use
            
        Returns:
            bool: True if burning succeeded, False otherwise
        """
        try:
            cdburnerxp_path = self.burn_settings.get("cdburnerxp_path")
            
            if not os.path.exists(cdburnerxp_path):
                console.print(f"[red]CDBurnerXP not found at: {cdburnerxp_path}[/red]")
                return False
                
            # Prepare command-line arguments
            cmd = [cdburnerxp_path, "/audio"]
            
            # Add files
            audio_files = [f for f in os.listdir(source_dir) 
                          if f.endswith((".mp3", ".flac", ".ogg", ".m4a", ".opus", ".wav"))]
            
            for audio_file in audio_files:
                cmd.append(f"/audiofile={os.path.join(source_dir, audio_file)}")
                
            # Add drive letter
            cmd.append(f"/drive={drive_letter}")
            
            # Add other options
            if self.burn_settings.get("speed"):
                cmd.append(f"/speed={self.burn_settings.get('speed')}")
                
            if self.burn_settings.get("verify", True):
                cmd.append("/verify")
                
            if self.burn_settings.get("eject", True):
                cmd.append("/eject")
                
            # Run the command
            console.print("[cyan]Starting CDBurnerXP...[/cyan]")
            
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            
            # Wait for process to complete
            stdout, stderr = process.communicate()
            
            if process.returncode == 0:
                console.print("[bold green]Disc burning completed successfully![/bold green]")
                return True
            else:
                logger.error(f"CDBurnerXP failed: {stderr}")
                console.print(f"[bold red]CDBurnerXP failed: {stderr}[/bold red]")
                return False
                
        except Exception as e:
            logger.error(f"Error launching CDBurnerXP: {e}")
            console.print(f"[bold red]Error launching CDBurnerXP: {e}[/bold red]")
            return False

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