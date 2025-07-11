from pydantic import BaseModel


class DictionaryScraper(BaseModel):
    """A Pydantic model to configure Dictionary Scrapers"""

    source: str  # url to download dictionary file
    protocol: str  # http, ftp, file system... etc
    file_type: str  # txt, xml, yml... etc
    zip_type: str  # zip, gzip etc
    file_name: str
    interval: int = 1  # change to a bigger number for dev
    upsert: bool = True  # for dev


ChineseScraper = DictionaryScraper(
    source="https://www.mdbg.net/chinese/export/cedict/cedict_1_0_ts_utf-8_mdbg.txt.gz",
    protocol="http",
    file_type="txt",
    zip_type="gz",
    file_name="cedict_1_0_ts_utf-8_mdbg.txt",
    interval=1,
    upsert=True,
)

JapaneseScraper = DictionaryScraper(
    source="ftp://ftp.edrdg.org/pub/Nihongo//JMdict_e.gz",
    protocol="ftp",
    file_type="xml",
    zip_type="gz",
    file_name="JMdict_e",
    interval=1,
    upsert=True,
)

KoreanScraper = DictionaryScraper(
    source="https://raw.githubusercontent.com/mhagiwara/cc-kedict/refs/heads/master/kedict.yml",
    protocol="http",
    file_type="yml",
    zip_type="none",
    file_name="kedict.yml",
    interval=1,
    upsert=True,
)

VietnameseScraper = DictionaryScraper(
    source="http://www.denisowski.org/Vietnamese/vnedict.txt",
    protocol="http",
    file_type="txt",
    zip_type="none",
    file_name="vnedict.txt",
    interval=1,
    upsert=True,
)
