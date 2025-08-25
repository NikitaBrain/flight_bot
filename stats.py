import logging
from datetime import datetime
import requests
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from config import AVIASALES_STATS_URL, AVIASALES_API_TOKEN
from utils import get_city_code

logger = logging.getLogger(__name__)

async def handle_price_stats(update: Update, text: str) -> None:
    """Обработка статистики цен с детализацией по месяцам и общей сводкой"""
    try:
        parts = text.split()
        if len(parts) < 2:
            await update.message.reply_text("❌ Укажите города отправления и назначения (например: Москва Сочи)")
            return

        origin = await get_city_code(parts[0])
        destination = await get_city_code(parts[1])
        
        if not origin or not destination:
            await update.message.reply_text("❌ Города не найдены. Попробуйте другие названия.")
            return

        params = {
            'origin': origin,
            'destination': destination,
            'token': AVIASALES_API_TOKEN,
            'currency': 'rub'
        }

        response = requests.get(AVIASALES_STATS_URL, params=params, timeout=15)
        data = response.json()
        
        if not data.get('success', False):
            await update.message.reply_text("❌ Ошибка при получении данных от API.")
            return
            
        stats = data.get('data', {})
        
        if not stats:
            await update.message.reply_text("❌ Нет данных о ценах для анализа.")
            return

        # Собираем данные для статистики
        monthly_data = []
        valid_months = 0
        
        # Формируем основное сообщение
        message = f"📊 Подробная статистика цен {origin} → {destination}:\n\n"
        
        # Обрабатываем каждый месяц
        for month_str, month_data in sorted(stats.items()):
            if not isinstance(month_data, dict):
                continue
                
            price = month_data.get('price')
            if not price:
                continue
                
            # Форматируем название месяца
            try:
                month_name = datetime.strptime(month_str, "%Y-%m").strftime("%B %Y")
            except ValueError:
                month_name = month_str
                
            monthly_data.append({
                'month': month_str,
                'month_name': month_name,
                'price': price
            })
            valid_months += 1
            
            message += (
                f"• {month_name}:\n"
                f"  💰 Минимальная цена: {price} RUB\n\n"
            )

        if valid_months == 0:
            await update.message.reply_text("❌ Нет данных о ценах для отображения.")
            return

        # Рассчитываем общую статистику
        min_price = min(item['price'] for item in monthly_data)
        max_price = max(item['price'] for item in monthly_data)
        avg_price = sum(item['price'] for item in monthly_data) / valid_months
        
        # Самый дешевый и дорогой месяц
        cheapest_month = min(monthly_data, key=lambda x: x['price'])
        expensive_month = max(monthly_data, key=lambda x: x['price'])

        # Добавляем общую статистику
        message += (
            "\n🔍 Итоговая статистика:\n"
            f"• Самый дешевый месяц: {cheapest_month['month_name']} - {cheapest_month['price']} RUB\n"
            f"• Самый дорогой месяц: {expensive_month['month_name']} - {expensive_month['price']} RUB\n"
            f"• Средняя минимальная цена: {int(avg_price)} RUB\n"
            f"• Разброс цен: {max_price - min_price} RUB\n"
            f"• Анализировано месяцев: {valid_months}\n\n"
            # f"🔗 Подробнее: https://www.aviasales.ru/stats/{origin}{destination}"
        )

        keyboard = [[InlineKeyboardButton("← Назад", callback_data='back')]]
        await update.message.reply_text(
            message,
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        
    except requests.exceptions.RequestException as e:
        logger.error(f"Ошибка сети при запросе статистики: {e}")
        await update.message.reply_text("❌ Ошибка соединения с сервером. Попробуйте позже.")
    except Exception as e:
        logger.error(f"Ошибка в статистике цен: {e}")
        await update.message.reply_text("❌ Произошла непредвиденная ошибка. Попробуйте другой запрос.")