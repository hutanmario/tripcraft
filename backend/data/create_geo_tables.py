"""
create_geo_tables.py
====================
Creează tabelele countries, cities, attractions, și asocierile lor.

Rulare:
    cd backend
    venv\Scripts\python.exe data/create_geo_tables.py
"""

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.database import engine, Base

# Importă toate modelele ca să fie înregistrate în Base.metadata
from app.models.destination import Tag, Destination, DestinationTag
from app.models.geography import Country, City, Attraction

from sqlalchemy import text


def main():
    print("Creare tabele geografice...")

    # Creează doar tabelele noi (nu atinge ce există deja)
    Base.metadata.create_all(bind=engine)

    # Verificare
    with engine.connect() as conn:
        result = conn.execute(text("""
            SELECT tablename FROM pg_tables
            WHERE schemaname = 'public'
            ORDER BY tablename
        """))
        tables = [r[0] for r in result]

    new = [t for t in ["countries", "cities", "attractions",
                        "country_tags", "city_tags", "attraction_tags"]
           if t in tables]

    print(f"Tabele create cu succes: {', '.join(new)}")
    print(f"Total tabele în DB: {len(tables)}")


if __name__ == "__main__":
    main()