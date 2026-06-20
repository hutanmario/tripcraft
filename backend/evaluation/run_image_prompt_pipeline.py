#!/usr/bin/env python3
"""
Pipeline alternativ pentru recunoasterea imaginilor TripCraft.

Scop: in loc sa detectam cateva concepte CLIP generice si apoi sa le mapam
semantic spre DB, scoram direct tagurile reale TripCraft cu prompturi multiple.

Rulare (din directorul backend/):
    python -m evaluation.run_image_prompt_pipeline

Rulare rapida:
    python -m evaluation.run_image_prompt_pipeline --limit 5

Rezultatul este compatibil cu run_image_recognition_eval.py, prin campul
`matched_db_tags`.
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import torch
from PIL import Image


BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.database import SessionLocal
from app.models.tag import Tag
from app.services.clip_service import clip_service


EVAL_DIR = Path(__file__).resolve().parent
RESULTS_DIR = EVAL_DIR / "results"
STATIC_IMAGES_DIR = BACKEND_DIR / "static" / "quiz_images"
DEFAULT_DATASET_PATH = EVAL_DIR / "image_recognition_dataset.json"
OUTPUT_JSON = RESULTS_DIR / "image_prompt_multitag_predictions.json"

TOP_N = 20
SCORE_MODE = "top2_mean"
RERANK_MODE = "calibrated"

# Taguri care descriu preferinte generale, contexte sau intentii greu de
# confirmat dintr-o singura fotografie. Le pastram disponibile, dar le cerem
# scor mai bun ca sa intre peste concepte vizuale clare.
TAG_SCORE_MULTIPLIERS = {
    "adventure-active": 0.86,
    "air-extreme-sports": 0.88,
    "architecture": 0.93,
    "arts-museums": 0.96,
    "accessible-attractions": 0.87,
    "beach-water": 0.9,
    "child-activities": 0.88,
    "child-beaches": 0.9,
    "comfort-accommodation": 0.88,
    "culture-history": 0.86,
    "easy-sightseeing": 0.9,
    "family-comfort": 0.84,
    "film-festivals": 0.88,
    "float-tanks": 0.9,
    "food-drink": 0.86,
    "food-social-tours": 0.9,
    "food-tours-guided": 0.86,
    "guided-group-tours": 0.9,
    "hiking-trekking": 0.94,
    "local-festivals": 0.9,
    "nightlife-social": 0.86,
    "nature-outdoors": 0.86,
    "paragliding": 0.9,
    "playgrounds-parks": 0.9,
    "rooftop-parties": 0.9,
    "science-centers": 0.9,
    "science-interactive-museums": 0.9,
    "science-museums": 0.9,
    "street-photography-spots": 0.9,
    "tech-innovation": 0.9,
    "urban-modern": 0.88,
    "wellness-slow": 0.86,
    "wwii-history": 0.86,
}

# Afinitati vizuale care nu sunt mereu surprinse de parent_id in DB.
# Cheia este tagul care primeste evidence, valorile sunt taguri-sursa si
# proportia din scorul lor care poate fi mostenita.
VISUAL_AFFINITY_BOOSTS = {
    "art-museums": {
        "arts-museums": 0.98,
        "contemporary-art": 0.88,
        "history-museums": 0.84,
    },
    "canal-river-cruises": {
        "cruises": 0.9,
        "kayaking-canoeing": 0.86,
        "sailing": 0.86,
    },
    "contemporary-architecture": {
        "modernist-architecture": 0.9,
        "photography-urban": 0.86,
        "urban-culture": 0.82,
        "urban-modern": 0.82,
    },
    "contemporary-art": {
        "arts-museums": 0.96,
        "street-art": 0.86,
        "urban-culture": 0.82,
    },
    "guided-walking-tours": {
        "ancient-ruins": 0.8,
        "castles-palaces": 0.8,
        "historical-sites": 0.82,
        "gothic-architecture": 0.76,
        "orthodox-churches": 0.76,
    },
    "hiking": {
        "alpine-climbing": 0.82,
        "coastal-walks": 0.84,
        "day-hiking": 0.95,
        "forest-bathing": 0.82,
        "multi-day-trekking": 0.92,
    },
    "historical-sites": {
        "ancient-ruins": 0.96,
        "castles-palaces": 0.96,
        "gothic-architecture": 0.84,
        "orthodox-churches": 0.84,
        "religious-sites": 0.82,
        "roman-history": 0.94,
    },
    "national-parks": {
        "birdwatching": 0.86,
        "photography-landscapes": 0.86,
        "wildlife-nature": 0.92,
        "wildlife-watching": 0.9,
    },
    "photography-landscapes": {
        "coastal-walks": 0.9,
        "day-hiking": 0.86,
        "fjords": 0.9,
        "glaciers": 0.92,
        "hidden-coves": 0.86,
        "national-parks": 0.88,
        "winter-nature": 0.86,
    },
    "street-casual-food": {
        "bakeries-pastries": 0.88,
        "food-trucks": 0.95,
        "local-tavernas": 0.88,
        "specialty-coffee": 0.78,
        "street-food": 0.96,
    },
    "street-food": {
        "food-trucks": 0.88,
        "street-casual-food": 0.92,
    },
    "water-sports": {
        "kayaking-canoeing": 0.92,
        "paddleboarding": 0.9,
        "sailing": 0.84,
        "scuba-diving": 0.96,
        "surfing-kitesurfing": 0.96,
    },
    "wildlife-nature": {
        "birdwatching": 0.9,
        "national-parks": 0.9,
        "wildlife-watching": 0.94,
    },
    "winter-nature": {
        "glaciers": 0.92,
        "skiing": 0.9,
        "snowshoeing": 0.9,
    },
}

PARENT_TO_CHILD_INHERITANCE = 0.99
CHILD_TO_PARENT_INHERITANCE = 0.97
PARENT_TO_CHILD_MIN_RATIO = 0.88
CHILD_TO_PARENT_ALLOWED_SLUGS = {
    "arts-museums",
    "contemplative-nature",
    "food-markets",
    "historical-sites",
    "street-casual-food",
    "water-sports",
    "wildlife-nature",
}
PARENT_TO_CHILD_ALLOWED_SLUGS: set[str] = set()


logging.basicConfig(level=logging.WARNING)
log = logging.getLogger("image_prompt_pipeline")
log.setLevel(logging.INFO)
log.propagate = False
handler = logging.StreamHandler()
handler.setFormatter(logging.Formatter("%(message)s"))
log.addHandler(handler)


@dataclass(frozen=True)
class TagPromptBundle:
    slug: str
    name: str
    category: str
    is_leaf: bool
    parent_slug: str | None
    child_slugs: tuple[str, ...]
    prompts: tuple[str, ...]


VISUAL_CATEGORY_HINTS = {
    "nature-outdoors": "nature and outdoor travel",
    "culture-history": "culture, heritage, museums and historical travel",
    "nightlife-social": "nightlife, entertainment and social travel",
    "adventure-active": "active adventure and sports travel",
    "food-drink": "food, drinks and culinary travel",
    "wellness-slow": "wellness, spa and slow travel",
    "urban-modern": "urban design, modern city and creative travel",
    "family-comfort": "family attractions and comfortable travel",
}


# Manual hints pentru tagurile unde numele scurt este ambiguu sau prea abstract.
# Fallback-ul automat acopera toate tagurile din DB; acest dictionar doar adauga
# prompturi vizuale mai concrete pentru conceptele importante.
TAG_VISUAL_HINTS = {
    "sandy-beaches": [
        "a sunny sandy beach with sea water and shoreline",
        "a travel photo of a sandy beach vacation by the ocean",
        "clear water, sand, beach umbrellas and seaside scenery",
    ],
    "hidden-coves": [
        "a secluded small cove with turquoise water and rocks",
        "a hidden beach cove surrounded by cliffs",
    ],
    "snorkeling-diving": [
        "snorkeling in clear tropical water with reef",
        "a travel photo of snorkeling and underwater sea life",
    ],
    "scuba-diving": [
        "scuba divers underwater with coral reef",
        "a diving travel photo in clear blue water",
    ],
    "water-sports": [
        "people doing water sports on a lake or sea",
        "active travel water sports with boards boats or waves",
    ],
    "surfing-kitesurfing": [
        "surfers riding ocean waves",
        "kitesurfing on a windy beach with colorful kites",
    ],
    "coastal-walks": [
        "a scenic walking path along sea cliffs and coastline",
        "people walking by a coastal trail with ocean views",
    ],
    "kayaking-canoeing": [
        "kayaks or canoes on calm water in nature",
        "people kayaking on a lake river or sea",
    ],
    "canal-river-cruises": [
        "a tourist boat cruise on a river or canal",
        "boats traveling through a city canal or river",
    ],
    "sailing": [
        "sailboats on the sea with white sails",
        "a sailing trip on blue water",
    ],
    "cruises": [
        "a cruise ship or tourist boat trip on water",
        "large passenger ship for travel vacation",
    ],
    "day-hiking": [
        "people hiking on a marked trail during the day",
        "a day hike through mountains or forest",
    ],
    "hiking": [
        "hikers walking on a nature trail",
        "a scenic hiking route in mountains forest or countryside",
    ],
    "multi-day-trekking": [
        "backpackers trekking for multiple days in mountains",
        "long distance trekking with backpacks and wild landscape",
    ],
    "camping": [
        "a camping tent in nature",
        "camping outdoors near mountains forest or lake",
    ],
    "alpine-climbing": [
        "alpine climbers on snowy mountain peaks",
        "technical mountaineering in high mountains",
    ],
    "rock-climbing": [
        "a person rock climbing on a cliff",
        "climbers on vertical rock wall with ropes",
    ],
    "via-ferrata": [
        "via ferrata route with cables on a mountain cliff",
        "people climbing protected iron path in mountains",
    ],
    "glaciers": [
        "a glacier landscape with ice and snow",
        "icy mountain glacier travel scenery",
    ],
    "skiing": [
        "skiers on snowy ski slopes",
        "winter sports resort with people skiing",
    ],
    "snowshoeing": [
        "people snowshoeing through deep snow",
        "winter hike with snowshoes in snowy forest",
    ],
    "winter-nature": [
        "snowy winter nature landscape",
        "winter travel scenery with snow ice and mountains",
    ],
    "forest-bathing": [
        "peaceful green forest path for slow nature travel",
        "quiet forest scenery with tall trees and soft light",
    ],
    "national-parks": [
        "a national park landscape with wild nature",
        "protected natural park with mountains forest or wildlife",
    ],
    "wildlife-watching": [
        "tourists watching wild animals in nature",
        "wildlife photography safari or animal watching travel",
    ],
    "wildlife-nature": [
        "wild animals in natural habitat",
        "nature travel photo with wildlife",
    ],
    "birdwatching": [
        "people birdwatching with binoculars in nature",
        "birds in a wetland or forest for bird watching",
    ],
    "photography-landscapes": [
        "a dramatic scenic landscape for travel photography",
        "beautiful natural viewpoint with mountains water or sunset",
    ],
    "castles-palaces": [
        "a historic castle or palace tourist attraction",
        "medieval castle walls towers and fortress",
    ],
    "ancient-ruins": [
        "ancient archaeological ruins with stone columns",
        "old ruins from an ancient civilization",
    ],
    "historical-sites": [
        "a historical tourist site with old architecture or ruins",
        "heritage landmark showing history and culture",
    ],
    "gothic-architecture": [
        "gothic cathedral architecture with pointed arches",
        "medieval gothic building with ornate stone facade",
    ],
    "religious-sites": [
        "a sacred religious site church temple or monastery",
        "spiritual travel landmark with religious architecture",
    ],
    "orthodox-churches": [
        "orthodox church with domes icons or painted walls",
        "eastern orthodox monastery or church travel photo",
    ],
    "vernacular-architecture": [
        "traditional local architecture and old houses",
        "vernacular buildings showing regional style",
    ],
    "history-museums": [
        "museum exhibition about history with artifacts",
        "historical museum interior with displays",
    ],
    "roman-history": [
        "roman ruins ancient amphitheater or columns",
        "travel photo of roman empire archaeological heritage",
    ],
    "art-museums": [
        "art museum or gallery with paintings and sculptures",
        "people viewing art in a museum gallery",
    ],
    "contemporary-art": [
        "contemporary art installation in a gallery",
        "modern artwork exhibition or creative space",
        "outdoor contemporary public art sculpture in a city plaza",
        "large modern art installation in front of contemporary buildings",
    ],
    "street-art": [
        "colorful street art mural on an urban wall",
        "graffiti and murals in a city neighborhood",
    ],
    "graffiti-tours": [
        "graffiti art walls on an urban walking tour",
        "street art tour with murals and painted buildings",
    ],
    "contemporary-architecture": [
        "modern contemporary architecture with glass and steel",
        "futuristic city building and modern design",
        "modern public building with contemporary urban design",
        "contemporary city architecture around a public square",
    ],
    "modernist-architecture": [
        "modernist architecture with clean geometric forms",
        "20th century modernist building design",
    ],
    "brutalist-architecture": [
        "brutalist concrete architecture building",
        "massive raw concrete urban structure",
    ],
    "photography-urban": [
        "urban photography of city streets and architecture",
        "cityscape viewpoint for street photography",
    ],
    "tech-hubs": [
        "modern technology district with offices and startups",
        "urban tech hub with contemporary buildings",
    ],
    "street-food": [
        "street food vendor cooking local food outdoors",
        "busy street food market with dishes and stalls",
    ],
    "street-casual-food": [
        "casual street food meal from a local vendor",
        "informal food stalls and quick local dishes",
    ],
    "food-trucks": [
        "food trucks serving meals on a street",
        "mobile food truck market with people eating",
    ],
    "farmers-markets": [
        "farmers market with fresh produce stalls",
        "local market selling vegetables fruit and artisan food",
    ],
    "food-markets": [
        "local food market with many produce stalls",
        "indoor or outdoor market full of food vendors",
    ],
    "fish-markets": [
        "fish market with fresh seafood on display",
        "local seafood market travel photo",
    ],
    "michelin-restaurants": [
        "fine dining restaurant with elegant plated food",
        "luxury restaurant tasting menu dish",
    ],
    "tasting-menus": [
        "gourmet tasting menu with small elegant plates",
        "fine dining multi course meal",
    ],
    "fine-dining-exp": [
        "fine dining experience in an elegant restaurant",
        "chef prepared gourmet plate in upscale restaurant",
    ],
    "wine-vineyards": [
        "vineyard rows and wine tasting travel scenery",
        "wine region with grape vines and winery",
    ],
    "wine-bars": [
        "wine bar with glasses bottles and cozy interior",
        "people tasting wine in a bar or cellar",
    ],
    "drinks-tastings": [
        "drink tasting with glasses bottles and local beverages",
        "wine beer or spirits tasting experience",
    ],
    "specialty-coffee": [
        "specialty coffee shop with espresso and barista",
        "latte art and third wave coffee cafe",
    ],
    "bakeries-pastries": [
        "bakery display with pastries bread and cakes",
        "local bakery with fresh pastries",
    ],
    "rooftop-bars": [
        "rooftop bar with city skyline view",
        "people drinking cocktails on a rooftop terrace",
    ],
    "rooftop-views": [
        "panoramic city view from a rooftop",
        "urban skyline seen from a high terrace",
    ],
    "craft-cocktail-bars": [
        "craft cocktails served in an elegant bar",
        "bartender making cocktails at a bar",
    ],
    "underground-clubs": [
        "underground nightclub with dark lights and dancing",
        "crowded basement club nightlife scene",
    ],
    "techno-clubs": [
        "techno club dance floor with DJ and lights",
        "electronic music nightclub with lasers",
    ],
    "clubbing": [
        "people dancing in a nightclub",
        "club nightlife dance floor with colorful lights",
    ],
    "jazz-live-music": [
        "jazz band performing live in a small venue",
        "live jazz music club with musicians on stage",
    ],
    "live-entertainment": [
        "live entertainment performance on stage",
        "audience watching a concert or show",
    ],
    "music-festivals": [
        "outdoor music festival stage with crowd",
        "large concert festival with lights and audience",
    ],
    "theater-musicals": [
        "theater stage performance or musical show",
        "audience watching actors on a theater stage",
    ],
    "opera-classical": [
        "opera house or classical music performance",
        "orchestra concert in an elegant hall",
    ],
    "thermal-baths": [
        "thermal baths with warm mineral pools",
        "people relaxing in hot spring spa pools",
    ],
    "spa-thermal": [
        "spa thermal pool and wellness bath",
        "relaxing thermal spa interior with water",
    ],
    "hot-springs-outdoor": [
        "outdoor hot springs in nature with steam",
        "natural hot spring pools surrounded by landscape",
    ],
    "hammam": [
        "traditional hammam bath with marble and steam",
        "turkish bath spa interior",
    ],
    "yoga-retreats": [
        "people practicing yoga at a retreat",
        "yoga class in peaceful nature or studio",
    ],
    "meditation-centers": [
        "quiet meditation center with cushions",
        "people meditating in a calm retreat space",
    ],
    "mindfulness-retreats": [
        "mindfulness retreat with meditation and calm nature",
        "peaceful wellness retreat for relaxation",
    ],
    "luxury-spa": [
        "luxury spa treatment room with candles and towels",
        "upscale wellness spa with pool and loungers",
    ],
    "science-museums": [
        "science museum with exhibits and displays",
        "interactive science exhibition for visitors",
    ],
    "science-interactive-museums": [
        "interactive science museum with hands on exhibits",
        "children using interactive science displays",
    ],
    "science-centers": [
        "science center with educational exhibits",
        "modern science center for families",
    ],
    "zoos-aquariums": [
        "aquarium tanks or zoo animals for visitors",
        "family visiting animals in zoo or aquarium",
    ],
    "kids-workshops": [
        "children doing creative workshop activities",
        "family friendly hands on kids workshop",
    ],
    "theme-parks": [
        "theme park rides roller coaster and attractions",
        "amusement park with colorful rides",
    ],
    "water-parks": [
        "water park with slides and pools",
        "family water slides and swimming pools",
    ],
}


def _slug_to_label(slug: str) -> str:
    return slug.replace("-", " ").replace("_", " ").strip()


def _category_label(category: str) -> str:
    return VISUAL_CATEGORY_HINTS.get(category, _slug_to_label(category))


def _generic_prompts(slug: str, name: str, category: str, is_leaf: bool) -> list[str]:
    label = name.strip() if name else _slug_to_label(slug)
    slug_label = _slug_to_label(slug)
    category_label = _category_label(category)
    specificity = "specific travel activity" if is_leaf else "travel preference category"

    prompts = [
        f"a travel photo of {label}",
        f"a tourism image showing {label}",
        f"a realistic vacation photo featuring {slug_label}",
        f"{category_label}: {label}",
        f"a {specificity} about {slug_label}",
    ]
    return prompts


def _build_prompts_for_tag(tag: Tag) -> TagPromptBundle:
    prompts = [
        *TAG_VISUAL_HINTS.get(tag.slug, []),
        *_generic_prompts(tag.slug, tag.name or "", tag.category or "", bool(tag.is_leaf)),
    ]
    cleaned = tuple(dict.fromkeys(prompt.strip() for prompt in prompts if prompt.strip()))
    return TagPromptBundle(
        slug=tag.slug,
        name=tag.name or tag.slug,
        category=tag.category or "uncategorized",
        is_leaf=bool(tag.is_leaf),
        parent_slug=tag.parent.slug if tag.parent else None,
        child_slugs=tuple(sorted(child.slug for child in tag.children)),
        prompts=cleaned,
    )


def _load_dataset(dataset_path: Path) -> dict[str, Any]:
    if not dataset_path.exists():
        raise FileNotFoundError(f"Datasetul nu exista: {dataset_path}")

    payload = json.loads(dataset_path.read_text(encoding="utf-8"))
    images = payload.get("images")
    if not isinstance(images, list) or not images:
        raise ValueError("Datasetul trebuie sa contina lista nevida `images`.")

    normalized = []
    seen = set()
    for image in images:
        image_id = image.get("id") or Path(str(image.get("file", ""))).stem.replace("-", "_")
        if not image_id:
            raise ValueError("Imagine fara `id` sau `file`.")
        if image_id in seen:
            raise ValueError(f"ID duplicat in dataset: {image_id}")
        seen.add(image_id)

        file_name = image.get("file")
        if not file_name:
            raise ValueError(f"Imaginea {image_id} nu are `file`.")
        image_path = STATIC_IMAGES_DIR / file_name
        if not image_path.exists():
            raise FileNotFoundError(f"Lipseste imaginea: {image_path}")

        normalized.append(
            {
                **image,
                "id": image_id,
                "file": file_name,
                "category": image.get("category", "uncategorized"),
                "expected_tags": list(dict.fromkeys(image.get("expected_tags", []))),
                "notes": image.get("notes", ""),
            }
        )

    payload["images"] = normalized
    return payload


def _select_images(images: list[dict[str, Any]], limit: int | None, only: str | None) -> list[dict[str, Any]]:
    selected = images
    if only:
        wanted = {item.strip() for item in only.split(",") if item.strip()}
        selected = [
            image
            for image in selected
            if image["id"] in wanted or Path(image["file"]).stem in wanted
        ]
    if limit is not None:
        selected = selected[:limit]
    if not selected:
        raise RuntimeError("Nu exista imagini selectate.")
    return selected


def _load_tag_bundles(leaf_only: bool) -> list[TagPromptBundle]:
    db = SessionLocal()
    try:
        query = db.query(Tag)
        if leaf_only:
            query = query.filter(Tag.is_leaf.is_(True))
        tags = query.order_by(Tag.slug.asc()).all()
        return [_build_prompts_for_tag(tag) for tag in tags]
    finally:
        db.close()


def _display_path(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(BACKEND_DIR)).replace("\\", "/")
    except ValueError:
        return str(path)


def _tensor_from_model_output(value: Any) -> torch.Tensor:
    if isinstance(value, torch.Tensor):
        return value
    if hasattr(value, "pooler_output"):
        return value.pooler_output
    if hasattr(value, "last_hidden_state"):
        return value.last_hidden_state[:, 0]
    raise TypeError(f"Nu pot converti output-ul modelului la Tensor: {type(value)!r}")


def _normalize(features: torch.Tensor) -> torch.Tensor:
    return features / features.norm(dim=-1, keepdim=True).clamp_min(1e-12)


def _encode_text_prompts(
    bundles: list[TagPromptBundle],
    batch_size: int,
) -> tuple[torch.Tensor, list[tuple[int, int]], list[str]]:
    clip_service._load_model()
    model = clip_service._model
    processor = clip_service._processor

    prompts = []
    tag_prompt_ranges = []
    cursor = 0
    for bundle in bundles:
        prompts.extend(bundle.prompts)
        tag_prompt_ranges.append((cursor, cursor + len(bundle.prompts)))
        cursor += len(bundle.prompts)

    encoded_batches = []
    with torch.no_grad():
        for start in range(0, len(prompts), batch_size):
            batch = prompts[start:start + batch_size]
            inputs = processor(
                text=batch,
                return_tensors="pt",
                padding=True,
                truncation=True,
            )
            features = _tensor_from_model_output(model.get_text_features(**inputs))
            encoded_batches.append(_normalize(features).cpu())

    return torch.cat(encoded_batches, dim=0), tag_prompt_ranges, prompts


def _encode_image(image_path: Path) -> torch.Tensor:
    clip_service._load_model()
    model = clip_service._model
    processor = clip_service._processor

    image = Image.open(image_path).convert("RGB")
    inputs = processor(images=image, return_tensors="pt")
    with torch.no_grad():
        features = _tensor_from_model_output(model.get_image_features(**inputs))
    return _normalize(features).cpu()[0]


def _score_tags(
    image_features: torch.Tensor,
    text_features: torch.Tensor,
    bundles: list[TagPromptBundle],
    tag_prompt_ranges: list[tuple[int, int]],
    score_mode: str,
) -> tuple[dict[str, float], dict[str, list[dict[str, float | str]]]]:
    similarities = torch.matmul(text_features, image_features)
    scores: dict[str, float] = {}
    prompt_debug: dict[str, list[dict[str, float | str]]] = {}

    for bundle, (start, end) in zip(bundles, tag_prompt_ranges):
        tag_sims = similarities[start:end]
        sorted_values, sorted_indices = torch.sort(tag_sims, descending=True)

        if score_mode == "max":
            score = float(sorted_values[0])
        elif score_mode == "mean":
            score = float(tag_sims.mean())
        elif score_mode == "top2_mean":
            n = min(2, len(sorted_values))
            score = float(sorted_values[:n].mean())
        else:
            raise ValueError(f"score_mode necunoscut: {score_mode}")

        scores[bundle.slug] = score
        prompt_debug[bundle.slug] = [
            {
                "prompt": bundle.prompts[int(idx)],
                "score": round(float(value), 4),
            }
            for value, idx in zip(sorted_values[:3], sorted_indices[:3])
        ]

    return scores, prompt_debug


def _rerank_scores(
    scores: dict[str, float],
    bundles: list[TagPromptBundle],
    rerank_mode: str,
) -> tuple[dict[str, float], dict[str, dict[str, Any]]]:
    if rerank_mode == "none":
        return dict(scores), {}
    if rerank_mode != "calibrated":
        raise ValueError(f"rerank_mode necunoscut: {rerank_mode}")

    bundle_by_slug = {bundle.slug: bundle for bundle in bundles}
    reranked: dict[str, float] = {}
    diagnostics: dict[str, dict[str, Any]] = {}

    for bundle in bundles:
        raw_score = float(scores[bundle.slug])
        evidence_score = raw_score
        evidence_source = "raw"
        evidence_reason = None

        if bundle.slug in CHILD_TO_PARENT_ALLOWED_SLUGS:
            for child_slug in bundle.child_slugs:
                child_score = scores.get(child_slug)
                if child_score is None:
                    continue
                candidate = float(child_score) * CHILD_TO_PARENT_INHERITANCE
                if candidate > evidence_score:
                    evidence_score = candidate
                    evidence_source = child_slug
                    evidence_reason = "child_to_parent"

        if (
            bundle.parent_slug
            and bundle.parent_slug in PARENT_TO_CHILD_ALLOWED_SLUGS
            and bundle.parent_slug in scores
        ):
            parent_score = float(scores[bundle.parent_slug])
            candidate = parent_score * PARENT_TO_CHILD_INHERITANCE
            if (
                candidate > evidence_score
                and raw_score >= parent_score * PARENT_TO_CHILD_MIN_RATIO
            ):
                evidence_score = candidate
                evidence_source = bundle.parent_slug
                evidence_reason = "parent_to_child"

        for source_slug, multiplier in VISUAL_AFFINITY_BOOSTS.get(bundle.slug, {}).items():
            source_score = scores.get(source_slug)
            if source_score is None:
                continue
            candidate = float(source_score) * multiplier
            if candidate > evidence_score:
                evidence_score = candidate
                evidence_source = source_slug
                evidence_reason = f"visual_affinity:{multiplier:.2f}"

        score_multiplier = TAG_SCORE_MULTIPLIERS.get(bundle.slug, 1.0)
        final_score = evidence_score * score_multiplier
        reranked[bundle.slug] = final_score

        if final_score != raw_score or evidence_source != "raw":
            diagnostics[bundle.slug] = {
                "raw_score": round(raw_score, 4),
                "evidence_score": round(evidence_score, 4),
                "final_score": round(final_score, 4),
                "score_multiplier": score_multiplier,
                "evidence_source": evidence_source,
                "evidence_reason": evidence_reason,
                "parent_slug": bundle.parent_slug,
                "is_leaf": bundle.is_leaf,
                "category": bundle.category,
            }

    missing_slugs = set(scores) - set(bundle_by_slug)
    for slug in missing_slugs:
        reranked[slug] = float(scores[slug])

    return reranked, diagnostics


def _top_scores(scores: dict[str, float], top_n: int) -> dict[str, float]:
    return {
        slug: round(float(score), 4)
        for slug, score in sorted(scores.items(), key=lambda item: item[1], reverse=True)[:top_n]
    }


def run_prompt_pipeline(
    dataset_path: Path = DEFAULT_DATASET_PATH,
    output_path: Path = OUTPUT_JSON,
    limit: int | None = None,
    only: str | None = None,
    top_n: int = TOP_N,
    leaf_only: bool = False,
    score_mode: str = SCORE_MODE,
    rerank_mode: str = RERANK_MODE,
    text_batch_size: int = 128,
) -> dict[str, Any]:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    dataset = _load_dataset(dataset_path)
    images = _select_images(dataset["images"], limit=limit, only=only)

    bundles = _load_tag_bundles(leaf_only=leaf_only)
    if not bundles:
        raise RuntimeError("Nu exista taguri pentru prompt pipeline.")

    started = time.time()
    log.info(f"Encoding {sum(len(b.prompts) for b in bundles)} prompts for {len(bundles)} tags...")
    text_features, tag_prompt_ranges, _all_prompts = _encode_text_prompts(
        bundles=bundles,
        batch_size=text_batch_size,
    )

    results = []
    for index, sample in enumerate(images, start=1):
        image_path = STATIC_IMAGES_DIR / sample["file"]
        log.info(f"[{index}/{len(images)}] {sample['file']}")
        image_started = time.time()
        image_features = _encode_image(image_path)
        scores, prompt_debug = _score_tags(
            image_features=image_features,
            text_features=text_features,
            bundles=bundles,
            tag_prompt_ranges=tag_prompt_ranges,
            score_mode=score_mode,
        )
        reranked_scores, rerank_debug = _rerank_scores(
            scores=scores,
            bundles=bundles,
            rerank_mode=rerank_mode,
        )
        top_scores = _top_scores(reranked_scores, top_n=top_n)
        raw_top_scores = _top_scores(scores, top_n=top_n)
        top_debug = {slug: prompt_debug[slug] for slug in top_scores}
        top_rerank_debug = {
            slug: rerank_debug[slug]
            for slug in top_scores
            if slug in rerank_debug
        }

        results.append(
            {
                "id": sample["id"],
                "file": sample["file"],
                "category": sample["category"],
                "image_path": _display_path(image_path),
                "expected_tags": sample["expected_tags"],
                "matched_db_tags": top_scores,
                "direct_tag_scores": top_scores,
                "raw_tag_scores": raw_top_scores,
                "top_prompt_matches": top_debug,
                "rerank_adjustments": top_rerank_debug,
                "processing_time_sec": round(time.time() - image_started, 2),
                "notes": sample["notes"],
            }
        )

    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "description": "Prompt-based direct multi-tag image recognition over TripCraft DB tags.",
        "command": f"python -m evaluation.run_image_prompt_pipeline --score-mode {score_mode} --rerank-mode {rerank_mode}",
        "dataset": {
            "path": _display_path(dataset_path),
            "version": dataset.get("version"),
            "name": dataset.get("name"),
            "total_images": len(dataset["images"]),
            "selected_images": len(images),
        },
        "model": "openai/clip-vit-large-patch14",
        "pipeline": {
            "name": "prompt_multitag",
            "score_mode": score_mode,
            "rerank_mode": rerank_mode,
            "leaf_only": leaf_only,
            "top_n": top_n,
            "num_tags_scored": len(bundles),
            "num_prompts": sum(len(bundle.prompts) for bundle in bundles),
            "manual_prompt_hints": len(TAG_VISUAL_HINTS),
        },
        "num_images": len(results),
        "processing_time_sec": round(time.time() - started, 2),
        "results": results,
    }

    output_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    return payload


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Ruleaza pipeline-ul direct prompt multi-tag.")
    parser.add_argument("--dataset", default=str(DEFAULT_DATASET_PATH), help="Manifest JSON cu imagini.")
    parser.add_argument("--output", default=str(OUTPUT_JSON), help="Fisier JSON pentru predictii.")
    parser.add_argument("--limit", type=int, default=None, help="Proceseaza doar primele N imagini.")
    parser.add_argument("--only", default=None, help="ID-uri sau filename stems separate prin virgula.")
    parser.add_argument("--top-n", type=int, default=TOP_N, help="Cate taguri prezise se salveaza per imagine.")
    parser.add_argument("--leaf-only", action="store_true", help="Scoreaza doar tagurile leaf din DB.")
    parser.add_argument(
        "--score-mode",
        choices=["max", "mean", "top2_mean"],
        default=SCORE_MODE,
        help="Cum agregam scorurile prompturilor pentru un tag.",
    )
    parser.add_argument(
        "--rerank-mode",
        choices=["none", "calibrated"],
        default=RERANK_MODE,
        help="Cum recalibram scorurile dupa scoring-ul CLIP brut.",
    )
    parser.add_argument("--text-batch-size", type=int, default=128, help="Batch size pentru text embeddings.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    payload = run_prompt_pipeline(
        dataset_path=Path(args.dataset),
        output_path=Path(args.output),
        limit=args.limit,
        only=args.only,
        top_n=args.top_n,
        leaf_only=args.leaf_only,
        score_mode=args.score_mode,
        rerank_mode=args.rerank_mode,
        text_batch_size=args.text_batch_size,
    )
    print(
        "Saved {path} ({images} images, {tags} tags, {prompts} prompts, rerank={rerank}, {seconds}s)".format(
            path=args.output,
            images=payload["num_images"],
            tags=payload["pipeline"]["num_tags_scored"],
            prompts=payload["pipeline"]["num_prompts"],
            rerank=payload["pipeline"]["rerank_mode"],
            seconds=payload["processing_time_sec"],
        )
    )


if __name__ == "__main__":
    main()
