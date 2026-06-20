# TripCraft — Roadmap de îmbunătățiri identificate empiric

> Document generat pe baza evaluării empirice din `backend/evaluation/`.
> Cifrele de referință: **Profile Recovery = 0.55**, **NDCG@10 = 0.60** (formula IDF, 50 useri sintetici, SEED=42).

---

## Context — ce s-a făcut deja

### Formula IDF pentru raritate (implementat)

**Problema:** componenta de raritate producea bonus > 0 pentru 0/1429 atracții (media = 0.00002).

**Soluția implementată** în `app/services/itinerary_scorer.py`:
- `_smooth_idf_attr(total, count)` — replică `_smooth_idf` din `country_recommender.py` (liniile 204–209), aplicată pe `attraction_tags`
- `_effective_idf_attr(idf, attr_score)` — replică `_effective_idf` (linia 347–348)
- `get_attraction_tag_idf(db)` — cache global, sursă unică de adevăr
- Prag coborât: `> 0.6` → `> 0.4`
- Numitor: `len(user_high_score_tags)` → `len(common_tags)`
- Formula: `mean(user_score × (effective_idf − 1.0) for tid in common_tags)`

**Rezultat după:** 918/1429 atracții cu bonus > 0, CV raritate = 2.09 (față de 0 anterior).

---

## Bottleneck principal identificat

**Profile Recovery (Spearman macro) = 0.55**

Chestionarul cu 15–20 carduri binare recuperează doar ~55% din ordinea preferințelor la nivel de macro-categorie. Sistemul de scoring e mai bun decât informația pe care o primește.

Cauza: cu 166 taguri-frunză și ~20 de biți de informație (carduri binare), sistemul este sever sub-determinat la nivel de frunze.

---

## Soluțiile propuse

### Soluția 1 — Mai multe carduri + entropie mai agresivă

**Idee:** crește `MAX_CARDS` de la 20 la 25–30 și lasă `compute_entropy` să ghideze selecția spre categoriile cu cea mai mare incertitudine.

**Fișiere afectate:** `app/services/quiz_engine.py` (`MAX_CARDS`), `app/routers/quiz.py`

**Impact estimat:** Profile Recovery 0.55 → 0.63

**Risc:** fricțiune UX pentru user. De compensat cu progress bar și posibilitate de skip.

**Efort:** mic.

---

### Soluția 2 — Etapa clarify mai agresivă

**Idee:** după swipe-uri, identifică categoriile cu incertitudine mare (scor ~0.5) și generează 4–6 întrebări de tip *"Preferi muzee sau castele?"* care actualizează simultan multiple taguri per răspuns.

**Fișiere afectate:** `app/services/clarify_generator.py`, `app/routers/quiz.py`

**Impact estimat:** +0.05–0.08 pe Profile Recovery (cumulat cu Soluția 1)

**Efort:** mediu.

---

### Soluția 3 — Prior ierarhic macro→frunze

**Idee:** tagurile nevăzute nu rămân la 0.5 neutru. Dacă utilizatorul a swiped RIGHT pe `beach-water`, tagurile sibling din același L2 (`sandy-beaches`, `hidden-coves`, `snorkeling`) primesc un prior slab (0.60–0.65) în loc de 0.5.

**Formula:**
```
prior(leaf_slug) = 0.5 + 0.15 × macro_weight(l1_parent)
```

**Fișiere afectate:** `app/routers/quiz.py` (propagare după fiecare swipe) sau `app/services/itinerary_scorer.py` (la construirea vectorului)

**Impact estimat:** Profile Recovery 0.55 → 0.65 (independent, fără carduri extra)

**Efort:** mic. Zero carduri suplimentare.

---

### Soluția 4 — Implicit feedback post-recomandare

**Idee:** dacă userul salvează un itinerariu, face click pe o atracție sau dă skip la o țară, acestea sunt semnale gratuite despre profilul real. Se folosesc pentru a rafina `final_profile` în `QuizV4Session`.

**Modele de semnal:**
- Save itinerariu → atracțiile salvate confirmă tagurile lor
- Skip țară → penalizare ușoară pentru tagurile dominante ale acelei țări
- Click pe atracție → boost pentru tagurile ei

**Fișiere afectate:** `app/routers/itinerary.py`, `app/models/quiz_v4_session.py`

**Impact estimat:** Profile Recovery → 0.80–0.85 după 3–5 interacțiuni

**Efort:** mare. Necesită loop de feedback în produs.

---

### Soluția 5 — CLIP multi-tag per card (cel mai mare câștig per card)

**Idee:** infrastructura CLIP există deja (`app/services/clip_service.py`). O imagine de hiking activează simultan `hiking-trekking`, `contemplative-nature`, `adventure-active`, `wildlife-nature`, `forest-bathing`. Un singur swipe actualizează 4–5 taguri deodată.

**Câștig informațional:** 4–5× per card față de acum.

**Implementare:**
1. La indexarea imaginilor din `QuizImage`, stochezi vectorul CLIP + tagurile activate (similaritate CLIP > prag)
2. La fiecare swipe, actualizezi Bayesian TOATE tagurile activate de imaginea respectivă, nu doar tagul principal

**Formula actualizare:**
```python
for tag_slug, similarity in image_tags:
    delta = RIGHT_WEIGHT * similarity  # sau LEFT_WEIGHT * similarity
    adjust_tag_score(tag_scores, tag_slug, delta, bayesian=True)
```

**Fișiere afectate:** `app/services/clip_service.py`, `app/routers/quiz.py`

**Impact estimat:** Profile Recovery → 0.75–0.80 (cu același număr de carduri)

**Efort:** mediu. Infrastructura CLIP e gata, nevoie de indexare multi-tag și actualizare în router.

---

### Soluția 6 — SVD/PCA pe profile latente (cea mai principiată)

#### Ce este

Cele 166 taguri-frunză nu sunt independente — au o structură de corelație. SVD descoperă empiric k=6–10 „axe principale de preferință" din date și comprimă profilul în acel spațiu.

#### Matricea de intrare

```
M [n_useri × 166_taguri] → SVD → U [n×k] × Σ [k×k] × Vᵀ [k×166]
```

**V** (tag embeddings în spațiul latent) e rezultatul principal: știi cum se proiectează fiecare tag pe fiecare axă.

#### Axele latente descoperite (exemple tipice)

```
Axa 1: "solitar în natură"  ←→  "social urban"
Axa 2: "cultural rafinat"   ←→  "activ sportiv"
Axa 3: "warm coast"         ←→  "cold adventure"
Axa 4: "budget"             ←→  "luxury"
Axa 5: "familie"            ←→  "couple romantic"
```

#### Două variante de integrare

**Varianta A — post-procesare (Bayesian rămâne intact):**
```
Quiz Bayesian (neschimbat) → tag_scores parțial → SVD reconstruction → profil complet 166 taguri
```
Quiz-ul rulează exact ca acum. SVD completează tagurile neobservate după quiz, exploatând corelațiile. Zero schimbări în quiz, efort mic.

**Varianta B — redesign quiz:**
Quiz-ul estimează direct coordonatele latente (k=8 numere), nu taguri individuale. Cardurile sunt alese să discrimineze pe axele latente. Mai puternic teoretic, dar rescriere completă a quiz-ului.

#### Cu ce date pentru SVD

**Opțiunea recomandată: profile sintetice atent construite**

Nu ai nevoie de 100+ sesiuni reale. Poți rula SVD pe profile sintetice dacă sunt atent construite să reflecte structura de corelații reale:

```
C(8,1) =  8  profile cu o categorie dominantă
C(8,2) = 28  profile cu două categorii dominante
C(8,3) = 56  profile cu trei categorii dominante
+ 50–100 variante cu specializare internă per categorie
+ corelații cross-categorie realiste (luxury, budget, etc.)
─────────────────────────────────────────────────────
Total: ~200–300 profile
```

**Limita importantă:** SVD pe sintetice descoperă structura modelului tău generativ, nu neapărat pe cea a utilizatorilor reali. Dacă corelațiile sunt realiste, e o bună aproximare. Când acumulezi date reale, blending-ul rezolvă discrepanța.

#### Strategia de evoluție

```
Faza 1 (acum):           SVD pe ~300 profile sintetice atent construite
                          k = 6–8 axe latente
                          Profile Recovery estimat: 0.68–0.75

Faza 2 (50+ sesiuni):    M = α·M_synthetic + (1−α)·M_real
                          α scade pe măsură ce cresc datele reale
                          Profile Recovery estimat: 0.78–0.85

Faza 3 (200+ sesiuni):   SVD pur pe date reale
                          Profile Recovery estimat: 0.83–0.88
```

**Efort:** mediu (Varianta A). Necesită generare profile sintetice structurate, SVD, și un pas de reconstrucție post-quiz.

---

## Plafonul teoretic

Chiar cu toate soluțiile implementate, Profile Recovery nu va ajunge la 1.0.

**De ce:** problema e parțial information-teoretică. Fiecare card binar = ~1 bit. Cu 30 de carduri ai ~30 biți. Recuperarea completă a unui vector de 166 dimensiuni cu precizie bună necesită mult mai mult.

**Plafonul realist al oricărui sistem quiz:** ~0.85–0.90.

Restul de gap (0.10–0.15) vine din:
- Tagurile nu acoperă complet spațiul real de preferințe (preferințe ne-etichetate)
- Zgomot inerent în răspunsurile utilizatorilor (inconsistență)
- Preferințe contextuale (același user vrea altceva vara față de iarnă)

---

## Impact estimat cumulat

| Soluție | Profile Recovery | NDCG@10 |
|---|---|---|
| Starea actuală (IDF implementat) | 0.55 | 0.60 |
| + Prior ierarhic (Sol. 3) | 0.65 | 0.63 |
| + CLIP multi-tag (Sol. 5) | 0.75 | 0.67 |
| + SVD Varianta A, sintetice (Sol. 6) | 0.75–0.78 | 0.68 |
| + Implicit feedback (Sol. 4, timp) | 0.82–0.85 | 0.72–0.74 |
| **Plafon realist** | **~0.88** | **~0.76** |

> Estimările NDCG sunt bazate pe corelația observată empiric: Profile Recovery +0.10 ≈ NDCG +0.03–0.04.

---

## Prioritizare recomandată

| Prioritate | Soluție | Efort | Impact | Când |
|---|---|---|---|---|
| 1 | Prior ierarhic macro→frunze (Sol. 3) | mic | +0.10 PR | acum |
| 2 | CLIP multi-tag (Sol. 5) | mediu | +0.10–0.15 PR | acum |
| 3 | SVD Varianta A pe sintetice (Sol. 6) | mediu | +0.03–0.05 PR | acum |
| 4 | Mai multe carduri (Sol. 1) | mic | +0.08 PR | acum |
| 5 | Clarify agresiv (Sol. 2) | mediu | +0.05–0.08 PR | sprint următor |
| 6 | Implicit feedback (Sol. 4) | mare | +0.07–0.10 PR | când ai engagement data |
| 7 | SVD pe date reale (Sol. 6 Faza 3) | mare | +0.05–0.08 PR | 200+ sesiuni reale |

---

*Generat: 2026-06-08 | Evaluare: `backend/evaluation/` | SEED=42*
