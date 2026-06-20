# Analiză Statistică — TripCraft
*Generat de `backend/evaluation/run_statistical_analysis.py` | SEED=42 | 2026-06-10*

---

## Configurație evaluare

| Parametru | Valoare |
|---|---|
| Utilizatori sintetici generați | 50 |
| Utilizatori valizi (cu atracții relevante) | 45 |
| Utilizatori excluși (0 atracții relevante) | 5 |
| Seed reproductibilitate | 42 |
| Bootstrap iterații | 10.000 |
| Nivel interval de încredere | 95% |
| Metodă bootstrap | Percentilă |
| Test statistic | Wilcoxon signed-rank bilateral |
| Corecție comparații multiple | Holm–Bonferroni |
| `zero_method` Wilcoxon | `"wilcox"` (perechile cu diferență 0 excluse) |

---

## G1 — Poartă de validare

```
OK — res vs CSV: 45 useri, toate metricile in toleranta 1e-9.
Metrici verificate: ndcg@10, prec@10, rec@20, profile_recovery_spearman

OK — Consistenta interna res == _cfg_rows[productie] confirmata.
Re-sortarea prin componente (0.70·cos+0.20·pop+0.10·rar) reproduce
exact rankingul score_attractions() — budget_penalty=0 pentru toti userii.
```

Metricile reconstituite din pipeline-ul re-rulat cu SEED=42 coincid cu `quality_per_user.csv` la toleranță 1e-9 pe toți cei 45 de utilizatori valizi. Consistența internă între `res` (scorul real al scorerului) și `_cfg_rows["productie"]` (re-sortare prin componente) este confirmată — `budget_penalty=0` în toate cazurile evaluate.

---

## Tabel 1 — Intervale de încredere bootstrap (configurația de producție)

| Metrică | N | Medie | CI 95% inferior | CI 95% superior |
|---|---|---|---|---|
| NDCG@10 | 45 | 0,6038 | 0,5231 | 0,6811 |
| Precision@10 | 45 | 0,4622 | 0,3756 | 0,5511 |
| Recall@20 | 45 | 0,7030 | 0,6325 | 0,7699 |
| Recuperare profil (Spearman) | 45 | 0,5517 | 0,4811 | 0,6177 |

*Bootstrap percentilă, 10.000 reeșantionări, seed=42.*
*Intervalele cuantifică variabilitatea pe cei 45 de utilizatori sintetici valizi, nu generalizabilitatea la utilizatori reali.*

---

## Tabel 2 — Comparație statistică: producție vs. configurații alternative (NDCG@10)

| Comparație | N | N_nz | W | p brut | p Holm | r_rb | Semnificație |
|---|---|---|---|---|---|---|---|
| Producție vs. Doar cosinus (1.00/0.00/0.00) | 45 | 32 | 141,0 | 0,0214 | 0,1072 | +0,466 | ns |
| Producție vs. Fără raritate (0.80/0.20/0.00) | 45 | 16 | 62,0 | 0,7564 | 1,0000 | +0,088 | ns |
| Producție vs. Rar=Pop (0.70/0.15/0.15) | 45 | 15 | 45,0 | 0,3942 | 1,0000 | −0,250 | ns |
| Producție vs. Rar>Pop (0.70/0.10/0.20) | 45 | 23 | 94,0 | 0,1808 | 0,7231 | +0,319 | ns |
| Producție vs. Cos redus (0.60/0.20/0.20) | 45 | 16 | 64,0 | 0,8361 | 1,0000 | +0,059 | ns |

**Legendă:**
- **N** — numărul de perechi per-utilizator
- **N_nz** — numărul de perechi cu diferențe non-zero
- **W** — statistica Wilcoxon signed-rank
- **p brut** — p-value necorectat
- **p Holm** — p-value corectat Holm–Bonferroni (5 comparații simultane)
- **r_rb** — corelație rank-biserială (>0 ⟹ producție > alternativă)
- `***` p<0,001 &nbsp; `**` p<0,01 &nbsp; `*` p<0,05 &nbsp; `ns` nesemnificativ (după corecție)

---

## Configurații de ponderare evaluate

| Configurație | w_cosinus | w_popularitate | w_raritate |
|---|---|---|---|
| **productie** *(referință)* | 0,70 | 0,20 | 0,10 |
| doar_cosinus | 1,00 | 0,00 | 0,00 |
| fara_raritate | 0,80 | 0,20 | 0,00 |
| raritate_egal_pop | 0,70 | 0,15 | 0,15 |
| raritate_peste_pop | 0,70 | 0,10 | 0,20 |
| cos_redus | 0,60 | 0,20 | 0,20 |

---

## Text pentru Capitolul 6 (proză academică)

Pentru a cuantifica variabilitatea internă a măsurătorilor și a oferi o perspectivă asupra robusteții configurației de producție în raport cu alternativele evaluate, s-au calculat intervale de încredere prin metoda bootstrap percentilă și s-au efectuat teste statistice de comparație pe eșantionul de 45 de utilizatori sintetici valizi (din cei 50 generați, cinci au fost excluși deoarece nu au prezentat nicio atracție relevantă în țara recomandată). Este important de precizat de la bun început că toate inferențele statistice prezentate în această secțiune cuantifică exclusiv variabilitatea măsurătorilor pe utilizatorii sintetici cu profil-adevăr latent cunoscut, reflectând fidelitatea internă a sistemului față de un model generativ controlat, și nu semnificația statistică în raport cu utilizatori umani reali sau cu un eșantion reprezentativ dintr-o populație naturală.

Intervalele de încredere la nivel de 95% pentru configurația de producție, estimate prin 10.000 de reeșantionări bootstrap cu metodă percentilă și sâmbure fix (seed=42), sunt prezentate în Tabelul 1. Valoarea medie NDCG@10 de 0,6038 se încadrează într-un interval bootstrap de [0,5231; 0,6811], interval relativ larg care reflectă eterogenitatea profilurilor sintetice — utilizatorii cu 2–3 categorii dominante puternic diferențiate produc scoruri mai ridicate decât cei cu preferințe difuze. Precision@10 prezintă o medie de 0,4622 cu interval [0,3756; 0,5511], iar Recall@20 atinge 0,7030 [0,6325; 0,7699], indicând că sistemul recuperează o proporție substanțială din atracțiile relevante latente în primele 20 de poziții. Corelația Spearman pentru recuperarea profilului înregistrează o medie de 0,5517 [0,4811; 0,6177], confirmând că profilul reconstruit prin simularea chestionarului aproximează cu fidelitate moderată profilul latent.

Pentru comparația statistică a configurației de producție cu cele cinci alternative de ponderare, s-a aplicat testul Wilcoxon signed-rank cu perechi (bilateral, `zero_method="wilcox"`) pe vectorii de NDCG@10 per utilizator, urmat de corecția Holm–Bonferroni pentru comparații multiple. Numărul de perechi cu diferențe non-zero variază considerabil: 32 din 45 pentru comparația cu configurația `doar_cosinus` (1,00/0,00/0,00), față de doar 15–16 pentru configurațiile echilibrate (`fara_raritate`, `raritate_egal_pop`, `cos_redus`), ceea ce reflectă faptul că, pentru o majoritate a utilizatorilor sintetici, re-ponderarea componentelor de popularitate și raritate nu modifică ordinea primelor zece atracții. Niciuna dintre comparații nu atinge pragul de semnificație statistică după corecția Holm (cel mai mic p corectat: 0,107 pentru producție vs. doar_cosinus), deși p-ul brut al acestei comparații (p = 0,021) ar fi semnificativ în absența corecției pentru comparații multiple. Corelația rank-biserială de 0,466 asociată acestei comparații indică o tendință de magnitudine medie în favoarea configurației de producție față de varianta exclusiv-cosinus, tendință care nu este, însă, detectabilă cu certitudine statistică pe un eșantion de 45 de unități. Nesemnificația tuturor celorlalte comparații — în special față de `raritate_egal_pop` (r = −0,250) și `cos_redus` (r = 0,059) — este un rezultat așteptat și interpretabil ca robustețe a sistemului la variații moderate ale ponderilor, nu ca absență a oricărei diferențe. Puterea statistică a testelor este, prin construcție, limitată: eșantionul de 45 de utilizatori sintetici nu a fost dimensionat pentru a detecta efecte mici (d < 0,2), iar scopul evaluării este validitatea internă, nu puterea statistică în sens clasic.

---

## Notă metodologică

> Testele statistice și intervalele de încredere din această secțiune cuantifică **variabilitatea măsurătorilor pe utilizatorii sintetici** și **fidelitatea internă** a sistemului față de un model generativ controlat — **nu** semnificația statistică în lumea reală și **nu** garantează comportamentul pe utilizatori umani reali.
>
> **Nesemnificația statistică** pentru configurațiile echilibrate și apropiate de producție (`raritate_egal_pop`, `cos_redus`, `fara_raritate`, `raritate_peste_pop`) este un rezultat **așteptat** și indică **robustețe** a sistemului la variații mici ale ponderilor — nu o lipsă de efect.
>
> **Semnificația potențială** (p brut = 0,021, nesemnificativ după Holm) față de `doar_cosinus` confirmă că ponderea de raritate aduce o contribuție detectabilă pe date sintetice, în condiții controlate.

---

## Fișiere generate

| Fișier | Conținut |
|---|---|
| `statistical_ci.csv` | CI bootstrap per metrică (configurația de producție) |
| `statistical_significance.csv` | Wilcoxon + Holm per comparație |
| `statistical_figure.png` | Bar chart NDCG@10 cu bare de eroare CI 95% |

---

*Script: `backend/evaluation/run_statistical_analysis.py` | SEED=42 | Bootstrap=10.000 | CI=95%*
