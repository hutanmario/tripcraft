"""
seed_taxonomy.py
Construieste taxonomia ierarhica a tagurilor in DB.

Slug-urile pentru noduri interne au prefix:
  - root-XXX pentru root-uri
  - cat-XXX pentru categorii
ca sa evite coliziuni cu tagurile-frunze existente.

Reguli impuse de acest script:
  - Fiecare tag-frunza apare in EXACT O categorie (nu duplicate intre categorii).
  - UPDATE-ul foloseste garda "AND parent_id IS NULL" (first-wins) ca safety net:
    daca un tag a primit deja un parinte, nu il suprascrie.
  - Tagurile orfane din Grup 1 si Grup 2 sunt adoptate explicit in categorii.
  - Tagurile din Grup 3 (hiper-specifice, 1-4 destinatii) raman orfane intentionat.
"""

import os
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


# ---------------------------------------------------------------------------
# TAXONOMY
# Fiecare frunza apare in cel mult O categorie.
# Reguli pentru tagurile care apareau in mai multe categorii in versiunea veche:
#   beach       → cat-beach (activitate de natura, nu sezon)
#   summer      → cat-summer (sezon, nu activitate)
#   climbing    → cat-mountain (mai specific muntilor)
#   diving      → cat-water-activities (activitate acvatica)
#   sports      → cat-adventure (generic pentru adventure)
#   wine-tasting    → cat-gastronomy (gastronomie, nu sezon)
#   mediterranean   → cat-gastronomy (stil culinar/cultural)
#   wellness/spa    → cat-luxury-style (wellness = luxury, conform deciziei)
#   luxury          → cat-luxury-style (stil de calatorie, nu buget)
#
# cat-luxury-only (Budget) a ramas fara frunze dupa eliminarea lui luxury
# si a fost eliminata din taxonomie pentru a evita un nod gol in quiz.
# ---------------------------------------------------------------------------
TAXONOMY = {
    "root-city": {
        "name": "City",
        "icon": "city",
        "description": "Urban experiences and city breaks",
        "categories": {
            "cat-nightlife": {
                "name": "Nightlife",
                "icon": "nightlife",
                "question": "What is your perfect city evening?",
                "leaves": [
                    "nightlife", "music", "festivals",
                    "pubs",          # adoptat din orfane Grup 2
                ],
            },
            "cat-culture-history": {
                "name": "Culture and History",
                "icon": "culture",
                "question": "How do you want to engage with culture?",
                "leaves": [
                    "museums", "history", "culture", "art", "architecture",
                    "ancient-ruins", "castles", "unesco",
                    "religious",        # adoptat Grup 1 (63 dest)
                    "medieval",         # adoptat Grup 1 (56 dest)
                    "landmark",         # adoptat Grup 1 (22 dest)
                    "archaeology",      # adoptat Grup 1 (12 dest)
                    "literature",       # adoptat Grup 2 (6 dest)
                ],
            },
            "cat-gastronomy": {
                "name": "Gastronomy",
                "icon": "food",
                "question": "What flavors are you craving?",
                "leaves": [
                    "gastronomy", "street-food",
                    "wine-tasting",     # revenit la gastronomy (scos din cat-autumn)
                    "mediterranean",    # revenit la gastronomy (scos din cat-summer)
                    "beer",             # adoptat Grup 2 (6 dest)
                ],
            },
            "cat-shopping-modern": {
                "name": "Shopping and Modern",
                "icon": "shopping",
                "question": "What kind of urban experience attracts you?",
                "leaves": [
                    "shopping", "modern", "design",
                    "city-break",       # adoptat Grup 1 (168 dest)
                ],
            },
            "cat-local-experience": {
                "name": "Local Experience",
                "icon": "local",
                "question": "How do you want to connect locally?",
                "leaves": [
                    "local-culture", "traditional",
                    "multicultural",        # adoptat Grup 1 (50 dest)
                    "university-town",      # adoptat Grup 1 (25 dest)
                    "fishing-villages",     # adoptat Grup 2 (6 dest)
                    "village",              # adoptat Grup 1 (14 dest)
                ],
            },
        },
    },

    "root-nature": {
        "name": "Nature",
        "icon": "nature",
        "description": "Outdoors landscapes and wildlife",
        "categories": {
            "cat-beach": {
                "name": "Beach",
                "icon": "beach",
                "question": "What kind of beach experience?",
                "leaves": [
                    "beach",    # revenit la cat-beach (scos din cat-summer)
                    "island",   # adoptat Grup 1 (29 dest)
                ],
            },
            "cat-mountain": {
                "name": "Mountain",
                "icon": "mountain",
                "question": "How do you want to experience the mountains?",
                "leaves": [
                    "mountain", "hiking",
                    "climbing",     # revenit la cat-mountain (scos din cat-adventure)
                    "alpine",       # adoptat Grup 1 (36 dest)
                    "volcanic",     # adoptat Grup 1 (13 dest)
                    "fjords",       # adoptat Grup 1 (10 dest)
                ],
            },
            "cat-forest-wildlife": {
                "name": "Forest and Wildlife",
                "icon": "forest",
                "question": "What kind of wild nature attracts you?",
                "leaves": [
                    "nature", "wildlife", "national-park",
                    "forests",      # adoptat Grup 1 (15 dest)
                    "countryside",  # adoptat Grup 1 (34 dest)
                    "waterfalls",   # adoptat Grup 1 (10 dest)
                ],
            },
            "cat-water-activities": {
                "name": "Water Activities",
                "icon": "water",
                "question": "How do you want to interact with water?",
                "leaves": [
                    "lake",
                    "diving",   # revenit la cat-water-activities (scos din cat-adventure)
                    "river",    # adoptat Grup 1 (12 dest)
                    "canals",   # adoptat Grup 2 (9 dest)
                    "surfing",  # adoptat Grup 2 (5 dest)
                ],
            },
        },
    },

    "root-traveler-style": {
        "name": "Traveler Style",
        "icon": "star",
        "description": "Your travel personality",
        "categories": {
            "cat-romantic": {
                "name": "Romantic",
                "icon": "heart",
                "question": "What feels romantic to you?",
                "leaves": [
                    "romantic",
                    "thermal-springs",  # adoptat Grup 2 (8 dest); wellness/spa mutat la luxury
                ],
            },
            "cat-family-friendly": {
                "name": "Family-friendly",
                "icon": "family",
                "question": "What is important when traveling with family?",
                "leaves": ["family-friendly"],
            },
            "cat-adventure": {
                "name": "Adventure",
                "icon": "adventure",
                "question": "What kind of adventure?",
                "leaves": [
                    "adventure",
                    "sports",   # revenit la cat-adventure (scos din cat-water-activities)
                    "cycling",  # adoptat Grup 1 (78 dest)
                    # climbing si diving mutate la categoriile lor primare
                ],
            },
            "cat-offbeat": {
                "name": "Offbeat",
                "icon": "offbeat",
                "question": "How off-the-beaten-path do you want to go?",
                "leaves": [
                    "offbeat", "photography",
                    "unique-stays",  # adoptat Grup 1 (35 dest) — ajustat la offbeat
                ],
            },
            "cat-luxury-style": {
                "name": "Luxury Style",
                "icon": "luxury",
                "question": "What does luxury mean to you?",
                "leaves": [
                    "luxury",       # revenit la cat-luxury-style (scos din Budget)
                    "wellness/spa", # revenit la cat-luxury-style (ajustat fata de cat-romantic)
                    "spa",          # adoptat Grup 1 (15 dest) — ajustat la luxury-style
                ],
            },
        },
    },

    "root-season": {
        "name": "Season",
        "icon": "season",
        "description": "When you want to travel",
        "categories": {
            "cat-spring": {
                "name": "Spring",
                "icon": "spring",
                "question": "What spring vibes attract you?",
                "leaves": [
                    "spring", "flowers",
                    "mild-climate",  # nou in DB (adaugat inainte de seed)
                    "temperate",     # adoptat Grup 1 (306 dest) — climat temperat
                    "year-round",    # adoptat Grup 1 (288 dest) — accesibil tot anul
                ],
            },
            "cat-summer": {
                "name": "Summer",
                "icon": "summer",
                "question": "What is your ideal summer trip?",
                "leaves": [
                    "summer",   # beach si mediterranean mutate la categoriile lor
                    "warm",     # adoptat Grup 1 (111 dest)
                ],
            },
            "cat-autumn": {
                "name": "Autumn",
                "icon": "autumn",
                "question": "What autumn experiences attract you?",
                "leaves": [
                    "autumn",   # nou in DB
                    "foliage",  # nou in DB; wine-tasting mutat la gastronomy
                ],
            },
            "cat-winter": {
                "name": "Winter",
                "icon": "winter",
                "question": "What winter activities call to you?",
                "leaves": [
                    "winter", "skiing", "christmas-markets", "northern-lights",
                    "snow",     # nou in DB
                    "cold",     # adoptat Grup 1 (35 dest)
                ],
            },
        },
    },

    "root-budget": {
        "name": "Budget",
        "icon": "money",
        "description": "Your budget preference",
        "categories": {
            "cat-budget-friendly": {
                "name": "Budget-friendly",
                "icon": "budget",
                "question": "How budget-conscious are you?",
                "leaves": ["budget"],
            },
            "cat-mid-range": {
                "name": "Mid-range",
                "icon": "midrange",
                "question": "Mid-range comfort?",
                "leaves": ["mid-range"],
            },
            # cat-luxury-only eliminata: luxury mutat la cat-luxury-style (Traveler Style)
            # Un nod gol ar rupe quiz-ul (drill endpoint returneaza 400 daca nu are copii)
        },
    },
}


def main():
    conn = psycopg2.connect(**DB_CONFIG)
    cur = conn.cursor()

    # Incarca toate tag-urile frunza existente in DB (pentru lookup rapid)
    cur.execute("SELECT id, name FROM tags WHERE is_leaf = TRUE OR is_leaf IS NULL")
    existing_by_name = {row[1]: row[0] for row in cur.fetchall()}
    print(f"Taguri-frunze in DB: {len(existing_by_name)}")

    # Reseteaza toate legaturile parinte (forteaza reconstructie completa)
    # NOTA: nu stergem tagurile, doar parent_id
    cur.execute("UPDATE tags SET parent_id = NULL")
    conn.commit()

    # Sterge nodurile interne vechi (root + category) — vor fi recreate din TAXONOMY
    cur.execute("DELETE FROM tags WHERE is_leaf = FALSE")
    conn.commit()
    print("Noduri interne anterioare sterse, ierarhie resetata.")

    skipped_leaves = []
    created_roots = 0
    created_categories = 0
    linked_leaves = 0

    for root_slug, root_data in TAXONOMY.items():
        cur.execute(
            """
            INSERT INTO tags (name, slug, category, parent_id, is_leaf, description, icon)
            VALUES (%s, %s, %s, NULL, FALSE, %s, %s)
            RETURNING id
            """,
            (root_data["name"], root_slug, "root",
             root_data.get("description"), root_data.get("icon")),
        )
        root_id = cur.fetchone()[0]
        created_roots += 1

        for cat_slug, cat_data in root_data["categories"].items():
            cur.execute(
                """
                INSERT INTO tags (name, slug, category, parent_id, is_leaf, question_template, icon)
                VALUES (%s, %s, %s, %s, FALSE, %s, %s)
                RETURNING id
                """,
                (cat_data["name"], cat_slug, "category", root_id,
                 cat_data["question"], cat_data.get("icon")),
            )
            cat_id = cur.fetchone()[0]
            created_categories += 1

            for leaf_name in cat_data["leaves"]:
                if leaf_name not in existing_by_name:
                    skipped_leaves.append(leaf_name)
                    continue

                leaf_id = existing_by_name[leaf_name]
                # GARDA first-wins: nu suprascrie daca tag-ul a primit deja un parinte
                # (safety net — TAXONOMY e deja curatata de duplicate)
                cur.execute(
                    "UPDATE tags SET parent_id = %s, is_leaf = TRUE WHERE id = %s AND parent_id IS NULL",
                    (cat_id, leaf_id),
                )
                if cur.rowcount > 0:
                    linked_leaves += 1
                else:
                    print(f"  WARN first-wins skip: '{leaf_name}' deja are parinte")

    conn.commit()
    cur.close()
    conn.close()

    print()
    print("Done!")
    print(f"   Root noduri create:  {created_roots}")
    print(f"   Categorii create:    {created_categories}")
    print(f"   Frunze legate:       {linked_leaves}")
    if skipped_leaves:
        unique_skipped = sorted(set(skipped_leaves))
        print(f"   Frunze necunoscute (lipsa in DB): {unique_skipped}")


if __name__ == "__main__":
    main()
