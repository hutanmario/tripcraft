"""
app/routers/quiz_v4.py
======================
Quiz v4 — adaptive, bazat pe geografia nouă (countries/cities/attractions).

Flow:
  POST /quiz/v4/start   → sesiune nouă + primul card
  POST /quiz/v4/swipe   → înregistrează swipe, returnează next card sau phase=clarify
  POST /quiz/v4/answer  → răspuns la întrebare obligatorie/conflict
  GET  /quiz/v4/results → top 5 țări cu scoruri
  GET  /quiz/v4/profile → profilul de taguri al utilizatorului
"""

import uuid
import random
import logging
import requests
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from app.limiter import limiter
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_user
from app.models.quiz_v4_session import QuizV4Session
from app.models.user import User
from app.models.tag import Tag
from app.config import settings

from app.services.quiz_engine import (
    MIN_CARDS, MAX_CARDS, ENTROPY_THRESHOLD, MIN_L3_BEFORE_STOP, L1_ORDER,
    compute_entropy, adjust_tag_score, compute_adaptive_lambda, generate_prompt,
)
from app.services.clarify_generator import get_clarify_questions
from app.models.recommendation import RecommendationImpression
from app.services.country_recommender import SCORING_MODEL_VERSION, compute_country_scores, get_country_tag_idf

router = APIRouter(prefix="/quiz/v4", tags=["Quiz v4"])


def _profile_confidence(session: QuizV4Session, final_profile: dict) -> dict:
    beliefs = session.tag_beliefs or {}
    profile_values = [float(v) for v in (final_profile or {}).values() if isinstance(v, (int, float))]
    top_slugs = [
        slug for slug, _ in sorted((final_profile or {}).items(), key=lambda item: item[1], reverse=True)[:8]
    ]

    evidence_values = []
    for slug in top_slugs:
        belief = beliefs.get(slug)
        if belief:
            evidence_values.append(float(belief.get("alpha", 1.0)) + float(belief.get("beta", 1.0)))

    avg_evidence = sum(evidence_values) / len(evidence_values) if evidence_values else 0.0
    evidence_score = min(avg_evidence / 8.0, 1.0)
    card_score = min(float(session.card_count or 0) / float(MAX_CARDS), 1.0)

    if len(profile_values) >= 2:
        mean_score = sum(profile_values) / len(profile_values)
        variance = sum((value - mean_score) ** 2 for value in profile_values) / len(profile_values)
        concentration_score = min((variance ** 0.5) / 0.35, 1.0)
    else:
        concentration_score = 0.0

    entropy_score = 0.0
    try:
        entropy = float(session.last_entropy)
        if entropy < 999:
            entropy_score = max(0.0, min(1.0, 1.0 - entropy / 4.0))
    except (TypeError, ValueError):
        entropy_score = 0.0

    value = round(
        0.35 * evidence_score
        + 0.25 * card_score
        + 0.25 * concentration_score
        + 0.15 * entropy_score,
        4,
    )
    label = "High confidence" if value >= 0.7 else "Medium confidence" if value >= 0.45 else "Early signal"
    return {
        "value": value,
        "label": label,
        "avg_evidence": round(avg_evidence, 2),
        "card_count": session.card_count,
        "method": "beta_evidence_card_count_profile_concentration_entropy",
    }
logger = logging.getLogger(__name__)
VALID_SWIPE_DIRECTIONS = {"right", "left", "skip"}


# ─── SCHEMAS ──────────────────────────────────────────────────────────────────

class StartResponse(BaseModel):
    session_id: str
    card: dict
    card_count: int
    phase: str = "swipe"


class SwipeRequest(BaseModel):
    session_id: str
    tag_slug: str
    direction: str          # "right" | "left" | "skip"
    image_url: Optional[str] = None


class SwipeResponse(BaseModel):
    phase: str              # "swipe" | "clarify"
    card: Optional[dict] = None
    card_count: int
    entropy: float
    questions: Optional[list] = None


class AnswerRequest(BaseModel):
    session_id: str
    question_id: str
    answer: str


class AnswerResponse(BaseModel):
    phase: str              # "clarify" | "completed"
    next_question: Optional[dict] = None
    results_ready: bool = False


# ─── SESSION OWNERSHIP ────────────────────────────────────────────────────────

def get_owned_quiz_session(session_id: str, db: Session, current_user: User) -> QuizV4Session:
    try:
        sid = uuid.UUID(str(session_id))
    except (TypeError, ValueError):
        raise HTTPException(status_code=400, detail="Invalid session_id")

    session = db.query(QuizV4Session).filter(QuizV4Session.id == sid).first()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    if session.user_id is None or session.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Session does not belong to current user")

    return session


# ─── CARD BUILDING ────────────────────────────────────────────────────────────

def fetch_unsplash_image(query: str, exclude_ids: list) -> dict:
    access_key = settings.UNSPLASH_ACCESS_KEY
    if not access_key:
        return {
            "url": f"https://source.unsplash.com/800x600/?{query.replace(' ', ',')}",
            "id": str(uuid.uuid4()),
            "credit": "Unsplash",
        }
    try:
        resp = requests.get(
            "https://api.unsplash.com/search/photos",
            params={"query": query, "per_page": 10, "orientation": "landscape"},
            headers={"Authorization": f"Client-ID {access_key}"},
            timeout=8,
        )
        if resp.status_code == 200:
            results = resp.json().get("results", [])
            fresh = [r for r in results if r["id"] not in exclude_ids] or results
            if fresh:
                photo = fresh[0]
                return {
                    "url": photo["urls"]["regular"],
                    "id": photo["id"],
                    "credit": photo["user"]["name"],
                    "alt": photo.get("alt_description", query),
                }
    except Exception:
        pass
    return {
        "url": f"https://source.unsplash.com/800x600/?{query.replace(' ', ',')}",
        "id": str(uuid.uuid4()),
        "credit": "Unsplash",
    }


def get_tag_level(tag: Tag, db: Session) -> str:
    if tag.parent_id is None:
        return "L1"
    parent = tag.parent or db.query(Tag).filter(Tag.id == tag.parent_id).first()
    if parent and parent.parent_id is None:
        return "L2"
    return "L3"


def sort_l3_by_idf(tags: list[Tag], db: Session) -> list[Tag]:
    tag_idf = get_country_tag_idf(db)
    return sorted(tags, key=lambda tag: tag_idf.get(tag.slug, 1.0), reverse=True)


def get_next_tag(session: QuizV4Session, db: Session) -> Optional[Tag]:
    """Selectează următorul tag pentru swipe folosind decision tree adaptiv."""
    shown = set(session.shown_tags or [])
    swipe_results = session.swipe_results or {}
    card_count = session.card_count

    # Faza 1: L1 obligatorii (toate cele 8 categorii).
    # /start afiseaza L1_ORDER[0] si seteaza card_count=1; primul swipe face
    # card_count=2 si apeleaza get_next_tag — deci indexul corect e card_count-1.
    # Conditia <= len(L1_ORDER) asigura ca L1_ORDER[7] (family-comfort) e inclus.
    if card_count <= len(L1_ORDER):
        l1_slug = L1_ORDER[card_count - 1]
        tag = db.query(Tag).filter(Tag.slug == l1_slug, Tag.is_leaf == False).first()
        if tag and tag.slug not in shown:
            return tag
        l1_tag = db.query(Tag).filter(Tag.slug == l1_slug).first()
        if l1_tag:
            child = db.query(Tag).filter(Tag.parent_id == l1_tag.id, Tag.slug.notin_(shown)).first()
            if child:
                return child

    right_slugs = [slug for slug, d in swipe_results.items() if d == "right"]
    right_tags = db.query(Tag).filter(Tag.slug.in_(right_slugs)).all() if right_slugs else []
    right_l1_tags = [tag for tag in right_tags if get_tag_level(tag, db) == "L1"]

    # Faza 2 (primary): L3 frunze din L1-urile placute, round-robin prin L2 parinti.
    # Scopul: bugetul ramas dupa Phase 1 merge pe frunze — exact dimensiunea
    # pe care scorarea atractiilor opereaza — acoperind in latime subcategoriile L2.
    if right_l1_tags:
        l2_of_liked: list[Tag] = []
        for l1_tag in right_l1_tags:
            l2s = db.query(Tag).filter(
                Tag.parent_id == l1_tag.id, Tag.is_leaf == False
            ).all()
            l2_of_liked.extend(l2s)
        random.shuffle(l2_of_liked)
        for l2_tag in l2_of_liked:
            l3_tags = db.query(Tag).filter(
                Tag.parent_id == l2_tag.id, Tag.slug.notin_(shown), Tag.is_leaf == True
            ).all()
            if l3_tags:
                return sort_l3_by_idf(l3_tags, db)[0]

    # Faza 3 (fallback): L2 non-leaf daca nu mai exista frunze disponibile
    if right_l1_tags:
        for l1_tag in random.sample(right_l1_tags, len(right_l1_tags)):
            l2_tags = db.query(Tag).filter(
                Tag.parent_id == l1_tag.id, Tag.slug.notin_(shown), Tag.is_leaf == False
            ).all()
            if l2_tags:
                return random.choice(l2_tags)

    # Faza 4: orice frunza L3 neafisata
    any_l3 = db.query(Tag).filter(
        Tag.slug.notin_(shown), Tag.is_leaf == True
    ).all()
    if any_l3:
        return sort_l3_by_idf(any_l3, db)[0]

    # Faza 5: orice L2 neexplorat (last resort)
    unexplored = db.query(Tag).filter(
        Tag.slug.notin_(shown), Tag.is_leaf == False, Tag.parent_id.isnot(None)
    ).all()
    if unexplored:
        return random.choice(unexplored)

    return None


def build_card(tag: Tag, session: QuizV4Session, db: Session) -> dict:
    shown_images = session.shown_images or []
    query = tag.name
    if tag.parent_id:
        parent = db.query(Tag).filter(Tag.id == tag.parent_id).first()
        if parent:
            query = f"{parent.name} {tag.name} travel"
    else:
        query = f"{tag.name} travel destination"

    image = fetch_unsplash_image(query, shown_images)
    return {
        "tag_slug":    tag.slug,
        "tag_name":    tag.name,
        "tag_level":   get_tag_level(tag, db),
        "image_url":   image["url"],
        "image_id":    image["id"],
        "image_credit": image.get("credit", ""),
        "prompt":      generate_prompt(tag.slug, tag.name),
    }


# ─── ENDPOINTS ────────────────────────────────────────────────────────────────

@router.post("/start")
def start_quiz(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    session = QuizV4Session(
        user_id=current_user.id,
        shown_tags=[],
        shown_images=[],
        swipe_results={},
        tag_scores={},
        tag_beliefs={},   # initializat explicit ca dict gol (nu None) — garanteaza modul Beta
        card_count=0,
        current_stage="swipe",
    )
    db.add(session)
    db.flush()

    first_tag = db.query(Tag).filter(Tag.slug == L1_ORDER[0]).first()
    if not first_tag:
        first_tag = db.query(Tag).filter(Tag.is_leaf == False, Tag.parent_id == None).first()

    card = build_card(first_tag, session, db)
    session.shown_tags   = [first_tag.slug]
    session.shown_images = [card["image_id"]]
    session.card_count   = 1
    db.commit()
    db.refresh(session)

    return {"session_id": str(session.id), "card": card, "card_count": 1, "phase": "swipe", "entropy": 999.0}


@router.post("/swipe")
@limiter.limit("60/minute")
def swipe_card(request: Request, req: SwipeRequest, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    session = get_owned_quiz_session(req.session_id, db, current_user)
    if session.current_stage != "swipe":
        raise HTTPException(status_code=400, detail=f"Session is in stage: {session.current_stage}")

    direction = (req.direction or "").lower().strip()
    if direction not in VALID_SWIPE_DIRECTIONS:
        raise HTTPException(status_code=400, detail="Invalid swipe direction")

    swipe_results = dict(session.swipe_results or {})
    swipe_results[req.tag_slug] = direction
    session.swipe_results = swipe_results

    tag_scores   = dict(session.tag_scores or {})
    tag_beliefs  = dict(session.tag_beliefs or {})

    tag = db.query(Tag).filter(Tag.slug == req.tag_slug).first()
    if tag and direction != "skip":
        if req.tag_slug not in tag_beliefs:
            tag_beliefs[req.tag_slug] = {"alpha": 1.0, "beta": 1.0}
        if direction == "right":
            tag_beliefs[req.tag_slug]["alpha"] += 1.0
        else:
            tag_beliefs[req.tag_slug]["beta"] += 0.5
        b = tag_beliefs[req.tag_slug]
        tag_scores[req.tag_slug] = round(b["alpha"] / (b["alpha"] + b["beta"]), 4)
        session.tag_beliefs = tag_beliefs

    session.tag_scores = tag_scores
    session.card_count = (session.card_count or 0) + 1

    prev_entropy = float(session.last_entropy or 999)
    entropy = compute_entropy(tag_scores)
    session.last_entropy = str(round(entropy, 4))

    # Estimam carduri L3 vazute: dupa fix-ul Phase 1 (8 L1 obligatorii),
    # toate cardurile de la index 9 incolo sunt L3 frunze (Phase 2 prioritizeaza frunze).
    l3_shown_estimate = max(0, session.card_count - len(L1_ORDER))
    should_stop = (
        session.card_count >= MAX_CARDS
        or (session.card_count >= MIN_CARDS and entropy < ENTROPY_THRESHOLD
            and l3_shown_estimate >= MIN_L3_BEFORE_STOP)
        or (session.card_count >= 16 and abs(prev_entropy - entropy) < 0.1
            and l3_shown_estimate >= MIN_L3_BEFORE_STOP)
    )

    if should_stop:
        all_questions = get_clarify_questions(session, db)
        session.clarify_questions = all_questions
        session.current_stage = "clarify"
        db.commit()
        return {"phase": "clarify", "card": None, "card_count": session.card_count,
                "entropy": round(entropy, 4), "questions": all_questions}

    next_tag = get_next_tag(session, db)
    if not next_tag:
        all_questions = get_clarify_questions(session, db)
        session.clarify_questions = all_questions
        session.current_stage = "clarify"
        db.commit()
        return {"phase": "clarify", "card": None, "card_count": session.card_count,
                "entropy": round(entropy, 4), "questions": all_questions}

    card = build_card(next_tag, session, db)
    session.shown_tags   = list(session.shown_tags or []) + [next_tag.slug]
    session.shown_images = list(session.shown_images or []) + [card["image_id"]]
    db.commit()

    return {"phase": "swipe", "card": card, "card_count": session.card_count,
            "entropy": round(entropy, 4), "questions": None}


@router.post("/answer")
def answer_question(req: AnswerRequest, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    session = get_owned_quiz_session(req.session_id, db, current_user)

    clarify_answers = list(session.clarify_answers or [])
    existing = next((a for a in clarify_answers if a["question_id"] == req.question_id), None)
    if existing:
        existing["answer"] = req.answer
    else:
        clarify_answers.append({"question_id": req.question_id, "answer": req.answer})
    session.clarify_answers = clarify_answers

    if req.question_id == "budget":
        session.budget = req.answer
    elif req.question_id == "season":
        session.season = req.answer
    elif req.question_id == "travel_style":
        session.travel_style = req.answer

    tag_scores  = dict(session.tag_scores or {})
    is_bayesian = session.tag_beliefs is not None  # {} e falsy dar e Bayesian; None = sesiune legacy

    def apply_weights(question_id: str) -> None:
        clarify_qs = session.clarify_questions or []
        q = next((x for x in clarify_qs if x["id"] == question_id), None)
        if q:
            opt = next((o for o in q.get("options", []) if o["value"] == req.answer), None)
            if opt:
                for slug, weight in opt.get("tag_weights", {}).items():
                    adjust_tag_score(tag_scores, slug, weight, is_bayesian)

    if req.question_id in ("budget", "season", "travel_style"):
        apply_weights(req.question_id)

    elif req.question_id.startswith("conflict_"):
        parts = req.question_id.split("_")
        if len(parts) == 3:
            try:
                tag_a = db.query(Tag).filter(Tag.id == int(parts[1])).first()
                tag_b = db.query(Tag).filter(Tag.id == int(parts[2])).first()
                if tag_a and tag_b:
                    if req.answer == "0":
                        adjust_tag_score(tag_scores, tag_a.slug,  0.5, is_bayesian)
                        adjust_tag_score(tag_scores, tag_b.slug, -0.3, is_bayesian)
                    elif req.answer == "1":
                        adjust_tag_score(tag_scores, tag_b.slug,  0.5, is_bayesian)
                        adjust_tag_score(tag_scores, tag_a.slug, -0.3, is_bayesian)
            except (ValueError, IndexError):
                pass

    elif req.question_id == "lifestyle" or req.question_id.startswith(
        ("gap_", "lifestyle_", "nature_urban_", "season_conflict_")
    ):
        apply_weights(req.question_id)

    elif req.question_id.startswith("ambiguity_"):
        if req.answer != "both" and req.answer in tag_scores:
            adjust_tag_score(tag_scores, req.answer, 0.6, is_bayesian)
            parts = req.question_id.split("_", 1)[1]
            other = parts.replace(req.answer + "_", "").replace("_" + req.answer, "")
            if other and other != req.answer:
                adjust_tag_score(tag_scores, other, -0.2, is_bayesian)

    session.tag_scores = tag_scores

    answered_ids    = {a["question_id"] for a in clarify_answers}
    mandatory_ids   = {"budget", "season", "travel_style"}
    all_question_ids = {q["id"] for q in (session.clarify_questions or [])}

    if all_question_ids.issubset(answered_ids) and mandatory_ids.issubset(answered_ids):
        tag_scores_snap = dict(session.tag_scores or {})

        if session.tag_beliefs:
            normalized_scores = {k: v for k, v in tag_scores_snap.items() if v > 0.5}
        else:
            positive = {k: max(0, v) for k, v in tag_scores_snap.items()}
            max_score = max(positive.values()) if positive else 1.0
            normalized_scores = {k: v / max_score for k, v in positive.items()}

        # Propagare L1/L2 → copii
        nl_tags = db.query(Tag).filter(Tag.is_leaf == False).all()
        nl_by_slug = {t.slug: t for t in nl_tags}
        children_by_parent: dict = {}
        if nl_tags:
            for t in db.query(Tag).filter(Tag.parent_id.in_([t.id for t in nl_tags])).all():
                children_by_parent.setdefault(t.parent_id, []).append(t)

        directly_swiped = set(tag_scores_snap.keys())
        expanded = dict(normalized_scores)
        for slug, score in list(normalized_scores.items()):
            tag = nl_by_slug.get(slug)
            if tag:
                for child in children_by_parent.get(tag.id, []):
                    if child.slug not in directly_swiped:
                        expanded[child.slug] = expanded.get(child.slug, 0) + score * 0.6
                        if not child.is_leaf:
                            for gc in children_by_parent.get(child.id, []):
                                if gc.slug not in directly_swiped:
                                    expanded[gc.slug] = expanded.get(gc.slug, 0) + score * 0.3

        max_exp = max(expanded.values()) if expanded else 1
        session.final_profile  = {k: round(v / max_exp, 4) for k, v in expanded.items() if v > 0}
        session.current_stage  = "completed"
        session.completed_at   = datetime.now(timezone.utc)
        db.commit()
        return {"phase": "completed", "next_question": None, "results_ready": True}

    next_q = next((q for q in (session.clarify_questions or []) if q["id"] not in answered_ids), None)
    db.commit()
    return {"phase": "clarify", "next_question": next_q, "results_ready": False}


@router.get("/results/{session_id}")
def get_results(
    session_id: str,
    diversity: bool = Query(default=True),
    lambda_param: Optional[float] = Query(default=None, ge=0.0, le=1.0),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    session = get_owned_quiz_session(session_id, db, current_user)
    if session.current_stage != "completed":
        raise HTTPException(status_code=400, detail="Quiz not completed yet")

    final_profile = session.final_profile or session.tag_scores or {}
    lambda_used   = lambda_param if lambda_param is not None else compute_adaptive_lambda(final_profile)
    top_countries = compute_country_scores(session, db, diversity=diversity, lambda_param=lambda_param)
    map_countries = compute_country_scores(session, db, diversity=False, top_n=50)
    confidence = _profile_confidence(session, final_profile)

    if diversity and top_countries:
        db.add(RecommendationImpression(
            user_id=current_user.id,
            session_id=str(session.id),
            surface="dashboard",
            model_version=SCORING_MODEL_VERSION,
            ranking=[
                {
                    "rank": idx + 1,
                    "country_id": item.get("country_id"),
                    "country_name": item.get("country_name"),
                    "score": item.get("score"),
                    "matching_tags": item.get("matching_tags", [])[:5],
                }
                for idx, item in enumerate(top_countries)
            ],
            context={
                "budget": session.budget,
                "season": session.season,
                "travel_style": session.travel_style,
                "pace_preference": session.pace_preference,
                "lambda_used": round(lambda_used, 4),
                "confidence": confidence,
            },
        ))
        db.commit()

    return {
        "session_id":   session_id,
        "budget":       session.budget,
        "season":       session.season,
        "travel_style": session.travel_style,
        "pace_preference": session.pace_preference,
        "top_countries": top_countries,
        "map_countries": map_countries,
        "card_count":   session.card_count,
        "lambda_used":  round(lambda_used, 4),
        "confidence": confidence,
        "scoring_model_version": SCORING_MODEL_VERSION,
    }


@router.get("/profile/{session_id}")
def get_profile(session_id: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    session = get_owned_quiz_session(session_id, db, current_user)
    profile = session.final_profile or session.tag_scores or {}
    sorted_profile = sorted(profile.items(), key=lambda x: x[1], reverse=True)[:20]

    enriched = []
    for slug, score in sorted_profile:
        if score <= 0:
            continue
        tag = db.query(Tag).filter(Tag.slug == slug).first()
        if tag:
            enriched.append({"slug": slug, "name": tag.name, "score": round(score, 4), "is_leaf": tag.is_leaf})

    return {
        "session_id": session_id,
        "stage":      session.current_stage,
        "card_count": session.card_count,
        "entropy":    session.last_entropy,
        "profile":    enriched,
    }
