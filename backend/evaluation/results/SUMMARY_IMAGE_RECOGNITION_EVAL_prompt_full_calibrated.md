# Image Recognition Evaluation

Generated at: `2026-06-12T11:40:17.512608+00:00`
Run name: `prompt_full_calibrated`
Prediction key: `matched_db_tags`

## Inputs

- Dataset: `evaluation/image_recognition_dataset_full.json`
- Predictions: `evaluation/results/image_prompt_multitag_full_calibrated_predictions.json`
- Images: `201`
- Expected tags: `358`
- Mean predicted tags/image: `20.0`

## Global Metrics

| K | Macro P@K | Micro P@K | Macro R@K | Micro R@K | F1@K | Hit-rate@K | MRR@K | MAP@K | NDCG@K |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 1 | 0.5274 | 0.5274 | 0.2861 | 0.2961 | 0.3665 | 0.5274 | 0.5274 | 0.5274 | 0.5274 |
| 3 | 0.3433 | 0.3433 | 0.5572 | 0.5782 | 0.4204 | 0.7313 | 0.6219 | 0.4735 | 0.5319 |
| 5 | 0.2328 | 0.2328 | 0.6393 | 0.6536 | 0.3381 | 0.791 | 0.6351 | 0.5001 | 0.5701 |
| 10 | 0.1318 | 0.1318 | 0.7313 | 0.7402 | 0.2219 | 0.8706 | 0.645 | 0.5166 | 0.6038 |

## Diagnostic

- Zero-hit@5 rate: `0.209`
- Full-recall@5 rate: `0.4876`
- Main thesis baseline: `P@3=0.3433`, `R@5=0.6393`, `NDCG@5=0.5701`

## Category Breakdown

| Category | N | P@3 | R@5 | F1@5 | Hit-rate@5 | NDCG@5 | Zero-hit@5 |
|---|---:|---:|---:|---:|---:|---:|---:|
| family_comfort | 20 | 0.2167 | 0.425 | 0.219 | 0.7 | 0.3617 | 0.3 |
| urban_modern | 21 | 0.2381 | 0.4762 | 0.2608 | 0.619 | 0.4172 | 0.381 |
| wellness_slow | 22 | 0.303 | 0.5455 | 0.29 | 0.6818 | 0.5053 | 0.3182 |
| nightlife_social | 25 | 0.32 | 0.62 | 0.3257 | 0.76 | 0.512 | 0.24 |
| food_drink | 23 | 0.3768 | 0.6957 | 0.3561 | 0.7826 | 0.6257 | 0.2174 |
| culture_history | 28 | 0.369 | 0.6964 | 0.3724 | 0.8929 | 0.6166 | 0.1071 |
| nature_outdoors | 35 | 0.4286 | 0.7429 | 0.3973 | 0.8857 | 0.6868 | 0.1143 |
| adventure_active | 27 | 0.4074 | 0.7778 | 0.4092 | 0.8889 | 0.7029 | 0.1111 |

## Hardest Categories

- `family_comfort`: R@5 `0.425`, zero-hit@5 `0.3`
- `urban_modern`: R@5 `0.4762`, zero-hit@5 `0.381`
- `wellness_slow`: R@5 `0.5455`, zero-hit@5 `0.3182`
- `nightlife_social`: R@5 `0.62`, zero-hit@5 `0.24`
- `food_drink`: R@5 `0.6957`, zero-hit@5 `0.2174`
- `culture_history`: R@5 `0.6964`, zero-hit@5 `0.1071`
- `nature_outdoors`: R@5 `0.7429`, zero-hit@5 `0.1143`
- `adventure_active`: R@5 `0.7778`, zero-hit@5 `0.1111`

## No-Hit Images

- `accessible_attractions` (family_comfort): expected `accessible-attractions, easy-sightseeing`, predicted top5 `countryside-walks, forest-bathing, silent-retreats, digital-detox, contemplative-nature`
- `adventure_active` (adventure_active): expected `adventure-active`, predicted top5 `hiking, day-hiking, running-marathons, forest-bathing, multi-day-trekking`
- `all_inclusive_resorts` (family_comfort): expected `all-inclusive-resorts, comfort-accommodation`, predicted top5 `luxury-spa, ayurveda, yoga-retreats, silent-retreats, boutique-hotels`
- `architecture` (culture_history): expected `architecture`, predicted top5 `modernist-architecture, contemporary-architecture, contemporary-art, vernacular-architecture, design-weeks`
- `art_museums` (culture_history): expected `art-museums, arts-museums`, predicted top5 `historical-sites, castles-palaces, vernacular-architecture, thermal-baths, folk-traditions`
- `ayurveda` (wellness_slow): expected `ayurveda, holistic-health`, predicted top5 `community-experiences, farm-to-table, living-culture, traditional-crafts, cooking-classes`
- `bar_scene` (nightlife_social): expected `bar-scene`, predicted top5 `underground-clubs, arcade-bars, contemporary-art, speakeasy-bars, techno-clubs`
- `beach_water` (nature_outdoors): expected `beach-water`, predicted top5 `hammam, water-parks, beach-clubs, sandy-beaches, child-beaches`
- `camping` (nature_outdoors): expected `camping, contemplative-nature`, predicted top5 `horseback-riding, sandy-beaches, wildlife-nature, wildlife-watching, coastal-walks`
- `comfort_accommodation` (family_comfort): expected `comfort-accommodation`, predicted top5 `glamping-family, glamping, camping, motor-sports, digital-detox`
- `culture_history` (culture_history): expected `culture-history`, predicted top5 `ancient-ruins, historical-sites, guided-walking-tours, religious-sites, art-museums`
- `digital_detox` (wellness_slow): expected `digital-detox, mindfulness-retreats`, predicted top5 `watches-shopping, tech-hubs, factory-tours, arts-museums, design-weeks`
- `easy_sightseeing` (family_comfort): expected `easy-sightseeing`, predicted top5 `social-tours, guided-walking-tours, instagram-spots, meetup-events, community-experiences`
- `factory_tours` (urban_modern): expected `factory-tours, tech-innovation`, predicted top5 `graffiti-tours, pub-crawls, ruin-bars, street-art, craft-beer`
- `family_comfort` (family_comfort): expected `family-comfort`, predicted top5 `family-attractions, child-activities, sound-therapy, silent-retreats, contemplative-nature`
- ... plus `27` more in the failures CSV.

## Frequently Missed Tags

- `architecture`: expected `6`, hit@5 `0`, recall@5 `0.0`
- `beach-water`: expected `5`, hit@5 `0`, recall@5 `0.0`
- `comfort-accommodation`: expected `5`, hit@5 `0`, recall@5 `0.0`
- `easy-sightseeing`: expected `5`, hit@5 `0`, recall@5 `0.0`
- `social-tours`: expected `3`, hit@5 `0`, recall@5 `0.0`
- `tech-innovation`: expected `3`, hit@5 `0`, recall@5 `0.0`
- `digital-detox`: expected `1`, hit@5 `0`, recall@5 `0.0`
- `art-museums`: expected `1`, hit@5 `0`, recall@5 `0.0`
- `scenic-drives`: expected `1`, hit@5 `0`, recall@5 `0.0`
- `meetup-events`: expected `1`, hit@5 `0`, recall@5 `0.0`
- `sports-bars`: expected `1`, hit@5 `0`, recall@5 `0.0`
- `street-food`: expected `1`, hit@5 `0`, recall@5 `0.0`

## Frequent False Positives

- `silent-retreats`: false-positive top5 count `16`
- `contemplative-nature`: false-positive top5 count `15`
- `mindfulness-retreats`: false-positive top5 count `13`
- `community-experiences`: false-positive top5 count `12`
- `modernist-architecture`: false-positive top5 count `11`
- `forest-bathing`: false-positive top5 count `10`
- `silence-retreats`: false-positive top5 count `10`
- `digital-detox`: false-positive top5 count `9`
- `photography-urban`: false-positive top5 count `9`
- `street-casual-food`: false-positive top5 count `9`
- `wildlife-nature`: false-positive top5 count `9`
- `historical-sites`: false-positive top5 count `9`

## Output Files

- Full JSON: `image_recognition_eval_prompt_full_calibrated.json`
- Per-image CSV: `image_recognition_eval_prompt_full_calibrated_per_image.csv`
- Category CSV: `image_recognition_eval_prompt_full_calibrated_by_category.csv`
- Tag CSV: `image_recognition_eval_prompt_full_calibrated_by_tag.csv`
- Failures CSV: `image_recognition_eval_prompt_full_calibrated_failures.csv`
- Category chart: `image_recognition_eval_prompt_full_calibrated_category_recall.png`
