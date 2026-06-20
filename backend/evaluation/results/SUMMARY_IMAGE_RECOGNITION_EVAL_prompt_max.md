# Image Recognition Evaluation

Generated at: `2026-06-12T00:12:58.862147+00:00`
Run name: `prompt_max`
Prediction key: `matched_db_tags`

## Inputs

- Dataset: `evaluation/image_recognition_dataset.json`
- Predictions: `evaluation/results/image_prompt_multitag_max_predictions.json`
- Images: `47`
- Expected tags: `141`
- Mean predicted tags/image: `20.0`

## Global Metrics

| K | Macro P@K | Micro P@K | Macro R@K | Micro R@K | F1@K | Hit-rate@K | MRR@K | MAP@K | NDCG@K |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 1 | 0.7021 | 0.7021 | 0.234 | 0.234 | 0.3511 | 0.7021 | 0.7021 | 0.7021 | 0.7021 |
| 3 | 0.4681 | 0.4681 | 0.4681 | 0.4681 | 0.4681 | 0.8723 | 0.7837 | 0.4173 | 0.5191 |
| 5 | 0.3362 | 0.3362 | 0.5603 | 0.5603 | 0.4202 | 0.9149 | 0.7943 | 0.4602 | 0.5724 |
| 10 | 0.2085 | 0.2085 | 0.695 | 0.695 | 0.3208 | 0.9787 | 0.8026 | 0.5027 | 0.6337 |

## Diagnostic

- Zero-hit@5 rate: `0.0851`
- Full-recall@5 rate: `0.1489`
- Main thesis baseline: `P@3=0.4681`, `R@5=0.5603`, `NDCG@5=0.5724`

## Category Breakdown

| Category | N | P@3 | R@5 | F1@5 | Hit-rate@5 | NDCG@5 | Zero-hit@5 |
|---|---:|---:|---:|---:|---:|---:|---:|
| culture_history | 7 | 0.2857 | 0.2857 | 0.2143 | 0.7143 | 0.3192 | 0.2857 |
| wellness_slow | 4 | 0.4167 | 0.5 | 0.375 | 1.0 | 0.4588 | 0.0 |
| adventure_active | 2 | 0.5 | 0.5 | 0.375 | 1.0 | 0.5 | 0.0 |
| nature_outdoors | 6 | 0.3889 | 0.5556 | 0.4167 | 1.0 | 0.5669 | 0.0 |
| family_comfort | 3 | 0.5556 | 0.5556 | 0.4167 | 1.0 | 0.6462 | 0.0 |
| beach_water | 7 | 0.4286 | 0.5714 | 0.4286 | 1.0 | 0.604 | 0.0 |
| food_drink | 7 | 0.619 | 0.619 | 0.4643 | 0.8571 | 0.6297 | 0.1429 |
| urban_modern | 4 | 0.3333 | 0.6667 | 0.5 | 0.75 | 0.554 | 0.25 |
| winter | 2 | 0.6667 | 0.6667 | 0.5 | 1.0 | 0.7346 | 0.0 |
| nightlife_social | 5 | 0.6667 | 0.8 | 0.6 | 1.0 | 0.8339 | 0.0 |

## Hardest Categories

- `culture_history`: R@5 `0.2857`, zero-hit@5 `0.2857`
- `wellness_slow`: R@5 `0.5`, zero-hit@5 `0.0`
- `adventure_active`: R@5 `0.5`, zero-hit@5 `0.0`
- `nature_outdoors`: R@5 `0.5556`, zero-hit@5 `0.0`
- `family_comfort`: R@5 `0.5556`, zero-hit@5 `0.0`
- `beach_water`: R@5 `0.5714`, zero-hit@5 `0.0`
- `food_drink`: R@5 `0.619`, zero-hit@5 `0.1429`
- `urban_modern`: R@5 `0.6667`, zero-hit@5 `0.25`

## No-Hit Images

- `history_museums` (culture_history): expected `history-museums, historical-sites, roman-history`, predicted top5 `tech-innovation, science-museums, science-interactive-museums, science-centers, stargazing`
- `art_museums` (culture_history): expected `art-museums, contemporary-art, history-museums`, predicted top5 `local-festivals, wwii-history, castles-palaces, chocolate-culture, historical-sites`
- `contemporary_art` (urban_modern): expected `contemporary-art, art-museums, street-art`, predicted top5 `science-centers, science-interactive-museums, science-museums, food-drink, arts-museums`
- `street_food` (food_drink): expected `street-food, street-casual-food, food-trucks`, predicted top5 `food-markets, food-tours-guided, farmers-markets, spice-markets, flea-markets`

## Frequently Missed Tags

- `national-parks`: expected `3`, hit@5 `0`, recall@5 `0.0`
- `spa-thermal`: expected `3`, hit@5 `0`, recall@5 `0.0`
- `history-museums`: expected `2`, hit@5 `0`, recall@5 `0.0`
- `guided-walking-tours`: expected `2`, hit@5 `0`, recall@5 `0.0`
- `kids-workshops`: expected `2`, hit@5 `0`, recall@5 `0.0`
- `roman-history`: expected `2`, hit@5 `0`, recall@5 `0.0`
- `art-museums`: expected `2`, hit@5 `0`, recall@5 `0.0`
- `canal-river-cruises`: expected `2`, hit@5 `0`, recall@5 `0.0`
- `lake-swimming`: expected `1`, hit@5 `0`, recall@5 `0.0`
- `water-parks`: expected `1`, hit@5 `0`, recall@5 `0.0`
- `camping`: expected `1`, hit@5 `0`, recall@5 `0.0`
- `craft-cocktail-bars`: expected `1`, hit@5 `0`, recall@5 `0.0`

## Frequent False Positives

- `food-tours-guided`: false-positive top5 count `5`
- `wildlife-nature`: false-positive top5 count `5`
- `air-extreme-sports`: false-positive top5 count `4`
- `child-beaches`: false-positive top5 count `4`
- `wwii-history`: false-positive top5 count `4`
- `history-museums`: false-positive top5 count `3`
- `adventure-active`: false-positive top5 count `3`
- `child-activities`: false-positive top5 count `3`
- `cooking-classes`: false-positive top5 count `3`
- `foraging`: false-positive top5 count `3`
- `playgrounds-parks`: false-positive top5 count `3`
- `ruin-bars`: false-positive top5 count `3`

## Output Files

- Full JSON: `image_recognition_eval_prompt_max.json`
- Per-image CSV: `image_recognition_eval_prompt_max_per_image.csv`
- Category CSV: `image_recognition_eval_prompt_max_by_category.csv`
- Tag CSV: `image_recognition_eval_prompt_max_by_tag.csv`
- Failures CSV: `image_recognition_eval_prompt_max_failures.csv`
- Category chart: `image_recognition_eval_prompt_max_category_recall.png`
