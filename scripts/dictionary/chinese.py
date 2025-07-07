import argparse
import os
import re
from typing import List, Optional

from pydantic import BaseModel, ValidationError

from supabase import Client, create_client


def main():
    """
    Main function to parse arguments and process the file.
    """
    parser = argparse.ArgumentParser(
        description="A script to parse entries from the CC-CEDICT and update supabase database with entries"
    )

    parser.add_argument("filepath", help="Path to CCEDICT file... e.g ./cedict_ts.u8")

    args = parser.parse_args()

    file_path = args.filepath
    print(f"Attempting to process file: {file_path}")

    if not os.path.exists(file_path):
        print(f"Error: The file '{file_path}' was not found.")
        return

    try:
        with open(file_path, "r", encoding="utf-8") as f:
            for i, line in enumerate(f):
                if i < 15:
                    print(f"Line {i+1}: {line.strip()}")
            if i >= 15:
                print("...")
            response = input("Does this file look correct? (Y/n) ")
            if response.lower() == "n" or response.lower() == "no":
                print("exiting...")
                exit()
    except Exception as e:
        print(f"An error occurred while reading the file: {e}")
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            client = setup_supabase_client()
            for i, line in enumerate(f):
                if line[0] == "#":
                    continue
                else:
                    entry = parse_chinese_entry(line)
                    upsert_chinese_entry(client, entry)
                    if i % 1000 == 0:
                        print("adding", i)
    except Exception as e:
        print(f"An error occurred while reading the file: {e}")


class ChineseEntry(BaseModel):
    """A Pydantic model for a Chinese dictionary entry."""

    traditional: str
    simplified: str
    pronunciation: str
    definitions: List[str]


def parse_chinese_entry(entry_str: str) -> Optional[ChineseEntry]:
    """
    Parses a string containing Chinese word data into a Pydantic model.
    """
    pattern = re.compile(r"(\S+)\s+(\S+)\s+\[(.*?)\]\s+\/(.*)\/")
    match = pattern.match(entry_str.strip())

    if not match:
        return None

    traditional, simplified, pronunciation, defs_string = match.groups()
    definitions = [d.strip() for d in defs_string.split("/") if d.strip()]

    try:
        entry_object = ChineseEntry(
            traditional=traditional,
            simplified=simplified,
            pronunciation=pronunciation,
            definitions=definitions,
        )
        return entry_object
    except ValidationError as e:
        print(f"Data failed validation: {e}")
        return None


def setup_supabase_client() -> Client:
    """
    Initializes and returns the Supabase client using environment variables.
    """
    print("setting up supabase client...")
    supabase_url = os.environ.get("SUPABASE_URL")
    supabase_key = os.environ.get("SUPABASE_KEY")

    if not supabase_url or not supabase_key:
        raise ValueError(
            "SUPABASE_URL and SUPABASE_KEY must be set in your environment."
        )

    return create_client(supabase_url, supabase_key)


def upsert_chinese_entry(supabase: Client, entry: ChineseEntry) -> dict:
    """
    Inserts a new entry into the 'chinese_entries' table using a Pydantic model.
    If an entry with the same (traditional, simplified) primary key already
    exists, it updates it.

    Args:
        supabase: An initialized Supabase client instance.
        entry: An instance of the ChineseEntry Pydantic model.

    Returns:
        The data of the upserted record from the database.
    """
    try:
        # Convert the Pydantic model to a dictionary before sending to Supabase
        entry_dict = entry.model_dump()

        # The .upsert() method handles the INSERT or UPDATE logic automatically
        response = supabase.table("chinese_entries").upsert(entry_dict).execute()

        if response.data:
            # print(
            #     f"Successfully upserted: ('{entry.traditional}', '{entry.simplified}')"
            # )
            return response.data[0]
        else:
            # print("Upsert successful, but no data returned.")
            return {}

    except Exception as e:
        print(f"An error occurred: {e}")
        return {}


if __name__ == "__main__":
    main()
