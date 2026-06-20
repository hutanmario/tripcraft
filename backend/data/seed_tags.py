"""
seed_tags.py
Populează tabela tags și destination_tags din destinations_europe_v3.csv
"""

import os
import psycopg2
import csv

DB_CONFIG = {
    "host": os.getenv("DB_HOST", "localhost"),
    "port": int(os.getenv("DB_PORT", "5432")),
    "database": os.getenv("DB_NAME", "tripcraft"),
    "user": os.getenv("DB_USER", "postgres"),
    "password": os.getenv("DB_PASSWORD", "")
}

CSV_FILE = "destinations_europe_v3.csv"


def get_conn():
    return psycopg2.connect(**DB_CONFIG)


def seed():
    conn = get_conn()
    cur = conn.cursor()

    # Citește CSV
    with open(CSV_FILE, newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))

    # Colectează taguri unice
    all_tags = set()
    for row in rows:
        for tag in row["tags"].split(","):
            all_tags.add(tag.strip())

    print(f"Taguri unice găsite: {len(all_tags)}")

    # Inserează taguri
    tag_id_map = {}  # tag_name -> id
    for tag in sorted(all_tags):
        cur.execute("""
            INSERT INTO tags (name, slug, category)
            VALUES (%s, %s, %s)
            ON CONFLICT (slug) DO NOTHING
            RETURNING id
        """, (tag, tag, "general"))
        result = cur.fetchone()
        if result:
            tag_id_map[tag] = result[0]

    # Recuperează id-urile pentru cele care existau deja
    cur.execute("SELECT name, id FROM tags")
    for name, tid in cur.fetchall():
        tag_id_map[name] = tid

    print(f"Taguri în DB: {len(tag_id_map)}")

    # Leagă destinațiile de taguri
    cur.execute("SELECT id, name FROM destinations")
    dest_map = {name: did for did, name in cur.fetchall()}

    linked = 0
    for row in rows:
        dest_id = dest_map.get(row["name"])
        if not dest_id:
            continue
        for tag in row["tags"].split(","):
            tag = tag.strip()
            tag_id = tag_id_map.get(tag)
            if not tag_id:
                continue
            cur.execute("""
                INSERT INTO destination_tags (destination_id, tag_id)
                VALUES (%s, %s)
                ON CONFLICT DO NOTHING
            """, (dest_id, tag_id))
            linked += 1

    conn.commit()
    cur.close()
    conn.close()
    print(f"Legături destination_tags create: {linked}")
    print("✅ Done!")


if __name__ == "__main__":
    seed()