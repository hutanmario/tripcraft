# Rezumat Evaluare Downstream — TripCraft Quiz Design vs Calitate Recomandari

## Avertisment metodologic

> Relevanța (ground truth) e **cosine_sim(latent, atracție) > 0.2**, definită din
> profilul latent, **INDEPENDENT de scorul sistemului**. Ground truth și ordonarea
> împart reprezentarea cosinus peste taguri — ele sunt corelate structural.
> Aceasta înseamnă că ORACLE va fi avantajat metodologic față de quiz-uri,
> deoarece profilul oracle e identic cu cel care definește relevanța.
> Validitate: **INTERNĂ** pe date sintetice. Nu se generalizează la utilizatori reali.
> Evaluarea se face pe **aceeași țară** (cea aleasă de ORACLE) pentru comparabilitate.

## Configuratie

| Parametru | Valoare |
|---|---|
| Useri sintetici | 50 |
| Useri valizi (relevant > 0) | 48 |
| Useri sarite | 2 |
| SEED | 42 |
| Prag relevanta | 0.2 |
| K values | [5, 10, 20] |
| Tara evaluare | oracle top-1 (fixa) |

## Metrici per sursa de profil (medie)

| Sursa | Recovery | P@10 | R@10 | NDCG@5 | NDCG@10 | NDCG@20 | Gap NDCG@10 | CountryHit |
|---|---|---|---|---|---|---|---|---|
| **oracle** | 0.972 | 0.6542 | 0.8161 | 0.9973 | 0.9903 | 0.9908 | +0.0000 | 1.000 |
| **baseline** | 0.562 | 0.3896 | 0.4324 | 0.4833 | 0.4968 | 0.5376 | -0.4935 | 0.083 |
| **hier2+p** | 0.521 | 0.5146 | 0.6109 | 0.7648 | 0.7564 | 0.7930 | -0.2339 | 0.167 |
| **cf_6040+p** | 0.605 | 0.5438 | 0.6815 | 0.7416 | 0.7683 | 0.8015 | -0.2220 | 0.167 |

## Semnificatie statistica (Wilcoxon)

### NDCG@10 — vs oracle (one-sided, quiz < oracle) + vs baseline (two-sided)

| Sursa | vs oracle p | sig | vs baseline p | sig |
|---|---|---|---|---|
| baseline | 0.0000 | ** | — | — |
| hier2+p | 0.0000 | ** | 0.0 | ** |
| cf_6040+p | 0.0000 | ** | 0.0 | ** |

## Corelatie recuperare profil vs NDCG@10

| Sursa | N | Pearson r | p | Spearman r | p |
|---|---|---|---|---|---|
| **oracle** | 48 | 0.2337 | 0.1098 | 0.1882 | 0.2002 |
| **baseline** | 48 | 0.2308 | 0.1145 | 0.2428 | 0.0963 |
| **hier2+p** | 48 | 0.1282 | 0.3853 | 0.1676 | 0.2548 |
| **cf_6040+p** | 48 | 0.3804 | 0.0077 | 0.3215 | 0.0259 |
| **POOLED** | 192 | 0.4467 | 0.0000 | 0.5429 | 0.0000 |

## Regula de decizie

- **Gap cel mai bun quiz vs oracle (NDCG@10):** `-0.2220`
- **Corelatie pooled recuperarevsNDCG@10:** Spearman `r=0.5429`, `p=0.0000`

> **CONCLUZIE**: corelatie semnificativa (`|r| >= 0.20`) -> recuperarea profilului conteaza pentru calitatea recomandarilor. Imbunatatirile de quiz se traduc in NDCG mai mare.

## Fisiere generate

- `downstream_per_user.csv` — user x sursa x metrici
- `downstream_summary.csv` — medii + gap vs oracle
- `downstream_significance.csv` — Wilcoxon p-values
- `downstream_recovery_correlation.csv` — corelare recuperare profil vs NDCG@10
- `downstream_metrics.png` — bar chart comparativ per sursa
- `downstream_recovery_scatter.png` — scatter recuperare vs NDCG@10

*Generat de `evaluation/run_downstream_eval.py` | SEED=42*