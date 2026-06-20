# SUMMARY_PRODUCTION_FIX.md — Before/After Quiz Production Fixes

## Modificari aplicate (minime, chirurgicale)

### Fix 1 — Off-by-one culture-history (`app/routers/quiz.py`)

**Problema:** `/start` afisa `L1_ORDER[0]` si seta `card_count=1`. Primul swipe
facea `card_count=2`, iar `get_next_tag(card_count=2)` returna `L1_ORDER[2]`,
sarind `L1_ORDER[1] = "culture-history"` complet.

**Diff:**
```diff
-    if card_count < len(L1_ORDER):
-        l1_slug = L1_ORDER[card_count]
+    if card_count <= len(L1_ORDER):
+        l1_slug = L1_ORDER[card_count - 1]
```

**Efect:** Secventa Phase 1 acopera acum toti indecșii `[0..7]` → 8 categorii L1
obligatorii, inclusiv culture-history.

---

### Fix 2 — Phase 2 prioritizeaza frunze L3 (`app/routers/quiz.py`)

**Problema:** Phase 2 (Faza 3) servea carduri L2 non-leaf din liked L1s.
Faza 2 (care ar servi L3) nu apuca sa ruleze niciodata: dupa 8 L1 + ~8 L2 = 16
carduri, entropia convergea si quizul se oprea. Tagurile frunza (cele 166 pe care
scorarea atractiilor opereaza) nu apareau niciodata.

**Diff (structura Phase 2 rescrisa):**
```diff
-    # Faza 2: L2 liked -> L3 (rareori atins)
-    # Faza 3: L1 liked -> L2 non-leaf (bloca Phase 2)
-    # Faza 4: L3 din L2 liked
-    # Faza 5: orice L2
+    # Faza 2 (primary): L3 frunze din L1-urile placute,
+    #   round-robin prin L2 parinti pentru acoperire in latime
+    # Faza 3 (fallback): L2 non-leaf daca nu exista frunze
+    # Faza 4: orice frunza L3 neafisata
+    # Faza 5 (last resort): orice L2
```

**Efect:** Cardurile 9-20 merg acum pe frunze L3, acoperind subcategorii diferite
ale liked L1s prin round-robin pe parinti L2.

---

### Fix 3 — Garda entropie (`app/routers/quiz.py` + `app/services/quiz_engine.py`)

**Problema:** Oprirea pe entropie putea termina quizul dupa 15 carduri, inainte
de a arata orice frunza.

**quiz_engine.py:**
```diff
+MIN_L3_BEFORE_STOP = 7  # minim frunze vazute inainte de stop pe entropie
```

**quiz.py:**
```diff
+    l3_shown_estimate = max(0, session.card_count - len(L1_ORDER))
     should_stop = (
         session.card_count >= MAX_CARDS
-        or (session.card_count >= MIN_CARDS and entropy < ENTROPY_THRESHOLD)
-        or (session.card_count >= 16 and abs(prev_entropy - entropy) < 0.1)
+        or (session.card_count >= MIN_CARDS and entropy < ENTROPY_THRESHOLD
+            and l3_shown_estimate >= MIN_L3_BEFORE_STOP)
+        or (session.card_count >= 16 and abs(prev_entropy - entropy) < 0.1
+            and l3_shown_estimate >= MIN_L3_BEFORE_STOP)
     )
```

**Efect:** Entropia nu mai poate opri quizul inainte de cel putin 7 frunze vazute
(= cardurile 9-15 cu noul Phase 2). `MAX_CARDS=20` si `MIN_CARDS=15` nemodificate.

---

### Fix 4 — Initializare Bayesian (`app/routers/quiz.py`)

**Problema (NECONFIRMAT anterior):** Sesiunile noi porneau cu `tag_beliefs=None`.
`is_bayesian = bool(None)` = False → fallback la modul additive in clarify.
In practica rar (orice swipe non-skip initializeaza `tag_beliefs`), dar incorect
structural pentru sesiuni cu primul swipe = skip.

**Diff:**
```diff
 session = QuizV4Session(
+    tag_beliefs={},   # explicit gol, nu None — garanteaza modul Beta
     ...
 )
-    is_bayesian = bool(session.tag_beliefs)
+    is_bayesian = session.tag_beliefs is not None  # {} e falsy dar e Bayesian
```

---

## Fidelitatea re-evaluarii

Harness-ul `evaluation/run_production_comparison.py` reimplementeaza logica quiz
(nu importa din `quiz.py` — accesul la DB nu e disponibil in harness).
Toate cele 4 fix-uri au fost oglindite **identic** in functiile harness:
- `_get_next_tag`: fix 1 (index `card_count-1`, conditia `<=`) + fix 2 (Faza 2 L3 priority)
- `quiz_production`: fix 3 (garda `l3_shown_estimate >= MIN_L3_BEFORE_STOP`)

Fix 4 (tag_beliefs init) nu afecteaza harness-ul (harness foloseste Beta direct).

---

## Rezultate Before / After (48 useri valizi, SEED=42)

### Distributia cardurilor pe nivel

| | Inainte | Dupa |
|---|---|---|
| L1 cards/user (medie) | 7.0 | **8.0** |
| L2 cards/user (medie) | 8.7 | **0.0** |
| L3 cards/user (medie) | 0.0 | **8.5** |
| Total cards/user (medie) | 15.7 | 16.5 |

**L1=8** confirma fix 1 (culture-history inclus). **L3=8.5** confirma fix 2
(frunzele apar). **L2=0** confirma ca Phase 2 merge pe frunze, nu pe L2.

### Metrici de calitate (sursa `production`)

| Metrica | Inainte | Dupa | Delta |
|---|---|---|---|
| NDCG@10 | 0.441 | **0.445** | +0.004 |
| Precision@10 | 0.390 | **0.360** | -0.030 |
| Recovery macro (Spearman) | -0.099 | **0.344** | **+0.443** |
| CHit% (selectie tara corecta) | 12.5% | 4.2% | -8.3pp |

### Semnificatie statistica (Wilcoxon)

| Comparatie | NDCG@10 p | sig |
|---|---|---|
| productie-reparata vs oracle | 0.000 | ** |
| productie-reparata vs baseline | 0.313 | ns |
| productie-reparata vs hier2+p | 0.000 | ** |
| productie-reparata vs cf_6040+p | 0.000 | ** |

### Gap fata de variante

| | NDCG@10 | Gap vs oracle | Gap vs productie-reparata |
|---|---|---|---|
| oracle | 0.990 | — | +0.545 |
| cf_6040+p | 0.768 | -0.222 | +0.323 |
| hier2+p | 0.756 | -0.234 | +0.311 |
| **productie-reparata** | **0.445** | **-0.545** | — |
| baseline | 0.497 | -0.493 | +0.052 (ns) |

---

## Interpretare

**Ce s-a imbunatatit:**
- Recovery macro: -0.099 → **+0.344** (+0.443) — profilul reconstrut reflecta
  acum real preferintele latente. Fix-urile ating frunzele pe care scorarea
  opereaza.
- Distributia cardurilor: corecta structural (8 L1, 0 L2, ~8 L3).
- Bug culture-history eliminat.

**Ce nu s-a imbunatatit semnificativ:**
- NDCG@10: +0.004 (nesemnificativ statistic, p=0.31 vs baseline).
- CHit (selectie tara): 12.5% → 4.2% (a scazut).

**Explicatie paradox:**
Profilul bazat pe L3 frunze specifice (ex. "sandy-beaches", "local-cuisine")
este mai precis ca recuperare, dar selecteaza tari diferite de oracle. Oracle
foloseste profilul latent complet (161 frunze); quiz-ul reparat acopera ~8 frunze
din ~2-3 L1s. Diversitatea mai mica de taguri observate → vector de profil mai
ingust → tara selectata poate fi o nisa a liked L1s, nu cea mai buna global.

**Concluzia cheie:** bottleneck-ul NDCG nu este bugs-ul de indexare sau lipsa
L3 in Phase 1 — este **selectia tarii** (CHit 4-17% la toate variantele vs 100%
oracle). cf_6040+p bate productia-reparata cu +0.32 NDCG (semnificativ **),
in principal prin selectia mai buna a tarii (Phase 1 recall 83% vs inferenta L1).

Fix-urile sunt necesare pentru corectitudinea structurala a quizului
(nu mai omit culture-history, ajung la frunze) dar nu rezolva bottleneck-ul
principal care este selectia tarii.

---

*Generat de `evaluation/run_production_comparison.py` (harness cu fix-uri oglindite)
| SEED=42 | 48 useri valizi din 50*
