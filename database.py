import datetime
import os
from sqlalchemy import create_engine, Column, String, Date
from sqlalchemy.orm import declarative_base, sessionmaker
from setup import get_logger

logger = get_logger(__name__)

# Base class for the database models
Base = declarative_base()


class Compliment(Base):
    __tablename__ = "compliments"

    date = Column(Date, primary_key=True)
    content = Column(String)


class DatabaseManager:
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

    def add_compliment(self, compliment_content: str, date: datetime.date) -> None:
        db = self.SessionLocal()
        try:
            db.add(Compliment(content=compliment_content, date=date))
            db.commit()
        except Exception as e:
            logger.error(f"Error adding compliment: {e}")
            db.rollback()
            raise
        finally:
            db.close()

    def get_compliment(self, date: datetime.date) -> str | None:
        db = self.SessionLocal()
        try:
            compliment = db.query(Compliment).filter(Compliment.date == date).first()
            return compliment.content if compliment else None
        except Exception as e:
            logger.error(f"Error getting compliment: {e}")
            return None
        finally:
            db.close()
