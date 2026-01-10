import datetime
import os
from sqlalchemy import (
    create_engine,
    Column,
    String,
    Date,
    BigInteger,
    Integer,
    text,
    inspect,
)
from sqlalchemy.orm import declarative_base, sessionmaker
from setup import get_logger

logger = get_logger(__name__)

# Base class for the database models
Base = declarative_base()


class Compliment(Base):
    __tablename__ = "compliments"

    date = Column(Date, primary_key=True)
    language = Column(String, primary_key=True)  # 'en' or 'ru'
    content = Column(String)


class UserSettings(Base):
    __tablename__ = "user_settings"

    chat_id = Column(BigInteger, primary_key=True)
    hour = Column(Integer, default=8)  # Hour in GMT (0-23)
    language = Column(String, default="en")  # Language code: 'en' or 'ru'


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

        # Run migrations to add any missing columns from models
        self._migrate_add_missing_columns()

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

    def _get_sqlalchemy_type_sql(self, column: Column) -> str:
        """Convert SQLAlchemy column type to PostgreSQL SQL type string."""
        col_type = column.type

        # Map SQLAlchemy types to PostgreSQL types
        if isinstance(col_type, String):
            length = col_type.length
            if length:
                return f"VARCHAR({length})"
            return "VARCHAR"
        elif isinstance(col_type, Integer):
            return "INTEGER"
        elif isinstance(col_type, BigInteger):
            return "BIGINT"
        elif isinstance(col_type, Date):
            return "DATE"
        else:
            # Fallback: use the type's compile method
            return str(col_type.compile(dialect=self.engine.dialect))

    def _get_column_default_sql(self, column: Column) -> str:
        """Get SQL default value for a column."""
        # Handle server defaults (preferred for database-level defaults)
        if hasattr(column, "server_default") and column.server_default is not None:
            default_arg = column.server_default.arg
            if isinstance(default_arg, str):
                # Remove quotes if already quoted
                default_arg = default_arg.strip("'\"")
                return f"DEFAULT '{default_arg}'"
            return f"DEFAULT {default_arg}"

        # Handle Python defaults (convert to SQL)
        if column.default is not None:
            if hasattr(column.default, "arg"):
                default_value = column.default.arg
                # Convert Python values to SQL
                if isinstance(default_value, str):
                    return f"DEFAULT '{default_value}'"
                elif isinstance(default_value, (int, float)):
                    return f"DEFAULT {default_value}"
                elif default_value is None:
                    return "DEFAULT NULL"

        return ""

    def _extract_default_value(self, column: Column):
        """Extract default value from column for use in UPDATE statements."""
        # Try server_default first
        if hasattr(column, "server_default") and column.server_default is not None:
            default_arg = column.server_default.arg
            if isinstance(default_arg, str):
                return default_arg.strip("'\"")
            return default_arg

        # Try Python default
        if column.default is not None and hasattr(column.default, "arg"):
            return column.default.arg

        return None

    def _migrate_add_missing_columns(self):
        """Add any missing columns from models to existing database tables."""
        try:
            inspector = inspect(self.engine)

            # Iterate through all tables in Base.metadata
            for table_name, table in Base.metadata.tables.items():
                if not inspector.has_table(table_name):
                    # Table doesn't exist, create_all will handle it
                    continue

                # Get existing columns in database
                db_columns = {
                    col["name"]: col for col in inspector.get_columns(table_name)
                }
                db_column_names = set(db_columns.keys())

                # Get model columns
                model_columns = {col.name: col for col in table.columns}
                model_column_names = set(model_columns.keys())

                # Find missing columns
                missing_columns = model_column_names - db_column_names

                if not missing_columns:
                    # Check if primary key needs updating
                    self._migrate_primary_key(table_name, table, inspector)
                    continue

                logger.info(
                    f"Found {len(missing_columns)} missing column(s) in {table_name}: {missing_columns}"
                )

                with self.engine.begin() as conn:
                    for col_name in missing_columns:
                        column = model_columns[col_name]
                        sql_type = self._get_sqlalchemy_type_sql(column)
                        default_sql = self._get_column_default_sql(column)

                        # Build ALTER TABLE statement
                        alter_sql = (
                            f"ALTER TABLE {table_name} ADD COLUMN {col_name} {sql_type}"
                        )
                        if default_sql:
                            alter_sql += f" {default_sql}"

                        logger.info(f"Adding column {col_name} to {table_name}")
                        conn.execute(text(alter_sql))

                        # If column has a default and is NOT NULL, update existing NULL rows
                        # (PostgreSQL will set default automatically, but we ensure consistency)
                        if default_sql and not column.nullable:
                            # Extract default value for UPDATE statement
                            default_value = self._extract_default_value(column)

                            if default_value is not None:
                                if isinstance(default_value, str):
                                    update_sql = f"UPDATE {table_name} SET {col_name} = '{default_value}' WHERE {col_name} IS NULL"
                                else:
                                    update_sql = f"UPDATE {table_name} SET {col_name} = {default_value} WHERE {col_name} IS NULL"
                                conn.execute(text(update_sql))

                    # After adding columns, ensure any new primary key columns have values
                    # (needed before we can add them to primary key constraint)
                    model_pk_columns = {
                        col.name for col in table.columns if col.primary_key
                    }
                    for pk_col_name in model_pk_columns:
                        if pk_col_name in missing_columns:
                            # This is a new primary key column, ensure it has values
                            pk_column = model_columns[pk_col_name]
                            if not pk_column.nullable:
                                default_value = self._extract_default_value(pk_column)
                                if default_value is not None:
                                    if isinstance(default_value, str):
                                        update_sql = f"UPDATE {table_name} SET {pk_col_name} = '{default_value}' WHERE {pk_col_name} IS NULL"
                                    else:
                                        update_sql = f"UPDATE {table_name} SET {pk_col_name} = {default_value} WHERE {pk_col_name} IS NULL"
                                    conn.execute(text(update_sql))

                    # After adding columns, check if primary key needs updating
                    self._migrate_primary_key(table_name, table, inspector, conn)

                logger.info(f"Successfully migrated {table_name} table")

        except Exception as e:
            logger.error(f"Error during migration: {e}", exc_info=True)
            # Don't raise - allow the application to continue
            # The migration will be retried on next startup if needed

    def _migrate_primary_key(self, table_name: str, table, inspector, conn=None):
        """Update primary key constraint if model definition differs from database."""
        try:
            pk_constraint = inspector.get_pk_constraint(table_name)
            db_pk_columns = (
                set(pk_constraint.get("constrained_columns", []))
                if pk_constraint
                else set()
            )

            # Get model primary key columns
            model_pk_columns = {col.name for col in table.columns if col.primary_key}

            # If primary keys match, no migration needed
            if db_pk_columns == model_pk_columns:
                return

            # Primary keys differ, need to update
            logger.info(
                f"Updating primary key for {table_name}: "
                f"database has {db_pk_columns}, model has {model_pk_columns}"
            )

            # Use provided connection or create new one
            if conn is None:
                with self.engine.begin() as conn:
                    self._update_primary_key(
                        table_name, db_pk_columns, model_pk_columns, pk_constraint, conn
                    )
            else:
                self._update_primary_key(
                    table_name, db_pk_columns, model_pk_columns, pk_constraint, conn
                )

        except Exception as e:
            logger.error(f"Error updating primary key for {table_name}: {e}")

    def _update_primary_key(
        self,
        table_name: str,
        db_pk_columns: set,
        model_pk_columns: set,
        pk_constraint,
        conn,
    ):
        """Helper method to update primary key constraint."""
        # Drop existing primary key if it exists
        if db_pk_columns:
            constraint_name = pk_constraint.get("name", f"{table_name}_pkey")
            conn.execute(
                text(
                    f"ALTER TABLE {table_name} DROP CONSTRAINT IF EXISTS {constraint_name}"
                )
            )

        # Add new primary key if model has primary key columns
        if model_pk_columns:
            pk_columns_str = ", ".join(sorted(model_pk_columns))
            conn.execute(
                text(f"ALTER TABLE {table_name} ADD PRIMARY KEY ({pk_columns_str})")
            )
            logger.info(f"Updated primary key for {table_name} to ({pk_columns_str})")

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
