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
from src.playlist_manager import fetch_and_organize_playlists, organize_tracks
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

def update_tracks():
    with Progress() as progress:
        task = progress.add_task("[cyan]Updating tracks...", total=100)
        while not progress.finished:
            progress.update(task, advance=0.1)
            fetch_and_organize_playlists()
            organize_tracks()
            progress.update(task, advance=100)

def main():
    console.print(Panel(Text("Welcome to Spotify Playlist Downloader", justify="center"), box=box.ROUNDED))

    playlists = fetch_and_organize_playlists()
    mixes = fetch_and_organize_playlists()

    display_playlists(playlists)
    display_personalized_mixes(mixes)

    selected_playlists = select_playlists(playlists)
    selected_mixes = select_mixes(mixes)

    download_location = get_download_location()
    update_frequency = get_update_frequency()

    console.print(f"Download location: {download_location}")
    console.print(f"Update frequency: {update_frequency}")

    with Live(console=console, refresh_per_second=4):
        update_tracks()

if __name__ == "__main__":
    main()
