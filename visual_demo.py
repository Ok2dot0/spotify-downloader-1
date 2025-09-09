#!/usr/bin/env python3
"""Visual demo of the AI Music Discovery UI."""

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich import box

console = Console(width=100)

def show_main_menu_demo():
    """Show how the main menu looks with AI option."""
    console.clear()
    
    # Header
    console.print(Panel(
        "[bold cyan]🎵 SPOTIFY DOWNLOADER & BURNER v2.0.0 🎵[/bold cyan]",
        style="cyan",
        box=box.DOUBLE
    ))
    
    # Main menu with AI option
    table = Table(show_header=False, box=box.ROUNDED, show_edge=False)
    table.add_column("Key", style="cyan", justify="right", width=6)
    table.add_column("Icon", style="bright_white", justify="center", width=4)
    table.add_column("Option", style="white", max_width=80)
    
    table.add_row("[bold cyan][1][/bold cyan]", "📁", "[bold green]Manage Existing Albums[/bold green]\n  Play, burn or delete your downloaded albums")
    table.add_row("[bold cyan][2][/bold cyan]", "🔍", "[bold green]Search & Download[/bold green]\n  Find and download new music from Spotify")
    table.add_row("[bold cyan][3][/bold cyan]", "🎬", "[bold magenta]Video Management[/bold magenta]\n  Download and manage videos")
    table.add_row("[bold cyan][4][/bold cyan]", "🤖", "[bold bright_blue]AI Music Discovery[/bold bright_blue]\n  Use AI to analyze images and find music")
    table.add_row("[bold cyan][5][/bold cyan]", "⚙️", "[bold yellow]Settings[/bold yellow]\n  Configure download and burning options")
    table.add_row("[bold cyan][6][/bold cyan]", "ℹ️", "[bold blue]About / Help[/bold blue]")
    
    console.print(table)
    console.print("\n[bold cyan]Select an option (NEW: AI Music Discovery available!)[/bold cyan]")

def show_ai_menu_demo():
    """Show the AI Music Discovery submenu."""
    console.clear()
    
    # Header  
    console.print(Panel(
        "[bold cyan]🎵 SPOTIFY DOWNLOADER & BURNER v2.0.0 🎵[/bold cyan]",
        style="cyan", 
        box=box.DOUBLE
    ))
    
    # AI Status
    console.print(Panel(
        "Provider: ollama\nModel: llama3.2-vision:latest\nVision: ✅",
        title="🤖 AI Music Discovery",
        border_style="bright_blue",
        box=box.ROUNDED
    ))
    
    # AI menu options
    table = Table(show_header=False, box=box.ROUNDED, show_edge=False)
    table.add_column("Key", style="cyan", justify="right", width=6)
    table.add_column("Icon", style="bright_white", justify="center", width=4)  
    table.add_column("Option", style="white", max_width=80)
    
    table.add_row("[bold cyan][1][/bold cyan]", "🖼️", "[bold green]Analyze Image for Music[/bold green]\n  Upload an image to discover related music")
    table.add_row("[bold cyan][2][/bold cyan]", "📝", "[bold green]Analyze Text for Music[/bold green]\n  Enter text to find related music") 
    table.add_row("[bold cyan][3][/bold cyan]", "🔍", "[bold yellow]AI Search History[/bold yellow]\n  View previous AI-powered searches")
    table.add_row("[bold cyan][4][/bold cyan]", "⚙️", "[bold magenta]AI Settings[/bold magenta]\n  Configure AI provider and model")
    
    console.print(table)
    console.print("\n[bold cyan]Select an option (or 'B' to go back)[/bold cyan]")

def show_analysis_results_demo():
    """Show AI analysis results."""
    console.clear()
    
    console.print(Panel(
        "[bold cyan]🎵 SPOTIFY DOWNLOADER & BURNER v2.0.0 🎵[/bold cyan]",
        style="cyan",
        box=box.DOUBLE
    ))
    
    # Analysis results
    result_text = """[bold green]🎤 Artists:[/bold green] Taylor Swift
[bold blue]💿 Albums:[/bold blue] Folklore
[bold yellow]🎵 Songs:[/bold yellow] Cardigan, The 1, Exile
[bold magenta]🎭 Genre:[/bold magenta] indie folk
[bold cyan]🔑 Keywords:[/bold cyan] folklore, taylor swift, indie, acoustic

[bold white]🎯 Confidence:[/bold white] 95%

[dim italic]Detected album cover with clear artist name and album title. High confidence match for Taylor Swift's Folklore album.[/dim italic]

[dim]AI Provider: ollama | Model: llama3.2-vision:latest[/dim]"""

    console.print(Panel(
        result_text,
        title="🤖 AI Analysis Results", 
        border_style="green",
        box=box.ROUNDED
    ))
    
    console.print("\n[bold green]🔍 Generated 4 search queries based on analysis:[/bold green]")
    console.print("  1. [cyan]artist:\"Taylor Swift\"[/cyan]")
    console.print("  2. [cyan]album:\"Folklore\"[/cyan]") 
    console.print("  3. [cyan]track:\"Cardigan\"[/cyan]")
    console.print("  4. [cyan]genre:\"indie folk\"[/cyan]")
    
    console.print("\n[bold]Would you like to search for music using these AI-generated queries? (y/n)[/bold]")

if __name__ == "__main__":
    console.print("[bold]🎮 AI Music Discovery UI Demo[/bold]")
    console.print("=" * 50)
    
    input("\nPress Enter to see Main Menu with AI option...")
    show_main_menu_demo()
    
    input("\nPress Enter to see AI Music Discovery menu...")
    show_ai_menu_demo()
    
    input("\nPress Enter to see AI Analysis Results...")
    show_analysis_results_demo()
    
    console.print("\n[bold green]✨ Demo complete! The AI Music Discovery feature seamlessly integrates with the existing interface.[/bold green]")