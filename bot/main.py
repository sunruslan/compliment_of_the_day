"""Main entry point for the Telegram bot."""

import os
from datetime import time, timedelta
from telegram.ext import ApplicationBuilder, CommandHandler, Defaults
from setup import setup_application, get_logger, get_config
from bot.handlers import start, stop, help, settime, setlanguage
from bot.jobs import generate_compliment, send_compliment, GMT
from db import DatabaseManager

logger = get_logger(__name__)


def main():
    """Initialize and run the Telegram bot."""
    setup_application()

    # Set timezone defaults for the application (GMT/UTC)
    defaults = Defaults(tzinfo=GMT)
    application = (
        ApplicationBuilder().token(os.getenv("TG_BOT_TOKEN")).defaults(defaults).build()
    )

    # Register command handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("stop", stop))
    application.add_handler(CommandHandler("help", help))
    application.add_handler(CommandHandler("settime", settime))
    application.add_handler(CommandHandler("setlanguage", setlanguage))

    # Schedule compliment generation for both languages at GMT time
    generate_hour = get_config("telegram.jobs.generate_hour", 0)
    generate_minute = get_config("telegram.jobs.generate_minute", 0)
    first_delay = get_config("telegram.jobs.first_run_delay", 10)

    # Create wrapper functions for each language
    async def generate_en(context):
        await generate_compliment(context, "en")

    async def generate_ru(context):
        await generate_compliment(context, "ru")

    # Schedule initial generation for English
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

    # Schedule initial generation for Russian
    # Use longer delay to ensure English job completes first (generation takes ~5-10 seconds)
    application.job_queue.run_once(
        generate_ru,
        when=timedelta(seconds=first_delay + 15),  # Longer delay to avoid conflicts
        name="generate_compliment_ru_init",
    )
    # Schedule daily generation for Russian
    application.job_queue.run_daily(
        generate_ru,
        time=time(hour=generate_hour, minute=generate_minute),
        name="generate_compliment_ru",
    )

    # Schedule jobs for all activated users on startup
    db = DatabaseManager()
    activated_users = db.get_activated_users()
    logger.info(f"Found {len(activated_users)} activated user(s), scheduling jobs...")

    for user in activated_users:
        chat_id = user["chat_id"]
        hour = user["hour"]
        # Schedule daily run at GMT time for each activated user
        application.job_queue.run_daily(
            send_compliment,
            time=time(hour=hour, minute=0),
            chat_id=chat_id,
            name=str(chat_id),
        )
        logger.info(f"Scheduled job for user {chat_id} at {hour:02d}:00 GMT")

    application.run_polling()


if __name__ == "__main__":
    main()
