#!/usr/bin/env python3
"""
backend/evaluation/run_hierarchical_test.py
============================================
Test empiric: Quiz ierarhic vs Quiz flat (baseline).

Motivatie:
  Toate metodele anterioare (prior, SemTag) atacau OUTPUT-ul quiz-ului.
  Problema reala e in INPUT: 2-3 swipe-uri per categorie nu pot recupera
  within-category preferences. Quiz-ul ierarhic atacă DESIGNUL quiz-ului.

Structura quiz ierarhic:
  Faza 1 (8 carduri): 1 card per L1 → identifica categoriile dominante
  Faza 2 (12 carduri): drill-down in top-2 sau top-3 L1 dominante

Variante testate:
  baseline         — 20 carduri random round-robin (referinta)
  baseline+prior   — + prior ierarhic
  hier2            — 8 broad + 12 focused top-2 L1
  hier2+prior      — hier2 + prior
  hier3            — 8 broad + 12 focused top-3 L1
  hier3+prior      — hier3 + prior

Metrici:
  - Leaf Spearman global (161 taguri)
  - Macro Spearman (8 L1)
  - Dominant-leaf Spearman (Spearman NUMAI pe categoriile dominante ale userului)
    ← metrica cheie: masoara discriminarea where it counts

Rulare:
    python -m evaluation.run_hierarchical_test
"""

import sys
import os
import math
import logging
from collections import defaultdict

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

L1_SLUGS   = list(L1_ORDER)
N_USERS    = 50
N_PHASE1   = 8    # 1 card per L1 → broad survey
N_TOTAL    = 20   # identic cu baseline — acelasi nr total de carduri
PRIOR_STR  = 0.30


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
    print(f"  {n_leaf} taguri-frunza | {len(L1_SLUGS)} L1 categorii")
    for l1, lv in l1_to_leaf.items():
        print(f"    {l1}: {len(lv)} frunze")

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
            "user_id": i,
            "dominant": dominant,
            "latent_macro": latent_macro,
            "latent_leaf": latent_leaf,
        })
    return users


# ─────────────────────────────────────────────────────────────────────────────
# Metrici
# ─────────────────────────────────────────────────────────────────────────────

def macro_recovery(scores, latent_macro, l1_to_leaf):
    rec, lat = [], []
    for l1 in L1_SLUGS:
        leaves = l1_to_leaf.get(l1, [])
        rec.append(float(np.mean([scores.get(s, 0.5) for s in leaves])) if leaves else 0.5)
        lat.append(latent_macro.get(l1, 0.1))
    sp, _ = spearmanr(rec, lat)
    return float(sp) if not np.isnan(sp) else 0.0

def leaf_recovery(scores, latent_leaf, l1_to_leaf):
    all_leaves = [s for lv in l1_to_leaf.values() for s in lv]
    rec = [scores.get(s, 0.5) for s in all_leaves]
    lat = [latent_leaf.get(s, 0.0)  for s in all_leaves]
    sp, _ = spearmanr(rec, lat)
    return float(sp) if not np.isnan(sp) else 0.0

def dominant_leaf_recovery(scores, latent_leaf, dominant_l1s, l1_to_leaf):
    """
    Leaf Spearman RESTRICTIONAT la categoriile dominante ale userului.
    Aceasta e metrica cheie: masoara discriminarea within-category
    tocmai unde conteaza (preferintele principale ale userului).
    """
    dom_leaves = [s for l1 in dominant_l1s for s in l1_to_leaf.get(l1, [])]
    if len(dom_leaves) < 3:
        return float("nan")
    rec = [scores.get(s, 0.5) for s in dom_leaves]
    lat = [latent_leaf.get(s, 0.0)  for s in dom_leaves]
    sp, _ = spearmanr(rec, lat)
    return float(sp) if not np.isnan(sp) else 0.0

def coverage_in_dominant(scores, dominant_l1s, l1_to_leaf):
    """Cate taguri din categoriile dominante au scor != 0.5."""
    dom_leaves = [s for l1 in dominant_l1s for s in l1_to_leaf.get(l1, [])]
    covered = sum(1 for s in dom_leaves if scores.get(s, 0.5) != 0.5)
    return covered, len(dom_leaves)


# ─────────────────────────────────────────────────────────────────────────────
# Variante quiz
# ─────────────────────────────────────────────────────────────────────────────

def _swipe(tag_scores, slug, latent_leaf, rng):
    lat = latent_leaf.get(slug, 0.08)
    p   = 1.0 / (1.0 + math.exp(-5.0 * (lat - 0.5)))
    delta = RIGHT_WEIGHT if rng.random() < p else LEFT_WEIGHT
    adjust_tag_score(tag_scores, slug, delta, bayesian=True)
    return delta


def quiz_baseline(latent_leaf, l1_to_leaf, rng):
    """Quiz curent: round-robin L1, 15-20 carduri."""
    tag_scores, seen = {}, set()
    n = int(rng.integers(MIN_CARDS, MAX_CARDS + 1))
    cp = 0
    for _ in range(n):
        slug = None
        for _ in range(len(L1_SLUGS)):
            l1 = L1_SLUGS[cp % len(L1_SLUGS)]
            cp += 1
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


def apply_prior(tag_scores, l1_to_leaf, strength=PRIOR_STR):
    result = dict(tag_scores)
    for l1, leaves in l1_to_leaf.items():
        obs = [tag_scores[s] for s in leaves if s in tag_scores]
        if not obs:
            continue
        agg = float(np.mean(obs))
        for s in leaves:
            if s not in result:
                result[s] = 0.5 + strength * (agg - 0.5)
    return result


def _l1_aggregate(tag_scores, l1_to_leaf):
    """Scorul mediu observat per L1 categorie."""
    agg = {}
    for l1, leaves in l1_to_leaf.items():
        obs = [tag_scores[s] for s in leaves if s in tag_scores]
        agg[l1] = float(np.mean(obs)) if obs else 0.5
    return agg


def quiz_hierarchical(latent_leaf, l1_to_leaf, rng, n_dominant=2):
    """
    Quiz ierarhic in doua faze, ACELASI numar total de carduri ca baseline.

    Faza 1 — broad survey: 1 card per L1 categorie (8 carduri)
      Scop: identifica care L1 categorii sunt dominante pentru acest user.
      Problema: selectia aleatoare poate alege un tag nereprezentativ
      (de ex. `beach-water` pentru un user care iubeste hiking dar nu plaja).
      Aceasta e limitarea inerenta a unui singur swipe per categorie.

    Faza 2 — drill-down: N_TOTAL - N_PHASE1 carduri (12) focalizate exclusiv
      pe top-{n_dominant} L1 categorii identificate in Faza 1.
      Acoperire: ~6 carduri per categorie dominanta (vs ~2.5 in baseline).

    n_dominant: 2 → mehr Tiefe, 3 → mai multa latime
    """
    tag_scores, seen = {}, set()

    # ── Faza 1: 1 card aleatoriu per L1 ──────────────────────────────────────
    for l1 in L1_SLUGS:
        cands = [s for s in l1_to_leaf.get(l1, []) if s not in seen]
        if not cands:
            continue
        slug = cands[int(rng.integers(0, len(cands)))]
        seen.add(slug)
        _swipe(tag_scores, slug, latent_leaf, rng)

    # Identifica categoriile dominante dupa Faza 1
    l1_agg = _l1_aggregate(tag_scores, l1_to_leaf)
    sorted_l1 = sorted(l1_agg.items(), key=lambda x: -x[1])
    dominant = [l1 for l1, _ in sorted_l1[:n_dominant]]

    # ── Faza 2: drill-down in categoriile dominante ───────────────────────────
    n_phase2 = N_TOTAL - N_PHASE1
    cp = 0
    cards_phase2 = 0

    for _ in range(n_phase2):
        slug = None
        for _ in range(len(dominant)):
            l1 = dominant[cp % len(dominant)]
            cp += 1
            cands = [s for s in l1_to_leaf.get(l1, []) if s not in seen]
            if cands:
                slug = cands[int(rng.integers(0, len(cands)))]
                break
        if slug is None:
            break
        seen.add(slug)
        _swipe(tag_scores, slug, latent_leaf, rng)
        cards_phase2 += 1

        if len(seen) >= MIN_CARDS and compute_entropy(tag_scores) < 1.0:
            break

    return tag_scores, dominant   # returnam si categoriile identificate


def quiz_hier_only(latent_leaf, l1_to_leaf, rng, n_dominant=2):
    """Wrapper care returneaza doar tag_scores (compatibil cu API comun)."""
    scores, _ = quiz_hierarchical(latent_leaf, l1_to_leaf, rng, n_dominant)
    return scores


# ─────────────────────────────────────────────────────────────────────────────
# Rulare comparatie
# ─────────────────────────────────────────────────────────────────────────────

def run(users, data):
    print(f"\nTest quiz ierarhic | {N_USERS} useri | SEED={SEED}")
    print(f"  N_PHASE1={N_PHASE1}  N_TOTAL={N_TOTAL}  n_dominant=[2,3]  prior_strength={PRIOR_STR}")
    print(f"  Faza 2 depth: {N_TOTAL-N_PHASE1} carduri pe top-2 L1 = "
          f"~{(N_TOTAL-N_PHASE1)//2:.0f} carduri/categorie dominanta "
          f"(vs ~{N_TOTAL//len(L1_SLUGS):.0f} in baseline)\n")

    rows = []
    phase1_accuracy = []   # cat de des Phase 1 identifica corect categoriile dominante

    for user in users:
        uid = user["user_id"]
        rng_u = np.random.default_rng(SEED + uid)

        # Baseline
        b_scores = quiz_baseline(user["latent_leaf"], data["l1_to_leaf"],
                                  np.random.default_rng(SEED + uid))
        # Hier2
        h2_scores, h2_dom = quiz_hierarchical(
            user["latent_leaf"], data["l1_to_leaf"],
            np.random.default_rng(SEED + uid), n_dominant=2
        )
        # Hier3
        h3_scores, h3_dom = quiz_hierarchical(
            user["latent_leaf"], data["l1_to_leaf"],
            np.random.default_rng(SEED + uid), n_dominant=3
        )

        # Acuratetea identificarii categoriilor dominante in Faza 1
        true_dom = set(user["dominant"])
        h2_recall = len(true_dom & set(h2_dom)) / len(true_dom) if true_dom else 0.0
        h3_recall = len(true_dom & set(h3_dom)) / len(true_dom) if true_dom else 0.0
        phase1_accuracy.append({
            "user_id": uid,
            "n_true_dominant": len(true_dom),
            "h2_recall": h2_recall,
            "h3_recall": h3_recall,
            "h2_correct": h2_recall == 1.0,
            "h3_correct": h3_recall == 1.0,
        })

        all_scores = {
            "baseline":    b_scores,
            "baseline+p":  apply_prior(b_scores,  data["l1_to_leaf"]),
            "hier2":       h2_scores,
            "hier2+p":     apply_prior(h2_scores, data["l1_to_leaf"]),
            "hier3":       h3_scores,
            "hier3+p":     apply_prior(h3_scores, data["l1_to_leaf"]),
        }

        row = {
            "user_id": uid,
            "dominant": "|".join(user["dominant"]),
            "n_dominant": len(user["dominant"]),
            "h2_dom": "|".join(h2_dom),
            "h3_dom": "|".join(h3_dom),
            "h2_recall_phase1": round(h2_recall, 3),
            "h3_recall_phase1": round(h3_recall, 3),
        }

        for vname, scores in all_scores.items():
            row[f"leaf_{vname}"]  = round(leaf_recovery(
                scores, user["latent_leaf"], data["l1_to_leaf"]), 4)
            row[f"macro_{vname}"] = round(macro_recovery(
                scores, user["latent_macro"], data["l1_to_leaf"]), 4)
            row[f"cov_{vname}"]   = sum(
                1 for s, v in scores.items() if v != 0.5)

            # Dominant-leaf: restricted la TRUE dominant categories
            row[f"dom_leaf_{vname}"] = round(dominant_leaf_recovery(
                scores, user["latent_leaf"], user["dominant"], data["l1_to_leaf"]), 4)

        rows.append(row)

    df = pd.DataFrame(rows)
    df_phase1 = pd.DataFrame(phase1_accuracy)
    return df, df_phase1


# ─────────────────────────────────────────────────────────────────────────────
# Raportare
# ─────────────────────────────────────────────────────────────────────────────

VNAMES = ["baseline", "baseline+p", "hier2", "hier2+p", "hier3", "hier3+p"]
VLABELS = {
    "baseline":   "Baseline",
    "baseline+p": "Baseline\n+Prior",
    "hier2":      "Hier-2",
    "hier2+p":    "Hier-2\n+Prior",
    "hier3":      "Hier-3",
    "hier3+p":    "Hier-3\n+Prior",
}
VCOLORS = {
    "baseline":   "#9E9E9E",
    "baseline+p": "#FF9800",
    "hier2":      "#1565C0",
    "hier2+p":    "#42A5F5",
    "hier3":      "#1B5E20",
    "hier3+p":    "#66BB6A",
}


def report(df, df_phase1):
    b_leaf  = df["leaf_baseline"].mean()
    b_macro = df["macro_baseline"].mean()
    b_dom   = df["dom_leaf_baseline"].mean()

    print("=" * 72)
    print(f"  {'Varianta':<14} {'Leaf':>7} {'dLeaf':>7} "
          f"{'Macro':>7} {'dMacro':>7} "
          f"{'DomLeaf':>9} {'dDomLeaf':>9} {'Cov':>5}")
    print("  " + "-" * 68)
    for v in VNAMES:
        leaf  = df[f"leaf_{v}"].mean()
        macro = df[f"macro_{v}"].mean()
        dom   = df[f"dom_leaf_{v}"].mean()
        cov   = df[f"cov_{v}"].mean()
        print(f"  {v:<14} {leaf:>7.4f} {leaf-b_leaf:>+7.4f} "
              f"{macro:>7.4f} {macro-b_macro:>+7.4f} "
              f"{dom:>9.4f} {dom-b_dom:>+9.4f} {cov:>5.1f}")

    # Semnificatie statistica pe dominant-leaf (metrica cheie)
    print(f"\n  Semnificatie statistica dominant-leaf (Wilcoxon vs baseline):")
    print(f"  {'Varianta':<14}  {'p-value':>10}  {'sig':>6}")
    print("  " + "-" * 34)
    for v in [k for k in VNAMES if k != "baseline"]:
        try:
            _, p = wilcoxon(df[f"dom_leaf_{v}"], df["dom_leaf_baseline"],
                            alternative="greater")
        except Exception:
            p = float("nan")
        sig = "**" if p < 0.05 else ("*" if p < 0.10 else "ns")
        print(f"  {v:<14}  {p:>10.4f}  {sig:>6}")

    # Acuratetea Phase 1
    h2_acc = df_phase1["h2_correct"].mean()
    h3_acc = df_phase1["h3_correct"].mean()
    h2_rec = df_phase1["h2_recall"].mean()
    h3_rec = df_phase1["h3_recall"].mean()
    print(f"\n  Acuratete identificare dominante in Faza 1:")
    print(f"  Hier-2: {h2_acc*100:.1f}% identifica corect TOATE categoriile "
          f"| recall mediu {h2_rec:.3f}")
    print(f"  Hier-3: {h3_acc*100:.1f}% identifica corect TOATE categoriile "
          f"| recall mediu {h3_rec:.3f}")
    print(f"\n  NOTA: Faza 1 alege ALEATORIU 1 tag per L1. Daca tagul ales")
    print(f"  nu e reprezentativ (e.g. beach-water pt un user de hiking),")
    print(f"  Phase 1 poate misidentifica categoria dominanta.")
    print(f"  Acuratetea actuala reflecta aceasta limitare reala.")

    print("=" * 72)
    return h2_acc, h3_acc


def make_plots(df, h2_acc, h3_acc):
    metrics = [
        ("leaf",     "Leaf recovery\n(161 frunze)",     True),
        ("macro",    "Macro recovery\n(8 L1)",           False),
        ("dom_leaf", "Dominant-leaf recovery\n(cheie)", True),
    ]

    fig, axes = plt.subplots(1, 3, figsize=(15, 5))

    for ax, (mkey, mtitle, highlight) in zip(axes, metrics):
        means = [df[f"{mkey}_{v}"].mean() for v in VNAMES]
        stds  = [df[f"{mkey}_{v}"].std()  for v in VNAMES]
        clrs  = [VCOLORS[v] for v in VNAMES]
        edge  = ["red" if highlight and v.startswith("hier") else "black"
                 for v in VNAMES]
        lw    = [2.0 if highlight and v.startswith("hier") else 0.6
                 for v in VNAMES]
        bars  = ax.bar([VLABELS[v] for v in VNAMES], means, yerr=stds,
                       capsize=4, color=clrs, edgecolor=edge, linewidth=lw)
        ax.axhline(means[0], color="gray", linewidth=0.8, linestyle="--", alpha=0.5)
        ax.set_title(mtitle, fontsize=10)
        ax.set_ylabel("Spearman")
        ax.set_ylim(0, min(1.0, max(means) * 1.45))
        ax.tick_params(axis="x", labelsize=8)
        for bar, m, s in zip(bars, means, stds):
            ax.text(bar.get_x() + bar.get_width()/2,
                    bar.get_height() + s + 0.01,
                    f"{m:.3f}", ha="center", va="bottom", fontsize=8,
                    fontweight="bold")

    plt.suptitle(
        f"Quiz Ierarhic vs Baseline  "
        f"(Phase1 accuracy: Hier-2={h2_acc*100:.0f}%, Hier-3={h3_acc*100:.0f}%)",
        fontsize=11
    )
    plt.tight_layout()
    plt.savefig(os.path.join(RESULTS_DIR, "hierarchical_recovery.png"), dpi=150)
    plt.close()

    # Distributie dominant-leaf per varianta
    fig, ax = plt.subplots(figsize=(10, 4))
    plot_data = [df[f"dom_leaf_{v}"].values for v in VNAMES]
    bp = ax.boxplot(plot_data,
                    tick_labels=[VLABELS[v] for v in VNAMES],
                    patch_artist=True,
                    medianprops=dict(color="red", linewidth=1.5))
    for patch, v in zip(bp["boxes"], VNAMES):
        patch.set_facecolor(VCOLORS[v])
        patch.set_alpha(0.75)
    ax.set_ylabel("Dominant-leaf Spearman")
    ax.set_title("Distributia recuperarii within-category (categorii dominante)")
    ax.tick_params(axis="x", labelsize=8)
    plt.tight_layout()
    plt.savefig(os.path.join(RESULTS_DIR, "hierarchical_dominant_leaf_dist.png"), dpi=150)
    plt.close()

    # Phase 1 accuracy vs n_dominant per user
    fig, ax = plt.subplots(figsize=(7, 4))
    df2 = df[["n_dominant", "h2_recall_phase1", "h3_recall_phase1"]].copy()
    for n_dom in df2["n_dominant"].unique():
        sub = df2[df2["n_dominant"] == n_dom]
        ax.scatter([n_dom - 0.1] * len(sub), sub["h2_recall_phase1"],
                   alpha=0.5, color="#1565C0", s=30, label="Hier-2" if n_dom == 2 else "")
        ax.scatter([n_dom + 0.1] * len(sub), sub["h3_recall_phase1"],
                   alpha=0.5, color="#1B5E20", s=30, label="Hier-3" if n_dom == 2 else "")
    ax.set_xticks([2, 3])
    ax.set_xticklabels(["2 dominante\n(in profil)", "3 dominante\n(in profil)"])
    ax.set_ylabel("Recall Phase 1")
    ax.set_ylim(-0.05, 1.15)
    ax.axhline(1.0, color="gray", linestyle="--", alpha=0.4)
    ax.set_title("Acuratete identificare dominante in Faza 1")
    ax.legend()
    plt.tight_layout()
    plt.savefig(os.path.join(RESULTS_DIR, "hierarchical_phase1_accuracy.png"), dpi=150)
    plt.close()

    print(f"  Salvat: hierarchical_recovery.png")
    print(f"  Salvat: hierarchical_dominant_leaf_dist.png")
    print(f"  Salvat: hierarchical_phase1_accuracy.png")


# ─────────────────────────────────────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────────────────────────────────────

def main():
    print("\n" + "=" * 72)
    print("  Quiz Ierarhic — Test Empiric")
    print(f"  SEED={SEED} | N={N_USERS} | Phase1={N_PHASE1} carduri | Total={N_TOTAL}")
    print("=" * 72)

    db = SessionLocal()
    try:
        data = load_data(db)
    finally:
        db.close()

    users = generate_users(data["l1_to_leaf"], _rng)
    df, df_phase1 = run(users, data)

    print("\n" + "=" * 72)
    h2_acc, h3_acc = report(df, df_phase1)
    print("=" * 72)

    make_plots(df, h2_acc, h3_acc)

    df.to_csv(os.path.join(RESULTS_DIR, "hierarchical_per_user.csv"), index=False)
    df_phase1.to_csv(os.path.join(RESULTS_DIR, "hierarchical_phase1.csv"), index=False)
    print(f"  Salvat: hierarchical_per_user.csv, hierarchical_phase1.csv")


if __name__ == "__main__":
    main()
