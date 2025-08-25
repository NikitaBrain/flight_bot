import logging
import requests
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from config import AVIATIONSTACK_API_KEY, AVIATIONSTACK_FLIGHT_URL
from utils import format_date
import json

logger = logging.getLogger(__name__)

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
        message = f"✈️ Информация о рейсе {flight_number}:\n\n"
        
        # Основная информация с безопасным доступом к данным
        departure = flight_data.get('departure', {}) or {}
        arrival = flight_data.get('arrival', {}) or {}
        
        message += f"🛫 Вылет: {departure.get('airport', 'Неизвестно')} "
        message += f"({departure.get('iata', '?')})\n"
        
        message += f"🛬 Прибытие: {arrival.get('airport', 'Неизвестно')} "
        message += f"({arrival.get('iata', '?')})\n\n"
        
        # Время вылета и прибытия
        if departure.get('scheduled'):
            message += f"📅 Запланированный вылет: {format_date(departure['scheduled'])}\n"
        
        if arrival.get('scheduled'):
            message += f"📅 Запланированное прибытие: {format_date(arrival['scheduled'])}\n\n"
        
        # Статус рейса
        status = flight_data.get('flight_status', 'unknown')
        status_emoji = {
            'scheduled': '📅',
            'active': '🛫',
            'landed': '🛬',
            'cancelled': '❌',
            'incident': '⚠️',
            'diverted': '🔄'
        }.get(status, '❓')
        
        message += f"📊 Статус: {status_emoji} {status.capitalize()}\n"
        
        # Дополнительная информация с проверкой на None
        airline = flight_data.get('airline', {}) or {}
        if airline and airline.get('name'):
            message += f"🏛️ Авиакомпания: {airline['name']}\n"
        
        # Безопасный доступ к aircraft (может быть None)
        aircraft = flight_data.get('aircraft')
        if aircraft and isinstance(aircraft, dict) and aircraft.get('iata'):
            message += f"🛩️ Тип ВС: {aircraft['iata']}\n"
        elif aircraft and isinstance(aircraft, dict) and aircraft.get('registration'):
            message += f"🛩️ Регистрация: {aircraft['registration']}\n"
        
        flight_info = flight_data.get('flight', {}) or {}
        if flight_info and flight_info.get('number'):
            message += f"🔢 Номер рейса: {flight_info['number']}\n"
        
        # Информация о задержке
        if departure.get('delay'):
            message += f"⏰ Задержка вылета: {departure['delay']} мин\n"
        
        if arrival.get('delay'):
            message += f"⏰ Задержка прибытия: {arrival['delay']} мин\n"
        
        # Добавляем дату рейса
        if flight_data.get('flight_date'):
            message += f"📅 Дата рейса: {flight_data['flight_date']}\n"
        
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