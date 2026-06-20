import anthropic
import json
import time
import psycopg2
import os
import re
import numpy as np
from datetime import datetime
from dotenv import load_dotenv

load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), '..', '.env'))

DATABASE_URL = os.getenv("DATABASE_URL")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")

conn = psycopg2.connect(DATABASE_URL)
cursor = conn.cursor()

client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

# ═══════════════════════════════════════════════
# CITIRE DATE DIN DB
# ═══════════════════════════════════════════════

cursor.execute("SELECT id, name FROM countries ORDER BY name")
countries = cursor.fetchall()
print(f"Loaded {len(countries)} countries")

cursor.execute("""
    SELECT t.id, t.slug, t.name,
           p.slug as parent_slug,
           gp.slug as grandparent_slug
    FROM tags t
    LEFT JOIN tags p ON p.id = t.parent_id
    LEFT JOIN tags gp ON gp.id = p.parent_id
    WHERE t.is_leaf = true
    ORDER BY t.slug
""")
tags_raw = cursor.fetchall()

all_tags_context = {}
tag_ids = {}
for tag_id, slug, name, parent_slug, grandparent_slug in tags_raw:
    tag_ids[slug] = tag_id
    context = name
    if parent_slug:
        context = f"{name} ({parent_slug}"
        if grandparent_slug:
            context += f" > {grandparent_slug}"
        context += ")"
    all_tags_context[slug] = context

print(f"Loaded {len(all_tags_context)} leaf tags")

# ═══════════════════════════════════════════════
# CONSTRUIEȘTE TAGS GRUPATE PE IERARHIE
# ═══════════════════════════════════════════════

cursor.execute("""
    SELECT
        COALESCE(gp.slug, p.slug, 'other') as l1,
        COALESCE(p.slug, 'other') as l2,
        t.slug, t.name
    FROM tags t
    LEFT JOIN tags p ON p.id = t.parent_id
    LEFT JOIN tags gp ON gp.id = p.parent_id
    WHERE t.is_leaf = true
    ORDER BY l1, l2, t.slug
""")
tags_hier = cursor.fetchall()

grouped = {}
for l1, l2, slug, name in tags_hier:
    if l1 not in grouped:
        grouped[l1] = {}
    if l2 not in grouped[l1]:
        grouped[l1][l2] = []
    grouped[l1][l2].append(f"      - {slug}: {name}")

tags_hierarchical_grouped = ""
for l1, l2_dict in sorted(grouped.items()):
    tags_hierarchical_grouped += f"\n  [{l1.upper()}]\n"
    for l2, tag_lines in sorted(l2_dict.items()):
        tags_hierarchical_grouped += f"    ({l2})\n"
        tags_hierarchical_grouped += "\n".join(tag_lines) + "\n"

# ═══════════════════════════════════════════════
# DATE GEOGRAFICE PER ȚARĂ
# ═══════════════════════════════════════════════

COUNTRY_GEO_CONTEXT = {
    "Albania": "Coastal Balkan country on Adriatic and Ionian Sea. Mediterranean climate. Mountains in north and east. Small country, 3M people. Emerging tourism destination.",
    "Austria": "Landlocked Central European country. Alpine climate, extensive mountain ranges. 9M people. Strong winter sports, classical music, imperial history.",
    "Belgium": "Small coastal Western European country. Temperate maritime climate. 11M people. Medieval cities, world-famous beer and chocolate, EU capital.",
    "Bosnia and Herzegovina": "Landlocked Balkan country. Continental/mountain climate. 3M people. Ottoman heritage, mountain rivers, recovering tourism post-war.",
    "Bulgaria": "Black Sea coast plus landlocked interior. Continental climate. 7M people. Beach resorts, mountain skiing, ancient Thracian history, Orthodox heritage.",
    "Croatia": "Long Adriatic coastline with 1000+ islands. Mediterranean climate. 4M people. Major sailing destination, Dubrovnik, Dalmatian coast, national parks.",
    "Cyprus": "Mediterranean island, southernmost EU country. Hot dry summers, mild winters. 1.2M people. Ancient ruins, beaches, wine, year-round sun.",
    "Czech Republic": "Landlocked Central European country. Continental climate. 11M people. Prague tourism powerhouse, medieval architecture, beer culture, spa towns.",
    "Denmark": "Scandinavian country with long coastline. Temperate maritime climate. 6M people. Cycling culture, design, Noma gastronomy, Viking heritage.",
    "Estonia": "Baltic country with extensive coastline and islands. Continental/maritime climate. 1.3M people. Medieval Tallinn, digital nation, forests and bogs.",
    "Finland": "Nordic country with thousands of lakes and forests. Subarctic climate. 5.5M people. Sauna culture, northern lights, Lapland, extreme nature.",
    "France": "Large Western European country with Atlantic and Mediterranean coasts. Varied climate. 67M people. World tourism leader, wine, cuisine, art, fashion.",
    "Germany": "Large Central European country. Temperate continental climate. 83M people. Engineering, Christmas markets, castles, beer, diverse cities.",
    "Greece": "Mediterranean country with extensive coastline and 6000 islands. Hot dry summers. 11M people. Ancient ruins, island hopping, beaches, sailing.",
    "Hungary": "Landlocked Central European country. Continental climate. 10M people. Budapest thermal baths, Danube, wine regions, ruin bars.",
    "Iceland": "North Atlantic volcanic island. Subarctic climate. 370K people. Geothermal, northern lights, glaciers, extreme nature, midnight sun.",
    "Ireland": "Atlantic island. Mild wet maritime climate. 5M people. Pub culture, coastal walks, Celtic heritage, whiskey, green landscapes.",
    "Italy": "Mediterranean peninsula with islands. Mediterranean and alpine climate. 60M people. Ancient Rome, Renaissance art, fashion, cuisine, beaches.",
    "Kosovo": "Small landlocked Balkan country. Continental climate. 1.8M people. Newest European country, Ottoman heritage, mountains, emerging destination.",
    "Latvia": "Baltic country with coastline. Continental/maritime climate. 1.9M people. Art nouveau Riga, forests, beaches, folk traditions.",
    "Lithuania": "Baltic country with short coastline. Continental climate. 2.8M people. Baroque Vilnius, Curonian Spit, amber, folk traditions.",
    "Luxembourg": "Very small landlocked Western European country. Temperate climate. 650K people. Financial center, medieval castles, Mullerthal hiking, Moselle wine.",
    "Malta": "Tiny Mediterranean archipelago. Hot dry Mediterranean climate. 530K people. Ancient temples, WWII history, scuba diving, beaches, English-speaking.",
    "Moldova": "Small landlocked Eastern European country. Continental climate. 2.6M people. Wine caves, Orthodox monasteries, Soviet heritage, emerging destination.",
    "Montenegro": "Small Balkan country with Adriatic coastline and mountains. Mediterranean/continental. 620K people. Dramatic scenery, sailing, beaches, Durmitor.",
    "Netherlands": "Flat coastal Western European country. Temperate maritime climate. 17M people. Cycling, canals, tulips, world-class museums, liberal culture.",
    "North Macedonia": "Landlocked Balkan country. Continental climate. 2M people. Lake Ohrid UNESCO, Byzantine monasteries, mountains, emerging destination.",
    "Norway": "Scandinavian country with very long Atlantic coastline and fjords. Subarctic climate. 5.4M people. Fjords iconic, northern lights, extreme outdoor, oil wealth.",
    "Poland": "Large Central/Eastern European country. Continental climate. 38M people. Warsaw, Krakow, WWII sites, craft beer revival, Gothic architecture.",
    "Portugal": "Atlantic coastal Iberian country. Mediterranean/oceanic climate. 10M people. Surfing, wine, fado, beaches, historic exploration heritage.",
    "Romania": "Carpathian mountain country with Black Sea coast. Continental climate. 19M people. Dracula castles, Carpathian wildlife, Danube Delta birdwatching, folk traditions.",
    "Serbia": "Landlocked Central Balkan country. Continental climate. 7M people. Belgrade nightlife, EXIT festival, craft beer, Danube, folk traditions.",
    "Slovakia": "Landlocked Central European country. Continental/mountain climate. 5.5M people. High Tatras, medieval castles, caves, spa towns, folk traditions.",
    "Slovenia": "Small Alpine/Mediterranean country. Alpine and Mediterranean climate. 2.1M people. Lake Bled, Soca valley, caves, outdoor sports, compact gem.",
    "Spain": "Large Iberian country with Atlantic and Mediterranean coasts. Mediterranean/oceanic. 47M people. Beaches, flamenco, Gaudi, tapas, festivals, football.",
    "Sweden": "Large Scandinavian country with long coastline. Temperate/subarctic. 10M people. Design, forest bathing, northern lights, midsommar traditions.",
    "Switzerland": "Small landlocked Alpine country. Alpine climate. 8.7M people. Skiing world-class, hiking, paragliding, luxury watches, chocolate, banking.",
    "Ukraine": "Large Eastern European country. Continental climate. 44M people. Kyiv baroque, Carpathians, Danube Delta, folk traditions, WWII history.",
    "United Kingdom": "Atlantic archipelago. Temperate maritime climate. 67M people. London global hub, theater, museums, pub culture, Gothic architecture, countryside.",
}

# ═══════════════════════════════════════════════
# TAGURI ABSTRACTE CU DEFAULTS PRE-CALCULATE
# ═══════════════════════════════════════════════

ABSTRACT_TAGS_DEFAULT = {
    "esports-arenas": {
        "Germany": 0.65, "United Kingdom": 0.60,
        "Sweden": 0.55, "Netherlands": 0.55, "default": 0.20
    },
    "stand-up-comedy": {
        "United Kingdom": 0.80, "Ireland": 0.70,
        "Netherlands": 0.55, "default": 0.15
    },
    "meetup-events": {
        "United Kingdom": 0.65, "Netherlands": 0.60,
        "Germany": 0.55, "default": 0.25
    },
    "accessible-attractions": {
        "United Kingdom": 0.80, "Netherlands": 0.75,
        "Germany": 0.70, "default": 0.40
    },
    "all-inclusive-resorts": {
        "Greece": 0.70, "Bulgaria": 0.65,
        "Cyprus": 0.70, "Malta": 0.65, "default": 0.15
    },
    "cruises": {
        "Norway": 0.85, "Croatia": 0.80,
        "Greece": 0.85, "default": 0.30
    },
    "casinos": {
        "Malta": 0.60, "Czech Republic": 0.55, "default": 0.25
    },
    "hop-on-hop-off": {
        "France": 0.80, "United Kingdom": 0.80,
        "Italy": 0.80, "Spain": 0.75, "default": 0.45
    },
}

# ═══════════════════════════════════════════════
# FUNCȚIE GENERARE TAGS
# ═══════════════════════════════════════════════

def generate_country_tags_v2(country_name, tags_context,
                              tags_hier_grouped, geo_context):

    country_geo = geo_context.get(
        country_name,
        "European country. Research geographic and cultural context."
    )

    abstract_defaults = {}
    for tag, country_scores in ABSTRACT_TAGS_DEFAULT.items():
        if tag in tags_context:
            abstract_defaults[tag] = country_scores.get(
                country_name,
                country_scores.get("default", 0.25)
            )

    abstract_tags_text = "\n".join([
        f"  - {tag}: suggested {score:.2f} (abstract tag, use as baseline)"
        for tag, score in abstract_defaults.items()
    ]) if abstract_defaults else "  (none)"

    prompt = f"""You are a world-class travel expert and destination analyst.
You are building a personalized travel recommendation AI where country-tag scores
determine which destinations tourists receive. Accuracy is critical — wrong scores
mean tourists get inappropriate recommendations.

COUNTRY TO EVALUATE: {country_name}

GEOGRAPHIC AND CULTURAL PROFILE:
{country_geo}

SCORING INSTRUCTIONS — USE THE FULL RANGE:
- 5-15 tags at 0.85-1.00 (ICONIC — defining features of this country)
- 15-25 tags at 0.55-0.84 (STRONG — major tourism activities)
- 20-35 tags at 0.25-0.54 (MODERATE — available but not primary)
- 30-50 tags at 0.00-0.24 (WEAK or ABSENT — rare or impossible here)

GEOGRAPHIC CONSTRAINTS — STRICTLY ENFORCE:
- Landlocked countries: sandy-beaches=0.00, sailing<=0.10,
  snorkeling-diving=0.00, coastal-walks<=0.15,
  surfing-kitesurfing=0.00, scuba-diving=0.00
- Mediterranean/warm climate: skiing<=0.15 unless mountain interior,
  northern-lights=0.00, snowmobile=0.00, glaciers=0.00
- Arctic/Nordic: sandy-beaches<=0.20
- Small countries under 1M people: lower scores on variety activities
- Islands: higher scores on water activities, sailing, beaches

CALIBRATION ANCHORS:
Norway: fjords=0.99, northern-lights=0.97, sandy-beaches=0.05
Greece: sandy-beaches=0.96, ancient-ruins=0.95, skiing=0.12, northern-lights=0.00
Switzerland: skiing=0.98, paragliding=0.95, sandy-beaches=0.00, sailing=0.05
Malta: scuba-diving=0.92, sandy-beaches=0.90, skiing=0.00, northern-lights=0.00
Netherlands: cycling-biking=0.98, canal-river-cruises=0.95, skiing=0.05

ABSTRACT TAGS pre-suggested for {country_name}:
{abstract_tags_text}

TAGS TO SCORE grouped by category:
{tags_hier_grouped}

SELF-VERIFICATION before responding:
- Is {country_name} landlocked? If yes set all sea/coast to 0.00-0.10
- Is {country_name} Mediterranean? If yes set skiing/arctic to 0.00-0.15
- Are there 5-15 truly iconic tags >= 0.85?
- Are there 30+ tags at <= 0.24?

Return ONLY this exact JSON, no markdown, no explanation:
{{
  "country": "{country_name}",
  "is_landlocked": true_or_false,
  "climate_zone": "mediterranean or continental or oceanic or subarctic or alpine",
  "iconic_features": ["tag1", "tag2", "tag3"],
  "tourism_profile": "One sentence about what kind of tourist visits {country_name} and why",
  "tags": {{
    "slug": score_as_float
  }}
}}

ALL {len(tags_context)} slugs must be present.
Scores must be floats 0.00-1.00 with 2 decimal places."""

    for attempt in range(3):
        try:
            message = client.messages.create(
                model="claude-sonnet-4-5",
                max_tokens=4096,
                temperature=0.2,
                messages=[{"role": "user", "content": prompt}]
            )

            response_text = message.content[0].text.strip()

            if "```" in response_text:
                json_match = re.search(r'\{.*\}', response_text, re.DOTALL)
                if json_match:
                    response_text = json_match.group()

            data = json.loads(response_text)

            missing = [s for s in tags_context if s not in data.get("tags", {})]
            if missing:
                print(f"  Warning: missing {len(missing)} slugs, filling with 0.05")
                for slug in missing:
                    data["tags"][slug] = 0.05

            data["tags"] = {
                k: round(max(0.0, min(1.0, float(v))), 2)
                for k, v in data["tags"].items()
            }

            scores = list(data["tags"].values())
            iconic = sum(1 for s in scores if s >= 0.85)
            absent = sum(1 for s in scores if s <= 0.24)
            mean_s = sum(scores) / len(scores)

            print(f"  iconic(>=0.85)={iconic} | absent(<=0.24)={absent} | "
                  f"mean={mean_s:.2f} | "
                  f"{data.get('tourism_profile', '')[:70]}")

            return data

        except json.JSONDecodeError as e:
            print(f"  JSON error attempt {attempt+1}: {e}")
            print(f"  Preview: {response_text[:300]}")
            time.sleep(2 ** attempt)
        except Exception as e:
            print(f"  Error attempt {attempt+1}: {type(e).__name__}: {e}")
            time.sleep(2 ** attempt)

    print(f"  FAILED all attempts for {country_name}")
    return None

# ═══════════════════════════════════════════════
# RULARE PRINCIPALĂ
# ═══════════════════════════════════════════════

results = {
    "generated_at": datetime.now().isoformat(),
    "model": "claude-sonnet-4-5",
    "total_countries": len(countries),
    "countries": {}
}

for i, (country_id, country_name) in enumerate(countries):
    print(f"\nProcessing {i+1}/{len(countries)}: {country_name}...")

    data = generate_country_tags_v2(
        country_name,
        all_tags_context,
        tags_hierarchical_grouped,
        COUNTRY_GEO_CONTEXT
    )

    if data:
        filtered = {
            slug: score for slug, score in data["tags"].items()
            if score >= 0.20
        }
        if len(filtered) < 20:
            sorted_all = sorted(data["tags"].items(), key=lambda x: -x[1])
            filtered = {slug: score for slug, score in sorted_all[:20]}

        results["countries"][country_name] = {
            "id": country_id,
            "is_landlocked": data.get("is_landlocked", False),
            "climate_zone": data.get("climate_zone", "unknown"),
            "iconic_features": data.get("iconic_features", []),
            "tourism_profile": data.get("tourism_profile", ""),
            "all_scores": data["tags"],
            "filtered_tags": filtered,
            "tag_count": len(filtered)
        }
    else:
        print(f"  SKIPPED: {country_name}")

    time.sleep(1.5)

# ═══════════════════════════════════════════════
# SALVARE JSON
# ═══════════════════════════════════════════════

output_path = os.path.join(
    os.path.dirname(__file__), '..', 'data', 'country_tags_llm.json'
)
os.makedirs(os.path.dirname(output_path), exist_ok=True)
with open(output_path, "w", encoding="utf-8") as f:
    json.dump(results, f, ensure_ascii=False, indent=2)
print(f"\nSaved to {output_path}")

# ═══════════════════════════════════════════════
# VALIDARE
# ═══════════════════════════════════════════════

tag_counts = [c["tag_count"] for c in results["countries"].values()]
all_scores_flat = [s for c in results["countries"].values()
                   for s in c["all_scores"].values()]

print(f"\n=== VALIDARE ===")
print(f"Tari procesate: {len(results['countries'])}/39")
print(f"Media taguri per tara: {sum(tag_counts)/len(tag_counts):.1f}")
print(f"Min/Max taguri: {min(tag_counts)} / {max(tag_counts)}")
print(f"Score mean: {sum(all_scores_flat)/len(all_scores_flat):.3f}")
print(f"Score std: {np.std(all_scores_flat):.3f} (target > 0.25)")

checks = [
    ("Norway", "northern-lights", ">=", 0.90),
    ("Norway", "sandy-beaches", "<=", 0.15),
    ("Greece", "sandy-beaches", ">=", 0.85),
    ("Greece", "skiing", "<=", 0.20),
    ("Switzerland", "paragliding", ">=", 0.80),
    ("Switzerland", "sandy-beaches", "<=", 0.05),
    ("Malta", "skiing", "<=", 0.05),
    ("Malta", "scuba-diving", ">=", 0.80),
    ("Romania", "wildlife-watching", ">=", 0.70),
    ("Iceland", "glaciers", ">=", 0.90),
    ("Finland", "northern-lights", ">=", 0.80),
    ("Hungary", "sandy-beaches", "<=", 0.05),
]

print("\n=== VERIFICARI SEMANTICE ===")
all_ok = True
for country, tag, op, threshold in checks:
    if country not in results["countries"]:
        print(f"  SKIP {country} — not processed")
        continue
    actual = results["countries"][country]["all_scores"].get(tag, 0)
    ok = actual >= threshold if op == ">=" else actual <= threshold
    status = "OK" if ok else "FAIL"
    print(f"  [{status}] {country} - {tag}: {actual:.2f} ({op} {threshold})")
    if not ok:
        all_ok = False

tag_coverage = {}
for country_data in results["countries"].values():
    for slug in country_data["filtered_tags"]:
        tag_coverage[slug] = tag_coverage.get(slug, 0) + 1

dead_tags = [s for s in all_tags_context if tag_coverage.get(s, 0) == 0]
print(f"\nTaguri moarte (0 tari): {len(dead_tags)} (target < 20)")
if dead_tags:
    print(f"  Exemple: {dead_tags[:10]}")

if all_ok:
    print("\nValidare OK — continuam cu insertia in DB")
else:
    print("\nAtentie: unele verificari au esuat — revizuieste inainte de DB")

# ═══════════════════════════════════════════════
# INSERARE IN DB
# ═══════════════════════════════════════════════

print("\nInserare in DB...")
cursor.execute("DELETE FROM country_tags")

inserted = 0
for country_name, country_data in results["countries"].items():
    country_id = country_data["id"]
    for slug, score in country_data["filtered_tags"].items():
        tag_id = tag_ids.get(slug)
        if tag_id:
            cursor.execute("""
                INSERT INTO country_tags (country_id, tag_id, score)
                VALUES (%s, %s, %s)
                ON CONFLICT (country_id, tag_id)
                DO UPDATE SET score = EXCLUDED.score
            """, (country_id, tag_id, round(score, 4)))
            inserted += 1

conn.commit()
print(f"Inserate {inserted} country_tags in DB")

cursor.execute("""
    SELECT COUNT(*), AVG(score), STDDEV(score), MIN(score), MAX(score)
    FROM country_tags
""")
stats = cursor.fetchone()
print(f"\n=== STATISTICI FINALE DB ===")
print(f"Total rows: {stats[0]}")
print(f"AVG score: {float(stats[1]):.3f}")
print(f"STDDEV: {float(stats[2]):.3f}")
print(f"MIN/MAX: {float(stats[3]):.3f} / {float(stats[4]):.3f}")

cursor.close()
conn.close()
print("\nDone.")
