# Rezumat Evaluare Empirica — TripCraft Scoring

**Formula de productie:** `final = 0.70*cosinus + 0.20*popularitate + 0.10*raritate`

| Parametru | Valoare |
|---|---|
| Atractii in DB | 1429 |
| Etichete-frunza | 166 |
| Profiluri testate | 26 |
| Seed | 42 |

## 1. Coeficienti de variatie per componenta

| Componenta | Media | Std | Min | Max | **CV** |
|---|---|---|---|---|---|
| cosinus | 0.0895 | 0.0960 | 0.0000 | 0.6399 | **1.0726** |
| popularitate | 0.8323 | 0.0884 | 0.5119 | 1.0000 | **0.1062** |
| raritate | 0.0779 | 0.1630 | 0.0000 | 0.9500 | **2.0924** |

> **Confirmat:** popularitatea are CV semnificativ mai mic decat cosinusul (0.1062 vs 1.0726), validand ipoteza ca termenul de popularitate se aplateaza — variatie redusa intre atractii, impact limitat in reordonare.

## 2. Sensibilitate la ponderi (vs. configuratia de productie)

| Configuratie | Ponderi (cos/pop/rar) | Spearman | Kendall | Overlap@10 | Overlap@20 |
|---|---|---|---|---|---|
| doar_cosinus | 1.00/0.00/0.00 | 0.8478 | 0.7531 | 0.6885 | 0.6846 |
| fara_pop | 0.78/0.00/0.22 | 0.8517 | 0.7595 | 0.6269 | 0.6096 |
| pop_ridicata | 0.50/0.40/0.10 | 0.9757 | 0.9085 | 0.7346 | 0.8192 |
| raritate_rid | 0.50/0.20/0.30 | 0.9926 | 0.9569 | 0.6885 | 0.7365 |

> \* Spearman/Kendall = N/A pentru 3 profiluri la care toate scorurile cosinus sunt 0 (profil fara suprapunere cu atractiile). In aceste cazuri, configuratia 'productie' ordoneaza prin popularitate (safety-net), iar configuratiile fara popularitate produc scoruri constante — corelatie de rang nedefinita matematic.

## 3. Efectul asupra itinerariului (top-15, medie pe 3-4 profiluri)

| Metrica | Productie | Doar cosinus |
|---|---|---|
| Atractii coincidente | **8.8/15** | — |
| Diversitate categorii | 2.2 | 2.5 |
| Durata totala (ore) | 34.0 | 33.0 |

## Fisiere generate

- `scoring_components_stats.csv` — componente detaliate per profil si atractie
- `coeficient_variatie.png` — grafic bar CV pe cele 3 componente
- `sensitivity_rankings.csv` — Spearman/Kendall/overlap per profil si configuratie
- `overlap_configuratii.png` — grafic overlap@10 si overlap@20 per configuratie
- `itinerary_effect.csv` — comparatie itinerariu productie vs. doar cosinus

---
*Generat automat de `backend/evaluation/run_evaluation.py` | SEED=42*