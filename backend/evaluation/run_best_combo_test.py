#!/usr/bin/env python3
"""
backend/evaluation/run_best_combo_test.py
==========================================
Test focalizat: Prior ierarhic vs SemTag-L1 vs combinatia lor.

Variante comparate:
  1. baseline        — quiz Bayesian curent (referinta)
  2. prior           — + prior ierarhic post-quiz
  3. semtag_l1       — + sentence transformers filtrat L1 (swipe multi-tag)
  4. semtag_l1+prior — combinatia (semtag_l1 THEN prior pe taguri ramase)

Metrici:
  - Leaf recovery (Spearman pe 161 taguri-frunza)
  - Macro recovery (Spearman pe 8 macro-categorii)
  - Coverage (% taguri cu scor != 0.5)
  - Per-L1 breakdown: care categorii beneficiaza mai mult

Test statistic: Wilcoxon signed-rank (paired, one-sided: varianta > baseline).

Rulare:
    python -m evaluation.run_best_combo_test
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
PRIOR_STRENGTH = 0.30
SEMTAG_TOP_K = 4
SEMTAG_MIN_SIM = 0.40


# ─────────────────────────────────────────────────────────────────────────────
# Incarcare date + embeddings
# ─────────────────────────────────────────────────────────────────────────────

def load_data(db):
    print("Incarcare date si calcul embeddings...")
    all_tags = db.query(Tag).all()
    all_tag_ids = [t.id for t in all_tags]
    slug_to_tag = {t.slug: t for t in all_tags}

    # L1 -> frunze
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

    # slug -> L1
    slug_to_l1 = {}
    for l1, leaves in l1_to_leaf.items():
        for s in leaves:
            slug_to_l1[s] = l1

    # Sentence Transformer: vecini semantici filtrati la L1
    from sentence_transformers import SentenceTransformer
    leaf_tags = [t for t in all_tags if t.is_leaf]
    leaf_slugs = [t.slug for t in leaf_tags]
    texts = [t.name + (f": {t.description}" if t.description else "") for t in leaf_tags]

    model = SentenceTransformer("all-MiniLM-L6-v2")
    embs = model.encode(texts, normalize_embeddings=True, show_progress_bar=False)
    sim_matrix = embs @ embs.T

    slug_to_sem_l1 = {}
    for i, slug in enumerate(leaf_slugs):
        l1_s = slug_to_l1.get(slug)
        ranked = sorted(
            [(leaf_slugs[j], float(sim_matrix[i, j]))
             for j in range(len(leaf_slugs))
             if j != i and slug_to_l1.get(leaf_slugs[j]) == l1_s and l1_s is not None],
            key=lambda x: -x[1]
        )
        neighbors = [(s, sim) for s, sim in ranked if sim >= SEMTAG_MIN_SIM][:SEMTAG_TOP_K]
        if neighbors:
            slug_to_sem_l1[slug] = neighbors

    n_with = sum(1 for v in slug_to_sem_l1.values() if v)
    avg = sum(len(v) for v in slug_to_sem_l1.values()) / max(1, n_with)
    print(f"  {len(leaf_tags)} frunze | {n_with} cu vecini semantici L1 (medie {avg:.1f}/tag)")

    return {
        "all_tags": all_tags,
        "all_tag_ids": all_tag_ids,
        "l1_to_leaf": l1_to_leaf,
        "slug_to_l1": slug_to_l1,
        "slug_to_sem_l1": slug_to_sem_l1,
        "leaf_slugs": leaf_slugs,
    }


# ─────────────────────────────────────────────────────────────────────────────
# Generare useri sintetici
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
    all_leaves = [s for leaves in l1_to_leaf.values() for s in leaves]
    rec = [scores.get(s, 0.5) for s in all_leaves]
    lat = [latent_leaf.get(s, 0.0) for s in all_leaves]
    sp, _ = spearmanr(rec, lat)
    return float(sp) if not np.isnan(sp) else 0.0

def per_l1_leaf_recovery(scores, latent_leaf, l1_to_leaf):
    """Spearman leaf per fiecare L1 categorie separat."""
    result = {}
    for l1, leaves in l1_to_leaf.items():
        if len(leaves) < 3:
            result[l1] = float("nan")
            continue
        rec = [scores.get(s, 0.5) for s in leaves]
        lat = [latent_leaf.get(s, 0.0) for s in leaves]
        sp, _ = spearmanr(rec, lat)
        result[l1] = float(sp) if not np.isnan(sp) else 0.0
    return result

def coverage(scores):
    return sum(1 for v in scores.values() if v != 0.5)


# ─────────────────────────────────────────────────────────────────────────────
# Variante quiz
# ─────────────────────────────────────────────────────────────────────────────

def _pick_card(l1_to_leaf, seen, cycle_pos, rng):
    for _ in range(len(L1_SLUGS)):
        l1 = L1_SLUGS[cycle_pos % len(L1_SLUGS)]
        cycle_pos += 1
        cands = [s for s in l1_to_leaf.get(l1, []) if s not in seen]
        if cands:
            return cands[int(rng.integers(0, len(cands)))], cycle_pos
    return None, cycle_pos


def quiz_baseline(latent_leaf, l1_to_leaf, rng):
    tag_scores, seen = {}, set()
    n = int(rng.integers(MIN_CARDS, MAX_CARDS + 1))
    cp = 0
    for _ in range(n):
        slug, cp = _pick_card(l1_to_leaf, seen, cp, rng)
        if slug is None:
            break
        seen.add(slug)
        lat = latent_leaf.get(slug, 0.08)
        p = 1.0 / (1.0 + math.exp(-5.0 * (lat - 0.5)))
        adjust_tag_score(tag_scores, slug, RIGHT_WEIGHT if rng.random() < p else LEFT_WEIGHT, True)
        if len(seen) >= MIN_CARDS and compute_entropy(tag_scores) < 1.0:
            break
    return tag_scores


def apply_prior(tag_scores, l1_to_leaf, strength=PRIOR_STRENGTH):
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


def quiz_semtag_l1(latent_leaf, l1_to_leaf, slug_to_sem_l1, rng):
    tag_scores, seen = {}, set()
    n = int(rng.integers(MIN_CARDS, MAX_CARDS + 1))
    cp = 0
    for _ in range(n):
        t1, cp = _pick_card(l1_to_leaf, seen, cp, rng)
        if t1 is None:
            break
        seen.add(t1)
        nbrs = [(s, sim) for s, sim in slug_to_sem_l1.get(t1, []) if s not in seen][:3]
        image_tags = [(t1, 1.0)] + nbrs
        lat_mean = float(np.mean([latent_leaf.get(s, 0.08) for s, _ in image_tags[:3]]))
        p = 1.0 / (1.0 + math.exp(-5.0 * (lat_mean - 0.5)))
        base = RIGHT_WEIGHT if rng.random() < p else LEFT_WEIGHT
        for slug, w in image_tags:
            adjust_tag_score(tag_scores, slug, base * w, True)
        if len(seen) >= MIN_CARDS and compute_entropy(tag_scores) < 1.0:
            break
    return tag_scores


def quiz_semtag_l1_with_prior(latent_leaf, l1_to_leaf, slug_to_sem_l1, rng):
    return apply_prior(
        quiz_semtag_l1(latent_leaf, l1_to_leaf, slug_to_sem_l1, rng),
        l1_to_leaf
    )


# ─────────────────────────────────────────────────────────────────────────────
# Rulare principala
# ─────────────────────────────────────────────────────────────────────────────

VARIANTS = {
    "baseline":        lambda u, d, r: quiz_baseline(u["latent_leaf"], d["l1_to_leaf"], r),
    "prior":           lambda u, d, r: apply_prior(quiz_baseline(u["latent_leaf"], d["l1_to_leaf"], r), d["l1_to_leaf"]),
    "semtag_l1":       lambda u, d, r: quiz_semtag_l1(u["latent_leaf"], d["l1_to_leaf"], d["slug_to_sem_l1"], r),
    "semtag_l1+prior": lambda u, d, r: quiz_semtag_l1_with_prior(u["latent_leaf"], d["l1_to_leaf"], d["slug_to_sem_l1"], r),
}


def run(users, data):
    print(f"\nTest {len(VARIANTS)} variante pe {N_USERS} useri | SEED={SEED}")
    print(f"  PRIOR_STRENGTH={PRIOR_STRENGTH} | SEMTAG_MIN_SIM={SEMTAG_MIN_SIM}\n")

    rows = []
    per_l1_rows = []

    for user in users:
        uid = user["user_id"]
        row = {"user_id": uid, "dominant": "|".join(user["dominant"])}

        for vname, vfn in VARIANTS.items():
            scores = vfn(user, data, np.random.default_rng(SEED + uid))
            row[f"leaf_{vname}"]  = round(leaf_recovery(scores, user["latent_leaf"], data["l1_to_leaf"]), 4)
            row[f"macro_{vname}"] = round(macro_recovery(scores, user["latent_macro"], data["l1_to_leaf"]), 4)
            row[f"cov_{vname}"]   = coverage(scores)

            # Per-L1 breakdown
            per_l1 = per_l1_leaf_recovery(scores, user["latent_leaf"], data["l1_to_leaf"])
            for l1, sp in per_l1.items():
                per_l1_rows.append({
                    "user_id": uid, "variant": vname, "l1": l1, "spearman": sp
                })

        rows.append(row)

    df = pd.DataFrame(rows)
    df_l1 = pd.DataFrame(per_l1_rows)
    return df, df_l1


# ─────────────────────────────────────────────────────────────────────────────
# Raportare
# ─────────────────────────────────────────────────────────────────────────────

def report(df, df_l1):
    vnames = list(VARIANTS.keys())
    b_leaf  = df["leaf_baseline"].mean()
    b_macro = df["macro_baseline"].mean()

    print("=" * 68)
    print(f"  {'Varianta':<20} {'Leaf':>7} {'dLeaf':>7} {'Macro':>7} {'dMacro':>7} {'Cov':>5}")
    print("  " + "-" * 54)
    for v in vnames:
        leaf  = df[f"leaf_{v}"].mean()
        macro = df[f"macro_{v}"].mean()
        cov   = df[f"cov_{v}"].mean()
        print(f"  {v:<20} {leaf:>7.4f} {leaf-b_leaf:>+7.4f} "
              f"{macro:>7.4f} {macro-b_macro:>+7.4f} {cov:>5.1f}")

    # Semnificatie statistica (Wilcoxon, leaf + macro)
    print(f"\n  Semnificatie statistica (Wilcoxon vs baseline, one-sided):")
    print(f"  {'Varianta':<20} {'leaf p':>9} {'leaf sig':>10} {'macro p':>9} {'macro sig':>10}")
    print("  " + "-" * 62)
    for v in [k for k in vnames if k != "baseline"]:
        try:
            _, pl = wilcoxon(df[f"leaf_{v}"],  df["leaf_baseline"],  alternative="greater")
        except Exception:
            pl = float("nan")
        try:
            _, pm = wilcoxon(df[f"macro_{v}"], df["macro_baseline"], alternative="greater")
        except Exception:
            pm = float("nan")
        sl = "**" if pl < 0.05 else ("*" if pl < 0.10 else "ns")
        sm = "**" if pm < 0.05 else ("*" if pm < 0.10 else "ns")
        print(f"  {v:<20} {pl:>9.4f} {sl:>10} {pm:>9.4f} {sm:>10}")

    # Per-L1 breakdown: medie leaf Spearman per categorie
    print(f"\n  Leaf recovery per L1 categorie (medie useri):")
    pivot = df_l1.groupby(["l1","variant"])["spearman"].mean().unstack("variant")
    pivot = pivot.reindex(columns=vnames)
    short = {"nature-outdoors":"nature", "culture-history":"culture",
             "nightlife-social":"nightlife", "adventure-active":"adventure",
             "food-drink":"food", "wellness-slow":"wellness",
             "urban-modern":"urban", "family-comfort":"family"}
    print(f"  {'L1':<12}", end="")
    for v in vnames:
        print(f" {v[:11]:>12}", end="")
    print()
    print("  " + "-" * (12 + 13 * len(vnames)))
    for l1 in L1_SLUGS:
        row_vals = pivot.loc[l1] if l1 in pivot.index else [float("nan")]*len(vnames)
        print(f"  {short.get(l1,l1):<12}", end="")
        for v in vnames:
            val = pivot.loc[l1, v] if l1 in pivot.index and v in pivot.columns else float("nan")
            print(f" {val:>12.4f}", end="")
        print()

    return pivot


# ─────────────────────────────────────────────────────────────────────────────
# Grafice
# ─────────────────────────────────────────────────────────────────────────────

def make_plots(df, df_l1, pivot):
    vnames = list(VARIANTS.keys())
    colors = {"baseline": "#9E9E9E", "prior": "#FF9800",
              "semtag_l1": "#7B1FA2", "semtag_l1+prior": "#4CAF50"}
    labels = {"baseline": "Baseline", "prior": "+Prior",
              "semtag_l1": "+SemTag\n(L1)", "semtag_l1+prior": "+SemTag(L1)\n+Prior"}

    # ── 1. Bar: leaf + macro recovery ────────────────────────────────────────
    fig, axes = plt.subplots(1, 2, figsize=(11, 5))
    for ax, metric, title in [
        (axes[0], "leaf",  "Leaf recovery (161 taguri-frunza)"),
        (axes[1], "macro", "Macro recovery (8 L1 categorii)"),
    ]:
        means = [df[f"{metric}_{v}"].mean() for v in vnames]
        stds  = [df[f"{metric}_{v}"].std()  for v in vnames]
        clrs  = [colors[v] for v in vnames]
        bars  = ax.bar([labels[v] for v in vnames], means, yerr=stds,
                       capsize=5, color=clrs, edgecolor="black", linewidth=0.6)
        ax.axhline(means[0], color="gray", linewidth=0.8, linestyle="--", alpha=0.5)
        ax.set_title(title)
        ax.set_ylabel("Spearman rank corr.")
        ax.set_ylim(0, min(1.0, max(means) * 1.40))
        for bar, m, s in zip(bars, means, stds):
            ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + s + 0.01,
                    f"{m:.4f}", ha="center", va="bottom", fontsize=9, fontweight="bold")
    plt.suptitle("Prior vs SemTag-L1 vs Combinatie", fontsize=12)
    plt.tight_layout()
    plt.savefig(os.path.join(RESULTS_DIR, "best_combo_recovery.png"), dpi=150)
    plt.close()

    # ── 2. Per-L1 heatmap ─────────────────────────────────────────────────────
    short = {"nature-outdoors":"nature", "culture-history":"culture",
             "nightlife-social":"nightlife", "adventure-active":"adventure",
             "food-drink":"food", "wellness-slow":"wellness",
             "urban-modern":"urban", "family-comfort":"family"}
    data_plot = pivot.rename(index=short, columns=labels).reindex(
        index=[short.get(l1, l1) for l1 in L1_SLUGS],
        columns=[labels[v] for v in vnames]
    )

    fig, ax = plt.subplots(figsize=(9, 5))
    import matplotlib.colors as mcolors
    im = ax.imshow(data_plot.values.astype(float), aspect="auto",
                   cmap="RdYlGn", vmin=-0.2, vmax=0.8)
    ax.set_xticks(range(len(vnames)))
    ax.set_xticklabels([labels[v] for v in vnames], fontsize=10)
    ax.set_yticks(range(len(L1_SLUGS)))
    ax.set_yticklabels([short.get(l1, l1) for l1 in L1_SLUGS], fontsize=10)
    plt.colorbar(im, ax=ax, label="Leaf Spearman per L1")
    for i in range(len(L1_SLUGS)):
        for j in range(len(vnames)):
            val = data_plot.values[i, j]
            if not np.isnan(val):
                ax.text(j, i, f"{val:.2f}", ha="center", va="center",
                        fontsize=9, color="black" if 0.2 < val < 0.7 else "white")
    ax.set_title("Leaf recovery per L1 categorie")
    plt.tight_layout()
    plt.savefig(os.path.join(RESULTS_DIR, "best_combo_per_l1.png"), dpi=150)
    plt.close()

    # ── 3. Distributie leaf recovery (violin) ────────────────────────────────
    fig, ax = plt.subplots(figsize=(9, 4))
    plot_data = [df[f"leaf_{v}"].values for v in vnames]
    parts = ax.violinplot(plot_data, positions=range(len(vnames)),
                          showmedians=True, showextrema=True)
    for body, v in zip(parts["bodies"], vnames):
        body.set_facecolor(colors[v])
        body.set_alpha(0.7)
    ax.set_xticks(range(len(vnames)))
    ax.set_xticklabels([labels[v] for v in vnames])
    ax.set_ylabel("Leaf Spearman")
    ax.set_title("Distributia Leaf Recovery — 50 useri")
    plt.tight_layout()
    plt.savefig(os.path.join(RESULTS_DIR, "best_combo_distribution.png"), dpi=150)
    plt.close()

    print(f"\n  Salvat: best_combo_recovery.png")
    print(f"  Salvat: best_combo_per_l1.png")
    print(f"  Salvat: best_combo_distribution.png")


# ─────────────────────────────────────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────────────────────────────────────

def main():
    print("\n" + "=" * 68)
    print("  Prior vs SemTag-L1 vs Combinatie — Test Focalizat")
    print(f"  SEED={SEED} | N={N_USERS} | prior_strength={PRIOR_STRENGTH} | semtag_sim>={SEMTAG_MIN_SIM}")
    print("=" * 68)

    db = SessionLocal()
    try:
        data = load_data(db)
    finally:
        db.close()

    users = generate_users(data["l1_to_leaf"], _rng)
    df, df_l1 = run(users, data)

    print("\n" + "=" * 68)
    pivot = report(df, df_l1)
    print("=" * 68)

    make_plots(df, df_l1, pivot)

    df.to_csv(os.path.join(RESULTS_DIR, "best_combo_per_user.csv"), index=False)
    df_l1.to_csv(os.path.join(RESULTS_DIR, "best_combo_per_l1.csv"), index=False)
    print(f"  Salvat: best_combo_per_user.csv, best_combo_per_l1.csv")


if __name__ == "__main__":
    main()
