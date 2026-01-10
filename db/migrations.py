"""Database migration utilities."""

from sqlalchemy import Column, String, Integer, BigInteger, Date, text, inspect
from setup import get_logger
from db.models import Base

logger = get_logger(__name__)


def get_sqlalchemy_type_sql(column: Column, engine) -> str:
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
        return str(col_type.compile(dialect=engine.dialect))


def get_column_default_sql(column: Column) -> str:
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


def extract_default_value(column: Column):
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


def migrate_add_missing_columns(engine):
    """Add any missing columns from models to existing database tables."""
    try:
        inspector = inspect(engine)

        # Iterate through all tables in Base.metadata
        for table_name, table in Base.metadata.tables.items():
            if not inspector.has_table(table_name):
                # Table doesn't exist, create_all will handle it
                continue

            # Get existing columns in database
            db_columns = {col["name"]: col for col in inspector.get_columns(table_name)}
            db_column_names = set(db_columns.keys())

            # Get model columns
            model_columns = {col.name: col for col in table.columns}
            model_column_names = set(model_columns.keys())

            # Find missing columns
            missing_columns = model_column_names - db_column_names

            if not missing_columns:
                # Check if primary key needs updating
                migrate_primary_key(engine, table_name, table, inspector)
                continue

            logger.info(
                f"Found {len(missing_columns)} missing column(s) in {table_name}: {missing_columns}"
            )

            with engine.begin() as conn:
                for col_name in missing_columns:
                    column = model_columns[col_name]
                    sql_type = get_sqlalchemy_type_sql(column, engine)
                    default_sql = get_column_default_sql(column)

                    # Build ALTER TABLE statement
                    alter_sql = (
                        f"ALTER TABLE {table_name} ADD COLUMN {col_name} {sql_type}"
                    )
                    if default_sql:
                        alter_sql += f" {default_sql}"

                    logger.info(f"Adding column {col_name} to {table_name}")
                    conn.execute(text(alter_sql))

                    # If column has a default and is NOT NULL, update existing NULL rows
                    if default_sql and not column.nullable:
                        default_value = extract_default_value(column)

                        if default_value is not None:
                            if isinstance(default_value, str):
                                update_sql = f"UPDATE {table_name} SET {col_name} = '{default_value}' WHERE {col_name} IS NULL"
                            else:
                                update_sql = f"UPDATE {table_name} SET {col_name} = {default_value} WHERE {col_name} IS NULL"
                            conn.execute(text(update_sql))

                # After adding columns, ensure any new primary key columns have values
                model_pk_columns = {
                    col.name for col in table.columns if col.primary_key
                }
                for pk_col_name in model_pk_columns:
                    if pk_col_name in missing_columns:
                        pk_column = model_columns[pk_col_name]
                        if not pk_column.nullable:
                            default_value = extract_default_value(pk_column)
                            if default_value is not None:
                                if isinstance(default_value, str):
                                    update_sql = f"UPDATE {table_name} SET {pk_col_name} = '{default_value}' WHERE {pk_col_name} IS NULL"
                                else:
                                    update_sql = f"UPDATE {table_name} SET {pk_col_name} = {default_value} WHERE {pk_col_name} IS NULL"
                                conn.execute(text(update_sql))

                # After adding columns, check if primary key needs updating
                migrate_primary_key(engine, table_name, table, inspector, conn)

            logger.info(f"Successfully migrated {table_name} table")

    except Exception as e:
        logger.error(f"Error during migration: {e}", exc_info=True)


def migrate_primary_key(engine, table_name: str, table, inspector, conn=None):
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
            with engine.begin() as conn:
                update_primary_key(
                    table_name, db_pk_columns, model_pk_columns, pk_constraint, conn
                )
        else:
            update_primary_key(
                table_name, db_pk_columns, model_pk_columns, pk_constraint, conn
            )

    except Exception as e:
        logger.error(f"Error updating primary key for {table_name}: {e}")


def update_primary_key(
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
