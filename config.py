import os
from pathlib import Path

# Токены API
TELEGRAM_BOT_TOKEN = '7685757919:AAHV6adfKlZ2HvrJbEQoGC0ySPU_imor3I4'
AVIASALES_API_TOKEN = '7a6233b5ebbb583624f1e9df6db828eb'
<<<<<<< HEAD
=======
AVIATIONSTACK_API_KEY = '4b3d76593292cc886fd08c39af48eb72'
>>>>>>> master

# API Endpoints
AVIASALES_CHEAP_URL = 'https://api.travelpayouts.com/v1/prices/cheap'
AVIASALES_CALENDAR_URL = 'https://api.travelpayouts.com/v1/prices/calendar'
CITY_SEARCH_URL = 'https://api.travelpayouts.com/data/ru/cities.json'
AIRLINES_URL = 'https://api.travelpayouts.com/data/ru/airlines.json'
AIRCRAFT_URL = 'https://api.travelpayouts.com/data/ru/planes.json'
AVIASALES_STATS_URL = 'https://api.travelpayouts.com/v1/prices/monthly'
AVIASALES_POPULAR_ROUTES_URL = 'https://api.travelpayouts.com/v1/city-directions'
AVIASALES_AIRLINE_ROUTES_URL = 'https://api.travelpayouts.com/v1/airline-directions'
<<<<<<< HEAD
=======
AVIATIONSTACK_FLIGHT_URL = 'https://api.aviationstack.com/v1/flights'
>>>>>>> master
POPULAR_AIRLINES = ['SU', 'S7', 'U6', 'DP', 'UT', 'FV', 'WZ', '6R', 'N4', '5N']

# Настройки избранного
FAVORITES_FILE = str((Path(__file__).parent / 'data' / 'favorites.json').absolute())
os.makedirs(Path(__file__).parent / 'data', exist_ok=True)