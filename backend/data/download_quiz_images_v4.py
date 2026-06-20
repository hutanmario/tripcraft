"""
Download one Unsplash image per leaf tag and store in quiz_images.
Rate: 50 req/hour → sleep 72s between requests.
Run from: backend/ folder with venv activated.
"""
import os, sys, time, requests
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()
ACCESS_KEY = os.getenv("UNSPLASH_ACCESS_KEY")
if not ACCESS_KEY:
    print("ERROR: UNSPLASH_ACCESS_KEY not found in .env"); sys.exit(1)

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent.parent))
from app.database import engine
from sqlalchemy import text

SAVE_DIR = Path(__file__).parent.parent / "static" / "quiz-images-v4"
SAVE_DIR.mkdir(parents=True, exist_ok=True)

SLEEP = 73  # seconds between requests (50/hour = 1 per 72s, +1 buffer)

def get_existing_urls():
    with engine.connect() as conn:
        rows = conn.execute(text("SELECT source_url FROM quiz_images WHERE source_url IS NOT NULL"))
        return {r[0] for r in rows}

def ensure_tag_id_column():
    with engine.connect() as conn:
        conn.execute(text("""
            ALTER TABLE quiz_images 
            ADD COLUMN IF NOT EXISTS tag_id INTEGER REFERENCES tags(id)
        """))
        conn.commit()

def get_leaf_tags():
    with engine.connect() as conn:
        rows = conn.execute(text(
            "SELECT id, name, slug, category FROM tags WHERE is_leaf=True ORDER BY category, name"
        ))
        return rows.fetchall()

def search_unsplash(query, existing_urls):
    url = "https://api.unsplash.com/search/photos"
    params = {"query": query, "per_page": 10, "orientation": "portrait"}
    headers = {"Authorization": f"Client-ID {ACCESS_KEY}"}
    resp = requests.get(url, params=params, headers=headers, timeout=15)
    resp.raise_for_status()
    photos = resp.json().get("results", [])
    for photo in photos:
        page_url = photo["links"]["html"]
        if page_url not in existing_urls:
            return photo
    return None

def download_image(photo_url, save_path):
    resp = requests.get(photo_url, timeout=30)
    resp.raise_for_status()
    save_path.write_bytes(resp.content)

def insert_image(tag_id, slug, category, photo, file_path):
    with engine.connect() as conn:
        conn.execute(text("""
            INSERT INTO quiz_images 
                (file_path, source_category, source_url, photographer, photographer_url, 
                 width, height, is_active, clip_tags, tag_id)
            VALUES 
                (:file_path, :category, :source_url, :photographer, :photographer_url,
                 :width, :height, True, :clip_tags, :tag_id)
            ON CONFLICT DO NOTHING
        """), {
            "file_path": file_path,
            "category": category,
            "source_url": photo["links"]["html"],
            "photographer": photo["user"]["name"],
            "photographer_url": photo["user"]["links"]["html"],
            "width": photo["width"],
            "height": photo["height"],
            "clip_tags": "{}",
            "tag_id": tag_id,
        })
        conn.commit()

def main():
    ensure_tag_id_column()
    tags = get_leaf_tags()
    existing_urls = get_existing_urls()
    
    print(f"Found {len(tags)} leaf tags. Estimated time: {len(tags) * SLEEP // 60} minutes.\n")
    
    downloaded = 0
    skipped = 0
    errors = 0

    for i, (tag_id, name, slug, category) in enumerate(tags):
        # Check if already downloaded for this tag
        with engine.connect() as conn:
            existing = conn.execute(text(
                "SELECT id FROM quiz_images WHERE tag_id=:tid"
            ), {"tid": tag_id}).fetchone()
        
        if existing:
            print(f"[{i+1}/{len(tags)}] SKIP (exists): {name}")
            skipped += 1
            continue

        print(f"[{i+1}/{len(tags)}] Searching: {name} ...", end=" ", flush=True)
        
        try:
            photo = search_unsplash(name, existing_urls)
            if not photo:
                print("no unique photo found")
                errors += 1
            else:
                save_path = SAVE_DIR / f"{slug}.jpg"
                download_image(photo["urls"]["regular"], save_path)
                file_path = f"quiz-images-v4/{slug}.jpg"
                insert_image(tag_id, slug, category, photo, file_path)
                existing_urls.add(photo["links"]["html"])
                print(f"OK → {photo['user']['name']}")
                downloaded += 1
        except Exception as e:
            print(f"ERROR: {e}")
            errors += 1

        # Rate limit: sleep between requests (skip sleep on last item)
        if i < len(tags) - 1:
            time.sleep(SLEEP)

    print(f"\n=== DONE ===")
    print(f"Downloaded: {downloaded}")
    print(f"Skipped:    {skipped}")
    print(f"Errors:     {errors}")

if __name__ == "__main__":
    main()