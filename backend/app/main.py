import logging
import threading
from contextlib import asynccontextmanager
from pathlib import Path
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from app import models
from slowapi.errors import RateLimitExceeded
from slowapi import _rate_limit_exceeded_handler
from app.config import settings
from app.limiter import limiter
from app.routers import auth, ml
from app.routers import quiz, itinerary
from app.routers.social import router as social_router
from app.routers import interactive_mode
from app.services.clip_service import clip_service

logger = logging.getLogger(__name__)

def _preload_clip():
    try:
        logger.info("Pre-loading CLIP ViT-L/14 model...")
        clip_service._load_model()
        from app.database import SessionLocal
        from app.services.image_db_tagging_service import image_db_tagging_service

        db = SessionLocal()
        try:
            image_db_tagging_service.preload(db)
        finally:
            db.close()
        logger.info("CLIP ViT-L/14 ready")
    except Exception as e:
        logger.warning(f"CLIP preload failed: {e}")


@asynccontextmanager
async def lifespan(app: FastAPI):
    threading.Thread(target=_preload_clip, daemon=True).start()
    yield

app = FastAPI(
    title="TripCraft",
    description="Sistem inteligent de planificare a călătoriilor",
    version="1.0.0",
    lifespan=lifespan,
)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS.split(","),
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
)

app.include_router(auth.router)
app.include_router(quiz.router)
app.include_router(ml.router)
app.include_router(itinerary.router)
app.include_router(social_router)
app.include_router(interactive_mode.router)

_STATIC_DIR = Path(__file__).resolve().parent.parent / "static"
app.mount("/static", StaticFiles(directory=_STATIC_DIR), name="static")

@app.get("/")
def root():
    return {"message": "TripCraft API is running"}


@app.get("/health")
def health_check():
    from app.database import SessionLocal
    from sqlalchemy import text
    from fastapi.responses import JSONResponse

    status = {"database": "ok", "clip_model": "ok"}
    healthy = True

    db = SessionLocal()
    try:
        db.execute(text("SELECT 1"))
    except Exception:
        status["database"] = "unavailable"
        healthy = False
    finally:
        db.close()

    if not clip_service.is_loaded():
        status["clip_model"] = "loading"

    status["status"] = "ok" if healthy else "degraded"
    return JSONResponse(content=status, status_code=200 if healthy else 503)
