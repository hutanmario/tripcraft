"""
ml.py
Router pentru endpoint-urile de ML — CLIP tagging, TF-IDF, embeddings.
"""

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional
import requests
import logging
import time
import numpy as np
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone

from app.database import get_db, SessionLocal
from app.models.tag import Tag
from app.models.quiz_v4_session import QuizV4Session
from app.services.clip_service import clip_service
from app.services.image_db_tagging_service import image_db_tagging_service
from app.services.clarify_generator import MANDATORY_IDS, get_clarify_questions
from app.services.quiz_engine import adjust_tag_score
from app.dependencies import get_current_user
from app.models.user import User
import uuid
from sentence_transformers import SentenceTransformer, util as st_util

logger = logging.getLogger(__name__)

_st_model = None
_clip_jobs: dict = {}
_clip_executor = ThreadPoolExecutor(max_workers=2)


def get_st_model():
    global _st_model
    if _st_model is None:
        _st_model = SentenceTransformer('all-MiniLM-L6-v2')
    return _st_model


router = APIRouter(prefix="/ml", tags=["Machine Learning"])


# ─── Schemas ──────────────────────────────────────────────────────────────────

class ImageUrlRequest(BaseModel):
    image_url: str
    top_k: Optional[int] = 8



class ImageB64Item(BaseModel):
    data: str  # base64 JPEG
    name: str = "photo.jpg"

class AnalyzePhotosB64Request(BaseModel):
    files: list[ImageB64Item]


class PhotoClarifyAnswer(BaseModel):
    question_id: str
    answer: str


class ConfirmPhotoAnalysisRequest(BaseModel):
    session_id: str
    tag_scores: dict[str, float]
    clarification: Optional[PhotoClarifyAnswer] = None
    selected_check: Optional[str] = None


# ─── Constante pentru analyze-photos ──────────────────────────────────────────

_CLIP_OVERRIDE_MAP = {
    "summer": "beach-water",
    "warm": "beach-water",
    "tropical": "beach-water",
    "winter": "winter-nature",
    "skiing": "winter-nature",
    "city": "urban-modern",
    "urban": "urban-modern",
    "shopping": "urban-modern",
    "history": "culture-history",
    "ancient-ruins": "historical-sites",
    "castles": "historical-sites",
    "religious": "historical-sites",
    "romantic": "romantic-couple",
    "wellness": "wellness-slow",
    "spa": "wellness-slow",
    "hiking": "hiking-trekking",
    "mountain": "adventure-active",
}

_BLACKLISTED_SLUGS = {
    "hot-springs-outdoor", "roman-history", "living-culture",
    "national-parks", "music-festivals"
}


def _run_clip_analysis_legacy(files_data: list, user_id: Optional[int] = None) -> dict:
    """
    Procesează imaginile CLIP și returnează profilul de taguri + scene analysis.
    Rulează în thread separat — creează propria sesiune DB.
    """
    from collections import Counter
    db = SessionLocal()
    try:
        total_start = time.time()
        num_images = len(files_data)

        tag_sum: dict = {}
        tag_count: dict = {}
        scene_results = []
        season_results = []

        for file_data in files_data:
            contents = file_data["contents"]
            t0 = time.time()
            tags = clip_service.tag_image_from_bytes(contents, top_k=15)
            elapsed = time.time() - t0
            logger.info(f"CLIP ViT-L/14 inference: {elapsed:.2f}s for {file_data['filename']}")

            for tag, score in tags.items():
                tag_sum[tag] = tag_sum.get(tag, 0) + score
                tag_count[tag] = tag_count.get(tag, 0) + 1

            scene = clip_service.analyze_scene(contents)
            scene_results.append(scene)

            colors = clip_service.extract_dominant_colors(contents)
            for tag, boost in colors["preference_boosts"].items():
                tag_sum[tag] = tag_sum.get(tag, 0) + boost * 0.5
                tag_count[tag] = tag_count.get(tag, 0) + 0.3

            season = clip_service.estimate_season(contents)
            season_results.append(season)
            for tag, boost in season["tag_boosts"].items():
                tag_sum[tag] = tag_sum.get(tag, 0) + boost * 0.4
                tag_count[tag] = tag_count.get(tag, 0) + 0.2

        # Agregare ponderată prin frecvență: avg_score_când_prezent * sqrt(frecvență)
        aggregated_scores = {}
        for tag in tag_sum:
            if tag_count[tag] > 0:
                avg_when_present = tag_sum[tag] / tag_count[tag]
                frequency = min(tag_count[tag] / num_images, 1.0)
                aggregated_scores[tag] = avg_when_present * (frequency ** 0.5)

        # Threshold adaptiv: mean + 0.5 * std
        if aggregated_scores:
            scores_list = list(aggregated_scores.values())
            mean_s = float(np.mean(scores_list))
            std_s = float(np.std(scores_list))
            adaptive_threshold = mean_s + 0.5 * std_s
            significant_tags = {t: s for t, s in aggregated_scores.items() if s > adaptive_threshold}
            if len(significant_tags) < 3:
                sorted_fallback = sorted(aggregated_scores.items(), key=lambda x: -x[1])
                significant_tags = dict(sorted_fallback[:3])
        else:
            significant_tags = {}

        # Mapează tagurile CLIP la slug-urile din DB prin semantic matching
        db_tags = db.query(Tag).all()
        db_slugs = [t.slug for t in db_tags]
        db_names = [t.name if hasattr(t, 'name') and t.name else t.slug.replace('-', ' ') for t in db_tags]

        model = get_st_model()
        db_embeddings = model.encode(db_names, convert_to_tensor=True)

        tag_scores = {}
        for clip_tag, score in significant_tags.items():
            clip_embedding = model.encode(clip_tag.replace('-', ' '), convert_to_tensor=True)
            similarities = st_util.cos_sim(clip_embedding, db_embeddings)[0]
            best_idx = int(similarities.argmax())
            best_score = float(similarities[best_idx])

            if best_score > 0.35:
                best_slug = db_slugs[best_idx]
                if best_slug not in tag_scores:
                    tag_scores[best_slug] = 0
                tag_scores[best_slug] = max(tag_scores[best_slug], round(score, 4))

        # Override manual pentru taguri cu mapping greșit cunoscut
        for clip_tag, db_slug in _CLIP_OVERRIDE_MAP.items():
            if clip_tag in significant_tags:
                score = significant_tags[clip_tag]
                if db_slug not in tag_scores:
                    tag_scores[db_slug] = 0
                tag_scores[db_slug] = max(tag_scores[db_slug], round(score, 4))
                wrong_slugs = [k for k in list(tag_scores.keys()) if k != db_slug and clip_tag in k]
                for w in wrong_slugs:
                    del tag_scores[w]

        tag_scores = {k: v for k, v in tag_scores.items() if k not in _BLACKLISTED_SLUGS}

        logger.info(f"detected_tags: {significant_tags}")
        logger.info(f"matched_db_tags: {tag_scores}")

        # Agregare scene analysis — vot majoritar peste toate imaginile
        def majority(lst):
            return Counter(lst).most_common(1)[0][0] if lst else None

        final_scene = {
            "setting": majority([s["setting"] for s in scene_results]),
            "environment": majority([s["environment"] for s in scene_results]),
            "crowding": majority([s["crowding"] for s in scene_results]),
            "time_of_day": majority([s["time_of_day"] for s in scene_results]),
            "has_landmark": any(s["has_landmark"] for s in scene_results),
            "has_food": any(s["has_food"] for s in scene_results),
            "has_beach": any(s["has_beach"] for s in scene_results),
            "has_mountain": any(s["has_mountain"] for s in scene_results),
            "dominant_season": majority([s["dominant_season"] for s in season_results]),
        }

        # Creează sesiune QuizV4 cu profilul generat din poze
        session_id = uuid.uuid4()
        session = QuizV4Session(
            id=session_id,
            user_id=user_id,
            tag_scores=tag_scores,
            current_stage='completed',
            final_profile=tag_scores,
            completed_at=datetime.now(timezone.utc),
        )
        db.add(session)
        db.commit()

        total_elapsed = time.time() - total_start
        logger.info(f"Total CLIP analysis: {total_elapsed:.2f}s for {num_images} images")

        return {
            "session_id": str(session_id),
            "detected_tags": significant_tags,
            "matched_db_tags": tag_scores,
            "scene_analysis": final_scene,
            "num_images_analyzed": num_images,
            "processing_time": round(total_elapsed, 2),
        }
    finally:
        db.close()


def _run_clip_analysis(files_data: list, user_id: Optional[int] = None) -> dict:
    """
    Proceseaza 1-5 poze ale userului si extrage taguri reale din DB.
    Ruleaza in thread separat si creeaza propria sesiune DB.
    """
    db = SessionLocal()
    try:
        total_start = time.time()
        analysis = image_db_tagging_service.analyze_user_photos(db=db, files_data=files_data)
        tag_scores = analysis["matched_db_tags"]
        if not tag_scores:
            raise RuntimeError("Nu s-au putut extrage taguri relevante din poze.")

        session_id = uuid.uuid4()
        session = QuizV4Session(
            id=session_id,
            user_id=user_id,
            tag_scores=tag_scores,
            current_stage="completed",
            final_profile=tag_scores,
            completed_at=datetime.now(timezone.utc),
        )
        db.add(session)
        db.commit()

        total_elapsed = time.time() - total_start
        logger.info(
            "Photo DB-tag analysis completed in %.2fs for %s images: %s",
            total_elapsed,
            len(files_data),
            tag_scores,
        )

        return {
            **analysis,
            "session_id": str(session_id),
            "matched_db_tags": tag_scores,
            "detected_tags": tag_scores,
            "processing_time": round(total_elapsed, 2),
        }
    finally:
        db.close()


# ─── Endpoints ────────────────────────────────────────────────────────────────

def _get_owned_photo_session(
    session_id: str,
    db: Session,
    current_user: User,
) -> QuizV4Session:
    try:
        session_uuid = uuid.UUID(str(session_id))
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid session_id")

    session = (
        db.query(QuizV4Session)
        .filter(
            QuizV4Session.id == session_uuid,
            QuizV4Session.user_id == current_user.id,
        )
        .first()
    )
    if not session:
        raise HTTPException(status_code=404, detail="Photo analysis session not found")

    return session


def _tag_label(tag: Tag) -> str:
    return tag.name or tag.slug.replace("-", " ").title()


def _top_two_photo_question(session: QuizV4Session, db: Session) -> Optional[dict]:
    profile = session.final_profile or session.tag_scores or {}
    ranked = []
    for slug, raw_score in profile.items():
        try:
            score = float(raw_score)
        except (TypeError, ValueError):
            continue
        if slug and np.isfinite(score) and score > 0:
            ranked.append((slug, score))

    ranked.sort(key=lambda item: item[1], reverse=True)
    top_slugs = [slug for slug, _ in ranked[:4]]
    if len(top_slugs) < 2:
        return None

    tags_by_slug = {
        tag.slug: tag
        for tag in db.query(Tag).filter(Tag.slug.in_(top_slugs)).all()
    }
    usable = [slug for slug in top_slugs if slug in tags_by_slug]
    if len(usable) < 2:
        return None

    first, second = usable[0], usable[1]
    return {
        "id": f"photo_priority_{first}_{second}",
        "question": "What should shape this trip more?",
        "type": "single",
        "source": "photo_priority",
        "options": [
            {
                "value": first,
                "label": _tag_label(tags_by_slug[first]),
                "tag_weights": {first: 0.25, second: -0.08},
            },
            {
                "value": second,
                "label": _tag_label(tags_by_slug[second]),
                "tag_weights": {second: 0.25, first: -0.08},
            },
            {
                "value": "balanced",
                "label": "A balanced mix",
                "tag_weights": {first: 0.08, second: 0.08},
            },
        ],
    }


def _photo_clarify_questions(session: QuizV4Session, db: Session) -> list[dict]:
    questions = list(session.clarify_questions or [])
    if not questions:
        questions = get_clarify_questions(session, db)

    optional_questions = [
        question
        for question in questions
        if question.get("id") not in MANDATORY_IDS
    ]

    priority_question = _top_two_photo_question(session, db)
    if priority_question:
        existing_ids = {question.get("id") for question in questions}
        if priority_question["id"] not in existing_ids:
            questions = [priority_question] + questions
            optional_questions = [priority_question] + optional_questions

    session.clarify_questions = questions
    return optional_questions


def _first_unanswered_photo_clarify_question(
    session: QuizV4Session,
    db: Session,
) -> Optional[dict]:
    answered_ids = {
        answer.get("question_id")
        for answer in (session.clarify_answers or [])
        if isinstance(answer, dict)
    }

    for question in _photo_clarify_questions(session, db):
        if question.get("id") not in answered_ids:
            return question

    return None


def _clarify_weights_for_answer(
    session: QuizV4Session,
    db: Session,
    answer: Optional[PhotoClarifyAnswer],
) -> dict[str, float]:
    if not answer:
        return {}

    questions = _photo_clarify_questions(session, db)
    question = next(
        (item for item in questions if item.get("id") == answer.question_id),
        None,
    )
    if not question:
        return {}

    option = next(
        (
            item
            for item in question.get("options", [])
            if item.get("value") == answer.answer
        ),
        None,
    )
    if not option:
        return {}

    clarify_answers = list(session.clarify_answers or [])
    existing = next(
        (
            item
            for item in clarify_answers
            if item.get("question_id") == answer.question_id
        ),
        None,
    )
    if existing:
        existing["answer"] = answer.answer
    else:
        clarify_answers.append({
            "question_id": answer.question_id,
            "answer": answer.answer,
        })
    session.clarify_answers = clarify_answers

    weights = {}
    for slug, raw_weight in (option.get("tag_weights") or {}).items():
        try:
            weight = float(raw_weight)
        except (TypeError, ValueError):
            continue
        if isinstance(slug, str) and slug.strip() and np.isfinite(weight):
            weights[slug] = weight

    return weights


@router.post("/tag-image-url")
def tag_image_from_url(req: ImageUrlRequest):
    """
    Primește URL-ul unei imagini și returnează tagurile generate de CLIP.
    Util pentru testare și pentru quiz-ul vizual.
    """
    tags = clip_service.tag_image_from_url(req.image_url, req.top_k)
    if not tags:
        raise HTTPException(status_code=422, detail="Nu s-au putut genera taguri pentru această imagine.")
    return {
        "image_url": req.image_url,
        "tags": tags,
        "top_tag": max(tags, key=tags.get),
    }


@router.post("/tag-image-upload")
async def tag_image_from_upload(file: UploadFile = File(...), top_k: int = 8):
    """
    Primește o imagine uploadată și returnează tagurile generate de CLIP.
    """
    contents = await file.read()
    tags = clip_service.tag_image_from_bytes(contents, top_k)
    if not tags:
        raise HTTPException(status_code=422, detail="Nu s-au putut genera taguri pentru această imagine.")
    return {
        "filename": file.filename,
        "tags": tags,
        "top_tag": max(tags, key=tags.get),
    }




@router.get("/quiz-images")
def get_quiz_images():
    """
    Returnează setul de imagini generice pentru quiz-ul vizual bazat pe CLIP.
    Imagini cu scene generale — nu destinații specifice.
    """
    quiz_images = [
        {"id": 1, "url": "https://images.unsplash.com/photo-1507525428034-b723cf961d3e?w=600", "scene": "beach"},
        {"id": 2, "url": "https://images.unsplash.com/photo-1464822759023-fed622ff2c3b?w=600", "scene": "mountain"},
        {"id": 3, "url": "https://images.unsplash.com/photo-1477959858617-67f85cf4f1df?w=600", "scene": "city"},
        {"id": 4, "url": "https://images.unsplash.com/photo-1448375240586-882707db888b?w=600", "scene": "forest"},
        {"id": 5, "url": "https://images.unsplash.com/photo-1533929736458-ca588d08c8be?w=600", "scene": "market"},
        {"id": 6, "url": "https://images.unsplash.com/photo-1551632436-cbf8dd35adfa?w=600", "scene": "adventure"},
        {"id": 7, "url": "https://images.unsplash.com/photo-1555993539-1732b0258235?w=600", "scene": "food"},
        {"id": 8, "url": "https://images.unsplash.com/photo-1548013146-72479768bada?w=600", "scene": "temple"},
        {"id": 9, "url": "https://images.unsplash.com/photo-1520250497591-112f2f40a3f4?w=600", "scene": "wellness"},
        {"id": 10, "url": "https://images.unsplash.com/photo-1516483638261-f4dbaf036963?w=600", "scene": "romantic"},
        {"id": 11, "url": "https://images.unsplash.com/photo-1551524559-8af4e6624178?w=600", "scene": "nightlife"},
        {"id": 12, "url": "https://images.unsplash.com/photo-1500534314209-a25ddb2bd429?w=600", "scene": "nature"},
        {"id": 13, "url": "https://images.unsplash.com/photo-1459478309853-2c33a60058e7?w=600", "scene": "lake"},
        {"id": 14, "url": "https://images.unsplash.com/photo-1506905925346-21bda4d32df4?w=600", "scene": "hiking"},
        {"id": 15, "url": "https://images.unsplash.com/photo-1511882150382-421056c89033?w=600", "scene": "castle"},
    ]
    return {"images": quiz_images, "total": len(quiz_images)}


@router.get("/quiz-clusters")
def get_quiz_clusters():
    """
    Returnează clusterele K-Means pentru quiz-ul vizual ierarhic.
    Level 1: 6 clustere mari
    Level 2: 3 sub-clustere per cluster
    """
    import json
    import os

    clusters_path = os.path.join(
        os.path.dirname(__file__), "..", "..", "static", "quiz-images", "quiz_clusters.json"
    )

    if not os.path.exists(clusters_path):
        raise HTTPException(status_code=404, detail="Clusterele nu au fost generate. Rulează kmeans_quiz_images.py mai întâi.")

    with open(clusters_path, "r", encoding="utf-8") as f:
        clusters = json.load(f)

    # Returnează câte o imagine reprezentativă per cluster pentru Level 1
    level1_images = []
    for cluster_id, cluster_data in clusters["level1"].items():
        level1_images.append({
            "cluster_id": int(cluster_id),
            "dominant_category": cluster_data["dominant_category"],
            "image": cluster_data["representative"],
            "size": cluster_data["size"],
        })

    return {
        "level1": level1_images,
        "full_clusters": clusters,
    }


@router.post("/quiz-tag-selection")
def tag_image_selection(req: ImageUrlRequest):
    """
    Primește URL-ul imaginii selectate de user și returnează tagurile CLIP.
    Folosit când userul face swipe/click pe o imagine din quiz.
    """
    tags = clip_service.tag_image_from_url(req.image_url, top_k=10)
    if not tags:
        raise HTTPException(status_code=422, detail="Nu s-au putut genera taguri.")

    # Filtrăm tagurile cu scor prea mic
    significant_tags = {tag: score for tag, score in tags.items() if score > 0.1}

    return {
        "image_url": req.image_url,
        "tags": significant_tags,
        "top_tags": list(significant_tags.keys())[:5],
    }


@router.post("/analyze-photos")
async def analyze_photos(
    files: list[UploadFile] = File(...),
    current_user: User = Depends(get_current_user),
):
    """
    Primește 1-5 imagini, citește bytes imediat, lansează procesarea CLIP
    în background și returnează job_id pentru polling.
    """
    if not files:
        raise HTTPException(status_code=400, detail="At least 1 image is required")
    if len(files) > 5:
        raise HTTPException(status_code=400, detail="Maximum 5 images allowed")

    # Citește conținutul fișierelor în contextul async înainte de a le trimite în thread
    files_data = []
    for file in files:
        if len(files_data) >= 5:
            break
        contents = await file.read()
        files_data.append({"filename": file.filename or f"photo_{len(files_data)}.jpg", "contents": contents})

    job_id = str(uuid.uuid4())
    _clip_jobs[job_id] = {"status": "processing", "result": None, "error": None}
    user_id = current_user.id

    def process_job():
        try:
            result = _run_clip_analysis(files_data, user_id=user_id)
            _clip_jobs[job_id] = {"status": "done", "result": result, "error": None}
        except Exception as e:
            logger.error(f"CLIP job {job_id} failed: {e}", exc_info=True)
            _clip_jobs[job_id] = {"status": "error", "result": None, "error": str(e)}

    _clip_executor.submit(process_job)

    return {"job_id": job_id, "status": "processing"}


@router.post("/analyze-photos-b64")
async def analyze_photos_b64(
    req: AnalyzePhotosB64Request,
    current_user: User = Depends(get_current_user),
):
    """
    Varianta JSON a analyze-photos — acceptă imagini encodate base64.
    Folosit de React Native new arch unde multipart/FormData cu file URIs e broken.
    """
    import base64 as b64mod
    if not req.files:
        raise HTTPException(status_code=400, detail="At least 1 image is required")
    if len(req.files) > 5:
        raise HTTPException(status_code=400, detail="Maximum 5 images allowed")

    files_data = []
    for item in req.files:
        try:
            contents = b64mod.b64decode(item.data)
        except Exception:
            raise HTTPException(status_code=422, detail=f"Invalid base64 data for {item.name}")
        files_data.append({"filename": item.name, "contents": contents})

    job_id = str(uuid.uuid4())
    _clip_jobs[job_id] = {"status": "processing", "result": None, "error": None}
    user_id = current_user.id

    def process_job():
        try:
            result = _run_clip_analysis(files_data, user_id=user_id)
            _clip_jobs[job_id] = {"status": "done", "result": result, "error": None}
        except Exception as e:
            logger.error(f"CLIP job {job_id} failed: {e}", exc_info=True)
            _clip_jobs[job_id] = {"status": "error", "result": None, "error": str(e)}

    _clip_executor.submit(process_job)
    return {"job_id": job_id, "status": "processing"}


@router.get("/analyze-status/{job_id}")
async def analyze_status(
    job_id: str,
    current_user: User = Depends(get_current_user),
):
    """
    Polling endpoint — returnează statusul unui job CLIP.
    Când statusul e 'done', returnează rezultatul și șterge job-ul din memorie.
    """
    if job_id not in _clip_jobs:
        raise HTTPException(status_code=404, detail="Job not found")

    job = _clip_jobs[job_id]

    if job["status"] == "done":
        result = job["result"]
        del _clip_jobs[job_id]
        return {"status": "done", "result": result}

    if job["status"] == "error":
        error = job["error"]
        del _clip_jobs[job_id]
        raise HTTPException(status_code=500, detail=f"Processing failed: {error}")

    return {"status": "processing"}


@router.get("/photo-clarify/{session_id}")
def get_photo_clarify_question(
    session_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Returneaza prima intrebare dinamica de clarificare pentru profilul extras din poze.
    Foloseste acelasi generator ca quiz-ul, dar expune doar intrebarile optionale.
    """
    session = _get_owned_photo_session(session_id, db, current_user)
    question = _first_unanswered_photo_clarify_question(session, db)
    db.commit()
    return {"question": question}


@router.post("/confirm-photo-analysis")
def confirm_photo_analysis(
    req: ConfirmPhotoAnalysisRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Confirma profilul extras din poze dupa review-ul din UI.
    Permite utilizatorului sa elimine/adauge taguri inainte ca sesiunea sa fie folosita
    pentru recomandari si itinerarii.
    """
    session = _get_owned_photo_session(req.session_id, db, current_user)

    requested_scores = {}
    for slug, raw_score in (req.tag_scores or {}).items():
        if not isinstance(slug, str) or not slug.strip():
            continue
        try:
            requested_scores[str(slug)] = float(raw_score)
        except (TypeError, ValueError):
            continue

    clarification_boosts = {
        "markets": ("food-markets", 0.72),
        "street": ("street-food", 0.72),
    }
    boost_slug, boost_score = clarification_boosts.get(req.selected_check or "", (None, None))
    clarify_weights = _clarify_weights_for_answer(session, db, req.clarification)

    requested_slugs = set(requested_scores.keys())
    if boost_slug:
        requested_slugs.add(boost_slug)
    requested_slugs.update(clarify_weights.keys())
    if not requested_slugs:
        raise HTTPException(status_code=400, detail="At least one tag is required")

    valid_slugs = {
        slug
        for (slug,) in db.query(Tag.slug).filter(Tag.slug.in_(requested_slugs)).all()
    }

    cleaned_scores = {}
    for slug, score in requested_scores.items():
        if slug not in valid_slugs:
            continue
        if not np.isfinite(score):
            continue
        cleaned_scores[slug] = round(max(0.05, min(float(score), 1.0)), 4)

    if boost_slug in valid_slugs and boost_score is not None:
        cleaned_scores[boost_slug] = max(cleaned_scores.get(boost_slug, 0), boost_score)

    for slug, weight in clarify_weights.items():
        if slug in valid_slugs:
            adjust_tag_score(cleaned_scores, slug, weight, bayesian=False)

    cleaned_scores = {
        slug: round(max(0.05, min(float(score), 1.0)), 4)
        for slug, score in cleaned_scores.items()
        if np.isfinite(score) and score > 0
    }

    if not cleaned_scores:
        raise HTTPException(status_code=400, detail="No valid tags were provided")

    session.tag_scores = cleaned_scores
    session.final_profile = cleaned_scores
    session.current_stage = "completed"
    session.completed_at = datetime.now(timezone.utc)
    db.commit()

    return {
        "session_id": str(session.id),
        "final_profile": cleaned_scores,
    }
