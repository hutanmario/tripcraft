#!/usr/bin/env python3
"""
backend/evaluation/run_quiz_variants_test.py
============================================
Test complet variante quiz — nu modifică producția.

Variante (toate cu prior ierarhic final):
  baseline          — 20 carduri round-robin
  baseline+p        — baseline + prior ierarhic
  hier2+p           — Phase1: 1 card random/L1 → top-2 → Phase2 12 depth + prior
  cf_6040+p         — Phase1 explicit + 60/40 depth/explore + prior
  cf_sp_pure_mod    — Phase1 explicit → prior moderat pe frunze → Phase2 20 depth pur
  cf_sp_pure_str    — idem, prior tare
  cf_sp_8020_mod    — Phase1 explicit → prior moderat → Phase2 80/20 + prior
  cf_sp_8020_str    — idem, prior tare

Parametri prior tare din selectie:
  Moderat: selected→0.65, non-selected→0.38
  Tare:    selected→0.82, non-selected→0.25

Metrici: Spearman leaf-global, macro (L1), dominant-leaf.
Semnificatie: Wilcoxon paired vs baseline si vs hier2+p.
Robustete zgomot: 0/10/20% swipe-uri inversate.
Runtime: per user, medie si p95.

Output:
  quiz_variants_metrics.csv
  quiz_significance.csv
  quiz_noise_robustness.csv
  quiz_variants_bars.png
  quiz_noise_robustness.png
  SUMMARY_QUIZ.md

Rulare:
  python -m evaluation.run_quiz_variants_test
"""

import sys, os, math, time, logging
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

L1_SLUGS = list(L1_ORDER)
N_USERS  = 50
N_PHASE2 = 20
N_HIER_TOTAL = 20
N_HIER_P1    = 8

# Prior ierarhic final (aceeasi ca in testele anterioare)
HIER_PRIOR_STR = 0.30

# Prior din selectia Phase 1 — doua intensitati
SEL_PRIOR_MOD_SEL    = 0.65   # frunze selectate — moderat
SEL_PRIOR_MOD_NONSEL = 0.38   # frunze ne-selectate — moderat
SEL_PRIOR_STR_SEL    = 0.82   # frunze selectate — tare
SEL_PRIOR_STR_NONSEL = 0.25   # frunze ne-selectate — tare

# Phase 1 UI constraints
MAX_SELECTED = 4
MIN_SELECTED = 1

# Variante principale
VNAMES = [
    "baseline", "baseline+p", "hier2+p",
    "cf_6040+p",
    "cf_sp_pure_mod", "cf_sp_pure_str",
    "cf_sp_8020_mod", "cf_sp_8020_str",
]
VCOLORS = {
    "baseline":       "#9E9E9E",
    "baseline+p":     "#FF9800",
    "hier2+p":        "#1565C0",
    "cf_6040+p":      "#880E4F",
    "cf_sp_pure_mod": "#81C784",
    "cf_sp_pure_str": "#2E7D32",
    "cf_sp_8020_mod": "#80DEEA",
    "cf_sp_8020_str": "#006064",
}
VLABELS = {
    "baseline":       "Baseline",
    "baseline+p":     "Base+P",
    "hier2+p":        "Hier2+P",
    "cf_6040+p":      "CF\n60/40+P",
    "cf_sp_pure_mod": "CF-SP\nPure(mod)",
    "cf_sp_pure_str": "CF-SP\nPure(str)",
    "cf_sp_8020_mod": "CF-SP\n80/20(mod)",
    "cf_sp_8020_str": "CF-SP\n80/20(str)",
}

# Variante pentru testul de zgomot
NOISE_VNAMES = ["baseline", "hier2+p", "cf_6040+p", "cf_sp_pure_str"]
NOISE_RATES  = [0.0, 0.10, 0.20]


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
    return {"l1_to_leaf": l1_to_leaf}


# ─────────────────────────────────────────────────────────────────────────────
# Useri sintetici (aceiasi ca in testele anterioare — SEED=42)
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
# Primitiva swipe (cu suport zgomot)
# ─────────────────────────────────────────────────────────────────────────────

def _swipe(tag_scores, slug, latent_leaf, rng, noise_rate=0.0):
    lat = latent_leaf.get(slug, 0.08)
    p   = 1.0 / (1.0 + math.exp(-5.0 * (lat - 0.5)))
    if noise_rate > 0.0 and rng.random() < noise_rate:
        p = 1.0 - p   # inversam decizia cu probabilitate noise_rate
    adjust_tag_score(tag_scores, slug,
                     RIGHT_WEIGHT if rng.random() < p else LEFT_WEIGHT, True)


# ─────────────────────────────────────────────────────────────────────────────
# Prior ierarhic final (la fel ca in testele anterioare)
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


# ─────────────────────────────────────────────────────────────────────────────
# Phase 1: selectie explicita de categorii (aceeasi logica ca in testul anterior)
# ─────────────────────────────────────────────────────────────────────────────

def phase1_select(latent_macro, rng):
    probs = {
        l1: 1.0 / (1.0 + math.exp(-5.0 * (latent_macro.get(l1, 0.1) - 0.5)))
        for l1 in L1_SLUGS
    }
    raw = [l1 for l1 in L1_SLUGS if rng.random() < probs[l1]]
    if len(raw) > MAX_SELECTED:
        raw = sorted(raw, key=lambda l: -probs[l])[:MAX_SELECTED]
    if len(raw) < MIN_SELECTED:
        remaining = sorted([l for l in L1_SLUGS if l not in raw], key=lambda l: -probs[l])
        raw += remaining[:MIN_SELECTED - len(raw)]
    non_sel = [l for l in L1_SLUGS if l not in raw]
    return raw, non_sel


def phase1_accuracy(selected, dominant):
    s = set(selected)
    d = set(dominant)
    recall    = len(d & s) / len(d) if d else 0.0
    precision = len(d & s) / len(s) if s else 0.0
    return recall, precision


# ─────────────────────────────────────────────────────────────────────────────
# Initializare prior tare din selectia Phase 1
# ─────────────────────────────────────────────────────────────────────────────

def init_selection_prior(selected, non_selected, l1_to_leaf, sel_score, nonsel_score):
    """
    Initializeaza tag_scores cu valorile priorului din selectia Phase 1.

    Semantica:
      - Frunzele din categoriile selectate primesc sel_score (>0.5) — user a confirmat
        explicit ca ii place categoria.
      - Frunzele din categoriile ne-selectate primesc nonsel_score (<0.5) — user nu a ales.

    Aceasta initializare permite Phase 2 sa refineze de la o baza informata in loc de 0.5.
    Frunzele ne-vazute in Phase 2 pastreaza scorul initial (+ prior ierarhic final).
    """
    tag_scores = {}
    for l1 in selected:
        for slug in l1_to_leaf.get(l1, []):
            tag_scores[slug] = sel_score
    for l1 in non_selected:
        for slug in l1_to_leaf.get(l1, []):
            tag_scores[slug] = nonsel_score
    return tag_scores


# ─────────────────────────────────────────────────────────────────────────────
# Functii quiz
# ─────────────────────────────────────────────────────────────────────────────

def quiz_baseline(user, data, rng, noise_rate=0.0):
    lf, l1l = user["latent_leaf"], data["l1_to_leaf"]
    tag_scores, seen = {}, set()
    n  = int(rng.integers(MIN_CARDS, MAX_CARDS + 1))
    cp = 0
    for _ in range(n):
        slug = None
        for _ in range(len(L1_SLUGS)):
            l1    = L1_SLUGS[cp % len(L1_SLUGS)]; cp += 1
            cands = [s for s in l1l.get(l1, []) if s not in seen]
            if cands:
                slug = cands[int(rng.integers(0, len(cands)))]
                break
        if slug is None:
            break
        seen.add(slug)
        _swipe(tag_scores, slug, lf, rng, noise_rate)
        if len(seen) >= MIN_CARDS and compute_entropy(tag_scores) < 1.0:
            break
    return tag_scores, []


def quiz_hier2(user, data, rng, noise_rate=0.0):
    lf, l1l = user["latent_leaf"], data["l1_to_leaf"]
    tag_scores, seen = {}, set()
    for l1 in L1_SLUGS:
        cands = [s for s in l1l.get(l1, []) if s not in seen]
        if not cands:
            continue
        slug = cands[int(rng.integers(0, len(cands)))]
        seen.add(slug)
        _swipe(tag_scores, slug, lf, rng, noise_rate)
    agg = {
        l1: float(np.mean([tag_scores[s] for s in lv if s in tag_scores]) or 0.5)
        for l1, lv in l1l.items()
        if any(s in tag_scores for s in lv)
    }
    dominant2 = sorted(agg, key=lambda l: -agg.get(l, 0.5))[:2]
    cp = 0
    for _ in range(N_HIER_TOTAL - N_HIER_P1):
        slug = None
        for _ in range(len(dominant2)):
            l1    = dominant2[cp % len(dominant2)]; cp += 1
            cands = [s for s in l1l.get(l1, []) if s not in seen]
            if cands:
                slug = cands[int(rng.integers(0, len(cands)))]
                break
        if slug is None:
            break
        seen.add(slug)
        _swipe(tag_scores, slug, lf, rng, noise_rate)
    return tag_scores, []


def quiz_cf_6040(user, data, rng, noise_rate=0.0):
    lf, lm, l1l = user["latent_leaf"], user["latent_macro"], data["l1_to_leaf"]
    selected, non_sel = phase1_select(lm, rng)
    tag_scores, seen  = {}, set()
    n_depth   = round(N_PHASE2 * 0.60)
    n_explore = N_PHASE2 - n_depth
    cp = 0
    for _ in range(n_depth):
        slug = None
        for _ in range(len(selected)):
            l1    = selected[cp % len(selected)]; cp += 1
            cands = [s for s in l1l.get(l1, []) if s not in seen]
            if cands:
                slug = cands[int(rng.integers(0, len(cands)))]
                break
        if slug is None:
            break
        seen.add(slug)
        _swipe(tag_scores, slug, lf, rng, noise_rate)
    cp2 = 0
    for _ in range(n_explore):
        if not non_sel:
            break
        slug = None
        for _ in range(len(non_sel)):
            l1    = non_sel[cp2 % len(non_sel)]; cp2 += 1
            cands = [s for s in l1l.get(l1, []) if s not in seen]
            if cands:
                slug = cands[int(rng.integers(0, len(cands)))]
                break
        if slug is None:
            break
        seen.add(slug)
        _swipe(tag_scores, slug, lf, rng, noise_rate)
    return tag_scores, selected


def quiz_cf_strongprior(user, data, rng,
                         depth_ratio=1.0,
                         sel_score=SEL_PRIOR_STR_SEL,
                         nonsel_score=SEL_PRIOR_STR_NONSEL,
                         noise_rate=0.0):
    """
    Phase 1: selectie explicita → initializare prior tare pe frunze.
    Phase 2: depth_ratio din N_PHASE2 carduri in selectate, rest explore.

    Diferenta fata de cf_6040: tag_scores porneste de la valorile priorului
    din selectie (nu de la 0.5). Frunzele ne-vizitate in Phase 2 pastreaza
    scorul initial, care reflecta deja semnalul explicit al userului.
    """
    lf, lm, l1l = user["latent_leaf"], user["latent_macro"], data["l1_to_leaf"]
    selected, non_sel = phase1_select(lm, rng)

    # Initializare prior din selectia Phase 1
    tag_scores = init_selection_prior(selected, non_sel, l1l, sel_score, nonsel_score)
    seen = set()

    n_depth   = round(N_PHASE2 * depth_ratio)
    n_explore = N_PHASE2 - n_depth

    cp = 0
    for _ in range(n_depth):
        slug = None
        for _ in range(len(selected)):
            l1    = selected[cp % len(selected)]; cp += 1
            cands = [s for s in l1l.get(l1, []) if s not in seen]
            if cands:
                slug = cands[int(rng.integers(0, len(cands)))]
                break
        if slug is None:
            break
        seen.add(slug)
        _swipe(tag_scores, slug, lf, rng, noise_rate)

    cp2 = 0
    for _ in range(n_explore):
        if not non_sel:
            break
        slug = None
        for _ in range(len(non_sel)):
            l1    = non_sel[cp2 % len(non_sel)]; cp2 += 1
            cands = [s for s in l1l.get(l1, []) if s not in seen]
            if cands:
                slug = cands[int(rng.integers(0, len(cands)))]
                break
        if slug is None:
            break
        seen.add(slug)
        _swipe(tag_scores, slug, lf, rng, noise_rate)

    return tag_scores, selected


# ─────────────────────────────────────────────────────────────────────────────
# Metrici
# ─────────────────────────────────────────────────────────────────────────────

def spearman_safe(a, b):
    sp, _ = spearmanr(a, b)
    return float(sp) if not np.isnan(sp) else 0.0

def leaf_recovery(scores, latent_leaf, l1_to_leaf):
    leaves = [s for lv in l1_to_leaf.values() for s in lv]
    return spearman_safe(
        [scores.get(s, 0.5) for s in leaves],
        [latent_leaf.get(s, 0.0) for s in leaves],
    )

def macro_recovery(scores, latent_macro, l1_to_leaf):
    rec = [float(np.mean([scores.get(s, 0.5) for s in lv])) if lv else 0.5
           for lv in (l1_to_leaf.get(l1, []) for l1 in L1_SLUGS)]
    lat = [latent_macro.get(l1, 0.1) for l1 in L1_SLUGS]
    return spearman_safe(rec, lat)

def dominant_leaf_recovery(scores, latent_leaf, dominant, l1_to_leaf):
    leaves = [s for l1 in dominant for s in l1_to_leaf.get(l1, [])]
    if len(leaves) < 3:
        return float("nan")
    return spearman_safe(
        [scores.get(s, 0.5) for s in leaves],
        [latent_leaf.get(s, 0.0) for s in leaves],
    )


# ─────────────────────────────────────────────────────────────────────────────
# Runner principal
# ─────────────────────────────────────────────────────────────────────────────

def _run_variant(user, data, vname, rng, noise_rate=0.0):
    """Ruleaza o varianta si returneaza (scores, selected, elapsed_ms)."""
    t0 = time.perf_counter()
    if vname in ("baseline", "baseline+p"):
        scores, sel = quiz_baseline(user, data, rng, noise_rate)
    elif vname in ("hier2+p",):
        scores, sel = quiz_hier2(user, data, rng, noise_rate)
    elif vname in ("cf_6040+p",):
        scores, sel = quiz_cf_6040(user, data, rng, noise_rate)
    elif vname == "cf_sp_pure_mod":
        scores, sel = quiz_cf_strongprior(user, data, rng,
                          depth_ratio=1.0,
                          sel_score=SEL_PRIOR_MOD_SEL,
                          nonsel_score=SEL_PRIOR_MOD_NONSEL,
                          noise_rate=noise_rate)
    elif vname == "cf_sp_pure_str":
        scores, sel = quiz_cf_strongprior(user, data, rng,
                          depth_ratio=1.0,
                          sel_score=SEL_PRIOR_STR_SEL,
                          nonsel_score=SEL_PRIOR_STR_NONSEL,
                          noise_rate=noise_rate)
    elif vname == "cf_sp_8020_mod":
        scores, sel = quiz_cf_strongprior(user, data, rng,
                          depth_ratio=0.80,
                          sel_score=SEL_PRIOR_MOD_SEL,
                          nonsel_score=SEL_PRIOR_MOD_NONSEL,
                          noise_rate=noise_rate)
    elif vname == "cf_sp_8020_str":
        scores, sel = quiz_cf_strongprior(user, data, rng,
                          depth_ratio=0.80,
                          sel_score=SEL_PRIOR_STR_SEL,
                          nonsel_score=SEL_PRIOR_STR_NONSEL,
                          noise_rate=noise_rate)
    else:
        raise ValueError(f"Varianta necunoscuta: {vname}")

    elapsed = (time.perf_counter() - t0) * 1000.0   # ms

    # Aplica prior ierarhic final (pentru toate variantele cu +p)
    if "+p" in vname or vname.startswith("cf_sp"):
        scores = apply_hier_prior(scores, data["l1_to_leaf"])

    return scores, sel, elapsed


def run_main(users, data):
    print(f"\n  Rulare variante principale ({N_USERS} useri) ...")
    rows      = []
    runtimes  = {v: [] for v in VNAMES}
    p1_stats  = []

    for user in users:
        uid  = user["user_id"]
        row  = {"user_id": uid, "n_dominant": len(user["dominant"]),
                "dominant": "|".join(user["dominant"])}

        p1_done = False
        for v in VNAMES:
            scores, sel, elapsed = _run_variant(
                user, data, v, np.random.default_rng(SEED + uid)
            )
            runtimes[v].append(elapsed)
            row[f"leaf_{v}"]  = round(leaf_recovery(scores, user["latent_leaf"], data["l1_to_leaf"]), 4)
            row[f"macro_{v}"] = round(macro_recovery(scores, user["latent_macro"], data["l1_to_leaf"]), 4)
            row[f"dom_{v}"]   = round(dominant_leaf_recovery(scores, user["latent_leaf"],
                                                              user["dominant"], data["l1_to_leaf"]), 4)
            row[f"cov_{v}"]   = sum(1 for s in scores.values() if s != 0.5)

            if not p1_done and sel:
                rec, prec = phase1_accuracy(sel, user["dominant"])
                p1_stats.append({
                    "user_id": uid, "n_sel": len(sel), "n_dom": len(user["dominant"]),
                    "recall": rec, "precision": prec, "all_found": rec == 1.0,
                })
                p1_done = True

        if not p1_done:
            p1_stats.append({
                "user_id": uid, "n_sel": 0, "n_dom": len(user["dominant"]),
                "recall": float("nan"), "precision": float("nan"), "all_found": False,
            })

        rows.append(row)

    df      = pd.DataFrame(rows)
    df_p1   = pd.DataFrame(p1_stats)
    df_rt   = pd.DataFrame({v: runtimes[v] for v in VNAMES})
    return df, df_p1, df_rt


# ─────────────────────────────────────────────────────────────────────────────
# Test robustete la zgomot
# ─────────────────────────────────────────────────────────────────────────────

def run_noise(users, data):
    print(f"  Rulare test zgomot (variante: {NOISE_VNAMES}) ...")
    rows = []
    for noise_rate in NOISE_RATES:
        for v in NOISE_VNAMES:
            doms, macros, leaves = [], [], []
            for user in users:
                uid = user["user_id"]
                scores, _, _ = _run_variant(
                    user, data, v, np.random.default_rng(SEED + uid + int(noise_rate * 1000))
                )
                doms.append(dominant_leaf_recovery(
                    scores, user["latent_leaf"], user["dominant"], data["l1_to_leaf"]))
                macros.append(macro_recovery(scores, user["latent_macro"], data["l1_to_leaf"]))
                leaves.append(leaf_recovery(scores, user["latent_leaf"], data["l1_to_leaf"]))
            rows.append({
                "variant":    v,
                "noise_rate": noise_rate,
                "dom_mean":   round(float(np.nanmean(doms)),   4),
                "dom_std":    round(float(np.nanstd(doms)),    4),
                "macro_mean": round(float(np.mean(macros)),    4),
                "leaf_mean":  round(float(np.mean(leaves)),    4),
            })
    return pd.DataFrame(rows)


# ─────────────────────────────────────────────────────────────────────────────
# Semnificatie statistica
# ─────────────────────────────────────────────────────────────────────────────

def compute_significance(df):
    rows = []
    comparisons = [("baseline", "vs baseline"), ("hier2+p", "vs hier2+p")]
    for mk in ("dom", "macro"):
        for v in [x for x in VNAMES if x != "baseline"]:
            row = {"metric": mk, "variant": v}
            for ref, label in comparisons:
                a = df[f"{mk}_{v}"].dropna()
                b = df[f"{mk}_{ref}"].dropna()
                idx = a.index.intersection(b.index)
                try:
                    _, pval = wilcoxon(a.loc[idx], b.loc[idx], alternative="greater")
                except Exception:
                    pval = float("nan")
                row[f"pval_{label.replace(' ', '_')}"] = round(pval, 4)
                row[f"sig_{label.replace(' ', '_')}"]  = (
                    "**" if pval < 0.05 else ("*" if pval < 0.10 else "ns")
                ) if not np.isnan(pval) else "nan"
            rows.append(row)
    return pd.DataFrame(rows)


# ─────────────────────────────────────────────────────────────────────────────
# Raportare consola
# ─────────────────────────────────────────────────────────────────────────────

def report(df, df_p1, df_rt, df_sig, df_noise):
    b_leaf  = df["leaf_baseline"].mean()
    b_macro = df["macro_baseline"].mean()
    b_dom   = df["dom_baseline"].mean()

    print("\n" + "=" * 82)
    print(f"  {'Varianta':<20} {'Leaf':>7} {'dLeaf':>7} "
          f"{'Macro':>7} {'dMacro':>7} "
          f"{'DomLeaf':>8} {'dDomLeaf':>9} {'Cov':>5}")
    print("  " + "-" * 76)
    for v in VNAMES:
        leaf  = df[f"leaf_{v}"].mean()
        macro = df[f"macro_{v}"].mean()
        dom   = df[f"dom_{v}"].mean()
        cov   = df[f"cov_{v}"].mean()
        mark  = " *" if "sp" in v else "  "
        print(f"{mark} {v:<20} {leaf:>7.4f} {leaf-b_leaf:>+7.4f} "
              f"{macro:>7.4f} {macro-b_macro:>+7.4f} "
              f"{dom:>8.4f} {dom-b_dom:>+9.4f} {cov:>5.1f}")

    print(f"\n  Semnificatie dominant-leaf (Wilcoxon one-sided, alternative='greater'):")
    print(f"  {'Varianta':<20} {'vs baseline':>12} {'sig':>5}  {'vs hier2+p':>12} {'sig':>5}")
    print("  " + "-" * 64)
    for _, r in df_sig[df_sig["metric"] == "dom"].iterrows():
        v = r["variant"]
        if v == "baseline":
            continue
        print(f"  {v:<20} {r['pval_vs_baseline']:>12.4f} {r['sig_vs_baseline']:>5}  "
              f"{r['pval_vs_hier2+p']:>12.4f} {r['sig_vs_hier2+p']:>5}")

    print(f"\n  Semnificatie macro (Wilcoxon one-sided):")
    print(f"  {'Varianta':<20} {'vs baseline':>12} {'sig':>5}  {'vs hier2+p':>12} {'sig':>5}")
    print("  " + "-" * 64)
    for _, r in df_sig[df_sig["metric"] == "macro"].iterrows():
        v = r["variant"]
        if v == "baseline":
            continue
        print(f"  {v:<20} {r['pval_vs_baseline']:>12.4f} {r['sig_vs_baseline']:>5}  "
              f"{r['pval_vs_hier2+p']:>12.4f} {r['sig_vs_hier2+p']:>5}")

    p1_recall = df_p1["recall"].dropna()
    p1_all    = df_p1["all_found"]
    print(f"\n  Phase 1 accuracy (variante catfirst):")
    print(f"  Recall dominant:  {p1_recall.mean():.3f}  (std={p1_recall.std():.3f})")
    print(f"  All correct:      {p1_all.mean()*100:.1f}%")
    print(f"  N selectate (med):{df_p1['n_sel'].mean():.1f}")

    print(f"\n  Runtime (ms) — medie si p95:")
    print(f"  {'Varianta':<20} {'Mean':>8} {'p95':>8}")
    print("  " + "-" * 38)
    for v in VNAMES:
        vals = df_rt[v].values
        print(f"  {v:<20} {np.mean(vals):>8.3f} {np.percentile(vals, 95):>8.3f}")

    print(f"\n  Robustete zgomot (dominant-leaf mean):")
    print(f"  {'Varianta':<20} {'0%':>8} {'10%':>8} {'20%':>8}")
    print("  " + "-" * 46)
    for v in NOISE_VNAMES:
        vals = [df_noise[(df_noise.variant == v) & (df_noise.noise_rate == nr)]["dom_mean"].values[0]
                for nr in NOISE_RATES]
        print(f"  {v:<20} {vals[0]:>8.4f} {vals[1]:>8.4f} {vals[2]:>8.4f}")
    print("=" * 82)


# ─────────────────────────────────────────────────────────────────────────────
# Grafice
# ─────────────────────────────────────────────────────────────────────────────

def make_plots(df, df_noise):
    # Bar chart pentru cele 3 metrici
    metrics = [
        ("dom",   "Dominant-Leaf Spearman\n(metrica cheie)"),
        ("macro", "Macro Spearman\n(8 categorii L1)"),
        ("leaf",  "Leaf Spearman\n(161 frunze)"),
    ]
    fig, axes = plt.subplots(1, 3, figsize=(17, 5))
    for ax, (mk, title) in zip(axes, metrics):
        means = [df[f"{mk}_{v}"].mean() for v in VNAMES]
        stds  = [df[f"{mk}_{v}"].std()  for v in VNAMES]
        clrs  = [VCOLORS[v] for v in VNAMES]
        edge  = ["red" if "sp" in v else "black" for v in VNAMES]
        lw    = [2.0 if "sp" in v else 0.6 for v in VNAMES]
        bars  = ax.bar([VLABELS[v] for v in VNAMES], means, yerr=stds,
                       capsize=4, color=clrs, edgecolor=edge, linewidth=lw)
        ax.axhline(means[0], color="gray", linestyle="--", linewidth=0.8, alpha=0.5)
        ax.axhline(df[f"{mk}_hier2+p"].mean(), color="#1565C0",
                   linestyle=":", linewidth=1.2, alpha=0.7)
        ax.set_title(title, fontsize=9)
        ax.set_ylabel("Spearman")
        ax.set_ylim(0, min(1.0, max(means) * 1.5))
        ax.tick_params(axis="x", labelsize=7.5)
        for bar, m in zip(bars, means):
            ax.text(bar.get_x() + bar.get_width() / 2,
                    bar.get_height() + 0.008,
                    f"{m:.3f}", ha="center", va="bottom", fontsize=7, fontweight="bold")
    plt.suptitle("Quiz variants — comparatie metrici (50 useri sintetici, SEED=42)", fontsize=10)
    plt.tight_layout()
    plt.savefig(os.path.join(RESULTS_DIR, "quiz_variants_bars.png"), dpi=150)
    plt.close()
    print("  Salvat: quiz_variants_bars.png")

    # Grafic robustete zgomot
    fig, axes2 = plt.subplots(1, 2, figsize=(12, 4))
    markers = ["o", "s", "^", "D"]
    noise_colors = ["#9E9E9E", "#1565C0", "#880E4F", "#2E7D32"]
    for ax, mk, title in zip(axes2, ["dom_mean", "macro_mean"],
                              ["Dominant-Leaf vs zgomot", "Macro vs zgomot"]):
        for v, mr, cl in zip(NOISE_VNAMES, markers, noise_colors):
            vals = [df_noise[(df_noise.variant == v) & (df_noise.noise_rate == nr)][mk].values[0]
                    for nr in NOISE_RATES]
            ax.plot([int(nr * 100) for nr in NOISE_RATES], vals,
                    marker=mr, color=cl, linewidth=2, markersize=8, label=v)
        ax.set_xlabel("Zgomot (%)")
        ax.set_ylabel("Spearman")
        ax.set_title(title, fontsize=9)
        ax.set_xticks([0, 10, 20])
        ax.legend(fontsize=8)
        ax.grid(True, alpha=0.3)
    plt.tight_layout()
    plt.savefig(os.path.join(RESULTS_DIR, "quiz_noise_robustness.png"), dpi=150)
    plt.close()
    print("  Salvat: quiz_noise_robustness.png")


# ─────────────────────────────────────────────────────────────────────────────
# SUMMARY_QUIZ.md
# ─────────────────────────────────────────────────────────────────────────────

def save_summary(df, df_p1, df_rt, df_sig, df_noise):
    lines = []
    lines.append("# Rezumat Evaluare Variante Quiz — TripCraft\n")
    lines.append("## Avertisment metodologic\n")
    lines.append("> Recuperarea măsoară reconstrucția unui **profil latent sintetic** sub modelul de")
    lines.append("> simulare a swipe-urilor, **nu comportament uman real**.")
    lines.append("> Metricile sunt Spearman rank-correlation între scorurile estimate și profilul latent.")
    lines.append("> Validitate: **INTERNĂ** pe date sintetice. Nu se poate generaliza direct la useri reali.")
    lines.append("> Swipe-urile sunt simulate probabilistic cu P(right) = sigmoid(5*(lat-0.5)).")
    lines.append("")
    lines.append("## Configuratie\n")
    lines.append(f"| Parametru | Valoare |")
    lines.append(f"|---|---|")
    lines.append(f"| Useri sintetici | {N_USERS} |")
    lines.append(f"| SEED | {SEED} |")
    lines.append(f"| Phase2 carduri | {N_PHASE2} |")
    lines.append(f"| Prior ierarhic final (strength) | {HIER_PRIOR_STR} |")
    lines.append(f"| Prior selectie moderat (selected/non-sel) | {SEL_PRIOR_MOD_SEL}/{SEL_PRIOR_MOD_NONSEL} |")
    lines.append(f"| Prior selectie tare (selected/non-sel) | {SEL_PRIOR_STR_SEL}/{SEL_PRIOR_STR_NONSEL} |")
    lines.append(f"| Phase1 MAX_SELECTED | {MAX_SELECTED} |")
    lines.append("")
    lines.append("## Metrici per varianta (medie pe 50 useri)\n")
    lines.append("| Varianta | Leaf | Macro | DomLeaf | Delta DomLeaf |")
    lines.append("|---|---|---|---|---|")
    b_dom = df["dom_baseline"].mean()
    for v in VNAMES:
        dom = df[f"dom_{v}"].mean()
        lines.append(
            f"| {v} | {df[f'leaf_{v}'].mean():.4f} | "
            f"{df[f'macro_{v}'].mean():.4f} | {dom:.4f} | {dom-b_dom:+.4f} |"
        )
    lines.append("")
    lines.append("## Semnificatie statistica — Dominant-Leaf (Wilcoxon one-sided)\n")
    lines.append("| Varianta | vs baseline p | sig | vs hier2+p p | sig |")
    lines.append("|---|---|---|---|---|")
    for _, r in df_sig[df_sig["metric"] == "dom"].iterrows():
        if r["variant"] == "baseline":
            continue
        lines.append(
            f"| {r['variant']} | {r['pval_vs_baseline']:.4f} | {r['sig_vs_baseline']} | "
            f"{r['pval_vs_hier2+p']:.4f} | {r['sig_vs_hier2+p']} |"
        )
    lines.append("")
    lines.append("## Semnificatie statistica — Macro (Wilcoxon one-sided)\n")
    lines.append("| Varianta | vs baseline p | sig | vs hier2+p p | sig |")
    lines.append("|---|---|---|---|---|")
    for _, r in df_sig[df_sig["metric"] == "macro"].iterrows():
        if r["variant"] == "baseline":
            continue
        lines.append(
            f"| {r['variant']} | {r['pval_vs_baseline']:.4f} | {r['sig_vs_baseline']} | "
            f"{r['pval_vs_hier2+p']:.4f} | {r['sig_vs_hier2+p']} |"
        )
    lines.append("")
    lines.append("## Phase 1 — Acuratete selectie categorii\n")
    p1r = df_p1["recall"].dropna()
    lines.append(f"| Metrica | Valoare |")
    lines.append(f"|---|---|")
    lines.append(f"| Recall dominant L1 | {p1r.mean():.3f} (std={p1r.std():.3f}) |")
    lines.append(f"| Precision | {df_p1['precision'].dropna().mean():.3f} |")
    lines.append(f"| All correct | {df_p1['all_found'].mean()*100:.1f}% |")
    lines.append(f"| N selectate (medie) | {df_p1['n_sel'].mean():.1f} |")
    lines.append(f"| Comparatie quiz anterior (rand) | recall=0.630, all_correct=24% |")
    lines.append("")
    lines.append("## Robustete la zgomot (dominant-leaf mean)\n")
    lines.append("| Varianta | Zgomot 0% | Zgomot 10% | Zgomot 20% | Degradare |")
    lines.append("|---|---|---|---|---|")
    for v in NOISE_VNAMES:
        vals = [df_noise[(df_noise.variant == v) & (df_noise.noise_rate == nr)]["dom_mean"].values[0]
                for nr in NOISE_RATES]
        deg = vals[2] - vals[0]
        lines.append(f"| {v} | {vals[0]:.4f} | {vals[1]:.4f} | {vals[2]:.4f} | {deg:+.4f} |")
    lines.append("")
    lines.append("## Runtime (ms)\n")
    lines.append("| Varianta | Mean | p95 |")
    lines.append("|---|---|---|")
    for v in VNAMES:
        vals = df_rt[v].values
        lines.append(f"| {v} | {np.mean(vals):.3f} | {np.percentile(vals, 95):.3f} |")
    lines.append("")
    lines.append("## Concluzii cheie\n")
    best_dom_v = max(VNAMES, key=lambda v: df[f"dom_{v}"].mean())
    best_macro_v = max(VNAMES, key=lambda v: df[f"macro_{v}"].mean())
    lines.append(f"- **Best DomLeaf**: `{best_dom_v}` ({df[f'dom_{best_dom_v}'].mean():.4f})")
    lines.append(f"- **Best Macro**: `{best_macro_v}` ({df[f'macro_{best_macro_v}'].mean():.4f})")
    lines.append(f"- Phase 1 explicit: recall={p1r.mean():.2f} vs 0.63 (inferit din 1 card random)")
    lines.append("")
    lines.append("## Fisiere generate\n")
    lines.append("- `quiz_variants_metrics.csv` — metrici per user per varianta")
    lines.append("- `quiz_significance.csv` — p-values Wilcoxon")
    lines.append("- `quiz_noise_robustness.csv` — degradare la zgomot")
    lines.append("- `quiz_variants_bars.png` — bar chart comparativ")
    lines.append("- `quiz_noise_robustness.png` — curbe degradare zgomot")
    lines.append("")
    lines.append(f"*Generat de `evaluation/run_quiz_variants_test.py` | SEED={SEED}*")

    path = os.path.join(RESULTS_DIR, "SUMMARY_QUIZ.md")
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    print(f"  Salvat: SUMMARY_QUIZ.md")


# ─────────────────────────────────────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────────────────────────────────────

def main():
    print("\n" + "=" * 82)
    print("  Quiz Variants Test — TripCraft")
    print(f"  SEED={SEED} | N={N_USERS} | Phase2={N_PHASE2} carduri")
    print(f"  Variante: {VNAMES}")
    print("=" * 82)

    db = SessionLocal()
    try:
        data = load_data(db)
    finally:
        db.close()

    users = generate_users(data["l1_to_leaf"], _rng)

    df, df_p1, df_rt = run_main(users, data)
    df_noise = run_noise(users, data)
    df_sig   = compute_significance(df)

    report(df, df_p1, df_rt, df_sig, df_noise)
    make_plots(df, df_noise)

    df.to_csv(os.path.join(RESULTS_DIR, "quiz_variants_metrics.csv"), index=False)
    df_sig.to_csv(os.path.join(RESULTS_DIR, "quiz_significance.csv"), index=False)
    df_noise.to_csv(os.path.join(RESULTS_DIR, "quiz_noise_robustness.csv"), index=False)
    print(f"  Salvat: quiz_variants_metrics.csv, quiz_significance.csv, quiz_noise_robustness.csv")

    save_summary(df, df_p1, df_rt, df_sig, df_noise)


if __name__ == "__main__":
    main()
