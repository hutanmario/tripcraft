from app.database import SessionLocal
from app.models.geography import Attraction
db = SessionLocal()
attrs = [
    Attraction(name='Altstadt Dusseldorf', city_id=433, category='Urban & Modern', latitude=51.2267, longitude=6.7736),
    Attraction(name='Rheinturm Tower', city_id=433, category='Urban & Modern', latitude=51.2164, longitude=6.7644),
    Attraction(name='Kunstsammlung NRW', city_id=433, category='Culture & History', latitude=51.2289, longitude=6.7867),
    Attraction(name='Hincesti Park', city_id=736, category='Nature & Outdoors', latitude=46.8283, longitude=28.5856),
    Attraction(name='Hincesti Market', city_id=736, category='Urban & Modern', latitude=46.8278, longitude=28.5850),
]
for a in attrs:
    db.add(a)
db.commit()
print('Done')
db.close()
