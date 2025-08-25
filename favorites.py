from typing import Dict, Optional
from datetime import datetime
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from storage import favorite_storage
from config import AVIASALES_CHEAP_URL, AVIASALES_API_TOKEN
import requests
from utils import get_airline_name, format_date

logger = logging.getLogger(__name__)

class FavoritesManager:
    """Управление избранными рейсами и уведомлениями"""
    
    @staticmethod
    def create_route_key(origin: str, destination: str, 
                        depart_date: Optional[str] = None, 
                        return_date: Optional[str] = None) -> str:
        """Создает уникальный ключ для маршрута"""
        key_parts = [origin, destination]
        if depart_date:
            key_parts.append(depart_date)
        if return_date:
            key_parts.append(return_date)
        return "-".join(key_parts)
    
    @staticmethod
    async def add_to_favorites(update: Update, user_id: int, search_params: Dict) -> None:
        """Добавляет рейс в избранное"""
        route_key = FavoritesManager.create_route_key(
            origin=search_params['origin'],
            destination=search_params['destination'],
            depart_date=search_params.get('depart_date'),
            return_date=search_params.get('return_date')
        )
        
        route_data = {
            'route_key': route_key,
            'origin': search_params['origin'],
            'destination': search_params['destination'],
            'depart_date': search_params.get('depart_date'),
            'return_date': search_params.get('return_date'),
            'added_at': datetime.now().isoformat()
        }
        
        if favorite_storage.add_favorite(user_id, route_data):
            message = update.message or update.callback_query.message
            await message.reply_text(
                "✅ Рейс добавлен в избранное!\n"
                "Вы будете получать ежедневные уведомления о самых дешевых билетах.",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("Мои избранные", callback_data='my_favorites')],
                    [InlineKeyboardButton("Назад", callback_data='back')]
                ])
            )
        else:
            message = update.message or update.callback_query.message
            await message.reply_text("❌ Этот рейс уже есть в вашем избранном!")
    
    @staticmethod
    async def show_favorites_menu(update: Update, user_id: int) -> None:
        """Показывает меню избранных рейсов"""
        message = update.message or update.callback_query.message
        
        favorites = favorite_storage.get_user_favorites(user_id)
        
        if not favorites:
            await message.reply_text(
                "У вас пока нет избранных рейсов.",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("Назад", callback_data='back')]
                ])
            )
            return
        
        keyboard = []
        for fav in favorites:
            btn_text = (
                f"{fav['origin']} → {fav['destination']} "
                f"{fav.get('depart_date', '')} {fav.get('return_date', '')}"
            )
            keyboard.append([InlineKeyboardButton(
                btn_text, 
                callback_data=f"fav_detail_{fav['route_key']}"
            )])
        
        keyboard.append([InlineKeyboardButton("← Назад", callback_data='back')])
        
        await message.reply_text(
            "📌 Ваши избранные рейсы:",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    
    @staticmethod
    async def show_favorite_details(update: Update, user_id: int, route_key: str) -> None:
        """Показывает детали избранного рейса с кнопкой удаления"""
        message = update.message or update.callback_query.message
        
        favorites = favorite_storage.get_user_favorites(user_id)
        favorite = next((f for f in favorites if f['route_key'] == route_key), None)
        
        if not favorite:
            await message.reply_text("❌ Рейс не найден в избранном")
            return
        
        msg_text = (
            f"🔍 Избранный рейс:\n"
            f"🛫 {favorite['origin']} → {favorite['destination']}\n"
            f"📅 Вылет: {favorite.get('depart_date', 'любая дата')}\n"
            f"📅 Возвращение: {favorite.get('return_date', 'не указано')}\n\n"
            f"Добавлен: {datetime.fromisoformat(favorite['added_at']).strftime('%d.%m.%Y %H:%M')}"
        )
        
        keyboard = [
            [InlineKeyboardButton("🗑 Удалить из избранного", callback_data=f"fav_remove_{route_key}")],
            [InlineKeyboardButton("← Назад", callback_data='my_favorites')]
        ]
        
        await message.reply_text(
            msg_text,
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    
    @staticmethod
    async def remove_favorite(update: Update, user_id: int, route_key: str) -> None:
        """Удаляет рейс из избранного"""
        message = update.message or update.callback_query.message
        
        if favorite_storage.remove_favorite(user_id, route_key):
            await message.reply_text("✅ Рейс удален из избранного!")
        else:
            await message.reply_text("❌ Не удалось найти этот рейс в избранном")
    
    @staticmethod
    async def check_favorites_and_notify(context) -> None:
        """Проверяет избранные рейсы и отправляет уведомления"""
        all_favorites = favorite_storage.get_all_favorites()
        
        for user_id, favorites in all_favorites.items():
            for fav in favorites:
                try:
                    params = {
                        'origin': fav['origin'],
                        'destination': fav['destination'],
                        'token': AVIASALES_API_TOKEN,
                        'currency': 'rub'
                    }
                    
                    if fav.get('depart_date'):
                        params['depart_date'] = fav['depart_date']
                    if fav.get('return_date'):
                        params['return_date'] = fav['return_date']
                    
                    response = requests.get(AVIASALES_CHEAP_URL, params=params, timeout=15)
                    data = response.json()
                    
                    if data.get('success', False) and data.get('data'):
                        tickets = []
                        for dest_data in data['data'].values():
                            if isinstance(dest_data, dict):
                                tickets.extend(dest_data.values())
                        
                        if tickets:
                            valid_tickets = [t for t in tickets if isinstance(t, dict) and 'price' in t]
                            if valid_tickets:
                                cheapest = min(valid_tickets, key=lambda x: float(x['price']))
                                
                                message = (
                                    f"🔔 Ежедневное обновление по вашему избранному рейсу:\n"
                                    f"🛫 {fav['origin']} → {fav['destination']}\n"
                                    f"📅 Вылет: {fav.get('depart_date', 'любая дата')}\n"
                                    f"📅 Возвращение: {fav.get('return_date', 'не указано')}\n\n"
                                    f"🎫 Самый дешевый билет сегодня:\n"
                                    f"💰 Цена: {cheapest['price']} RUB\n"
                                    f"✈️ Авиакомпания: {await get_airline_name(cheapest.get('airline', ''))}\n"
                                    f"🛫 Вылет: {format_date(cheapest.get('departure_at', ''))}\n"
                                    f"_*точное предложение смотрите на официальном сайте авиакомпании_"
                                    # f"🔗 Подробнее: https://www.aviasales.ru/search/{fav['origin']}{fav['destination']}"
                                )
                                
                                await context.bot.send_message(chat_id=user_id, text=message)
                except Exception as e:
                    logger.error(f"Error checking favorite for user {user_id}: {e}")