# Rezumat Evaluare Calitativa — TripCraft (formula IDF rarity)

## Avertisment metodologic

> Ground truth-ul este definit **exclusiv** din profilul-adevar latent
> al userului sintetic, calculat inainte de rularea sistemului.
> Relevanta = cosine_sim(latent_vector, attraction_vector) > 0.2.
> **NU** se foloseste scorul sistemului pentru a defini relevanta
> (ar fi circular). Validitate: **INTERNA** pe date sintetice.

## Configuratie

| Parametru | Valoare |
|---|---|
| Useri sintetici | 50 |
| Useri evaluati (cu relevanti > 0) | 45 |
| Useri sarite (0 atractii relevante) | 5 |
| Prag relevanta (RELEVANCE_THRESHOLD) | 0.2 |
| K values | [5, 10, 20] |
| SEED | 42 |

## 1. Metrici de calitate (configuratia de productie, medii)

| Metrica | @5 | @10 | @20 |
|---|---|---|---|
| Precision | 0.5244 | 0.4622 | 0.3611 |
| Recall | 0.3244 | 0.5057 | 0.7030 |
| NDCG | 0.5842 | 0.6038 | 0.6338 |
| Diversity | 0.6658 | 0.6901 | 0.7026 |

**Recuperare profil (Spearman macro, medie):** 0.5517
**Prevalenta relevantilor in tara (medie):** 0.2821

## 2. Comparatie configuratii ponderi (medie pe 50 useri)

| Configuratie | Prec@10 | Recall@10 | NDCG@10 | Div@10 |
|---|---|---|---|---|
| cos_redus | 0.4600 | 0.5048 | 0.6041 | 0.6892 |
| doar_cosinus | 0.4356 | 0.4551 | 0.5704 | 0.6942 |
| fara_raritate | 0.4644 | 0.4954 | 0.5961 | 0.6881 |
| productie <- productie | 0.4622 | 0.5057 | 0.6038 | 0.6901 |
| raritate_egal_pop | 0.4644 | 0.5045 | 0.6086 | 0.6862 |
| raritate_peste_pop | 0.4533 | 0.4991 | 0.5986 | 0.6862 |

## 3. Runtime (stress test)

- **Quiz**: mean=0.000s  std=0.000s  p50=0.000s  p95=0.000s
- **Country rec.**: mean=0.002s  std=0.001s  p50=0.002s  p95=0.003s
- **Attraction scoring**: mean=0.002s  std=0.001s  p50=0.002s  p95=0.003s
- **Itinerary build**: mean=0.097s  std=0.022s  p50=0.098s  p95=0.134s

## Fisiere generate

- `quality_per_user.csv` — metrici per user
- `quality_per_weight_config.csv` — metrici mediate per configuratie ponderi
- `runtime.csv` — timpii pe etape per user
- `quality_metrics_vs_k.png` — Precision/Recall/NDCG vs K
- `quality_diversity_recovery.png` — distributia diversitatii si recuperarii
- `quality_per_config.png` — comparatia configuratiilor de ponderi
- `runtime_distribution.png` — distributia timpilor pe etape

---
*Generat de `backend/evaluation/run_quality_eval.py` | SEED=42*