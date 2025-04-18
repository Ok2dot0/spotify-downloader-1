from rich.console import Console
from rich.table import Table
from rich.prompt import Prompt
from rich.progress import Progress
from rich.live import Live
from rich.layout import Layout
from rich.panel import Panel
from rich.text import Text
from rich import box
import os
from src.spotify_api import get_user_playlists, get_user_personalized_mixes
from src.playlist_manager import fetch_and_organize_playlists
from src.settings import get_download_location, get_update_frequency

console = Console()

def display_playlists(playlists):
    table = Table(title="Spotify Playlists", box=box.ROUNDED)
    table.add_column("Index", justify="center", style="cyan", no_wrap=True)
    table.add_column("Playlist Name", style="magenta")

    for idx, playlist in enumerate(playlists['items']):
        table.add_row(str(idx), playlist['name'])

    console.print(table)

def display_personalized_mixes(mixes):
    table = Table(title="Personalized Mixes", box=box.ROUNDED)
    table.add_column("Index", justify="center", style="cyan", no_wrap=True)
    table.add_column("Mix Name", style="magenta")

    for idx, mix in enumerate(mixes['items']):
        table.add_row(str(idx), mix['name'])

    console.print(table)

def select_playlists(playlists):
    selected_indices = Prompt.ask("Enter the indices of the playlists to download (comma-separated)", default="")
    selected_indices = [int(idx.strip()) for idx in selected_indices.split(",") if idx.strip().isdigit()]
    selected_playlists = [playlists['items'][idx] for idx in selected_indices if idx < len(playlists['items'])]
    return selected_playlists

def select_mixes(mixes):
    selected_indices = Prompt.ask("Enter the indices of the mixes to download (comma-separated)", default="")
    selected_indices = [int(idx.strip()) for idx in selected_indices.split(",") if idx.strip().isdigit()]
    selected_mixes = [mixes['items'][idx] for idx in selected_indices if idx < len(mixes['items'])]
    return selected_mixes

def update_tracks(selected_playlists, selected_mixes):
    console.print("[yellow]Note: Processing currently includes ALL playlists and top tracks, not just selected ones.[/]")
    with Progress(console=console) as progress:
        task = progress.add_task("[cyan]Processing tracks...", total=None)
        try:
            fetch_and_organize_playlists()
            progress.update(task, completed=100)
        except Exception as e:
            console.print(f"[bold red]An error occurred during track processing: {e}[/]")
            progress.stop()

def main():
    console.print(Panel(Text("Welcome to Spotify Playlist Downloader", justify="center"), box=box.ROUNDED))

    playlists = None
    mixes = None

    try:
        console.print("Fetching playlists from Spotify...")
        playlists = get_user_playlists()
        console.print("Fetching personalized mixes (top tracks) from Spotify...")
        mixes = get_user_personalized_mixes()
    except Exception as e:
        console.print(f"[bold red]Error fetching initial data from Spotify: {e}[/]")
        console.print("[yellow]Please check your connection and Spotify credentials/permissions.[/]")
        return

    if playlists and playlists.get('items'):
        display_playlists(playlists)
    else:
        console.print("[yellow]No playlists found or error fetching playlists.[/]")

    if mixes and mixes.get('items'):
        display_personalized_mixes(mixes)
    else:
        console.print("[yellow]No personalized mixes (top tracks) found or error fetching them.[/]")

    selected_playlists = []
    if playlists and playlists.get('items'):
        selected_playlists = select_playlists(playlists)

    selected_mixes = []
    if mixes and mixes.get('items'):
        selected_mixes = select_mixes(mixes)

    download_location = get_download_location()
    update_frequency = get_update_frequency()

    console.print(f"Download location: [cyan]{download_location}[/]")
    console.print(f"Update frequency: [cyan]{update_frequency}[/]")

    proceed = Prompt.ask("Proceed with downloading/updating tracks?", choices=["yes", "no"], default="yes")

    if proceed.lower() == "yes":
        console.print("[cyan]Starting track update process...[/]")
        update_tracks(selected_playlists, selected_mixes)
        console.print("[green]Track update process finished.[/]")
    else:
        console.print("Operation cancelled by user.")

if __name__ == "__main__":
    main()
