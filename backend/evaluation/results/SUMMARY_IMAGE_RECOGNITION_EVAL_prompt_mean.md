# Image Recognition Evaluation

Generated at: `2026-06-12T00:12:58.960461+00:00`
Run name: `prompt_mean`
Prediction key: `matched_db_tags`

## Inputs

- Dataset: `evaluation/image_recognition_dataset.json`
- Predictions: `evaluation/results/image_prompt_multitag_mean_predictions.json`
- Images: `47`
- Expected tags: `141`
- Mean predicted tags/image: `20.0`

## Global Metrics

| K | Macro P@K | Micro P@K | Macro R@K | Micro R@K | F1@K | Hit-rate@K | MRR@K | MAP@K | NDCG@K |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 1 | 0.766 | 0.766 | 0.2553 | 0.2553 | 0.383 | 0.766 | 0.766 | 0.766 | 0.766 |
| 3 | 0.4468 | 0.4468 | 0.4468 | 0.4468 | 0.4468 | 0.8723 | 0.8156 | 0.4137 | 0.5138 |
| 5 | 0.3277 | 0.3277 | 0.5461 | 0.5461 | 0.4096 | 0.9149 | 0.8252 | 0.4591 | 0.5697 |
| 10 | 0.2043 | 0.2043 | 0.6809 | 0.6809 | 0.3142 | 0.9787 | 0.8337 | 0.4979 | 0.6312 |

## Diagnostic

- Zero-hit@5 rate: `0.0851`
- Full-recall@5 rate: `0.1915`
- Main thesis baseline: `P@3=0.4468`, `R@5=0.5461`, `NDCG@5=0.5697`

## Category Breakdown

| Category | N | P@3 | R@5 | F1@5 | Hit-rate@5 | NDCG@5 | Zero-hit@5 |
|---|---:|---:|---:|---:|---:|---:|---:|
| culture_history | 7 | 0.2381 | 0.2857 | 0.2143 | 0.7143 | 0.3393 | 0.2857 |
| adventure_active | 2 | 0.3333 | 0.5 | 0.375 | 1.0 | 0.56 | 0.0 |
| beach_water | 7 | 0.4286 | 0.5238 | 0.3929 | 1.0 | 0.5752 | 0.0 |
| food_drink | 7 | 0.4762 | 0.5238 | 0.3929 | 0.8571 | 0.5303 | 0.1429 |
| nature_outdoors | 6 | 0.4444 | 0.5556 | 0.4167 | 1.0 | 0.5826 | 0.0 |
| family_comfort | 3 | 0.5556 | 0.5556 | 0.4167 | 1.0 | 0.6462 | 0.0 |
| urban_modern | 4 | 0.3333 | 0.5833 | 0.4375 | 0.75 | 0.5621 | 0.25 |
| wellness_slow | 4 | 0.4167 | 0.5833 | 0.4375 | 1.0 | 0.5373 | 0.0 |
| winter | 2 | 0.5 | 0.6667 | 0.5 | 1.0 | 0.6774 | 0.0 |
| nightlife_social | 5 | 0.8 | 0.8667 | 0.65 | 1.0 | 0.8709 | 0.0 |

## Hardest Categories

- `culture_history`: R@5 `0.2857`, zero-hit@5 `0.2857`
- `adventure_active`: R@5 `0.5`, zero-hit@5 `0.0`
- `beach_water`: R@5 `0.5238`, zero-hit@5 `0.0`
- `food_drink`: R@5 `0.5238`, zero-hit@5 `0.1429`
- `nature_outdoors`: R@5 `0.5556`, zero-hit@5 `0.0`
- `family_comfort`: R@5 `0.5556`, zero-hit@5 `0.0`
- `urban_modern`: R@5 `0.5833`, zero-hit@5 `0.25`
- `wellness_slow`: R@5 `0.5833`, zero-hit@5 `0.0`

## No-Hit Images

- `history_museums` (culture_history): expected `history-museums, historical-sites, roman-history`, predicted top5 `science-museums, tech-innovation, science-interactive-museums, science-centers, stargazing`
- `art_museums` (culture_history): expected `art-museums, contemporary-art, history-museums`, predicted top5 `easy-sightseeing, castles-palaces, wwii-history, historical-sites, film-festivals`
- `contemporary_art` (urban_modern): expected `contemporary-art, art-museums, street-art`, predicted top5 `science-museums, science-centers, science-interactive-museums, food-tours-guided, arts-museums`
- `street_food` (food_drink): expected `street-food, street-casual-food, food-trucks`, predicted top5 `food-markets, farmers-markets, food-tours-guided, spice-markets, food-social-tours`

## Frequently Missed Tags

- `photography-landscapes`: expected `4`, hit@5 `0`, recall@5 `0.0`
- `national-parks`: expected `3`, hit@5 `0`, recall@5 `0.0`
- `guided-walking-tours`: expected `2`, hit@5 `0`, recall@5 `0.0`
- `history-museums`: expected `2`, hit@5 `0`, recall@5 `0.0`
- `roman-history`: expected `2`, hit@5 `0`, recall@5 `0.0`
- `art-museums`: expected `2`, hit@5 `0`, recall@5 `0.0`
- `canal-river-cruises`: expected `2`, hit@5 `0`, recall@5 `0.0`
- `kids-workshops`: expected `2`, hit@5 `0`, recall@5 `0.0`
- `lake-swimming`: expected `1`, hit@5 `0`, recall@5 `0.0`
- `hidden-coves`: expected `1`, hit@5 `0`, recall@5 `0.0`
- `music-festivals`: expected `1`, hit@5 `0`, recall@5 `0.0`
- `via-ferrata`: expected `1`, hit@5 `0`, recall@5 `0.0`

## Frequent False Positives

- `food-social-tours`: false-positive top5 count `7`
- `food-tours-guided`: false-positive top5 count `7`
- `adventure-active`: false-positive top5 count `6`
- `contemplative-nature`: false-positive top5 count `6`
- `nature-outdoors`: false-positive top5 count `5`
- `guided-walking-tours`: false-positive top5 count `4`
- `hiking-trekking`: false-positive top5 count `4`
- `history-museums`: false-positive top5 count `3`
- `architecture`: false-positive top5 count `3`
- `arts-museums`: false-positive top5 count `3`
- `child-beaches`: false-positive top5 count `3`
- `float-tanks`: false-positive top5 count `3`

## Output Files

- Full JSON: `image_recognition_eval_prompt_mean.json`
- Per-image CSV: `image_recognition_eval_prompt_mean_per_image.csv`
- Category CSV: `image_recognition_eval_prompt_mean_by_category.csv`
- Tag CSV: `image_recognition_eval_prompt_mean_by_tag.csv`
- Failures CSV: `image_recognition_eval_prompt_mean_failures.csv`
- Category chart: `image_recognition_eval_prompt_mean_category_recall.png`
