import argparse
import os
import sys
from typing import List, Optional
from xml.etree import ElementTree as ET
from xml.etree.ElementTree import Element

from config import JapaneseScraper
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
from rich.status import Status
from utils import download_file_ftp, setup_supabase_client, unzip_gz_file

from supabase import Client

# Initialize the Rich Console for all output
console = Console()

CODEC = "utf-8"


def main():
    """
    Main function to orchestrate the download, unzipping, parsing, and upsert process
    for Japanese dictionary entries based on the JapaneseScraper configuration.
    """
    console.rule("[bold blue]Starting Japanese Scraper[/bold blue]")

    # Unpack configuration settings
    try:
        config_values = JapaneseScraper.model_dump()
        source = config_values.get("source")
        protocol = config_values.get("protocol")
        file_type = config_values.get("file_type")
        zip_type = config_values.get("zip_type")
        file_name = config_values.get("file_name")
        interval = config_values.get("interval")
        upsert = config_values.get("upsert")

        console.log(f"[bold magenta]Configuration loaded:[/bold magenta]")
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
        sys.exit(1)

    # --- Step 1: Download the file ---
    console.log(
        "\n[bold yellow]Step 1:[/bold yellow] [bold blue]Downloading file...[/bold blue]"
    )
    downloaded_path = None
    if protocol == "ftp":
        downloaded_path = download_file_ftp(
            source, f"{file_name}.gz"
        )  # Assuming it downloads as .gz
    else:
        console.log(
            f"[bold red]Error:[/bold red] Unsupported protocol '{protocol}'. Only 'ftp' is supported.",
            style="red",
        )
        console.log(
            "[bold red]Exiting due to unsupported protocol.[/bold red]", style="red"
        )
        sys.exit(1)

    if not downloaded_path:
        console.log("[bold red]File download failed. Exiting.[/bold red]", style="red")
        sys.exit(1)

    # --- Step 2: Unzip the file ---
    unzipped_path = downloaded_path  # Initialize for cleanup
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
            sys.exit(1)
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
    else:
        console.log(
            f"[bold red]Error:[/bold red] Unsupported zip type '{zip_type}'. Only 'gz' is supported.",
            style="red",
        )
        console.log(
            "[bold red]Exiting due to unsupported zip type.[/bold red]", style="red"
        )
        sys.exit(1)  # Exit if zip_type is not 'gz'

    # --- Step 3: Parse and upsert data ---
    console.log(
        "\n[bold yellow]Step 3:[/bold yellow] [bold blue]Parsing file and upserting data...[/bold blue]"
    )
    if file_type == "xml":
        parse_japanese_xml(upsert, interval, unzipped_path)
    else:
        console.log(
            f"[bold red]Error:[/bold red] Unsupported file type '{file_type}'. Only 'xml' is supported for parsing.",
            style="red",
        )
        console.log(
            "[bold red]Exiting due to unsupported file type.[/bold red]", style="red"
        )
        sys.exit(1)

    console.rule("[bold blue]Japanese Scraper Finished[/bold blue]")


class JapaneseEntry(BaseModel):
    """A Pydantic model for a Japanese dictionary entry."""

    word: str
    readings: Optional[List[str]]
    alt_forms: Optional[List[str]]
    definitions: List[str]


def parse_kebs(k_eles: List[Element]) -> Optional[List[str]]:
    """Extracts 'keb' (kanji entry form) texts from XML k_ele elements."""
    kebs = []
    for k_ele in k_eles:
        keb = k_ele.find("keb")
        if keb is not None and keb.text:
            kebs.append(keb.text)
    return kebs or None


def parse_readings(r_eles: List[Element]) -> Optional[List[str]]:
    """Extracts 'reb' (reading entry form) texts from XML r_ele elements."""
    readings = []
    for r_ele in r_eles:
        # Ignore no-kanji readings if 'nokanji' attribute is present
        if r_ele.find("re_nokanji") is not None:
            continue
        reb = r_ele.find("reb")
        if reb is not None and reb.text:
            readings.append(reb.text)
    return readings or None


def parse_definitions(senses: List[Element]) -> List[str]:
    """
    Extracts English definitions, part-of-speech (pos), and dialect (dial)
    information from XML sense elements. Combines them into a single string.
    """
    definitions = []
    for sense in senses:
        gloss = sense.find("gloss")
        # Ensure it's an English gloss
        if (
            gloss is None
            or gloss.attrib.get("{http://www.w3.org/XML/1998/namespace}lang") != "eng"
        ):
            continue

        definition_text = gloss.text.strip() if gloss.text else ""
        if not definition_text:
            continue  # Skip empty definitions

        # Append part-of-speech (pos)
        poses = sense.findall("pos")
        for pos in poses:
            if pos.text:
                definition_text += f";;{pos.text.strip()}"

        # Append dialect (dial)
        dials = sense.findall("dial")
        for dial in dials:
            if dial.text:
                definition_text += f"//{dial.text.strip()}"

        definitions.append(definition_text)
    return definitions


def parse_japanese_entry_from_xml_element(
    entry_element: Element, index: int
) -> Optional[List[JapaneseEntry]]:
    """
    Parses a single XML <entry> element into a list of JapaneseEntry Pydantic models.
    Each <keb> within an entry can form a distinct JapaneseEntry.

    Args:
        entry_element (Element): The XML Element representing a single dictionary entry.
        index (int): The index of this XML entry in the list (for logging purposes).

    Returns:
        Optional[List[JapaneseEntry]]: A list of validated JapaneseEntry objects, or None if parsing fails for all forms.
    """
    kebs = parse_kebs(entry_element.findall("k_ele"))
    readings = parse_readings(entry_element.findall("r_ele"))
    definitions = parse_definitions(entry_element.findall("sense"))

    # If no definitions or no kebs/readings, it's not a valid entry
    if not definitions or (not kebs and not readings):
        return None  # Indicate unparseable entry

    res: List[JapaneseEntry] = []

    # If there are kanji forms, iterate through them.
    # Otherwise, use readings as the primary "word" forms.
    primary_forms = kebs if kebs else readings

    if not primary_forms:  # Should not happen if previous check passed, but for safety
        return None

    for i, primary_form in enumerate(primary_forms):
        # Determine alt_forms based on the current primary_form
        # If kebs exist, alt_forms are other kebs. If only readings, other readings.
        if kebs:  # Primary forms are kanji (kebs)
            alt_forms = [f for idx, f in enumerate(kebs) if idx != i] or None
        else:  # Primary forms are readings (readings, if kebs was None)
            alt_forms = [f for idx, f in enumerate(readings) if idx != i] or None

        try:
            mod = JapaneseEntry(
                word=primary_form,
                readings=readings
                if kebs
                else None,  # Only store readings if there was a kanji word
                alt_forms=alt_forms,
                definitions=definitions,
            )
            res.append(mod)
        except ValidationError as e:
            console.log(
                f"[bold orange3]⚠️ Parsing Failed:[/bold orange3] '[yellow]{primary_form}[/yellow]' [bold orange3]due to validation error:[/bold orange3]\n[dim]{e}[/dim]",
                style="orange3",
            )
            # Continue to try other forms within the same XML entry, don't return None immediately
        except Exception as e:
            console.log(
                f"[bold red]❌ Parsing Failed:[/bold red] '[yellow]{primary_form}[/yellow]' [bold red]due to an unexpected error:[/bold red] [dim]{e}[/dim]",
                style="red",
            )
            # Continue to try other forms

    return (
        res if res else None
    )  # Return list if any entries were successfully parsed, else None


def upsert_japanese_entry(supabase: Client, entry: JapaneseEntry) -> bool:
    """
    Inserts a new entry into the 'japanese_entries' table.
    If an entry with the same word primary key already exists, it updates it.

    Args:
        supabase: An initialized Supabase client instance.
        entry: An instance of the JapaneseEntry Pydantic model.

    Returns:
        bool: True if the upsert was successful, False otherwise.
    """
    try:
        entry_dict = entry.model_dump(
            exclude_none=True
        )  # exclude_none for cleaner data

        response = supabase.table("japanese_entries").upsert(entry_dict).execute()

        if response.data:
            return True
        else:
            # Supabase might return empty data if no actual change, or if just not returning data
            return True

    except Exception as e:
        # Re-raise to be caught in the main loop for rich error logging
        raise e


def parse_japanese_xml(upsert: bool, interval: int, file_path: str):
    """
    Parses a Japanese dictionary XML file, previews content, and optionally
    upserts entries into a Supabase database.

    Args:
        upsert (bool): If True, upserts parsed entries into the database.
        interval (int): Only process and (if upsert is True) upsert every `interval` *parsed JapaneseEntry objects*.
        file_path (str): The path to the XML file to parse.
    """
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

    # Load and parse the XML file
    entries_list = []  # List of XML <entry> elements
    with Status(
        "[bold green]Loading and parsing XML file...", spinner="dots", console=console
    ) as status:
        try:
            tree = ET.parse(file_path)
            entries_list = tree.getroot().findall("entry")
            if not entries_list:
                status.update(
                    "[bold red]❌ Error: No <entry> elements found in XML file.[/bold red]",
                    spinner_style="red",
                )
                console.log(
                    "[bold red]❌ Error: No <entry> elements found in XML file.[/bold red]",
                    style="red",
                )
                if os.path.exists(file_path):
                    try:
                        os.remove(file_path)
                    except OSError as e:
                        console.log(
                            f"[bold orange3]Warning:[/bold orange3] Could not remove {file_path}: {e}",
                            style="orange3",
                        )
                return

            status.update(
                f"[bold green]XML file successfully loaded.[/bold green] [cyan]{len(entries_list)}[/cyan] raw XML entries found."
            )
        except ET.ParseError as e:
            status.update(
                f"[bold red]❌ Error parsing XML file: {e}[/bold red]",
                spinner_style="red",
            )
            console.log(
                f"[bold red]❌ Error parsing XML file: {e}[/bold red]", style="red"
            )
            if os.path.exists(file_path):
                try:
                    os.remove(file_path)
                except OSError as e:
                    console.log(
                        f"[bold orange3]Warning:[/bold orange3] Could not remove {file_path}: {e}",
                        style="orange3",
                    )
            return
        except Exception as e:
            status.update(
                f"[bold red]❌ An unexpected error occurred while loading XML: {e}[/bold red]",
                spinner_style="red",
            )
            console.log(
                f"[bold red]❌ An unexpected error occurred while loading XML: {e}[/bold red]",
                style="red",
            )
            if os.path.exists(file_path):
                try:
                    os.remove(file_path)
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
    raw_xml_entry_index = 0
    max_preview_attempts = (
        100  # To prevent infinite loop if all early entries fail to parse
    )

    while (
        preview_count < 15
        and raw_xml_entry_index < len(entries_list)
        and raw_xml_entry_index < max_preview_attempts
    ):
        xml_entry = entries_list[raw_xml_entry_index]
        parsed_entries = parse_japanese_entry_from_xml_element(
            xml_entry, raw_xml_entry_index + 1
        )

        if parsed_entries:
            for entry in parsed_entries:
                if preview_count >= 15:
                    break
                console.log(
                    f"[dim]Entry {raw_xml_entry_index+1}.{preview_count+1}:[/dim] [white]Word:[/white] [cyan]{entry.word}[/cyan] | "
                    f"[white]Readings:[/white] [blue]{', '.join(entry.readings[:2]) + ('...' if entry.readings and len(entry.readings) > 2 else '') if entry.readings else 'N/A'}[/blue] | "
                    f"[white]Defs:[/white] [green]{(entry.definitions[0][:50] + '...' if len(entry.definitions[0]) > 50 else entry.definitions[0]) if entry.definitions else 'N/A'}[/green]",
                    style="dim",
                )
                preview_count += 1
        else:
            console.log(
                f"[dim]Entry {raw_xml_entry_index+1}:[/dim] [red]Failed to parse for preview. Skipping.[/red]",
                style="dim red",
            )

        raw_xml_entry_index += 1

    if raw_xml_entry_index < len(
        entries_list
    ):  # If we didn't go through all entries for preview
        console.log("[dim]... (truncated)[/dim]", style="dim")

    response = Confirm.ask("[bold yellow]Do these entries look correct?[/bold yellow]")
    if not response:
        console.log(
            "[bold red]Operation cancelled by user. Exiting.[/bold red]", style="red"
        )
        if os.path.exists(file_path):
            try:
                os.remove(file_path)
            except OSError as e:
                console.log(
                    f"[bold orange3]Warning:[/bold orange3] Could not remove {file_path}: {e}",
                    style="orange3",
                )
        sys.exit(1)

    # --- Main parsing and upserting loop ---
    supabase = None
    if upsert:
        try:
            supabase = setup_supabase_client()
            console.log("[bold green]Supabase client connected.[/bold green]")
        except ValueError as e:
            console.log(
                f"[bold red]❌ Configuration Error:[/bold red] {e}", style="red"
            )
            console.log(
                "[bold red]Cannot proceed with upserting. Exiting.[/bold red]",
                style="red",
            )
            sys.exit(1)
        except Exception as e:
            console.log(
                f"[bold red]❌ An unexpected error occurred during Supabase setup:[/bold red] {e}",
                style="red",
            )
            console.log(
                "[bold red]Cannot proceed with upserting. Exiting.[/bold red]",
                style="red",
            )
            sys.exit(1)

    processed_count = 0  # Total JapaneseEntry objects processed
    upserted_count = 0  # JapaneseEntry objects successfully upserted
    skipped_interval_count = 0  # JapaneseEntry objects skipped by interval
    parse_error_count = (
        0  # Raw XML entries that failed to yield *any* valid JapaneseEntry
    )
    upsert_failure_count = 0  # JapaneseEntry objects that failed to upsert to DB

    console.log(
        f"\n[bold blue]Starting parsing and (optional) upserting...[/bold blue]"
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
            "XML Parse Errors: [red]{task.fields[xml_parse_errors]}[/red]"
        ),  # XML level parse errors
        "•",
        TextColumn("Upsert Failures: [red]{task.fields[upsert_failure_count]}[/red]"),
        "•",
        TimeElapsedColumn(),
        "•",
        TimeRemainingColumn(),
        console=console,
    ) as progress:
        # The total for the progress bar is the count of XML <entry> elements
        parsing_task = progress.add_task(
            "[white]Parsing XML entries...",
            total=len(entries_list),
            processed_count=0,  # This will track individual JapaneseEntry objects
            upserted_count=0,
            skipped_count=0,
            xml_parse_errors=0,  # Track XML entries that don't yield any valid JapaneseEntry
            upsert_failure_count=0,
        )

        for i, entry_xml_element in enumerate(entries_list):
            progress.update(parsing_task, advance=1)  # Advance for each raw XML entry

            parsed_entries_from_xml = parse_japanese_entry_from_xml_element(
                entry_xml_element, i + 1
            )

            if parsed_entries_from_xml:
                for j_entry in (
                    parsed_entries_from_xml
                ):  # Iterate over each JapaneseEntry from this XML element
                    processed_count += (
                        1  # Increment total processed for each Pydantic model
                    )

                    if upsert and processed_count % interval == 0:
                        if supabase:
                            try:
                                upsert_success = upsert_japanese_entry(
                                    supabase, j_entry
                                )
                                if upsert_success:
                                    upserted_count += 1
                                else:
                                    upsert_failure_count += 1
                                    console.log(
                                        f"[bold red]❌ Upsert failed for:[/bold red] [dim]'{j_entry.word}'[/dim] (No data returned by Supabase)",
                                        style="red",
                                        justify="left",
                                    )
                            except Exception as e:
                                upsert_failure_count += 1
                                console.log(
                                    f"[bold red]❌ Upsert Exception for:[/bold red] [dim]'{j_entry.word}'[/dim]: [dim]{e}[/dim]",
                                    style="red",
                                    justify="left",
                                )
                        else:
                            skipped_interval_count += 1  # Count as skipped if upsert intended but client missing
                            console.log(
                                f"[bold orange3]Warning:[/bold orange3] Skipping upsert for '{j_entry.word}' because Supabase client is not initialized.",
                                style="orange3",
                            )
                    else:
                        skipped_interval_count += (
                            1  # Count as skipped if not upserting or not interval
                        )

                    # Update progress bar fields after processing each JapaneseEntry
                    progress.update(
                        parsing_task,
                        processed_count=processed_count,
                        upserted_count=upserted_count,
                        skipped_count=skipped_interval_count,
                        upsert_failure_count=upsert_failure_count,
                    )
            else:
                # If the XML entry failed to parse into ANY valid JapaneseEntry models
                parse_error_count += 1
                progress.update(parsing_task, xml_parse_errors=parse_error_count)
                # Error message already logged by parse_japanese_entry_from_xml_element if parsing issue

        # Final update to ensure progress bar reflects all counts
        progress.update(
            parsing_task,
            completed=len(entries_list),
            processed_count=processed_count,
            upserted_count=upserted_count,
            skipped_count=skipped_interval_count,
            xml_parse_errors=parse_error_count,
            upsert_failure_count=upsert_failure_count,
        )

    # Final Summary (consistent with Chinese/Korean output)
    console.log(f"\n[bold green]Parsing and upserting complete![/bold green]")
    console.log(
        f"  [white]Total XML entries scanned:[/white] [cyan]{len(entries_list)}[/cyan]"
    )
    console.log(
        f"  [white]Total JapaneseEntry objects processed:[/white] [cyan]{processed_count}[/cyan]"
    )
    console.log(
        f"  [white]Entries successfully upserted:[/white] [green]{upserted_count}[/green]"
    )
    console.log(
        f"  [white]Entries skipped (by interval/no upsert):[/white] [yellow]{skipped_interval_count}[/yellow]"
    )
    console.log(
        f"  [white]XML entries with parsing errors:[/white] [red]{parse_error_count}[/red]"
    )
    console.log(
        f"  [white]JapaneseEntry objects with upsert failures:[/white] [red]{upsert_failure_count}[/red]"
    )

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


if __name__ == "__main__":
    main()
