import os
from datetime import time, datetime, timedelta

from telegram import Update
from telegram.ext import ApplicationBuilder, ContextTypes, CommandHandler
from compliment import ComplimentGenerator
from setup import get_logger, get_config
from database import DatabaseManager
from news import FreshHeadlinesRetriever

logger = get_logger(__name__)


async def send_compliment(context: ContextTypes.DEFAULT_TYPE):
    try:
        db = DatabaseManager()
        compliment = db.get_compliment(datetime.now().date())
        if not compliment:
            compliment = get_config(
                "telegram.messages.fallback_compliment", "You're very pretty kitty!"
            )
    except Exception as e:
        logger.error(f"Error getting compliment: {e}")
        compliment = get_config(
            "telegram.messages.fallback_compliment", "You're very pretty kitty!"
        )

    await context.bot.send_message(chat_id=context.job.chat_id, text=compliment)


def job_exists(name: str, context: ContextTypes.DEFAULT_TYPE) -> bool:
    current_jobs = context.job_queue.get_jobs_by_name(name)
    return len(current_jobs) > 0


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    if job_exists(str(chat_id), context):
        await update.effective_message.reply_text(
            text=get_config(
                "telegram.messages.already_running", "Bot is already running!"
            )
        )
        return

    compliment_hour = get_config("telegram.jobs.compliment_hour", 9)
    compliment_minute = get_config("telegram.jobs.compliment_minute", 0)
    first = get_config("telegram.jobs.first_run_delay", 10)

    context.job_queue.run_once(
        send_compliment,
        when=timedelta(seconds=first),
        chat_id=chat_id,
        name=str(chat_id),
    )
    context.job_queue.run_daily(
        send_compliment,
        time=time(hour=compliment_hour, minute=compliment_minute),
        chat_id=chat_id,
        name=str(chat_id),
    )
    await update.effective_message.reply_text(
        text=get_config(
            "telegram.messages.start",
            "I'm a compliment bot! I will make your day every day by giving you a random compliment based on news!",
        )
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
    job_removed = remove_job_if_exists(str(chat_id), context)
    text = (
        get_config("telegram.messages.stopping", "Stopping the bot!")
        if job_removed
        else get_config("telegram.messages.not_running", "Bot was not running.")
    )
    await update.effective_message.reply_text(text=text)


async def help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.effective_message.reply_text(
        text=get_config(
            "telegram.messages.help",
            "I'm a compliment bot! I will make your day every day by giving you a random compliment based on news! Please use /start to start the bot and /stop to stop the bot.",
        )
    )


async def generate_compliment(context: ContextTypes.DEFAULT_TYPE):
    try:
        db = DatabaseManager()
        generator = ComplimentGenerator(FreshHeadlinesRetriever())
        compliment = generator.generate_compliment_for_date(datetime.now().date())
        if compliment:
            db.add_compliment(compliment, datetime.now().date())
            logger.info(
                f"Generated compliment for {datetime.now().date()}: {compliment}"
            )
        else:
            logger.warning(f"Failed to generate compliment for {datetime.now().date()}")
    except Exception as e:
        logger.error(f"Error generating compliment: {e}")


def main():
    from setup import setup_application

    setup_application()
    application = ApplicationBuilder().token(os.getenv("TG_BOT_TOKEN")).build()

    start_handler = CommandHandler("start", start)
    stop_handler = CommandHandler("stop", stop)
    help_handler = CommandHandler("help", help)
    application.add_handler(start_handler)
    application.add_handler(stop_handler)
    application.add_handler(help_handler)

    # Schedule compliment generation
    application.job_queue.run_once(
        generate_compliment,
        when=timedelta(seconds=get_config("telegram.jobs.first_run_delay", 10)),
    )
    generate_hour = get_config("telegram.jobs.generate_hour", 0)
    generate_minute = get_config("telegram.jobs.generate_minute", 0)
    application.job_queue.run_daily(
        generate_compliment, time=time(hour=generate_hour, minute=generate_minute)
    )

    application.run_polling()


if __name__ == "__main__":
    main()
