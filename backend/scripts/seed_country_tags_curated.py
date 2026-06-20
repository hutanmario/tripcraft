from app.database import SessionLocal
from app.models.geography import Country, country_tags
from app.models.destination import Tag
from sqlalchemy import delete, text

COUNTRY_TAGS = {
    "France": ["wine-vineyards", "michelin-restaurants", "art-museums", "castles-palaces", "cycling-biking", "local-festivals", "street-food", "fashion-weeks", "cooking-classes", "wine-bars", "opera-classical", "guided-walking-tours", "scenic-train-rides", "film-festivals", "food-tours-guided", "boutique-hotels", "contemporary-art", "designer-districts", "christmas-markets"],
    "Italy": ["michelin-restaurants", "ancient-ruins", "art-museums", "wine-vineyards", "cycling-biking", "sandy-beaches", "opera-classical", "cooking-classes", "street-food", "fashion-weeks", "roman-history", "scuba-diving", "sailing", "local-festivals", "wine-bars", "food-tours-guided", "boutique-hotels", "contemporary-art", "tasting-menus", "thermal-baths"],
    "Spain": ["street-food", "local-festivals", "sandy-beaches", "wine-vineyards", "art-museums", "cycling-biking", "flamenco", "michelin-restaurants", "surfing-kitesurfing", "sailing", "castles-palaces", "guided-walking-tours", "food-tours-guided", "wine-bars", "contemporary-art", "food-social-tours", "rooftop-bars", "techno-clubs", "fish-markets", "graffiti-tours"],
    "Germany": ["castles-palaces", "craft-beer", "cycling-biking", "christmas-markets", "art-museums", "techno-clubs", "opera-classical", "hiking", "history-museums", "street-food", "wwii-history", "contemporary-architecture", "music-festivals", "design-weeks", "factory-tours", "scenic-train-rides", "farmers-markets", "tech-hubs", "underground-clubs", "food-tours-guided"],
    "United Kingdom": ["art-museums", "castles-palaces", "theater-musicals", "pub-crawls", "cycling-biking", "history-museums", "street-food", "music-festivals", "guided-walking-tours", "fashion-weeks", "contemporary-art", "fish-markets", "specialty-coffee", "design-weeks", "rooftop-bars", "craft-beer", "thrifting-vintage", "opera-classical", "wwii-history", "jazz-live-music"],
    "Netherlands": ["cycling-biking", "art-museums", "canal-river-cruises", "street-food", "music-festivals", "craft-beer", "farmers-markets", "contemporary-art", "design-weeks", "specialty-coffee", "guided-walking-tours", "flea-markets", "food-tours-guided", "rooftop-bars", "tech-hubs", "jazz-live-music", "pop-up-events", "thrifting-vintage", "wine-bars", "food-social-tours"],
    "Belgium": ["craft-beer", "chocolate-culture", "art-museums", "waffles-culture", "cycling-biking", "castles-palaces", "local-festivals", "street-food", "comic-art", "food-tours-guided", "michelin-restaurants", "guided-walking-tours", "christmas-markets", "contemporary-art", "fish-markets", "wine-bars", "specialty-coffee", "flea-markets", "opera-classical", "food-social-tours"],
    "Switzerland": ["skiing", "hiking", "luxury-spa", "chocolate-culture", "scenic-train-rides", "cycling-biking", "thermal-baths", "glamping", "watches-shopping", "multi-day-trekking", "via-ferrata", "paragliding", "rock-climbing", "scenic-cable-cars", "lake-swimming", "yoga-retreats", "boutique-hotels", "snowshoeing", "stargazing", "wine-vineyards"],
    "Austria": ["opera-classical", "skiing", "castles-palaces", "cycling-biking", "christmas-markets", "thermal-baths", "hiking", "art-museums", "michelin-restaurants", "music-festivals", "wine-vineyards", "scenic-train-rides", "snowshoeing", "via-ferrata", "guided-walking-tours", "local-festivals", "specialty-coffee", "contemporary-art", "yoga-retreats", "food-tours-guided"],
    "Portugal": ["sandy-beaches", "wine-vineyards", "street-food", "surfing-kitesurfing", "cycling-biking", "ancient-ruins", "local-festivals", "sailing", "fish-markets", "coastal-walks", "food-tours-guided", "wine-bars", "guided-walking-tours", "scenic-drives", "kayaking-canoeing", "craft-beer", "specialty-coffee", "thrifting-vintage", "flea-markets", "contemporary-art"],
    "Greece": ["ancient-ruins", "sandy-beaches", "sailing", "street-food", "local-festivals", "wine-vineyards", "scuba-diving", "hiking", "roman-history", "coastal-walks", "snorkeling-diving", "kayaking-canoeing", "food-tours-guided", "guided-walking-tours", "fish-markets", "rooftop-bars", "stargazing", "photography-landscapes", "hidden-coves", "fishing"],
    "Sweden": ["cycling-biking", "northern-lights", "hiking", "design-weeks", "street-food", "music-festivals", "kayaking-canoeing", "fishing", "specialty-coffee", "contemporary-art", "skiing", "coastal-walks", "foraging", "forest-bathing", "digital-detox", "farmers-markets", "folk-traditions", "stargazing", "tech-hubs", "food-social-tours"],
    "Norway": ["northern-lights", "fjords", "hiking", "skiing", "whale-watching", "cycling-biking", "fishing", "kayaking-canoeing", "stargazing", "photography-landscapes", "multi-day-trekking", "snowmobile", "snowshoeing", "rock-climbing", "via-ferrata", "camping", "foraging", "coastal-walks", "scenic-drives", "birdwatching"],
    "Denmark": ["cycling-biking", "street-food", "castles-palaces", "sailing", "music-festivals", "specialty-coffee", "coastal-walks", "art-museums", "design-weeks", "food-tours-guided", "craft-beer", "contemporary-architecture", "farmers-markets", "kayaking-canoeing", "rooftop-bars", "fish-markets", "folk-traditions", "guided-walking-tours", "thrifting-vintage", "jazz-live-music"],
    "Finland": ["northern-lights", "hiking", "skiing", "fishing", "kayaking-canoeing", "foraging", "stargazing", "snowmobile", "snowshoeing", "digital-detox", "forest-bathing", "design-weeks", "folk-traditions", "camping", "silence-retreats", "photography-landscapes", "lake-swimming", "birdwatching", "food-social-tours", "specialty-coffee"],
    "Iceland": ["northern-lights", "hot-springs-outdoor", "hiking", "whale-watching", "photography-landscapes", "multi-day-trekking", "fishing", "stargazing", "snowmobile", "kayaking-canoeing", "scenic-drives", "horseback-riding", "camping", "snorkeling-diving", "rock-climbing", "birdwatching", "digital-detox", "fjords", "glaciers", "zip-lining"],
    "Ireland": ["pub-crawls", "coastal-walks", "hiking", "castles-palaces", "local-festivals", "music-festivals", "fishing", "cycling-biking", "guided-walking-tours", "folk-traditions", "craft-beer", "scenic-drives", "birdwatching", "horseback-riding", "photography-landscapes", "foraging", "kayaking-canoeing", "history-museums", "food-tours-guided", "food-social-tours"],
    "Poland": ["castles-palaces", "craft-beer", "street-food", "local-festivals", "cycling-biking", "art-museums", "history-museums", "christmas-markets", "wwii-history", "food-tours-guided", "guided-walking-tours", "folk-traditions", "contemporary-art", "thrifting-vintage", "techno-clubs", "ruin-bars", "specialty-coffee", "farmers-markets", "flea-markets", "hiking"],
    "Czech Republic": ["craft-beer", "castles-palaces", "street-food", "local-festivals", "cycling-biking", "art-museums", "christmas-markets", "guided-walking-tours", "food-tours-guided", "ruin-bars", "specialty-coffee", "thrifting-vintage", "folk-traditions", "contemporary-art", "opera-classical", "hiking", "wine-vineyards", "jazz-live-music", "thermal-baths", "history-museums"],
    "Hungary": ["thermal-baths", "castles-palaces", "wine-vineyards", "street-food", "local-festivals", "cycling-biking", "art-museums", "opera-classical", "ruin-bars", "food-tours-guided", "folk-traditions", "guided-walking-tours", "christmas-markets", "contemporary-art", "craft-beer", "jazz-live-music", "farmers-markets", "fishing", "horseback-riding", "history-museums"],
    "Romania": ["castles-palaces", "hiking", "local-festivals", "wine-vineyards", "wildlife-watching", "cycling-biking", "orthodox-churches", "folk-traditions", "skiing", "birdwatching", "horseback-riding", "foraging", "camping", "multi-day-trekking", "photography-landscapes", "thermal-baths", "fishing", "stargazing", "history-museums", "food-tours-guided"],
    "Croatia": ["sandy-beaches", "sailing", "local-festivals", "ancient-ruins", "coastal-walks", "wine-vineyards", "street-food", "cycling-biking", "scuba-diving", "snorkeling-diving", "kayaking-canoeing", "hidden-coves", "guided-walking-tours", "food-tours-guided", "rooftop-bars", "fish-markets", "rock-climbing", "photography-landscapes", "national-parks", "fishing"],
    "Slovakia": ["hiking", "castles-palaces", "skiing", "hot-springs-outdoor", "cycling-biking", "local-festivals", "caving-spelunking", "folk-traditions", "multi-day-trekking", "via-ferrata", "rock-climbing", "snowshoeing", "thermal-baths", "birdwatching", "horseback-riding", "foraging", "camping", "photography-landscapes", "fishing", "wine-vineyards"],
    "Slovenia": ["hiking", "skiing", "cycling-biking", "kayaking-canoeing", "caving-spelunking", "local-festivals", "sailing", "thermal-baths", "via-ferrata", "rock-climbing", "multi-day-trekking", "photography-landscapes", "lake-swimming", "foraging", "camping", "glamping", "stargazing", "birdwatching", "wine-vineyards", "food-tours-guided"],
    "Estonia": ["history-museums", "cycling-biking", "coastal-walks", "local-festivals", "hiking", "fishing", "kayaking-canoeing", "birdwatching", "foraging", "digital-detox", "folk-traditions", "photography-landscapes", "camping", "lake-swimming", "northern-lights", "art-museums", "tech-hubs", "guided-walking-tours", "food-social-tours", "contemporary-art"],
    "Latvia": ["history-museums", "cycling-biking", "local-festivals", "coastal-walks", "hiking", "art-museums", "folk-traditions", "fishing", "birdwatching", "foraging", "photography-landscapes", "camping", "lake-swimming", "northern-lights", "guided-walking-tours", "contemporary-art", "christmas-markets", "kayaking-canoeing", "food-social-tours", "food-tours-guided"],
    "Lithuania": ["history-museums", "cycling-biking", "local-festivals", "hiking", "folk-traditions", "coastal-walks", "birdwatching", "fishing", "foraging", "photography-landscapes", "camping", "art-museums", "guided-walking-tours", "northern-lights", "kayaking-canoeing", "lake-swimming", "contemporary-art", "christmas-markets", "food-social-tours", "food-tours-guided"],
    "Bulgaria": ["sandy-beaches", "hiking", "skiing", "wine-vineyards", "ancient-ruins", "orthodox-churches", "local-festivals", "cycling-biking", "wildlife-watching", "thermal-baths", "birdwatching", "horseback-riding", "folk-traditions", "foraging", "photography-landscapes", "camping", "rock-climbing", "multi-day-trekking", "fishing", "history-museums"],
    "Serbia": ["techno-clubs", "street-food", "local-festivals", "cycling-biking", "art-museums", "craft-beer", "music-festivals", "guided-walking-tours", "ruin-bars", "wine-vineyards", "folk-traditions", "contemporary-art", "specialty-coffee", "underground-clubs", "jazz-live-music", "fishing", "hiking", "farmers-markets", "food-tours-guided", "rooftop-bars"],
    "Albania": ["sandy-beaches", "hiking", "ancient-ruins", "local-festivals", "coastal-walks", "cycling-biking", "foraging", "photography-landscapes", "kayaking-canoeing", "birdwatching", "camping", "multi-day-trekking", "folk-traditions", "fishing", "snorkeling-diving", "hidden-coves", "rock-climbing", "via-ferrata", "food-tours-guided", "wine-vineyards"],
    "Bosnia and Herzegovina": ["hiking", "local-festivals", "cycling-biking", "ancient-ruins", "foraging", "kayaking-canoeing", "birdwatching", "camping", "multi-day-trekking", "folk-traditions", "photography-landscapes", "skiing", "fishing", "rock-climbing", "guided-walking-tours", "food-tours-guided", "street-food", "wine-vineyards", "orthodox-churches", "history-museums"],
    "Montenegro": ["sandy-beaches", "hiking", "sailing", "coastal-walks", "local-festivals", "cycling-biking", "kayaking-canoeing", "photography-landscapes", "scuba-diving", "snorkeling-diving", "hidden-coves", "fishing", "rock-climbing", "wine-vineyards", "camping", "birdwatching", "food-tours-guided", "multi-day-trekking", "national-parks", "guided-walking-tours"],
    "North Macedonia": ["hiking", "ancient-ruins", "local-festivals", "cycling-biking", "birdwatching", "folk-traditions", "photography-landscapes", "camping", "multi-day-trekking", "fishing", "kayaking-canoeing", "orthodox-churches", "wine-vineyards", "guided-walking-tours", "rock-climbing", "foraging", "lake-swimming", "national-parks", "food-tours-guided", "street-food"],
    "Kosovo": ["hiking", "local-festivals", "cycling-biking", "folk-traditions", "photography-landscapes", "camping", "multi-day-trekking", "ancient-ruins", "skiing", "rock-climbing", "birdwatching", "fishing", "guided-walking-tours", "foraging", "food-tours-guided", "street-food", "wine-vineyards", "via-ferrata", "orthodox-churches", "history-museums"],
    "Moldova": ["wine-vineyards", "local-festivals", "cycling-biking", "orthodox-churches", "folk-traditions", "caving-spelunking", "foraging", "fishing", "photography-landscapes", "camping", "food-tours-guided", "guided-walking-tours", "wine-bars", "farmers-markets", "birdwatching", "hiking", "horseback-riding", "cooking-classes", "street-food", "lake-swimming"],
    "Luxembourg": ["castles-palaces", "cycling-biking", "hiking", "wine-vineyards", "art-museums", "local-festivals", "guided-walking-tours", "christmas-markets", "contemporary-architecture", "food-tours-guided", "specialty-coffee", "farmers-markets", "scenic-drives", "photography-landscapes", "boutique-hotels", "michelin-restaurants", "craft-beer", "folk-traditions", "foraging", "birdwatching"],
    "Malta": ["sandy-beaches", "ancient-ruins", "scuba-diving", "sailing", "local-festivals", "fish-markets", "snorkeling-diving", "coastal-walks", "guided-walking-tours", "history-museums", "kayaking-canoeing", "food-tours-guided", "hidden-coves", "photography-landscapes", "roman-history", "street-food", "wine-vineyards", "rock-climbing", "birdwatching", "fishing"],
    "Cyprus": ["sandy-beaches", "ancient-ruins", "wine-vineyards", "hiking", "scuba-diving", "sailing", "local-festivals", "coastal-walks", "snorkeling-diving", "kayaking-canoeing", "hidden-coves", "photography-landscapes", "food-tours-guided", "guided-walking-tours", "fish-markets", "street-food", "birdwatching", "horseback-riding", "hot-springs-outdoor", "roman-history"],
    "Ukraine": ["art-museums", "orthodox-churches", "local-festivals", "cycling-biking", "ancient-ruins", "folk-traditions", "guided-walking-tours", "wine-vineyards", "photography-landscapes", "history-museums", "street-food", "food-tours-guided", "contemporary-art", "christmas-markets", "hiking", "birdwatching", "farmers-markets", "cooking-classes", "wwii-history", "specialty-coffee"],
}

def main():
    db = SessionLocal()

    db.execute(text("DELETE FROM country_tags"))
    db.commit()
    print("Deleted existing country_tags")

    inserted = 0
    not_found_tags = set()
    not_found_countries = []

    for country_name, tag_slugs in COUNTRY_TAGS.items():
        tag_slugs = list(dict.fromkeys(tag_slugs))

        country = db.query(Country).filter(Country.name == country_name).first()
        if not country:
            not_found_countries.append(country_name)
            continue

        seen_tag_ids = set()
        for i, slug in enumerate(tag_slugs):
            tag = db.query(Tag).filter(Tag.slug == slug).first()
            if not tag:
                not_found_tags.add(slug)
                continue
            if tag.id in seen_tag_ids:
                continue
            seen_tag_ids.add(tag.id)

            score = round(max(1.0 - (i * 0.03), 0.4), 2)

            db.execute(
                country_tags.insert().values(
                    country_id=country.id,
                    tag_id=tag.id,
                    score=score
                )
            )
            inserted += 1

    db.commit()
    print(f"Inserted: {inserted} country_tags")
    if not_found_countries:
        print(f"Countries not found: {not_found_countries}")
    if not_found_tags:
        print(f"Tags not found in DB: {not_found_tags}")
    db.close()

if __name__ == "__main__":
    main()