"""
download_quiz_images.py
Descarcă imaginile Unsplash pentru tagurile care nu au încă image_url setat.
Procesează maxim 45 taguri pe rulare (limita Unsplash: 50 req/oră).

Utilizare:
    cd backend
    python scripts/download_quiz_images.py
"""

import io
import os
import sys
import time
import requests
import psycopg2
from dotenv import load_dotenv

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), '..', '.env'))

DATABASE_URL      = os.getenv("DATABASE_URL")
UNSPLASH_KEY      = os.getenv("UNSPLASH_ACCESS_KEY")
MAX_PER_RUN       = 45
DELAY_SECONDS     = 1.5

# Directorul relativ la rădăcina proiectului backend/
SCRIPT_DIR   = os.path.dirname(os.path.abspath(__file__))
BACKEND_DIR  = os.path.dirname(SCRIPT_DIR)
OUTPUT_DIR   = os.path.join(BACKEND_DIR, "static", "quiz_images")


def main():
    if not UNSPLASH_KEY:
        print("EROARE: UNSPLASH_ACCESS_KEY nu este setat în .env")
        sys.exit(1)

    if not DATABASE_URL:
        print("EROARE: DATABASE_URL nu este setat în .env")
        sys.exit(1)

    os.makedirs(OUTPUT_DIR, exist_ok=True)
    print(f"Folder imagini: {OUTPUT_DIR}")

    conn   = psycopg2.connect(DATABASE_URL)
    cursor = conn.cursor()

    # Asigură că există coloanele de credit (idempotent)
    cursor.execute("ALTER TABLE tags ADD COLUMN IF NOT EXISTS image_credit VARCHAR(255)")
    cursor.execute("ALTER TABLE tags ADD COLUMN IF NOT EXISTS image_credit_url VARCHAR(500)")
    conn.commit()

    # Câte taguri totale fără imagine
    cursor.execute("SELECT COUNT(*) FROM tags WHERE image_url IS NULL")
    total_missing = cursor.fetchone()[0]
    print(f"Taguri fără image_url: {total_missing}")

    if total_missing == 0:
        print("Toate tagurile au deja imagine. Nimic de făcut.")
        conn.close()
        return

    # Selectează maxim MAX_PER_RUN taguri de procesat
    cursor.execute(
        "SELECT id, slug, name FROM tags WHERE image_url IS NULL ORDER BY id LIMIT %s",
        (MAX_PER_RUN,)
    )
    tags = cursor.fetchall()
    print(f"Se procesează {len(tags)} taguri în această sesiune...\n")

    downloaded = 0
    failed     = 0

    for tag_id, slug, name in tags:
        dest_path  = os.path.join(OUTPUT_DIR, f"{slug}.jpg")
        db_url     = f"/static/quiz_images/{slug}.jpg"

        # Dacă fișierul există deja pe disk, actualizează doar DB-ul (fără credite)
        if os.path.exists(dest_path):
            cursor.execute(
                "UPDATE tags SET image_url = %s WHERE id = %s",
                (db_url, tag_id)
            )
            conn.commit()
            print(f"  [SKIP – exista pe disk] {slug}")
            downloaded += 1
            continue

        # Cerere Unsplash
        try:
            resp = requests.get(
                "https://api.unsplash.com/photos/random",
                params={
                    "query":       name,
                    "orientation": "landscape",
                    "client_id":   UNSPLASH_KEY,
                },
                timeout=10,
            )
        except requests.exceptions.RequestException as exc:
            print(f"  [EROARE reț] {slug}: {exc}")
            failed += 1
            time.sleep(DELAY_SECONDS)
            continue

        if resp.status_code == 429:
            print(f"\n  RATE LIMIT atins după {downloaded} descărcări. Oprire.")
            break

        if resp.status_code != 200:
            print(f"  [HTTP {resp.status_code}] {slug}: {resp.text[:120]}")
            failed += 1
            time.sleep(DELAY_SECONDS)
            continue

        photo    = resp.json()
        img_url  = photo.get("urls", {}).get("regular")
        if not img_url:
            print(f"  [NO URL] {slug}")
            failed += 1
            time.sleep(DELAY_SECONDS)
            continue

        photographer_name = photo.get("user", {}).get("name", "")
        photographer_url  = photo.get("user", {}).get("links", {}).get("html", "")

        # Descarcă imaginea
        try:
            img_resp = requests.get(img_url, timeout=20)
            img_resp.raise_for_status()
        except requests.exceptions.RequestException as exc:
            print(f"  [EROARE download] {slug}: {exc}")
            failed += 1
            time.sleep(DELAY_SECONDS)
            continue

        with open(dest_path, "wb") as f:
            f.write(img_resp.content)

        # Actualizează DB cu URL + credite
        cursor.execute(
            """UPDATE tags
               SET image_url        = %s,
                   image_credit     = %s,
                   image_credit_url = %s
               WHERE id = %s""",
            (db_url, photographer_name, photographer_url, tag_id)
        )
        conn.commit()

        size = len(img_resp.content) // 1024
        print(f"  [OK] {slug:<35} {size:>5} KB  (foto: {photographer_name})")
        downloaded += 1

        time.sleep(DELAY_SECONDS)

    # Câte mai rămân după această rulare
    cursor.execute("SELECT COUNT(*) FROM tags WHERE image_url IS NULL")
    remaining = cursor.fetchone()[0]

    conn.close()

    print(f"\n{'='*50}")
    print(f"Descărcate în această sesiune : {downloaded}")
    print(f"Eșuate                        : {failed}")
    print(f"Rămân fără imagine            : {remaining}")
    if remaining > 0:
        print(f"Rulează scriptul din nou pentru a continua.")
    else:
        print("Toate tagurile au acum imagine!")


if __name__ == "__main__":
    main()
