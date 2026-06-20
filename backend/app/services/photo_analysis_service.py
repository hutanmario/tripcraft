import logging
import time
import uuid
from datetime import datetime, timezone
from typing import Optional

from app.database import SessionLocal
from app.models.quiz_v4_session import QuizV4Session
from app.services.image_db_tagging_service import image_db_tagging_service

logger = logging.getLogger(__name__)


def run_photo_analysis(files_data: list[dict], user_id: Optional[int] = None) -> dict:
    """
    Process user photos and persist the generated quiz profile.

    This function is intentionally importable by an RQ worker. Keep it free of
    FastAPI dependencies so background execution does not need the API router.
    """
    db = SessionLocal()
    try:
        total_start = time.time()
        analysis = image_db_tagging_service.analyze_user_photos(
            db=db,
            files_data=files_data,
        )
        tag_scores = analysis["matched_db_tags"]
        if not tag_scores:
            raise RuntimeError("Could not extract relevant tags from the photos.")

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
