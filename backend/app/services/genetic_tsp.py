import random
import math
from typing import List, Tuple

def haversine(lat1, lon1, lat2, lon2) -> float:
    R = 6371
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi/2)**2 + math.cos(phi1)*math.cos(phi2)*math.sin(dlambda/2)**2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))

def route_distance(route: List[dict]) -> float:
    total = 0.0
    for i in range(len(route) - 1):
        total += haversine(route[i]["lat"], route[i]["lon"],
                           route[i+1]["lat"], route[i+1]["lon"])
    return total

def genetic_tsp(cities: List[dict], generations=300, pop_size=100,
                mutation_rate=0.02) -> List[dict]:
    """
    cities: [{"id": int, "lat": float, "lon": float, "name": str}]
    Returns ordered list (best route found).
    """
    if len(cities) <= 2:
        return cities

    def create_individual():
        ind = cities[:]
        random.shuffle(ind)
        return ind

    def crossover(p1, p2):
        size = len(p1)
        a, b = sorted(random.sample(range(size), 2))
        child = p1[a:b]
        child += [c for c in p2 if c not in child]
        return child

    def mutate(ind):
        if random.random() < mutation_rate:
            i, j = random.sample(range(len(ind)), 2)
            ind[i], ind[j] = ind[j], ind[i]
        return ind

    population = [create_individual() for _ in range(pop_size)]

    for _ in range(generations):
        population.sort(key=route_distance)
        elite = population[:10]
        next_gen = elite[:]
        while len(next_gen) < pop_size:
            p1, p2 = random.choices(population[:30], k=2)
            child = mutate(crossover(p1, p2))
            next_gen.append(child)
        population = next_gen

    return population[0]