from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters
from flight_ticket import start, handle_message, button_handler
from jobs import daily_favorites_check
from config import TELEGRAM_BOT_TOKEN
from datetime import time

def main():
    app = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
    
    # Добавляем обработчики
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    # Добавляем задачу для ежедневной проверки избранного
    job_queue = app.job_queue
    if job_queue:
        # Запускать каждый день в 10:00 утра
        job_queue.run_daily(daily_favorites_check, time=time(hour=7, minute=0))
    
    print("Бот запущен...")
    app.run_polling()

if __name__ == '__main__':
    main()