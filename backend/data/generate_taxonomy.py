"""
generate_taxonomy.py
====================
Generează taxonomia completă de taguri în DB.

Structură: L1 (8 categorii) → L2 (~40 subcategorii) → L3 (~160 taguri frunză)

Rulare:
    cd backend
    python data/generate_taxonomy.py

Scriptul e idempotent: dacă un tag există deja (după slug), îl sare.
"""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.database import SessionLocal
from app.models.destination import Tag


# ─── TAXONOMIA COMPLETĂ ───────────────────────────────────────────────────────
# Format: (slug, name, parent_slug_or_None, is_leaf, question_template)
# L1: parent=None, is_leaf=False
# L2: parent=L1_slug, is_leaf=False
# L3: parent=L2_slug, is_leaf=True

TAXONOMY = [

    # ══════════════════════════════════════════════════════════════════════════
    # L1: NIGHTLIFE & SOCIAL
    # ══════════════════════════════════════════════════════════════════════════
    ("nightlife-social", "Nightlife & Social", None, False,
     "Ce tip de experiențe sociale îți plac cel mai mult?"),

    # L2
    ("clubbing", "Clubbing & Dance", "nightlife-social", False,
     "Ce tip de cluburi preferi?"),
    ("bar-scene", "Bar Scene", "nightlife-social", False,
     "Ce tip de baruri preferi?"),
    ("live-entertainment", "Live Entertainment", "nightlife-social", False,
     "Ce tip de spectacole live îți plac?"),
    ("social-tours", "Social Tours", "nightlife-social", False,
     "Preferi experiențele sociale organizate?"),
    ("gaming-entertainment", "Gaming & Casinos", "nightlife-social", False,
     "Ești interesat de gaming sau cazinouri?"),

    # L3 — Clubbing
    ("techno-clubs", "Techno & Electronic Clubs", "clubbing", True, None),
    ("beach-clubs", "Beach Clubs & Day Parties", "clubbing", True, None),
    ("rooftop-parties", "Rooftop Parties", "clubbing", True, None),
    ("underground-clubs", "Underground Clubs", "clubbing", True, None),

    # L3 — Bar Scene
    ("rooftop-bars", "Rooftop Bars", "bar-scene", True, None),
    ("craft-cocktail-bars", "Craft Cocktail Bars", "bar-scene", True, None),
    ("sports-bars", "Sports Bars", "bar-scene", True, None),
    ("speakeasy-bars", "Speakeasy & Hidden Bars", "bar-scene", True, None),
    ("wine-bars", "Wine Bars", "bar-scene", True, None),

    # L3 — Live Entertainment
    ("stand-up-comedy", "Stand-up Comedy", "live-entertainment", True, None),
    ("theater-musicals", "Theater & Musicals", "live-entertainment", True, None),
    ("jazz-live-music", "Jazz & Live Music Venues", "live-entertainment", True, None),
    ("cabaret", "Cabaret & Variety Shows", "live-entertainment", True, None),
    ("opera-classical", "Opera & Classical Concerts", "live-entertainment", True, None),

    # L3 — Social Tours
    ("pub-crawls", "Pub Crawls & Bar Hopping", "social-tours", True, None),
    ("food-social-tours", "Social Food Tours", "social-tours", True, None),
    ("meetup-events", "Meetups & Social Events", "social-tours", True, None),

    # L3 — Gaming & Casinos
    ("casinos", "Casinos", "gaming-entertainment", True, None),
    ("esports-arenas", "Esports & Gaming Arenas", "gaming-entertainment", True, None),
    ("arcade-bars", "Arcade Bars", "gaming-entertainment", True, None),


    # ══════════════════════════════════════════════════════════════════════════
    # L1: NATURE & OUTDOORS
    # ══════════════════════════════════════════════════════════════════════════
    ("nature-outdoors", "Nature & Outdoors", None, False,
     "Ce tip de experiențe în natură îți plac?"),

    # L2
    ("hiking-trekking", "Hiking & Trekking", "nature-outdoors", False,
     "Ce tip de drumeții preferi?"),
    ("winter-nature", "Winter & Snow", "nature-outdoors", False,
     "Îți plac activitățile de iarnă?"),
    ("beach-water", "Beach & Water", "nature-outdoors", False,
     "Preferi marea sau lacurile?"),
    ("wildlife-nature", "Wildlife & Ecosystems", "nature-outdoors", False,
     "Ești interesat de natură sălbatică?"),
    ("contemplative-nature", "Contemplative Nature", "nature-outdoors", False,
     "Îți plac experiențele contemplative în natură?"),

    # L3 — Hiking
    ("day-hiking", "Day Hiking", "hiking-trekking", True, None),
    ("multi-day-trekking", "Multi-day Trekking", "hiking-trekking", True, None),
    ("alpine-climbing", "Alpine & Summit Climbing", "hiking-trekking", True, None),
    ("via-ferrata", "Via Ferrata", "hiking-trekking", True, None),
    ("coastal-walks", "Coastal Walks & Cliffs", "hiking-trekking", True, None),

    # L3 — Winter
    ("skiing", "Skiing & Snowboarding", "winter-nature", True, None),
    ("snowshoeing", "Snowshoeing", "winter-nature", True, None),
    ("ice-skating", "Ice Skating", "winter-nature", True, None),
    ("northern-lights", "Northern Lights Hunting", "winter-nature", True, None),
    ("snowmobile", "Snowmobile & Arctic Tours", "winter-nature", True, None),

    # L3 — Beach & Water
    ("sandy-beaches", "Sandy Beaches", "beach-water", True, None),
    ("hidden-coves", "Hidden Coves & Lagoons", "beach-water", True, None),
    ("lake-swimming", "Lake Swimming & Rivers", "beach-water", True, None),
    ("snorkeling-diving", "Snorkeling & Diving", "beach-water", True, None),
    ("hot-springs-outdoor", "Outdoor Hot Springs", "beach-water", True, None),

    # L3 — Wildlife
    ("wildlife-watching", "Wildlife Watching", "wildlife-nature", True, None),
    ("birdwatching", "Birdwatching", "wildlife-nature", True, None),
    ("national-parks", "National Parks & Reserves", "wildlife-nature", True, None),
    ("foraging", "Foraging (Mushrooms, Truffles)", "wildlife-nature", True, None),
    ("botanic-gardens", "Botanic Gardens & Arboretums", "wildlife-nature", True, None),

    # L3 — Contemplative
    ("stargazing", "Stargazing & Astrotourism", "contemplative-nature", True, None),
    ("forest-bathing", "Forest Bathing (Shinrin-yoku)", "contemplative-nature", True, None),
    ("scenic-drives", "Scenic Drives & Viewpoints", "contemplative-nature", True, None),
    ("photography-landscapes", "Landscape Photography", "contemplative-nature", True, None),


    # ══════════════════════════════════════════════════════════════════════════
    # L1: CULTURE & HISTORY
    # ══════════════════════════════════════════════════════════════════════════
    ("culture-history", "Culture & History", None, False,
     "Ce aspect al culturii și istoriei te atrage?"),

    # L2
    ("historical-sites", "Historical Sites", "culture-history", False,
     "Ce tip de situri istorice preferi?"),
    ("arts-museums", "Arts & Museums", "culture-history", False,
     "Ești interesat de artă și muzee?"),
    ("living-culture", "Living Culture", "culture-history", False,
     "Îți plac experiențele culturale vii, interactive?"),
    ("architecture", "Architecture", "culture-history", False,
     "Te interesează arhitectura?"),

    # L3 — Historical Sites
    ("ancient-ruins", "Ancient Ruins & Archaeology", "historical-sites", True, None),
    ("castles-palaces", "Castles & Palaces", "historical-sites", True, None),
    ("religious-sites", "Religious Sites & Cathedrals", "historical-sites", True, None),
    ("wwii-history", "WWII & Modern History Sites", "historical-sites", True, None),
    ("roman-history", "Roman & Greek Heritage", "historical-sites", True, None),

    # L3 — Arts & Museums
    ("art-museums", "Art Museums & Galleries", "arts-museums", True, None),
    ("science-museums", "Science & Interactive Museums", "arts-museums", True, None),
    ("history-museums", "History & War Museums", "arts-museums", True, None),
    ("street-art", "Street Art & Murals", "arts-museums", True, None),
    ("contemporary-art", "Contemporary Art Spaces", "arts-museums", True, None),

    # L3 — Living Culture
    ("local-festivals", "Local Festivals & Celebrations", "living-culture", True, None),
    ("traditional-crafts", "Traditional Crafts & Workshops", "living-culture", True, None),
    ("guided-walking-tours", "Guided Historical Walking Tours", "living-culture", True, None),
    ("community-experiences", "Local Community Experiences", "living-culture", True, None),
    ("folk-traditions", "Folk Traditions & Dance", "living-culture", True, None),

    # L3 — Architecture
    ("gothic-architecture", "Gothic & Medieval Architecture", "architecture", True, None),
    ("modernist-architecture", "Modernist & Art Nouveau", "architecture", True, None),
    ("brutalist-architecture", "Brutalist & Soviet Architecture", "architecture", True, None),
    ("vernacular-architecture", "Vernacular & Traditional Architecture", "architecture", True, None),
    ("contemporary-architecture", "Contemporary Architecture", "architecture", True, None),


    # ══════════════════════════════════════════════════════════════════════════
    # L1: FOOD & DRINK
    # ══════════════════════════════════════════════════════════════════════════
    ("food-drink", "Food & Drink", None, False,
     "Ce experiențe culinare cauți în călătorii?"),

    # L2
    ("street-casual-food", "Street & Casual Food", "food-drink", False,
     "Îți plac experiențele culinare informale?"),
    ("fine-dining-exp", "Fine Dining", "food-drink", False,
     "Ești interesat de restaurante fine dining?"),
    ("drinks-tastings", "Drinks & Tastings", "food-drink", False,
     "Ce tipuri de degustări preferi?"),
    ("culinary-learning", "Culinary Learning", "food-drink", False,
     "Vrei să înveți să gătești preparate locale?"),
    ("food-markets", "Food Markets & Local Produce", "food-drink", False,
     "Îți plac piețele locale de alimente?"),

    # L3 — Street Food
    ("street-food", "Street Food Stalls", "street-casual-food", True, None),
    ("food-trucks", "Food Trucks & Pop-ups", "street-casual-food", True, None),
    ("local-tavernas", "Local Tavernas & Trattorias", "street-casual-food", True, None),
    ("bakeries-pastries", "Bakeries & Pastry Shops", "street-casual-food", True, None),

    # L3 — Fine Dining
    ("michelin-restaurants", "Michelin Star Restaurants", "fine-dining-exp", True, None),
    ("tasting-menus", "Tasting Menus & Chef Tables", "fine-dining-exp", True, None),
    ("farm-to-table", "Farm-to-Table & Agritourism", "fine-dining-exp", True, None),

    # L3 — Drinks
    ("wine-vineyards", "Wine & Vineyards", "drinks-tastings", True, None),
    ("craft-beer", "Craft Beer & Microbreweries", "drinks-tastings", True, None),
    ("distilleries", "Distilleries & Spirits Tasting", "drinks-tastings", True, None),
    ("specialty-coffee", "Specialty Coffee Culture", "drinks-tastings", True, None),
    ("tea-culture", "Tea Culture & Ceremonies", "drinks-tastings", True, None),

    # L3 — Culinary Learning
    ("cooking-classes", "Cooking Classes & Workshops", "culinary-learning", True, None),
    ("food-tours-guided", "Guided Food Tours", "culinary-learning", True, None),

    # L3 — Markets
    ("farmers-markets", "Farmers Markets", "food-markets", True, None),
    ("fish-markets", "Fish & Seafood Markets", "food-markets", True, None),
    ("spice-markets", "Spice & Specialty Markets", "food-markets", True, None),


    # ══════════════════════════════════════════════════════════════════════════
    # L1: ADVENTURE & ACTIVE
    # ══════════════════════════════════════════════════════════════════════════
    ("adventure-active", "Adventure & Active", None, False,
     "Ce activități sportive și de aventură preferi?"),

    # L2
    ("water-sports", "Water Sports", "adventure-active", False,
     "Ce sporturi nautice practici sau vrei să încerci?"),
    ("air-extreme-sports", "Air & Extreme Sports", "adventure-active", False,
     "Ești atras de sporturi extreme?"),
    ("land-sports", "Land Sports & Cycling", "adventure-active", False,
     "Ce sporturi terestre preferi?"),
    ("motor-sports", "Motor Sports & Off-road", "adventure-active", False,
     "Te interesează sporturile cu motor?"),
    ("rope-park-sports", "Rope Parks & Zip-lining", "adventure-active", False,
     "Îți plac parcurile de aventură?"),

    # L3 — Water Sports
    ("surfing-kitesurfing", "Surfing & Kitesurfing", "water-sports", True, None),
    ("kayaking-canoeing", "Kayaking & Canoeing", "water-sports", True, None),
    ("white-water-rafting", "White Water Rafting", "water-sports", True, None),
    ("sailing", "Sailing & Yachting", "water-sports", True, None),
    ("scuba-diving", "Scuba Diving", "water-sports", True, None),
    ("paddleboarding", "Paddleboarding (SUP)", "water-sports", True, None),

    # L3 — Air & Extreme
    ("paragliding", "Paragliding & Hang Gliding", "air-extreme-sports", True, None),
    ("skydiving", "Skydiving", "air-extreme-sports", True, None),
    ("bungee-jumping", "Bungee Jumping", "air-extreme-sports", True, None),
    ("base-jumping", "Base Jumping", "air-extreme-sports", True, None),
    ("hot-air-balloon", "Hot Air Balloon Rides", "air-extreme-sports", True, None),

    # L3 — Land Sports
    ("cycling-biking", "Cycling & Mountain Biking", "land-sports", True, None),
    ("rock-climbing", "Rock Climbing & Bouldering", "land-sports", True, None),
    ("caving-spelunking", "Caving & Spelunking", "land-sports", True, None),
    ("horseback-riding", "Horseback Riding", "land-sports", True, None),
    ("running-marathons", "Running & Marathons", "land-sports", True, None),

    # L3 — Motor Sports
    ("atv-offroad", "ATV & Off-road", "motor-sports", True, None),
    ("motorbike-tours", "Motorbike Tours", "motor-sports", True, None),
    ("go-karting", "Go-Karting", "motor-sports", True, None),

    # L3 — Rope Parks
    ("zip-lining", "Zip-lining", "rope-park-sports", True, None),
    ("rope-parks", "Rope Parks & Tree Climbing", "rope-park-sports", True, None),


    # ══════════════════════════════════════════════════════════════════════════
    # L1: WELLNESS & SLOW TRAVEL
    # ══════════════════════════════════════════════════════════════════════════
    ("wellness-slow", "Wellness & Slow Travel", None, False,
     "Ce tip de experiențe de relaxare și wellness cauți?"),

    # L2
    ("spa-thermal", "Spa & Thermal Baths", "wellness-slow", False,
     "Ești interesat de spa și băi termale?"),
    ("mindfulness-retreats", "Mindfulness & Retreats", "wellness-slow", False,
     "Te interesează retreat-urile?"),
    ("holistic-health", "Holistic & Alternative Health", "wellness-slow", False,
     "Ești interesat de terapii alternative?"),
    ("slow-scenic", "Slow & Scenic Travel", "wellness-slow", False,
     "Preferi călătoriile lente și contemplative?"),

    # L3 — Spa
    ("thermal-baths", "Thermal Baths & Hot Springs", "spa-thermal", True, None),
    ("luxury-spa", "Luxury Spa Resorts", "spa-thermal", True, None),
    ("hammam", "Hammam & Turkish Baths", "spa-thermal", True, None),
    ("float-tanks", "Float Tanks & Sensory Deprivation", "spa-thermal", True, None),

    # L3 — Mindfulness
    ("yoga-retreats", "Yoga Retreats", "mindfulness-retreats", True, None),
    ("meditation-centers", "Meditation Centers", "mindfulness-retreats", True, None),
    ("silent-retreats", "Silent Retreats (Vipassana)", "mindfulness-retreats", True, None),
    ("digital-detox", "Digital Detox & Off-grid Stays", "mindfulness-retreats", True, None),

    # L3 — Holistic
    ("ayurveda", "Ayurveda & Indian Medicine", "holistic-health", True, None),
    ("sound-therapy", "Sound Therapy & Crystal Healing", "holistic-health", True, None),
    ("acupuncture-tcm", "Acupuncture & TCM", "holistic-health", True, None),

    # L3 — Slow Travel
    ("scenic-train-rides", "Scenic Train Rides", "slow-scenic", True, None),
    ("countryside-walks", "Countryside & Village Walks", "slow-scenic", True, None),
    ("canal-river-cruises", "Canal & River Cruises", "slow-scenic", True, None),
    ("glamping", "Glamping & Eco Lodges", "slow-scenic", True, None),


    # ══════════════════════════════════════════════════════════════════════════
    # L1: URBAN & MODERN
    # ══════════════════════════════════════════════════════════════════════════
    ("urban-modern", "Urban & Modern", None, False,
     "Ce îți place din viața urbană și cultura modernă?"),

    # L2
    ("shopping-fashion", "Shopping & Fashion", "urban-modern", False,
     "Ce tip de shopping preferi?"),
    ("tech-innovation", "Tech & Innovation", "urban-modern", False,
     "Te interesează tehnologia și inovația?"),
    ("urban-culture", "Urban Culture & Events", "urban-modern", False,
     "Ce tipuri de evenimente urbane cauți?"),
    ("photography-urban", "Photography & Aesthetics", "urban-modern", False,
     "Ești pasionat de fotografie urbană?"),

    # L3 — Shopping
    ("luxury-shopping", "Luxury Boutiques & Malls", "shopping-fashion", True, None),
    ("thrifting-vintage", "Thrifting & Vintage Markets", "shopping-fashion", True, None),
    ("local-artisan-shops", "Local Artisan Shops", "shopping-fashion", True, None),
    ("flea-markets", "Flea Markets", "shopping-fashion", True, None),
    ("designer-districts", "Designer Districts", "shopping-fashion", True, None),

    # L3 — Tech
    ("tech-hubs", "Tech Hubs & Startup Spaces", "tech-innovation", True, None),
    ("factory-tours", "Factory & Industrial Tours", "tech-innovation", True, None),
    ("science-centers", "Science Centers & Planetariums", "tech-innovation", True, None),

    # L3 — Urban Culture
    ("pop-up-events", "Pop-up Events & Exhibitions", "urban-culture", True, None),
    ("film-festivals", "Film Festivals", "urban-culture", True, None),
    ("music-festivals", "Music Festivals", "urban-culture", True, None),
    ("design-weeks", "Design & Fashion Weeks", "urban-culture", True, None),
    ("graffiti-tours", "Graffiti & Urban Art Tours", "urban-culture", True, None),

    # L3 — Photography
    ("instagram-spots", "Iconic Photo Spots", "photography-urban", True, None),
    ("street-photography-spots", "Street Photography Districts", "photography-urban", True, None),
    ("rooftop-views", "Rooftop Views & Panoramas", "photography-urban", True, None),


    # ══════════════════════════════════════════════════════════════════════════
    # L1: FAMILY & COMFORT
    # ══════════════════════════════════════════════════════════════════════════
    ("family-comfort", "Family & Comfort", None, False,
     "Călătorești cu familia sau preferi confortul maxim?"),

    # L2
    ("family-attractions", "Family Attractions", "family-comfort", False,
     "Ce activități pentru familie cauți?"),
    ("comfort-accommodation", "Comfort & Accommodation", "family-comfort", False,
     "Ce tip de cazare preferi?"),
    ("easy-sightseeing", "Easy Sightseeing", "family-comfort", False,
     "Preferi turismul ușor și accesibil?"),
    ("child-activities", "Child-specific Activities", "family-comfort", False,
     "Ai copii mici în călătorie?"),

    # L3 — Family Attractions
    ("theme-parks", "Theme Parks & Amusement Parks", "family-attractions", True, None),
    ("zoos-aquariums", "Zoos & Aquariums", "family-attractions", True, None),
    ("science-interactive-museums", "Interactive Science Museums", "family-attractions", True, None),
    ("water-parks", "Water Parks", "family-attractions", True, None),

    # L3 — Comfort Accommodation
    ("all-inclusive-resorts", "All-inclusive Resorts", "comfort-accommodation", True, None),
    ("boutique-hotels", "Boutique Hotels", "comfort-accommodation", True, None),
    ("glamping-family", "Family Glamping", "comfort-accommodation", True, None),
    ("cruises", "Cruises & Boat Tours", "comfort-accommodation", True, None),

    # L3 — Easy Sightseeing
    ("hop-on-hop-off", "Hop-on Hop-off Bus Tours", "easy-sightseeing", True, None),
    ("scenic-cable-cars", "Scenic Cable Cars & Funiculars", "easy-sightseeing", True, None),
    ("guided-group-tours", "Guided Group Tours", "easy-sightseeing", True, None),
    ("accessible-attractions", "Accessible & Barrier-free Sites", "easy-sightseeing", True, None),

    # L3 — Child Activities
    ("petting-zoos", "Petting Zoos & Farm Stays", "child-activities", True, None),
    ("playgrounds-parks", "Playgrounds & City Parks", "child-activities", True, None),
    ("kids-workshops", "Kids Workshops & Crafts", "child-activities", True, None),
    ("child-beaches", "Child-friendly Beaches", "child-activities", True, None),
]


# ─── CONFLICT PAIRS ───────────────────────────────────────────────────────────
# Perechi de taguri care generează întrebări de clarificare în quiz.
# Format: (slug_a, slug_b, question_ro, options)
CONFLICT_PAIRS = [
    ("skiing", "sandy-beaches",
     "Preferi vacanțele de iarnă sau de vară?",
     ["Iarnă — îmi plac zăpada și sporturile de iarnă",
      "Vară — plajă, soare și mare",
      "Ambele, în funcție de perioadă"]),

    ("techno-clubs", "silent-retreats",
     "Cauți energie și agitație sau liniște și relaxare?",
     ["Energie — distracție, muzică, oameni",
      "Liniște — retreat, natură, pace",
      "Un mix echilibrat"]),

    ("michelin-restaurants", "street-food",
     "Cum preferi să explorezi mâncarea locală?",
     ["Fine dining — restaurante cu stele Michelin",
      "Street food — piețe locale și mâncare stradală",
      "Ambele — depinde de dispoziție"]),

    ("day-hiking", "all-inclusive-resorts",
     "Preferi vacanțele active sau relaxante?",
     ["Activ — drumeții, sport, explorare",
      "Relaxant — piscină, resort, confort",
      "Mix — activitate dimineața, relaxare după-amiaza"]),

    ("castles-palaces", "techno-clubs",
     "Ce te motivează mai mult în călătorie?",
     ["Cultură și istorie — muzee, castele, patrimoniu",
      "Distracție și viață de noapte",
      "Un mix de ambele"]),

    ("scuba-diving", "skiing",
     "Preferi apa sau zăpada?",
     ["Apă — scufundări, snorkeling, surfing",
      "Zăpadă — schi, snowboard, munte",
      "Îmi place și una și alta"]),

    ("yoga-retreats", "music-festivals",
     "Cum îți încarci bateriile în vacanță?",
     ["Liniște și meditație — yoga, retreat, natură",
      "Socializare și energie — festivaluri, concerte",
      "Alternez în funcție de nevoie"]),

    ("luxury-shopping", "thrifting-vintage",
     "Care e stilul tău de shopping?",
     ["Luxury — brand-uri, boutique-uri exclusiviste",
      "Vintage — second-hand, thrift stores, piețe de vechituri",
      "Nu mă interesează shopping-ul în vacanță"]),
]


# ─── INSERT LOGIC ─────────────────────────────────────────────────────────────

def upsert_tags(db):
    """Inserează tagurile dacă nu există deja (după slug). Returnează map slug→Tag."""
    slug_to_tag: dict[str, Tag] = {}

    # Primul pass: L1 (fără parent)
    l1_entries = [(s, n, p, il, q) for s, n, p, il, q in TAXONOMY if p is None]
    # Al doilea pass: L2
    l2_entries = [(s, n, p, il, q) for s, n, p, il, q in TAXONOMY
                  if p is not None and not il]
    # Al treilea pass: L3 (frunze)
    l3_entries = [(s, n, p, il, q) for s, n, p, il, q in TAXONOMY if il]

    def insert_batch(entries, level_name):
        for slug, name, parent_slug, is_leaf, question_template in entries:
            existing = db.query(Tag).filter(Tag.slug == slug).first()
            if existing:
                slug_to_tag[slug] = existing
                continue

            parent_id = None
            if parent_slug:
                parent_tag = slug_to_tag.get(parent_slug)
                if not parent_tag:
                    print(f"  [WARN] Parent '{parent_slug}' not found for '{slug}' — skipping")
                    continue
                parent_id = parent_tag.id

            # Determină categoria L1 (pentru câmpul `category`)
            if parent_slug is None:
                category = slug
            else:
                # Urcă în arbore până la L1
                root = slug_to_tag.get(parent_slug)
                while root and root.parent_id is not None:
                    root = db.query(Tag).filter(Tag.id == root.parent_id).first()
                category = root.slug if root else parent_slug

            tag = Tag(
                name=name,
                slug=slug,
                category=category,
                parent_id=parent_id,
                is_leaf=is_leaf,
                question_template=question_template,
            )
            db.add(tag)
            db.flush()  # obține ID-ul fără commit
            slug_to_tag[slug] = tag
            print(f"  [+] {level_name}: {slug}")

    print("\n── Inserare L1 (categorii principale) ──")
    insert_batch(l1_entries, "L1")
    db.commit()

    print("\n── Inserare L2 (subcategorii) ──")
    insert_batch(l2_entries, "L2")
    db.commit()

    print("\n── Inserare L3 (taguri frunză) ──")
    insert_batch(l3_entries, "L3")
    db.commit()

    return slug_to_tag


def insert_conflict_pairs(db, slug_to_tag: dict):
    """
    Inserează perechile de conflicte în tabela tag_conflicts.
    Tabela se creează dacă nu există.
    """
    from sqlalchemy import text
    import json

    db.execute(text("""
        CREATE TABLE IF NOT EXISTS tag_conflicts (
            id SERIAL PRIMARY KEY,
            tag_a_id INTEGER NOT NULL REFERENCES tags(id),
            tag_b_id INTEGER NOT NULL REFERENCES tags(id),
            question TEXT NOT NULL,
            options JSONB NOT NULL,
            UNIQUE(tag_a_id, tag_b_id)
        )
    """))
    db.commit()

    print("\n── Inserare perechi de conflicte ──")
    inserted = 0
    for slug_a, slug_b, question, options in CONFLICT_PAIRS:
        tag_a = slug_to_tag.get(slug_a)
        tag_b = slug_to_tag.get(slug_b)
        if not tag_a or not tag_b:
            print(f"  [WARN] Conflict pair skipped — missing tag: {slug_a} / {slug_b}")
            continue

        result = db.execute(text("""
            INSERT INTO tag_conflicts (tag_a_id, tag_b_id, question, options)
            VALUES (:a, :b, :q, cast(:o AS jsonb))
            ON CONFLICT (tag_a_id, tag_b_id) DO NOTHING
        """), {"a": tag_a.id, "b": tag_b.id, "q": question,
               "o": json.dumps(options, ensure_ascii=False)})
        if result.rowcount:
            print(f"  [+] Conflict: {slug_a} ↔ {slug_b}")
            inserted += 1

    db.commit()
    print(f"  Total conflicte inserate: {inserted}")


def print_summary(db):
    total = db.query(Tag).count()
    l1 = db.query(Tag).filter(Tag.parent_id.is_(None)).count()
    l2 = db.query(Tag).filter(Tag.parent_id.isnot(None), Tag.is_leaf == False).count()
    l3 = db.query(Tag).filter(Tag.is_leaf == True).count()
    print(f"\n{'═'*50}")
    print(f"  Taxonomie generată cu succes!")
    print(f"  L1 (categorii):     {l1}")
    print(f"  L2 (subcategorii):  {l2}")
    print(f"  L3 (taguri frunză): {l3}")
    print(f"  TOTAL taguri:       {total}")
    print(f"{'═'*50}\n")


def main():
    print("TripCraft — Generare Taxonomie Taguri")
    print("=" * 50)

    db = SessionLocal()
    try:
        slug_to_tag = upsert_tags(db)
        insert_conflict_pairs(db, slug_to_tag)
        print_summary(db)
    except Exception as e:
        db.rollback()
        print(f"\n[ERROR] {e}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    main()