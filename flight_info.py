import logging
import requests
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from config import AVIATIONSTACK_API_KEY, AVIATIONSTACK_FLIGHT_URL
from utils import format_date
from favorites import FavoritesManager
from storage import favorite_storage
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
        "Введите номер рейса:\n"
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
        
        # Формируем сообщение с информацией о рейсе
        message = f"✈️ Информация о рейсе {flight_number}:\n\n"
        
        # Основная информация
        departure = flight_data.get('departure', {}) or {}
        arrival = flight_data.get('arrival', {}) or {}
        airline = flight_data.get('airline', {}) or {}
        flight_info = flight_data.get('flight', {}) or {}
        
        # 📅 Дата и статус рейса
        flight_date = safe_get(flight_data, 'flight_date')
        if flight_date:
            message += f"📅 Дата рейса: {format_flight_date(flight_date)}\n"
        
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
        
        # Сохраняем данные рейса для возможного добавления в избранное
        user_id = update.message.from_user.id
        flight_data_for_favorite = {
            'flight_number': flight_number,
            'flight_iata': flight_iata,
            'airline': airline_name,
            'departure_airport': dep_airport,
            'departure_iata': dep_iata,
            'arrival_airport': arr_airport,
            'arrival_iata': arr_iata,
            'flight_date': flight_date,
            'current_status': status,
            'scheduled_departure': dep_scheduled,
            'estimated_departure': dep_estimated
        }
        
        # Сохраняем в контексте для callback
        context.user_data['current_flight_data'] = flight_data_for_favorite
        
        # Клавиатура с кнопкой добавления в избранное
        keyboard = [
            [InlineKeyboardButton("⭐ Добавить в избранное", callback_data=f'fav_flight_{flight_number}')],
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

async def add_flight_to_favorites(update: Update, context: ContextTypes.DEFAULT_TYPE, flight_number: str):
    """Добавляет рейс в избранное для отслеживания"""
    try:
        query = update.callback_query
        await query.answer()
        
        user_id = query.from_user.id
        flight_data = context.user_data.get('current_flight_data', {})
        
        if not flight_data:
            await query.edit_message_text("❌ Не удалось добавить рейс в избранное. Сначала выполните поиск рейса.")
            return
        
        # Создаем уникальный ключ для рейса
        route_key = f"flight_{flight_number}_{flight_data.get('flight_date', '')}"
        
        favorite_data = {
            'route_key': route_key,
            'type': 'flight',
            'flight_number': flight_number,
            'flight_iata': flight_data.get('flight_iata'),
            'airline': flight_data.get('airline'),
            'departure_airport': flight_data.get('departure_airport'),
            'departure_iata': flight_data.get('departure_iata'),
            'arrival_airport': flight_data.get('arrival_airport'),
            'arrival_iata': flight_data.get('arrival_iata'),
            'flight_date': flight_data.get('flight_date'),
            'current_status': flight_data.get('current_status'),
            'scheduled_departure': flight_data.get('scheduled_departure'),
            'estimated_departure': flight_data.get('estimated_departure'),
            'added_at': datetime.now().isoformat()
        }
        
        if favorite_storage.add_favorite(user_id, favorite_data):
            await query.edit_message_text(
                f"✅ Рейс {flight_number} добавлен в избранное!\n"
                "Вы будете получать уведомления об изменении статуса и времени вылета.",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("Мои избранные рейсы", callback_data='my_favorites')],
                    [InlineKeyboardButton("← Назад", callback_data='back')]
                ])
            )
        else:
            await query.edit_message_text("❌ Этот рейс уже есть в вашем избранном!")
            
    except Exception as e:
        logger.error(f"Ошибка при добавлении рейса в избранное: {e}")
        await update.callback_query.edit_message_text(
            "❌ Ошибка при добавлении в избранное.",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("← Назад", callback_data='back')]
            ])
        )