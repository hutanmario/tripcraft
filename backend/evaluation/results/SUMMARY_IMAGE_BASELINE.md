# Image Recognition Baseline

Generated at: `2026-06-12T11:30:30.300054+00:00`

## Dataset

- Path: `evaluation/image_recognition_dataset.json`
- Version: `2`
- Total images in manifest: `47`
- Selected images in run: `47`

## Aggregate

- Images: `47`
- Mean precision@3: `0.1206`
- Mean precision@5: `0.0723`
- Mean recall@5: `0.1206`
- Total processing time: `157.19s`

## Per Image

| Category | Image | Expected | Raw CLIP top 5 | Matched DB tags | Hits@5 | P@3 | R@5 |
|---|---|---|---|---|---|---:|---:|
| beach_water | sandy-beaches.jpg | sandy-beaches, hidden-coves, snorkeling-diving | wildlife, beach, family-friendly, offbeat, national-park | winter-nature, glaciers, wildlife-nature | - | 0.0 | 0.0 |
| beach_water | beach-clubs.jpg | beach-clubs, sandy-beaches, rooftop-bars | family-friendly, spa, cycling, offbeat, nightlife | family-comfort, winter-nature, wellness-slow, cycling-biking, underground-clubs, nightlife-social, beach-water, holistic-health, historical-sites, culture-history, contemporary-art | - | 0.0 | 0.0 |
| beach_water | coastal-walks.jpg | coastal-walks, photography-landscapes, sandy-beaches | beach, offbeat, family-friendly, national-park, unesco | beach-water, sandy-beaches, underground-clubs, family-comfort, cycling-biking, nature-outdoors, coastal-walks, culture-history, hiking-trekking, surfing-kitesurfing | sandy-beaches | 0.3333 | 0.3333 |
| beach_water | kayaking-canoeing.jpg | kayaking-canoeing, lake-swimming, canal-river-cruises | adventure, nature, lake, hiking, national-park | adventure-active, nature-outdoors, lake-swimming, hiking-trekking, family-comfort, underground-clubs, cycling-biking, romantic-couple, sandy-beaches, alpine-climbing, rock-climbing, contemporary-art, drinks-tastings, historical-sites | lake-swimming | 0.3333 | 0.3333 |
| beach_water | sailing.jpg | sailing, cruises, canal-river-cruises | diving, family-friendly, offbeat, adventure, lake | local-festivals, scuba-diving, sandy-beaches, family-comfort, underground-clubs, adventure-active, lake-swimming, contemporary-art, drinks-tastings | - | 0.0 | 0.0 |
| beach_water | scuba-diving.jpg | scuba-diving, snorkeling-diving, water-sports | diving, family-friendly, national-park, unesco, religious | scuba-diving, sandy-beaches, family-comfort, historical-sites, underground-clubs, nature-outdoors | scuba-diving | 0.3333 | 0.3333 |
| beach_water | surfing-kitesurfing.jpg | surfing-kitesurfing, water-sports, sandy-beaches | family-friendly, cycling, offbeat, local-culture, art | sandy-beaches, family-comfort, cycling-biking, underground-clubs, contemporary-art, adventure-active, beach-water, winter-nature | sandy-beaches | 0.3333 | 0.3333 |
| nature_outdoors | day-hiking.jpg | day-hiking, hiking, photography-landscapes | hiking, climbing, nature, mountain, offbeat | rock-climbing, nature-outdoors, alpine-climbing, adventure-active, hiking-trekking, underground-clubs, family-comfort, sandy-beaches, cycling-biking, historical-sites | - | 0.0 | 0.0 |
| nature_outdoors | multi-day-trekking.jpg | multi-day-trekking, hiking, camping | hiking, adventure, climbing, family-friendly, nature | hiking-trekking, adventure-active, rock-climbing, family-comfort, nature-outdoors, underground-clubs, alpine-climbing | - | 0.0 | 0.0 |
| adventure_active | alpine-climbing.jpg | alpine-climbing, rock-climbing, glaciers | climbing, mountain, hiking, adventure, nature | rock-climbing, alpine-climbing, adventure-active, sandy-beaches, hiking-trekking, nature-outdoors, family-comfort, romantic-couple | alpine-climbing, rock-climbing | 0.6667 | 0.6667 |
| adventure_active | rock-climbing.jpg | rock-climbing, via-ferrata, alpine-climbing | climbing, adventure, family-friendly, local-culture, offbeat | rock-climbing, winter-nature, adventure-active, family-comfort, glaciers, hiking-trekking, underground-clubs | rock-climbing | 0.3333 | 0.3333 |
| winter | skiing.jpg | skiing, winter-nature, snowshoeing | skiing, mountain, family-friendly, spa, climbing | winter-nature, alpine-climbing, adventure-active, family-comfort, wellness-slow, rock-climbing, nature-outdoors, underground-clubs, drinks-tastings, cycling-biking | winter-nature | 0.3333 | 0.3333 |
| winter | glaciers.jpg | glaciers, winter-nature, photography-landscapes | climbing, nature, mountain, hiking, adventure | winter-nature, glaciers, snowshoeing | glaciers, winter-nature | 0.6667 | 0.6667 |
| nature_outdoors | forest-bathing.jpg | forest-bathing, hiking, wildlife-watching | nature, hiking, forest, national-park, offbeat | nature-outdoors, underground-clubs, adventure-active, hiking-trekking, holistic-health, wellness-slow, water-parks, romantic-couple, nightlife-social | - | 0.0 | 0.0 |
| nature_outdoors | national-parks.jpg | national-parks, wildlife-watching, photography-landscapes | wildlife, adventure, family-friendly, national-park, nature | sandy-beaches, wildlife-nature, adventure-active | - | 0.0 | 0.0 |
| nature_outdoors | wildlife-watching.jpg | wildlife-watching, wildlife-nature, national-parks | wildlife, hiking, adventure, nature, offbeat | winter-nature, sandy-beaches, wildlife-nature, hiking-trekking, adventure-active | wildlife-nature | 0.3333 | 0.3333 |
| nature_outdoors | birdwatching.jpg | birdwatching, wildlife-watching, national-parks | wildlife, hiking, adventure, family-friendly, religious | hiking-trekking, wildlife-nature, adventure-active, family-comfort, historical-sites, cycling-biking, contemporary-art, nature-outdoors, sandy-beaches, underground-clubs | - | 0.0 | 0.0 |
| culture_history | castles-palaces.jpg | castles-palaces, historical-sites, guided-walking-tours | family-friendly, cycling, offbeat, spa, museums | family-comfort, cycling-biking, underground-clubs, wellness-slow, arts-museums, architecture, historical-sites, drinks-tastings, culture-history, contemporary-art, holistic-health, sandy-beaches | - | 0.0 | 0.0 |
| culture_history | ancient-ruins.jpg | ancient-ruins, historical-sites, guided-walking-tours | ancient-ruins, history, religious, family-friendly, unesco | culture-history, historical-sites, family-comfort, contemporary-art, wellness-slow, underground-clubs, arts-museums, architecture, drinks-tastings | historical-sites | 0.3333 | 0.3333 |
| culture_history | gothic-architecture.jpg | gothic-architecture, religious-sites, orthodox-churches | unesco, architecture, culture, religious, history | winter-nature, architecture, historical-sites, culture-history | - | 0.0 | 0.0 |
| culture_history | orthodox-churches.jpg | orthodox-churches, religious-sites, vernacular-architecture | religious, unesco, history, spa, traditional | historical-sites, culture-history, wellness-slow, folk-traditions, family-comfort, architecture, arts-museums, underground-clubs, contemporary-art, cycling-biking, sandy-beaches, drinks-tastings | - | 0.0 | 0.0 |
| culture_history | history-museums.jpg | history-museums, historical-sites, roman-history | museums, art, architecture, adventure, family-friendly | winter-nature, arts-museums, snowshoeing, contemporary-art, architecture | - | 0.0 | 0.0 |
| culture_history | roman-history.jpg | roman-history, ancient-ruins, historical-sites | museums, traditional, art, culture, family-friendly | winter-nature, arts-museums, folk-traditions, sandy-beaches, contemporary-art, family-comfort | - | 0.0 | 0.0 |
| culture_history | art-museums.jpg | historical-sites, vernacular-architecture, guided-walking-tours | art, family-friendly, museums, shopping, spa | winter-nature, contemporary-art, family-comfort, arts-museums, urban-modern, wellness-slow, cycling-biking, historical-sites, architecture, underground-clubs, culture-history | - | 0.0 | 0.0 |
| urban_modern | contemporary-art.jpg | contemporary-art, contemporary-architecture, modernist-architecture | museums, art, family-friendly, gastronomy, spa | arts-museums, winter-nature, contemporary-art, family-comfort, culinary-learning, wellness-slow, architecture, drinks-tastings, underground-clubs, cycling-biking, historical-sites | contemporary-art | 0.3333 | 0.3333 |
| urban_modern | street-art.jpg | street-art, graffiti-tours, contemporary-art | art, family-friendly, museums, local-culture, architecture | contemporary-art, sandy-beaches, family-comfort, arts-museums, architecture, nightlife-social, cycling-biking, underground-clubs, urban-modern | contemporary-art | 0.3333 | 0.3333 |
| urban_modern | contemporary-architecture.jpg | contemporary-architecture, modernist-architecture, tech-hubs | architecture, modern, urban, art, museums | architecture, winter-nature, urban-modern, contemporary-art, arts-museums | - | 0.0 | 0.0 |
| urban_modern | brutalist-architecture.jpg | brutalist-architecture, contemporary-architecture, photography-urban | urban, architecture, unesco, modern, art | winter-nature, snowshoeing, glaciers, urban-modern | - | 0.0 | 0.0 |
| food_drink | street-food.jpg | farmers-markets, food-markets, street-casual-food | street-food, shopping, gastronomy, festivals, family-friendly | urban-modern, street-casual-food, culinary-learning, family-comfort, contemporary-art, folk-traditions, underground-clubs, drinks-tastings, cycling-biking, historical-sites, wellness-slow | street-casual-food | 0.3333 | 0.3333 |
| food_drink | food-trucks.jpg | food-trucks, street-food, street-casual-food | gastronomy, street-food, local-culture, nightlife, family-friendly | culinary-learning, street-casual-food, nightlife-social, family-comfort, sandy-beaches, underground-clubs, cycling-biking, drinks-tastings | street-casual-food | 0.3333 | 0.3333 |
| food_drink | farmers-markets.jpg | farmers-markets, food-markets, local-artisan-shops | gastronomy, street-food, local-culture, wine-tasting, family-friendly | culinary-learning, street-casual-food, drinks-tastings, family-comfort, sandy-beaches, cycling-biking, underground-clubs | - | 0.0 | 0.0 |
| food_drink | fish-markets.jpg | fish-markets, food-markets, street-food | gastronomy, street-food, local-culture, adventure, religious | culinary-learning, adventure-active, street-casual-food, historical-sites, nightlife-social, urban-modern, family-comfort, water-sports, folk-traditions, underground-clubs, contemporary-art | - | 0.0 | 0.0 |
| food_drink | michelin-restaurants.jpg | michelin-restaurants, tasting-menus, fine-dining-exp | gastronomy, local-culture, offbeat, wine-tasting, art | winter-nature, culinary-learning, glaciers, underground-clubs, drinks-tastings | - | 0.0 | 0.0 |
| food_drink | wine-vineyards.jpg | wine-vineyards, wine-bars, drinks-tastings | wine-tasting, family-friendly, cycling, offbeat, local-culture | drinks-tastings, family-comfort, cycling-biking, underground-clubs, hiking-trekking, culinary-learning, historical-sites, nature-outdoors, contemporary-art, adventure-active, countryside-walks, romantic-couple | drinks-tastings | 0.3333 | 0.3333 |
| food_drink | specialty-coffee.jpg | specialty-coffee, bakeries-pastries, street-casual-food | art, family-friendly, local-culture, gastronomy, wine-tasting | contemporary-art, family-comfort, culinary-learning, drinks-tastings, underground-clubs, cycling-biking, folk-traditions, arts-museums, wellness-slow, street-casual-food, adventure-active | - | 0.0 | 0.0 |
| nightlife_social | rooftop-bars.jpg | rooftop-bars, rooftop-views, craft-cocktail-bars | modern, urban, architecture, art, wellness | urban-modern, architecture, contemporary-art, winter-nature, holistic-health, wellness-slow | - | 0.0 | 0.0 |
| nightlife_social | underground-clubs.jpg | underground-clubs, techno-clubs, clubbing | nightlife, local-culture, castles, urban, traditional | winter-nature, nightlife-social, bar-scene | - | 0.0 | 0.0 |
| nightlife_social | techno-clubs.jpg | techno-clubs, underground-clubs, clubbing | nightlife, art, local-culture, family-friendly, museums | winter-nature, nightlife-social, contemporary-art, family-comfort | - | 0.0 | 0.0 |
| nightlife_social | jazz-live-music.jpg | jazz-live-music, live-entertainment, music-festivals | nightlife, offbeat, art, local-culture, family-friendly | nightlife-social, winter-nature, underground-clubs, contemporary-art, family-comfort, bar-scene | - | 0.0 | 0.0 |
| nightlife_social | theater-musicals.jpg | theater-musicals, live-entertainment, opera-classical | art, museums, architecture, nightlife, family-friendly | winter-nature, contemporary-art, arts-museums, architecture, snowshoeing, nightlife-social, family-comfort | - | 0.0 | 0.0 |
| wellness_slow | thermal-baths.jpg | thermal-baths, spa-thermal, hot-springs-outdoor | hiking, unesco, spa, national-park, nature | sandy-beaches, hiking-trekking, wellness-slow | - | 0.0 | 0.0 |
| wellness_slow | hammam.jpg | hammam, spa-thermal, thermal-baths | history, museums, culture, ancient-ruins, traditional | winter-nature, sandy-beaches, historical-sites, culture-history, arts-museums | - | 0.0 | 0.0 |
| wellness_slow | yoga-retreats.jpg | yoga-retreats, meditation-centers, mindfulness-retreats | wellness, spa, diving, offbeat, religious | holistic-health, wellness-slow, scuba-diving, sandy-beaches, underground-clubs, historical-sites, family-comfort, hiking-trekking, cycling-biking, contemporary-art, rock-climbing, nature-outdoors, nightlife-social, adventure-active | - | 0.0 | 0.0 |
| wellness_slow | luxury-spa.jpg | luxury-spa, spa-thermal, thermal-baths | wellness, spa, family-friendly, culture, traditional | sandy-beaches, holistic-health, wellness-slow, family-comfort, folk-traditions, historical-sites, adventure-active | - | 0.0 | 0.0 |
| family_comfort | science-museums.jpg | science-museums, science-interactive-museums, science-centers | museums, art, family-friendly, architecture, unesco | arts-museums, contemporary-art, sandy-beaches, family-comfort, architecture, historical-sites, wellness-slow | - | 0.0 | 0.0 |
| family_comfort | zoos-aquariums.jpg | zoos-aquariums, wildlife-watching, kids-workshops | art, family-friendly, museums, adventure, local-culture | winter-nature, contemporary-art, family-comfort, arts-museums, adventure-active, nightlife-social, historical-sites, urban-modern, underground-clubs, folk-traditions, wellness-slow | - | 0.0 | 0.0 |
| family_comfort | theme-parks.jpg | theme-parks, water-parks, kids-workshops | family-friendly, adventure, nightlife, museums, cycling | family-comfort, adventure-active, nightlife-social, arts-museums, cycling-biking, underground-clubs, contemporary-art, urban-modern, drinks-tastings, architecture | - | 0.0 | 0.0 |

## Files

- JSON: `image_baseline_current.json`
- CSV: `image_baseline_current.csv`

## Notes

- `expected_tags` sunt repere manuale initiale, nu un dataset final validat.
- Acest baseline masoara pipeline-ul curent, inclusiv mapping-ul semantic din `ml.py`.
- Urmatorul pas este sa comparam acest baseline cu un pipeline multi-prompt pe tagurile reale.
