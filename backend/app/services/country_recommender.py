"""
Recomandare țări bazată pe profilul de taguri al utilizatorului.
Cosine similarity + MMR re-ranking pentru diversitate geografică.
"""

import logging
import math
from typing import Optional

import numpy as np
from sqlalchemy.orm import Session
from sqlalchemy import select, func

from app.models.tag import Tag
from app.models.geography import Country, country_tags
from app.services.quiz_engine import compute_adaptive_lambda, mmr_rerank

logger = logging.getLogger(__name__)

IDF_ALPHA = 0.5
IDF_MAX_WEIGHT = 2.0
SCORING_MODEL_VERSION = "country_recommender_v4.3"
_tag_idf_cache: dict[str, float] | None = None
_country_scoring_context_cache: dict | None = None

LANDLOCKED_COUNTRIES = {
    "Austria",
    "Belarus",
    "Czech Republic",
    "Czechia",
    "Hungary",
    "Kosovo",
    "Luxembourg",
    "Moldova",
    "North Macedonia",
    "Serbia",
    "Slovakia",
    "Switzerland",
}

COASTAL_PROFILE_TAGS = {
    "beach-water",
    "sailing",
    "hidden-coves",
    "coastal-walks",
    "snorkeling-diving",
    "scuba-diving",
    "sandy-beaches",
    "beach-clubs",
    "child-beaches",
}

SAILING_PROFILE_TAGS = {"water-sports", "sailing", "hidden-coves", "coastal-walks"}
COLD_SAILING_MISMATCH_COUNTRIES = {"Iceland"}

CYCLING_PROFILE_TAGS = {"cycling-biking"}
LOW_CYCLING_INFRA_COUNTRIES = {
    "Albania",
    "Bosnia and Herzegovina",
    "Kosovo",
    "Moldova",
    "North Macedonia",
}

FOREST_PROFILE_TAGS = {
    "contemplative-nature",
    "wildlife-nature",
    "forest-bathing",
    "foraging",
    "birdwatching",
    "wildlife-safaris",
    "wildlife-watching",
    "camping",
}
LOW_FOREST_COUNTRIES = {"Belgium", "Cyprus", "Luxembourg", "Malta", "Netherlands"}

THERMAL_PROFILE_TAGS = {"spa-thermal", "thermal-baths", "hot-springs-outdoor"}
THERMAL_COUNTRY_TAGS = {"thermal-baths", "hot-springs-outdoor"}

WARM_ROMANTIC_PROFILE_TAGS = {
    "beach-water",
    "hidden-coves",
    "sandy-beaches",
    "wine-vineyards",
    "boutique-hotels",
    "castles-palaces",
}
COLD_ROMANTIC_MISMATCH_COUNTRIES = {"Finland"}
SUMMER_ROMANCE_PROFILE_TAGS = {
    "spa-thermal",
    "historical-sites",
    "castles-palaces",
    "wine-vineyards",
    "hot-springs-outdoor",
}


def _profile_strength(profile: dict, tags: set[str]) -> float:
    return max((float(profile.get(tag, 0.0)) for tag in tags), default=0.0)


def _country_tag_strength(country_scores_by_slug: dict, tags: set[str]) -> float:
    return max((float(country_scores_by_slug.get(tag, 0.0)) for tag in tags), default=0.0)


def _budget_bonus_and_penalty(budget: str | None, cost: float | None) -> float:
    if not budget or cost is None:
        return 0.0

    if budget == "budget":
        if cost <= 60:
            return 0.05
        if cost > 120:
            return -0.25
        if cost > 90:
            return -0.15
        if cost > 70:
            return -0.08
        return 0.0

    if budget == "mid" and 60 < cost <= 150:
        return 0.05

    if budget == "luxury" and cost > 150:
        return 0.05

    return 0.0


def _constraint_penalty(
    country_name: str,
    expanded_profile: dict,
    country_scores_by_slug: dict,
    budget: str | None,
    season: str | None,
    cost: float | None,
) -> tuple[float, list[str]]:
    penalty = 0.0
    applied: list[str] = []

    coastal_strength = _profile_strength(expanded_profile, COASTAL_PROFILE_TAGS)
    if coastal_strength >= 0.45 and country_name in LANDLOCKED_COUNTRIES:
        penalty -= 0.30
        applied.append("coastal_profile_landlocked_country")

    summer_culture_nature = (
        budget == "budget"
        and season == "summer"
        and _profile_strength(expanded_profile, {"nature-outdoors"}) >= 0.45
        and _profile_strength(expanded_profile, {"culture-history", "historical-sites"}) >= 0.45
    )
    if summer_culture_nature and country_name in LANDLOCKED_COUNTRIES:
        penalty -= 0.25
        applied.append("summer_culture_nature_profile_landlocked_country")

    sailing_strength = _profile_strength(expanded_profile, SAILING_PROFILE_TAGS)
    if sailing_strength >= 0.45 and country_name in COLD_SAILING_MISMATCH_COUNTRIES:
        penalty -= 0.25
        applied.append("sailing_profile_cold_water_mismatch")

    cycling_strength = _profile_strength(expanded_profile, CYCLING_PROFILE_TAGS)
    if cycling_strength >= 0.45 and country_name in LOW_CYCLING_INFRA_COUNTRIES:
        penalty -= 0.25
        applied.append("cycling_profile_low_infrastructure_country")

    forest_strength = _profile_strength(expanded_profile, FOREST_PROFILE_TAGS)
    country_forest_strength = _country_tag_strength(country_scores_by_slug, FOREST_PROFILE_TAGS)
    if forest_strength >= 0.45 and country_name in LOW_FOREST_COUNTRIES and country_forest_strength < 0.55:
        penalty -= 0.20
        applied.append("forest_slow_travel_low_forest_country")

    thermal_strength = _profile_strength(expanded_profile, THERMAL_PROFILE_TAGS)
    country_thermal_strength = _country_tag_strength(country_scores_by_slug, THERMAL_COUNTRY_TAGS)
    if budget == "budget" and thermal_strength >= 0.45 and country_thermal_strength < 0.50:
        penalty -= 0.18
        applied.append("budget_thermal_profile_weak_thermal_match")

    warm_coast_strength = _profile_strength(expanded_profile, {"beach-water", "hidden-coves", "sandy-beaches"})
    romantic_strength = _profile_strength(expanded_profile, WARM_ROMANTIC_PROFILE_TAGS)
    if (
        warm_coast_strength >= 0.45
        and romantic_strength >= 0.45
        and country_name in COLD_ROMANTIC_MISMATCH_COUNTRIES
    ):
        penalty -= 0.18
        applied.append("warm_romantic_profile_cold_country_mismatch")

    summer_romance_strength = _profile_strength(expanded_profile, SUMMER_ROMANCE_PROFILE_TAGS)
    if (
        budget == "luxury"
        and season == "summer"
        and summer_romance_strength >= 0.45
        and country_name in COLD_ROMANTIC_MISMATCH_COUNTRIES
    ):
        penalty -= 0.32
        applied.append("summer_honeymoon_profile_cold_country_mismatch")

    if budget == "budget" and cost is not None and cost > 120:
        applied.append("budget_profile_expensive_country")

    return penalty, applied


def _smooth_idf(total_countries: int, countries_with_tag: int) -> float:
    if total_countries <= 0:
        return 1.0
    raw = math.log((total_countries + 1) / (countries_with_tag + 1)) + 1.0
    blended = 1.0 + IDF_ALPHA * (raw - 1.0)
    return round(min(IDF_MAX_WEIGHT, max(1.0, blended)), 4)


def get_country_tag_idf(db: Session) -> dict[str, float]:
    """Return leaf-tag IDF scores computed from country_tags.

    This is the single source of truth for rarity weighting in both country
    ranking and adaptive quiz card selection.
    """
    global _tag_idf_cache
    if _tag_idf_cache is not None:
        return _tag_idf_cache

    total_countries = db.query(Country).count()
    rows = db.execute(
        select(Tag.slug, func.count(country_tags.c.country_id))
        .join(country_tags, country_tags.c.tag_id == Tag.id)
        .where(Tag.is_leaf == True)
        .group_by(Tag.slug)
    ).fetchall()

    _tag_idf_cache = {
        slug: _smooth_idf(total_countries, int(country_count))
        for slug, country_count in rows
    }
    return _tag_idf_cache


def clear_country_scoring_cache() -> None:
    global _country_scoring_context_cache, _tag_idf_cache
    _country_scoring_context_cache = None
    _tag_idf_cache = None


def get_country_scoring_context(db: Session) -> dict:
    """Return static country/tag vectors reused by solo and group scoring.

    Country tags, IDF weights, and taxonomy mappings are effectively static while
    the app is running. Caching them avoids rebuilding the same 39 x N tag matrix
    for every group member.
    """
    global _country_scoring_context_cache
    if _country_scoring_context_cache is not None:
        return _country_scoring_context_cache

    all_tags = db.query(Tag).filter(Tag.is_leaf == True).all()
    tag_id_to_slug = {tag.id: tag.slug for tag in all_tags}
    slug_to_name = {tag.slug: tag.name for tag in all_tags}
    slug_to_idx = {tag.slug: idx for idx, tag in enumerate(all_tags)}

    non_leaf_tags = db.query(Tag).filter(Tag.is_leaf == False).all()
    non_leaf_by_slug = {tag.slug: {"id": tag.id, "slug": tag.slug} for tag in non_leaf_tags}
    children_by_parent: dict[int, list[dict]] = {}
    if non_leaf_tags:
        parent_ids = [tag.id for tag in non_leaf_tags]
        for tag in db.query(Tag).filter(Tag.parent_id.in_(parent_ids)).all():
            children_by_parent.setdefault(tag.parent_id, []).append({
                "id": tag.id,
                "slug": tag.slug,
                "is_leaf": tag.is_leaf,
            })

    countries = [
        {
            "id": country.id,
            "name": country.name,
            "iso2": country.iso2,
            "description": country.description,
            "image_url": country.image_url,
            "avg_cost_per_day": country.avg_cost_per_day,
            "best_seasons": country.best_seasons,
            "capital": country.capital,
        }
        for country in db.query(Country).all()
    ]
    country_ids = [country["id"] for country in countries]

    all_country_tag_rows = db.execute(
        select(country_tags.c.country_id, country_tags.c.tag_id, country_tags.c.score).where(
            country_tags.c.country_id.in_(country_ids)
        )
    ).fetchall()

    tags_by_country: dict[int, list[tuple[int, float]]] = {}
    for row in all_country_tag_rows:
        tags_by_country.setdefault(row.country_id, []).append((row.tag_id, float(row.score)))

    tag_idf_by_slug = get_country_tag_idf(db)
    tag_counts = [len(values) for values in tags_by_country.values()]
    median_count = float(np.median(tag_counts)) if tag_counts else 1.0
    density_alpha = 0.15

    country_data = {}
    for country in countries:
        rows = tags_by_country.get(country["id"], [])
        country_vector = np.zeros(len(all_tags))
        user_weight_vector = np.ones(len(all_tags))
        tag_dict: dict[int, float] = {}
        country_scores_by_slug: dict[str, float] = {}

        for tag_id, score in rows:
            slug = tag_id_to_slug.get(tag_id)
            if not slug:
                continue
            idx = slug_to_idx.get(slug)
            if idx is None:
                continue
            idf = tag_idf_by_slug.get(slug, 1.0)
            effective_idf = _effective_idf(idf, score)
            idf_weight = math.sqrt(effective_idf)
            user_weight_vector[idx] = idf_weight
            country_vector[idx] = score * idf_weight
            tag_dict[tag_id] = score
            country_scores_by_slug[slug] = score

        country_data[country["id"]] = {
            "rows_count": len(rows),
            "density_factor": (len(rows) / median_count) ** density_alpha if median_count else 1.0,
            "country_vector": country_vector,
            "user_weight_vector": user_weight_vector,
            "tag_dict": tag_dict,
            "country_scores_by_slug": country_scores_by_slug,
        }

    _country_scoring_context_cache = {
        "all_tags_count": len(all_tags),
        "tag_id_to_slug": tag_id_to_slug,
        "slug_to_name": slug_to_name,
        "slug_to_idx": slug_to_idx,
        "non_leaf_by_slug": non_leaf_by_slug,
        "children_by_parent": children_by_parent,
        "countries": countries,
        "country_data": country_data,
        "tag_idf_by_slug": tag_idf_by_slug,
    }
    return _country_scoring_context_cache


def _effective_idf(idf: float, country_score: float) -> float:
    return round(1.0 + (idf - 1.0) * max(0.0, min(1.0, country_score)), 4)


def _reason_text(tag_name: str, country_name: str, country_score: float, idf: float) -> str:
    distinctiveness = "rare" if idf >= 1.55 else "distinctive" if idf > 1.15 else "relevant"
    return (
        f"{tag_name} is a {distinctiveness} match: "
        f"{country_name} scores {round(country_score * 100)}% on it."
    )


def _constraint_reason_texts(country_name: str, applied_constraints: list[str]) -> list[dict]:
    reason_templates = {
        "coastal_profile_landlocked_country": (
            "Coastal preference mismatch",
            f"{country_name} is landlocked, so it is weaker for beach or sailing-oriented trips.",
        ),
        "summer_culture_nature_profile_landlocked_country": (
            "Summer water access mismatch",
            f"{country_name} matches culture/nature, but lacks direct coastline for a summer water-focused trip.",
        ),
        "sailing_profile_cold_water_mismatch": (
            "Cold-water sailing mismatch",
            f"{country_name} is less suitable for warm sailing or beach-water expectations.",
        ),
        "cycling_profile_low_infrastructure_country": (
            "Cycling infrastructure caution",
            f"{country_name} was reduced because cycling infrastructure may not fit a cycling-heavy profile.",
        ),
        "forest_slow_travel_low_forest_country": (
            "Slow-nature mismatch",
            f"{country_name} is weaker for forest, wildlife, or quiet nature signals.",
        ),
        "budget_thermal_profile_weak_thermal_match": (
            "Thermal wellness mismatch",
            f"{country_name} has weaker thermal-wellness coverage for this budget profile.",
        ),
        "warm_romantic_profile_cold_country_mismatch": (
            "Warm romance mismatch",
            f"{country_name} was reduced because the profile points toward warmer romantic coastal travel.",
        ),
        "summer_honeymoon_profile_cold_country_mismatch": (
            "Summer luxury mismatch",
            f"{country_name} is less aligned with a warm summer luxury or honeymoon-style profile.",
        ),
        "budget_profile_expensive_country": (
            "Budget caution",
            f"{country_name} is comparatively expensive for the selected budget.",
        ),
    }
    return [
        {
            "constraint": constraint,
            "title": reason_templates[constraint][0],
            "reason": reason_templates[constraint][1],
        }
        for constraint in applied_constraints
        if constraint in reason_templates
    ]


def compute_country_scores(
    session,
    db: Session,
    diversity: bool = True,
    lambda_param: Optional[float] = None,
    top_n: int = 5,
) -> list:
    """
    Cosine similarity între profilul utilizatorului și tagurile țărilor,
    opțional re-ranked cu MMR pentru diversitate geografică.

    diversity=True  → greedy MMR (λ=lambda_param sau adaptiv)
    diversity=False → pure cosine ranking
    """
    final_profile = session.final_profile or session.tag_scores or {}
    constraint_profile = session.tag_scores or final_profile
    if not final_profile:
        return []

    if lambda_param is None:
        effective_lambda = compute_adaptive_lambda(final_profile)
        scores_list = list(final_profile.values())
        cv = float(np.std(scores_list) / np.mean(scores_list)) if len(scores_list) >= 2 and np.mean(scores_list) > 0 else 0.0
        logger.info(f"MMR adaptive λ = {effective_lambda:.3f} (CV={cv:.3f})")
    else:
        effective_lambda = lambda_param
        logger.info(f"MMR manual λ = {effective_lambda:.3f}")

    context = get_country_scoring_context(db)
    slug_to_name = context["slug_to_name"]
    slug_to_idx = context["slug_to_idx"]
    non_leaf_by_slug = context["non_leaf_by_slug"]
    children_by_parent = context["children_by_parent"]
    tag_idf_by_slug = context["tag_idf_by_slug"]

    # Propagă scorurile L1/L2 la tagurile leaf
    expanded_profile = dict(final_profile)
    for slug, score in list(final_profile.items()):
        tag = non_leaf_by_slug.get(slug)
        if tag:
            for child in children_by_parent.get(tag["id"], []):
                expanded_profile[child["slug"]] = expanded_profile.get(child["slug"], 0) + score * 0.7
                if not child["is_leaf"]:
                    for gc in children_by_parent.get(child["id"], []):
                        expanded_profile[gc["slug"]] = expanded_profile.get(gc["slug"], 0) + score * 0.4

    user_vector = np.zeros(context["all_tags_count"])
    for slug, score in expanded_profile.items():
        idx = slug_to_idx.get(slug)
        if idx is not None:
            user_vector[idx] = float(score)

    if np.linalg.norm(user_vector) == 0:
        return []

    # Median tag count — baza pentru corecția de densitate.
    # Selective cosine rezolvă deja problema vectorilor densi (France vs Kosovo).
    # DENSITY_ALPHA mic (0.15) = corecție ușoară care ajută France/Italy fără să
    # penalizeze țările mici (Greece 90 tags, Iceland 119 tags) care apar legitim.
    # DENSITY_ALPHA=0 dezactivează complet; 0.3 penaliza Greece prea agresiv.
    results = []
    for country in context["countries"]:
        cached_country = context["country_data"].get(country["id"])
        if not cached_country or cached_country["rows_count"] == 0:
            continue

        country_vector = cached_country["country_vector"]
        user_weight_vector = cached_country["user_weight_vector"]
        tag_dict = cached_country["tag_dict"]
        country_scores_by_slug = cached_country["country_scores_by_slug"]

        # Selective cosine: calculăm similaritatea DOAR pe dimensiunile relevante
        # pentru utilizator (taguri cu scor > 0 în user_vector).
        # Motivare: un user de cultură nu trebuie penalizat că France are și taguri
        # de gastronomie/modă — acele dimensiuni sunt irelevante pentru query-ul lui
        # și umflau ||France|| artificial, coborând France sub Kosovo pentru culture.
        relevant_mask = user_vector > 0
        if not np.any(relevant_mask):
            continue

        u_slice = user_vector[relevant_mask] * user_weight_vector[relevant_mask]
        c_slice = country_vector[relevant_mask]

        norm_u = np.linalg.norm(u_slice)
        norm_c = np.linalg.norm(c_slice)
        if norm_u == 0 or norm_c == 0:
            continue

        similarity = float(np.dot(u_slice, c_slice) / (norm_u * norm_c))

        # Corecție densitate: țările cu mai multe taguri decât mediana primesc un mic boost,
        # cele cu mai puține primesc o mică penalizare. Evită ca destinații mici/specializate
        # să domine destinații mari (France, Italy) doar din cauza vectorului mai compact.
        density_factor = cached_country["density_factor"]

        season_bonus = 0.0
        if session.season and country["best_seasons"]:
            if session.season in country["best_seasons"]:
                season_bonus = 0.05

        cost = float(country["avg_cost_per_day"]) if country["avg_cost_per_day"] is not None else None
        budget_bonus = _budget_bonus_and_penalty(session.budget, cost)
        constraint_penalty, applied_constraints = _constraint_penalty(
            country["name"],
            constraint_profile,
            country_scores_by_slug,
            session.budget,
            session.season,
            cost,
        )

        final_score = max(0.0, (similarity + season_bonus + budget_bonus + constraint_penalty) * density_factor)
        constraint_reasons = _constraint_reason_texts(country["name"], applied_constraints)

        contributions = []
        for slug, user_score in expanded_profile.items():
            country_tag_score = country_scores_by_slug.get(slug)
            if not country_tag_score or user_score <= 0:
                continue

            idf = tag_idf_by_slug.get(slug, 1.0)
            effective_idf = _effective_idf(idf, country_tag_score)
            contribution = float(user_score) * country_tag_score * effective_idf
            if contribution <= 0:
                continue

            contributions.append({
                "tag_slug": slug,
                "tag_name": slug_to_name.get(slug, slug.replace("-", " ").title()),
                "user_score": round(float(user_score), 4),
                "country_score": round(country_tag_score, 4),
                "idf": round(idf, 4),
                "effective_idf": round(effective_idf, 4),
                "contribution": round(contribution, 4),
            })

        contributions.sort(key=lambda item: item["contribution"], reverse=True)
        matching_reasons = [
            {
                **item,
                "reason": _reason_text(
                    item["tag_name"],
                    country["name"],
                    item["country_score"],
                    item["effective_idf"],
                ),
            }
            for item in contributions[:3]
        ]

        results.append({
            "country_id": country["id"],
            "country_name": country["name"],
            "iso2": country["iso2"],
            "score": round(final_score, 4),
            "similarity": round(similarity, 4),
            "scoring_model": "idf_weighted_cosine",
            "scoring_model_version": SCORING_MODEL_VERSION,
            "description": country["description"],
            "image_url": country["image_url"],
            "avg_cost_per_day": country["avg_cost_per_day"],
            "best_seasons": country["best_seasons"],
            "capital": country["capital"],
            "matching_tags": [item["tag_slug"] for item in contributions[:5]],
            "matching_reasons": matching_reasons,
            "penalty_reasons": constraint_reasons,
            "score_components": {
                "idf_weighted_similarity": round(similarity, 4),
                "density_factor": round(density_factor, 4),
                "season_bonus": round(season_bonus, 4),
                "budget_bonus": round(budget_bonus, 4),
                "constraint_penalty": round(constraint_penalty, 4),
                "applied_constraints": applied_constraints,
            },
            "_tag_dict": tag_dict,
        })

    results.sort(key=lambda x: x["score"], reverse=True)

    if diversity and len(results) > 1:
        selected = mmr_rerank(results, effective_lambda, top_n)
    else:
        selected = results[:top_n]

    for r in selected:
        r.pop("_tag_dict", None)

    return selected
