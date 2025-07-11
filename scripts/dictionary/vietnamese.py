import os
import re
from typing import List, Optional

from config import VietnameseScraper
from pydantic import BaseModel, ValidationError
from rich.console import Console
from rich.progress import (
    BarColumn,
    Progress,
    TextColumn,
    TimeElapsedColumn,
    TimeRemainingColumn,
)
from rich.prompt import Confirm

# No need to import Status if we're not using it transiently for each upsert
# from rich.status import Status
from utils import download_file, setup_supabase_client, unzip_gz_file, log_config_loaded

from supabase import Client

# Initialize the Rich Console for all output
console = Console()


def main():
    """
    Main function to orchestrate the scraping, unzipping, and parsing process
    based on the configuration defined in VietnameseScraper.
    """
    console.rule("[bold blue]Starting Vietnamese Scraper[/bold blue]")

    # Unpack configuration settings
    try:
        config_values = VietnameseScraper.model_dump()
        source = config_values.get("source")
        protocol = config_values.get("protocol")
        file_type = config_values.get("file_type")
        zip_type = config_values.get("zip_type")
        file_name = config_values.get("file_name")
        interval = config_values.get("interval")
        upsert = config_values.get("upsert")

        log_config_loaded(source, protocol, file_type, zip_type, file_name, interval, upsert)
    except Exception as e:
        console.log(
            f"[bold red]Error loading configuration:[/bold red] {e}", style="red"
        )
        console.log(
            "[bold red]Exiting due to configuration error.[/bold red]", style="red"
        )
        exit(1)

    # --- Step 1: Download the file ---
    console.log(
        "\n[bold yellow]Step 1:[/bold yellow] [bold blue]Downloading file...[/bold blue]"
    )
    downloaded_path = None
    if protocol == "http":
        downloaded_path = download_file(
            source, f"{file_name}.gz" if zip_type == "gz" else file_name
        )
    elif protocol == "ftp":
        # Using the placeholder for FTP. You'd need to uncomment and ensure download_file_ftp exists in utils
        # from utils import download_file_ftp
        # downloaded_path = download_file_ftp(source, f"{file_name}.gz" if zip_type == "gz" else file_name)
        console.log(
            "[bold red]Error:[/bold red] FTP protocol support is currently commented out or not fully implemented.",
            style="red",
        )
    else:
        console.log(
            f"[bold red]Error:[/bold red] Unsupported protocol '{protocol}'. Only 'http' (and 'ftp' placeholder) are supported.",
            style="red",
        )
        console.log(
            "[bold red]Exiting due to unsupported protocol.[/bold red]", style="red"
        )
        exit(1)

    if not downloaded_path:
        console.log("[bold red]File download failed. Exiting.[/bold red]", style="red")
        exit(1)

    # --- Step 2: Unzip the file if necessary ---
    unzipped_path = downloaded_path
    if zip_type == "gz":
        console.log(
            "\n[bold yellow]Step 2:[/bold yellow] [bold blue]Unzipping file...[/bold blue]"
        )
        unzipped_path = unzip_gz_file(downloaded_path)
        if not unzipped_path:
            console.log(
                "[bold red]File unzipping failed. Exiting.[/bold red]", style="red"
            )
            os.remove(downloaded_path)  # Clean up downloaded .gz file
            exit(1)
        # Clean up the .gz file after successful unzipping
        try:
            os.remove(downloaded_path)
            console.log(
                f"[bold green]Cleaned up:[/bold green] Removed original .gz file: [dim]{downloaded_path}[/dim]"
            )
        except OSError as e:
            console.log(
                f"[bold orange3]Warning:[/bold orange3] Could not remove {downloaded_path}: {e}",
                style="orange3",
            )
    elif zip_type != "none":
        console.log(
            f"[bold red]Error:[/bold red] Unsupported zip type '{zip_type}'. Only 'gz' or 'none' are supported.",
            style="red",
        )
        console.log(
            "[bold red]Exiting due to unsupported zip type.[/bold red]", style="red"
        )
        exit(1)
    else:
        console.log(
            "\n[bold yellow]Step 2:[/bold yellow] [bold blue]No unzipping required (zip_type='none').[/bold blue]"
        )

    # --- Step 3: Parse and upsert data ---
    console.log(
        "\n[bold yellow]Step 3:[/bold yellow] [bold blue]Parsing file and upserting data...[/bold blue]"
    )
    if file_type == "txt":
        parse_Vietnamese_txt(upsert, interval, unzipped_path)
    else:
        console.log(
            f"[bold red]Error:[/bold red] Unsupported file type '{file_type}'. Only 'txt' is supported for parsing.",
            style="red",
        )
        console.log(
            "[bold red]Exiting due to unsupported file type.[/bold red]", style="red"
        )
        exit(1)

    console.rule("[bold blue]Vietnamese Scraper Finished[/bold blue]")


def parse_Vietnamese_txt(upsert: bool, interval: int, file_path: str):
    """
    Parses a Vietnamese dictionary text file, previews content, and optionally
    upserts entries into a Supabase database.

    Args:
        upsert (bool): If True, upserts parsed entries into the database.
        interval (int): Only process and (if upsert is True) upsert every `interval` lines.
        file_path (str): The path to the text file to parse.
    """
    if not os.path.exists(file_path):
        console.log(
            f"[bold red]Error:[/bold red] The file '[yellow]{file_path}[/yellow]' was not found.",
            style="red",
        )
        return

    # --- File preview and confirmation ---
    console.log(
        f"\n[bold yellow]Previewing file:[/bold yellow] [green]{file_path}[/green]"
    )
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            for i, line in enumerate(f):
                if i < 15:  # Displaying first 15 lines
                    console.log(f"[dim]Line {i+1}:[/dim] {line.strip()}", style="dim")
                else:
                    console.log("[dim]... (truncated)[/dim]", style="dim")
                    break  # Stop reading after 15 lines for preview

            # Use rich.prompt.Confirm for a better interactive experience
            response = Confirm.ask(
                "[bold yellow]Does this file look correct?[/bold yellow]"
            )
            if not response:
                console.log(
                    "[bold red]Operation cancelled by user. Exiting.[/bold red]",
                    style="red",
                )
                exit()
    except Exception as e:
        console.log(
            f"[bold red]An error occurred while reading the file for preview:[/bold red] {e}",
            style="red",
        )
        return

    # --- Main parsing and upserting loop ---
    console.log("\n[bold blue]Starting parsing and (optional) upserting...[/bold blue]")
    client = None
    if upsert:
        try:
            # setup_supabase_client already uses rich.status.Status so it's good
            client = setup_supabase_client()
        except ValueError as e:
            console.log(f"[bold red]Supabase setup failed:[/bold red] {e}", style="red")
            console.log(
                "[bold red]Cannot proceed with upserting. Exiting.[/bold red]",
                style="red",
            )
            exit(1)

    processed_count = 0
    upserted_count = 0
    skipped_count = 0
    parse_errors = 0

    try:
        with open(file_path, "r", encoding="utf-8") as f:
            # Get total lines for an accurate progress bar
            total_lines = sum(1 for _ in f)
            f.seek(0)  # Reset file pointer to the beginning

            with Progress(
                TextColumn(
                    "[bold green]{task.description}[/bold green]", justify="right"
                ),
                BarColumn(bar_width=None),
                "[progress.percentage]{task.percentage:>3.1f}%",
                "•",
                TextColumn("Processed: {task.fields[processed_count]}"),
                "•",
                TextColumn("Upserted: {task.fields[upserted_count]}"),
                "•",
                TextColumn("Skipped: {task.fields[skipped_count]}"),
                "•",
                TextColumn("Parse Errors: {task.fields[parse_errors]}"),
                "•",
                TimeElapsedColumn(),
                "•",
                TimeRemainingColumn(),
                console=console,
            ) as progress:
                parsing_task = progress.add_task(
                    "[white]Parsing entries...",
                    total=total_lines,
                    processed_count=processed_count,
                    upserted_count=upserted_count,
                    skipped_count=skipped_count,
                    parse_errors=parse_errors,
                )

                for i, line in enumerate(f):
                    progress.update(parsing_task, advance=1)
                    processed_count += 1

                    if line.strip().startswith("#") or i == 0:  # Skip comment lines
                        skipped_count += 1
                        progress.update(parsing_task, skipped_count=skipped_count)
                        continue

                    if i % interval == 0:
                        entry = parse_vietnamese_entry(line)
                        if entry:
                            if upsert and client:
                                # Removed the transient Status here.
                                # The main progress bar will handle the overall visual update.
                                response = upsert_vietnamese_entry(client, entry)
                                if response:
                                    upserted_count += 1
                                else:
                                    # Log a warning if upsert fails, but don't disrupt progress bar
                                    console.log(
                                        f"[bold red]Upsert failed for:[/bold red] [dim]'{entry.word}'[/dim]",
                                        style="red",
                                        justify="left",
                                    )
                                    parse_errors += 1  # Count failed upserts as errors for reporting
                            else:
                                # Count as skipped if not upserting or client not available
                                skipped_count += 1
                            progress.update(
                                parsing_task,
                                upserted_count=upserted_count,
                                parse_errors=parse_errors,
                            )
                        else:
                            parse_errors += 1
                            progress.update(parsing_task, parse_errors=parse_errors)
                            console.log(
                                f"[bold orange3]Warning:[/bold orange3] Failed to parse line {i+1}: '[dim]{line.strip()}[/dim]'",
                                style="orange3",
                            )
                    else:
                        skipped_count += 1  # Count as skipped if not within interval
                        progress.update(parsing_task, skipped_count=skipped_count)

                # Final update for the progress bar fields to ensure they reflect final counts
                progress.update(
                    parsing_task,
                    completed=total_lines,
                    processed_count=processed_count,
                    upserted_count=upserted_count,
                    skipped_count=skipped_count,
                    parse_errors=parse_errors,
                )

        console.log("\n[bold green]Parsing and upserting complete![/bold green]")
        console.log(
            f"  [white]Total lines processed:[/white] [cyan]{processed_count}[/cyan]"
        )
        console.log(
            f"  [white]Entries upserted:[/white] [green]{upserted_count}[/green]"
        )
        console.log(
            f"  [white]Lines skipped (comments/interval):[/white] [yellow]{skipped_count}[/yellow]"
        )
        console.log(
            f"  [white]Lines with parsing errors or failed upserts:[/white] [red]{parse_errors}[/red]"
        )

    except FileNotFoundError:
        console.log(
            f"[bold red]Error:[/bold red] The file '{file_path}' was not found during parsing.",
            style="red",
        )
    except Exception as e:
        console.log(
            f"[bold red]An unexpected error occurred during parsing:[/bold red] {e}",
            style="red",
        )
        # To get more detail, you could print the full traceback:
        # console.print_exception(show_locals=True)
    finally:
        # Clean up the unzipped file
        if os.path.exists(file_path):
            try:
                os.remove(file_path)
                console.log(
                    f"[bold green]Cleaned up:[/bold green] Removed unzipped file: [dim]{file_path}[/dim]"
                )
            except OSError as e:
                console.log(
                    f"[bold orange3]Warning:[/bold orange3] Could not remove {file_path}: {e}",
                    style="orange3",
                )


class VietnameseEntry(BaseModel):
    """A Pydantic model for a Vietnamese dictionary entry, representing its structure."""

    word: str
    definitions: List[str]


def parse_vietnamese_entry(entry_str: str) -> Optional[VietnameseEntry]:
    """
    Parses a single string line containing Vietnamese word data into a VietnameseEntry Pydantic model.
    Expected format: Word : Definition, Word : (1) Defintion (2) Definition
    Example: Ba Lê : Paris
    """
    pattern = re.compile(r"^(.*?)\s*:\s*(.*)$")
    match = pattern.match(entry_str.strip())

    if not match:
        # This function is called within a loop that tracks errors, so no console.log here.
        # The calling function handles logging the parsing error.
        return None

    word, raw_defs = match.groups()
    
    definitions = []

    if re.match(r'^\(\d+\)', raw_defs):
        # Case: It starts with "(number)"
        numbered_def_pattern = re.compile(r'\(\d+\)\s*(.*?)(?=\s*\(\d+\)|$)')
        extracted_defs = numbered_def_pattern.findall(raw_defs)
        definitions = [d.strip() for d in extracted_defs if d.strip()]
        
    else:
        # Case: It starts with "(number)"
        if raw_defs:
            definitions.append(raw_defs)

    try:
        entry_object = VietnameseEntry(
            word=word,
            definitions=definitions,
        )
        return entry_object
    except ValidationError:
        # This function is called within a loop that tracks errors, so no console.log here.
        # The calling function handles logging the validation error.
        return None


def upsert_vietnamese_entry(supabase: Client, entry: VietnameseEntry) -> dict:
    """
    Inserts a new entry into the 'vietnamese_entries' table using a Pydantic model.
    If an entry with the same word primary key already
    exists, it updates it.

    Args:
        supabase: An initialized Supabase client instance.
        entry: An instance of the VietnameseEntry Pydantic model.

    Returns:
        dict: The data of the upserted record from the database if successful,
              an empty dictionary otherwise.
    """
    try:
        # Convert the Pydantic model to a dictionary before sending to Supabase
        entry_dict = entry.model_dump()

        # The .upsert() method handles the INSERT or UPDATE logic automatically
        response = supabase.table("vietnamese_entries").upsert(entry_dict).execute()

        if response.data:
            # This function is called inside a Progress bar loop,
            # so direct console.log for success is usually avoided to prevent output flickering.
            return response.data[0]
        else:
            # In cases where no data is returned but no error is raised by Supabase,
            # it indicates a successful operation but no new row was created/updated.
            # (e.g., if the data was identical and Supabase optimises the upsert)
            return {}

    except Exception:
        # Error messages for upsert failures are now logged from the calling function (parse_vietnamese_txt)
        # to ensure they appear without interfering with the progress bar.
        # We simply return an empty dict to signal failure.
        return {}


if __name__ == "__main__":
    main()
