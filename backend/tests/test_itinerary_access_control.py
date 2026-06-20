from types import SimpleNamespace

from app.routers.itinerary import _can_access_plan


def test_owner_can_access_plan():
    plan = SimpleNamespace(user_id=7, group_trip_id=None)

    assert _can_access_plan(db=None, plan=plan, user_id=7) is True


def test_anonymous_plan_is_not_public():
    plan = SimpleNamespace(user_id=None, group_trip_id=None)

    assert _can_access_plan(db=None, plan=plan, user_id=7) is False
