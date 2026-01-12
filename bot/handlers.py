"""Command handlers for the Telegram bot."""

from datetime import time, timedelta
from telegram import Update
from telegram.ext import ContextTypes
from setup import get_logger, get_config
from db import DatabaseManager
from translations import get_translation, format_translation
from bot.utils import remove_job_if_exists, validate_hour
from bot.jobs import send_compliment

logger = get_logger(__name__)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /start command."""
    chat_id = update.effective_chat.id

    # Remove existing jobs if any
    remove_job_if_exists(str(chat_id), context)

    # Get user's hour and language or use defaults
    db = DatabaseManager()
    hour = db.get_user_hour(chat_id)
    language = db.get_user_language(chat_id)

    # If user doesn't exist (hour is None), set defaults
    if hour is None:
        hour = get_config("telegram.jobs.default_hour", 8)
        # Save default hour and language for new user
        db.set_user_hour(chat_id, hour)
        # Ensure language is set (get_user_language returns "en" by default, but we should save it)
        if not language or language == "en":
            db.set_user_language(chat_id, "en")
        else:
            db.set_user_language(chat_id, language)

    # Set activated to True
    db.set_user_activated(chat_id, True)

    first = get_config("telegram.jobs.first_run_delay", 10)

    # Schedule first run
    context.job_queue.run_once(
        send_compliment,
        when=timedelta(seconds=first),
        chat_id=chat_id,
        name=str(chat_id),
    )

    # Schedule daily run at GMT time
    context.job_queue.run_daily(
        send_compliment,
        time=time(hour=hour, minute=0),
        chat_id=chat_id,
        name=str(chat_id),
    )

    await update.effective_message.reply_text(
        text=get_translation("messages.start", language)
    )


async def stop(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /stop command."""
    chat_id = update.effective_chat.id
    db = DatabaseManager()
    language = db.get_user_language(chat_id)
    job_removed = remove_job_if_exists(str(chat_id), context)
    # Set activated to False
    db.set_user_activated(chat_id, False)
    text = (
        get_translation("messages.stopping", language)
        if job_removed
        else get_translation("messages.not_running", language)
    )
    await update.effective_message.reply_text(text=text)


async def settime(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /settime command - Set the hour for receiving compliments (0-23 in GMT)."""
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
        # Activate user when they set a time (they want to receive compliments)
        db.set_user_activated(chat_id, True)
    except ValueError:
        await update.effective_message.reply_text(
            text=get_translation("messages.settime_invalid", language)
        )
        return

    # Remove existing jobs and reschedule with new time
    remove_job_if_exists(str(chat_id), context)

    # Schedule daily run at GMT time
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
    """Handle /setlanguage command - Set the language for messages and compliments."""
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
    """Handle /help command."""
    chat_id = update.effective_chat.id
    db = DatabaseManager()
    language = db.get_user_language(chat_id)
    await update.effective_message.reply_text(
        text=get_translation("messages.help", language)
    )
