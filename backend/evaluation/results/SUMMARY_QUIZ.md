# Rezumat Evaluare Variante Quiz — TripCraft

## Avertisment metodologic

> Recuperarea măsoară reconstrucția unui **profil latent sintetic** sub modelul de
> simulare a swipe-urilor, **nu comportament uman real**.
> Metricile sunt Spearman rank-correlation între scorurile estimate și profilul latent.
> Validitate: **INTERNĂ** pe date sintetice. Nu se poate generaliza direct la useri reali.
> Swipe-urile sunt simulate probabilistic cu P(right) = sigmoid(5*(lat-0.5)).

## Configuratie

| Parametru | Valoare |
|---|---|
| Useri sintetici | 50 |
| SEED | 42 |
| Phase2 carduri | 20 |
| Prior ierarhic final (strength) | 0.3 |
| Prior selectie moderat (selected/non-sel) | 0.65/0.38 |
| Prior selectie tare (selected/non-sel) | 0.82/0.25 |
| Phase1 MAX_SELECTED | 4 |

## Metrici per varianta (medie pe 50 useri)

| Varianta | Leaf | Macro | DomLeaf | Delta DomLeaf |
|---|---|---|---|---|
| baseline | 0.1745 | 0.5552 | 0.0258 | +0.0000 |
| baseline+p | 0.5582 | 0.5543 | 0.0218 | -0.0040 |
| hier2+p | 0.4725 | 0.5263 | 0.1973 | +0.1715 |
| cf_6040+p | 0.5816 | 0.5939 | 0.1177 | +0.0919 |
| cf_sp_pure_mod | 0.4815 | 0.5698 | 0.0233 | -0.0025 |
| cf_sp_pure_str | 0.5610 | 0.6061 | -0.0019 | -0.0277 |
| cf_sp_8020_mod | 0.4843 | 0.5709 | 0.0077 | -0.0181 |
| cf_sp_8020_str | 0.5465 | 0.5714 | -0.0124 | -0.0382 |

## Semnificatie statistica — Dominant-Leaf (Wilcoxon one-sided)

| Varianta | vs baseline p | sig | vs hier2+p p | sig |
|---|---|---|---|---|
| baseline+p | 0.5096 | ns | 0.9944 | ns |
| hier2+p | 0.0015 | ** | nan | nan |
| cf_6040+p | 0.0495 | ** | 0.8153 | ns |
| cf_sp_pure_mod | 0.4673 | ns | 0.9939 | ns |
| cf_sp_pure_str | 0.5289 | ns | 0.9933 | ns |
| cf_sp_8020_mod | 0.6784 | ns | 0.9966 | ns |
| cf_sp_8020_str | 0.7056 | ns | 0.9949 | ns |

## Semnificatie statistica — Macro (Wilcoxon one-sided)

| Varianta | vs baseline p | sig | vs hier2+p p | sig |
|---|---|---|---|---|
| baseline+p | 0.6768 | ns | 0.2420 | ns |
| hier2+p | 0.7550 | ns | nan | nan |
| cf_6040+p | 0.2845 | ns | 0.0690 | * |
| cf_sp_pure_mod | 0.4771 | ns | 0.1811 | ns |
| cf_sp_pure_str | 0.1938 | ns | 0.0351 | ** |
| cf_sp_8020_mod | 0.5834 | ns | 0.2511 | ns |
| cf_sp_8020_str | 0.5834 | ns | 0.2450 | ns |

## Phase 1 — Acuratete selectie categorii

| Metrica | Valoare |
|---|---|
| Recall dominant L1 | 0.830 (std=0.255) |
| Precision | 0.740 |
| All correct | 66.0% |
| N selectate (medie) | 2.7 |
| Comparatie quiz anterior (rand) | recall=0.630, all_correct=24% |

## Robustete la zgomot (dominant-leaf mean)

| Varianta | Zgomot 0% | Zgomot 10% | Zgomot 20% | Degradare |
|---|---|---|---|---|
| baseline | 0.0257 | 0.0199 | 0.0495 | +0.0238 |
| hier2+p | 0.1973 | 0.1349 | 0.0907 | -0.1066 |
| cf_6040+p | 0.1177 | 0.0866 | 0.1685 | +0.0508 |
| cf_sp_pure_str | -0.0019 | 0.0964 | 0.0903 | +0.0922 |

## Runtime (ms)

| Varianta | Mean | p95 |
|---|---|---|
| baseline | 0.095 | 0.142 |
| baseline+p | 0.092 | 0.182 |
| hier2+p | 0.138 | 0.229 |
| cf_6040+p | 0.082 | 0.100 |
| cf_sp_pure_mod | 0.093 | 0.165 |
| cf_sp_pure_str | 0.102 | 0.232 |
| cf_sp_8020_mod | 0.110 | 0.291 |
| cf_sp_8020_str | 0.098 | 0.201 |

## Concluzii cheie

- **Best DomLeaf**: `hier2+p` (0.1973)
- **Best Macro**: `cf_sp_pure_str` (0.6061)
- Phase 1 explicit: recall=0.83 vs 0.63 (inferit din 1 card random)

## Fisiere generate

- `quiz_variants_metrics.csv` — metrici per user per varianta
- `quiz_significance.csv` — p-values Wilcoxon
- `quiz_noise_robustness.csv` — degradare la zgomot
- `quiz_variants_bars.png` — bar chart comparativ
- `quiz_noise_robustness.png` — curbe degradare zgomot

*Generat de `evaluation/run_quiz_variants_test.py` | SEED=42*