"""
fetch_wikimedia_images.py
Populeaza image_url folosind Wikipedia + Wikimedia.
"""
import os
import time
import requests
from urllib.parse import urlparse
from dotenv import load_dotenv
import psycopg2

load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))

db_url = os.getenv("DATABASE_URL")
if not db_url:
    raise RuntimeError("DATABASE_URL lipseste din .env")

parsed = urlparse(db_url)
DB_CONFIG = {
    "host": parsed.hostname,
    "port": parsed.port,
    "database": parsed.path.lstrip("/"),
    "user": parsed.username,
    "password": parsed.password,
}

WIKIPEDIA_API = "https://en.wikipedia.org/w/api.php"
HEADERS = {"User-Agent": "TripCraft/1.0 (Bachelor Thesis Project)"}


def search_article(query, retries=3):
    params = {"action": "query", "list": "search", "srsearch": query, "srlimit": 1, "format": "json"}
    for attempt in range(retries):
        try:
            r = requests.get(WIKIPEDIA_API, params=params, headers=HEADERS, timeout=10)
            if r.status_code == 429:
                wait = (attempt + 1) * 5
                print(f"  [429] sleep {wait}s...", end="", flush=True)
                time.sleep(wait)
                continue
            r.raise_for_status()
            results = r.json().get("query", {}).get("search", [])
            if results:
                return results[0]["title"]
            return None
        except Exception as e:
            if attempt == retries - 1:
                print(f"  Search error '{query}': {e}")
                return None
            time.sleep(2)
    return None


def get_page_image(title, retries=3):
    params = {"action": "query", "titles": title, "prop": "pageimages", "pithumbsize": 800, "format": "json"}
    for attempt in range(retries):
        try:
            r = requests.get(WIKIPEDIA_API, params=params, headers=HEADERS, timeout=10)
            if r.status_code == 429:
                wait = (attempt + 1) * 5
                time.sleep(wait)
                continue
            r.raise_for_status()
            pages = r.json().get("query", {}).get("pages", {})
            for page_data in pages.values():
                thumbnail = page_data.get("thumbnail", {})
                source = thumbnail.get("source")
                if source:
                    return source
            return None
        except Exception as e:
            if attempt == retries - 1:
                print(f"  Image error '{title}': {e}")
                return None
            time.sleep(2)
    return None


def fetch_destination_image(name, country):
    title = search_article(f"{name} {country}")
    if title:
        url = get_page_image(title)
        if url:
            return url
    title = search_article(name)
    if title:
        url = get_page_image(title)
        if url:
            return url
    return None


def main(only_missing=True, limit=None):
    conn = psycopg2.connect(**DB_CONFIG)
    cur = conn.cursor()

    if only_missing:
        cur.execute("""
            SELECT id, name, country FROM destinations
            WHERE image_url IS NULL
               OR image_url = ''
               OR (image_url NOT LIKE '%wikimedia%' AND image_url NOT LIKE '%wikipedia%')
            ORDER BY id
        """)
    else:
        cur.execute("SELECT id, name, country FROM destinations ORDER BY id")

    destinations = cur.fetchall()
    if limit:
        destinations = destinations[:limit]

    print(f"De procesat: {len(destinations)} destinatii (only_missing={only_missing})\n")
    success = 0
    failed = 0

    for i, (dest_id, name, country) in enumerate(destinations):
        print(f"[{i+1}/{len(destinations)}] {name}, {country} ... ", end="", flush=True)
        try:
            url = fetch_destination_image(name, country)
            if url:
                cur.execute("UPDATE destinations SET image_url = %s WHERE id = %s", (url, dest_id))
                conn.commit()
                print("OK")
                success += 1
            else:
                print("- (no image)")
                failed += 1
        except Exception as e:
            print(f"X ({e})")
            failed += 1
        time.sleep(1.0)

    cur.close()
    conn.close()
    print(f"\nDone! Imagini gasite: {success}, Esuate: {failed}")


if __name__ == "__main__":
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument("--all", action="store_true")
    p.add_argument("--limit", type=int, default=None)
    args = p.parse_args()
    main(only_missing=not args.all, limit=args.limit)