from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session, selectinload, joinedload
from sqlalchemy import func
from pydantic import BaseModel, Field
from typing import Literal, Optional
from uuid import UUID
from app.database import get_db
from app.dependencies import get_current_user
from app.models.user import User
from app.models.quiz_v4_session import QuizV4Session
from app.models.tag import Tag
from app.models.geography import attraction_tags, city_tags
from app.services.itinerary_builder import build_itinerary
from app.models.itinerary import ItineraryPlan, ItineraryDay, ItineraryRating
from collections import Counter
import json

router = APIRouter(prefix="/itinerary", tags=["itinerary"])

class ItineraryRequest(BaseModel):
    country_id: int
    nr_zile: int = Field(..., ge=3, le=14)
    session_id: str
    budget_level: Optional[Literal["budget", "mid", "luxury"]] = None


class RatingRequest(BaseModel):
    rating: int = Field(..., ge=1, le=5)
    aspects: list[str] = []  # ["wrong_vibe","too_many_stops","good_cities","matches_style"]


class RegenerateRequest(BaseModel):
    feedback: list[str] = []  # ["more_nature", "more_culture", "more_beach", "relaxed_pace", "cheaper"]
    budget_level: Optional[Literal["budget", "mid", "luxury"]] = None


class ReplaceAttractionRequest(BaseModel):
    attraction_id: int
    feedback: list[str] = []  # ["more_nature", "more_culture", "cheaper", "shorter"]
    apply: bool = True


class TravelMemoryRequest(BaseModel):
    liked_attraction_ids: list[int] = []
    disliked_attraction_ids: list[int] = []
    aspects: list[str] = []  # ["too_crowded", "too_expensive", "great_vibe"]


def _can_access_plan(db: Session, plan: ItineraryPlan, user_id: int) -> bool:
    if plan.user_id == user_id:
        return True
    if plan.group_trip_id:
        from app.models.social import GroupTripMember
        return db.query(GroupTripMember).filter(
            GroupTripMember.trip_id == plan.group_trip_id,
            GroupTripMember.user_id == user_id,
        ).first() is not None
    return False


def _score_to_percent(raw_score: float, min_score: float, max_score: float) -> int:
    if max_score == min_score:
        return 82
    return round(70 + ((raw_score - min_score) / (max_score - min_score)) * 26)


def _route_point_from_attr(attr) -> Optional[dict]:
    if attr.latitude is None or attr.longitude is None:
        return None
    return {
        "lat": attr.latitude,
        "lng": attr.longitude,
        "label": attr.name,
    }


def _estimate_day_transfer_hours(city, route_points: list[dict]) -> float:
    if not city or city.latitude is None or city.longitude is None or not route_points:
        return 0.0

    from app.services.genetic_tsp import haversine

    total = 0.0
    current = {"lat": city.latitude, "lng": city.longitude}
    for point in route_points:
        km = haversine(current["lat"], current["lng"], point["lat"], point["lng"])
        if km > 0:
            leg_hours = km / 18.0
            total += max(0.08, min(leg_hours, 0.75))
        current = point
    return total


def _group_plan_members(db: Session, plan: ItineraryPlan, current_user: User) -> Optional[dict]:
    if not plan.group_trip_id:
        return None

    from app.models.social import GroupTrip

    group_trip = db.query(GroupTrip).filter(GroupTrip.id == plan.group_trip_id).first()
    if not group_trip:
        return None

    members = []
    for member in group_trip.members:
        if not member.user:
            continue
        members.append({
            "id": member.user.id,
            "username": member.user.username,
            "full_name": member.user.full_name,
            "is_current_user": member.user.id == current_user.id,
        })

    return {
        "trip_id": group_trip.id,
        "name": group_trip.name,
        "members": members,
    }


def _city_experience_explanation(
    city,
    attraction_ids: list[int],
    profile: dict,
    tag_idf_by_slug: dict,
    city_tag_weights: dict,
    tag_weights_by_attraction: dict,
    attractions_by_id: dict,
    group_member_profiles: list[dict],
    build_solo_explanations,
    build_group_explanation,
    ranked_tags,
    top_matching_tags,
    weighted_cosine,
    fallback_tag_weights,
) -> dict:
    weights = Counter()
    for slug, weight in (city_tag_weights or {}).items():
        weights[slug] += float(weight or 1.0) * 1.5

    for attraction_id in attraction_ids or []:
        attr = attractions_by_id.get(attraction_id)
        if not attr:
            continue
        for slug, weight in (tag_weights_by_attraction.get(attraction_id) or fallback_tag_weights(attr)).items():
            weights[slug] += float(weight or 1.0)

    explanation_weights = dict(weights)
    if not explanation_weights:
        return {
            "city_score_raw": 0.0,
            "city_tags": [],
            "city_matched_tags": [],
            "city_explanations": [],
            "city_group_explanation": None,
        }

    city_name = city.name if city else "this city"
    return {
        "city_score_raw": weighted_cosine(profile, explanation_weights, tag_idf_by_slug) if profile else 0.0,
        "city_tags": ranked_tags(explanation_weights, profile, tag_idf_by_slug, limit=4),
        "city_matched_tags": top_matching_tags(explanation_weights, profile, tag_idf_by_slug, limit=3),
        "city_explanations": build_solo_explanations(explanation_weights, profile, tag_idf_by_slug),
        "city_group_explanation": build_group_explanation(
            city_name,
            explanation_weights,
            tag_idf_by_slug,
            group_member_profiles,
        ),
    }

@router.post("/generate")
def generate_itinerary(req: ItineraryRequest, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    days = build_itinerary(
        country_id=req.country_id,
        nr_zile=req.nr_zile,
        session_id=req.session_id,
        budget_level=req.budget_level,
        db=db
    )
    if not days:
        raise HTTPException(status_code=404, detail="No cities found for this country")

    plan = ItineraryPlan(
        session_id=req.session_id,
        country_id=req.country_id,
        nr_zile=req.nr_zile,
        user_id=current_user.id,
    )
    db.add(plan)
    db.flush()

    for day in days:
        db.add(ItineraryDay(
            plan_id=plan.id,
            day_number=day["day"],
            city_id=day["city_id"],
            attraction_ids=[a["attraction_id"] for a in day["attractions"]]
        ))
    db.commit()

    return {"plan_id": plan.id, "days": days}

@router.get("/plan/{plan_id}")
def get_plan(plan_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    plan = db.query(ItineraryPlan).filter(ItineraryPlan.id == plan_id).first()
    if not plan:
        raise HTTPException(status_code=404, detail="Plan not found")
    if not _can_access_plan(db, plan, current_user.id):
        raise HTTPException(status_code=403, detail="Access denied")
    return {
        "plan_id": plan.id,
        "country_id": plan.country_id,
        "nr_zile": plan.nr_zile,
        "days": [
            {"day": d.day_number, "city_id": d.city_id, "attraction_ids": d.attraction_ids}
            for d in sorted(plan.days, key=lambda x: x.day_number)
        ]
    }

@router.get("/plan/{plan_id}/full")
def get_plan_full(plan_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    plan = db.query(ItineraryPlan).filter(ItineraryPlan.id == plan_id).first()
    if not plan:
        raise HTTPException(status_code=404, detail="Plan not found")
    if not _can_access_plan(db, plan, current_user.id):
        raise HTTPException(status_code=403, detail="Access denied")

    from app.models.geography import Attraction

    all_attraction_ids = [aid for d in plan.days for aid in d.attraction_ids]
    attractions_by_id = {
        a.id: a
        for a in db.query(Attraction).filter(Attraction.id.in_(all_attraction_ids)).all()
    }

    days_out = []
    for d in sorted(plan.days, key=lambda x: x.day_number):
        attractions = []
        for aid in d.attraction_ids:
            attr = attractions_by_id.get(aid)
            if attr:
                attractions.append({
                    "id": attr.id,
                    "name": attr.name,
                    "description": attr.description,
                    "lat": attr.latitude,
                    "lon": attr.longitude,
                    "entry_fee_eur": attr.entry_fee_eur,
                    "avg_duration_hours": attr.avg_duration_hours,
                    "image_url": attr.image_url,
                    "rating": attr.rating,
                })
        days_out.append({
            "day": d.day_number,
            "city_id": d.city_id,
            "attractions": attractions
        })

    return {"plan_id": plan.id, "country_id": plan.country_id, "nr_zile": plan.nr_zile, "days": days_out}

@router.get("/plan/{plan_id}/cities")
def get_plan_cities(plan_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    plan = db.query(ItineraryPlan).filter(ItineraryPlan.id == plan_id).first()
    if not plan:
        raise HTTPException(status_code=404, detail="Plan not found")
    if not _can_access_plan(db, plan, current_user.id):
        raise HTTPException(status_code=403, detail="Access denied")

    from app.models.geography import City, Attraction

    all_city_ids = list({d.city_id for d in plan.days})
    all_attraction_ids = [aid for d in plan.days for aid in d.attraction_ids]
    cities_by_id = {
        c.id: c
        for c in db.query(City).filter(City.id.in_(all_city_ids)).all()
    }
    attractions_by_id = {
        a.id: a
        for a in db.query(Attraction).filter(Attraction.id.in_(all_attraction_ids)).all()
    }

    days_out = []
    for d in sorted(plan.days, key=lambda x: x.day_number):
        city = cities_by_id.get(d.city_id)
        attractions = []
        for aid in d.attraction_ids:
            attr = attractions_by_id.get(aid)
            if attr:
                attractions.append({
                    "id": attr.id,
                    "name": attr.name,
                    "category": attr.category,
                    "lat": attr.latitude,
                    "lon": attr.longitude,
                    "image_url": attr.image_url,
                })
        days_out.append({
            "day": d.day_number,
            "city_id": d.city_id,
            "city_name": city.name if city else "Unknown",
            "city_image_url": city.image_url if city else None,
            "attractions": attractions
        })

    return {
        "plan_id": plan.id,
        "nr_zile": plan.nr_zile,
        "days": days_out
    }


@router.get("/plan/{plan_id}/experience")
def get_plan_experience(plan_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    plan = db.query(ItineraryPlan).filter(ItineraryPlan.id == plan_id).first()
    if not plan:
        raise HTTPException(status_code=404, detail="Plan not found")
    if not _can_access_plan(db, plan, current_user.id):
        raise HTTPException(status_code=403, detail="Access denied")

    from uuid import UUID
    from app.models.quiz_v4_session import QuizV4Session
    from app.models.geography import Country, City, Attraction
    from app.routers.interactive_mode import (
        _build_group_explanation,
        _build_solo_explanations,
        _fallback_tag_weights,
        _load_attraction_tag_weights,
        _load_city_tag_weights,
        _load_group_member_profiles,
        _ranked_tags,
        _top_matching_tags,
        _weighted_cosine,
        get_fim_tag_idf,
    )

    country = db.query(Country).filter(Country.id == plan.country_id).first()
    ordered_days = sorted(plan.days, key=lambda x: x.day_number)
    all_city_ids = list({d.city_id for d in ordered_days if d.city_id})
    all_attraction_ids = [aid for d in ordered_days for aid in (d.attraction_ids or [])]

    cities_by_id = {
        c.id: c
        for c in db.query(City).filter(City.id.in_(all_city_ids)).all()
    } if all_city_ids else {}
    attractions_by_id = {
        a.id: a
        for a in (
            db.query(Attraction)
            .filter(Attraction.id.in_(all_attraction_ids))
            .options(selectinload(Attraction.tags))
            .all()
        )
    } if all_attraction_ids else {}

    session = None
    if plan.session_id:
        try:
            session_uuid = UUID(str(plan.session_id))
            session = db.query(QuizV4Session).filter(QuizV4Session.id == session_uuid).first()
        except (TypeError, ValueError):
            session = None
    profile = {}
    if session:
        raw_profile = session.final_profile or session.tag_scores or {}
        for slug, value in raw_profile.items():
            try:
                score = float(value)
            except (TypeError, ValueError):
                continue
            if score > 0:
                profile[slug] = score

    tag_idf_by_slug = get_fim_tag_idf(db)
    tag_weights_by_city = _load_city_tag_weights(db, all_city_ids)
    tag_weights_by_attraction = _load_attraction_tag_weights(db, all_attraction_ids)
    group_member_profiles = _load_group_member_profiles(db, plan.group_trip_id, current_user) if plan.group_trip_id else []

    raw_scores = {}
    for aid, attr in attractions_by_id.items():
        tag_weights = tag_weights_by_attraction.get(aid) or _fallback_tag_weights(attr)
        raw_scores[aid] = _weighted_cosine(profile, tag_weights, tag_idf_by_slug) if profile else 0.0

    min_score = min(raw_scores.values()) if raw_scores else 0.0
    max_score = max(raw_scores.values()) if raw_scores else 0.0

    days_out = []
    total_hours = 0.0
    total_entry_fee = 0.0
    total_attractions = 0

    for d in ordered_days:
        city = cities_by_id.get(d.city_id)
        attractions = []
        route_points = []
        day_hours = 0.0
        day_entry_fee = 0.0

        for order, aid in enumerate(d.attraction_ids or []):
            attr = attractions_by_id.get(aid)
            if not attr:
                continue

            tag_weights = tag_weights_by_attraction.get(attr.id) or _fallback_tag_weights(attr)
            tags = _ranked_tags(tag_weights, profile, tag_idf_by_slug, limit=4)
            matched_tags = _top_matching_tags(tag_weights, profile, tag_idf_by_slug, limit=3)
            explanations = _build_solo_explanations(tag_weights, profile, tag_idf_by_slug)
            group_explanation = _build_group_explanation(
                attr.name,
                tag_weights,
                tag_idf_by_slug,
                group_member_profiles,
            )

            duration = float(attr.avg_duration_hours or 0.0)
            fee = float(attr.entry_fee_eur or 0.0)
            day_hours += duration
            day_entry_fee += fee
            total_attractions += 1

            point = _route_point_from_attr(attr)
            if point:
                route_points.append(point)

            attractions.append({
                "id": attr.id,
                "order": order,
                "name": attr.name,
                "description": attr.description,
                "category": attr.category,
                "lat": attr.latitude,
                "lng": attr.longitude,
                "lon": attr.longitude,
                "image_url": attr.image_url,
                "image_credit": attr.image_credit,
                "avg_duration_hours": attr.avg_duration_hours,
                "entry_fee_eur": attr.entry_fee_eur,
                "rating": attr.rating,
                "raw_score": round(raw_scores.get(attr.id, 0.0), 4),
                "score": _score_to_percent(raw_scores.get(attr.id, 0.0), min_score, max_score),
                "tags": tags,
                "matched_tags": matched_tags,
                "explanations": explanations,
                "group_explanation": group_explanation,
            })

        transfer_hours = _estimate_day_transfer_hours(city, route_points)
        total_day_hours = day_hours + transfer_hours
        total_hours += total_day_hours
        total_entry_fee += day_entry_fee
        city_explanation = _city_experience_explanation(
            city,
            d.attraction_ids or [],
            profile,
            tag_idf_by_slug,
            tag_weights_by_city.get(d.city_id, {}),
            tag_weights_by_attraction,
            attractions_by_id,
            group_member_profiles,
            _build_solo_explanations,
            _build_group_explanation,
            _ranked_tags,
            _top_matching_tags,
            _weighted_cosine,
            _fallback_tag_weights,
        )

        days_out.append({
            "day": d.day_number,
            "day_number": d.day_number,
            "city_id": d.city_id,
            "city": city.name if city else "Unknown",
            "city_name": city.name if city else "Unknown",
            "lat": city.latitude if city else None,
            "lng": city.longitude if city else None,
            "city_image_url": city.image_url if city else None,
            "city_image_credit": city.image_credit if city else None,
            "city_description": city.description if city else None,
            "city_score_raw": round(city_explanation["city_score_raw"], 4),
            "city_tags": city_explanation["city_tags"],
            "city_matched_tags": city_explanation["city_matched_tags"],
            "city_explanations": city_explanation["city_explanations"],
            "city_group_explanation": city_explanation["city_group_explanation"],
            "visit_hours": round(day_hours, 1),
            "transfer_hours": round(transfer_hours, 1),
            "total_hours": round(total_day_hours, 1),
            "total_entry_fee": round(day_entry_fee, 2),
            "route_points": route_points,
            "attractions": attractions,
        })

    city_raw_scores = [day["city_score_raw"] for day in days_out]
    min_city_score = min(city_raw_scores) if city_raw_scores else 0.0
    max_city_score = max(city_raw_scores) if city_raw_scores else 0.0
    for day in days_out:
        day["city_score"] = _score_to_percent(day["city_score_raw"], min_city_score, max_city_score)

    city_segments = []
    for day in days_out:
        last = city_segments[-1] if city_segments else None
        if last and last["city_id"] == day["city_id"]:
            last["day_end"] = day["day"]
            last["days_count"] = last["day_end"] - last["day_start"] + 1
            last["attractions_count"] += len(day["attractions"])
            if day["city_score"] > last.get("score", 0):
                last["score"] = day["city_score"]
                last["tags"] = day["city_tags"]
                last["matched_tags"] = day["city_matched_tags"]
                last["explanations"] = day["city_explanations"]
                last["group_explanation"] = day["city_group_explanation"]
        else:
            city_segments.append({
                "city_id": day["city_id"],
                "city_name": day["city_name"],
                "day_start": day["day"],
                "day_end": day["day"],
                "days_count": 1,
                "attractions_count": len(day["attractions"]),
                "image_url": day["city_image_url"] or (day["attractions"][0]["image_url"] if day["attractions"] else None),
                "score": day["city_score"],
                "tags": day["city_tags"],
                "matched_tags": day["city_matched_tags"],
                "explanations": day["city_explanations"],
                "group_explanation": day["city_group_explanation"],
            })

    group = _group_plan_members(db, plan, current_user)

    return {
        "plan_id": plan.id,
        "country": {
            "id": country.id if country else plan.country_id,
            "name": country.name if country else "Unknown",
            "image_url": country.image_url if country else None,
            "image_credit": country.image_credit if country else None,
        },
        "country_id": plan.country_id,
        "country_name": country.name if country else "Unknown",
        "source": plan.source or "auto",
        "is_group": bool(plan.group_trip_id),
        "group": group,
        "totals": {
            "days": plan.nr_zile,
            "cities": len({d["city_id"] for d in days_out if d["city_id"]}),
            "attractions": total_attractions,
            "hours": round(total_hours, 1),
            "entry_fee_eur": round(total_entry_fee, 2),
        },
        "num_days": plan.nr_zile,
        "nr_zile": plan.nr_zile,
        "days": days_out,
        "city_segments": city_segments,
    }

class SaveRequest(BaseModel):
    group_trip_id: Optional[int] = None

@router.post("/plan/{plan_id}/save")
def save_plan(plan_id: int, req: SaveRequest = None, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    plan = db.query(ItineraryPlan).filter(ItineraryPlan.id == plan_id).first()
    if not plan:
        raise HTTPException(status_code=404, detail="Plan not found")
    if not _can_access_plan(db, plan, current_user.id):
        raise HTTPException(status_code=403, detail="Access denied")
    plan.is_saved = True
    if plan.user_id is None:
        plan.user_id = current_user.id
    if req and req.group_trip_id:
        from app.models.social import GroupTripMember
        is_member = db.query(GroupTripMember).filter(
            GroupTripMember.trip_id == req.group_trip_id,
            GroupTripMember.user_id == current_user.id,
        ).first()
        if not is_member:
            raise HTTPException(status_code=403, detail="Access denied for this group trip")
        plan.group_trip_id = req.group_trip_id
    db.commit()
    return {"saved": True, "plan_id": plan_id}


@router.delete("/plan/{plan_id}/save")
def unsave_plan(plan_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    plan = db.query(ItineraryPlan).filter(ItineraryPlan.id == plan_id).first()
    if not plan:
        raise HTTPException(status_code=404, detail="Plan not found")
    if not _can_access_plan(db, plan, current_user.id):
        raise HTTPException(status_code=403, detail="Access denied")
    if plan.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Only the plan owner can remove this saved trip")

    plan.is_saved = False
    db.commit()
    return {"saved": False, "plan_id": plan_id}

@router.get("/saved")
def get_saved_itineraries(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    from app.models.social import GroupTripMember, GroupTrip
    from app.models.geography import Country

    # 1. Planuri solo — eager-load days și country
    solo_plans = (
        db.query(ItineraryPlan)
        .options(selectinload(ItineraryPlan.days))
        .filter(
            ItineraryPlan.user_id == current_user.id,
            ItineraryPlan.is_saved == True,
            ItineraryPlan.group_trip_id == None,
        )
        .order_by(ItineraryPlan.id.desc())
        .all()
    )

    # 2. Planuri de grup — eager-load days, group_trip și membrii
    group_plans = (
        db.query(ItineraryPlan)
        .options(
            selectinload(ItineraryPlan.days),
        )
        .join(GroupTrip, GroupTrip.id == ItineraryPlan.group_trip_id)
        .join(GroupTripMember, GroupTripMember.trip_id == GroupTrip.id)
        .filter(
            GroupTripMember.user_id == current_user.id,
            ItineraryPlan.is_saved == True,
        )
        .order_by(ItineraryPlan.id.desc())
        .all()
    )

    country_ids = {p.country_id for p in solo_plans + group_plans if p.country_id}
    all_countries = {}
    if country_ids:
        all_countries = {
            c.id: c
            for c in db.query(Country).filter(Country.id.in_(country_ids)).all()
        }

    # Pre-fetch group trips and members for group plans in one query
    group_trip_ids = [p.group_trip_id for p in group_plans if p.group_trip_id]
    group_trips_map = {}
    if group_trip_ids:
        gts = (
            db.query(GroupTrip)
            .options(joinedload(GroupTrip.members).joinedload(GroupTripMember.user))
            .filter(GroupTrip.id.in_(group_trip_ids))
            .all()
        )
        group_trips_map = {gt.id: gt for gt in gts}

    def plan_to_dict(plan, is_group=False):
        # Use pre-fetched country — zero extra queries
        country = all_countries.get(plan.country_id)
        num_cities = len(set(d.city_id for d in plan.days))
        total_stops = sum(len(d.attraction_ids or []) for d in plan.days)
        result = {
            "plan_id": plan.id,
            "country_name": country.name if country else "Unknown",
            "country_id": plan.country_id,
            "capital": country.capital if country else "",
            "flag_emoji": getattr(country, "flag_emoji", None) or "🌍",
            "nr_zile": plan.nr_zile,
            "nr_cities": num_cities,
            "total_stops": total_stops,
            "is_group": is_group,
            "group_trip_id": plan.group_trip_id,
            "source": plan.source or "auto",
            "can_delete": plan.user_id == current_user.id,
            "created_at": plan.created_at.isoformat() if plan.created_at else None,
            "saved_at": plan.created_at.isoformat() if plan.created_at else None,
        }
        if is_group and plan.group_trip_id:
            # Use pre-fetched group trip — zero extra queries
            group_trip = group_trips_map.get(plan.group_trip_id)
            if group_trip:
                result["trip_name"] = group_trip.name
                members = []
                for member in group_trip.members:
                    if not member.user:
                        continue
                    members.append({
                        "id": member.user.id,
                        "username": member.user.username,
                        "full_name": member.user.full_name,
                        "is_current_user": member.user.id == current_user.id,
                    })
                result["group_members"] = members
                result["companions"] = [m for m in members if not m["is_current_user"]]
        return result

    return {
        "plans": [plan_to_dict(p, False) for p in solo_plans] +
                 [plan_to_dict(p, True) for p in group_plans]
    }


# ─── RATING ───────────────────────────────────────────────────────────────────

# How much each aspect shifts the base rating signal
_LEARNING_RATE = 0.25


_PROFILE_ASPECT_BONUS = {
    "matches_style": +0.4,
    "wrong_vibe": -0.4,
}


def _plan_rating_signal(rating: int, aspects: list) -> float:
    base_adj = (rating - 3) / 2.0
    aspect_adj = sum(_PROFILE_ASPECT_BONUS.get(a, 0) for a in (aspects or []))
    return max(-1.0, min(1.0, base_adj + aspect_adj))


def _refresh_session_profile_from_beliefs(db: Session, session: QuizV4Session) -> None:
    beliefs = session.tag_beliefs or {}
    tag_scores = {}
    for slug, belief in beliefs.items():
        alpha = float((belief or {}).get("alpha", 1.0))
        beta = float((belief or {}).get("beta", 1.0))
        denom = alpha + beta
        if denom > 0:
            tag_scores[slug] = round(alpha / denom, 4)

    session.tag_scores = tag_scores
    normalized_scores = {slug: score for slug, score in tag_scores.items() if score > 0.5}
    if not normalized_scores:
        session.final_profile = {}
        return

    nl_tags = db.query(Tag).filter(Tag.is_leaf == False).all()
    nl_by_slug = {tag.slug: tag for tag in nl_tags}
    children_by_parent: dict[int, list[Tag]] = {}
    if nl_tags:
        for tag in db.query(Tag).filter(Tag.parent_id.in_([tag.id for tag in nl_tags])).all():
            children_by_parent.setdefault(tag.parent_id, []).append(tag)

    directly_scored = set(tag_scores.keys())
    expanded = dict(normalized_scores)
    for slug, score in list(normalized_scores.items()):
        tag = nl_by_slug.get(slug)
        if not tag:
            continue
        for child in children_by_parent.get(tag.id, []):
            if child.slug not in directly_scored:
                expanded[child.slug] = expanded.get(child.slug, 0) + score * 0.6
            if not child.is_leaf:
                for grandchild in children_by_parent.get(child.id, []):
                    if grandchild.slug not in directly_scored:
                        expanded[grandchild.slug] = expanded.get(grandchild.slug, 0) + score * 0.3

    max_score = max(expanded.values()) if expanded else 1.0
    session.final_profile = {
        slug: round(score / max_score, 4)
        for slug, score in expanded.items()
        if score > 0
    }


def _apply_plan_rating_to_session(
    db: Session,
    session: QuizV4Session,
    plan_tag_weights: dict,
    rating: int,
    aspects: list,
    previous_rating: int | None = None,
    previous_aspects: list | None = None,
) -> bool:
    if not session:
        return False

    previous_signal = (
        _plan_rating_signal(previous_rating, previous_aspects)
        if previous_rating is not None
        else 0.0
    )
    signal_delta = _plan_rating_signal(rating, aspects) - previous_signal
    if abs(signal_delta) < 1e-9:
        return False

    beliefs = dict(session.tag_beliefs or {})
    for tag_slug, relevance in plan_tag_weights.items():
        if tag_slug not in beliefs:
            beliefs[tag_slug] = {"alpha": 1.0, "beta": 1.0}
        delta = signal_delta * float(relevance) * _LEARNING_RATE
        if delta > 0:
            beliefs[tag_slug]["alpha"] = beliefs[tag_slug].get("alpha", 1.0) + delta
        else:
            beliefs[tag_slug]["beta"] = beliefs[tag_slug].get("beta", 1.0) + abs(delta)

    session.tag_beliefs = beliefs
    _refresh_session_profile_from_beliefs(db, session)
    return True


def _plan_tag_weights(db: Session, plan: ItineraryPlan) -> dict[str, float]:
    attraction_ids = [
        attraction_id
        for day in plan.days
        for attraction_id in (day.attraction_ids or [])
    ]
    city_ids = list({day.city_id for day in plan.days if day.city_id})
    if not attraction_ids and not city_ids:
        return {}

    weights = Counter()
    if attraction_ids:
        rows = (
            db.query(Tag.slug, func.sum(attraction_tags.c.score).label("weight"))
            .join(attraction_tags, attraction_tags.c.tag_id == Tag.id)
            .filter(attraction_tags.c.attraction_id.in_(attraction_ids))
            .group_by(Tag.slug)
            .all()
        )
        for slug, weight in rows:
            weights[slug] += float(weight or 0.0)

    if city_ids:
        rows = (
            db.query(Tag.slug, func.sum(city_tags.c.score).label("weight"))
            .join(city_tags, city_tags.c.tag_id == Tag.id)
            .filter(city_tags.c.city_id.in_(city_ids))
            .group_by(Tag.slug)
            .all()
        )
        for slug, weight in rows:
            weights[slug] += float(weight or 0.0) * 0.5

    top_weights = dict(weights.most_common(20))
    max_weight = max(top_weights.values(), default=0.0)
    if max_weight <= 0:
        return {}

    return {
        slug: round(weight / max_weight, 4)
        for slug, weight in top_weights.items()
        if weight > 0
    }


def _rating_session_for_plan(db: Session, plan: ItineraryPlan, user_id: int) -> Optional[QuizV4Session]:
    if plan.session_id:
        try:
            session_uuid = UUID(str(plan.session_id))
            session = db.query(QuizV4Session).filter(
                QuizV4Session.id == session_uuid,
                QuizV4Session.user_id == user_id,
                QuizV4Session.current_stage == "completed",
            ).first()
            if session:
                return session
        except (TypeError, ValueError):
            pass

    return db.query(QuizV4Session).filter(
        QuizV4Session.user_id == user_id,
        QuizV4Session.current_stage == "completed",
    ).order_by(QuizV4Session.completed_at.desc().nullslast()).first()


def _apply_pace_feedback(
    session: Optional[QuizV4Session],
    rating: int,
    aspects: list,
    previous_aspects: list | None = None,
) -> bool:
    if not session:
        return False

    previous = session.pace_preference
    if "too_many_stops" in (aspects or []):
        session.pace_preference = "relaxed"
    elif "too_many_stops" in (previous_aspects or []) and previous == "relaxed":
        session.pace_preference = "balanced" if rating >= 3 else None
    elif rating >= 4 and previous is None:
        session.pace_preference = "balanced"

    return session.pace_preference != previous


_REGEN_FEEDBACK_BOOSTS = {
    "more_nature": {
        "nature-outdoors": 0.35,
        "hiking-trekking": 0.25,
        "parks-gardens": 0.25,
        "scenic-drives": 0.2,
    },
    "more_culture": {
        "culture-history": 0.35,
        "museums": 0.25,
        "historical-sites": 0.25,
        "architecture": 0.2,
    },
    "more_beach": {
        "beach-water": 0.35,
        "sandy-beaches": 0.3,
        "hidden-coves": 0.25,
        "beach-clubs-day-parties": 0.2,
    },
    "more_food": {
        "food-drink": 0.35,
        "local-cuisine": 0.25,
        "wine-tasting": 0.2,
        "cafes": 0.2,
    },
}


def _feedback_profile_boosts(feedback: list[str]) -> dict[str, float]:
    boosts = Counter()
    for key in feedback or []:
        for slug, value in _REGEN_FEEDBACK_BOOSTS.get(key, {}).items():
            boosts[slug] += value
    return dict(boosts)


def _feedback_budget_level(feedback: list[str], explicit_budget: Optional[str]) -> Optional[str]:
    if explicit_budget:
        return explicit_budget
    if "cheaper" in (feedback or []):
        return "budget"
    return None


def _session_for_current_user(db: Session, user_id: int) -> Optional[QuizV4Session]:
    return db.query(QuizV4Session).filter(
        QuizV4Session.user_id == user_id,
        QuizV4Session.current_stage == "completed",
    ).order_by(QuizV4Session.completed_at.desc().nullslast()).first()


def _tag_labels(db: Session, slugs: list[str]) -> dict[str, str]:
    if not slugs:
        return {}
    rows = db.query(Tag.slug, Tag.name).filter(Tag.slug.in_(slugs)).all()
    return {slug: name for slug, name in rows}


def _apply_tag_weights_signal_to_session(
    db: Session,
    session: Optional[QuizV4Session],
    tag_weights: dict[str, float],
    signal: float,
) -> bool:
    if not session or not tag_weights or abs(signal) < 1e-9:
        return False

    beliefs = dict(session.tag_beliefs or {})
    for tag_slug, relevance in tag_weights.items():
        if tag_slug not in beliefs:
            beliefs[tag_slug] = {"alpha": 1.0, "beta": 1.0}
        delta = signal * float(relevance) * _LEARNING_RATE
        if delta > 0:
            beliefs[tag_slug]["alpha"] = float(beliefs[tag_slug].get("alpha", 1.0)) + delta
        else:
            beliefs[tag_slug]["beta"] = float(beliefs[tag_slug].get("beta", 1.0)) + abs(delta)

    session.tag_beliefs = beliefs
    _refresh_session_profile_from_beliefs(db, session)
    db.add(session)
    return True


def _attraction_tag_weights(db: Session, attraction_ids: list[int]) -> dict[str, float]:
    if not attraction_ids:
        return {}
    rows = (
        db.query(Tag.slug, func.sum(attraction_tags.c.score).label("weight"))
        .join(attraction_tags, attraction_tags.c.tag_id == Tag.id)
        .filter(attraction_tags.c.attraction_id.in_(attraction_ids))
        .group_by(Tag.slug)
        .all()
    )
    weights = {slug: float(weight or 0.0) for slug, weight in rows}
    max_weight = max(weights.values(), default=0.0)
    if max_weight <= 0:
        return {}
    return {slug: round(weight / max_weight, 4) for slug, weight in weights.items() if weight > 0}


def _rating_event_summary(db: Session, rating: ItineraryRating, plan: ItineraryPlan) -> dict:
    weights = _plan_tag_weights(db, plan)
    signal = _plan_rating_signal(rating.rating, rating.aspects or [])
    top_slugs = list(weights.keys())[:5]
    labels = _tag_labels(db, top_slugs)
    direction = "positive" if signal > 0 else "negative" if signal < 0 else "neutral"
    return {
        "plan_id": plan.id,
        "rating": rating.rating,
        "aspects": rating.aspects or [],
        "direction": direction,
        "signal": round(signal, 3),
        "created_at": rating.created_at.isoformat() if rating.created_at else None,
        "tags": [
            {
                "slug": slug,
                "name": labels.get(slug, slug.replace("-", " ").title()),
                "impact": round(float(weights.get(slug, 0.0)) * signal, 3),
            }
            for slug in top_slugs
        ],
    }


@router.post("/plan/{plan_id}/rate")
def rate_plan(
    plan_id: int,
    req: RatingRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    plan = db.query(ItineraryPlan).filter(ItineraryPlan.id == plan_id).first()
    if not plan or not _can_access_plan(db, plan, current_user.id):
        raise HTTPException(status_code=404, detail="Plan not found")

    plan_tag_weights = _plan_tag_weights(db, plan)
    session = _rating_session_for_plan(db, plan, current_user.id)

    existing = db.query(ItineraryRating).filter(
        ItineraryRating.plan_id == plan_id,
        ItineraryRating.user_id == current_user.id,
    ).first()
    if existing:
        previous_rating = existing.rating
        previous_aspects = existing.aspects or []
        existing.rating = req.rating
        existing.aspects = req.aspects
        profile_updated = False
        if session and plan_tag_weights:
            profile_updated = _apply_plan_rating_to_session(
                db,
                session,
                plan_tag_weights,
                req.rating,
                req.aspects,
                previous_rating=previous_rating,
                previous_aspects=previous_aspects,
            )
            db.add(session)
        pace_updated = _apply_pace_feedback(session, req.rating, req.aspects, previous_aspects)
        if pace_updated:
            db.add(session)
        db.commit()
        return {
            "rated": True,
            "updated": True,
            "profile_updated": profile_updated,
            "tags_updated": list(plan_tag_weights.keys())[:8],
            "pacing_feedback": "too_many_stops" in (req.aspects or []),
            "pace_preference": session.pace_preference if session else None,
        }

    # Save rating
    db.add(ItineraryRating(
        plan_id=plan_id,
        user_id=current_user.id,
        rating=req.rating,
        aspects=req.aspects,
    ))

    profile_updated = False
    if session and plan_tag_weights:
        profile_updated = _apply_plan_rating_to_session(db, session, plan_tag_weights, req.rating, req.aspects)
        db.add(session)
    pace_updated = _apply_pace_feedback(session, req.rating, req.aspects)
    if pace_updated:
        db.add(session)

    db.commit()
    return {
        "rated": True,
        "updated": False,
        "profile_updated": profile_updated,
        "tags_updated": list(plan_tag_weights.keys())[:8],
        "pacing_feedback": "too_many_stops" in (req.aspects or []),
        "pace_preference": session.pace_preference if session else None,
    }


@router.post("/plan/{plan_id}/regenerate")
def regenerate_plan(
    plan_id: int,
    req: RegenerateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    plan = db.query(ItineraryPlan).filter(ItineraryPlan.id == plan_id).first()
    if not plan or not _can_access_plan(db, plan, current_user.id):
        raise HTTPException(status_code=404, detail="Plan not found")

    session = _rating_session_for_plan(db, plan, current_user.id)
    if session and "relaxed_pace" in (req.feedback or []) and session.pace_preference != "relaxed":
        session.pace_preference = "relaxed"
        db.add(session)
        db.flush()

    days = build_itinerary(
        country_id=plan.country_id,
        nr_zile=plan.nr_zile,
        session_id=plan.session_id,
        budget_level=_feedback_budget_level(req.feedback, req.budget_level),
        profile_boosts=_feedback_profile_boosts(req.feedback),
        db=db,
    )
    if not days:
        raise HTTPException(status_code=404, detail="No itinerary generated")

    new_plan = ItineraryPlan(
        session_id=plan.session_id,
        country_id=plan.country_id,
        nr_zile=plan.nr_zile,
        user_id=current_user.id,
        group_trip_id=plan.group_trip_id,
        source=plan.source or "auto",
        is_saved=False,
    )
    db.add(new_plan)
    db.flush()

    for day in days:
        db.add(ItineraryDay(
            plan_id=new_plan.id,
            day_number=day["day"],
            city_id=day["city_id"],
            attraction_ids=[a["attraction_id"] for a in day["attractions"]],
        ))

    db.commit()
    return {
        "plan_id": new_plan.id,
        "source_plan_id": plan.id,
        "feedback": req.feedback or [],
        "days": days,
    }


@router.post("/plan/{plan_id}/days/{day_number}/replace-attraction")
def replace_attraction(
    plan_id: int,
    day_number: int,
    req: ReplaceAttractionRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    from app.models.geography import Attraction
    from app.services.itinerary_scorer import get_user_tag_vector, score_attractions

    plan = db.query(ItineraryPlan).filter(ItineraryPlan.id == plan_id).first()
    if not plan or not _can_access_plan(db, plan, current_user.id):
        raise HTTPException(status_code=404, detail="Plan not found")

    day = next((item for item in plan.days if item.day_number == day_number), None)
    if not day or req.attraction_id not in (day.attraction_ids or []):
        raise HTTPException(status_code=404, detail="Attraction not found in this day")

    all_used_ids = {
        attraction_id
        for itinerary_day in plan.days
        for attraction_id in (itinerary_day.attraction_ids or [])
    }
    all_tag_ids = [tag.id for tag in db.query(Tag).all()]
    user_vector, user_raw_scores = get_user_tag_vector(
        plan.session_id,
        db,
        all_tag_ids,
        profile_boosts=_feedback_profile_boosts(req.feedback),
    )

    candidates = (
        db.query(Attraction)
        .filter(
            Attraction.city_id == day.city_id,
            Attraction.id.notin_(list(all_used_ids - {req.attraction_id})),
            Attraction.id != req.attraction_id,
        )
        .all()
    )
    if "cheaper" in (req.feedback or []):
        candidates = [attr for attr in candidates if float(attr.entry_fee_eur or 0.0) <= 20.0]
    if "shorter" in (req.feedback or []):
        candidates = [attr for attr in candidates if float(attr.avg_duration_hours or 1.0) <= 2.0]

    scored = score_attractions(
        candidates,
        user_vector,
        all_tag_ids,
        db,
        budget_level="budget" if "cheaper" in (req.feedback or []) else None,
        user_raw_scores=user_raw_scores,
    )
    if not scored:
        raise HTTPException(status_code=404, detail="No replacement found for this city")

    replacement = scored[0]["attraction"]
    if req.apply:
        ids = list(day.attraction_ids or [])
        day.attraction_ids = [replacement.id if aid == req.attraction_id else aid for aid in ids]
        db.add(day)
        db.commit()

    return {
        "replaced": req.apply,
        "old_attraction_id": req.attraction_id,
        "replacement": {
            "id": replacement.id,
            "name": replacement.name,
            "description": replacement.description,
            "category": replacement.category,
            "lat": replacement.latitude,
            "lng": replacement.longitude,
            "lon": replacement.longitude,
            "image_url": replacement.image_url,
            "avg_duration_hours": replacement.avg_duration_hours,
            "entry_fee_eur": replacement.entry_fee_eur,
            "rating": replacement.rating,
            "score": round(float(scored[0]["score"]), 4),
        },
    }


@router.post("/plan/{plan_id}/memory")
def save_travel_memory(
    plan_id: int,
    req: TravelMemoryRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    plan = db.query(ItineraryPlan).filter(ItineraryPlan.id == plan_id).first()
    if not plan or not _can_access_plan(db, plan, current_user.id):
        raise HTTPException(status_code=404, detail="Plan not found")

    session = _rating_session_for_plan(db, plan, current_user.id)
    liked = list(dict.fromkeys(req.liked_attraction_ids or []))
    disliked = list(dict.fromkeys(req.disliked_attraction_ids or []))

    liked_updated = _apply_tag_weights_signal_to_session(
        db,
        session,
        _attraction_tag_weights(db, liked),
        0.7 + (0.2 if "great_vibe" in (req.aspects or []) else 0.0),
    )
    disliked_updated = _apply_tag_weights_signal_to_session(
        db,
        session,
        _attraction_tag_weights(db, disliked),
        -0.7 - (0.2 if "too_crowded" in (req.aspects or []) else 0.0),
    )
    if "too_expensive" in (req.aspects or []) and session:
        session.budget = "budget"
        db.add(session)

    db.commit()
    return {
        "saved": True,
        "profile_updated": liked_updated or disliked_updated,
        "liked_count": len(liked),
        "disliked_count": len(disliked),
        "budget_preference": session.budget if session else None,
    }


@router.get("/travel-insights")
def get_travel_insights(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    ratings = (
        db.query(ItineraryRating)
        .filter(ItineraryRating.user_id == current_user.id)
        .order_by(ItineraryRating.created_at.desc())
        .limit(8)
        .all()
    )
    plan_ids = [rating.plan_id for rating in ratings]
    plans = {
        plan.id: plan
        for plan in (
            db.query(ItineraryPlan)
            .options(selectinload(ItineraryPlan.days))
            .filter(ItineraryPlan.id.in_(plan_ids))
            .all()
        )
    } if plan_ids else {}

    events = [
        _rating_event_summary(db, rating, plans[rating.plan_id])
        for rating in ratings
        if rating.plan_id in plans
    ]
    positive_events = sum(1 for event in events if event["direction"] == "positive")
    negative_events = sum(1 for event in events if event["direction"] == "negative")

    impact = Counter()
    for event in events:
        for tag in event["tags"]:
            impact[tag["slug"]] += float(tag["impact"])
    top_impact_slugs = [slug for slug, _ in impact.most_common(6)]
    labels = _tag_labels(db, top_impact_slugs)

    session = _session_for_current_user(db, current_user.id)
    profile = session.final_profile if session else {}
    top_profile = sorted((profile or {}).items(), key=lambda item: item[1], reverse=True)[:6]
    profile_labels = _tag_labels(db, [slug for slug, _ in top_profile])

    return {
        "ratings_count": len(events),
        "positive_events": positive_events,
        "negative_events": negative_events,
        "pace_preference": session.pace_preference if session else None,
        "budget_preference": session.budget if session else None,
        "profile_explanation": [
            {
                "slug": slug,
                "name": profile_labels.get(slug, slug.replace("-", " ").title()),
                "score": round(float(score), 4),
            }
            for slug, score in top_profile
        ],
        "learning_impact": [
            {
                "slug": slug,
                "name": labels.get(slug, slug.replace("-", " ").title()),
                "impact": round(float(impact[slug]), 3),
                "direction": "up" if impact[slug] > 0 else "down" if impact[slug] < 0 else "flat",
            }
            for slug in top_impact_slugs
        ],
        "recent_events": events[:5],
    }
