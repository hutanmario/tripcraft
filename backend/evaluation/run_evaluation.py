#!/usr/bin/env python3
"""
backend/evaluation/run_evaluation.py
=====================================
Evaluare empirica a formulei de scorare TripCraft:
    final = 0.70 * cosinus + 0.20 * popularitate + 0.10 * raritate

Rulare (din directorul backend/):
    python -m evaluation.run_evaluation

Rezultatele se salveaza in backend/evaluation/results/.
Codul de productie nu este modificat — se refolosesc formulele din
itinerary_scorer.py (liniile 62-136).
"""

import sys
import os
import math
import random
import logging

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from scipy.stats import spearmanr, kendalltau
from sqlalchemy import select

# ── Seed reproductibilitate ────────────────────────────────────────────────────
SEED = 42
random.seed(SEED)
np.random.seed(SEED)

# ── Path setup: rulam din backend/ ────────────────────────────────────────────
_BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _BACKEND_DIR not in sys.path:
    sys.path.insert(0, _BACKEND_DIR)

from app.database import SessionLocal
from app.models import Tag, QuizV4Session
from app.models.geography import Attraction, attraction_tags
# Refolosim direct functiile IDF din productie (itinerary_scorer.py)
from app.services.itinerary_scorer import get_attraction_tag_idf, _effective_idf_attr

RESULTS_DIR = os.path.join(os.path.dirname(__file__), "results")
os.makedirs(RESULTS_DIR, exist_ok=True)

logging.basicConfig(level=logging.WARNING)
log = logging.getLogger("eval")
log.setLevel(logging.INFO)
_handler = logging.StreamHandler()
_handler.setFormatter(logging.Formatter("%(message)s"))
log.addHandler(_handler)

# ── Configuratii ponderi ─────────────────────────────────────────────────────
WEIGHT_CONFIGS = {
    "productie":    (0.70, 0.20, 0.10),
    "doar_cosinus": (1.00, 0.00, 0.00),
    "fara_pop":     (0.78, 0.00, 0.22),
    "pop_ridicata": (0.50, 0.40, 0.10),
    "raritate_rid": (0.50, 0.20, 0.30),
}

# Macro-categorii L1 din quiz_engine.py
L1_SLUGS = [
    "nature-outdoors",
    "culture-history",
    "nightlife-social",
    "adventure-active",
    "food-drink",
    "wellness-slow",
    "urban-modern",
    "family-comfort",
]

SYNTHETIC_LABELS = {
    "nature-outdoors":   "Naturalist",
    "culture-history":   "Culturist",
    "nightlife-social":  "Nocturn",
    "adventure-active":  "Aventurier",
    "food-drink":        "Gastronomic",
    "wellness-slow":     "Wellbeing",
    "urban-modern":      "Urban",
    "family-comfort":    "Familie",
}


# ─────────────────────────────────────────────────────────────────────────────
# Functii de calcul componente
# ─────────────────────────────────────────────────────────────────────────────

def preload_attraction_tags(attraction_ids, db):
    """Preincarca toate randurile din attraction_tags o singura data."""
    if not attraction_ids:
        return {}
    all_rows = db.execute(
        select(attraction_tags).where(
            attraction_tags.c.attraction_id.in_(attraction_ids)
        )
    ).fetchall()
    tags_by_attraction = {}
    for row in all_rows:
        tags_by_attraction.setdefault(row.attraction_id, []).append(row)
    return tags_by_attraction


def _cosine_and_popularity(attr, user_vector, all_tag_ids, idx_map,
                            tags_by_attraction, tags_counts, max_tags):
    """Calculeaza cosinus si popularitate (identice in ambele versiuni)."""
    attr_vec = np.zeros(len(all_tag_ids))
    attr_tag_ids = set()
    attr_scores_on_tags = {}
    for row in tags_by_attraction.get(attr.id, []):
        if row.tag_id in idx_map:
            score_val = float(row.score or 1.0)
            attr_vec[idx_map[row.tag_id]] = score_val
            attr_tag_ids.add(row.tag_id)
            attr_scores_on_tags[row.tag_id] = score_val

    norm = np.linalg.norm(attr_vec)
    if norm > 0:
        attr_vec /= norm

    cosine = max(0.0, float(np.dot(user_vector, attr_vec)))
    nr_tags = tags_counts.get(attr.id, 0)
    popularity = (
        math.log(1 + nr_tags) / math.log(1 + max_tags) if max_tags > 0 else 0.0
    )
    return cosine, popularity, attr_tag_ids, attr_scores_on_tags


def compute_components_old(attractions, user_vector, all_tag_ids, user_raw_scores,
                           tags_by_attraction):
    """
    Formula VECHE de raritate: 1/(count+1), prag 0.6, numitor=len(user_high_score_tags).
    Pastrata doar pentru comparatia inainte/dupa in evaluare.
    """
    idx_map = {tid: i for i, tid in enumerate(all_tag_ids)}
    tags_counts = {aid: len(rows) for aid, rows in tags_by_attraction.items()}
    max_tags = max(tags_counts.values(), default=1)

    tag_attraction_count = {}
    for rows in tags_by_attraction.values():
        for row in rows:
            tag_attraction_count[row.tag_id] = tag_attraction_count.get(row.tag_id, 0) + 1
    tag_rarity = {tid: 1.0 / (c + 1) for tid, c in tag_attraction_count.items()}

    user_high = {tid: s for tid, s in (user_raw_scores or {}).items() if s > 0.6}

    records = []
    for attr in attractions:
        cosine, popularity, attr_tag_ids, _ = _cosine_and_popularity(
            attr, user_vector, all_tag_ids, idx_map, tags_by_attraction, tags_counts, max_tags
        )
        rarity = 0.0
        if user_high:
            common = attr_tag_ids & set(user_high.keys())
            if common:
                rarity = sum(user_high[t] * tag_rarity.get(t, 0.0) for t in common) / len(user_high)
        rarity = min(1.0, rarity)
        records.append({
            "attraction_id": attr.id, "name": attr.name,
            "category": attr.category or "",
            "cosine": cosine, "popularity": popularity, "rarity": rarity,
        })
    return records


def compute_components(attractions, user_vector, all_tag_ids, user_raw_scores,
                       tags_by_attraction, tag_idf):
    """
    Formula NOUA de raritate: IDF smooth + effective_idf, prag 0.4,
    numitor = len(common_tags).

    Replica exact itinerary_scorer.py dupa redesign (liniile 118-146):
      rarity = mean( user_score[t] * (effective_idf(idf[t], attr_score[t]) - 1.0)
                     for t in common_tags )
    unde idf vine din get_attraction_tag_idf (IDF_ALPHA=0.5, cap=2.0),
    consistent cu country_recommender.py liniile 204-209 si 347-348.
    """
    idx_map = {tid: i for i, tid in enumerate(all_tag_ids)}
    tags_counts = {aid: len(rows) for aid, rows in tags_by_attraction.items()}
    max_tags = max(tags_counts.values(), default=1)

    # prag coborat: IDF penalizeaza natural tagurile comune
    user_high = {tid: s for tid, s in (user_raw_scores or {}).items() if s > 0.4}

    records = []
    for attr in attractions:
        cosine, popularity, attr_tag_ids, attr_scores_on_tags = _cosine_and_popularity(
            attr, user_vector, all_tag_ids, idx_map, tags_by_attraction, tags_counts, max_tags
        )
        rarity = 0.0
        if user_high:
            common = attr_tag_ids & set(user_high.keys())
            if common:
                rarity = sum(
                    user_high[t] * (
                        _effective_idf_attr(tag_idf.get(t, 1.0), attr_scores_on_tags.get(t, 1.0)) - 1.0
                    )
                    for t in common
                ) / len(common)
        records.append({
            "attraction_id": attr.id, "name": attr.name,
            "category": attr.category or "",
            "cosine": cosine, "popularity": popularity, "rarity": rarity,
        })
    return records


def build_user_vector(profile_dict, all_tag_ids, all_tags):
    """
    Construieste vectorul normalizat si raw_scores din profile_dict (slug->float).
    Replica get_user_tag_vector din itinerary_scorer.py (liniile 21-42) fara DB.
    """
    slug_to_id = {t.slug: t.id for t in all_tags}
    raw_scores = {tid: 0.0 for tid in all_tag_ids}
    for slug, score in profile_dict.items():
        tid = slug_to_id.get(slug)
        if tid is not None and tid in raw_scores:
            raw_scores[tid] = float(score)

    vec = np.array([raw_scores[tid] for tid in all_tag_ids], dtype=float)
    norm = np.linalg.norm(vec)
    normalized = vec / norm if norm > 0 else vec
    return normalized, raw_scores


def apply_weights(records, w_cos, w_pop, w_rar):
    """
    Aplica ponderile si returneaza lista ordonata descrescator dupa scorul final.
    Nu include budget_penalty — scopul e izolarea efectului celor 3 componente.
    """
    result = []
    for r in records:
        final = w_cos * r["cosine"] + w_pop * r["popularity"] + w_rar * r["rarity"]
        result.append({**r, "final": final})
    result.sort(key=lambda x: x["final"], reverse=True)
    return result


def overlap_at_k(sorted_ids_a, sorted_ids_b, k):
    a = set(sorted_ids_a[:k])
    b = set(sorted_ids_b[:k])
    return len(a & b) / k if k > 0 else 0.0


# ─────────────────────────────────────────────────────────────────────────────
# TASK 1: Incarcare date
# ─────────────────────────────────────────────────────────────────────────────

def task1_load_data(db):
    print("\n" + "=" * 62)
    print("TASK 1: Incarcare date din baza de date")
    print("=" * 62)

    # Toate tagurile (leaf + non-leaf) — consistent cu itinerary_builder.py:462
    # care face db.query(Tag).all()
    all_tags = db.query(Tag).all()
    all_tag_ids = [t.id for t in all_tags]
    n_leaf = sum(1 for t in all_tags if t.is_leaf)

    attractions = db.query(Attraction).all()

    print(f"  Atractii totale:    {len(attractions)}")
    print(f"  Etichete totale:    {len(all_tags)}")
    print(f"  Etichete-frunza:    {n_leaf}")

    return attractions, all_tag_ids, all_tags, n_leaf


# ─────────────────────────────────────────────────────────────────────────────
# TASK 2: Profiluri de utilizator
# ─────────────────────────────────────────────────────────────────────────────

def task2_load_profiles(db, all_tags):
    print("\n" + "=" * 62)
    print("TASK 2: Profiluri de utilizator")
    print("=" * 62)

    profiles = []

    # ── Profiluri reale din DB ────────────────────────────────────────────────
    real_sessions = (
        db.query(QuizV4Session)
        .filter(
            QuizV4Session.current_stage == "completed",
            QuizV4Session.final_profile.isnot(None),
        )
        .order_by(QuizV4Session.completed_at.desc())
        .limit(20)
        .all()
    )

    for sess in real_sessions:
        profile_data = sess.final_profile or sess.tag_scores or {}
        if profile_data:
            profiles.append({
                "id": f"real_{str(sess.id)[:8]}",
                "type": "real",
                "tag_scores": profile_data,
                "budget": sess.budget,
            })

    n_real = len(profiles)
    print(f"  Sesiuni completate gasite in DB:  {len(real_sessions)}")
    print(f"  Profiluri reale valide:           {n_real}")

    # ── Profiluri sintetice (cate unul per macro-categorie) ───────────────────
    # Construim maparea L1 -> sluguri frunza
    id_to_tag = {t.id: t for t in all_tags}
    slug_to_tag = {t.slug: t for t in all_tags}
    leaf_slugs = {t.slug for t in all_tags if t.is_leaf}

    l1_to_leaf = {}
    for l1_slug in L1_SLUGS:
        l1_tag = slug_to_tag.get(l1_slug)
        if l1_tag is None:
            l1_to_leaf[l1_slug] = set()
            continue

        featured = set()
        l2_tags = [t for t in all_tags if t.parent_id == l1_tag.id]
        for l2 in l2_tags:
            if l2.is_leaf:
                featured.add(l2.slug)
            l3_tags = [t for t in all_tags if t.parent_id == l2.id]
            for l3 in l3_tags:
                if l3.is_leaf:
                    featured.add(l3.slug)
        l1_to_leaf[l1_slug] = featured

    for l1_slug in L1_SLUGS:
        featured = l1_to_leaf.get(l1_slug, set())
        tag_scores = {}
        for slug in leaf_slugs:
            tag_scores[slug] = 0.85 if slug in featured else 0.10
        profiles.append({
            "id": f"synthetic_{l1_slug}",
            "type": "synthetic",
            "label": SYNTHETIC_LABELS.get(l1_slug, l1_slug),
            "l1": l1_slug,
            "tag_scores": tag_scores,
            "budget": None,
        })

    n_synthetic = len(profiles) - n_real
    print(f"  Profiluri sintetice construite:   {n_synthetic}")
    print(f"  TOTAL profiluri:                  {len(profiles)}")

    # Afisam sumar categorii per sintetic
    for l1_slug in L1_SLUGS:
        cnt = len(l1_to_leaf.get(l1_slug, set()))
        label = SYNTHETIC_LABELS.get(l1_slug, l1_slug)
        print(f"    [{label:<12}] {cnt:>3} frunze in '{l1_slug}'")

    return profiles


# ─────────────────────────────────────────────────────────────────────────────
# TASK 3: Analiza componentelor de scor
# ─────────────────────────────────────────────────────────────────────────────

def task3_component_analysis(attractions, all_tag_ids, all_tags, profiles, db):
    print("\n" + "=" * 62)
    print("TASK 3: Analiza componentelor de scor")
    print("=" * 62)

    tags_by_attraction = preload_attraction_tags([a.id for a in attractions], db)
    tag_idf = get_attraction_tag_idf(db)

    # ── Comparatie inainte / dupa redesign raritate ───────────────────────────
    print("\n  [Comparatie formula raritate: VECHE vs NOUA]")
    _sample_prof = profiles[0]
    _uv, _rs = build_user_vector(_sample_prof["tag_scores"], all_tag_ids, all_tags)
    _old = compute_components_old(attractions, _uv, all_tag_ids, _rs, tags_by_attraction)
    _new = compute_components(attractions, _uv, all_tag_ids, _rs, tags_by_attraction, tag_idf)
    for label, comps_list in [("VECHE", _old), ("NOUA ", _new)]:
        rar = np.array([c["rarity"] for c in comps_list])
        mean_v, std_v = rar.mean(), rar.std()
        cv_v = std_v / mean_v if mean_v > 0 else 0.0
        nonzero = np.sum(rar > 0)
        print(f"    [{label}] media={mean_v:.5f}  std={std_v:.5f}  CV={cv_v:.3f}  "
              f"atractii_cu_bonus={nonzero}/{len(rar)}")

    all_rows_per_component = {"cosine": [], "popularity": [], "rarity": []}
    detail_rows = []

    for prof in profiles:
        user_vector, raw_scores = build_user_vector(
            prof["tag_scores"], all_tag_ids, all_tags
        )
        comps = compute_components(
            attractions, user_vector, all_tag_ids, raw_scores, tags_by_attraction, tag_idf
        )
        for c in comps:
            all_rows_per_component["cosine"].append(c["cosine"])
            all_rows_per_component["popularity"].append(c["popularity"])
            all_rows_per_component["rarity"].append(c["rarity"])
            detail_rows.append({
                "profile_id": prof["id"],
                "profile_type": prof["type"],
                **c,
            })

    # Statistici per componenta
    stats = {}
    print(f"\n  {'Componenta':<14} {'Media':>8} {'Std':>8} {'Min':>8} {'Max':>8} {'CV':>8}")
    print("  " + "-" * 56)
    for comp_name, values in [
        ("cosinus",      all_rows_per_component["cosine"]),
        ("popularitate", all_rows_per_component["popularity"]),
        ("raritate",     all_rows_per_component["rarity"]),
    ]:
        arr = np.array(values)
        mean = arr.mean()
        std  = arr.std()
        cv   = std / mean if mean > 0 else 0.0
        stats[comp_name] = {
            "media": mean, "std": std,
            "min": arr.min(), "max": arr.max(), "cv": cv,
        }
        print(
            f"  {comp_name:<14} {mean:>8.4f} {std:>8.4f} "
            f"{arr.min():>8.4f} {arr.max():>8.4f} {cv:>8.4f}"
        )

    # Salvare CSV cu toate componentele
    df = pd.DataFrame(detail_rows)
    df.to_csv(os.path.join(RESULTS_DIR, "scoring_components_stats.csv"), index=False)

    # Grafic bar: coeficient de variatie pe cele 3 componente
    fig, ax = plt.subplots(figsize=(7, 4))
    comp_names = ["cosinus", "popularitate", "raritate"]
    cv_vals = [stats[c]["cv"] for c in comp_names]
    colors = ["#2196F3", "#FF9800", "#4CAF50"]
    bars = ax.bar(comp_names, cv_vals, color=colors, edgecolor="black", linewidth=0.6)
    ax.set_ylabel("Coefficient of Variation (std/mean)")
    ax.set_title("Score Component Variability — TripCraft Attractions")
    ax.set_ylim(0, max(cv_vals) * 1.30)
    for bar, cv in zip(bars, cv_vals):
        ax.text(
            bar.get_x() + bar.get_width() / 2,
            bar.get_height() + max(cv_vals) * 0.02,
            f"{cv:.3f}",
            ha="center", va="bottom", fontsize=11, fontweight="bold",
        )
    plt.tight_layout()
    plt.savefig(os.path.join(RESULTS_DIR, "coeficient_variatie.png"), dpi=150)
    plt.close()
    print(f"\n  Salvat: scoring_components_stats.csv")
    print(f"  Salvat: coeficient_variatie.png")

    return stats, tags_by_attraction, tag_idf


# ─────────────────────────────────────────────────────────────────────────────
# TASK 4: Analiza de sensibilitate a ponderilor
# ─────────────────────────────────────────────────────────────────────────────

def task4_sensitivity(attractions, all_tag_ids, all_tags, profiles,
                      tags_by_attraction, tag_idf):
    print("\n" + "=" * 62)
    print("TASK 4: Analiza de sensibilitate a ponderilor")
    print("=" * 62)

    non_prod_configs = [c for c in WEIGHT_CONFIGS if c != "productie"]
    agg = {c: {"spearman": [], "kendall": [], "ov10": [], "ov20": []}
           for c in non_prod_configs}

    # Contorizam profiluri cu semnal cosinus zero (nu pot produce Spearman definit
    # pentru configuratii care elimina popularitatea)
    n_zero_cosine = 0

    sensitivity_rows = []
    w_cos_p, w_pop_p, w_rar_p = WEIGHT_CONFIGS["productie"]

    for prof in profiles:
        user_vector, raw_scores = build_user_vector(
            prof["tag_scores"], all_tag_ids, all_tags
        )
        comps = compute_components(
            attractions, user_vector, all_tag_ids, raw_scores, tags_by_attraction, tag_idf
        )

        aid_list = [r["attraction_id"] for r in comps]

        # Scoruri de productie aliniate cu aid_list
        prod_scores = np.array([
            w_cos_p * r["cosine"] + w_pop_p * r["popularity"] + w_rar_p * r["rarity"]
            for r in comps
        ])
        prod_sorted_ids = [
            aid_list[i] for i in np.argsort(-prod_scores)
        ]

        cosine_vals = np.array([r["cosine"] for r in comps])
        profile_has_cosine_signal = np.std(cosine_vals) > 1e-9

        if not profile_has_cosine_signal:
            n_zero_cosine += 1

        for cfg_name, (wc, wp, wr) in WEIGHT_CONFIGS.items():
            alt_scores = np.array([
                wc * r["cosine"] + wp * r["popularity"] + wr * r["rarity"]
                for r in comps
            ])
            alt_sorted_ids = [
                aid_list[i] for i in np.argsort(-alt_scores)
            ]

            if len(aid_list) < 2:
                continue

            # Spearman / Kendall sunt definite doar cand ambele siruri variaza
            if np.std(prod_scores) > 1e-9 and np.std(alt_scores) > 1e-9:
                spear, _ = spearmanr(prod_scores, alt_scores)
                kend,  _ = kendalltau(prod_scores, alt_scores)
            else:
                spear = float("nan")
                kend  = float("nan")
            ov10 = overlap_at_k(prod_sorted_ids, alt_sorted_ids, 10)
            ov20 = overlap_at_k(prod_sorted_ids, alt_sorted_ids, 20)

            sensitivity_rows.append({
                "profile_id":   prof["id"],
                "profile_type": prof["type"],
                "config":       cfg_name,
                "spearman":     round(spear, 6),
                "kendall":      round(kend, 6),
                "overlap10":    round(ov10, 6),
                "overlap20":    round(ov20, 6),
            })

            if cfg_name != "productie":
                agg[cfg_name]["spearman"].append(spear)
                agg[cfg_name]["kendall"].append(kend)
                agg[cfg_name]["ov10"].append(ov10)
                agg[cfg_name]["ov20"].append(ov20)

    # Salvare CSV
    pd.DataFrame(sensitivity_rows).to_csv(
        os.path.join(RESULTS_DIR, "sensitivity_rankings.csv"), index=False
    )

    # Statistici medii (nanmean ignora profilurile fara semnal cosinus)
    print(f"\n  Profiluri cu semnal cosinus zero (Spearman/Kendall nedefinit): {n_zero_cosine}")
    print(f"\n  {'Config':<18} {'Spearman':>10} {'Kendall':>10} {'Ov@10':>8} {'Ov@20':>8}")
    print("  " + "-" * 56)
    mean_stats = {}
    for cfg_name in non_prod_configs:
        s = agg[cfg_name]
        arr_spear = np.array(s["spearman"], dtype=float)
        arr_kend  = np.array(s["kendall"],  dtype=float)
        ms = {
            "spearman": float(np.nanmean(arr_spear)) if len(arr_spear) > 0 else float("nan"),
            "kendall":  float(np.nanmean(arr_kend))  if len(arr_kend)  > 0 else float("nan"),
            "ov10":     float(np.mean(s["ov10"]))    if s["ov10"]      else 0.0,
            "ov20":     float(np.mean(s["ov20"]))    if s["ov20"]      else 0.0,
        }
        n_valid_spear = int(np.sum(~np.isnan(arr_spear)))
        mean_stats[cfg_name] = ms
        spear_str = f"{ms['spearman']:10.4f}" if not np.isnan(ms['spearman']) else f"{'nan (n='+str(n_valid_spear)+')':>10}"
        kend_str  = f"{ms['kendall']:10.4f}"  if not np.isnan(ms['kendall'])  else "       nan"
        print(
            f"  {cfg_name:<18} {spear_str} {kend_str} "
            f"{ms['ov10']:>8.4f} {ms['ov20']:>8.4f}"
        )

    # Grafic overlap
    configs = non_prod_configs
    ov10_vals = [mean_stats[c]["ov10"] for c in configs]
    ov20_vals = [mean_stats[c]["ov20"] for c in configs]

    x = np.arange(len(configs))
    width = 0.35
    fig, ax = plt.subplots(figsize=(9, 5))
    b1 = ax.bar(x - width / 2, ov10_vals, width, label="Overlap@10",
                color="#2196F3", edgecolor="black", linewidth=0.5)
    b2 = ax.bar(x + width / 2, ov20_vals, width, label="Overlap@20",
                color="#FF9800", edgecolor="black", linewidth=0.5)
    ax.set_ylabel("Overlap vs. production config (mean over profiles)")
    ax.set_title("Weight Sensitivity — Overlap vs. Production Ranking")
    ax.set_xticks(x)
    ax.set_xticklabels(configs, rotation=18, ha="right", fontsize=9)
    ax.set_ylim(0, 1.15)
    ax.axhline(1.0, color="gray", linewidth=0.8, linestyle="--", alpha=0.6)
    ax.legend()
    for bar in list(b1) + list(b2):
        h = bar.get_height()
        ax.text(
            bar.get_x() + bar.get_width() / 2, h + 0.012,
            f"{h:.2f}", ha="center", va="bottom", fontsize=8,
        )
    plt.tight_layout()
    plt.savefig(os.path.join(RESULTS_DIR, "overlap_configuratii.png"), dpi=150)
    plt.close()
    print(f"\n  Salvat: sensitivity_rankings.csv")
    print(f"  Salvat: overlap_configuratii.png")

    return mean_stats, n_zero_cosine


# ─────────────────────────────────────────────────────────────────────────────
# TASK 5: Efectul asupra itinerariului
# ─────────────────────────────────────────────────────────────────────────────

def task5_itinerary_effect(attractions, all_tag_ids, all_tags, profiles,
                           tags_by_attraction, tag_idf):
    """
    Compara top-15 atractii (≈ 5 zile × 3 atractii/zi) sub configuratia de
    productie vs. 'doar_cosinus', pentru 3-4 profiluri selectate.
    Raporteaza: nr. atractii coincidente, diversitate categorii, durata totala.
    """
    print("\n" + "=" * 62)
    print("TASK 5: Efectul asupra itinerariului")
    print("=" * 62)
    print("  (simulare top-15 atractii = 5 zile x ~3 atractii/zi)")

    # Selectam 4 profiluri: preferabil reale, completam cu sintetice
    real_profs    = [p for p in profiles if p["type"] == "real"]
    synth_profs   = [p for p in profiles if p["type"] == "synthetic"]
    selected = (real_profs[:4] + synth_profs[:(4 - min(len(real_profs), 4))])[:4]
    if not selected:
        selected = synth_profs[:4]

    ITINERARY_SIZE = 15
    attrs_map = {a.id: a for a in attractions}

    w_cos_p, w_pop_p, w_rar_p = WEIGHT_CONFIGS["productie"]
    w_cos_c, w_pop_c, w_rar_c = WEIGHT_CONFIGS["doar_cosinus"]

    records = []
    for prof in selected:
        user_vector, raw_scores = build_user_vector(
            prof["tag_scores"], all_tag_ids, all_tags
        )
        comps = compute_components(
            attractions, user_vector, all_tag_ids, raw_scores, tags_by_attraction, tag_idf
        )

        prod_ranked = apply_weights(comps, w_cos_p, w_pop_p, w_rar_p)[:ITINERARY_SIZE]
        cos_ranked  = apply_weights(comps, w_cos_c, w_pop_c, w_rar_c)[:ITINERARY_SIZE]

        prod_ids = {r["attraction_id"] for r in prod_ranked}
        cos_ids  = {r["attraction_id"] for r in cos_ranked}
        n_coincid = len(prod_ids & cos_ids)

        prod_cats = {r["category"] for r in prod_ranked if r.get("category")}
        cos_cats  = {r["category"] for r in cos_ranked  if r.get("category")}

        def total_dur(ranked):
            return sum(
                float(attrs_map[r["attraction_id"]].avg_duration_hours or 2.0)
                for r in ranked
                if r["attraction_id"] in attrs_map
            )

        prod_dur = total_dur(prod_ranked)
        cos_dur  = total_dur(cos_ranked)

        records.append({
            "profile_id":                    prof["id"],
            "profile_type":                  prof["type"],
            "atractii_coincid":              n_coincid,
            "total_simulate":                ITINERARY_SIZE,
            "diversitate_categ_productie":   len(prod_cats),
            "diversitate_categ_cosinus":     len(cos_cats),
            "durata_productie_ore":          round(prod_dur, 1),
            "durata_cosinus_ore":            round(cos_dur, 1),
        })

        print(
            f"  {prof['id']:<28}: coincid={n_coincid}/{ITINERARY_SIZE}  "
            f"categ prod={len(prod_cats)} cos={len(cos_cats)}  "
            f"dur prod={prod_dur:.1f}h cos={cos_dur:.1f}h"
        )

    pd.DataFrame(records).to_csv(
        os.path.join(RESULTS_DIR, "itinerary_effect.csv"), index=False
    )
    print(f"\n  Salvat: itinerary_effect.csv")

    return records


# ─────────────────────────────────────────────────────────────────────────────
# TASK 6: SUMMARY.md
# ─────────────────────────────────────────────────────────────────────────────

def task6_summary(stats, mean_sensitivity, itinerary_records,
                  n_attractions, n_leaf_tags, n_profiles, n_zero_cosine=0):
    print("\n" + "=" * 62)
    print("TASK 6: Rezumat (SUMMARY.md)")
    print("=" * 62)

    cv_cos  = stats.get("cosinus",      {}).get("cv", 0.0)
    cv_pop  = stats.get("popularitate", {}).get("cv", 0.0)
    cv_rar  = stats.get("raritate",     {}).get("cv", 0.0)

    if cv_pop < cv_cos:
        pop_obs = (
            "**Confirmat:** popularitatea are CV semnificativ mai mic decat cosinusul "
            f"({cv_pop:.4f} vs {cv_cos:.4f}), validand ipoteza ca termenul de popularitate "
            "se aplateaza — variatie redusa intre atractii, impact limitat in reordonare."
        )
    else:
        pop_obs = (
            f"Popularitatea (CV={cv_pop:.4f}) nu este mai mica decat cosinusul "
            f"(CV={cv_cos:.4f}) — variabilitate comparabila."
        )

    lines = [
        "# Rezumat Evaluare Empirica — TripCraft Scoring",
        "",
        "**Formula de productie:** `final = 0.70*cosinus + 0.20*popularitate + 0.10*raritate`",
        "",
        f"| Parametru | Valoare |",
        f"|---|---|",
        f"| Atractii in DB | {n_attractions} |",
        f"| Etichete-frunza | {n_leaf_tags} |",
        f"| Profiluri testate | {n_profiles} |",
        f"| Seed | {SEED} |",
        "",
        "## 1. Coeficienti de variatie per componenta",
        "",
        "| Componenta | Media | Std | Min | Max | **CV** |",
        "|---|---|---|---|---|---|",
    ]
    for comp, s in stats.items():
        lines.append(
            f"| {comp} | {s['media']:.4f} | {s['std']:.4f} | "
            f"{s['min']:.4f} | {s['max']:.4f} | **{s['cv']:.4f}** |"
        )

    lines += [
        "",
        f"> {pop_obs}",
        "",
        "## 2. Sensibilitate la ponderi (vs. configuratia de productie)",
        "",
        "| Configuratie | Ponderi (cos/pop/rar) | Spearman | Kendall | Overlap@10 | Overlap@20 |",
        "|---|---|---|---|---|---|",
    ]
    config_labels = {
        "doar_cosinus": "1.00/0.00/0.00",
        "fara_pop":     "0.78/0.00/0.22",
        "pop_ridicata": "0.50/0.40/0.10",
        "raritate_rid": "0.50/0.20/0.30",
    }
    for cfg, ms in mean_sensitivity.items():
        w_str = config_labels.get(cfg, "")
        def _fmt(v):
            return f"{v:.4f}" if not (isinstance(v, float) and np.isnan(v)) else "N/A*"
        lines.append(
            f"| {cfg} | {w_str} | {_fmt(ms['spearman'])} | {_fmt(ms['kendall'])} | "
            f"{ms['ov10']:.4f} | {ms['ov20']:.4f} |"
        )

    if n_zero_cosine > 0:
        lines += [
            "",
            f"> \\* Spearman/Kendall = N/A pentru {n_zero_cosine} profiluri la care "
            f"toate scorurile cosinus sunt 0 (profil fara suprapunere cu atractiile). "
            f"In aceste cazuri, configuratia 'productie' ordoneaza prin popularitate "
            f"(safety-net), iar configuratiile fara popularitate produc scoruri constante "
            f"— corelatie de rang nedefinita matematic.",
        ]

    if itinerary_records:
        avg_coincid    = np.mean([r["atractii_coincid"]              for r in itinerary_records])
        avg_cats_prod  = np.mean([r["diversitate_categ_productie"]   for r in itinerary_records])
        avg_cats_cos   = np.mean([r["diversitate_categ_cosinus"]     for r in itinerary_records])
        avg_dur_prod   = np.mean([r["durata_productie_ore"]          for r in itinerary_records])
        avg_dur_cos    = np.mean([r["durata_cosinus_ore"]            for r in itinerary_records])
        lines += [
            "",
            "## 3. Efectul asupra itinerariului (top-15, medie pe 3-4 profiluri)",
            "",
            f"| Metrica | Productie | Doar cosinus |",
            f"|---|---|---|",
            f"| Atractii coincidente | **{avg_coincid:.1f}/15** | — |",
            f"| Diversitate categorii | {avg_cats_prod:.1f} | {avg_cats_cos:.1f} |",
            f"| Durata totala (ore) | {avg_dur_prod:.1f} | {avg_dur_cos:.1f} |",
        ]

    lines += [
        "",
        "## Fisiere generate",
        "",
        "- `scoring_components_stats.csv` — componente detaliate per profil si atractie",
        "- `coeficient_variatie.png` — grafic bar CV pe cele 3 componente",
        "- `sensitivity_rankings.csv` — Spearman/Kendall/overlap per profil si configuratie",
        "- `overlap_configuratii.png` — grafic overlap@10 si overlap@20 per configuratie",
        "- `itinerary_effect.csv` — comparatie itinerariu productie vs. doar cosinus",
        "",
        "---",
        f"*Generat automat de `backend/evaluation/run_evaluation.py` | SEED={SEED}*",
    ]

    summary_text = "\n".join(lines)
    summary_path = os.path.join(RESULTS_DIR, "SUMMARY.md")
    with open(summary_path, "w", encoding="utf-8") as f:
        f.write(summary_text)

    print()
    print(summary_text)
    return summary_text


# ─────────────────────────────────────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────────────────────────────────────

def main():
    print("\n" + "=" * 62)
    print("  TripCraft — Evaluare Empirica Scor Atractii")
    print(f"  SEED = {SEED}   |   numpy={np.__version__}")
    print("=" * 62)

    db = SessionLocal()
    try:
        attractions, all_tag_ids, all_tags, n_leaf = task1_load_data(db)
        profiles = task2_load_profiles(db, all_tags)
        stats, tags_by_attraction, tag_idf = task3_component_analysis(
            attractions, all_tag_ids, all_tags, profiles, db
        )
        mean_sensitivity, n_zero_cosine = task4_sensitivity(
            attractions, all_tag_ids, all_tags, profiles, tags_by_attraction, tag_idf
        )
        itinerary_records = task5_itinerary_effect(
            attractions, all_tag_ids, all_tags, profiles, tags_by_attraction, tag_idf
        )
        task6_summary(
            stats, mean_sensitivity, itinerary_records,
            len(attractions), n_leaf, len(profiles), n_zero_cosine,
        )
    finally:
        db.close()

    print("\n" + "=" * 62)
    print("Fisiere generate in backend/evaluation/results/:")
    for fname in sorted(os.listdir(RESULTS_DIR)):
        fpath = os.path.join(RESULTS_DIR, fname)
        size = os.path.getsize(fpath)
        print(f"  {fname:<40}  {size:>8,} bytes")
    print("=" * 62)


if __name__ == "__main__":
    main()
