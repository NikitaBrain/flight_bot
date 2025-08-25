from telegram.ext import ContextTypes
import logging
from favorites import FavoritesManager

logger = logging.getLogger(__name__)

async def daily_favorites_check(context: ContextTypes.DEFAULT_TYPE) -> None:
    """Ежедневная проверка избранных рейсов"""
    logger.info("Running daily favorites check...")
    try:
        await FavoritesManager.check_favorites_and_notify(context)
        logger.info("Daily favorites check completed successfully")
    except Exception as e:
        logger.error(f"Error in daily favorites check: {e}")