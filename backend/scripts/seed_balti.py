from app.database import SessionLocal
from app.models.geography import Attraction
db = SessionLocal()
attrs = [
    Attraction(name='Balti Central Park', city_id=730, category='Nature & Outdoors', latitude=47.7617, longitude=27.9297),
    Attraction(name='Balti City Museum', city_id=730, category='Culture & History', latitude=47.7622, longitude=27.9303),
    Attraction(name='Assumption Cathedral Balti', city_id=730, category='Culture & History', latitude=47.7628, longitude=27.9311),
]
for a in attrs:
    db.add(a)
db.commit()
print('Done')
db.close()
