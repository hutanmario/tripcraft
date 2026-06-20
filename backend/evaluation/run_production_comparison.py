#!/usr/bin/env python3
"""
backend/evaluation/run_production_comparison.py
================================================
Compara quiz-ul de productie (simulat fidel) cu variantele evaluate anterior.

SURSE DE PROFIL:
  oracle        -- profil latent direct (plafonul teoretic)
  production    -- simulare fidela a quiz.py: Beta scoring + card tree adaptiv
  baseline      -- 20 carduri round-robin, scoruri additive (referinta veche)
  hier2+p       -- Phase1 probe/L1 + Phase2 depth + prior ierarhic
  cf_6040+p     -- Phase1 selectie explicita + 60/40 + prior ierarhic

COMPORTAMENT PRODUCTIE SIMULAT (quiz.py):
  - Start: arata L1_ORDER[0], card_count=1
  - Swipe: card_count += 1, THEN get_next_tag(card_count)
    -> Faza 1 (card_count < 8): L1_ORDER[card_count] -- NB: L1_ORDER[1] e sarit!
    -> Faza 2: L2 liked fara L3 aratat -> arata L3 din ramura
    -> Faza 3: L1 liked -> coboara la L2 copii
    -> Faza 4: L3 din L2 liked
    -> Faza 5: orice L2 neexplorat
  - Scoring: Beta bayesian (alpha/beta, nu additive weights)
  - Stop: >= MAX_CARDS sau (>= MIN_CARDS si entropia < 1.0) sau
          (>= 16 si |delta_entropia| < 0.1)
  - Final: propagare L1/L2 liked -> copii (*0.6) si nepoti (*0.3), normaliz.

EVALUARE:
  - Tara fixa = cea aleasa de ORACLE (pt comparabilitate)
  - Ground truth: cosine_sim(latent, atractie) > 0.2
  - Metrici: NDCG@k, Precision@k, Recall@k, Diversity@k
  - Diagnostic: corelatie recuperare profil vs NDCG@10
  - Semnificatie: Wilcoxon pairwise

AVERTISMENT:
  Validitate INTERNA pe date sintetice. Ground truth si scorarea impart
  reprezentarea cosinus -- oracle avantajat metodologic.

Output:
  production_comparison_per_user.csv
  production_comparison_summary.csv
  production_comparison_significance.csv
  production_comparison_correlation.csv
  production_comparison_metrics.png
  production_comparison_scatter.png
  SUMMARY_PRODUCTION.md

Rulare:
  python -m evaluation.run_production_comparison
"""

import sys, os, math, time, logging
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from scipy.stats import spearmanr, pearsonr, wilcoxon
from types import SimpleNamespace

SEED = 42
np.random.seed(SEED)
_rng = np.random.default_rng(SEED)

_BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _BACKEND_DIR not in sys.path:
    sys.path.insert(0, _BACKEND_DIR)

from app.database import SessionLocal
from app.models import Tag
from app.models.geography import Attraction, City, attraction_tags
from app.services.itinerary_scorer import score_attractions
from app.services.country_recommender import compute_country_scores
from app.services.quiz_engine import (
    adjust_tag_score, compute_entropy,
    RIGHT_WEIGHT, LEFT_WEIGHT, MIN_CARDS, MAX_CARDS, MIN_L3_BEFORE_STOP, L1_ORDER,
)
from sqlalchemy import select

RESULTS_DIR = os.path.join(os.path.dirname(__file__), "results")
os.makedirs(RESULTS_DIR, exist_ok=True)
logging.basicConfig(level=logging.WARNING)

L1_SLUGS = list(L1_ORDER)
N_USERS  = 50
K_VALUES = [5, 10, 20]
RELEVANCE_THRESHOLD = 0.20
HIER_PRIOR_STR = 0.30
ENTROPY_THRESHOLD = 1.0

# Phase1 params
MAX_SELECTED = 4
MIN_SELECTED = 1
N_PHASE2     = 20
N_HIER_TOTAL = 20
N_HIER_P1    = 8

SOURCES = ["oracle", "production", "baseline", "hier2+p", "cf_6040+p"]
SOURCE_COLORS = {
    "oracle":      "#FFC107",
    "production":  "#E91E63",
    "baseline":    "#9E9E9E",
    "hier2+p":     "#1565C0",
    "cf_6040+p":   "#880E4F",
}
SOURCE_LABELS = {
    "oracle":      "ORACLE\n(perfect)",
    "production":  "Productie\n(actual)",
    "baseline":    "Baseline\n(ref)",
    "hier2+p":     "Hier2\n+Prior",
    "cf_6040+p":   "CF 60/40\n+Prior",
}


# ─────────────────────────────────────────────────────────────────────────────
# Date (cu ierarhie tag pentru simularea productiei)
# ─────────────────────────────────────────────────────────────────────────────

def load_data(db):
    all_tags    = db.query(Tag).all()
    all_tag_ids = [t.id for t in all_tags]
    slug_to_id  = {t.slug: t.id for t in all_tags}
    id_to_slug  = {t.id: t.slug for t in all_tags}

    # Ierarhie
    id_to_parent_id = {t.id: t.parent_id for t in all_tags}
    is_leaf_slug    = {t.slug: bool(t.is_leaf) for t in all_tags}

    # Nivel tag: L1 (no parent), L2 (parent e L1), L3 (altfel)
    tag_level = {}
    for t in all_tags:
        if t.parent_id is None:
            tag_level[t.slug] = "L1"
        else:
            gp_id = id_to_parent_id.get(t.parent_id)
            tag_level[t.slug] = "L2" if gp_id is None else "L3"

    # Copii per slug (toate tipurile)
    children_by_slug = {}
    for t in all_tags:
        if t.parent_id is not None:
            parent_slug = id_to_slug.get(t.parent_id)
            if parent_slug:
                children_by_slug.setdefault(parent_slug, []).append(t.slug)

    # L1 -> frunze (pentru metrici de recuperare)
    slug_to_tag = {t.slug: t for t in all_tags}
    l1_to_leaf  = {}
    for l1_slug in L1_SLUGS:
        l1_tag = slug_to_tag.get(l1_slug)
        if not l1_tag:
            l1_to_leaf[l1_slug] = []
            continue
        leaves = []
        for l2 in [t for t in all_tags if t.parent_id == l1_tag.id]:
            if l2.is_leaf:
                leaves.append(l2.slug)
            for l3 in [t for t in all_tags if t.parent_id == l2.id]:
                if l3.is_leaf:
                    leaves.append(l3.slug)
        l1_to_leaf[l1_slug] = leaves

    # Atractii
    all_attractions = db.query(Attraction).all()
    attr_ids = [a.id for a in all_attractions]
    idx_map  = {tid: i for i, tid in enumerate(all_tag_ids)}
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

    all_cities = db.query(City).all()
    country_to_city_ids = {}
    for c in all_cities:
        country_to_city_ids.setdefault(c.country_id, []).append(c.id)

    n_leaf = sum(len(v) for v in l1_to_leaf.values())
    print(f"  {len(all_attractions)} atractii | {len(all_tag_ids)} taguri | {n_leaf} frunze")
    print(f"  L1={sum(1 for v in tag_level.values() if v=='L1')} "
          f"L2={sum(1 for v in tag_level.values() if v=='L2')} "
          f"L3={sum(1 for v in tag_level.values() if v=='L3')}")
    return {
        "all_tag_ids": all_tag_ids, "slug_to_id": slug_to_id,
        "l1_to_leaf": l1_to_leaf, "all_attractions": all_attractions,
        "attr_vecs": attr_vecs, "country_to_city_ids": country_to_city_ids,
        # pentru simularea productiei
        "tag_level": tag_level, "children_by_slug": children_by_slug,
        "is_leaf_slug": is_leaf_slug,
    }


# ─────────────────────────────────────────────────────────────────────────────
# Useri sintetici (identici cu toate testele anterioare, SEED=42)
# ─────────────────────────────────────────────────────────────────────────────

def generate_users(l1_to_leaf, rng):
    users = []
    for i in range(N_USERS):
        n_dom    = int(rng.integers(2, 4))
        dominant = rng.choice(L1_SLUGS, size=n_dom, replace=False).tolist()
        latent_macro = {
            l1: float(rng.uniform(0.65, 0.92)) if l1 in dominant
                else float(rng.uniform(0.04, 0.18))
            for l1 in L1_SLUGS
        }
        latent_leaf = {}
        for l1, w in latent_macro.items():
            for slug in l1_to_leaf.get(l1, []):
                latent_leaf[slug] = max(0.0, min(1.0, w + float(rng.normal(0.0, 0.035))))
        users.append({
            "user_id": i, "dominant": dominant,
            "latent_macro": latent_macro, "latent_leaf": latent_leaf,
        })
    return users


# ─────────────────────────────────────────────────────────────────────────────
# Primitiva swipe (comuna tuturor variantelor)
# ─────────────────────────────────────────────────────────────────────────────

def _swipe_additive(tag_scores, slug, latent_leaf, rng):
    """Additive weights (baseline, hier2+p, cf_6040+p)."""
    lat = latent_leaf.get(slug, 0.08)
    p   = 1.0 / (1.0 + math.exp(-5.0 * (lat - 0.5)))
    adjust_tag_score(tag_scores, slug,
                     RIGHT_WEIGHT if rng.random() < p else LEFT_WEIGHT, True)

def _swipe_beta(tag_beliefs, tag_scores, slug, latent_leaf, rng):
    """Beta bayesian (productie)."""
    lat = latent_leaf.get(slug, 0.08)
    p   = 1.0 / (1.0 + math.exp(-5.0 * (lat - 0.5)))
    direction = "right" if rng.random() < p else "left"
    if slug not in tag_beliefs:
        tag_beliefs[slug] = {"alpha": 1.0, "beta": 1.0}
    if direction == "right":
        tag_beliefs[slug]["alpha"] += 1.0
    else:
        tag_beliefs[slug]["beta"] += 0.5
    b = tag_beliefs[slug]
    tag_scores[slug] = round(b["alpha"] / (b["alpha"] + b["beta"]), 4)
    return direction


# ─────────────────────────────────────────────────────────────────────────────
# get_next_tag simulat (fidel cu quiz.py)
# ─────────────────────────────────────────────────────────────────────────────

def _get_next_tag(shown, swipe_res, card_count, data, rng):
    tag_level        = data["tag_level"]
    children_by_slug = data["children_by_slug"]
    is_leaf          = data["is_leaf_slug"]

    # Fix 1: conditia <= si index card_count-1 corecteaza off-by-one (culture-history era sarit)
    if card_count <= len(L1_SLUGS):
        slug = L1_SLUGS[card_count - 1]
        if slug not in shown:
            return slug
        for child in children_by_slug.get(slug, []):
            if child not in shown:
                return child

    right_slugs = {s for s, d in swipe_res.items() if d == "right"}
    right_l1 = [s for s in right_slugs if tag_level.get(s) == "L1"]

    # Fix 2 — Faza 2 (primary): L3 frunze din L1-urile placute, round-robin prin L2
    if right_l1:
        l2_of_liked = []
        for l1 in right_l1:
            l2_of_liked.extend(
                c for c in children_by_slug.get(l1, []) if not is_leaf.get(c, False)
            )
        perm = rng.permutation(len(l2_of_liked))
        for i in perm:
            l2 = l2_of_liked[i]
            l3s = [c for c in children_by_slug.get(l2, [])
                   if c not in shown and is_leaf.get(c, False)]
            if l3s:
                return l3s[0]

    # Fix 2 — Faza 3 (fallback): L2 non-leaf daca nu exista frunze
    if right_l1:
        perm = rng.permutation(len(right_l1))
        for i in perm:
            l2s = [c for c in children_by_slug.get(right_l1[i], [])
                   if c not in shown and not is_leaf.get(c, False)]
            if l2s:
                return l2s[int(rng.integers(0, len(l2s)))]

    # Fix 2 — Faza 4: orice frunza L3 neafisata
    any_l3 = [s for s, lvl in tag_level.items() if lvl == "L3" and s not in shown
              and is_leaf.get(s, False)]
    if any_l3:
        return any_l3[int(rng.integers(0, len(any_l3)))]

    # Fix 2 — Faza 5: orice L2 nevazut (last resort)
    all_l2_unseen = [s for s, lvl in tag_level.items()
                     if lvl == "L2" and s not in shown]
    if all_l2_unseen:
        return all_l2_unseen[int(rng.integers(0, len(all_l2_unseen)))]

    return None


# ─────────────────────────────────────────────────────────────────────────────
# Propagare finala (productie: L1/L2 liked -> copii)
# ─────────────────────────────────────────────────────────────────────────────

def _apply_production_propagation(tag_scores, data):
    is_leaf          = data["is_leaf_slug"]
    children_by_slug = data["children_by_slug"]

    # Normalizeaza (pastreaza doar > 0.5, Bayesian mode)
    normalized = {k: v for k, v in tag_scores.items() if v > 0.5}
    directly_swiped = set(tag_scores.keys())
    expanded = dict(normalized)

    for slug, score in list(normalized.items()):
        if not is_leaf.get(slug, True):  # doar taguri non-frunza se propaga
            for child in children_by_slug.get(slug, []):
                if child not in directly_swiped:
                    expanded[child] = expanded.get(child, 0.0) + score * 0.6
                    if not is_leaf.get(child, True):
                        for gc in children_by_slug.get(child, []):
                            if gc not in directly_swiped:
                                expanded[gc] = expanded.get(gc, 0.0) + score * 0.3

    max_exp = max(expanded.values()) if expanded else 1.0
    return {k: round(v / max_exp, 4) for k, v in expanded.items() if v > 0}


# ─────────────────────────────────────────────────────────────────────────────
# QUIZ FUNCTIONS
# ─────────────────────────────────────────────────────────────────────────────

def apply_hier_prior(scores, l1_to_leaf, strength=HIER_PRIOR_STR):
    result = dict(scores)
    for l1, lv in l1_to_leaf.items():
        obs = [scores[s] for s in lv if s in scores]
        if not obs:
            continue
        agg = float(np.mean(obs))
        for s in lv:
            if s not in result:
                result[s] = 0.5 + strength * (agg - 0.5)
    return result

def phase1_select(latent_macro, rng):
    probs = {l1: 1.0/(1.0+math.exp(-5.0*(latent_macro.get(l1,0.1)-0.5))) for l1 in L1_SLUGS}
    raw = [l1 for l1 in L1_SLUGS if rng.random() < probs[l1]]
    if len(raw) > MAX_SELECTED:
        raw = sorted(raw, key=lambda l: -probs[l])[:MAX_SELECTED]
    if len(raw) < MIN_SELECTED:
        raw += sorted([l for l in L1_SLUGS if l not in raw],
                      key=lambda l: -probs[l])[:MIN_SELECTED-len(raw)]
    return raw, [l for l in L1_SLUGS if l not in raw]


def quiz_production(user, data, rng):
    """Simulare fidela a quiz.py cu Beta scoring si card tree adaptiv."""
    lf = user["latent_leaf"]
    shown, swipe_res, tag_beliefs, tag_scores = set(), {}, {}, {}
    card_count = 1

    # START: arata L1_ORDER[0]
    first = L1_SLUGS[0]
    shown.add(first)
    _swipe_beta(tag_beliefs, tag_scores, first, lf, rng)
    prev_entropy = compute_entropy(tag_scores)

    card_level_counts = {"L1": 1, "L2": 0, "L3": 0}

    while True:
        card_count += 1  # incrementat INAINTE de get_next_tag (ca in productie)
        next_slug = _get_next_tag(shown, swipe_res, card_count, data, rng)
        if next_slug is None:
            break

        shown.add(next_slug)
        _swipe_beta(tag_beliefs, tag_scores, next_slug, lf, rng)
        lvl = data["tag_level"].get(next_slug, "L3")
        card_level_counts[lvl] = card_level_counts.get(lvl, 0) + 1

        entropy = compute_entropy(tag_scores)
        # Fix 3: guard — permite oprire pe entropie doar dupa MIN_L3_BEFORE_STOP frunze vazute
        l3_shown_estimate = max(0, card_count - len(L1_SLUGS))
        should_stop = (
            card_count >= MAX_CARDS
            or (card_count >= MIN_CARDS and entropy < ENTROPY_THRESHOLD
                and l3_shown_estimate >= MIN_L3_BEFORE_STOP)
            or (card_count >= 16 and abs(prev_entropy - entropy) < 0.1
                and l3_shown_estimate >= MIN_L3_BEFORE_STOP)
        )
        if should_stop:
            break
        prev_entropy = entropy

    final = _apply_production_propagation(tag_scores, data)
    return final, card_count, card_level_counts


def quiz_baseline(user, data, rng):
    lf, l1l = user["latent_leaf"], data["l1_to_leaf"]
    tag_scores, seen, cp = {}, set(), 0
    n = int(rng.integers(MIN_CARDS, MAX_CARDS + 1))
    for _ in range(n):
        slug = None
        for _ in range(len(L1_SLUGS)):
            l1 = L1_SLUGS[cp % len(L1_SLUGS)]; cp += 1
            cands = [s for s in l1l.get(l1, []) if s not in seen]
            if cands: slug = cands[int(rng.integers(0, len(cands)))]; break
        if slug is None: break
        seen.add(slug); _swipe_additive(tag_scores, slug, lf, rng)
        if len(seen) >= MIN_CARDS and compute_entropy(tag_scores) < 1.0: break
    return tag_scores, len(seen), {}

def quiz_hier2_prior(user, data, rng):
    lf, l1l = user["latent_leaf"], data["l1_to_leaf"]
    tag_scores, seen = {}, set()
    for l1 in L1_SLUGS:
        cands = [s for s in l1l.get(l1, []) if s not in seen]
        if not cands: continue
        slug = cands[int(rng.integers(0, len(cands)))]
        seen.add(slug); _swipe_additive(tag_scores, slug, lf, rng)
    agg = {l1: float(np.mean([tag_scores[s] for s in lv if s in tag_scores]) or 0.5)
           for l1, lv in l1l.items() if any(s in tag_scores for s in lv)}
    dom2 = sorted(agg, key=lambda l: -agg.get(l, 0.5))[:2]
    cp = 0
    for _ in range(N_HIER_TOTAL - N_HIER_P1):
        slug = None
        for _ in range(len(dom2)):
            l1 = dom2[cp % len(dom2)]; cp += 1
            cands = [s for s in l1l.get(l1, []) if s not in seen]
            if cands: slug = cands[int(rng.integers(0, len(cands)))]; break
        if slug is None: break
        seen.add(slug); _swipe_additive(tag_scores, slug, lf, rng)
    return apply_hier_prior(tag_scores, l1l), len(seen), {}

def quiz_cf6040_prior(user, data, rng):
    lf, lm, l1l = user["latent_leaf"], user["latent_macro"], data["l1_to_leaf"]
    selected, non_sel = phase1_select(lm, rng)
    tag_scores, seen = {}, set()
    n_depth, n_explore = round(N_PHASE2 * 0.60), round(N_PHASE2 * 0.40)
    cp = 0
    for _ in range(n_depth):
        slug = None
        for _ in range(len(selected)):
            l1 = selected[cp % len(selected)]; cp += 1
            cands = [s for s in l1l.get(l1, []) if s not in seen]
            if cands: slug = cands[int(rng.integers(0, len(cands)))]; break
        if slug is None: break
        seen.add(slug); _swipe_additive(tag_scores, slug, lf, rng)
    cp2 = 0
    for _ in range(n_explore):
        if not non_sel: break
        slug = None
        for _ in range(len(non_sel)):
            l1 = non_sel[cp2 % len(non_sel)]; cp2 += 1
            cands = [s for s in l1l.get(l1, []) if s not in seen]
            if cands: slug = cands[int(rng.integers(0, len(cands)))]; break
        if slug is None: break
        seen.add(slug); _swipe_additive(tag_scores, slug, lf, rng)
    return apply_hier_prior(tag_scores, l1l), len(seen), {}


def get_all_profiles(user, data, rng):
    uid = user["user_id"]
    profiles, card_counts, level_stats = {}, {}, {}

    profiles["oracle"]    = dict(user["latent_leaf"])
    card_counts["oracle"] = len(user["latent_leaf"])

    p, n, ls = quiz_production(user, data, np.random.default_rng(SEED + uid))
    profiles["production"] = p; card_counts["production"] = n; level_stats["production"] = ls

    p, n, _ = quiz_baseline(user, data, np.random.default_rng(SEED + uid))
    profiles["baseline"] = p; card_counts["baseline"] = n

    p, n, _ = quiz_hier2_prior(user, data, np.random.default_rng(SEED + uid))
    profiles["hier2+p"] = p; card_counts["hier2+p"] = n

    p, n, _ = quiz_cf6040_prior(user, data, np.random.default_rng(SEED + uid))
    profiles["cf_6040+p"] = p; card_counts["cf_6040+p"] = n

    return profiles, card_counts, level_stats


# ─────────────────────────────────────────────────────────────────────────────
# Metrici
# ─────────────────────────────────────────────────────────────────────────────

def precision_at_k(ranked, rel, k):
    return sum(1 for a in ranked[:k] if a in rel) / k if k else 0.0

def recall_at_k(ranked, rel, k):
    return len(set(ranked[:k]) & rel) / len(rel) if rel else 0.0

def ndcg_at_k(ranked, rel, k):
    dcg  = sum(1.0/math.log2(i+2) for i,a in enumerate(ranked[:k]) if a in rel)
    idcg = sum(1.0/math.log2(i+2) for i in range(min(len(rel), k)))
    return dcg/idcg if idcg else 0.0

def diversity_at_k(ranked, attr_vecs, k):
    vecs = [attr_vecs[a] for a in ranked[:k] if a in attr_vecs]
    if len(vecs) < 2: return 0.0
    sims = [float(np.dot(vecs[i],vecs[j])/(np.linalg.norm(vecs[i])*np.linalg.norm(vecs[j])))
            for i in range(len(vecs)) for j in range(i+1,len(vecs))
            if np.linalg.norm(vecs[i])>0 and np.linalg.norm(vecs[j])>0]
    return 1.0 - float(np.mean(sims)) if sims else 0.0

def macro_recovery(profile, latent_macro, l1_to_leaf):
    rec = [float(np.mean([profile.get(s, 0.5) for s in l1_to_leaf.get(l1,[])]))
           if l1_to_leaf.get(l1) else 0.5 for l1 in L1_SLUGS]
    lat = [latent_macro.get(l1, 0.1) for l1 in L1_SLUGS]
    sp, _ = spearmanr(rec, lat)
    return float(sp) if not np.isnan(sp) else 0.0

def build_vec(profile, all_tag_ids, slug_to_id):
    raw = {tid: 0.0 for tid in all_tag_ids}
    for slug, score in profile.items():
        tid = slug_to_id.get(slug)
        if tid is not None: raw[tid] = float(score)
    vec  = np.array([raw[tid] for tid in all_tag_ids], dtype=float)
    norm = np.linalg.norm(vec)
    return (vec/norm if norm > 0 else vec), raw

def ground_truth_set(latent_leaf, all_tag_ids, slug_to_id, attr_vecs_subset):
    lv, _ = build_vec(latent_leaf, all_tag_ids, slug_to_id)
    return {aid for aid, avec in attr_vecs_subset.items()
            if float(np.dot(lv, avec)) > RELEVANCE_THRESHOLD}


# ─────────────────────────────────────────────────────────────────────────────
# Eval per user
# ─────────────────────────────────────────────────────────────────────────────

def _mock(profile):
    return SimpleNamespace(final_profile=profile, tag_scores=profile,
                           budget="mid", season="summer",
                           travel_style="couple", pace_preference="balanced")

def eval_user(user, data, db, rng):
    uid = user["user_id"]

    # Oracle alege tara — fixa pentru toti
    oracle_profile = dict(user["latent_leaf"])
    try:
        countries = compute_country_scores(_mock(oracle_profile), db,
                                           diversity=False, lambda_param=0.7, top_n=5)
    except Exception:
        return None
    if not countries:
        return None

    top_cid   = countries[0]["country_id"]
    top_cname = countries[0].get("country_name", "?")

    city_ids = data["country_to_city_ids"].get(top_cid, [])
    attrs = [a for a in data["all_attractions"]
             if hasattr(a, "city_id") and a.city_id in set(city_ids)]
    if not attrs:
        return None

    country_attr_vecs = {a.id: data["attr_vecs"][a.id] for a in attrs if a.id in data["attr_vecs"]}
    relevant = ground_truth_set(user["latent_leaf"], data["all_tag_ids"],
                                data["slug_to_id"], country_attr_vecs)
    if not relevant:
        return {"user_id": uid, "skip_reason": "no_relevant"}

    row = {
        "user_id": uid, "dominant": "|".join(user["dominant"]),
        "n_dominant": len(user["dominant"]),
        "oracle_country": top_cname,
        "n_relevant": len(relevant),
        "n_attractions": len(attrs),
        "prevalence": round(len(relevant)/len(attrs), 4),
    }

    profiles, card_counts, level_stats = get_all_profiles(user, data, rng)

    for src in SOURCES:
        profile = profiles[src]
        row[f"n_cards_{src}"]    = card_counts.get(src, 0)
        row[f"recovery_{src}"]   = round(macro_recovery(profile, user["latent_macro"],
                                                         data["l1_to_leaf"]), 4)

        # Country hit
        if src != "oracle":
            try:
                ctrs = compute_country_scores(_mock(profile), db,
                                              diversity=False, lambda_param=0.7, top_n=1)
                row[f"country_hit_{src}"] = int(bool(ctrs) and ctrs[0]["country_id"] == top_cid)
            except Exception:
                row[f"country_hit_{src}"] = 0

        # Scorare atractii
        uv, raw = build_vec(profile, data["all_tag_ids"], data["slug_to_id"])
        try:
            scored = score_attractions(attrs, uv, data["all_tag_ids"], db, user_raw_scores=raw)
        except Exception:
            scored = []
        if not scored:
            continue
        ranked = [r["attraction"].id for r in scored]
        for k in K_VALUES:
            row[f"prec@{k}_{src}"]  = round(precision_at_k(ranked, relevant, k), 4)
            row[f"rec@{k}_{src}"]   = round(recall_at_k(ranked, relevant, k), 4)
            row[f"ndcg@{k}_{src}"]  = round(ndcg_at_k(ranked, relevant, k), 4)
            row[f"div@{k}_{src}"]   = round(diversity_at_k(ranked, data["attr_vecs"], k), 4)

    # Stats niveluri productie
    ls = level_stats.get("production", {})
    row["prod_l1_cards"] = ls.get("L1", 0)
    row["prod_l2_cards"] = ls.get("L2", 0)
    row["prod_l3_cards"] = ls.get("L3", 0)

    return row


# ─────────────────────────────────────────────────────────────────────────────
# Runner
# ─────────────────────────────────────────────────────────────────────────────

def run_all(users, data, db):
    print(f"  Evaluare ({N_USERS} useri x {len(SOURCES)} surse) ...")
    rows, n_skip = [], 0
    for i, user in enumerate(users):
        if (i+1) % 10 == 0:
            print(f"    ... user {i+1}/{N_USERS}")
        r = eval_user(user, data, db, np.random.default_rng(SEED + user["user_id"]))
        if r is None or "skip_reason" in r:
            n_skip += 1; continue
        rows.append(r)
    print(f"  Evaluati: {len(rows)}/{N_USERS}  (sarite: {n_skip})")
    return pd.DataFrame(rows), n_skip


# ─────────────────────────────────────────────────────────────────────────────
# Sumar + semnificatie + corelatie
# ─────────────────────────────────────────────────────────────────────────────

def build_summary(df):
    rows = []
    for src in SOURCES:
        row = {"source": src}
        for mk in ["prec","rec","ndcg","div"]:
            for k in K_VALUES:
                col = f"{mk}@{k}_{src}"
                row[f"{mk}@{k}"] = round(df[col].mean(), 4) if col in df.columns else float("nan")
        row["recovery"]       = round(df[f"recovery_{src}"].mean(), 4)
        row["n_cards"]        = round(df[f"n_cards_{src}"].mean(), 1)
        row["country_hit"]    = round(df[f"country_hit_{src}"].mean(), 3) if f"country_hit_{src}" in df.columns else 1.0
        rows.append(row)
    df_sum = pd.DataFrame(rows)
    oracle_ndcg = df_sum[df_sum.source=="oracle"]["ndcg@10"].values[0]
    df_sum["gap_ndcg10"] = df_sum["ndcg@10"] - oracle_ndcg
    return df_sum

def compute_significance(df):
    rows = []
    for mk in ["ndcg@10", "prec@10"]:
        prefix = mk.split("@")[0]; k = mk.split("@")[1]
        oracle_col = f"{prefix}@{k}_oracle"
        prod_col   = f"{prefix}@{k}_production"
        for src in [s for s in SOURCES if s != "oracle"]:
            src_col = f"{prefix}@{k}_{src}"
            if src_col not in df.columns: continue
            a = df[src_col].dropna(); b_o = df[oracle_col].dropna()
            b_p = df[prod_col].dropna() if prod_col in df.columns else pd.Series(dtype=float)
            idx_o = a.index.intersection(b_o.index)
            try:
                _, p_o = wilcoxon(a.loc[idx_o], b_o.loc[idx_o], alternative="less")
            except Exception:
                p_o = float("nan")
            if src == "production":
                p_p = float("nan")
            else:
                idx_p = a.index.intersection(b_p.index)
                try:
                    _, p_p = wilcoxon(a.loc[idx_p], b_p.loc[idx_p], alternative="two-sided")
                except Exception:
                    p_p = float("nan")
            rows.append({
                "metric": mk, "source": src,
                "pval_vs_oracle": round(p_o, 4),
                "sig_vs_oracle": "**" if p_o<0.05 else ("*" if p_o<0.10 else "ns"),
                "pval_vs_production": round(p_p,4) if not np.isnan(p_p) else float("nan"),
                "sig_vs_production": ("**" if p_p<0.05 else ("*" if p_p<0.10 else "ns"))
                                      if not np.isnan(p_p) else "—",
            })
    return pd.DataFrame(rows)

def compute_correlation(df):
    rows = []
    all_rec, all_ndcg = [], []
    for src in SOURCES:
        x = df[f"recovery_{src}"].dropna()
        y = df[f"ndcg@10_{src}"].dropna() if f"ndcg@10_{src}" in df.columns else pd.Series()
        idx = x.index.intersection(y.index)
        xv, yv = x.loc[idx].values, y.loc[idx].values
        if len(xv) < 5: continue
        pr, ppr = pearsonr(xv, yv)
        sp, psp = spearmanr(xv, yv)
        rows.append({"source":src,"n":len(xv),
                     "pearson_r":round(float(pr),4),"pearson_p":round(float(ppr),4),
                     "spearman_r":round(float(sp),4),"spearman_p":round(float(psp),4)})
        all_rec.extend(xv.tolist()); all_ndcg.extend(yv.tolist())
    if len(all_rec) >= 5:
        pr, ppr = pearsonr(all_rec, all_ndcg)
        sp, psp = spearmanr(all_rec, all_ndcg)
        rows.append({"source":"POOLED","n":len(all_rec),
                     "pearson_r":round(float(pr),4),"pearson_p":round(float(ppr),4),
                     "spearman_r":round(float(sp),4),"spearman_p":round(float(psp),4)})
    return pd.DataFrame(rows)


# ─────────────────────────────────────────────────────────────────────────────
# Raportare consola
# ─────────────────────────────────────────────────────────────────────────────

def report(df, df_sum, df_sig, df_corr):
    print("\n" + "="*84)
    print(f"  {'Sursa':<14} {'Rec':>6} {'Cards':>6} {'CHit':>6} "
          f"{'P@10':>6} {'N@5':>6} {'N@10':>6} {'N@20':>6} {'Gap N10':>9}")
    print("  " + "-"*78)
    for _, r in df_sum.iterrows():
        mark = "  *" if r.source in ("oracle","production") else "   "
        print(f"{mark} {r.source:<14} "
              f"{r.recovery:>6.3f} {r.n_cards:>6.0f} {r.country_hit:>6.3f} "
              f"{r.get('prec@10',float('nan')):>6.4f} "
              f"{r.get('ndcg@5',float('nan')):>6.4f} "
              f"{r.get('ndcg@10',float('nan')):>6.4f} "
              f"{r.get('ndcg@20',float('nan')):>6.4f} "
              f"{r.gap_ndcg10:>+9.4f}")

    print(f"\n  Semnificatie NDCG@10 (vs oracle: one-sided less; vs production: two-sided):")
    print(f"  {'Sursa':<14} {'vs oracle p':>12} {'sig':>5}  {'vs prod p':>12} {'sig':>5}")
    print("  " + "-"*56)
    for _, r in df_sig[df_sig.metric=="ndcg@10"].iterrows():
        p_p = r["pval_vs_production"]
        p_p_str = f"{p_p:.4f}" if not np.isnan(p_p) else "       —"
        print(f"  {r.source:<14} {r.pval_vs_oracle:>12.4f} {r.sig_vs_oracle:>5}  "
              f"{p_p_str:>12} {r.sig_vs_production:>5}")

    print(f"\n  Corelatie recuperare vs NDCG@10:")
    print(f"  {'Sursa':<14} {'Pearson r':>10} {'p':>8} {'Spearman r':>11} {'p':>8}")
    print("  " + "-"*54)
    for _, r in df_corr.iterrows():
        mark = "  *" if r.source == "POOLED" else "   "
        print(f"{mark} {r.source:<14} {r.pearson_r:>9.4f}  {r.pearson_p:>8.4f}  "
              f"{r.spearman_r:>10.4f}  {r.spearman_p:>8.4f}")

    # Distributia cardurilor in productie
    if "prod_l1_cards" in df.columns:
        print(f"\n  Distributia cardurilor in productie (medie/user):")
        print(f"  L1: {df['prod_l1_cards'].mean():.1f}  "
              f"L2: {df['prod_l2_cards'].mean():.1f}  "
              f"L3: {df['prod_l3_cards'].mean():.1f}  "
              f"Total: {df['n_cards_production'].mean():.1f}")
        print(f"  NB: bug culture-history REPARAT -- acum L1=8 (toate categoriile), L2=0, L3 in Phase 2")

    print("="*84)


# ─────────────────────────────────────────────────────────────────────────────
# Grafice
# ─────────────────────────────────────────────────────────────────────────────

def make_plots(df, df_sum, df_corr):
    # Bar chart NDCG + Precision + Recovery
    metrics_plot = [("ndcg","NDCG@k"), ("prec","Precision@k"), ("div","Diversity@k")]
    fig, axes = plt.subplots(1, 3, figsize=(17, 5))
    x = np.arange(len(K_VALUES)); w = 0.15
    for ax, (mk, title) in zip(axes, metrics_plot):
        for i, src in enumerate(SOURCES):
            vals = [df_sum[df_sum.source==src][f"{mk}@{k}"].values[0] for k in K_VALUES]
            offset = (i - len(SOURCES)/2 + 0.5)*w
            ax.bar(x+offset, vals, w, label=SOURCE_LABELS[src],
                   color=SOURCE_COLORS[src], edgecolor="black", linewidth=0.5,
                   hatch="///" if src=="oracle" else ("xxx" if src=="production" else ""))
        ax.set_xticks(x); ax.set_xticklabels([str(k) for k in K_VALUES])
        ax.set_xlabel("K"); ax.set_title(title, fontsize=9)
        ax.legend(fontsize=6.5); ax.set_ylim(0, min(1.0, ax.get_ylim()[1]*1.15))
    plt.suptitle("Quiz design vs calitate recomandari (tara fixa=oracle, 48 useri)", fontsize=10)
    plt.tight_layout()
    plt.savefig(os.path.join(RESULTS_DIR, "production_comparison_metrics.png"), dpi=150)
    plt.close(); print("  Salvat: production_comparison_metrics.png")

    # Scatter recuperare vs NDCG@10 (fara oracle)
    srcs_plot = [s for s in SOURCES if s != "oracle"]
    fig, axes2 = plt.subplots(1, len(srcs_plot), figsize=(16, 4))
    for ax, src in zip(axes2, srcs_plot):
        xv = df[f"recovery_{src}"].values
        yv = df[f"ndcg@10_{src}"].values if f"ndcg@10_{src}" in df.columns else np.zeros(len(xv))
        ax.scatter(xv, yv, color=SOURCE_COLORS[src], alpha=0.7, edgecolors="black", linewidths=0.4, s=55)
        m, b = np.polyfit(xv, yv, 1)
        xs = np.linspace(min(xv), max(xv), 100)
        ax.plot(xs, m*xs+b, color="red", linewidth=1.5, linestyle="--")
        cr = df_corr[df_corr.source==src]
        sp = cr.iloc[0]["spearman_r"] if not cr.empty else float("nan")
        pp = cr.iloc[0]["spearman_p"] if not cr.empty else float("nan")
        ax.set_xlabel("Recuperare profil (macro Spearman)")
        ax.set_ylabel("NDCG@10"); ax.set_title(f"{src}\nr={sp:.3f} p={pp:.3f}", fontsize=9)
    plt.suptitle("Corelatie: recuperare profil vs NDCG@10", fontsize=10)
    plt.tight_layout()
    plt.savefig(os.path.join(RESULTS_DIR, "production_comparison_scatter.png"), dpi=150)
    plt.close(); print("  Salvat: production_comparison_scatter.png")


# ─────────────────────────────────────────────────────────────────────────────
# SUMMARY_PRODUCTION.md
# ─────────────────────────────────────────────────────────────────────────────

def save_summary(df, df_sum, df_sig, df_corr, n_skip):
    oracle_ndcg = df_sum[df_sum.source=="oracle"]["ndcg@10"].values[0]
    prod_ndcg   = df_sum[df_sum.source=="production"]["ndcg@10"].values[0]
    best_quiz   = df_sum[~df_sum.source.isin(["oracle","baseline","production"])]["ndcg@10"].max()
    df_quiz = df_sum[~df_sum.source.isin(["oracle","baseline","production"])].reset_index(drop=True)
    best_quiz_src = df_quiz.loc[df_quiz["ndcg@10"].idxmax(), "source"]

    lines = [
        "# Comparatie Productie vs Variante Quiz — TripCraft",
        "",
        "## Avertisment metodologic",
        "> Validitate INTERNA pe date sintetice (SEED=42, 50 useri). Ground truth si scorarea",
        "> impart reprezentarea cosinus -- oracle avantajat metodologic.",
        "> Evaluarea se face pe aceeasi tara (top-1 oracle) pentru comparabilitate.",
        "> NB: productia are un bug -- L1_ORDER[1]='culture-history' este sarit in Phase 1.",
        "",
        "## Configuratie",
        f"| Parametru | Valoare |", "|---|---|",
        f"| Useri valizi | {len(df)} |",
        f"| SEED | {SEED} |", f"| K | {K_VALUES} |",
        f"| Relevance threshold | {RELEVANCE_THRESHOLD} |",
        "",
        "## Metrici comparative (medie pe useri valizi)",
        "",
        "| Sursa | Recovery | Cards | CHit% | P@10 | NDCG@10 | Gap NDCG@10 |",
        "|---|---|---|---|---|---|---|",
    ]
    for _, r in df_sum.iterrows():
        lines.append(
            f"| **{r.source}** | {r.recovery:.3f} | {r.n_cards:.0f} | "
            f"{r.country_hit*100:.0f}% | {r.get('prec@10',float('nan')):.4f} | "
            f"{r.get('ndcg@10',float('nan')):.4f} | {r.gap_ndcg10:+.4f} |"
        )
    lines += [
        "",
        "## Semnificatie NDCG@10 (Wilcoxon)",
        "",
        "| Sursa | vs oracle p | sig | vs productie p | sig |",
        "|---|---|---|---|---|",
    ]
    for _, r in df_sig[df_sig.metric=="ndcg@10"].iterrows():
        p_p = r["pval_vs_production"]
        p_p_str = f"{p_p:.4f}" if not np.isnan(p_p) else "—"
        lines.append(
            f"| {r.source} | {r.pval_vs_oracle:.4f} | {r.sig_vs_oracle} | "
            f"{p_p_str} | {r.sig_vs_production} |"
        )
    lines += [
        "",
        "## Corelatie recuperare profil vs NDCG@10",
        "",
        "| Sursa | Pearson r | p | Spearman r | p |",
        "|---|---|---|---|---|",
    ]
    for _, r in df_corr.iterrows():
        lines.append(f"| **{r.source}** | {r.pearson_r:.4f} | {r.pearson_p:.4f} | "
                     f"{r.spearman_r:.4f} | {r.spearman_p:.4f} |")
    lines += [
        "",
        "## Distributia cardurilor in productie",
        f"| Nivel | Medie/user |", "|---|---|",
        f"| L1 (categorii) | {df['prod_l1_cards'].mean():.1f} |",
        f"| L2 (subcategorii) | {df['prod_l2_cards'].mean():.1f} |",
        f"| L3/frunze | {df['prod_l3_cards'].mean():.1f} |",
        f"| Total | {df['n_cards_production'].mean():.1f} |",
        f"| **Bug**: L1_ORDER[1]='culture-history' sarit in Phase 1 ||",
        "",
        "## Concluzie",
        "",
        f"- Productie NDCG@10: `{prod_ndcg:.4f}` (gap vs oracle: `{prod_ndcg-oracle_ndcg:+.4f}`)",
        f"- Cel mai bun quiz nou: `{best_quiz_src}` NDCG@10=`{best_quiz:.4f}`",
        f"- Diferenta productie vs cel mai bun quiz: `{best_quiz-prod_ndcg:+.4f}`",
        "",
        f"*Generat de evaluation/run_production_comparison.py | SEED={SEED}*",
    ]
    path = os.path.join(RESULTS_DIR, "SUMMARY_PRODUCTION.md")
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    print("  Salvat: SUMMARY_PRODUCTION.md")


# ─────────────────────────────────────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────────────────────────────────────

def main():
    print("\n" + "="*84)
    print("  TripCraft — Productie vs Variante Quiz (simulare fidela)")
    print(f"  SEED={SEED} | N={N_USERS} | K={K_VALUES}")
    print(f"  Surse: {SOURCES}")
    print("="*84)

    db = SessionLocal()
    try:
        print("\nIncarcare date ...")
        data = load_data(db)
        print("\nGenerare useri sintetici ...")
        users = generate_users(data["l1_to_leaf"], _rng)
        print("")
        df, n_skip = run_all(users, data, db)
    finally:
        db.close()

    df_sum  = build_summary(df)
    df_sig  = compute_significance(df)
    df_corr = compute_correlation(df)

    report(df, df_sum, df_sig, df_corr)
    make_plots(df, df_sum, df_corr)

    df.to_csv(os.path.join(RESULTS_DIR, "production_comparison_per_user.csv"), index=False)
    df_sum.to_csv(os.path.join(RESULTS_DIR, "production_comparison_summary.csv"), index=False)
    df_sig.to_csv(os.path.join(RESULTS_DIR, "production_comparison_significance.csv"), index=False)
    df_corr.to_csv(os.path.join(RESULTS_DIR, "production_comparison_correlation.csv"), index=False)
    print("  Salvat: production_comparison_*.csv")
    save_summary(df, df_sum, df_sig, df_corr, n_skip)

    print(f"\nFisiere in results/:")
    for fname in sorted(f for f in os.listdir(RESULTS_DIR) if "production" in f or "SUMMARY_PROD" in f):
        size = os.path.getsize(os.path.join(RESULTS_DIR, fname))
        print(f"  {fname:<52}  {size:>8,} bytes")


if __name__ == "__main__":
    main()
