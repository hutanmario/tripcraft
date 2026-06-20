import math
import uuid
from collections import Counter
from itertools import combinations
from typing import Dict, List, Optional

from sqlalchemy.orm import Session

from app.models import Attraction, City, QuizV4Session, Tag
from app.services.genetic_tsp import genetic_tsp, haversine
from app.services.itinerary_scorer import get_user_tag_vector, score_attractions


HOURS_PER_DAY = 8.0
DEFAULT_ATTRACTION_DURATION = 2.0
VISIT_BUFFER_HOURS = 0.2
TIME_UNITS_PER_HOUR = 4  # 15 minute precision for knapsack.
MIN_STOPS_PER_DAY = 2
TARGET_STOPS_PER_DAY = 3
MAX_STOPS_PER_DAY = 5
EXACT_CANDIDATE_POOL = 16
INTRA_CITY_SPEED_KMH = 18.0
MIN_TRANSFER_HOURS = 0.08
MAX_TRANSFER_HOURS_PER_LEG = 0.75


def _duration_hours(attr: Attraction) -> float:
    duration = float(attr.avg_duration_hours or DEFAULT_ATTRACTION_DURATION)
    return max(0.5, min(duration, 6.0))


def _visit_weight_hours(attr: Attraction) -> float:
    return _duration_hours(attr) + VISIT_BUFFER_HOURS


def _get_session_preferences(session_id: str, db: Session) -> tuple[Optional[str], Optional[str]]:
    try:
        sid = uuid.UUID(str(session_id))
    except (TypeError, ValueError):
        return None, None

    session = db.query(QuizV4Session).filter(QuizV4Session.id == sid).first()
    return (session.budget, session.pace_preference) if session else (None, None)


def _pace_max_stops(pace_preference: Optional[str]) -> int:
    if pace_preference == "relaxed":
        return 2
    if pace_preference == "packed":
        return 5
    return MAX_STOPS_PER_DAY


def _target_city_count(nr_zile: int, available: int) -> int:
    if nr_zile <= 3:
        target = 2
    elif nr_zile <= 7:
        target = 3
    else:
        target = 5
    return max(1, min(target, available, nr_zile))


def _city_candidate_score(city: City, scored_attrs: List[dict]) -> float:
    if not scored_attrs:
        return 0.0

    top_scores = [max(float(item["score"]), 0.0) for item in scored_attrs[:5]]
    top_match = sum(top_scores) / len(top_scores) if top_scores else 0.0
    positive_count = sum(1 for item in scored_attrs if item["score"] > 0)
    attraction_depth = min(positive_count / 8.0, 1.0)
    categories = {
        item["attraction"].category
        for item in scored_attrs[:8]
        if item["attraction"].category
    }
    diversity = min(len(categories) / 4.0, 1.0)
    capital_bonus = 1.0 if getattr(city, "is_capital", False) else 0.0

    return (
        0.62 * top_match
        + 0.20 * attraction_depth
        + 0.13 * diversity
        + 0.05 * capital_bonus
    )


def _score_city_candidates(cities: List[City], city_attractions: Dict[int, List[dict]]) -> List[dict]:
    scored = []
    for city in cities:
        attrs = city_attractions.get(city.id, [])
        if not attrs:
            continue
        total_candidate_hours = sum(_duration_hours(item["attraction"]) for item in attrs[:24])
        scored.append({
            "id": city.id,
            "name": city.name,
            "lat": city.latitude,
            "lon": city.longitude,
            "score": _city_candidate_score(city, attrs),
            "candidate_hours": total_candidate_hours,
            "attraction_count": len(attrs),
        })

    scored.sort(key=lambda item: item["score"], reverse=True)
    return scored


def _select_trip_cities(scored_cities: List[dict], nr_zile: int) -> List[dict]:
    target = _target_city_count(nr_zile, len(scored_cities))
    return scored_cities[:target]


def _city_day_capacity(city: dict) -> int:
    by_hours = max(1, math.ceil(city.get("candidate_hours", 0.0) / HOURS_PER_DAY))
    by_count = max(1, math.ceil(city.get("attraction_count", 0) / 4))
    return min(max(by_hours, by_count), 4)


def _allocate_days_to_cities(ordered_cities: List[dict], nr_zile: int) -> List[dict]:
    if not ordered_cities:
        return []

    allocations = [1 for _ in ordered_cities]
    extra_days = nr_zile - len(ordered_cities)
    capacities = [_city_day_capacity(city) for city in ordered_cities]

    while extra_days > 0:
        candidates = [
            i for i, current in enumerate(allocations)
            if current < capacities[i]
        ]
        if not candidates:
            candidates = list(range(len(ordered_cities)))

        min_alloc = min(allocations[i] for i in candidates)
        balanced_candidates = [
            i for i in candidates
            if allocations[i] == min_alloc
        ]
        best_idx = max(
            balanced_candidates,
            key=lambda i: ordered_cities[i]["score"],
        )
        allocations[best_idx] += 1
        extra_days -= 1

    day_cities = []
    for city, count in zip(ordered_cities, allocations):
        day_cities.extend([city] * count)
    return day_cities[:nr_zile]


def _category_for_item(item: dict) -> str:
    return item["attraction"].category or "general"


def _optimizer_value(item: dict, used_category_counts: Dict[str, int]) -> float:
    attr = item["attraction"]
    score = max(float(item["score"]), 0.0)
    rating = float(attr.rating or 0.0)
    rating_bonus = min(max((rating - 3.5) / 1.5, 0.0), 1.0) * 0.08

    category = _category_for_item(item)
    category_count = used_category_counts.get(category, 0)
    diversity_bonus = 0.08 if category_count == 0 else max(0.0, 0.04 / (category_count + 1))

    return score + rating_bonus + diversity_bonus


def _select_day_attractions_knapsack(
    scored_attrs: List[dict],
    used_attraction_ids: set,
    used_category_counts: Dict[str, int],
    max_stops_per_day: int = MAX_STOPS_PER_DAY,
    city: Optional[dict] = None,
) -> List[dict]:
    """
    Time-budget optimizer for one day.

    We keep a small top candidate pool, then evaluate feasible combinations with
    visit duration and estimated transfer time. This behaves like a bounded
    knapsack optimizer, but avoids the greedy failure mode of picking one long
    attraction that blocks a better set of shorter stops.
    """
    candidates = [
        item for item in scored_attrs
        if item["attraction"].id not in used_attraction_ids
    ]
    if not candidates:
        return []

    candidates = sorted(
        candidates,
        key=lambda item: _optimizer_value(item, used_category_counts),
        reverse=True,
    )[:EXACT_CANDIDATE_POOL]

    for item in candidates:
        item["_optimizer_value"] = _optimizer_value(item, used_category_counts)

    capacity = int(HOURS_PER_DAY * TIME_UNITS_PER_HOUR)
    max_stops = min(MAX_STOPS_PER_DAY, max_stops_per_day, len(candidates))
    if max_stops <= 0:
        return []

    min_stops = MIN_STOPS_PER_DAY if len(candidates) >= MIN_STOPS_PER_DAY else 1
    best = None
    best_rank = -math.inf

    for size in range(1, max_stops + 1):
        for combo in combinations(candidates, size):
            selected = list(combo)
            ordered = _order_day_route(selected, city) if city else selected
            weight_units = sum(
                int(math.ceil(_visit_weight_hours(item["attraction"]) * TIME_UNITS_PER_HOUR))
                for item in selected
            )
            if weight_units > capacity:
                continue

            total_hours = _visit_hours(ordered)
            if city:
                total_hours += _transfer_hours_for_route(ordered, city)
            if total_hours > HOURS_PER_DAY and size > 1:
                continue

            value = sum(item["_optimizer_value"] for item in selected)
            stop_bonus = size * 0.04
            fullness_bonus = min(total_hours / HOURS_PER_DAY, 1.0) * 0.03
            min_stop_bonus = 0.20 if size >= min_stops else 0.0
            rank = value + stop_bonus + fullness_bonus + min_stop_bonus

            if rank > best_rank:
                best = ordered
                best_rank = rank

    if best:
        return best

    return [candidates[0]]


def _max_stops_for_city_day(
    city: dict,
    city_attractions: Dict[int, List[dict]],
    used_attraction_ids: set,
    city_day_totals: Counter,
    city_day_done: Counter,
) -> int:
    city_id = city["id"]
    available_count = sum(
        1 for item in city_attractions.get(city_id, [])
        if item["attraction"].id not in used_attraction_ids
    )
    if available_count <= 0:
        return 0

    remaining_days_after = max(
        city_day_totals.get(city_id, 0) - city_day_done.get(city_id, 0) - 1,
        0,
    )
    reserved_for_future = remaining_days_after * TARGET_STOPS_PER_DAY
    allowed_today = available_count - reserved_for_future
    if allowed_today <= 0:
        allowed_today = max(1, math.ceil(available_count / (remaining_days_after + 1)))

    return max(1, min(MAX_STOPS_PER_DAY, allowed_today))


def _item_has_coords(item: dict) -> bool:
    attr = item["attraction"]
    return attr.latitude is not None and attr.longitude is not None


def _distance_from_point(point: dict, item: dict) -> float:
    attr = item["attraction"]
    return haversine(point["lat"], point["lon"], attr.latitude, attr.longitude)


def _route_distance_from_start(route: List[dict], start: dict) -> float:
    if not route:
        return 0.0
    distance = _distance_from_point(start, route[0])
    for i in range(len(route) - 1):
        distance += _distance_from_point(
            {
                "lat": route[i]["attraction"].latitude,
                "lon": route[i]["attraction"].longitude,
            },
            route[i + 1],
        )
    return distance


def _nearest_neighbor_route(items: List[dict], start: dict) -> List[dict]:
    remaining = items[:]
    ordered = []
    current = start
    while remaining:
        next_item = min(remaining, key=lambda item: _distance_from_point(current, item))
        ordered.append(next_item)
        remaining.remove(next_item)
        current = {
            "lat": next_item["attraction"].latitude,
            "lon": next_item["attraction"].longitude,
        }
    return ordered


def _two_opt_route(route: List[dict], start: dict) -> List[dict]:
    if len(route) < 4:
        return route

    best = route[:]
    improved = True
    while improved:
        improved = False
        for i in range(1, len(best) - 2):
            for j in range(i + 1, len(best)):
                if j - i == 1:
                    continue
                candidate = best[:]
                candidate[i:j] = reversed(candidate[i:j])
                if _route_distance_from_start(candidate, start) < _route_distance_from_start(best, start):
                    best = candidate
                    improved = True
        route = best
    return best


def _order_day_route(selected: List[dict], city: dict) -> List[dict]:
    geocoded = [item for item in selected if _item_has_coords(item)]
    missing_coords = [item for item in selected if not _item_has_coords(item)]
    if not geocoded:
        return selected

    start = {"lat": city["lat"], "lon": city["lon"]}
    ordered = _nearest_neighbor_route(geocoded, start)
    ordered = _two_opt_route(ordered, start)
    return ordered + missing_coords


def _transfer_hours_for_route(ordered: List[dict], city: dict) -> float:
    geocoded = [item for item in ordered if _item_has_coords(item)]
    if not geocoded:
        return 0.0

    total = 0.0
    current = {"lat": city["lat"], "lon": city["lon"]}
    for item in geocoded:
        km = _distance_from_point(current, item)
        if km > 0:
            leg_hours = km / INTRA_CITY_SPEED_KMH
            total += max(MIN_TRANSFER_HOURS, min(leg_hours, MAX_TRANSFER_HOURS_PER_LEG))
        current = {
            "lat": item["attraction"].latitude,
            "lon": item["attraction"].longitude,
        }
    return total


def _visit_hours(selected: List[dict]) -> float:
    return sum(_duration_hours(item["attraction"]) for item in selected)


def _trim_to_time_limit(ordered: List[dict], city: dict) -> List[dict]:
    if not ordered:
        return []

    min_stops = MIN_STOPS_PER_DAY if len(ordered) >= MIN_STOPS_PER_DAY else 1
    best = None
    best_rank = -math.inf

    for size in range(len(ordered), 0, -1):
        for combo in combinations(ordered, size):
            candidate = _order_day_route(list(combo), city)
            total_hours = _visit_hours(candidate) + _transfer_hours_for_route(candidate, city)
            if total_hours > HOURS_PER_DAY and size > 1:
                continue

            value = sum(item.get("_optimizer_value", item["score"]) for item in candidate)
            stop_bonus = size * 0.03
            fullness_bonus = min(total_hours / HOURS_PER_DAY, 1.0) * 0.02
            min_stop_bonus = 0.15 if size >= min_stops else 0.0
            rank = value + stop_bonus + fullness_bonus + min_stop_bonus

            if rank > best_rank:
                best = candidate
                best_rank = rank

    if best:
        return best

    return ordered[:1]


def _best_city_with_unused_attractions(
    ordered_cities: List[dict],
    city_attractions: Dict[int, List[dict]],
    used_attraction_ids: set,
) -> Optional[dict]:
    candidates = []
    for city in ordered_cities:
        has_unused = any(
            item["attraction"].id not in used_attraction_ids
            for item in city_attractions.get(city["id"], [])
        )
        if has_unused:
            candidates.append(city)
    if not candidates:
        return None
    return max(candidates, key=lambda city: city["score"])


def _day_payload(day_num: int, city: dict, selected: List[dict]) -> dict:
    visit_hours = _visit_hours(selected)
    transfer_hours = _transfer_hours_for_route(selected, city)
    attractions = []
    for item in selected:
        attr = item["attraction"]
        attractions.append({
            "attraction_id": attr.id,
            "name": attr.name,
            "duration_hours": _duration_hours(attr),
            "entry_fee_eur": attr.entry_fee_eur,
            "score": round(float(item["score"]), 4),
            "lat": attr.latitude,
            "lon": attr.longitude,
        })

    return {
        "day": day_num,
        "city_id": city["id"],
        "city_name": city["name"],
        "attractions": attractions,
        "visit_hours": round(visit_hours, 1),
        "transfer_hours": round(transfer_hours, 1),
        "total_hours": round(visit_hours + transfer_hours, 1),
    }


def build_itinerary(
    country_id: int,
    nr_zile: int,
    session_id: str,
    budget_level: str = None,
    profile_boosts: dict | None = None,
    db: Session = None,
) -> List[Dict]:
    cities = db.query(City).filter(City.country_id == country_id).all()
    if not cities:
        return []

    city_nodes = [
        city for city in cities
        if city.latitude is not None and city.longitude is not None
    ]
    if not city_nodes:
        return []

    all_tag_ids = [tag.id for tag in db.query(Tag).all()]
    user_vector, user_raw_scores = get_user_tag_vector(session_id, db, all_tag_ids, profile_boosts=profile_boosts)
    session_budget, pace_preference = _get_session_preferences(session_id, db)
    effective_budget = budget_level or session_budget
    pace_max_stops = _pace_max_stops(pace_preference)

    city_ids = [city.id for city in city_nodes]
    all_attractions = db.query(Attraction).filter(Attraction.city_id.in_(city_ids)).all()
    scored_all = score_attractions(
        all_attractions,
        user_vector,
        all_tag_ids,
        db,
        budget_level=effective_budget,
        user_raw_scores=user_raw_scores,
    )

    city_attractions: Dict[int, List[dict]] = {}
    for item in scored_all:
        city_attractions.setdefault(item["attraction"].city_id, []).append(item)

    scored_cities = _score_city_candidates(city_nodes, city_attractions)
    if not scored_cities:
        return []

    selected_cities = _select_trip_cities(scored_cities, nr_zile)
    ordered_cities = genetic_tsp(selected_cities, generations=200, pop_size=80)
    day_cities = _allocate_days_to_cities(ordered_cities, nr_zile)

    days = []
    used_attraction_ids = set()
    used_category_counts: Dict[str, int] = {}
    city_day_totals = Counter(city["id"] for city in day_cities)
    city_day_done = Counter()

    for day_num, city in enumerate(day_cities, start=1):
        active_city = city
        scored_attrs = city_attractions.get(active_city["id"], [])
        max_stops_today = _max_stops_for_city_day(
            active_city,
            city_attractions,
            used_attraction_ids,
            city_day_totals,
            city_day_done,
        )
        max_stops_today = min(max_stops_today, pace_max_stops)
        selected = _select_day_attractions_knapsack(
            scored_attrs,
            used_attraction_ids,
            used_category_counts,
            max_stops_today,
            active_city,
        )

        if not selected:
            fallback_city = _best_city_with_unused_attractions(
                ordered_cities,
                city_attractions,
                used_attraction_ids,
            )
            if fallback_city:
                active_city = fallback_city
                max_stops_today = _max_stops_for_city_day(
                    active_city,
                    city_attractions,
                    used_attraction_ids,
                    city_day_totals,
                    city_day_done,
                )
                max_stops_today = min(max_stops_today, pace_max_stops)
                selected = _select_day_attractions_knapsack(
                    city_attractions.get(active_city["id"], []),
                    used_attraction_ids,
                    used_category_counts,
                    max_stops_today,
                    active_city,
                )

        if not selected:
            selected = _select_day_attractions_knapsack(
                scored_attrs,
                set(),
                used_category_counts,
                pace_max_stops,
                active_city,
            )

        selected = _order_day_route(selected, active_city)
        selected = _trim_to_time_limit(selected, active_city)

        for item in selected:
            attr = item["attraction"]
            used_attraction_ids.add(attr.id)
            category = _category_for_item(item)
            used_category_counts[category] = used_category_counts.get(category, 0) + 1

        days.append(_day_payload(day_num, active_city, selected))
        city_day_done[city["id"]] += 1

    return days
