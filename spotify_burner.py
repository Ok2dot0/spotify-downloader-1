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
        
    def display_track_info(self, track):
        """Display detailed track information.
        
        Args:
            track: Track data from Spotify API
            
        Returns:
            list: Track URI for downloading
        """
        # Create a title with themed styling
        title_text = "[bold cyan]TRACK DETAILS[/bold cyan]"
        console.print(self.center_text(title_text))
        console.print(self.center_text(f"[{app_state['theme']['border']}]{'═' * 60}[/{app_state['theme']['border']}]"))
        console.print("")
        
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
        
        # Create a visual popularity meter
        pop_meter = "█" * (popularity // 10) + "░" * (10 - (popularity // 10))
        popularity_display = f"{pop_meter} ({popularity}%)"
        
        # Get album art if available
        album_image_url = None
        if 'album' in track and 'images' in track['album'] and track['album']['images']:
            album_image_url = track['album']['images'][0]['url']
        
        # Create a grid layout for better visual organization
        layout = Layout()
        layout.split_column(
            Layout(name="header"),
            Layout(name="content"),
            Layout(name="footer")
        )
        
        layout["content"].split_row(
            Layout(name="track_info"),
            Layout(name="album_info")
        )
        
        # Create layout for track details with icons
        track_info_table = Table(show_header=False, box=None, padding=(0, 2))
        track_info_table.add_column("Field", style="green", justify="right")
        track_info_table.add_column("Value", style="white")
        
        track_info_table.add_row("🎵 Title:", f"[bold white]{track_name}[/bold white]")
        track_info_table.add_row("👤 Artist:", f"[yellow]{artists}[/yellow]")
        track_info_table.add_row("⏱️ Duration:", f"[cyan]{duration_str}[/cyan]")
        track_info_table.add_row("🔢 Track Number:", f"{track_number} (Disc {disc_number})")
        track_info_table.add_row("⭐ Popularity:", popularity_display)
        
        # Create a panel for track info
        track_panel = Panel(
            track_info_table,
            title="Track Information",
            title_align="left",
            border_style=app_state["theme"]["border"],
            box=app_state["theme"]["box"],
            width=40,
            expand=False
        )
        
        # Create album info panel
        album_info_table = Table(show_header=False, box=None, padding=(0, 2))
        album_info_table.add_column("Field", style="green", justify="right")
        album_info_table.add_column("Value", style="white")
        
        album_info_table.add_row("💿 Album:", f"[bold white]{album_name}[/bold white]")
        album_info_table.add_row("📅 Release Date:", f"[yellow]{release_date}[/yellow]")
        
        # Create a panel for album info
        album_panel = Panel(
            album_info_table,
            title="Album Information",
            title_align="left",
            border_style=app_state["theme"]["border"],
            box=app_state["theme"]["box"],
            width=40,
            expand=False
        )
        
        # Create a grid to display the two panels side by side
        info_layout = Table.grid(padding=1)
        info_layout.add_column("Left", justify="center")
        info_layout.add_column("Right", justify="center")
        info_layout.add_row(track_panel, album_panel)
        
        console.print(self.center_text(info_layout))
        console.print("")
        
        # Add a confirmation panel
        confirm_panel = Panel(
            "[white]Use this track for download? Type [bold]Y[/bold] to confirm or [bold]N[/bold] to cancel[/white]",
            border_style="blue",
            box=box.SIMPLE,
            expand=False,
            width=80
        )
        console.print(self.center_text(confirm_panel))
        console.print("")
        
        # Return the track URI for downloading
        return [track.get('uri')]

    def display_album_info(self, album):
        """Display detailed album information and tracks.
        
        Args:
            album: Album data from Spotify API
            
        Returns:
            list: Track URIs for downloading
        """
        # Create a title with themed styling
        title_text = "[bold cyan]ALBUM DETAILS[/bold cyan]"
        console.print(self.center_text(title_text))
        console.print(self.center_text(f"[{app_state['theme']['border']}]{'═' * 60}[/{app_state['theme']['border']}]"))
        console.print("")
        
        # Get album ID to fetch full details
        album_id = album.get('id')
        
        try:
            # Show loading spinner while getting detailed info
            with Progress(
                SpinnerColumn(),
                TextColumn("[cyan]Loading album details...[/cyan]"),
                transient=True,
            ) as progress:
                task = progress.add_task("loading", total=None)
                
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
            
            # Create a visual popularity meter
            pop_meter = "█" * (popularity // 10) + "░" * (10 - (popularity // 10))
            popularity_display = f"{pop_meter} ({popularity}%)"
            
            # Get tracks
            tracks = album_details.get('tracks', {}).get('items', [])
            
            # Get album art if available
            album_art_url = None
            if 'images' in album_details and album_details['images']:
                album_art_url = album_details['images'][0]['url']
            
            # Create album info table with visual enhancements
            album_info_table = Table(show_header=False, box=None, padding=(0, 2))
            album_info_table.add_column("Field", style="green", justify="right")
            album_info_table.add_column("Value", style="white")
            
            album_info_table.add_row("💿 Title:", f"[bold white]{album_name}[/bold white]")
            album_info_table.add_row("👤 Artist:", f"[yellow]{artists}[/yellow]")
            album_info_table.add_row("📅 Release:", f"[cyan]{release_date}[/cyan]")
            album_info_table.add_row("🏷️ Label:", label)
            album_info_table.add_row("📊 Type:", f"[magenta]{album_type}[/magenta]")
            album_info_table.add_row("🎵 Tracks:", f"[bold green]{total_tracks}[/bold green]")
            album_info_table.add_row("⭐ Popularity:", popularity_display)
            
            # Create a panel with the album info
            album_panel = Panel(
                album_info_table,
                title="Album Information",
                title_align="left",
                title_style="bold cyan",
                border_style=app_state["theme"]["border"],
                box=app_state["theme"]["box"],
                width=80,
                expand=False
            )
            
            console.print(self.center_text(album_panel))
            console.print("")
            
            # Display track list with enhanced visual styling
            track_title = f"[bold cyan]TRACK LIST ({total_tracks} tracks)[/bold cyan]"
            console.print(self.center_text(track_title))
            console.print("")
            
            # Create a styled table for tracks
            tracks_table = Table(
                box=app_state["theme"]["box"],
                border_style=app_state["theme"]["border"],
                row_styles=["", "dim"],  # Alternating row styles
                highlight=True,
                width=80,
                expand=False
            )
            
            tracks_table.add_column("#", style="cyan", justify="right", width=4)
            tracks_table.add_column("Track Title", style="white")
            tracks_table.add_column("Duration", style="yellow", justify="right", width=10)
            tracks_table.add_column("Preview", style="green", justify="center", width=8)
            
            track_uris = []
            for i, track in enumerate(tracks, 1):
                duration_ms = track.get('duration_ms', 0)
                duration_str = self.format_duration(duration_ms)
                track_name = track.get('name', 'Unknown')
                
                # Check if preview URL is available
                has_preview = "🔊 Yes" if track.get('preview_url') else "❌ No"
                
                tracks_table.add_row(
                    str(i), 
                    track_name, 
                    duration_str,
                    has_preview
                )
                
                track_uris.append(track.get('uri'))
                
            # Create a panel for the tracks table
            tracks_panel = Panel(
                tracks_table,
                title="Album Tracks",
                title_align="center",
                title_style="bold green",
                border_style=app_state["theme"]["border"],
                box=app_state["theme"]["box"],
                padding=(1, 2),
                expand=False
            )
            
            console.print(self.center_text(tracks_panel))
            console.print("")
            
            # Add a confirmation panel
            total_duration_ms = sum(track.get('duration_ms', 0) for track in tracks)
            minutes = total_duration_ms // 60000
            seconds = (total_duration_ms % 60000) // 1000
            total_duration = f"{minutes} minutes, {seconds} seconds"
            
            confirm_text = (
                f"[bold white]Total Playtime:[/bold white] [cyan]{total_duration}[/cyan]\n"
                f"[bold white]Downloading:[/bold white] [green]{len(track_uris)} tracks[/green]\n\n"
                "[white]Use this album for download? Type [bold]Y[/bold] to confirm or [bold]N[/bold] to cancel[/white]"
            )
            
            confirm_panel = Panel(
                confirm_text,
                title="Confirm Download",
                border_style="blue",
                box=box.ROUNDED,
                expand=False,
                width=80
            )
            console.print(self.center_text(confirm_panel))
            console.print("")
            
            return track_uris
            
        except Exception as e:
            logger.error(f"Error fetching album details: {e}")
            
            # Display an error panel with details
            error_panel = Panel(
                f"[bold red]Error fetching album details:[/bold red]\n[white]{str(e)}[/white]",
                title="Error",
                border_style="red",
                box=app_state["theme"]["box"],
                expand=False,
                width=80
            )
            console.print(self.center_text(error_panel))
            console.print("")
            
            return []

    def search_music(self, query):
        """Search for music on Spotify.
        
        Args:
            query: Search query string
            
        Returns:
            dict: Selected item data or None if cancelled
        """
        console.clear()
        self.show_header()
        
        # Create a title with themed styling
        title_text = "[bold cyan]SPOTIFY SEARCH[/bold cyan]"
        console.print(self.center_text(title_text))
        console.print(self.center_text(f"[{app_state['theme']['border']}]{'═' * 60}[/{app_state['theme']['border']}]"))
        console.print("")
        
        # Create a search query panel
        query_panel = Panel(
            f"[yellow]Searching for:[/yellow] [bold white]{query}[/bold white]",
            title="Search Query",
            title_align="left",
            border_style="cyan",
            box=app_state["theme"]["box"],
            expand=False
        )
        console.print(self.center_text(query_panel))
        console.print("")
        
        if not self.spotify:
            if not self.initialize_spotify():
                error_panel = Panel(
                    "[bold red]Failed to initialize Spotify API connection.[/bold red]\n"
                    "[yellow]Please check your internet connection and API credentials.[/yellow]",
                    title="Connection Error",
                    border_style="red",
                    box=app_state["theme"]["box"],
                    expand=False
                )
                console.print(self.center_text(error_panel))
                return None
        
        try:
            # Display searching progress with a custom spinner
            with Progress(
                SpinnerColumn("dots"),
                TextColumn("[cyan]Searching Spotify...[/cyan]"),
                BarColumn(bar_width=40, complete_style="green", finished_style="green"),
                TextColumn("[yellow]Please wait[/yellow]"),
                console=console,
                transient=True,
            ) as progress:
                task = progress.add_task("search", total=100)
                
                # Update progress while searching
                progress.update(task, advance=30)
                track_results = self.spotify.search(query, limit=5, type='track')
                progress.update(task, advance=35)
                album_results = self.spotify.search(query, limit=5, type='album')
                progress.update(task, advance=35)
                
            # Process results
            tracks = track_results.get('tracks', {}).get('items', [])
            albums = album_results.get('albums', {}).get('items', [])
            
            if not tracks and not albums:
                # No results panel with suggestions
                no_results_panel = Panel(
                    "[bold yellow]No results found for your search.[/bold yellow]\n\n"
                    "[white]Suggestions:[/white]\n"
                    "• Check for spelling mistakes\n"
                    "• Try using fewer or different keywords\n"
                    "• Try searching by artist name or album title only",
                    title="No Results",
                    border_style="yellow",
                    box=app_state["theme"]["box"],
                    expand=False
                )
                console.print(self.center_text(no_results_panel))
                return None
                
            # Create results table with alternating row styles
            table = Table(
                title="Search Results", 
                box=app_state["theme"]["box"], 
                title_style="bold cyan",
                header_style="bold",
                border_style=app_state["theme"]["border"],
                row_styles=["", "dim"],
                highlight=True,
                width=90,
                expand=False
            )
            
            table.add_column("#", style="cyan", justify="right", width=3)
            table.add_column("Type", style="green", width=10)
            table.add_column("Title", style="white")
            table.add_column("Artist", style="yellow")
            table.add_column("Duration/Tracks", style="magenta", justify="right", width=15)
            
            # Add tracks to table with icons
            result_items = []
            idx = 1
            
            # Add tracks with 🎵 icon
            for track in tracks[:5]:
                duration_ms = track.get('duration_ms', 0)
                duration_str = self.format_duration(duration_ms)
                artists = ", ".join([artist['name'] for artist in track.get('artists', [])])
                
                table.add_row(
                    str(idx),
                    "🎵 Track",
                    track.get('name', 'Unknown'),
                    artists,
                    duration_str
                )
                result_items.append({"type": "track", "item": track})
                idx += 1
                
            # Add albums with 💿 icon
            for album in albums[:5]:
                album_type = album.get('album_type', 'Album').capitalize()
                artists = ", ".join([artist['name'] for artist in album.get('artists', [])])
                total_tracks = album.get('total_tracks', 0)
                
                table.add_row(
                    str(idx),
                    f"💿 {album_type}",
                    album.get('name', 'Unknown'),
                    artists,
                    f"{total_tracks} tracks"
                )
                result_items.append({"type": "album", "item": album})
                idx += 1
                
            # Wrap results table in a panel
            results_panel = Panel(
                table,
                border_style=app_state["theme"]["border"],
                box=app_state["theme"]["box"],
                padding=(1, 2),
                expand=False
            )
            console.print(self.center_text(results_panel))
            console.print("")
            
            # Instructions panel for selection
            instruction_panel = Panel(
                "Select a number to view details, or [bold]C[/bold] to cancel and return to menu",
                border_style="blue",
                box=box.ROUNDED,
                expand=False
            )
            console.print(self.center_text(instruction_panel))
            
            # Center the prompt and make it more visible
            console.print("")
            console.print(self.center_text("[white]Your selection:[/white]"))
            
            # Centralize the input prompt
            selection = Prompt.ask(
                self.center_text(""),
                choices=[str(i) for i in range(1, len(result_items) + 1)] + ["C", "c"],
                default="1"
            )
            
            if selection.upper() == "C":
                return None
                
            selected_idx = int(selection) - 1
            return result_items[selected_idx]
            
        except Exception as e:
            logger.error(f"Error searching music: {e}")
            error_panel = Panel(
                f"[bold red]Error while searching:[/bold red]\n[white]{str(e)}[/white]",
                title="Search Error",
                border_style="red",
                box=app_state["theme"]["box"],
                expand=False
            )
            console.print(self.center_text(error_panel))
            return None

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
```
