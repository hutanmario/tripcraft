"""
fetch_unsplash_quiz_images.py
Descarcă 80 imagini de pe Unsplash (4 per categorie × 20 categorii mid-level)
pentru quiz-ul v3 swipe-based și le salvează în DB + disc.

UTILIZARE:
    cd backend/
    python -m data.fetch_unsplash_quiz_images

PREREQUISITE:
    - UNSPLASH_ACCESS_KEY setat în .env (https://unsplash.com/developers)
    - PostgreSQL pornit, tabelul quiz_images creat (prin uvicorn sau create_all)
    - Folder static/quiz-images-v3/ va fi creat automat

RATE LIMITING:
    Unsplash free tier permite 50 requests/oră.
    Scriptul face time.sleep(75) între fiecare request individual → ~48 req/oră.
    De ce 75 și nu 72 (= 3600/50)?  Marja de 3 secunde absorbe variații de latență
    ale rețelei și asigură că nu depășim niciodată limita, chiar dacă ceasul
    sistemului are drift mic. Un ban de la Unsplash necesită re-aplicare pentru cheie.

IDEMPOTENȚĂ:
    Verifică în DB dacă există deja o imagine cu (source_category, query) înainte
    de fiecare download. Dacă da, sare peste. Permite re-rularea în caz de întrerupere.

ATRIBUIRE:
    Unsplash API Terms of Service (https://unsplash.com/api-terms) obligă la afișarea
    numelui fotografului și link-ului spre profilul său ori de câte ori imaginea
    apare în aplicație. Metadatele sunt salvate în DB.
"""

import sys
import os
import time
import logging
from pathlib import Path
from datetime import datetime, timezone

import requests
from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session
from urllib.parse import urlparse

# ---------------------------------------------------------------------------
# Setup path — permite import din app/ când scriptul rulează din backend/
# ---------------------------------------------------------------------------
BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))

load_dotenv(BACKEND_DIR / ".env")

from app.database import Base
from app.models.quiz_image import QuizImage

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Configurație
# ---------------------------------------------------------------------------
UNSPLASH_API_BASE = "https://api.unsplash.com"
STATIC_DIR = BACKEND_DIR / "static" / "quiz-images-v3"

# De ce sleep 75? → 50 req/oră = 72 sec/req minim; 75 adaugă marja de siguranță
# pentru variații de latență și drift de ceas. Estimat: 80 imagini × 75 sec = ~100 min.
SLEEP_BETWEEN_REQUESTS = 75  # secunde

# ---------------------------------------------------------------------------
# CATEGORY_QUERIES
# 20 categorii mid-level × 4 query-uri diverse = 80 imagini
#
# Principii de selecție a query-urilor:
# - Fiecare query surprinde un ASPECT DIFERIT al categoriei (nu variații ale aceluiași)
# - Query-urile sunt descriptive, nu nominaliste — "mountain village" > "mountain"
# - Preferăm query-uri specifice geografic când are sens (europe, mediterranean)
#   pentru că datele noastre sunt preponderent europene
# - Evităm query-uri prea generice ("nature") care ar produce imagini ambigue
# ---------------------------------------------------------------------------
CATEGORY_QUERIES: dict[str, list[str]] = {
    # ── City ────────────────────────────────────────────────────────────────
    "nightlife": [
        "city nightlife neon lights",
        "rooftop bar city view",
        "jazz club live music",
        "crowded street night festival",
    ],
    "culture and history": [
        "medieval castle europe",
        "ancient roman ruins",
        "cathedral gothic architecture",
        "historical museum interior",
    ],
    "gastronomy": [
        "traditional market food stalls",
        "fine dining restaurant plating",
        "wine vineyard harvest",
        "street food asia market",
    ],
    "shopping and modern": [
        "modern shopping district city",
        "design concept store interior",
        "contemporary urban architecture",
        "fashion week street style",
    ],
    "local experience": [
        "local village market europe",
        "traditional craft artisan workshop",
        "fishing village morning harbor",
        "community festival celebration",
    ],
    # ── Nature ──────────────────────────────────────────────────────────────
    "beach": [
        "mediterranean beach crystal water",
        "tropical island paradise aerial",
        "dramatic coastal cliffs ocean",
        "beach sunset golden hour",
    ],
    "mountain": [
        "alpine mountain peaks snow",
        "hiking trail mountain meadow",
        "mountain village autumn europe",
        "dramatic rocky mountain ridge",
    ],
    "forest and wildlife": [
        "dense forest misty morning",
        "wildlife safari animals nature",
        "national park waterfall trail",
        "autumn foliage forest path",
    ],
    "water activities": [
        "scuba diving coral reef",
        "surfing ocean wave",
        "kayaking river canyon",
        "sailing boat open sea",
    ],
    # ── Traveler Style ──────────────────────────────────────────────────────
    "romantic": [
        "romantic couple sunset beach",
        "candlelit dinner terrace view",
        "cobblestone street paris evening",
        "thermal spa couples retreat",
    ],
    "family-friendly": [
        "family vacation beach children",
        "amusement park family fun",
        "children museum interactive exhibit",
        "family hiking trail nature",
    ],
    "adventure": [
        "rock climbing mountain cliff",
        "mountain biking trail speed",
        "paragliding aerial view landscape",
        "white water rafting river",
    ],
    "offbeat": [
        "hidden gem abandoned village",
        "unusual landscape geology surreal",
        "treehouse unique accommodation forest",
        "remote destination road trip",
    ],
    "luxury style": [
        "luxury resort infinity pool",
        "five star hotel suite view",
        "private yacht mediterranean",
        "luxury spa treatment room",
    ],
    # ── Season ──────────────────────────────────────────────────────────────
    "spring": [
        "cherry blossom spring flowers",
        "tulip field netherlands spring",
        "mountain meadow wildflowers bloom",
        "spring rain cobblestone city",
    ],
    "summer": [
        "summer beach vacation sunny",
        "outdoor terrace summer dining",
        "festival summer crowd music",
        "road trip summer convertible",
    ],
    "autumn": [
        "autumn foliage forest golden",
        "vineyard harvest season grapes",
        "pumpkin market autumn fair",
        "misty autumn mountain village",
    ],
    "winter": [
        "ski resort fresh powder snow",
        "christmas market snowy village",
        "frozen lake winter landscape",
        "northern lights aurora night",
    ],
    # ── Budget ──────────────────────────────────────────────────────────────
    "budget-friendly": [
        "backpacker hostel travel",
        "street food budget travel",
        "camping tent nature budget",
        "local bus travel adventure",
    ],
    "mid-range": [
        "comfortable boutique hotel room",
        "mid-range restaurant dining",
        "city tour bus sightseeing",
        "cozy apartment rental travel",
    ],
}


def slug_from_category(category: str) -> str:
    """Convertește numele categoriei în slug pentru path-uri de fișiere.
    Ex: 'culture and history' → 'culture-and-history'
    """
    return category.strip().lower().replace(" ", "-")


def download_image(url: str, dest_path: Path) -> bool:
    """Descarcă o imagine de la URL și o salvează pe disc.
    Returnează True dacă a reușit, False dacă a eșuat.
    """
    try:
        resp = requests.get(url, timeout=30, stream=True)
        resp.raise_for_status()
        dest_path.parent.mkdir(parents=True, exist_ok=True)
        with open(dest_path, "wb") as f:
            for chunk in resp.iter_content(chunk_size=8192):
                f.write(chunk)
        return True
    except Exception as e:
        log.error(f"  Eroare download imagine: {e}")
        return False


def search_unsplash(query: str, access_key: str) -> dict | None:
    """Caută o imagine pe Unsplash și returnează primul rezultat.
    Returnează None dacă nu există rezultate sau dacă apare o eroare.
    """
    params = {
        "query": query,
        "per_page": 1,
        "orientation": "landscape",
        "content_filter": "high",   # filtrează conținut explicit
    }
    headers = {"Authorization": f"Client-ID {access_key}"}

    try:
        resp = requests.get(
            f"{UNSPLASH_API_BASE}/search/photos",
            params=params,
            headers=headers,
            timeout=15,
        )

        if resp.status_code == 403:
            log.warning("  Rate limit atins (403). Aștept 1 oră...")
            time.sleep(3600)
            # Retry o singură dată
            resp = requests.get(
                f"{UNSPLASH_API_BASE}/search/photos",
                params=params,
                headers=headers,
                timeout=15,
            )

        resp.raise_for_status()
        data = resp.json()

        results = data.get("results", [])
        if not results:
            log.warning(f"  Niciun rezultat pentru query: '{query}'")
            return None

        return results[0]

    except requests.RequestException as e:
        log.error(f"  Eroare request Unsplash: {e}")
        return None


def already_downloaded(session: Session, category: str, query: str) -> bool:
    """Verifică dacă există deja o imagine pentru această (category, query) în DB.
    Folosim câmpul description ca proxy pentru query — nu e perfect dar e suficient
    pentru idempotență (query-urile noastre sunt unice per categorie).
    """
    existing = session.query(QuizImage).filter(
        QuizImage.source_category == category,
        QuizImage.description == f"query:{query}",
    ).first()
    return existing is not None


def main():
    access_key = os.getenv("UNSPLASH_ACCESS_KEY")
    if not access_key:
        log.error("UNSPLASH_ACCESS_KEY nu e setat în .env. Opresc.")
        sys.exit(1)

    db_url = os.getenv("DATABASE_URL")
    if not db_url:
        log.error("DATABASE_URL nu e setat în .env. Opresc.")
        sys.exit(1)

    # Numără totalul de descărcări planificate
    total_planned = sum(len(queries) for queries in CATEGORY_QUERIES.values())
    estimated_minutes = (total_planned * SLEEP_BETWEEN_REQUESTS) // 60

    print(f"\n{'=' * 60}")
    print(f"  TripCraft — Quiz Image Fetcher v3")
    print(f"{'=' * 60}")
    print(f"  Categorii:         {len(CATEGORY_QUERIES)}")
    print(f"  Imagini planificate: {total_planned}")
    print(f"  Sleep între req:   {SLEEP_BETWEEN_REQUESTS}s")
    print(f"  Timp estimat:      ~{estimated_minutes} minute")
    print(f"  Output folder:     {STATIC_DIR}")
    print(f"{'=' * 60}\n")

    confirm = input("Continui? (y/n): ").strip().lower()
    if confirm != "y":
        print("Anulat.")
        sys.exit(0)

    engine = create_engine(db_url)
    session = Session(engine)

    start_time = time.time()
    downloaded_count = 0
    skipped_count = 0
    failed_count = 0
    failed_details = []

    request_number = 0
    total_requests = total_planned

    for category, queries in CATEGORY_QUERIES.items():
        cat_slug = slug_from_category(category)
        cat_dir = STATIC_DIR / cat_slug
        cat_dir.mkdir(parents=True, exist_ok=True)

        log.info(f"\n── Categorie: {category} ──")

        for idx, query in enumerate(queries, start=1):
            request_number += 1
            image_index = idx
            file_name = f"{cat_slug}_{image_index}.jpg"
            file_path_abs = cat_dir / file_name
            # Path relativ față de static/ — asta stocăm în DB
            file_path_rel = f"quiz-images-v3/{cat_slug}/{file_name}"

            log.info(f"[{request_number}/{total_requests}] {file_name} ← '{query}'")

            # IDEMPOTENȚĂ: skip dacă e deja în DB
            if already_downloaded(session, category, query):
                log.info(f"  → Skip (deja în DB)")
                skipped_count += 1
                continue

            # Apelează Unsplash
            result = search_unsplash(query, access_key)
            if result is None:
                failed_count += 1
                failed_details.append((category, query, "niciun rezultat Unsplash"))
                # Sleep chiar și la eșec — am consumat totuși un request
                if request_number < total_requests:
                    log.info(f"  → Sleep {SLEEP_BETWEEN_REQUESTS}s (rate limit)...")
                    time.sleep(SLEEP_BETWEEN_REQUESTS)
                continue

            # Extrage metadatele
            image_url = result["urls"]["regular"]   # 1080px, potrivit pentru web
            source_url = result["links"]["html"]
            photographer = result["user"]["name"]
            photographer_url = result["user"]["links"]["html"]
            width = result["width"]
            height = result["height"]
            # Folosim câmpul description ca fingerprint de idempotență
            description = f"query:{query}"

            # Descarcă imaginea pe disc
            ok = download_image(image_url, file_path_abs)
            if not ok:
                failed_count += 1
                failed_details.append((category, query, "eroare download"))
                if request_number < total_requests:
                    log.info(f"  → Sleep {SLEEP_BETWEEN_REQUESTS}s...")
                    time.sleep(SLEEP_BETWEEN_REQUESTS)
                continue

            # Insert în DB
            quiz_image = QuizImage(
                file_path=file_path_rel,
                source_category=category,
                source_url=source_url,
                photographer=photographer,
                photographer_url=photographer_url,
                description=description,
                width=width,
                height=height,
                clip_tags=None,
                clip_processed_at=None,
                downloaded_at=datetime.now(timezone.utc),
                is_active=True,
            )
            session.add(quiz_image)
            session.commit()

            size_kb = file_path_abs.stat().st_size // 1024
            log.info(f"  → OK: {photographer} | {width}×{height} | {size_kb}KB")
            downloaded_count += 1

            # Rate limiting — nu sleepăm după ultimul request
            if request_number < total_requests:
                log.info(f"  → Sleep {SLEEP_BETWEEN_REQUESTS}s (rate limit)...")
                time.sleep(SLEEP_BETWEEN_REQUESTS)

    session.close()

    # ── Raport final ────────────────────────────────────────────────────────
    elapsed = int(time.time() - start_time)
    total_size = sum(f.stat().st_size for f in STATIC_DIR.rglob("*.jpg")) if STATIC_DIR.exists() else 0
    total_size_mb = total_size / (1024 * 1024)

    print(f"\n{'=' * 60}")
    print(f"  RAPORT FINAL")
    print(f"{'=' * 60}")
    print(f"  Descărcate cu succes: {downloaded_count}")
    print(f"  Sărite (deja existau): {skipped_count}")
    print(f"  Eșuate:               {failed_count}")
    print(f"  Durată totală:        {elapsed // 60}m {elapsed % 60}s")
    print(f"  Dimensiune folder:    {total_size_mb:.1f} MB")

    if failed_details:
        print(f"\n  Eșecuri detaliate:")
        for cat, q, reason in failed_details:
            print(f"    [{cat}] '{q}' → {reason}")

    print(f"{'=' * 60}\n")


if __name__ == "__main__":
    main()
