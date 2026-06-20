import math
import logging
import numpy as np
import uuid
from sqlalchemy import select, func
from app.models.geography import attraction_tags, Attraction
from app.models import Tag, QuizV4Session

logger = logging.getLogger(__name__)

# ── IDF constants — identice cu country_recommender.py (liniile 20-21) ───────
IDF_ALPHA = 0.5
IDF_MAX_WEIGHT = 2.0
_attraction_tag_idf_cache: dict | None = None


def _smooth_idf_attr(total_attractions: int, attractions_with_tag: int) -> float:
    """IDF smooth pentru raritatea tagurilor la nivel de atractii.

    Replica _smooth_idf din country_recommender.py (liniile 204-209),
    aplicata pe attraction_tags in loc de country_tags.
    """
    if total_attractions <= 0:
        return 1.0
    raw = math.log((total_attractions + 1) / (attractions_with_tag + 1)) + 1.0
    blended = 1.0 + IDF_ALPHA * (raw - 1.0)
    return round(min(IDF_MAX_WEIGHT, max(1.0, blended)), 4)


def _effective_idf_attr(idf: float, attr_score: float) -> float:
    """Scala IDF prin scorul efectiv al atractiei pe tag.

    Replica _effective_idf din country_recommender.py (linia 347-348).
    """
    return round(1.0 + (idf - 1.0) * max(0.0, min(1.0, attr_score)), 4)


def get_attraction_tag_idf(db) -> dict[int, float]:
    """IDF per tag_id calculat din attraction_tags global.

    Sursa de adevar unica pentru raritatea tagurilor la nivel de atractii.
    Cacheuit global, analog cu get_country_tag_idf din country_recommender.py.
    """
    global _attraction_tag_idf_cache
    if _attraction_tag_idf_cache is not None:
        return _attraction_tag_idf_cache

    total = db.query(Attraction).count()
    rows = db.execute(
        select(
            attraction_tags.c.tag_id,
            func.count(attraction_tags.c.attraction_id).label("cnt"),
        ).group_by(attraction_tags.c.tag_id)
    ).fetchall()

    _attraction_tag_idf_cache = {
        tag_id: _smooth_idf_attr(total, int(cnt))
        for tag_id, cnt in rows
    }
    return _attraction_tag_idf_cache


def clear_attraction_idf_cache() -> None:
    global _attraction_tag_idf_cache
    _attraction_tag_idf_cache = None


def get_user_tag_vector(session_id: str, db, all_tag_ids: list, profile_boosts: dict | None = None):
    """Returns (normalized_vector, raw_scores_dict {tag_id: raw_score})."""
    try:
        quiz_session = db.query(QuizV4Session).filter(
            QuizV4Session.id == uuid.UUID(session_id)
        ).first()
    except (ValueError, AttributeError):
        quiz_session = None

    tag_scores_map = {tid: 0.0 for tid in all_tag_ids}

    profile = None
    if quiz_session:
        profile = quiz_session.final_profile or quiz_session.tag_scores

    if profile:
        tags = db.query(Tag).filter(Tag.id.in_(all_tag_ids)).all()
        slug_to_id = {t.slug: t.id for t in tags}
        for slug, score in profile.items():
            tid = slug_to_id.get(slug)
            if tid:
                tag_scores_map[tid] = float(score)
        for slug, boost in (profile_boosts or {}).items():
            tid = slug_to_id.get(slug)
            if tid:
                tag_scores_map[tid] = max(0.0, float(tag_scores_map.get(tid, 0.0)) + float(boost))

    vec = np.array([tag_scores_map[tid] for tid in all_tag_ids], dtype=float)
    norm = np.linalg.norm(vec)
    normalized = vec / norm if norm > 0 else vec
    return normalized, tag_scores_map


def score_attractions(
    attractions,
    user_vector,
    all_tag_ids,
    db,
    budget_level=None,
    user_raw_scores=None,
    log_n: int = 0,
):
    """
    Hybrid scorer:
      final = 0.70·cosine + 0.20·popularity + 0.10·rarity − budget_penalty

    cosine      — normalized cosine similarity in [0,1]
    popularity  — log(1+nr_tags) / log(1+max_tags), proxy for documentation depth
    rarity      — IDF-weighted bonus for matching rare tags the user strongly prefers;
                  consistent cu country_recommender.py (_smooth_idf_attr / _effective_idf_attr)
    """
    idx_map = {tid: i for i, tid in enumerate(all_tag_ids)}
    results = []

    attraction_ids = [attr.id for attr in attractions]
    if not attraction_ids:
        return results

    all_rows = db.execute(
        select(attraction_tags).where(attraction_tags.c.attraction_id.in_(attraction_ids))
    ).fetchall()
    tags_by_attraction: dict = {}
    for row in all_rows:
        tags_by_attraction.setdefault(row.attraction_id, []).append(row)

    # ── Popularity pre-compute ─────────────────────────────────────────────────
    tags_counts_per_attr = {aid: len(rows) for aid, rows in tags_by_attraction.items()}
    max_tags = max(tags_counts_per_attr.values(), default=1)

    # ── Rarity IDF pre-compute ────────────────────────────────────────────────
    # IDF global per tag_id (cacheuit) — raritate bazata pe distributia din DB
    tag_idf = get_attraction_tag_idf(db)

    # Utilizator: taguri cu scor > 0.4 (prag coborat fata de 0.6 anterior pentru
    # activare mai larga; IDF-ul natural penalizeaza tagurile comune)
    user_high_score_tags: dict = {}
    if user_raw_scores:
        user_high_score_tags = {tid: s for tid, s in user_raw_scores.items() if s > 0.4}

    for attr in attractions:
        attr_vec = np.zeros(len(all_tag_ids))
        attr_tag_ids: set = set()
        attr_scores_on_tags: dict = {}  # tag_id -> scorul atractiei pe tag
        for row in tags_by_attraction.get(attr.id, []):
            if row.tag_id in idx_map:
                score_val = float(row.score or 1.0)
                attr_vec[idx_map[row.tag_id]] = score_val
                attr_tag_ids.add(row.tag_id)
                attr_scores_on_tags[row.tag_id] = score_val

        norm = np.linalg.norm(attr_vec)
        if norm > 0:
            attr_vec /= norm

        cosine_score = max(0.0, float(np.dot(user_vector, attr_vec)))

        # ── Popularity score ───────────────────────────────────────────────────
        nr_tags = tags_counts_per_attr.get(attr.id, 0)
        if max_tags > 0:
            popularity_score = math.log(1 + nr_tags) / math.log(1 + max_tags)
        else:
            popularity_score = 0.0

        # ── Rarity bonus (IDF-based) ───────────────────────────────────────────
        # Formula: mean( user_score[tid] * (effective_idf(idf[tid], attr_score[tid]) - 1.0) )
        #          pentru tagurile comune utilizator–atractie
        # (effective_idf - 1.0) ∈ [0, 1]  ⟹  rarity_bonus ∈ [0, 1]
        # Replica logica din country_recommender.py liniile 316-320 si 347-348,
        # adaptata la nivel de atractie.
        rarity_bonus = 0.0
        if user_high_score_tags:
            common_tags = attr_tag_ids & set(user_high_score_tags.keys())
            if common_tags:
                rarity_sum = sum(
                    user_high_score_tags[tid] * (
                        _effective_idf_attr(
                            tag_idf.get(tid, 1.0),
                            attr_scores_on_tags.get(tid, 1.0),
                        ) - 1.0
                    )
                    for tid in common_tags
                )
                rarity_bonus = rarity_sum / len(common_tags)  # media per tag comun

        # ── Budget penalty (original logic preserved) ──────────────────────────
        budget_penalty = 0.0
        if budget_level == "budget" and attr.entry_fee_eur and attr.entry_fee_eur > 20:
            budget_penalty = 0.2
        elif budget_level == "luxury" and attr.entry_fee_eur == 0:
            budget_penalty = 0.05

        final_score = (
            0.70 * cosine_score
            + 0.20 * popularity_score
            + 0.10 * rarity_bonus
            - budget_penalty
        )

        results.append({
            "attraction": attr,
            "score": final_score,
            "_cosine": cosine_score,
            "_popularity": popularity_score,
            "_rarity": rarity_bonus,
        })

    results.sort(key=lambda x: x["score"], reverse=True)

    if log_n > 0:
        for item in results[:log_n]:
            a = item["attraction"]
            logger.info(
                f"Attraction: {a.name} | cosine={item['_cosine']:.3f} | "
                f"pop={item['_popularity']:.3f} | rarity={item['_rarity']:.3f} | "
                f"final={item['score']:.3f}"
            )

    return results
