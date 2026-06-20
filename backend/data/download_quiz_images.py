"""
download_quiz_images.py
Descarcă imagini reprezentative pentru quiz-ul vizual.
Organizate pe 6 categorii mari, 5 imagini per categorie = 30 total.
"""

import os
import requests
import json
import time

UNSPLASH_ACCESS_KEY = os.getenv("UNSPLASH_ACCESS_KEY", "")

OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "..", "static", "quiz-images")

CATEGORIES = {
    "beach": [
        "tropical beach with turquoise water",
        "sandy beach ocean waves sunset",
        "beach palm trees clear water",
        "mediterranean beach rocky coast",
        "beach umbrellas summer vacation",
    ],
    "mountain": [
        "alpine mountain peaks snow",
        "mountain hiking trail scenic view",
        "mountain valley green meadow",
        "rocky mountain summit clouds",
        "mountain lake reflection",
    ],
    "city": [
        "vibrant city skyline urban",
        "european old town cobblestone street",
        "city market square people",
        "modern city architecture buildings",
        "city night lights bridge",
    ],
    "nature": [
        "dense forest trees sunlight",
        "waterfall jungle tropical nature",
        "northern lights aurora borealis",
        "green countryside rolling hills",
        "desert sand dunes landscape",
    ],
    "culture": [
        "ancient temple ruins archaeology",
        "medieval castle fortress historic",
        "colorful local market bazaar",
        "traditional festival celebration",
        "art museum gallery interior",
    ],
    "adventure": [
        "rock climbing mountain adventure",
        "whitewater rafting river",
        "paragliding flying aerial view",
        "scuba diving coral reef underwater",
        "cycling mountain bike trail",
    ],
}


def search_unsplash(query: str, per_page: int = 1) -> str | None:
    url = "https://api.unsplash.com/search/photos"
    params = {
        "query": query,
        "per_page": per_page,
        "orientation": "landscape",
        "client_id": UNSPLASH_ACCESS_KEY,
    }
    try:
        res = requests.get(url, params=params, timeout=10)
        data = res.json()
        results = data.get("results", [])
        if results:
            return results[0]["urls"]["regular"]
    except Exception as e:
        print(f"  Eroare Unsplash: {e}")
    return None


def download_image(url: str, filepath: str) -> bool:
    try:
        res = requests.get(url, timeout=15)
        with open(filepath, "wb") as f:
            f.write(res.content)
        return True
    except Exception as e:
        print(f"  Eroare download: {e}")
        return False


def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    manifest = {}
    total_downloaded = 0

    for category, queries in CATEGORIES.items():
        print(f"\n📁 Categorie: {category}")
        cat_dir = os.path.join(OUTPUT_DIR, category)
        os.makedirs(cat_dir, exist_ok=True)
        manifest[category] = []

        for i, query in enumerate(queries):
            print(f"  [{i+1}/{len(queries)}] {query}...", end=" ")

            image_url = search_unsplash(query)
            if not image_url:
                print("✗ nu s-a găsit")
                continue

            filename = f"{category}_{i+1}.jpg"
            filepath = os.path.join(cat_dir, filename)

            if download_image(image_url, filepath):
                manifest[category].append({
                    "filename": filename,
                    "path": f"/static/quiz-images/{category}/{filename}",
                    "query": query,
                    "unsplash_url": image_url,
                })
                total_downloaded += 1
                print("✓")
            else:
                print("✗ eroare download")

            time.sleep(1.2)  # Unsplash rate limit

    # Salvează manifestul
    manifest_path = os.path.join(OUTPUT_DIR, "manifest.json")
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2, ensure_ascii=False)

    print(f"\n✅ Done! {total_downloaded}/30 imagini descărcate")
    print(f"📄 Manifest salvat în: {manifest_path}")


if __name__ == "__main__":
    main()