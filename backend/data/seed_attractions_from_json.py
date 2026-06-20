"""
seed_attractions_from_json.py
==============================
Importa 854 atractii din obiective.txt in DB, cu legacy_tags pentru NLP.

Rulare:
    cd backend
    venv\Scripts\python.exe data/seed_attractions_from_json.py
"""

import sys, os, json, re
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.database import SessionLocal, engine
from app.models.geography import Country, City, Attraction
from sqlalchemy import text

DATA_PATH = os.path.join(os.path.dirname(__file__), "obiective.txt")


def parse_json(path):
    with open(path, encoding="utf-8") as f:
        raw = f.read()
    # Normalize Windows line endings
    raw = raw.replace("\r\n", "\n").replace("\r", "\n")
    # Remove JS comments /* ... */
    raw = re.sub(r"/\*.*?\*/", "", raw, flags=re.DOTALL)
    # Fix artifacts: ""{ -> {
    raw = re.sub(r'""\\s*\{', "{", raw)
    # Fix missing commas between objects/arrays
    raw = re.sub(r",\s*\{\s*\{", ",{", raw)
    raw = re.sub(r"\}\s*\{", "},{", raw)
    raw = re.sub(r"\]\s*\[", ",", raw)
    raw = re.sub(r"\]\s*\{", ",{", raw)
    raw = raw.strip()
    if not raw.startswith("["):
        raw = "[" + raw
    if not raw.endswith("]"):
        raw = raw + "]"
    return json.loads(raw)


def main():
    # Adauga coloana legacy_tags pe attractions daca nu exista
    with engine.connect() as conn:
        conn.execute(text(
            "ALTER TABLE attractions ADD COLUMN IF NOT EXISTS legacy_tags TEXT"
        ))
        conn.commit()

    db = SessionLocal()

    # Cache: (city_name_lower, iso2) -> City
    city_cache = {}
    for city in db.query(City).all():
        country = db.query(Country).filter(Country.id == city.country_id).first()
        if country:
            key = (city.name.lower(), country.iso2.upper())
            city_cache[key] = city

    data = parse_json(DATA_PATH)
    print(f"Gasite {len(data)} atractii in fisier.\n")

    inserted = skipped = warn = 0

    for entry in data:
        city_name = (entry.get("city") or "").strip()
        iso2 = (entry.get("country") or "").strip().upper()
        name = (entry.get("name") or "").strip()
        lat = entry.get("lat")
        lon = entry.get("lon")
        category = entry.get("category", "")
        legacy_tags = entry.get("tags", "")

        if not city_name or not iso2 or not name:
            warn += 1
            continue

        city = city_cache.get((city_name.lower(), iso2))
        if not city:
            matches = [v for k, v in city_cache.items() if k[0] == city_name.lower()]
            city = matches[0] if matches else None

        if not city:
            print(f"  [WARN] Orasul '{city_name}' ({iso2}) nu exista in DB -- {name}")
            warn += 1
            continue

        existing = db.query(Attraction).filter(
            Attraction.name == name,
            Attraction.city_id == city.id
        ).first()
        if existing:
            skipped += 1
            continue

        attraction = Attraction(
            name=name,
            city_id=city.id,
            latitude=lat,
            longitude=lon,
            category=category,
            legacy_tags=legacy_tags,
        )
        db.add(attraction)
        inserted += 1

        if inserted % 100 == 0:
            db.commit()
            print(f"  ... {inserted} inserate pana acum")

    db.commit()

    print(f"\n{'='*50}")
    print(f"  Inserate:   {inserted}")
    print(f"  Sarite:     {skipped}")
    print(f"  Warnings:   {warn}")
    print(f"  TOTAL DB:   {db.query(Attraction).count()}")
    print(f"{'='*50}")
    db.close()


if __name__ == "__main__":
    main()