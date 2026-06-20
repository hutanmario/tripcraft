from app.database import SessionLocal
from app.models.geography import City, Attraction
data = {'Dusseldorf': [{'name': 'Altstadt Dusseldorf', 'category': 'Urban & Modern', 'lat': 51.2267, 'lon': 6.7736}, {'name': 'Kunstsammlung NRW', 'category': 'Culture & History', 'lat': 51.2289, 'lon': 6.7867}], 'Orheiul Vechi': [{'name': 'Cave Monastery Orheiul Vechi', 'category': 'Culture & History', 'lat': 47.3833, 'lon': 29.0}], 'Tiraspol': [{'name': 'Tiraspol Fortress', 'category': 'Culture & History', 'lat': 46.8403, 'lon': 29.5997}], 'Cahul': [{'name': 'Cahul Park', 'category': 'Nature & Outdoors', 'lat': 45.9044, 'lon': 28.2056}], 'Comrat': [{'name': 'Comrat Regional Museum', 'category': 'Culture & History', 'lat': 46.2956, 'lon': 28.6678}], 'Purcari': [{'name': 'Purcari Winery', 'category': 'Food & Drink', 'lat': 46.7167, 'lon': 29.9167}], 'Hincesti': [{'name': 'Hincesti Park', 'category': 'Nature & Outdoors', 'lat': 46.8283, 'lon': 28.5856}]}
db = SessionLocal()
inserted = 0
for city_name, attractions in data.items():
    city = db.query(City).filter(City.name.ilike('%' + city_name + '%')).first()
    if not city:
        print('Not found: ' + city_name)
        continue
    for a in attractions:
        db.add(Attraction(name=a['name'], city_id=city.id, category=a['category'], latitude=a['lat'], longitude=a['lon']))
        inserted += 1
db.commit()
print('Inserted: ' + str(inserted))
db.close()
