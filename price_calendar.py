import logging
from datetime import datetime
import requests
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from config import AVIASALES_CALENDAR_URL, AVIASALES_API_TOKEN
from utils import get_city_code, format_date

logger = logging.getLogger(__name__)

async def handle_price_calendar(update: Update, text: str) -> None:
    """Обработка запроса календаря цен"""
    try:
        parts = text.split()
        if len(parts) < 2:
            await update.message.reply_text("❌ Укажите города отправления и назначения (например: Москва Сочи)")
            return

        origin = await get_city_code(parts[0])
        destination = await get_city_code(parts[1])
        
        if not origin or not destination:
            await update.message.reply_text("❌ Города не найдены. Провробуйте другие названия.")
            return

        params = {
            'origin': origin,
            'destination': destination,
            'depart_date': datetime.now().strftime("%Y-%m"),
            'calendar_type': 'departure_date',
            'token': AVIASALES_API_TOKEN,
            'currency': 'rub'
        }

        response = requests.get(AVIASALES_CALENDAR_URL, params=params, timeout=15)
        data = response.json()
        
        if not data.get('data'):
            await update.message.reply_text("❌ Данные по ценам не найдены для указанного направления.")
            return

        message = f"📅 Календарь цен {origin} → {destination}:\n\n"
        prices = []
        
        for date_str, ticket_data in data['data'].items():
            if 'price' in ticket_data:
                date = datetime.strptime(date_str, "%Y-%m-%d")
                prices.append((date.strftime("%d.%m.%Y"), ticket_data['price']))
        
        prices.sort(key=lambda x: datetime.strptime(x[0], "%d.%m.%Y"))
        
        for date, price in prices[:30]:
            message += f"📅 {date}: {price} RUB\n"
        
        # message += f"\n🔗 Подробнее: https://www.aviasales.ru/search/{origin}{destination}"

        keyboard = [[InlineKeyboardButton("← Назад", callback_data='back')]]
        await update.message.reply_text(
            message,
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        
    except Exception as e:
        logger.error(f"Ошибка в календаре цен: {e}")
        await update.message.reply_text("❌ Ошибка при получении данных. Попробуйте позже.")