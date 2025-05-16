#!/usr/bin/env python3
"""
Spotify Album Downloader and Burner

This script serves as the main entry point for the Spotify Album Downloader and Burner
application. It integrates the menu system, search, download, and burning functionality.
"""

import os
import sys
import argparse
import logging
import dotenv
from rich.console import Console
from spotify_burner import SpotifyBurner, VERSION, app_state
from spot_menu import SpotifyBurnerMenu

# Initialize console for rich output
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
logger = logging.getLogger("spot_burn")

# Load environment variables from .env file
dotenv.load_dotenv()

class SpotifyBurnerApp:
    """Main application class that integrates SpotifyBurner and SpotifyBurnerMenu."""
    
    def __init__(self):
        """Initialize the application components."""
        # Create instances of both core components
        self.burner = SpotifyBurner()
        self.menu = SpotifyBurnerMenu()
        
        # Sync configuration between components
        self._sync_config()
        
    def _sync_config(self):
        """Synchronize configuration between menu and burner components."""
        # Ensure menu has access to the same configuration as burner
        self.menu.config = self.burner.config
        self.menu.terminal_width = self.burner.terminal_width
        
    def run_guided_mode(self):
        """Run the application in menu-guided mode."""
        running = True
        while running:
            # Show the main menu and handle the selection
            choice = self.menu.show_menu()
            
            if choice == "Q":  # Quit option
                running = False
                console.print("[green]Thank you for using Spotify Album Downloader and Burner![/green]")
                continue
            
            elif choice == "1":  # Manage Existing Albums
                self.burner.show_existing_albums()
            
            elif choice == "2":  # Search & Download
                self.burner.search_and_download()
            
            elif choice == "3":  # Video Management
                self.burner.show_video_menu()
            
            elif choice == "4":  # Settings
                self.burner.show_settings_menu()
            
            elif choice == "5":  # About
                self.menu.about_app()
                
            # Wait for keypress after each operation completes
            if running:
                self.burner.wait_for_keypress()
    
    def run_direct_mode(self, query, output_dir=None, drive=None, threads=None, 
                        audio_format=None, bitrate=None):
        """Run the application with direct parameters for command-line usage."""
        # Override config with command line arguments
        if output_dir:
            self.burner.download_dir = output_dir
        if drive:
            self.burner.dvd_drive = drive
        if threads and 1 <= threads <= 10:
            self.burner.max_threads = threads
            app_state["max_concurrent_downloads"] = threads
        if audio_format:
            self.burner.audio_format = audio_format
        if bitrate:
            self.burner.bitrate = bitrate
        
        # Run the app with the provided query
        return self.burner.run(query)
    
    def run(self, query=None, **kwargs):
        """Main entry point that decides between guided menu mode or direct mode."""
        try:
            if query:
                # Direct mode with query and other parameters
                return self.run_direct_mode(query, **kwargs)
            else:
                # Guided menu mode
                return self.run_guided_mode()
        finally:
            # Clean up resources when application exits
            if hasattr(self.burner, 'executor') and self.burner.executor:
                self.burner.executor.shutdown(wait=False)


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
    parser.add_argument(
        "--setup", action="store_true", help="Run the initial setup wizard"
    )
    
    args = parser.parse_args()
    
    app = SpotifyBurnerApp()
    
    # Check if setup wizard was requested
    if args.setup:
        app.burner.setup_wizard()
        return 0
    
    # Run the app with all command line arguments
    return app.run(
        query=args.query,
        output_dir=args.output,
        drive=args.drive, 
        threads=args.threads,
        audio_format=args.format,
        bitrate=args.bitrate
    )


if __name__ == "__main__":
    sys.exit(main())
