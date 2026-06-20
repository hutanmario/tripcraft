"""
tag_quiz_images_with_clip.py
Rulează CLIP pe imaginile din quiz_images (descărcate de fetch_unsplash_quiz_images.py)
și salvează scorurile precomputed în coloana clip_tags JSONB.

UTILIZARE:
    cd backend/
    python -m data.tag_quiz_images_with_clip            # procesează doar netagate
    python -m data.tag_quiz_images_with_clip --reset    # șterge clip_tags și re-procesează tot

DESIGN:
    Scorurile CLIP sunt precomputed (offline) și stocate în DB pentru a elimina
    latența CLIP la runtime. Quiz-ul v3 folosește aceste scoruri pentru a selecta
    imaginile cele mai relevante pentru profilul unui user, fără să încarce modelul
    CLIP la fiecare request.

THRESHOLD ADAPTIV (mean + 0.5 * std):
    Scorurile sunt cosine similarity brute din CLIP (tipic 0.15-0.40 pentru perechi
    text-imagine pozitive pe CLIP-ViT-B/32). Nu se aplică softmax sau normalizare prin max.

    Threshold-ul vechi (0.20 fix pe scoruri max-normalizate) a fost eliminat deoarece
    forța tag-ul de top la 1.0 indiferent de confidența reală — bug de logică.

    Threshold-ul adaptiv se calculează per imagine: mean + 0.5 * std pe toate cele ~60
    scoruri cosine. Reține tagurile cu semnal semnificativ deasupra baseline-ului
    semantic al imaginii respective. Detalii în docstring-ul funcției select_relevant_tags.

TOP 5:
    Stocăm maxim 5 taguri per imagine. Motivele:
    - Quizul selectează imagini pe baza overlap-ului cu profilul userului;
      5 taguri sunt suficiente pentru matching precis
    - JSONB mai mic = query-uri mai rapide (GIN index pe JSONB e eficient la scale mic)
    - Peste 5 taguri, scorurile devin prea mici pentru a fi discriminative

PROCESARE:
    Imaginile sunt procesate de pe disc (nu URL). CLIP rulează local — nu e nevoie
    de internet după ce modelul e descărcat prima dată (~340MB, cached în HuggingFace).
"""

import sys
import argparse
import logging
from pathlib import Path
from datetime import datetime, timezone
from collections import defaultdict

# ---------------------------------------------------------------------------
# Path setup — permite import din app/ când rulăm din backend/
# ---------------------------------------------------------------------------
BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))

from dotenv import load_dotenv
load_dotenv(BACKEND_DIR / ".env")

from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from app.models.quiz_image import QuizImage
from app.config import settings
from app.services.clip_service import CLIPService, TAG_PROMPTS, CLIP_EXCLUDED_TAGS

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
# Numărul maxim de taguri stocate per imagine.
# Explicație în docstring-ul modulului.
TOP_K_TAGS = 5

STATIC_DIR = BACKEND_DIR / "static"


def load_image_bytes(file_path_rel: str) -> bytes | None:
    """Citește imaginea de pe disc și returnează bytes.
    file_path_rel este relativ față de directorul static/ al backend-ului.
    Ex: 'quiz-images-v3/mountain/mountain_1.jpg'
    """
    abs_path = STATIC_DIR / file_path_rel
    if not abs_path.exists():
        log.error(f"  Fișier lipsă pe disc: {abs_path}")
        return None
    try:
        return abs_path.read_bytes()
    except OSError as e:
        log.error(f"  Eroare citire fișier {abs_path}: {e}")
        return None


def build_report(all_tag_scores: list[dict]) -> None:
    """Generează și afișează raportul final după procesare.

    Args:
        all_tag_scores: lista de dict-uri {tag: score} pentru fiecare imagine procesată
    """
    if not all_tag_scores:
        print("\n  Nicio imagine procesată.")
        return

    # Distribuția scorurilor (pe toate tagurile din toate imaginile)
    all_scores = [score for tags in all_tag_scores for score in tags.values()]
    if all_scores:
        print(f"\n  Distribuție scoruri CLIP:")
        print(f"    min:   {min(all_scores):.4f}")
        print(f"    max:   {max(all_scores):.4f}")
        print(f"    medie: {sum(all_scores) / len(all_scores):.4f}")

    # Top 10 taguri după frecvență de apariție
    tag_frequency: dict[str, int] = defaultdict(int)
    for tags in all_tag_scores:
        for tag in tags:
            tag_frequency[tag] += 1

    top_tags = sorted(tag_frequency.items(), key=lambda x: x[1], reverse=True)[:10]
    print(f"\n  Top 10 taguri cele mai frecvent atribuite:")
    for tag, freq in top_tags:
        bar = "█" * freq
        print(f"    {tag:<25} {freq:3d} imagini  {bar}")

    # Taguri care nu au apărut în nicio imagine
    all_assigned_tags = set(tag_frequency.keys())
    all_known_tags = set(TAG_PROMPTS.keys())
    unassigned = sorted(all_known_tags - all_assigned_tags)
    if unassigned:
        print(f"\n  Taguri NEATRIBUITE niciunei imagini ({len(unassigned)}):")
        print(f"    {', '.join(unassigned)}")
        print(f"  → Posibil: tagurile sunt prea abstracte pentru CLIP,")
        print(f"    sau pool-ul de imagini nu le acoperă semantic.")


def select_relevant_tags(scores: dict[str, float], top_k: int = 5) -> dict[str, float]:
    """
    Selectează taguri relevante dintr-un dict de scoruri cosine brute folosind
    un threshold adaptiv bazat pe distribuția scorurilor imaginii curente.

    Adaptive threshold preserves signal strength variation between images.
    Fixed threshold + max-norm collapses all images to same score shape regardless
    of confidence — that was the original bug (every image had max=1.0).

    Algorithm:
      threshold = mean + 0.5 * std  (tags significantly above average)

    De ce mean + 0.5*std?
      - mean pe 60 taguri cosine CLIP e ~0.20 (nivelul baseline de similaritate semantică)
      - std pe aceeași imagine e ~0.04–0.10 (spread-ul semnalului)
      - threshold = mean + 0.5*std ≈ 30% peste medie → reține doar taguri cu semnal clar
      - Alternativa 1*std ar fi prea restrictivă (ar da 1-2 taguri per imagine)
      - Alternativa 0*std (= media) ar da ~30 taguri per imagine (prea multe)
      - 0.5*std echilibrează: tipic 3-6 taguri per imagine pentru CLIP-ViT-B/32

    Floor la top 1: garantăm că orice imagine are cel puțin un tag chiar dacă
    toate scorurile sunt similare (imagine ambiguă semantic).
    """
    if not scores:
        return {}

    values = list(scores.values())
    mean = sum(values) / len(values)
    variance = sum((v - mean) ** 2 for v in values) / len(values)
    std = variance ** 0.5
    threshold = mean + 0.5 * std

    sorted_tags = sorted(scores.items(), key=lambda x: -x[1])
    relevant = [(t, s) for t, s in sorted_tags if s >= threshold][:top_k]

    # Floor: întotdeauna cel puțin 1 tag
    if not relevant and sorted_tags:
        relevant = [sorted_tags[0]]

    return {tag: round(score, 4) for tag, score in relevant}


def process_images(session: Session, clip: CLIPService, reset: bool) -> None:
    """Procesează toate imaginile din DB care nu au clip_tags (sau toate dacă --reset).

    Args:
        session: SQLAlchemy session
        clip: instanța CLIPService (model lazy-loaded la primul apel)
        reset: dacă True, șterge clip_tags existente și re-procesează tot
    """
    if reset:
        log.info("--reset: șterg clip_tags pentru toate imaginile...")
        session.query(QuizImage).update({
            "clip_tags": None,
            "clip_processed_at": None,
        })
        session.commit()
        log.info("Reset complet.")

    # Selectează imaginile de procesat
    images = (
        session.query(QuizImage)
        .filter(
            QuizImage.clip_processed_at.is_(None),
            QuizImage.is_active == True,
        )
        .order_by(QuizImage.id)
        .all()
    )

    if not images:
        log.info("Nicio imagine de procesat. Toate au clip_processed_at setat.")
        return

    log.info(f"Imagini de procesat: {len(images)}")
    candidate_tags = [t for t in TAG_PROMPTS if t not in CLIP_EXCLUDED_TAGS]
    log.info(f"CLIP classification: {len(candidate_tags)} tags ({len(CLIP_EXCLUDED_TAGS)} excluded)")
    log.info(f"Excluded: {sorted(CLIP_EXCLUDED_TAGS)}")
    log.info("Se încarcă modelul CLIP (prima dată poate dura ~30s)...")

    all_tag_scores: list[dict] = []
    success_count = 0
    error_count = 0

    for i, img in enumerate(images, start=1):
        filename = Path(img.file_path).name

        # Citește imaginea de pe disc
        image_bytes = load_image_bytes(img.file_path)
        if image_bytes is None:
            error_count += 1
            continue

        # Rulează CLIP — returnează scoruri cosine brute pentru TOATE tagurile
        try:
            raw_tags = clip.tag_image_from_bytes(image_bytes, top_k=len(TAG_PROMPTS))
        except Exception as e:
            log.error(f"  Eroare CLIP: {e}")
            error_count += 1
            continue

        # Guard: tag_image_from_bytes returnează {} dacă CLIP a eșuat intern
        if not raw_tags:
            log.warning(f"  CLIP a returnat dict gol pentru {filename} — skip")
            error_count += 1
            continue

        # Calculează statistici pentru logging și threshold adaptiv
        all_values = list(raw_tags.values())
        mean_s = sum(all_values) / len(all_values)
        variance_s = sum((v - mean_s) ** 2 for v in all_values) / len(all_values)
        std_s = variance_s ** 0.5
        threshold_s = mean_s + 0.5 * std_s

        sorted_all = sorted(raw_tags.items(), key=lambda x: -x[1])
        top5_str = ", ".join(f"{t}={s:.4f}" for t, s in sorted_all[:5])

        # Aplică threshold adaptiv
        top_tags = select_relevant_tags(raw_tags, top_k=TOP_K_TAGS)

        log.info(f"[{i}/{len(images)}] {filename}")
        log.info(f"  Raw top: {top5_str}")
        log.info(f"  Threshold: {threshold_s:.4f} (mean={mean_s:.4f}, std={std_s:.4f})")
        log.info(f"  Saved: {top_tags}")

        # Update în DB
        img.clip_tags = top_tags if top_tags else {}
        img.clip_processed_at = datetime.now(timezone.utc)
        session.add(img)
        session.commit()

        all_tag_scores.append(top_tags)
        success_count += 1

    # ── Raport final ────────────────────────────────────────────────────────
    print(f"\n{'=' * 60}")
    print(f"  RAPORT CLIP TAGGING")
    print(f"{'=' * 60}")
    print(f"  Procesate cu succes: {success_count}")
    print(f"  Erori:               {error_count}")

    build_report(all_tag_scores)
    print(f"{'=' * 60}\n")


def main():
    parser = argparse.ArgumentParser(
        description="Rulează CLIP precomputed pe imaginile din quiz_images."
    )
    parser.add_argument(
        "--reset",
        action="store_true",
        help="Șterge clip_tags existente și re-procesează toate imaginile.",
    )
    args = parser.parse_args()

    db_url = settings.DATABASE_URL
    if not db_url:
        log.error("DATABASE_URL nu e setat în .env. Opresc.")
        sys.exit(1)

    engine = create_engine(db_url)
    session = Session(engine)

    # Instanțiază CLIPService (singleton — modelul e încărcat lazy la primul apel)
    clip = CLIPService.get_instance()

    try:
        process_images(session, clip, reset=args.reset)
    finally:
        session.close()


if __name__ == "__main__":
    main()
