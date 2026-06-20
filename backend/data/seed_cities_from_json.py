"""
seed_cities_from_json.py
========================
Importă orașele din orase.txt în DB, cu legacy_tags păstrate pentru NLP.

Rulare:
    cd backend
    venv\Scripts\python.exe data/seed_cities_from_json.py
"""

import sys, os, json
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.database import SessionLocal
from app.models.geography import Country, City

DATA_PATH = os.path.join(os.path.dirname(__file__), "orase.txt")


def main():
    db = SessionLocal()

    # Cache țări iso2 → Country
    countries = {c.iso2: c for c in db.query(Country).all()}

    with open(DATA_PATH, encoding="utf-8") as f:
        raw = f.read()
        import re
        raw = re.sub(r'/\*.*?\*/', '', raw, flags=re.DOTALL)
        raw = re.sub(r'\}\s*\{', '},{', raw)
        raw = re.sub(r'\]\s*\[', ',', raw)
        raw = re.sub(r'\]\s*\{', ',{', raw)
        raw = raw.strip()
        if not raw.startswith('['):
            raw = '[' + raw
        if not raw.endswith(']'):
            raw = raw + ']'
        cities_data = json.loads(raw)

    print(f"Găsite {len(cities_data)} orașe în fișier.\n")

    inserted = skipped = warn = 0

    for entry in cities_data:
        iso2 = entry.get("country", "").upper()
        name = entry.get("city", "").strip()
        lat = entry.get("lat")
        lon = entry.get("lon")
        desc = entry.get("description", "")
        legacy_tags = entry.get("tags", "")
        cost = entry.get("cost_index")

        if not iso2 or not name or lat is None or lon is None:
            print(f"  [SKIP] Date incomplete: {entry}")
            warn += 1
            continue

        country = countries.get(iso2)
        if not country:
            print(f"  [WARN] Țara '{iso2}' nu există în DB — sărit {name}")
            warn += 1
            continue

        existing = db.query(City).filter(
            City.name == name, City.country_id == country.id
        ).first()
        if existing:
            skipped += 1
            continue

        city = City(
            name=name,
            country_id=country.id,
            latitude=lat,
            longitude=lon,
            description=desc,
            legacy_tags=legacy_tags,
            avg_cost_per_day=float(cost) if cost else None,
        )
        db.add(city)
        inserted += 1

    db.commit()

    print(f"\n{'═'*50}")
    print(f"  Inserate:  {inserted}")
    print(f"  Sărite:    {skipped}")
    print(f"  Warnings:  {warn}")
    print(f"  TOTAL DB:  {db.query(City).count()}")
    print(f"{'═'*50}")
    db.close()


if __name__ == "__main__":
    main()