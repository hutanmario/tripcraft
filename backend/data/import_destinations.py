"""
import_destinations.py
Creează tabela destinations și importă destinations_europe_v3.csv în PostgreSQL
"""

import psycopg2
import csv
import os

# ⚠️ Modifică dacă ai altă parolă/user/db
DB_CONFIG = {
    "host": os.getenv("DB_HOST", "localhost"),
    "port": int(os.getenv("DB_PORT", "5432")),
    "database": os.getenv("DB_NAME", "tripcraft"),
    "user": os.getenv("DB_USER", "postgres"),
    "password": os.getenv("DB_PASSWORD", "")
}

CSV_FILE = "destinations_europe_v3.csv"  # pune CSV-ul în același folder

CREATE_TABLE = """
CREATE TABLE IF NOT EXISTS destinations (
    id SERIAL PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    country VARCHAR(100) NOT NULL,
    cluster VARCHAR(100) NOT NULL,
    latitude DOUBLE PRECISION NOT NULL,
    longitude DOUBLE PRECISION NOT NULL,
    avg_cost_per_day INTEGER NOT NULL,
    rating NUMERIC(3,1) NOT NULL,
    tags TEXT NOT NULL
);
"""

CREATE_INDEX = """
CREATE INDEX IF NOT EXISTS idx_destinations_country ON destinations(country);
CREATE INDEX IF NOT EXISTS idx_destinations_cluster ON destinations(cluster);
CREATE INDEX IF NOT EXISTS idx_destinations_rating ON destinations(rating);
CREATE INDEX IF NOT EXISTS idx_destinations_cost ON destinations(avg_cost_per_day);
"""

def import_csv():
    conn = psycopg2.connect(**DB_CONFIG)
    cur = conn.cursor()

    print("📦 Creez tabela destinations...")
    cur.execute(CREATE_TABLE)
    for stmt in CREATE_INDEX.strip().split(";"):
        if stmt.strip():
            cur.execute(stmt)
    conn.commit()

    # Verifică dacă deja are date
    cur.execute("SELECT COUNT(*) FROM destinations;")
    count = cur.fetchone()[0]
    if count > 0:
        print(f"⚠️  Tabela are deja {count} rânduri. Șterg și reimport...")
        cur.execute("TRUNCATE TABLE destinations RESTART IDENTITY;")
        conn.commit()

    print(f"📖 Citesc {CSV_FILE}...")
    with open(CSV_FILE, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    print(f"   Găsite {len(rows)} destinații")

    INSERT = """
        INSERT INTO destinations (name, country, cluster, latitude, longitude, avg_cost_per_day, rating, tags)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
    """

    data = [
        (
            r["name"],
            r["country"],
            r["cluster"],
            float(r["latitude"]),
            float(r["longitude"]),
            int(r["avg_cost_per_day"]),
            float(r["rating"]),
            r["tags"]
        )
        for r in rows
    ]

    cur.executemany(INSERT, data)
    conn.commit()

    cur.execute("SELECT COUNT(*) FROM destinations;")
    final_count = cur.fetchone()[0]
    print(f"✅ Import complet! {final_count} destinații în baza de date.")

    # Statistici rapide
    cur.execute("SELECT cluster, COUNT(*) FROM destinations GROUP BY cluster ORDER BY cluster;")
    print("\n🗺️  Distribuție pe clustere:")
    for row in cur.fetchall():
        print(f"   {row[0]}: {row[1]} destinații")

    cur.execute("SELECT country, COUNT(*) FROM destinations GROUP BY country ORDER BY country;")
    print("\n📊 Destinații pe țară:")
    for row in cur.fetchall():
        print(f"   {row[0]}: {row[1]}")

    cur.close()
    conn.close()

if __name__ == "__main__":
    import_csv()
