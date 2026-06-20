import pytest

from app.services.clarify_generator import (
    MAX_CLARIFY_QUESTIONS,
    MAX_OPTIONAL_QUESTIONS,
    MANDATORY_IDS,
    _optional_priority,
    _score_tags,
    preference_strength,
)


def test_bayesian_left_score_has_no_positive_preference():
    assert preference_strength(0.4, bayesian=True) == 0.0


def test_bayesian_neutral_score_has_no_positive_preference():
    assert preference_strength(0.5, bayesian=True) == 0.0


def test_bayesian_right_score_counts_only_excess_above_neutral():
    assert preference_strength(0.75, bayesian=True) == pytest.approx(0.25)


def test_legacy_positive_score_keeps_original_meaning():
    assert preference_strength(1.8, bayesian=False) == 1.8


def test_score_tags_ignores_bayesian_dislikes():
    tag_scores = {
        "nightlife-social": 0.4,
        "urban-modern": 0.5,
        "bar-scene": 0.7,
    }
    assert _score_tags(tag_scores, {"nightlife-social", "urban-modern", "bar-scene"}, True) == pytest.approx(0.2)


def test_clarify_question_budget_reserves_three_mandatory_slots():
    assert len(MANDATORY_IDS) == 3
    assert MAX_CLARIFY_QUESTIONS == 6
    assert MAX_OPTIONAL_QUESTIONS == 3


def test_optional_question_priority_prefers_conflicts_over_gaps():
    conflict = {"source": "conflict"}
    gap = {"source": "gap"}
    assert _optional_priority(conflict) < _optional_priority(gap)
