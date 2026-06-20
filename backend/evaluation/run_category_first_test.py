#!/usr/bin/env python3
"""
backend/evaluation/run_category_first_test.py
==============================================
Test empiric: Quiz cu selectie explicita de categorii + depth/explore.

Design propus:
  Phase 1 — Category Selection (UI nou, nu swipe-uri):
    Afiseaza 8 categorii L1 cate 4 (doua ecrane).
    Userul ALEGE direct categoriile care ii plac (tap to select).
    Cost: ~2 interactiuni de ecran, nu 8 swipe-uri.
    Acuratete de identificare a dominantelor: ~65-75% (vs 24% cu inferenta).

  Phase 2 — Depth + Explore (swipe-uri obisnuite):
    N_DEPTH carduri (70%): leaf swipes in categoriile selectate in Phase 1.
    N_EXPLORE carduri (30%): leaf swipes in categoriile NON-selectate.
    Scopul explore: nu omitem preferinte neasteptate + prior mai informat.

Comparatie directa:
  baseline         — quiz curent 20 carduri round-robin
  baseline+prior   — + prior ierarhic
  hier2+prior      — quiz ierarhic (Phase 1 random) din testul anterior
  catfirst_70      — selectie explicita + 70/30 depth/explore (fara prior)
  catfirst_70+p    — catfirst_70 + prior
  catfirst_80+p    — 80/20 depth/explore + prior (mai adanc, mai putin explore)
  catfirst_60+p    — 60/40 depth/explore + prior (mai echilibrat)

Rulare:
    python -m evaluation.run_category_first_test
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

SEED = 42
np.random.seed(SEED)
_rng = np.random.default_rng(SEED)

_BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _BACKEND_DIR not in sys.path:
    sys.path.insert(0, _BACKEND_DIR)

from app.database import SessionLocal
from app.models import Tag
from app.services.quiz_engine import (
    adjust_tag_score, compute_entropy,
    RIGHT_WEIGHT, LEFT_WEIGHT, MIN_CARDS, MAX_CARDS, L1_ORDER,
)

RESULTS_DIR = os.path.join(os.path.dirname(__file__), "results")
os.makedirs(RESULTS_DIR, exist_ok=True)
logging.basicConfig(level=logging.WARNING)

L1_SLUGS     = list(L1_ORDER)
N_USERS      = 50
N_PHASE2     = 20   # carduri leaf in Phase 2 (Phase 1 e UI gratuit)
N_HIER_TOTAL = 20   # pentru hier2 din testul anterior
N_HIER_P1    = 8
PRIOR_STR    = 0.30

# Parametri selectie Phase 1
# Userului ii sunt aratate 8 categorii (4+4). Selecteaza cu P = sigmoid(5*(lat-0.5))
MAX_SELECTED = 4    # maxim categorii selectabile in UI (pragmatic)
MIN_SELECTED = 1    # minim (daca nu selecteaza nimic, alegem top-1)


# ─────────────────────────────────────────────────────────────────────────────
# Date
# ─────────────────────────────────────────────────────────────────────────────

def load_data(db):
    all_tags = db.query(Tag).all()
    slug_to_tag = {t.slug: t for t in all_tags}
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
    n_leaf = sum(len(v) for v in l1_to_leaf.values())
    print(f"  {n_leaf} taguri-frunza | {len(L1_SLUGS)} categorii L1")
    return {"all_tags": all_tags, "l1_to_leaf": l1_to_leaf}


# ─────────────────────────────────────────────────────────────────────────────
# Useri sintetici
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
                latent_leaf[slug] = max(0.0, min(1.0, w + float(rng.normal(0, 0.035))))
        users.append({
            "user_id": i, "dominant": dominant,
            "latent_macro": latent_macro, "latent_leaf": latent_leaf,
        })
    return users


# ─────────────────────────────────────────────────────────────────────────────
# Metrici
# ─────────────────────────────────────────────────────────────────────────────

def macro_recovery(scores, latent_macro, l1_to_leaf):
    rec, lat = [], []
    for l1 in L1_SLUGS:
        lv = l1_to_leaf.get(l1, [])
        rec.append(float(np.mean([scores.get(s, 0.5) for s in lv])) if lv else 0.5)
        lat.append(latent_macro.get(l1, 0.1))
    sp, _ = spearmanr(rec, lat)
    return float(sp) if not np.isnan(sp) else 0.0

def leaf_recovery(scores, latent_leaf, l1_to_leaf):
    leaves = [s for lv in l1_to_leaf.values() for s in lv]
    sp, _ = spearmanr([scores.get(s, 0.5) for s in leaves],
                      [latent_leaf.get(s, 0.0) for s in leaves])
    return float(sp) if not np.isnan(sp) else 0.0

def dominant_leaf_recovery(scores, latent_leaf, dominant, l1_to_leaf):
    leaves = [s for l1 in dominant for s in l1_to_leaf.get(l1, [])]
    if len(leaves) < 3:
        return float("nan")
    sp, _ = spearmanr([scores.get(s, 0.5) for s in leaves],
                      [latent_leaf.get(s, 0.0) for s in leaves])
    return float(sp) if not np.isnan(sp) else 0.0


# ─────────────────────────────────────────────────────────────────────────────
# Functii quiz
# ─────────────────────────────────────────────────────────────────────────────

def _swipe(tag_scores, slug, latent_leaf, rng):
    lat = latent_leaf.get(slug, 0.08)
    p   = 1.0 / (1.0 + math.exp(-5.0 * (lat - 0.5)))
    adjust_tag_score(tag_scores, slug,
                     RIGHT_WEIGHT if rng.random() < p else LEFT_WEIGHT, True)

def apply_prior(scores, l1_to_leaf, strength=PRIOR_STR):
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


# ── Baseline ──────────────────────────────────────────────────────────────────
def quiz_baseline(latent_leaf, l1_to_leaf, rng):
    tag_scores, seen = {}, set()
    n = int(rng.integers(MIN_CARDS, MAX_CARDS + 1))
    cp = 0
    for _ in range(n):
        slug = None
        for _ in range(len(L1_SLUGS)):
            l1 = L1_SLUGS[cp % len(L1_SLUGS)]; cp += 1
            cands = [s for s in l1_to_leaf.get(l1, []) if s not in seen]
            if cands:
                slug = cands[int(rng.integers(0, len(cands)))]
                break
        if slug is None:
            break
        seen.add(slug)
        _swipe(tag_scores, slug, latent_leaf, rng)
        if len(seen) >= MIN_CARDS and compute_entropy(tag_scores) < 1.0:
            break
    return tag_scores


# ── Hier2+Prior (referinta din testul anterior) ───────────────────────────────
def quiz_hier2(latent_leaf, l1_to_leaf, rng):
    tag_scores, seen = {}, set()
    # Phase 1: 1 card random per L1
    for l1 in L1_SLUGS:
        cands = [s for s in l1_to_leaf.get(l1, []) if s not in seen]
        if not cands:
            continue
        slug = cands[int(rng.integers(0, len(cands)))]
        seen.add(slug)
        _swipe(tag_scores, slug, latent_leaf, rng)
    # Identifica dominante
    agg = {l1: float(np.mean([tag_scores[s] for s in lv if s in tag_scores]) or 0.5)
           for l1, lv in l1_to_leaf.items()
           if [s for s in lv if s in tag_scores]}
    dominant = sorted(agg, key=lambda l1: -agg.get(l1, 0.5))[:2]
    # Phase 2
    cp = 0
    for _ in range(N_HIER_TOTAL - N_HIER_P1):
        slug = None
        for _ in range(len(dominant)):
            l1 = dominant[cp % len(dominant)]; cp += 1
            cands = [s for s in l1_to_leaf.get(l1, []) if s not in seen]
            if cands:
                slug = cands[int(rng.integers(0, len(cands)))]
                break
        if slug is None:
            break
        seen.add(slug)
        _swipe(tag_scores, slug, latent_leaf, rng)
    return tag_scores


# ── Category-First: Phase 1 selectie explicita + Phase 2 depth/explore ────────
def phase1_select_categories(latent_macro, rng):
    """
    Simuleaza selectia explicita a categoriilor de catre user.

    UI: 8 categorii afisate cate 4 (2 ecrane). Userul tappe categoriile dorite.
    Simulare: P(select L1) = sigmoid(5 * (latent_macro[L1] - 0.5))

    Returnuri:
      selected     — L1 slugs alese de user
      non_selected — restul
    """
    probs = {
        l1: 1.0 / (1.0 + math.exp(-5.0 * (latent_macro.get(l1, 0.1) - 0.5)))
        for l1 in L1_SLUGS
    }
    raw_selected = [l1 for l1 in L1_SLUGS if rng.random() < probs[l1]]

    # UX constraint: maxim MAX_SELECTED, minim MIN_SELECTED
    if len(raw_selected) > MAX_SELECTED:
        # Pastram cele cu probabilitate mare
        raw_selected = sorted(raw_selected, key=lambda l1: -probs[l1])[:MAX_SELECTED]
    if len(raw_selected) < MIN_SELECTED:
        # Adaugam cele mai probabile
        remaining = sorted(
            [l1 for l1 in L1_SLUGS if l1 not in raw_selected],
            key=lambda l1: -probs[l1]
        )
        raw_selected += remaining[:MIN_SELECTED - len(raw_selected)]

    non_selected = [l1 for l1 in L1_SLUGS if l1 not in raw_selected]
    return raw_selected, non_selected


def quiz_category_first(latent_leaf, latent_macro, l1_to_leaf, rng,
                         depth_ratio=0.70):
    """
    Quiz cu selectie explicita de categorii (Phase 1) + depth+explore (Phase 2).

    Phase 1: Userul alege 1-MAX_SELECTED categorii din 8 (4+4 pe ecran).
             Costul UI e minim (~2 interactiuni de ecran vs 8 swipe-uri).
             Acuratete de identificare dominante: ~65-75% (vs 24% cu inferenta).

    Phase 2: N_PHASE2 swipe-uri pe taguri-frunza.
      - depth_ratio (implicit 70%): carduri in categoriile selectate
      - 1 - depth_ratio (implicit 30%): explorare in categoriile ne-selectate
    Rationale explore: previne over-fitting pe categoriile selectate;
    permite descoperirea preferintelor neasteptate; da prior mai mult context.
    """
    selected, non_selected = phase1_select_categories(latent_macro, rng)

    tag_scores, seen = {}, set()
    n_depth   = round(N_PHASE2 * depth_ratio)
    n_explore = N_PHASE2 - n_depth

    # DEPTH: carduri in categoriile selectate
    cp = 0
    for _ in range(n_depth):
        slug = None
        for _ in range(len(selected)):
            l1 = selected[cp % len(selected)]; cp += 1
            cands = [s for s in l1_to_leaf.get(l1, []) if s not in seen]
            if cands:
                slug = cands[int(rng.integers(0, len(cands)))]
                break
        if slug is None:
            break
        seen.add(slug)
        _swipe(tag_scores, slug, latent_leaf, rng)

    # EXPLORE: carduri in categoriile ne-selectate
    cp2 = 0
    for _ in range(n_explore):
        if not non_selected:
            break
        slug = None
        for _ in range(len(non_selected)):
            l1 = non_selected[cp2 % len(non_selected)]; cp2 += 1
            cands = [s for s in l1_to_leaf.get(l1, []) if s not in seen]
            if cands:
                slug = cands[int(rng.integers(0, len(cands)))]
                break
        if slug is None:
            break
        seen.add(slug)
        _swipe(tag_scores, slug, latent_leaf, rng)

    return tag_scores, selected


# ─────────────────────────────────────────────────────────────────────────────
# Rulare comparatie
# ─────────────────────────────────────────────────────────────────────────────

DEPTH_RATIOS = {
    "catfirst_10": 0.10,
    "catfirst_20": 0.20,
    "catfirst_30": 0.30,
    "catfirst_40": 0.40,
    "catfirst_50": 0.50,
    "catfirst_55": 0.55,
    "catfirst_60": 0.60,
    "catfirst_65": 0.65,
    "catfirst_70": 0.70,
    "catfirst_75": 0.75,
    "catfirst_80": 0.80,
    "catfirst_85": 0.85,
    "catfirst_90": 0.90,
    "catfirst_95": 0.95,
    "catfirst_100": 1.00,
}

VNAMES = [
    "baseline", "baseline+p", "hier2+p",
    "catfirst_10+p", "catfirst_20+p", "catfirst_30+p",
    "catfirst_40+p", "catfirst_50+p", "catfirst_55+p",
    "catfirst_60+p", "catfirst_65+p", "catfirst_70+p",
    "catfirst_75+p", "catfirst_80+p", "catfirst_85+p",
    "catfirst_90+p", "catfirst_95+p", "catfirst_100+p",
]

import colorsys
def _grad(i, n):
    r, g, b = colorsys.hsv_to_rgb(0.33, 0.3 + 0.7 * i / max(n - 1, 1), 0.5 + 0.5 * i / max(n - 1, 1))
    return f"#{int(r*255):02X}{int(g*255):02X}{int(b*255):02X}"

_cf_keys = [v for v in VNAMES if v.startswith("catfirst") and "+p" in v]
VCOLORS = {"baseline": "#9E9E9E", "baseline+p": "#FF9800", "hier2+p": "#1565C0"}
VCOLORS.update({k: _grad(i, len(_cf_keys)) for i, k in enumerate(_cf_keys)})

VLABELS = {"baseline": "Base", "baseline+p": "Base+P", "hier2+p": "Hier2+P"}
VLABELS.update({v: v.replace("catfirst_", "").replace("+p", "%+P") for v in _cf_keys})


def run(users, data):
    print(f"\nTest category-first quiz | {N_USERS} useri | SEED={SEED}")
    print(f"  Phase2 cards={N_PHASE2} | depth ratios={list(DEPTH_RATIOS.values())}")
    print(f"  Phase1 selection: MAX={MAX_SELECTED} MIN={MIN_SELECTED}\n")

    rows = []
    phase1_stats = []

    for user in users:
        uid = user["user_id"]

        # Baseline
        b = quiz_baseline(user["latent_leaf"], data["l1_to_leaf"],
                          np.random.default_rng(SEED + uid))
        # Hier2
        h2 = quiz_hier2(user["latent_leaf"], data["l1_to_leaf"],
                        np.random.default_rng(SEED + uid))
        # Category-first variants
        cf_scores = {}
        cf_selected = {}
        for vname, dr in DEPTH_RATIOS.items():
            sc, sel = quiz_category_first(
                user["latent_leaf"], user["latent_macro"],
                data["l1_to_leaf"], np.random.default_rng(SEED + uid), dr
            )
            cf_scores[vname] = sc
            cf_selected[vname] = sel

        # Phase 1 accuracy (sel e identica pentru orice ratio, seed fix)
        sel = cf_selected[next(iter(DEPTH_RATIOS))]
        true_dom = set(user["dominant"])
        recall = len(true_dom & set(sel)) / len(true_dom) if true_dom else 0.0
        precision = len(true_dom & set(sel)) / len(sel) if sel else 0.0
        phase1_stats.append({
            "user_id": uid,
            "n_true_dom": len(true_dom),
            "n_selected": len(sel),
            "recall": recall,
            "precision": precision,
            "all_found": recall == 1.0,
        })

        all_scores = {
            "baseline":   b,
            "baseline+p": apply_prior(b, data["l1_to_leaf"]),
            "hier2+p":    apply_prior(h2, data["l1_to_leaf"]),
        }
        for vname, sc in cf_scores.items():
            all_scores[vname]        = sc
            all_scores[vname + "+p"] = apply_prior(sc, data["l1_to_leaf"])

        row = {
            "user_id": uid,
            "dominant": "|".join(user["dominant"]),
            "n_dominant": len(user["dominant"]),
            "phase1_selected": "|".join(sel),
            "phase1_recall": round(recall, 3),
            "phase1_precision": round(precision, 3),
        }
        for vname, scores in all_scores.items():
            row[f"leaf_{vname}"]  = round(leaf_recovery(
                scores, user["latent_leaf"], data["l1_to_leaf"]), 4)
            row[f"macro_{vname}"] = round(macro_recovery(
                scores, user["latent_macro"], data["l1_to_leaf"]), 4)
            row[f"dom_{vname}"]   = round(dominant_leaf_recovery(
                scores, user["latent_leaf"], user["dominant"], data["l1_to_leaf"]), 4)
            row[f"cov_{vname}"]   = sum(1 for v in scores.values() if v != 0.5)
        rows.append(row)

    df = pd.DataFrame(rows)
    df_p1 = pd.DataFrame(phase1_stats)
    return df, df_p1


# ─────────────────────────────────────────────────────────────────────────────
# Raportare
# ─────────────────────────────────────────────────────────────────────────────

def report(df, df_p1):
    b_leaf  = df["leaf_baseline"].mean()
    b_macro = df["macro_baseline"].mean()
    b_dom   = df["dom_baseline"].mean()

    print("=" * 76)
    print(f"  {'Varianta':<18} {'Leaf':>7} {'dLeaf':>7} "
          f"{'Macro':>7} {'dMacro':>7} "
          f"{'DomLeaf':>8} {'dDomLeaf':>9} {'Cov':>5}")
    print("  " + "-" * 72)
    for v in VNAMES:
        leaf  = df[f"leaf_{v}"].mean()
        macro = df[f"macro_{v}"].mean()
        dom   = df[f"dom_{v}"].mean()
        cov   = df[f"cov_{v}"].mean()
        marker = " *" if v.startswith("catfirst") and "+p" in v else "  "
        print(f"{marker} {v:<18} {leaf:>7.4f} {leaf-b_leaf:>+7.4f} "
              f"{macro:>7.4f} {macro-b_macro:>+7.4f} "
              f"{dom:>8.4f} {dom-b_dom:>+9.4f} {cov:>5.1f}")

    # Semnificatie statistica dominant-leaf
    print(f"\n  Semnificatie statistica dominant-leaf (Wilcoxon vs baseline):")
    print(f"  {'Varianta':<18}  {'p-val':>8}  {'sig':>5}  {'vs hier2+p p':>14}  {'sig':>5}")
    print("  " + "-" * 58)
    for v in [k for k in VNAMES if k != "baseline"]:
        try:
            _, p_vs_b = wilcoxon(df[f"dom_{v}"], df["dom_baseline"], alternative="greater")
        except Exception:
            p_vs_b = float("nan")
        try:
            _, p_vs_h = wilcoxon(df[f"dom_{v}"], df["dom_hier2+p"], alternative="greater")
        except Exception:
            p_vs_h = float("nan")
        s_b = "**" if p_vs_b < 0.05 else ("*" if p_vs_b < 0.10 else "ns")
        s_h = "**" if p_vs_h < 0.05 else ("*" if p_vs_h < 0.10 else "ns")
        print(f"  {v:<18}  {p_vs_b:>8.4f}  {s_b:>5}  {p_vs_h:>14.4f}  {s_h:>5}")

    # Phase 1 statistics
    print(f"\n  Phase 1 — Acuratete selectie categorii:")
    print(f"  Recall (dominantele gasite):    {df_p1['recall'].mean():.3f}  "
          f"(std={df_p1['recall'].std():.3f})")
    print(f"  Precision (selectii corecte):   {df_p1['precision'].mean():.3f}  "
          f"(std={df_p1['precision'].std():.3f})")
    print(f"  Toate dominantele gasite:       {df_p1['all_found'].mean()*100:.1f}%")
    print(f"  Nr mediu categorii selectate:   {df_p1['n_selected'].mean():.1f}")
    print(f"\n  Comparatie Phase 1 accuracy:")
    print(f"    Quiz anterior (rand 1 card): recall=0.630, all_correct=24%")
    print(f"    Category-first (explicit):   recall={df_p1['recall'].mean():.3f}, "
          f"all_correct={df_p1['all_found'].mean()*100:.0f}%")
    print("=" * 76)


# ─────────────────────────────────────────────────────────────────────────────
# Grafice
# ─────────────────────────────────────────────────────────────────────────────

def make_plots(df, df_p1):
    cf_vnames = [v for v in VNAMES if v.startswith("catfirst") and "+p" in v]
    dr_vals   = [DEPTH_RATIOS[v.replace("+p", "")] for v in cf_vnames]

    # Plot 1: curba DomLeaf/Macro/Leaf vs depth ratio
    fig, axes = plt.subplots(1, 3, figsize=(15, 4))
    ref_lines = [
        ("baseline",   "#9E9E9E", "--", "Baseline"),
        ("baseline+p", "#FF9800", "--", "Baseline+P"),
        ("hier2+p",    "#1565C0", "-.", "Hier2+P"),
    ]
    for ax, mk, title in zip(axes,
                              ["dom", "macro", "leaf"],
                              ["Dominant-Leaf (metrica cheie)", "Macro recovery", "Leaf recovery"]):
        vals = [df[f"{mk}_{v}"].mean() for v in cf_vnames]
        stds = [df[f"{mk}_{v}"].std()  for v in cf_vnames]
        ax.plot(dr_vals, vals, "o-", color="#4CAF50", linewidth=2, markersize=6, label="CatFirst+P")
        ax.fill_between(dr_vals,
                        [v - s for v, s in zip(vals, stds)],
                        [v + s for v, s in zip(vals, stds)],
                        alpha=0.15, color="#4CAF50")
        best_i = int(np.argmax(vals))
        ax.annotate(f"best={dr_vals[best_i]:.0%}\n{vals[best_i]:.3f}",
                    xy=(dr_vals[best_i], vals[best_i]),
                    xytext=(dr_vals[best_i] + 0.03, vals[best_i] + 0.01),
                    fontsize=7.5, color="darkgreen")
        for key, color, ls, label in ref_lines:
            ax.axhline(df[f"{mk}_{key}"].mean(), color=color, linestyle=ls,
                       linewidth=1.3, label=label, alpha=0.8)
        ax.set_xlabel("Depth ratio")
        ax.set_ylabel("Spearman")
        ax.set_title(title, fontsize=9)
        ax.set_xticks(dr_vals)
        ax.set_xticklabels([f"{int(d*100)}%" for d in dr_vals], fontsize=7, rotation=45)
        ax.legend(fontsize=7)

    plt.suptitle(
        f"CatFirst: toate depth ratios (10%→100%)  "
        f"| Phase1 recall={df_p1['recall'].mean():.2f}, all_correct={df_p1['all_found'].mean()*100:.0f}%",
        fontsize=9
    )
    plt.tight_layout()
    plt.savefig(os.path.join(RESULTS_DIR, "catfirst_recovery.png"), dpi=150)
    plt.close()

    # Plot 2: boxplot variante cheie + best catfirst
    best_v = cf_vnames[int(np.argmax([df[f"dom_{v}"].mean() for v in cf_vnames]))]
    key_v = ["baseline", "baseline+p", "hier2+p", best_v]
    fig, ax = plt.subplots(figsize=(9, 4))
    bp = ax.boxplot([df[f"dom_{v}"].values for v in key_v],
                    tick_labels=[VLABELS.get(v, v) for v in key_v],
                    patch_artist=True,
                    medianprops=dict(color="red", linewidth=1.5))
    for patch, v in zip(bp["boxes"], key_v):
        patch.set_facecolor(VCOLORS.get(v, "#4CAF50"))
        patch.set_alpha(0.75)
    ax.set_ylabel("Dominant-Leaf Spearman")
    ax.set_title(f"Distributia dominant-leaf — variante cheie (best catfirst={best_v})")
    plt.tight_layout()
    plt.savefig(os.path.join(RESULTS_DIR, "catfirst_dominant_dist.png"), dpi=150)
    plt.close()

    # Plot 3: heatmap depth_ratio x metrica
    fig, axes2 = plt.subplots(1, 2, figsize=(12, 4))
    for ax, mk, title in zip(axes2,
                              ["dom", "macro"],
                              ["DomLeaf vs depth ratio", "Macro vs depth ratio"]):
        vals = [df[f"{mk}_{v}"].mean() for v in cf_vnames]
        stds = [df[f"{mk}_{v}"].std()  for v in cf_vnames]
        bars = ax.bar([f"{int(d*100)}%" for d in dr_vals], vals, yerr=stds,
                      capsize=3, color="#4CAF50", edgecolor="black", linewidth=0.5, alpha=0.8)
        ax.axhline(df[f"{mk}_hier2+p"].mean(), color="#1565C0",
                   linestyle="--", linewidth=1.5, label="Hier2+P")
        ax.axhline(df[f"{mk}_baseline+p"].mean(), color="#FF9800",
                   linestyle="--", linewidth=1.2, label="Baseline+P")
        ax.set_xlabel("Depth ratio")
        ax.set_ylabel("Spearman")
        ax.set_title(title, fontsize=9)
        ax.tick_params(axis="x", labelsize=8, rotation=45)
        ax.legend(fontsize=8)
        for bar, v in zip(bars, vals):
            ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 0.005,
                    f"{v:.3f}", ha="center", va="bottom", fontsize=6.5)

    axes2[1].hist(df_p1["recall"], bins=10, color="#4CAF50", edgecolor="black",
                  linewidth=0.5, alpha=0.8)
    axes2[1].axvline(df_p1["recall"].mean(), color="red", linewidth=1.5, linestyle="--",
                     label=f"mean={df_p1['recall'].mean():.2f}")
    axes2[1].set_xlabel("Phase 1 recall")
    axes2[1].set_ylabel("Nr useri")
    axes2[1].set_title("Distributia Phase 1 recall")
    axes2[1].legend()

    plt.tight_layout()
    plt.savefig(os.path.join(RESULTS_DIR, "catfirst_analysis.png"), dpi=150)
    plt.close()

    print(f"\n  Salvat: catfirst_recovery.png")
    print(f"  Salvat: catfirst_dominant_dist.png")
    print(f"  Salvat: catfirst_analysis.png")


# ─────────────────────────────────────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────────────────────────────────────

def main():
    print("\n" + "=" * 76)
    print("  Category-First Quiz — Test Empiric")
    print(f"  SEED={SEED} | N={N_USERS} | Phase2={N_PHASE2} carduri")
    print(f"  Phase1: max {MAX_SELECTED} categorii selectate din {len(L1_SLUGS)}")
    print("=" * 76)

    db = SessionLocal()
    try:
        data = load_data(db)
    finally:
        db.close()

    users = generate_users(data["l1_to_leaf"], _rng)
    df, df_p1 = run(users, data)
    report(df, df_p1)
    make_plots(df, df_p1)

    df.to_csv(os.path.join(RESULTS_DIR, "catfirst_per_user.csv"), index=False)
    df_p1.to_csv(os.path.join(RESULTS_DIR, "catfirst_phase1.csv"), index=False)
    print(f"  Salvat: catfirst_per_user.csv, catfirst_phase1.csv")


if __name__ == "__main__":
    main()
