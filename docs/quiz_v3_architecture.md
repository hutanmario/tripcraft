# Quiz V3 — Arhitectură Backend

## Prezentare generală

Quiz V3 este un sistem de profilare a preferințelor de călătorie în 3 etape secvențiale, bazat pe semnal implicit (swipe pe imagini), rafinare explicită (drilldown în taxonomie) și clarificare activă (întrebări dinamice).

```
Etapa 1: SWIPE          Etapa 2: DRILLDOWN        Etapa 3: CLARIFY
─────────────────       ──────────────────────    ─────────────────────
20 imagini Unsplash  →  Arbore taxonomie         →  4 întrebări dinamice
  swipe right/left      ordonat după relevanță      + 1 întrebare buget
  ↓                     frunze pre-selectate        ↓
  CLIP tags aggregate   ↓                           final_profile [0,1]
  swipe_aggregated_tags drilldown_selections        → UserPreference UPSERT
```

## Modelul de date: QuizV3Session

Un singur rând PostgreSQL cu câmpuri JSONB pentru toate etapele.

**Decizie de design:** JSONB în loc de tabele separate.
- Avantaj principal: o singură query `SELECT * FROM quiz_v3_sessions WHERE id = $1` returnează tot statul sesiunii, indiferent de etapă.
- Avantaj secundar: schema flexibilă per etapă fără migrări.
- Trade-off acceptat: nu poți face JOIN-uri eficiente pe conținut JSONB (dar sesiunile sunt întotdeauna accesate by PK).

| Câmp | Tip | Descriere |
|------|-----|-----------|
| `id` | UUID PK | Generat cu uuid4() la creare |
| `user_id` | Integer FK nullable | NULL pentru sesiuni anonime |
| `current_stage` | String | `swipe` → `drilldown` → `clarify` → `completed` |
| `swipe_results` | JSONB | `{str(image_id): "right"\|"left"}` |
| `swipe_aggregated_tags` | JSONB | `{tag_slug: float_0_to_1}` după normalizare |
| `drilldown_selections` | JSONB | `[tag_id, ...]` — ID-uri întregi ale frunzelor |
| `clarify_questions` | JSONB | Întrebările generate, cached pentru /complete |
| `clarify_answers` | JSONB | `[{question_id, option_id}, ...]` |
| `final_profile` | JSONB | `{tag_slug: float_0_to_1}` — scris o singură dată |

---

## API Endpoints

### POST `/quiz/v3/start`

**Input:** Header `Authorization: Bearer <token>` opțional

**Output:**
```json
{"session_id": "uuid-v4", "stage": "swipe"}
```

**Comportament:** Creează `QuizV3Session` cu `user_id` din JWT dacă e prezent, altfel `user_id=NULL`.

---

### GET `/quiz/v3/swipe/images?session_id=X`

**Output:**
```json
[
  {
    "id": 42,
    "file_path": "quiz-images-v3/mountain/mountain_1.jpg",
    "photographer": "John Doe",
    "photographer_url": "https://unsplash.com/@johndoe",
    "source_url": "https://unsplash.com/photos/abc123"
  }
]
```

**Algoritm stratificat:**
1. Filtrează `QuizImage` unde `is_active=True AND clip_processed_at IS NOT NULL`
2. Grupează imaginile pe `source_category`
3. Alege câte 1 imagine random din fiecare categorie (până la 15 categorii)
4. Completează până la 20 cu imagini random din pool-ul total

**503 dacă:** mai puțin de 20 imagini cu CLIP procesat disponibile.

**IMPORTANT:** `clip_tags` nu se returnează niciodată — ar influența alegerile utilizatorului.

---

### POST `/quiz/v3/swipe/answer`

**Input:**
```json
{"session_id": "uuid", "image_id": 42, "direction": "right"}
```

**Output:**
```json
{"progress": "15/20", "answered": 15, "complete": false}
```

Suprascrie răspunsul dacă utilizatorul re-swipuie aceeași imagine.

---

### POST `/quiz/v3/swipe/complete`

**Input:** `{"session_id": "uuid"}`

**Output:**
```json
{
  "next_stage": "drilldown",
  "top_tags": [{"name": "mountain", "score": 0.92}, ...]
}
```

**Algoritm de agregare CLIP tags:**

```
pentru fiecare imagine cu direction='right':
    profil[tag] += clip_score(tag)

pentru fiecare imagine cu direction='left':
    profil[tag] -= clip_score(tag) × 0.3

# Decizie: factorul 0.3 pentru semnal negativ
# Motivație: swipe-left poate indica lipsă interes, nu neapărat repulsie activă.
# Factorul 0.3 previne eliminarea completă a tagurilor din categorii valide
# dacă câteva imagini cu conținut mixt sunt respinse.

# Păstrăm doar valorile pozitive
profil_pozitiv = {k: v for k, v in profil.items() if v > 0}

# Min-max normalizare pe valorile pozitive → [0, 1]
# Decizie: normalizare pe pozitive (nu pe întreg range-ul cu negative)
# Motivație: vrem scoruri interpretabile ca preferințe (0=neutral, 1=puternic preferat),
# nu ca distanțe față de cel mai respins tag.
min_val = min(profil_pozitiv.values())
max_val = max(profil_pozitiv.values())
profil_normalizat[tag] = (v - min_val) / (max_val - min_val)
```

---

### GET `/quiz/v3/drilldown/tree?session_id=X`

**Output (structură nested):**
```json
{
  "tree": [
    {
      "id": "nature",
      "name": "Nature",
      "relevance_score": 0.72,
      "expanded": true,
      "highlighted": true,
      "children": [
        {
          "id": "mountain",
          "name": "Mountain",
          "relevance_score": 0.85,
          "expanded": true,
          "highlighted": true,
          "children": [
            {
              "id": 42,
              "name": "alpine",
              "slug": "alpine",
              "relevance_score": 0.88,
              "pre_selected": true,
              "is_leaf": true
            }
          ]
        }
      ]
    }
  ]
}
```

**Algoritm de scoring:**

| Nivel | Formula |
|-------|---------|
| Frunze | `swipe_aggregated_tags.get(tag.slug, 0.0)` |
| Categorii mid | `mean(scor_frunze_copii)` |
| Root | `mean(scor_categorii_copii)` |

**Praguri și motivații:**

| Flag | Prag | Motivație |
|------|------|-----------|
| `pre_selected` | scor > 0.5 | Peste media normalizată → semnal clar pozitiv |
| `expanded` | scor > 0.4 | Ușor peste medie → merită explorat |
| `highlighted` | scor > 0.6 | Categorie dominantă, evidențiată vizual |

**Notă taxonomie:** Cele 51 frunze orfane (fără mid-parent) nu apar în arbore — există ca tags standalone pentru compatibilitate cu quiz_v2 și recomandări.

---

### POST `/quiz/v3/drilldown/submit`

**Input:**
```json
{"session_id": "uuid", "selected_tag_ids": [42, 17, 8, 55]}
```

**Validare:** Verifică că toate ID-urile există în DB și sunt frunze (`is_leaf=True`).

**Output:** `{"next_stage": "clarify", "selected_count": 4}`

---

### GET `/quiz/v3/clarify/questions?session_id=X`

**Output:**
```json
{
  "questions": [
    {
      "id": "q_a1b2c3d4",
      "type": "conflict",
      "question": "Observăm că ești atras atât de Mountain cât și de Beach. Care îți place mai mult?",
      "options": [
        {"id": "opt_1", "label": "Mountain", "tag_adjustments": {"mountain": 0.3, "beach": -0.2}},
        {"id": "opt_2", "label": "Beach", "tag_adjustments": {"beach": 0.3, "mountain": -0.2}},
        {"id": "opt_3", "label": "Ambele la fel", "tag_adjustments": {}}
      ],
      "context": "Detected conflict: mountain (0.70) vs beach (0.65), co-occurrence: 0.08"
    },
    {
      "id": "q_budget",
      "type": "budget",
      "question": "Care este bugetul tău preferat pentru călătorii?",
      "options": [
        {"id": "opt_budget", "label": "Budget-friendly", "tag_adjustments": {"budget": 1.0, "luxury": -0.5}},
        {"id": "opt_mid", "label": "Mid-range", "tag_adjustments": {"mid-range": 1.0}},
        {"id": "opt_luxury", "label": "Luxury", "tag_adjustments": {"luxury": 1.0, "budget": -0.5}}
      ],
      "context": "Always generated — budget is the most impactful clarification axis."
    }
  ]
}
```

Întrebările se generează o singură dată și se stochează în `clarify_questions` JSONB. Apeluri ulterioare returnează cache-ul.

---

### POST `/quiz/v3/clarify/answer`

**Input:**
```json
{"session_id": "uuid", "question_id": "q_a1b2c3d4", "option_id": "opt_1"}
```

Suprascrie răspunsul anterior la aceeași întrebare dacă există.

---

### POST `/quiz/v3/clarify/complete`

**Output:**
```json
{
  "complete": true,
  "profile": {"mountain": 0.92, "hiking": 0.85, "mid-range": 1.0, ...},
  "redirect_to": "/recommendations"
}
```

**Algoritm finalizare:**

```
# 1. Construiește profilul combinat
combined = dict(swipe_aggregated_tags)
pentru fiecare tag_id în drilldown_selections:
    combined[tag.slug] = swipe_tags.get(tag.slug, 1.0)
    # Decizie: 1.0 dacă absent din swipe = selecție explicită puternică

# 2. Aplică ajustările din răspunsuri
pentru fiecare answer în clarify_answers:
    option = găsește opțiunea în clarify_questions
    pentru fiecare (tag_slug, adjustment) în option.tag_adjustments:
        combined[tag_slug] = combined.get(tag_slug, 0) + adjustment

# 3. Clamp la [0, 1]
final_profile = {k: max(0.0, min(1.0, v)) for k, v in combined.items() if v > 0}

# 4. UPSERT în UserPreference (doar pentru useri autentificați)
pentru fiecare (slug, score) în final_profile:
    dacă UserPreference există:
        score_nou = max(score, score_vechi × 0.7)
        # Decizie: blending max(new, old×0.7)
        # Motivație: previne scăderi dramatice ale preferințelor existente.
        # Un user care a mai dat feedback pozitiv la un tag nu îl va "uita" 
        # complet dacă quiz-ul îi dă un scor mai mic (poate nu a swipuit 
        # imagini relevante în această sesiune).
        source = 'mixed' dacă exista altă sursă
    altfel:
        INSERT cu score, source='quiz_v3'
```

---

## ClarifyEngine — Algoritmii celor 3 Detectoare

### 1. detect_conflicts — Co-occurrence în destinații reale

**Problemă:** Userul poate fi atras de taguri care rareori coexistă geografic (ex: munte + plajă tropicală, sau nightlife + quiet retreat).

**Algoritm:**
```
pentru fiecare pereche (tag_a, tag_b) cu scor > 0.5 în profil:
    count_a = nr destinații cu tag_a
    count_b = nr destinații cu tag_b
    count_both = nr destinații cu ambele (SQL JOIN pe destination_tags)
    
    co_occurrence = count_both / min(count_a, count_b)
    
    dacă co_occurrence < 0.2:  # sub 20% din destinații le au pe ambele
        conflict detectat
```

**Prag co_occurrence < 0.2:** Sub 20% din destinațiile care conțin tag_a (sau tag_b) le conțin pe ambele. Ales empiric: dacă 1 din 5 destinații le combină, nu e un conflict real. Dacă mai puțin de 1 din 5, merită clarificat.

**Exemplu real:** mountain (scor 0.85) vs beach (scor 0.80). Dacă din 100 destinații cu "mountain" doar 5 au și "beach" → co_occurrence = 0.05 < 0.2 → conflict.

### 2. detect_category_gaps — Semnal puternic fără rafinare

**Problemă:** Userul poate fi atras de o categorie (ex: "Gastronomy") cu un scor swipe mediu mare, dar să nu fi selectat nicio frunză din ea în drilldown — pierdere de informație.

**Algoritm:**
```
pentru fiecare categorie mid-level:
    avg_score = mean(combined_profile[leaf.slug] for leaf in children)
    
    has_drilldown = any(leaf.id in drilldown_selections for leaf in children)
    
    dacă avg_score > 0.5 și not has_drilldown:
        gap detectat → generăm "Ce te interesează din <categorie>?"
```

**Prag 0.5:** Același cu `pre_selected` — categorii care ar fi apărut evidențiate în drilldown dar au rămas neexplorate.

### 3. detect_ambiguous_signals — Confirmarea semnalelor moderate

**Problemă:** Taguri cu scor 0.3-0.6 sunt "zgomotoase" — userul a dat semnal mixt (câteva imagini right, câteva left). Merită o întrebare simplă de confirmare.

**Algoritm:**
```
pentru fiecare tag cu 0.3 ≤ score ≤ 0.6:
    ambiguity = |score - 0.5|  # distanța față de punctul de maximă incertitudine

sortare ascending după ambiguity → cele mai ambigue primele
returnează top 5
```

**Prag [0.3, 0.6]:** Sub 0.3 = semnal clar negativ (nu merită confirmat). Peste 0.6 = semnal clar pozitiv (nu merită confirmat). Zona [0.3, 0.6] = semnal neclar, beneficiază de 1 întrebare.

### Prioritizare și limita de 4 + 1 întrebări

```
Prioritate 1: Conflicte (rezolvă ambiguitate mare, semnal contrar)
Prioritate 2: Category gaps (recuperează informație pierdută)
Prioritate 3: Ambiguous signals (rafinare fină)
+ Buget (întotdeauna ultimul — dimensiunea cea mai impactantă)
```

**Decizie: max 4 dinamice + 1 buget = 5 total.** Calibrat pentru echilibrul calitate/abandon:
- Mai puțin de 3 întrebări → profilul rămâne insuficient rafinat
- Mai mult de 6 întrebări → abandon rate crește semnificativ (user testing intern)
- Întrebarea de buget e hardcodată și obligatorie: impactul cel mai mare asupra recomandărilor

---

## Fișiere implementate

| Fișier | Responsabilitate |
|--------|-----------------|
| `app/models/quiz_v3_session.py` | ORM model cu JSONB multi-etapă |
| `app/routers/quiz_v3.py` | 9 endpoint-uri, prefix `/quiz/v3` |
| `app/services/quiz_v3_clarify_engine.py` | Cei 3 detectori + generator întrebări |
| `tests/test_quiz_v3_flow.py` | 13 teste (6 integrare + 5 unit + 2 tree ordering) |

## Compatibilitate

Quiz V2 (`app/routers/quiz_v2.py`) rămâne intact și funcțional ca fallback.
Quiz V3 e complet independent — tabele separate, router separat, servicii separate.
