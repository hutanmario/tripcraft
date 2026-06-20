"""
fix_attraction_cities.py
========================
Repara atractiile cu orasul NULL sau gresit prin fuzzy name matching.
Normalizeaza caractere speciale si face match aproximativ.

Rulare:
    cd backend
    venv\Scripts\python.exe data/fix_attraction_cities.py
"""

import sys, os, re, json
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.database import SessionLocal
from app.models.geography import Country, City, Attraction
from app.config import settings

# ─── NORMALIZARE ──────────────────────────────────────────────────────────────

CHAR_MAP = str.maketrans({
    'ă': 'a', 'â': 'a', 'î': 'i', 'ș': 's', 'ț': 't',
    'Ă': 'A', 'Â': 'A', 'Î': 'I', 'Ș': 'S', 'Ț': 'T',
    'ä': 'a', 'ö': 'o', 'ü': 'u', 'ß': 'ss',
    'Ä': 'A', 'Ö': 'O', 'Ü': 'U',
    'á': 'a', 'é': 'e', 'í': 'i', 'ó': 'o', 'ú': 'u',
    'à': 'a', 'è': 'e', 'ì': 'i', 'ò': 'o', 'ù': 'u',
    'â': 'a', 'ê': 'e', 'î': 'i', 'ô': 'o', 'û': 'u',
    'ã': 'a', 'õ': 'o', 'ñ': 'n',
    'ć': 'c', 'č': 'c', 'ş': 's', 'ğ': 'g',
    'ł': 'l', 'ń': 'n', 'ź': 'z', 'ż': 'z', 'ś': 's',
    'ě': 'e', 'ř': 'r', 'ž': 'z', 'š': 's', 'ý': 'y',
    'ő': 'o', 'ű': 'u', 'ą': 'a', 'ę': 'e',
    'đ': 'd', 'ð': 'd', 'þ': 'th',
    'ï': 'i', 'ë': 'e',
    'ø': 'o', 'å': 'a', 'æ': 'ae',
    'Ø': 'O', 'Å': 'A', 'Æ': 'AE',
})


def normalize(s: str) -> str:
    """Normalizează string: lowercase, fără diacritice, fără spații extra."""
    s = s.translate(CHAR_MAP)
    s = s.lower().strip()
    s = re.sub(r'[^a-z0-9 ]', ' ', s)
    s = re.sub(r'\s+', ' ', s).strip()
    return s


def similarity(a: str, b: str) -> float:
    """Similaritate simplă bazată pe cuvinte comune."""
    words_a = set(normalize(a).split())
    words_b = set(normalize(b).split())
    if not words_a or not words_b:
        return 0.0
    common = words_a & words_b
    return len(common) / max(len(words_a), len(words_b))


# ─── MAPPINGS MANUALE ─────────────────────────────────────────────────────────
# Format: (city_name_in_obiective, iso2) -> city_name_in_db
# Adaugă aici orice mapping care nu se rezolvă automat

MANUAL_MAP = {
    ("London", "GB"): "Londra",
    ("Zürich", "CH"): "Zurich",
    ("Zurich", "CH"): "Zurich",
    ("Ghent", "BE"): "Gent",
    ("Anvers", "BE"): "Antwerpen",
    ("Gdańsk", "PL"): "Gdansk",
    ("Gdansk", "PL"): "Gdansk",
    ("Thessaloniki", "GR"): "Salonic",
    ("Chisinau", "MD"): "Chisinau",
    ("Santorini (Fira)", "GR"): "Santorini",
    ("Rhodes", "GR"): "Rodos",
    ("Tromsø", "NO"): "Tromso",
    ("Tromso", "NO"): "Tromso",
    ("Göteborg", "SE"): "Gothenburg",
    ("Malmö", "SE"): "Malmo",
    ("Umeå", "SE"): "Umea",
    ("Jönköping", "SE"): "Jonkoping",
    ("Plzeň", "CZ"): "Plzen",
    ("Pécs", "HU"): "Pecs",
    ("Győr", "HU"): "Gyor",
    ("Nesebar", "BG"): "Nessebar",
    ("Lagos", "PT"): "Lagos",
    ("Nazaré", "PT"): "Nazare",
    ("Vysoke Tatry", "SK"): "Vysoke Tatry",
    ("Luxemburg", "LU"): "Luxembourg City",
    ("Berna", "CH"): "Bern",
    ("Zell am See", "AT"): "Zell am See",
    ("Kotor", "ME"): "Kotor",
    ("Budva", "ME"): "Budva",
    ("Zabljak", "ME"): "Zabljak",
    ("Sarande", "AL"): "Sarande",
    ("Milestii Mici", "MD"): "Milestii Mici",
    ("Mokra Gora", "RS"): "Mokra Gora",
}

# Orașe din țări neacoperite (Turcia etc.) — le ignorăm
SKIP_COUNTRIES = {"TR"}


def main():
    db = SessionLocal()

    # Build city cache: norm_name -> [(City, iso2)]
    all_cities = db.query(City).all()
    country_cache = {c.id: c for c in db.query(Country).all()}

    city_by_norm = {}
    for city in all_cities:
        country = country_cache.get(city.country_id)
        iso2 = country.iso2.upper() if country else ""
        norm = normalize(city.name)
        if norm not in city_by_norm:
            city_by_norm[norm] = []
        city_by_norm[norm].append((city, iso2))

    # Re-parsează obiective.txt pentru a obține datele originale
    DATA_PATH = os.path.join(os.path.dirname(__file__), "obiective.txt")
    with open(DATA_PATH, encoding="utf-8") as f:
        raw = f.read()
    raw = raw.replace("\r\n", "\n").replace("\r", "\n")
    raw = re.sub(r"/[*].*?[*]/", "", raw, flags=re.DOTALL)
    raw = raw.replace('""', "")
    raw = re.sub(r"\}\s*\{", "},{", raw)
    raw = re.sub(r"\]\s*\[", ",", raw)
    raw = re.sub(r"\]\s*\{", ",{", raw)
    raw = raw.strip()
    if not raw.startswith("["): raw = "[" + raw
    if not raw.endswith("]"): raw = raw + "]"
    obiective = json.loads(raw)

    print(f"Procesare {len(obiective)} atracții din fișier...\n")

    fixed = skipped_country = already_ok = inserted_new = not_found = 0

    for entry in obiective:
        city_name = (entry.get("city") or "").strip()
        iso2 = (entry.get("country") or "").strip().upper()
        name = (entry.get("name") or "").strip()
        lat = entry.get("lat")
        lon = entry.get("lon")
        category = entry.get("category", "")
        legacy_tags = entry.get("tags", "")

        if not name or not city_name or not iso2:
            continue

        # Skip țări neacoperite
        if iso2 in SKIP_COUNTRIES:
            skipped_country += 1
            continue

        # Caută atracția deja în DB
        # Găsim mai întâi orașul corect
        city = None

        # 1. Manual map
        mapped_name = MANUAL_MAP.get((city_name, iso2))
        if mapped_name:
            norm = normalize(mapped_name)
            candidates = city_by_norm.get(norm, [])
            for c, c_iso2 in candidates:
                if c_iso2 == iso2:
                    city = c
                    break
            if not city and candidates:
                city = candidates[0][0]

        # 2. Exact match normalized
        if not city:
            norm = normalize(city_name)
            candidates = city_by_norm.get(norm, [])
            for c, c_iso2 in candidates:
                if c_iso2 == iso2:
                    city = c
                    break
            if not city and candidates:
                city = candidates[0][0]

        # 3. Fuzzy match
        if not city:
            best_score = 0.0
            best_city = None
            norm_input = normalize(city_name)
            for norm_db, candidates in city_by_norm.items():
                score = similarity(norm_input, norm_db)
                if score > best_score:
                    # Preferă același iso2
                    for c, c_iso2 in candidates:
                        if c_iso2 == iso2 and score > 0.5:
                            best_score = score
                            best_city = c
                    if not best_city and score > 0.7:
                        best_city = candidates[0][0]
                        best_score = score
            city = best_city

        if not city:
            print(f"  [NOT FOUND] '{city_name}' ({iso2}) — {name}")
            not_found += 1
            continue

        # Verifică dacă atracția există deja în DB
        existing = db.query(Attraction).filter(
            Attraction.name == name,
            Attraction.city_id == city.id
        ).first()

        if existing:
            already_ok += 1
            continue

        # Inserează atracția cu orașul corectat
        attraction = Attraction(
            name=name,
            city_id=city.id,
            latitude=lat,
            longitude=lon,
            category=category,
            legacy_tags=legacy_tags,
        )
        db.add(attraction)
        inserted_new += 1
        print(f"  [+] '{name}' → {city.name} ({iso2})")

    db.commit()

    print(f"\n{'='*50}")
    print(f"  Deja în DB:          {already_ok}")
    print(f"  Inserate acum:       {inserted_new}")
    print(f"  Țări neacoperite:    {skipped_country}")
    print(f"  Negăsite:            {not_found}")
    print(f"  TOTAL atracții DB:   {db.query(Attraction).count()}")
    print(f"{'='*50}")
    db.close()


if __name__ == "__main__":
    main()