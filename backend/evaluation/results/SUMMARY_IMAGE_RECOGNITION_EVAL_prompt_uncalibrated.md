# Image Recognition Evaluation

Generated at: `2026-06-12T11:30:38.262815+00:00`
Run name: `prompt_uncalibrated`
Prediction key: `matched_db_tags`

## Inputs

- Dataset: `evaluation/image_recognition_dataset.json`
- Predictions: `evaluation/results/image_prompt_multitag_uncalibrated_predictions.json`
- Images: `47`
- Expected tags: `141`
- Mean predicted tags/image: `20.0`

## Global Metrics

| K | Macro P@K | Micro P@K | Macro R@K | Micro R@K | F1@K | Hit-rate@K | MRR@K | MAP@K | NDCG@K |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 1 | 0.8085 | 0.8085 | 0.2695 | 0.2695 | 0.4043 | 0.8085 | 0.8085 | 0.8085 | 0.8085 |
| 3 | 0.4965 | 0.4965 | 0.4965 | 0.4965 | 0.4965 | 0.9362 | 0.8723 | 0.461 | 0.5666 |
| 5 | 0.3787 | 0.3787 | 0.6312 | 0.6312 | 0.4734 | 1.0 | 0.8862 | 0.5255 | 0.644 |
| 10 | 0.2213 | 0.2213 | 0.7376 | 0.7376 | 0.3404 | 1.0 | 0.8862 | 0.5589 | 0.6904 |

## Diagnostic

- Zero-hit@5 rate: `0.0`
- Full-recall@5 rate: `0.234`
- Main thesis baseline: `P@3=0.4965`, `R@5=0.6312`, `NDCG@5=0.644`

## Category Breakdown

| Category | N | P@3 | R@5 | F1@5 | Hit-rate@5 | NDCG@5 | Zero-hit@5 |
|---|---:|---:|---:|---:|---:|---:|---:|
| culture_history | 7 | 0.2857 | 0.381 | 0.2857 | 1.0 | 0.4046 | 0.0 |
| nature_outdoors | 6 | 0.4444 | 0.5556 | 0.4167 | 1.0 | 0.5928 | 0.0 |
| family_comfort | 3 | 0.5556 | 0.5556 | 0.4167 | 1.0 | 0.6462 | 0.0 |
| wellness_slow | 4 | 0.5 | 0.5833 | 0.4375 | 1.0 | 0.6194 | 0.0 |
| beach_water | 7 | 0.4762 | 0.619 | 0.4643 | 1.0 | 0.6463 | 0.0 |
| adventure_active | 2 | 0.3333 | 0.6667 | 0.5 | 1.0 | 0.5745 | 0.0 |
| urban_modern | 4 | 0.4167 | 0.75 | 0.5625 | 1.0 | 0.6816 | 0.0 |
| food_drink | 7 | 0.619 | 0.7619 | 0.5714 | 1.0 | 0.7527 | 0.0 |
| nightlife_social | 5 | 0.8 | 0.8 | 0.6 | 1.0 | 0.8346 | 0.0 |
| winter | 2 | 0.5 | 0.8333 | 0.625 | 1.0 | 0.8091 | 0.0 |

## Hardest Categories

- `culture_history`: R@5 `0.381`, zero-hit@5 `0.0`
- `nature_outdoors`: R@5 `0.5556`, zero-hit@5 `0.0`
- `family_comfort`: R@5 `0.5556`, zero-hit@5 `0.0`
- `wellness_slow`: R@5 `0.5833`, zero-hit@5 `0.0`
- `beach_water`: R@5 `0.619`, zero-hit@5 `0.0`
- `adventure_active`: R@5 `0.6667`, zero-hit@5 `0.0`
- `urban_modern`: R@5 `0.75`, zero-hit@5 `0.0`
- `food_drink`: R@5 `0.7619`, zero-hit@5 `0.0`

## No-Hit Images


## Frequently Missed Tags

- `guided-walking-tours`: expected `3`, hit@5 `0`, recall@5 `0.0`
- `national-parks`: expected `3`, hit@5 `0`, recall@5 `0.0`
- `roman-history`: expected `2`, hit@5 `0`, recall@5 `0.0`
- `canal-river-cruises`: expected `2`, hit@5 `0`, recall@5 `0.0`
- `kids-workshops`: expected `2`, hit@5 `0`, recall@5 `0.0`
- `water-parks`: expected `1`, hit@5 `0`, recall@5 `0.0`
- `camping`: expected `1`, hit@5 `0`, recall@5 `0.0`
- `craft-cocktail-bars`: expected `1`, hit@5 `0`, recall@5 `0.0`
- `fish-markets`: expected `1`, hit@5 `0`, recall@5 `0.0`
- `local-artisan-shops`: expected `1`, hit@5 `0`, recall@5 `0.0`
- `meditation-centers`: expected `1`, hit@5 `0`, recall@5 `0.0`
- `music-festivals`: expected `1`, hit@5 `0`, recall@5 `0.0`

## Frequent False Positives

- `food-tours-guided`: false-positive top5 count `6`
- `wwii-history`: false-positive top5 count `4`
- `wildlife-nature`: false-positive top5 count `4`
- `guided-walking-tours`: false-positive top5 count `3`
- `accessible-attractions`: false-positive top5 count `3`
- `adventure-active`: false-positive top5 count `3`
- `air-extreme-sports`: false-positive top5 count `3`
- `child-activities`: false-positive top5 count `3`
- `child-beaches`: false-positive top5 count `3`
- `nature-outdoors`: false-positive top5 count `3`
- `historical-sites`: false-positive top5 count `3`
- `modernist-architecture`: false-positive top5 count `3`

## Output Files

- Full JSON: `image_recognition_eval_prompt_uncalibrated.json`
- Per-image CSV: `image_recognition_eval_prompt_uncalibrated_per_image.csv`
- Category CSV: `image_recognition_eval_prompt_uncalibrated_by_category.csv`
- Tag CSV: `image_recognition_eval_prompt_uncalibrated_by_tag.csv`
- Failures CSV: `image_recognition_eval_prompt_uncalibrated_failures.csv`
- Category chart: `image_recognition_eval_prompt_uncalibrated_category_recall.png`
