import datetime
from sqlalchemy import create_engine, Column, String, Date
from sqlalchemy.orm import declarative_base, Session
from setup import get_logger, get_config

logger = get_logger(__name__)
Base = declarative_base()


class Compliment(Base):
    __tablename__ = "compliments"

    date = Column(Date, primary_key=True)
    content = Column(String)


class DatabaseManager:
    def __init__(self):
        database_name = get_config("database.name", "compliment.db")
        database_type = get_config("database.type", "sqlite")
        self.engine = create_engine(f"{database_type}:///{database_name}")
        Base.metadata.create_all(self.engine)

    def add_compliment(self, compliment_content: str, date: datetime.date) -> None:
        try:
            with Session(self.engine) as session:
                session.add(Compliment(content=compliment_content, date=date))
                session.commit()
        except Exception as e:
            logger.error(f"Error adding compliment: {e}")

    def get_compliment(self, date: datetime.date) -> str | None:
        compliment = None
        try:
            with Session(self.engine) as session:
                compliment = (
                    session.query(Compliment).filter(Compliment.date == date).first()
                )
                return compliment.content if compliment else None
        except Exception as e:
            logger.error(f"Error getting compliment: {e}")
            return None
