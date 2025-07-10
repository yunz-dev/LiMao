## Dictionary Sources:
- Chinese: `https://www.mdbg.net/chinese/export/cedict/cedict_1_0_ts_utf-8_mdbg.txt.gz`
    - CCedict (Creative Commons Attribution-Share Alike 3.0 License)
- Japanese `ftp://ftp.edrdg.org/pub/Nihongo//JMdict_e.gz`
    - JMDict (creative Commons Attribution-ShareAlike License V4.0)
- Korean, Vietnamese, Indonesian
    - Wikitionary Dumps (Creative Commons Attribution-ShareAlike 4.0 International License (CC-BY-SA) and the GNU Free Documentation License (GFDL))
    - for now we are using this for korean: `https://github.com/mhagiwara/cc-kedict`

### Instructions
- install supabase cli
- go to `/supabase` and run `supabase start` and `supabase db reset`
    - make sure to note down the api url and the service role key
- go to `/scripts/dictionary` and fill out the the `.env`
default config should look something like this:
```
SUPABASE_URL=http://127.0.0.1:54321
SUPABASE_KEY=ADD_YOUR_OWN_SUPABASE_SERVICE_ROLE_KEY_HERE
```
- run `pip install -r requirements.txt` and `python3 main.py` in `/scripts/dictionary` in order to populate the database
- yipeee
- you can find the database at `http://localhost:54323` (typically)

### Language Scrapers Overview
- download dictionary data from open sources (like cc-cedict and jmdict)
- decompress (.gz) or read raw data directly (.yml)
- parse entries into pydantic models
- upsert each entry into supabase database (table)

## Chinese Scraper
- processes CC-CEDICT format entries:
    - traditional
    - simplified
    - definition 1
    - definition 2
- every entry has to be has something in it
- compiles into table with entries and is upserted:
    - traditional
    - simplified
    - pronunciation
    - definitions

## Korean Scraper
- processes CC-KEDICT format entries:
    - word
    - romaja
    - pos
    - defs
    - notes, conj, syns, tags, etc. (metadata)
- normalises data type to fit parse expected data type and compiles into table with same
  entries and is upserted - each entry except word being optional

## Japanese Scraper
- processes JMDict format entries:
    - kanji
    - kana
    - senses
- normalises data type to fit parse expected data type (ensures kana is present,
  joins definitions into a list, etc.)
- compiles into table with entries and is upserted:
    - word
    - readings
    - alt forms
    - definitions