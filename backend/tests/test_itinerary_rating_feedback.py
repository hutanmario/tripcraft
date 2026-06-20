from types import SimpleNamespace

import pytest

from app.routers.itinerary import (
    _apply_pace_feedback,
    _apply_plan_rating_to_session,
    _plan_rating_signal,
)


class _EmptyQuery:
    def filter(self, *args, **kwargs):
        return self

    def all(self):
        return []


class _EmptyTagDb:
    def query(self, *args, **kwargs):
        return _EmptyQuery()


def _session(**overrides):
    data = {
        "tag_beliefs": {},
        "tag_scores": {},
        "final_profile": {},
        "pace_preference": None,
    }
    data.update(overrides)
    return SimpleNamespace(**data)


def test_rating_signal_clamps_positive_aspect_to_one():
    assert _plan_rating_signal(5, ["matches_style"]) == pytest.approx(1.0)


def test_rating_signal_clamps_negative_aspect_to_minus_one():
    assert _plan_rating_signal(1, ["wrong_vibe"]) == pytest.approx(-1.0)


def test_neutral_rating_with_pacing_aspect_has_no_profile_signal():
    assert _plan_rating_signal(3, ["too_many_stops"]) == pytest.approx(0.0)


def test_positive_rating_increases_alpha_and_refreshes_profile():
    session = _session()

    updated = _apply_plan_rating_to_session(
        _EmptyTagDb(),
        session,
        {"hiking-trekking": 1.0, "museums": 0.5},
        rating=5,
        aspects=["matches_style"],
    )

    assert updated is True
    assert session.tag_beliefs["hiking-trekking"]["alpha"] == pytest.approx(1.25)
    assert session.tag_beliefs["hiking-trekking"]["beta"] == pytest.approx(1.0)
    assert session.tag_beliefs["museums"]["alpha"] == pytest.approx(1.125)
    assert session.tag_scores["hiking-trekking"] == pytest.approx(0.5556)
    assert session.final_profile["hiking-trekking"] == pytest.approx(1.0)
    assert 0 < session.final_profile["museums"] < 1


def test_negative_rating_increases_beta_and_removes_positive_profile():
    session = _session(
        tag_beliefs={"beach": {"alpha": 1.5, "beta": 1.0}},
        tag_scores={"beach": 0.6},
        final_profile={"beach": 1.0},
    )

    updated = _apply_plan_rating_to_session(
        _EmptyTagDb(),
        session,
        {"beach": 1.0},
        rating=1,
        aspects=["wrong_vibe"],
    )

    assert updated is True
    assert session.tag_beliefs["beach"]["alpha"] == pytest.approx(1.5)
    assert session.tag_beliefs["beach"]["beta"] == pytest.approx(1.25)
    assert session.tag_scores["beach"] == pytest.approx(0.5455)
    assert session.final_profile == {"beach": 1.0}


def test_rating_edit_applies_only_signal_delta():
    session = _session(tag_beliefs={"food": {"alpha": 1.25, "beta": 1.0}})

    updated = _apply_plan_rating_to_session(
        _EmptyTagDb(),
        session,
        {"food": 1.0},
        rating=1,
        aspects=["wrong_vibe"],
        previous_rating=5,
        previous_aspects=["matches_style"],
    )

    assert updated is True
    assert session.tag_beliefs["food"]["alpha"] == pytest.approx(1.25)
    assert session.tag_beliefs["food"]["beta"] == pytest.approx(1.5)
    assert session.tag_scores["food"] == pytest.approx(0.4545)
    assert session.final_profile == {}


def test_repeating_same_rating_does_not_double_learn():
    session = _session(tag_beliefs={"culture": {"alpha": 1.25, "beta": 1.0}})

    updated = _apply_plan_rating_to_session(
        _EmptyTagDb(),
        session,
        {"culture": 1.0},
        rating=5,
        aspects=["matches_style"],
        previous_rating=5,
        previous_aspects=["matches_style"],
    )

    assert updated is False
    assert session.tag_beliefs["culture"] == {"alpha": 1.25, "beta": 1.0}


def test_too_many_stops_sets_relaxed_pace_without_changing_profile_signal():
    session = _session()

    pace_updated = _apply_pace_feedback(session, 3, ["too_many_stops"])
    profile_updated = _apply_plan_rating_to_session(
        _EmptyTagDb(),
        session,
        {"architecture": 1.0},
        rating=3,
        aspects=["too_many_stops"],
    )

    assert pace_updated is True
    assert profile_updated is False
    assert session.pace_preference == "relaxed"
    assert session.tag_beliefs == {}


def test_removing_too_many_stops_resets_relaxed_pace_to_balanced_on_good_rating():
    session = _session(pace_preference="relaxed")

    updated = _apply_pace_feedback(
        session,
        rating=4,
        aspects=[],
        previous_aspects=["too_many_stops"],
    )

    assert updated is True
    assert session.pace_preference == "balanced"
