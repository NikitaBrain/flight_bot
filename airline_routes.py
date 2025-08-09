import logging
import requests
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from config import AVIASALES_AIRLINE_ROUTES_URL, AVIASALES_API_TOKEN
from utils import get_city_name, get_airline_name

logger = logging.getLogger(__name__)

def format_city(code: str, name: str) -> str:
    """Форматирует вывод города"""
    if code in ['SVO', 'DME', 'VKO']:
        return f"Москва ({code})"
    return f"{name} ({code})" if name != code else code

async def show_airline_selection(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показывает меню выбора авиакомпании"""
    if update.callback_query:
        query = update.callback_query
        await query.answer()
        message = query.message
    else:
        message = update.message
    
    keyboard = [
        [InlineKeyboardButton("Аэрофлот (SU)", callback_data='airline_SU')],
        [InlineKeyboardButton("S7 Airlines (S7)", callback_data='airline_S7')],
        [InlineKeyboardButton("Победа (DP)", callback_data='airline_DP')],
        [InlineKeyboardButton("Уральские авиалинии (U6)", callback_data='airline_U6')],
        [InlineKeyboardButton("ЮТэйр (UT)", callback_data='airline_UT')],
        [InlineKeyboardButton("Smartavia (5N)", callback_data='airline_5N')],
        [InlineKeyboardButton("← Назад", callback_data='back')]
    ]
    
    if update.callback_query:
        await message.edit_text(
            "✈️ Выберите авиакомпанию для просмотра популярных рейсов:",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    else:
        await message.reply_text(
            "✈️ Выберите авиакомпанию для просмотра популярных рейсов:",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

async def show_airline_routes(update: Update, context: ContextTypes.DEFAULT_TYPE, airline_code: str):
    """Показывает популярные рейсы авиакомпании"""
    query = update.callback_query
    await query.answer()
    
    try:
        # Получаем текущее сообщение для сравнения
        current_message = query.message.text
        current_markup = query.message.reply_markup

        params = {'airline_code': airline_code, 'limit': 10, 'token': AVIASALES_API_TOKEN}
        response = requests.get(AVIASALES_AIRLINE_ROUTES_URL, params=params, timeout=15)
        data = response.json()

        if not data.get('success', False) or not data.get('data'):
            new_message = "❌ Не удалось получить данные о рейсах."
            new_markup = InlineKeyboardMarkup([
                [InlineKeyboardButton("← Попробовать снова", callback_data='airline_routes')],
                [InlineKeyboardButton("← В главное меню", callback_data='back')]
            ])
            
            if (new_message != current_message) or (str(new_markup) != str(current_markup)):
                await query.edit_message_text(
                    text=new_message,
                    reply_markup=new_markup
                )
            return

        airline_name = await get_airline_name(airline_code)
        message = f"✈️ Топ-10 популярных рейсов {airline_name} ({airline_code}):\n\n"
        
        for i, (route, _) in enumerate(data['data'].items(), 1):
            origin, destination = route.split('-')
            origin_name = await get_city_name(origin)
            dest_name = await get_city_name(destination)
            
            message += f"{i}. {format_city(origin, origin_name)} → {format_city(destination, dest_name)}\n"

        keyboard = [
            [InlineKeyboardButton("← Выбрать другую авиакомпанию", callback_data='airline_routes')],
            [InlineKeyboardButton("← В главное меню", callback_data='back')]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        # Проверяем, действительно ли нужно обновлять сообщение
        if (message != current_message) or (str(reply_markup) != str(current_markup)):
            await query.edit_message_text(
                text=message,
                reply_markup=reply_markup,
            )
        else:
            await query.answer("Информация уже актуальна")

    except Exception as e:
        logger.error(f"Ошибка: {e}")
        await query.edit_message_text(
            "❌ Ошибка при обработке запроса.",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("← Попробовать снова", callback_data='airline_routes')],
                [InlineKeyboardButton("← В главное меню", callback_data='back')]
            ])
        )