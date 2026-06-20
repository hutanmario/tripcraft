"""
seed_questions.py
=================
Seeduiește toate întrebările de clarificare în DB.

Tipuri:
- mandatory: buget, sezon, travel_style (mereu puse)
- gap: pentru categorii L1 neexplorate
- conflict: generate din tag_conflicts (automat)
- ambiguity: generate dinamic (nu se seeduiesc, sunt calculate)

Rulare:
    cd backend
    venv\Scripts\python.exe data/seed_questions.py
"""

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.database import SessionLocal
from app.models.question import Question, QuestionOption, option_tags
from app.models.destination import Tag
from sqlalchemy import text

# ─── DATE ÎNTREBĂRI ───────────────────────────────────────────────────────────
# Format:
# {
#   "id": slug unic,
#   "tag_slug": tagul L1 asociat (sau None pentru mandatory),
#   "type": "single",
#   "source": "mandatory" | "gap" | "lifestyle",
#   "question_text": "...",
#   "options": [
#     {"value": "...", "label": "...", "tag_weights": {"slug": weight, ...}},
#   ]
# }

QUESTIONS = [

    # ══════════════════════════════════════════════════════════════════════════
    # MANDATORY — mereu puse la finalul clarify
    # ══════════════════════════════════════════════════════════════════════════

    {
        "id": "budget",
        "tag_slug": None,
        "source": "mandatory",
        "question_text": "Care este bugetul tău mediu pe zi?",
        "options": [
            {"value": "budget", "label": "Economic — sub 50€/zi",
             "tag_weights": {}},
            {"value": "mid",    "label": "Mediu — între 50 și 150€/zi",
             "tag_weights": {}},
            {"value": "luxury", "label": "Luxury — peste 150€/zi",
             "tag_weights": {"luxury-spa": 0.4, "michelin-restaurants": 0.4,
                             "boutique-hotels": 0.4, "luxury-shopping": 0.3}},
        ],
    },

    {
        "id": "season",
        "tag_slug": None,
        "source": "mandatory",
        "question_text": "În ce perioadă preferi să călătorești?",
        "options": [
            {"value": "spring", "label": "Primăvară",
             "tag_weights": {"local-festivals": 0.3, "cycling-biking": 0.3,
                             "botanic-gardens": 0.3}},
            {"value": "summer", "label": "Vară",
             "tag_weights": {"sandy-beaches": 0.4, "beach-clubs": 0.4,
                             "sailing": 0.3, "hidden-coves": 0.3}},
            {"value": "autumn", "label": "Toamnă",
             "tag_weights": {"wine-vineyards": 0.4, "hiking": 0.3,
                             "local-festivals": 0.3}},
            {"value": "winter", "label": "Iarnă",
             "tag_weights": {"skiing": 0.5, "northern-lights": 0.4,
                             "christmas-markets": 0.4, "thermal-baths": 0.3}},
            {"value": "any",    "label": "Orice perioadă",
             "tag_weights": {}},
        ],
    },

    {
        "id": "travel_style",
        "tag_slug": None,
        "source": "mandatory",
        "question_text": "Cu cine călătorești de obicei?",
        "options": [
            {"value": "solo",   "label": "Solo",
             "tag_weights": {"digital-detox": 0.2, "meditation-centers": 0.2,
                             "pub-crawls": 0.2}},
            {"value": "couple", "label": "În cuplu",
             "tag_weights": {"boutique-hotels": 0.3, "michelin-restaurants": 0.3,
                             "wine-vineyards": 0.2, "sailing": 0.2}},
            {"value": "family", "label": "Cu familia (copii)",
             "tag_weights": {"theme-parks": 0.5, "zoos-aquariums": 0.4,
                             "child-beaches": 0.4, "all-inclusive-resorts": 0.3}},
            {"value": "group",  "label": "Cu prietenii",
             "tag_weights": {"techno-clubs": 0.3, "beach-clubs": 0.3,
                             "pub-crawls": 0.3, "music-festivals": 0.3}},
        ],
    },

    # ══════════════════════════════════════════════════════════════════════════
    # GAP — categorii L1 neexplorate
    # ══════════════════════════════════════════════════════════════════════════

    {
        "id": "gap_nature-outdoors",
        "tag_slug": "nature-outdoors",
        "source": "gap",
        "question_text": "Cât de mult te atrage natura și activitățile în aer liber?",
        "options": [
            {"value": "love", "label": "Mult — drumeții, peisaje, aventură în natură",
             "tag_weights": {"nature-outdoors": 0.8, "hiking-trekking": 0.6,
                             "national-parks": 0.5, "wildlife-watching": 0.4}},
            {"value": "sometimes", "label": "Uneori, dacă destinația o permite",
             "tag_weights": {"nature-outdoors": 0.3, "scenic-drives": 0.3}},
            {"value": "no", "label": "Prefer orașul și activitățile indoor",
             "tag_weights": {"urban-modern": 0.3}},
        ],
    },

    {
        "id": "gap_nightlife-social",
        "tag_slug": "nightlife-social",
        "source": "gap",
        "question_text": "Viața de noapte contează în vacanța ta?",
        "options": [
            {"value": "essential", "label": "Da — cluburi, baruri, energie urbană nocturnă",
             "tag_weights": {"nightlife-social": 0.8, "techno-clubs": 0.5,
                             "bar-scene": 0.5, "rooftop-bars": 0.4}},
            {"value": "sometimes", "label": "O seară sau două, da",
             "tag_weights": {"nightlife-social": 0.3, "jazz-live-music": 0.3,
                             "rooftop-bars": 0.2}},
            {"value": "no", "label": "Nu — prefer relaxare sau cultură seara",
             "tag_weights": {"wellness-slow": 0.2, "opera-classical": 0.2}},
        ],
    },

    {
        "id": "gap_food-drink",
        "tag_slug": "food-drink",
        "source": "gap",
        "question_text": "Gastronomia locală e o prioritate pentru tine?",
        "options": [
            {"value": "yes", "label": "Absolut — mănânc local, vizitez piețe, iau cursuri",
             "tag_weights": {"food-drink": 0.8, "street-food": 0.5,
                             "food-tours-guided": 0.5, "cooking-classes": 0.4,
                             "farmers-markets": 0.4}},
            {"value": "somewhat", "label": "Îmi place mâncarea bună dar nu e prioritatea #1",
             "tag_weights": {"food-drink": 0.3, "michelin-restaurants": 0.2}},
            {"value": "no", "label": "Nu, mâncarea e secundară în vacanță",
             "tag_weights": {}},
        ],
    },

    {
        "id": "gap_wellness-slow",
        "tag_slug": "wellness-slow",
        "source": "gap",
        "question_text": "Cauți relaxare și wellness în vacanță?",
        "options": [
            {"value": "yes", "label": "Da — spa, băi termale, ritm lent, retreat",
             "tag_weights": {"wellness-slow": 0.8, "thermal-baths": 0.6,
                             "luxury-spa": 0.5, "yoga-retreats": 0.4,
                             "forest-bathing": 0.3}},
            {"value": "sometimes", "label": "Un mix de activitate și relaxare",
             "tag_weights": {"wellness-slow": 0.3, "thermal-baths": 0.2}},
            {"value": "no", "label": "Nu — prefer ritmul alert și aventura",
             "tag_weights": {"adventure-active": 0.3}},
        ],
    },

    {
        "id": "gap_culture-history",
        "tag_slug": "culture-history",
        "source": "gap",
        "question_text": "Cultura și istoria te fascinează în călătorii?",
        "options": [
            {"value": "yes", "label": "Da — muzee, ruine, arhitectură, tururi ghidate",
             "tag_weights": {"culture-history": 0.8, "ancient-ruins": 0.5,
                             "art-museums": 0.5, "guided-walking-tours": 0.4,
                             "history-museums": 0.4}},
            {"value": "somewhat", "label": "Câteodată, dacă e ceva spectaculos",
             "tag_weights": {"culture-history": 0.3, "castles-palaces": 0.2}},
            {"value": "no", "label": "Nu în mod special",
             "tag_weights": {}},
        ],
    },

    {
        "id": "gap_adventure-active",
        "tag_slug": "adventure-active",
        "source": "gap",
        "question_text": "Sporturile și aventura fac parte din vacanța ta ideală?",
        "options": [
            {"value": "yes", "label": "Da — escaladă, surfing, rafting, sporturi extreme",
             "tag_weights": {"adventure-active": 0.8, "rock-climbing": 0.5,
                             "white-water-rafting": 0.5, "surfing-kitesurfing": 0.4,
                             "paragliding": 0.4}},
            {"value": "somewhat", "label": "Activități moderate — ciclism, hiking ușor",
             "tag_weights": {"adventure-active": 0.3, "cycling-biking": 0.4,
                             "day-hiking": 0.3}},
            {"value": "no", "label": "Nu, prefer activitățile relaxante",
             "tag_weights": {"wellness-slow": 0.2}},
        ],
    },

    {
        "id": "gap_urban-modern",
        "tag_slug": "urban-modern",
        "source": "gap",
        "question_text": "Te atrage viața urbană modernă și cultura contemporană?",
        "options": [
            {"value": "yes", "label": "Da — street art, design, shopping, pop-up events",
             "tag_weights": {"urban-modern": 0.8, "street-art": 0.5,
                             "design-weeks": 0.5, "contemporary-art": 0.4,
                             "pop-up-events": 0.4}},
            {"value": "somewhat", "label": "Îmi place să explorez cartierele creative",
             "tag_weights": {"urban-modern": 0.3, "thrifting-vintage": 0.3}},
            {"value": "no", "label": "Prefer natura sau destinațiile istorice",
             "tag_weights": {"nature-outdoors": 0.2, "culture-history": 0.2}},
        ],
    },

    # ══════════════════════════════════════════════════════════════════════════
    # LIFESTYLE — întrebări suplimentare de rafinare
    # ══════════════════════════════════════════════════════════════════════════

    {
        "id": "lifestyle_transport",
        "tag_slug": None,
        "source": "lifestyle",
        "question_text": "Cum preferi să te deplasezi în vacanță?",
        "options": [
            {"value": "walking", "label": "Pe jos — explorez lent, fiecare stradă",
             "tag_weights": {"guided-walking-tours": 0.4, "countryside-walks": 0.4,
                             "coastal-walks": 0.3}},
            {"value": "cycling", "label": "Cu bicicleta — activ și liber",
             "tag_weights": {"cycling-biking": 0.6, "canal-river-cruises": 0.2}},
            {"value": "scenic", "label": "Tren panoramic sau croazieră",
             "tag_weights": {"scenic-train-rides": 0.6, "canal-river-cruises": 0.5,
                             "cruises": 0.4}},
            {"value": "car", "label": "Cu mașina — rute proprii, flexibilitate",
             "tag_weights": {"scenic-drives": 0.5, "national-parks": 0.3}},
        ],
    },

    {
        "id": "lifestyle_accommodation",
        "tag_slug": None,
        "source": "lifestyle",
        "question_text": "Unde preferi să dormi în vacanță?",
        "options": [
            {"value": "boutique", "label": "Hotel boutique cu caracter local",
             "tag_weights": {"boutique-hotels": 0.6, "local-festivals": 0.2}},
            {"value": "luxury", "label": "Resort de lux sau all-inclusive",
             "tag_weights": {"all-inclusive-resorts": 0.6, "luxury-spa": 0.4}},
            {"value": "glamping", "label": "Glamping sau eco-lodge",
             "tag_weights": {"glamping": 0.6, "nature-outdoors": 0.3,
                             "digital-detox": 0.3}},
            {"value": "local", "label": "Airbnb sau cazare locală autentică",
             "tag_weights": {"community-experiences": 0.5, "local-festivals": 0.3,
                             "traditional-crafts": 0.2}},
        ],
    },

    {
        "id": "lifestyle_photography",
        "tag_slug": None,
        "source": "lifestyle",
        "question_text": "Fotografia face parte din experiența ta de călătorie?",
        "options": [
            {"value": "yes", "label": "Da — caut peisaje și momente perfecte",
             "tag_weights": {"photography-landscapes": 0.6, "instagram-spots": 0.5,
                             "rooftop-views": 0.4, "scenic-drives": 0.3}},
            {"value": "casual", "label": "Fac poze dar nu e o prioritate",
             "tag_weights": {"instagram-spots": 0.2}},
            {"value": "no", "label": "Nu, prefer să trăiesc momentul",
             "tag_weights": {}},
        ],
    },

    {
        "id": "lifestyle_social",
        "tag_slug": None,
        "source": "lifestyle",
        "question_text": "Îți place să interacționezi cu localnicii și cultura lor?",
        "options": [
            {"value": "yes", "label": "Da — îmi place să cunosc oameni și tradiții locale",
             "tag_weights": {"community-experiences": 0.6, "local-festivals": 0.5,
                             "traditional-crafts": 0.4, "folk-traditions": 0.4,
                             "cooking-classes": 0.3}},
            {"value": "somewhat", "label": "Câteodată, dacă se ivește ocazia",
             "tag_weights": {"local-festivals": 0.2, "guided-walking-tours": 0.2}},
            {"value": "no", "label": "Prefer intimitatea și liniștea",
             "tag_weights": {"digital-detox": 0.3, "silence-retreats": 0.3}},
        ],
    },
]


# ─── SEED ─────────────────────────────────────────────────────────────────────

def main():
    db = SessionLocal()

    # Cache taguri
    all_tags = {t.slug: t for t in db.query(Tag).all()}

    print(f"Seeduire {len(QUESTIONS)} întrebări...\n")
    inserted = skipped = 0

    for q_data in QUESTIONS:
        # Verifică dacă există deja
        existing = db.query(Question).filter(
            Question.question_text == q_data["question_text"]
        ).first()
        if existing:
            skipped += 1
            continue

        # Găsim tag-ul asociat
        tag = all_tags.get(q_data["tag_slug"]) if q_data["tag_slug"] else None

        # Creăm întrebarea
        question = Question(
            tag_id=tag.id if tag else list(all_tags.values())[0].id,
            question_text=q_data["question_text"],
            type=q_data.get("type", "single"),
            source=q_data["source"],
        )
        db.add(question)
        db.flush()

        # Creăm opțiunile
        for opt_data in q_data["options"]:
            option = QuestionOption(
                question_id=question.id,
                option_text=opt_data["label"],
                value=opt_data["value"],
            )
            db.add(option)
            db.flush()

            # Asociem tagurile cu weight
            for slug, weight in opt_data.get("tag_weights", {}).items():
                tag_obj = all_tags.get(slug)
                if tag_obj:
                    db.execute(
                        option_tags.insert().values(
                            option_id=option.id,
                            tag_id=tag_obj.id,
                            weight=weight,
                        )
                    )
                else:
                    print(f"    [WARN] Tag '{slug}' not found")

        db.commit()
        print(f"  [+] {q_data['id']} ({q_data['source']})")
        inserted += 1

    print(f"\n{'='*50}")
    print(f"  Inserate:  {inserted}")
    print(f"  Sarite:    {skipped}")
    print(f"  TOTAL DB:  {db.query(Question).count()}")
    print(f"{'='*50}")
    db.close()


if __name__ == "__main__":
    main()