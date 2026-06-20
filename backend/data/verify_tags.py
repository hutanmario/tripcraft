import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.database import SessionLocal
from app.models.geography import City, Attraction, city_tags, attraction_tags
from app.models.destination import Tag
from sqlalchemy import select

db = SessionLocal()

print("=== TAGURI ORASE ===\n")
for city_name in ["Berlin", "Ibiza", "Santorini", "Budapest", "Tromso", "Lyon", "Zakopane"]:
    city = db.query(City).filter(City.name.ilike(f"%{city_name}%")).first()
    if not city:
        print(f"{city_name}: NOT FOUND")
        continue
    rows = db.execute(
        select(city_tags.c.tag_id, city_tags.c.score)
        .where(city_tags.c.city_id == city.id)
        .order_by(city_tags.c.score.desc())
    ).fetchall()
    tags = []
    for tag_id, score in rows:
        tag = db.query(Tag).filter(Tag.id == tag_id).first()
        if tag:
            tags.append(f"{tag.slug}({score:.2f})")
    print(f"{city.name}: {', '.join(tags)}")

print("\n=== TAGURI ATRACTII ===\n")
for attr_name in ["Colosseum", "Berghain", "Sagrada", "Alhambra", "Louvre"]:
    attr = db.query(Attraction).filter(Attraction.name.ilike(f"%{attr_name}%")).first()
    if not attr:
        print(f"{attr_name}: NOT FOUND")
        continue
    rows = db.execute(
        select(attraction_tags.c.tag_id, attraction_tags.c.score)
        .where(attraction_tags.c.attraction_id == attr.id)
        .order_by(attraction_tags.c.score.desc())
    ).fetchall()
    tags = []
    for tag_id, score in rows:
        tag = db.query(Tag).filter(Tag.id == tag_id).first()
        if tag:
            tags.append(f"{tag.slug}({score:.2f})")
    print(f"{attr.name}: {', '.join(tags)}")

db.close()
