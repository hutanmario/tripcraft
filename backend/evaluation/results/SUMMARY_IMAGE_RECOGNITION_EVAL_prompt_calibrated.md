# Image Recognition Evaluation

Generated at: `2026-06-12T11:30:38.361673+00:00`
Run name: `prompt_calibrated`
Prediction key: `matched_db_tags`

## Inputs

- Dataset: `evaluation/image_recognition_dataset.json`
- Predictions: `evaluation/results/image_prompt_multitag_predictions.json`
- Images: `47`
- Expected tags: `141`
- Mean predicted tags/image: `20.0`

## Global Metrics

| K | Macro P@K | Micro P@K | Macro R@K | Micro R@K | F1@K | Hit-rate@K | MRR@K | MAP@K | NDCG@K |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 1 | 0.8298 | 0.8298 | 0.2766 | 0.2766 | 0.4149 | 0.8298 | 0.8298 | 0.8298 | 0.8298 |
| 3 | 0.6099 | 0.6099 | 0.6099 | 0.6099 | 0.6099 | 1.0 | 0.9113 | 0.5496 | 0.658 |
| 5 | 0.4383 | 0.4383 | 0.7305 | 0.7305 | 0.5479 | 1.0 | 0.9113 | 0.6223 | 0.7272 |
| 10 | 0.2511 | 0.2511 | 0.8369 | 0.8369 | 0.3863 | 1.0 | 0.9113 | 0.6604 | 0.7756 |

## Diagnostic

- Zero-hit@5 rate: `0.0`
- Full-recall@5 rate: `0.4043`
- Main thesis baseline: `P@3=0.6099`, `R@5=0.7305`, `NDCG@5=0.7272`

## Category Breakdown

| Category | N | P@3 | R@5 | F1@5 | Hit-rate@5 | NDCG@5 | Zero-hit@5 |
|---|---:|---:|---:|---:|---:|---:|---:|
| culture_history | 7 | 0.5238 | 0.5238 | 0.3929 | 1.0 | 0.5539 | 0.0 |
| wellness_slow | 4 | 0.5 | 0.5833 | 0.4375 | 1.0 | 0.6194 | 0.0 |
| family_comfort | 3 | 0.4444 | 0.6667 | 0.5 | 1.0 | 0.6245 | 0.0 |
| adventure_active | 2 | 0.5 | 0.6667 | 0.5 | 1.0 | 0.6011 | 0.0 |
| nature_outdoors | 6 | 0.6111 | 0.7222 | 0.5417 | 1.0 | 0.7067 | 0.0 |
| urban_modern | 4 | 0.5 | 0.75 | 0.5625 | 1.0 | 0.7484 | 0.0 |
| beach_water | 7 | 0.619 | 0.8095 | 0.6071 | 1.0 | 0.7904 | 0.0 |
| food_drink | 7 | 0.7143 | 0.8095 | 0.6071 | 1.0 | 0.8026 | 0.0 |
| nightlife_social | 5 | 0.8 | 0.8667 | 0.65 | 1.0 | 0.8832 | 0.0 |
| winter | 2 | 0.8333 | 1.0 | 0.75 | 1.0 | 0.9735 | 0.0 |

## Hardest Categories

- `culture_history`: R@5 `0.5238`, zero-hit@5 `0.0`
- `wellness_slow`: R@5 `0.5833`, zero-hit@5 `0.0`
- `family_comfort`: R@5 `0.6667`, zero-hit@5 `0.0`
- `adventure_active`: R@5 `0.6667`, zero-hit@5 `0.0`
- `nature_outdoors`: R@5 `0.7222`, zero-hit@5 `0.0`
- `urban_modern`: R@5 `0.75`, zero-hit@5 `0.0`
- `beach_water`: R@5 `0.8095`, zero-hit@5 `0.0`
- `food_drink`: R@5 `0.8095`, zero-hit@5 `0.0`

## No-Hit Images


## Frequently Missed Tags

- `guided-walking-tours`: expected `3`, hit@5 `0`, recall@5 `0.0`
- `roman-history`: expected `2`, hit@5 `0`, recall@5 `0.0`
- `canal-river-cruises`: expected `2`, hit@5 `0`, recall@5 `0.0`
- `kids-workshops`: expected `2`, hit@5 `0`, recall@5 `0.0`
- `camping`: expected `1`, hit@5 `0`, recall@5 `0.0`
- `craft-cocktail-bars`: expected `1`, hit@5 `0`, recall@5 `0.0`
- `fish-markets`: expected `1`, hit@5 `0`, recall@5 `0.0`
- `local-artisan-shops`: expected `1`, hit@5 `0`, recall@5 `0.0`
- `meditation-centers`: expected `1`, hit@5 `0`, recall@5 `0.0`
- `music-festivals`: expected `1`, hit@5 `0`, recall@5 `0.0`
- `tech-hubs`: expected `1`, hit@5 `0`, recall@5 `0.0`
- `thermal-baths`: expected `3`, hit@5 `1`, recall@5 `0.3333`

## Frequent False Positives

- `contemplative-nature`: false-positive top5 count `5`
- `arts-museums`: false-positive top5 count `4`
- `modernist-architecture`: false-positive top5 count `4`
- `wildlife-nature`: false-positive top5 count `4`
- `guided-walking-tours`: false-positive top5 count `3`
- `cooking-classes`: false-positive top5 count `3`
- `historical-sites`: false-positive top5 count `3`
- `alpine-climbing`: false-positive top5 count `3`
- `hidden-coves`: false-positive top5 count `3`
- `history-museums`: false-positive top5 count `3`
- `cabaret`: false-positive top5 count `2`
- `culinary-learning`: false-positive top5 count `2`

## Output Files

- Full JSON: `image_recognition_eval_prompt_calibrated.json`
- Per-image CSV: `image_recognition_eval_prompt_calibrated_per_image.csv`
- Category CSV: `image_recognition_eval_prompt_calibrated_by_category.csv`
- Tag CSV: `image_recognition_eval_prompt_calibrated_by_tag.csv`
- Failures CSV: `image_recognition_eval_prompt_calibrated_failures.csv`
- Category chart: `image_recognition_eval_prompt_calibrated_category_recall.png`
