from logging.config import fileConfig
import os

from sqlalchemy import engine_from_config, pool
from alembic import context
from dotenv import load_dotenv

# -------------------------------------------------------------------
# Alembic Config
# -------------------------------------------------------------------
config = context.config

# Logging
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# -------------------------------------------------------------------
# Load .env and build DB URL (same style as your app/db/database.py)
# -------------------------------------------------------------------
load_dotenv()

DB_USER = os.getenv("user")
DB_PASSWORD = os.getenv("password")
DB_HOST = os.getenv("host")
DB_PORT = os.getenv("port")
DB_NAME = os.getenv("dbname")

if not all([DB_USER, DB_PASSWORD, DB_HOST, DB_PORT, DB_NAME]):
    missing = [k for k, v in {
        "user": DB_USER,
        "password": DB_PASSWORD,
        "host": DB_HOST,
        "port": DB_PORT,
        "dbname": DB_NAME,
    }.items() if not v]
    raise RuntimeError(f"Missing DB env vars in .env: {missing}")

DATABASE_URL = (
    f"postgresql+psycopg2://{DB_USER}:{DB_PASSWORD}"
    f"@{DB_HOST}:{DB_PORT}/{DB_NAME}?sslmode=require"
)

# Tell Alembic to use this URL (overrides alembic.ini)
config.set_main_option("sqlalchemy.url", DATABASE_URL)

# -------------------------------------------------------------------
# Import Base + import models so Base.metadata has tables
# -------------------------------------------------------------------
from app.db.database import Base  # <-- your Base

# IMPORTANT: import ALL model modules here (so autogenerate detects them)
from app.models import (
    student_models,
    teacher_models,
    cr_models,
    chat_room_models,
    message_models,
    # add other model files you have, e.g.:
    class_note_models,
    notice_models,
    ct_question_models,
    lecture_slide_models,
    result_sheet_models,
    result_entry_models,
    semester_question_models,
)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode."""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,  # helps detect column type changes
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode."""
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,  # helps detect column type changes
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
