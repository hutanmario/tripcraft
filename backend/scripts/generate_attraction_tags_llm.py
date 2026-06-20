import anthropic
import json
import time
import psycopg2
import os
import re
import sys
import io
from datetime import datetime
from dotenv import load_dotenv

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), '..', '.env'))

conn = psycopg2.connect(os.getenv("DATABASE_URL"))
cursor = conn.cursor()

client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

# ---------------------------------------------------------------------------
# PASUL 1 — Citește datele din DB
# ---------------------------------------------------------------------------

cursor.execute("""
    SELECT a.id, a.name, a.category, a.legacy_tags,
           ci.name as city_name, co.name as country_name,
           a.avg_duration_hours
    FROM attractions a
    JOIN cities ci ON ci.id = a.city_id
    JOIN countries co ON co.id = ci.country_id
    ORDER BY
        CASE WHEN EXISTS (
            SELECT 1 FROM attraction_tags at WHERE at.attraction_id = a.id
        ) THEN 1 ELSE 0 END ASC,
        a.id ASC
""")
attractions = cursor.fetchall()
print(f"Loaded {len(attractions)} attractions")

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

tag_ids = {}
all_tags_context = {}
for tag_id, slug, name, parent_slug, grandparent_slug in tags_raw:
    tag_ids[slug] = tag_id
    context = name
    if parent_slug:
        context = f"{name} ({parent_slug}"
        if grandparent_slug:
            context += f" > {grandparent_slug}"
        context += ")"
    all_tags_context[slug] = context

tags_list_text = "\n".join(
    [f"- {slug}: {desc}" for slug, desc in all_tags_context.items()]
)
print(f"Loaded {len(tag_ids)} leaf tags")

# ---------------------------------------------------------------------------
# PASUL 2 — Procesează în batch-uri
# ---------------------------------------------------------------------------

BATCH_SIZE = 10


def generate_attraction_batch(batch: list) -> dict | None:
    attractions_text = ""
    for i, attr in enumerate(batch):
        attractions_text += (
            f'\n{i + 1}. id={attr["id"]} "{attr["name"]}"\n'
            f'   Categorie: {attr["category"]}\n'
            f'   Oraș: {attr["city_name"]}, {attr["country_name"]}\n'
            f'   Legacy tags: {attr["legacy_tags"] or "N/A"}\n'
        )

    prompt = f"""You are a tourism expert. For each attraction below, provide:
1. The most relevant tags from the available list (5-15 tags)
2. Estimated visit duration in hours
3. A brief description (1-2 sentences, English)

ATTRACTIONS TO ANALYZE:
{attractions_text}

AVAILABLE TAGS:
{tags_list_text}

SCORING RULES:
- Score 0.85-1.00: tag is defining/iconic for this attraction
- Score 0.60-0.84: tag is very relevant
- Score 0.40-0.59: tag is moderately relevant
- Score 0.20-0.39: tag is somewhat relevant
- Only include tags with score >= 0.20
- Include 5-15 tags per attraction

DURATION GUIDELINES:
- Monument/statue/viewpoint: 0.25-0.5h
- Church/cathedral: 0.5-1.5h
- Museum (small): 1.0-2.0h
- Museum (large): 2.0-3.5h
- Park/garden: 1.0-2.5h
- Castle/palace: 1.5-3.0h
- Market/bazaar: 0.5-1.5h
- Beach/lake: 1.5-4.0h
- Theme park/zoo: 3.0-6.0h

Return ONLY this JSON, no markdown:
{{
  "attractions": [
    {{
      "id": <integer from the id= field above>,
      "name": "attraction name",
      "tags": {{
        "slug": <score_float>
      }},
      "avg_duration_hours": <float>,
      "description": "1-2 sentence description"
    }}
  ]
}}

ALL {len(batch)} attractions must appear in the response.
Scores must be floats 0.20-1.00.
"""

    for attempt in range(3):
        try:
            message = client.messages.create(
                model="claude-haiku-4-5",
                max_tokens=4000,
                temperature=0.1,
                messages=[{"role": "user", "content": prompt}],
            )

            response_text = message.content[0].text.strip()

            if "```" in response_text:
                json_match = re.search(r"\{.*\}", response_text, re.DOTALL)
                if json_match:
                    response_text = json_match.group()

            data = json.loads(response_text)

            for attr_data in data.get("attractions", []):
                attr_data["tags"] = {
                    k: round(max(0.20, min(1.0, float(v))), 2)
                    for k, v in attr_data.get("tags", {}).items()
                    if k in tag_ids
                }
                if "avg_duration_hours" in attr_data:
                    attr_data["avg_duration_hours"] = round(
                        max(0.25, min(8.0, float(attr_data["avg_duration_hours"]))), 2
                    )

            return data

        except json.JSONDecodeError as e:
            print(f"  JSON error attempt {attempt + 1}: {e}")
            time.sleep(2 ** attempt)
        except Exception as e:
            print(f"  Error attempt {attempt + 1}: {type(e).__name__}: {e}")
            time.sleep(2 ** attempt)

    return None


attrs_list = [
    {
        "id": row[0],
        "name": row[1],
        "category": row[2],
        "legacy_tags": row[3],
        "city_name": row[4],
        "country_name": row[5],
        "avg_duration_hours": row[6],
    }
    for row in attractions
]

results = {
    "generated_at": datetime.now().isoformat(),
    "model": "claude-haiku-4-5",
    "total_attractions": len(attractions),
    "attractions": {},
}

total_batches = (len(attrs_list) + BATCH_SIZE - 1) // BATCH_SIZE

for batch_idx in range(total_batches):
    start = batch_idx * BATCH_SIZE
    end = min(start + BATCH_SIZE, len(attrs_list))
    batch = attrs_list[start:end]

    print(
        f"Processing batch {batch_idx + 1}/{total_batches} "
        f"(attractions {start + 1}-{end})..."
    )

    data = generate_attraction_batch(batch)

    if data:
        for attr_data in data.get("attractions", []):
            attr_id = attr_data["id"]
            results["attractions"][str(attr_id)] = {
                "name": attr_data.get("name", ""),
                "tags": attr_data.get("tags", {}),
                "avg_duration_hours": attr_data.get("avg_duration_hours", 1.5),
                "description": attr_data.get("description", ""),
            }
        print(f"  → {len(data.get('attractions', []))} attractions processed")
    else:
        print(f"  → FAILED batch {batch_idx + 1}, using fallback")
        for attr in batch:
            results["attractions"][str(attr["id"])] = {
                "name": attr["name"],
                "tags": {},
                "avg_duration_hours": 1.5,
                "description": "",
            }

    time.sleep(0.5)

output_path = os.path.join(
    os.path.dirname(__file__), "..", "data", "attraction_tags_llm.json"
)
os.makedirs(os.path.dirname(output_path), exist_ok=True)
with open(output_path, "w", encoding="utf-8") as f:
    json.dump(results, f, ensure_ascii=False, indent=2)

processed = len(results["attractions"])
with_tags = sum(1 for v in results["attractions"].values() if v["tags"])
print(f"\nSaved {processed} attractions to {output_path}")
print(f"  {with_tags} have tags, {processed - with_tags} used fallback")

# ---------------------------------------------------------------------------
# PASUL 3 — Inserează în DB
# ---------------------------------------------------------------------------

print("\nInserting into DB...")

cursor.execute("SELECT COUNT(*) FROM attraction_tags")
before_count = cursor.fetchone()[0]
print(f"attraction_tags before: {before_count}")

inserted_tags = 0
updated_duration = 0
updated_description = 0

for attr_id_str, attr_data in results["attractions"].items():
    attr_id = int(attr_id_str)

    for slug, score in attr_data["tags"].items():
        tag_id = tag_ids.get(slug)
        if tag_id:
            cursor.execute(
                """
                INSERT INTO attraction_tags (attraction_id, tag_id, score)
                VALUES (%s, %s, %s)
                ON CONFLICT (attraction_id, tag_id)
                DO UPDATE SET score = GREATEST(attraction_tags.score, EXCLUDED.score)
                """,
                (attr_id, tag_id, score),
            )
            inserted_tags += 1

    if attr_data.get("avg_duration_hours"):
        cursor.execute(
            """
            UPDATE attractions
            SET avg_duration_hours = %s
            WHERE id = %s AND avg_duration_hours IS NULL
            """,
            (attr_data["avg_duration_hours"], attr_id),
        )
        if cursor.rowcount > 0:
            updated_duration += 1

    if attr_data.get("description"):
        cursor.execute(
            """
            UPDATE attractions
            SET description = %s
            WHERE id = %s AND description IS NULL
            """,
            (attr_data["description"], attr_id),
        )
        if cursor.rowcount > 0:
            updated_description += 1

conn.commit()

cursor.execute("SELECT COUNT(*) FROM attraction_tags")
after_count = cursor.fetchone()[0]

cursor.execute(
    "SELECT COUNT(*) FROM attractions WHERE avg_duration_hours IS NOT NULL"
)
duration_count = cursor.fetchone()[0]

cursor.execute("SELECT COUNT(*) FROM attractions WHERE description IS NOT NULL")
desc_count = cursor.fetchone()[0]

cursor.execute("""
    SELECT
        ROUND(AVG(tag_count)::numeric, 2),
        MIN(tag_count),
        MAX(tag_count),
        ROUND(STDDEV(tag_count)::numeric, 2)
    FROM (
        SELECT attraction_id, COUNT(*) as tag_count
        FROM attraction_tags
        GROUP BY attraction_id
    ) t
""")
tag_stats = cursor.fetchone()

cursor.execute("""
    SELECT COUNT(*) FROM attractions a
    WHERE NOT EXISTS (
        SELECT 1 FROM attraction_tags at WHERE at.attraction_id = a.id
    )
""")
no_tags_count = cursor.fetchone()[0]

print(f"\n=== RAPORT FINAL ===")
print(f"attraction_tags: {before_count} → {after_count} (+{after_count - before_count})")
print(f"Taguri inserate/actualizate: {inserted_tags}")
print(f"Atracții cu durată: {duration_count}/1429")
print(f"Atracții cu descriere: {desc_count}/1429")
print(f"Atracții fără niciun tag: {no_tags_count}")
print(f"AVG taguri/atracție: {float(tag_stats[0]):.2f}")
print(f"MIN/MAX taguri: {tag_stats[1]} / {tag_stats[2]}")
print(f"STDDEV taguri: {float(tag_stats[3]):.2f}")

cursor.close()
conn.close()
print("\nDone.")
