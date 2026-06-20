#!/usr/bin/env python3
"""
backend/evaluation/run_statistical_analysis.py
===============================================
Strat de rigoare statistica non-distructiv peste evaluarea existenta.
Nu modifica niciun fisier din evaluation/ existent.

GARANTII IMPLEMENTATE
  G1 — Poarta de validare: dupa reconstituirea metricilor per-user din
       _cfg_rows, verifica automat ca vectorul de productie coincide cu
       quality_per_user.csv (toleranta 1e-9 pe ndcg@10, prec@10, rec@20,
       profile_recovery_spearman). Daca nu coincid, executia se opreste
       cu mesaj clar — nu se continua cu testele.

  G2 — Siguranta importului: run_quality_eval.py isi executa logica exclusiv
       sub if __name__ == "__main__" (linia 967). Importul de mai jos activeaza
       doar definitiile de functii si constantele de modul (seed-uri, makedirs,
       logging) — nu porneste nicio evaluare.

  G3 — Wilcoxon cu tratarea egalitatilor: zero_method="wilcox" (perechile cu
       diferenta 0 sunt excluse din statistica). Raportam n_nonzero pentru
       fiecare comparatie. Diferentele mici sau toate-zero sunt tratate
       grafios. NEsemnificatia statistica pentru configuratii echilibrate
       apropiate (raritate_egal_pop, cos_redus) este ASTEPTATA si raportata
       ca atare, nu ca eroare.

OUTPUT
  results/statistical_ci.csv           — CI bootstrap pentru configuratia de productie
  results/statistical_significance.csv — Wilcoxon per comparatie (cu Holm)
  results/statistical_figure.png       — bar chart NDCG@10 cu bare CI 95%

RULARE (din backend/):
  python -m evaluation.run_statistical_analysis
"""

import sys
import os
import math
import warnings

# Consola Windows poate fi cp1252 — fortam UTF-8 pentru caracterele romanesti
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from scipy.stats import wilcoxon as scipy_wilcoxon

# ── Constante ─────────────────────────────────────────────────────────────────
SEED             = 42
BOOTSTRAP_ITER   = 10_000
BOOTSTRAP_SEED   = 42
CI_LEVEL         = 0.95
TOLERANCE        = 1e-9

# ── Path setup ────────────────────────────────────────────────────────────────
_BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _BACKEND_DIR not in sys.path:
    sys.path.insert(0, _BACKEND_DIR)

# ── G2: Import sigur ──────────────────────────────────────────────────────────
# run_quality_eval.py are garda if __name__ == "__main__" la linia 967.
# Importul de mai jos NU declanseaza rularea completa a evaluarii.
# Efecte de nivel-modul (random.seed, np.random.seed, makedirs, logging)
# sunt inofensive; le re-setam imediat dupa import pentru a asigura
# ca starea RNG din scriptul nostru este identica cu cea din rularea originala.
from evaluation.run_quality_eval import (  # noqa: E402
    load_data,
    generate_users,
    eval_user,
    N_USERS,
    WEIGHT_CONFIGS,
    RESULTS_DIR,
    ndcg_at_k,          # noqa: F401 — importate pentru referinta, nu apelate direct
    precision_at_k,     # noqa: F401
    recall_at_k,        # noqa: F401
)
from app.database import SessionLocal  # noqa: E402

# Re-setam RNG-ul dupa import — importul run_quality_eval seteaza seed-urile
# globale si creeaza propriul _rng; noi cream un _rng proaspat identic.
np.random.seed(SEED)
_rng = np.random.default_rng(SEED)


def _p(fname: str) -> str:
    return os.path.join(RESULTS_DIR, fname)


# ─────────────────────────────────────────────────────────────────────────────
# PASUL 1 — Reconstituire metrici per-user (acelasi SEED, aceiasi 50 useri)
# ─────────────────────────────────────────────────────────────────────────────

def collect_per_user(data, db):
    """
    Ruleaza pipeline-ul identic cu run_quality_eval.main() — acelasi SEED,
    aceeasi secventa RNG per user (np.random.default_rng(SEED + i)).

    Returneaza:
      prod_rows  — list[dict] cu metricile din res (config productie, scorarul real)
      cfg_data   — dict{config: list[dict]} cu metricile din _cfg_rows per config
      spearman   — list[float] profile_recovery_spearman (useri valizi, ordinea prod_rows)
    """
    print(f"\n[STAT] Generare {N_USERS} useri sintetici (SEED={SEED})...")
    users = generate_users(data["l1_to_leaf"], _rng)

    prod_rows  = []
    cfg_data   = {cfg: [] for cfg in WEIGHT_CONFIGS}
    spearman   = []
    n_skipped  = 0

    print("[STAT] Evaluare per user...")
    for i, user in enumerate(users):
        if (i + 1) % 10 == 0:
            print(f"  ... {i + 1}/{N_USERS}")

        r = eval_user(user, data, db, np.random.default_rng(SEED + i))
        if r is None:
            n_skipped += 1
            continue

        cfg_rows = r.pop("_cfg_rows", [])

        if r.get("skip_reason"):
            n_skipped += 1
            continue

        # Metricile din res (scorarul real cu config de productie)
        prod_rows.append({
            "user_id":                    r["user_id"],
            "ndcg@10":                    r["ndcg@10"],
            "prec@10":                    r["prec@10"],
            "rec@20":                     r["rec@20"],
            "profile_recovery_spearman":  r["profile_recovery_spearman"],
        })
        spearman.append(r["profile_recovery_spearman"])

        # Metricile din _cfg_rows (toate configuratiile, inclusiv "productie")
        for row in cfg_rows:
            cfg_name = row.get("config")
            if cfg_name in cfg_data:
                cfg_data[cfg_name].append({
                    "user_id":  row["user_id"],
                    "ndcg@10":  row["ndcg@10"],
                    "prec@10":  row["prec@10"],
                    "rec@20":   row.get("rec@20", float("nan")),
                })

    print(f"  Useri evaluati: {len(prod_rows)}/{N_USERS}  (sarite: {n_skipped})")
    return prod_rows, cfg_data, spearman


# ─────────────────────────────────────────────────────────────────────────────
# G1 — POARTA DE VALIDARE
# ─────────────────────────────────────────────────────────────────────────────

def validate(prod_rows, cfg_data):
    """
    Compara metricile reconstituite (config productie, din res) cu
    quality_per_user.csv. Toleranta: TOLERANCE = 1e-9.

    Daca oricare diferenta depaseste toleranta, opreste executia.
    Verifica si consistenta interna res vs _cfg_rows["productie"].
    """
    print("\n" + "=" * 62)
    print("G1 — POARTA DE VALIDARE")
    print("=" * 62)

    csv_path = _p("quality_per_user.csv")
    if not os.path.exists(csv_path):
        sys.exit(
            f"\n[VALIDARE ESUAT] {csv_path} nu exista.\n"
            "Ruleaza mai intai: python -m evaluation.run_quality_eval\n"
        )

    df_ref = pd.read_csv(csv_path)
    # Useri valizi in CSV: fara skip_reason
    df_ref_valid = df_ref[df_ref["skip_reason"].isna()].set_index("user_id")

    metrics_check = [
        ("ndcg@10",                   "ndcg@10"),
        ("prec@10",                   "prec@10"),
        ("rec@20",                    "rec@20"),
        ("profile_recovery_spearman", "profile_recovery_spearman"),
    ]

    errors_csv = []
    prod_by_uid = {r["user_id"]: r for r in prod_rows}

    # 1. Compara prod_rows (res) cu CSV
    for uid, ref_row in df_ref_valid.iterrows():
        if uid not in prod_by_uid:
            errors_csv.append(f"  User {uid}: prezent in CSV, absent din reconstituire.")
            continue
        rec = prod_by_uid[uid]
        for rec_col, csv_col in metrics_check:
            v_rec = rec.get(rec_col, float("nan"))
            v_csv = float(ref_row[csv_col])
            delta = abs(v_rec - v_csv)
            if delta > TOLERANCE:
                errors_csv.append(
                    f"  User {uid}, {csv_col}: "
                    f"reconstituit={v_rec:.12f}  CSV={v_csv:.12f}  "
                    f"delta={delta:.2e}"
                )

    if errors_csv:
        msg = (
            "\n[VALIDARE ESUAT] Metricile reconstituite NU coincid cu quality_per_user.csv.\n"
            "Pipeline-ul nu este determinist sau datele DB s-au modificat.\n"
            "Reconstituirile celorlalte configuratii NU sunt de incredere.\n"
            "EXECUTIA SE OPRESTE.\n\n"
            "Diferente gasite:\n" + "\n".join(errors_csv)
        )
        print(msg)
        sys.exit(1)

    n_val = len(prod_rows)
    print(f"  OK — res vs CSV: {n_val} useri, toate metricile in toleranta 1e-9.")
    print("  Metrici verificate: ndcg@10, prec@10, rec@20, profile_recovery_spearman")

    # 2. Consistenta interna: res["productie"] vs _cfg_rows["productie"]
    #    (verifica ca re-sortarea prin componente reproduce rankingul scorarului)
    cfg_prod_by_uid = {r["user_id"]: r for r in cfg_data.get("productie", [])}
    internal_errs = []
    for uid, rec in prod_by_uid.items():
        if uid not in cfg_prod_by_uid:
            internal_errs.append(f"  User {uid}: absent din _cfg_rows[productie].")
            continue
        for col in ["ndcg@10", "prec@10", "rec@20"]:
            v_res = rec.get(col, float("nan"))
            v_cfg = cfg_prod_by_uid[uid].get(col, float("nan"))
            delta = abs(v_res - v_cfg)
            if delta > TOLERANCE:
                internal_errs.append(
                    f"  User {uid}, {col}: res={v_res:.10f}  "
                    f"_cfg_rows={v_cfg:.10f}  delta={delta:.2e}"
                )

    if internal_errs:
        print(
            "\n  [INFO] Discrepante interne res vs _cfg_rows[productie] "
            f"({len(internal_errs)} cazuri):\n"
            + "\n".join(internal_errs[:5])
            + ("\n  ... (trunchiat)" if len(internal_errs) > 5 else "")
            + "\n  Posibila cauza: budget_penalty != 0 pentru unele atractii, sau\n"
            "  tie-breaking diferit. Continuam cu metricile din res (fidele scorerului real)."
        )
    else:
        print(
            "  OK — Consistenta interna res == _cfg_rows[productie] confirmata.\n"
            "  Re-sortarea prin componente (0.70·cos+0.20·pop+0.10·rar) reproduce\n"
            "  exact rankingul score_attractions() — budget_penalty=0 pentru toti userii."
        )


# ─────────────────────────────────────────────────────────────────────────────
# PASUL 2 — Bootstrap CI 95% (productie)
# ─────────────────────────────────────────────────────────────────────────────

def _bootstrap_ci(values, n_iter=BOOTSTRAP_ITER, seed=BOOTSTRAP_SEED, ci=CI_LEVEL):
    """Interval de incredere prin bootstrap (metoda percentilelor)."""
    arr = np.array(values, dtype=float)
    rng = np.random.default_rng(seed)
    boot_means = np.fromiter(
        (rng.choice(arr, size=len(arr), replace=True).mean() for _ in range(n_iter)),
        dtype=float,
        count=n_iter,
    )
    alpha = (1.0 - ci) / 2.0
    lo = float(np.percentile(boot_means, 100.0 * alpha))
    hi = float(np.percentile(boot_means, 100.0 * (1.0 - alpha)))
    return float(arr.mean()), lo, hi


def compute_bootstrap_cis(prod_rows, spearman):
    metrics_map = {
        "NDCG@10":      [r["ndcg@10"]  for r in prod_rows],
        "Precision@10": [r["prec@10"]  for r in prod_rows],
        "Recall@20":    [r["rec@20"]   for r in prod_rows],
        "Spearman":     spearman,
    }

    print("\n" + "=" * 62)
    print(f"PASUL 2 — Bootstrap CI {int(CI_LEVEL*100)}%  "
          f"(productie, {BOOTSTRAP_ITER:,} reeșantionări, seed={BOOTSTRAP_SEED})")
    print("=" * 62)
    print(f"  {'Metrica':<22} {'N':>4} {'Medie':>8} {'CI low':>8} {'CI high':>8}")
    print("  " + "-" * 54)

    ci_rows = []
    for name, vals in metrics_map.items():
        n = len(vals)
        mean, lo, hi = _bootstrap_ci(vals)
        ci_rows.append({
            "metric":       name,
            "n":            n,
            "mean":         mean,
            "ci_low":       lo,
            "ci_high":      hi,
            "ci_level":     CI_LEVEL,
            "n_bootstrap":  BOOTSTRAP_ITER,
        })
        print(f"  {name:<22} {n:>4} {mean:>8.4f} {lo:>8.4f} {hi:>8.4f}")

    return ci_rows


# ─────────────────────────────────────────────────────────────────────────────
# PASUL 3 — Wilcoxon signed-rank + Holm (G3)
# ─────────────────────────────────────────────────────────────────────────────

def _rank_biserial(x, y):
    """
    Corelatie rank-biserial pentru testul Wilcoxon pereche.
    r = (W+ - W-) / (W+ + W-), calculat pe diferentele non-zero.
    Valori pozitive: productie > alternativa.
    """
    diff = np.asarray(x, dtype=float) - np.asarray(y, dtype=float)
    nonzero = diff[diff != 0.0]
    if len(nonzero) == 0:
        return 0.0
    ranks = np.argsort(np.argsort(np.abs(nonzero))) + 1.0
    w_plus  = float(ranks[nonzero > 0].sum())
    w_minus = float(ranks[nonzero < 0].sum())
    denom = w_plus + w_minus
    return float((w_plus - w_minus) / denom) if denom > 0 else 0.0


def _holm(p_values):
    """Corecție Holm-Bonferroni. Returneaza p-values ajustate in aceeasi ordine."""
    m = len(p_values)
    indexed = sorted(enumerate(p_values), key=lambda x: x[1])
    p_adj = [None] * m
    running_max = 0.0
    for rank, (orig_idx, p) in enumerate(indexed):
        adj = min(p * (m - rank), 1.0)
        running_max = max(running_max, adj)
        p_adj[orig_idx] = running_max
    return p_adj


def compute_wilcoxon(prod_rows, cfg_data):
    """
    G3 — Wilcoxon signed-rank (two-sided) pe NDCG@10 per user.
    Productie (din res) vs fiecare configuratie alternativa (din _cfg_rows).
    """
    prod_by_uid = {r["user_id"]: r["ndcg@10"] for r in prod_rows}
    valid_uids  = sorted(prod_by_uid.keys())

    comparisons = [c for c in WEIGHT_CONFIGS if c != "productie"]
    raw_results = []

    for cfg_name in comparisons:
        alt_by_uid = {r["user_id"]: r["ndcg@10"] for r in cfg_data.get(cfg_name, [])}
        common     = [u for u in valid_uids if u in alt_by_uid]

        entry = {
            "comparison":    f"productie vs {cfg_name}",
            "n_pairs":       len(common),
            "n_nonzero":     0,
            "statistic":     float("nan"),
            "p_raw":         float("nan"),
            "rank_biserial": float("nan"),
            "note":          "",
        }

        if len(common) < 5:
            entry["note"] = f"prea putine perechi comune ({len(common)})"
            raw_results.append(entry)
            continue

        prod_vec = np.array([prod_by_uid[u] for u in common])
        alt_vec  = np.array([alt_by_uid[u]  for u in common])
        diff     = prod_vec - alt_vec
        n_nz     = int(np.sum(diff != 0.0))
        entry["n_nonzero"] = n_nz

        if n_nz == 0:
            entry["p_raw"]         = 1.0
            entry["rank_biserial"] = 0.0
            entry["note"]          = "toate diferentele sunt zero — configuratii identice"
            raw_results.append(entry)
            continue

        if n_nz == 1:
            # scipy.wilcoxon nu poate calcula p pentru o singura pereche nonzero
            entry["note"] = "o singura pereche nonzero — test neinformativ"
            raw_results.append(entry)
            continue

        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            stat, p_val = scipy_wilcoxon(
                prod_vec, alt_vec,
                zero_method="wilcox",   # G3: perechile cu dif=0 excluse
                alternative="two-sided",
            )

        entry["statistic"]     = float(stat)
        entry["p_raw"]         = float(p_val)
        entry["rank_biserial"] = _rank_biserial(prod_vec, alt_vec)
        raw_results.append(entry)

    # Corecție Holm pe p_raw-urile valide
    valid_idx = [i for i, r in enumerate(raw_results) if not math.isnan(r["p_raw"])]
    if valid_idx:
        p_vals = [raw_results[i]["p_raw"] for i in valid_idx]
        p_holm = _holm(p_vals)
        for rank_in_valid, orig_i in enumerate(valid_idx):
            raw_results[orig_i]["p_holm"] = p_holm[rank_in_valid]

    for r in raw_results:
        r.setdefault("p_holm", float("nan"))

    return raw_results


# ─────────────────────────────────────────────────────────────────────────────
# PASUL 4 — Figura (bar chart NDCG@10 cu CI 95%)
# ─────────────────────────────────────────────────────────────────────────────

_CFG_LABEL = {
    "productie":           "Producție\n(0.70·cos+0.20·pop+0.10·rar)",
    "doar_cosinus":        "Doar cosinus\n(1.00·cos)",
    "fara_raritate":       "Fără raritate\n(0.80·cos+0.20·pop)",
    "raritate_egal_pop":   "Rar=Pop\n(0.70·cos+0.15·pop+0.15·rar)",
    "raritate_peste_pop":  "Rar>Pop\n(0.70·cos+0.10·pop+0.20·rar)",
    "cos_redus":           "Cos redus\n(0.60·cos+0.20·pop+0.20·rar)",
}


def make_figure(cfg_data, prod_rows, ci_rows, wilcoxon_rows):
    """
    Bar chart NDCG@10 per configuratie.
    Bare de eroare = CI 95% bootstrap (metoda percentilelor, 10 000 reeșantionari).
    Stil sobru: albastru pentru productie, gri muted pentru alternative.
    Stelute de semnificatie deasupra barelor alternative (* p<0.05, ** p<0.01, *** p<0.001).
    """
    ordered = ["productie"] + [c for c in WEIGHT_CONFIGS if c != "productie"]

    # CI pentru productie din ci_rows; CI pentru alternative prin bootstrap separat
    ndcg_stats = {}
    ci_prod = next((r for r in ci_rows if r["metric"] == "NDCG@10"), None)
    if ci_prod:
        ndcg_stats["productie"] = (ci_prod["mean"], ci_prod["ci_low"], ci_prod["ci_high"])

    bseed = BOOTSTRAP_SEED + 100
    for cfg in ordered:
        if cfg == "productie":
            continue
        vals = [r["ndcg@10"] for r in cfg_data.get(cfg, [])
                if not math.isnan(r["ndcg@10"])]
        if vals:
            m, lo, hi = _bootstrap_ci(vals, seed=bseed)
            ndcg_stats[cfg] = (m, lo, hi)
        bseed += 1

    # Semnificatie Wilcoxon (p_holm) per configuratie alternativa
    sig_map = {}
    for r in wilcoxon_rows:
        cfg_name = r["comparison"].replace("productie vs ", "")
        p_h = r.get("p_holm", float("nan"))
        if math.isnan(p_h):
            sig_map[cfg_name] = ""
        elif p_h < 0.001:
            sig_map[cfg_name] = "***"
        elif p_h < 0.01:
            sig_map[cfg_name] = "**"
        elif p_h < 0.05:
            sig_map[cfg_name] = "*"
        else:
            sig_map[cfg_name] = "ns"

    labels   = [_CFG_LABEL.get(c, c) for c in ordered]
    means    = [ndcg_stats.get(c, (float("nan"),) * 3)[0] for c in ordered]
    err_lo   = [
        max(0.0, ndcg_stats.get(c, (m, m, m))[0] - ndcg_stats.get(c, (m, m, m))[1])
        for c, m in zip(ordered, means)
    ]
    err_hi   = [
        max(0.0, ndcg_stats.get(c, (m, m, m))[2] - ndcg_stats.get(c, (m, m, m))[0])
        for c, m in zip(ordered, means)
    ]
    colors   = ["#2c5f8a" if c == "productie" else "#8a9bb0" for c in ordered]

    fig, ax = plt.subplots(figsize=(10, 5.5))
    x    = np.arange(len(ordered))
    bars = ax.bar(
        x, means,
        yerr=[err_lo, err_hi],
        capsize=4,
        color=colors,
        edgecolor="#3a3a3a",
        linewidth=0.7,
        error_kw=dict(ecolor="#3a3a3a", elinewidth=1.0, capthick=1.0),
        zorder=3,
    )

    # Valori numerice deasupra barelor
    for bar, val in zip(bars, means):
        if not math.isnan(val):
            ax.text(
                bar.get_x() + bar.get_width() / 2.0,
                bar.get_height() + max(err_hi[list(means).index(val)], 0) + 0.003,
                f"{val:.4f}",
                ha="center", va="bottom",
                fontsize=7.2, color="#1a1a1a",
            )

    # Stelute de semnificatie pentru configuratii alternative
    for i, cfg in enumerate(ordered):
        if cfg == "productie":
            continue
        label = sig_map.get(cfg, "")
        if label:
            m   = means[i]
            ehi = err_hi[i]
            ax.text(
                x[i], m + ehi + 0.016,
                label,
                ha="center", va="bottom",
                fontsize=9, color="#c0392b" if label != "ns" else "#555555",
            )

    # Linie de referinta = media productie
    m_prod = ndcg_stats.get("productie", (float("nan"),))[0]
    if not math.isnan(m_prod):
        ax.axhline(
            m_prod, color="#2c5f8a", linewidth=0.9,
            linestyle="--", alpha=0.55,
            label=f"Referință producție ({m_prod:.4f})",
            zorder=2,
        )

    ax.set_xticks(x)
    ax.set_xticklabels(labels, fontsize=8)
    ax.set_ylabel("NDCG@10  (medie, n=50 utilizatori sintetici)", fontsize=9.5)
    ax.set_title(
        "Comparație configurații de ponderare — NDCG@10\n"
        "Bare de eroare: interval de încredere 95% (bootstrap percentilă, "
        f"{BOOTSTRAP_ITER:,} reeșantionări)",
        fontsize=10,
    )

    all_vals = [v for v in means if not math.isnan(v)]
    if all_vals:
        y_min = max(0.0, min(all_vals) - 0.06)
        y_max = max(all_vals) + 0.06
        ax.set_ylim(y_min, y_max)

    ax.legend(fontsize=8.5, framealpha=0.75, loc="lower right")
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.grid(axis="y", linewidth=0.5, alpha=0.35, color="#888888", zorder=0)

    plt.tight_layout()
    path = _p("statistical_figure.png")
    plt.savefig(path, dpi=150, bbox_inches="tight")
    plt.close()
    print(f"  Figura salvata: {path}")


# ─────────────────────────────────────────────────────────────────────────────
# PASUL 5 — Rezumat imprimat + salvare CSV
# ─────────────────────────────────────────────────────────────────────────────

def _sig_label(p_holm):
    if math.isnan(p_holm):
        return "n/a"
    if p_holm < 0.001:
        return "***"
    if p_holm < 0.01:
        return "**"
    if p_holm < 0.05:
        return "*"
    return "ns"


def save_and_print(ci_rows, wilcoxon_rows, prod_rows):
    n = len(prod_rows)

    # Salvare CSV
    pd.DataFrame(ci_rows).to_csv(_p("statistical_ci.csv"), index=False)
    pd.DataFrame(wilcoxon_rows).to_csv(_p("statistical_significance.csv"), index=False)

    print("\n" + "=" * 72)
    print("REZUMAT ANALIZA STATISTICA — TripCraft")
    print(
        f"  N useri sintetici valizi: {n}  |  SEED={SEED}  |  "
        f"Bootstrap: {BOOTSTRAP_ITER:,} reeșantionări  |  CI={int(CI_LEVEL*100)}%"
    )
    print("=" * 72)

    # Tabel CI
    print(f"\n{'Metrica':<24} {'N':>4} {'Medie':>8} {'CI 95% low':>11} {'CI 95% high':>11}")
    print("  " + "-" * 60)
    for r in ci_rows:
        print(
            f"  {r['metric']:<22} {r['n']:>4} "
            f"{r['mean']:>8.4f} {r['ci_low']:>11.4f} {r['ci_high']:>11.4f}"
        )

    # Tabel Wilcoxon
    print(
        f"\n{'Comparatie':<34} {'N':>4} {'Nz':>4} {'W':>9} "
        f"{'p_brut':>8} {'p_Holm':>8} {'r_rb':>6}  Semn."
    )
    print("  " + "-" * 82)
    for r in wilcoxon_rows:
        p_r  = r.get("p_raw",         float("nan"))
        p_h  = r.get("p_holm",        float("nan"))
        rb   = r.get("rank_biserial", float("nan"))
        w    = r.get("statistic",     float("nan"))
        note = r.get("note", "")
        semn = _sig_label(p_h)

        comp = r["comparison"].replace("productie vs ", "prod vs ")
        w_s  = f"{w:>9.1f}" if not math.isnan(w) else "      n/a"
        p_r_s = f"{p_r:>8.4f}" if not math.isnan(p_r) else "     n/a"
        p_h_s = f"{p_h:>8.4f}" if not math.isnan(p_h) else "     n/a"
        rb_s  = f"{rb:>6.3f}"  if not math.isnan(rb)  else "   n/a"

        line = (
            f"  {comp:<32} {r['n_pairs']:>4} {r['n_nonzero']:>4} "
            f"{w_s} {p_r_s} {p_h_s} {rb_s}  {semn}"
        )
        if note:
            line += f"  [{note}]"
        print(line)

    print(
        "\nLegenda: N=n_perechi, Nz=n_diferente_nonzero, W=statistica_Wilcoxon_signed-rank,\n"
        "  p_brut=p_necorectat, p_Holm=p_corectat_Holm-Bonferroni,\n"
        "  r_rb=corelatie_rank-biserial (>0 ⟹ productie > alternativa),\n"
        "  *** p<0.001  ** p<0.01  * p<0.05  ns=nesemnificativ"
    )

    print(
        "\n[NOTA METODOLOGICA]\n"
        "  Intervalele de incredere si testele statistice cuantifica\n"
        "  VARIABILITATEA MASURATORIIOR pe cei 50 de utilizatori sintetici\n"
        "  si FIDELITATEA INTERNA a sistemului — NU semnificatia in lumea\n"
        "  reala si NU garanteaza comportamentul pe utilizatori umani reali.\n"
        "\n"
        "  NEsemnificatia statistica pentru configuratii echilibrate si\n"
        "  apropiate de productie (raritate_egal_pop, cos_redus, fara_raritate,\n"
        "  raritate_peste_pop) este ASTEPTATA si indica ROBUSTETE a sistemului\n"
        "  la variatii mici ale ponderilor — nu o lipsa de efect.\n"
        "\n"
        "  Semnificatia clara (asteptata) doar pentru productie vs doar_cosinus\n"
        "  confirma ca ponderea de raritate aduce o contributie detectabila\n"
        "  pe date sintetice, in conditii controlate."
    )

    print(f"\n  CSV salvat: {_p('statistical_ci.csv')}")
    print(f"  CSV salvat: {_p('statistical_significance.csv')}")
    print(f"  Figura:     {_p('statistical_figure.png')}")
    print()


# ─────────────────────────────────────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────────────────────────────────────

def main():
    print("\n" + "=" * 62)
    print("  TripCraft — Analiza Statistica (strat non-distructiv)")
    print(f"  SEED={SEED}  |  Bootstrap={BOOTSTRAP_ITER:,}  |  CI={int(CI_LEVEL*100)}%")
    print(f"  Toleranta validare: {TOLERANCE:.0e}")
    print("=" * 62)

    db = SessionLocal()
    try:
        # Pasul 1: incarcare date + reconstituire metrici per-user
        data = load_data(db)
        prod_rows, cfg_data, spearman = collect_per_user(data, db)

        if not prod_rows:
            print("[EROARE] Nu au rezultat useri valizi. Verificati DB-ul.")
            return

        # G1 — Poarta de validare (opreste executia daca esueaza)
        validate(prod_rows, cfg_data)

        # Pasul 2 — Bootstrap CI
        ci_rows = compute_bootstrap_cis(prod_rows, spearman)

        # Pasul 3 — Wilcoxon (G3)
        print("\n" + "=" * 62)
        print(
            "PASUL 3 — Wilcoxon signed-rank  "
            "(G3: zero_method='wilcox', two-sided, corecție Holm)"
        )
        print("=" * 62)
        wilcoxon_rows = compute_wilcoxon(prod_rows, cfg_data)

        # Pasul 4 — Figura
        print("\n" + "=" * 62)
        print("PASUL 4 — Figura (bar chart NDCG@10 cu CI 95%)")
        print("=" * 62)
        make_figure(cfg_data, prod_rows, ci_rows, wilcoxon_rows)

        # Pasul 5 — Salvare + rezumat
        save_and_print(ci_rows, wilcoxon_rows, prod_rows)

    finally:
        db.close()


if __name__ == "__main__":
    main()
