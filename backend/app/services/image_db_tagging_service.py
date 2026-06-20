"""
Serviciu pentru extragerea directa a tagurilor TripCraft din pozele userului.

Foloseste acelasi CLIP ViT-L/14 deja incarcat in aplicatie, dar in loc sa
scoreze concepte generice si apoi sa le mapeze semantic, scoreaza direct
tagurile din DB prin prompturi multiple si reranking calibrat.
"""

from __future__ import annotations

import io
import logging
import math
import threading
import time
from collections import Counter
from pathlib import Path
from typing import Any

import torch
from PIL import Image
from sqlalchemy.orm import Session

from app.models.tag import Tag
from app.services.clip_service import clip_service

# Refolosim configuratia calibrata validata in benchmark. Pe termen lung,
# aceste constante pot fi mutate intr-un modul comun app/evaluation.
from evaluation.run_image_prompt_pipeline import (
    RERANK_MODE,
    SCORE_MODE,
    _build_prompts_for_tag,
    _encode_text_prompts,
    _rerank_scores,
    _score_tags,
    _tensor_from_model_output,
    _top_scores,
)


logger = logging.getLogger(__name__)

TEXT_BATCH_SIZE = 128
PER_IMAGE_TOP_N = 20
PROFILE_TOP_N = 15
MIN_PROFILE_TAGS = 5
PROFILE_CONFIDENCE_FLOOR = 0.32
PROFILE_SCORE_FLOOR = 0.38


class ImageDbTaggingService:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._cache_signature: tuple[tuple[str, int | None], ...] | None = None
        self._bundles = None
        self._text_features = None
        self._tag_prompt_ranges = None
        self._root_slugs: set[str] = set()

    def _tag_signature(self, tags: list[Tag]) -> tuple[tuple[str, int | None], ...]:
        return tuple((tag.slug, tag.parent_id) for tag in tags)

    def _ensure_prompt_cache(self, db: Session) -> None:
        tags = db.query(Tag).order_by(Tag.slug.asc()).all()
        signature = self._tag_signature(tags)

        with self._lock:
            if (
                self._cache_signature == signature
                and self._bundles is not None
                and self._text_features is not None
                and self._tag_prompt_ranges is not None
            ):
                return

            started = time.time()
            bundles = [_build_prompts_for_tag(tag) for tag in tags]
            text_features, tag_prompt_ranges, _ = _encode_text_prompts(
                bundles=bundles,
                batch_size=TEXT_BATCH_SIZE,
            )
            self._cache_signature = signature
            self._bundles = bundles
            self._text_features = text_features
            self._tag_prompt_ranges = tag_prompt_ranges
            self._root_slugs = {tag.slug for tag in tags if tag.parent_id is None}
            logger.info(
                "Cached %s image-tag prompts for %s DB tags in %.2fs",
                sum(len(bundle.prompts) for bundle in bundles),
                len(bundles),
                time.time() - started,
            )

    def preload(self, db: Session) -> None:
        self._ensure_prompt_cache(db)

    def _encode_image_bytes(self, image_bytes: bytes) -> torch.Tensor:
        clip_service._load_model()
        image = Image.open(io.BytesIO(image_bytes)).convert("RGB")
        inputs = clip_service._processor(images=image, return_tensors="pt")
        with torch.no_grad():
            features = _tensor_from_model_output(clip_service._model.get_image_features(**inputs))
        features = features / features.norm(dim=-1, keepdim=True).clamp_min(1e-12)
        return features.cpu()[0]

    def _score_image(self, image_bytes: bytes) -> tuple[dict[str, float], dict[str, float]]:
        image_features = self._encode_image_bytes(image_bytes)
        raw_scores, _prompt_debug = _score_tags(
            image_features=image_features,
            text_features=self._text_features,
            bundles=self._bundles,
            tag_prompt_ranges=self._tag_prompt_ranges,
            score_mode=SCORE_MODE,
        )
        reranked_scores, _rerank_debug = _rerank_scores(
            scores=raw_scores,
            bundles=self._bundles,
            rerank_mode=RERANK_MODE,
        )
        return raw_scores, reranked_scores

    def _image_confidences(self, scores: dict[str, float]) -> dict[str, float]:
        top_items = sorted(scores.items(), key=lambda item: item[1], reverse=True)[:PER_IMAGE_TOP_N]
        if not top_items:
            return {}

        high = float(top_items[0][1])
        low = float(top_items[-1][1])
        span = max(high - low, 1e-6)
        confidences = {}

        for rank, (slug, score) in enumerate(top_items, start=1):
            relative = (float(score) - low) / span
            rank_weight = 1.0 / math.sqrt(rank)
            confidence = max(0.0, min(1.0, 0.75 * relative + 0.25 * rank_weight))
            if confidence >= PROFILE_CONFIDENCE_FLOOR:
                confidences[slug] = round(confidence, 4)

        return confidences

    def _aggregate_profile(self, per_image_confidences: list[dict[str, float]]) -> dict[str, float]:
        values_by_slug: dict[str, list[float]] = {}
        for confidences in per_image_confidences:
            for slug, confidence in confidences.items():
                if slug in self._root_slugs:
                    continue
                values_by_slug.setdefault(slug, []).append(float(confidence))

        if not values_by_slug:
            return {}

        num_images = max(1, len(per_image_confidences))
        aggregated = {}
        for slug, values in values_by_slug.items():
            max_score = max(values)
            mean_score = sum(values) / len(values)
            frequency = len(values) / num_images
            score = 0.58 * max_score + 0.27 * mean_score + 0.15 * math.sqrt(frequency)
            aggregated[slug] = round(min(score, 1.0), 4)

        ranked = sorted(aggregated.items(), key=lambda item: item[1], reverse=True)
        selected = [
            (slug, score)
            for slug, score in ranked
            if score >= PROFILE_SCORE_FLOOR
        ][:PROFILE_TOP_N]

        if len(selected) < MIN_PROFILE_TAGS:
            selected = ranked[: min(MIN_PROFILE_TAGS, len(ranked))]

        return dict(selected)

    def _scene_summary(self, scene_results: list[dict[str, Any]], season_results: list[dict[str, Any]]) -> dict[str, Any]:
        def majority(values: list[Any]) -> Any:
            return Counter(values).most_common(1)[0][0] if values else None

        return {
            "setting": majority([scene["setting"] for scene in scene_results]),
            "environment": majority([scene["environment"] for scene in scene_results]),
            "crowding": majority([scene["crowding"] for scene in scene_results]),
            "time_of_day": majority([scene["time_of_day"] for scene in scene_results]),
            "has_landmark": any(scene["has_landmark"] for scene in scene_results),
            "has_food": any(scene["has_food"] for scene in scene_results),
            "has_beach": any(scene["has_beach"] for scene in scene_results),
            "has_mountain": any(scene["has_mountain"] for scene in scene_results),
            "dominant_season": majority([season["dominant_season"] for season in season_results]),
        }

    def analyze_user_photos(self, db: Session, files_data: list[dict[str, Any]]) -> dict[str, Any]:
        if not files_data:
            raise ValueError("Trebuie trimisa cel putin o imagine.")
        if len(files_data) > 5:
            raise ValueError("Maximum 5 images allowed")

        total_started = time.time()
        self._ensure_prompt_cache(db)

        per_image_results = []
        per_image_confidences = []
        scene_results = []
        season_results = []

        for index, file_data in enumerate(files_data, start=1):
            filename = file_data.get("filename") or f"photo_{index}.jpg"
            contents = file_data["contents"]
            image_started = time.time()

            try:
                raw_scores, reranked_scores = self._score_image(contents)
            except Exception as exc:
                raise ValueError(f"Nu am putut procesa imaginea {filename}: {exc}") from exc

            top_scores = _top_scores(reranked_scores, PER_IMAGE_TOP_N)
            raw_top_scores = _top_scores(raw_scores, PER_IMAGE_TOP_N)
            confidences = self._image_confidences(reranked_scores)
            per_image_confidences.append(confidences)

            scene = clip_service.analyze_scene(contents)
            season = clip_service.estimate_season(contents)
            scene_results.append(scene)
            season_results.append(season)

            per_image_results.append(
                {
                    "filename": filename,
                    "matched_db_tags": top_scores,
                    "raw_tag_scores": raw_top_scores,
                    "profile_confidences": confidences,
                    "scene": scene,
                    "season": season,
                    "processing_time_sec": round(time.time() - image_started, 2),
                }
            )

        profile = self._aggregate_profile(per_image_confidences)
        return {
            "pipeline": {
                "name": "db_prompt_multitag",
                "model": "openai/clip-vit-large-patch14",
                "score_mode": SCORE_MODE,
                "rerank_mode": RERANK_MODE,
                "max_images": 5,
            },
            "matched_db_tags": profile,
            "detected_tags": profile,
            "per_image": per_image_results,
            "scene_analysis": self._scene_summary(scene_results, season_results),
            "num_images_analyzed": len(files_data),
            "processing_time": round(time.time() - total_started, 2),
        }


image_db_tagging_service = ImageDbTaggingService()
