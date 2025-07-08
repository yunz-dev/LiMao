import sys  # Import sys for clean exits

from chinese import main as update_chinese_dictionary
from japanese import main as update_japanese_dictionary
from korean import main as update_korean_dictionary
from rich.console import Console

# Initialize the Rich Console for all output
console = Console()


def main():
    """
    Main script to orchestrate the update of Chinese, Japanese, and Korean
    dictionaries in the database. Provides high-level logging using rich.
    """
    console.rule("[bold magenta]Starting All Dictionary Updates[/bold magenta]")
    console.log(f"Current time: [green]{console.get_datetime()}[/green]")
    console.log("Starting update process for all languages...")

    # --- Update Chinese Dictionary ---
    console.rule("[bold blue]Updating Chinese Dictionary[/bold blue]")
    try:
        console.log("Calling [cyan]update_chinese_dictionary()[/cyan]...")
        update_chinese_dictionary()
        console.log(
            "[bold green]✅ Chinese Dictionary update completed successfully.[/bold green]"
        )
    except Exception as e:
        console.log(
            f"[bold red]❌ Error updating Chinese Dictionary:[/bold red] {e}",
            style="red",
        )
        console.log(
            "[bold red]Proceeding to next dictionary, but Chinese update failed.[/bold red]",
            style="orange3",
        )  # Indicate partial failure

    console.print("\n")  # Add a newline for spacing between dictionary outputs

    # --- Update Japanese Dictionary ---
    console.rule("[bold blue]Updating Japanese Dictionary[/bold blue]")
    try:
        console.log("Calling [cyan]update_japanese_dictionary()[/cyan]...")
        update_japanese_dictionary()
        console.log(
            "[bold green]✅ Japanese Dictionary update completed successfully.[/bold green]"
        )
    except Exception as e:
        console.log(
            f"[bold red]❌ Error updating Japanese Dictionary:[/bold red] {e}",
            style="red",
        )
        console.log(
            "[bold red]Proceeding to next dictionary, but Japanese update failed.[/bold red]",
            style="orange3",
        )  # Indicate partial failure

    console.print("\n")  # Add a newline for spacing between dictionary outputs

    # --- Update Korean Dictionary ---
    console.rule("[bold blue]Updating Korean Dictionary[/bold blue]")
    try:
        console.log("Calling [cyan]update_korean_dictionary()[/cyan]...")
        update_korean_dictionary()
        console.log(
            "[bold green]✅ Korean Dictionary update completed successfully.[/bold green]"
        )
    except Exception as e:
        console.log(
            f"[bold red]❌ Error updating Korean Dictionary:[/bold red] {e}",
            style="red",
        )
        console.log("[bold red]Korean update failed.[/bold red]", style="orange3")

    console.rule("[bold magenta]All Dictionary Updates Finished[/bold magenta]")
    console.log(f"Process finished at: [green]{console.get_datetime()}[/green]")


if __name__ == "__main__":
    # Load environment variables if your individual scripts don't handle it
    # from dotenv import load_dotenv
    # load_dotenv() # Uncomment if needed for this top-level script

    try:
        main()
    except KeyboardInterrupt:
        console.log(
            "\n[bold yellow]Operation interrupted by user (Ctrl+C).[/bold yellow]",
            style="yellow",
        )
        sys.exit(1)
    except Exception as e:
        console.log(
            f"\n[bold red]An unhandled error occurred during the overall process:[/bold red] {e}",
            style="red",
        )
        console.print_exception(
            show_locals=True
        )  # Show traceback for unexpected errors
        sys.exit(1)
