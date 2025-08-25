import logging
import requests
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from config import AVIATIONSTACK_API_KEY, AVIATIONSTACK_FLIGHT_URL
from utils import format_date
import json
from datetime import datetime

logger = logging.getLogger(__name__)

def translate_status(status):
    """Переводит статус рейса на русский"""
    status_translations = {
        'scheduled': '🔄 Запланирован',
        'active': '🛫 В полете',
        'landed': '🛬 Приземлился',
        'cancelled': '❌ Отменен',
        'incident': '⚠️ Происшествие',
        'diverted': '🔄 Перенаправлен',
        'unknown': '❓ Неизвестен'
    }
    return status_translations.get(status, f'❓ {status}')

def safe_get(data, key, default=None):
    """Безопасное получение значения из словаря"""
    if not data or not isinstance(data, dict):
        return default
    value = data.get(key, default)
    return value if value not in [None, 'null', 'None', ''] else default

def format_flight_date(date_str):
    """Форматирует дату в дд.мм.гггг"""
    try:
        dt = datetime.strptime(date_str, "%Y-%m-%d")
        return dt.strftime("%d.%m.%Y")
    except:
        return date_str

async def show_flight_info_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показывает меню для получения информации о рейсе"""
    if update.callback_query:
        query = update.callback_query
        await query.answer()
        message = query.message
    else:
        message = update.message
    
    keyboard = [
        [InlineKeyboardButton("← Назад", callback_data='back')]
    ]
    
    instruction_text = (
        "✈️ Получение информации о рейсе\n\n"
        "Введите номер рейса в формате:\n"
        "<код авиакомпании><номер рейса>\n\n"
        "Примеры:\n"
        "SU1234\n"
        "S7151\n"
        "U6256\n\n"
        "Я покажу актуальную информацию о рейсе."
    )
    
    if update.callback_query:
        await message.edit_text(
            instruction_text,
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    else:
        await message.reply_text(
            instruction_text,
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

async def handle_flight_info_request(update: Update, flight_number: str):
    """Обрабатывает запрос информации о рейсе"""
    try:
        # Очищаем номер рейса от лишних символов
        flight_number = flight_number.strip().upper()
        
        if not flight_number:
            await update.message.reply_text("❌ Пожалуйста, введите номер рейса")
            return
        
        # Параметры запроса к AviationStack
        params = {
            'access_key': AVIATIONSTACK_API_KEY,
            'flight_iata': flight_number,
            'limit': 1
        }
        
        # Выполняем запрос
        response = requests.get(AVIATIONSTACK_FLIGHT_URL, params=params, timeout=15)
        
        try:
            data = response.json()
        except json.JSONDecodeError as e:
            logger.error(f"JSON decode error: {e}")
            await update.message.reply_text(
                "❌ Ошибка при обработке ответа от сервера авиаданных.",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("← Попробовать снова", callback_data='flight_info')],
                    [InlineKeyboardButton("← Назад", callback_data='back')]
                ])
            )
            return
        
        # Проверяем наличие данных о рейсах
        flight_data_list = data.get('data', [])
        if not flight_data_list:
            await update.message.reply_text(
                f"❌ Информация о рейсе {flight_number} не найдена.\n"
                "Проверьте правильность номера рейса.",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("← Попробовать снова", callback_data='flight_info')],
                    [InlineKeyboardButton("← Назад", callback_data='back')]
                ])
            )
            return
        
        flight_data = flight_data_list[0]
        
        # Формируем сообщение с информацией о рейсе
        message = f"✈️ Информация о рейсе {flight_number}:\n\n"
        
        # Основная информация
        departure = flight_data.get('departure', {}) or {}
        arrival = flight_data.get('arrival', {}) or {}
        airline = flight_data.get('airline', {}) or {}
        flight_info = flight_data.get('flight', {}) or {}
        
        # 📅 Дата рейса в формате дд.мм.гггг
        flight_date = safe_get(flight_data, 'flight_date')
        if flight_date:
            message += f"📅 Дата рейса: {format_flight_date(flight_date)}\n"
        
        # 📊 Статус на русском
        status = safe_get(flight_data, 'flight_status', 'unknown')
        message += f"📊 Статус: {translate_status(status)}\n\n"
        
        # 🛫 Откуда и куда
        dep_airport = safe_get(departure, 'airport')
        dep_iata = safe_get(departure, 'iata')
        arr_airport = safe_get(arrival, 'airport')
        arr_iata = safe_get(arrival, 'iata')
        
        message += f"🛫 Откуда: {dep_airport or 'Неизвестно'} ({dep_iata or '?'})\n"
        message += f"🛬 Куда: {arr_airport or 'Неизвестно'} ({arr_iata or '?'})\n\n"
        
        # 🕐 Время вылета
        dep_scheduled = safe_get(departure, 'scheduled')
        dep_estimated = safe_get(departure, 'estimated')
        dep_actual = safe_get(departure, 'actual')
        
        if dep_scheduled:
            message += f"🕐 Вылет запланирован: {format_date(dep_scheduled)}\n"
        if dep_estimated and dep_estimated != dep_scheduled:
            message += f"🕐 Вылет ожидается: {format_date(dep_estimated)}\n"
        if dep_actual:
            message += f"🕐 Вылет фактический: {format_date(dep_actual)}\n"
        
        # Задержка вылета
        dep_delay = safe_get(departure, 'delay')
        if dep_delay and int(dep_delay) > 0:
            message += f"⏰ Задержка вылета: {dep_delay} мин\n"
        
        message += "\n"
        
        # 🕐 Время прибытия
        arr_scheduled = safe_get(arrival, 'scheduled')
        arr_estimated = safe_get(arrival, 'estimated')
        arr_actual = safe_get(arrival, 'actual')
        
        if arr_scheduled:
            message += f"🕐 Прибытие запланировано: {format_date(arr_scheduled)}\n"
        if arr_estimated and arr_estimated != arr_scheduled:
            message += f"🕐 Прибытие ожидается: {format_date(arr_estimated)}\n"
        if arr_actual:
            message += f"🕐 Прибытие фактическое: {format_date(arr_actual)}\n"
        
        # Задержка прибытия
        arr_delay = safe_get(arrival, 'delay')
        if arr_delay and int(arr_delay or 0) > 0:
            message += f"⏰ Задержка прибытия: {arr_delay} мин\n"
        
        message += "\n"
        
        # ✈️ Информация о рейсе
        airline_name = safe_get(airline, 'name')
        if airline_name:
            message += f"🏛️ Авиакомпания: {airline_name}\n"
        
        # Только номер рейса в формате IATA (без ICAO)
        flight_iata = safe_get(flight_info, 'iata')
        if flight_iata:
            message += f"🔢 Номер рейса: {flight_iata}\n"
        
        # Дополнительная информация (только если не None)
        dep_terminal = safe_get(departure, 'terminal')
        if dep_terminal:
            message += f"📍 Терминал вылета: {dep_terminal}\n"
        
        dep_gate = safe_get(departure, 'gate')
        if dep_gate:
            message += f"🚪 Гейт вылета: {dep_gate}\n"
        
        arr_terminal = safe_get(arrival, 'terminal')
        if arr_terminal:
            message += f"📍 Терминал прибытия: {arr_terminal}\n"
        
        arr_gate = safe_get(arrival, 'gate')
        if arr_gate:
            message += f"🚪 Гейт прибытия: {arr_gate}\n"
        
        arr_baggage = safe_get(arrival, 'baggage')
        if arr_baggage:
            message += f"🎒 Багаж: {arr_baggage}\n"
        
        # Клавиатура для возврата
        keyboard = [
            [InlineKeyboardButton("🔍 Проверить другой рейс", callback_data='flight_info')],
            [InlineKeyboardButton("← Назад", callback_data='back')]
        ]
        
        await update.message.reply_text(
            message,
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        
    except Exception as e:
        logger.error(f"Ошибка при получении информации о рейсе: {e}", exc_info=True)
        await update.message.reply_text(
            "❌ Произошла ошибка при получении информации о рейсе.\nПопробуйте позже.",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("← Попробовать снова", callback_data='flight_info')],
                [InlineKeyboardButton("← Назад", callback_data='back')]
            ])
        )