import os
import sys
from typing import List, Optional

import yaml
from config import KoreanScraper
from dotenv import load_dotenv

# --- Install required packages ---
# pip install pydantic supabase pyyaml rich
from pydantic import BaseModel, ValidationError
from rich.console import Console
from rich.progress import (
    BarColumn,
    Progress,
    TextColumn,
    TimeElapsedColumn,
    TimeRemainingColumn,
)
from rich.prompt import Confirm  # Used for interactive prompts
from rich.status import Status  # Used for initial setup spinners
from utils import (
    download_file,
    setup_supabase_client,
)  # Assuming these are from your previous utility file

from supabase import (
    Client,
)  # Keep create_client for setup_supabase_client internally

# Initialize the Rich Console for all output
console = Console()


def main():
    """
    Main function to orchestrate the download, parsing, and upsert process
    for Korean dictionary entries based on the KoreanScraper configuration.
    """
    console.rule("[bold blue]Starting Korean Scraper[/bold blue]")

    # Unpack configuration settings
    try:
        config_values = KoreanScraper.model_dump()
        source = config_values.get("source")
        protocol = config_values.get("protocol")
        file_type = config_values.get("file_type")
        zip_type = config_values.get("zip_type")
        file_name = config_values.get("file_name")
        interval = config_values.get("interval")
        upsert = config_values.get("upsert")

        console.log("[bold magenta]Configuration loaded:[/bold magenta]")
        console.log(f"  [cyan]Source:[/cyan] {source}")
        console.log(f"  [cyan]Protocol:[/cyan] {protocol}")
        console.log(f"  [cyan]File Type:[/cyan] {file_type}")
        console.log(f"  [cyan]Zip Type:[/cyan] {zip_type}")
        console.log(f"  [cyan]Local File Name:[/cyan] {file_name}")
        console.log(f"  [cyan]Processing Interval:[/cyan] {interval}")
        console.log(f"  [cyan]Upsert to DB:[/cyan] {upsert}")

    except Exception as e:
        console.log(
            f"[bold red]Error loading configuration:[/bold red] {e}", style="red"
        )
        console.log(
            "[bold red]Exiting due to configuration error.[/bold red]", style="red"
        )
        sys.exit(1)  # Use sys.exit for clean exits

    # --- Step 1: Download the file ---
    console.log(
        "\n[bold yellow]Step 1:[/bold yellow] [bold blue]Downloading file...[/bold blue]"
    )
    downloaded_path = None
    if protocol == "http":
        downloaded_path = download_file(
            source, file_name
        )  # Assuming download_file handles file extension if needed
    # elif protocol == "ftp": # Add FTP support if needed, using download_file_ftp from utils
    #    downloaded_path = download_file_ftp(source, file_name)
    else:
        console.log(
            f"[bold red]Error:[/bold red] Unsupported protocol '{protocol}'. Only 'http' is supported.",
            style="red",
        )
        console.log(
            "[bold red]Exiting due to unsupported protocol.[/bold red]", style="red"
        )
        sys.exit(1)

    if not downloaded_path:
        console.log("[bold red]File download failed. Exiting.[/bold red]", style="red")
        sys.exit(1)

    # --- Step 2: Handle unzipping (or lack thereof) ---
    if zip_type == "none":
        console.log(
            "\n[bold yellow]Step 2:[/bold yellow] [bold blue]No unzipping required (zip_type='none').[/bold blue]"
        )
    else:
        # If you were to add zip support, you'd integrate unzip_gz_file or similar here.
        # For now, it just exits if zip_type is not 'none'.
        console.log(
            f"[bold red]Error:[/bold red] Unsupported zip type '{zip_type}'. Only 'none' is supported for now.",
            style="red",
        )
        console.log(
            "[bold red]Exiting due to unsupported zip type.[/bold red]", style="red"
        )
        sys.exit(1)

    # --- Step 3: Parse and upsert data ---
    console.log(
        "\n[bold yellow]Step 3:[/bold yellow] [bold blue]Parsing file and upserting data...[/bold blue]"
    )
    if file_type == "yml":
        # Pass the path to the downloaded file directly
        parse_korean_yml(upsert, interval, downloaded_path)
    else:
        console.log(
            f"[bold red]Error:[/bold red] Unsupported file type '{file_type}'. Only 'yml' is supported for parsing.",
            style="red",
        )
        console.log(
            "[bold red]Exiting due to unsupported file type.[/bold red]", style="red"
        )
        sys.exit(1)

    console.rule("[bold blue]Korean Scraper Finished[/bold blue]")


# --- 2. Pydantic Data Model ---
class KoreanEntry(BaseModel):
    """A Pydantic model for a Korean dictionary entry."""

    word: str
    romaja: Optional[str] = None
    pos: Optional[str] = None
    defs: Optional[List[str]] = None  # This will hold the extracted definition strings
    conj: Optional[List[str]] = None
    notes: Optional[List[str]] = None
    syns: Optional[List[str]] = None
    tags: Optional[List[str]] = None


def upsert_korean_entry(supabase: Client, entry: KoreanEntry) -> bool:
    """
    Inserts a new entry into the 'korean_entries' table using a Pydantic model.
    If an entry with the same word primary key already exists, it updates it.

    Args:
        supabase: An initialized Supabase client instance.
        entry: An instance of the KoreanEntry Pydantic model.

    Returns:
        bool: True if the upsert was successful, False otherwise.
    """
    try:
        # Convert the Pydantic model to a dictionary suitable for Supabase
        entry_dict = entry.model_dump(exclude_none=True)

        # The .upsert() method handles the INSERT or UPDATE logic automatically
        # based on the table's primary key.
        response = supabase.table("korean_entries").upsert(entry_dict).execute()

        # Check if Supabase returned data (indicating success, though not strictly an error if empty)
        if response.data:
            return True
        else:
            # Supabase might return empty data if no change was made (e.g., identical entry)
            # or if the upsert was successful but didn't return the full row.
            # Treat this as success for simplicity here.
            return True

    except Exception as e:
        # Re-raise the exception to be caught in the main loop for richer logging
        raise e


def parse_korean_entry_from_yaml_item(
    item: dict, line_num: int
) -> Optional[KoreanEntry]:
    """
    Helper function to parse and validate a single YAML item into a KoreanEntry.
    Includes data normalization steps for 'romaja', list fields, and 'defs'.

    Args:
        item (dict): The dictionary representing a single YAML entry.
        line_num (int): The line number (or index) of the item for error reporting.

    Returns:
        Optional[KoreanEntry]: A validated KoreanEntry object, or None if validation fails.
    """
    try:
        # --- NEW: Handle boolean conversion for 'romaja' ---
        # The YAML parser may interpret unquoted 'on' as the boolean True.
        # This converts it back to a string (e.g., True -> "True") to prevent validation errors.
        if "romaja" in item and isinstance(item.get("romaja"), bool):
            item["romaja"] = str(item["romaja"])

        # --- Handle str to List[str] conversion ---
        # These fields should be lists, but might be a single string in the YAML.
        # This converts them to a list with a single item if they are a string.
        fields_to_normalize = ["notes", "defs", "conj", "syns", "tags"]
        for field in fields_to_normalize:
            if field in item and isinstance(item.get(field), str):
                item[field] = [item[field]]

        # Transformation: Extract 'def' strings to match the Pydantic model
        # This handles the case where 'defs' is a list of dictionaries.
        if "defs" in item and isinstance(item.get("defs"), list):
            new_defs = []
            for d in item["defs"]:
                if isinstance(d, dict) and "def" in d:
                    new_defs.append(d.get("def", ""))
                elif isinstance(d, str):
                    new_defs.append(d)
            item["defs"] = new_defs

        # Validation
        korean_entry = KoreanEntry(**item)
        return korean_entry

    except ValidationError as e:
        word_for_log = item.get("word", f"entry #{line_num}")
        console.log(
            f"[bold orange3]⚠️ Parsing Failed:[/bold orange3] '[yellow]{word_for_log}[/yellow]' [bold orange3]due to validation error:[/bold orange3]\n[dim]{e}[/dim]",
            style="orange3",
        )
        return None
    except Exception as e:
        word_for_log = item.get("word", f"entry #{line_num}")
        console.log(
            f"[bold red]❌ Parsing Failed:[/bold red] '[yellow]{word_for_log}[/yellow]' [bold red]due to an unexpected error:[/bold red] [dim]{e}[/dim]",
            style="red",
        )
        return None


# --- 4. Main Orchestration Function ---
def parse_korean_yml(upsert: bool, interval: int, file_path: str):
    """
    Main function to parse arguments, process the YAML file, and upsert entries.

    Args:
        upsert (bool): If True, upserts parsed entries into the database.
        interval (int): Only process and (if upsert is True) upsert every `interval` lines.
        file_path (str): The path to the YAML file to parse.
    """

    # Initialize Supabase client if upserting is enabled
    supabase = None
    if upsert:
        try:
            # setup_supabase_client itself now uses rich.status.Status
            supabase = setup_supabase_client()
            console.log("[bold green]Supabase client connected.[/bold green]")
        except ValueError as e:
            console.log(
                f"[bold red]❌ Configuration Error:[/bold red] {e}", style="red"
            )
            console.log(
                "[bold red]Exiting as Supabase connection failed.[/bold red]",
                style="red",
            )
            sys.exit(1)
        except Exception as e:
            console.log(
                f"[bold red]❌ An unexpected error occurred during Supabase setup:[/bold red] {e}",
                style="red",
            )
            console.log("[bold red]Exiting.[/bold red]", style="red")
            sys.exit(1)

    # Check for file existence
    console.log(
        f"\n[bold blue]Attempting to process file:[/bold blue] [green]{file_path}[/green]"
    )
    if not os.path.exists(file_path):
        console.log(
            f"[bold red]❌ Error: The file '[yellow]{file_path}[/yellow]' was not found.[/bold red]",
            style="red",
        )
        # Clean up downloaded file if parsing fails at this stage
        if os.path.exists(file_path):
            try:
                os.remove(file_path)
                console.log(
                    f"[bold green]Cleaned up:[/bold green] Removed downloaded file: [dim]{file_path}[/dim]"
                )
            except OSError as e:
                console.log(
                    f"[bold orange3]Warning:[/bold orange3] Could not remove {file_path}: {e}",
                    style="orange3",
                )
        return  # Return instead of exit to allow main() to clean up if needed

    # Load and parse the YAML file
    yaml_data = None
    with Status(
        "[bold green]Loading and parsing YAML file...", spinner="dots", console=console
    ) as status:
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                yaml_data = yaml.safe_load(f)
            if not isinstance(yaml_data, list):
                status.update(
                    "[bold red]❌ Error: YAML root must be a list of dictionary entries.[/bold red]",
                    spinner_style="red",
                )
                console.log(
                    "[bold red]❌ Error: YAML root must be a list of dictionary entries.[/bold red]",
                    style="red",
                )
                # Clean up downloaded file
                if os.path.exists(file_path):
                    try:
                        os.remove(file_path)
                        console.log(
                            f"[bold green]Cleaned up:[/bold green] Removed downloaded file: [dim]{file_path}[/dim]"
                        )
                    except OSError as e:
                        console.log(
                            f"[bold orange3]Warning:[/bold orange3] Could not remove {file_path}: {e}",
                            style="orange3",
                        )
                return
            status.update(
                "[bold green]YAML file successfully loaded and parsed.[/bold green]",
                spinner_style="green",
            )
        except yaml.YAMLError as e:
            status.update(
                f"[bold red]❌ Error parsing YAML file: {e}[/bold red]",
                spinner_style="red",
            )
            console.log(
                f"[bold red]❌ Error parsing YAML file: {e}[/bold red]", style="red"
            )
            # Clean up downloaded file
            if os.path.exists(file_path):
                try:
                    os.remove(file_path)
                    console.log(
                        f"[bold green]Cleaned up:[/bold green] Removed downloaded file: [dim]{file_path}[/dim]"
                    )
                except OSError as e:
                    console.log(
                        f"[bold orange3]Warning:[/bold orange3] Could not remove {file_path}: {e}",
                        style="orange3",
                    )
            return
        except Exception as e:
            status.update(
                f"[bold red]❌ An unexpected error occurred while loading YAML: {e}[/bold red]",
                spinner_style="red",
            )
            console.log(
                f"[bold red]❌ An unexpected error occurred while loading YAML: {e}[/bold red]",
                style="red",
            )
            # Clean up downloaded file
            if os.path.exists(file_path):
                try:
                    os.remove(file_path)
                    console.log(
                        f"[bold green]Cleaned up:[/bold green] Removed downloaded file: [dim]{file_path}[/dim]"
                    )
                except OSError as e:
                    console.log(
                        f"[bold orange3]Warning:[/bold orange3] Could not remove {file_path}: {e}",
                        style="orange3",
                    )
            return

    # --- Preview and Confirmation ---
    console.log(
        f"\n[bold yellow]Previewing file entries:[/bold yellow] [green]{file_path}[/green]"
    )
    preview_count = 0
    for i, item in enumerate(yaml_data):
        if preview_count >= 15:  # Display first 3 entries
            console.log("[dim]... (truncated)[/dim]", style="dim")
            break

        entry = parse_korean_entry_from_yaml_item(item, i + 1)
        if entry:
            console.log(
                f"[dim]Entry {i+1}:[/dim] [white]Word:[/white] [cyan]{entry.word}[/cyan] | [white]Romaja:[/white] [blue]{entry.romaja}[/blue] | [white]Defs:[/white] [green]{', '.join(entry.defs[:2]) + ('...' if len(entry.defs) > 2 else '')}[/green]",
                style="dim",
            )
            preview_count += 1
        else:
            console.log(
                f"[dim]Entry {i+1}:[/dim] [red]Failed to parse for preview. Skipping.[/red]",
                style="dim red",
            )
            # Don't increment preview_count if parsing failed for a preview item, to get 3 successful previews
            # unless the list is too short.
            # If you want to show *any* 3 lines regardless of parse success, increment here.
            # For now, we'll try to get 3 *parsed* entries.
            pass

    response = Confirm.ask("[bold yellow]Do these entries look correct?[/bold yellow]")
    if not response:
        console.log(
            "[bold red]Operation cancelled by user. Exiting.[/bold red]", style="red"
        )
        # Clean up downloaded file
        if os.path.exists(file_path):
            try:
                os.remove(file_path)
                console.log(
                    f"[bold green]Cleaned up:[/bold green] Removed downloaded file: [dim]{file_path}[/dim]"
                )
            except OSError as e:
                console.log(
                    f"[bold orange3]Warning:[/bold orange3] Could not remove {file_path}: {e}",
                    style="orange3",
                )
        sys.exit(1)

    # Process and upsert each entry one by one
    success_count = 0
    skipped_interval_count = 0  # Added for consistency with Chinese script
    parse_error_count = 0  # Separate count for parsing errors
    upsert_failure_count = 0  # Separate count for upsert errors

    total_entries = len(yaml_data)
    console.log(
        "\n[bold blue]Starting parsing and (optional) upserting...[/bold blue]"
    )

    with Progress(
        TextColumn("[bold green]{task.description}[/bold green]", justify="right"),
        BarColumn(bar_width=None),
        "[progress.percentage]{task.percentage:>3.1f}%",
        "•",
        TextColumn("Processed: [white]{task.fields[processed_count]}[/white]"),
        "•",
        TextColumn("Upserted: [green]{task.fields[upserted_count]}[/green]"),
        "•",
        TextColumn("Skipped: [yellow]{task.fields[skipped_count]}[/yellow]"),
        "•",
        TextColumn(
            "Parse Errors: [red]{task.fields[parse_error_count]}[/red]"
        ),  # Updated column
        "•",
        TextColumn(
            "Upsert Failures: [red]{task.fields[upsert_failure_count]}[/red]"
        ),  # New column
        "•",
        TimeElapsedColumn(),
        "•",
        TimeRemainingColumn(),
        console=console,
    ) as progress:
        parsing_task = progress.add_task(
            "[white]Parsing entries...",
            total=total_entries,
            processed_count=0,
            upserted_count=0,
            skipped_count=0,
            parse_error_count=0,  # Initial values for new fields
            upsert_failure_count=0,
        )

        for i, item in enumerate(yaml_data):
            # Update processed count regardless of skip/parse status
            progress.update(parsing_task, advance=1, processed_count=i + 1)

            # Check if current entry should be skipped based on interval
            if i % interval != 0:
                skipped_interval_count += 1
                progress.update(parsing_task, skipped_count=skipped_interval_count)
                continue

            # Parse the entry using the helper function
            korean_entry = parse_korean_entry_from_yaml_item(item, i + 1)

            if korean_entry:
                # Entry parsed successfully
                if upsert:
                    if supabase:  # Ensure supabase client is initialized
                        try:
                            upsert_success = upsert_korean_entry(supabase, korean_entry)
                            if upsert_success:
                                success_count += 1
                                progress.update(
                                    parsing_task, upserted_count=success_count
                                )
                            else:
                                upsert_failure_count += 1
                                progress.update(
                                    parsing_task,
                                    upsert_failure_count=upsert_failure_count,
                                )
                                console.log(
                                    f"[bold red]❌ Upsert failed for:[/bold red] [dim]'{korean_entry.word}'[/dim] (No data returned by Supabase)",
                                    style="red",
                                    justify="left",
                                )
                        except Exception as e:
                            upsert_failure_count += 1
                            progress.update(
                                parsing_task, upsert_failure_count=upsert_failure_count
                            )
                            console.log(
                                f"[bold red]❌ Upsert Exception for:[/bold red] [dim]'{korean_entry.word}'[/dim]: [dim]{e}[/dim]",
                                style="red",
                                justify="left",
                            )
                    else:
                        # This case should ideally be caught by initial supabase setup error,
                        # but as a fallback, if upsert is True but client is None.
                        skipped_interval_count += (
                            1  # Count as skipped if upsert was intended but impossible
                        )
                        progress.update(
                            parsing_task, skipped_count=skipped_interval_count
                        )
                        console.log(
                            f"[bold orange3]Warning:[/bold orange3] Skipping upsert for '{korean_entry.word}' because Supabase client is not initialized.",
                            style="orange3",
                        )
                else:
                    # If upsert is False, just count as successfully processed/skipped by interval
                    success_count += 1  # For consistency with Chinese model, count non-upserted but parsed as success
                    progress.update(
                        parsing_task, upserted_count=success_count
                    )  # Use upserted_count as a general "processed successfully" count if not upserting
            else:
                # Entry parsing failed (error already logged by parse_korean_entry_from_yaml_item)
                parse_error_count += 1
                progress.update(parsing_task, parse_error_count=parse_error_count)

        # Final update to ensure progress bar reflects all counts
        progress.update(
            parsing_task,
            processed_count=total_entries,  # Ensure processed count reaches total
            upserted_count=success_count,
            skipped_count=skipped_interval_count,
            parse_error_count=parse_error_count,
            upsert_failure_count=upsert_failure_count,
        )

    # Final Summary (consistent with Chinese output)
    console.log("\n[bold green]Parsing and upserting complete![/bold green]")
    console.log(
        f"  [white]Total entries processed:[/white] [cyan]{total_entries}[/cyan]"
    )
    console.log(
        f"  [white]Entries successfully handled:[/white] [green]{success_count}[/green]"
    )
    console.log(
        f"  [white]Entries skipped (by interval):[/white] [yellow]{skipped_interval_count}[/yellow]"
    )
    console.log(
        f"  [white]Entries with parsing errors:[/white] [red]{parse_error_count}[/red]"
    )
    console.log(
        f"  [white]Entries with upsert failures:[/white] [red]{upsert_failure_count}[/red]"
    )

    # Clean up the downloaded file
    if os.path.exists(file_path):
        try:
            os.remove(file_path)
            console.log(
                f"[bold green]Cleaned up:[/bold green] Removed downloaded file: [dim]{file_path}[/dim]"
            )
        except OSError as e:
            console.log(
                f"[bold orange3]Warning:[/bold orange3] Could not remove {file_path}: {e}",
                style="orange3",
            )


# --- 5. Script Entry Point ---
if __name__ == "__main__":
    # Load environment variables for Supabase (usually done at the top level of your script)
    load_dotenv()
    main()
