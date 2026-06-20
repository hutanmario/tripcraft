from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime, timezone
from types import SimpleNamespace
from app.database import get_db
from app.dependencies import get_current_user
from app.models.social import Friendship, GroupTrip, GroupTripMember
from app.models.user import User
from app.models.quiz_v4_session import QuizV4Session
from app.models.geography import Country
from app.models.tag import Tag
from app.services.country_recommender import compute_country_scores, get_country_scoring_context
import uuid as uuid_module
import numpy as np
import math

router = APIRouter(prefix="/social", tags=["social"])


def _user_payload(user: User, reason: Optional[str] = None) -> dict:
    payload = {
        "id": user.id,
        "username": user.username,
        "full_name": user.full_name,
    }
    if reason:
        payload["reason"] = reason
    return payload


def _normalize_friend_ids(current_user_id: int, member_ids: Optional[list[int]]) -> list[int]:
    normalized = []
    for member_id in member_ids or []:
        if member_id == current_user_id:
            continue
        if member_id not in normalized:
            normalized.append(member_id)
    return normalized


def _accepted_friendship(db: Session, user_id: int, friend_id: int) -> Optional[Friendship]:
    return db.query(Friendship).filter(
        Friendship.status == "accepted",
        (
            ((Friendship.requester_id == user_id) & (Friendship.receiver_id == friend_id))
            | ((Friendship.requester_id == friend_id) & (Friendship.receiver_id == user_id))
        ),
    ).first()


def _friendship_between(db: Session, user_id: int, other_user_id: int) -> Optional[Friendship]:
    return db.query(Friendship).filter(
        (
            ((Friendship.requester_id == user_id) & (Friendship.receiver_id == other_user_id))
            | ((Friendship.requester_id == other_user_id) & (Friendship.receiver_id == user_id))
        )
    ).first()


def _relationship_status(current_user_id: int, friendship: Optional[Friendship]) -> dict:
    if not friendship:
        return {
            "friendship_status": "none",
            "friendship_id": None,
            "can_send_request": True,
            "status_label": "Add",
        }
    if friendship.status == "accepted":
        status = "friends"
        label = "Friends"
    elif friendship.status == "pending" and friendship.requester_id == current_user_id:
        status = "request_sent"
        label = "Request sent"
    elif friendship.status == "pending" and friendship.receiver_id == current_user_id:
        status = "request_received"
        label = "Respond"
    else:
        status = friendship.status or "unknown"
        label = status.replace("_", " ").title()
    return {
        "friendship_status": status,
        "friendship_id": friendship.id,
        "can_send_request": status in {"none"},
        "status_label": label,
    }


def _ensure_accepted_friends(db: Session, current_user_id: int, friend_ids: list[int]) -> None:
    for friend_id in friend_ids:
        if not db.query(User).filter(User.id == friend_id).first():
            raise HTTPException(status_code=404, detail=f"User {friend_id} not found")
        if not _accepted_friendship(db, current_user_id, friend_id):
            raise HTTPException(status_code=403, detail=f"User {friend_id} is not your accepted friend")


def _profile_from_session(session: Optional[QuizV4Session]) -> dict:
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
    sessions = db.query(QuizV4Session).filter(
        QuizV4Session.user_id == user_id,
        QuizV4Session.current_stage == "completed",
    ).order_by(
        QuizV4Session.completed_at.desc(),
        QuizV4Session.started_at.desc(),
    ).limit(10).all()

    for session in sessions:
        if _profile_from_session(session):
            return session
    return None


def _current_user_fallback_session(
    db: Session,
    current_user_id: int,
    current_session_id: Optional[str],
) -> Optional[QuizV4Session]:
    if not current_session_id:
        return None
    try:
        session_uuid = uuid_module.UUID(current_session_id)
    except (TypeError, ValueError):
        return None

    session = db.query(QuizV4Session).filter(QuizV4Session.id == session_uuid).first()
    if not session or session.current_stage != "completed":
        return None
    if session.user_id is not None and session.user_id != current_user_id:
        return None
    if not _profile_from_session(session):
        return None
    if session.user_id is None:
        return None
    return session


def _resolve_member_profiles(
    db: Session,
    current_user: User,
    member_ids: Optional[list[int]],
    current_session_id: Optional[str] = None,
) -> dict:
    friend_ids = _normalize_friend_ids(current_user.id, member_ids)
    _ensure_accepted_friends(db, current_user.id, friend_ids)

    all_user_ids = [current_user.id] + friend_ids
    users = {
        user.id: user
        for user in db.query(User).filter(User.id.in_(all_user_ids)).all()
    }

    included = []
    excluded = []
    profile_rows = []
    sessions_by_user_id = {}

    for user_id in all_user_ids:
        user = users.get(user_id)
        if not user:
            continue
        session = _latest_completed_session_for_user(db, user_id)
        if not session and user_id == current_user.id:
            session = _current_user_fallback_session(db, current_user.id, current_session_id)
        profile = _profile_from_session(session)
        if session and profile:
            user_info = _user_payload(user)
            included.append(user_info)
            profile_rows.append({
                "user_id": user_id,
                "user": user_info,
                "profile": profile,
                "session_id": str(session.id),
                "budget": session.budget,
                "season": session.season,
                "travel_style": session.travel_style,
            })
            sessions_by_user_id[user_id] = str(session.id)
        else:
            excluded.append(_user_payload(user, "No completed quiz or photo profile"))

    if not any(row["user_id"] == current_user.id for row in profile_rows):
        raise HTTPException(
            status_code=404,
            detail="Your completed quiz profile was not found. Please finish the quiz or photo onboarding first.",
        )

    return {
        "friend_ids": friend_ids,
        "included": included,
        "excluded": excluded,
        "profiles": [row["profile"] for row in profile_rows],
        "profile_rows": profile_rows,
        "sessions_by_user_id": sessions_by_user_id,
        "conflicts": _detect_group_conflicts(profile_rows),
    }


def _aggregate_member_profiles(member_profiles: list[dict]) -> dict:
    all_tags = set()
    for profile in member_profiles:
        all_tags.update(profile.keys())

    aggregated = {}
    for tag in all_tags:
        scores = [float(profile.get(tag, 0.0)) for profile in member_profiles]
        mean_score = sum(scores) / len(scores)
        if mean_score <= 0:
            continue
        variance = sum((score - mean_score) ** 2 for score in scores) / len(scores)
        std_score = variance ** 0.5
        consensus = 1.0 - min(std_score, 1.0)
        aggregated[tag] = round(mean_score * consensus, 4)

    max_value = max(aggregated.values()) if aggregated else 1.0
    return {slug: round(score / max_value, 4) for slug, score in aggregated.items() if score > 0}


def _score_profile_with_solo_recommender(
    db: Session,
    profile: dict,
    budget: Optional[str] = None,
    season: Optional[str] = None,
) -> dict[int, dict]:
    country_count = len(get_country_scoring_context(db)["countries"])
    session_like = SimpleNamespace(
        final_profile=profile,
        tag_scores=profile,
        budget=budget,
        season=season,
    )
    scores = compute_country_scores(
        session_like,
        db,
        diversity=False,
        top_n=country_count,
    )
    return {item["country_id"]: item for item in scores}


def _fit_label(score: float) -> str:
    if score >= 0.70:
        return "strong"
    if score >= 0.45:
        return "good"
    if score >= 0.25:
        return "weak"
    return "poor"


def _human_tag_label(slug: str, fallback: Optional[str] = None) -> str:
    value = fallback or slug or ""
    return value.replace("-", " ").title()


def _profile_cosine(profile_a: dict, profile_b: dict) -> float:
    if not profile_a or not profile_b:
        return 0.0
    dot = sum(float(profile_a.get(slug, 0.0)) * float(profile_b.get(slug, 0.0)) for slug in set(profile_a) & set(profile_b))
    norm_a = math.sqrt(sum(float(score) ** 2 for score in profile_a.values()))
    norm_b = math.sqrt(sum(float(score) ** 2 for score in profile_b.values()))
    if not norm_a or not norm_b:
        return 0.0
    return max(0.0, min(1.0, dot / (norm_a * norm_b)))


def _top_shared_profile_tags(db: Session, profile_a: dict, profile_b: dict, limit: int = 3) -> list[dict]:
    shared = []
    for slug in set(profile_a) & set(profile_b):
        score_a = float(profile_a.get(slug, 0.0))
        score_b = float(profile_b.get(slug, 0.0))
        if score_a <= 0 or score_b <= 0:
            continue
        shared.append({
            "slug": slug,
            "score": round((min(score_a, score_b) + (score_a * score_b)) / 2, 4),
        })
    shared.sort(key=lambda item: item["score"], reverse=True)
    shared = shared[:limit]
    if not shared:
        return []

    labels = {
        tag.slug: tag.name
        for tag in db.query(Tag).filter(Tag.slug.in_([item["slug"] for item in shared])).all()
    }
    for item in shared:
        item["name"] = _human_tag_label(item["slug"], labels.get(item["slug"]))
    return shared


def _compatibility_label(score: float) -> str:
    if score >= 78:
        return "Strong travel match"
    if score >= 62:
        return "Good travel match"
    if score >= 45:
        return "Mixed travel match"
    return "Different travel styles"


def _friend_compatibility_summary(shared_tags: list[dict], conflict: Optional[dict], score: int) -> str:
    if shared_tags:
        tag_names = [tag["name"] for tag in shared_tags[:2]]
        if len(tag_names) == 1:
            return f"Both of you lean toward {tag_names[0]}."
        return f"Both of you lean toward {tag_names[0]} and {tag_names[1]}."
    if conflict:
        return conflict.get("message") or "Your travel styles may need a compromise."
    if score >= 45:
        return "You have some overlap, but the shared taste signals are still broad."
    return "Your profiles point in different directions, useful for a balanced group trip."


def _build_friend_compatibility(
    db: Session,
    current_user: User,
    current_session: Optional[QuizV4Session],
    friend: User,
) -> dict:
    current_profile = _profile_from_session(current_session)
    if not current_profile:
        return {
            "status": "missing_current_profile",
            "score": None,
            "label": "Quiz needed",
            "summary": "Complete your quiz to compare travel styles.",
            "shared_tags": [],
            "conflict": None,
        }

    friend_session = _latest_completed_session_for_user(db, friend.id)
    friend_profile = _profile_from_session(friend_session)
    if not friend_profile:
        return {
            "status": "missing_friend_profile",
            "score": None,
            "label": "No travel profile yet",
            "summary": "This friend needs a completed quiz or photo profile before compatibility can be estimated.",
            "shared_tags": [],
            "conflict": None,
        }

    cosine = _profile_cosine(current_profile, friend_profile)
    shared_tags = _top_shared_profile_tags(db, current_profile, friend_profile, limit=3)
    shared_boost = min(0.18, 0.06 * len(shared_tags))
    score = int(round(max(0.0, min(1.0, cosine + shared_boost)) * 100))
    member_rows = [
        {
            "user_id": current_user.id,
            "user": _user_payload(current_user),
            "profile": current_profile,
            "budget": current_session.budget,
            "season": current_session.season,
            "travel_style": current_session.travel_style,
        },
        {
            "user_id": friend.id,
            "user": _user_payload(friend),
            "profile": friend_profile,
            "budget": friend_session.budget,
            "season": friend_session.season,
            "travel_style": friend_session.travel_style,
        },
    ]
    conflicts = _detect_group_conflicts(member_rows)
    conflict = conflicts[0] if conflicts else None

    return {
        "status": "ready",
        "score": score,
        "label": _compatibility_label(score),
        "summary": _friend_compatibility_summary(shared_tags, conflict, score),
        "shared_tags": shared_tags,
        "conflict": {
            "type": conflict.get("type"),
            "severity": conflict.get("severity"),
            "title": conflict.get("title"),
            "message": conflict.get("message"),
        } if conflict else None,
        "session_id": str(friend_session.id),
    }


def _score_member_name(member_score: dict) -> str:
    return member_score.get("full_name") or member_score.get("username") or f"User {member_score.get('user_id')}"


def _top_reason_label(reason: dict) -> str:
    if not reason:
        return ""
    return reason.get("tag_name") or reason.get("tag_slug") or reason.get("reason", "")


def _build_group_explanation(
    country_name: str,
    group_item: Optional[dict],
    individual_scores: list[dict],
    mean_score: float,
    min_score: float,
    consensus_factor: float,
) -> dict:
    strong_members = [member for member in individual_scores if member["score"] >= 0.70]
    good_members = [member for member in individual_scores if member["score"] >= 0.45]
    weak_members = [member for member in individual_scores if member["score"] < 0.45]

    group_reasons = []
    for reason in (group_item or {}).get("matching_reasons", [])[:3]:
        label = _top_reason_label(reason)
        if label:
            group_reasons.append({
                "tag": reason.get("tag_slug"),
                "label": label,
                "reason": reason.get("reason"),
            })

    member_highlights = []
    for member in sorted(individual_scores, key=lambda item: item["score"], reverse=True):
        reasons = []
        for reason in member.get("matching_reasons", [])[:2]:
            label = _top_reason_label(reason)
            if label:
                reasons.append(label)
        member_highlights.append({
            "user_id": member["user_id"],
            "name": _score_member_name(member),
            "score": member["score"],
            "fit": member["fit"],
            "reasons": reasons,
        })

    tradeoffs = []
    for member in weak_members:
        tradeoffs.append({
            "user_id": member["user_id"],
            "name": _score_member_name(member),
            "score": member["score"],
            "message": f"Weaker fit for {_score_member_name(member)}.",
        })

    if consensus_factor < 0.75:
        tradeoffs.append({
            "type": "low_consensus",
            "message": "Group preferences are spread out, so this destination is more of a compromise.",
        })

    strong_names = [_score_member_name(member) for member in strong_members]
    good_count = len(good_members)
    total_count = len(individual_scores)
    if strong_names:
        summary = (
            f"{country_name} is a strong group option for {', '.join(strong_names[:2])}"
            f"{' and others' if len(strong_names) > 2 else ''}, with {good_count}/{total_count} travellers above a good fit."
        )
    elif good_count:
        summary = f"{country_name} is a balanced compromise: {good_count}/{total_count} travellers have a good fit."
    else:
        summary = f"{country_name} is a weak compromise for this group and may need manual adjustment."

    return {
        "summary": summary,
        "good_fit_count": good_count,
        "total_members": total_count,
        "mean_score": round(mean_score, 4),
        "min_member_score": round(min_score, 4),
        "consensus": round(consensus_factor, 4),
        "top_group_reasons": group_reasons,
        "member_highlights": member_highlights,
        "tradeoffs": tradeoffs[:3],
    }


CONFLICT_THRESHOLD = 0.45

CONFLICT_TAG_GROUPS = {
    "beach": {
        "beach-water",
        "sandy-beaches",
        "child-beaches",
        "beach-clubs",
        "hidden-coves",
        "coastal-walks",
        "sailing",
        "water-sports",
        "snorkeling-diving",
        "scuba-diving",
        "surfing-kitesurfing",
        "lake-swimming",
    },
    "winter": {
        "winter-nature",
        "skiing",
        "snowshoeing",
        "snowmobile",
        "ice-skating",
        "northern-lights",
        "glaciers",
    },
    "nightlife": {
        "nightlife-social",
        "clubbing",
        "techno-clubs",
        "underground-clubs",
        "bar-scene",
        "pub-crawls",
        "craft-cocktail-bars",
        "rooftop-bars",
        "beach-clubs",
        "music-festivals",
        "live-entertainment",
        "ruin-bars",
    },
    "family": {
        "family-comfort",
        "family-attractions",
        "child-activities",
        "child-beaches",
        "theme-parks",
        "water-parks",
        "easy-sightseeing",
        "comfort-accommodation",
        "all-inclusive-resorts",
    },
    "adventure": {
        "adventure-active",
        "air-extreme-sports",
        "land-sports",
        "rope-park-sports",
        "bungee-jumping",
        "via-ferrata",
        "alpine-climbing",
        "multi-day-trekking",
        "rafting",
        "kayaking",
        "paragliding",
        "skiing",
    },
    "slow": {
        "wellness-slow",
        "mindfulness-retreats",
        "yoga-retreats",
        "meditation-retreats",
        "silence-retreats",
        "holistic-health",
        "slow-scenic",
        "spa-thermal",
        "thermal-baths",
        "hot-springs-outdoor",
        "contemplative-nature",
        "digital-detox",
    },
    "urban": {
        "urban-modern",
        "shopping-fashion",
        "luxury-shopping",
        "street-art",
        "contemporary-art",
        "contemporary-architecture",
        "modernist-architecture",
        "design-weeks",
        "rooftop-views",
        "tech-cities",
        "specialty-coffee",
    },
    "nature": {
        "nature-outdoors",
        "hiking-trekking",
        "day-hiking",
        "multi-day-trekking",
        "national-parks",
        "camping",
        "wildlife-nature",
        "wildlife-safaris",
        "wildlife-watching",
        "birdwatching",
        "foraging",
        "forest-bathing",
        "photography-landscapes",
        "contemplative-nature",
        "stargazing",
    },
    "luxury": {
        "fine-dining-exp",
        "michelin-restaurants",
        "tasting-menus",
        "boutique-hotels",
        "luxury-shopping",
        "watches-shopping",
        "fashion-weeks",
        "beach-clubs",
        "rooftop-bars",
    },
    "budget": {
        "street-food",
        "local-tavernas",
        "farmers-markets",
        "food-markets",
        "camping",
        "pub-crawls",
        "local-festivals",
        "folk-traditions",
    },
    "culture": {
        "culture-history",
        "historical-sites",
        "ancient-ruins",
        "art-museums",
        "history-museums",
        "castles-palaces",
        "religious-sites",
        "roman-history",
        "wwii-history",
        "gothic-architecture",
        "vernacular-architecture",
        "folk-traditions",
        "local-festivals",
    },
    "food": {
        "food-drink",
        "street-food",
        "local-tavernas",
        "food-markets",
        "farmers-markets",
        "wine-vineyards",
        "craft-beer",
        "distilleries",
        "cooking-classes",
        "food-tours-guided",
        "michelin-restaurants",
        "fine-dining-exp",
        "specialty-coffee",
    },
}

TAG_CONFLICT_RULES = [
    {
        "type": "beach_vs_winter",
        "a": "beach",
        "b": "winter",
        "severity": "high",
        "title": "Beach vs winter conflict",
        "message": "Some travellers want warm coastal activities while others prefer snow, winter nature, or northern lights.",
    },
    {
        "type": "nightlife_vs_family",
        "a": "nightlife",
        "b": "family",
        "severity": "high",
        "title": "Nightlife vs family comfort conflict",
        "message": "The group is split between late-night social activities and calmer family-friendly travel.",
    },
    {
        "type": "adventure_vs_slow",
        "a": "adventure",
        "b": "slow",
        "severity": "medium",
        "title": "Adventure vs slow travel conflict",
        "message": "Some travellers prefer intense active days while others lean toward wellness, slower pacing, or recovery time.",
    },
    {
        "type": "urban_vs_nature",
        "a": "urban",
        "b": "nature",
        "severity": "medium",
        "title": "City vs nature conflict",
        "message": "The group is split between urban/cultural density and outdoor nature-focused travel.",
    },
    {
        "type": "luxury_vs_budget",
        "a": "luxury",
        "b": "budget",
        "severity": "medium",
        "title": "Luxury vs budget experience conflict",
        "message": "Some travellers prefer premium experiences while others lean toward low-cost or local options.",
    },
    {
        "type": "nightlife_vs_slow",
        "a": "nightlife",
        "b": "slow",
        "severity": "medium",
        "title": "Party energy vs quiet retreat conflict",
        "message": "The group mixes nightlife-heavy preferences with calm wellness or retreat-style preferences.",
    },
    {
        "type": "adventure_vs_family",
        "a": "adventure",
        "b": "family",
        "severity": "medium",
        "title": "High-adventure vs comfort conflict",
        "message": "Some travellers want physically demanding activities while others prefer safer, easier, comfort-oriented days.",
    },
    {
        "type": "culture_vs_nightlife",
        "a": "culture",
        "b": "nightlife",
        "severity": "low",
        "title": "Day culture vs nightlife focus",
        "message": "The group may need a balance between museums/history during the day and social evenings.",
    },
    {
        "type": "food_vs_adventure",
        "a": "food",
        "b": "adventure",
        "severity": "low",
        "title": "Food focus vs active itinerary",
        "message": "Some travellers care most about food and tastings while others prefer activity-heavy days.",
    },
]


def _member_display_name(row: dict) -> str:
    user = row.get("user") or {}
    return user.get("full_name") or user.get("username") or f"User {row.get('user_id')}"


def _active_group_members(member_rows: list[dict], tag_group: str, threshold: float = CONFLICT_THRESHOLD) -> list[dict]:
    tags = CONFLICT_TAG_GROUPS[tag_group]
    members = []
    for row in member_rows:
        profile = row.get("profile") or {}
        max_score = max((float(profile.get(tag, 0.0)) for tag in tags), default=0.0)
        if tag_group == "family" and row.get("travel_style") == "family":
            max_score = max(max_score, 0.75)
        if tag_group == "luxury" and row.get("budget") == "luxury":
            max_score = max(max_score, 0.75)
        if tag_group == "budget" and row.get("budget") == "budget":
            max_score = max(max_score, 0.75)
        if tag_group == "winter" and row.get("season") == "winter":
            max_score = max(max_score, 0.55)
        if max_score >= threshold:
            members.append({
                "user_id": row["user_id"],
                "username": (row.get("user") or {}).get("username"),
                "full_name": (row.get("user") or {}).get("full_name"),
                "name": _member_display_name(row),
                "strength": round(max_score, 4),
            })
    return members


def _disjoint_members(members_a: list[dict], members_b: list[dict]) -> tuple[list[dict], list[dict]]:
    ids_a = {member["user_id"] for member in members_a}
    ids_b = {member["user_id"] for member in members_b}
    return (
        [member for member in members_a if member["user_id"] not in ids_b],
        [member for member in members_b if member["user_id"] not in ids_a],
    )


def _field_groups(member_rows: list[dict], field: str) -> dict[str, list[dict]]:
    groups: dict[str, list[dict]] = {}
    for row in member_rows:
        value = row.get(field)
        if not value:
            continue
        groups.setdefault(value, []).append({
            "user_id": row["user_id"],
            "username": (row.get("user") or {}).get("username"),
            "full_name": (row.get("user") or {}).get("full_name"),
            "name": _member_display_name(row),
        })
    return groups


def _append_field_conflict(
    conflicts: list[dict],
    conflict_type: str,
    severity: str,
    title: str,
    message: str,
    groups: dict[str, list[dict]],
) -> None:
    if len(groups) < 2:
        return
    conflicts.append({
        "type": conflict_type,
        "severity": severity,
        "title": title,
        "message": message,
        "groups": [
            {"value": value, "members": members}
            for value, members in sorted(groups.items())
        ],
    })


def _detect_group_conflicts(member_rows: list[dict]) -> list[dict]:
    if len(member_rows) < 2:
        return []

    conflicts: list[dict] = []

    budget_groups = _field_groups(member_rows, "budget")
    if "budget" in budget_groups and "luxury" in budget_groups:
        budget_severity = "high"
    elif len(budget_groups) >= 2:
        budget_severity = "medium"
    else:
        budget_severity = "low"
    _append_field_conflict(
        conflicts,
        "budget_mismatch",
        budget_severity,
        "Budget mismatch",
        "Travellers selected different budget levels, so the group may need to optimize around the strictest budget.",
        budget_groups,
    )

    season_groups = _field_groups(member_rows, "season")
    if "summer" in season_groups and "winter" in season_groups:
        season_severity = "high"
    elif len(season_groups) >= 2:
        season_severity = "medium"
    else:
        season_severity = "low"
    _append_field_conflict(
        conflicts,
        "season_mismatch",
        season_severity,
        "Season mismatch",
        "Travellers prefer different travel seasons, which can change the best destinations and activities.",
        season_groups,
    )

    style_groups = _field_groups(member_rows, "travel_style")
    _append_field_conflict(
        conflicts,
        "travel_style_mismatch",
        "low",
        "Travel style mismatch",
        "Travellers completed the quiz with different trip styles, so the plan may need a broader compromise.",
        style_groups,
    )

    seen_types = {conflict["type"] for conflict in conflicts}
    for rule in TAG_CONFLICT_RULES:
        members_a = _active_group_members(member_rows, rule["a"])
        members_b = _active_group_members(member_rows, rule["b"])
        only_a, only_b = _disjoint_members(members_a, members_b)
        if not only_a or not only_b or rule["type"] in seen_types:
            continue
        conflicts.append({
            "type": rule["type"],
            "severity": rule["severity"],
            "title": rule["title"],
            "message": rule["message"],
            "group_a": {
                "preference": rule["a"],
                "members": only_a,
            },
            "group_b": {
                "preference": rule["b"],
                "members": only_b,
            },
        })
        seen_types.add(rule["type"])

    severity_rank = {"high": 0, "medium": 1, "low": 2}
    conflicts.sort(key=lambda item: (severity_rank.get(item["severity"], 3), item["type"]))
    return conflicts[:8]


def _group_conflict_penalty(conflicts: list[dict], min_member_score: float) -> float:
    if not conflicts or min_member_score >= 0.35:
        return 0.0

    severity_weights = {
        "high": 0.10,
        "medium": 0.06,
        "low": 0.03,
    }
    unresolved_factor = 1.0 if min_member_score < 0.25 else 0.5
    raw_penalty = sum(
        severity_weights.get(conflict.get("severity"), 0.0)
        for conflict in conflicts
    ) * unresolved_factor
    return round(min(raw_penalty, 0.18), 4)


def _score_countries_for_group(db: Session, member_rows: list[dict]) -> list[dict]:
    average_weight = 0.50
    least_misery_weight = 0.30
    consensus_weight = 0.20
    individual_weight = 0.85
    aggregated_profile_weight = 0.15

    member_rows = [row for row in member_rows if row.get("profile")]
    if not member_rows:
        return []

    member_profiles = [row["profile"] for row in member_rows]
    aggregated_profile = _aggregate_member_profiles(member_profiles)
    group_conflicts = _detect_group_conflicts(member_rows)

    group_scores = _score_profile_with_solo_recommender(db, aggregated_profile)
    member_score_maps = [
        (
            row,
            _score_profile_with_solo_recommender(
                db,
                row["profile"],
                row.get("budget"),
                row.get("season"),
            ),
        )
        for row in member_rows
    ]

    candidate_country_ids = set(group_scores.keys())
    for _, score_map in member_score_maps:
        candidate_country_ids.update(score_map.keys())

    results = []
    for country_id in candidate_country_ids:
        group_item = group_scores.get(country_id)
        fallback_item = group_item
        if fallback_item is None:
            for _, score_map in member_score_maps:
                fallback_item = score_map.get(country_id)
                if fallback_item:
                    break
        if not fallback_item:
            continue

        individual_scores = []
        numeric_scores = []
        for row, score_map in member_score_maps:
            item = score_map.get(country_id)
            score = float(item["score"]) if item else 0.0
            numeric_scores.append(score)
            user = row.get("user") or {"id": row["user_id"]}
            individual_scores.append({
                "user_id": row["user_id"],
                "username": user.get("username"),
                "full_name": user.get("full_name"),
                "score": round(score, 4),
                "fit": _fit_label(score),
                "matching_tags": (item or {}).get("matching_tags", [])[:3],
                "matching_reasons": (item or {}).get("matching_reasons", [])[:2],
            })

        scores_arr = np.array(numeric_scores, dtype=float)
        mean_score = float(np.mean(scores_arr))
        std_score = float(np.std(scores_arr))
        min_score = float(np.min(scores_arr))
        max_misery_gap = max(0.0, mean_score - min_score)
        fairness_index = max(0.0, 1.0 - min(max_misery_gap / max(mean_score, 0.0001), 1.0))

        consensus_factor = 1.0 - min(std_score, 1.0)
        misery_factor = 1.0 - min(max_misery_gap * 1.5, 1.0)
        consensus_score = mean_score * consensus_factor
        least_misery_score = min_score
        individual_group_score = (
            average_weight * mean_score
            + least_misery_weight * least_misery_score
            + consensus_weight * consensus_score
        )
        group_profile_score = float(group_item["score"]) if group_item else mean_score
        conflict_penalty = _group_conflict_penalty(group_conflicts, min_score)
        final_score = max(
            0.0,
            individual_weight * individual_group_score
            + aggregated_profile_weight * group_profile_score
            - conflict_penalty,
        )

        result = {
            key: fallback_item.get(key)
            for key in (
                "country_id",
                "country_name",
                "iso2",
                "description",
                "image_url",
                "avg_cost_per_day",
                "best_seasons",
                "capital",
                "matching_tags",
                "matching_reasons",
            )
        }
        result.update({
            "score": round(final_score, 4),
            "mean_score": round(mean_score, 4),
            "min_member_score": round(min_score, 4),
            "consensus": round(consensus_factor, 4),
            "misery_score": round(misery_factor, 4),
            "fairness_index": round(fairness_index, 4),
            "dissatisfaction_gap": round(max_misery_gap, 4),
            "group_profile_score": round(group_profile_score, 4),
            "conflict_penalty": round(conflict_penalty, 4),
            "individual_scores": individual_scores,
            "group_explanation": _build_group_explanation(
                fallback_item.get("country_name"),
                group_item,
                individual_scores,
                mean_score,
                min_score,
                consensus_factor,
            ),
            "scoring_model": "group_fairness_consensus_v2",
            "score_components": {
                "formula": (
                    "score = 0.85 * (0.50*mean + 0.30*min_member + "
                    "0.20*consensus_score) + 0.15*aggregated_profile - conflict_penalty"
                ),
                "individual_group_score": round(individual_group_score, 4),
                "group_profile_score": round(group_profile_score, 4),
                "mean_score": round(mean_score, 4),
                "min_member_score": round(min_score, 4),
                "dissatisfaction_gap": round(max_misery_gap, 4),
                "fairness_index": round(fairness_index, 4),
                "least_misery_score": round(least_misery_score, 4),
                "consensus_score": round(consensus_score, 4),
                "consensus_factor": round(consensus_factor, 4),
                "misery_factor": round(misery_factor, 4),
                "conflict_penalty": round(conflict_penalty, 4),
                "weights": {
                    "average": average_weight,
                    "least_misery": least_misery_weight,
                    "consensus": consensus_weight,
                    "individual": individual_weight,
                    "aggregated_profile": aggregated_profile_weight,
                },
            },
        })
        results.append(result)

    results.sort(key=lambda item: item["score"], reverse=True)
    return results


@router.get("/users/search")
def search_users(q: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    term = q.strip()
    if len(term) < 2:
        return {"users": []}

    users = db.query(User).filter(
        User.id != current_user.id,
        (User.username.ilike(f"%{term}%")) | (User.full_name.ilike(f"%{term}%")),
    ).limit(10).all()
    results = []
    for user in users:
        payload = _user_payload(user)
        payload.update(_relationship_status(current_user.id, _friendship_between(db, current_user.id, user.id)))
        results.append(payload)
    return {"users": results}


class FriendRequest(BaseModel):
    receiver_id: int


@router.post("/friends/request")
def send_friend_request(req: FriendRequest, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    if req.receiver_id == current_user.id:
        raise HTTPException(status_code=400, detail="You cannot send a friend request to yourself")

    receiver = db.query(User).filter(User.id == req.receiver_id).first()
    if not receiver:
        raise HTTPException(status_code=404, detail="User not found")

    existing = db.query(Friendship).filter(
        ((Friendship.requester_id == current_user.id) & (Friendship.receiver_id == req.receiver_id))
        | ((Friendship.requester_id == req.receiver_id) & (Friendship.receiver_id == current_user.id))
    ).first()
    if existing:
        raise HTTPException(status_code=400, detail="Friend request already exists")

    friendship = Friendship(requester_id=current_user.id, receiver_id=req.receiver_id)
    db.add(friendship)
    db.commit()
    return {"status": "sent"}


@router.put("/friends/accept/{friendship_id}")
def accept_friend_request(friendship_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    friendship = db.query(Friendship).filter(Friendship.id == friendship_id).first()
    if not friendship:
        raise HTTPException(status_code=404, detail="Not found")
    if friendship.receiver_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized")
    friendship.status = "accepted"
    db.commit()
    return {"status": "accepted"}


@router.put("/friends/decline/{friendship_id}")
def decline_friend_request(friendship_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    friendship = db.query(Friendship).filter(Friendship.id == friendship_id).first()
    if not friendship:
        raise HTTPException(status_code=404, detail="Not found")
    if friendship.receiver_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized")
    friendship.status = "declined"
    db.commit()
    return {"status": "declined"}


@router.get("/friends/pending")
def get_pending_requests(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    pending = db.query(Friendship).filter(
        Friendship.receiver_id == current_user.id,
        Friendship.status == "pending",
    ).all()
    current_session = _latest_completed_session_for_user(db, current_user.id)
    return {"requests": [
        {
            "id": friendship.id,
            "requester": {
                **_user_payload(friendship.requester),
                "compatibility": _build_friend_compatibility(db, current_user, current_session, friendship.requester),
            },
        }
        for friendship in pending
    ]}


@router.get("/friends")
def get_friends(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    friendships = db.query(Friendship).filter(
        ((Friendship.requester_id == current_user.id) | (Friendship.receiver_id == current_user.id)),
        Friendship.status == "accepted",
    ).all()
    current_session = _latest_completed_session_for_user(db, current_user.id)
    friends = []
    for friendship in friendships:
        friend = friendship.receiver if friendship.requester_id == current_user.id else friendship.requester
        payload = _user_payload(friend)
        payload["compatibility"] = _build_friend_compatibility(db, current_user, current_session, friend)
        friends.append(payload)
    return {"friends": friends}


@router.delete("/friends/{friend_id}")
def remove_friend(friend_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    friendship = _friendship_between(db, current_user.id, friend_id)
    if not friendship or friendship.status != "accepted":
        raise HTTPException(status_code=404, detail="Accepted friendship not found")
    db.delete(friendship)
    db.commit()
    return {"status": "removed", "friend_id": friend_id}


class GroupTripCreate(BaseModel):
    name: str = Field(default="Group Trip", min_length=1, max_length=80)
    country_id: int
    nr_zile: int = Field(..., ge=3, le=14)
    member_ids: list[int] = Field(default_factory=list)
    current_session_id: Optional[str] = None


class GroupInteractiveSessionCreate(BaseModel):
    name: str = Field(default="Group Interactive Trip", min_length=1, max_length=80)
    country_id: int
    nr_zile: int = Field(..., ge=1, le=10)
    member_ids: list[int] = Field(default_factory=list)
    current_session_id: Optional[str] = None


@router.post("/group-trip")
def create_group_trip(req: GroupTripCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    country = db.query(Country).filter(Country.id == req.country_id).first()
    if not country:
        raise HTTPException(status_code=404, detail="Country not found")

    resolved = _resolve_member_profiles(db, current_user, req.member_ids, req.current_session_id)
    all_member_ids = [current_user.id] + resolved["friend_ids"]

    trip = GroupTrip(
        name=req.name.strip() or "Group Trip",
        creator_id=current_user.id,
        country_id=req.country_id,
        nr_zile=req.nr_zile,
    )
    db.add(trip)
    db.flush()

    for user_id in all_member_ids:
        db.add(GroupTripMember(
            trip_id=trip.id,
            user_id=user_id,
            session_id=resolved["sessions_by_user_id"].get(user_id),
        ))

    db.commit()
    return {
        "trip_id": trip.id,
        "status": "created",
        "members_count": len(all_member_ids),
        "included_members": resolved["included"],
        "excluded_members": resolved["excluded"],
        "conflicts": resolved["conflicts"],
    }


@router.post("/group-interactive-session")
def create_group_interactive_session(
    req: GroupInteractiveSessionCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    country = db.query(Country).filter(Country.id == req.country_id).first()
    if not country:
        raise HTTPException(status_code=404, detail="Country not found")

    resolved = _resolve_member_profiles(db, current_user, req.member_ids, req.current_session_id)
    aggregated = _aggregate_member_profiles(resolved["profiles"])
    if not aggregated:
        raise HTTPException(status_code=404, detail="No valid group profile")

    trip = GroupTrip(
        name=req.name.strip() or "Group Interactive Trip",
        creator_id=current_user.id,
        country_id=req.country_id,
        nr_zile=req.nr_zile,
    )
    db.add(trip)
    db.flush()

    for user_id in [current_user.id] + resolved["friend_ids"]:
        db.add(GroupTripMember(
            trip_id=trip.id,
            user_id=user_id,
            session_id=resolved["sessions_by_user_id"].get(user_id),
        ))

    session_id = uuid_module.uuid4()
    db.add(QuizV4Session(
        id=session_id,
        user_id=current_user.id,
        tag_scores=aggregated,
        current_stage="completed",
        final_profile=aggregated,
        completed_at=datetime.now(timezone.utc),
        travel_style="group",
    ))

    db.commit()
    return {
        "session_id": str(session_id),
        "group_trip_id": trip.id,
        "country_id": country.id,
        "country_name": country.name,
        "days": req.nr_zile,
        "members_count": len(resolved["included"]),
        "included_members": resolved["included"],
        "excluded_members": resolved["excluded"],
        "conflicts": resolved["conflicts"],
    }


@router.post("/group-trip/{trip_id}/generate")
def generate_group_itinerary(trip_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    from app.models.itinerary import ItineraryPlan, ItineraryDay
    from app.services.itinerary_builder import build_itinerary

    trip = db.query(GroupTrip).filter(GroupTrip.id == trip_id).first()
    if not trip:
        raise HTTPException(status_code=404, detail="Trip not found")

    is_member = db.query(GroupTripMember).filter(
        GroupTripMember.trip_id == trip_id,
        GroupTripMember.user_id == current_user.id,
    ).first()
    if trip.creator_id != current_user.id and not is_member:
        raise HTTPException(status_code=403, detail="Not authorized for this group trip")

    members = db.query(GroupTripMember).filter(GroupTripMember.trip_id == trip_id).all()
    member_profiles = []
    member_rows = []
    included = []
    excluded = []

    for member in members:
        session = None
        if member.session_id:
            try:
                sid = uuid_module.UUID(member.session_id)
                session = db.query(QuizV4Session).filter(
                    QuizV4Session.id == sid,
                    QuizV4Session.user_id == member.user_id,
                ).first()
            except (TypeError, ValueError):
                session = None

        if not _profile_from_session(session):
            session = _latest_completed_session_for_user(db, member.user_id)
            if session:
                member.session_id = str(session.id)

        profile = _profile_from_session(session)
        if profile:
            member_profiles.append(profile)
            user_info = _user_payload(member.user)
            included.append(user_info)
            member_rows.append({
                "user_id": member.user_id,
                "user": user_info,
                "profile": profile,
                "session_id": str(session.id),
                "budget": session.budget,
                "season": session.season,
                "travel_style": session.travel_style,
            })
        else:
            excluded.append(_user_payload(member.user, "No completed quiz or photo profile"))

    if not member_profiles:
        raise HTTPException(status_code=404, detail="No valid member profiles")

    aggregated = _aggregate_member_profiles(member_profiles)
    temp_session_id = uuid_module.uuid4()
    temp_session = QuizV4Session(
        id=temp_session_id,
        user_id=current_user.id,
        tag_scores=aggregated,
        current_stage="completed",
        final_profile=aggregated,
        completed_at=datetime.now(timezone.utc),
    )
    db.add(temp_session)
    db.flush()

    days = build_itinerary(
        country_id=trip.country_id,
        nr_zile=trip.nr_zile,
        session_id=str(temp_session_id),
        db=db,
    )
    if not days:
        raise HTTPException(status_code=404, detail="No itinerary generated")

    plan = ItineraryPlan(
        session_id=str(temp_session_id),
        country_id=trip.country_id,
        nr_zile=trip.nr_zile,
        user_id=current_user.id,
        group_trip_id=trip_id,
        source="group",
    )
    db.add(plan)
    db.flush()

    for day in days:
        db.add(ItineraryDay(
            plan_id=plan.id,
            day_number=day["day"],
            city_id=day["city_id"],
            attraction_ids=[attraction["attraction_id"] for attraction in day["attractions"]],
        ))

    db.commit()
    return {
        "plan_id": plan.id,
        "trip_id": trip_id,
        "days": days,
        "included_members": included,
        "excluded_members": excluded,
        "conflicts": _detect_group_conflicts(member_rows),
    }


class GroupRecommendationRequest(BaseModel):
    member_ids: list[int] = Field(default_factory=list)
    current_session_id: Optional[str] = None


@router.post("/group-recommendations")
def get_group_recommendations(req: GroupRecommendationRequest, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """
    Group recommender using a maximum-misery aware score.

    The client sends friend ids only. The backend validates accepted friendships and
    resolves each member's latest completed Quiz v4 or photo profile.
    """
    resolved = _resolve_member_profiles(db, current_user, req.member_ids, req.current_session_id)
    results = _score_countries_for_group(db, resolved["profile_rows"])
    db.commit()

    return {
        "top_countries": results[:10],
        "members_count": len(resolved["included"]),
        "requested_members_count": 1 + len(resolved["friend_ids"]),
        "included_members": resolved["included"],
        "excluded_members": resolved["excluded"],
        "conflicts": resolved["conflicts"],
        "algorithm": "Hybrid group aggregation (average + least-misery + consensus)",
    }
