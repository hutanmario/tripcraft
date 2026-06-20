#!/usr/bin/env python3
"""
evaluation/scenarii_6_4.py
===========================
Generează date REALE pentru secțiunea 6.4 din lucrarea de licență
(Scenarii de utilizare) – 5 profiluri de utilizator distincte.

Rulare (din directorul backend/):
    python -m evaluation.scenarii_6_4

Constrângeri:
  - Doar date reale din DB și funcții de producție (fără valori inventate)
  - Refolosește compute_country_scores() și build_itinerary() din producție
  - Tag beliefs construite identic cu logica din app/routers/quiz.py
  - Sesiunile temporare sunt inserate și șterse din DB
"""

import sys, os, uuid, json, math, textwrap
from types import SimpleNamespace

# Forțează UTF-8 pe Windows pentru a evita erori cu caractere românești
if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8")
if sys.stderr.encoding and sys.stderr.encoding.lower() != "utf-8":
    sys.stderr.reconfigure(encoding="utf-8")

# ── Path setup ─────────────────────────────────────────────────────────────────
_BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _BACKEND_DIR not in sys.path:
    sys.path.insert(0, _BACKEND_DIR)

import logging
logging.basicConfig(level=logging.WARNING)

# ── Încarcă .env din backend/ (necesar înainte de orice import app.*) ─────────
_env_path = os.path.join(_BACKEND_DIR, ".env")
if os.path.exists(_env_path):
    with open(_env_path, encoding="utf-8") as _f:
        for _line in _f:
            _line = _line.strip()
            if _line and not _line.startswith("#") and "=" in _line:
                _k, _, _v = _line.partition("=")
                os.environ.setdefault(_k.strip(), _v.strip())

from sqlalchemy import select

from app.database import SessionLocal
from app.models import Tag, QuizV4Session
from app.models.geography import Country, City, Attraction, country_tags as ct_table
from app.services.country_recommender import (
    compute_country_scores,
    clear_country_scoring_cache,
    get_country_scoring_context,
)
from app.services.itinerary_builder import build_itinerary
from app.services.quiz_engine import compute_entropy, L1_ORDER

RESULTS_DIR = os.path.join(os.path.dirname(__file__), "results")
os.makedirs(RESULTS_DIR, exist_ok=True)

# ─────────────────────────────────────────────────────────────────────────────
# CONSTANTE – identice cu app/routers/quiz.py
# ─────────────────────────────────────────────────────────────────────────────
RIGHT_ALPHA = 1.0   # quiz.py linia 344
LEFT_BETA   = 0.5   # quiz.py linia 346

# ─────────────────────────────────────────────────────────────────────────────
# DEFINIȚII ARHETIPURI
# Tag-urile sunt sluguri REALE din taxonomia DB (fișier tags_leaf.txt, 166 sluguri).
# Fiecare arhetip specifică:
#   - l1_likes: L1-urile la care userul face like (din L1_ORDER)
#   - target_tags: leaf tags la care userul face like
#   - neutral_tags: leaf tags la care userul face dislike (din categorii nedorite)
#   - budget / season / travel_style / pace
# ─────────────────────────────────────────────────────────────────────────────

ARCHETYPES = [
    {
        "name": "Aventurier și viață de noapte",
        "description": "Tânăr solist pasionat de adrenalină și ieșiri nocturne",
        "l1_likes": {"adventure-active", "nightlife-social", "nature-outdoors"},
        "target_tags": [
            "hiking",
            "rock-climbing",
            "via-ferrata",
            "white-water-rafting",
            "paragliding",
            "techno-clubs",
            "pub-crawls",
            "underground-clubs",
            "rooftop-parties",
            "zip-lining",
        ],
        "neutral_tags_dislike": [
            "michelin-restaurants",
            "yoga-retreats",
            "silence-retreats",
            "opera-classical",
            "luxury-spa",
            "kids-workshops",
            "petting-zoos",
            "float-tanks",
        ],
        "budget": "mid",
        "season": "summer",
        "travel_style": "solo",
        "pace": "packed",
    },
    {
        "name": "Istorie și gastronomie",
        "description": "Cuplu interesat de patrimoniu cultural și experiențe culinare",
        "l1_likes": {"culture-history", "food-drink"},
        "target_tags": [
            "ancient-ruins",
            "history-museums",
            "castles-palaces",
            "roman-history",
            "gothic-architecture",
            "wine-vineyards",
            "michelin-restaurants",
            "cooking-classes",
            "food-tours-guided",
            "farmers-markets",
        ],
        "neutral_tags_dislike": [
            "techno-clubs",
            "skydiving",
            "bungee-jumping",
            "theme-parks",
            "pub-crawls",
            "zip-lining",
            "rooftop-parties",
            "underground-clubs",
        ],
        "budget": "mid",
        "season": "autumn",
        "travel_style": "couple",
        "pace": "balanced",
    },
    {
        "name": "Natură și relaxare",
        "description": "Persoană care caută liniște în natură și wellness profund",
        "l1_likes": {"nature-outdoors", "wellness-slow"},
        "target_tags": [
            "national-parks",
            "forest-bathing",
            "lake-swimming",
            "stargazing",
            "birdwatching",
            "yoga-retreats",
            "digital-detox",
            "silence-retreats",
            "thermal-baths",
            "countryside-walks",
        ],
        "neutral_tags_dislike": [
            "techno-clubs",
            "pub-crawls",
            "luxury-shopping",
            "rooftop-parties",
            "skydiving",
            "esports-arenas",
            "casinos",
            "fashion-weeks",
        ],
        "budget": "budget",
        "season": "spring",
        "travel_style": "couple",
        "pace": "relaxed",
    },
    {
        "name": "Familie și confort",
        "description": "Familie cu copii care prioritizează siguranța și activitățile distractive",
        "l1_likes": {"family-comfort", "urban-modern"},
        "target_tags": [
            "theme-parks",
            "petting-zoos",
            "zoos-aquariums",
            "playgrounds-parks",
            "science-interactive-museums",
            "kids-workshops",
            "accessible-attractions",
            "child-beaches",
            "glamping-family",
            "hop-on-hop-off",
        ],
        "neutral_tags_dislike": [
            "techno-clubs",
            "underground-clubs",
            "skydiving",
            "bungee-jumping",
            "base-jumping",
            "pub-crawls",
            "rooftop-parties",
            "speakeasy-bars",
        ],
        "budget": "mid",
        "season": "summer",
        "travel_style": "family",
        "pace": "relaxed",
    },
    {
        "name": "Urban, modern și social",
        "description": "Millennial urban conectat, pasionat de design, cafenele și events",
        "l1_likes": {"urban-modern", "nightlife-social", "food-drink"},
        "target_tags": [
            "contemporary-architecture",
            "designer-districts",
            "specialty-coffee",
            "rooftop-bars",
            "meetup-events",
            "pop-up-events",
            "street-art",
            "craft-beer",
            "instagram-spots",
            "tech-hubs",
        ],
        "neutral_tags_dislike": [
            "silence-retreats",
            "digital-detox",
            "multi-day-trekking",
            "yoga-retreats",
            "float-tanks",
            "foraging",
            "birdwatching",
            "wildlife-watching",
        ],
        "budget": "mid",
        "season": "any",
        "travel_style": "group",
        "pace": "balanced",
    },
]

# ─────────────────────────────────────────────────────────────────────────────
# SIMULARE QUIZ BAYESIAN
# Reproduce EXACT logica din app/routers/quiz.py (liniile 340-349)
# ─────────────────────────────────────────────────────────────────────────────

def _swipe(beliefs: dict, tag_slug: str, direction: str) -> float:
    """Aplică un swipe Bayesian și returnează scorul actualizat."""
    if tag_slug not in beliefs:
        beliefs[tag_slug] = {"alpha": 1.0, "beta": 1.0}
    if direction == "right":
        beliefs[tag_slug]["alpha"] += RIGHT_ALPHA
    else:
        beliefs[tag_slug]["beta"] += LEFT_BETA
    b = beliefs[tag_slug]
    return round(b["alpha"] / (b["alpha"] + b["beta"]), 4)


def simulate_quiz(archetype: dict) -> tuple[dict, dict, int, float]:
    """
    Simulează un parcurs complet prin chestionar pentru un arhetip.

    Phase 1: 8 carduri L1 (câte un swipe per macro-categorie)
    Phase 2: leaf tags (target → right, neutral_dislike → left)

    Returnează: (tag_scores, tag_beliefs, card_count, entropy_final)
    """
    beliefs = {}
    tag_scores = {}

    # Phase 1 – 8 carduri L1 obligatorii
    for l1_slug in L1_ORDER:
        direction = "right" if l1_slug in archetype["l1_likes"] else "left"
        tag_scores[l1_slug] = _swipe(beliefs, l1_slug, direction)

    # Phase 2 – leaf tags target (like)
    for slug in archetype["target_tags"]:
        tag_scores[slug] = _swipe(beliefs, slug, "right")

    # Phase 2 – leaf tags neutral (dislike) – completăm până la MIN_CARDS
    cards_l3 = len(archetype["target_tags"])
    for slug in archetype["neutral_tags_dislike"]:
        tag_scores[slug] = _swipe(beliefs, slug, "left")
        cards_l3 += 1

    card_count = len(L1_ORDER) + cards_l3
    entropy = compute_entropy(tag_scores)
    return tag_scores, beliefs, card_count, entropy


# ─────────────────────────────────────────────────────────────────────────────
# INSERARE / ȘTERGERE SESIUNE TEMPORARĂ DIN DB
# ─────────────────────────────────────────────────────────────────────────────

def insert_session(db, archetype: dict, tag_scores: dict, tag_beliefs: dict) -> str:
    """Inserează o sesiune QuizV4Session temporară în DB și returnează UUID-ul."""
    session_id = uuid.uuid4()
    session = QuizV4Session(
        id=session_id,
        user_id=None,
        tag_beliefs=tag_beliefs,
        tag_scores=tag_scores,
        final_profile=tag_scores,
        budget=archetype["budget"],
        season=archetype["season"] if archetype["season"] != "any" else None,
        travel_style=archetype["travel_style"],
        pace_preference=archetype["pace"],
        card_count=archetype.get("_card_count", 18),
        current_stage="done",
    )
    db.add(session)
    db.commit()
    db.refresh(session)
    return str(session_id)


def delete_session(db, session_id: str):
    """Șterge sesiunea temporară din DB."""
    try:
        sid = uuid.UUID(session_id)
        s = db.query(QuizV4Session).filter(QuizV4Session.id == sid).first()
        if s:
            db.delete(s)
            db.commit()
    except Exception:
        pass


# ─────────────────────────────────────────────────────────────────────────────
# MOCK SESSION pentru compute_country_scores (nu necesită DB)
# ─────────────────────────────────────────────────────────────────────────────

def make_mock_session(archetype: dict, tag_scores: dict) -> SimpleNamespace:
    return SimpleNamespace(
        final_profile=tag_scores,
        tag_scores=tag_scores,
        budget=archetype["budget"],
        season=archetype["season"] if archetype["season"] != "any" else None,
        travel_style=archetype["travel_style"],
        pace_preference=archetype["pace"],
    )


# ─────────────────────────────────────────────────────────────────────────────
# TAGURI RELEVANTE ALE ȚĂRII RECOMANDATE
# ─────────────────────────────────────────────────────────────────────────────

def compute_relevant_tags(top_country: dict, tag_scores: dict, n: int = 6) -> list[dict]:
    """
    Intersecție dintre top taguri ale profilului și tagurile țării alese,
    sortate după contribuție (user_score × country_score).
    """
    country_scores_by_slug = {}
    for reason in top_country.get("matching_reasons", []):
        country_scores_by_slug[reason["tag_slug"]] = reason["country_score"]

    # Completăm cu matching_tags din rezultatul recomandatorului
    contributions = top_country.get("matching_reasons", [])

    results = []
    for item in contributions:
        slug = item["tag_slug"]
        user_score = float(tag_scores.get(slug, 0.0))
        country_score = item["country_score"]
        results.append({
            "tag": slug,
            "tag_name": item["tag_name"],
            "user_score": round(user_score, 4),
            "country_score": round(country_score, 4),
            "idf": item.get("idf", 1.0),
            "contribution": item["contribution"],
        })

    results.sort(key=lambda x: x["contribution"], reverse=True)
    return results[:n]


# ─────────────────────────────────────────────────────────────────────────────
# TOP TAGURI ALE PROFILULUI UTILIZATORULUI
# ─────────────────────────────────────────────────────────────────────────────

def top_profile_tags(tag_scores: dict, leaf_slugs: set, n: int = 8) -> list[dict]:
    """Returnează top N leaf tags cu scoruri > 0.5 (deasupra neutrului Bayesian)."""
    leaf_scores = {
        slug: score
        for slug, score in tag_scores.items()
        if slug in leaf_slugs and score > 0.5
    }
    sorted_tags = sorted(leaf_scores.items(), key=lambda x: x[1], reverse=True)
    return [{"tag": slug, "score": round(score, 4)} for slug, score in sorted_tags[:n]]


# ─────────────────────────────────────────────────────────────────────────────
# PONDERI MACRO L1 DIN PROFIL
# ─────────────────────────────────────────────────────────────────────────────

def macro_weights(tag_scores: dict) -> dict:
    """Returnează ponderea fiecărei categorii L1 în profilul utilizatorului."""
    total = sum(
        score for slug, score in tag_scores.items()
        if slug in L1_ORDER and score > 0
    )
    if total == 0:
        return {slug: 0.0 for slug in L1_ORDER}
    return {
        slug: round(tag_scores.get(slug, 0.0) / total, 4)
        for slug in L1_ORDER
    }


# ─────────────────────────────────────────────────────────────────────────────
# PIPELINE PRINCIPAL
# ─────────────────────────────────────────────────────────────────────────────

def run_archetype(archetype: dict, db, leaf_slugs: set) -> dict:
    """Rulează pipeline-ul complet pentru un arhetip și returnează rezultatele."""
    name = archetype["name"]
    print(f"\n{'='*60}")
    print(f"  {name}")
    print(f"{'='*60}")

    # 1. Simulare quiz
    tag_scores, tag_beliefs, card_count, entropy = simulate_quiz(archetype)
    archetype["_card_count"] = card_count
    print(f"  Quiz: {card_count} carduri, entropie finală = {entropy:.4f}")

    # 2. Inserare sesiune temporară în DB
    session_id = insert_session(db, archetype, tag_scores, tag_beliefs)
    print(f"  Sesiune inserată: {session_id}")

    # 3. Mock session pentru recomandator
    mock_session = make_mock_session(archetype, tag_scores)

    # 4. Recomandare țări (producție) – top 5 cu MMR diversity
    top_countries = compute_country_scores(mock_session, db, diversity=True, top_n=5)
    if not top_countries:
        print("  EROARE: nicio țară recomandată!")
        delete_session(db, session_id)
        return {}

    top_country = top_countries[0]
    country_name = top_country["country_name"]
    country_id   = top_country["country_id"]
    country_score = top_country["score"]
    print(f"  Țara recomandată: {country_name} (scor={country_score:.4f})")
    for c in top_countries[1:4]:
        print(f"    #{top_countries.index(c)+1} {c['country_name']} (scor={c['score']:.4f})")

    # 5. Itinerariu real (2 zile, buget din arhetip)
    try:
        days = build_itinerary(
            country_id=country_id,
            nr_zile=2,
            session_id=session_id,
            budget_level=archetype["budget"],
            db=db,
        )
    except Exception as e:
        print(f"  AVERTISMENT itinerariu: {e}")
        days = []

    # 6. Taguri relevante ale țării
    relevant = compute_relevant_tags(top_country, tag_scores)

    # 7. Top taguri profil
    prof_tags = top_profile_tags(tag_scores, leaf_slugs)

    # 8. Ponderi macro L1
    macro = macro_weights(tag_scores)

    # 9. Categorie dominantă
    dom_cat = max(
        {slug: tag_scores.get(slug, 0.0) for slug in L1_ORDER}.items(),
        key=lambda x: x[1]
    )[0]

    # Orase din itinerariu
    cities_seen = []
    for day in days:
        city_name = day.get("city_name", "")
        if city_name and city_name not in cities_seen:
            cities_seen.append(city_name)

    # Atractii
    attractions_all = []
    for day in days:
        for attr in day.get("attractions", []):
            attractions_all.append({
                "zi": day["day"],
                "oras": day.get("city_name", ""),
                "name": attr.get("name", ""),
                "duration_h": attr.get("duration_hours", 0),
                "score": round(float(attr.get("score", 0)), 4),
            })

    # Ștergere sesiune temporară
    delete_session(db, session_id)
    print(f"  Sesiune ștearsă.")

    return {
        "name": name,
        "description": archetype["description"],
        "budget": archetype["budget"],
        "season": archetype["season"],
        "travel_style": archetype["travel_style"],
        "pace": archetype["pace"],
        "card_count": card_count,
        "entropy_final": round(entropy, 4),
        "profile_top_tags": prof_tags,
        "macro_weights": macro,
        "dominant_category": dom_cat,
        "top_countries": [
            {"tara": c["country_name"], "scor": c["score"]} for c in top_countries[:4]
        ],
        "country": country_name,
        "country_score": country_score,
        "country_capital": top_country.get("capital", ""),
        "relevant_tags": relevant,
        "cities": cities_seen,
        "itinerariu": days,
        "attractions_flat": attractions_all,
    }


# ─────────────────────────────────────────────────────────────────────────────
# GENERARE FIȘIERE OUTPUT
# ─────────────────────────────────────────────────────────────────────────────

def write_md(results: list[dict]):
    lines = [
        "# Scenarii de utilizare – Secțiunea 6.4",
        "",
        "Toate datele provin din rularea efectivă a sistemului TripCraft pe baza de date reală.",
        "Scorurile de potrivire reprezintă similaritatea cosinus IDF-ponderată calculată de `compute_country_scores()` (v4.3).",
        "",
        "---",
        "",
    ]

    for idx, r in enumerate(results, 1):
        if not r:
            continue
        lines.append(f"## {idx}. {r['name']}")
        lines.append(f"**Tip utilizator:** {r['description']}")
        lines.append(f"**Budget:** {r['budget']} | **Sezon:** {r['season']} | **Stil:** {r['travel_style']} | **Ritm:** {r['pace']}")
        lines.append("")

        lines.append("### Profil de taguri (top taguri, scor > 0.5)")
        lines.append("| Tag | Scor Bayesian |")
        lines.append("|-----|---------------|")
        for t in r["profile_top_tags"]:
            lines.append(f"| `{t['tag']}` | {t['score']:.4f} |")
        lines.append("")

        lines.append(f"**Carduri chestionar:** {r['card_count']}  |  **Entropie finală:** {r['entropy_final']:.4f}")
        lines.append("")

        lines.append("### Clasificare țări")
        lines.append("| Rang | Țara | Scor potrivire |")
        lines.append("|------|------|----------------|")
        for i, c in enumerate(r["top_countries"], 1):
            lines.append(f"| {i} | {c['tara']} | {c['scor']:.4f} |")
        lines.append("")

        lines.append(f"### Țara recomandată: **{r['country']}** (scor = {r['country_score']:.4f})")
        lines.append("")

        if r["relevant_tags"]:
            lines.append("### Taguri relevante ale țării (explică potrivirea)")
            lines.append("| Tag | Scor user | Scor țară | IDF | Contribuție |")
            lines.append("|-----|-----------|-----------|-----|-------------|")
            for t in r["relevant_tags"]:
                lines.append(
                    f"| `{t['tag']}` | {t['user_score']:.4f} | {t['country_score']:.4f} "
                    f"| {t['idf']:.4f} | {t['contribution']:.4f} |"
                )
            lines.append("")

        lines.append(f"**Orașe vizitate:** {', '.join(r['cities']) if r['cities'] else '(itinerariu indisponibil)'}")
        lines.append("")

        if r["attractions_flat"]:
            lines.append("### Atracții reprezentative pe zile")
            current_day = None
            for a in r["attractions_flat"]:
                if a["zi"] != current_day:
                    current_day = a["zi"]
                    lines.append(f"**Ziua {current_day} – {a['oras']}**")
                lines.append(f"- {a['name']} ({a['duration_h']:.1f}h, scor={a['score']:.4f})")
            lines.append("")

        lines.append("---")
        lines.append("")

    out = os.path.join(RESULTS_DIR, "scenarii_utilizatori.md")
    with open(out, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    print(f"\n[MD]  Salvat: {out}")
    return out


def write_json(results: list[dict]):
    heatmap_countries = sorted(
        {c["tara"] for r in results if r for c in r.get("top_countries", [])[:4]}
    )
    heatmap = {}
    for r in results:
        if not r:
            continue
        row = {}
        for c_entry in r.get("top_countries", []):
            row[c_entry["tara"]] = c_entry["scor"]
        heatmap[r["name"]] = row

    payload = {
        "profiluri": [
            {
                "profil": r["name"],
                "profil_top_taguri": r["profile_top_tags"],
                "ponderi_macro_L1": r["macro_weights"],
                "tara": r["country"],
                "scor_tara": r["country_score"],
                "top_tari": r["top_countries"],
                "categorie_dominanta": r["dominant_category"],
                "carduri_chestionar": r["card_count"],
                "entropie_finala": r["entropy_final"],
                "taguri_relevante_tara": r["relevant_tags"],
                "orase": r["cities"],
            }
            for r in results if r
        ],
        "heatmap_profiluri_tari": {
            "profile_names": [r["name"] for r in results if r],
            "country_names": heatmap_countries,
            "matrix": [
                [heatmap.get(r["name"], {}).get(c, 0.0) for c in heatmap_countries]
                for r in results if r
            ],
        },
    }

    out = os.path.join(RESULTS_DIR, "scenarii_figura.json")
    with open(out, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    print(f"[JSON] Salvat: {out}")
    return out


def print_table_65(results: list[dict]):
    print("\n" + "="*80)
    print("TABELUL 6.5 – Rezultate scenarii de utilizare (copy-paste în licență)")
    print("="*80)
    print(f"{'Profil':<32} | {'Țara aleasă':<18} | {'Orașe (top 2)':<28} | {'Atracții (top 2)'}")
    print("-"*80)
    for r in results:
        if not r:
            continue
        cities_str = ", ".join(r["cities"][:2]) if r["cities"] else "–"
        attrs_top2 = r["attractions_flat"][:2]
        attrs_str = "; ".join(a["name"] for a in attrs_top2) if attrs_top2 else "–"
        print(f"{r['name'][:31]:<32} | {r['country'][:17]:<18} | {cities_str[:27]:<28} | {attrs_str[:45]}")
    print("="*80)


# ─────────────────────────────────────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────────────────────────────────────

def main():
    db = SessionLocal()
    try:
        # Resetează cache-urile globale (util dacă scriptul rulează mai de multe ori)
        clear_country_scoring_cache()

        # Fetch leaf slugs reale din DB
        leaf_tags = db.query(Tag).filter(Tag.is_leaf == True).all()
        leaf_slugs = {t.slug for t in leaf_tags}
        print(f"Leaf tags în DB: {len(leaf_slugs)}")

        # Validare: verifică că tagurile arhetipurilor există realmente în DB
        for arch in ARCHETYPES:
            missing = [s for s in arch["target_tags"] if s not in leaf_slugs]
            if missing:
                print(f"  AVERTISMENT [{arch['name']}]: taguri lipsă din DB: {missing}")
            else:
                print(f"  OK [{arch['name']}]: toate tagurile există în DB")

        results = []
        for arch in ARCHETYPES:
            r = run_archetype(arch, db, leaf_slugs)
            results.append(r)

        # Scriere fișiere output
        md_path  = write_md(results)
        json_path = write_json(results)

        # Tabel 6.5 pentru copy-paste
        print_table_65(results)

        # Afișare conținut fișiere
        print("\n" + "="*80)
        print("CONȚINUT scenarii_utilizatori.md")
        print("="*80)
        with open(md_path, encoding="utf-8") as f:
            print(f.read())

        print("\n" + "="*80)
        print("CONȚINUT scenarii_figura.json")
        print("="*80)
        with open(json_path, encoding="utf-8") as f:
            print(f.read())

    finally:
        db.close()


if __name__ == "__main__":
    main()
