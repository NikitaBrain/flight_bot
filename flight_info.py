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
        'scheduled': '✔️ Запланирован',
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
        "Примеры:\n"
        "SU1234\n"
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
        
        # Основная информация
        departure = flight_data.get('departure', {}) or {}
        arrival = flight_data.get('arrival', {}) or {}
        airline = flight_data.get('airline', {}) or {}
        flight_info = flight_data.get('flight', {}) or {}
        aircraft = flight_data.get('aircraft', {}) or {}
        
        # Формируем сообщение с информацией о рейсе
        message = f"✈️ Информация о рейсе {flight_number}:\n\n"
        
        # Откуда и куда
        dep_airport = safe_get(departure, 'airport')
        dep_iata = safe_get(departure, 'iata')
        arr_airport = safe_get(arrival, 'airport')
        arr_iata = safe_get(arrival, 'iata')
        
        message += f"{dep_airport or 'Неизвестно'} ({dep_iata or '?'}) - {arr_airport or 'Неизвестно'} ({arr_iata or '?'})\n"
        
        # Дата рейса и статус
        flight_date = safe_get(flight_data, 'flight_date')
        if flight_date:
            message += f"📅 Дата рейса: {format_flight_date(flight_date)}\n"
        
        status = safe_get(flight_data, 'flight_status', 'unknown')
        message += f"📊 Статус: {translate_status(status)}\n\n"
        
        # 🛫 ВЫЛЕТ
        message += "🛫 ВЫЛЕТ:\n"
        message += f"📍 Аэропорт: {dep_airport or 'Неизвестно'} ({dep_iata or '?'})\n"
        
        # Только не-None поля для вылета
        dep_terminal = safe_get(departure, 'terminal')
        if dep_terminal:
            message += f"ℹ️ Терминал: {dep_terminal}\n"
        
        dep_gate = safe_get(departure, 'gate')
        if dep_gate:
            message += f"🚪 Гейт: {dep_gate}\n"
        
        dep_scheduled = safe_get(departure, 'scheduled')
        if dep_scheduled:
            message += f"🕐 Запланировано: {format_date(dep_scheduled)}\n"
        
        dep_estimated = safe_get(departure, 'estimated')
        if dep_estimated:
            message += f"🕐 Ожидается: {format_date(dep_estimated)}\n"
        
        dep_actual = safe_get(departure, 'actual')
        if dep_actual:
            message += f"🕐 Фактически: {format_date(dep_actual)}\n"
        
        dep_delay = safe_get(departure, 'delay')
        if dep_delay and int(dep_delay) > 0:
            message += f"⏰ Задержка: {dep_delay} мин\n"
        
        message += "\n"
        
        # 🛬 ПРИБЫТИЕ
        message += "🛬 ПРИБЫТИЕ:\n"
        message += f"📍 Аэропорт: {arr_airport or 'Неизвестно'} ({arr_iata or '?'})\n"
        
        # Только не-None поля для прибытия
        arr_terminal = safe_get(arrival, 'terminal')
        if arr_terminal:
            message += f"ℹ️ Терминал: {arr_terminal}\n"
        
        arr_gate = safe_get(arrival, 'gate')
        if arr_gate:
            message += f"🚪 Гейт: {arr_gate}\n"
        
        arr_baggage = safe_get(arrival, 'baggage')
        if arr_baggage:
            message += f"🛄 Багаж: {arr_baggage}\n"
        
        arr_scheduled = safe_get(arrival, 'scheduled')
        if arr_scheduled:
            message += f"🕐 Запланировано: {format_date(arr_scheduled)}\n"
        
        arr_estimated = safe_get(arrival, 'estimated')
        if arr_estimated:
            message += f"🕐 Ожидается: {format_date(arr_estimated)}\n"
        
        arr_actual = safe_get(arrival, 'actual')
        if arr_actual:
            message += f"🕐 Фактически: {format_date(arr_actual)}\n"
        
        arr_delay = safe_get(arrival, 'delay')
        if arr_delay and int(arr_delay or 0) > 0:
            message += f"• ⏰ Задержка: {arr_delay} мин\n"
        
        message += "\n"
        
        # ✈️ ИНФОРМАЦИЯ О РЕЙСЕ
        message += "✈️ ИНФОРМАЦИЯ О РЕЙСЕ:\n"
        
        airline_name = safe_get(airline, 'name')
        airline_iata = safe_get(airline, 'iata')
        if airline_name and airline_iata:
            message += f"• Авиакомпания: {airline_name} ({airline_iata})\n"
        elif airline_name:
            message += f"• Авиакомпания: {airline_name}\n"
        
        flight_iata = safe_get(flight_info, 'iata')
        if flight_iata:
            message += f"• Номер рейса: {flight_iata}\n"
        
        # Информация о самолете (если есть)
        aircraft_iata = safe_get(aircraft, 'iata')
        aircraft_name = safe_get(aircraft, 'name')
        if aircraft_iata and aircraft_name:
            message += f"• Самолет: {aircraft_name} ({aircraft_iata})\n"
        elif aircraft_name:
            message += f"• Самолет: {aircraft_name}\n"
        elif aircraft_iata:
            message += f"• Самолет: {aircraft_iata}\n"
        
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