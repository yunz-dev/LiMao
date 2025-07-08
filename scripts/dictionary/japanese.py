import argparse
import os
from typing import List, Optional

import xml.etree.ElementTree as ET
import xml.etree.ElementTree.Element as Element
from pydantic import BaseModel, ValidationError

from supabase import Client
from utils import setup_supabase_client

CODEC = "utf-8"


def main():
    """
    Main function to parse arguments and process the file.
    """
    parser = argparse.ArgumentParser(
        description="A script to parse entries from the JMDICT file and update supabase database with entries"
    )

    parser.add_argument("filepath", help="Path to JMDICT file... e.g ./JMDICT")

    args = parser.parse_args()

    file_path = args.filepath
    print(f"Attempting to process file: {file_path}")

    if not os.path.exists(file_path):
        print(f"Error: The file '{file_path}' was not found.")
        exit(1)

    try:
        with open(file_path, "r", encoding=CODEC) as f:
            for i, line in enumerate(f):
                if i >= 15:
                    break
                print(f"Line {i+1}: {line.strip()}")
            if i >= 15:
                print("...")
            response = input("Does this file look correct? (Y/n) ")
            response = 'y'
            if response.lower() in ("n", "no"):
                print("exiting...")
                exit()
        client = setup_supabase_client()
        tree = ET.parse(file_path)
        entries_list = tree.getroot().findall("entry")
        print(f"{len(entries_list)} entries found.")
        n = len(entries_list) // 100
        i = 0
        perc = 0
        for entry_tree in entries_list:
            entries = parse_japanese_entry(entry_tree)
            for entry in entries:
                upsert_japanese_entry(client, entry)
            if i == 0:
                perc += 1
                print("\r[" + "-" * (perc // 2) + " " * (50 - perc // 2) + f"] {perc}%", end="")
            i = (i + 1) % n
        print("\rFinished adding all entries." + " " * 35)
    except Exception as e:
        print(f"An error occurred while reading the file: {e}")
        exit(1)


class JapaneseEntry(BaseModel):
    """A Pydantic model for a Japanese dictionary entry."""

    word: str
    readings: Optional[List[str]]
    alt_forms: Optional[List[str]]
    definitions: List[str]


def parse_kebs(k_eles: List[Element]) -> Optional[List[str]]:
    kebs = []
    for k_ele in k_eles:
        keb = k_ele.find("keb")
        if keb is not None:
            kebs.append(keb.text)
    return kebs


def parse_readings(r_eles: List[Element]) -> Optional[List[str]]:
    readings = []
    for r_ele in r_eles:
        reb = r_ele.find("reb")
        if reb is not None:
            readings.append(reb.text)
    return readings or None


def parse_definitions(senses: List[Element]) -> List[str]:
    definitions = []
    for sense in senses:
        gloss = sense.find("gloss")
        if gloss is None or gloss.attrib.get("{http://www.w3.org/XML/1998/namespace}lang") != "eng":
            continue
        definition = gloss.text
        poses = sense.findall("pos")
        for pos in poses:
            definition += f";;{pos.text}"
        dials = sense.findall("dial")
        for dial in dials:
            definition += f"//{dial.text}"
        definitions.append(definition)
    return definitions


def parse_japanese_entry(entry) -> Optional[List[JapaneseEntry]]:
    """
    Parses an entry containing Japanese word data into a Pydantic model.
    """
    kebs = parse_kebs(entry.findall("k_ele"))
    readings = parse_readings(entry.findall('r_ele'))
    definitions = parse_definitions(entry.findall("sense"))

    res = []

    if not kebs and readings:
        kebs = readings
        readings = None

    for i, keb in enumerate(kebs):
        alts = kebs[:i] + kebs[i+1:] or None
        try:
            mod = JapaneseEntry(
                word=keb,
                readings=readings,
                alt_forms=alts,
                definitions=definitions
            )
        except ValidationError as e:
            print(f"Data failed validation: {e}")
        res.append(mod)
    return res


def upsert_japanese_entry(supabase: Client, entry: JapaneseEntry) -> dict:
    """
    Inserts a new entry into the 'japanese_entries' table using a Pydantic model.
    If an entry with the same (traditional, simplified) primary key already
    exists, it updates it.

    Args:
        supabase: An initialized Supabase client instance.
        entry: An instance of the JapaneseEntry Pydantic model.

    Returns:
        The data of the upserted record from the database.
    """
    try:
        # Convert the Pydantic model to a dictionary before sending to Supabase
        entry_dict = entry.model_dump()

        # The .upsert() method handles the INSERT or UPDATE logic automatically
        response = supabase.table(
            "japanese_entries").upsert(entry_dict).execute()

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
