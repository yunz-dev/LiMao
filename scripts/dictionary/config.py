from pydantic import BaseModel


class DictionaryScraper(BaseModel):
    """A Pydantic model to configure Dictionary Scrapers"""

    source: str  # url to download dictionary file
    protocol: str  # http, ftp, file system... etc
    file_type: str  # txt, xml, yml... etc
    zip_type: str  # zip, gzip etc
    file_name: str
    interval: int = 1  # for dev
    upsert: bool = True  # for dev


ChineseScraper = DictionaryScraper(
    source="https://www.mdbg.net/chinese/export/cedict/cedict_1_0_ts_utf-8_mdbg.txt.gz",
    protocol="http",
    file_type="txt",
    zip_type="gz",
    file_name="cedict_1_0_ts_utf-8_mdbg.txt",
    interval=100,  # for dev
    upsert=True,
)

JapaneseScraper = DictionaryScraper(
    source="https://example.com/dictionaries/english.txt",
    protocol="http",
    file_type="txt",
    zip_type="gz",
    file_name="english_dictionary.txt",
    interval=500,  # for dev
    upsert=True,
)

KoreanScraper = DictionaryScraper(
    source="https://example.com/dictionaries/english.txt",
    protocol="http",
    file_type="txt",
    zip_type="gz",
    file_name="english_dictionary.txt",
    interval=500,  # for dev
    upsert=True,
)
