#!/usr/bin/env python3
"""
Evaluator independent pentru recunoasterea pe imagini TripCraft.

Citeste un manifest de imagini etichetate si unul sau mai multe fisiere de
predictii. Nu ruleaza CLIP si nu atinge baza de date, deci poate evalua rapid
orice pipeline: baseline-ul actual, un pipeline multi-prompt sau variante viitoare.

Rulare standard (din directorul backend/):
    python -m evaluation.run_image_recognition_eval

Evaluare explicita:
    python -m evaluation.run_image_recognition_eval \
        --predictions evaluation/results/image_baseline_current.json \
        --name current

Evaluare pe alt camp de predictii, ex. tagurile brute CLIP:
    python -m evaluation.run_image_recognition_eval --prediction-key raw_clip_tags
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import statistics
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


EVAL_DIR = Path(__file__).resolve().parent
RESULTS_DIR = EVAL_DIR / "results"
DEFAULT_DATASET_PATH = EVAL_DIR / "image_recognition_dataset.json"
DEFAULT_PREDICTIONS_PATH = RESULTS_DIR / "image_baseline_current.json"
DEFAULT_PREDICTION_KEY = "matched_db_tags"
K_VALUES = (1, 3, 5, 10)


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"Fisierul nu exista: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def _display_path(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(EVAL_DIR.parents[0])).replace("\\", "/")
    except ValueError:
        return str(path)


def _mean(values: list[float]) -> float:
    return float(statistics.fmean(values)) if values else 0.0


def _round(value: float, digits: int = 4) -> float:
    return round(float(value), digits)


def _load_dataset(dataset_path: Path) -> dict[str, dict[str, Any]]:
    payload = _read_json(dataset_path)
    images = payload.get("images")
    if not isinstance(images, list) or not images:
        raise ValueError("Datasetul trebuie sa contina o lista nevida `images`.")

    by_id: dict[str, dict[str, Any]] = {}
    for index, image in enumerate(images, start=1):
        if not isinstance(image, dict):
            raise ValueError(f"Intrarea #{index} din dataset nu este obiect JSON.")

        image_id = image.get("id") or Path(str(image.get("file", ""))).stem.replace("-", "_")
        if not image_id:
            raise ValueError(f"Intrarea #{index} din dataset nu are `id` sau `file`.")
        if image_id in by_id:
            raise ValueError(f"ID duplicat in dataset: {image_id}")

        expected_tags = image.get("expected_tags")
        if not isinstance(expected_tags, list) or not expected_tags:
            raise ValueError(f"Imaginea {image_id} nu are `expected_tags` valid.")

        by_id[image_id] = {
            **image,
            "id": image_id,
            "file": image.get("file", ""),
            "category": image.get("category", "uncategorized"),
            "expected_tags": list(dict.fromkeys(expected_tags)),
            "notes": image.get("notes", ""),
        }
    return by_id


def _load_prediction_results(predictions_path: Path) -> tuple[dict[str, Any], dict[str, dict[str, Any]]]:
    payload = _read_json(predictions_path)
    results = payload.get("results")
    if not isinstance(results, list) or not results:
        raise ValueError("Fisierul de predictii trebuie sa contina o lista nevida `results`.")

    by_id: dict[str, dict[str, Any]] = {}
    for index, result in enumerate(results, start=1):
        if not isinstance(result, dict):
            raise ValueError(f"Predictia #{index} nu este obiect JSON.")

        result_id = result.get("id") or Path(str(result.get("file", ""))).stem.replace("-", "_")
        if not result_id:
            raise ValueError(f"Predictia #{index} nu are `id` sau `file`.")
        if result_id in by_id:
            raise ValueError(f"ID duplicat in predictii: {result_id}")

        by_id[result_id] = result
    return payload, by_id


def _prediction_items(result: dict[str, Any], prediction_key: str) -> list[tuple[str, float]]:
    value = result.get(prediction_key)
    if value is None:
        raise ValueError(f"Predictia {result.get('id')} nu contine campul `{prediction_key}`.")

    if isinstance(value, dict):
        return sorted(
            [(str(tag), float(score)) for tag, score in value.items()],
            key=lambda item: item[1],
            reverse=True,
        )

    if isinstance(value, list):
        items: list[tuple[str, float]] = []
        for rank, entry in enumerate(value, start=1):
            if isinstance(entry, str):
                items.append((entry, 1.0 / rank))
            elif isinstance(entry, dict):
                tag = entry.get("tag") or entry.get("slug") or entry.get("id")
                score = entry.get("score", 1.0 / rank)
                if tag:
                    items.append((str(tag), float(score)))
            else:
                raise ValueError(f"Format de predictie nesuportat: {entry!r}")
        return items

    raise ValueError(f"Campul `{prediction_key}` trebuie sa fie dict sau lista.")


def _unique_ranked_tags(items: list[tuple[str, float]]) -> list[str]:
    ranked = []
    seen = set()
    for tag, _score in items:
        if tag not in seen:
            ranked.append(tag)
            seen.add(tag)
    return ranked


def _dcg(relevance: list[int]) -> float:
    return sum(rel / math.log2(index + 2) for index, rel in enumerate(relevance))


def _ndcg_at_k(ranked: list[str], expected: set[str], k: int) -> float:
    relevance = [1 if tag in expected else 0 for tag in ranked[:k]]
    ideal_hits = min(len(expected), k)
    if ideal_hits == 0:
        return 0.0
    ideal = [1] * ideal_hits + [0] * max(0, k - ideal_hits)
    return _dcg(relevance) / _dcg(ideal)


def _average_precision_at_k(ranked: list[str], expected: set[str], k: int) -> float:
    if not expected:
        return 0.0
    hits = 0
    precision_sum = 0.0
    for rank, tag in enumerate(ranked[:k], start=1):
        if tag in expected:
            hits += 1
            precision_sum += hits / rank
    return precision_sum / min(len(expected), k)


def _mrr_at_k(ranked: list[str], expected: set[str], k: int) -> float:
    for rank, tag in enumerate(ranked[:k], start=1):
        if tag in expected:
            return 1.0 / rank
    return 0.0


def _per_image_metrics(dataset_item: dict[str, Any], prediction: dict[str, Any], prediction_key: str) -> dict[str, Any]:
    expected_tags = dataset_item["expected_tags"]
    expected = set(expected_tags)
    prediction_scores = _prediction_items(prediction, prediction_key)
    ranked = _unique_ranked_tags(prediction_scores)
    rank_by_tag = {tag: rank for rank, tag in enumerate(ranked, start=1)}

    row: dict[str, Any] = {
        "id": dataset_item["id"],
        "file": dataset_item["file"],
        "category": dataset_item["category"],
        "expected_tags": expected_tags,
        "predicted_tags": ranked,
        "predicted_count": len(ranked),
        "first_hit_rank": None,
        "missed_expected": [],
        "false_positive_top5": [],
    }

    for rank, tag in enumerate(ranked, start=1):
        if tag in expected:
            row["first_hit_rank"] = rank
            break

    for k in K_VALUES:
        top_k = ranked[:k]
        hits = [tag for tag in top_k if tag in expected]
        false_positive = [tag for tag in top_k if tag not in expected]
        precision = len(hits) / k
        recall = len(hits) / len(expected) if expected else 0.0
        f1 = (2 * precision * recall / (precision + recall)) if precision + recall else 0.0

        row[f"hits_at_{k}"] = hits
        row[f"hit_ranks_at_{k}"] = {tag: rank_by_tag[tag] for tag in hits}
        row[f"precision_at_{k}"] = precision
        row[f"recall_at_{k}"] = recall
        row[f"f1_at_{k}"] = f1
        row[f"hit_rate_at_{k}"] = 1.0 if hits else 0.0
        row[f"ndcg_at_{k}"] = _ndcg_at_k(ranked, expected, k)
        row[f"map_at_{k}"] = _average_precision_at_k(ranked, expected, k)
        row[f"mrr_at_{k}"] = _mrr_at_k(ranked, expected, k)
        if k == 5:
            row["false_positive_top5"] = false_positive

    row["missed_expected"] = [tag for tag in expected_tags if tag not in row["hits_at_5"]]
    return row


def _aggregate(rows: list[dict[str, Any]]) -> dict[str, Any]:
    total_expected = sum(len(row["expected_tags"]) for row in rows)
    aggregate: dict[str, Any] = {
        "num_images": len(rows),
        "total_expected_tags": total_expected,
        "mean_predicted_count": _round(_mean([row["predicted_count"] for row in rows])),
    }

    for k in K_VALUES:
        total_hits = sum(len(row[f"hits_at_{k}"]) for row in rows)
        aggregate[f"macro_precision_at_{k}"] = _round(_mean([row[f"precision_at_{k}"] for row in rows]))
        aggregate[f"macro_recall_at_{k}"] = _round(_mean([row[f"recall_at_{k}"] for row in rows]))
        aggregate[f"macro_f1_at_{k}"] = _round(_mean([row[f"f1_at_{k}"] for row in rows]))
        aggregate[f"hit_rate_at_{k}"] = _round(_mean([row[f"hit_rate_at_{k}"] for row in rows]))
        aggregate[f"mrr_at_{k}"] = _round(_mean([row[f"mrr_at_{k}"] for row in rows]))
        aggregate[f"map_at_{k}"] = _round(_mean([row[f"map_at_{k}"] for row in rows]))
        aggregate[f"ndcg_at_{k}"] = _round(_mean([row[f"ndcg_at_{k}"] for row in rows]))
        aggregate[f"micro_precision_at_{k}"] = _round(total_hits / (len(rows) * k) if rows else 0.0)
        aggregate[f"micro_recall_at_{k}"] = _round(total_hits / total_expected if total_expected else 0.0)

    aggregate["zero_hit_rate_at_5"] = _round(_mean([1.0 if not row["hits_at_5"] else 0.0 for row in rows]))
    aggregate["full_recall_rate_at_5"] = _round(_mean([1.0 if row["recall_at_5"] >= 1.0 else 0.0 for row in rows]))
    return aggregate


def _category_breakdown(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        groups[row["category"]].append(row)

    breakdown = []
    for category, items in sorted(groups.items()):
        summary = _aggregate(items)
        breakdown.append(
            {
                "category": category,
                "num_images": len(items),
                "precision_at_3": summary["macro_precision_at_3"],
                "recall_at_5": summary["macro_recall_at_5"],
                "f1_at_5": summary["macro_f1_at_5"],
                "hit_rate_at_5": summary["hit_rate_at_5"],
                "ndcg_at_5": summary["ndcg_at_5"],
                "zero_hit_rate_at_5": summary["zero_hit_rate_at_5"],
            }
        )
    return sorted(breakdown, key=lambda item: (item["recall_at_5"], item["precision_at_3"]))


def _tag_breakdown(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    expected_count = Counter()
    hit5_count = Counter()
    false_positive_top5_count = Counter()
    first_hit_ranks: dict[str, list[int]] = defaultdict(list)
    missed_images: dict[str, list[str]] = defaultdict(list)

    for row in rows:
        expected = set(row["expected_tags"])
        for tag in expected:
            expected_count[tag] += 1
        for tag, rank in row["hit_ranks_at_5"].items():
            hit5_count[tag] += 1
            first_hit_ranks[tag].append(int(rank))
        for tag in row["false_positive_top5"]:
            if tag not in expected:
                false_positive_top5_count[tag] += 1
        for tag in row["missed_expected"]:
            missed_images[tag].append(row["id"])

    tags = set(expected_count) | set(false_positive_top5_count)
    breakdown = []
    for tag in sorted(tags):
        exp = expected_count[tag]
        hit = hit5_count[tag]
        fp = false_positive_top5_count[tag]
        breakdown.append(
            {
                "tag": tag,
                "expected_count": exp,
                "hit_at_5_count": hit,
                "recall_at_5": _round(hit / exp if exp else 0.0),
                "false_positive_top5_count": fp,
                "mean_first_hit_rank": _round(_mean(first_hit_ranks[tag])) if first_hit_ranks[tag] else None,
                "missed_images": missed_images[tag],
            }
        )
    return sorted(
        breakdown,
        key=lambda item: (
            item["recall_at_5"],
            -item["expected_count"],
            -item["false_positive_top5_count"],
            item["tag"],
        ),
    )


def evaluate_predictions(
    dataset_path: Path,
    predictions_path: Path,
    prediction_key: str = DEFAULT_PREDICTION_KEY,
    name: str | None = None,
) -> dict[str, Any]:
    dataset = _load_dataset(dataset_path)
    prediction_payload, predictions = _load_prediction_results(predictions_path)

    missing_predictions = sorted(set(dataset) - set(predictions))
    extra_predictions = sorted(set(predictions) - set(dataset))
    if missing_predictions:
        raise ValueError("Lipsesc predictii pentru: " + ", ".join(missing_predictions[:20]))

    rows = [
        _per_image_metrics(dataset_item, predictions[image_id], prediction_key)
        for image_id, dataset_item in dataset.items()
    ]

    label = name or predictions_path.stem.replace("image_baseline_", "")
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "name": label,
        "prediction_key": prediction_key,
        "dataset": {
            "path": _display_path(dataset_path),
            "num_images": len(dataset),
        },
        "predictions": {
            "path": _display_path(predictions_path),
            "model": prediction_payload.get("model"),
            "generated_at": prediction_payload.get("generated_at"),
            "num_results": len(predictions),
            "extra_prediction_ids": extra_predictions,
        },
        "summary": _aggregate(rows),
        "category_breakdown": _category_breakdown(rows),
        "tag_breakdown": _tag_breakdown(rows),
        "per_image": rows,
    }


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")


def _write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str]) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            flat = {}
            for key in fieldnames:
                value = row.get(key)
                if isinstance(value, list):
                    flat[key] = ", ".join(str(item) for item in value)
                else:
                    flat[key] = value
            writer.writerow(flat)


def _write_outputs(payload: dict[str, Any], output_prefix: Path) -> dict[str, Path]:
    output_prefix.parent.mkdir(parents=True, exist_ok=True)

    json_path = output_prefix.with_suffix(".json")
    per_image_path = output_prefix.with_name(output_prefix.name + "_per_image.csv")
    category_path = output_prefix.with_name(output_prefix.name + "_by_category.csv")
    tag_path = output_prefix.with_name(output_prefix.name + "_by_tag.csv")
    failures_path = output_prefix.with_name(output_prefix.name + "_failures.csv")
    chart_path = output_prefix.with_name(output_prefix.name + "_category_recall.png")

    _write_json(json_path, payload)
    _write_csv(
        per_image_path,
        payload["per_image"],
        [
            "id",
            "category",
            "file",
            "expected_tags",
            "predicted_tags",
            "hits_at_5",
            "missed_expected",
            "false_positive_top5",
            "first_hit_rank",
            "precision_at_3",
            "precision_at_5",
            "recall_at_5",
            "f1_at_5",
            "mrr_at_5",
            "map_at_5",
            "ndcg_at_5",
        ],
    )
    _write_csv(
        category_path,
        payload["category_breakdown"],
        [
            "category",
            "num_images",
            "precision_at_3",
            "recall_at_5",
            "f1_at_5",
            "hit_rate_at_5",
            "ndcg_at_5",
            "zero_hit_rate_at_5",
        ],
    )
    _write_csv(
        tag_path,
        payload["tag_breakdown"],
        [
            "tag",
            "expected_count",
            "hit_at_5_count",
            "recall_at_5",
            "false_positive_top5_count",
            "mean_first_hit_rank",
            "missed_images",
        ],
    )

    failures = [
        row
        for row in payload["per_image"]
        if not row["hits_at_5"]
    ]
    _write_csv(
        failures_path,
        failures,
        [
            "id",
            "category",
            "file",
            "expected_tags",
            "predicted_tags",
            "missed_expected",
            "false_positive_top5",
            "precision_at_3",
            "recall_at_5",
        ],
    )

    _write_category_chart(payload["category_breakdown"], chart_path)
    return {
        "json": json_path,
        "per_image_csv": per_image_path,
        "category_csv": category_path,
        "tag_csv": tag_path,
        "failures_csv": failures_path,
        "category_chart": chart_path,
    }


def _write_category_chart(category_rows: list[dict[str, Any]], chart_path: Path) -> None:
    try:
        import matplotlib

        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except Exception:
        return

    if not category_rows:
        return

    rows = sorted(category_rows, key=lambda row: row["recall_at_5"])
    labels = [row["category"] for row in rows]
    recall = [row["recall_at_5"] for row in rows]
    precision = [row["precision_at_3"] for row in rows]

    fig, ax = plt.subplots(figsize=(10, max(4, len(rows) * 0.42)))
    y = range(len(rows))
    ax.barh([i - 0.18 for i in y], recall, height=0.34, label="Recall@5", color="#2A9D8F")
    ax.barh([i + 0.18 for i in y], precision, height=0.34, label="Precision@3", color="#264653")
    ax.set_yticks(list(y))
    ax.set_yticklabels(labels)
    ax.set_xlim(0, 1)
    ax.set_xlabel("Score")
    ax.set_title("Image Recognition Baseline by Category")
    ax.grid(axis="x", alpha=0.25)
    ax.legend(loc="lower right")
    fig.tight_layout()
    fig.savefig(chart_path, dpi=160)
    plt.close(fig)


def _metric_table(summary: dict[str, Any]) -> list[str]:
    lines = [
        "| K | Macro P@K | Micro P@K | Macro R@K | Micro R@K | F1@K | Hit-rate@K | MRR@K | MAP@K | NDCG@K |",
        "|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for k in K_VALUES:
        lines.append(
            "| {k} | {mp} | {up} | {mr} | {ur} | {f1} | {hr} | {mrr} | {mapv} | {ndcg} |".format(
                k=k,
                mp=summary[f"macro_precision_at_{k}"],
                up=summary[f"micro_precision_at_{k}"],
                mr=summary[f"macro_recall_at_{k}"],
                ur=summary[f"micro_recall_at_{k}"],
                f1=summary[f"macro_f1_at_{k}"],
                hr=summary[f"hit_rate_at_{k}"],
                mrr=summary[f"mrr_at_{k}"],
                mapv=summary[f"map_at_{k}"],
                ndcg=summary[f"ndcg_at_{k}"],
            )
        )
    return lines


def _write_summary_markdown(payload: dict[str, Any], output_paths: dict[str, Path], summary_path: Path) -> None:
    summary = payload["summary"]
    no_hit = [row for row in payload["per_image"] if not row["hits_at_5"]]
    hardest_categories = payload["category_breakdown"][:8]
    missed_tags = [
        row for row in payload["tag_breakdown"]
        if row["expected_count"] > 0 and row["recall_at_5"] < 1.0
    ][:12]
    false_positive_tags = sorted(
        payload["tag_breakdown"],
        key=lambda row: row["false_positive_top5_count"],
        reverse=True,
    )[:12]

    lines = [
        "# Image Recognition Evaluation",
        "",
        f"Generated at: `{payload['generated_at']}`",
        f"Run name: `{payload['name']}`",
        f"Prediction key: `{payload['prediction_key']}`",
        "",
        "## Inputs",
        "",
        f"- Dataset: `{payload['dataset']['path']}`",
        f"- Predictions: `{payload['predictions']['path']}`",
        f"- Images: `{summary['num_images']}`",
        f"- Expected tags: `{summary['total_expected_tags']}`",
        f"- Mean predicted tags/image: `{summary['mean_predicted_count']}`",
        "",
        "## Global Metrics",
        "",
        *_metric_table(summary),
        "",
        "## Diagnostic",
        "",
        f"- Zero-hit@5 rate: `{summary['zero_hit_rate_at_5']}`",
        f"- Full-recall@5 rate: `{summary['full_recall_rate_at_5']}`",
        f"- Main thesis baseline: `P@3={summary['macro_precision_at_3']}`, `R@5={summary['macro_recall_at_5']}`, `NDCG@5={summary['ndcg_at_5']}`",
        "",
        "## Category Breakdown",
        "",
        "| Category | N | P@3 | R@5 | F1@5 | Hit-rate@5 | NDCG@5 | Zero-hit@5 |",
        "|---|---:|---:|---:|---:|---:|---:|---:|",
    ]

    for row in payload["category_breakdown"]:
        lines.append(
            "| {category} | {n} | {p3} | {r5} | {f1} | {hit} | {ndcg} | {zero} |".format(
                category=row["category"],
                n=row["num_images"],
                p3=row["precision_at_3"],
                r5=row["recall_at_5"],
                f1=row["f1_at_5"],
                hit=row["hit_rate_at_5"],
                ndcg=row["ndcg_at_5"],
                zero=row["zero_hit_rate_at_5"],
            )
        )

    lines.extend(["", "## Hardest Categories", ""])
    for row in hardest_categories:
        lines.append(f"- `{row['category']}`: R@5 `{row['recall_at_5']}`, zero-hit@5 `{row['zero_hit_rate_at_5']}`")

    lines.extend(["", "## No-Hit Images", ""])
    for row in no_hit[:15]:
        lines.append(
            "- `{id}` ({category}): expected `{expected}`, predicted top5 `{predicted}`".format(
                id=row["id"],
                category=row["category"],
                expected=", ".join(row["expected_tags"]),
                predicted=", ".join(row["predicted_tags"][:5]) or "-",
            )
        )
    if len(no_hit) > 15:
        lines.append(f"- ... plus `{len(no_hit) - 15}` more in the failures CSV.")

    lines.extend(["", "## Frequently Missed Tags", ""])
    for row in missed_tags:
        lines.append(
            f"- `{row['tag']}`: expected `{row['expected_count']}`, hit@5 `{row['hit_at_5_count']}`, recall@5 `{row['recall_at_5']}`"
        )

    lines.extend(["", "## Frequent False Positives", ""])
    for row in false_positive_tags:
        if row["false_positive_top5_count"] <= 0:
            continue
        lines.append(f"- `{row['tag']}`: false-positive top5 count `{row['false_positive_top5_count']}`")

    lines.extend(
        [
            "",
            "## Output Files",
            "",
            f"- Full JSON: `{output_paths['json'].name}`",
            f"- Per-image CSV: `{output_paths['per_image_csv'].name}`",
            f"- Category CSV: `{output_paths['category_csv'].name}`",
            f"- Tag CSV: `{output_paths['tag_csv'].name}`",
            f"- Failures CSV: `{output_paths['failures_csv'].name}`",
            f"- Category chart: `{output_paths['category_chart'].name}`",
        ]
    )

    summary_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _write_comparison_markdown(evaluated: list[tuple[dict[str, Any], dict[str, Path], Path]], summary_path: Path) -> None:
    if len(evaluated) < 2:
        return

    rows = []
    for payload, _paths, _summary_path in evaluated:
        summary = payload["summary"]
        rows.append(
            {
                "name": payload["name"],
                "precision_at_3": summary["macro_precision_at_3"],
                "recall_at_5": summary["macro_recall_at_5"],
                "f1_at_5": summary["macro_f1_at_5"],
                "hit_rate_at_5": summary["hit_rate_at_5"],
                "mrr_at_5": summary["mrr_at_5"],
                "map_at_5": summary["map_at_5"],
                "ndcg_at_5": summary["ndcg_at_5"],
                "zero_hit_rate_at_5": summary["zero_hit_rate_at_5"],
                "summary_file": _summary_path.name,
            }
        )

    baseline = rows[0]
    best = max(rows, key=lambda row: (row["ndcg_at_5"], row["recall_at_5"], row["precision_at_3"]))

    def delta(metric: str) -> float:
        return _round(best[metric] - baseline[metric])

    lines = [
        "# Image Recognition Evaluation Comparison",
        "",
        f"Generated at: `{datetime.now(timezone.utc).isoformat()}`",
        "",
        "## Best Run",
        "",
        f"- Best by NDCG@5: `{best['name']}`",
        f"- P@3 delta vs `{baseline['name']}`: `{delta('precision_at_3')}`",
        f"- R@5 delta vs `{baseline['name']}`: `{delta('recall_at_5')}`",
        f"- NDCG@5 delta vs `{baseline['name']}`: `{delta('ndcg_at_5')}`",
        f"- Zero-hit@5 delta vs `{baseline['name']}`: `{delta('zero_hit_rate_at_5')}`",
        "",
        "## Runs",
        "",
        "| Run | P@3 | R@5 | F1@5 | Hit-rate@5 | MRR@5 | MAP@5 | NDCG@5 | Zero-hit@5 | Report |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---|",
    ]

    for row in sorted(rows, key=lambda item: item["ndcg_at_5"], reverse=True):
        lines.append(
            "| {name} | {p3} | {r5} | {f1} | {hit} | {mrr} | {mapv} | {ndcg} | {zero} | `{report}` |".format(
                name=row["name"],
                p3=row["precision_at_3"],
                r5=row["recall_at_5"],
                f1=row["f1_at_5"],
                hit=row["hit_rate_at_5"],
                mrr=row["mrr_at_5"],
                mapv=row["map_at_5"],
                ndcg=row["ndcg_at_5"],
                zero=row["zero_hit_rate_at_5"],
                report=row["summary_file"],
            )
        )

    lines.extend(
        [
            "",
            "## Interpretation",
            "",
            "- `P@3` masoara cat de curate sunt primele 3 taguri afisate.",
            "- `R@5` masoara cat din ground truth este recuperat in top 5.",
            "- `NDCG@5` recompenseaza hiturile gasite mai sus in ranking.",
            "- `Zero-hit@5` este rata imaginilor unde niciun tag asteptat nu apare in top 5; mai mic este mai bine.",
        ]
    )

    summary_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Evalueaza predictii pentru recunoasterea imaginilor.")
    parser.add_argument("--dataset", default=str(DEFAULT_DATASET_PATH), help="Manifestul JSON cu expected_tags.")
    parser.add_argument(
        "--predictions",
        nargs="+",
        default=[str(DEFAULT_PREDICTIONS_PATH)],
        help="Unul sau mai multe fisiere JSON cu predictii.",
    )
    parser.add_argument(
        "--names",
        nargs="*",
        default=None,
        help="Nume scurte pentru fisierele de predictii, in aceeasi ordine.",
    )
    parser.add_argument(
        "--prediction-key",
        default=DEFAULT_PREDICTION_KEY,
        help="Campul din fiecare rezultat folosit drept predictii.",
    )
    parser.add_argument(
        "--output-dir",
        default=str(RESULTS_DIR),
        help="Directorul in care se scriu fisierele de evaluare.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    dataset_path = Path(args.dataset)
    prediction_paths = [Path(path) for path in args.predictions]
    names = args.names or []
    if names and len(names) != len(prediction_paths):
        raise ValueError("--names trebuie sa aiba acelasi numar de valori ca --predictions.")

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    evaluated = []
    multi_run = len(prediction_paths) > 1
    for index, predictions_path in enumerate(prediction_paths):
        name = names[index] if names else predictions_path.stem.replace("image_baseline_", "")
        payload = evaluate_predictions(
            dataset_path=dataset_path,
            predictions_path=predictions_path,
            prediction_key=args.prediction_key,
            name=name,
        )
        prefix = output_dir / f"image_recognition_eval_{name}"
        output_paths = _write_outputs(payload, prefix)
        summary_path = (
            output_dir / f"SUMMARY_IMAGE_RECOGNITION_EVAL_{name}.md"
            if multi_run
            else output_dir / "SUMMARY_IMAGE_RECOGNITION_EVAL.md"
        )
        _write_summary_markdown(payload, output_paths, summary_path)
        evaluated.append((payload, output_paths, summary_path))

        summary = payload["summary"]
        print(
            f"{name}: P@3={summary['macro_precision_at_3']} "
            f"R@5={summary['macro_recall_at_5']} NDCG@5={summary['ndcg_at_5']}"
        )

    if len(evaluated) > 1:
        comparison_path = output_dir / "image_recognition_eval_comparison.csv"
        rows = []
        for payload, _paths, _summary_path in evaluated:
            summary = payload["summary"]
            rows.append(
                {
                    "name": payload["name"],
                    "prediction_key": payload["prediction_key"],
                    "precision_at_3": summary["macro_precision_at_3"],
                    "recall_at_5": summary["macro_recall_at_5"],
                    "f1_at_5": summary["macro_f1_at_5"],
                    "hit_rate_at_5": summary["hit_rate_at_5"],
                    "mrr_at_5": summary["mrr_at_5"],
                    "map_at_5": summary["map_at_5"],
                    "ndcg_at_5": summary["ndcg_at_5"],
                    "zero_hit_rate_at_5": summary["zero_hit_rate_at_5"],
                }
            )
        _write_csv(
            comparison_path,
            rows,
            [
                "name",
                "prediction_key",
                "precision_at_3",
                "recall_at_5",
                "f1_at_5",
                "hit_rate_at_5",
                "mrr_at_5",
                "map_at_5",
                "ndcg_at_5",
                "zero_hit_rate_at_5",
            ],
        )
        comparison_summary_path = output_dir / "SUMMARY_IMAGE_RECOGNITION_COMPARISON.md"
        _write_comparison_markdown(evaluated, comparison_summary_path)
        _write_comparison_markdown(evaluated, output_dir / "SUMMARY_IMAGE_RECOGNITION_EVAL.md")
        print(f"Comparison CSV: {comparison_path}")


if __name__ == "__main__":
    main()
