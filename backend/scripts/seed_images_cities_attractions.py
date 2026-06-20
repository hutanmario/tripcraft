import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import time
import json
import requests
from dotenv import load_dotenv
from app.database import SessionLocal
from app.models.geography import City, Attraction, Country

load_dotenv()
UNSPLASH_KEY = os.getenv("UNSPLASH_ACCESS_KEY")
BASE_URL = "https://api.unsplash.com/search/photos"
PROGRESS_FILE = "scripts/image_seed_progress.json"


def get_image(query: str) -> str | None:
    try:
        res = requests.get(BASE_URL, params={
            "query": query,
            "per_page": 1,
            "orientation": "landscape"
        }, headers={"Authorization": f"Client-ID {UNSPLASH_KEY}"})
        data = res.json()
        if data.get("results"):
            return data["results"][0]["urls"]["regular"]
        return None
    except:
        return None


def load_progress():
    if os.path.exists(PROGRESS_FILE):
        with open(PROGRESS_FILE, "r") as f:
            return json.load(f)
    return {"cities_done": [], "attractions_done": []}


def save_progress(progress):
    with open(PROGRESS_FILE, "w") as f:
        json.dump(progress, f)


def main():
    db = SessionLocal()
    progress = load_progress()
    processed = 0

    # 1. Cities fără imagine
    cities = db.query(City).filter(City.image_url == None).all()
    cities = [c for c in cities if c.id not in progress["cities_done"]]
    print(f"Cities rămase: {len(cities)}")

    for city in cities:
        country = db.query(Country).filter(Country.id == city.country_id).first()
        query = f"{city.name} {country.name if country else ''} city"
        url = get_image(query)
        if url:
            city.image_url = url
            print(f"  ✓ {city.name}")
        else:
            print(f"  ✗ {city.name}: no result")
        progress["cities_done"].append(city.id)
        processed += 1
        save_progress(progress)
        db.commit()
        time.sleep(120)

    # 2. Attractions fără imagine
    attractions = db.query(Attraction).filter(Attraction.image_url == None).all()
    attractions = [a for a in attractions if a.id not in progress["attractions_done"]]
    print(f"Atracții rămase: {len(attractions)}")

    for attr in attractions:
        city = db.query(City).filter(City.id == attr.city_id).first()
        query = f"{attr.name} {city.name if city else ''}"
        url = get_image(query)
        if url:
            attr.image_url = url
            print(f"  ✓ {attr.name}")
        else:
            print(f"  ✗ {attr.name}: no result")
        progress["attractions_done"].append(attr.id)
        processed += 1
        save_progress(progress)
        db.commit()
        time.sleep(120)

    db.close()

    total_done = len(progress["cities_done"]) + len(progress["attractions_done"])
    print(f"\nAll done! Total processed: {total_done}")


if __name__ == "__main__":
    main()
