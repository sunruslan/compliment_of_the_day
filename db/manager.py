"""Database manager for the compliment bot."""

import datetime
import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from setup import get_logger
from db.models import Base, Compliment, UserSettings
from db.migrations import migrate_add_missing_columns

logger = get_logger(__name__)


class DatabaseManager:
    """Manages database connections and operations."""

    def __init__(self):
        # Get DATABASE_URL from environment (Railway.com provides this)
        database_url = os.getenv("DATABASE_URL")

        if not database_url:
            raise ValueError(
                "DATABASE_URL environment variable is required. "
                "Please set it in your .env file or environment."
            )

        # Clean up the URL: strip whitespace and remove quotes if present
        database_url = database_url.strip().strip('"').strip("'")

        # Railway.com provides DATABASE_URL in format: postgresql://user:pass@host:port/dbname
        # SQLAlchemy expects postgresql:// (not postgres://) for psycopg2
        # Some providers use postgres://, so we normalize it
        if database_url.startswith("postgres://"):
            database_url = database_url.replace("postgres://", "postgresql://", 1)

        # Create synchronous engine
        self.engine = create_engine(database_url, pool_pre_ping=True)

        # Create sessionmaker with bind to engine
        self.SessionLocal = sessionmaker(
            autocommit=False, autoflush=False, bind=self.engine
        )

        # Initialize database tables
        Base.metadata.create_all(bind=self.engine)

        # Run migrations to add any missing columns from models
        migrate_add_missing_columns(self.engine)

    def add_compliment(
        self, compliment_content: str, date: datetime.date, language: str
    ) -> None:
        """Add a compliment for a specific date and language."""
        db = self.SessionLocal()
        try:
            db.add(Compliment(content=compliment_content, date=date, language=language))
            db.commit()
        except Exception as e:
            logger.error(f"Error adding compliment: {e}")
            db.rollback()
            raise
        finally:
            db.close()

    def get_compliment(self, date: datetime.date, language: str) -> str | None:
        """Get a compliment for a specific date and language."""
        db = self.SessionLocal()
        try:
            compliment = (
                db.query(Compliment)
                .filter(Compliment.date == date, Compliment.language == language)
                .first()
            )
            return compliment.content if compliment else None
        except Exception as e:
            logger.error(f"Error getting compliment: {e}")
            return None
        finally:
            db.close()

    def get_user_language(self, chat_id: int) -> str:
        """Get user's preferred language ('en' or 'ru'), default is 'en'."""
        db = self.SessionLocal()
        try:
            user_settings = (
                db.query(UserSettings).filter(UserSettings.chat_id == chat_id).first()
            )
            return (
                user_settings.language
                if user_settings and user_settings.language
                else "en"
            )
        except Exception as e:
            logger.error(f"Error getting user language: {e}")
            return "en"
        finally:
            db.close()

    def set_user_language(self, chat_id: int, language: str) -> None:
        """Set user's preferred language ('en' or 'ru')."""
        if language not in ("en", "ru"):
            raise ValueError(f"Language must be 'en' or 'ru', got {language}")
        db = self.SessionLocal()
        try:
            user_settings = (
                db.query(UserSettings).filter(UserSettings.chat_id == chat_id).first()
            )
            if user_settings:
                user_settings.language = language
            else:
                db.add(UserSettings(chat_id=chat_id, language=language))
            db.commit()
        except Exception as e:
            logger.error(f"Error setting user language: {e}")
            db.rollback()
            raise
        finally:
            db.close()

    def get_user_hour(self, chat_id: int) -> int | None:
        """Get user's preferred hour (0-23) in GMT or None if not set."""
        db = self.SessionLocal()
        try:
            user_settings = (
                db.query(UserSettings).filter(UserSettings.chat_id == chat_id).first()
            )
            return user_settings.hour if user_settings else None
        except Exception as e:
            logger.error(f"Error getting user hour: {e}")
            return None
        finally:
            db.close()

    def set_user_hour(self, chat_id: int, hour: int) -> None:
        """Set user's preferred hour (0-23) in GMT."""
        if not (0 <= hour <= 23):
            raise ValueError(f"Hour must be between 0 and 23, got {hour}")
        db = self.SessionLocal()
        try:
            user_settings = (
                db.query(UserSettings).filter(UserSettings.chat_id == chat_id).first()
            )
            if user_settings:
                user_settings.hour = hour
            else:
                db.add(UserSettings(chat_id=chat_id, hour=hour, language="en"))
            db.commit()
        except Exception as e:
            logger.error(f"Error setting user hour: {e}")
            db.rollback()
            raise
        finally:
            db.close()

    def set_user_activated(self, chat_id: int, activated: bool) -> None:
        """Set user's activated status."""
        db = self.SessionLocal()
        try:
            user_settings = (
                db.query(UserSettings).filter(UserSettings.chat_id == chat_id).first()
            )
            if user_settings:
                user_settings.activated = activated
            else:
                # If user doesn't exist, create with default values
                default_hour = 8
                db.add(
                    UserSettings(
                        chat_id=chat_id,
                        hour=default_hour,
                        language="en",
                        activated=activated,
                    )
                )
            db.commit()
        except Exception as e:
            logger.error(f"Error setting user activated status: {e}")
            db.rollback()
            raise
        finally:
            db.close()

    def get_activated_users(self) -> list[dict]:
        """Get all activated users with their settings.
        Returns a list of dictionaries with chat_id, hour, and language."""
        db = self.SessionLocal()
        try:
            users = db.query(UserSettings).filter(UserSettings.activated).all()
            return [
                {"chat_id": user.chat_id, "hour": user.hour, "language": user.language}
                for user in users
            ]
        except Exception as e:
            logger.error(f"Error getting activated users: {e}")
            return []
        finally:
            db.close()
