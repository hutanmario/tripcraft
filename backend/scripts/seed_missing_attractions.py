import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.database import SessionLocal
from app.models.geography import Attraction, City

ATTRACTIONS_DATA = {
    "Turin": [
        {"name": "Mole Antonelliana", "category": "Culture & History", "lat": 45.0693, "lon": 7.6927},
        {"name": "Palazzo Reale di Torino", "category": "Culture & History", "lat": 45.0732, "lon": 7.6858},
        {"name": "Museo Egizio", "category": "Culture & History", "lat": 45.0677, "lon": 7.6844},
        {"name": "Piazza Castello", "category": "Urban & Modern", "lat": 45.0727, "lon": 7.6858},
    ],
    "Florence": [
        {"name": "Galleria degli Uffizi", "category": "Culture & History", "lat": 43.7677, "lon": 11.2553},
        {"name": "Cattedrale di Santa Maria del Fiore", "category": "Culture & History", "lat": 43.7731, "lon": 11.2560},
        {"name": "Ponte Vecchio", "category": "Urban & Modern", "lat": 43.7679, "lon": 11.2531},
        {"name": "Piazzale Michelangelo", "category": "Nature & Outdoors", "lat": 43.7629, "lon": 11.2648},
    ],
    "Bologna": [
        {"name": "Piazza Maggiore", "category": "Urban & Modern", "lat": 44.4939, "lon": 11.3428},
        {"name": "Due Torri", "category": "Culture & History", "lat": 44.4944, "lon": 11.3469},
        {"name": "Basilica di San Petronio", "category": "Culture & History", "lat": 44.4932, "lon": 11.3427},
        {"name": "Archiginnasio di Bologna", "category": "Culture & History", "lat": 44.4928, "lon": 11.3431},
    ],
    "Palermo": [
        {"name": "Cattedrale di Palermo", "category": "Culture & History", "lat": 38.1117, "lon": 13.3561},
        {"name": "Teatro Massimo", "category": "Culture & History", "lat": 38.1197, "lon": 13.3617},
        {"name": "Mercato di Ballarò", "category": "Food & Drink", "lat": 38.1108, "lon": 13.3558},
        {"name": "Palazzo dei Normanni", "category": "Culture & History", "lat": 38.1108, "lon": 13.3522},
    ],
    "Genoa": [
        {"name": "Caruggi di Genova", "category": "Urban & Modern", "lat": 44.4072, "lon": 8.9330},
        {"name": "Palazzo Ducale", "category": "Culture & History", "lat": 44.4073, "lon": 8.9340},
        {"name": "Acquario di Genova", "category": "Adventure & Active", "lat": 44.4121, "lon": 8.9232},
        {"name": "Boccadasse", "category": "Nature & Outdoors", "lat": 44.3952, "lon": 9.0013},
    ],
    "Verona": [
        {"name": "Arena di Verona", "category": "Culture & History", "lat": 45.4386, "lon": 10.9942},
        {"name": "Casa di Giulietta", "category": "Culture & History", "lat": 45.4424, "lon": 10.9984},
        {"name": "Piazza delle Erbe", "category": "Urban & Modern", "lat": 45.4425, "lon": 10.9978},
        {"name": "Castelvecchio", "category": "Culture & History", "lat": 45.4408, "lon": 10.9877},
    ],
    "Bath": [
        {"name": "Roman Baths", "category": "Culture & History", "lat": 51.3813, "lon": -2.3596},
        {"name": "Bath Abbey", "category": "Culture & History", "lat": 51.3814, "lon": -2.3590},
        {"name": "Royal Crescent", "category": "Urban & Modern", "lat": 51.3855, "lon": -2.3674},
        {"name": "Thermae Bath Spa", "category": "Adventure & Active", "lat": 51.3804, "lon": -2.3601},
    ],
    "Braga": [
        {"name": "Bom Jesus do Monte", "category": "Culture & History", "lat": 41.5503, "lon": -8.3856},
        {"name": "Sé de Braga", "category": "Culture & History", "lat": 41.5504, "lon": -8.4267},
        {"name": "Jardins de Santa Bárbara", "category": "Nature & Outdoors", "lat": 41.5499, "lon": -8.4271},
        {"name": "Museu dos Biscainhos", "category": "Culture & History", "lat": 41.5516, "lon": -8.4297},
    ],
    "Cordoba": [
        {"name": "Mezquita-Catedral de Córdoba", "category": "Culture & History", "lat": 37.8789, "lon": -4.7794},
        {"name": "Alcázar de los Reyes Cristianos", "category": "Culture & History", "lat": 37.8760, "lon": -4.7816},
        {"name": "Barrio de la Judería", "category": "Urban & Modern", "lat": 37.8797, "lon": -4.7808},
        {"name": "Puente Romano", "category": "Culture & History", "lat": 37.8770, "lon": -4.7791},
    ],
    "Leipzig": [
        {"name": "Völkerschlachtdenkmal", "category": "Culture & History", "lat": 51.3128, "lon": 12.4131},
        {"name": "Thomaskirche", "category": "Culture & History", "lat": 51.3391, "lon": 12.3733},
        {"name": "Markt Leipzig", "category": "Urban & Modern", "lat": 51.3406, "lon": 12.3747},
        {"name": "Zoo Leipzig", "category": "Nature & Outdoors", "lat": 51.3508, "lon": 12.3694},
    ],
    "Stuttgart": [
        {"name": "Schlossplatz", "category": "Urban & Modern", "lat": 48.7784, "lon": 9.1800},
        {"name": "Staatsgalerie Stuttgart", "category": "Culture & History", "lat": 48.7800, "lon": 9.1856},
        {"name": "Mercedes-Benz Museum", "category": "Culture & History", "lat": 48.7880, "lon": 9.2320},
        {"name": "Wilhelma Zoo", "category": "Nature & Outdoors", "lat": 48.8061, "lon": 9.2072},
    ],
    "Evora": [
        {"name": "Templo Romano de Évora", "category": "Culture & History", "lat": 38.5722, "lon": -7.9073},
        {"name": "Catedral de Évora", "category": "Culture & History", "lat": 38.5718, "lon": -7.9083},
        {"name": "Capela dos Ossos", "category": "Culture & History", "lat": 38.5699, "lon": -7.9063},
        {"name": "Jardim Público de Évora", "category": "Nature & Outdoors", "lat": 38.5685, "lon": -7.9072},
    ],
    "Leiden": [
        {"name": "Rijksmuseum van Oudheden", "category": "Culture & History", "lat": 52.1579, "lon": 4.4930},
        {"name": "Burcht van Leiden", "category": "Culture & History", "lat": 52.1591, "lon": 4.4928},
        {"name": "Hortus Botanicus Leiden", "category": "Nature & Outdoors", "lat": 52.1572, "lon": 4.4906},
        {"name": "Pieterskerk Leiden", "category": "Culture & History", "lat": 52.1578, "lon": 4.4921},
    ],
}


def main():
    db = SessionLocal()
    inserted = 0
    skipped = 0

    for city_name, attractions in ATTRACTIONS_DATA.items():
        city = db.query(City).filter(City.name == city_name).first()
        if not city:
            print(f"City not found: {city_name}")
            continue
        for a in attractions:
            existing = db.query(Attraction).filter(
                Attraction.name == a["name"],
                Attraction.city_id == city.id
            ).first()
            if existing:
                skipped += 1
                continue
            db.add(Attraction(
                name=a["name"],
                city_id=city.id,
                category=a["category"],
                latitude=a["lat"],
                longitude=a["lon"],
            ))
            inserted += 1

    db.commit()
    print(f"Inserted: {inserted}, Skipped: {skipped}")
    db.close()


if __name__ == "__main__":
    main()
