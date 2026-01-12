"""Database models for the compliment bot."""

from sqlalchemy import Column, String, Date, BigInteger, Integer, Boolean
from sqlalchemy.orm import declarative_base

# Base class for the database models
Base = declarative_base()


class Compliment(Base):
    """Model for storing daily compliments."""

    __tablename__ = "compliments"

    date = Column(Date, primary_key=True)
    language = Column(String, primary_key=True)  # 'en' or 'ru'
    content = Column(String)


class UserSettings(Base):
    """Model for storing user preferences."""

    __tablename__ = "user_settings"

    chat_id = Column(BigInteger, primary_key=True)
    hour = Column(Integer, default=8)  # Hour in GMT (0-23)
    language = Column(String, default="en")  # Language code: 'en' or 'ru'
    activated = Column(Boolean, default=False)  # Whether user has activated the bot
