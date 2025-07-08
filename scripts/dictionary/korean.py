#!/usr/bin/env python3
"""
A script to parse dictionary entries from a Korean YAML file,
validate them, and upsert them into a Supabase database table
using a modular, function-based approach.
"""
from dotenv import load_dotenv

load_dotenv()
import argparse
import os
import sys
import yaml
from typing import List, Optional

# --- 1. Install required packages ---
# pip install pydantic supabase pyyaml
from pydantic import BaseModel, ValidationError
from supabase import create_client, Client


# --- 2. Pydantic Data Model ---
# This model ensures the data from the YAML file has the correct structure.
class KoreanEntry(BaseModel):
    """A Pydantic model for a Korean dictionary entry."""
    word: str
    romaja: Optional[str] = None
    pos: Optional[str] = None
    defs: Optional[List[str]] = None # This will hold the extracted definition strings
    conj: Optional[List[str]] = None
    notes: Optional[List[str]] = None
    syns: Optional[List[str]] = None
    tags: Optional[List[str]] = None


# --- 3. Functions for Database Interaction ---
def setup_supabase_client() -> Client:
    """
    Initializes and returns the Supabase client using environment variables.
    """
    print("Setting up Supabase client...")
    supabase_url = os.environ.get("SUPABASE_URL")
    supabase_key = os.environ.get("SUPABASE_KEY")

    if not supabase_url or not supabase_key:
        raise ValueError(
            "SUPABASE_URL and SUPABASE_KEY must be set in your environment."
        )
    
    client = create_client(supabase_url, supabase_key)
    print("✅ Supabase client connected.")
    return client


def upsert_korean_entry(supabase: Client, entry: KoreanEntry):
    """
    Inserts a new entry into the 'korean_entries' table using a Pydantic model.
    If an entry with the same word primary key already exists, it updates it.

    Args:
        supabase: An initialized Supabase client instance.
        entry: An instance of the KoreanEntry Pydantic model.
    """
    try:
        # Convert the Pydantic model to a dictionary suitable for Supabase
        entry_dict = entry.model_dump(exclude_none=True)

        # The .upsert() method handles the INSERT or UPDATE logic automatically
        # based on the table's primary key.
        supabase.table("korean_entries").upsert(entry_dict).execute()

    except Exception as e:
        # Re-raise the exception to be caught in the main loop
        raise e


# --- 4. Main Orchestration Function ---
def main():
    """
    Main function to parse arguments, process the YAML file, and upsert entries.
    """
    parser = argparse.ArgumentParser(
        description="A script to parse entries from the Korean dictionary YAML file and update a Supabase database."
    )
    parser.add_argument("filepath", help="Path to the Korean dictionary YAML file (e.g., ./kedict.yml)")
    args = parser.parse_args()

    # Initialize Supabase client
    try:
        supabase = setup_supabase_client()
    except ValueError as e:
        print(f"❌ Configuration Error: {e}")
        sys.exit(1)

    # Check for file existence
    file_path = args.filepath
    print(f"\nAttempting to process file: {file_path}")
    if not os.path.exists(file_path):
        print(f"❌ Error: The file '{file_path}' was not found.")
        return

    # Load and parse the YAML file
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            yaml_data = yaml.safe_load(f)
        if not isinstance(yaml_data, list):
            print("❌ Error: YAML root must be a list of dictionary entries.")
            return
    except yaml.YAMLError as e:
        print(f"❌ Error parsing YAML file: {e}")
        return

    # Process and upsert each entry one by one
    success_count = 0
    failure_count = 0
    total_entries = len(yaml_data)
    print(f"Processing {total_entries} entries...")

    for i, item in enumerate(yaml_data):
        word_for_log = item.get('word', f'entry #{i+1}')
        try:
            # --- NEW: Handle boolean conversion for 'romaja' ---
            # The YAML parser may interpret unquoted 'on' as the boolean True.
            # This converts it back to a string (e.g., True -> "True") to prevent validation errors.
            if 'romaja' in item and isinstance(item.get('romaja'), bool):
                item['romaja'] = str(item['romaja'])
            
            # --- Handle str to List[str] conversion ---
            # These fields should be lists, but might be a single string in the YAML.
            # This converts them to a list with a single item if they are a string.
            fields_to_normalize = ['notes', 'defs', 'conj', 'syns', 'tags']
            for field in fields_to_normalize:
                if field in item and isinstance(item.get(field), str):
                    item[field] = [item[field]]
            
            # Transformation: Extract 'def' strings to match the Pydantic model
            # This handles the case where 'defs' is a list of dictionaries.
            if 'defs' in item and isinstance(item.get('defs'), list):
                # This check handles complex definitions like `[{def: '...'}, {def: '...'}]`
                # while also correctly handling simple lists of strings like `['def1', 'def2']`
                # that might have been created by the normalization step above.
                new_defs = []
                for d in item['defs']:
                    if isinstance(d, dict) and 'def' in d:
                        new_defs.append(d.get('def', ''))
                    elif isinstance(d, str):
                        new_defs.append(d)
                item['defs'] = new_defs


            # Validation
            korean_entry = KoreanEntry(**item)
            
            # Upsert operation
            upsert_korean_entry(supabase, korean_entry)
            success_count += 1
            # print(f"({i+1}/{total_entries}) ✅ Successfully upserted '{korean_entry.word}'")

        except ValidationError as e:
            failure_count += 1
            print(f"({i+1}/{total_entries}) ⚠️  Skipping '{word_for_log}' due to validation error:\n{e}\n")
        except Exception as e:
            failure_count += 1
            print(f"({i+1}/{total_entries}) ❌ Failed to upsert '{word_for_log}' due to a database error: {e}")
            
    print("\n--- Processing Complete ---")
    print(f"✨ Successful upserts: {success_count}")
    print(f"💔 Failed entries: {failure_count}")


# --- 5. Script Entry Point ---
if __name__ == "__main__":
    main()