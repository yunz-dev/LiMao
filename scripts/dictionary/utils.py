import ftplib
import gzip
import os
from urllib.parse import urlparse

import requests
from dotenv import load_dotenv
from rich.console import Console
from rich.progress import (
    BarColumn,
    Progress,
    TextColumn,
    TimeRemainingColumn,
    TransferSpeedColumn,
)
from rich.status import Status

from supabase import Client, create_client

console = Console()  # Initialize Rich Console for consistent output


def download_file_ftp(ftp_url, local_filename=None):
    """
    Downloads a file from an FTP URL with a Rich progress bar.

    Args:
        ftp_url (str): The FTP URL of the file to download (e.g., "ftp://user:pass@ftp.example.com/path/to/file.txt").
        local_filename (str, optional): The name to save the file as locally.
                                        If None, extracts from the URL.

    Returns:
        str: The path to the downloaded file, or None if an error occurred.
    """
    try:
        parsed_url = urlparse(ftp_url)

        host = parsed_url.hostname
        username = parsed_url.username if parsed_url.username else "anonymous"
        password = parsed_url.password if parsed_url.password else ""
        remote_path = parsed_url.path.lstrip("/")  # Remove leading slash

        if local_filename is None:
            local_filename = os.path.basename(remote_path)

        console.log(
            f"[bold blue]Attempting to download[/bold blue] [green]{ftp_url}[/green] to [cyan]{local_filename}[/cyan]..."
        )

        with ftplib.FTP(host) as ftp:
            ftp.login(user=username, passwd=password)

            remote_dir = os.path.dirname(remote_path)
            if remote_dir:
                ftp.cwd(remote_dir)
                remote_filename_only = os.path.basename(remote_path)
            else:
                remote_filename_only = remote_path

            # Get file size for the progress bar
            try:
                filesize = ftp.size(remote_filename_only)
            except Exception:
                filesize = None  # Cannot get size, progress bar will be indeterminate

            with Progress(
                TextColumn("[bold blue]{task.description}", justify="right"),
                BarColumn(bar_width=None),
                "[progress.percentage]{task.percentage:>3.1f}%",
                "•",
                TransferSpeedColumn(),
                "•",
                TimeRemainingColumn(),
                console=console,
            ) as progress:
                download_task = progress.add_task(
                    f"[green]Downloading {remote_filename_only}", total=filesize
                )

                chunk_size = 8192
                with open(local_filename, "wb") as f:
                    # Callback function for retrbinary to update the progress bar
                    def handle_chunk(chunk):
                        f.write(chunk)
                        progress.update(download_task, advance=len(chunk))

                    ftp.retrbinary(
                        f"RETR {remote_filename_only}", handle_chunk, chunk_size
                    )

            console.log(
                f"[bold green]Successfully downloaded[/bold green] [cyan]{local_filename}[/cyan]"
            )
            return local_filename

    except ftplib.all_errors as e:
        console.log(
            f"[bold red]Error downloading from FTP:[/bold red] {e}", style="red"
        )
        return None
    except Exception as e:
        console.log(
            f"[bold red]An unexpected error occurred:[/bold red] {e}", style="red"
        )
        return None


def download_file(url, local_filename=None):
    """
    Downloads a file from a given URL with a Rich progress bar.

    Args:
        url (str): The URL of the file to download.
        local_filename (str, optional): The name to save the file as locally.
                                        If None, extracts from the URL.

    Returns:
        str: The path to the downloaded file, or None if an error occurred.
    """
    if local_filename is None:
        local_filename = url.split("/")[-1]

    console.log(
        f"[bold blue]Attempting to download[/bold blue] [green]{url}[/green] to [cyan]{local_filename}[/cyan]..."
    )

    try:
        with requests.get(url, stream=True) as r:
            r.raise_for_status()  # Raise an HTTPError for bad responses (4xx or 5xx)

            total_size = int(r.headers.get("content-length", 0))

            with Progress(
                TextColumn("[bold blue]{task.description}", justify="right"),
                BarColumn(bar_width=None),
                "[progress.percentage]{task.percentage:>3.1f}%",
                "•",
                TransferSpeedColumn(),
                "•",
                TimeRemainingColumn(),
                console=console,
            ) as progress:
                download_task = progress.add_task(
                    f"[green]Downloading {local_filename}", total=total_size
                )
                with open(local_filename, "wb") as f:
                    for chunk in r.iter_content(chunk_size=8192):
                        f.write(chunk)
                        progress.update(download_task, advance=len(chunk))

        console.log(
            f"[bold green]Successfully downloaded[/bold green] [cyan]{local_filename}[/cyan]"
        )
        return local_filename
    except requests.exceptions.RequestException as e:
        console.log(
            f"[bold red]Error downloading the file:[/bold red] {e}", style="red"
        )
        return None
    except Exception as e:
        console.log(
            f"[bold red]An unexpected error occurred:[/bold red] {e}", style="red"
        )
        return None


def unzip_gz_file(gz_filepath, output_dir="."):
    """
    Unzips a .gz file into the specified directory with a Rich spinner.

    Args:
        gz_filepath (str): The path to the .gz file to unzip.
        output_dir (str, optional): The directory to extract the file into.
                                    Defaults to the current directory.

    Returns:
        str: The path to the unzipped file, or None if an error occurred.
    """
    if not os.path.exists(gz_filepath):
        console.log(
            f"[bold red]Error: .gz file not found at[/bold red] [yellow]{gz_filepath}[/yellow]",
            style="red",
        )
        return None

    if not os.path.isdir(output_dir):
        console.log(
            f"[bold blue]Output directory[/bold blue] '[yellow]{output_dir}[/yellow]' [blue]does not exist. Creating it...[/blue]"
        )
        os.makedirs(output_dir)

    output_filename = os.path.join(
        output_dir, os.path.basename(gz_filepath).replace(".gz", "")
    )

    with Status(
        f"[bold green]Unzipping[/bold green] [cyan]{gz_filepath}[/cyan] to [yellow]{output_filename}[/yellow]...",
        spinner="dots",
        console=console,
    ) as status:
        try:
            with gzip.open(gz_filepath, "rb") as f_in:
                # Read in chunks to potentially show some progress (though Rich Status is just a spinner here)
                with open(output_filename, "wb") as f_out:
                    while True:
                        chunk = f_in.read(8192)
                        if not chunk:
                            break
                        f_out.write(chunk)
            status.update(
                f"[bold green]Successfully unzipped[/bold green] [cyan]{output_filename}[/cyan]",
                spinner="aesthetic",
                spinner_style="green",
            )
            return output_filename
        except Exception as e:
            status.update(
                f"[bold red]Error unzipping the file:[/bold red] {e}",
                spinner="arrow",
                spinner_style="red",
            )
            console.log(
                f"[bold red]Error unzipping the file:[/bold red] {e}", style="red"
            )
            return None


def setup_supabase_client() -> Client:
    """
    Initializes and returns the Supabase client using environment variables with a Rich spinner.
    """
    with Status(
        "[bold magenta]Setting up Supabase client...", spinner="point", console=console
    ) as status:
        load_dotenv()
        supabase_url = os.environ.get("SUPABASE_URL")
        supabase_key = os.environ.get("SUPABASE_KEY")

        if not supabase_url or not supabase_key:
            status.update(
                "[bold red]SUPABASE_URL and SUPABASE_KEY must be set in your environment.[/bold red]",
                spinner="square",
                spinner_style="red",
            )
            console.log(
                "[bold red]SUPABASE_URL and SUPABASE_KEY must be set in your environment.[/bold red]",
                style="red",
            )
            raise ValueError(
                "SUPABASE_URL and SUPABASE_KEY must be set in your environment."
            )
        status.update(
            "[bold green]Supabase client setup complete![/bold green]",
            spinner="line",
            spinner_style="green",
        )
        return create_client(supabase_url, supabase_key)
