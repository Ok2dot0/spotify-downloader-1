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
import platform
import requests
import subprocess
import threading
import queue
import logging
import importlib.util
import signal
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Union, Any
from functools import partial
from concurrent.futures import ThreadPoolExecutor
import webbrowser
import shutil

# Check if packages are installed before importing
try:
    import dotenv
except ImportError:
    sys.exit("Required package 'python-dotenv' is missing. Please install it with: pip install python-dotenv")

try:
    from colorama import init, Fore, Back, Style
    from rich.console import Console
    from rich.table import Table
    from rich.panel import Panel
    from rich.layout import Layout
    from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TimeRemainingColumn
    from rich.prompt import Confirm, Prompt, IntPrompt
    from rich import box
except ImportError:
    sys.exit("Required packages are missing. Please install them with: pip install colorama rich")

try:
    import spotipy
    from spotipy.oauth2 import SpotifyClientCredentials
except ImportError:
    sys.exit("Required package 'spotipy' is missing. Please install it with: pip install spotipy")

# Define platform constants for better readability
IS_WINDOWS = sys.platform.startswith('win')
IS_MACOS = sys.platform == 'darwin'
IS_LINUX = sys.platform.startswith('linux')

# Import platform-specific modules
if IS_WINDOWS:
    try:
        import msvcrt  # For Windows key detection
    except ImportError:
        print("Warning: msvcrt module not available on this Windows system")
else:
    try:
        import select  # For Unix key detection
        import termios, tty
    except ImportError:
        print("Warning: Terminal control modules not available on this system")

# Import Windows-specific modules for disc burning only on Windows
WINDOWS_IMAPI_AVAILABLE = False
if IS_WINDOWS:
    try:
        # Only attempt to import these if we're on Windows
        import win32com.client
        import pythoncom
        from win32com.client import constants
        import comtypes
        import win32api
        WINDOWS_IMAPI_AVAILABLE = True
    except ImportError:
        WINDOWS_IMAPI_AVAILABLE = False
        print("Warning: Windows COM libraries (pywin32/comtypes) not available. CD/DVD burning will be limited.")
        print("To enable full burning capabilities, install: pip install pywin32 comtypes")

# Initialize colorama for cross-platform colored terminal output
init()
console = Console(width=None)  # width=None makes it auto-detect terminal width

# Define minimum required terminal dimensions
MIN_TERMINAL_WIDTH = 100
MIN_TERMINAL_HEIGHT = 30

# Configure logging with proper paths
def setup_logging():
    """Set up logging with proper file paths and rotation"""
    try:
        # Create log directory in user's home folder for better portability
        log_dir = os.path.join(os.path.expanduser("~"), ".spotify_burner", "logs")
        os.makedirs(log_dir, exist_ok=True)
        log_path = os.path.join(log_dir, "spotify_burner.log")
        
        # Get log level from environment or default to INFO
        log_level_name = os.environ.get("LOG_LEVEL", "INFO")
        try:
            log_level = getattr(logging, log_level_name.upper(), logging.INFO)
        except AttributeError:
            log_level = logging.INFO
            print(f"Warning: Invalid log level '{log_level_name}', using INFO")
        
        # Configure logging with rotation to prevent log files from growing too large
        logger = logging.getLogger("spotify_burner")
        logger.setLevel(log_level)
        
        # Clear any existing handlers to prevent duplicates
        if logger.handlers:
            for handler in logger.handlers[:]:
                logger.removeHandler(handler)
        
        # Add a rotating file handler
        try:
            # Try to use a rotating handler if available
            try:
                from logging.handlers import RotatingFileHandler
                file_handler = RotatingFileHandler(
                    log_path, maxBytes=10*1024*1024, backupCount=5, encoding='utf-8'
                )
            except ImportError:
                # Fall back to standard file handler if rotating handler is not available
                file_handler = logging.FileHandler(log_path, encoding='utf-8')
                
            file_formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
            file_handler.setFormatter(file_formatter)
            logger.addHandler(file_handler)
        except (PermissionError, OSError) as e:
            print(f"Warning: Could not set up file logging: {e}")
            
        # Add console handler for warnings and errors
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.WARNING)  # Only show warnings and errors in console
        console_formatter = logging.Formatter('%(levelname)s: %(message)s')
        console_handler.setFormatter(console_formatter)
        logger.addHandler(console_handler)
        
        return logger
    except Exception as e:
        # Set up a minimal fallback logger if anything goes wrong
        print(f"Error setting up logging: {e}")
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        return logging.getLogger("spotify_burner")

# Initialize logger
logger = setup_logging()

# Load environment variables from .env file
dotenv.load_dotenv()

# Constants
DEFAULT_OUTPUT_DIR = os.path.join(os.path.expanduser("~"), "Music", "SpotifyDownloads")
CONFIG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.json")
VERSION = "2.0.0"  # Updated version number
PYTHON_PATH = ".\\WinPython\\WPy64-31330\\python\\python.exe"
# Application state
app_state = {
    "download_queue": queue.Queue(),
    "current_downloads": 0,
    "max_concurrent_downloads": 3,  # Default concurrent downloads
    "terminal_size": {"width": 0, "height": 0}  # Will store terminal dimensions
}

def notify_terminal_resize_issues():
    """Display notification about terminal size issues if detected during runtime."""
    width, height = app_state["terminal_size"]["width"], app_state["terminal_size"]["height"]
    
    if width < MIN_TERMINAL_WIDTH or height < MIN_TERMINAL_HEIGHT:
        # Save current cursor position
        if not IS_WINDOWS:
            print("\033[s", end="", flush=True)  # Save cursor position
        
        # Clear notification area (last line of terminal)
        print(f"\033[{height};0H\033[K", end="", flush=True)  # Move to last line and clear
        
        # Display warning with red background on the bottom line
        print(f"\033[{height};0H\033[41;97m Terminal size too small: {width}x{height}. " +
              f"Minimum required: {MIN_TERMINAL_WIDTH}x{MIN_TERMINAL_HEIGHT} \033[0m", 
              end="", flush=True)
        
        # Restore cursor position
        if not IS_WINDOWS:
            print("\033[u", end="", flush=True)  # Restore cursor position
            
        return False
    return True

def check_terminal_size():
    """Check if the terminal has adequate dimensions for the application.
    Updates app_state with current dimensions and returns status.
    
    Returns:
        bool: True if terminal size is adequate, False otherwise
    """
    # Get current terminal size
    terminal_width, terminal_height = shutil.get_terminal_size((80, 24))  # Default fallback (80x24)
    
    # Update application state with current dimensions
    app_state["terminal_size"]["width"] = terminal_width
    app_state["terminal_size"]["height"] = terminal_height
    
    # Log the terminal size when it changes
    if hasattr(check_terminal_size, 'last_width') and \
       (check_terminal_size.last_width != terminal_width or 
        check_terminal_size.last_height != terminal_height):
        logger.info(f"Terminal resized to {terminal_width}x{terminal_height}")
    
    # Store last dimensions to detect changes
    check_terminal_size.last_width = terminal_width
    check_terminal_size.last_height = terminal_height
    
    # Check against minimum requirements
    if terminal_width < MIN_TERMINAL_WIDTH or terminal_height < MIN_TERMINAL_HEIGHT:
        return False
    return True

def is_very_small_terminal():
    """Check if the terminal is in a very constrained state (below minimum requirements).
    
    Returns:
        bool: True if terminal is below minimum size, False otherwise
    """
    width = app_state["terminal_size"]["width"]
    height = app_state["terminal_size"]["height"]
    return width < MIN_TERMINAL_WIDTH or height < MIN_TERMINAL_HEIGHT

def is_compact_terminal():
    """Check if the terminal is in a size that requires compact UI.
    
    Returns:
        bool: True if terminal should use compact UI, False otherwise
    """
    width = app_state["terminal_size"]["width"]
    height = app_state["terminal_size"]["height"]
    return width < MIN_TERMINAL_WIDTH + 20 or height < MIN_TERMINAL_HEIGHT + 5

def get_terminal_class():
    """Get a classification of the current terminal size.
    
    Returns:
        str: Size classification - 'very_small', 'compact', 'standard', or 'large'
    """
    width = app_state["terminal_size"]["width"]
    height = app_state["terminal_size"]["height"]
    
    if width < MIN_TERMINAL_WIDTH or height < MIN_TERMINAL_HEIGHT:
        return 'very_small'
    elif width < MIN_TERMINAL_WIDTH + 20 or height < MIN_TERMINAL_HEIGHT + 5:
        return 'compact'
    elif width >= 120 and height >= 40:
        return 'large'
    else:
        return 'standard'

def get_adaptive_width(component_type="panel", min_width=70):
    """Get width adjusted to terminal size.
    
    Args:
        component_type: Type of UI component ("panel", "table", "header", etc.)
        min_width: Minimum width to return (default 70)
    
    Returns:
        int: Width adjusted to the current terminal size
    """
    terminal_width = app_state["terminal_size"]["width"]
    # Return default if terminal width is not yet initialized
    if terminal_width <= 0:
        return 100
    
    # Get terminal size classification
    terminal_class = get_terminal_class()
    
    # Special handling for different component types
    if component_type == "panel":
        if terminal_class == 'large':
            return terminal_width - 10  # Larger margins for big terminals
        elif terminal_class == 'standard':
            return terminal_width - 5   # Medium margins
        elif terminal_class == 'compact':
            return terminal_width - 3   # Minimal margins
        else:  # very_small
            return max(min_width, terminal_width - 2)  # Almost full width
    
    elif component_type == "table":
        # Tables should be slightly smaller than panels
        if terminal_class == 'large':
            return terminal_width - 12
        elif terminal_class == 'standard':
            return terminal_width - 8
        elif terminal_class == 'compact':
            return terminal_width - 4
        else:  # very_small
            return max(min_width, terminal_width - 2)
            
    elif component_type == "header":
        # Headers can use most of the terminal width
        if terminal_class == 'very_small':
            return max(min_width, terminal_width - 2)
        else:
            return max(min_width, terminal_width - 4)
        
    # Default
    return max(min_width, terminal_width - 5)
        
def create_responsive_table(columns, show_header=True, title=None, box_style=None, border_style=None, compact_mode=None):
    """Create a responsive table with appropriate widths based on terminal size.
    
    Args:
        columns: List of column definitions, each should be a dict with keys:
            - 'name': Column name (for header)
            - 'style': Column style
            - 'justify': Text justification ('left', 'center', 'right')
            - 'width_ratio': Relative width ratio (optional)
            - 'no_wrap': Whether to disable text wrapping (optional)
            - 'min_width': Minimum column width (optional)
            - 'hide_when_compact': Hide this column in compact view (optional)
        show_header: Whether to show the table header
        title: Optional table title
        box_style: Box style for the table
        border_style: Border style for the table
        compact_mode: Force compact mode (True/False) or auto-detect if None
        
    Returns:
        rich.table.Table: A configured responsive table
    """
    # Get theme settings if not specified
    if box_style is None:
        box_style = app_state["theme"]["box"] if "theme" in app_state else box.ROUNDED
    if border_style is None:
        border_style = app_state["theme"]["border"] if "theme" in app_state else "cyan"
        
    # Determine if we should use compact mode
    if compact_mode is None:
        terminal_class = get_terminal_class()
        is_compact = terminal_class in ('very_small', 'compact')
    else:
        is_compact = compact_mode
    
    # Use simpler box style for compact mode
    if is_compact and box_style != box.SIMPLE:
        box_style = box.SIMPLE
        
    # Create the base table
    table = Table(
        show_header=show_header,
        box=box_style,
        border_style=border_style,
        title=title,
        title_style=f"bold {border_style}" if title else None,
        title_justify="center",
        width=get_adaptive_width("table")
    )
    
    # Calculate available width for columns with ratio
    available_width = get_adaptive_width("table")
    terminal_class = get_terminal_class()
    
    # Calculate total ratio
    total_ratio = sum(col.get('width_ratio', 1) 
                   for col in columns 
                   if 'width_ratio' in col and not (is_compact and col.get('hide_when_compact', False)))
    
    # Define minimum widths based on terminal size
    min_widths = {
        "icon": 2,
        "number": 3 if terminal_class in ('standard', 'large') else 2,
        "key": 5 if terminal_class in ('standard', 'large') else 3,
        "duration": 8 if terminal_class == 'large' else 6 if terminal_class == 'standard' else 4,
        "name": {
            'large': 25,
            'standard': 20,
            'compact': 15,
            'very_small': 12
        }.get(terminal_class, 15),
        "description": {
            'large': 40,
            'standard': 30,
            'compact': 20,
            'very_small': 15
        }.get(terminal_class, 20),
    }
    
    # Filter out columns that should be hidden in compact mode
    filtered_columns = [col for col in columns if not (is_compact and col.get('hide_when_compact', False))]
    
    # Add columns with calculated widths
    for col in filtered_columns:
        col_name = col.get('name', '')
        col_style = col.get('style', 'white')
        col_justify = col.get('justify', 'left')
        no_wrap = col.get('no_wrap', False)
        
        # Calculate width based on ratio or use fixed width
        if 'width' in col:
            width = col['width']
        elif 'width_ratio' in col and total_ratio > 0:
            # Calculate proportional width
            ratio = col['width_ratio'] / total_ratio
            width = int(available_width * ratio)
            
            # Apply minimum if specified
            if 'min_width' in col:
                width = max(width, col['min_width'])
            elif 'type' in col and col['type'] in min_widths:
                if isinstance(min_widths[col['type']], dict):
                    min_width = min_widths[col['type']].get(terminal_class, 
                                min_widths[col['type']].get('standard', 10))
                    width = max(width, min_width)
                else:
                    width = max(width, min_widths[col['type']])
        elif 'type' in col and col['type'] in min_widths:
            if isinstance(min_widths[col['type']], dict):
                width = min_widths[col['type']].get(terminal_class, 
                            min_widths[col['type']].get('standard', 10))
            else:
                width = min_widths[col['type']]
        else:
            width = None
            
        table.add_column(
            col_name, style=col_style, justify=col_justify, 
            width=width, no_wrap=no_wrap
        )
        
    return table

def start_size_monitor():
    """Start a background thread to periodically monitor terminal size changes.
    This is used as a fallback for environments where signal handlers don't work.
    
    Returns:
        threading.Thread: The monitoring thread
    """
    def monitor_terminal_size():
        last_width, last_height = 0, 0
        was_adequate_size = True  # Track if we previously had adequate size
        
        while not getattr(monitor_terminal_size, "stop", False):
            try:
                check_terminal_size()
                width = app_state["terminal_size"]["width"]
                height = app_state["terminal_size"]["height"]
                
                # Log size changes but avoid flooding logs
                if width != last_width or height != last_height:
                    logger.debug(f"Terminal size changed to {width}x{height}")
                    
                    # Check if size became inadequate
                    is_adequate = width >= MIN_TERMINAL_WIDTH and height >= MIN_TERMINAL_HEIGHT
                    
                    # Show warning if size changed from adequate to inadequate
                    if was_adequate_size and not is_adequate:
                        notify_terminal_resize_issues()
                        
                    # Update status tracking
                    was_adequate_size = is_adequate
                    last_width, last_height = width, height
                    
                # Sleep for a while to avoid burning CPU
                time.sleep(1)
            except Exception as e:
                logger.error(f"Error in terminal size monitor: {e}")
                time.sleep(5)  # Slow down if errors occur
    
    # Create and start the monitoring thread
    monitor_thread = threading.Thread(
        target=monitor_terminal_size,
        name="TerminalSizeMonitor",
        daemon=True  # Make thread exit when main program exits
    )
    monitor_thread.start()
    
    # Store stop flag with the thread for clean shutdown
    def stop_monitor():
        monitor_terminal_size.stop = True
        
    app_state["size_monitor"] = {
        "thread": monitor_thread,
        "stop": stop_monitor
    }
    
    return monitor_thread

class SpotifyBurner:
    def __init__(self):
        """Initialize the SpotifyBurner application."""
        self.spotify = None
        self.config = self.load_config()
        self.download_dir = self.config.get("download_dir", DEFAULT_OUTPUT_DIR)
        self.dvd_drive = self.config.get("dvd_drive", None)
        self.max_threads = self.config.get("max_threads", 3)
        self.audio_format = self.config.get("audio_format", "mp3")
        self.bitrate = self.config.get("bitrate", "128k")
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
        
        # Hide cursor at startup
        self.hide_cursor()
        
        # Start terminal size monitor
        start_size_monitor()
        
        # Setup signal handlers for clean exit
        self.setup_signal_handlers()
        
    def setup_signal_handlers(self):
        """Set up signal handlers for clean exit and terminal resize."""
        # Define signal handler function for termination signals
        def signal_handler(sig, frame):
            logger.info(f"Received signal {sig}, performing clean exit...")
            self.show_cursor()  # Ensure cursor is visible
            if hasattr(self, 'executor') and self.executor:
                self.executor.shutdown(wait=False)
            sys.exit(0)
        
        # Register terminal resize signal handler on Unix platforms
        if not IS_WINDOWS and hasattr(signal, 'SIGWINCH'):
            def resize_handler(sig, frame):
                # Store previous dimensions for comparison
                previous_width = app_state["terminal_size"]["width"]
                previous_height = app_state["terminal_size"]["height"]
                
                # Update terminal dimensions when resize is detected
                check_terminal_size()
                new_width = app_state["terminal_size"]["width"]
                new_height = app_state["terminal_size"]["height"]
                
                logger.debug(f"Terminal resize detected: {new_width}x{new_height}")
                
                # Show notification if size becomes inadequate
                if (previous_width >= MIN_TERMINAL_WIDTH and new_width < MIN_TERMINAL_WIDTH) or \
                   (previous_height >= MIN_TERMINAL_HEIGHT and new_height < MIN_TERMINAL_HEIGHT):
                    notify_terminal_resize_issues()
            
            signal.signal(signal.SIGWINCH, resize_handler)
        
        # Register signal handlers if on a platform that supports them
        if not IS_WINDOWS:  # Windows doesn't support all these signals
            signal.signal(signal.SIGTERM, signal_handler)
            signal.signal(signal.SIGHUP, signal_handler)
        
        # SIGINT (Ctrl+C) works on all platforms
        signal.signal(signal.SIGINT, signal_handler)
        
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
            theme_name: Name of the theme to apply (default, dark, light, modern, neon, spotify)
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
            },
            "modern": {
                "main_color": "bright_blue",
                "accent_color": "bright_cyan",
                "warning_color": "gold1",
                "error_color": "bright_red",
                "success_color": "bright_green",
                "header_style": "bold bright_blue",
                "border_style": "bright_blue",
                "box_type": box.ROUNDED
            },
            "neon": {
                "main_color": "hot_pink",
                "accent_color": "bright_cyan",
                "warning_color": "bright_yellow",
                "error_color": "bright_red",
                "success_color": "bright_green",
                "header_style": "bold hot_pink",
                "border_style": "purple",
                "box_type": box.DOUBLE
            },
            "spotify": {
                "main_color": "green4",
                "accent_color": "green1",
                "warning_color": "yellow",
                "error_color": "red",
                "success_color": "green",
                "header_style": "bold green",
                "border_style": "green",
                "box_type": box.ROUNDED
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

    def search_music(self, query, search_type=None):
        """Search for music on Spotify.
        
        Args:
            query: Search query string
            search_type: Type of search ('song', 'album', 'playlist', or None for all)
            
        Returns:
            dict: Selected album or track info, or None if cancelled
        """
        if not query:
            console.print("[yellow]Search query is empty[/yellow]")
            return None
            
        logger.info(f"Searching for: {query} (Type: {search_type or 'all'})")
        console.print(f"\n[bold]Searching for:[/bold] {query}")
        
        try:
            albums = []
            tracks = []
            playlists = []
              # Determine which types to search based on search_type
            if search_type == 'song' or search_type is None:
                try:
                    tracks_result = self.spotify.search(query, type="track", limit=10)
                    tracks = tracks_result.get("tracks", {}).get("items", []) if tracks_result else []
                except Exception as e:
                    logger.error(f"Error searching for tracks: {e}")
                    console.print(f"[yellow]Error searching for tracks: {e}[/yellow]")
                    tracks = []
                
            if search_type == 'album' or search_type is None:
                try:
                    albums_result = self.spotify.search(query, type="album", limit=10)
                    albums = albums_result.get("albums", {}).get("items", []) if albums_result else []
                except Exception as e:
                    logger.error(f"Error searching for albums: {e}")
                    console.print(f"[yellow]Error searching for albums: {e}[/yellow]")
                    albums = []
            
            if search_type == 'playlist' or search_type is None:
                try:
                    playlists_result = self.spotify.search(q=query, type='playlist', limit=10)
                    if playlists_result:
                        playlists_data = playlists_result.get('playlists') # Safely get 'playlists' dictionary
                        if playlists_data and isinstance(playlists_data, dict): # Check it's a dict
                            items = playlists_data.get('items') # Safely get 'items' list
                            if items and isinstance(items, list): # Check it's a list
                                for p_item in items:
                                    if p_item and isinstance(p_item, dict): # Ensure item is a dict and not None
                                        playlists.append(p_item)
                except spotipy.SpotifyException as e:
                    logger.error(f"Spotify API error searching for playlists: {e}")
                    console.print(f"[yellow]Spotify API error: Could not fetch playlists.[/yellow]")
                # Other exceptions will be caught by the main try-except in search_music
            
            # Display results only if found
            if not albums and not tracks and not playlists:
                console.print("[yellow]No results found. Try a different search query.[/yellow]")
                return None
                
            # Display albums
            if albums:
                console.print("\n[bold]Albums:[/bold]")
                album_table = Table(box=box.SIMPLE)
                album_table.add_column("No.", style="dim", width=4, justify="right")
                album_table.add_column("Album", style="cyan")
                album_table.add_column("Artist", style="green")
                album_table.add_column("Year", style="yellow", width=6)
                
                for i, album in enumerate(albums, 1):
                    # Extract album information
                    album_name = album["name"]
                    artist_name = album["artists"][0]["name"] if album["artists"] else "Unknown Artist"
                    release_year = album.get("release_date", "")[:4] if album.get("release_date") else ""
                    
                    # Add to table
                    album_table.add_row(str(i), album_name, artist_name, release_year)
                
                console.print(album_table)
            
            # Display tracks
            if tracks:
                console.print("\n[bold]Tracks:[/bold]")
                track_table = Table(box=box.SIMPLE)
                track_table.add_column("No.", style="dim", width=4, justify="right")
                track_table.add_column("Title", style="cyan")
                track_table.add_column("Artist", style="green")
                track_table.add_column("Album", style="yellow")
                
                start_index = len(albums) + 1
                for i, track in enumerate(tracks, start_index):
                    # Extract track information
                    track_name = track["name"]
                    artist_name = track["artists"][0]["name"] if track["artists"] else "Unknown Artist"
                    album_name = track["album"]["name"] if "album" in track else "Single"
                    
                    # Add to table
                    track_table.add_row(str(i), track_name, artist_name, album_name)
                
                console.print(track_table)
                
            # Display playlists
            if playlists:
                console.print("\n[bold]Playlists:[/bold]")
                playlist_table = Table(box=box.SIMPLE)
                playlist_table.add_column("No.", style="dim", width=4, justify="right")
                playlist_table.add_column("Playlist", style="cyan")
                playlist_table.add_column("Owner", style="green")
                playlist_table.add_column("Tracks", style="yellow", width=8)
                
                start_index = len(albums) + len(tracks) + 1
                for i, playlist_item in enumerate(playlists, start_index):
                    # Extract playlist information safely
                    playlist_name = playlist_item.get("name", "Unknown Playlist")
                    
                    owner_data = playlist_item.get("owner") # owner_data can be None or a dict
                    owner_name = owner_data.get("display_name", "Unknown Owner") if isinstance(owner_data, dict) else "Unknown Owner"
                    
                    tracks_data = playlist_item.get("tracks") # tracks_data can be None or a dict
                    track_count_value = tracks_data.get("total") if isinstance(tracks_data, dict) else None
                    track_count = str(track_count_value) if track_count_value is not None else "?"
                    
                    # Add to table
                    playlist_table.add_row(str(i), playlist_name, owner_name, track_count)
                
                console.print(playlist_table)
            
            # Prompt for selection
            total_items = len(albums) + len(tracks) + len(playlists)
            input_message = f"Enter selection number [1-{total_items}], or 'C' to cancel"
            
            while True:
                choice = Prompt.ask(input_message, choices=[str(i) for i in range(1, total_items + 1)] + ["C", "c"])
                
                if choice.upper() == "C":
                    return None
                    
                try:
                    # Parse selection
                    index = int(choice) - 1
                    
                    # Determine if album, track, or playlist
                    if index < len(albums):
                        return {
                            "type": "album",
                            "item": albums[index]
                        }
                    elif index < len(albums) + len(tracks):
                        track_index = index - len(albums)
                        return {
                            "type": "track",
                            "item": tracks[track_index]
                        }
                    else:
                        playlist_index = index - (len(albums) + len(tracks))
                        return {
                            "type": "playlist",
                            "item": playlists[playlist_index]
                        }
                except (ValueError, IndexError):
                    console.print(f"[red]Invalid selection. Please enter a number between 1 and {total_items}.[red]")
                    
        except KeyboardInterrupt:
            console.print("\n[yellow]Search cancelled by user.[/yellow]")
            return None
        except Exception as e:
            logger.error(f"Error during search: {e}")
            console.print(f"[bold red]Error during search: {e}[/bold red]")
            return None

    def search_and_download(self):
        """Search for and download music from Spotify."""
        self.clear_screen()
        
        # Show search header
        console.print("[bold cyan]SEARCH AND DOWNLOAD MUSIC[bold cyan]")
        console.print("=" * 50)
        
        # Get search type first
        console.print("\n[bold]What would you like to search for?[/bold]")
        console.print("[1] Songs")
        console.print("[2] Albums")
        console.print("[3] Playlists")
        console.print("[4] All Types")
        
        search_type_choice = Prompt.ask("Select search type", choices=["1", "2", "3", "4"], default="4")
        
        search_type = None
        if search_type_choice == "1":
            search_type = "song"
        elif search_type_choice == "2":
            search_type = "album"
        elif search_type_choice == "3":
            search_type = "playlist"
        # else type remains None (search all types)
        
        # Get search query
        query = Prompt.ask("Enter search query")
        if not query:
            return
        
        # Search for music
        selection = self.search_music(query, search_type)
        if not selection:
            self.wait_for_keypress()
            return
        
        # Display detailed information and get tracks
        tracks = self.display_music_info(selection)
        if not tracks:
            console.print("[yellow]No tracks found for the selection.[/yellow]")
            self.wait_for_keypress()
            return
        
        # Get album URL for more efficient album downloads
        album_url = None
        if selection["type"] == "album":
            album_url = selection["item"]["external_urls"].get("spotify")
        
        # Confirm download
        if not Confirm.ask("\nDo you want to download these tracks?"):
            return
        
        # Determine base name for download folder
        base_folder_name = "Downloaded Tracks"  # Default
        item = selection["item"]
        if selection["type"] == "album":
            artist_name = item["artists"][0]["name"] if item.get("artists") else "Unknown Artist"
            album_name = item.get("name", "Unknown Album")
            base_folder_name = f"{artist_name} - {album_name}"
        elif selection["type"] == "track":
            artist_name = item["artists"][0]["name"] if item.get("artists") else "Unknown Artist"
            if item.get("album") and item["album"].get("name"):
                album_name = item["album"].get("name", "Unknown Album")
                base_folder_name = f"{artist_name} - {album_name}"
            else:
                track_name = item.get("name", "Unknown Track")
                base_folder_name = f"{artist_name} - {track_name}"
        elif selection["type"] == "playlist":
            base_folder_name = item.get("name", "Unnamed Playlist")


        # Sanitize the base folder name
        sane_folder_name = re.sub(r'[<>:\"/\\\\|?*]', '_', base_folder_name)  # Invalid path chars
        sane_folder_name = re.sub(r'[\\.\\s]+$', '', sane_folder_name) # trailing dots/spaces
        sane_folder_name = re.sub(r'^[\\.\\s]+', '', sane_folder_name) # leading dots/spaces
        if not sane_folder_name:
            sane_folder_name = "Sanitized_Downloaded_Tracks"
            
        current_output_dir = os.path.join(self.download_dir, sane_folder_name)
        
        # Download tracks
        success = self.download_tracks(tracks, current_output_dir, album_url)
        if not success:
            console.print("[red]Download failed or was incomplete! Check the error messages above for details.[/red]")
            self.wait_for_keypress()
            return
        
        # Enhance metadata
        self.enhance_download_metadata(selection, current_output_dir)
        
        # Ask about burning
        if Confirm.ask("\nDo you want to burn these tracks to CD/DVD?"):
            self.burn_to_disc(current_output_dir, self.dvd_drive)
        
        self.wait_for_keypress()

    def display_music_info(self, selection):
        """Display detailed information about the selected music.
        
        Args:
            selection: Dictionary containing album, track, or playlist info
            
        Returns:
            list: List of track URLs for downloading
        """
        if not selection:
            return []
            
        item_type = selection["type"]
        item = selection["item"]
        
        self.clear_screen()
        
        if item_type == "album":
            # Display album info
            album_id = item["id"]
            album_name = item["name"]
            artist_name = item["artists"][0]["name"] if item["artists"] else "Unknown Artist"
            release_date = item.get("release_date", "Unknown")
            total_tracks = item.get("total_tracks", "Unknown")
            
            # Display album info in a panel
            album_info = f"[bold cyan]{album_name}[/bold cyan]\n"
            album_info += f"[green]Artist:[/green] {artist_name}\n"
            album_info += f"[green]Release Date:[/green] {release_date}\n"
            album_info += f"[green]Tracks:[/green] {total_tracks}"
            
            console.print(Panel(album_info, title="Album Information", border_style="cyan"))
            
            # Get album tracks
            try:
                album_tracks = self.spotify.album_tracks(album_id)
                tracks = album_tracks["items"] if "items" in album_tracks else []
                
                if not tracks:
                    console.print("[yellow]No tracks found in this album.[/yellow]")
                    return []
                
                # Display tracks in a table
                tracks_table = Table(title=f"Tracks in {album_name}", box=box.SIMPLE)
                tracks_table.add_column("No.", style="dim", width=4, justify="right")
                tracks_table.add_column("Title", style="cyan")
                tracks_table.add_column("Duration", style="yellow", justify="right")
                
                track_urls = []
                for i, track in enumerate(tracks, 1):
                    track_name = track["name"]
                    duration_ms = track["duration_ms"]
                    minutes, seconds = divmod(duration_ms // 1000, 60)
                    duration = f"{minutes}:{seconds:02d}"
                    
                    tracks_table.add_row(str(i), track_name, duration)
                    
                    # Add track URL
                    track_urls.append(track["external_urls"].get("spotify", ""))
                
                console.print(tracks_table)
                return track_urls
                
            except Exception as e:
                logger.error(f"Error getting album tracks: {e}")
                console.print(f"[bold red]Error getting album tracks: {e}[/bold red]")
                return []
                
        elif item_type == "track":
            # Display track info
            track_name = item["name"]
            artist_name = item["artists"][0]["name"] if item["artists"] else "Unknown Artist"
            album_name = item["album"]["name"] if "album" in item else "Single"
            duration_ms = item["duration_ms"]
            minutes, seconds = divmod(duration_ms // 1000, 60)
            duration = f"{minutes}:{seconds:02d}"
            
            # Display track info in a panel
            track_info = f"[bold cyan]{track_name}[/bold cyan]\n"
            track_info += f"[green]Artist:[/green] {artist_name}\n"
            track_info += f"[green]Album:[/green] {album_name}\n"
            track_info += f"[green]Duration:[/green] {duration}"
            
            console.print(Panel(track_info, title="Track Information", border_style="cyan"))
            
            # Return single track URL
            track_url = item["external_urls"].get("spotify", "")
            return [track_url] if track_url else []
            
        elif item_type == "playlist":
            # Display playlist info
            playlist_id = item["id"]
            playlist_name = item["name"]
            owner_name = item["owner"]["display_name"] if "owner" in item else "Unknown Owner"
            total_tracks = item.get("tracks", {}).get("total", "Unknown")
            
            # Display playlist info in a panel
            playlist_info = f"[bold cyan]{playlist_name}[/bold cyan]\n"
            playlist_info += f"[green]Owner:[/green] {owner_name}\n"
            playlist_info += f"[green]Tracks:[/green] {total_tracks}"
            
            console.print(Panel(playlist_info, title="Playlist Information", border_style="cyan"))
            
            # Get playlist tracks
            try:
                # Playlists can be large, so we might need to paginate
                tracks = []
                results = self.spotify.playlist_tracks(playlist_id)
                
                if not results:
                    logger.error("Received empty results when fetching playlist tracks")
                    console.print("[yellow]Error: Could not retrieve playlist tracks[/yellow]")
                    return []
                    
                # Use get() with default to avoid KeyError
                playlist_items = results.get('items', [])
                if playlist_items:
                    tracks.extend(playlist_items)
                
                # Handle pagination if next page exists
                while results.get('next'):
                    results = self.spotify.next(results)
                    if not results:
                        break
                    next_items = results.get('items', [])
                    if next_items:
                        tracks.extend(next_items)
                
                if not tracks:
                    console.print("[yellow]No tracks found in this playlist.[/yellow]")
                    return []
                
                # Display tracks in a table
                tracks_table = Table(title=f"Tracks in {playlist_name}", box=box.SIMPLE)
                tracks_table.add_column("No.", style="dim", width=4, justify="right")
                tracks_table.add_column("Title", style="cyan")
                tracks_table.add_column("Artist", style="green")
                tracks_table.add_column("Album", style="yellow")
                tracks_table.add_column("Duration", style="yellow", justify="right")
                
                track_urls = []
                for i, item in enumerate(tracks, 1):
                    # In playlists, the track is nested inside the item
                    if not item or 'track' not in item:
                        continue
                    
                    track = item['track']
                    if not track:  # Skip if track is None (can happen with removed tracks)
                        continue
                    
                    try:
                        track_name = track.get("name", "Unknown Track")
                        
                        # Get artist name safely
                        artists = track.get("artists", [])
                        artist_name = artists[0].get("name", "Unknown Artist") if artists else "Unknown Artist"
                        
                        # Get album name safely
                        album = track.get("album", {})
                        album_name = album.get("name", "Single") if album else "Single"
                        
                        # Get duration safely
                        duration_ms = track.get("duration_ms", 0)
                        minutes, seconds = divmod(duration_ms // 1000, 60)
                        duration = f"{minutes}:{seconds:02d}"
                    except Exception as e:
                        logger.error(f"Error processing playlist track: {e}")
                        continue
                    
                    tracks_table.add_row(str(i), track_name, artist_name, album_name, duration)
                    
                    # Add track URL safely
                    external_urls = track.get("external_urls", {})
                    track_url = external_urls.get("spotify", "")
                    if track_url:
                        track_urls.append(track_url)
                
                console.print(tracks_table)
                
                # For large playlists, confirm download
                if len(tracks) > 50:
                    console.print(f"\n[yellow]Warning: This playlist contains {len(tracks)} tracks.[/yellow]")
                    if not Confirm.ask("Are you sure you want to download all these tracks?"):
                        return []
                
                return track_urls
                
            except Exception as e:
                logger.error(f"Error getting playlist tracks: {e}")
                console.print(f"[bold red]Error getting playlist tracks: {e}[/bold red]")
                return []
            
        return []

    def enhance_download_metadata(self, selection, output_dir):
        """Enhance downloaded music metadata.
        
        Args:
            selection: Dictionary containing album or track info
            output_dir: Directory containing downloaded music
        """
        if not selection or not output_dir:
            return
            
        console.print("\n[bold cyan]Enhancing metadata...[/bold cyan]")
        
        try:
            # TODO: Additional metadata enhancement could be implemented here
            # - Fix tags
            
            console.print("[green]Metadata enhancement completed[/green]")
            
        except Exception as e:
            logger.error(f"Error enhancing metadata: {e}")
            console.print(f"[yellow]Error enhancing metadata: {e}[/yellow]")

    def play_album(self, album_path):
        """Play an album with the default system player.
        
        Args:
            album_path: Path to the album directory
        """
        if not os.path.exists(album_path):
            console.print("[red]Album path not found.[/red]")
            return
            
        console.print(f"[bold]Opening album:[/bold] {album_path}")
        
        try:
            if sys.platform == "win32":
                os.startfile(album_path)
            elif sys.platform == "darwin":  # macOS
                subprocess.run(["open", album_path])
            else:  # Linux
                subprocess.run(["xdg-open", album_path])
        except Exception as e:
            console.print(f"[red]Error opening album: {e}[/red]")
            
    def delete_album(self, album_path):
        """Delete an album directory and its contents.
        
        Args:
            album_path: Path to the album directory
            
        Returns:
            bool: True if deletion was successful
        """
        if not os.path.exists(album_path):
            console.print("[red]Album path not found.[/red]")
            return False
            
        try:
            shutil.rmtree(album_path)
            logger.info(f"Deleted album: {album_path}")
            console.print(f"[green]Album deleted successfully.[/green]")
            return True
        except Exception as e:
            logger.error(f"Error deleting album {album_path}: {e}")
            console.print(f"[red]Error deleting album: {e}[/red]")
            return False
            
    def detect_optical_drives(self):
        """Detect optical drives on the system.
        
        Returns:
            dict: A dictionary mapping drive letters to drive numbers
        """
        drives = {}
        
        # Try using CDBurnerXP's --list-drives command to get drive information
        try:
            # First check for environment variable (set by batch file)
            env_path = os.environ.get("CDBURNERXP_PATH")
            # Then check burn settings, then fall back to default if not set
            default_exe = ".\\CDBurnerXP\\cdbxpcmd.exe"
            cdburnerxp_path = env_path or self.burn_settings.get("cdburnerxp_path") or default_exe
            
            if os.path.exists(cdburnerxp_path):
                logger.info(f"Using CDBurnerXP at {cdburnerxp_path} to detect drives")
                console.print(f"[cyan]Detecting optical drives with CDBurnerXP...[/cyan]")
                
                # Run the command to list drives
                process = subprocess.run([cdburnerxp_path, "--list-drives"], 
                                        capture_output=True, text=True)
                
                if process.returncode == 0:
                    # Process successful output
                    output = process.stdout
                    lines = output.strip().split('\n')
                              # Parse the output to get drive numbers and letters
                    for line in lines:
                        # Handle formats like "0: DVD RW (H:\)" or "0: Drive D:\"
                        if ':' in line:
                            parts = line.split(':', 1)
                            drive_number = parts[0].strip()
                            
                            # Extract drive letter from parentheses like (H:\) or from format like "Drive D:\"
                            if '(' in line and ')' in line:
                                drive_letter = line.split('(')[1].split(')')[0].replace(':\\', '')
                                drives[drive_letter] = drive_number
                            else:
                                match = re.search(r'Drive\s+([A-Z]):.*', parts[1])
                                if match:
                                    drive_letter = match.group(1)
                                    drives[drive_letter] = drive_number
                            
                            if drive_letter in drives:
                                logger.info(f"Found optical drive: {drive_letter}: (drive number {drive_number})")
                    
                    if drives:
                        return drives
                    else:
                        logger.warning("No drives found with CDBurnerXP --list-drives")
                else:
                    logger.warning(f"CDBurnerXP --list-drives returned error code {process.returncode}")
        except Exception as e:
            logger.error(f"Error using CDBurnerXP to detect drives: {e}")
        
        # Fall back to Windows or system-specific methods if the CDBurnerXP method fails
        drive_letters = []
        
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
                        # VolumePathNames returns a tuple, not a callable method
                        try:
                            volume_paths = disc_recorder.VolumePathNames
                            # Check if volume_paths is None, empty, or not a sequence
                            if volume_paths and hasattr(volume_paths, '__len__') and len(volume_paths) > 0:
                                drive_letter = volume_paths[0]
                                drive_letters.append(drive_letter)
                                logger.info(f"Found optical drive (fallback): {drive_letter}")
                            else:
                                logger.warning(f"No volume path found for disc recorder {i}")
                        except Exception as e:
                            logger.warning(f"Error accessing volume paths for disc recorder {i}: {e}")
                            # Try to get friendly name as fallback
                            try:
                                friendly_name = disc_recorder.GetDeviceName()
                                logger.info(f"Found optical drive with name: {friendly_name} but could not get drive letter")
                            except:
                                pass
                        
                except Exception as e:
                    logger.error(f"Error detecting optical drives via IMAPI2: {e}")
                    # Fallback to the standard method
                    drive_letters = self._detect_optical_drives_fallback()
                finally:
                    # Clean up COM
                    pythoncom.CoUninitialize()
            else:
                # Use fallback if pywin32 is not available
                drive_letters = self._detect_optical_drives_fallback()
        else:
            # For Unix-based systems
            if os.path.exists('/dev/cdrom'):
                drive_letters.append('/dev/cdrom')
            if os.path.exists('/dev/dvd'):
                drive_letters.append('/dev/dvd')
          # Convert the list of drive letters to a dictionary with mock drive numbers
        for i, drive_letter in enumerate(drive_letters):
            drives[drive_letter] = str(i)
        
        return drives

    def _detect_optical_drives_fallback(self):
        """Fallback method to detect optical drives using standard Windows API.
        
        Returns:
            list: A list of drive letters
        """
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
          # Use CDBurnerXP command-line for burning
        # First check for environment variable (set by batch file)
        env_path = os.environ.get("CDBURNERXP_PATH")
        # Then check burn settings, then fall back to default if not set
        default_exe = ".\\CDBurnerXP\\cdbxpcmd.exe"
        cdburnerxp_path = env_path or self.burn_settings.get("cdburnerxp_path") or default_exe
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
            disc_label = disc_label[:16] if len(disc_label) > 16 else disc_label            # First, get a list of available drives directly from CDBurnerXP
            console.print("[cyan]Getting list of available drives from CDBurnerXP...[/cyan]")
            try:
                # Run the --list-drives command to get available drives
                drives_cmd = f'"{cdburnerxp_path}" --list-drives'
                logger.info(f"Executing drive detection command: {drives_cmd}")
                drives_result = subprocess.run(drives_cmd, capture_output=True, text=True, shell=True)
                
                # Parse the output to get drive numbers and their corresponding letters
                drive_mapping = {}
                if drives_result.returncode == 0:
                    drive_output = drives_result.stdout.strip()
                    console.print(f"[dim]Available drives: \n{drive_output}[/dim]")
                    
                    # Parse output like "0: DVD RW (H:\)" to extract drive number and letter
                    for line in drive_output.split('\n'):
                        if ':' in line:
                            try:
                                parts = line.split(':', 1)
                                drive_num = parts[0].strip()
                                # Extract drive letter from parentheses like (H:\)
                                if '(' in parts[1] and ')' in parts[1]:
                                    drive_info = parts[1].strip()
                                    drive_letter_match = re.search(r'\(([A-Z]):\\?\)', drive_info)
                                    if drive_letter_match:
                                        drive_letter = drive_letter_match.group(1)
                                        drive_mapping[drive_letter] = drive_num
                                        logger.info(f"Mapped drive {drive_letter}: to drive number {drive_num}")
                            except Exception as parse_error:
                                logger.error(f"Error parsing drive info '{line}': {parse_error}")
                    
                    logger.info(f"Found optical drives: {drive_mapping}")
                else:
                    logger.error(f"Error getting drive list: {drives_result.stderr}")
                    console.print(f"[red]Error getting drive list: {drives_result.stderr}[/red]")
            except Exception as e:
                logger.error(f"Exception getting drive list: {e}")
                console.print(f"[red]Exception getting drive list: {e}[/red]")
                drive_mapping = {}
            
            if not drive_mapping:
                # Fall back to detect_optical_drives if CDBurnerXP drive list fails
                optical_drives = self.detect_optical_drives()
                if not optical_drives:
                    logger.error("No optical drives detected for burning")
                    console.print("[bold red]Error: No optical drives detected[/bold red]")
                    self.show_manual_burn_instructions(source_dir)
                    return False
                
                # Use first detected drive number (default to 0)
                selected_drive = "0"
                console.print(f"[yellow]No drive mapping found, defaulting to drive 0[/yellow]")
            else:
                if drive:
                    # User specified a drive letter, try to map to drive number
                    drive_letter = drive.replace(':', '')
                    if drive_letter in drive_mapping:
                        selected_drive = drive_mapping[drive_letter]
                    else:
                        # If drive letter not found in mapping, use first available
                        selected_drive = list(drive_mapping.values())[0]
                        console.print(f"[yellow]Drive {drive} not found, using drive {selected_drive}[/yellow]")
                else:
                    # No drive specified, use first available
                    selected_drive = list(drive_mapping.values())[0]
                
                console.print(f"[cyan]Using optical drive {selected_drive}[/cyan]")
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
                    burn_folder = source_dir            # According to the CDBurnerXP documentation, build command string
            # Using the correct syntax for folder options and drive number (not letter)
            # Make sure to properly escape and quote paths
            
            # Handle absolute paths to avoid issues
            burn_folder_absolute = os.path.abspath(burn_folder)
            cdburnerxp_path_absolute = os.path.abspath(cdburnerxp_path)
            
            # Build base command with properly quoted executable path
            cmd_string = f'"{cdburnerxp_path_absolute}" {action} -device:{selected_drive}'
            
            # Handle source content based on action type
            if action == '--burn-video':
                # For DVD-Video, specify the full path of the VIDEO_TS folder
                # Format: -folder:PATH with quotes for paths with spaces
                cmd_string += f' -folder:"{burn_folder_absolute}"'
            elif action == '--burn-audio':
                # For audio discs, use the folder option with proper quoting
                cmd_string += f' -folder:"{burn_folder_absolute}"'
            else:
                # For data discs, use the folder option with proper quoting
                cmd_string += f' -folder:"{burn_folder_absolute}"'
            
            # Add disc name with proper escaping if it contains special characters
            # Remove quotes from label if present and escape if needed
            safe_label = disc_label.replace('"', '').replace("'", "")
            cmd_string += f' -name:"{safe_label}"'
              # Add audio-specific mode (only for CD-R/CD-RW)
            if action == '--burn-audio':
                cmd_string += ' -dao'  # Disc-at-once for gapless
                
            # Add speed if configured
            if self.burn_settings.get("speed"):
                cmd_string += f' -speed:{self.burn_settings.get("speed")}'
                
            # Add verification flag
            if self.burn_settings.get("verify"):
                cmd_string += ' -verify'
                
            # Add eject flag
            if self.burn_settings.get("eject"):
                cmd_string += ' -eject'
                
            # Finalize disc
            cmd_string += ' -close'
                  # This command display will be handled in the execution section below# Log the command
            logger.info(f"Executing CDBurnerXP command: {cmd_string}")
            
            # Display the command for better debugging
            console.print("[bold cyan]Burning command details:[/bold cyan]")
            console.print(f"[cyan]Action:[/cyan] {action}")
            console.print(f"[cyan]Drive:[/cyan] {selected_drive}")
            console.print(f"[cyan]Source:[/cyan] {burn_folder_absolute}")
            console.print(f"[cyan]Disc label:[/cyan] {safe_label}")
            console.print(f"[cyan]Full command:[/cyan] {cmd_string}")
            console.print("[cyan]Launching CDBurnerXP burning process...[/cyan]")
            
            # Execute the command with shell=True to properly handle quoted paths
            try:
                process = subprocess.run(cmd_string, capture_output=True, text=True, shell=True)
            except Exception as run_error:
                logger.error(f"Error executing CDBurnerXP: {run_error}")
                console.print(f"[bold red]Error executing CDBurnerXP: {run_error}[/bold red]")
                raise run_error
            if process.returncode == 0:
                console.print("[green]Burn completed successfully![green]")
                logger.info("Burn completed successfully")
                return True
            else:
                error_msg = process.stderr or process.stdout or "Unknown error"
                logger.error(f"Error during burn process: {error_msg}")
                console.print(f"[bold red]Error during burn: {error_msg}[bold red]")
                self.show_manual_burn_instructions(source_dir)
                return False
        except Exception as e:
            logger.error(f"Error during burn process: {e}")
            console.print(f"[bold red]Error during burn process: {e}[bold red]")
            self.show_manual_burn_instructions(source_dir)
            return False

    def graceful_shutdown(self):
        """Perform cleanup operations for a graceful shutdown."""
        logger.info("Performing graceful shutdown...")
        
        # Show cursor before exiting
        self.show_cursor()
        
        # Shutdown the executor if it exists
        if hasattr(self, 'executor') and self.executor:
            self.executor.shutdown(wait=False)
            
        # Set stop flag for any running threads
        self.stop_threads = True
        
        # Stop the terminal size monitor if it's running
        if "size_monitor" in app_state and app_state["size_monitor"]:
            try:
                app_state["size_monitor"]["stop"]()
                logger.debug("Stopped terminal size monitor")
            except Exception as e:
                logger.error(f"Error stopping terminal size monitor: {e}")
        
        logger.info("Graceful shutdown completed")
        
    def hide_cursor(self):
        """Hide the cursor in the terminal."""
        print("\033[?25l", end="", flush=True)  # ANSI escape code to hide cursor
        
    def show_cursor(self):
        """Show the cursor in the terminal."""
        print("\033[?25h", end="", flush=True)  # ANSI escape code to show cursor
        
    def show_manual_burn_instructions(self, download_dir):
        """Show manual burning instructions if automatic burning fails."""
        self.clear_screen()
        console.print("\n[bold yellow]Manual CD/DVD Burning Instructions[bold yellow]")
        console.print("=" * 70 + "\n")
        
        console.print(f"Your downloaded files are located in:\n[bold]{download_dir}[bold]\n")
        
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

    def clear_screen(self):
        """Clear the screen and reset cursor position for consistent display."""
        console.clear()
        # Reset cursor position to top-left corner
        print("\033[H", end="")  # Move cursor to home position
        # Hide cursor for cleaner appearance
        self.hide_cursor()
        
    def show_header(self):
        """Display the application header."""
        # Update terminal dimensions
        check_terminal_size()
        
        # Get theme-appropriate colors
        header_style = app_state["theme"]["header"] if "theme" in app_state else "bold cyan"
        main_color = app_state["theme"]["main"] if "theme" in app_state else "cyan"
        accent_color = app_state["theme"]["accent"] if "theme" in app_state else "green"
        
        # Get current terminal dimensions
        width = app_state["terminal_size"]["width"]
        height = app_state["terminal_size"]["height"]
        
        # For very small terminals, show compact header
        if width < MIN_TERMINAL_WIDTH - 20 or height < MIN_TERMINAL_HEIGHT - 5:
            # Ultra-compact header for very constrained terminals
            compact_text = [
                f"[{main_color}]SPOTIFY DOWNLOADER & BURNER v{VERSION}[/{main_color}]"
            ]
            
            header = Panel(
                "\n".join(compact_text),
                box=box.SIMPLE,
                border_style=header_style,
                padding=(0, 1),
                width=width - 2,
            )
            
            console.print(header)
            return
            
        # For larger terminals, show full logo
        if app_state["terminal_size"]["width"] >= MIN_TERMINAL_WIDTH:
            # Select header style based on theme
            if self.theme in ["modern", "spotify"]:
                # Create a panel with modern theme logo
                logo_text = [
                    f"[{main_color}]    ███████╗██████╗  ██████╗ ████████╗██╗███████╗██╗   ██╗[/{main_color}]    [{accent_color}]██████╗ ██╗   ██╗██████╗ ███╗   ██╗[/{accent_color}]",
                    f"[{main_color}]    ██╔════╝██╔══██╗██╔═══██╗╚══██╔══╝██║██╔════╝╚██╗ ██╔╝[/{main_color}]    [{accent_color}]██╔══██╗██║   ██║██╔══██╗████╗  ██║[/{accent_color}]",
                    f"[{main_color}]    ███████╗██████╔╝██║   ██║   ██║   ██║█████╗   ╚████╔╝ [/{main_color}]    [{accent_color}]██████╔╝██║   ██║██████╔╝██╔██╗ ██║[/{accent_color}]",
                    f"[{main_color}]    ╚════██║██╔═══╝ ██║   ██║   ██║   ██║██╔══╝    ╚██╔╝  [/{main_color}]    [{accent_color}]██╔══██╗██║   ██║██╔══██╗██║╚██╗██║[/{accent_color}]",
                    f"[{main_color}]    ███████║██║     ╚██████╔╝   ██║   ██║██║        ██║   [/{main_color}]    [{accent_color}]██████╔╝╚██████╔╝██║  ██║██║ ╚████║[/{accent_color}]",
                    f"[{main_color}]    ╚══════╝╚═╝      ╚═════╝    ╚═╝   ╚═╝╚═╝        ╚═╝   [/{main_color}]    [{accent_color}]╚═════╝  ╚═════╝ ╚═╝  ╚═╝╚═╝  ╚═══╝[/{accent_color}]",
                    "",
                    f"[bold white]                                  v{VERSION}[/bold white]"
                ]
                
                header = Panel(
                    "\n".join(logo_text),
                    box=box.ROUNDED,
                    border_style=header_style,
                    padding=(1, 2),
                    width=get_adaptive_width(),
                    title=f"[{header_style}]SPOTIFY DOWNLOADER & BURNER[/{header_style}]",
                    title_align="center"
                )
                
                console.print(header)
                
            elif self.theme == "neon":
                # For neon theme, use panel with neon style
                neon_text = [
                    f"[{main_color}]  ███████╗██████╗  ██████╗ ████████╗██╗███████╗██╗   ██╗[/{main_color}]    [{accent_color}]██████╗ ██╗   ██╗██████╗ ███╗   ██╗[/{accent_color}]",
                    f"[{main_color}]  ██╔════╝██╔══██╗██╔═══██╗╚══██╔══╝██║██╔════╝╚██╗ ██╔╝[/{main_color}]    [{accent_color}]██╔══██╗██║   ██║██╔══██╗████╗  ██║[/{accent_color}]",
                    f"[{main_color}]  ███████╗██████╔╝██║   ██║   ██║   ██║█████╗   ╚████╔╝ [/{main_color}]    [{accent_color}]██████╔╝██║   ██║██████╔╝██╔██╗ ██║[/{accent_color}]",
                    f"[{main_color}]  ╚════██║██╔═══╝ ██║   ██║   ██║   ██║██╔══╝    ╚██╔╝  [/{main_color}]    [{accent_color}]██╔══██╗██║   ██║██╔══██╗██║╚██╗██║[/{accent_color}]",
                    f"[{main_color}]  ███████║██║     ╚██████╔╝   ██║   ██║██║        ██║   [/{main_color}]    [{accent_color}]██████╔╝╚██████╔╝██║  ██║██║ ╚████║[/{accent_color}]",
                    f"[{main_color}]  ╚══════╝╚═╝      ╚═════╝    ╚═╝   ╚═╝╚═╝        ╚═╝   [/{main_color}]    [{accent_color}]╚═════╝  ╚═════╝ ╚═╝  ╚═╝╚═╝  ╚═══╝[/{accent_color}]",
                    "",
                    f"[bold white]                                  VERSION {VERSION}[/bold white]"
                ]
                
                header = Panel(
                    "\n".join(neon_text),
                    box=box.DOUBLE,
                    border_style=header_style,
                    padding=(1, 2),
                    width=get_adaptive_width(),
                    title=f"[{header_style}]NEON STYLE[/{header_style}]",
                    title_align="center"
                )
                
                console.print(header)
                
            else:
                # For classic theme, use panel with standard style
                classic_text = [
                    f"[{header_style}]  ███████╗ ██████╗   ██████╗  ████████╗ ██╗ ███████╗ ██╗   ██╗    ██████╗  ██╗   ██╗ ██████╗  ███╗   ██╗ ███████╗ ██████╗  [/{header_style}]",
                    f"[{header_style}]  ██╔════╝ ██╔══██╗ ██╔═══██╗ ╚══██╔══╝ ██║ ██╔════╝ ╚██╗ ██╔╝    ██╔══██╗ ██║   ██║ ██╔══██╗ ████╗  ██║ ██╔════╝ ██╔══██╗ [/{header_style}]",
                    f"[{header_style}]  ███████╗ ██████╔╝ ██║   ██║    ██║    ██║ █████╗    ╚████╔╝     ██████╔╝ ██║   ██║ ██████╔╝ ██╔██╗ ██║ █████╗   ██████╔╝ [/{header_style}]",
                    f"[{header_style}]  ╚════██║ ██╔═══╝  ██║   ██║    ██║    ██║ ██╔══╝     ╚██╔╝      ██╔══██╗ ██║   ██║ ██╔══██╗ ██║╚██╗██║ ██╔══╝   ██╔══██╗ [/{header_style}]",
                    f"[{header_style}]  ███████║ ██║      ╚██████╔╝    ██║    ██║ ██║         ██║       ██████╔╝ ╚██████╔╝ ██║  ██║ ██║ ╚████║ ███████╗ ██║  ██║ [/{header_style}]",
                    f"[{header_style}]  ╚══════╝ ╚═╝       ╚═════╝     ╚═╝    ╚═╝ ╚═╝         ╚═╝       ╚═════╝   ╚═════╝  ╚═╝  ╚═╝ ╚═╝  ╚═══╝ ╚══════╝ ╚═╝  ╚═╝ [/{header_style}]",
                    "",
                    f"[bold white]                                  SPOTIFY DOWNLOADER & BURNER v{VERSION}                                  [/bold white]"
                ]
                
                header = Panel(
                    "\n".join(classic_text),
                    box=box.ROUNDED,
                    border_style=header_style,
                    padding=(1, 0),
                    width=get_adaptive_width()
                )
                
                console.print(header)
        else:
            # For smaller terminals, show a simplified header
            simple_header = f"[{header_style}]SPOTIFY DOWNLOADER & BURNER v{VERSION}[/{header_style}]"
            console.print(Panel(
                simple_header, 
                border_style=header_style, 
                box=box.ROUNDED,
                width=get_adaptive_width()
            ))
        
        # Add slogan with theme-specific formatting
        if self.theme == "neon":
            console.print(f"[{accent_color} bold]🎵 Search, download, and burn your favorite music! 🎵[/{accent_color} bold]\n")
        elif self.theme == "spotify":
            console.print(Panel.fit(
                f"[bold]Powered by Spotify API & SpotDL[/bold]", 
                border_style=accent_color,
                width=get_adaptive_width(),
                padding=(0, 2)
            ))
        else:
            console.print(f"[bold]Search, download, and burn your favorite music![/bold]\n")

    def show_main_menu(self):
        """Display the main menu and handle user input."""
        while True:
            # Update terminal size first
            check_terminal_size()
            
            # Check if terminal size is adequate, show notification if not
            if not notify_terminal_resize_issues():
                # We still continue showing the menu, but the notification will be visible
                pass
                
            # Clear console and ensure cursor is at the top position
            self.clear_screen()
            self.show_header()
            
            # Get theme colors for consistent styling
            main_color = app_state["theme"]["main"] if "theme" in app_state else "cyan"
            accent_color = app_state["theme"]["accent"] if "theme" in app_state else "green"
            box_style = app_state["theme"]["box"] if "theme" in app_state else box.ROUNDED
            border_style = app_state["theme"]["border"] if "theme" in app_state else "cyan"
            
            # Create styled menu panel with options table inside
            menu_title = "[bold]MAIN MENU[/bold]" if self.theme != "spotify" else "[bold]✨ MAIN MENU ✨[/bold]"
            
            # Determine appropriate column widths based on terminal size
            is_wide = app_state["terminal_size"]["width"] >= MIN_TERMINAL_WIDTH
              # Create options table
            table = Table(show_header=False, box=box_style, show_edge=False)
            table.add_column("Key", style=main_color, justify="right", width=6 if is_wide else 3)
            table.add_column("Icon", style="bright_white", justify="center", width=4 if is_wide else 2)
            table.add_column("Option", style="white", max_width=80 if is_wide else 40)
            
            # Add menu options with icons
            table.add_row(
                f"[bold {main_color}][1][/bold {main_color}]", 
                "📁", 
                f"[bold green]Manage Existing Albums[/bold green]\n  Play, burn or delete your downloaded albums"
            )
            table.add_row(
                f"[bold {main_color}][2][/bold {main_color}]", 
                "🔍", 
                f"[bold {accent_color}]Search & Download[/bold {accent_color}]\n  Find and download new music from Spotify"
            )
            table.add_row(
                f"[bold {main_color}][3][/bold {main_color}]", 
                "🎬", 
                f"[bold magenta]Video Management[/bold magenta]\n  Download and manage videos"
            )
            table.add_row(
                f"[bold {main_color}][4][/bold {main_color}]", 
                "⚙️", 
                f"[bold yellow]Settings[/bold yellow]\n  Configure download and burning options"
            )
            table.add_row(                f"[bold {main_color}][5][/bold {main_color}]", 
                "ℹ️", 
                f"[bold blue]About / Help[/bold blue]"
            )            # Display the menu table
            console.print(table)
            
            console.print()
            
            # Make prompt match the theme
            prompt_style = f"bold {main_color}" if main_color != "white" else "bold cyan"
            choice = Prompt.ask(
                f"[{prompt_style}]Select an option[/{prompt_style}]",
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
                # Ensure cursor is visible when exiting
                self.show_cursor()
                return

    def show_existing_albums(self):
        """Display existing albums and provide options to manage them."""
        # Show scanning animation
        with Progress(
            SpinnerColumn(),
            TextColumn("[bold cyan]Scanning your music library...[/bold cyan]"),
            console=console,
            transient=True
        ) as progress:
            progress.add_task("scan", total=None)
            albums = self.scan_existing_albums()
        
        # Get theme colors for consistent styling
        main_color = app_state["theme"]["main"] if "theme" in app_state else "cyan"
        accent_color = app_state["theme"]["accent"] if "theme" in app_state else "green"
        border_style = app_state["theme"]["border"] if "theme" in app_state else "cyan"
        box_style = app_state["theme"]["box"] if "theme" in app_state else box.ROUNDED
        
        if not albums:
            console.print(Panel(
                "[yellow]No albums found in your download directory.[/yellow]",
                title="Music Library",
                border_style=border_style,
                box=box_style
            ))
            self.wait_for_keypress("Press any key to return to the main menu...")
            return False
            
        while True:
            self.clear_screen()
            self.show_header()
            
            # Create a table to display the albums
            table = Table(
                title=f"Your Music Library - {len(albums)} Albums", 
                show_header=True, 
                header_style=f"bold {main_color}", 
                box=box_style,
                border_style=border_style,
                title_style=f"bold {border_style}"
            )
            
            table.add_column("#", style="dim", width=4)
            table.add_column("Album", style=main_color)
            table.add_column("Artist", style=accent_color)
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
            
            # Get theme colors for options menu
            main_color = app_state["theme"]["main"] if "theme" in app_state else "cyan"
            accent_color = app_state["theme"]["accent"] if "theme" in app_state else "green"
            border_style = app_state["theme"]["border"] if "theme" in app_state else "cyan"
            
            # Create an options menu with icons
            options_table = Table(show_header=False, box=box.SIMPLE, show_edge=False)
            options_table.add_column("Key", style=main_color, justify="right", width=3)
            options_table.add_column("Icon", style="bright_white", justify="center", width=3)
            options_table.add_column("Option", style="white")
            
            options_table.add_row("[1]", "🎵", "[cyan]Play album[/cyan] (opens in default player)")
            options_table.add_row("[2]", "💿", "[green]Burn album to CD/DVD[/green]")
            options_table.add_row("[3]", "📀", "[blue]Burn multiple albums to CD/DVD[/blue]")
            options_table.add_row("[4]", "🗑️", "[red]Delete album[/red]")
            options_table.add_row("[5]", "🔙", "[yellow]Return to main menu[/yellow]")
            
            # Show options in a panel
            console.print(Panel(
                options_table,
                title="Album Management Options",
                border_style=border_style,
                padding=(1, 2)
            ))
            
            # Add a tip for better UX
            console.print("[dim]Tip: Select an album by number, then choose what to do with it.[/dim]\n")
            
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
        """Wait for any key to be pressed with optional animation."""
        # Show cursor while waiting for input
        self.show_cursor()
        
        if not message:
            # If no message is provided, wait silently
            if sys.platform == "win32" or sys.platform == "win64":
                msvcrt.getch()  # Windows
            else:
                input()  # Unix-based systems (Enter key)
            # Hide cursor again after input
            self.hide_cursor()
            return
            
        # Get theme color for consistent styling
        accent_color = app_state["theme"]["accent"] if "theme" in app_state else "green"
        
        # Use animated spinner for a more modern look
        with Progress(
            SpinnerColumn(spinner_name="dots" if self.theme != "neon" else "dots12"),
            TextColumn(f"[{accent_color}]{message}[/{accent_color}]"),
            console=console,
            transient=True
        ) as progress:
            task = progress.add_task("waiting", total=None)
            
            # Wait for keypress
            if sys.platform == "win32" or sys.platform == "win64":
                msvcrt.getch()  # Windows
            else:
                input()  # Unix-based systems (Enter key)
            
            # Hide cursor again after input
            self.hide_cursor()

    def prompt_for_album_number(self, albums):
        """Prompt user to select an album number."""
        while True:
            try:
                # Show cursor for input
                self.show_cursor()
                album_num = int(Prompt.ask(f"Enter album number [1-{len(albums)}]"))
                # Hide cursor after input
                self.hide_cursor()
                
                if 1 <= album_num <= len(albums):
                    return album_num
                else:
                    console.print(f"[red]Please enter a number between 1 and {len(albums)}[/red]")
            except ValueError:
                console.print("[red]Please enter a valid number[/red]")
                # Ensure cursor is hidden after error
                self.hide_cursor()

    def prompt_for_album_numbers(self, albums):
        """Prompt user to select one or multiple album numbers."""
        while True:
            # Show cursor for input
            self.show_cursor()
            input_str = Prompt.ask(f"Enter album numbers separated by commas [1-{len(albums)}]")
            # Hide cursor after input
            self.hide_cursor()
            
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
                    console.print(f"[green]Downloaded: {url}[green]")
                    downloaded.append(url)
                else:
                    console.print(f"[red]Error downloading {url}: {process.stderr or process.stdout}[red]")
            except Exception as e:
                console.print(f"[red]Exception downloading {url}: {e}[red]")
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
            console.print(f"[red]Error playing video: {e}[red]")

    def show_video_menu(self):
        """Sub-menu for downloading and managing videos."""
        while True:
            self.clear_screen()
            console.print("\n[bold magenta]Video Management Menu[bold magenta]")
            console.print("[1] [cyan]Download videos from URLs[cyan]")
            console.print("[2] [green]Manage existing videos[green]")
            console.print("[3] [yellow]Return to main menu[yellow]")
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
                    console.print("[yellow]No videos match your criteria.[yellow]")
                    self.wait_for_keypress()
                    continue
                while True:
                    self.clear_screen()
                    console.print(f"\n[bold green]Found {len(videos)} videos:[/bold green]")
                    table = Table(title="Your Video Library", show_header=True, header_style="bold blue", box=box.ROUNDED)
                    table.add_column("#", style="dim", width=4)
                    table.add_column("Video", style="cyan")
                    table.add_column("Size (MB)", justify="right")
                    for i, vid in enumerate(videos):
                        table.add_row(str(i+1), vid['name'], str(vid['size']))
                    console.print(table)
                    console.print("\n[bold]Video Management Options:[/bold]")
                    console.print("[1] [cyan]Play video(s)[cyan]")
                    console.print("[2] [green]Burn selected videos[green]")
                    console.print("[3] [red]Delete selected videos[red]")
                    console.print("[4] [yellow]Return to video menu[yellow]")
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
                                console.print(f"[green]Deleted: {videos[n-1]['name']}[green]")
                            except Exception as e:
                                logger.error(f"Error deleting video {videos[n-1]['path']}: {e}")
                                console.print(f"[red]Error deleting {videos[n-1]['name']}: {e}[red]")
                        videos = self.scan_existing_videos()
                        if not videos:
                            console.print("[yellow]No more videos.[yellow]")
                            console.print("Press any key to continue...")
                            break
                    elif sub == "4":
                        break
            elif choice == "3":
                break

    def manage_settings(self):
        """Manage application settings including CDBurnerXP options."""
        while True:
            self.clear_screen()
            self.show_header()
            
            # Get themed box and styling
            box_style = app_state["theme"]["box"] if "theme" in app_state else box.ROUNDED
            border_style = app_state["theme"]["border"] if "theme" in app_state else "cyan"
            
            # Create a more visually appealing settings table
            table = Table(
                title="Application Settings",
                show_header=True,
                box=box_style,
                border_style=border_style,
                title_style=f"bold {border_style}",
                padding=(0, 1)
            )
            
            table.add_column("#", style="cyan", justify="right", width=3)
            table.add_column("Setting", style="white", width=22)
            table.add_column("Current Value", style="green")
            
            # Categorize settings with section headers
            table.add_row("", "[bold]Interface[/bold]", "", style="dim")
            table.add_row("10", "Theme", self.theme.capitalize())
            
            table.add_row("", "[bold]Storage[/bold]", "", style="dim")
            table.add_row("1", "Download Directory", self.download_dir)
            table.add_row("2", "Optical Drive", self.dvd_drive or "Auto-detect")
            
            table.add_row("", "[bold]Audio Settings[/bold]", "", style="dim")
            table.add_row("3", "Audio Format", self.audio_format)
            table.add_row("4", "Audio Bitrate", self.bitrate)
            table.add_row("5", "Maximum Threads", str(self.max_threads))
            
            table.add_row("", "[bold]Burning Configuration[/bold]", "", style="dim")
            table.add_row("6", "CDBurnerXP Path", self.burn_settings.get("cdburnerxp_path"))
            table.add_row("7", "Burning Speed", str(self.burn_settings.get("speed") or "Auto"))
            table.add_row("8", "Verify After Burning", "Yes" if self.burn_settings.get("verify") else "No")
            table.add_row("9", "Eject After Burning", "Yes" if self.burn_settings.get("eject") else "No")
            
            console.print(table)
            console.print()
            
            # Add a help text
            console.print("[dim]Choose a setting number to modify, or [B] to go back[/dim]")
            console.print()
            
            choice = Prompt.ask(
                "Select setting to change ([bold]B[/bold] to go back)",
                choices=[str(i) for i in range(1,11)] + ["B","b"], 
                default="B"
            ).upper()
            if choice == "B":
                self.save_config()
                break
            elif choice == "1":
                self.download_dir = Prompt.ask("Enter download directory", default=self.download_dir)
            elif choice == "2":
                self.dvd_drive = Prompt.ask("Enter drive letter (e.g. E:)", default=self.dvd_drive)
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
                # Display theme selection as a table with preview
                self.clear_screen()
                self.show_header()
                
                # Create theme preview table
                theme_table = Table(show_header=True, box=box.ROUNDED, title="Theme Selection")
                theme_table.add_column("#", style="cyan", justify="center")
                theme_table.add_column("Theme", style="white")
                theme_table.add_column("Description", style="white")
                
                # Add theme options with descriptions
                theme_table.add_row("1", "[cyan bold]Default[/cyan bold]", "Classic cyan theme with rounded boxes")
                theme_table.add_row("2", "[blue bold]Dark[/blue bold]", "Deep blue theme with heavy borders")
                theme_table.add_row("3", "[magenta bold]Light[/magenta bold]", "Magenta theme with square boxes")
                theme_table.add_row("4", "[bright_blue bold]Modern[/bright_blue bold]", "Bright blue with clean minimalist design")
                theme_table.add_row("5", "[hot_pink bold]Neon[/hot_pink bold]", "Vibrant pink and cyan with double borders")
                theme_table.add_row("6", "[green bold]Spotify[/green bold]", "Green theme inspired by Spotify's brand")
                
                console.print(theme_table)
                console.print()
                
                # Let user select a theme
                theme_choice = Prompt.ask(
                    "Select a theme",
                    choices=["1", "2", "3", "4", "5", "6", "B", "b"],
                    default="B"
                ).upper()
                
                if theme_choice == "1":
                    self.theme = "default"
                    self.apply_theme("default")
                elif theme_choice == "2":
                    self.theme = "dark"
                    self.apply_theme("dark")
                elif theme_choice == "3":
                    self.theme = "light"
                    self.apply_theme("light")
                elif theme_choice == "4":
                    self.theme = "modern"
                    self.apply_theme("modern")
                elif theme_choice == "5":
                    self.theme = "neon"
                    self.apply_theme("neon")
                elif theme_choice == "6":
                    self.theme = "spotify"
                    self.apply_theme("spotify")
                
                # If not B (back), save the theme change
                if theme_choice != "B":
                    # Save the configuration with the new theme
                    self.save_config()
                    console.print(f"[green]Theme changed to {self.theme}[/green]")

    def about_app(self):
        """Display information about the application."""
        self.clear_screen()
        self.show_header()
        
        # Get theme-specific colors
        main_color = app_state["theme"]["main"] if "theme" in app_state else "cyan"
        accent_color = app_state["theme"]["accent"] if "theme" in app_state else "green"
        border_style = app_state["theme"]["border"] if "theme" in app_state else "cyan"
        box_style = app_state["theme"]["box"] if "theme" in app_state else box.ROUNDED
        
        # Create a layout for better organization
        layout = Layout()
        
        # Split the layout into sections
        layout.split_column(
            Layout(name="title"),
            Layout(name="body"),
            Layout(name="footer")
        )
        
        # Split the body into two columns
        layout["body"].split_row(
            Layout(name="features", ratio=2),
            Layout(name="info", ratio=1)
        )
        
        # Title section with app name and version
        title_text = f"[bold]Spotify Album Downloader and Burner v{VERSION}[/bold]"
        layout["title"].update(Panel(
            title_text,
            title="About",
            title_align="center",
            border_style=border_style,
            box=box_style,
            padding=(1, 2)
        ))
        
        # Feature highlights
        features_text = (
            f"[bold {main_color}]🌟 Key Features:[/bold {main_color}]\n\n"
            "- 🔍 [bold]Powerful Search:[/bold] Find tracks and albums on Spotify with ease\n\n"
            "- ⚡ [bold]Multithreaded Downloads:[/bold] Download multiple tracks simultaneously\n\n"
            "- 💿 [bold]Direct CD/DVD Burning:[/bold] Burn your music to disc\n\n"
            "- 🎵 [bold]Multiple Audio Formats:[/bold] Choose from MP3, FLAC, OGG, and more\n\n"
            "- 📊 [bold]Library Management:[/bold] Organize, play, and manage your downloaded music\n\n"
            "- 📹 [bold]Video Support:[/bold] Download and manage videos from URLs\n\n"
            "- ⚙️ [bold]Advanced Settings:[/bold] Customize download location, audio quality, and more"
        )
        layout["features"].update(Panel(
            features_text,
            title=f"[{accent_color}]Features[/{accent_color}]",
            border_style=border_style,
            box=box_style,
            padding=(1, 2)
        ))
        
        # Info section (Requirements, Credits, License)
        info_section = Table.grid(padding=1)
        info_section.add_column()
        
        # Requirements subsection
        requirements = Table.grid(padding=0)
        requirements.add_column(style="bold")
        requirements.add_column()
        requirements.add_row(f"[{main_color}]📋[/{main_color}]", f"[bold {main_color}]Requirements[/bold {main_color}]")
        requirements.add_row("", "• Python 3.6+")
        requirements.add_row("", "• Windows OS for native CD/DVD burning")
        requirements.add_row("", "• Spotify Developer API credentials")
        
        # Credits subsection
        credits = Table.grid(padding=0)
        credits.add_column(style="bold")
        credits.add_column()
        credits.add_row(f"[{main_color}]🙏[/{main_color}]", f"[bold {main_color}]Credits[/bold {main_color}]")
        credits.add_row("", "• Spotipy: Lightweight Python client")
        credits.add_row("", "• SpotDL: Download music from Spotify")
        credits.add_row("", "• Rich: Beautiful terminal formatting")
        credits.add_row("", "• Colorama: Cross-platform terminal output")
        
        # License subsection
        license_info = Table.grid(padding=0)
        license_info.add_column(style="bold")
        license_info.add_column()
        license_info.add_row(f"[{main_color}]📄[/{main_color}]", f"[bold {main_color}]License[/bold {main_color}]")
        license_info.add_row("", "This project is licensed under the MIT License.")
        
        # Add all subsections to info section
        info_section.add_row(requirements)
        info_section.add_row(credits)
        info_section.add_row(license_info)
        
        layout["info"].update(Panel(
            info_section,
            title=f"[{accent_color}]Information[/{accent_color}]",
            border_style=border_style,
            box=box_style
        ))
        
        # Footer with press any key message
        layout["footer"].update(Panel(
            "[dim italic]Press any key to return to the main menu...[/dim italic]",
            border_style=border_style,
            box=box_style
        ))
        
        # Print the layout
        console.print(layout)
        
        # Wait for key press to return to main menu
        self.wait_for_keypress("")

    def run(self, query=None, search_type=None):
        """Run the application with optional command line query.
        
        Args:
            query: Optional search query
            search_type: Type of search ('song', 'album', 'playlist', or None for all)
        
        Returns:
            int: Exit code (0 for success, 1 for error)
        """
        try:
            # Check terminal dimensions first
            if not check_terminal_size():
                self.show_cursor()  # Ensure cursor is visible
                width, height = app_state["terminal_size"]["width"], app_state["terminal_size"]["height"]
                console.print(f"[bold red]Error: Terminal size too small ({width}x{height}).[/bold red]")
                console.print(f"[yellow]Minimum required terminal size: {MIN_TERMINAL_WIDTH}x{MIN_TERMINAL_HEIGHT}[/yellow]")
                console.print("[yellow]Please resize your terminal window and try again.[/yellow]")
                return 1
                
            # Show the app header
            self.show_header()
            
            # Check for interrupted downloads at startup
            self.check_for_interrupted_downloads()
            
            # Initialize Spotify API
            if not self.initialize_spotify():
                return 1
                
            if query:
                # Direct mode with query - go straight to search
                selection = self.search_music(query, search_type)
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
                    console.print("[red]Download failed or was incomplete! Check the error messages above for details.[/red]")
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
                # Ensure cursor is visible when app ends
                self.show_cursor()
                return 0
                
        except KeyboardInterrupt:
            console.print("\n[yellow]Operation cancelled by user.[/yellow]")            # Ensure cursor is visible when app ends
            self.show_cursor()
            return 0
        except Exception as e:
            logger.error(f"Unexpected error: {e}")
            console.print(f"[bold red]An unexpected error occurred: {e}[/bold red]")
            # Ensure cursor is visible when app ends
            self.show_cursor()
            return 1
            
    def download_tracks(self, track_urls, output_dir=None, album_url=None):
        """Download tracks from Spotify URLs using spotdl.
        
        Args:
            track_urls: List of Spotify track URLs to download
            output_dir: Directory to save downloads (if None, uses default)
            album_url: Optional album URL for more efficient downloading
            
        Returns:
            bool: True if download was successful
        """
        if not track_urls:
            console.print("[yellow]No tracks to download.[/yellow]")
            return False
            
        # Create output directory if it doesn't exist
        if output_dir:
            os.makedirs(output_dir, exist_ok=True)
        else:
            output_dir = self.download_dir
            os.makedirs(output_dir, exist_ok=True)
        
        logger.info(f"Downloading {len(track_urls)} tracks to {output_dir}")
        console.print(f"\n[bold cyan]Downloading {len(track_urls)} tracks to:[/bold cyan]")
        console.print(f"[bold]{output_dir}[/bold]")
        
        # Maximum number of retry attempts
        MAX_RETRIES = 3
        
        # If we have an album URL, use that for more efficient downloading
        if album_url and len(track_urls) > 1:
            album_download_success = False
            retry_count = 0
            
            while not album_download_success and retry_count < MAX_RETRIES:
                try:
                    retry_suffix = f" (Retry {retry_count + 1}/{MAX_RETRIES})" if retry_count > 0 else ""
                    with Progress(
                        SpinnerColumn(),
                        TextColumn("[progress.description]{task.description}"),
                        BarColumn(),
                        TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
                        TimeRemainingColumn()
                    ) as progress:
                        task = progress.add_task(f"[cyan]Downloading album...{retry_suffix}", total=100)
                        
                        # Build spotdl command with correct python interpreter
                        cmd = [
                            str(PYTHON_PATH),
                            "-m",
                            "spotdl",
                            "--output", output_dir,
                            "--format", self.audio_format,
                            "--bitrate", self.bitrate,
                            album_url
                        ]
                        print(cmd)
                        
                        # Start the process with Popen to allow monitoring
                        process = subprocess.Popen(
                            cmd,
                            stdout=subprocess.PIPE,
                            stderr=subprocess.STDOUT,
                            text=True,
                            bufsize=1,
                            universal_newlines=True
                        )
                        
                        # Record all output for error reporting
                        output_lines = []
                        
                        # Read output line by line and update progress
                        while True:
                            line = process.stdout.readline()
                            if not line and process.poll() is not None:
                                break
                            if line:
                                line = line.strip()
                                output_lines.append(line)
                                logger.debug(line)
                                
                                # Estimate progress based on output
                                if "Downloaded" in line and "%" in line:
                                    try:
                                        # Try to parse progress from spotdl output
                                        percent_str = line.split("%")[0].split(" ")[-1].strip()
                                        percent = float(percent_str)
                                        progress.update(task, completed=percent)
                                    except:
                                        # If parsing fails, show indeterminate progress
                                        progress.update(task, advance=1)
                        
                        # Get return code
                        return_code = process.poll()
                        
                        # Finish progress bar
                        progress.update(task, completed=100)
                        
                        if return_code == 0:
                            console.print("[green]Album download completed successfully![/green]")
                            album_download_success = True
                            return True
                        else:
                            # If this is the last retry, show detailed error and fall through to individual tracks
                            if retry_count >= MAX_RETRIES - 1:
                                console.print("[red]Error downloading album. Falling back to individual tracks...[/red]")
                                console.print("[yellow]Error details:[/yellow]")
                                error_output = "\n".join(output_lines[-10:])  # Show last 10 lines
                                console.print(f"[yellow]{error_output}[/yellow]")
                            else:
                                console.print(f"[yellow]Album download failed. Retrying ({retry_count + 1}/{MAX_RETRIES})...[/yellow]")
                                # Wait briefly before retry
                                time.sleep(2)
                                retry_count += 1
                                continue  # Try again
                            
                            # If all retries failed, fall through to individual track download
                except Exception as e:
                    logger.error(f"Error downloading album: {str(e)}")
                    console.print(f"[yellow]Error downloading album: {str(e)}[/yellow]")
                    
                    if retry_count >= MAX_RETRIES - 1:
                        console.print("[yellow]Falling back to individual track download...[/yellow]")
                    else:
                        console.print(f"[yellow]Retrying album download ({retry_count + 1}/{MAX_RETRIES})...[/yellow]")
                        time.sleep(2)  # Wait before retry
                        retry_count += 1
                        continue  # Try again
                
                # If we get here and haven't continued the loop, break out
                break
          # Download individual tracks
        try:
            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                BarColumn(),
                TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
                TimeRemainingColumn()
            ) as progress:
                # Create a task for overall progress tracking
                task = progress.add_task("[cyan]Downloading tracks...", total=len(track_urls))
                
                # Use ThreadPoolExecutor to download tracks in parallel
                download_futures = []
                for url in track_urls:
                    future = self.executor.submit(
                        self._download_single_track,
                        url,
                        output_dir,
                        progress,
                        MAX_RETRIES  # Pass max retries to single track download
                    )
                    download_futures.append(future)
                
                # Wait for all downloads to complete
                successful_downloads = 0
                failed_tracks = []
                
                for i, future in enumerate(download_futures):
                    try:
                        result = future.result()
                        if result["success"]:
                            successful_downloads += 1
                        else:
                            failed_tracks.append({
                                "url": track_urls[i],
                                "error": result["error"]
                            })
                        progress.update(task, advance=1)
                    except Exception as e:
                        logger.error(f"Error in download thread: {str(e)}")
                        failed_tracks.append({
                            "url": track_urls[i],
                            "error": str(e)
                        })
                        progress.update(task, advance=1)
                
                # Report results
                if successful_downloads == len(track_urls):
                    console.print(f"[green]All {successful_downloads} tracks downloaded successfully![/green]")
                    return True
                elif successful_downloads > 0:
                    console.print(f"[yellow]Downloaded {successful_downloads} of {len(track_urls)} tracks.[/yellow]")
                    
                    # Show failed track details
                    if failed_tracks:
                        console.print("[yellow]Failed tracks:[/yellow]")
                        for failed in failed_tracks:
                            track_id = failed["url"].split('/')[-1]
                            console.print(f"[red]Track {track_id}: {failed['error']}[/red]")
                    
                    # Return true if we got at least half of the tracks
                    return successful_downloads >= len(track_urls) / 2
                else:
                    console.print("[bold red]Failed to download any tracks.[/bold red]")
                    
                    # Show error details for failed tracks
                    if failed_tracks:
                        console.print("[yellow]Error details:[/yellow]")
                        for failed in failed_tracks:
                            track_id = failed["url"].split('/')[-1]
                            console.print(f"[red]Track {track_id}: {failed['error']}[/red]")
                    
                    return False
        except Exception as e:
            logger.error(f"Error downloading tracks: {str(e)}")
            console.print(f"[bold red]Error downloading tracks: {str(e)}[/bold red]")  # Show traceback for better debugging
            import traceback
            logger.error(f"Traceback: {traceback.format_exc()}")
            return False
            
    def _download_single_track(self, url, output_dir, progress=None, max_retries=3):
        """Download a single track using spotdl with automatic retries.
        
        Args:
            url: Spotify track URL
            output_dir: Output directory
            progress: Optional progress display object
            max_retries: Maximum number of retries (default: 3)
            
        Returns:
            dict: Dictionary with 'success' boolean and optional 'error' message
        """
        task_id = None
        track_id = url.split('/')[-1]
        if progress:
            task_id = progress.add_task(f"[green]Track: {track_id}", total=100)
        
        retry_count = 0
        while retry_count < max_retries:
            retry_suffix = f" (Retry {retry_count + 1}/{max_retries})" if retry_count > 0 else ""
            
            if task_id is not None and retry_count > 0:
                progress.update(task_id, description=f"[yellow]Track: {track_id}{retry_suffix}")
                progress.update(task_id, completed=0)  # Reset progress for retry
            
            try:
                # Build command
                cmd = [
                    "spotdl",
                    "--output", output_dir,
                    "--format", self.audio_format,
                    "--bitrate", self.bitrate,
                    url
                ]
                
                # Run the command
                process = subprocess.Popen(
                    cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    bufsize=1,
                    universal_newlines=True
                )
                
                # Collect output for error reporting
                output_lines = []
                error_lines = []
                
                # Read output and update progress
                while True:
                    line = process.stdout.readline()
                    if not line and process.poll() is not None:
                        break
                    if line:
                        line = line.strip()
                        output_lines.append(line)
                        logger.debug(line)
                        
                        # Update progress based on output
                        if "Downloaded" in line and "%" in line:
                            try:
                                percent_str = line.split("%")[0].split(" ")[-1].strip()
                                percent = float(percent_str)
                                if task_id is not None:
                                    progress.update(task_id, completed=percent)
                            except:
                                # If parsing fails, show indeterminate progress
                                if task_id is not None:
                                    progress.update(task_id, advance=2)
                        
                        # Collect error lines for reporting
                        if "ERROR" in line or "Error" in line:
                            error_lines.append(line)
                
                # Get return code
                return_code = process.poll()
                
                # Complete the progress
                if task_id is not None:
                    progress.update(task_id, completed=100)
                
                if return_code == 0:
                    # Success! Return with success status
                    if task_id is not None:
                        progress.update(task_id, description=f"[green]Track: {track_id} ✓")
                    return {"success": True}
                else:
                    # Check if this is the last retry
                    if retry_count >= max_retries - 1:
                        if task_id is not None:
                            progress.update(task_id, description=f"[red]Failed: {track_id}")
                        
                        # Compile error message from output
                        error_message = "Unknown error"
                        if error_lines:
                            error_message = error_lines[-1]  # Use the last error message
                        elif output_lines:
                            error_message = output_lines[-1]  # Use the last output line
                            
                        logger.error(f"Failed to download track {track_id} after {max_retries} retries: {error_message}")
                        return {
                            "success": False,
                            "error": error_message
                        }
                    else:
                        # Not the last retry, try again
                        logger.warning(f"Retry {retry_count + 1}/{max_retries} for track {track_id}")
                        retry_count += 1
                        time.sleep(2)  # Wait before retry
                        continue
                        
            except KeyboardInterrupt:
                logger.error(f"Download of track {track_id} interrupted by user")
                if task_id is not None:
                    progress.update(task_id, description=f"[yellow]Interrupted: {track_id}")
                return {
                    "success": False,
                    "error": "Interrupted by user"
                }
            except subprocess.SubprocessError as e:
                error_msg = str(e)
                logger.error(f"subprocess error downloading track {track_id}: {error_msg}")
                
                # Check if this is the last retry
                if retry_count >= max_retries - 1:
                    if task_id is not None:
                        progress.update(task_id, description=f"[red]Process error: {track_id}")
                    return {
                        "success": False,
                        "error": f"Process error: {error_msg}"
                    }
                else:
                    retry_count += 1
                    time.sleep(2)  # Wait before retry
                    continue
            except Exception as e:
                error_msg = str(e)
                logger.error(f"Error downloading track {track_id}: {error_msg}")
                
                # Check if this is the last retry
                if retry_count >= max_retries - 1:
                    if task_id is not None:
                        progress.update(task_id, description=f"[red]Failed: {track_id}")
                    return {
                        "success": False,
                        "error": error_msg
                    }
                else:
                    retry_count += 1
                    time.sleep(2)  # Wait before retry
                    continue

    def check_for_interrupted_downloads(self):
        """Check for interrupted downloads and offer to resume them."""
        # Check if download directory exists
        if not os.path.exists(self.download_dir):
            return False
            
        # Scan for partially downloaded files (typically with .part or .tmp extension)
        partial_files = []
        for root, dirs, files in os.walk(self.download_dir):
            for file in files:
                if file.endswith(('.part', '.tmp')):
                    partial_files.append(os.path.join(root, file))
                    
        if not partial_files:
            return False
            
        # Ask user if they want to resume downloads
        console.print(f"[yellow]Found {len(partial_files)} interrupted downloads.[/yellow]")
        
        if Confirm.ask("Would you like to attempt to resume these downloads?"):
            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                BarColumn(),
                TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
                TimeRemainingColumn()
            ) as progress:
                task = progress.add_task("[cyan]Resuming downloads...", total=len(partial_files))
                
                for file_path in partial_files:
                    try:
                        # Extract the original filename from the partial file
                        original_name = file_path.replace('.part', '').replace('.tmp', '')
                        dir_path = os.path.dirname(file_path)
                        
                        # Build spotdl command with resume flag
                        cmd = [
                            "spotdl",
                            "--output", dir_path,
                            "--format", self.audio_format,
                            "--bitrate", self.bitrate,
                            "--resume"  # Add resume flag
                        ]
                        
                        # Try to extract a Spotify URL from the filename
                        # This is a heuristic approach and may not work for all files
                        meta_file = f"{original_name}.spotdlTrackingFile"
                        if os.path.exists(meta_file):
                            try:
                                with open(meta_file, 'r') as f:
                                    content = f.read()
                                    if 'spotify.com' in content:
                                        spotify_url = re.search(r'https://open\.spotify\.com/[^\s"\']+', content)
                                        if spotify_url:
                                            cmd.append(spotify_url.group(0))
                            except:
                                pass
                        
                        if len(cmd) <= 5:  # No URL was added
                            # Just try to resume based on the file path
                            cmd.append(original_name)
                        
                        # Run the command
                        subprocess.run(cmd, capture_output=True, text=True)
                        progress.update(task, advance=1)
                        
                    except Exception as e:
                        logger.error(f"Error resuming download {file_path}: {e}")
                        
            console.print("[green]Resume attempts completed.[/green]")
        
        return True


def main():
    """Main entry point."""
    # Check terminal size first before parsing arguments
    if not check_terminal_size():
        width, height = app_state["terminal_size"]["width"], app_state["terminal_size"]["height"]
        print(f"\033[31mError: Terminal size too small ({width}x{height})\033[0m")
        print(f"\033[33mMinimum required terminal size: {MIN_TERMINAL_WIDTH}x{MIN_TERMINAL_HEIGHT}\033[0m")
        print("\033[33mPlease resize your terminal window and try again.\033[0m")
        return 1
        
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
    parser.add_argument(
        "--type", choices=["song", "album", "playlist", "all"], default="all",
        help="Type of content to search for (default: all)"
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
        # Convert 'all' to None for the search_type parameter
        search_type = None if args.type == 'all' else args.type
        return app.run(args.query, search_type)
    except KeyboardInterrupt:
        console.print("\n[yellow]Operation cancelled by user.[/yellow]")
        # Ensure cursor is visible when app ends
        app.show_cursor()
        return 0
    except Exception as e:
        logger.error(f"Unhandled error in main: {e}")
        console.print(f"[bold red]An unhandled error occurred: {e}[/bold red]")
        # Ensure cursor is visible when app ends
        app.show_cursor()
        return 1
    finally:
        # Clean up resources when application exits
        if hasattr(app, 'executor') and app.executor:
            app.executor.shutdown(wait=False)
        # Ensure cursor is always visible
        try:
            app.show_cursor()
        except:
            pass


if __name__ == "__main__":
    sys.exit(main())