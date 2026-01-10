import os
from datetime import time, datetime, timedelta, timezone

from telegram import Update
from telegram.ext import ApplicationBuilder, ContextTypes, CommandHandler, Defaults
from compliment import ComplimentGenerator
from setup import get_logger, get_config
from database import DatabaseManager
from news import FreshHeadlinesRetriever
from translations import get_translation, format_translation

logger = get_logger(__name__)

# GMT timezone
GMT = timezone.utc


async def send_compliment(context: ContextTypes.DEFAULT_TYPE):
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


def job_exists(name: str, context: ContextTypes.DEFAULT_TYPE) -> bool:
    current_jobs = context.job_queue.get_jobs_by_name(name)
    return len(current_jobs) > 0


def validate_hour(hour: int) -> bool:
    """Validate that hour is between 0 and 23."""
    return 0 <= hour <= 23


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id

    # Remove existing jobs if any
    remove_job_if_exists(str(chat_id), context)

    # Get user's hour and language or use defaults
    db = DatabaseManager()
    hour = db.get_user_hour(chat_id)
    language = db.get_user_language(chat_id)

    # If user doesn't exist, set defaults
    if hour is None:
        hour = get_config("telegram.jobs.default_hour", 8)
        # Save default hour and language for new user
        db.set_user_hour(chat_id, hour)
        if language == "en":  # Only set if not already set
            db.set_user_language(chat_id, "en")

    first = get_config("telegram.jobs.first_run_delay", 10)

    # Schedule first run
    context.job_queue.run_once(
        send_compliment,
        when=timedelta(seconds=first),
        chat_id=chat_id,
        name=str(chat_id),
    )

    # Schedule daily run at GMT time (system timezone should be UTC/GMT)
    context.job_queue.run_daily(
        send_compliment,
        time=time(hour=hour, minute=0),
        chat_id=chat_id,
        name=str(chat_id),
    )

    await update.effective_message.reply_text(
        text=get_translation("messages.start", language)
    )


def remove_job_if_exists(name: str, context: ContextTypes.DEFAULT_TYPE) -> bool:
    """Remove job with given name. Returns whether job was removed."""
    current_jobs = context.job_queue.get_jobs_by_name(name)
    if not current_jobs:
        return False
    for job in current_jobs:
        job.schedule_removal()
    return True


async def stop(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    db = DatabaseManager()
    language = db.get_user_language(chat_id)
    job_removed = remove_job_if_exists(str(chat_id), context)
    text = (
        get_translation("messages.stopping", language)
        if job_removed
        else get_translation("messages.not_running", language)
    )
    await update.effective_message.reply_text(text=text)


async def settime(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Set the hour for receiving compliments (0-23 in GMT)."""
    chat_id = update.effective_chat.id
    db = DatabaseManager()
    language = db.get_user_language(chat_id)

    if not context.args or len(context.args) == 0:
        await update.effective_message.reply_text(
            text=get_translation("messages.settime_usage", language)
        )
        return

    try:
        hour = int(context.args[0])
    except ValueError:
        await update.effective_message.reply_text(
            text=get_translation("messages.settime_invalid", language)
        )
        return

    if not validate_hour(hour):
        await update.effective_message.reply_text(
            text=get_translation("messages.settime_invalid", language)
        )
        return

    # Update user hour
    try:
        db.set_user_hour(chat_id, hour)
    except ValueError:
        await update.effective_message.reply_text(
            text=get_translation("messages.settime_invalid", language)
        )
        return

    # Remove existing jobs and reschedule with new time
    remove_job_if_exists(str(chat_id), context)

    # Schedule daily run at GMT time (system timezone should be UTC/GMT)
    context.job_queue.run_daily(
        send_compliment,
        time=time(hour=hour, minute=0),
        chat_id=chat_id,
        name=str(chat_id),
    )

    # Format hour for display
    hour_display = f"{hour:02d}:00"
    period = "AM" if hour < 12 else "PM"
    hour_12 = hour if hour <= 12 else hour - 12
    if hour == 0:
        hour_12 = 12
    display_time = f"{hour_12}:00 {period}"

    await update.effective_message.reply_text(
        text=format_translation(
            "messages.settime_success",
            language,
            hour_display=hour_display,
            display_time=display_time,
        )
    )


async def setlanguage(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Set the language for messages and compliments."""
    chat_id = update.effective_chat.id
    db = DatabaseManager()
    # Get current language for error messages
    current_language = db.get_user_language(chat_id)

    if not context.args or len(context.args) == 0:
        await update.effective_message.reply_text(
            text=get_translation("messages.setlanguage_usage", current_language)
        )
        return

    language_arg = context.args[0].lower()

    if language_arg not in ("en", "ru"):
        await update.effective_message.reply_text(
            text=get_translation("messages.setlanguage_invalid", current_language)
        )
        return

    # Update user language
    try:
        db.set_user_language(chat_id, language_arg)
        language_name = get_translation(f"language_names.{language_arg}", language_arg)
        await update.effective_message.reply_text(
            text=format_translation(
                "messages.setlanguage_success",
                language_arg,
                language_name=language_name,
            )
        )
    except ValueError:
        await update.effective_message.reply_text(
            text=get_translation("messages.setlanguage_invalid", current_language)
        )


async def help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    db = DatabaseManager()
    language = db.get_user_language(chat_id)
    await update.effective_message.reply_text(
        text=get_translation("messages.help", language)
    )


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


def main():
    from setup import setup_application

    setup_application()

    # Set timezone defaults for the application (GMT/UTC)
    defaults = Defaults(tzinfo=GMT)
    application = (
        ApplicationBuilder().token(os.getenv("TG_BOT_TOKEN")).defaults(defaults).build()
    )

    start_handler = CommandHandler("start", start)
    stop_handler = CommandHandler("stop", stop)
    help_handler = CommandHandler("help", help)
    settime_handler = CommandHandler("settime", settime)
    setlanguage_handler = CommandHandler("setlanguage", setlanguage)
    application.add_handler(start_handler)
    application.add_handler(stop_handler)
    application.add_handler(help_handler)
    application.add_handler(settime_handler)
    application.add_handler(setlanguage_handler)

    # Schedule compliment generation for both languages at GMT time
    generate_hour = get_config("telegram.jobs.generate_hour", 0)
    generate_minute = get_config("telegram.jobs.generate_minute", 0)
    first_delay = get_config("telegram.jobs.first_run_delay", 10)

    # Create wrapper functions for each language
    async def generate_en(context: ContextTypes.DEFAULT_TYPE):
        await generate_compliment(context, "en")

    async def generate_ru(context: ContextTypes.DEFAULT_TYPE):
        await generate_compliment(context, "ru")

    # Schedule initial generation for English (use different name to avoid conflicts)
    application.job_queue.run_once(
        generate_en,
        when=timedelta(seconds=first_delay),
        name="generate_compliment_en_init",
    )
    # Schedule daily generation for English
    application.job_queue.run_daily(
        generate_en,
        time=time(hour=generate_hour, minute=generate_minute),
        name="generate_compliment_en",
    )

    # Schedule initial generation for Russian (use different name to avoid conflicts)
    application.job_queue.run_once(
        generate_ru,
        when=timedelta(seconds=first_delay + 2),  # Small delay to avoid conflicts
        name="generate_compliment_ru_init",
    )
    # Schedule daily generation for Russian
    application.job_queue.run_daily(
        generate_ru,
        time=time(hour=generate_hour, minute=generate_minute),
        name="generate_compliment_ru",
    )

    application.run_polling()


if __name__ == "__main__":
    main()
