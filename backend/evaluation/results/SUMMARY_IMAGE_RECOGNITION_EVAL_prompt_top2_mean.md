# Image Recognition Evaluation

Generated at: `2026-06-12T00:12:58.759877+00:00`
Run name: `prompt_top2_mean`
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
| 1 | 0.7872 | 0.7872 | 0.2624 | 0.2624 | 0.3936 | 0.7872 | 0.7872 | 0.7872 | 0.7872 |
| 3 | 0.4823 | 0.4823 | 0.4823 | 0.4823 | 0.4823 | 0.9149 | 0.8511 | 0.4468 | 0.5503 |
| 5 | 0.3617 | 0.3617 | 0.6028 | 0.6028 | 0.4521 | 0.9362 | 0.8553 | 0.5082 | 0.6195 |
| 10 | 0.2149 | 0.2149 | 0.7163 | 0.7163 | 0.3306 | 0.9787 | 0.8607 | 0.541 | 0.6693 |

## Diagnostic

- Zero-hit@5 rate: `0.0638`
- Full-recall@5 rate: `0.234`
- Main thesis baseline: `P@3=0.4823`, `R@5=0.6028`, `NDCG@5=0.6195`

## Category Breakdown

| Category | N | P@3 | R@5 | F1@5 | Hit-rate@5 | NDCG@5 | Zero-hit@5 |
|---|---:|---:|---:|---:|---:|---:|---:|
| culture_history | 7 | 0.2857 | 0.3333 | 0.25 | 0.8571 | 0.3787 | 0.1429 |
| nature_outdoors | 6 | 0.4444 | 0.5556 | 0.4167 | 1.0 | 0.5928 | 0.0 |
| family_comfort | 3 | 0.5556 | 0.5556 | 0.4167 | 1.0 | 0.6462 | 0.0 |
| wellness_slow | 4 | 0.5 | 0.5833 | 0.4375 | 1.0 | 0.6194 | 0.0 |
| beach_water | 7 | 0.4762 | 0.619 | 0.4643 | 1.0 | 0.6463 | 0.0 |
| adventure_active | 2 | 0.3333 | 0.6667 | 0.5 | 1.0 | 0.5745 | 0.0 |
| urban_modern | 4 | 0.4167 | 0.6667 | 0.5 | 0.75 | 0.6311 | 0.25 |
| food_drink | 7 | 0.5238 | 0.6667 | 0.5 | 0.8571 | 0.6434 | 0.1429 |
| nightlife_social | 5 | 0.8 | 0.8 | 0.6 | 1.0 | 0.8346 | 0.0 |
| winter | 2 | 0.5 | 0.8333 | 0.625 | 1.0 | 0.8091 | 0.0 |

## Hardest Categories

- `culture_history`: R@5 `0.3333`, zero-hit@5 `0.1429`
- `nature_outdoors`: R@5 `0.5556`, zero-hit@5 `0.0`
- `family_comfort`: R@5 `0.5556`, zero-hit@5 `0.0`
- `wellness_slow`: R@5 `0.5833`, zero-hit@5 `0.0`
- `beach_water`: R@5 `0.619`, zero-hit@5 `0.0`
- `adventure_active`: R@5 `0.6667`, zero-hit@5 `0.0`
- `urban_modern`: R@5 `0.6667`, zero-hit@5 `0.25`
- `food_drink`: R@5 `0.6667`, zero-hit@5 `0.1429`

## No-Hit Images

- `art_museums` (culture_history): expected `art-museums, contemporary-art, history-museums`, predicted top5 `wwii-history, castles-palaces, local-festivals, film-festivals, vernacular-architecture`
- `contemporary_art` (urban_modern): expected `contemporary-art, art-museums, street-art`, predicted top5 `science-interactive-museums, science-museums, science-centers, food-tours-guided, arts-museums`
- `street_food` (food_drink): expected `street-food, street-casual-food, food-trucks`, predicted top5 `food-markets, farmers-markets, food-tours-guided, spice-markets, flea-markets`

## Frequently Missed Tags

- `national-parks`: expected `3`, hit@5 `0`, recall@5 `0.0`
- `guided-walking-tours`: expected `2`, hit@5 `0`, recall@5 `0.0`
- `roman-history`: expected `2`, hit@5 `0`, recall@5 `0.0`
- `art-museums`: expected `2`, hit@5 `0`, recall@5 `0.0`
- `canal-river-cruises`: expected `2`, hit@5 `0`, recall@5 `0.0`
- `kids-workshops`: expected `2`, hit@5 `0`, recall@5 `0.0`
- `vernacular-architecture`: expected `1`, hit@5 `0`, recall@5 `0.0`
- `water-parks`: expected `1`, hit@5 `0`, recall@5 `0.0`
- `camping`: expected `1`, hit@5 `0`, recall@5 `0.0`
- `craft-cocktail-bars`: expected `1`, hit@5 `0`, recall@5 `0.0`
- `fish-markets`: expected `1`, hit@5 `0`, recall@5 `0.0`
- `local-artisan-shops`: expected `1`, hit@5 `0`, recall@5 `0.0`

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
- `history-museums`: false-positive top5 count `3`

## Output Files

- Full JSON: `image_recognition_eval_prompt_top2_mean.json`
- Per-image CSV: `image_recognition_eval_prompt_top2_mean_per_image.csv`
- Category CSV: `image_recognition_eval_prompt_top2_mean_by_category.csv`
- Tag CSV: `image_recognition_eval_prompt_top2_mean_by_tag.csv`
- Failures CSV: `image_recognition_eval_prompt_top2_mean_failures.csv`
- Category chart: `image_recognition_eval_prompt_top2_mean_category_recall.png`
