# Comparatie Productie vs Variante Quiz — TripCraft

## Avertisment metodologic
> Validitate INTERNA pe date sintetice (SEED=42, 50 useri). Ground truth si scorarea
> impart reprezentarea cosinus -- oracle avantajat metodologic.
> Evaluarea se face pe aceeasi tara (top-1 oracle) pentru comparabilitate.
> NB: productia are un bug -- L1_ORDER[1]='culture-history' este sarit in Phase 1.

## Configuratie
| Parametru | Valoare |
|---|---|
| Useri valizi | 48 |
| SEED | 42 |
| K | [5, 10, 20] |
| Relevance threshold | 0.2 |

## Metrici comparative (medie pe useri valizi)

| Sursa | Recovery | Cards | CHit% | P@10 | NDCG@10 | Gap NDCG@10 |
|---|---|---|---|---|---|---|
| **oracle** | 0.972 | 161 | 100% | 0.6542 | 0.9903 | +0.0000 |
| **production** | 0.344 | 16 | 4% | 0.3604 | 0.4451 | -0.5452 |
| **baseline** | 0.562 | 18 | 8% | 0.3896 | 0.4968 | -0.4935 |
| **hier2+p** | 0.521 | 20 | 17% | 0.5146 | 0.7564 | -0.2339 |
| **cf_6040+p** | 0.605 | 20 | 17% | 0.5438 | 0.7683 | -0.2220 |

## Semnificatie NDCG@10 (Wilcoxon)

| Sursa | vs oracle p | sig | vs productie p | sig |
|---|---|---|---|---|
| production | 0.0000 | ** | — | — |
| baseline | 0.0000 | ** | 0.3133 | ns |
| hier2+p | 0.0000 | ** | 0.0000 | ** |
| cf_6040+p | 0.0000 | ** | 0.0000 | ** |

## Corelatie recuperare profil vs NDCG@10

| Sursa | Pearson r | p | Spearman r | p |
|---|---|---|---|---|
| **oracle** | 0.2337 | 0.1098 | 0.1882 | 0.2002 |
| **production** | -0.0521 | 0.7250 | 0.0289 | 0.8453 |
| **baseline** | 0.2308 | 0.1145 | 0.2428 | 0.0963 |
| **hier2+p** | 0.1282 | 0.3853 | 0.1676 | 0.2548 |
| **cf_6040+p** | 0.3804 | 0.0077 | 0.3215 | 0.0259 |
| **POOLED** | 0.4070 | 0.0000 | 0.5085 | 0.0000 |

## Distributia cardurilor in productie
| Nivel | Medie/user |
|---|---|
| L1 (categorii) | 8.0 |
| L2 (subcategorii) | 0.0 |
| L3/frunze | 8.5 |
| Total | 16.5 |
| **Bug**: L1_ORDER[1]='culture-history' sarit in Phase 1 ||

## Concluzie

- Productie NDCG@10: `0.4451` (gap vs oracle: `-0.5452`)
- Cel mai bun quiz nou: `cf_6040+p` NDCG@10=`0.7683`
- Diferenta productie vs cel mai bun quiz: `+0.3232`

*Generat de evaluation/run_production_comparison.py | SEED=42*