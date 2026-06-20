"""
backend/app/routers/fim_router.py
===================================
Full Interactive Mode — recomandare city/attraction în timp real.
Reutilizează modele și DB din restul aplicației; nu duplică logică.
"""

import json
import math
import logging
from collections import Counter, defaultdict
from typing import Dict, List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import func
from sqlalchemy.orm import Session, selectinload

from app.database import get_db
from app.dependencies import get_current_user
from app.models.user import User
from app.models.quiz_v4_session import QuizV4Session
from app.models.geography import Country, City, Attraction, attraction_tags, city_tags
from app.models.tag import Tag
from app.models.itinerary import ItineraryPlan, ItineraryDay

router = APIRouter(prefix="/fim", tags=["Full Interactive Mode"])
logger = logging.getLogger(__name__)

FIM_IDF_ALPHA = 0.45
FIM_IDF_MAX_WEIGHT = 2.0
CITY_ATTRACTION_WEIGHT = 0.62
CITY_PROFILE_WEIGHT = 0.34
CITY_COVERAGE_BONUS = 0.04
MAX_DAY_HOURS = 8.0
SUGGESTED_TASTE_WEIGHT = 0.50
SUGGESTED_NOVELTY_WEIGHT = 0.20
SUGGESTED_PROXIMITY_WEIGHT = 0.15
SUGGESTED_DURATION_WEIGHT = 0.10
SUGGESTED_RATING_WEIGHT = 0.05

_fim_tag_idf_cache: Optional[Dict[str, float]] = None

# ─── CITY_COORDS fallback ─────────────────────────────────────────────────────

CITY_COORDS = {
    "Paris":      (48.8566,  2.3522),
    "Lyon":       (45.7640,  4.8357),
    "Bordeaux":   (44.8378, -0.5792),
    "Nice":       (43.7102,  7.2620),
    "Roma":       (41.9028, 12.4964),
    "Milano":     (45.4642,  9.1900),
    "Barcelona":  (41.3851,  2.1734),
    "Madrid":     (40.4168, -3.7038),
    "Berlin":     (52.5200, 13.4050),
    "Amsterdam":  (52.3676,  4.9041),
    "Viena":      (48.2082, 16.3738),
    "Praga":      (50.0755, 14.4378),
    "Budapesta":  (47.4979, 19.0402),
    "Varsovia":   (52.2297, 21.0122),
    "Lisabona":   (38.7223, -9.1393),
    "Atena":      (37.9838, 23.7275),
}

# ─── Pydantic schemas ─────────────────────────────────────────────────────────

class CityResult(BaseModel):
    id: int
    city: str
    country: str
    score: float
    tags: List[str]
    explanations: List[str] = Field(default_factory=list)
    group_explanation: Optional[dict] = None
    attraction_count: int
    lat: float
    lng: float
    description: Optional[str] = None
    image_url: Optional[str] = None

class NextCityResult(CityResult):
    profile_score: float
    distance_km: Optional[float] = None
    next_city_reasons: List[str] = Field(default_factory=list)

class AttractionResult(BaseModel):
    id: int
    name: str
    score: float
    tags: List[str]
    matched_tags: List[str]
    explanations: List[str] = Field(default_factory=list)
    group_explanation: Optional[dict] = None
    lat: Optional[float]
    lng: Optional[float]
    avg_duration_hours: Optional[float]
    entry_fee_eur: Optional[float]
    rating: Optional[float] = None
    image_url: Optional[str]

class FIMItem(BaseModel):
    attraction_id: int
    day: int
    order: int

class FIMTripSave(BaseModel):
    session_id: str
    country: str
    country_id: Optional[int] = None
    group_trip_id: Optional[int] = None
    num_days: int
    items: List[FIMItem]

# ─── Internal helpers ─────────────────────────────────────────────────────────

def _smooth_fim_idf(total_docs: int, docs_with_tag: int) -> float:
    if total_docs <= 0 or docs_with_tag <= 0:
        return 1.0
    raw = math.log((total_docs + 1) / (docs_with_tag + 1)) + 1.0
    blended = 1.0 + FIM_IDF_ALPHA * (raw - 1.0)
    return round(min(FIM_IDF_MAX_WEIGHT, max(1.0, blended)), 4)


def get_fim_tag_idf(db: Session) -> Dict[str, float]:
    """Combined city+attraction IDF, cached lazily for FIM ranking."""
    global _fim_tag_idf_cache
    if _fim_tag_idf_cache is not None:
        return _fim_tag_idf_cache

    total_docs = (
        (db.query(func.count(City.id)).scalar() or 0)
        + (db.query(func.count(Attraction.id)).scalar() or 0)
    )
    df_by_slug: Dict[str, int] = defaultdict(int)

    city_rows = (
        db.query(Tag.slug, func.count(city_tags.c.city_id))
        .join(city_tags, city_tags.c.tag_id == Tag.id)
        .group_by(Tag.slug)
        .all()
    )
    attraction_rows = (
        db.query(Tag.slug, func.count(attraction_tags.c.attraction_id))
        .join(attraction_tags, attraction_tags.c.tag_id == Tag.id)
        .group_by(Tag.slug)
        .all()
    )

    for slug, count in city_rows + attraction_rows:
        df_by_slug[slug] += int(count or 0)

    _fim_tag_idf_cache = {
        slug: _smooth_fim_idf(total_docs, docs_with_tag)
        for slug, docs_with_tag in df_by_slug.items()
    }
    return _fim_tag_idf_cache


def _score_weight(slug: str, score: float, tag_idf_by_slug: Optional[Dict[str, float]]) -> float:
    idf = (tag_idf_by_slug or {}).get(slug, 1.0)
    strength = min(abs(score), 1.0)
    effective_idf = 1.0 + (idf - 1.0) * strength
    return score * math.sqrt(effective_idf)


def _weighted_cosine(
    tag_scores: Dict[str, float],
    item_tag_weights: Dict[str, float],
    tag_idf_by_slug: Optional[Dict[str, float]] = None,
) -> float:
    if not tag_scores or not item_tag_weights:
        return 0.0

    norm_user = math.sqrt(
        sum(_score_weight(slug, score, tag_idf_by_slug) ** 2 for slug, score in tag_scores.items())
    )
    norm_item = math.sqrt(
        sum(_score_weight(slug, score, tag_idf_by_slug) ** 2 for slug, score in item_tag_weights.items())
    )
    if norm_user == 0.0 or norm_item == 0.0:
        return 0.0

    dot = 0.0
    for slug, item_score in item_tag_weights.items():
        user_score = tag_scores.get(slug, 0.0)
        if user_score == 0.0:
            continue
        dot += (
            _score_weight(slug, user_score, tag_idf_by_slug)
            * _score_weight(slug, item_score, tag_idf_by_slug)
        )
    return dot / (norm_user * norm_item)


def _load_city_tag_weights(db: Session, city_ids: List[int]) -> Dict[int, Dict[str, float]]:
    if not city_ids:
        return {}
    rows = (
        db.query(city_tags.c.city_id, Tag.slug, city_tags.c.score)
        .join(Tag, Tag.id == city_tags.c.tag_id)
        .filter(city_tags.c.city_id.in_(city_ids))
        .all()
    )
    weights: Dict[int, Dict[str, float]] = defaultdict(dict)
    for city_id, slug, score in rows:
        weights[int(city_id)][slug] = float(score or 1.0)
    return weights


def _load_attraction_tag_weights(db: Session, attraction_ids: List[int]) -> Dict[int, Dict[str, float]]:
    if not attraction_ids:
        return {}
    rows = (
        db.query(attraction_tags.c.attraction_id, Tag.slug, attraction_tags.c.score)
        .join(Tag, Tag.id == attraction_tags.c.tag_id)
        .filter(attraction_tags.c.attraction_id.in_(attraction_ids))
        .all()
    )
    weights: Dict[int, Dict[str, float]] = defaultdict(dict)
    for attraction_id, slug, score in rows:
        weights[int(attraction_id)][slug] = float(score or 1.0)
    return weights


def _fallback_tag_weights(entity) -> Dict[str, float]:
    return {tag.slug: 1.0 for tag in (entity.tags or [])}


def _ranked_tags(
    tag_weights: Dict[str, float],
    tag_scores: Dict[str, float],
    tag_idf_by_slug: Optional[Dict[str, float]],
    limit: int = 3,
) -> List[str]:
    ranked = sorted(
        tag_weights.items(),
        key=lambda item: (
            item[1]
            * (1.0 + max(tag_scores.get(item[0], 0.0), 0.0))
            * (tag_idf_by_slug or {}).get(item[0], 1.0)
        ),
        reverse=True,
    )
    return [slug for slug, _ in ranked[:limit]]


def _format_tag_label(slug: str) -> str:
    return (slug or "").replace("-", " ").strip().title()


def _top_matching_tags(
    tag_weights: Dict[str, float],
    profile: Dict[str, float],
    tag_idf_by_slug: Dict[str, float],
    limit: int = 3,
) -> List[str]:
    ranked = []
    for slug, weight in tag_weights.items():
        profile_score = float(profile.get(slug, 0.0))
        if profile_score <= 0:
            continue
        ranked.append((
            slug,
            profile_score * weight * tag_idf_by_slug.get(slug, 1.0),
        ))
    ranked.sort(key=lambda item: item[1], reverse=True)
    return [slug for slug, _ in ranked[:limit]]


def _build_solo_explanations(
    tag_weights: Dict[str, float],
    tag_scores: Dict[str, float],
    tag_idf_by_slug: Dict[str, float],
    context_reasons: Optional[List[str]] = None,
) -> List[str]:
    explanations = []
    matched = _top_matching_tags(tag_weights, tag_scores, tag_idf_by_slug, limit=3)
    if matched:
        labels = [_format_tag_label(slug) for slug in matched[:2]]
        explanations.append(f"Matches your interest in {' and '.join(labels)}.")

    distinctive = [
        slug for slug in matched
        if tag_idf_by_slug.get(slug, 1.0) >= 1.45
    ]
    if distinctive:
        explanations.append(f"Distinctive fit: {_format_tag_label(distinctive[0])}.")

    for reason in context_reasons or []:
        if reason and reason not in explanations:
            explanations.append(reason)

    return explanations[:4]


def _profile_from_quiz_session(session: Optional[QuizV4Session]) -> Dict[str, float]:
    if not session:
        return {}
    raw_profile = session.final_profile or session.tag_scores or {}
    profile = {}
    for slug, value in raw_profile.items():
        try:
            score = float(value)
        except (TypeError, ValueError):
            continue
        if score > 0:
            profile[slug] = score
    return profile


def _latest_completed_session_for_user(db: Session, user_id: int) -> Optional[QuizV4Session]:
    return (
        db.query(QuizV4Session)
        .filter(
            QuizV4Session.user_id == user_id,
            QuizV4Session.current_stage == "completed",
        )
        .order_by(
            QuizV4Session.completed_at.desc(),
            QuizV4Session.started_at.desc(),
        )
        .first()
    )


def _member_name(user: Optional[User], current_user: Optional[User] = None) -> str:
    if current_user and user and user.id == current_user.id:
        return "You"
    if not user:
        return "Traveller"
    return user.full_name or user.username or f"User {user.id}"


def _load_group_member_profiles(
    db: Session,
    group_trip_id: Optional[int],
    current_user: User,
) -> List[dict]:
    if not group_trip_id:
        return []

    from app.models.social import GroupTrip, GroupTripMember

    group_trip = db.query(GroupTrip).filter(GroupTrip.id == group_trip_id).first()
    if not group_trip:
        return []

    members = (
        db.query(GroupTripMember)
        .filter(GroupTripMember.trip_id == group_trip_id)
        .all()
    )
    if not any(member.user_id == current_user.id for member in members):
        raise HTTPException(status_code=403, detail="Not authorized for this group trip")

    rows = []
    for member in members:
        session = None
        if member.session_id:
            try:
                sid = UUID(member.session_id)
                session = (
                    db.query(QuizV4Session)
                    .filter(QuizV4Session.id == sid)
                    .first()
                )
                if session and session.user_id is not None and session.user_id != member.user_id:
                    session = None
            except (TypeError, ValueError):
                session = None
        if not _profile_from_quiz_session(session):
            session = _latest_completed_session_for_user(db, member.user_id)

        profile = _profile_from_quiz_session(session)
        if not profile:
            continue

        rows.append({
            "user_id": member.user_id,
            "name": _member_name(member.user, current_user),
            "profile": profile,
            "session_id": str(session.id) if session else None,
        })

    return rows


def _build_group_explanation(
    item_name: str,
    tag_weights: Dict[str, float],
    tag_idf_by_slug: Dict[str, float],
    member_profiles: List[dict],
) -> Optional[dict]:
    if not member_profiles:
        return None

    member_reasons = []
    fit_count = 0
    for row in member_profiles:
        profile = row["profile"]
        score = _weighted_cosine(profile, tag_weights, tag_idf_by_slug)
        matched = _top_matching_tags(tag_weights, profile, tag_idf_by_slug, limit=2)
        is_fit = score >= 0.08 or bool(matched)
        if is_fit:
            fit_count += 1
        member_reasons.append({
            "user_id": row["user_id"],
            "name": row["name"],
            "score": round(score, 4),
            "fit": "good" if is_fit else "weak",
            "reasons": [_format_tag_label(slug) for slug in matched],
        })

    member_reasons.sort(key=lambda item: item["score"], reverse=True)
    total = len(member_profiles)
    if fit_count == total:
        summary = f"Good group fit: {fit_count}/{total} travellers match {item_name}."
    elif fit_count > 0:
        summary = f"Balanced pick: {fit_count}/{total} travellers have clear matches for {item_name}."
    else:
        summary = f"Weak group fit: this may need manual adjustment."

    return {
        "summary": summary,
        "fit_count": fit_count,
        "total_members": total,
        "member_reasons": member_reasons,
    }


def _load_user_vec(session_id: str, db: Session, current_user: Optional[User] = None):
    """Returnează (tag_scores dict, norm_user float)."""
    try:
        sid = UUID(session_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid session_id (not a valid UUID)")

    session = db.query(QuizV4Session).filter(QuizV4Session.id == sid).first()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    if current_user and session.user_id is not None and session.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Session does not belong to current user")

    raw_scores: dict = session.final_profile or session.tag_scores or {}
    tag_scores = {slug: float(score) for slug, score in raw_scores.items() if score}
    norm_user = math.sqrt(sum(v ** 2 for v in tag_scores.values()))
    return tag_scores, norm_user


def _cosine(tag_scores: dict, norm_user: float, attraction_slugs: List[str]) -> float:
    """
    Cosine similarity între user_vector (continuu) și attraction_vector (binar).
    Echivalent matematic cu full-vector cosine, fără a aloca vectorii.
    """
    if not attraction_slugs or norm_user == 0.0:
        return 0.0
    dot = sum(tag_scores.get(slug, 0.0) for slug in attraction_slugs)
    norm_attr = math.sqrt(len(attraction_slugs))
    return dot / (norm_user * norm_attr)


def _score_attractions(
    attractions,
    tag_scores: dict,
    norm_user: float,
    tag_weights_by_attraction: Optional[Dict[int, Dict[str, float]]] = None,
    tag_idf_by_slug: Optional[Dict[str, float]] = None,
    group_member_profiles: Optional[List[dict]] = None,
) -> List[dict]:
    """Scoruiește și sortează o listă de obiecte Attraction."""
    results = []
    for attr in attractions:
        tag_weights = (tag_weights_by_attraction or {}).get(attr.id) or _fallback_tag_weights(attr)
        score = _weighted_cosine(tag_scores, tag_weights, tag_idf_by_slug)
        slugs = _ranked_tags(tag_weights, tag_scores, tag_idf_by_slug, limit=4)
        matched = [s for s in slugs if tag_scores.get(s, 0.0) > 0]
        explanations = _build_solo_explanations(tag_weights, tag_scores, tag_idf_by_slug or {})
        group_explanation = _build_group_explanation(
            attr.name,
            tag_weights,
            tag_idf_by_slug or {},
            group_member_profiles or [],
        )
        results.append({
            "id": attr.id,
            "name": attr.name,
            "score": round(score, 4),
            "tags": slugs,
            "matched_tags": matched,
            "explanations": explanations,
            "group_explanation": group_explanation,
            "lat": attr.latitude,
            "lng": attr.longitude,
            "avg_duration_hours": attr.avg_duration_hours,
            "entry_fee_eur": attr.entry_fee_eur,
            "rating": attr.rating,
            "image_url": attr.image_url,
        })
    results.sort(key=lambda x: x["score"], reverse=True)
    return results


def _haversine_km(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    radius_km = 6371.0
    d_lat = math.radians(lat2 - lat1)
    d_lng = math.radians(lng2 - lng1)
    a = (
        math.sin(d_lat / 2) ** 2
        + math.cos(math.radians(lat1))
        * math.cos(math.radians(lat2))
        * math.sin(d_lng / 2) ** 2
    )
    return radius_km * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def _novelty_score(
    candidate_weights: Dict[str, float],
    day_tag_weights: Dict[str, float],
    tag_idf_by_slug: Dict[str, float],
) -> float:
    if not candidate_weights or not day_tag_weights:
        return 1.0

    weighted_total = sum(
        weight * tag_idf_by_slug.get(slug, 1.0)
        for slug, weight in candidate_weights.items()
    )
    if weighted_total <= 0:
        return 1.0

    weighted_overlap = sum(
        min(weight, day_tag_weights.get(slug, 0.0)) * tag_idf_by_slug.get(slug, 1.0)
        for slug, weight in candidate_weights.items()
    )
    overlap_ratio = min(weighted_overlap / weighted_total, 1.0)
    return 1.0 - overlap_ratio


def _route_proximity_score(last_attraction: Optional[Attraction], candidate: Attraction) -> float:
    if (
        not last_attraction
        or last_attraction.latitude is None
        or last_attraction.longitude is None
        or candidate.latitude is None
        or candidate.longitude is None
    ):
        return 0.5

    km = _haversine_km(
        last_attraction.latitude,
        last_attraction.longitude,
        candidate.latitude,
        candidate.longitude,
    )
    return 1.0 - min(km / 8.0, 1.0)


def _duration_fit_score(candidate: Attraction, remaining_hours: float) -> float:
    duration = float(candidate.avg_duration_hours or 1.0)
    if duration <= 0:
        return 1.0
    if remaining_hours >= duration:
        return 1.0
    if remaining_hours <= 0:
        return 0.2 if duration <= 1.5 else 0.0
    return max(0.1, min(remaining_hours / duration, 1.0))


def _rating_score(candidate: Attraction) -> float:
    if candidate.rating is None:
        return 0.5
    return max(0.0, min(float(candidate.rating) / 5.0, 1.0))


def _score_suggested_attractions(
    attractions,
    tag_scores: dict,
    tag_weights_by_attraction: Dict[int, Dict[str, float]],
    tag_idf_by_slug: Dict[str, float],
    current_day_attractions: List[Attraction],
    last_attraction: Optional[Attraction],
    group_member_profiles: Optional[List[dict]] = None,
) -> List[dict]:
    day_tag_weights: Dict[str, float] = defaultdict(float)
    for attr in current_day_attractions:
        for slug, weight in (tag_weights_by_attraction.get(attr.id) or _fallback_tag_weights(attr)).items():
            day_tag_weights[slug] += weight

    used_hours = sum(float(attr.avg_duration_hours or 1.0) for attr in current_day_attractions)
    remaining_hours = max(MAX_DAY_HOURS - used_hours, 0.0)

    results = []
    for attr in attractions:
        tag_weights = tag_weights_by_attraction.get(attr.id) or _fallback_tag_weights(attr)
        taste_score = _weighted_cosine(tag_scores, tag_weights, tag_idf_by_slug)
        novelty = _novelty_score(tag_weights, day_tag_weights, tag_idf_by_slug)
        proximity = _route_proximity_score(last_attraction, attr)
        duration_fit = _duration_fit_score(attr, remaining_hours)
        rating = _rating_score(attr)
        context_reasons = []
        if proximity >= 0.65 and last_attraction:
            context_reasons.append("Close to your last stop.")
        if novelty >= 0.55 and day_tag_weights:
            context_reasons.append("Adds variety to this day.")
        if duration_fit >= 0.9:
            context_reasons.append("Fits the time left today.")
        final_score = (
            SUGGESTED_TASTE_WEIGHT * taste_score
            + SUGGESTED_NOVELTY_WEIGHT * novelty
            + SUGGESTED_PROXIMITY_WEIGHT * proximity
            + SUGGESTED_DURATION_WEIGHT * duration_fit
            + SUGGESTED_RATING_WEIGHT * rating
        )

        slugs = _ranked_tags(tag_weights, tag_scores, tag_idf_by_slug, limit=4)
        matched = [s for s in slugs if tag_scores.get(s, 0.0) > 0]
        explanations = _build_solo_explanations(
            tag_weights,
            tag_scores,
            tag_idf_by_slug,
            context_reasons,
        )
        group_explanation = _build_group_explanation(
            attr.name,
            tag_weights,
            tag_idf_by_slug,
            group_member_profiles or [],
        )
        results.append({
            "id": attr.id,
            "name": attr.name,
            "score": round(final_score, 4),
            "tags": slugs,
            "matched_tags": matched,
            "explanations": explanations,
            "group_explanation": group_explanation,
            "lat": attr.latitude,
            "lng": attr.longitude,
            "avg_duration_hours": attr.avg_duration_hours,
            "entry_fee_eur": attr.entry_fee_eur,
            "rating": attr.rating,
            "image_url": attr.image_url,
        })

    results.sort(key=lambda x: x["score"], reverse=True)
    return results


def _resolve_city_coords(city: City) -> Optional[tuple]:
    """lat, lng pentru un oraș — DB → CITY_COORDS dict → prima atracție."""
    if city.latitude and city.longitude:
        return city.latitude, city.longitude
    if city.name in CITY_COORDS:
        return CITY_COORDS[city.name]
    for attr in city.attractions:
        if attr.latitude and attr.longitude:
            return attr.latitude, attr.longitude
    return None

# ─── GET /fim/cities ──────────────────────────────────────────────────────────

def _resolve_country_by_query(db: Session, country: str, country_id: Optional[int]) -> Country:
    country_obj = None
    if country_id:
        country_obj = db.query(Country).filter(Country.id == country_id).first()
    if not country_obj:
        country_obj = (
            db.query(Country)
            .filter(
                (Country.name.ilike(country)) | (Country.iso2.ilike(country))
            )
            .first()
        )
    if not country_obj:
        raise HTTPException(status_code=404, detail=f"Country '{country}' does not exist in DB")
    return country_obj


def _score_cities_for_country(
    db: Session,
    country_obj: Country,
    tag_scores: dict,
    group_member_profiles: Optional[List[dict]] = None,
) -> List[dict]:
    cities = (
        db.query(City)
        .filter(City.country_id == country_obj.id)
        .options(selectinload(City.attractions).selectinload(Attraction.tags))
        .all()
    )

    tag_idf_by_slug = get_fim_tag_idf(db)
    city_ids = [city.id for city in cities]
    attraction_ids = [
        attr.id
        for city in cities
        for attr in city.attractions
    ]
    city_tag_weights_by_city = _load_city_tag_weights(db, city_ids)
    tag_weights_by_attraction = _load_attraction_tag_weights(db, attraction_ids)

    city_results = []
    for city in cities:
        if not city.attractions:
            continue

        scored = []
        for attr in city.attractions:
            tag_weights = tag_weights_by_attraction.get(attr.id) or _fallback_tag_weights(attr)
            score = _weighted_cosine(tag_scores, tag_weights, tag_idf_by_slug)
            scored.append((score, tag_weights))

        scored.sort(key=lambda item: item[0], reverse=True)
        top5 = scored[:5]
        attraction_score = sum(score for score, _ in top5) / len(top5) if top5 else 0.0
        city_tag_weights = city_tag_weights_by_city.get(city.id, {})
        city_profile_score = _weighted_cosine(tag_scores, city_tag_weights, tag_idf_by_slug)
        coverage_bonus = (
            min(math.log1p(len(city.attractions)) / math.log1p(12), 1.0)
            * CITY_COVERAGE_BONUS
        )
        city_score = min(
            1.0,
            (CITY_ATTRACTION_WEIGHT * attraction_score)
            + (CITY_PROFILE_WEIGHT * city_profile_score)
            + coverage_bonus,
        )

        tag_counter: Counter = Counter()
        for slug, weight in city_tag_weights.items():
            tag_counter[slug] += (
                weight
                * (1.0 + max(tag_scores.get(slug, 0.0), 0.0))
                * tag_idf_by_slug.get(slug, 1.0)
                * 1.5
            )
        for _, weights in scored[:10]:
            for slug, weight in weights.items():
                tag_counter[slug] += (
                    weight
                    * (1.0 + max(tag_scores.get(slug, 0.0), 0.0))
                    * tag_idf_by_slug.get(slug, 1.0)
                )

        top_tags = [tag for tag, _ in tag_counter.most_common(3)]
        city_explanation_weights = dict(tag_counter)
        explanations = _build_solo_explanations(
            city_explanation_weights,
            tag_scores,
            tag_idf_by_slug,
        )
        group_explanation = _build_group_explanation(
            city.name,
            city_explanation_weights,
            tag_idf_by_slug,
            group_member_profiles or [],
        )

        coords = _resolve_city_coords(city)
        if coords is None:
            logger.warning("Nu s-au gasit coordonate pentru city '%s', skip.", city.name)
            continue
        lat, lng = coords

        city_results.append({
            "id": city.id,
            "city": city.name,
            "country": country_obj.name,
            "score": round(city_score, 4),
            "tags": top_tags,
            "explanations": explanations,
            "group_explanation": group_explanation,
            "attraction_count": len(city.attractions),
            "lat": lat,
            "lng": lng,
            "description": city.description,
            "image_url": city.image_url,
        })

    city_results.sort(key=lambda item: item["score"], reverse=True)
    return city_results


def _next_city_distance_score(
    last_lat: Optional[float],
    last_lng: Optional[float],
    city: dict,
) -> tuple[float, Optional[float]]:
    if last_lat is None or last_lng is None or city.get("lat") is None or city.get("lng") is None:
        return 0.5, None
    distance_km = _haversine_km(last_lat, last_lng, city["lat"], city["lng"])
    return 1.0 - min(distance_km / 450.0, 1.0), distance_km


@router.get("/cities", response_model=List[CityResult])
def get_fim_cities(
    country: str = Query(..., description="Numele țării, ex: 'France'"),
    country_id: Optional[int] = Query(None),
    group_trip_id: Optional[int] = Query(None),
    session_id: str = Query(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Returnează orașele dintr-o țară scoruite după profilul user-ului.
    city_score = mean(top 5 scoruri de atracții din acel city).
    """
    tag_scores, norm_user = _load_user_vec(session_id, db, current_user)
    group_member_profiles = _load_group_member_profiles(db, group_trip_id, current_user)
    country_obj = _resolve_country_by_query(db, country, country_id)
    city_results = _score_cities_for_country(db, country_obj, tag_scores, group_member_profiles)
    logger.info("/fim/cities country=%s -> %d cities returned", country, len(city_results))
    return city_results


@router.get("/next-city", response_model=Optional[NextCityResult])
def get_next_city(
    country: str = Query(...),
    country_id: Optional[int] = Query(None),
    group_trip_id: Optional[int] = Query(None),
    session_id: str = Query(...),
    visited_city_ids: Optional[List[int]] = Query(None),
    visited_city_names: Optional[List[str]] = Query(None),
    last_lat: Optional[float] = Query(None),
    last_lng: Optional[float] = Query(None),
    current_day: int = Query(1),
    days: int = Query(1),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    tag_scores, norm_user = _load_user_vec(session_id, db, current_user)
    group_member_profiles = _load_group_member_profiles(db, group_trip_id, current_user)
    country_obj = _resolve_country_by_query(db, country, country_id)

    visited_ids = {int(value) for value in (visited_city_ids or []) if value is not None}
    visited_names = {str(value).strip().lower() for value in (visited_city_names or []) if value}

    candidates = [
        city for city in _score_cities_for_country(db, country_obj, tag_scores, group_member_profiles)
        if city["id"] not in visited_ids and city["city"].strip().lower() not in visited_names
    ]
    if not candidates:
        return None

    remaining_days = max(int(days) - int(current_day) + 1, 1)
    ranked = []
    for city in candidates:
        profile_score = float(city["score"])
        distance_score, distance_km = _next_city_distance_score(last_lat, last_lng, city)
        density_score = min(math.log1p(city.get("attraction_count") or 0) / math.log1p(14), 1.0)
        schedule_score = distance_score if remaining_days <= 1 else 0.75 + (0.25 * distance_score)
        final_score = (
            0.58 * profile_score
            + 0.24 * distance_score
            + 0.12 * density_score
            + 0.06 * schedule_score
        )

        reasons = []
        if city.get("explanations"):
            reasons.append(city["explanations"][0])
        if distance_km is not None:
            reasons.append(f"Efficient next hop: about {round(distance_km)} km from your last stop.")
        else:
            reasons.append("Best unvisited city based on your current profile.")
        if city.get("attraction_count", 0) >= 6:
            reasons.append("Enough recommended attractions to fill another day.")
        if remaining_days <= 1:
            reasons.append("Prioritised for the final available day.")

        enriched = {
            **city,
            "profile_score": round(profile_score, 4),
            "score": round(min(final_score, 1.0), 4),
            "distance_km": round(distance_km, 1) if distance_km is not None else None,
            "next_city_reasons": reasons[:4],
        }
        ranked.append(enriched)

    ranked.sort(key=lambda item: item["score"], reverse=True)
    return ranked[0]


@router.get("/cities/{city_id}/attractions", response_model=List[AttractionResult])
def get_city_attractions(
    city_id: int,
    session_id: str = Query(...),
    group_trip_id: Optional[int] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Toate atracțiile dintr-un city, sortate după cosine cu profilul user."""
    tag_scores, norm_user = _load_user_vec(session_id, db, current_user)
    group_member_profiles = _load_group_member_profiles(db, group_trip_id, current_user)

    city = (
        db.query(City)
        .filter(City.id == city_id)
        .options(selectinload(City.attractions).selectinload(Attraction.tags))
        .first()
    )
    if not city:
        raise HTTPException(status_code=404, detail=f"City id '{city_id}' does not exist in DB")

    attraction_ids = [attr.id for attr in city.attractions]
    tag_weights_by_attraction = _load_attraction_tag_weights(db, attraction_ids)
    tag_idf_by_slug = get_fim_tag_idf(db)
    return _score_attractions(
        city.attractions,
        tag_scores,
        norm_user,
        tag_weights_by_attraction,
        tag_idf_by_slug,
        group_member_profiles,
    )

# ─── GET /fim/cities/{city_id}/suggested ──────────────────────────────────────

@router.get("/cities/{city_id}/suggested", response_model=List[AttractionResult])
def get_city_suggested(
    city_id: int,
    session_id: str = Query(...),
    exclude_ids: List[int] = Query(default=[]),
    current_day_ids: List[int] = Query(default=[]),
    last_attraction_id: Optional[int] = Query(None),
    group_trip_id: Optional[int] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Top 5 atracții sugerate, excluzând cele deja adăugate în trip."""
    tag_scores, norm_user = _load_user_vec(session_id, db, current_user)
    group_member_profiles = _load_group_member_profiles(db, group_trip_id, current_user)

    city = (
        db.query(City)
        .filter(City.id == city_id)
        .options(selectinload(City.attractions).selectinload(Attraction.tags))
        .first()
    )
    if not city:
        raise HTTPException(status_code=404, detail=f"City id '{city_id}' does not exist in DB")

    eligible = [a for a in city.attractions if a.id not in exclude_ids]
    context_ids = list(dict.fromkeys(
        [aid for aid in current_day_ids if aid]
        + ([last_attraction_id] if last_attraction_id else [])
    ))
    context_attractions = (
        db.query(Attraction)
        .filter(Attraction.id.in_(context_ids))
        .options(selectinload(Attraction.tags))
        .all()
    ) if context_ids else []
    context_by_id = {attr.id: attr for attr in context_attractions}

    attraction_ids = list(dict.fromkeys(
        [attr.id for attr in eligible]
        + [attr.id for attr in context_attractions]
    ))
    tag_weights_by_attraction = _load_attraction_tag_weights(db, attraction_ids)
    tag_idf_by_slug = get_fim_tag_idf(db)

    current_day_attractions = [
        context_by_id[aid]
        for aid in current_day_ids
        if aid in context_by_id
    ]
    last_attraction = context_by_id.get(last_attraction_id) if last_attraction_id else None

    scored = _score_suggested_attractions(
        eligible,
        tag_scores,
        tag_weights_by_attraction,
        tag_idf_by_slug,
        current_day_attractions,
        last_attraction,
        group_member_profiles,
    )
    return scored[:5]

# ─── FIM trip persistence ─────────────────────────────────────────────────────

def _resolve_country(body: FIMTripSave, db: Session) -> Country:
    query = db.query(Country)
    if body.country_id:
        country_obj = query.filter(Country.id == body.country_id).first()
        if country_obj:
            return country_obj

    country_obj = query.filter(
        (Country.name.ilike(body.country)) | (Country.iso2.ilike(body.country))
    ).first()
    if not country_obj:
        raise HTTPException(status_code=404, detail=f"Country '{body.country}' not found")
    return country_obj


def _attraction_payload(attr: Attraction) -> dict:
    slugs = [t.slug for t in (attr.tags or [])]
    return {
        "id": attr.id,
        "name": attr.name,
        "score": None,
        "tags": slugs,
        "matched_tags": slugs,
        "lat": attr.latitude,
        "lng": attr.longitude,
        "avg_duration_hours": attr.avg_duration_hours,
        "entry_fee_eur": attr.entry_fee_eur,
        "image_url": attr.image_url,
    }


def _city_payload(city: Optional[City]) -> Optional[dict]:
    if not city:
        return None
    return {
        "id": city.id,
        "name": city.name,
        "city": city.name,
        "lat": city.latitude,
        "lng": city.longitude,
        "tags": [],
    }


def _save_fim_trip(body: FIMTripSave, db: Session, current_user: User):
    """Salvează un trip construit în Full Interactive Mode."""
    if body.num_days < 1 or body.num_days > 10:
        raise HTTPException(status_code=400, detail="num_days must be between 1 and 10")
    if not body.items:
        raise HTTPException(status_code=400, detail="Trip must contain at least one stop")

    try:
        sid = UUID(body.session_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid session_id")

    session = db.query(QuizV4Session).filter(QuizV4Session.id == sid).first()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    if session.user_id is None or session.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Session does not belong to current user")

    country_obj = _resolve_country(body, db)
    group_trip_id = None
    if body.group_trip_id:
        from app.models.social import GroupTrip, GroupTripMember
        group_trip = db.query(GroupTrip).filter(GroupTrip.id == body.group_trip_id).first()
        if not group_trip:
            raise HTTPException(status_code=404, detail="Group trip not found")
        if group_trip.country_id != country_obj.id:
            raise HTTPException(status_code=400, detail="Group trip country does not match selected country")
        is_member = db.query(GroupTripMember).filter(
            GroupTripMember.trip_id == group_trip.id,
            GroupTripMember.user_id == current_user.id,
        ).first()
        if not is_member:
            raise HTTPException(status_code=403, detail="Not authorized for this group trip")
        group_trip_id = group_trip.id

    attraction_ids = list(dict.fromkeys(item.attraction_id for item in body.items))
    attractions = (
        db.query(Attraction)
        .filter(Attraction.id.in_(attraction_ids))
        .options(selectinload(Attraction.city), selectinload(Attraction.tags))
        .all()
    )
    attractions_by_id = {a.id: a for a in attractions}
    missing = [aid for aid in attraction_ids if aid not in attractions_by_id]
    if missing:
        raise HTTPException(status_code=404, detail=f"Attractions not found: {missing}")

    wrong_country = [
        a.id for a in attractions
        if not a.city or a.city.country_id != country_obj.id
    ]
    if wrong_country:
        raise HTTPException(status_code=400, detail="Some attractions do not belong to selected country")

    by_day: dict = defaultdict(list)
    for item in sorted(body.items, key=lambda i: (i.day, i.order)):
        if item.day < 1 or item.day > body.num_days:
            raise HTTPException(status_code=400, detail="Item day is outside trip range")
        by_day[item.day].append(item.attraction_id)

    plan = ItineraryPlan(
        session_id=body.session_id,
        country_id=country_obj.id,
        nr_zile=body.num_days,
        user_id=current_user.id,
        group_trip_id=group_trip_id,
        is_saved=True,
        source="fim",
    )
    db.add(plan)
    db.flush()

    for day_num, attr_ids in sorted(by_day.items()):
        first_attr = attractions_by_id[attr_ids[0]]
        db.add(ItineraryDay(
            plan_id=plan.id,
            day_number=day_num,
            city_id=first_attr.city_id,
            attraction_ids=attr_ids,
        ))

    db.commit()
    logger.info("FIM trip saved: plan_id=%s user_id=%s country=%s", plan.id, current_user.id, country_obj.name)
    return {"plan_id": plan.id}


@router.post("/trips")
def create_fim_trip(
    body: FIMTripSave,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return _save_fim_trip(body, db, current_user)


@router.post("/trips/save")
def save_fim_trip(
    body: FIMTripSave,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return _save_fim_trip(body, db, current_user)


@router.get("/trips")
def get_fim_trips(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Returnează trip-urile FIM salvate ale utilizatorului."""
    plans = (
        db.query(ItineraryPlan)
        .filter(
            ItineraryPlan.user_id == current_user.id,
            ItineraryPlan.source == "fim",
        )
        .order_by(ItineraryPlan.id.desc())
        .all()
    )

    result = []
    for plan in plans:
        all_ids = [aid for day in plan.days for aid in (day.attraction_ids or [])]
        preview = [
            r[0]
            for r in db.query(Attraction.name).filter(Attraction.id.in_(all_ids[:3])).all()
        ] if all_ids else []

        country_name = None
        if plan.country_id:
            c = db.query(Country).filter(Country.id == plan.country_id).first()
            if c:
                country_name = c.name

        result.append({
            "plan_id": plan.id,
            "country": country_name or "Unknown",
            "country_id": plan.country_id,
            "num_days": plan.nr_zile,
            "created_at": plan.created_at.isoformat() if plan.created_at else None,
            "total_stops": len(all_ids),
            "preview_attractions": preview,
        })

    return result


@router.get("/trips/{plan_id}")
def get_fim_trip(
    plan_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    plan = (
        db.query(ItineraryPlan)
        .filter(
            ItineraryPlan.id == plan_id,
            ItineraryPlan.source == "fim",
        )
        .first()
    )
    if not plan:
        raise HTTPException(status_code=404, detail="Trip not found")
    if plan.user_id != current_user.id:
        if not plan.group_trip_id:
            raise HTTPException(status_code=403, detail="Access denied")
        from app.models.social import GroupTripMember
        is_member = db.query(GroupTripMember).filter(
            GroupTripMember.trip_id == plan.group_trip_id,
            GroupTripMember.user_id == current_user.id,
        ).first()
        if not is_member:
            raise HTTPException(status_code=403, detail="Access denied")

    country = db.query(Country).filter(Country.id == plan.country_id).first()
    all_ids = [aid for day in plan.days for aid in (day.attraction_ids or [])]
    attractions_by_id = {
        a.id: a
        for a in (
            db.query(Attraction)
            .filter(Attraction.id.in_(all_ids))
            .options(selectinload(Attraction.city), selectinload(Attraction.tags))
            .all()
        )
    }

    items = []
    for day in sorted(plan.days, key=lambda d: d.day_number):
        for order, attraction_id in enumerate(day.attraction_ids or []):
            attr = attractions_by_id.get(attraction_id)
            if not attr:
                continue
            items.append({
                "day": day.day_number,
                "order": order,
                "city": _city_payload(attr.city),
                "attraction": _attraction_payload(attr),
            })

    return {
        "plan_id": plan.id,
        "country": country.name if country else "Unknown",
        "country_id": plan.country_id,
        "num_days": plan.nr_zile,
        "created_at": plan.created_at.isoformat() if plan.created_at else None,
        "items": items,
    }
