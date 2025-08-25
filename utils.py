import logging
import requests
from datetime import datetime
import pytz
from config import CITY_SEARCH_URL, AIRLINES_URL, AIRCRAFT_URL

logger = logging.getLogger(__name__)

# Кэши данных
city_cache = {}
airline_cache = {}
aircraft_cache = {}

async def load_city_codes():
    """Загружаем коды городов"""
    global city_cache
    try:
        response = requests.get(CITY_SEARCH_URL, timeout=10)
        cities = response.json()
        city_cache = {city['code']: city for city in cities if 'code' in city}
        logger.info(f"Загружено {len(city_cache)} кодов городов")
    except Exception as e:
        logger.error(f"Ошибка загрузки кодов городов: {e}")

async def load_airline_codes():
    """Загружаем коды авиакомпаний"""
    global airline_cache
    try:
        response = requests.get(AIRLINES_URL, timeout=10)
        airlines = response.json()
        airline_cache = {a['code']: a for a in airlines if 'code' in a}
        logger.info(f"Загружено {len(airline_cache)} авиакомпаний")
    except Exception as e:
        logger.error(f"Ошибка загрузки авиакомпаний: {e}")

async def load_aircraft_data():
    """Загружаем данные о самолетах"""
    global aircraft_cache
    try:
        response = requests.get(AIRCRAFT_URL, timeout=10)
        aircrafts = response.json()
        aircraft_cache = {a['code']: a for a in aircrafts if 'code' in a}
        logger.info(f"Загружено {len(aircraft_cache)} типов самолетов")
    except Exception as e:
        logger.error(f"Ошибка загрузки данных о самолетах: {e}")

async def get_city_code(city_name: str) -> str:
    """Получаем IATA-код города"""
    city_name = city_name.lower().strip()
    if not city_cache:
        await load_city_codes()
    
    for code, city_data in city_cache.items():
        if city_data.get('name', '').lower() == city_name:
            return code
    
    for code, city_data in city_cache.items():
        if city_name in city_data.get('name', '').lower():
            return code
    return None

async def get_city_name(city_code: str) -> str:
    """Получаем название города по коду"""
    if not city_cache:
        await load_city_codes()
    city = city_cache.get(city_code.upper(), {})
    return city.get('name', city_code)

async def get_airline_name(airline_code: str) -> str:
    """Получаем название авиакомпании по коду"""
    if not airline_cache:
        await load_airline_codes()
    airline = airline_cache.get(airline_code.upper(), {})
    return airline.get('name', airline_code)

async def get_aircraft_name(aircraft_code: str) -> str:
    """Получаем название самолета по коду"""
    if not aircraft_cache:
        await load_aircraft_data()
    aircraft = aircraft_cache.get(aircraft_code.upper(), {})
    return aircraft.get('name', aircraft_code)

<<<<<<< HEAD
=======
def format_aviationstack_date(date_str: str) -> str:
    """Форматируем дату из AviationStack в дд.мм.гггг чч:мм"""
    try:
        dt = datetime.strptime(date_str, "%Y-%m-%dT%H:%M:%S%z")
        local_tz = pytz.timezone('Europe/Moscow')
        local_dt = dt.astimezone(local_tz)
        return local_dt.strftime("%d.%m.%Y %H:%M")
    except:
        return date_str

>>>>>>> master
def format_date(date_str: str) -> str:
    """Форматируем дату в дд.мм.гггг чч:мм"""
    try:
        dt = datetime.strptime(date_str, "%Y-%m-%dT%H:%M:%S%z")
        local_tz = pytz.timezone('Europe/Moscow')
        local_dt = dt.astimezone(local_tz)
        return local_dt.strftime("%d.%m.%Y %H:%M")
    except:
        return date_str