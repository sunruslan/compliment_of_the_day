"""Job functions for scheduled tasks."""

from datetime import datetime, timezone
from telegram.ext import ContextTypes
from setup import get_logger
from db import DatabaseManager
from translations import get_translation
from compliment import ComplimentGenerator
from news import FreshHeadlinesRetriever

logger = get_logger(__name__)

# GMT timezone
GMT = timezone.utc


async def send_compliment(context: ContextTypes.DEFAULT_TYPE):
    """Send daily compliment to user."""
    try:
        db = DatabaseManager()
        chat_id = context.job.chat_id
        # Get user's language
        language = db.get_user_language(chat_id)
        # Use GMT date
        current_date = datetime.now(GMT).date()
        compliment = db.get_compliment(current_date, language)
        if not compliment:
            compliment = get_translation("messages.fallback_compliment", language)
    except Exception as e:
        logger.error(f"Error getting compliment: {e}")
        language = "en"
        compliment = get_translation("messages.fallback_compliment", language)

    await context.bot.send_message(chat_id=chat_id, text=compliment)


async def generate_compliment(context: ContextTypes.DEFAULT_TYPE, language: str = "en"):
    """Generate compliment for a specific language."""
    try:
        db = DatabaseManager()
        # Use GMT date
        current_date = datetime.now(GMT).date()

        # Check if compliment already exists for today and language
        existing_compliment = db.get_compliment(current_date, language)
        if existing_compliment:
            logger.info(
                f"Compliment already exists for {current_date} ({language}), reusing existing one"
            )
            return

        # Generate new compliment if it doesn't exist
        generator = ComplimentGenerator(FreshHeadlinesRetriever(), language=language)
        compliment = generator.generate_compliment_for_date()
        if compliment:
            db.add_compliment(compliment, current_date, language)
            logger.info(
                f"Generated {language} compliment for {current_date}: {compliment}"
            )
        else:
            logger.warning(
                f"Failed to generate {language} compliment for {current_date}"
            )
    except Exception as e:
        logger.error(f"Error generating {language} compliment: {e}")
