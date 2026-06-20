#!/usr/bin/env python3
"""
Genereaza un manifest mare pentru evaluarea recunoasterii pe imagini.

Manifestul porneste de la fisierele din static/quiz_images, unde numele
fisierului corespunde unui slug din tabela tags. Este util ca benchmark de
coverage; pentru rezultate finale, cazurile ambigue trebuie revizuite manual.

Rulare (din directorul backend/):
    python -m evaluation.build_image_dataset_from_static
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.database import SessionLocal
from app.models.tag import Tag


EVAL_DIR = Path(__file__).resolve().parent
STATIC_IMAGES_DIR = BACKEND_DIR / "static" / "quiz_images"
DEFAULT_OUTPUT_PATH = EVAL_DIR / "image_recognition_dataset_full.json"
IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}


@dataclass(frozen=True)
class TagMeta:
    slug: str
    category: str
    is_leaf: bool
    parent_slug: str | None


def _load_tags() -> dict[str, TagMeta]:
    db = SessionLocal()
    try:
        tags = db.query(Tag).order_by(Tag.slug.asc()).all()
        return {
            tag.slug: TagMeta(
                slug=tag.slug,
                category=tag.category,
                is_leaf=bool(tag.is_leaf),
                parent_slug=tag.parent.slug if tag.parent else None,
            )
            for tag in tags
        }
    finally:
        db.close()


def _expected_tags(tag: TagMeta, root_slugs: set[str], include_parent: bool) -> list[str]:
    expected = [tag.slug]
    if include_parent and tag.parent_slug and tag.parent_slug not in root_slugs:
        expected.append(tag.parent_slug)
    return list(dict.fromkeys(expected))


def build_dataset(output_path: Path = DEFAULT_OUTPUT_PATH, include_parent: bool = True) -> dict[str, Any]:
    tags_by_slug = _load_tags()
    root_slugs = {tag.slug for tag in tags_by_slug.values() if tag.parent_slug is None}

    image_paths = sorted(
        path
        for path in STATIC_IMAGES_DIR.iterdir()
        if path.is_file() and path.suffix.lower() in IMAGE_EXTENSIONS
    )
    if not image_paths:
        raise RuntimeError(f"Nu exista imagini in {STATIC_IMAGES_DIR}")

    images = []
    missing_tags = []
    for image_path in image_paths:
        slug = image_path.stem
        tag = tags_by_slug.get(slug)
        if tag is None:
            missing_tags.append(slug)
            continue

        images.append(
            {
                "id": slug.replace("-", "_"),
                "file": image_path.name,
                "category": tag.category.replace("-", "_"),
                "expected_tags": _expected_tags(tag, root_slugs, include_parent=include_parent),
                "primary_tag": tag.slug,
                "is_leaf": bool(tag.is_leaf),
                "notes": "Auto-generat din numele fisierului si taxonomia DB; necesita revizie manuala pentru ground truth final.",
            }
        )

    if missing_tags:
        raise RuntimeError(
            "Exista imagini fara slug corespondent in DB: " + ", ".join(sorted(missing_tags))
        )

    payload = {
        "version": 1,
        "name": "TripCraft full static image recognition evaluation dataset",
        "description": (
            "Manifest auto-generat din static/quiz_images. Expected tags includ slugul "
            "principal din numele fisierului si, optional, parintele taxonomic concret."
        ),
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source": "backend/static/quiz_images",
        "generation": {
            "include_parent": include_parent,
            "total_static_images": len(image_paths),
            "matched_db_tags": len(images),
        },
        "images": images,
    }

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    return payload


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Genereaza dataset mare din static/quiz_images.")
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT_PATH), help="Fisierul JSON generat.")
    parser.add_argument(
        "--no-parent",
        action="store_true",
        help="Foloseste doar slugul principal, fara parinte taxonomic.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    payload = build_dataset(output_path=Path(args.output), include_parent=not args.no_parent)
    print(
        "Saved {path} ({images} images, include_parent={include_parent})".format(
            path=args.output,
            images=len(payload["images"]),
            include_parent=payload["generation"]["include_parent"],
        )
    )


if __name__ == "__main__":
    main()
