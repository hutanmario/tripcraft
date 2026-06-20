"""
fetch_images.py
Populează image_url în tabela destinations folosind Unsplash API.
"""

import os
import psycopg2
import requests
import time

DB_CONFIG = {
    "host": os.getenv("DB_HOST", "localhost"),
    "port": int(os.getenv("DB_PORT", "5432")),
    "database": os.getenv("DB_NAME", "tripcraft"),
    "user": os.getenv("DB_USER", "postgres"),
    "password": os.getenv("DB_PASSWORD", "")
}

UNSPLASH_ACCESS_KEY = os.getenv("UNSPLASH_ACCESS_KEY", "")


def get_image_url(query: str) -> str | None:
    url = "https://api.unsplash.com/search/photos"
    params = {
        "query": query,
        "per_page": 1,
        "orientation": "landscape",
        "client_id": UNSPLASH_ACCESS_KEY
    }
    try:
        response = requests.get(url, params=params, timeout=10)
        data = response.json()
        results = data.get("results", [])
        if results:
            return results[0]["urls"]["regular"]
    except Exception as e:
        print(f"  Eroare pentru {query}: {e}")
    return None


def fetch_all():
    conn = psycopg2.connect(**DB_CONFIG)
    cur = conn.cursor()

    cur.execute("SELECT id, name, country FROM destinations WHERE image_url IS NULL ORDER BY id")
    destinations = cur.fetchall()
    print(f"Destinații fără imagine: {len(destinations)}")

    updated = 0
    for dest_id, name, country in destinations:
        query = f"{name} {country} travel"
        print(f"  [{dest_id}] {name}, {country}...", end=" ")

        image_url = get_image_url(query)
        if image_url:
            cur.execute(
                "UPDATE destinations SET image_url = %s WHERE id = %s",
                (image_url, dest_id)
            )
            conn.commit()
            updated += 1
            print(f"✓")
        else:
            print(f"✗ nu s-a găsit")

        # Unsplash free tier: 50 requests/oră — pauză între requesturi
        time.sleep(1.5)

    cur.close()
    conn.close()
    print(f"\n✅ Done! {updated}/{len(destinations)} imagini actualizate.")


if __name__ == "__main__":
    fetch_all()