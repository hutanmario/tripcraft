#!/usr/bin/env python3
"""
backend/evaluation/run_quality_eval.py
=======================================
Evaluare cantitativa a sistemului TripCraft pe 50 de useri sintetici
cu profil-adevar cunoscut (model generativ controlat).

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
AVERTISMENT METODOLOGIC (OBLIGATORIU — citeste inainte de interpretare)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Ground truth-ul (relevanta atractiilor) este definit EXCLUSIV din
profilul-adevar LATENT al userului sintetic, calculat INAINTE de orice
rulare a sistemului de recomandare.

Procedura non-circulara:
  1. Se genereaza profil latent: {l1_slug: weight}  (modelul generativ)
  2. Se calculeaza INDEPENDENT relevanta: cosine_sim(latent_vector,
     attraction_vector) > RELEVANCE_THRESHOLD
  3. Se simuleaza chestionarul → profil RECONSTRUIT (cu zgomot)
  4. Sistemul rankeaza cu profilul RECONSTRUIT (nu cu cel latent)
  5. Metricile compara rankingul sistemului cu relevanta LATENTA

De ce e non-circular: profilul care defineste ground truth (latent)
este DIFERIT de profilul folosit de sistem (reconstruit din quiz).
Sistemul nu stie profilul latent — il aproximeaza prin quiz.

Validitate: INTERNA pe date sintetice. Nu se generalizeaza direct
la utilizatori reali fara validare externa suplimentara.
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Rulare (din directorul backend/):
    python -m evaluation.run_quality_eval
"""

import sys
import os
import math
import random
import time
import uuid
import logging

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from scipy.stats import spearmanr
from types import SimpleNamespace
from sqlalchemy import select

# ── Seed reproductibilitate ───────────────────────────────────────────────────
SEED = 42
random.seed(SEED)
np.random.seed(SEED)
_rng = np.random.default_rng(SEED)

# ── Path setup ────────────────────────────────────────────────────────────────
_BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _BACKEND_DIR not in sys.path:
    sys.path.insert(0, _BACKEND_DIR)

from app.database import SessionLocal
from app.models import Tag, QuizV4Session
from app.models.geography import Attraction, City, attraction_tags
from app.services.itinerary_scorer import score_attractions, get_attraction_tag_idf
from app.services.country_recommender import compute_country_scores, clear_country_scoring_cache
from app.services.itinerary_builder import build_itinerary
# Quiz engine (pure logic, fara DB) — reutilizare directa
from app.services.quiz_engine import (
    adjust_tag_score,   # modifica tag_scores in-place (Bayesian, baza 0.5)
    compute_entropy,
    RIGHT_WEIGHT,       # 1.0
    LEFT_WEIGHT,        # -0.4
    MIN_CARDS,          # 15
    MAX_CARDS,          # 20
    ENTROPY_THRESHOLD,  # 1.0
    L1_ORDER,           # ordinea L1 in quiz
)

RESULTS_DIR = os.path.join(os.path.dirname(__file__), "results")
os.makedirs(RESULTS_DIR, exist_ok=True)

logging.basicConfig(level=logging.WARNING)
_log = logging.getLogger("quality_eval")
_log.setLevel(logging.INFO)
_h = logging.StreamHandler()
_h.setFormatter(logging.Formatter("%(message)s"))
_log.addHandler(_h)

# ── Constante evaluare ────────────────────────────────────────────────────────
N_USERS = 50
K_VALUES = [5, 10, 20]
RELEVANCE_THRESHOLD = 0.20   # cosinus(latent_vec, attraction_vec) > prag → relevant
ITINERARY_DAYS = 5
COUNTRY_TOP_N = 5

WEIGHT_CONFIGS = {
    "productie":           (0.70, 0.20, 0.10),
    "doar_cosinus":        (1.00, 0.00, 0.00),
    "fara_raritate":       (0.80, 0.20, 0.00),
    "raritate_egal_pop":   (0.70, 0.15, 0.15),
    "raritate_peste_pop":  (0.70, 0.10, 0.20),
    "cos_redus":           (0.60, 0.20, 0.20),
}

L1_SLUGS = list(L1_ORDER)   # ['nature-outdoors', ..., 'family-comfort']


# ─────────────────────────────────────────────────────────────────────────────
# Functii metrice
# ─────────────────────────────────────────────────────────────────────────────

def precision_at_k(ranked_ids, relevant_set, k):
    return sum(1 for aid in ranked_ids[:k] if aid in relevant_set) / k if k > 0 else 0.0

def recall_at_k(ranked_ids, relevant_set, k):
    if not relevant_set:
        return 0.0
    return len(set(ranked_ids[:k]) & relevant_set) / len(relevant_set)

def ndcg_at_k(ranked_ids, relevant_set, k):
    dcg = sum(
        1.0 / math.log2(i + 2)
        for i, aid in enumerate(ranked_ids[:k])
        if aid in relevant_set
    )
    ideal = min(len(relevant_set), k)
    idcg = sum(1.0 / math.log2(i + 2) for i in range(ideal))
    return dcg / idcg if idcg > 0 else 0.0

def intra_list_diversity(ranked_ids, attr_vecs, k):
    """1 - similaritate cosinus medie intra-lista (top-k)."""
    vecs = [attr_vecs[aid] for aid in ranked_ids[:k] if aid in attr_vecs]
    if len(vecs) < 2:
        return 0.0
    sims = []
    for i in range(len(vecs)):
        ni = np.linalg.norm(vecs[i])
        for j in range(i + 1, len(vecs)):
            nj = np.linalg.norm(vecs[j])
            if ni > 0 and nj > 0:
                sims.append(float(np.dot(vecs[i], vecs[j]) / (ni * nj)))
    return 1.0 - float(np.mean(sims)) if sims else 0.0

def category_coverage(ranked_ids, cat_map, k):
    return len({cat_map.get(aid) for aid in ranked_ids[:k] if cat_map.get(aid)})

def macro_recovery(rec_profile, latent_macro, l1_to_leaf):
    """Spearman intre macro-scoruri reconstruite si macro-scoruri latente.
    Masoara cat de bine chestionarul recupereaza preferintele reale.
    """
    rec_vec, lat_vec = [], []
    for l1 in L1_SLUGS:
        leaves = l1_to_leaf.get(l1, [])
        rec_val = float(np.mean([rec_profile.get(s, 0.5) for s in leaves])) if leaves else 0.5
        rec_vec.append(rec_val)
        lat_vec.append(latent_macro.get(l1, 0.1))
    sp, _ = spearmanr(rec_vec, lat_vec)
    return float(sp) if not np.isnan(sp) else 0.0


# ─────────────────────────────────────────────────────────────────────────────
# Constructie vectori utilizator
# ─────────────────────────────────────────────────────────────────────────────

def build_vec_from_scores(profile_slug, all_tag_ids, slug_to_id):
    """Replica get_user_tag_vector din itinerary_scorer (fara DB)."""
    raw = {tid: 0.0 for tid in all_tag_ids}
    for slug, score in profile_slug.items():
        tid = slug_to_id.get(slug)
        if tid is not None and tid in raw:
            raw[tid] = float(score)
    vec = np.array([raw[tid] for tid in all_tag_ids], dtype=float)
    norm = np.linalg.norm(vec)
    return (vec / norm if norm > 0 else vec), raw


# ─────────────────────────────────────────────────────────────────────────────
# PASUL 0: Re-rulare evaluare existenta (formula IDF)
# ─────────────────────────────────────────────────────────────────────────────

def paso0_rerun():
    print("\n" + "=" * 62)
    print("PASUL 0: Re-rulare run_evaluation.py (formula IDF noua)")
    print("=" * 62)
    # Import si rulare directa — regenereaza toate fisierele din PASUL anterior
    from evaluation.run_evaluation import main as _eval_main
    _eval_main()
    print("\nPASUL 0 complet — fisiere regenerate in results/\n")


# ─────────────────────────────────────────────────────────────────────────────
# SECTIUNEA 1: Incarcare date
# ─────────────────────────────────────────────────────────────────────────────

def load_data(db):
    print("=" * 62)
    print("SECTIUNEA 1: Incarcare date")
    print("=" * 62)

    all_tags = db.query(Tag).all()
    all_tag_ids = [t.id for t in all_tags]
    slug_to_id = {t.slug: t.id for t in all_tags}
    slug_to_tag = {t.slug: t for t in all_tags}

    # Mapare L1 -> sluguri frunza
    l1_to_leaf = {}
    for l1_slug in L1_SLUGS:
        l1_tag = slug_to_tag.get(l1_slug)
        if l1_tag is None:
            l1_to_leaf[l1_slug] = []
            continue
        collected = []
        for l2 in [t for t in all_tags if t.parent_id == l1_tag.id]:
            if l2.is_leaf:
                collected.append(l2.slug)
            for l3 in [t for t in all_tags if t.parent_id == l2.id]:
                if l3.is_leaf:
                    collected.append(l3.slug)
        l1_to_leaf[l1_slug] = collected

    # Toate atractiile + vectorii lor de taguri
    all_attractions = db.query(Attraction).all()
    attr_ids = [a.id for a in all_attractions]
    idx_map = {tid: i for i, tid in enumerate(all_tag_ids)}

    rows = db.execute(
        select(attraction_tags).where(attraction_tags.c.attraction_id.in_(attr_ids))
    ).fetchall()
    tags_by_attr = {}
    for row in rows:
        tags_by_attr.setdefault(row.attraction_id, []).append(row)

    attr_vecs = {}
    for a in all_attractions:
        vec = np.zeros(len(all_tag_ids))
        for row in tags_by_attr.get(a.id, []):
            if row.tag_id in idx_map:
                vec[idx_map[row.tag_id]] = float(row.score or 1.0)
        norm = np.linalg.norm(vec)
        attr_vecs[a.id] = vec / norm if norm > 0 else vec

    cat_map = {a.id: a.category for a in all_attractions}

    # Country -> cities -> attractions (precomputed)
    all_cities = db.query(City).all()
    country_to_city_ids = {}
    for c in all_cities:
        country_to_city_ids.setdefault(c.country_id, []).append(c.id)

    print(f"  Atractii: {len(all_attractions)}, Taguri: {len(all_tag_ids)}")
    for l1, leaves in l1_to_leaf.items():
        print(f"    {l1}: {len(leaves)} frunze")

    return {
        "all_tags": all_tags,
        "all_tag_ids": all_tag_ids,
        "slug_to_id": slug_to_id,
        "l1_to_leaf": l1_to_leaf,
        "all_attractions": all_attractions,
        "attr_vecs": attr_vecs,
        "cat_map": cat_map,
        "country_to_city_ids": country_to_city_ids,
    }


# ─────────────────────────────────────────────────────────────────────────────
# SECTIUNEA 2: Generare useri sintetici
# ─────────────────────────────────────────────────────────────────────────────

def generate_users(l1_to_leaf, rng):
    """50 useri sintetici: 2-3 categorii dominante + zgomot Gaussian."""
    users = []
    for i in range(N_USERS):
        n_dom = int(rng.integers(2, 4))   # 2 sau 3 categorii dominante
        dominant = rng.choice(L1_SLUGS, size=n_dom, replace=False).tolist()

        latent_macro = {
            l1: float(rng.uniform(0.65, 0.92)) if l1 in dominant
                else float(rng.uniform(0.04, 0.18))
            for l1 in L1_SLUGS
        }

        # Profil latent in spatiul frunzelor (cu zgomot mic)
        latent_leaf = {}
        for l1, w in latent_macro.items():
            for slug in l1_to_leaf.get(l1, []):
                noise = float(rng.normal(0.0, 0.035))
                latent_leaf[slug] = max(0.0, min(1.0, w + noise))

        users.append({
            "user_id": i,
            "dominant": dominant,
            "latent_macro": latent_macro,
            "latent_leaf": latent_leaf,
        })

    dom_counts = [len(u["dominant"]) for u in users]
    print(f"\n  {N_USERS} useri sintetici generati.")
    print(f"  Distributie categorii dominante: 2 categorii={dom_counts.count(2)}, 3 categorii={dom_counts.count(3)}")
    return users


# ─────────────────────────────────────────────────────────────────────────────
# SECTIUNEA 3: Simulare chestionar
# ─────────────────────────────────────────────────────────────────────────────

def simulate_quiz(latent_leaf, l1_to_leaf, rng):
    """
    Simuleaza quiz v4 (MIN_CARDS..MAX_CARDS carduri, round-robin L1).
    Swipe probabilistic bazat pe scorul latent al tagului.

    Apeleaza adjust_tag_score din quiz_engine.py (Bayesian, baza 0.5).
    Returneaza: tag_scores dict {slug: float in [0,1]}
    """
    tag_scores = {}
    seen = set()
    n_cards = int(rng.integers(MIN_CARDS, MAX_CARDS + 1))
    cycle_pos = 0

    for _ in range(n_cards):
        slug = None
        for _ in range(len(L1_SLUGS)):
            l1 = L1_SLUGS[cycle_pos % len(L1_SLUGS)]
            cycle_pos += 1
            cands = [s for s in l1_to_leaf.get(l1, []) if s not in seen]
            if cands:
                slug = cands[int(rng.integers(0, len(cands)))]
                break

        if slug is None:
            break

        seen.add(slug)
        lat = latent_leaf.get(slug, 0.08)
        # P(right) = sigmoid(5*(lat - 0.5))
        prob_right = 1.0 / (1.0 + math.exp(-5.0 * (lat - 0.5)))
        delta = RIGHT_WEIGHT if rng.random() < prob_right else LEFT_WEIGHT

        # Reutilizeaza adjust_tag_score din quiz_engine.py (Bayesian)
        adjust_tag_score(tag_scores, slug, delta, bayesian=True)

        # Oprire anticipata daca entropia e suficient de mica
        if len(seen) >= MIN_CARDS and compute_entropy(tag_scores) < ENTROPY_THRESHOLD:
            break

    return tag_scores


# ─────────────────────────────────────────────────────────────────────────────
# SECTIUNEA 4: Ground truth (INDEPENDENT de sistem)
# ─────────────────────────────────────────────────────────────────────────────

def ground_truth(latent_vec, attr_vecs_subset):
    """
    IMPORTANT: aceasta functie foloseste EXCLUSIV latent_vec (profilul latent
    al userului), NU profilul reconstruit si NU scorul sistemului.

    Relevanta = cosine_sim(latent_vec, attraction_vec) > RELEVANCE_THRESHOLD.
    Independenta fata de sistem e garantata: sistemul foloseste profilul
    reconstruit (diferit de cel latent), nu scorul returnat aici.
    """
    relevant = set()
    for aid, avec in attr_vecs_subset.items():
        if float(np.dot(latent_vec, avec)) > RELEVANCE_THRESHOLD:
            relevant.add(aid)
    return relevant


# ─────────────────────────────────────────────────────────────────────────────
# SECTIUNEA 5: Pipeline complet per user
# ─────────────────────────────────────────────────────────────────────────────

def eval_user(user, data, db, rng):
    uid = user["user_id"]
    res = {
        "user_id": uid,
        "dominant": "|".join(user["dominant"]),
        "n_dominant": len(user["dominant"]),
    }

    # ── Quiz simulation ───────────────────────────────────────────────────────
    t0 = time.perf_counter()
    rec = simulate_quiz(user["latent_leaf"], data["l1_to_leaf"], rng)
    res["t_quiz_s"] = round(time.perf_counter() - t0, 4)
    res["n_cards_swiped"] = len(rec)

    # ── Recuperare profil ─────────────────────────────────────────────────────
    res["profile_recovery_spearman"] = macro_recovery(
        rec, user["latent_macro"], data["l1_to_leaf"]
    )

    # ── Country recommendation ────────────────────────────────────────────────
    mock_sess = SimpleNamespace(
        final_profile=rec,
        tag_scores=rec,
        budget="mid",
        season="summer",
        travel_style="couple",
        pace_preference="balanced",
    )
    t0 = time.perf_counter()
    try:
        countries = compute_country_scores(
            mock_sess, db, diversity=False, lambda_param=0.7, top_n=COUNTRY_TOP_N
        )
    except Exception as e:
        print(f"  [user {uid}] country error: {e}")
        return None
    res["t_country_s"] = round(time.perf_counter() - t0, 4)

    if not countries:
        return None
    top_country_id = countries[0]["country_id"]
    res["top_country"] = countries[0].get("country_name", "?")

    # ── Attraction scoring ────────────────────────────────────────────────────
    city_ids = data["country_to_city_ids"].get(top_country_id, [])
    if not city_ids:
        return None
    attrs_in_country = [
        a for a in data["all_attractions"] if hasattr(a, "city_id") and a.city_id in set(city_ids)
    ]
    if not attrs_in_country:
        return None

    user_vec, raw_scores = build_vec_from_scores(rec, data["all_tag_ids"], data["slug_to_id"])

    t0 = time.perf_counter()
    scored = score_attractions(attrs_in_country, user_vec, data["all_tag_ids"], db,
                               user_raw_scores=raw_scores)
    res["t_scoring_s"] = round(time.perf_counter() - t0, 4)
    res["n_country_attractions"] = len(scored)

    if not scored:
        return None

    ranked_ids = [r["attraction"].id for r in scored]

    # ── Ground truth (latent, INDEPENDENT de sistem) ──────────────────────────
    latent_vec, _ = build_vec_from_scores(
        user["latent_leaf"], data["all_tag_ids"], data["slug_to_id"]
    )
    country_attr_vecs = {
        r["attraction"].id: data["attr_vecs"][r["attraction"].id]
        for r in scored
        if r["attraction"].id in data["attr_vecs"]
    }
    relevant = ground_truth(latent_vec, country_attr_vecs)
    res["n_relevant"] = len(relevant)
    res["prevalence"] = round(len(relevant) / len(scored), 4) if scored else 0.0

    if not relevant:
        res["skip_reason"] = "no_relevant"
        return res

    # ── Metrici productie ─────────────────────────────────────────────────────
    for k in K_VALUES:
        res[f"prec@{k}"]  = round(precision_at_k(ranked_ids, relevant, k), 4)
        res[f"rec@{k}"]   = round(recall_at_k(ranked_ids, relevant, k), 4)
        res[f"ndcg@{k}"]  = round(ndcg_at_k(ranked_ids, relevant, k), 4)
        res[f"div@{k}"]   = round(intra_list_diversity(ranked_ids, data["attr_vecs"], k), 4)
        res[f"cov@{k}"]   = category_coverage(ranked_ids, data["cat_map"], k)

    # ── Metrici per configuratie de ponderi ───────────────────────────────────
    comps = [
        {
            "id": r["attraction"].id,
            "cos": r["_cosine"],
            "pop": r["_popularity"],
            "rar": r["_rarity"],
        }
        for r in scored
    ]
    cfg_rows = []
    for cfg_name, (wc, wp, wr) in WEIGHT_CONFIGS.items():
        alt = sorted(comps, key=lambda c: wc*c["cos"] + wp*c["pop"] + wr*c["rar"], reverse=True)
        alt_ids = [c["id"] for c in alt]
        row = {"user_id": uid, "config": cfg_name}
        for k in K_VALUES:
            row[f"prec@{k}"]  = round(precision_at_k(alt_ids, relevant, k), 4)
            row[f"rec@{k}"]   = round(recall_at_k(alt_ids, relevant, k), 4)
            row[f"ndcg@{k}"]  = round(ndcg_at_k(alt_ids, relevant, k), 4)
            row[f"div@{k}"]   = round(intra_list_diversity(alt_ids, data["attr_vecs"], k), 4)
        cfg_rows.append(row)

    res["_cfg_rows"] = cfg_rows
    return res


# ─────────────────────────────────────────────────────────────────────────────
# SECTIUNEA 6: Stress test runtime (cu build_itinerary real)
# ─────────────────────────────────────────────────────────────────────────────

def run_stress_test(users, data, db):
    """
    Masoara timpii pe etape pentru N_USERS useri.
    Creeaza QuizV4Session temporare in DB pentru build_itinerary, le sterge dupa.
    """
    print(f"\n  Stress test build_itinerary ({N_USERS} useri, {ITINERARY_DAYS} zile)...")
    records = []
    tmp_ids = []

    # Warmup: primul apel populeaza cache-urile
    if users:
        u0 = users[0]
        rec0 = simulate_quiz(u0["latent_leaf"], data["l1_to_leaf"], np.random.default_rng(0))
        ms0 = SimpleNamespace(final_profile=rec0, tag_scores=rec0, budget="mid", season="summer",
                              travel_style="couple", pace_preference="balanced")
        try:
            compute_country_scores(ms0, db, diversity=False, lambda_param=0.7, top_n=1)
        except Exception:
            pass

    rng_stress = np.random.default_rng(SEED + 1000)
    for user in users:
        t_quiz_s = 0.0
        t_country_s = 0.0
        t_score_s = 0.0
        t_itin_s = float("nan")
        n_days = 0

        # Quiz
        t0 = time.perf_counter()
        rec = simulate_quiz(user["latent_leaf"], data["l1_to_leaf"], rng_stress)
        t_quiz_s = time.perf_counter() - t0

        # Country
        mock = SimpleNamespace(final_profile=rec, tag_scores=rec, budget="mid", season="summer",
                               travel_style="couple", pace_preference="balanced")
        t0 = time.perf_counter()
        try:
            countries = compute_country_scores(mock, db, diversity=False, lambda_param=0.7, top_n=1)
        except Exception:
            countries = []
        t_country_s = time.perf_counter() - t0

        if not countries:
            continue
        cid = countries[0]["country_id"]

        # Attraction scoring
        city_ids = data["country_to_city_ids"].get(cid, [])
        attrs = [a for a in data["all_attractions"] if a.city_id in set(city_ids)]
        uv, rs = build_vec_from_scores(rec, data["all_tag_ids"], data["slug_to_id"])
        t0 = time.perf_counter()
        score_attractions(attrs, uv, data["all_tag_ids"], db, user_raw_scores=rs)
        t_score_s = time.perf_counter() - t0

        # Itinerary — necesita sesiune reala in DB
        tmp_sess = QuizV4Session(
            id=uuid.uuid4(),
            current_stage="completed",
            final_profile=rec,
            tag_scores=rec,
            budget="mid",
            season="summer",
            travel_style="couple",
            pace_preference="balanced",
        )
        try:
            db.add(tmp_sess)
            db.commit()
            tmp_ids.append(tmp_sess.id)
        except Exception as e:
            db.rollback()
            continue

        t0 = time.perf_counter()
        try:
            days = build_itinerary(
                country_id=cid,
                nr_zile=ITINERARY_DAYS,
                session_id=str(tmp_sess.id),
                db=db,
            )
            t_itin_s = time.perf_counter() - t0
            n_days = len(days) if days else 0
        except Exception as ex:
            t_itin_s = float("nan")
            print(f"    [user {user['user_id']}] build_itinerary error: {ex}")

        records.append({
            "user_id": user["user_id"],
            "country": countries[0].get("country_name", "?"),
            "t_quiz_s": round(t_quiz_s, 4),
            "t_country_s": round(t_country_s, 4),
            "t_scoring_s": round(t_score_s, 4),
            "t_itinerary_s": round(t_itin_s, 4) if not math.isnan(t_itin_s) else None,
            "n_itinerary_days": n_days,
        })

    # Cleanup sesiuni temporare
    if tmp_ids:
        try:
            db.query(QuizV4Session).filter(
                QuizV4Session.id.in_(tmp_ids)
            ).delete(synchronize_session=False)
            db.commit()
            print(f"  {len(tmp_ids)} sesiuni temporare sterse din DB.")
        except Exception as e:
            db.rollback()
            print(f"  Eroare cleanup: {e}")

    return records


# ─────────────────────────────────────────────────────────────────────────────
# SECTIUNEA 7: Salvare + grafice
# ─────────────────────────────────────────────────────────────────────────────

def _p(x): return os.path.join(RESULTS_DIR, x)

def save_results(per_user_rows, cfg_rows_all, stress_rows):
    # ── CSVs ──────────────────────────────────────────────────────────────────
    df_user = pd.DataFrame(per_user_rows)
    df_user.to_csv(_p("quality_per_user.csv"), index=False)

    df_cfg = pd.DataFrame(cfg_rows_all)
    df_cfg_mean = (
        df_cfg.groupby("config")
        .mean(numeric_only=True)
        .drop(columns=["user_id"], errors="ignore")
        .reset_index()
    )
    df_cfg_mean.to_csv(_p("quality_per_weight_config.csv"), index=False)

    df_stress = pd.DataFrame(stress_rows)
    df_stress.to_csv(_p("runtime.csv"), index=False)

    return df_user, df_cfg_mean, df_stress


def make_plots(df_user, df_cfg, df_stress):
    if "skip_reason" in df_user.columns:
        valid = df_user[df_user["skip_reason"].isna()].copy()
    else:
        valid = df_user.copy()

    # ── 1. Precision / Recall / NDCG vs K ────────────────────────────────────
    fig, axes = plt.subplots(1, 3, figsize=(13, 4))
    for ax, metric, label in zip(
        axes,
        ["prec", "rec", "ndcg"],
        ["Precision@K", "Recall@K", "NDCG@K"],
    ):
        means = [valid[f"{metric}@{k}"].mean() for k in K_VALUES]
        stds  = [valid[f"{metric}@{k}"].std()  for k in K_VALUES]
        ax.bar([str(k) for k in K_VALUES], means, yerr=stds, capsize=4,
               color="#2196F3", edgecolor="black", linewidth=0.5)
        ax.set_title(label)
        ax.set_xlabel("K")
        ax.set_ylim(0, 1.0)
        for i, (m, s) in enumerate(zip(means, stds)):
            ax.text(i, m + s + 0.01, f"{m:.3f}", ha="center", fontsize=8)
    plt.suptitle("Quality Metrics vs K — TripCraft (IDF rarity)", fontsize=11)
    plt.tight_layout()
    plt.savefig(_p("quality_metrics_vs_k.png"), dpi=150)
    plt.close()

    # ── 2. Distributia diversitatii si recuperarii profilului ─────────────────
    fig, axes = plt.subplots(1, 2, figsize=(10, 4))
    if f"div@{K_VALUES[-1]}" in valid.columns:
        axes[0].hist(valid[f"div@{K_VALUES[-1]}"].dropna(), bins=15, color="#4CAF50",
                     edgecolor="black", linewidth=0.5)
        axes[0].set_title(f"Intra-list Diversity @{K_VALUES[-1]}")
        axes[0].set_xlabel("1 - mean cosine sim")
    if "profile_recovery_spearman" in valid.columns:
        axes[1].hist(valid["profile_recovery_spearman"].dropna(), bins=15, color="#FF9800",
                     edgecolor="black", linewidth=0.5)
        axes[1].set_title("Profile Recovery (Spearman)")
        axes[1].set_xlabel("Spearman rank corr. (latent vs reconstructed)")
    plt.tight_layout()
    plt.savefig(_p("quality_diversity_recovery.png"), dpi=150)
    plt.close()

    # ── 3. Metrici per configuratie de ponderi ────────────────────────────────
    if df_cfg is not None and not df_cfg.empty:
        configs = df_cfg["config"].tolist()
        n_cfg = len(configs)
        fig, axes = plt.subplots(1, 3, figsize=(14, 5))
        x = np.arange(n_cfg)
        width = 0.25
        colors = {"@5": "#2196F3", "@10": "#FF9800", "@20": "#4CAF50"}
        for ax, metric, title in zip(axes, ["prec", "ndcg", "div"], ["Precision", "NDCG", "Diversity"]):
            for idx, k in enumerate(K_VALUES):
                col = f"{metric}@{k}"
                if col in df_cfg.columns:
                    bars = ax.bar(
                        x + (idx - 1) * width, df_cfg[col], width,
                        label=f"@{k}", color=colors[f"@{k}"],
                        edgecolor="black", linewidth=0.4,
                    )
            ax.set_title(title)
            ax.set_xticks(x)
            ax.set_xticklabels(configs, rotation=22, ha="right", fontsize=7)
            ax.set_ylim(0, 1.0)
            ax.legend(fontsize=7)
            # Marcam configuratia de productie
            if "productie" in configs:
                ax.axvline(configs.index("productie"), color="red", linewidth=0.8,
                           linestyle="--", alpha=0.5)
        plt.suptitle("Quality Metrics per Weight Configuration (mean over 50 users)", fontsize=10)
        plt.tight_layout()
        plt.savefig(_p("quality_per_config.png"), dpi=150)
        plt.close()

    # ── 4. Distributia timpilor ───────────────────────────────────────────────
    if df_stress is not None and not df_stress.empty:
        time_cols = ["t_quiz_s", "t_country_s", "t_scoring_s", "t_itinerary_s"]
        fig, ax = plt.subplots(figsize=(9, 4))
        plot_data = [df_stress[c].dropna().values for c in time_cols if c in df_stress.columns]
        labels = [c.replace("_s", "").replace("t_", "") for c in time_cols if c in df_stress.columns]
        ax.boxplot(plot_data, tick_labels=labels, patch_artist=True,
                   boxprops=dict(facecolor="#E3F2FD"),
                   medianprops=dict(color="red", linewidth=1.5))
        ax.set_ylabel("Timp (secunde)")
        ax.set_title(f"Runtime Distribution per etapa ({N_USERS} useri)")
        plt.tight_layout()
        plt.savefig(_p("runtime_distribution.png"), dpi=150)
        plt.close()


# ─────────────────────────────────────────────────────────────────────────────
# SECTIUNEA 8: SUMMARY_QUALITY.md
# ─────────────────────────────────────────────────────────────────────────────

def write_summary(df_user, df_cfg, df_stress, n_skipped):
    valid = df_user.copy()
    if "skip_reason" in valid.columns:
        valid = valid[valid["skip_reason"].isna()]

    lines = [
        "# Rezumat Evaluare Calitativa — TripCraft (formula IDF rarity)",
        "",
        "## Avertisment metodologic",
        "",
        "> Ground truth-ul este definit **exclusiv** din profilul-adevar latent",
        "> al userului sintetic, calculat inainte de rularea sistemului.",
        "> Relevanta = cosine_sim(latent_vector, attraction_vector) > "
        f"{RELEVANCE_THRESHOLD}.",
        "> **NU** se foloseste scorul sistemului pentru a defini relevanta",
        "> (ar fi circular). Validitate: **INTERNA** pe date sintetice.",
        "",
        "## Configuratie",
        "",
        f"| Parametru | Valoare |",
        f"|---|---|",
        f"| Useri sintetici | {N_USERS} |",
        f"| Useri evaluati (cu relevanti > 0) | {len(valid)} |",
        f"| Useri sarite (0 atractii relevante) | {n_skipped} |",
        f"| Prag relevanta (RELEVANCE_THRESHOLD) | {RELEVANCE_THRESHOLD} |",
        f"| K values | {K_VALUES} |",
        f"| SEED | {SEED} |",
        "",
        "## 1. Metrici de calitate (configuratia de productie, medii)",
        "",
        "| Metrica | @5 | @10 | @20 |",
        "|---|---|---|---|",
    ]

    for metric, label in [("prec", "Precision"), ("rec", "Recall"), ("ndcg", "NDCG"), ("div", "Diversity")]:
        row = f"| {label} |"
        for k in K_VALUES:
            col = f"{metric}@{k}"
            val = valid[col].mean() if col in valid.columns else float("nan")
            row += f" {val:.4f} |"
        lines.append(row)

    if "profile_recovery_spearman" in valid.columns:
        pr = valid["profile_recovery_spearman"].mean()
        lines += [
            "",
            f"**Recuperare profil (Spearman macro, medie):** {pr:.4f}",
        ]

    if "prevalence" in valid.columns:
        pv = valid["prevalence"].mean()
        lines += [f"**Prevalenta relevantilor in tara (medie):** {pv:.4f}"]

    lines += [
        "",
        "## 2. Comparatie configuratii ponderi (medie pe 50 useri)",
        "",
        "| Configuratie | Prec@10 | Recall@10 | NDCG@10 | Div@10 |",
        "|---|---|---|---|---|",
    ]
    if df_cfg is not None and not df_cfg.empty:
        for _, row in df_cfg.iterrows():
            tag = " <- productie" if row["config"] == "productie" else ""
            lines.append(
                f"| {row['config']}{tag} | "
                f"{row.get('prec@10', 0):.4f} | "
                f"{row.get('rec@10', 0):.4f} | "
                f"{row.get('ndcg@10', 0):.4f} | "
                f"{row.get('div@10', 0):.4f} |"
            )

    if df_stress is not None and not df_stress.empty:
        lines += ["", "## 3. Runtime (stress test)", ""]
        for col, label in [("t_quiz_s","Quiz"), ("t_country_s","Country rec."),
                           ("t_scoring_s","Attraction scoring"), ("t_itinerary_s","Itinerary build")]:
            if col not in df_stress.columns:
                continue
            arr = df_stress[col].dropna()
            if len(arr) == 0:
                continue
            lines.append(
                f"- **{label}**: mean={arr.mean():.3f}s  std={arr.std():.3f}s  "
                f"p50={arr.quantile(0.5):.3f}s  p95={arr.quantile(0.95):.3f}s"
            )

    lines += [
        "",
        "## Fisiere generate",
        "",
        "- `quality_per_user.csv` — metrici per user",
        "- `quality_per_weight_config.csv` — metrici mediate per configuratie ponderi",
        "- `runtime.csv` — timpii pe etape per user",
        "- `quality_metrics_vs_k.png` — Precision/Recall/NDCG vs K",
        "- `quality_diversity_recovery.png` — distributia diversitatii si recuperarii",
        "- `quality_per_config.png` — comparatia configuratiilor de ponderi",
        "- `runtime_distribution.png` — distributia timpilor pe etape",
        "",
        "---",
        f"*Generat de `backend/evaluation/run_quality_eval.py` | SEED={SEED}*",
    ]

    text = "\n".join(lines)
    with open(_p("SUMMARY_QUALITY.md"), "w", encoding="utf-8") as f:
        f.write(text)
    print()
    print(text)


# ─────────────────────────────────────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────────────────────────────────────

def main():
    print("\n" + "=" * 62)
    print("  TripCraft — Evaluare Calitativa (IDF rarity)")
    print(f"  SEED={SEED}  |  N_USERS={N_USERS}  |  K={K_VALUES}")
    print("=" * 62)

    # PASUL 0
    paso0_rerun()

    db = SessionLocal()
    try:
        # PASUL 1.1 — Date
        print("\n" + "=" * 62)
        print("PASUL 1: Evaluare calitativa")
        print("=" * 62)
        data = load_data(db)

        # PASUL 1.2 — Useri sintetici
        print("\nSECT. 2: Generare useri sintetici...")
        users = generate_users(data["l1_to_leaf"], _rng)

        # PASUL 1.3-5 — Eval per user
        print("\nSECT. 3-5: Simulare quiz + scoring + metrici...")
        per_user_rows = []
        cfg_rows_all = []
        n_skipped = 0

        for i, user in enumerate(users):
            if (i + 1) % 10 == 0:
                print(f"  ... user {i+1}/{N_USERS}")
            r = eval_user(user, data, db, np.random.default_rng(SEED + i))
            if r is None:
                n_skipped += 1
                continue
            cfg_rows = r.pop("_cfg_rows", [])
            skip = r.get("skip_reason")
            per_user_rows.append(r)
            if not skip:
                cfg_rows_all.extend(cfg_rows)
            else:
                n_skipped += 1

        valid_rows = [r for r in per_user_rows if "skip_reason" not in r]
        print(f"\n  Useri evaluati: {len(valid_rows)}/{N_USERS}  (sarite: {n_skipped})")

        # Sumar metrici de productie
        if valid_rows:
            df_v = pd.DataFrame(valid_rows)
            print(f"\n  [Productie — medii pe {len(df_v)} useri valizi]")
            print(f"  {'Metrica':<14} {'@5':>8} {'@10':>8} {'@20':>8}")
            print("  " + "-" * 40)
            for metric, label in [("prec","Precision"), ("rec","Recall"),
                                   ("ndcg","NDCG"), ("div","Diversity")]:
                vals = [df_v[f"{metric}@{k}"].mean() if f"{metric}@{k}" in df_v.columns else float("nan")
                        for k in K_VALUES]
                print(f"  {label:<14} {vals[0]:>8.4f} {vals[1]:>8.4f} {vals[2]:>8.4f}")
            if "profile_recovery_spearman" in df_v.columns:
                print(f"  {'Prof.Recovery':<14} {df_v['profile_recovery_spearman'].mean():>8.4f}")

        # PASUL 1.6 — Comparatie ponderi
        print("\nSECT. 6: Comparatie configuratii ponderi...")
        df_cfg_mean = None
        if cfg_rows_all:
            df_cfg_raw = pd.DataFrame(cfg_rows_all)
            df_cfg_mean = (
                df_cfg_raw.groupby("config")
                .mean(numeric_only=True)
                .drop(columns=["user_id"], errors="ignore")
                .reset_index()
            )
            print(f"\n  {'Config':<22} {'P@10':>8} {'R@10':>8} {'NDCG@10':>8} {'Div@10':>8}")
            print("  " + "-" * 56)
            for _, row in df_cfg_mean.iterrows():
                tag = " *" if row["config"] == "productie" else ""
                print(
                    f"  {row['config']+tag:<22} "
                    f"{row.get('prec@10', float('nan')):>8.4f} "
                    f"{row.get('rec@10', float('nan')):>8.4f} "
                    f"{row.get('ndcg@10', float('nan')):>8.4f} "
                    f"{row.get('div@10', float('nan')):>8.4f}"
                )

        # PASUL 1.7 — Stress test runtime
        print("\nSECT. 7: Stress test runtime...")
        stress_rows = run_stress_test(users, data, db)
        if stress_rows:
            df_s = pd.DataFrame(stress_rows)
            valid_s = df_s.dropna(subset=["t_itinerary_s"]) if "t_itinerary_s" in df_s.columns else df_s
            print(f"  {len(valid_s) if not valid_s.empty else 0} itinerarii generate cu succes / {len(stress_rows)}")
            for col, label in [("t_quiz_s","Quiz"), ("t_country_s","Country"),
                               ("t_scoring_s","Scoring"), ("t_itinerary_s","Itinerary")]:
                if col not in df_s.columns:
                    continue
                arr = df_s[col].dropna()
                if len(arr) == 0:
                    continue
                print(
                    f"  {label:<12}: mean={arr.mean():.3f}s  "
                    f"p50={arr.quantile(0.5):.3f}s  p95={arr.quantile(0.95):.3f}s"
                )
        else:
            stress_rows = []
            df_s = pd.DataFrame()

        # PASUL 1.8 — Salvare + grafice + summary
        print("\nSECT. 8: Salvare rezultate...")
        df_user_full = pd.DataFrame(per_user_rows)
        df_user_full.to_csv(_p("quality_per_user.csv"), index=False)
        if df_cfg_mean is not None:
            df_cfg_mean.to_csv(_p("quality_per_weight_config.csv"), index=False)
        df_s.to_csv(_p("runtime.csv"), index=False)

        make_plots(df_user_full, df_cfg_mean, df_s if not df_s.empty else None)
        write_summary(df_user_full, df_cfg_mean, df_s if not df_s.empty else None, n_skipped)

    finally:
        db.close()

    print("\n" + "=" * 62)
    print("Fisiere generate in backend/evaluation/results/:")
    for fname in sorted(os.listdir(RESULTS_DIR)):
        size = os.path.getsize(os.path.join(RESULTS_DIR, fname))
        print(f"  {fname:<45}  {size:>9,} bytes")
    print("=" * 62)


if __name__ == "__main__":
    main()
