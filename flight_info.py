import logging
import requests
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from config import AVIATIONSTACK_API_KEY, AVIATIONSTACK_FLIGHT_URL
from utils import format_date

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
        
        # Проверяем статус ответа
        if response.status_code != 200:
            await update.message.reply_text(
                f"❌ Ошибка сервера: {response.status_code}\nПопробуйте позже.",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("← Попробовать снова", callback_data='flight_info')],
                    [InlineKeyboardButton("← Назад", callback_data='back')]
                ])
            )
            return
        
        data = response.json()
        
        # Проверяем наличие данных о рейсах
        if not data.get('data'):
            await update.message.reply_text(
                f"❌ Информация о рейсе {flight_number} не найдена.\n"
                "Проверьте правильность номера рейса.",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("← Попробовать снова", callback_data='flight_info')],
                    [InlineKeyboardButton("← Назад", callback_data='back')]
                ])
            )
            return
        
        flight_data = data['data'][0]
        
        # Формируем сообщение с информацией о рейсе
        message = f"✈️ Информация о рейсе {flight_number}:\n\n"
        
        # Основная информация
        departure = flight_data.get('departure', {})
        arrival = flight_data.get('arrival', {})
        airline = flight_data.get('airline', {})
        flight = flight_data.get('flight', {})
        aircraft = flight_data.get('aircraft', {})
        
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
        
        status_translation = {
            'scheduled': 'по расписанию',
            'active': 'в полете',
            'landed': 'приземлился',
            'cancelled': 'отменен',
            'incident': 'инцидент',
            'diverted': 'перенаправлен',
            'unknown': 'неизвестен'
        }.get(status, 'неизвестен')
        
        message += f"📊 Статус: {status_emoji} {status_translation}\n"
        
        # Дополнительная информация
        if airline.get('name'):
            message += f"🏛️ Авиакомпания: {airline['name']}\n"
        
        if aircraft.get('iata'):
            message += f"🛩️ Тип ВС: {aircraft['iata']}\n"
        
        if flight.get('number'):
            message += f"🔢 Номер рейса: {flight['number']}\n"
        
        # Информация о задержке
        if departure.get('delay'):
            message += f"⏰ Задержка вылета: {departure['delay']} мин\n"
        
        if arrival.get('delay'):
            message += f"⏰ Задержка прибытия: {arrival['delay']} мин\n"
        
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
    except Exception as e:
        logger.error(f"Ошибка при получении информации о рейсе: {e}")
        await update.message.reply_text(
            "❌ Произошла ошибка при получении информации о рейсе.\nПопробуйте позже.",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("← Попробовать снова", callback_data='flight_info')],
                [InlineKeyboardButton("← Назад", callback_data='back')]
            ])
        )