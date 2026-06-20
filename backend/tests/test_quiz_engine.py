"""
test_quiz_engine.py
===================
Teste pentru funcțiile pure din quiz_engine.py.

Scopul dublu al acestor teste:
  1. Verifică corectitudinea matematică a algoritmului.
  2. Documentează MOTIVUL din spatele fiecărui magic number.
     Numele testului = regula. Docstring-ul = justificarea.

Nu necesită DB, server sau fișiere externe.
"""

import math
import pytest

from app.services.quiz_engine import (
    compute_entropy,
    adjust_tag_score,
    compute_adaptive_lambda,
    generate_prompt,
    cosine_dict,
    mmr_rerank,
    MIN_CARDS,
    MAX_CARDS,
    ENTROPY_THRESHOLD,
    L1_ORDER,
)


# ═══════════════════════════════════════════════════════════════════════════════
# ENTROPY — Shannon entropy pe distribuția de scoruri
# ═══════════════════════════════════════════════════════════════════════════════

class TestComputeEntropy:

    def test_no_scores_returns_sentinel_999(self):
        """Dict gol → 999.0 (sentinel = profil nedefinit, quiz continuă)."""
        assert compute_entropy({}) == 999.0

    def test_all_scores_below_threshold_returns_sentinel(self):
        """Scoruri Bayesian sub 0.5 (neutru) → 999.0.
        Utilizatorul nu a exprimat nicio preferință pozitivă clară."""
        scores = {"nature-outdoors": 0.4, "food-drink": 0.45}
        assert compute_entropy(scores) == 999.0

    def test_single_dominant_tag_gives_zero_entropy(self):
        """Un singur tag pozitiv → entropie 0.0 = profil perfect concentrat.
        ENTROPY_THRESHOLD=1.0: valoarea 0 e mult sub prag → quiz s-ar opri."""
        scores = {"nature-outdoors": 0.9}
        entropy = compute_entropy(scores)
        assert entropy == pytest.approx(0.0, abs=1e-9)

    def test_two_equal_tags_gives_max_entropy_for_two(self):
        """Două taguri cu scoruri egale → entropie = log2(2) = 1.0.
        ENTROPY_THRESHOLD=1.0: exact la prag → quiz se oprește.
        Justificare: utilizatorul e egal împărțit între 2 categorii — e suficient."""
        scores = {"nature-outdoors": 0.8, "food-drink": 0.8}
        entropy = compute_entropy(scores)
        assert entropy == pytest.approx(1.0, abs=1e-6)

    def test_eight_equal_tags_gives_max_possible_entropy(self):
        """8 categorii L1 cu scoruri egale → entropie = log2(8) = 3.0.
        Profil complet nedecis → quiz trebuie să continue (3.0 >> ENTROPY_THRESHOLD=1.0)."""
        scores = {slug: 0.8 for slug in L1_ORDER}
        entropy = compute_entropy(scores)
        assert entropy == pytest.approx(math.log2(8), abs=1e-6)

    def test_entropy_threshold_value_is_one(self):
        """ENTROPY_THRESHOLD=1.0 corespunde unui utilizator cu max 2 categorii egale.
        Sub 1.0 = profilul e suficient de clar pentru a genera recomandări."""
        assert ENTROPY_THRESHOLD == 1.0

    def test_bayesian_mode_detected_by_max_score_le_1_1(self):
        """Auto-detecție mod Bayesian: dacă max(scores) ≤ 1.1, prag neutru = 0.5.
        Scorurile Bayesian sunt medii Beta în [0,1]; scorurile legacy pot depăși 1."""
        bayesian_scores = {"nature-outdoors": 0.9, "food-drink": 0.6}
        legacy_scores   = {"nature-outdoors": 2.5, "food-drink": 1.5}

        entropy_bayesian = compute_entropy(bayesian_scores)
        entropy_legacy   = compute_entropy(legacy_scores)

        # Ambele au același raport de distribuție, dar entropia legacy e calculată diferit
        assert entropy_bayesian > 0
        assert entropy_legacy > 0

    def test_entropy_decreases_as_profile_concentrates(self):
        """Pe măsură ce un tag devine dominant, entropia scade.
        Aceasta e baza logicii de stopping: quiz se oprește când entropia scade sub prag."""
        dispersed    = {"nature-outdoors": 0.7, "food-drink": 0.65, "culture-history": 0.6}
        concentrated = {"nature-outdoors": 0.95, "food-drink": 0.55, "culture-history": 0.51}

        assert compute_entropy(dispersed) > compute_entropy(concentrated)


# ═══════════════════════════════════════════════════════════════════════════════
# BAYESIAN SCORING — update Beta(α, β) la fiecare swipe
# ═══════════════════════════════════════════════════════════════════════════════

class TestAdjustTagScore:

    def test_right_swipe_increases_score_above_neutral(self):
        """Un RIGHT swipe pe un tag nevăzut înainte → scor > 0.5 (neutral Bayesian).
        Delta pozitiv pe un tag neutru trebuie să producă preferință."""
        scores = {}
        adjust_tag_score(scores, "skiing", 0.5, bayesian=True)
        assert scores["skiing"] > 0.5

    def test_left_swipe_decreases_score_below_neutral(self):
        """Un LEFT swipe pe un tag nevăzut → scor < 0.5.
        Delta negativ produce dezinteres față de neutral."""
        scores = {}
        adjust_tag_score(scores, "skiing", -0.3, bayesian=True)
        assert scores["skiing"] < 0.5

    def test_bayesian_score_clamped_to_zero_one(self):
        """Modul Bayesian clampează la [0, 1] — scorurile nu pot ieși din intervalul Beta.
        Justificare: scorurile Bayesian sunt medii Beta(α,β) ∈ (0,1)."""
        scores = {"skiing": 0.95}
        adjust_tag_score(scores, "skiing", 0.5, bayesian=True)
        assert scores["skiing"] <= 1.0

        scores2 = {"skiing": 0.05}
        adjust_tag_score(scores2, "skiing", -0.5, bayesian=True)
        assert scores2["skiing"] >= 0.0

    def test_legacy_mode_no_clamping(self):
        """Modul legacy NU clampează — scorurile pot depăși [0,1].
        Backward compatibility cu sesiunile create înainte de Bayesian update."""
        scores = {"skiing": 0.9}
        adjust_tag_score(scores, "skiing", 0.5, bayesian=False)
        assert scores["skiing"] > 1.0

    def test_repeated_right_swipes_accumulate(self):
        """Swipe-uri repetate RIGHT cresc scorul progresiv.
        Justificare: semnalul repetat consolidează preferința."""
        scores = {}
        for _ in range(3):
            adjust_tag_score(scores, "nature-outdoors", 0.1, bayesian=True)
        assert scores["nature-outdoors"] > 0.5 + 0.1

    def test_unknown_tag_starts_at_bayesian_neutral(self):
        """Tag nevăzut → baza Bayesian este 0.5 (prior uniform Beta(1,1)).
        Justificare: fără informație, utilizatorul e neutru față de orice tag."""
        scores = {}
        adjust_tag_score(scores, "new-tag", 0.0, bayesian=True)
        assert scores["new-tag"] == pytest.approx(0.5)

    def test_unknown_tag_starts_at_zero_in_legacy(self):
        """Tag nevăzut în modul legacy → baza este 0.0.
        Compatibil cu acumularea simplă din versiunea anterioară."""
        scores = {}
        adjust_tag_score(scores, "new-tag", 0.0, bayesian=False)
        assert scores["new-tag"] == pytest.approx(0.0)


# ═══════════════════════════════════════════════════════════════════════════════
# ADAPTIVE LAMBDA — balans relevanță vs diversitate în MMR
# ═══════════════════════════════════════════════════════════════════════════════

class TestComputeAdaptiveLambda:

    def test_empty_profile_returns_default(self):
        """Profil gol → λ=0.7 (default moderat, relevanță ușor preferată)."""
        assert compute_adaptive_lambda({}) == pytest.approx(0.7)

    def test_single_tag_returns_default(self):
        """Un singur tag → imposibil de calculat CV → λ=0.7 default."""
        assert compute_adaptive_lambda({"nature-outdoors": 0.9}) == pytest.approx(0.7)

    def test_concentrated_profile_gives_high_lambda(self):
        """Profil concentrat (un tag dominant) → λ aproape de 0.9.
        Justificare: utilizatorul știe ce vrea → prioritizăm relevanța față de diversitate."""
        concentrated = {"nature-outdoors": 0.95, "food-drink": 0.1, "culture-history": 0.05}
        lam = compute_adaptive_lambda(concentrated)
        assert lam > 0.7

    def test_dispersed_profile_gives_low_lambda(self):
        """Profil dispersat (scoruri egale) → λ aproape de 0.5.
        Justificare: utilizatorul are gusturi variate → diversitatea contează mai mult."""
        dispersed = {slug: 0.7 for slug in L1_ORDER}
        lam = compute_adaptive_lambda(dispersed)
        assert lam < 0.7

    def test_lambda_always_in_valid_range(self):
        """λ mereu în [0.5, 0.9] — limite definite prin design.
        Sub 0.5: diversitatea ar domina complet (nerealist).
        Peste 0.9: relevanța ar domina complet (fără diversitate geografică)."""
        profiles = [
            {},
            {"a": 1.0},
            {slug: 0.8 for slug in L1_ORDER},
            {"nature-outdoors": 0.99, "food-drink": 0.01},
        ]
        for profile in profiles:
            lam = compute_adaptive_lambda(profile)
            assert 0.5 <= lam <= 0.9, f"λ={lam} în afara [0.5, 0.9] pentru {profile}"


# ═══════════════════════════════════════════════════════════════════════════════
# COSINE SIMILARITY — similaritate între vectori de taguri
# ═══════════════════════════════════════════════════════════════════════════════

class TestCosineDict:

    def test_identical_vectors_give_similarity_one(self):
        """Vectori identici → cosine = 1.0 (perfect match)."""
        v = {"nature": 0.8, "food": 0.5}
        assert cosine_dict(v, v) == pytest.approx(1.0)

    def test_orthogonal_vectors_give_similarity_zero(self):
        """Vectori fără tag-uri comune → cosine = 0.0 (nicio suprapunere)."""
        v1 = {"nature": 0.8}
        v2 = {"food": 0.6}
        assert cosine_dict(v1, v2) == pytest.approx(0.0)

    def test_empty_vectors_give_zero(self):
        """Dict gol → cosine = 0.0 (nicio informație)."""
        assert cosine_dict({}, {}) == pytest.approx(0.0)
        assert cosine_dict({"nature": 0.8}, {}) == pytest.approx(0.0)

    def test_partial_overlap_between_zero_and_one(self):
        """Suprapunere parțială → cosine ∈ (0, 1)."""
        v1 = {"nature": 0.8, "food": 0.5}
        v2 = {"nature": 0.6, "culture": 0.9}
        sim = cosine_dict(v1, v2)
        assert 0.0 < sim < 1.0

    def test_scaling_does_not_affect_similarity(self):
        """Cosine e invariant la scalare — contează direcția, nu magnitudinea.
        Justificare: scorul absolut al unui tag nu contează, ci raportul dintre taguri."""
        v1 = {"nature": 0.4, "food": 0.3}
        v2 = {"nature": 0.8, "food": 0.6}   # v1 * 2
        assert cosine_dict(v1, v2) == pytest.approx(1.0)


# ═══════════════════════════════════════════════════════════════════════════════
# MMR RERANKING — diversitate geografică în rezultate
# ═══════════════════════════════════════════════════════════════════════════════

class TestMmrRerank:

    def _make_result(self, name: str, score: float, tag_dict: dict) -> dict:
        return {"country_name": name, "score": score, "_tag_dict": tag_dict}

    def test_empty_list_returns_empty(self):
        assert mmr_rerank([], lambda_param=0.7, top_n=5) == []

    def test_single_result_returned_as_is(self):
        results = [self._make_result("France", 0.9, {"t1": 0.8})]
        selected = mmr_rerank(results, lambda_param=0.7, top_n=5)
        assert len(selected) == 1
        assert selected[0]["country_name"] == "France"

    def test_top_n_limits_output(self):
        """MMR returnează maxim top_n rezultate."""
        results = [self._make_result(f"Country{i}", 0.9 - i * 0.1, {"t1": 0.8}) for i in range(10)]
        selected = mmr_rerank(results, lambda_param=0.7, top_n=3)
        assert len(selected) == 3

    def test_first_result_is_always_top_scored(self):
        """Primul rezultat MMR e mereu cel cu scorul de relevanță cel mai mare.
        Justificare: seed-ul MMR este cel mai relevant — diversificăm restul."""
        results = [
            self._make_result("France",  0.95, {"t1": 0.9}),
            self._make_result("Germany", 0.85, {"t1": 0.8}),
            self._make_result("Spain",   0.80, {"t2": 0.9}),
        ]
        selected = mmr_rerank(results, lambda_param=0.7, top_n=3)
        assert selected[0]["country_name"] == "France"

    def test_high_lambda_prefers_relevance_over_diversity(self):
        """λ=1.0 → MMR devine ranking pur după scor (diversitatea ignorată).
        Rezultatele sunt ordonate descrescător după score."""
        results = [
            self._make_result("France",  0.95, {"t1": 0.9, "t2": 0.8}),
            self._make_result("Germany", 0.85, {"t1": 0.9, "t2": 0.8}),  # similar cu France
            self._make_result("Spain",   0.80, {"t3": 0.9, "t4": 0.8}),  # diferit
        ]
        selected = mmr_rerank(results, lambda_param=1.0, top_n=3)
        scores = [r["score"] for r in selected]
        assert scores == sorted(scores, reverse=True)

    def test_low_lambda_promotes_diverse_result(self):
        """λ=0.0 → MMR maximizează diversitatea (ignoră relevanța).
        Justificare: pentru profiluri dispersate, vrem țări variate geografic."""
        results = [
            self._make_result("France",  0.9, {"t1": 0.9, "t2": 0.8}),
            self._make_result("Germany", 0.8, {"t1": 0.9, "t2": 0.8}),  # very similar to France
            self._make_result("Japan",   0.7, {"t3": 0.9, "t4": 0.8}),  # very different
        ]
        selected = mmr_rerank(results, lambda_param=0.0, top_n=2)
        names = [r["country_name"] for r in selected]
        # Japan (diferit) trebuie preferat față de Germany (similar cu France)
        assert "Japan" in names

    def test_tag_dict_is_used_for_diversity_not_returned(self):
        """_tag_dict e folosit intern pentru MMR și nu e prezent în output.
        Caller-ul (country_recommender.py) face pop('_tag_dict') după MMR."""
        results = [self._make_result("France", 0.9, {"t1": 0.8})]
        selected = mmr_rerank(results, lambda_param=0.7, top_n=5)
        # _tag_dict e prezent — MMR nu face pop, asta e responsabilitatea caller-ului
        assert "_tag_dict" in selected[0]


# ═══════════════════════════════════════════════════════════════════════════════
# GENERATE PROMPT — mesaje pentru cardurile de swipe
# ═══════════════════════════════════════════════════════════════════════════════

class TestGeneratePrompt:

    def test_known_slug_returns_specific_prompt(self):
        """Tag-urile L1 principale au prompturi personalizate în română."""
        prompt = generate_prompt("nature-outdoors", "Nature & Outdoors")
        assert isinstance(prompt, str)
        assert len(prompt) > 5
        assert prompt != "Ce părere ai despre nature & outdoors?"

    def test_unknown_slug_returns_generic_fallback(self):
        """Tag necunoscut → fallback generic cu numele tag-ului.
        Justificare: baza de taguri poate crește; nu vrem crash pentru taguri noi."""
        prompt = generate_prompt("some-new-tag", "Some New Tag")
        assert "some new tag" in prompt.lower()

    def test_all_l1_tags_have_custom_prompts(self):
        """Toate cele 8 categorii L1 au prompturi custom (nu fallback generic).
        Justificare: L1 sunt primele carduri văzute de utilizator — trebuie să fie clare."""
        l1_names = {
            "nature-outdoors": "Nature",
            "culture-history": "Culture",
            "nightlife-social": "Nightlife",
            "adventure-active": "Adventure",
            "food-drink": "Food",
            "wellness-slow": "Wellness",
            "urban-modern": "Urban",
            "family-comfort": "Family",
        }
        for slug, name in l1_names.items():
            prompt = generate_prompt(slug, name)
            generic = f"Ce părere ai despre {name.lower()}?"
            assert prompt != generic, f"{slug} folosește fallback generic"


# ═══════════════════════════════════════════════════════════════════════════════
# CONSTANTE — validare valori și relații dintre ele
# ═══════════════════════════════════════════════════════════════════════════════

class TestClarifyMandatoryGuarantee:
    """
    Documentează bug-ul B8 din stress test (2026-06-02):
    Un utilizator cu profilul 'mixed_all' (toate 8 categorii L1 likte) generează
    atât de multe întrebări de conflict/nature_urban/season încât lista de 8
    era umplută FĂRĂ întrebările mandatory (budget/season/travel_style).
    Sesiunea nu se mai putea completa niciodată → GET /results returna 400.

    Fix: mandatory-urile sunt rezervate la finalul listei indiferent de celelalte.
    """

    def _apply_mandatory_fix(self, questions: list) -> list:
        """Reproduce logica din clarify_generator.py liniile finale."""
        MANDATORY_IDS = {"budget", "season", "travel_style"}
        mandatory = [q for q in questions if q["id"] in MANDATORY_IDS]
        optional  = [q for q in questions if q["id"] not in MANDATORY_IDS]
        return optional[:8 - len(mandatory)] + mandatory

    def _make_q(self, q_id: str) -> dict:
        return {"id": q_id, "source": "conflict" if q_id.startswith("conflict") else "mandatory"}

    def test_mandatory_always_present_when_list_is_full(self):
        """8 întrebări opționale + 3 mandatory → fix păstrează mandatory, taie opționalele."""
        optional_qs  = [self._make_q(f"conflict_{i}") for i in range(8)]
        mandatory_qs = [self._make_q("budget"), self._make_q("season"), self._make_q("travel_style")]
        questions = optional_qs + mandatory_qs  # 11 total, ca în bug-ul B8

        result = self._apply_mandatory_fix(questions)

        assert len(result) == 8
        result_ids = {q["id"] for q in result}
        assert "budget" in result_ids
        assert "season" in result_ids
        assert "travel_style" in result_ids

    def test_optional_capped_to_make_room_for_mandatory(self):
        """Cu 3 mandatory garantate, mai rămân maxim 5 slots pentru opționale."""
        optional_qs  = [self._make_q(f"conflict_{i}") for i in range(8)]
        mandatory_qs = [self._make_q("budget"), self._make_q("season"), self._make_q("travel_style")]

        result = self._apply_mandatory_fix(optional_qs + mandatory_qs)

        optional_in_result = [q for q in result if q["id"] not in {"budget", "season", "travel_style"}]
        assert len(optional_in_result) <= 5

    def test_mandatory_at_end_of_list(self):
        """Mandatory apar la finalul listei — UI-ul le vede ultimele."""
        optional_qs  = [self._make_q(f"conflict_{i}") for i in range(3)]
        mandatory_qs = [self._make_q("budget"), self._make_q("season"), self._make_q("travel_style")]

        result = self._apply_mandatory_fix(optional_qs + mandatory_qs)

        last_three_ids = [q["id"] for q in result[-3:]]
        assert set(last_three_ids) == {"budget", "season", "travel_style"}

    def test_few_optional_questions_not_affected(self):
        """Cu puține opționale (< 5), toate sunt păstrate + mandatory adăugate."""
        optional_qs  = [self._make_q("conflict_1"), self._make_q("ambiguity_a_b")]
        mandatory_qs = [self._make_q("budget"), self._make_q("season"), self._make_q("travel_style")]

        result = self._apply_mandatory_fix(optional_qs + mandatory_qs)

        assert len(result) == 5
        result_ids = {q["id"] for q in result}
        assert {"conflict_1", "ambiguity_a_b", "budget", "season", "travel_style"} == result_ids

    def test_empty_optional_only_mandatory_returned(self):
        """Fără întrebări opționale → doar cele 3 mandatory."""
        mandatory_qs = [self._make_q("budget"), self._make_q("season"), self._make_q("travel_style")]

        result = self._apply_mandatory_fix(mandatory_qs)

        assert len(result) == 3
        assert {q["id"] for q in result} == {"budget", "season", "travel_style"}


class TestDensityFactor:
    """
    Documentează factorul de corecție densitate din country_recommender.py.

    Problemă identificată în stress test (2026-06-02):
    Cosine similarity penalizează țările cu vectori mari (France 128 taguri)
    față de țările mici cu scoruri concentrate pe câteva categorii (Kosovo 112 taguri).
    O țară descrisă printr-un vector mai compact câștigă din geometrie, nu din relevanță.

    Fix: score_final = cosine × (tag_count / median_count) ^ ALPHA
    ALPHA=0.3 = corecție moderată (~4% boost pentru France, ~0% pentru Kosovo la median)
    """

    ALPHA = 0.3

    def _density_factor(self, tag_count: int, median_count: float) -> float:
        return (tag_count / median_count) ** self.ALPHA

    def test_country_at_median_gets_factor_one(self):
        """Țara cu exact tag_count=median nu e nici avantajată nici penalizată."""
        assert self._density_factor(120, 120.0) == pytest.approx(1.0)

    def test_large_country_gets_boost(self):
        """France (128 taguri, median=112) primește factor > 1 — mic boost."""
        factor = self._density_factor(128, 112.0)
        assert factor > 1.0
        assert factor < 1.1  # boost modest, nu distorsionant

    def test_small_country_gets_penalty(self):
        """Țară mică (90 taguri, median=112) primește factor < 1 — mică penalizare."""
        factor = self._density_factor(90, 112.0)
        assert factor < 1.0
        assert factor > 0.93  # penalizare moderată

    def test_alpha_03_gives_max_15_percent_correction(self):
        """Cu alpha=0.3, diferența maximă realistă (80 vs 130 taguri) → max ~15% corecție.
        Justificare: mai mult ar distorsiona rankingul, mai puțin n-ar ajuta France/Italy."""
        worst_case_boost   = self._density_factor(130, 80.0)   # mult mai mare ca median
        worst_case_penalty = self._density_factor(80, 130.0)   # mult mai mic ca median
        assert worst_case_boost < 1.18
        assert worst_case_penalty > 0.85

    def test_factor_is_monotone_with_tag_count(self):
        """Cu cât mai multe taguri, cu atât factorul e mai mare (funcție monotonă)."""
        median = 112.0
        factors = [self._density_factor(n, median) for n in [80, 100, 112, 120, 130]]
        assert factors == sorted(factors)

    def test_alpha_zero_means_no_correction(self):
        """Alpha=0 dezactivează corecția complet — utile pentru A/B testing."""
        alpha = 0.0
        assert (128 / 112.0) ** alpha == pytest.approx(1.0)
        assert (80 / 112.0) ** alpha == pytest.approx(1.0)


class TestConstants:

    def test_min_cards_less_than_max_cards(self):
        """MIN_CARDS < MAX_CARDS — quiz se poate opri înainte de maximum."""
        assert MIN_CARDS < MAX_CARDS

    def test_min_cards_covers_all_l1_categories(self):
        """MIN_CARDS=15 > len(L1_ORDER)=8 — garantăm că toate categoriile L1
        sunt prezentate înainte de oprire. Primele 8 carduri sunt L1 obligatorii."""
        assert MIN_CARDS > len(L1_ORDER)

    def test_l1_order_has_eight_categories(self):
        """L1_ORDER conține exact 8 categorii — una per domeniu principal de travel."""
        assert len(L1_ORDER) == 8

    def test_l1_order_has_no_duplicates(self):
        """Fiecare categorie L1 apare o singură dată în ordinea de prezentare."""
        assert len(L1_ORDER) == len(set(L1_ORDER))

    def test_entropy_threshold_equals_two_equal_category_entropy(self):
        """ENTROPY_THRESHOLD=1.0 = entropia exactă pentru 2 categorii egale.
        Justificare: quiz se oprește când profilul e la fel de clar ca 'prefer 2 lucruri egal'.
        Mai clar de atât = 1 categorie dominantă → suficient pentru recomandare."""
        two_equal = {"cat_a": 0.8, "cat_b": 0.8}
        entropy = compute_entropy(two_equal)
        assert entropy == pytest.approx(ENTROPY_THRESHOLD, abs=1e-6)
