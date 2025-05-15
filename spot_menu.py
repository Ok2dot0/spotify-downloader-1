#!/usr/bin/env python3
"""
Spotify Downloader Menu Demo

A simplified version of the menu display functionality
"""

import os
import sys
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt
from rich import box
from rich.style import Style

# Initialize console
console = Console()

VERSION = "2.0.0"

class SpotifyBurnerMenu:
    def __init__(self):
        self.terminal_width = console.width
    
    def center_text(self, text_or_renderable, width=None):
        """Center text or a rich renderable in the terminal."""
        width = width or self.terminal_width
        
        # For simple strings, use standard centering
        if isinstance(text_or_renderable, str):
            return text_or_renderable.center(width)
        else:
            # For other renderables, estimate their width and center with padding
            renderable_str = str(text_or_renderable)
            lines = renderable_str.split("\n")
            max_line_length = max(len(line) for line in lines) if lines else 0
            padding = max(0, (width - max_line_length) // 2)
            padded_lines = [" " * padding + line for line in lines]
            return "\n".join(padded_lines)
    
    def show_header(self):
        """Display the application header."""
        # ASCII art header
        border_color = "red"
        
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

        # Center version number and subtitle
        version_text = f"[bold white]v{VERSION}[/bold white]"
        
        console.print("")  # Add some space at the top
        console.print(self.center_text(border_top))
        console.print(self.center_text(version_text))
        console.print("")
        
        # Subtitle
        console.print(self.center_text("[bold]Search, download, and burn your favorite music![/bold]"))
        console.print("")
    
    def show_menu(self):
        """Display the main menu aligned to the left."""
        console.clear()
        self.show_header()

        # Menu options as a single string for left alignment
        menu = (
            "[white][1][/white] [green]Manage Existing Albums[/green] [dim]- Find and show your Spotify albums[/dim]\n"
            "[white][2][/white] [cyan]Search & Download[/cyan] [dim]- Find and download Spotify music[/dim]\n"
            "[white][3][/white] [magenta]Video Management[/magenta] [dim]- Download and manage videos[/dim]\n"
            "[white][4][/white] [yellow]Settings[/yellow] [dim]- Configure download options[/dim]\n"
            "[white][5][/white] [blue]About[/blue] [dim]- Information about app[/dim]\n"
            "[white][Q][/white] [red]Exit[/red] [dim]- Quit the application[/dim]"
        )
        console.print(Panel(menu, title="Main Menu", expand=False, border_style="cyan"))
        console.print("")
        console.print("[white]Select an option[/white]")

        choice = Prompt.ask("", choices=["1", "2", "3", "4", "5", "Q", "q"], default="2").upper()

        if choice == "Q":
            console.print("[green]Thank you for using Spotify Album Downloader and Burner![/green]")
            return False

        # For demo purposes, just display what was selected
        console.print(f"[cyan]You selected option {choice}[/cyan]")
        input("Press Enter to continue...")
        return True

def main():
    app = SpotifyBurnerMenu()
    running = True
    
    while running:
        running = app.show_menu()

if __name__ == "__main__":
    main()
