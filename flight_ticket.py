import requests
from telegram import (
    Update, 
    InlineKeyboardButton, 
    InlineKeyboardMarkup,
    ReplyKeyboardMarkup,
    ReplyKeyboardRemove,
    KeyboardButton
)
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    CallbackQueryHandler,
    filters
)
import logging
from datetime import datetime, timedelta
import pytz
from config import (
    TELEGRAM_BOT_TOKEN,
    AVIASALES_API_TOKEN,
    AVIASALES_CHEAP_URL,
    AVIASALES_CALENDAR_URL,
    CITY_SEARCH_URL,
    AIRLINES_URL,
    AIRCRAFT_URL
)
from favorites import FavoritesManager
from storage import favorite_storage
from price_calendar import handle_price_calendar
from stats import handle_price_stats
from airline_routes import show_airline_selection, show_airline_routes
from flight_info import show_flight_info_menu, handle_flight_info_request

# Настройка логгирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Кэш для хранения данных
city_cache = {}
airline_cache = {}
aircraft_cache = {}
user_states = {}
user_search_params = {}

async def load_city_codes():
    """Загружаем базу городов и их IATA-кодов"""
    global city_cache
    try:
        response = requests.get(CITY_SEARCH_URL, timeout=10)
        cities = response.json()
        city_cache = {city['name'].lower(): city['code'] for city in cities if 'code' in city and 'name' in city}
        logger.info(f"Loaded {len(city_cache)} city codes")
    except Exception as e:
        logger.error(f"Failed to load city codes: {e}")

async def load_airline_codes():
    """Загружаем базу авиакомпаний"""
    global airline_cache
    try:
        response = requests.get(AIRLINES_URL, timeout=10)
        airlines = response.json()
        airline_cache = {airline['code']: airline['name'] for airline in airlines if 'code' in airline and 'name' in airline}
        logger.info(f"Loaded {len(airline_cache)} airline codes")
    except Exception as e:
        logger.error(f"Failed to load airline codes: {e}")

async def load_aircraft_data():
    """Загружаем базу данных о самолетах"""
    global aircraft_cache
    try:
        response = requests.get(AIRCRAFT_URL, timeout=10)
        aircrafts = response.json()
        aircraft_cache = {aircraft['code']: aircraft['name'] for aircraft in aircrafts if 'code' in aircraft and 'name' in aircraft}
        logger.info(f"Loaded {len(aircraft_cache)} aircraft codes")
    except Exception as e:
        logger.error(f"Failed to load aircraft data: {e}")

async def get_city_code(city_name: str) -> str:
    """Получаем IATA-код города"""
    city_name = city_name.lower().strip()
    if city_name in city_cache:
        return city_cache[city_name]
    
    # Попробуем найти частичное совпадение
    for name, code in city_cache.items():
        if city_name in name:
            return code
    return None

async def get_airline_name(airline_code: str) -> str:
    """Получаем название авиакомпании по коду"""
    if not airline_cache:
        await load_airline_codes()
    return airline_cache.get(airline_code, airline_code)

async def get_aircraft_name(aircraft_code: str) -> str:
    """Получаем название самолета по коду"""
    if not aircraft_cache:
        await load_aircraft_data()
    return aircraft_cache.get(aircraft_code, aircraft_code)

def format_date(date_str: str) -> str:
    """Форматируем дату в дд.мм.гггг чч:мм"""
    try:
        dt = datetime.strptime(date_str, "%Y-%m-%dT%H:%M:%S%z")
        local_tz = pytz.timezone('Europe/Moscow')
        local_dt = dt.astimezone(local_tz)
        return local_dt.strftime("%d.%m.%Y %H:%M")
    except:
        return date_str

async def show_main_menu(update: Update, text: str = None, is_start: bool = False):
    """Показывает главное меню с Reply-кнопками под строкой ввода"""
    keyboard = [
        ["🔍 Дешевые билеты", "📅 Календарь цен"],
        ["📊 Статистика цен", "⭐ Избранное"],
        ["✈️ Популярные рейсы", "ℹ️ Инфо о рейсе"]
    ]
    reply_markup = ReplyKeyboardMarkup(
        keyboard,
        resize_keyboard=True,
        one_time_keyboard=False
    )
    
    if hasattr(update, 'message'):
        if is_start:
            await update.message.reply_text(
                "👋 Привет! Я - твой персональный бот для поиска авиабилетов!\n\n"
                "Вот что я могу для тебя сделать:\n"
                "✨ Найти самые дешевые билеты\n"
                "❤️ Сохранять направления и уведомлять о изменении цены\n"
                "📆 Показать лучшие даты для перелета\n"
                "📈 Поделиться статистикой цен\n"
                "✈️ Показать популярные направления у авиакомпаний\n"
                "ℹ️ Получить информацию о конкретном рейсе\n",
                reply_markup=reply_markup
            )
        else:
            await update.message.reply_text(
                "Выберите действие:",
                reply_markup=reply_markup
            )
    else:
        keyboard = [
            [InlineKeyboardButton("← Назад", callback_data='back')]
        ]
        await update.edit_message_text(
            "Выберите действие:",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    else:
        # Для callback-запросов оставляем возможность вернуться к главному меню
        keyboard = [
            [InlineKeyboardButton("← Назад", callback_data='back')]
        ]
        await update.edit_message_text(
            "Выберите действие:",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    else:
        # Для callback-запросов оставляем возможность вернуться к главному меню
        keyboard = [
            [InlineKeyboardButton("← Назад", callback_data='back')]
        ]
        await update.edit_message_text(
            "Выберите действие:",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработчик команды /start"""
    await load_city_codes()
    await load_airline_codes()
    await load_aircraft_data()
    await show_main_menu(update, is_start=True)

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработчик нажатий на кнопки"""
    query = update.callback_query
    await query.answer()

    logger.info(f"Received callback data: {query.data} (User: {query.from_user.id})")
    
    user_id = query.from_user.id
    choice = query.data
    
    current_state = user_states.get(user_id, 'no state')
    logger.info(f"User state before handling: {current_state}")
    
    if choice == 'back':
        await show_main_menu(query)
        return
    
    if choice == 'add_favorite':
        if user_id in user_search_params:
            await FavoritesManager.add_to_favorites(query, user_id, user_search_params[user_id])
        else:
            await query.edit_message_text("❌ Не удалось добавить в избранное. Сначала выполните поиск.")
        return
    
    if choice.startswith('fav_detail_'):
        route_key = choice.split('_', 2)[2]
        await FavoritesManager.show_favorite_details(query, user_id, route_key)
        return
    
    if choice.startswith('fav_remove_'):
        route_key = choice.split('_', 2)[2]
        await FavoritesManager.remove_favorite(query, user_id, route_key)
        return
    
    if choice.startswith('period_'):
        period = choice.split('_')[1]
        await handle_period_selection(query, user_id, period)
        return
    
    if choice.startswith('airline_'):
        airline_code = choice.split('_')[1]
        await show_airline_routes(update, context, airline_code)
        return
    
    if choice == 'airline_routes':
        await show_airline_selection(update, context)
        return
    
    # Обработка кнопок для информации о рейсе
    if choice == 'flight_info':
        user_states[user_id] = 'flight_info'
        from flight_info import show_flight_info_menu
        await show_flight_info_menu(update, context)
        return
    
    # Обработка других callback данных
    user_states[user_id] = choice
    
    instructions = {
        'cheap': (
            "🔍 Поиск дешевых билетов\n\n"
            "Введите маршрут в формате:\n"
            "<город отправления> <город назначения> [дата вылета ДД.ММ.ГГГГ] [дата возврата ДД.ММ.ГГГГ]\n\n"
            "Примеры:\n"
            "Москва Сочи\n"
            "Москва Сочи 01.08.2025\n"
            "Москва Сочи 01.08.2025 10.08.2025"
        ),
        'calendar': "📅 Введите маршрут для календаря цен в формате: <город отправления> <город назначения>",
        'stats': "📊 Введите маршрут для статистики цен в формате: <город отправления> <город назначения>",
        'flight_info': "✈️ Введите номер рейса в формате: <код авиакомпании><номер рейса> (например: SU1234)"
    }
    
    instruction_text = instructions.get(choice, "Выберите тип поиска")
    
    keyboard = [[InlineKeyboardButton("← Назад", callback_data='back')]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(
        text=instruction_text,
        reply_markup=reply_markup
    )

async def handle_cheap_tickets(update: Update, text: str):
    """Обработка поиска дешевых билетов"""
    try:
        parts = text.split()
        if len(parts) < 2:
            await update.message.reply_text("❌ Нужно указать как минимум город отправления и город назначения")
            return

        origin = await get_city_code(parts[0])
        destination = await get_city_code(parts[1])
        
        if not origin or not destination:
            await update.message.reply_text("❌ Не удалось распознать коды городов. Проверьте названия.")
            return

        depart_date = None
        return_date = None
        
        # Парсим даты, если они указаны
        if len(parts) >= 3:
            try:
                depart_date = datetime.strptime(parts[2], "%d.%m.%Y")
                if depart_date.date() < datetime.now().date():
                    await update.message.reply_text("❌ Дата вылета не может быть в прошлом")
                    return
            except ValueError:
                await update.message.reply_text("❌ Неверный формат даты вылета. Используйте ДД.ММ.ГГГГ")
                return
        
        if len(parts) >= 4:
            try:
                return_date = datetime.strptime(parts[3], "%d.%m.%Y")
                if depart_date and return_date.date() < depart_date.date():
                    await update.message.reply_text("❌ Дата возврата не может быть раньше даты вылета")
                    return
            except ValueError:
                await update.message.reply_text("❌ Неверный формат даты возврата. Используйте ДД.ММ.ГГГГ")
                return

        # Сохраняем параметры поиска для пользователя
        user_id = update.message.from_user.id
        user_search_params[user_id] = {
            'origin': origin,
            'destination': destination,
            'depart_date': depart_date.strftime("%Y-%m-%d") if depart_date else None,
            'return_date': return_date.strftime("%Y-%m-%d") if return_date else None
        }

        # Если даты не указаны, предлагаем выбрать период
        if not depart_date and not return_date:
            keyboard = [
                [
                    InlineKeyboardButton("7 дней", callback_data='period_7'),
                    InlineKeyboardButton("14 дней", callback_data='period_14')
                ],
                [
                    InlineKeyboardButton("30 дней", callback_data='period_30'),
                    InlineKeyboardButton("90 дней", callback_data='period_90')
                ],
                [
                    InlineKeyboardButton("Без периода", callback_data='period_none'),
                    InlineKeyboardButton("← Назад", callback_data='back')
                ]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await update.message.reply_text(
                "📅 Выберите период для поиска билетов:",
                reply_markup=reply_markup
            )
        else:
            # Если даты указаны, сразу выполняем поиск
            await search_exact_dates(
                update,
                origin=origin,
                destination=destination,
                depart_date=depart_date,
                return_date=return_date
            )
            
    except Exception as e:
        logger.error(f"Error in cheap tickets handler: {e}")
        await update.message.reply_text("❌ Произошла ошибка при обработке запроса. Попробуйте еще раз.")

async def search_exact_dates(update: Update, origin: str, destination: str, 
                           depart_date: datetime, return_date: datetime = None):
    """Поиск по точным датам"""
    params = {
        'origin': origin,
        'destination': destination,
        'depart_date': depart_date.strftime("%Y-%m-%d"),
        'token': AVIASALES_API_TOKEN,
        'currency': 'rub'
    }
    
    if return_date:
        params['return_date'] = return_date.strftime("%Y-%m-%d")
    
    await perform_search(update, params, is_period=False)

async def perform_search(update, params, is_period=False):
    """Функция для выполнения поиска билетов"""
    try:
        # Удаляем None значения из параметров
        params = {k: v for k, v in params.items() if v is not None}
        
        response = requests.get(AVIASALES_CHEAP_URL, params=params, timeout=15)
        data = response.json()
        
        if not data.get('success', False) or not data.get('data'):
            error_msg = "❌ Билеты не найдены. Попробуйте другие даты или направления."
            if hasattr(update, 'message'):
                await update.message.reply_text(error_msg)
            else:
                await update.edit_message_text(error_msg)
            return
        
        tickets = []
        for dest_data in data['data'].values():
            if isinstance(dest_data, dict):
                tickets.extend(dest_data.values())
        
        if not tickets:
            error_msg = "❌ Билеты не найдены для указанного направления."
            if hasattr(update, 'message'):
                await update.message.reply_text(error_msg)
            else:
                await update.edit_message_text(error_msg)
            return
        
        # Сохраняем параметры поиска для пользователя
        user_id = update.message.from_user.id if hasattr(update, 'message') else update.callback_query.from_user.id
        user_search_params[user_id] = params
        
        message = f"🎫 Билеты {params['origin']} → {params['destination']}:\n"
        
        if is_period:
            if 'depart_date' in params and 'return_date' in params:
                start_date = datetime.strptime(params['depart_date'], "%Y-%m-%d")
                end_date = datetime.strptime(params['return_date'], "%Y-%m-%d")
                message += f"📅 Период поиска: {start_date.strftime('%d.%m.%Y')}-{end_date.strftime('%d.%m.%Y')}\n"
        else:
            if 'depart_date' in params:
                depart_date = datetime.strptime(params['depart_date'], "%Y-%m-%d")
                message += f"🛫 Вылет: {depart_date.strftime('%d.%m.%Y')}\n"
            if 'return_date' in params:
                return_date = datetime.strptime(params['return_date'], "%Y-%m-%d")
                message += f"🛬 Возвращение: {return_date.strftime('%d.%m.%Y')}\n"
        
        message += "\n"
        
        for ticket in tickets[:5]:  # Ограничиваем 5 билетами
            if not isinstance(ticket, dict):
                continue
                
            airline_code = ticket.get('airline', '')
            airline_name = await get_airline_name(airline_code)
            
            flight_number = str(ticket.get('flight_number', ''))
            departure_at = format_date(ticket.get('departure_at', ''))
            return_at = format_date(ticket.get('return_at', '')) if ticket.get('return_at') else "не указана"
            price = ticket.get('price', '?')
            # flight_link = f"https://www.aviasales.ru/search/{params['origin']}{params['destination']}"
            
            aircraft_code = ticket.get('plane', '')
            aircraft_name = await get_aircraft_name(aircraft_code) if aircraft_code else "не указан"
            
            message += (
                f"✈️ Рейс: {airline_code}{flight_number}\n"
                f"🏛️ Авиакомпания: {airline_name}\n"
                f"🛩️ Тип ВС: {aircraft_name}\n"
                f"🛫 Вылет: {departure_at}\n"
                f"🛬 Возвращение: {return_at}\n"
                f"💰 Цена: {price} RUB\n"
                f"__точное предложение смотрите на официальном сайте авиакомпании__"
                # f"🔗 Подробнее: {flight_link}\n\n"
            )
        
        
        # Сохраняем параметры поиска для пользователя
        user_id = update.message.from_user.id if hasattr(update, 'message') else update.callback_query.from_user.id
        user_search_params[user_id] = params
        
        keyboard = [
            [InlineKeyboardButton("⭐ Добавить в избранное", callback_data='add_favorite')],
            [InlineKeyboardButton("← Назад", callback_data='back')]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        parse_mode='MarkdownV2'
        
        if hasattr(update, 'message'):
            await update.message.reply_text(message, reply_markup=reply_markup)
        else:
            await update.edit_message_text(message, reply_markup=reply_markup)
            
    except Exception as e:
        logger.error(f"Error in ticket search: {e}")
        error_msg = "❌ Произошла ошибка при поиске билетов. Попробуйте позже."
        if hasattr(update, 'message'):
            await update.message.reply_text(error_msg)
        else:
            await update.edit_message_text(error_msg)

async def handle_period_selection(query, user_id, period):
    """Обработка выбора периода"""
    try:
        params = user_search_params.get(user_id, {})
        if not params:
            await query.edit_message_text("❌ Ошибка: параметры поиска не найдены")
            return
        
        if period == 'none':
            # Поиск без периода
            params.update({
                'token': AVIASALES_API_TOKEN,
                'currency': 'rub'
            })
            # Удаляем даты если они есть
            params.pop('depart_date', None)
            params.pop('return_date', None)
            await perform_search(query, params, is_period=False)
            return
        
        days = int(period)
        today = datetime.now()
        end_date = today + timedelta(days=days)
        
        # Используем календарь цен для поиска всех комбинаций в периоде
        calendar_params = {
            'origin': params['origin'],
            'destination': params['destination'],
            'depart_date': today.strftime("%Y-%m"),
            'return_date': end_date.strftime("%Y-%m"),
            'calendar_type': 'departure_date',
            'token': AVIASALES_API_TOKEN,
            'currency': 'rub'
        }
        
        response = requests.get(AVIASALES_CALENDAR_URL, params=calendar_params, timeout=15)
        data = response.json()
        
        if not data.get('success', False) or not data.get('data'):
            await query.edit_message_text(
                "❌ Билеты не найдены в указанном периоде.",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("← Назад", callback_data='back')]])
            )
            return
        
        cheapest_ticket = None
        min_price = float('inf')
        
        for date_str, ticket_data in data['data'].items():
            if 'departure_at' in ticket_data and 'return_at' in ticket_data:
                try:
                    depart_date = datetime.strptime(ticket_data['departure_at'], "%Y-%m-%dT%H:%M:%S%z").date()
                    return_date = datetime.strptime(ticket_data['return_at'], "%Y-%m-%dT%H:%M:%S%z").date()
                    
                    # Проверяем что обе даты входят в период
                    if (today.date() <= depart_date <= end_date.date() and 
                        today.date() <= return_date <= end_date.date()):
                        
                        if ticket_data['price'] < min_price:
                            min_price = ticket_data['price']
                            cheapest_ticket = ticket_data
                except:
                    continue
        
        if not cheapest_ticket:
            await query.edit_message_text(
                "❌ Билеты с возвратом в указанный период не найдены.",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("← Назад", callback_data='back')]])
            )
            return
        
        # Обновляем user_search_params с датами из найденного билета
        user_search_params[user_id] = {
            'origin': params['origin'],
            'destination': params['destination'],
            'depart_date': cheapest_ticket['departure_at'][:10],  # Берем только дату YYYY-MM-DD
            'return_date': cheapest_ticket['return_at'][:10],     # Берем только дату YYYY-MM-DD
            'token': AVIASALES_API_TOKEN,
            'currency': 'rub'
        }
        
        # Формируем сообщение с результатом
        airline_name = await get_airline_name(cheapest_ticket['airline'])
        departure_at = format_date(cheapest_ticket['departure_at'])
        return_at = format_date(cheapest_ticket['return_at'])
        
        message = (
            f"🎫 Самый дешевый билет {params['origin']} → {params['destination']}:\n"
            f"📅 Период поиска: {today.strftime('%d.%m.%Y')}-{end_date.strftime('%d.%m.%Y')} ({days} дней)\n\n"
            f"✈️ Рейс: {cheapest_ticket['airline']}{cheapest_ticket['flight_number']}\n"
            f"🏛️ Авиакомпания: {airline_name}\n"
            f"🛫 Вылет: {departure_at}\n"
            f"🛬 Возвращение: {return_at}\n"
            f"💰 Цена: {cheapest_ticket['price']} RUB\n\n"
            f" *точное предложение смотрите на официальном сайте авиакомпании"
        )
        
        keyboard = [
            [InlineKeyboardButton("⭐ Добавить в избранное", callback_data='add_favorite')],
            [InlineKeyboardButton("← Назад", callback_data='back')]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            text=message,
            reply_markup=reply_markup
        )
        
    except Exception as e:
        logger.error(f"Error in period selection: {e}")
        await query.edit_message_text(
            "❌ Ошибка при обработке запроса. Попробуйте позже.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("← Назад", callback_data='back')]])
        )

async def handle_calendar(update: Update, text: str):
    """Обработка календаря цен"""
    try:
        parts = text.split()
        if len(parts) < 2:
            await update.message.reply_text("❌ Нужно указать город отправления и город назначения")
            return

        origin = await get_city_code(parts[0])
        destination = await get_city_code(parts[1])
        
        if not origin or not destination:
            await update.message.reply_text("❌ Не удалось распознать коды городов. Проверьте названия.")
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
        
        if not data.get('success', False) or not data.get('data'):
            await update.message.reply_text("❌ Билеты не найдены для указанного направления.")
            return
        
        # Формируем сообщение с минимальными ценами по дням
        message = f"📅 Календарь цен {origin} → {destination}:\n\n"
        prices = []
        
        for date_str, ticket_data in data['data'].items():
            if 'price' in ticket_data:
                date = datetime.strptime(date_str, "%Y-%m-%d")
                prices.append((date.strftime("%d.%m.%Y"), ticket_data['price']))
        
        # Сортируем по дате
        prices.sort(key=lambda x: datetime.strptime(x[0], "%d.%m.%Y"))
        
        for date, price in prices[:30]:  # Ограничиваем 30 записями
            message += f"{date}: {price} RUB\n"
        
        message += f"\n🔗 Подробнее: https://www.aviasales.ru/search/{origin}{destination}"
        
        keyboard = [[InlineKeyboardButton("← Назад", callback_data='back')]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(message, reply_markup=reply_markup)
        
    except Exception as e:
        logger.error(f"Error in calendar handler: {e}")
        await update.message.reply_text("❌ Произошла ошибка при обработке запроса. Попробуйте еще раз.")

async def handle_price_stats(update: Update, text: str):
    """Обработка статистики цен"""
    try:
        parts = text.split()
        if len(parts) < 2:
            await update.message.reply_text("❌ Нужно указать город отправления и город назначения")
            return

        origin = await get_city_code(parts[0])
        destination = await get_city_code(parts[1])
        
        if not origin or not destination:
            await update.message.reply_text("❌ Не удалось распознать коды городов. Проверьте названия.")
            return

        # Используем API календаря для получения статистики
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
        
        if not data.get('success', False) or not data.get('data'):
            await update.message.reply_text("❌ Данные по ценам не найдены для указанного направления.")
            return
        
        # Собираем все цены
        prices = [ticket['price'] for ticket in data['data'].values() if 'price' in ticket]
        
        if not prices:
            await update.message.reply_text("❌ Нет данных о ценах для анализа.")
            return
        
        min_price = min(prices)
        max_price = max(prices)
        avg_price = sum(prices) / len(prices)
        
        message = (
            f"📊 Статистика цен {origin} → {destination}:\n\n"
            f"🔹 Минимальная цена: {min_price} RUB\n"
            f"🔹 Максимальная цена: {max_price} RUB\n"
            f"🔹 Средняя цена: {int(avg_price)} RUB\n"
            f"🔹 Количество вариантов: {len(prices)}\n\n"
            # f"🔗 Подробнее: https://www.aviasales.ru/search/{origin}{destination}"
        )
        
        keyboard = [[InlineKeyboardButton("← Назад", callback_data='back')]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(message, reply_markup=reply_markup)
        
    except Exception as e:
        logger.error(f"Error in price stats handler: {e}")
        await update.message.reply_text("❌ Произошла ошибка при обработке запроса. Попробуйте еще раз.")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработчик текстовых сообщений"""
    user_id = update.message.from_user.id
    text = update.message.text.strip()
    
    # Обработка Reply-кнопок главного меню
    if text == "🔍 Дешевые билеты":
        user_states[user_id] = 'cheap'
        await update.message.reply_text(
            "🔍 Поиск дешевых билетов\n\n"
            "Введите маршрут в формате:\n"
            "<город отправления> <город назначения> [дата вылета ДД.ММ.ГГГГ] [дата возврата ДД.ММ.ГГГГ]\n\n"
            "Примеры:\n"
            "Москва Сочи\n"
            "Москва Сочи 01.08.2025\n"
            "Москва Сочи 01.08.2025 10.08.2025",
            reply_markup=ReplyKeyboardRemove()
        )
    elif text == "📅 Календарь цен":
        user_states[user_id] = 'calendar'
        await update.message.reply_text(
            "📅 Введите маршрут для календаря цен в формате: <город отправления> <город назначения>",
            reply_markup=ReplyKeyboardRemove()
        )
    elif text == "📊 Статистика цен":
        user_states[user_id] = 'stats'
        await update.message.reply_text(
            "📊 Введите маршрут для статистики цен в формате: <город отправления> <город назначения>",
            reply_markup=ReplyKeyboardRemove()
        )
    elif text == "⭐ Избранное":
        await FavoritesManager.show_favorites_menu(update, user_id)
    elif text == "✈️ Популярные рейсы":
        await show_airline_selection(update, context)
    elif text == "ℹ️ Инфо о рейсе":
        user_states[user_id] = 'flight_info'
        from flight_info import show_flight_info_menu
        await show_flight_info_menu(update, context)
    elif user_id in user_states:
        search_type = user_states[user_id]
        
        if search_type == 'cheap':
            await handle_cheap_tickets(update, text)
        elif search_type == 'calendar':
            await handle_price_calendar(update, text)
        elif search_type == 'stats':
            await handle_price_stats(update, text)
        elif search_type == 'flight_info':
            from flight_info import handle_flight_info_request
            await handle_flight_info_request(update, text)
    else:
        await show_main_menu(update)

def main():
    """Запуск бота"""
    app = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    logger.info("Bot is starting...")
    app.run_polling()

if __name__ == '__main__':
    main()