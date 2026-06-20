"""
seed_countries.py
=================
Inserează cele 39 de țări europene cu metadata, taguri și Unsplash images.

Rulare:
    cd backend
    venv\Scripts\python.exe data/seed_countries.py
"""

import sys, os, time, requests
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.database import SessionLocal
from app.models.geography import Country, country_tags
from app.models.destination import Tag
from app.config import settings
from sqlalchemy import insert

# ─── DATE ȚĂRI ────────────────────────────────────────────────────────────────
# Format: (name, iso2, iso3, capital, lat, lon, avg_cost_eur, currency, language,
#          best_seasons, description, tag_slugs)

COUNTRIES = [
    (
        "France", "FR", "FRA", "Paris", 46.2276, 2.2137, 120, "EUR", "French",
        "spring,summer,autumn",
        "France blends world-class art, gastronomy, Alpine skiing, and Mediterranean beaches. "
        "From the Eiffel Tower to lavender fields in Provence, it offers extraordinary diversity.",
        [
            "art-museums", "michelin-restaurants", "wine-vineyards", "castles-palaces",
            "gothic-architecture", "cycling-biking", "sandy-beaches", "skiing",
            "guided-walking-tours", "fashion-weeks", "cooking-classes", "food-tours-guided",
            "local-festivals", "contemporary-art", "rooftop-bars",
        ],
    ),
    (
        "Italy", "IT", "ITA", "Rome", 41.8719, 12.5674, 110, "EUR", "Italian",
        "spring,autumn",
        "Italy is a living museum of Western civilization — ancient ruins, Renaissance art, "
        "Baroque architecture, and the finest cuisine in the world.",
        [
            "ancient-ruins", "art-museums", "roman-history", "michelin-restaurants",
            "wine-vineyards", "gothic-architecture", "modernist-architecture",
            "cooking-classes", "street-food", "local-festivals", "sandy-beaches",
            "hidden-coves", "opera-classical", "guided-walking-tours", "fish-markets",
        ],
    ),
    (
        "Spain", "ES", "ESP", "Madrid", 40.4168, -3.7038, 100, "EUR", "Spanish",
        "spring,summer,autumn",
        "Spain captivates with flamenco rhythms, Moorish palaces, avant-garde cuisine, "
        "and some of Europe's most vibrant nightlife and beaches.",
        [
            "art-museums", "contemporary-art", "street-food", "michelin-restaurants",
            "techno-clubs", "beach-clubs", "sandy-beaches", "hidden-coves",
            "modernist-architecture", "local-festivals", "wine-vineyards",
            "flamenco", "guided-walking-tours", "rooftop-bars", "surfing-kitesurfing",
        ],
    ),
    (
        "Germany", "DE", "DEU", "Berlin", 51.1657, 10.4515, 105, "EUR", "German",
        "spring,summer,autumn",
        "Germany offers medieval castles, cutting-edge techno clubs, world-famous beer culture, "
        "Christmas markets, and the Alps for skiing and hiking.",
        [
            "castles-palaces", "techno-clubs", "craft-beer", "christmas-markets",
            "wwii-history", "modernist-architecture", "brutalist-architecture",
            "music-festivals", "cycling-biking", "science-museums", "street-art",
            "skiing", "pop-up-events", "farmers-markets", "tech-hubs",
        ],
    ),
    (
        "United Kingdom", "GB", "GBR", "London", 55.3781, -3.4360, 130, "GBP", "English",
        "spring,summer",
        "The UK combines iconic landmarks, world-leading museums, diverse street food scenes, "
        "legendary pub culture, and dramatic Scottish Highlands.",
        [
            "art-museums", "history-museums", "theater-musicals", "stand-up-comedy",
            "pub-crawls", "craft-beer", "street-food", "thrifting-vintage",
            "castles-palaces", "national-parks", "coastal-walks", "science-museums",
            "music-festivals", "rooftop-bars", "guided-walking-tours",
        ],
    ),
    (
        "Portugal", "PT", "PRT", "Lisbon", 39.3999, -8.2245, 90, "EUR", "Portuguese",
        "spring,summer,autumn",
        "Portugal charms with melancholic Fado music, azulejo-tiled buildings, "
        "world-class surf, and Atlantic seafood culture.",
        [
            "surfing-kitesurfing", "sandy-beaches", "hidden-coves", "wine-vineyards",
            "street-food", "fish-markets", "local-festivals", "coastal-walks",
            "modernist-architecture", "guided-walking-tours", "tram-rides",
            "rooftop-bars", "specialty-coffee", "thrifting-vintage", "scenic-drives",
        ],
    ),
    (
        "Netherlands", "NL", "NLD", "Amsterdam", 52.1326, 5.2913, 115, "EUR", "Dutch",
        "spring,summer",
        "The Netherlands enchants with tulip fields, canal networks, cycling culture, "
        "world-class museums, and a famously liberal urban scene.",
        [
            "cycling-biking", "canal-river-cruises", "art-museums", "science-museums",
            "craft-beer", "street-food", "rooftop-bars", "pub-crawls",
            "botanic-gardens", "thrifting-vintage", "farmers-markets",
            "tech-hubs", "pop-up-events", "specialty-coffee", "local-festivals",
        ],
    ),
    (
        "Greece", "GR", "GRC", "Athens", 39.0742, 21.8243, 85, "EUR", "Greek",
        "spring,summer,autumn",
        "Greece is the cradle of Western civilization — ancient ruins, crystal-clear Aegean waters, "
        "vibrant nightlife, and exceptional Mediterranean cuisine.",
        [
            "ancient-ruins", "roman-history", "sandy-beaches", "hidden-coves",
            "snorkeling-diving", "street-food", "wine-vineyards", "local-festivals",
            "sailing", "beach-clubs", "scenic-drives", "fish-markets",
            "guided-walking-tours", "rooftop-views", "photography-landscapes",
        ],
    ),
    (
        "Austria", "AT", "AUT", "Vienna", 47.5162, 14.5501, 115, "EUR", "German",
        "winter,spring,summer",
        "Austria offers imperial palaces, world-class classical music, alpine skiing, "
        "and a café culture that UNESCO has recognized as intangible heritage.",
        [
            "skiing", "snowshoeing", "castles-palaces", "opera-classical",
            "art-museums", "craft-cocktail-bars", "wine-bars", "thermal-baths",
            "cycling-biking", "hiking", "modernist-architecture", "christmas-markets",
            "guided-walking-tours", "boutique-hotels", "scenic-train-rides",
        ],
    ),
    (
        "Switzerland", "CH", "CHE", "Bern", 46.8182, 8.2275, 200, "CHF", "German/French/Italian",
        "winter,summer",
        "Switzerland combines the highest peaks in Europe, pristine lakes, luxury resorts, "
        "and a unique multilingual culture with impeccable precision.",
        [
            "skiing", "snowshoeing", "alpine-climbing", "via-ferrata",
            "scenic-train-rides", "luxury-spa", "boutique-hotels", "all-inclusive-resorts",
            "cycling-biking", "paragliding", "hot-air-balloon", "photography-landscapes",
            "chocolate-culture", "watches-shopping", "thermal-baths",
        ],
    ),
    (
        "Norway", "NO", "NOR", "Oslo", 60.4720, 8.4689, 180, "NOK", "Norwegian",
        "summer,winter",
        "Norway is the land of fjords, the midnight sun, Northern Lights, and Viking heritage, "
        "offering some of the world's most dramatic natural scenery.",
        [
            "northern-lights", "fjords", "national-parks", "hiking",
            "multi-day-trekking", "kayaking-canoeing", "wildlife-watching",
            "snowmobile", "birdwatching", "scenic-train-rides", "coastal-walks",
            "photography-landscapes", "stargazing", "sailing", "camping",
        ],
    ),
    (
        "Sweden", "SE", "SWE", "Stockholm", 60.1282, 18.6435, 150, "SEK", "Swedish",
        "summer,winter",
        "Sweden blends Viking history, innovative design culture, vast wilderness, "
        "and a progressive urban scene with exceptional food.",
        [
            "northern-lights", "national-parks", "wildlife-watching", "kayaking-canoeing",
            "cycling-biking", "design-weeks", "tech-hubs", "street-food",
            "specialty-coffee", "thrifting-vintage", "art-museums", "skiing",
            "forest-bathing", "stargazing", "camping",
        ],
    ),
    (
        "Denmark", "DK", "DNK", "Copenhagen", 56.2639, 9.5018, 160, "DKK", "Danish",
        "spring,summer",
        "Denmark is famed for hygge culture, New Nordic cuisine, cutting-edge architecture, "
        "and a cycling-friendly urban lifestyle.",
        [
            "cycling-biking", "michelin-restaurants", "street-food", "specialty-coffee",
            "contemporary-architecture", "design-weeks", "craft-beer",
            "thrifting-vintage", "canal-river-cruises", "art-museums",
            "tech-hubs", "rooftop-bars", "farmers-markets", "science-museums",
        ],
    ),
    (
        "Finland", "FI", "FIN", "Helsinki", 61.9241, 25.7482, 155, "EUR", "Finnish",
        "summer,winter",
        "Finland offers the purest nature in Europe — thousands of lakes, dense forests, "
        "reindeer safaris, and the authentic sauna culture.",
        [
            "northern-lights", "stargazing", "national-parks", "wildlife-watching",
            "snowmobile", "kayaking-canoeing", "thermal-baths", "forest-bathing",
            "silence-retreats", "digital-detox", "birdwatching", "fishing",
            "design-weeks", "specialty-coffee",
        ],
    ),
    (
        "Poland", "PL", "POL", "Warsaw", 51.9194, 19.1451, 65, "PLN", "Polish",
        "spring,summer,autumn",
        "Poland surprises with beautifully restored medieval cities, moving WWII history, "
        "a booming craft beer scene, and one of Europe's best nightlife scenes in Warsaw.",
        [
            "wwii-history", "castles-palaces", "craft-beer", "street-food",
            "techno-clubs", "pub-crawls", "history-museums", "guided-walking-tours",
            "local-festivals", "thrifting-vintage", "street-art", "traditional-crafts",
            "cycling-biking", "jazz-live-music",
        ],
    ),
    (
        "Czech Republic", "CZ", "CZE", "Prague", 49.8175, 15.4730, 70, "CZK", "Czech",
        "spring,summer,autumn",
        "Czech Republic is home to Prague, one of Europe's most beautiful medieval cities, "
        "alongside world-famous Pilsner beer culture and stunning Bohemian castles.",
        [
            "castles-palaces", "craft-beer", "gothic-architecture", "pub-crawls",
            "guided-walking-tours", "street-food", "local-festivals", "jazz-live-music",
            "history-museums", "theater-musicals", "traditional-crafts",
            "day-hiking", "cycling-biking", "street-art",
        ],
    ),
    (
        "Hungary", "HU", "HUN", "Budapest", 47.1625, 19.5033, 60, "HUF", "Hungarian",
        "spring,summer,autumn",
        "Hungary enchants with Budapest's grand thermal baths, ruin bars, Jewish quarter, "
        "and the sweeping Danube riverfront.",
        [
            "thermal-baths", "ruin-bars", "craft-beer", "wine-vineyards",
            "gothic-architecture", "opera-classical", "local-festivals",
            "street-food", "guided-walking-tours", "cycling-biking",
            "jazz-live-music", "history-museums", "pub-crawls",
        ],
    ),
    (
        "Romania", "RO", "ROU", "Bucharest", 45.9432, 24.9668, 50, "RON", "Romanian",
        "spring,summer,autumn",
        "Romania hides medieval castles, painted monasteries, the Carpathian Mountains, "
        "and the Danube Delta — one of Europe's wildest ecosystems.",
        [
            "castles-palaces", "national-parks", "wildlife-watching", "birdwatching",
            "skiing", "day-hiking", "multi-day-trekking", "traditional-crafts",
            "folk-traditions", "wine-vineyards", "guided-walking-tours",
            "wwii-history", "cycling-biking", "community-experiences",
        ],
    ),
    (
        "Croatia", "HR", "HRV", "Zagreb", 45.1000, 15.2000, 80, "EUR", "Croatian",
        "spring,summer,autumn",
        "Croatia's Adriatic coast offers crystal-clear waters, medieval walled cities, "
        "stunning national parks, and a booming sailing culture.",
        [
            "sandy-beaches", "hidden-coves", "sailing", "snorkeling-diving",
            "national-parks", "castles-palaces", "guided-walking-tours",
            "local-festivals", "wine-vineyards", "kayaking-canoeing",
            "street-food", "fish-markets", "beach-clubs",
        ],
    ),
    (
        "Slovenia", "SI", "SVN", "Ljubljana", 46.1512, 14.9955, 85, "EUR", "Slovenian",
        "spring,summer,autumn",
        "Slovenia packs alpine lakes, Karst caves, wine regions, and a charming capital "
        "into one of Europe's most compact and accessible countries.",
        [
            "day-hiking", "alpine-climbing", "caving-spelunking", "kayaking-canoeing",
            "cycling-biking", "wine-vineyards", "skiing", "national-parks",
            "guided-walking-tours", "thermal-baths", "scenic-drives",
            "photography-landscapes", "local-festivals",
        ],
    ),
    (
        "Iceland", "IS", "ISL", "Reykjavik", 64.9631, -19.0208, 220, "ISK", "Icelandic",
        "summer,winter",
        "Iceland is the land of fire and ice — volcanic landscapes, geysers, glaciers, "
        "whale watching, and the most spectacular Northern Lights in the world.",
        [
            "northern-lights", "stargazing", "glaciers", "hot-springs-outdoor",
            "wildlife-watching", "whale-watching", "photography-landscapes",
            "multi-day-trekking", "kayaking-canoeing", "snowmobile",
            "atv-offroad", "scenic-drives", "digital-detox", "camping",
        ],
    ),
    (
        "Ireland", "IE", "IRL", "Dublin", 53.1424, -7.6921, 120, "EUR", "English/Irish",
        "spring,summer",
        "Ireland offers dramatic Atlantic cliffs, ancient Celtic heritage, legendary pub culture, "
        "and a storytelling tradition unlike anywhere else in Europe.",
        [
            "pub-crawls", "craft-beer", "coastal-walks", "national-parks",
            "castles-palaces", "guided-walking-tours", "folk-traditions",
            "local-festivals", "stand-up-comedy", "wildlife-watching",
            "scenic-drives", "day-hiking", "community-experiences",
        ],
    ),
    (
        "Belgium", "BE", "BEL", "Brussels", 50.5039, 4.4699, 110, "EUR", "French/Dutch",
        "spring,summer",
        "Belgium is famous for its medieval city centers, extraordinary comic book culture, "
        "craft beer diversity, chocolate artisans, and the EU's cosmopolitan capital.",
        [
            "craft-beer", "chocolate-culture", "gothic-architecture", "art-museums",
            "street-food", "waffles-culture", "guided-walking-tours", "cycling-biking",
            "local-festivals", "comic-art", "flea-markets", "jazz-live-music",
            "michelin-restaurants", "contemporary-art",
        ],
    ),
    (
        "Bulgaria", "BG", "BGR", "Sofia", 42.7339, 25.4858, 45, "BGN", "Bulgarian",
        "spring,summer,autumn",
        "Bulgaria offers ancient Thracian treasures, Black Sea beaches, ski resorts, "
        "rose valleys, and an emerging urban scene in Sofia.",
        [
            "sandy-beaches", "skiing", "ancient-ruins", "national-parks",
            "wine-vineyards", "thermal-baths", "traditional-crafts", "folk-traditions",
            "hiking", "orthodox-churches", "street-food", "wildlife-watching",
        ],
    ),
    (
        "Serbia", "RS", "SRB", "Belgrade", 44.0165, 21.0059, 45, "RSD", "Serbian",
        "spring,summer,autumn",
        "Serbia's Belgrade is one of Europe's most underrated party capitals, "
        "with legendary floating clubs (splavovi), a rich Orthodox heritage, and vibrant café culture.",
        [
            "techno-clubs", "beach-clubs", "craft-beer", "street-food",
            "jazz-live-music", "guided-walking-tours", "wwii-history",
            "local-festivals", "orthodox-churches", "wine-vineyards",
            "pub-crawls", "cycling-biking",
        ],
    ),
    (
        "Albania", "AL", "ALB", "Tirana", 41.1533, 20.1683, 35, "ALL", "Albanian",
        "spring,summer,autumn",
        "Albania is Europe's best-kept secret — pristine Albanian Riviera beaches, "
        "Ottoman bazaars, rugged mountain landscapes, and extraordinary hospitality.",
        [
            "sandy-beaches", "hidden-coves", "day-hiking", "multi-day-trekking",
            "ancient-ruins", "local-festivals", "community-experiences",
            "street-food", "traditional-crafts", "national-parks",
            "photography-landscapes", "digital-detox",
        ],
    ),
    (
        "Montenegro", "ME", "MNE", "Podgorica", 42.7087, 19.3744, 55, "EUR", "Montenegrin",
        "spring,summer,autumn",
        "Montenegro packs fjords, medieval walled cities, Orthodox monasteries, "
        "and Adriatic beaches into a tiny but breathtaking country.",
        [
            "sandy-beaches", "sailing", "kayaking-canoeing", "hiking",
            "castles-palaces", "national-parks", "orthodox-churches",
            "scenic-drives", "wine-vineyards", "hidden-coves",
        ],
    ),
    (
        "North Macedonia", "MK", "MKD", "Skopje", 41.6086, 21.7453, 35, "MKD", "Macedonian",
        "spring,summer,autumn",
        "North Macedonia offers the ancient city of Ohrid on a UNESCO lake, Ottoman bazaars, "
        "Byzantine churches, and dramatic mountain landscapes.",
        [
            "ancient-ruins", "orthodox-churches", "national-parks", "hiking",
            "local-festivals", "traditional-crafts", "community-experiences",
            "lake-swimming", "guided-walking-tours", "street-food",
        ],
    ),
    (
        "Bosnia and Herzegovina", "BA", "BIH", "Sarajevo", 43.9159, 17.6791, 40, "BAM", "Bosnian",
        "spring,summer,autumn",
        "Bosnia and Herzegovina is a land of contrasts — Ottoman bazaars next to Austro-Hungarian "
        "boulevards, medieval fortresses, and haunting WWII history in Sarajevo.",
        [
            "wwii-history", "guided-walking-tours", "traditional-crafts", "street-food",
            "local-festivals", "orthodox-churches", "hiking", "national-parks",
            "white-water-rafting", "community-experiences", "history-museums",
        ],
    ),
    (
        "Slovakia", "SK", "SVK", "Bratislava", 48.6690, 19.6990, 65, "EUR", "Slovak",
        "spring,summer,autumn",
        "Slovakia surprises with magnificent High Tatras mountains, numerous medieval castles, "
        "cave systems, and folk traditions still alive in rural villages.",
        [
            "castles-palaces", "skiing", "hiking", "caving-spelunking",
            "national-parks", "folk-traditions", "traditional-crafts",
            "craft-beer", "guided-walking-tours", "cycling-biking",
        ],
    ),
    (
        "Latvia", "LV", "LVA", "Riga", 56.8796, 24.6032, 70, "EUR", "Latvian",
        "spring,summer",
        "Latvia is home to Riga, one of Europe's finest Art Nouveau cities, "
        "alongside pristine Baltic Sea beaches, ancient forests, and a rich folk song tradition.",
        [
            "modernist-architecture", "art-museums", "sandy-beaches", "national-parks",
            "folk-traditions", "local-festivals", "craft-beer", "guided-walking-tours",
            "forest-bathing", "cycling-biking", "traditional-crafts",
        ],
    ),
    (
        "Lithuania", "LT", "LTU", "Vilnius", 55.1694, 23.8813, 65, "EUR", "Lithuanian",
        "spring,summer",
        "Lithuania's Vilnius boasts a magnificent Baroque old town, Hill of Crosses pilgrimage site, "
        "and the quirky self-proclaimed republic of Užupis.",
        [
            "gothic-architecture", "modernist-architecture", "art-museums", "local-festivals",
            "guided-walking-tours", "traditional-crafts", "folk-traditions",
            "national-parks", "cycling-biking", "street-art", "craft-beer",
        ],
    ),
    (
        "Estonia", "EE", "EST", "Tallinn", 58.5953, 25.0136, 75, "EUR", "Estonian",
        "spring,summer",
        "Estonia combines a perfectly preserved medieval old town in Tallinn, "
        "with digital innovation, boreal forests, and a vibrant design scene.",
        [
            "castles-palaces", "tech-hubs", "design-weeks", "national-parks",
            "cycling-biking", "guided-walking-tours", "local-festivals",
            "craft-beer", "specialty-coffee", "forest-bathing", "birdwatching",
        ],
    ),
    (
        "Ukraine", "UA", "UKR", "Kyiv", 48.3794, 31.1656, 30, "UAH", "Ukrainian",
        "spring,summer,autumn",
        "Ukraine possesses magnificent Baroque churches, Carpathian mountain villages, "
        "ancient Scythian burial mounds, and a rich folk art tradition.",
        [
            "orthodox-churches", "folk-traditions", "traditional-crafts", "hiking",
            "national-parks", "wwii-history", "local-festivals", "street-food",
            "guided-walking-tours", "community-experiences",
        ],
    ),
    (
        "Malta", "MT", "MLT", "Valletta", 35.9375, 14.3754, 95, "EUR", "Maltese/English",
        "spring,summer,autumn",
        "Malta packs 7,000 years of history into a tiny Mediterranean archipelago, "
        "with megalithic temples, crystal-clear diving spots, and Baroque grandeur.",
        [
            "ancient-ruins", "snorkeling-diving", "sandy-beaches", "hidden-coves",
            "castles-palaces", "guided-walking-tours", "sailing", "street-food",
            "photography-landscapes", "history-museums",
        ],
    ),
    (
        "Cyprus", "CY", "CYP", "Nicosia", 35.1264, 33.4299, 90, "EUR", "Greek/Turkish",
        "spring,summer,autumn",
        "Cyprus offers Aphrodite's mythical birthplace, Crusader castles, "
        "Troodos mountain villages, and some of the Mediterranean's warmest waters.",
        [
            "sandy-beaches", "ancient-ruins", "castles-palaces", "wine-vineyards",
            "hiking", "snorkeling-diving", "local-festivals", "traditional-crafts",
            "guided-walking-tours", "scenic-drives",
        ],
    ),
    (
        "Luxembourg", "LU", "LUX", "Luxembourg City", 49.8153, 6.1296, 150, "EUR", "Luxembourgish",
        "spring,summer",
        "Luxembourg is a fairy-tale Grand Duchy — medieval fortresses, deep river gorges, "
        "Moselle wine region, and a cosmopolitan capital disproportionate to its tiny size.",
        [
            "castles-palaces", "wine-vineyards", "cycling-biking", "guided-walking-tours",
            "michelin-restaurants", "contemporary-architecture", "art-museums",
        ],
    ),
    (
        "Moldova", "MD", "MDA", "Chișinău", 47.4116, 28.3699, 25, "MDL", "Romanian",
        "spring,summer,autumn",
        "Moldova is Europe's least-visited country, hiding extraordinary wine cellars "
        "(the world's largest underground wine city), monasteries carved into cliffs, and genuine rural hospitality.",
        [
            "wine-vineyards", "orthodox-churches", "traditional-crafts", "community-experiences",
            "folk-traditions", "guided-walking-tours", "local-festivals", "cycling-biking",
        ],
    ),
    (
        "Kosovo", "XK", "XKX", "Pristina", 42.6026, 20.9030, 30, "EUR", "Albanian",
        "spring,summer,autumn",
        "Kosovo is the Balkans' youngest nation, with a vibrant café culture, "
        "Ottoman mosques alongside Orthodox monasteries, and dramatic Rugova canyon landscapes.",
        [
            "guided-walking-tours", "community-experiences", "local-festivals",
            "traditional-crafts", "hiking", "street-food", "orthodox-churches",
        ],
    ),
]


# ─── UNSPLASH FETCH ────────────────────────────────────────────────────────────

def fetch_unsplash_image(query: str, access_key: str) -> tuple[str | None, str | None]:
    """Returnează (image_url, credit) sau (None, None) dacă lipsește cheia sau request eșuează."""
    if not access_key:
        return None, None
    try:
        resp = requests.get(
            "https://api.unsplash.com/search/photos",
            params={"query": query, "per_page": 1, "orientation": "landscape"},
            headers={"Authorization": f"Client-ID {access_key}"},
            timeout=10,
        )
        if resp.status_code == 200:
            results = resp.json().get("results", [])
            if results:
                photo = results[0]
                url = photo["urls"]["regular"]
                credit = photo["user"]["name"]
                return url, credit
    except Exception as e:
        print(f"    [WARN] Unsplash error for '{query}': {e}")
    return None, None


# ─── MAIN ─────────────────────────────────────────────────────────────────────

def main():
    db = SessionLocal()
    access_key = settings.UNSPLASH_ACCESS_KEY or ""

    if not access_key:
        print("[INFO] UNSPLASH_ACCESS_KEY lipsă — imaginile vor fi NULL (se pot adăuga ulterior)")

    print(f"Inserare {len(COUNTRIES)} țări europene...\n")

    inserted = 0
    skipped = 0

    for (name, iso2, iso3, capital, lat, lon, cost, currency, language,
         best_seasons, description, tag_slugs) in COUNTRIES:

        # Idempotent: sare dacă există deja
        existing = db.query(Country).filter(Country.iso2 == iso2).first()
        if existing:
            print(f"  [SKIP] {name} — există deja")
            skipped += 1
            continue

        # Fetch imagine Unsplash
        image_url, image_credit = None, None
        if access_key:
            image_url, image_credit = fetch_unsplash_image(
                f"{name} travel landscape", access_key
            )
            time.sleep(0.3)  # rate limiting

        country = Country(
            name=name,
            iso2=iso2,
            iso3=iso3,
            capital=capital,
            latitude=lat,
            longitude=lon,
            avg_cost_per_day=cost,
            currency=currency,
            language=language,
            best_seasons=best_seasons,
            description=description,
            image_url=image_url,
            image_credit=image_credit,
        )
        db.add(country)
        db.flush()  # obține ID

        # Asociere taguri
        tags_added = 0
        for slug in tag_slugs:
            tag = db.query(Tag).filter(Tag.slug == slug).first()
            if tag:
                db.execute(
                    country_tags.insert().values(
                        country_id=country.id,
                        tag_id=tag.id,
                        score=1.0,
                    )
                )
                tags_added += 1
            else:
                print(f"    [WARN] Tag slug '{slug}' not found for {name}")

        db.commit()
        print(f"  [+] {name} ({iso2}) — {tags_added} taguri")
        inserted += 1

    print(f"\n{'═'*50}")
    print(f"  Țări inserate:  {inserted}")
    print(f"  Țări sărite:    {skipped}")
    print(f"  TOTAL în DB:    {db.query(Country).count()}")
    print(f"{'═'*50}")

    db.close()


if __name__ == "__main__":
    main()