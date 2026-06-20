"""
seed_cities.py
==============
~220 orașe europene cu taguri SPECIFICE și diferențiate.
Fiecare oraș are 4-6 taguri care îl definesc unic.

Rulare:
    cd backend
    venv\Scripts\python.exe data/seed_cities.py
"""

import sys, os, time, requests
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.database import SessionLocal
from app.models.geography import Country, City, city_tags
from app.models.destination import Tag
from app.config import settings

CITIES = [

    # ══ FRANCE ════════════════════════════════════════════════════════════════
    ("FR","Paris",48.8566,2.3522,2161000,True,130,
     "The City of Light — Louvre, haute couture, Michelin temples, café terraces.",
     ["art-museums","fashion-weeks","michelin-restaurants","opera-classical","rooftop-bars"]),

    ("FR","Lyon",45.7640,4.8357,515000,False,100,
     "France's gastronomic capital — bouchon restaurants, Paul Bocuse legacy, Beaujolais wine.",
     ["michelin-restaurants","cooking-classes","food-tours-guided","wine-vineyards","farmers-markets"]),

    ("FR","Chamonix",45.9237,6.8694,8800,False,160,
     "Europe's alpinism capital — Mont Blanc, extreme skiing, ice climbing, paragliding.",
     ["alpine-climbing","skiing","paragliding","via-ferrata","photography-landscapes"]),

    ("FR","Marseille",43.2965,5.3698,861000,False,90,
     "France's raw port city — bouillabaisse, dramatic calanques, street art energy.",
     ["fish-markets","hidden-coves","street-art","snorkeling-diving","street-food"]),

    ("FR","Bordeaux",44.8378,-0.5792,257000,False,105,
     "World wine capital — neoclassical grandeur, château tours, wine tourism routes.",
     ["wine-vineyards","cycling-biking","michelin-restaurants","contemporary-architecture","guided-walking-tours"]),

    ("FR","Nice",43.7102,7.2620,342000,False,115,
     "French Riviera queen — Belle Époque promenade, Matisse museum, Italian cuisine.",
     ["art-museums","rooftop-bars","sandy-beaches","local-festivals","specialty-coffee"]),

    ("FR","Strasbourg",48.5734,7.7521,284000,False,95,
     "Alsatian fairy tale — Europe's finest Christmas market, half-timbered houses, Riesling.",
     ["christmas-markets","wine-vineyards","gothic-architecture","cycling-biking","local-festivals"]),

    ("FR","Biarritz",43.4832,-1.5586,25000,False,120,
     "France's surf capital — Belle Époque Atlantic elegance meets Basque surf culture.",
     ["surfing-kitesurfing","coastal-walks","rooftop-bars","local-festivals","sandy-beaches"]),

    ("FR","Annecy",45.8992,6.1294,126000,False,110,
     "Alpine lake perfection — Europe's cleanest lake, paragliding, medieval canals.",
     ["kayaking-canoeing","paragliding","cycling-biking","photography-landscapes","lake-swimming"]),

    ("FR","Avignon",43.9493,4.8055,92000,False,95,
     "City of Popes — Europe's greatest theater festival, monumental papal palace.",
     ["local-festivals","castles-palaces","wine-vineyards","guided-walking-tours","opera-classical"]),

    ("FR","Colmar",48.0793,7.3585,69000,False,95,
     "Alsace's storybook gem — half-timbered canals, Unterlinden museum, Gewürztraminer.",
     ["wine-vineyards","christmas-markets","guided-walking-tours","traditional-crafts","local-festivals"]),

    ("FR","Toulouse",43.6047,1.4442,479000,False,90,
     "La Ville Rose — aerospace innovation, Occitan culture, vibrant student life.",
     ["tech-hubs","factory-tours","craft-beer","local-festivals","cycling-biking"]),

    # ══ ITALY ═════════════════════════════════════════════════════════════════
    ("IT","Rome",41.9028,12.4964,2873000,True,120,
     "The Eternal City — Colosseum, Vatican, 2,800 years of layered civilization.",
     ["ancient-ruins","roman-history","religious-sites","art-museums","street-food"]),

    ("IT","Florence",43.7696,11.2558,382000,False,115,
     "Cradle of the Renaissance — Uffizi, Michelangelo's David, leather artisans.",
     ["art-museums","traditional-crafts","cooking-classes","wine-vineyards","guided-walking-tours"]),

    ("IT","Venice",45.4408,12.3155,255000,False,135,
     "The floating city — 118 islands, Carnival masks, Murano glass, gondola culture.",
     ["canal-river-cruises","local-festivals","traditional-crafts","photography-landscapes","art-museums"]),

    ("IT","Milan",45.4654,9.1859,1371000,False,130,
     "Italy's fashion and design capital — Fashion Week, Salone del Mobile, aperitivo.",
     ["fashion-weeks","design-weeks","opera-classical","michelin-restaurants","contemporary-art"]),

    ("IT","Naples",40.8518,14.2681,967000,False,80,
     "Birthplace of pizza — anarchic street energy, underground Greek ruins, Pompeii gateway.",
     ["street-food","ancient-ruins","guided-walking-tours","local-festivals","caving-spelunking"]),

    ("IT","Bologna",44.4949,11.3426,391000,False,95,
     "La Grassa — tortellini birthplace, oldest university, Italy's finest food markets.",
     ["cooking-classes","food-tours-guided","farmers-markets","craft-beer","street-food"]),

    ("IT","Amalfi Coast",40.6340,14.6027,5000,False,160,
     "UNESCO clifftop drama — lemon groves, limoncello, Positano, Tyrrhenian sailing.",
     ["sailing","hidden-coves","scenic-drives","photography-landscapes","michelin-restaurants"]),

    ("IT","Cinque Terre",44.1461,9.6439,4000,False,130,
     "Five car-free fishing villages on Ligurian cliffs — hiking, fresh pesto, wine terraces.",
     ["hiking","photography-landscapes","wine-vineyards","hidden-coves","coastal-walks"]),

    ("IT","Turin",45.0703,7.6869,870000,False,90,
     "Italy's chocolate capital — Egyptian museum, Baroque colonnades, Juventus stadium.",
     ["art-museums","street-food","cycling-biking","history-museums","local-festivals"]),

    ("IT","Sicily - Palermo",38.1157,13.3615,668000,False,75,
     "Arab-Norman architecture meets street food chaos — Ballarò market, Baroque oratories.",
     ["street-food","fish-markets","ancient-ruins","traditional-crafts","local-festivals"]),

    ("IT","Dolomites - Cortina",46.5404,12.1357,5500,False,180,
     "Pink rock spires at sunset — world-class via ferratas, luxury skiing, alpine luxury.",
     ["skiing","alpine-climbing","via-ferrata","photography-landscapes","luxury-spa"]),

    ("IT","Verona",45.4384,10.9916,258000,False,100,
     "Romeo and Juliet's city — Roman amphitheater opera, Soave and Valpolicella wine.",
     ["opera-classical","ancient-ruins","wine-vineyards","local-festivals","guided-walking-tours"]),

    ("IT","Sardinia - Cagliari",39.2238,9.1217,154000,False,95,
     "Ancient Sardinia — Nuraghe towers, pink flamingos, turquoise Costa Smeralda.",
     ["ancient-ruins","sandy-beaches","snorkeling-diving","wildlife-watching","local-festivals"]),

    # ══ SPAIN ═════════════════════════════════════════════════════════════════
    ("ES","Barcelona",41.3851,2.1734,1620000,False,110,
     "Gaudí's living city — Sagrada Família, Barceloneta beach, world-class techno.",
     ["modernist-architecture","beach-clubs","techno-clubs","street-food","art-museums"]),

    ("ES","Madrid",40.4168,-3.7038,3223000,True,105,
     "Spain's art triangle — Prado, Reina Sofía, Thyssen; world's liveliest tapas scene.",
     ["art-museums","michelin-restaurants","flamenco","rooftop-bars","local-festivals"]),

    ("ES","Seville",37.3891,-5.9845,688000,False,90,
     "Soul of Andalusia — Semana Santa passion, flamenco tablaos, Moorish Alcázar.",
     ["flamenco","local-festivals","ancient-ruins","traditional-crafts","guided-walking-tours"]),

    ("ES","San Sebastián",43.3183,-1.9812,187000,False,135,
     "Pintxos paradise — more Michelin stars per capita than almost anywhere, surf beach.",
     ["michelin-restaurants","surfing-kitesurfing","cooking-classes","wine-vineyards","street-food"]),

    ("ES","Ibiza",38.9067,1.4206,49000,False,170,
     "Global nightlife capital — Pacha, Amnesia, Ushuaïa, legendary sunset DJ sets.",
     ["techno-clubs","beach-clubs","rooftop-bars","sailing","hidden-coves"]),

    ("ES","Granada",37.1773,-3.5986,232000,False,80,
     "Alhambra palace — Europe's greatest Islamic art, free tapas, flamenco in cave bars.",
     ["ancient-ruins","flamenco","street-food","hiking","traditional-crafts"]),

    ("ES","Bilbao",43.2630,-2.9350,345000,False,100,
     "Guggenheim effect — Frank Gehry titanium museum transformed post-industrial city.",
     ["contemporary-architecture","art-museums","michelin-restaurants","street-food","guided-walking-tours"]),

    ("ES","Valencia",39.4699,-0.3763,794000,False,90,
     "Paella's birthplace — City of Arts and Sciences, Las Fallas fire festival.",
     ["contemporary-architecture","local-festivals","sandy-beaches","cycling-biking","street-food"]),

    ("ES","Mallorca - Palma",39.5696,2.6502,416000,False,115,
     "Balearic elegance — Gothic cathedral, Arab baths, cycling Serra de Tramuntana.",
     ["cycling-biking","sailing","hidden-coves","guided-walking-tours","michelin-restaurants"]),

    ("ES","Córdoba",37.8882,-4.7794,325000,False,80,
     "Mezquita marvel — forest of 856 columns, Moorish patios competition, orange trees.",
     ["ancient-ruins","religious-sites","local-festivals","traditional-crafts","guided-walking-tours"]),

    ("ES","Tenerife",28.2916,-16.6291,222000,False,100,
     "Volcanic Canary island — Teide caldera stargazing, whale watching, black sand beaches.",
     ["stargazing","whale-watching","hiking","sandy-beaches","local-festivals"]),

    # ══ GERMANY ═══════════════════════════════════════════════════════════════
    ("DE","Berlin",52.5200,13.4050,3669000,True,100,
     "Europe's techno capital — Berghain, East Side Gallery murals, Stasi museum.",
     ["techno-clubs","street-art","wwii-history","brutalist-architecture","craft-beer"]),

    ("DE","Munich",48.1351,11.5820,1471000,False,115,
     "Bavaria's heart — Oktoberfest, BMW Welt, English Garden surfing, Alps day trips.",
     ["craft-beer","local-festivals","cycling-biking","science-museums","skiing"]),

    ("DE","Hamburg",53.5753,10.0153,1841000,False,110,
     "Elbphilharmonie meets Reeperbahn — Europe's largest port, fish market at 5am.",
     ["jazz-live-music","fish-markets","canal-river-cruises","music-festivals","craft-beer"]),

    ("DE","Leipzig",51.3397,12.3731,587000,False,85,
     "Germany's most underground city — dark techno, Bach's home, affordable creative scene.",
     ["techno-clubs","jazz-live-music","street-art","art-museums","craft-beer"]),

    ("DE","Dresden",51.0504,13.7373,556000,False,85,
     "Florence of the Elbe — Baroque Zwinger palace, Semperoper opera, Meissen porcelain.",
     ["gothic-architecture","opera-classical","art-museums","traditional-crafts","guided-walking-tours"]),

    ("DE","Cologne",50.9333,6.9500,1083000,False,100,
     "Germany's most extravagant carnival — Gothic cathedral, Rhine craft beer culture.",
     ["gothic-architecture","local-festivals","craft-beer","art-museums","guided-walking-tours"]),

    ("DE","Nuremberg",49.4521,11.0767,518000,False,90,
     "Germany's Christmas market icon — medieval castle, WWII tribunal courthouse.",
     ["christmas-markets","castles-palaces","wwii-history","traditional-crafts","guided-walking-tours"]),

    ("DE","Baden-Baden",48.7636,8.2421,55000,False,160,
     "Europe's most refined spa town — Caracalla thermal baths, Belle Époque casino.",
     ["thermal-baths","luxury-spa","casinos","boutique-hotels","scenic-drives"]),

    ("DE","Frankfurt",50.1109,8.6821,753000,False,120,
     "Financial skyline meets apple wine culture — Städel art museum, Sachsenhausen.",
     ["art-museums","wine-bars","tech-hubs","local-festivals","guided-walking-tours"]),

    ("DE","Heidelberg",49.3988,8.6724,160000,False,95,
     "Germany's most romantic castle ruin — oldest university, Neckar River valley.",
     ["castles-palaces","cycling-biking","wine-vineyards","guided-walking-tours","local-festivals"]),

    # ══ UNITED KINGDOM ════════════════════════════════════════════════════════
    ("GB","London",51.5074,-0.1278,8982000,True,145,
     "Global megacity — British Museum, West End theater, Borough Market, Shoreditch.",
     ["art-museums","theater-musicals","street-food","street-art","music-festivals"]),

    ("GB","Edinburgh",55.9533,-3.1883,524000,False,120,
     "Scotland's dramatic capital — Arthur's Seat, Edinburgh Fringe, whisky distilleries.",
     ["local-festivals","whisky-tasting","castles-palaces","hiking","stand-up-comedy"]),

    ("GB","Manchester",53.4808,-2.2426,553000,False,100,
     "Birthplace of rave culture — Factory Records, Madchester, craft beer scene.",
     ["music-festivals","craft-beer","art-museums","pub-crawls","street-food"]),

    ("GB","Bristol",51.4545,-2.5879,470000,False,100,
     "Banksy's hometown — Clifton Suspension Bridge, independent music, street art.",
     ["street-art","craft-beer","local-festivals","cycling-biking","thrifting-vintage"]),

    ("GB","Bath",51.3811,-2.3590,94000,False,115,
     "Georgian perfection — Roman Baths, Thermae Spa, honey-stone Royal Crescent.",
     ["thermal-baths","roman-history","guided-walking-tours","boutique-hotels","art-museums"]),

    ("GB","Oxford",51.7520,-1.2577,152000,False,115,
     "City of Dreaming Spires — 800-year-old university, punting, Bodleian Library.",
     ["history-museums","gothic-architecture","cycling-biking","pub-crawls","guided-walking-tours"]),

    ("GB","Liverpool",53.4084,-2.9916,498000,False,95,
     "Beatles' city — Cavern Club, Tate Liverpool, Albert Dock, passionate football.",
     ["music-festivals","art-museums","pub-crawls","guided-walking-tours","local-festivals"]),

    ("GB","Scottish Highlands",57.1200,-4.7100,235000,False,110,
     "Europe's last great wilderness — Ben Nevis, Glencoe, whisky distilleries, red deer.",
     ["hiking","wildlife-watching","whisky-tasting","stargazing","photography-landscapes"]),

    ("GB","Cornwall",50.2660,-5.0527,568000,False,100,
     "England's wild southwest — Atlantic surf, clotted cream teas, tin mine coast.",
     ["surfing-kitesurfing","coastal-walks","sandy-beaches","fish-markets","photography-landscapes"]),

    # ══ PORTUGAL ══════════════════════════════════════════════════════════════
    ("PT","Lisbon",38.7169,-9.1399,548000,True,95,
     "Seven hills of azulejos — Fado in Alfama, vintage trams, ginjinha bars.",
     ["tram-rides","local-festivals","specialty-coffee","thrifting-vintage","rooftop-views"]),

    ("PT","Porto",41.1579,-8.6291,237000,False,85,
     "Port wine cellars — azulejo railway stations, Livraria Lello bookshop, francesinha.",
     ["wine-vineyards","craft-beer","rooftop-views","traditional-crafts","guided-walking-tours"]),

    ("PT","Algarve",37.0179,-7.9307,450000,False,90,
     "Golden limestone sea stacks — Ponta da Piedade grottos, Sagres surfing, Benagil cave.",
     ["hidden-coves","surfing-kitesurfing","sailing","fish-markets","photography-landscapes"]),

    ("PT","Sintra",38.7978,-9.3906,37000,False,100,
     "Fairy-tale palace hilltop — Pena Palace candy-colored turrets, Moorish castle walls.",
     ["castles-palaces","photography-landscapes","hiking","cycling-biking","botanic-gardens"]),

    ("PT","Douro Valley",41.1580,-7.7850,5000,False,100,
     "UNESCO wine landscape — terraced quintas, Rabelo boat trips, vintage harvest.",
     ["wine-vineyards","scenic-train-rides","cycling-biking","cooking-classes","photography-landscapes"]),

    ("PT","Madeira - Funchal",32.6669,-16.9241,111000,False,95,
     "Floating garden island — levada walks through laurisilva forest, Madeira wine lodges.",
     ["hiking","botanic-gardens","wine-vineyards","paragliding","photography-landscapes"]),

    # ══ NETHERLANDS ═══════════════════════════════════════════════════════════
    ("NL","Amsterdam",52.3676,4.9041,821000,True,120,
     "Canal ring UNESCO city — Rijksmuseum, Anne Frank House, cycling, coffee shop culture.",
     ["cycling-biking","art-museums","canal-river-cruises","specialty-coffee","local-festivals"]),

    ("NL","Rotterdam",51.9244,4.4777,651000,False,100,
     "Experimental architecture lab — Cube Houses, Markthal, world's largest port.",
     ["contemporary-architecture","street-food","canal-river-cruises","craft-beer","cycling-biking"]),

    ("NL","Utrecht",52.0907,5.1214,361000,False,110,
     "Unique wharf-level canal terraces — Dom Tower, vibrant student life, craft beer.",
     ["cycling-biking","craft-beer","canal-river-cruises","specialty-coffee","local-festivals"]),

    ("NL","Keukenhof Region",52.2706,4.5469,5000,False,90,
     "7 million tulips — world's greatest flower spectacle, Dutch windmills, bulb fields.",
     ["botanic-gardens","cycling-biking","photography-landscapes","local-festivals"]),

    # ══ GREECE ════════════════════════════════════════════════════════════════
    ("GR","Athens",37.9838,23.7275,3154000,True,90,
     "Acropolis above — ancient agora, Monastiraki flea market, rooftop Parthenon views.",
     ["ancient-ruins","roman-history","street-food","rooftop-views","street-art"]),

    ("GR","Santorini",36.3932,25.4615,15500,False,170,
     "Caldera drama — white-washed Oia, volcanic beaches, Assyrtiko wine sunsets.",
     ["photography-landscapes","wine-vineyards","sailing","boutique-hotels","rooftop-views"]),

    ("GR","Mykonos",37.4467,25.3289,10000,False,210,
     "Cosmopolitan party island — Little Venice, Paradise Beach clubs, LGBTQ+ haven.",
     ["beach-clubs","techno-clubs","sailing","hidden-coves","rooftop-bars"]),

    ("GR","Thessaloniki",40.6401,22.9444,1110000,False,70,
     "Greece's food capital — bougatsa, souvlaki; Byzantine walls, Rotunda, student life.",
     ["street-food","history-museums","local-festivals","craft-beer","guided-walking-tours"]),

    ("GR","Crete - Heraklion",35.3387,25.1442,140000,False,85,
     "Minoan civilization — Palace of Knossos, Cretan raki, gorge hiking, olive oil.",
     ["ancient-ruins","hiking","wine-vineyards","local-festivals","snorkeling-diving"]),

    ("GR","Rhodes",36.4349,28.2176,50000,False,100,
     "Knights' medieval walled city — Street of Knights, Lindos acropolis, turquoise coves.",
     ["ancient-ruins","guided-walking-tours","hidden-coves","snorkeling-diving","local-festivals"]),

    ("GR","Meteora",39.7217,21.6306,2000,False,70,
     "Monasteries on sky-piercing rock pillars — surreal geology, rock climbing.",
     ["orthodox-churches","rock-climbing","photography-landscapes","hiking","guided-walking-tours"]),

    # ══ AUSTRIA ═══════════════════════════════════════════════════════════════
    ("AT","Vienna",48.2082,16.3738,1897000,True,120,
     "Imperial grandeur — Kunsthistorisches Museum, Vienna Philharmonic, Naschmarkt.",
     ["art-museums","opera-classical","castles-palaces","craft-cocktail-bars","guided-walking-tours"]),

    ("AT","Salzburg",47.8095,13.0550,155000,False,120,
     "Mozart's Baroque birthplace — Mozarteum concerts, Salzburg Festival, Alpine fortress.",
     ["opera-classical","local-festivals","castles-palaces","hiking","guided-walking-tours"]),

    ("AT","Innsbruck",47.2692,11.4041,132000,False,115,
     "Alpine city — Olympic ski jumps, Golden Roof, Nordkette cable car to 2,334m.",
     ["skiing","alpine-climbing","via-ferrata","cycling-biking","guided-walking-tours"]),

    ("AT","Hallstatt",47.5622,13.6493,778,False,135,
     "World's most photographed village — Bronze Age salt mine, mirror lake reflection.",
     ["photography-landscapes","caving-spelunking","lake-swimming","hiking","boutique-hotels"]),

    ("AT","Graz",47.0707,15.4395,291000,False,95,
     "UNESCO old town meets futuristic Kunsthaus — Murinsel island, Styrian wine culture.",
     ["contemporary-architecture","art-museums","wine-vineyards","local-festivals","cycling-biking"]),

    # ══ SWITZERLAND ═══════════════════════════════════════════════════════════
    ("CH","Zermatt",46.0207,7.7491,5700,False,260,
     "Matterhorn village — car-free, year-round skiing, glacier hiking, elite Alpine dining.",
     ["skiing","alpine-climbing","photography-landscapes","boutique-hotels","luxury-spa"]),

    ("CH","Interlaken",46.6863,7.8632,5700,False,160,
     "Adventure capital — skydiving over Eiger, paragliding over Jungfrau, canyoning.",
     ["skydiving","paragliding","bungee-jumping","hot-air-balloon","kayaking-canoeing"]),

    ("CH","Zurich",47.3769,8.5417,434000,False,215,
     "Switzerland's cultural engine — Kunsthaus, Street Parade techno, luxury shopping.",
     ["art-museums","luxury-shopping","techno-clubs","specialty-coffee","cycling-biking"]),

    ("CH","Geneva",46.2044,6.1432,203000,False,225,
     "Humanitarian capital — CERN particle physics, Red Cross Museum, finest watchmaking.",
     ["science-centers","watches-shopping","luxury-shopping","sailing","michelin-restaurants"]),

    ("CH","Lucerne",47.0502,8.3093,81000,False,185,
     "Medieval wooden bridge over a crystal lake — Rigi mountain, paddle steamer cruises.",
     ["scenic-train-rides","lake-swimming","photography-landscapes","guided-walking-tours","cycling-biking"]),

    ("CH","Basel",47.5596,7.5886,178000,False,195,
     "Art Basel global fair — 40+ museums per capita, Rhine swimming, Gothic cathedral.",
     ["art-museums","contemporary-art","local-festivals","cycling-biking","guided-walking-tours"]),

    # ══ NORWAY ════════════════════════════════════════════════════════════════
    ("NO","Oslo",59.9139,10.7522,693000,True,185,
     "Viking Ship Museum, Munch's The Scream, Vigeland sculpture park, electric fjord boats.",
     ["art-museums","history-museums","cycling-biking","sailing","specialty-coffee"]),

    ("NO","Bergen",60.3913,5.3221,285000,False,175,
     "Fjords gateway — UNESCO Bryggen wharf, funicular to Fløyen, daily fish market.",
     ["fjords","fish-markets","hiking","photography-landscapes","scenic-train-rides"]),

    ("NO","Tromsø",69.6492,18.9560,77000,False,205,
     "Arctic capital — world's best Northern Lights, Sami reindeer, whale safari.",
     ["northern-lights","wildlife-watching","snowmobile","whale-watching","stargazing"]),

    ("NO","Lofoten Islands",68.1542,13.9979,24000,False,165,
     "Jagged peaks from Arctic Ocean — rorbuer cabins, world-class Arctic surfing.",
     ["photography-landscapes","surfing-kitesurfing","fishing","kayaking-canoeing","wildlife-watching"]),

    ("NO","Stavanger",58.9700,5.7331,144000,False,180,
     "Pulpit Rock hike — Preikestolen 604m cliff, Kjeragbolten boulder, wooden old town.",
     ["hiking","fjords","photography-landscapes","craft-beer","guided-walking-tours"]),

    # ══ SWEDEN ════════════════════════════════════════════════════════════════
    ("SE","Stockholm",59.3293,18.0686,975000,True,155,
     "Venice of the North — Vasa Museum, ABBA Museum, Gamla Stan, design heritage.",
     ["art-museums","design-weeks","cycling-biking","specialty-coffee","guided-walking-tours"]),

    ("SE","Gothenburg",57.7089,11.9746,590000,False,135,
     "Liseberg amusement park, fish auction, New Nordic restaurants, archipelago kayaking.",
     ["michelin-restaurants","kayaking-canoeing","craft-beer","local-festivals","street-food"]),

    ("SE","Swedish Lapland",67.8558,20.2253,98000,False,205,
     "Icehotel, Sami reindeer sledding, Aurora Borealis, Abisko dark sky sanctuary.",
     ["northern-lights","snowmobile","stargazing","community-experiences","wildlife-watching"]),

    ("SE","Visby",57.6348,18.2948,24000,False,120,
     "Best-preserved medieval Hanseatic city — UNESCO rose city, medieval week festival.",
     ["castles-palaces","local-festivals","guided-walking-tours","sandy-beaches","cycling-biking"]),

    # ══ DENMARK ═══════════════════════════════════════════════════════════════
    ("DK","Copenhagen",55.6761,12.5683,794000,True,168,
     "Noma's New Nordic revolution — Tivoli Gardens, cycling on 390km of bike lanes.",
     ["michelin-restaurants","cycling-biking","design-weeks","specialty-coffee","canal-river-cruises"]),

    ("DK","Aarhus",56.1629,10.2039,349000,False,145,
     "ARoS rainbow panorama, street food market, Viking Museum Moesgård.",
     ["art-museums","street-food","craft-beer","local-festivals","cycling-biking"]),

    ("DK","Bornholm",55.1000,14.9000,40000,False,120,
     "Denmark's sunshine island — smoked herring, round medieval churches, cycling.",
     ["cycling-biking","sandy-beaches","traditional-crafts","fishing","photography-landscapes"]),

    # ══ FINLAND ═══════════════════════════════════════════════════════════════
    ("FI","Helsinki",60.1699,24.9384,658000,True,158,
     "Design District, Temppeliaukio rock church, sauna culture, Market Square.",
     ["design-weeks","thermal-baths","art-museums","specialty-coffee","local-festivals"]),

    ("FI","Rovaniemi",66.5039,25.7294,62000,False,185,
     "Santa Claus hometown — Arctic Circle, reindeer safaris, glass igloos, Northern Lights.",
     ["northern-lights","snowmobile","wildlife-watching","stargazing","digital-detox"]),

    ("FI","Tampere",61.4978,23.7610,238000,False,135,
     "World sauna capital — Moomin Museum, Finnish vappu celebration, Tampere Hall concerts.",
     ["thermal-baths","local-festivals","art-museums","craft-beer","guided-walking-tours"]),

    # ══ POLAND ════════════════════════════════════════════════════════════════
    ("PL","Warsaw",52.2297,21.0122,1793000,True,65,
     "Rebuilt from zero after WWII — POLIN Jewish museum, booming techno scene, milk bars.",
     ["wwii-history","techno-clubs","history-museums","street-food","cycling-biking"]),

    ("PL","Kraków",50.0647,19.9450,779000,False,55,
     "Royal capital — Wawel Castle, Kazimierz Jewish quarter, Auschwitz pilgrimage nearby.",
     ["castles-palaces","wwii-history","jazz-live-music","craft-beer","guided-walking-tours"]),

    ("PL","Gdańsk",54.3520,18.6466,470000,False,60,
     "Solidarity birthplace — amber workshops, Hanseatic Gothic, Baltic beach dunes.",
     ["history-museums","traditional-crafts","sandy-beaches","guided-walking-tours","local-festivals"]),

    ("PL","Zakopane",49.2992,19.9496,27000,False,60,
     "Tatra gateway — Giewont peak, Morskie Oko lake trek, Góral folk culture.",
     ["hiking","skiing","folk-traditions","national-parks","photography-landscapes"]),

    ("PL","Białowieża Forest",52.7062,23.8692,2600,False,50,
     "Europe's last primeval forest — European bison herds, UNESCO biosphere.",
     ["national-parks","wildlife-watching","birdwatching","forest-bathing","photography-landscapes"]),

    # ══ CZECH REPUBLIC ════════════════════════════════════════════════════════
    ("CZ","Prague",50.0755,14.4378,1309000,True,70,
     "Gothic castle above medieval city — Kafka's ghost, Staropramen pilsner, absinthe bars.",
     ["castles-palaces","craft-beer","gothic-architecture","jazz-live-music","guided-walking-tours"]),

    ("CZ","Český Krumlov",48.8127,14.3175,13500,False,65,
     "UNESCO horseshoe bend — Renaissance castle, Baroque theater still in use.",
     ["castles-palaces","kayaking-canoeing","photography-landscapes","local-festivals","guided-walking-tours"]),

    ("CZ","Karlovy Vary",50.2332,12.8716,47000,False,80,
     "Grand Bohemian spa — 13 hot spring colonnades, Becherovka distillery, film festival.",
     ["thermal-baths","local-festivals","distilleries","guided-walking-tours","boutique-hotels"]),

    ("CZ","Brno",49.1951,16.6068,382000,False,55,
     "Moravia's cosmopolitan capital — Functionalist Vila Tugendhat, Moravian wine culture.",
     ["modernist-architecture","wine-vineyards","craft-beer","local-festivals","caving-spelunking"]),

    # ══ HUNGARY ═══════════════════════════════════════════════════════════════
    ("HU","Budapest",47.4979,19.0402,1756000,True,65,
     "Thermal bath capital — Széchenyi baths, ruin bars, Dohány Street Synagogue.",
     ["thermal-baths","ruin-bars","gothic-architecture","opera-classical","guided-walking-tours"]),

    ("HU","Pécs",46.0727,18.2330,144000,False,40,
     "4,000 years — Roman necropolis, Ottoman Mosque, Zsolnay ceramics culture.",
     ["ancient-ruins","art-museums","traditional-crafts","local-festivals","guided-walking-tours"]),

    ("HU","Lake Balaton",46.8500,17.7000,120000,False,55,
     "Central Europe's sea — lavender farms, Badacsony volcano wine, summer sailing.",
     ["lake-swimming","wine-vineyards","sailing","cycling-biking","local-festivals"]),

    # ══ ROMANIA ═══════════════════════════════════════════════════════════════
    ("RO","Bucharest",44.4268,26.1025,1716000,True,50,
     "Little Paris — Ceaușescu's Palace of Parliament, Art Nouveau villas, underground techno.",
     ["techno-clubs","art-museums","guided-walking-tours","street-food","thrifting-vintage"]),

    ("RO","Cluj-Napoca",46.7712,23.6236,324000,False,45,
     "UNTOLD festival — Romania's biggest electronic music festival, vibrant student city.",
     ["music-festivals","craft-beer","local-festivals","street-food","art-museums"]),

    ("RO","Sibiu",45.7983,24.1256,147000,False,40,
     "Medieval Saxon citadel — watchtowers, Brukenthal Palace, sub-Carpathian hiking.",
     ["guided-walking-tours","traditional-crafts","christmas-markets","art-museums","folk-traditions"]),

    ("RO","Brașov",45.6579,25.6012,253000,False,45,
     "Bran Castle — Dracula tourism, Poiana Brasov ski, medieval Black Church, bear watching.",
     ["castles-palaces","skiing","wildlife-watching","hiking","guided-walking-tours"]),

    ("RO","Danube Delta",45.1500,29.6500,15000,False,55,
     "Europe's wildest wetland — 300 bird species, pelican colonies, floating reed islands.",
     ["birdwatching","wildlife-watching","kayaking-canoeing","fishing","photography-landscapes"]),

    ("RO","Sighișoara",46.2197,24.7916,28000,False,40,
     "Europe's only inhabited medieval citadel — Vlad the Impaler's birthplace, clock tower.",
     ["castles-palaces","guided-walking-tours","local-festivals","photography-landscapes","traditional-crafts"]),

    # ══ CROATIA ═══════════════════════════════════════════════════════════════
    ("HR","Dubrovnik",42.6507,18.0944,41000,False,145,
     "Game of Thrones' King's Landing — medieval city walls walk, island boat trips.",
     ["guided-walking-tours","sailing","photography-landscapes","hidden-coves","local-festivals"]),

    ("HR","Split",43.5081,16.4402,178000,False,100,
     "Living inside a Roman palace — Diocletian's walls contain a whole neighborhood.",
     ["ancient-ruins","sandy-beaches","sailing","local-festivals","street-food"]),

    ("HR","Hvar",43.1726,16.4412,11000,False,155,
     "Croatia's jet-set island — Carpe Diem beach club, lavender fields, rosé wine.",
     ["beach-clubs","sailing","wine-vineyards","hidden-coves","local-festivals"]),

    ("HR","Plitvice Lakes",44.8804,15.6168,3000,False,90,
     "16 terraced turquoise lakes — UNESCO forest, Instagrammable waterfalls.",
     ["national-parks","photography-landscapes","hiking","wildlife-watching","cycling-biking"]),

    ("HR","Rovinj",45.0811,13.6387,14000,False,115,
     "Venetian fishing village on peninsula — painters' studios, truffle hunting in Motovun.",
     ["photography-landscapes","cycling-biking","local-festivals","sailing","guided-walking-tours"]),

    # ══ SLOVENIA ══════════════════════════════════════════════════════════════
    ("SI","Ljubljana",46.0569,14.5058,284000,True,90,
     "Car-free old town on a castle hill — dragon bridges, riverside cafés, Saturday market.",
     ["cycling-biking","local-festivals","craft-beer","farmers-markets","guided-walking-tours"]),

    ("SI","Lake Bled",46.3683,14.1139,8000,False,115,
     "Church island on glacial lake — sunrise rowing, cliff castle, kremšnita cream cake.",
     ["photography-landscapes","kayaking-canoeing","hiking","cycling-biking","boutique-hotels"]),

    ("SI","Triglav National Park",46.3799,13.8435,2000,False,95,
     "Soča River emerald canyoning — Julian Alps, mountain huts, Bohinj lake ice swimming.",
     ["hiking","alpine-climbing","kayaking-canoeing","via-ferrata","photography-landscapes"]),

    # ══ ICELAND ═══════════════════════════════════════════════════════════════
    ("IS","Reykjavik",64.1355,-21.8954,128000,True,225,
     "World's northernmost capital — geothermal Blue Lagoon, whale watching, skyr culture.",
     ["hot-springs-outdoor","whale-watching","local-festivals","specialty-coffee","guided-walking-tours"]),

    ("IS","Golden Circle",64.3271,-20.1199,1000,False,200,
     "Geysir erupting every 5 min — Þingvellir tectonic plates, Gullfoss double waterfall.",
     ["national-parks","hot-springs-outdoor","snowmobile","photography-landscapes","stargazing"]),

    ("IS","South Coast",63.5264,-19.0292,1500,False,200,
     "Reynisfjara black sand beach, Skógafoss waterfall, Vatnajökull glacier hikes.",
     ["glaciers","photography-landscapes","hiking","wildlife-watching","camping"]),

    ("IS","Westfjords",65.9000,-22.7000,7100,False,185,
     "Iceland's most remote — Látrabjarg bird cliff, hot pots, true off-grid wilderness.",
     ["birdwatching","hiking","hot-springs-outdoor","digital-detox","photography-landscapes"]),

    # ══ IRELAND ═══════════════════════════════════════════════════════════════
    ("IE","Dublin",53.3498,-6.2603,1173000,True,135,
     "Guinness Storehouse, Trinity College Book of Kells, Temple Bar trad sessions.",
     ["pub-crawls","craft-beer","history-museums","local-festivals","guided-walking-tours"]),

    ("IE","Galway",53.2707,-9.0568,80000,False,115,
     "Ireland's cultural soul — trad music from every pub, Oyster Festival, Salthill.",
     ["folk-traditions","pub-crawls","local-festivals","coastal-walks","craft-beer"]),

    ("IE","Cliffs of Moher",52.9715,-9.4309,500,False,90,
     "700-foot Atlantic cliffs — puffin colonies, Doolin Cave, Aran Islands ferry.",
     ["coastal-walks","wildlife-watching","photography-landscapes","birdwatching","scenic-drives"]),

    ("IE","Killarney",52.0599,-9.5044,14000,False,100,
     "Ring of Kerry drive, Muckross Abbey, jaunting cars, red deer national park.",
     ["national-parks","cycling-biking","scenic-drives","wildlife-watching","hiking"]),

    # ══ BELGIUM ═══════════════════════════════════════════════════════════════
    ("BE","Brussels",50.8503,4.3517,1208000,True,115,
     "Grand Place Art Nouveau — Manneken Pis, Magritte Museum, EU bubble.",
     ["art-museums","chocolate-culture","craft-beer","guided-walking-tours","local-festivals"]),

    ("BE","Bruges",51.2093,3.2247,117000,False,115,
     "Venice of the North — Groeningemuseum Flemish Primitives, Jan van Eyck legacy.",
     ["canal-river-cruises","chocolate-culture","gothic-architecture","art-museums","guided-walking-tours"]),

    ("BE","Ghent",51.0543,3.7174,262000,False,100,
     "Thursday market, Ghent Altarpiece — vibrant vegetarian food, medieval core.",
     ["art-museums","craft-beer","local-festivals","street-food","guided-walking-tours"]),

    ("BE","Antwerp",51.2194,4.4025,529000,False,115,
     "Diamond quarter — Royal Museum of Fine Arts, Rubenshuis, MOMU fashion museum.",
     ["art-museums","fashion-weeks","michelin-restaurants","design-weeks","guided-walking-tours"]),

    # ══ BULGARIA ══════════════════════════════════════════════════════════════
    ("BG","Sofia",42.6977,23.3219,1307000,True,45,
     "Alexander Nevsky Cathedral, Soviet relics, booming craft beer, Vitosha skiing.",
     ["orthodox-churches","craft-beer","skiing","guided-walking-tours","street-food"]),

    ("BG","Plovdiv",42.1354,24.7453,346000,False,40,
     "Europe's oldest inhabited city — Thracian tomb, Roman stadium in shopping mall.",
     ["ancient-ruins","local-festivals","traditional-crafts","guided-walking-tours","art-museums"]),

    ("BG","Bansko",41.8370,23.4884,8800,False,55,
     "Balkans' best value ski resort — Pirin National Park, mehana folk restaurants.",
     ["skiing","hiking","national-parks","folk-traditions","thermal-baths"]),

    ("BG","Varna",43.2141,27.9147,335000,False,50,
     "Black Sea golden beaches — world's oldest gold treasure, beach clubs.",
     ["sandy-beaches","ancient-ruins","beach-clubs","local-festivals","guided-walking-tours"]),

    # ══ SERBIA ════════════════════════════════════════════════════════════════
    ("RS","Belgrade",44.8176,20.4569,1694000,True,45,
     "Europe's party capital — Kalemegdan fortress, floating splavovi clubs, rakia.",
     ["techno-clubs","beach-clubs","craft-beer","jazz-live-music","guided-walking-tours"]),

    ("RS","Novi Sad",45.2671,19.8335,289000,False,40,
     "EXIT Festival — Petrovaradin fortress transforms into Europe's greatest festival.",
     ["music-festivals","castles-palaces","craft-beer","local-festivals","guided-walking-tours"]),

    # ══ ALBANIA ═══════════════════════════════════════════════════════════════
    ("AL","Tirana",41.3275,19.8187,800000,True,35,
     "Enver Hoxha's bunkers transformed — colorful apartments, Blloku café district.",
     ["street-art","specialty-coffee","local-festivals","guided-walking-tours","craft-beer"]),

    ("AL","Albanian Riviera",40.0700,19.9600,20000,False,40,
     "Europe's last unspoiled coast — Ksamil's three islands, Ionian turquoise clarity.",
     ["hidden-coves","snorkeling-diving","hiking","photography-landscapes","digital-detox"]),

    ("AL","Berat",40.7058,19.9522,33000,False,30,
     "City of a Thousand Windows — UNESCO Ottoman houses, Byzantine castle, Onufri icons.",
     ["guided-walking-tours","orthodox-churches","photography-landscapes","traditional-crafts","art-museums"]),

    ("AL","Gjirokastër",40.0758,20.1389,20000,False,30,
     "Ismail Kadare's stone city — Ottoman mansions, Ali Pasha fortress, Folk Festival.",
     ["castles-palaces","local-festivals","history-museums","traditional-crafts","photography-landscapes"]),

    # ══ MONTENEGRO ════════════════════════════════════════════════════════════
    ("ME","Kotor",42.4247,18.7712,13000,False,85,
     "Venetian walled city — 1,500 stair climb to fortress, cat sanctuary, fjord sailing.",
     ["guided-walking-tours","sailing","photography-landscapes","hiking","local-festivals"]),

    ("ME","Budva",42.2864,18.8400,19000,False,90,
     "Montenegro's Adriatic party strip — medieval old town, summer beach clubs.",
     ["sandy-beaches","beach-clubs","local-festivals","sailing","guided-walking-tours"]),

    ("ME","Durmitor National Park",43.1500,19.0167,1500,False,60,
     "Black Lake, Tara Canyon Europe's deepest, white-water rafting, black pine skiing.",
     ["national-parks","white-water-rafting","skiing","hiking","photography-landscapes"]),

    # ══ NORTH MACEDONIA ═══════════════════════════════════════════════════════
    ("MK","Skopje",41.9981,21.4254,544000,True,35,
     "Alexander the Great obsession — colossal statue, Old Bazaar Ottoman market.",
     ["guided-walking-tours","ancient-ruins","traditional-crafts","hiking","local-festivals"]),

    ("MK","Ohrid",41.1231,20.8016,42000,False,40,
     "UNESCO lake of 365 churches — Samuel's Fortress, ancient theater, monastery springs.",
     ["orthodox-churches","lake-swimming","guided-walking-tours","photography-landscapes","local-festivals"]),

    # ══ BOSNIA ════════════════════════════════════════════════════════════════
    ("BA","Sarajevo",43.8563,18.4131,275000,True,40,
     "Jerusalem of Europe — Baščaršija bazaar, 1984 Olympics legacy, siege tunnel museum.",
     ["wwii-history","guided-walking-tours","traditional-crafts","street-food","history-museums"]),

    ("BA","Mostar",43.3438,17.8078,105000,False,45,
     "Stari Most bridge — cliff jumping, copper craftsmen's street, Sufi dervish tekke.",
     ["photography-landscapes","traditional-crafts","guided-walking-tours","white-water-rafting","local-festivals"]),

    # ══ SLOVAKIA ══════════════════════════════════════════════════════════════
    ("SK","Bratislava",48.1486,17.1077,475000,True,65,
     "Compact Danube capital — UFO bridge, wine bar culture, between Vienna and Budapest.",
     ["wine-bars","craft-beer","castles-palaces","cycling-biking","guided-walking-tours"]),

    ("SK","High Tatras",49.1789,20.1300,5000,False,70,
     "Carpathians' highest peaks — Lomnický štít cable car, Belianska cave system.",
     ["skiing","hiking","alpine-climbing","caving-spelunking","photography-landscapes"]),

    # ══ LATVIA ════════════════════════════════════════════════════════════════
    ("LV","Riga",56.9496,24.1052,614000,True,70,
     "Art Nouveau capital — more Jugendstil buildings than anywhere, Central Market in zeppelin hangars.",
     ["modernist-architecture","art-museums","craft-beer","local-festivals","guided-walking-tours"]),

    ("LV","Sigulda",57.1535,24.8530,11000,False,60,
     "Latvia's Switzerland — Olympic bobsled rides, Turaida Castle, Gauja River canoeing.",
     ["castles-palaces","kayaking-canoeing","hiking","national-parks","cycling-biking"]),

    # ══ LITHUANIA ═════════════════════════════════════════════════════════════
    ("LT","Vilnius",54.6872,25.2797,574000,True,65,
     "Baroque UNESCO old town — self-proclaimed Užupis republic, KGB museum.",
     ["gothic-architecture","street-art","guided-walking-tours","craft-beer","history-museums"]),

    ("LT","Trakai",54.6379,24.9342,5000,False,50,
     "Island castle on two lakes — Grand Duchy capital, Karaite community, kayaking.",
     ["castles-palaces","kayaking-canoeing","photography-landscapes","cycling-biking","guided-walking-tours"]),

    ("LT","Curonian Spit",55.3500,21.0500,3000,False,60,
     "UNESCO sand dunes — 70-metre dunes migrating, amber beaches, elk in pine forests.",
     ["photography-landscapes","cycling-biking","sandy-beaches","wildlife-watching","birdwatching"]),

    # ══ ESTONIA ═══════════════════════════════════════════════════════════════
    ("EE","Tallinn",59.4370,24.7536,437000,True,78,
     "Medieval Hanseatic meets e-Estonia — Toompea Castle, Telliskivi Creative City.",
     ["castles-palaces","tech-hubs","craft-beer","guided-walking-tours","local-festivals"]),

    ("EE","Pärnu",58.3859,24.4981,39000,False,70,
     "Estonia's summer capital — Art Nouveau villas, mud spa treatments, Baltic beach.",
     ["sandy-beaches","thermal-baths","cycling-biking","local-festivals","boutique-hotels"]),

    # ══ MALTA ═════════════════════════════════════════════════════════════════
    ("MT","Valletta",35.8997,14.5148,6444,True,95,
     "Europe's smallest capital — Caravaggio paintings in St John's Co-Cathedral.",
     ["ancient-ruins","art-museums","guided-walking-tours","history-museums","local-festivals"]),

    ("MT","Gozo",36.0449,14.2438,37000,False,90,
     "Sister island of silence — Azure Window, diving Blue Hole, Ggantija temples.",
     ["snorkeling-diving","ancient-ruins","hidden-coves","hiking","digital-detox"]),

    # ══ CYPRUS ════════════════════════════════════════════════════════════════
    ("CY","Paphos",34.7757,32.4242,36000,False,90,
     "Aphrodite's birthplace — Tomb of the Kings, Roman mosaic floors, Akamas hiking.",
     ["ancient-ruins","roman-history","hiking","snorkeling-diving","guided-walking-tours"]),

    ("CY","Limassol",34.6786,33.0413,235000,False,95,
     "Carnival capital — Commandaria wine route, Kourion amphitheater, marina nightlife.",
     ["local-festivals","wine-vineyards","ancient-ruins","beach-clubs","guided-walking-tours"]),

    ("CY","Troodos Mountains",34.9167,32.8833,1000,False,75,
     "Painted Byzantine UNESCO churches — cedar valley, Caledonian waterfalls, mountain wine.",
     ["orthodox-churches","hiking","wine-vineyards","photography-landscapes","scenic-drives"]),

    # ══ LUXEMBOURG ════════════════════════════════════════════════════════════
    ("LU","Luxembourg City",49.6117,6.1319,128000,True,155,
     "Grand Duchy UNESCO fortress gorge — Bock casemates tunnels, MUDAM contemporary art.",
     ["castles-palaces","art-museums","wine-vineyards","cycling-biking","michelin-restaurants"]),

    # ══ MOLDOVA ═══════════════════════════════════════════════════════════════
    ("MD","Chișinău",47.0105,28.8638,532000,True,25,
     "Europe's most underrated capital — Soviet mosaics, underground wine bars, NationalWine Day.",
     ["wine-vineyards","guided-walking-tours","local-festivals","traditional-crafts","cycling-biking"]),

    ("MD","Cricova",47.1387,28.8621,10000,False,30,
     "World's second-largest wine cellar — 120km underground tunnels, vintage collection.",
     ["wine-vineyards","guided-walking-tours","caving-spelunking","distilleries"]),

    # ══ KOSOVO ════════════════════════════════════════════════════════════════
    ("XK","Pristina",42.6629,21.1655,211000,True,30,
     "Balkans' youngest capital — Bill Clinton Boulevard, Newborn monument, café culture.",
     ["street-art","specialty-coffee","local-festivals","guided-walking-tours","community-experiences"]),

    ("XK","Prizren",42.2139,20.7397,85000,False,30,
     "Kosovo's most beautiful city — Sinan Pasha Mosque, Byzantine citadel, DocuFest.",
     ["orthodox-churches","local-festivals","traditional-crafts","photography-landscapes","guided-walking-tours"]),

    # ══ UKRAINE ═══════════════════════════════════════════════════════════════
    ("UA","Lviv",49.8397,24.0297,721000,False,30,
     "Coffee capital of Ukraine — Austro-Hungarian architecture, 1,000+ coffee shops, Opera.",
     ["specialty-coffee","opera-classical","guided-walking-tours","local-festivals","traditional-crafts"]),

    ("UA","Chernivtsi",48.2921,25.9358,265000,False,25,
     "The Little Vienna of Ukraine — Yuriy Fedkovych University (UNESCO), Habsburg legacy.",
     ["guided-walking-tours","photography-landscapes","folk-traditions","local-festivals","traditional-crafts"]),
]


def fetch_unsplash_image(query, access_key):
    if not access_key:
        return None, None
    try:
        r = requests.get(
            "https://api.unsplash.com/search/photos",
            params={"query": query, "per_page": 1, "orientation": "landscape"},
            headers={"Authorization": f"Client-ID {access_key}"},
            timeout=10,
        )
        if r.status_code == 200:
            results = r.json().get("results", [])
            if results:
                return results[0]["urls"]["regular"], results[0]["user"]["name"]
    except Exception as e:
        print(f"    [WARN] Unsplash: {e}")
    return None, None


def main():
    db = SessionLocal()
    access_key = settings.UNSPLASH_ACCESS_KEY or ""
    if not access_key:
        print("[INFO] UNSPLASH_ACCESS_KEY lipsă — imaginile vor fi NULL")

    countries = {c.iso2: c for c in db.query(Country).all()}
    print(f"Inserare {len(CITIES)} orașe...\n")
    inserted = skipped = warn_tags = 0

    for (iso2, name, lat, lon, pop, is_cap, cost, desc, tag_slugs) in CITIES:
        country = countries.get(iso2)
        if not country:
            print(f"  [WARN] Țara '{iso2}' lipsă — sărit {name}")
            continue

        existing = db.query(City).filter(
            City.name == name, City.country_id == country.id
        ).first()
        if existing:
            skipped += 1
            continue

        image_url, image_credit = None, None
        if access_key:
            image_url, image_credit = fetch_unsplash_image(f"{name} {country.name}", access_key)
            time.sleep(0.3)

        city = City(
            name=name, country_id=country.id,
            latitude=lat, longitude=lon,
            population=pop, is_capital=is_cap,
            avg_cost_per_day=cost, description=desc,
            image_url=image_url, image_credit=image_credit,
        )
        db.add(city)
        db.flush()

        tags_added = 0
        for slug in tag_slugs:
            tag = db.query(Tag).filter(Tag.slug == slug).first()
            if tag:
                db.execute(city_tags.insert().values(city_id=city.id, tag_id=tag.id, score=1.0))
                tags_added += 1
            else:
                print(f"    [WARN] Tag '{slug}' — {name}")
                warn_tags += 1

        db.commit()
        print(f"  [+] {name} ({iso2}) — {tags_added} taguri")
        inserted += 1

    print(f"\n{'═'*50}")
    print(f"  Orașe inserate:  {inserted}")
    print(f"  Sărite:          {skipped}")
    print(f"  Tag warnings:    {warn_tags}")
    print(f"  TOTAL în DB:     {db.query(City).count()}")
    print(f"{'═'*50}")
    db.close()


if __name__ == "__main__":
    main()