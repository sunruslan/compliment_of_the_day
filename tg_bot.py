import os
from datetime import time, datetime, timedelta, timezone

from telegram import Update
from telegram.ext import ApplicationBuilder, ContextTypes, CommandHandler, Defaults
from compliment import ComplimentGenerator
from setup import get_logger, get_config
from database import DatabaseManager
from news import FreshHeadlinesRetriever

logger = get_logger(__name__)

# GMT timezone
GMT = timezone.utc


async def send_compliment(context: ContextTypes.DEFAULT_TYPE):
    try:
        db = DatabaseManager()
        # Use GMT date
        compliment = db.get_compliment(datetime.now(GMT).date())
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


def validate_hour(hour: int) -> bool:
    """Validate that hour is between 0 and 23."""
    return 0 <= hour <= 23


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id

    # Remove existing jobs if any
    remove_job_if_exists(str(chat_id), context)

    # Get user's hour or use default
    db = DatabaseManager()
    hour = db.get_user_hour(chat_id)
    if hour is None:
        hour = get_config("telegram.jobs.default_hour", 8)
        # Save default hour for user
        db.set_user_hour(chat_id, hour)

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


async def settime(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Set the hour for receiving compliments (0-23 in GMT)."""
    chat_id = update.effective_chat.id

    if not context.args or len(context.args) == 0:
        await update.effective_message.reply_text(
            text=get_config(
                "telegram.messages.settime_usage",
                "Please specify an hour (0-23) in GMT: /settime <hour>\n"
                "Example: /settime 8 (for 8:00 AM GMT)",
            )
        )
        return

    try:
        hour = int(context.args[0])
    except ValueError:
        await update.effective_message.reply_text(
            text=get_config(
                "telegram.messages.settime_invalid",
                "Invalid hour. Please provide a number between 0 and 23.\n"
                "Example: /settime 8 (for 8:00 AM GMT)",
            )
        )
        return

    if not validate_hour(hour):
        await update.effective_message.reply_text(
            text=get_config(
                "telegram.messages.settime_invalid",
                f"Invalid hour: {hour}. Please provide a number between 0 and 23.\n"
                "Example: /settime 8 (for 8:00 AM GMT)",
            )
        )
        return

    # Update user hour
    db = DatabaseManager()
    try:
        db.set_user_hour(chat_id, hour)
    except ValueError as e:
        await update.effective_message.reply_text(
            text=get_config("telegram.messages.settime_invalid", str(e))
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
        text=get_config(
            "telegram.messages.settime_success",
            f"Time set to {hour_display} GMT ({display_time} GMT)! "
            f"Your compliment will be sent daily at this time.",
        )
    )


async def help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.effective_message.reply_text(
        text=get_config(
            "telegram.messages.help",
            "I'm a compliment bot! I will make your day every day by giving you a random compliment based on news!\n\n"
            "Commands:\n"
            "/start - Start receiving compliments\n"
            "/stop - Stop the bot\n"
            "/settime <hour> - Set when to receive compliments (0-23 in GMT)\n"
            "  Example: /settime 8 (for 8:00 AM GMT)\n"
            "/help - Show this help message",
        )
    )


async def generate_compliment(context: ContextTypes.DEFAULT_TYPE):
    try:
        db = DatabaseManager()
        # Use GMT date
        current_date = datetime.now(GMT).date()

        # Check if compliment already exists for today
        existing_compliment = db.get_compliment(current_date)
        if existing_compliment:
            logger.info(
                f"Compliment already exists for {current_date}, reusing existing one"
            )
            return

        # Generate new compliment if it doesn't exist
        generator = ComplimentGenerator(FreshHeadlinesRetriever())
        compliment = generator.generate_compliment_for_date()
        if compliment:
            db.add_compliment(compliment, current_date)
            logger.info(f"Generated compliment for {current_date}: {compliment}")
        else:
            logger.warning(f"Failed to generate compliment for {current_date}")
    except Exception as e:
        logger.error(f"Error generating compliment: {e}")


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
    application.add_handler(start_handler)
    application.add_handler(stop_handler)
    application.add_handler(help_handler)
    application.add_handler(settime_handler)

    # Schedule compliment generation at GMT time
    application.job_queue.run_once(
        generate_compliment,
        when=timedelta(seconds=get_config("telegram.jobs.first_run_delay", 10)),
    )
    generate_hour = get_config("telegram.jobs.generate_hour", 0)
    generate_minute = get_config("telegram.jobs.generate_minute", 0)
    # Schedule compliment generation at GMT time (system timezone should be UTC/GMT)
    application.job_queue.run_daily(
        generate_compliment,
        time=time(hour=generate_hour, minute=generate_minute),
    )

    application.run_polling()


if __name__ == "__main__":
    main()
