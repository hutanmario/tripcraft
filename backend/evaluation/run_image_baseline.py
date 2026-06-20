#!/usr/bin/env python3
"""
Baseline pentru recunoasterea imaginilor TripCraft.

Ruleaza pipeline-ul actual CLIP -> agregare -> mapping DB pe un manifest local
de imagini din static/quiz_images, fara sa creeze sesiuni in baza de date.

Rulare (din directorul backend/):
    python -m evaluation.run_image_baseline

Rulare rapida:
    python -m evaluation.run_image_baseline --limit 3

Rezultatele se salveaza in backend/evaluation/results/.
"""

from __future__ import annotations

import argparse
import csv
import json
import logging
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from statistics import mean
from typing import Any

import numpy as np
from sentence_transformers import util as st_util


BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.database import SessionLocal
from app.models.tag import Tag
from app.routers.ml import _BLACKLISTED_SLUGS, _CLIP_OVERRIDE_MAP, get_st_model
from app.services.clip_service import clip_service


RESULTS_DIR = Path(__file__).resolve().parent / "results"
STATIC_IMAGES_DIR = BACKEND_DIR / "static" / "quiz_images"

OUTPUT_JSON = RESULTS_DIR / "image_baseline_current.json"
OUTPUT_CSV = RESULTS_DIR / "image_baseline_current.csv"
OUTPUT_MD = RESULTS_DIR / "SUMMARY_IMAGE_BASELINE.md"
DEFAULT_DATASET_PATH = Path(__file__).resolve().parent / "image_recognition_dataset.json"

TOP_K = 15


logging.basicConfig(level=logging.WARNING)
log = logging.getLogger("image_baseline")
log.setLevel(logging.INFO)
log.propagate = False
handler = logging.StreamHandler()
handler.setFormatter(logging.Formatter("%(message)s"))
log.addHandler(handler)


def _round_scores(scores: dict[str, float], digits: int = 4) -> dict[str, float]:
    return {key: round(float(value), digits) for key, value in scores.items()}


def _sorted_scores(scores: dict[str, float], limit: int | None = None) -> dict[str, float]:
    items = sorted(scores.items(), key=lambda item: item[1], reverse=True)
    if limit is not None:
        items = items[:limit]
    return _round_scores(dict(items))


def _display_path(path: Path) -> str:
    try:
        return str(path.relative_to(BACKEND_DIR)).replace("\\", "/")
    except ValueError:
        return str(path)


def _load_dataset(dataset_path: Path) -> dict[str, Any]:
    if not dataset_path.exists():
        raise FileNotFoundError(f"Datasetul de imagini nu exista: {dataset_path}")

    payload = json.loads(dataset_path.read_text(encoding="utf-8"))
    images = payload.get("images")
    if not isinstance(images, list) or not images:
        raise ValueError("Datasetul trebuie sa contina o lista nevida `images`.")

    normalized = []
    seen_ids = set()
    for index, item in enumerate(images, start=1):
        if not isinstance(item, dict):
            raise ValueError(f"Imaginea #{index} din dataset nu este un obiect JSON.")

        file_name = item.get("file")
        if not isinstance(file_name, str) or not file_name:
            raise ValueError(f"Imaginea #{index} nu are campul `file` valid.")

        expected_tags = item.get("expected_tags")
        if not isinstance(expected_tags, list) or not expected_tags:
            raise ValueError(f"Imaginea {file_name} nu are `expected_tags` valid.")

        image_id = item.get("id") or Path(file_name).stem.replace("-", "_")
        if image_id in seen_ids:
            raise ValueError(f"ID duplicat in dataset: {image_id}")
        seen_ids.add(image_id)

        normalized.append(
            {
                **item,
                "id": image_id,
                "file": file_name,
                "expected_tags": list(dict.fromkeys(expected_tags)),
                "category": item.get("category", "uncategorized"),
                "notes": item.get("notes", ""),
            }
        )

    payload["images"] = normalized
    return payload


def _validate_samples(samples: list[dict[str, Any]], db_slugs: set[str]) -> None:
    missing_files = []
    missing_tags = []

    for sample in samples:
        image_path = STATIC_IMAGES_DIR / sample["file"]
        if not image_path.exists():
            missing_files.append(str(image_path))

        for tag in sample["expected_tags"]:
            if tag not in db_slugs:
                missing_tags.append(f"{sample['id']} -> {tag}")

    if missing_files or missing_tags:
        details = []
        if missing_files:
            details.append("Fisiere lipsa:\n" + "\n".join(f"- {path}" for path in missing_files))
        if missing_tags:
            details.append("Taguri lipsa din DB:\n" + "\n".join(f"- {tag}" for tag in missing_tags))
        raise ValueError("\n\n".join(details))


def _add_score(
    tag_sum: dict[str, float],
    tag_count: dict[str, float],
    tag: str,
    score: float,
    count_weight: float,
) -> None:
    tag_sum[tag] = tag_sum.get(tag, 0.0) + float(score)
    tag_count[tag] = tag_count.get(tag, 0.0) + float(count_weight)


def _aggregate_current_pipeline(image_bytes: bytes, top_k: int) -> dict[str, Any]:
    """Replica partea de scorare din _run_clip_analysis pentru o singura imagine."""
    started = time.time()
    tag_sum: dict[str, float] = {}
    tag_count: dict[str, float] = {}

    raw_tags = clip_service.tag_image_from_bytes(image_bytes, top_k=top_k)
    for tag, score in raw_tags.items():
        _add_score(tag_sum, tag_count, tag, score, 1.0)

    scene = clip_service.analyze_scene(image_bytes)

    colors = clip_service.extract_dominant_colors(image_bytes)
    for tag, boost in colors["preference_boosts"].items():
        _add_score(tag_sum, tag_count, tag, boost * 0.5, 0.3)

    season = clip_service.estimate_season(image_bytes)
    for tag, boost in season["tag_boosts"].items():
        _add_score(tag_sum, tag_count, tag, boost * 0.4, 0.2)

    aggregated_scores = {}
    for tag in tag_sum:
        if tag_count[tag] <= 0:
            continue
        avg_when_present = tag_sum[tag] / tag_count[tag]
        frequency = min(tag_count[tag], 1.0)
        aggregated_scores[tag] = avg_when_present * (frequency ** 0.5)

    if aggregated_scores:
        values = list(aggregated_scores.values())
        mean_s = float(np.mean(values))
        std_s = float(np.std(values))
        adaptive_threshold = mean_s + 0.5 * std_s
        significant_tags = {
            tag: score
            for tag, score in aggregated_scores.items()
            if score > adaptive_threshold
        }
        if len(significant_tags) < 3:
            significant_tags = dict(
                sorted(aggregated_scores.items(), key=lambda item: item[1], reverse=True)[:3]
            )
    else:
        mean_s = 0.0
        std_s = 0.0
        adaptive_threshold = 0.0
        significant_tags = {}

    return {
        "raw_clip_tags": _sorted_scores(raw_tags),
        "aggregated_scores": _sorted_scores(aggregated_scores, limit=top_k),
        "significant_tags": _sorted_scores(significant_tags),
        "adaptive_threshold": round(float(adaptive_threshold), 4),
        "aggregated_mean": round(float(mean_s), 4),
        "aggregated_std": round(float(std_s), 4),
        "scene_analysis": scene,
        "dominant_colors": colors["dominant_colors"][:5],
        "color_preference_boosts": _sorted_scores(colors["preference_boosts"]),
        "season_analysis": {
            "dominant_season": season["dominant_season"],
            "season_scores": _round_scores(season["season_scores"]),
            "tag_boosts": _round_scores(season["tag_boosts"]),
        },
        "processing_time_sec": round(time.time() - started, 2),
    }


def _load_db_mapping(db) -> tuple[list[str], list[str], Any]:
    db_tags = db.query(Tag).all()
    db_slugs = [tag.slug for tag in db_tags]
    db_names = [
        tag.name if getattr(tag, "name", None) else tag.slug.replace("-", " ")
        for tag in db_tags
    ]

    model = get_st_model()
    db_embeddings = model.encode(db_names, convert_to_tensor=True)
    return db_slugs, db_names, db_embeddings


def _load_db_slugs() -> set[str]:
    db = SessionLocal()
    try:
        return {tag.slug for tag in db.query(Tag).all()}
    finally:
        db.close()


def _map_to_db_tags(
    significant_tags: dict[str, float],
    db_slugs: list[str],
    db_embeddings: Any,
) -> tuple[dict[str, float], list[dict[str, Any]]]:
    """Replica mapping-ul curent din ml.py, dar intoarce si detalii de debug."""
    model = get_st_model()
    tag_scores: dict[str, float] = {}
    mapping_debug: list[dict[str, Any]] = []

    for clip_tag, score in significant_tags.items():
        clip_embedding = model.encode(clip_tag.replace("-", " "), convert_to_tensor=True)
        similarities = st_util.cos_sim(clip_embedding, db_embeddings)[0]
        best_idx = int(similarities.argmax())
        best_score = float(similarities[best_idx])
        best_slug = db_slugs[best_idx]

        mapped = False
        if best_score > 0.35:
            tag_scores[best_slug] = max(tag_scores.get(best_slug, 0.0), round(float(score), 4))
            mapped = True

        mapping_debug.append(
            {
                "clip_tag": clip_tag,
                "clip_score": round(float(score), 4),
                "best_db_slug": best_slug,
                "semantic_similarity": round(best_score, 4),
                "mapped": mapped,
            }
        )

    for clip_tag, db_slug in _CLIP_OVERRIDE_MAP.items():
        if clip_tag not in significant_tags:
            continue
        score = significant_tags[clip_tag]
        tag_scores[db_slug] = max(tag_scores.get(db_slug, 0.0), round(float(score), 4))
        wrong_slugs = [
            slug
            for slug in list(tag_scores.keys())
            if slug != db_slug and clip_tag in slug
        ]
        for slug in wrong_slugs:
            del tag_scores[slug]

        mapping_debug.append(
            {
                "clip_tag": clip_tag,
                "clip_score": round(float(score), 4),
                "best_db_slug": db_slug,
                "semantic_similarity": None,
                "mapped": True,
                "source": "manual_override",
            }
        )

    tag_scores = {
        slug: score
        for slug, score in tag_scores.items()
        if slug not in _BLACKLISTED_SLUGS
    }
    return _sorted_scores(tag_scores), mapping_debug


def _metrics(expected_tags: list[str], predicted_scores: dict[str, float]) -> dict[str, Any]:
    expected = set(expected_tags)
    predicted = list(predicted_scores.keys())

    def precision_at(k: int) -> float:
        if k <= 0:
            return 0.0
        return len(set(predicted[:k]) & expected) / k

    def recall_at(k: int) -> float:
        if not expected:
            return 0.0
        return len(set(predicted[:k]) & expected) / len(expected)

    return {
        "hits_all": sorted(set(predicted) & expected),
        "hits_at_5": sorted(set(predicted[:5]) & expected),
        "precision_at_3": round(precision_at(3), 4),
        "precision_at_5": round(precision_at(5), 4),
        "recall_at_5": round(recall_at(5), 4),
    }


def _select_samples(
    samples: list[dict[str, Any]],
    limit: int | None,
    only: str | None,
) -> list[dict[str, Any]]:
    if only:
        wanted = {item.strip() for item in only.split(",") if item.strip()}
        samples = [
            item
            for item in samples
            if item["id"] in wanted or Path(item["file"]).stem in wanted
        ]
    if limit is not None:
        samples = samples[:limit]
    return samples


def run_baseline(
    dataset_path: Path = DEFAULT_DATASET_PATH,
    limit: int | None = None,
    only: str | None = None,
    top_k: int = TOP_K,
) -> dict[str, Any]:
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    dataset_path = dataset_path.resolve()
    dataset = _load_dataset(dataset_path)
    samples = _select_samples(dataset["images"], limit=limit, only=only)
    if not samples:
        raise RuntimeError("Nu exista imagini selectate pentru baseline.")

    db = SessionLocal()
    try:
        db_slugs, _db_names, db_embeddings = _load_db_mapping(db)
    finally:
        db.close()
    _validate_samples(samples, set(db_slugs))

    results = []
    started = time.time()

    for index, sample in enumerate(samples, start=1):
        image_path = STATIC_IMAGES_DIR / sample["file"]
        if not image_path.exists():
            raise FileNotFoundError(f"Lipseste imaginea de baseline: {image_path}")

        log.info(f"[{index}/{len(samples)}] {sample['file']}")
        image_bytes = image_path.read_bytes()
        pipeline = _aggregate_current_pipeline(image_bytes, top_k=top_k)
        matched_db_tags, mapping_debug = _map_to_db_tags(
            pipeline["significant_tags"],
            db_slugs=db_slugs,
            db_embeddings=db_embeddings,
        )
        metrics = _metrics(sample["expected_tags"], matched_db_tags)

        results.append(
            {
                "id": sample["id"],
                "file": sample["file"],
                "category": sample["category"],
                "image_path": str(image_path.relative_to(BACKEND_DIR)).replace("\\", "/"),
                "expected_tags": sample["expected_tags"],
                "raw_clip_tags": pipeline["raw_clip_tags"],
                "aggregated_scores": pipeline["aggregated_scores"],
                "adaptive_threshold": pipeline["adaptive_threshold"],
                "significant_tags": pipeline["significant_tags"],
                "matched_db_tags": matched_db_tags,
                "mapping_debug": mapping_debug,
                "scene_analysis": pipeline["scene_analysis"],
                "dominant_colors": pipeline["dominant_colors"],
                "color_preference_boosts": pipeline["color_preference_boosts"],
                "season_analysis": pipeline["season_analysis"],
                "metrics": metrics,
                "processing_time_sec": pipeline["processing_time_sec"],
                "notes": sample["notes"],
            }
        )

    precision_3_values = [item["metrics"]["precision_at_3"] for item in results]
    precision_5_values = [item["metrics"]["precision_at_5"] for item in results]
    recall_5_values = [item["metrics"]["recall_at_5"] for item in results]

    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "description": "Baseline curent pentru pipeline-ul CLIP din TripCraft.",
        "command": f"python -m evaluation.run_image_baseline --dataset {_display_path(dataset_path)}",
        "dataset": {
            "path": _display_path(dataset_path),
            "version": dataset.get("version"),
            "name": dataset.get("name"),
            "description": dataset.get("description"),
            "total_images": len(dataset["images"]),
            "selected_images": len(samples),
        },
        "model": "openai/clip-vit-large-patch14",
        "top_k": top_k,
        "num_images": len(results),
        "processing_time_sec": round(time.time() - started, 2),
        "summary": {
            "mean_precision_at_3": round(mean(precision_3_values), 4),
            "mean_precision_at_5": round(mean(precision_5_values), 4),
            "mean_recall_at_5": round(mean(recall_5_values), 4),
        },
        "results": results,
    }

    OUTPUT_JSON.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    _write_csv(results)
    _write_markdown(payload)
    return payload


def validate_dataset(dataset_path: Path = DEFAULT_DATASET_PATH) -> dict[str, Any]:
    dataset_path = dataset_path.resolve()
    dataset = _load_dataset(dataset_path)
    _validate_samples(dataset["images"], _load_db_slugs())
    return {
        "path": _display_path(dataset_path),
        "version": dataset.get("version"),
        "name": dataset.get("name"),
        "num_images": len(dataset["images"]),
    }


def _write_csv(results: list[dict[str, Any]]) -> None:
    with OUTPUT_CSV.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "id",
                "category",
                "file",
                "expected_tags",
                "raw_clip_top5",
                "significant_tags",
                "matched_db_tags",
                "hits_at_5",
                "precision_at_3",
                "precision_at_5",
                "recall_at_5",
                "scene",
                "dominant_season",
                "processing_time_sec",
                "notes",
            ],
        )
        writer.writeheader()
        for item in results:
            scene = item["scene_analysis"]
            season = item["season_analysis"]
            metrics = item["metrics"]
            writer.writerow(
                {
                    "id": item["id"],
                    "category": item["category"],
                    "file": item["file"],
                    "expected_tags": ", ".join(item["expected_tags"]),
                    "raw_clip_top5": ", ".join(list(item["raw_clip_tags"].keys())[:5]),
                    "significant_tags": ", ".join(item["significant_tags"].keys()),
                    "matched_db_tags": ", ".join(item["matched_db_tags"].keys()),
                    "hits_at_5": ", ".join(metrics["hits_at_5"]),
                    "precision_at_3": metrics["precision_at_3"],
                    "precision_at_5": metrics["precision_at_5"],
                    "recall_at_5": metrics["recall_at_5"],
                    "scene": f"{scene['setting']}/{scene['environment']}/{scene['time_of_day']}",
                    "dominant_season": season["dominant_season"],
                    "processing_time_sec": item["processing_time_sec"],
                    "notes": item["notes"],
                }
            )


def _write_markdown(payload: dict[str, Any]) -> None:
    summary = payload["summary"]
    dataset = payload["dataset"]
    lines = [
        "# Image Recognition Baseline",
        "",
        f"Generated at: `{payload['generated_at']}`",
        "",
        "## Dataset",
        "",
        f"- Path: `{dataset['path']}`",
        f"- Version: `{dataset['version']}`",
        f"- Total images in manifest: `{dataset['total_images']}`",
        f"- Selected images in run: `{dataset['selected_images']}`",
        "",
        "## Aggregate",
        "",
        f"- Images: `{payload['num_images']}`",
        f"- Mean precision@3: `{summary['mean_precision_at_3']}`",
        f"- Mean precision@5: `{summary['mean_precision_at_5']}`",
        f"- Mean recall@5: `{summary['mean_recall_at_5']}`",
        f"- Total processing time: `{payload['processing_time_sec']}s`",
        "",
        "## Per Image",
        "",
        "| Category | Image | Expected | Raw CLIP top 5 | Matched DB tags | Hits@5 | P@3 | R@5 |",
        "|---|---|---|---|---|---|---:|---:|",
    ]

    for item in payload["results"]:
        metrics = item["metrics"]
        lines.append(
            "| {category} | {file} | {expected} | {raw} | {matched} | {hits} | {p3} | {r5} |".format(
                category=item["category"],
                file=item["file"],
                expected=", ".join(item["expected_tags"]),
                raw=", ".join(list(item["raw_clip_tags"].keys())[:5]),
                matched=", ".join(item["matched_db_tags"].keys()) or "-",
                hits=", ".join(metrics["hits_at_5"]) or "-",
                p3=metrics["precision_at_3"],
                r5=metrics["recall_at_5"],
            )
        )

    lines.extend(
        [
            "",
            "## Files",
            "",
            f"- JSON: `{OUTPUT_JSON.name}`",
            f"- CSV: `{OUTPUT_CSV.name}`",
            "",
            "## Notes",
            "",
            "- `expected_tags` sunt repere manuale initiale, nu un dataset final validat.",
            "- Acest baseline masoara pipeline-ul curent, inclusiv mapping-ul semantic din `ml.py`.",
            "- Urmatorul pas este sa comparam acest baseline cu un pipeline multi-prompt pe tagurile reale.",
        ]
    )

    OUTPUT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Ruleaza baseline-ul curent de recunoastere imagini.")
    parser.add_argument(
        "--dataset",
        default=str(DEFAULT_DATASET_PATH),
        help="Manifest JSON cu imagini si expected_tags.",
    )
    parser.add_argument("--limit", type=int, default=None, help="Proceseaza doar primele N imagini.")
    parser.add_argument(
        "--only",
        default=None,
        help="Lista de id-uri sau filename stems separate prin virgula, ex: sandy_beaches,street_food.",
    )
    parser.add_argument("--top-k", type=int, default=TOP_K, help="Numar taguri brute CLIP pastrate.")
    parser.add_argument(
        "--validate-only",
        action="store_true",
        help="Valideaza manifestul si iese fara sa ruleze CLIP.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.validate_only:
        info = validate_dataset(Path(args.dataset))
        log.info(f"Dataset valid: {info['path']} ({info['num_images']} imagini)")
        return

    payload = run_baseline(
        dataset_path=Path(args.dataset),
        limit=args.limit,
        only=args.only,
        top_k=args.top_k,
    )
    summary = payload["summary"]
    log.info("")
    log.info(f"Saved JSON: {OUTPUT_JSON}")
    log.info(f"Saved CSV:  {OUTPUT_CSV}")
    log.info(f"Saved MD:   {OUTPUT_MD}")
    log.info(
        "Baseline: P@3={p3}, P@5={p5}, R@5={r5}".format(
            p3=summary["mean_precision_at_3"],
            p5=summary["mean_precision_at_5"],
            r5=summary["mean_recall_at_5"],
        )
    )


if __name__ == "__main__":
    main()
