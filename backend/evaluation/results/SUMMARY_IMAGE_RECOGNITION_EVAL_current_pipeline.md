# Image Recognition Evaluation

Generated at: `2026-06-12T11:30:37.771783+00:00`
Run name: `current_pipeline`
Prediction key: `matched_db_tags`

## Inputs

- Dataset: `evaluation/image_recognition_dataset.json`
- Predictions: `evaluation/results/image_baseline_current.json`
- Images: `47`
- Expected tags: `141`
- Mean predicted tags/image: `7.8511`

## Global Metrics

| K | Macro P@K | Micro P@K | Macro R@K | Micro R@K | F1@K | Hit-rate@K | MRR@K | MAP@K | NDCG@K |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 1 | 0.1702 | 0.1702 | 0.0567 | 0.0567 | 0.0851 | 0.1702 | 0.1702 | 0.1702 | 0.1702 |
| 3 | 0.1206 | 0.1206 | 0.1206 | 0.1206 | 0.1206 | 0.3191 | 0.234 | 0.0922 | 0.1327 |
| 5 | 0.0723 | 0.0723 | 0.1206 | 0.1206 | 0.0904 | 0.3191 | 0.234 | 0.0922 | 0.1327 |
| 10 | 0.0447 | 0.0447 | 0.1489 | 0.1489 | 0.0687 | 0.383 | 0.2419 | 0.0968 | 0.1453 |

## Diagnostic

- Zero-hit@5 rate: `0.6809`
- Full-recall@5 rate: `0.0`
- Main thesis baseline: `P@3=0.1206`, `R@5=0.1206`, `NDCG@5=0.1327`

## Category Breakdown

| Category | N | P@3 | R@5 | F1@5 | Hit-rate@5 | NDCG@5 | Zero-hit@5 |
|---|---:|---:|---:|---:|---:|---:|---:|
| family_comfort | 3 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 1.0 |
| nightlife_social | 5 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 1.0 |
| wellness_slow | 4 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 1.0 |
| culture_history | 7 | 0.0476 | 0.0476 | 0.0357 | 0.1429 | 0.0423 | 0.8571 |
| nature_outdoors | 6 | 0.0556 | 0.0556 | 0.0417 | 0.1667 | 0.0391 | 0.8333 |
| food_drink | 7 | 0.1429 | 0.1429 | 0.1071 | 0.4286 | 0.1516 | 0.5714 |
| urban_modern | 4 | 0.1667 | 0.1667 | 0.125 | 0.5 | 0.176 | 0.5 |
| beach_water | 7 | 0.1905 | 0.1905 | 0.1429 | 0.5714 | 0.2099 | 0.4286 |
| adventure_active | 2 | 0.5 | 0.5 | 0.375 | 1.0 | 0.6173 | 0.0 |
| winter | 2 | 0.5 | 0.5 | 0.375 | 1.0 | 0.6173 | 0.0 |

## Hardest Categories

- `family_comfort`: R@5 `0.0`, zero-hit@5 `1.0`
- `nightlife_social`: R@5 `0.0`, zero-hit@5 `1.0`
- `wellness_slow`: R@5 `0.0`, zero-hit@5 `1.0`
- `culture_history`: R@5 `0.0476`, zero-hit@5 `0.8571`
- `nature_outdoors`: R@5 `0.0556`, zero-hit@5 `0.8333`
- `food_drink`: R@5 `0.1429`, zero-hit@5 `0.5714`
- `urban_modern`: R@5 `0.1667`, zero-hit@5 `0.5`
- `beach_water`: R@5 `0.1905`, zero-hit@5 `0.4286`

## No-Hit Images

- `sandy_beaches` (beach_water): expected `sandy-beaches, hidden-coves, snorkeling-diving`, predicted top5 `winter-nature, glaciers, wildlife-nature`
- `beach_clubs` (beach_water): expected `beach-clubs, sandy-beaches, rooftop-bars`, predicted top5 `family-comfort, winter-nature, wellness-slow, cycling-biking, underground-clubs`
- `sailing` (beach_water): expected `sailing, cruises, canal-river-cruises`, predicted top5 `local-festivals, scuba-diving, sandy-beaches, family-comfort, underground-clubs`
- `day_hiking` (nature_outdoors): expected `day-hiking, hiking, photography-landscapes`, predicted top5 `rock-climbing, nature-outdoors, alpine-climbing, adventure-active, hiking-trekking`
- `multi_day_trekking` (nature_outdoors): expected `multi-day-trekking, hiking, camping`, predicted top5 `hiking-trekking, adventure-active, rock-climbing, family-comfort, nature-outdoors`
- `forest_bathing` (nature_outdoors): expected `forest-bathing, hiking, wildlife-watching`, predicted top5 `nature-outdoors, underground-clubs, adventure-active, hiking-trekking, holistic-health`
- `national_parks` (nature_outdoors): expected `national-parks, wildlife-watching, photography-landscapes`, predicted top5 `sandy-beaches, wildlife-nature, adventure-active`
- `birdwatching` (nature_outdoors): expected `birdwatching, wildlife-watching, national-parks`, predicted top5 `hiking-trekking, wildlife-nature, adventure-active, family-comfort, historical-sites`
- `castles_palaces` (culture_history): expected `castles-palaces, historical-sites, guided-walking-tours`, predicted top5 `family-comfort, cycling-biking, underground-clubs, wellness-slow, arts-museums`
- `gothic_architecture` (culture_history): expected `gothic-architecture, religious-sites, orthodox-churches`, predicted top5 `winter-nature, architecture, historical-sites, culture-history`
- `orthodox_churches` (culture_history): expected `orthodox-churches, religious-sites, vernacular-architecture`, predicted top5 `historical-sites, culture-history, wellness-slow, folk-traditions, family-comfort`
- `history_museums` (culture_history): expected `history-museums, historical-sites, roman-history`, predicted top5 `winter-nature, arts-museums, snowshoeing, contemporary-art, architecture`
- `roman_history` (culture_history): expected `roman-history, ancient-ruins, historical-sites`, predicted top5 `winter-nature, arts-museums, folk-traditions, sandy-beaches, contemporary-art`
- `art_museums` (culture_history): expected `historical-sites, vernacular-architecture, guided-walking-tours`, predicted top5 `winter-nature, contemporary-art, family-comfort, arts-museums, urban-modern`
- `contemporary_architecture` (urban_modern): expected `contemporary-architecture, modernist-architecture, tech-hubs`, predicted top5 `architecture, winter-nature, urban-modern, contemporary-art, arts-museums`
- ... plus `17` more in the failures CSV.

## Frequently Missed Tags

- `wildlife-watching`: expected `5`, hit@5 `0`, recall@5 `0.0`
- `photography-landscapes`: expected `4`, hit@5 `0`, recall@5 `0.0`
- `contemporary-architecture`: expected `3`, hit@5 `0`, recall@5 `0.0`
- `food-markets`: expected `3`, hit@5 `0`, recall@5 `0.0`
- `guided-walking-tours`: expected `3`, hit@5 `0`, recall@5 `0.0`
- `hiking`: expected `3`, hit@5 `0`, recall@5 `0.0`
- `national-parks`: expected `3`, hit@5 `0`, recall@5 `0.0`
- `spa-thermal`: expected `3`, hit@5 `0`, recall@5 `0.0`
- `thermal-baths`: expected `3`, hit@5 `0`, recall@5 `0.0`
- `underground-clubs`: expected `2`, hit@5 `0`, recall@5 `0.0`
- `ancient-ruins`: expected `2`, hit@5 `0`, recall@5 `0.0`
- `canal-river-cruises`: expected `2`, hit@5 `0`, recall@5 `0.0`

## Frequent False Positives

- `family-comfort`: false-positive top5 count `27`
- `winter-nature`: false-positive top5 count `19`
- `sandy-beaches`: false-positive top5 count `14`
- `contemporary-art`: false-positive top5 count `14`
- `adventure-active`: false-positive top5 count `13`
- `underground-clubs`: false-positive top5 count `12`
- `arts-museums`: false-positive top5 count `12`
- `hiking-trekking`: false-positive top5 count `9`
- `wellness-slow`: false-positive top5 count `8`
- `architecture`: false-positive top5 count `7`
- `culinary-learning`: false-positive top5 count `7`
- `cycling-biking`: false-positive top5 count `6`

## Output Files

- Full JSON: `image_recognition_eval_current_pipeline.json`
- Per-image CSV: `image_recognition_eval_current_pipeline_per_image.csv`
- Category CSV: `image_recognition_eval_current_pipeline_by_category.csv`
- Tag CSV: `image_recognition_eval_current_pipeline_by_tag.csv`
- Failures CSV: `image_recognition_eval_current_pipeline_failures.csv`
- Category chart: `image_recognition_eval_current_pipeline_category_recall.png`
