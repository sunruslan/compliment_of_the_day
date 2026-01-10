"""Utility functions for the Telegram bot."""

from telegram.ext import ContextTypes


def job_exists(name: str, context: ContextTypes.DEFAULT_TYPE) -> bool:
    """Check if a job with the given name exists."""
    current_jobs = context.job_queue.get_jobs_by_name(name)
    return len(current_jobs) > 0


def remove_job_if_exists(name: str, context: ContextTypes.DEFAULT_TYPE) -> bool:
    """Remove job with given name. Returns whether job was removed."""
    current_jobs = context.job_queue.get_jobs_by_name(name)
    if not current_jobs:
        return False
    for job in current_jobs:
        job.schedule_removal()
    return True


def validate_hour(hour: int) -> bool:
    """Validate that hour is between 0 and 23."""
    return 0 <= hour <= 23
