"""
Logica pură a quiz-ului — fără acces la DB, fără HTTP.
Toate funcțiile sunt testabile izolat.
"""

import math
import random

# ─── CONSTANTS ────────────────────────────────────────────────────────────────

MIN_CARDS = 15
MAX_CARDS = 20
ENTROPY_THRESHOLD = 1.0
RIGHT_WEIGHT = 1.0
LEFT_WEIGHT = -0.4   # penalizare asimetrică — dislike contează mai puțin decât like
# Minim de carduri frunza L3 vazute inainte de a permite oprirea pe entropie.
# Cu 8 carduri L1 in Phase 1 si MAX_CARDS=20, 7 frunze = carduri 9-15 (= MIN_CARDS).
MIN_L3_BEFORE_STOP = 7

L1_ORDER = [
    "nature-outdoors",
    "culture-history",
    "nightlife-social",
    "adventure-active",
    "food-drink",
    "wellness-slow",
    "urban-modern",
    "family-comfort",
]

MANDATORY_QUESTIONS = [
    {
        "id": "budget",
        "question": "Care este bugetul tău mediu pe zi?",
        "type": "single",
        "options": [
            {"value": "budget", "label": "Economic (sub 50€/zi)"},
            {"value": "mid",    "label": "Mediu (50-150€/zi)"},
            {"value": "luxury", "label": "Luxury (peste 150€/zi)"},
        ],
    },
    {
        "id": "season",
        "question": "În ce perioadă preferi să călătorești?",
        "type": "single",
        "options": [
            {"value": "spring", "label": "Primăvară"},
            {"value": "summer", "label": "Vară"},
            {"value": "autumn", "label": "Toamnă"},
            {"value": "winter", "label": "Iarnă"},
            {"value": "any",    "label": "Orice perioadă"},
        ],
    },
    {
        "id": "travel_style",
        "question": "Cu cine călătorești de obicei?",
        "type": "single",
        "options": [
            {"value": "solo",   "label": "Solo"},
            {"value": "couple", "label": "În cuplu"},
            {"value": "family", "label": "Cu familia (copii)"},
            {"value": "group",  "label": "Cu prietenii"},
        ],
    },
]

# ─── ENTROPY ──────────────────────────────────────────────────────────────────

def compute_entropy(tag_scores: dict) -> float:
    """Entropie Shannon pe distribuția scorurilor pozitive.
    Auto-detectează modul Bayesian (toate valorile ≤1.1) și folosește 0.5 ca prag neutru.
    """
    values = list(tag_scores.values()) if tag_scores else []
    threshold = 0.5 if (values and max(values) <= 1.1) else 0.0
    positive = {k: v - threshold for k, v in tag_scores.items() if v > threshold}
    if not positive:
        return 999.0
    total = sum(positive.values())
    if total == 0:
        return 999.0
    probs = [v / total for v in positive.values()]
    return -sum(p * math.log2(p) for p in probs if p > 0)


# ─── TAG SCORING ──────────────────────────────────────────────────────────────

def adjust_tag_score(tag_scores: dict, slug: str, delta: float, bayesian: bool) -> None:
    """Aplică un delta la tag_scores in-place.
    Bayesian: baza neutră 0.5, rezultat clamped la [0, 1].
    Legacy: baza 0.0, fără clamping.
    """
    base = tag_scores.get(slug, 0.5 if bayesian else 0.0)
    new_val = base + delta
    tag_scores[slug] = max(0.0, min(1.0, new_val)) if bayesian else new_val


def compute_adaptive_lambda(final_profile: dict) -> float:
    """λ adaptiv bazat pe concentrarea profilului (CV = std/mean).
    Profil concentrat (CV mare) → λ mare (relevance-first).
    Profil dispersat (CV mic)   → λ mic (diversity-first).
    """
    import numpy as np

    if not final_profile:
        return 0.7
    scores = list(final_profile.values())
    if len(scores) < 2:
        return 0.7
    std_dev = float(np.std(scores))
    mean_score = float(np.mean(scores))
    cv = std_dev / mean_score if mean_score > 0 else 0.0
    return max(0.5, min(0.9, 0.5 + 0.5 * min(cv / 0.8, 1.0)))


# ─── MMR HELPERS ──────────────────────────────────────────────────────────────

def cosine_dict(v1: dict, v2: dict) -> float:
    """Cosine similarity între două dicts {tag_id: score}."""
    keys = set(v1.keys()) | set(v2.keys())
    if not keys:
        return 0.0
    dot = sum(v1.get(k, 0.0) * v2.get(k, 0.0) for k in keys)
    mag1 = math.sqrt(sum(s * s for s in v1.values()))
    mag2 = math.sqrt(sum(s * s for s in v2.values()))
    if mag1 == 0.0 or mag2 == 0.0:
        return 0.0
    return dot / (mag1 * mag2)


def mmr_rerank(sorted_results: list, lambda_param: float, top_n: int) -> list:
    """Greedy MMR selection.
    MMR(C) = λ · relevance(C) − (1−λ) · max_sim(C, selected)
    Fiecare item trebuie să aibă cheia '_tag_dict'; este eliminată de caller.
    """
    if not sorted_results:
        return []

    remaining = list(sorted_results)
    selected = [remaining.pop(0)]

    while remaining and len(selected) < top_n:
        best_mmr, best_idx = -float("inf"), 0
        for i, candidate in enumerate(remaining):
            max_sim = max(
                cosine_dict(candidate["_tag_dict"], sel["_tag_dict"])
                for sel in selected
            )
            mmr = lambda_param * candidate["score"] - (1 - lambda_param) * max_sim
            if mmr > best_mmr:
                best_mmr, best_idx = mmr, i
        selected.append(remaining.pop(best_idx))

    return selected


# ─── CARD CONTENT ─────────────────────────────────────────────────────────────

_PROMPTS = {
    "nature-outdoors":      "Îți place să explorezi natura?",
    "culture-history":      "Te pasionează cultura și istoria?",
    "nightlife-social":     "Preferi serile animate și viața socială?",
    "adventure-active":     "Ești adeptul aventurii și sporturilor?",
    "food-drink":           "Gastronomia locală e prioritatea ta?",
    "wellness-slow":        "Cauți relaxare și wellness?",
    "urban-modern":         "Te atrage viața urbană modernă?",
    "family-comfort":       "Călătorești confortabil cu familia?",
    "hiking-trekking":      "Îți plac drumețiile montane?",
    "winter-nature":        "Te simți bine în zăpadă și iarnă?",
    "beach-water":          "Preferi plajele și activitățile nautice?",
    "techno-clubs":         "Iubești cluburile și muzica electronică?",
    "bar-scene":            "Preferi atmosfera de bar și cocktail-uri?",
    "live-entertainment":   "Te atrag spectacolele live?",
    "skiing":               "Schiezi sau faci snowboard?",
    "wine-vineyards":       "Ești pasionat de vinuri și degustări?",
    "michelin-restaurants": "Apreciezi fine dining-ul?",
    "street-food":          "Preferi mâncarea stradală autentică?",
    "ancient-ruins":        "Te fascinează ruinele antice?",
    "art-museums":          "Iubești muzee și galerii de artă?",
    "local-festivals":      "Îți plac festivalurile locale?",
    "yoga-retreats":        "Meditezi sau faci yoga în vacanță?",
    "cycling-biking":       "Explorezi destinațiile pe bicicletă?",
    "sailing":              "Visezi la o croazieră cu barca?",
}


def generate_prompt(tag_slug: str, tag_name: str) -> str:
    return _PROMPTS.get(tag_slug, f"Ce părere ai despre {tag_name.lower()}?")
