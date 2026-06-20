"""
Generare întrebări de clarificare dinamice bazate pe profilul de swipe.
Strategii: conflict detection, gap detection, ambiguity, lifestyle, mandatory.
"""

import logging
from sqlalchemy.orm import Session
from sqlalchemy import text

from app.models.tag import Tag
from app.models.question import Question

logger = logging.getLogger(__name__)

L1_SLUGS = [
    "nature-outdoors", "culture-history", "nightlife-social",
    "adventure-active", "food-drink", "wellness-slow",
    "urban-modern", "family-comfort",
]

L1_LABELS = {
    "nature-outdoors":  "Nature & outdoors",
    "culture-history":  "Culture & history",
    "nightlife-social": "Nightlife",
    "adventure-active": "Adventure & sports",
    "food-drink":       "Food & gastronomy",
    "wellness-slow":    "Wellness & relaxation",
    "urban-modern":     "Urban & modern",
    "family-comfort":   "Family & comfort",
}

NATURE_TAGS = {"nature-outdoors", "hiking-trekking", "wildlife-nature",
               "contemplative-nature", "winter-nature", "beach-water"}
URBAN_TAGS  = {"nightlife-social", "urban-modern", "bar-scene",
               "clubbing", "live-entertainment", "urban-culture", "shopping-fashion"}
SUMMER_TAGS = {"beach-water", "sandy-beaches", "surfing-kitesurfing", "sailing"}
WINTER_TAGS = {"skiing", "northern-lights", "snowshoeing", "ice-skating",
               "winter-nature", "snowmobile"}
FAMILY_TAGS = {"family-comfort", "theme-parks", "child-beaches", "family-attractions",
               "easy-sightseeing", "water-parks"}
NIGHTLIFE_TAGS = {"nightlife-social", "bar-scene", "clubbing", "techno-clubs",
                  "music-festivals", "beach-clubs", "live-entertainment"}

MANDATORY_IDS = {"budget", "season", "travel_style"}
MAX_CLARIFY_QUESTIONS = 6
MAX_OPTIONAL_QUESTIONS = MAX_CLARIFY_QUESTIONS - len(MANDATORY_IDS)
CONFLICT_SCORE_THRESHOLD = 0.15

OPTIONAL_SOURCE_PRIORITY = {
    "conflict": 0,
    "season_conflict": 1,
    "nature_urban": 2,
    "ambiguity": 3,
    "lifestyle": 4,
    "gap": 5,
}

_FALLBACK_MANDATORY = {
    "budget": {
        "question": "What's your average daily budget?",
        "options": [
            {"value": "budget", "label": "Budget (under €50/day)",  "tag_weights": {}},
            {"value": "mid",    "label": "Mid-range (€50–150/day)", "tag_weights": {}},
            {"value": "luxury", "label": "Luxury (over €150/day)",  "tag_weights": {"luxury-spa": 0.4, "michelin-restaurants": 0.4}},
        ],
    },
    "season": {
        "question": "When do you prefer to travel?",
        "options": [
            {"value": "spring", "label": "Spring", "tag_weights": {"local-festivals": 0.3}},
            {"value": "summer", "label": "Summer", "tag_weights": {"sandy-beaches": 0.4, "beach-clubs": 0.4}},
            {"value": "autumn", "label": "Autumn", "tag_weights": {"wine-vineyards": 0.4}},
            {"value": "winter", "label": "Winter", "tag_weights": {"skiing": 0.5, "northern-lights": 0.4}},
            {"value": "any",    "label": "Any season", "tag_weights": {}},
        ],
    },
    "travel_style": {
        "question": "Who do you usually travel with?",
        "options": [
            {"value": "solo",   "label": "Solo",                  "tag_weights": {}},
            {"value": "couple", "label": "As a couple",           "tag_weights": {"boutique-hotels": 0.3}},
            {"value": "family", "label": "With family (kids)",    "tag_weights": {"theme-parks": 0.5, "child-beaches": 0.4}},
            {"value": "group",  "label": "With friends",          "tag_weights": {"techno-clubs": 0.3, "music-festivals": 0.3}},
        ],
    },
}


def preference_strength(score, bayesian: bool = True) -> float:
    try:
        value = float(score or 0)
    except (TypeError, ValueError):
        return 0.0
    if bayesian:
        return max(0.0, value - 0.5)
    return max(0.0, value)


def _score_tags(tag_scores: dict, slugs: set[str], bayesian: bool) -> float:
    return sum(preference_strength(tag_scores.get(slug, 0), bayesian) for slug in slugs)


def _has_right_from(right_slugs: set[str], slugs: set[str]) -> bool:
    return bool(right_slugs.intersection(slugs))


def _optional_priority(question: dict) -> int:
    return OPTIONAL_SOURCE_PRIORITY.get(question.get("source"), 99)


def _db_question_to_dict(q_obj, db: Session, q_id: str = None) -> dict:
    return {
        "id": q_id or f"db_{q_obj.id}",
        "question": q_obj.question_text,
        "type": q_obj.type or "single",
        "source": q_obj.source or "gap",
        "options": [
            {
                "value": opt.value or str(i),
                "label": opt.option_text,
                "tag_weights": {
                    row[0]: row[1]
                    for row in db.execute(
                        text("SELECT t.slug, ot.weight FROM option_tags ot JOIN tags t ON t.id = ot.tag_id WHERE ot.option_id = :oid"),
                        {"oid": opt.id}
                    ).fetchall()
                },
            }
            for i, opt in enumerate(q_obj.options)
        ],
    }


def get_clarify_questions(session, db: Session) -> list:
    """Generează până la 8 întrebări de clarificare pentru sesiunea dată."""
    import json

    swipe_results = session.swipe_results or {}
    tag_scores    = session.tag_scores or {}
    shown_tags    = set(session.shown_tags or [])
    is_bayesian   = bool(getattr(session, "tag_beliefs", None))

    questions: list = []
    seen_ids: set   = set()

    def add_q(q: dict) -> None:
        if q["id"] not in seen_ids:
            seen_ids.add(q["id"])
            questions.append(q)

    # ── 1. CONFLICT DIN DB ────────────────────────────────────────────────────
    right_slug_set = {s for s, d in swipe_results.items() if d == "right"}
    right_slugs = list(right_slug_set)
    if len(right_slugs) >= 2:
        try:
            right_tag_ids = db.execute(
                text("SELECT id FROM tags WHERE slug = ANY(:slugs)"),
                {"slugs": right_slugs}
            ).fetchall()
            right_ids = [r[0] for r in right_tag_ids]

            if right_ids:
                conflicts = db.execute(
                    text("""
                        SELECT tc.question, tc.options, tc.tag_a_id, tc.tag_b_id
                        FROM tag_conflicts tc
                        WHERE tc.tag_a_id = ANY(:ids) AND tc.tag_b_id = ANY(:ids)
                        LIMIT 1
                    """),
                    {"ids": right_ids}
                ).fetchall()

                for row in conflicts:
                    opts = row[1] if isinstance(row[1], list) else json.loads(row[1])
                    add_q({
                        "id": f"conflict_{row[2]}_{row[3]}",
                        "question": row[0],
                        "type": "single",
                        "source": "conflict",
                        "options": [
                            {"value": str(i), "label": opt, "tag_weights": {}}
                            for i, opt in enumerate(opts)
                        ],
                    })
        except Exception:
            pass

    explicit_season_conflict = _has_right_from(right_slug_set, SUMMER_TAGS) and _has_right_from(right_slug_set, WINTER_TAGS)
    if explicit_season_conflict:
        add_q({
            "id": "season_conflict_summer_winter",
            "question": "For this trip, what matters more?",
            "type": "single",
            "source": "season_conflict",
            "options": [
                {
                    "value": "summer",
                    "label": "Sun, beaches and warm water",
                    "tag_weights": {
                        "sandy-beaches": 0.45,
                        "beach-clubs": 0.25,
                        "sailing": 0.25,
                        "skiing": -0.25,
                        "northern-lights": -0.2,
                    },
                },
                {
                    "value": "winter",
                    "label": "Snow, mountains and nordic vibes",
                    "tag_weights": {
                        "skiing": 0.45,
                        "northern-lights": 0.35,
                        "winter-nature": 0.3,
                        "sandy-beaches": -0.25,
                        "beach-clubs": -0.2,
                    },
                },
                {"value": "both", "label": "Both, if the destination combines them", "tag_weights": {}},
            ],
        })

    if _has_right_from(right_slug_set, FAMILY_TAGS) and _has_right_from(right_slug_set, NIGHTLIFE_TAGS):
        add_q({
            "id": "lifestyle_family_nightlife",
            "question": "What vibe are you going for on this trip?",
            "type": "single",
            "source": "conflict",
            "options": [
                {
                    "value": "family",
                    "label": "Comfortable and family-friendly",
                    "tag_weights": {
                        "family-comfort": 0.45,
                        "theme-parks": 0.3,
                        "easy-sightseeing": 0.25,
                        "techno-clubs": -0.25,
                        "bar-scene": -0.2,
                    },
                },
                {
                    "value": "nightlife",
                    "label": "Social, lively, with strong nights out",
                    "tag_weights": {
                        "nightlife-social": 0.45,
                        "techno-clubs": 0.35,
                        "bar-scene": 0.25,
                        "family-comfort": -0.25,
                        "theme-parks": -0.2,
                    },
                },
                {"value": "balanced", "label": "A balanced mix", "tag_weights": {}},
            ],
        })

    # ── 1b. NATURE vs URBAN ───────────────────────────────────────────────────
    nature_score = _score_tags(tag_scores, NATURE_TAGS, is_bayesian)
    urban_score  = _score_tags(tag_scores, URBAN_TAGS, is_bayesian)
    if nature_score > CONFLICT_SCORE_THRESHOLD and urban_score > CONFLICT_SCORE_THRESHOLD:
        for q_obj in db.query(Question).filter(Question.source == "nature_urban").order_by(text("RANDOM()")).limit(1).all():
            add_q(_db_question_to_dict(q_obj, db, f"nature_urban_{q_obj.id}"))

    # ── 1c. SEASON CONFLICT ───────────────────────────────────────────────────
    summer_score = _score_tags(tag_scores, SUMMER_TAGS, is_bayesian)
    winter_score = _score_tags(tag_scores, WINTER_TAGS, is_bayesian)
    nature_base  = preference_strength(tag_scores.get("nature-outdoors", 0), is_bayesian)
    if not explicit_season_conflict and (
        (summer_score > CONFLICT_SCORE_THRESHOLD and winter_score > CONFLICT_SCORE_THRESHOLD)
        or (nature_base > CONFLICT_SCORE_THRESHOLD and winter_score > CONFLICT_SCORE_THRESHOLD)
    ):
        for q_obj in db.query(Question).filter(Question.source == "season_conflict").order_by(text("RANDOM()")).limit(1).all():
            add_q(_db_question_to_dict(q_obj, db, f"season_conflict_{q_obj.id}"))

    # ── 2. GAP DETECTION ──────────────────────────────────────────────────────
    for l1_slug in L1_SLUGS:
        if len([q for q in questions if q["source"] == "gap"]) >= 2:
            break
        if l1_slug in shown_tags:
            continue
        tag = db.query(Tag).filter(Tag.slug == l1_slug).first()
        if not tag:
            continue
        gap_q = db.query(Question).filter(Question.tag_id == tag.id, Question.source == "gap").first()
        if gap_q:
            add_q(_db_question_to_dict(gap_q, db, f"gap_{l1_slug}"))

    # ── 3. AMBIGUITY DETECTION ────────────────────────────────────────────────
    positive_l1 = {
        s: preference_strength(sc, is_bayesian)
        for s, sc in tag_scores.items()
        if s in L1_SLUGS and preference_strength(sc, is_bayesian) > 0
    }
    if len(positive_l1) >= 2:
        sorted_l1 = sorted(positive_l1.items(), key=lambda x: x[1], reverse=True)
        top1_slug, top1_score = sorted_l1[0]
        top2_slug, top2_score = sorted_l1[1]
        if top1_score > 0 and abs(top1_score - top2_score) < 0.3:
            add_q({
                "id": f"ambiguity_{top1_slug}_{top2_slug}",
                "question": "If you had to choose — what matters more?",
                "type": "single",
                "source": "ambiguity",
                "options": [
                    {"value": top1_slug, "label": L1_LABELS.get(top1_slug, top1_slug), "tag_weights": {top1_slug: 0.6}},
                    {"value": top2_slug, "label": L1_LABELS.get(top2_slug, top2_slug), "tag_weights": {top2_slug: 0.6}},
                    {"value": "both",    "label": "Both matter equally",  "tag_weights": {}},
                ],
            })

    # ── 4. LIFESTYLE ──────────────────────────────────────────────────────────
    lifestyle_q = db.query(Question).filter(Question.source == "lifestyle").order_by(text("RANDOM()")).first()
    if lifestyle_q:
        add_q(_db_question_to_dict(lifestyle_q, db, "lifestyle"))

    # ── 5. MANDATORY ──────────────────────────────────────────────────────────
    for mandatory_id in ["budget", "season", "travel_style"]:
        keyword = mandatory_id.replace("_", " ").split()[0]
        mq = db.query(Question).filter(
            Question.source == "mandatory",
            Question.question_text.ilike(f"%{keyword}%"),
        ).first()

        if mq:
            add_q(_db_question_to_dict(mq, db, mandatory_id))
        else:
            fb = _FALLBACK_MANDATORY[mandatory_id]
            add_q({
                "id": mandatory_id,
                "question": fb["question"],
                "type": "single",
                "source": "mandatory",
                "options": fb["options"],
            })

    # Mandatory (budget/season/travel_style) trebuie mereu prezente —
    # altfel quiz-ul nu poate fi completat. Le rezervăm slot-uri fixe.
    mandatory = [q for q in questions if q["id"] in MANDATORY_IDS]
    optional = [q for q in questions if q["id"] not in MANDATORY_IDS]
    optional = sorted(optional, key=_optional_priority)
    return optional[:MAX_OPTIONAL_QUESTIONS] + mandatory
