#!/usr/bin/env python3
"""
backend/evaluation/run_phase1_test.py
======================================
Test empiric pentru îmbunătățirile din Faza 1:
  A. Prior ierarhic macro→frunze
  B. Co-aparitie proxy (stand-in pentru CLIP multi-tag)

Compara Profile Recovery pe 4 variante de simulare quiz:
  1. Baseline     — quiz curent (Bayesian, fara imbunatatiri)
  2. +Prior       — + prior ierarhic post-quiz
  3. +Cooc        — + update multi-tag bazat pe co-aparitie in attraction_tags
  4. +Prior+Cooc  — ambele combinate

NU modifica codul de productie. Ruleaza pe aceiasi 50 useri sintetici
din run_quality_eval.py (SEED=42) pentru rezultate comparabile.

Rulare:
    python -m evaluation.run_phase1_test
"""

import sys
import os
import math
import logging

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from scipy.stats import spearmanr, wilcoxon
from sqlalchemy import select

SEED = 42
np.random.seed(SEED)
_rng = np.random.default_rng(SEED)

_BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _BACKEND_DIR not in sys.path:
    sys.path.insert(0, _BACKEND_DIR)

from app.database import SessionLocal
from app.models import Tag
from app.models.geography import attraction_tags
from app.services.quiz_engine import (
    adjust_tag_score, compute_entropy,
    RIGHT_WEIGHT, LEFT_WEIGHT, MIN_CARDS, MAX_CARDS, L1_ORDER,
)

RESULTS_DIR = os.path.join(os.path.dirname(__file__), "results")
os.makedirs(RESULTS_DIR, exist_ok=True)

logging.basicConfig(level=logging.WARNING)

L1_SLUGS = list(L1_ORDER)
N_USERS = 50

# Parametri tuning prior (testam si mai multi)
PRIOR_STRENGTHS = [0.20, 0.30, 0.40]
PRIOR_DEFAULT = 0.30

# Prag Jaccard pentru co-aparitie (STRICT: numai taguri din acelasi L1)
COOC_THRESHOLD = 0.20   # prag Jaccard minim pentru a considera relatia
COOC_WEIGHT = 0.22       # delta secundar = delta_primar × COOC_WEIGHT (conservator)


# ─────────────────────────────────────────────────────────────────────────────
# Incarcare date
# ─────────────────────────────────────────────────────────────────────────────

def load_data(db):
    print("Incarcare date...")
    all_tags = db.query(Tag).all()
    all_tag_ids = [t.id for t in all_tags]
    slug_to_id = {t.slug: t.id for t in all_tags}
    id_to_slug = {t.id: t.slug for t in all_tags}
    slug_to_tag = {t.slug: t for t in all_tags}

    # L1 → frunze
    l1_to_leaf = {}
    for l1 in L1_SLUGS:
        l1_tag = slug_to_tag.get(l1)
        if not l1_tag:
            l1_to_leaf[l1] = []
            continue
        leaves = []
        for l2 in [t for t in all_tags if t.parent_id == l1_tag.id]:
            if l2.is_leaf:
                leaves.append(l2.slug)
            for l3 in [t for t in all_tags if t.parent_id == l2.id]:
                if l3.is_leaf:
                    leaves.append(l3.slug)
        l1_to_leaf[l1] = leaves

    # L2 → frunze (pentru referinta)
    l2_to_leaf = {}
    for tag in all_tags:
        if not tag.is_leaf and tag.parent_id is not None:
            leaves = [t.slug for t in all_tags if t.parent_id == tag.id and t.is_leaf]
            if leaves:
                l2_to_leaf[tag.slug] = leaves

    # slug → L2 parent slug
    slug_to_l2 = {}
    for tag in all_tags:
        if tag.is_leaf and tag.parent_id:
            parent = next((t for t in all_tags if t.id == tag.parent_id), None)
            if parent:
                slug_to_l2[tag.slug] = parent.slug

    # Co-aparitie tag-uri in attraction_tags (Jaccard similarity)
    print("  Calcul co-aparitie taguri din attraction_tags...")
    rows = db.execute(select(attraction_tags)).fetchall()

    # attr_id → set de tag_ids
    attr_tags_map = {}
    for row in rows:
        attr_tags_map.setdefault(row.attraction_id, set()).add(row.tag_id)

    # Numar aparitii per tag
    tag_count = {}
    for tags_set in attr_tags_map.values():
        for tid in tags_set:
            tag_count[tid] = tag_count.get(tid, 0) + 1

    # Co-aparitii
    cooc_count = {}
    for tags_set in attr_tags_map.values():
        tag_list = list(tags_set)
        for i in range(len(tag_list)):
            for j in range(i + 1, len(tag_list)):
                a, b = tag_list[i], tag_list[j]
                key = (min(a, b), max(a, b))
                cooc_count[key] = cooc_count.get(key, 0) + 1

    # Jaccard = co_aparitii / (|A| + |B| - co_aparitii)
    cooc_by_slug = {}   # slug → [(slug_related, jaccard), ...]
    for (tid_a, tid_b), cnt in cooc_count.items():
        jaccard = cnt / (tag_count.get(tid_a, 1) + tag_count.get(tid_b, 1) - cnt)
        if jaccard < COOC_THRESHOLD:
            continue
        slug_a = id_to_slug.get(tid_a)
        slug_b = id_to_slug.get(tid_b)
        if slug_a and slug_b:
            cooc_by_slug.setdefault(slug_a, []).append((slug_b, jaccard))
            cooc_by_slug.setdefault(slug_b, []).append((slug_a, jaccard))

    # Sorteaza dupa Jaccard descrescator
    for slug in cooc_by_slug:
        cooc_by_slug[slug].sort(key=lambda x: -x[1])

    # Filtreaza: NUMAI perechi din ACELASI L1 macro-categorie
    # Rationale: co-aparitia cross-L1 reflecta co-locatie geografica (de ex.
    # beach + restaurant in orase costiere), NU similaritate semantica a imaginilor.
    # CLIP pe imagini ar gasi similaritate in interiorul categoriei, nu intre ele.
    slug_to_l1 = {}
    for l1, leaves in l1_to_leaf.items():
        for s in leaves:
            slug_to_l1[s] = l1

    cooc_same_l1 = {}
    for slug, related in cooc_by_slug.items():
        l1_slug = slug_to_l1.get(slug)
        filtered = [(r_slug, j) for r_slug, j in related
                    if slug_to_l1.get(r_slug) == l1_slug and l1_slug is not None]
        if filtered:
            cooc_same_l1[slug] = filtered

    n_pairs_all = sum(len(v) for v in cooc_by_slug.values()) // 2
    n_pairs_l1  = sum(len(v) for v in cooc_same_l1.values()) // 2
    print(f"  {n_pairs_all} perechi totale cu Jaccard >= {COOC_THRESHOLD}")
    print(f"  {n_pairs_l1} perechi INTRA-L1 (filtrate cross-categorie)")
    print(f"  Taguri cu relatii intra-L1: {len(cooc_same_l1)}/{len(all_tags)}")

    cooc_by_slug = cooc_same_l1   # inlocuim cu versiunea filtrata

    # L2 siblings per tag (pentru simularea imaginilor multi-tag)
    # slug → [slug_sibling1, slug_sibling2, ...] — alte frunze sub ACELASI L2 parent
    # Rationale: o imagine de "hiking pe munte" reprezinta vizual si
    # "forest-bathing" si "contemplative-nature" (acelasi L2), NU "beach-water".
    # Acestea sunt asocierile pe care CLIP le-ar gasi — structurale, nu statistice.
    id_to_parent = {t.id: t.parent_id for t in all_tags}
    slug_to_l2_siblings = {}
    for tag in all_tags:
        if not tag.is_leaf or not tag.parent_id:
            continue
        siblings = [
            t.slug for t in all_tags
            if t.is_leaf and t.parent_id == tag.parent_id and t.id != tag.id
        ]
        slug_to_l2_siblings[tag.slug] = siblings

    n_with_siblings = sum(1 for v in slug_to_l2_siblings.values() if v)
    avg_siblings = (
        sum(len(v) for v in slug_to_l2_siblings.values()) / len(slug_to_l2_siblings)
        if slug_to_l2_siblings else 0
    )
    print(f"  Taguri cu L2-siblings: {n_with_siblings}/{len(all_tags)}, "
          f"medie siblings/tag: {avg_siblings:.1f}")

    # Sentence Transformer embeddings pentru taguri-frunza
    # Textul = tag.name (e.g. "Hiking & Trekking") — suficient de descriptiv
    # Modelul all-MiniLM-L6-v2: 90MB, rapid pe CPU, bun pentru similaritate
    print("  Calcul sentence transformer embeddings (all-MiniLM-L6-v2)...")
    from sentence_transformers import SentenceTransformer
    leaf_tags = [t for t in all_tags if t.is_leaf]
    leaf_slugs_list = [t.slug for t in leaf_tags]
    leaf_texts = [
        f"{t.name}" + (f": {t.description}" if t.description else "")
        for t in leaf_tags
    ]
    st_model = SentenceTransformer("all-MiniLM-L6-v2")
    embeddings = st_model.encode(leaf_texts, normalize_embeddings=True,
                                 show_progress_bar=False)
    # Similaritate cosinus pairwise (embeddings sunt deja normalizate)
    sim_matrix = embeddings @ embeddings.T   # [n_leaf × n_leaf]

    # Pentru fiecare tag-frunza: top-k cele mai similare taguri (exclus el insusi)
    SEMTAG_TOP_K = 4      # cate taguri semantice asociem per imagine
    SEMTAG_MIN_SIM = 0.40  # prag minim similaritate cosinus

    slug_to_sem_neighbors = {}
    for i, slug in enumerate(leaf_slugs_list):
        sims = sim_matrix[i]
        # Sorteaza descrescator, exclud self (i)
        ranked = sorted(
            [(leaf_slugs_list[j], float(sims[j])) for j in range(len(leaf_slugs_list)) if j != i],
            key=lambda x: -x[1]
        )
        neighbors = [(s, sim) for s, sim in ranked if sim >= SEMTAG_MIN_SIM][:SEMTAG_TOP_K]
        slug_to_sem_neighbors[slug] = neighbors

    n_sem = sum(1 for v in slug_to_sem_neighbors.values() if v)
    avg_sem = (sum(len(v) for v in slug_to_sem_neighbors.values()) / len(slug_to_sem_neighbors)
               if slug_to_sem_neighbors else 0)
    print(f"  Vecini semantici (global, sim>={SEMTAG_MIN_SIM}): "
          f"{n_sem}/{len(leaf_slugs_list)}, medie: {avg_sem:.1f}/tag")

    # Varianta filtrata: vecini semantici NUMAI din acelasi L1
    # Combina calitatea semantica a modelului cu restrictia categoriei
    slug_to_l1_for_sem = {}
    for l1, leaves in l1_to_leaf.items():
        for s in leaves:
            slug_to_l1_for_sem[s] = l1

    slug_to_sem_l1 = {}
    for slug, nbrs in slug_to_sem_neighbors.items():
        l1_slug = slug_to_l1_for_sem.get(slug)
        filtered = [
            (s, sim) for s, sim in nbrs
            if slug_to_l1_for_sem.get(s) == l1_slug and l1_slug is not None
        ]
        if filtered:
            slug_to_sem_l1[slug] = filtered

    n_sem_l1 = sum(1 for v in slug_to_sem_l1.values() if v)
    avg_sem_l1 = (sum(len(v) for v in slug_to_sem_l1.values()) / len(slug_to_sem_l1)
                  if slug_to_sem_l1 else 0)
    print(f"  Vecini semantici (filtrat L1, sim>={SEMTAG_MIN_SIM}): "
          f"{n_sem_l1}/{len(leaf_slugs_list)}, medie: {avg_sem_l1:.1f}/tag")

    # Exemple comparative global vs L1-filtrat
    print("  Exemple (global vs L1-filtrat):")
    examples = [s for s in leaf_slugs_list
                if slug_to_sem_neighbors.get(s) and slug_to_sem_l1.get(s)][:3]
    for ex in examples:
        g = [(s, round(sim, 2)) for s, sim in slug_to_sem_neighbors[ex][:2]]
        l = [(s, round(sim, 2)) for s, sim in slug_to_sem_l1[ex][:2]]
        print(f"    {ex!r:28} global={g}  L1={l}")

    return {
        "all_tags": all_tags,
        "all_tag_ids": all_tag_ids,
        "slug_to_id": slug_to_id,
        "l1_to_leaf": l1_to_leaf,
        "l2_to_leaf": l2_to_leaf,
        "slug_to_l2": slug_to_l2,
        "cooc_by_slug": cooc_by_slug,
        "slug_to_l2_siblings": slug_to_l2_siblings,
        "slug_to_sem_neighbors": slug_to_sem_neighbors,
        "slug_to_sem_l1": slug_to_sem_l1,
        "SEMTAG_MIN_SIM": SEMTAG_MIN_SIM,
    }


# ─────────────────────────────────────────────────────────────────────────────
# Generare useri sintetici (identic cu run_quality_eval.py)
# ─────────────────────────────────────────────────────────────────────────────

def generate_users(l1_to_leaf, rng):
    users = []
    for i in range(N_USERS):
        n_dom = int(rng.integers(2, 4))
        dominant = rng.choice(L1_SLUGS, size=n_dom, replace=False).tolist()
        latent_macro = {
            l1: float(rng.uniform(0.65, 0.92)) if l1 in dominant
                else float(rng.uniform(0.04, 0.18))
            for l1 in L1_SLUGS
        }
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
    return users


# ─────────────────────────────────────────────────────────────────────────────
# Metrica: recuperare profil
# ─────────────────────────────────────────────────────────────────────────────

def macro_recovery(rec_profile, latent_macro, l1_to_leaf):
    """Spearman la nivel macro (8 categorii L1)."""
    rec_vec, lat_vec = [], []
    for l1 in L1_SLUGS:
        leaves = l1_to_leaf.get(l1, [])
        rec_val = float(np.mean([rec_profile.get(s, 0.5) for s in leaves])) if leaves else 0.5
        rec_vec.append(rec_val)
        lat_vec.append(latent_macro.get(l1, 0.1))
    sp, _ = spearmanr(rec_vec, lat_vec)
    return float(sp) if not np.isnan(sp) else 0.0


def leaf_recovery(rec_profile, latent_leaf, l1_to_leaf):
    """
    Spearman la nivel frunza (toate cele 161 taguri-frunza).
    Masoara cat de bine e recuperata preferinta la nivel de detaliu.
    Metrica complementara macro_recovery — prior-ul ierarhic ajuta
    in special aceasta metrica (macro e deja relativ stabil din
    putinele observatii directe).
    """
    all_leaves = [s for leaves in l1_to_leaf.values() for s in leaves]
    rec = [rec_profile.get(s, 0.5) for s in all_leaves]
    lat = [latent_leaf.get(s, 0.0) for s in all_leaves]
    sp, _ = spearmanr(rec, lat)
    return float(sp) if not np.isnan(sp) else 0.0


# ─────────────────────────────────────────────────────────────────────────────
# Varianta 1 — Baseline (quiz curent, fara imbunatatiri)
# ─────────────────────────────────────────────────────────────────────────────

def quiz_baseline(latent_leaf, l1_to_leaf, rng):
    """Quiz Bayesian standard — replica simulate_quiz din run_quality_eval.py."""
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
        prob_right = 1.0 / (1.0 + math.exp(-5.0 * (lat - 0.5)))
        delta = RIGHT_WEIGHT if rng.random() < prob_right else LEFT_WEIGHT
        adjust_tag_score(tag_scores, slug, delta, bayesian=True)
        if len(seen) >= MIN_CARDS and compute_entropy(tag_scores) < 1.0:
            break

    return tag_scores


# ─────────────────────────────────────────────────────────────────────────────
# Varianta 2 — + Prior ierarhic
# ─────────────────────────────────────────────────────────────────────────────

def apply_prior(tag_scores, l1_to_leaf, strength=PRIOR_DEFAULT):
    """
    Post-procesare: pentru fiecare frunza nevazuta, estimeaza scorul
    din agregatul L1 al frunzelor vazute din aceeasi categorie.

    Formula: prior(slug) = 0.5 + strength × (l1_agg − 0.5)

    Independenta: nu foloseste niciodata scorul sistemului de recomandare.
    Foloseste doar scorul agregat al categoriei parinte, calculat din
    swipe-urile reale ale userului.
    """
    result = dict(tag_scores)
    for l1, leaves in l1_to_leaf.items():
        observed = [tag_scores[s] for s in leaves if s in tag_scores]
        if not observed:
            continue
        l1_agg = float(np.mean(observed))
        for slug in leaves:
            if slug not in result:
                result[slug] = 0.5 + strength * (l1_agg - 0.5)
    return result


def quiz_with_prior(latent_leaf, l1_to_leaf, rng, strength=PRIOR_DEFAULT):
    tag_scores = quiz_baseline(latent_leaf, l1_to_leaf, rng)
    return apply_prior(tag_scores, l1_to_leaf, strength)


# ─────────────────────────────────────────────────────────────────────────────
# Varianta 3 — + Co-aparitie proxy (stand-in pentru CLIP multi-tag)
# ─────────────────────────────────────────────────────────────────────────────

def quiz_with_cooc(latent_leaf, l1_to_leaf, cooc_by_slug, rng):
    """
    Quiz cu update multi-tag bazat pe co-aparitie in attraction_tags.

    La fiecare swipe pe tagul T:
      - T primeste delta complet (RIGHT_WEIGHT sau LEFT_WEIGHT)
      - Tagurile cu Jaccard(T, T') >= COOC_THRESHOLD primesc delta × COOC_WEIGHT

    Rationale: tagurile care co-apar frecvent in atractii sunt semantic
    apropiate — similar cu ce ar detecta CLIP din imagini.
    Aceasta este o aproximare structurala, nu CLIP real.
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
        prob_right = 1.0 / (1.0 + math.exp(-5.0 * (lat - 0.5)))
        delta = RIGHT_WEIGHT if rng.random() < prob_right else LEFT_WEIGHT

        # Update primar
        adjust_tag_score(tag_scores, slug, delta, bayesian=True)

        # Update secundar: taguri intra-L1 cu co-aparitie (proxy CLIP)
        # Formula: delta_secundar = delta × COOC_WEIGHT × min(jaccard, 1.0)
        # NU amplificam dincolo de COOC_WEIGHT — semnalul secundar e intotdeauna
        # mai slab decat cel primar
        for related_slug, jaccard in cooc_by_slug.get(slug, []):
            if related_slug not in seen:
                secondary_delta = delta * COOC_WEIGHT * min(1.0, jaccard)
                adjust_tag_score(tag_scores, related_slug, secondary_delta, bayesian=True)

        if len(seen) >= MIN_CARDS and compute_entropy(tag_scores) < 1.0:
            break

    return tag_scores


# ─────────────────────────────────────────────────────────────────────────────
# Varianta 4 — + Prior + Co-aparitie (combinat)
# ─────────────────────────────────────────────────────────────────────────────

def quiz_full_phase1(latent_leaf, l1_to_leaf, cooc_by_slug, rng, strength=PRIOR_DEFAULT):
    tag_scores = quiz_with_cooc(latent_leaf, l1_to_leaf, cooc_by_slug, rng)
    return apply_prior(tag_scores, l1_to_leaf, strength)


# ─────────────────────────────────────────────────────────────────────────────
# Varianta 5 — Multi-tag imagine (simulare CLIP cu L2-siblings)
# ─────────────────────────────────────────────────────────────────────────────

# Ponderi pentru tagurile secundare ale imaginii
# T1 (tag principal):  1.00 × delta  — domina imaginea
# T2 (primul sibling): 0.65 × delta  — vizibil clar in imagine
# T3 (al doilea):      0.45 × delta  — prezent dar mai putin proeminent
MULTITAG_WEIGHTS = [1.0, 0.65, 0.45]


def quiz_multitag(latent_leaf, l1_to_leaf, slug_to_l2_siblings, rng):
    """
    Simulare quiz cu imagine multi-tag (proxy CLIP bazat pe L2-siblings).

    Fiecare card = o imagine asociata cu tagul primar T1 + pana la 2
    sibling-uri L2 (T2, T3).

    Swipe-ul userului se bazeaza pe media latenta a TUTUROR tagurilor
    vizibile in imagine (nu doar T1) — simuland ca userul reactioneaza
    la imaginea ca intreg, nu la un concept abstract.

    Diferenta fata de cooc:
    - L2-siblings sunt semantic similare prin STRUCTURA (acelasi sub-nod)
    - cooc era statistica (co-aparitie in atractii = co-locatie geografica)
    - Aceasta simulare aproximeaza ce ar face CLIP pe imaginile reale
    """
    tag_scores = {}
    seen = set()
    n_cards = int(rng.integers(MIN_CARDS, MAX_CARDS + 1))
    cycle_pos = 0

    for _ in range(n_cards):
        # Selectie tag primar (round-robin L1)
        t1 = None
        for _ in range(len(L1_SLUGS)):
            l1 = L1_SLUGS[cycle_pos % len(L1_SLUGS)]
            cycle_pos += 1
            cands = [s for s in l1_to_leaf.get(l1, []) if s not in seen]
            if cands:
                t1 = cands[int(rng.integers(0, len(cands)))]
                break
        if t1 is None:
            break
        seen.add(t1)

        # Taguri secundare: pana la 2 L2-siblings nevazuti
        siblings = [s for s in slug_to_l2_siblings.get(t1, []) if s not in seen]
        image_tags = [t1] + siblings[:2]   # maxim 3 taguri per imagine

        # Swipe bazat pe media latenta a TUTUROR tagurilor din imagine
        lat_mean = float(np.mean([latent_leaf.get(s, 0.08) for s in image_tags]))
        prob_right = 1.0 / (1.0 + math.exp(-5.0 * (lat_mean - 0.5)))
        swipe_right = rng.random() < prob_right

        # Update cu ponderi descrescatoare
        for i, slug in enumerate(image_tags):
            weight = MULTITAG_WEIGHTS[i] if i < len(MULTITAG_WEIGHTS) else 0.3
            delta = (RIGHT_WEIGHT if swipe_right else LEFT_WEIGHT) * weight
            adjust_tag_score(tag_scores, slug, delta, bayesian=True)

        if len(seen) >= MIN_CARDS and compute_entropy(tag_scores) < 1.0:
            break

    return tag_scores


def quiz_multitag_with_prior(latent_leaf, l1_to_leaf, slug_to_l2_siblings, rng,
                              strength=PRIOR_DEFAULT):
    tag_scores = quiz_multitag(latent_leaf, l1_to_leaf, slug_to_l2_siblings, rng)
    return apply_prior(tag_scores, l1_to_leaf, strength)


# ─────────────────────────────────────────────────────────────────────────────
# Varianta 6 — Sentence Transformer semantic neighbors
# ─────────────────────────────────────────────────────────────────────────────

# Ponderi pentru vecini semantici (proportionale cu similaritatea)
# T1 (primar):  delta complet
# T_i (vecin):  delta × similarity_i  (direct proportional cu sim cosinus)
# Avantaj fata de L2-siblings: distinge "hiking" de "birdwatching" chiar daca
# sunt in acelasi L2, pentru ca au embeddings diferite semantic.


def quiz_semtag(latent_leaf, l1_to_leaf, slug_to_sem_neighbors, rng):
    """
    Quiz cu update semantic multi-tag bazat pe sentence transformers.

    Pentru fiecare card cu tagul primar T1:
      - Identifica top-k vecini semantici ai lui T1 din embedding space
      - Swipe-ul se bazeaza pe media latenta a primelor 3 taguri vizibile
      - Updateaza T1 si vecinii semantici cu delta ponderat de similaritatea cosinus

    Diferenta fata de L2-siblings:
      - L2-siblings: structurala (acelasi sub-nod ierarhic)
      - Semantic neighbors: intelege sensul textului (e.g. "spa" aproape de
        "yoga-retreats" chiar daca sunt in L2-uri diferite)
      - Distinge "hiking" de "birdwatching" desi ambele sunt in nature-outdoors
    """
    tag_scores = {}
    seen = set()
    n_cards = int(rng.integers(MIN_CARDS, MAX_CARDS + 1))
    cycle_pos = 0

    for _ in range(n_cards):
        t1 = None
        for _ in range(len(L1_SLUGS)):
            l1 = L1_SLUGS[cycle_pos % len(L1_SLUGS)]
            cycle_pos += 1
            cands = [s for s in l1_to_leaf.get(l1, []) if s not in seen]
            if cands:
                t1 = cands[int(rng.integers(0, len(cands)))]
                break
        if t1 is None:
            break
        seen.add(t1)

        # Vecini semantici (top-3 nevazuti)
        sem_nbrs = [
            (s, sim) for s, sim in slug_to_sem_neighbors.get(t1, [])
            if s not in seen
        ][:3]

        # Tagurile "vizibile" in imaginea simulata
        image_tags = [(t1, 1.0)] + sem_nbrs   # (slug, similarity_weight)

        # Swipe bazat pe media latenta a primelor 3 taguri
        lat_mean = float(np.mean([
            latent_leaf.get(s, 0.08) for s, _ in image_tags[:3]
        ]))
        prob_right = 1.0 / (1.0 + math.exp(-5.0 * (lat_mean - 0.5)))
        swipe_right = rng.random() < prob_right
        base_delta = RIGHT_WEIGHT if swipe_right else LEFT_WEIGHT

        # Update: delta ponderat de similaritatea semantica
        for slug, sim_weight in image_tags:
            delta = base_delta * sim_weight
            adjust_tag_score(tag_scores, slug, delta, bayesian=True)

        if len(seen) >= MIN_CARDS and compute_entropy(tag_scores) < 1.0:
            break

    return tag_scores


def quiz_semtag_with_prior(latent_leaf, l1_to_leaf, slug_to_sem_neighbors, rng,
                            strength=PRIOR_DEFAULT):
    tag_scores = quiz_semtag(latent_leaf, l1_to_leaf, slug_to_sem_neighbors, rng)
    return apply_prior(tag_scores, l1_to_leaf, strength)


# ─────────────────────────────────────────────────────────────────────────────
# Varianta 7 — SemTag filtrat L1 (semantic + restrictie categorie)
# ─────────────────────────────────────────────────────────────────────────────

def quiz_semtag_l1(latent_leaf, l1_to_leaf, slug_to_sem_l1, rng):
    """
    Vecini semantici RESTRICTIONATI la acelasi L1.

    Combina avantajele:
    - Discriminare semantica in interiorul categoriei (ST intelege ca
      'hiking' != 'birdwatching' chiar daca ambele sunt in nature-outdoors)
    - Fara zgomot cross-categorie (arcade-bars nu contamineaza food-drink)

    Aceasta e varianta corecta pentru simularea imaginilor CLIP multi-tag:
    o imagine de hiking arata hiking + forest-bathing + contemplative-nature,
    nu hiking + restaurant + beach-club.
    """
    tag_scores = {}
    seen = set()
    n_cards = int(rng.integers(MIN_CARDS, MAX_CARDS + 1))
    cycle_pos = 0

    for _ in range(n_cards):
        t1 = None
        for _ in range(len(L1_SLUGS)):
            l1 = L1_SLUGS[cycle_pos % len(L1_SLUGS)]
            cycle_pos += 1
            cands = [s for s in l1_to_leaf.get(l1, []) if s not in seen]
            if cands:
                t1 = cands[int(rng.integers(0, len(cands)))]
                break
        if t1 is None:
            break
        seen.add(t1)

        sem_nbrs = [
            (s, sim) for s, sim in slug_to_sem_l1.get(t1, [])
            if s not in seen
        ][:3]

        image_tags = [(t1, 1.0)] + sem_nbrs
        lat_mean = float(np.mean([latent_leaf.get(s, 0.08) for s, _ in image_tags[:3]]))
        prob_right = 1.0 / (1.0 + math.exp(-5.0 * (lat_mean - 0.5)))
        base_delta = RIGHT_WEIGHT if rng.random() < prob_right else LEFT_WEIGHT

        for slug, sim_weight in image_tags:
            adjust_tag_score(tag_scores, slug, base_delta * sim_weight, bayesian=True)

        if len(seen) >= MIN_CARDS and compute_entropy(tag_scores) < 1.0:
            break

    return tag_scores


def quiz_semtag_l1_with_prior(latent_leaf, l1_to_leaf, slug_to_sem_l1, rng,
                               strength=PRIOR_DEFAULT):
    tag_scores = quiz_semtag_l1(latent_leaf, l1_to_leaf, slug_to_sem_l1, rng)
    return apply_prior(tag_scores, l1_to_leaf, strength)


# ─────────────────────────────────────────────────────────────────────────────
# Rulare comparatie
# ─────────────────────────────────────────────────────────────────────────────

def run_comparison(users, data):
    print(f"\nComparatie Profile Recovery pe {N_USERS} useri (SEED={SEED})...")
    print(f"  Prior strength = {PRIOR_DEFAULT}  |  Cooc threshold = {COOC_THRESHOLD}  |  Cooc weight = {COOC_WEIGHT}\n")

    variants = [
        "baseline", "prior",
        "cooc", "prior+cooc",
        "multitag", "multitag+prior",
        "semtag", "semtag+prior",
        "semtag_l1", "semtag_l1+prior",
    ]
    rows = []

    for user in users:
        uid = user["user_id"]

        scores = {
            "baseline":
                quiz_baseline(user["latent_leaf"], data["l1_to_leaf"],
                              np.random.default_rng(SEED + uid)),
            "prior":
                quiz_with_prior(user["latent_leaf"], data["l1_to_leaf"],
                                np.random.default_rng(SEED + uid)),
            "cooc":
                quiz_with_cooc(user["latent_leaf"], data["l1_to_leaf"],
                               data["cooc_by_slug"], np.random.default_rng(SEED + uid)),
            "prior+cooc":
                quiz_full_phase1(user["latent_leaf"], data["l1_to_leaf"],
                                 data["cooc_by_slug"], np.random.default_rng(SEED + uid)),
            "multitag":
                quiz_multitag(user["latent_leaf"], data["l1_to_leaf"],
                              data["slug_to_l2_siblings"], np.random.default_rng(SEED + uid)),
            "multitag+prior":
                quiz_multitag_with_prior(user["latent_leaf"], data["l1_to_leaf"],
                                         data["slug_to_l2_siblings"],
                                         np.random.default_rng(SEED + uid)),
            "semtag":
                quiz_semtag(user["latent_leaf"], data["l1_to_leaf"],
                            data["slug_to_sem_neighbors"], np.random.default_rng(SEED + uid)),
            "semtag+prior":
                quiz_semtag_with_prior(user["latent_leaf"], data["l1_to_leaf"],
                                       data["slug_to_sem_neighbors"],
                                       np.random.default_rng(SEED + uid)),
            "semtag_l1":
                quiz_semtag_l1(user["latent_leaf"], data["l1_to_leaf"],
                               data["slug_to_sem_l1"], np.random.default_rng(SEED + uid)),
            "semtag_l1+prior":
                quiz_semtag_l1_with_prior(user["latent_leaf"], data["l1_to_leaf"],
                                          data["slug_to_sem_l1"],
                                          np.random.default_rng(SEED + uid)),
        }

        row = {"user_id": uid, "dominant": "|".join(user["dominant"])}
        for v, tag_scores in scores.items():
            row[f"pr_macro_{v}"] = round(macro_recovery(tag_scores, user["latent_macro"], data["l1_to_leaf"]), 4)
            row[f"pr_leaf_{v}"]  = round(leaf_recovery(tag_scores, user["latent_leaf"], data["l1_to_leaf"]), 4)
            row[f"n_tags_{v}"]   = sum(1 for s in tag_scores if tag_scores[s] != 0.5)
        rows.append(row)

    df = pd.DataFrame(rows)

    # Statistici macro
    print(f"\n  MACRO recovery (Spearman pe 8 categorii L1):")
    print(f"  {'Varianta':<16} {'Media':>8} {'Std':>8} {'Tags obs.':>10}")
    print("  " + "-" * 44)
    for v in variants:
        col = f"pr_macro_{v}"
        pr = df[col]
        tags = df[f"n_tags_{v}"]
        print(f"  {v:<16} {pr.mean():>8.4f} {pr.std():>8.4f} {tags.mean():>10.1f}")

    # Statistici leaf
    print(f"\n  LEAF recovery (Spearman pe {sum(len(l) for l in data['l1_to_leaf'].values())} taguri-frunza):")
    print(f"  {'Varianta':<16} {'Media':>8} {'Std':>8}")
    print("  " + "-" * 36)
    for v in variants:
        col = f"pr_leaf_{v}"
        pr = df[col]
        print(f"  {v:<16} {pr.mean():>8.4f} {pr.std():>8.4f}")

    # Delta fata de baseline (leaf recovery, mai relevant)
    print(f"\n  Delta LEAF recovery fata de baseline:")
    for v in ["prior", "cooc", "prior+cooc"]:
        delta = df[f"pr_leaf_{v}"] - df["pr_leaf_baseline"]
        try:
            _, pval = wilcoxon(df[f"pr_leaf_{v}"], df["pr_leaf_baseline"], alternative="greater")
        except Exception:
            pval = float("nan")
        sig = "**" if pval < 0.05 else ("*" if pval < 0.10 else "ns")
        print(f"  {v:<16}: {delta.mean():+.4f} (p={pval:.4f} {sig})")

    print(f"\n  Delta MACRO recovery fata de baseline:")
    for v in ["prior", "cooc", "prior+cooc"]:
        delta = df[f"pr_macro_{v}"] - df["pr_macro_baseline"]
        try:
            _, pval = wilcoxon(df[f"pr_macro_{v}"], df["pr_macro_baseline"], alternative="greater")
        except Exception:
            pval = float("nan")
        sig = "**" if pval < 0.05 else ("*" if pval < 0.10 else "ns")
        print(f"  {v:<16}: {delta.mean():+.4f} (p={pval:.4f} {sig})")

    return df


# ─────────────────────────────────────────────────────────────────────────────
# Tuning prior strength
# ─────────────────────────────────────────────────────────────────────────────

def tune_prior_strength(users, data):
    print(f"\nTuning prior strength {PRIOR_STRENGTHS}...")
    results = {}
    for strength in PRIOR_STRENGTHS:
        prs = []
        for user in users:
            tag_scores = quiz_baseline(user["latent_leaf"], data["l1_to_leaf"],
                                       np.random.default_rng(SEED + user["user_id"]))
            tag_scores = apply_prior(tag_scores, data["l1_to_leaf"], strength)
            prs.append(macro_recovery(tag_scores, user["latent_macro"], data["l1_to_leaf"]))
        results[strength] = float(np.mean(prs))
        print(f"  strength={strength:.2f} -> PR medie = {results[strength]:.4f}")
    best = max(results, key=results.get)
    print(f"  Optim: strength={best} -> {results[best]:.4f}")
    return results, best


# ─────────────────────────────────────────────────────────────────────────────
# Grafice
# ─────────────────────────────────────────────────────────────────────────────

def make_plots(df, prior_tuning, best_strength):
    variants = [
        "baseline", "prior",
        "multitag", "multitag+prior",
        "semtag", "semtag+prior",
        "semtag_l1", "semtag_l1+prior",
    ]
    labels = [
        "Baseline", "+Prior",
        "+L2-sib", "+L2-sib\n+Prior",
        "+SemTag\n(global)", "+SemTag\n+Prior",
        "+SemTag\n(L1)", "+SemTag\n(L1)+Prior",
    ]
    colors = [
        "#9E9E9E", "#FF9800",
        "#2196F3", "#64B5F6",
        "#E53935", "#EF9A9A",
        "#7B1FA2", "#4CAF50",
    ]

    macro_means = [df[f"pr_macro_{v}"].mean() for v in variants]
    macro_stds  = [df[f"pr_macro_{v}"].std()  for v in variants]
    leaf_means  = [df[f"pr_leaf_{v}"].mean()  for v in variants]
    leaf_stds   = [df[f"pr_leaf_{v}"].std()   for v in variants]

    fig, axes = plt.subplots(1, 2, figsize=(14, 5))

    for ax, means, stds, title, ylabel in [
        (axes[0], macro_means, macro_stds,
         "MACRO recovery (8 L1 categorii)",    "Spearman macro"),
        (axes[1], leaf_means,  leaf_stds,
         "LEAF recovery (161 taguri-frunza)",  "Spearman leaf"),
    ]:
        bars = ax.bar(labels, means, yerr=stds, capsize=4,
                      color=colors, edgecolor="black", linewidth=0.5)
        ax.set_title(title)
        ax.set_ylabel(ylabel)
        ax.set_ylim(0, min(1.0, max(means) * 1.40))
        ax.axhline(means[0], color="gray", linewidth=0.8, linestyle="--", alpha=0.5)
        for bar, m, s in zip(bars, means, stds):
            ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + s + 0.01,
                    f"{m:.3f}", ha="center", va="bottom", fontsize=8, fontweight="bold")

    plt.suptitle("Comparatie variante quiz — Prior Ierarhic vs Multi-tag (L2 siblings)", fontsize=11)
    plt.tight_layout()
    plt.savefig(os.path.join(RESULTS_DIR, "phase1_profile_recovery.png"), dpi=150)
    plt.close()

    # ── 3. Prior strength tuning ──────────────────────────────────────────────
    if prior_tuning:
        fig, ax = plt.subplots(figsize=(6, 4))
        strengths = list(prior_tuning.keys())
        pr_vals = list(prior_tuning.values())
        ax.plot(strengths, pr_vals, "o-", color="#FF9800", linewidth=2, markersize=8)
        ax.axvline(best_strength, color="red", linewidth=1, linestyle="--",
                   label=f"Optim: {best_strength}")
        ax.set_xlabel("Prior strength (alpha)")
        ax.set_ylabel("Profile Recovery medie")
        ax.set_title("Tuning prior strength")
        ax.legend()
        plt.tight_layout()
        plt.savefig(os.path.join(RESULTS_DIR, "phase1_prior_tuning.png"), dpi=150)
        plt.close()

    print(f"\n  Salvat: phase1_profile_recovery.png")
    if prior_tuning:
        print(f"  Salvat: phase1_prior_tuning.png")


# ─────────────────────────────────────────────────────────────────────────────
# Analiza calitativa: ce taguri sunt mai bine acoperite
# ─────────────────────────────────────────────────────────────────────────────

def analyze_coverage(users, data):
    """Compara cate taguri sunt actualizate (diferite de 0.5) per varianta."""
    print(f"\nAcoperire taguri (taguri cu scor != 0.5):")
    for v, quiz_fn in [
        ("baseline",   lambda u, r: quiz_baseline(u["latent_leaf"], data["l1_to_leaf"], r)),
        ("prior",      lambda u, r: quiz_with_prior(u["latent_leaf"], data["l1_to_leaf"], r)),
        ("cooc",       lambda u, r: quiz_with_cooc(u["latent_leaf"], data["l1_to_leaf"], data["cooc_by_slug"], r)),
        ("prior+cooc", lambda u, r: quiz_full_phase1(u["latent_leaf"], data["l1_to_leaf"], data["cooc_by_slug"], r)),
    ]:
        coverages = []
        for user in users:
            rng_u = np.random.default_rng(SEED + user["user_id"])
            scores = quiz_fn(user, rng_u)
            n_covered = sum(1 for s, sc in scores.items() if sc != 0.5)
            coverages.append(n_covered)
        n_leaf = sum(len(v_) for v_ in data["l1_to_leaf"].values())
        mean_cov = np.mean(coverages)
        print(f"  {v:<16}: {mean_cov:.1f}/{n_leaf} taguri acoperite ({100*mean_cov/n_leaf:.1f}%)")


# ─────────────────────────────────────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────────────────────────────────────

def main():
    print("\n" + "=" * 62)
    print("  Faza 1 Test — Prior Ierarhic + Co-aparitie Proxy")
    print(f"  SEED={SEED} | N_USERS={N_USERS}")
    print("=" * 62)

    db = SessionLocal()
    try:
        data = load_data(db)
    finally:
        db.close()

    users = generate_users(data["l1_to_leaf"], _rng)

    # Tuning prior strength
    prior_tuning, best_strength = tune_prior_strength(users, data)

    # Comparatie principala
    df = run_comparison(users, data)

    # Analiza acoperire
    analyze_coverage(users, data)

    # Salvare + grafice
    df.to_csv(os.path.join(RESULTS_DIR, "phase1_comparison.csv"), index=False)
    make_plots(df, prior_tuning, best_strength)

    # Sumar final
    b_macro = df["pr_macro_baseline"].mean()
    b_leaf  = df["pr_leaf_baseline"].mean()

    print(f"\n{'='*62}")
    print(f"  REZULTAT FINAL — comparatie toate variantele")
    print(f"{'='*62}")
    print(f"  {'Varianta':<20} {'Macro':>8} {'dMacro':>8} {'Leaf':>8} {'dLeaf':>8}")
    print(f"  {'-'*56}")
    for v in ["baseline", "prior", "cooc", "prior+cooc",
              "multitag", "multitag+prior",
              "semtag", "semtag+prior",
              "semtag_l1", "semtag_l1+prior"]:
        macro = df[f"pr_macro_{v}"].mean()
        leaf  = df[f"pr_leaf_{v}"].mean()
        print(f"  {v:<20} {macro:>8.4f} {macro-b_macro:>+8.4f} {leaf:>8.4f} {leaf-b_leaf:>+8.4f}")
    print(f"{'='*62}")

    print(f"\nFisiere generate:")
    for fname in ["phase1_comparison.csv", "phase1_profile_recovery.png", "phase1_prior_tuning.png"]:
        fpath = os.path.join(RESULTS_DIR, fname)
        if os.path.exists(fpath):
            print(f"  {fname}  ({os.path.getsize(fpath):,} bytes)")


if __name__ == "__main__":
    main()
