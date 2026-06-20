"""
auto_tag_nlp.py
===============
Foloseste sentence-transformers multilingv pentru a mapa automat
legacy_tags + description -> taguri din taxonomia noua.

Model: paraphrase-multilingual-MiniLM-L12-v2 (suporta romana)

Rulare:
    cd backend
    venv\Scripts\python.exe data/auto_tag_nlp.py
"""

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import numpy as np
from sentence_transformers import SentenceTransformer
from sklearn.metrics.pairwise import cosine_similarity
from sqlalchemy import delete, select, func
from app.database import SessionLocal
from app.models.destination import Tag
from app.models.geography import (
    City, Attraction, Country,
    city_tags, attraction_tags, country_tags
)

# ─── CONFIG ───────────────────────────────────────────────────────────────────
MODEL_NAME    = "paraphrase-multilingual-MiniLM-L12-v2"
TOP_K_CITY    = 6
TOP_K_ATTR    = 5
TOP_K_COUNTRY = 8
MIN_SCORE     = 0.30

EXCLUDE_SLUGS = {
    "temperate", "budget", "affordable", "quiet-travel",
    "green-city", "eco-friendly", "local-tavernas",
}

BAD_LEGACY_TAGS = {
    "cars", "industry", "finance", "politics", "cleanliness",
    "digitalization", "multiculturalism", "minimalism", "affordable",
    "cheap-travel", "quiet-travel", "sunshine", "expensive",
    "family-travel", "romance", "nature", "mountains",
    "architecture", "gastronomy", "culture",
    "university-culture", "football",
}


# ─── TEXT BUILDERS ────────────────────────────────────────────────────────────

def build_tag_text(tag: Tag) -> str:
    return tag.name


def build_city_text(city: City, country_name: str) -> str:
    parts = []
    # Numele orasului repetat pentru a-i creste ponderea semantica
    if city.name:
        parts.extend([city.name, city.name, city.name])
    if city.description:
        parts.append(city.description)
    if city.legacy_tags:
        raw_tags = [t.strip() for t in city.legacy_tags.split(",")]
        good_tags = [
            t.replace("-", " ") for t in raw_tags
            if t.strip() not in BAD_LEGACY_TAGS and t.strip()
        ]
        if good_tags:
            parts.append(" ".join(good_tags))
    return " ".join(parts)


def build_attraction_text(attr: Attraction) -> str:
    parts = []
    if attr.name:
        parts.extend([attr.name, attr.name])
    if attr.category:
        parts.append(attr.category)
    if attr.legacy_tags:
        legacy = attr.legacy_tags.replace(",", " ").replace("-", " ")
        parts.append(legacy)
    if attr.description:
        parts.append(attr.description)
    return " ".join(parts)


# ─── MATCHING ─────────────────────────────────────────────────────────────────

def get_top_tags(text_embedding, tag_embeddings, tag_list, top_k, min_score):
    scores = cosine_similarity([text_embedding], tag_embeddings)[0]
    top_indices = np.argsort(scores)[::-1]
    result = []
    for idx in top_indices:
        if len(result) >= top_k:
            break
        tag = tag_list[idx]
        score = float(scores[idx])
        if score < min_score:
            break
        if tag.slug in EXCLUDE_SLUGS:
            continue
        result.append((tag, score))
    return result


# ─── MAIN ─────────────────────────────────────────────────────────────────────

def main():
    print("Incarcare model sentence-transformers multilingv...")
    model = SentenceTransformer(MODEL_NAME)
    print(f"Model '{MODEL_NAME}' incarcat.\n")

    db = SessionLocal()

    # 1. Embeddings taguri frunza
    print("Generare embeddings taguri...")
    leaf_tags = db.query(Tag).filter(Tag.is_leaf == True).all()
    tag_texts = [build_tag_text(t) for t in leaf_tags]
    tag_embeddings = model.encode(tag_texts, show_progress_bar=True, batch_size=64)
    print(f"  {len(leaf_tags)} taguri frunza encodate.\n")

    country_cache = {c.id: c.name for c in db.query(Country).all()}

    # 2. Auto-tagging orase
    print("Auto-tagging orase...")
    cities = db.query(City).all()
    city_texts = [build_city_text(c, country_cache.get(c.country_id, "")) for c in cities]
    city_embeddings = model.encode(city_texts, show_progress_bar=True, batch_size=64)

    db.execute(delete(city_tags))
    db.commit()

    for city, embedding in zip(cities, city_embeddings):
        top = get_top_tags(embedding, tag_embeddings, leaf_tags, TOP_K_CITY, MIN_SCORE)
        for tag, score in top:
            db.execute(city_tags.insert().values(
                city_id=city.id, tag_id=tag.id, score=round(score, 4)
            ))
    db.commit()
    print(f"  {len(cities)} orase taguite.\n")

    # 3. Auto-tagging atractii
    print("Auto-tagging atractii...")
    attractions = db.query(Attraction).all()
    attr_texts = [build_attraction_text(a) for a in attractions]
    attr_embeddings = model.encode(attr_texts, show_progress_bar=True, batch_size=64)

    db.execute(delete(attraction_tags))
    db.commit()

    for attr, embedding in zip(attractions, attr_embeddings):
        top = get_top_tags(embedding, tag_embeddings, leaf_tags, TOP_K_ATTR, MIN_SCORE)
        for tag, score in top:
            db.execute(attraction_tags.insert().values(
                attraction_id=attr.id, tag_id=tag.id, score=round(score, 4)
            ))
    db.commit()
    print(f"  {len(attractions)} atractii taguite.\n")

    # 4. Recompute taguri tari din orase
    print("Recompute taguri tari din orase...")
    db.execute(delete(country_tags))
    db.commit()

    countries = db.query(Country).all()
    recomputed = 0

    for country in countries:
        city_ids = [c.id for c in db.query(City).filter(City.country_id == country.id).all()]
        if not city_ids:
            continue

        tag_scores = {}
        for city_id in city_ids:
            rows = db.execute(
                select(city_tags.c.tag_id, city_tags.c.score).where(
                    city_tags.c.city_id == city_id
                )
            ).fetchall()
            for tag_id, score in rows:
                tag_scores.setdefault(tag_id, []).append(score)

        avg_scores = {
            tag_id: sum(scores) / len(scores)
            for tag_id, scores in tag_scores.items()
        }
        top_tags = sorted(avg_scores.items(), key=lambda x: x[1], reverse=True)[:TOP_K_COUNTRY]

        for tag_id, score in top_tags:
            db.execute(country_tags.insert().values(
                country_id=country.id, tag_id=tag_id, score=round(score, 4)
            ))
        recomputed += 1

    db.commit()
    print(f"  {recomputed} tari recomputed.\n")

    # 5. Statistici
    total_city_tags    = db.execute(select(func.count()).select_from(city_tags)).scalar()
    total_attr_tags    = db.execute(select(func.count()).select_from(attraction_tags)).scalar()
    total_country_tags = db.execute(select(func.count()).select_from(country_tags)).scalar()

    print(f"{'='*50}")
    print(f"  Taguri orase:     {total_city_tags}")
    print(f"  Taguri atractii:  {total_attr_tags}")
    print(f"  Taguri tari:      {total_country_tags}")
    print(f"{'='*50}")

    db.close()


if __name__ == "__main__":
    main()