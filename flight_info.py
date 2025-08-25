import logging
import requests
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from config import AVIATIONSTACK_API_KEY, AVIATIONSTACK_FLIGHT_URL
from utils import format_date
import json

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

def safe_get(data, key, default='Неизвестно'):
    """Безопасное получение значения из словаря"""
    if not data or not isinstance(data, dict):
        return default
    return data.get(key, default)

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
        
        # Логируем ответ для отладки
        logger.info(f"AviationStack response status: {response.status_code}")
        
        try:
            data = response.json()
        except json.JSONDecodeError as e:
            logger.error(f"JSON decode error: {e}, response text: {response.text}")
            await update.message.reply_text(
                "❌ Ошибка при обработке ответа от сервера авиаданных.",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("← Попробовать снова", callback_data='flight_info')],
                    [InlineKeyboardButton("← Назад", callback_data='back')]
                ])
            )
            return
        
        # Проверяем структуру ответа
        if not data or not isinstance(data, dict):
            logger.error(f"Invalid response format: {data}")
            await update.message.reply_text(
                "❌ Неверный формат ответа от сервера авиаданных.",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("← Попробовать снова", callback_data='flight_info')],
                    [InlineKeyboardButton("← Назад", callback_data='back')]
                ])
            )
            return
        
        # Проверяем наличие ошибок в ответе
        if 'error' in data:
            error_info = data.get('error', {})
            error_message = error_info.get('message', 'Неизвестная ошибка')
            logger.error(f"AviationStack error: {error_message}")
            await update.message.reply_text(
                f"❌ Ошибка API: {error_message}",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("← Попробовать снова", callback_data='flight_info')],
                    [InlineKeyboardButton("← Назад", callback_data='back')]
                ])
            )
            return
        
        # Проверяем наличие данных о рейсах
        flight_data_list = data.get('data', [])
        if not flight_data_list or not isinstance(flight_data_list, list):
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
        message = f"✈️ Детальная информация о рейсе {flight_number}:\n\n"
        
        # Основная информация
        departure = flight_data.get('departure', {}) or {}
        arrival = flight_data.get('arrival', {}) or {}
        airline = flight_data.get('airline', {}) or {}
        flight_info = flight_data.get('flight', {}) or {}
        aircraft = flight_data.get('aircraft', {}) or {}
        live_data = flight_data.get('live', {}) or {}
        
        # 📅 Дата и статус рейса
        message += f"📅 Дата рейса: {flight_data.get('flight_date', 'Неизвестно')}\n"
        status = flight_data.get('flight_status', 'unknown')
        message += f"📊 Статус: {translate_status(status)}\n\n"
        
        # 🛫 Информация о вылете
        message += "🛫 ВЫЛЕТ:\n"
        message += f"• Аэропорт: {safe_get(departure, 'airport')} ({safe_get(departure, 'iata')})\n"
        message += f"• Терминал: {safe_get(departure, 'terminal')}\n"
        message += f"• Гейт: {safe_get(departure, 'gate')}\n"
        
        if departure.get('scheduled'):
            message += f"• Запланировано: {format_date(departure['scheduled'])}\n"
        if departure.get('estimated'):
            message += f"• Ожидается: {format_date(departure['estimated'])}\n"
        if departure.get('actual'):
            message += f"• Фактически: {format_date(departure['actual'])}\n"
        
        delay = departure.get('delay')
        if delay and int(delay) > 0:
            message += f"• ⏰ Задержка: {delay} мин\n"
        
        message += "\n"
        
        # 🛬 Информация о прибытии
        message += "🛬 ПРИБЫТИЕ:\n"
        message += f"• Аэропорт: {safe_get(arrival, 'airport')} ({safe_get(arrival, 'iata')})\n"
        message += f"• Терминал: {safe_get(arrival, 'terminal')}\n"
        message += f"• Гейт: {safe_get(arrival, 'gate')}\n"
        message += f"• Багаж: {safe_get(arrival, 'baggage')}\n"
        
        if arrival.get('scheduled'):
            message += f"• Запланировано: {format_date(arrival['scheduled'])}\n"
        if arrival.get('estimated'):
            message += f"• Ожидается: {format_date(arrival['estimated'])}\n"
        if arrival.get('actual'):
            message += f"• Фактически: {format_date(arrival['actual'])}\n"
        
        arrival_delay = arrival.get('delay')
        if arrival_delay and int(arrival_delay or 0) > 0:
            message += f"• ⏰ Задержка: {arrival_delay} мин\n"
        
        message += "\n"
        
        # ✈️ Информация о рейсе и авиакомпании
        message += "✈️ ИНФОРМАЦИЯ О РЕЙСЕ:\n"
        message += f"• Авиакомпания: {safe_get(airline, 'name')} ({safe_get(airline, 'iata')})\n"
        message += f"• Номер рейса: {safe_get(flight_info, 'number')}\n"
        message += f"• Код IATA: {safe_get(flight_info, 'iata')}\n"
        message += f"• Код ICAO: {safe_get(flight_info, 'icao')}\n"
        
        # 🛩️ Информация о самолете (если доступна)
        if aircraft:
            message += f"• Тип ВС: {safe_get(aircraft, 'iata')} ({safe_get(aircraft, 'registration')})\n"
        
        # 📡 Live данные (если доступны)
        if live_data:
            message += "\n📡 ДАННЫЕ В РЕАЛЬНОМ ВРЕМЕНИ:\n"
            if live_data.get('altitude'):
                message += f"• Высота: {live_data['altitude']} м\n"
            if live_data.get('speed'):
                message += f"• Скорость: {live_data['speed']} км/ч\n"
            if live_data.get('direction'):
                message += f"• Направление: {live_data['direction']}°\n"
        
        # Клавиатура для возврата
        keyboard = [
            [InlineKeyboardButton("🔍 Проверить другой рейс", callback_data='flight_info')],
            [InlineKeyboardButton("← Назад", callback_data='back')]
        ]
        
        await update.message.reply_text(
            message,
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        
    except requests.exceptions.Timeout:
        await update.message.reply_text(
            "❌ Превышено время ожидания ответа от сервера.\nПопробуйте позже.",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("← Попробовать снова", callback_data='flight_info')],
                [InlineKeyboardButton("← Назад", callback_data='back')]
                ])
            )
    except IndexError:
        await update.message.reply_text(
            f"❌ Информация о рейсе {flight_number} не найдена.\n"
            "Проверьте правильность номера рейса.",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("← Попробовать снова", callback_data='flight_info')],
                [InlineKeyboardButton("← Назад", callback_data='back')]
            ])
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