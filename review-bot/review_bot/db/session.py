from __future__ import annotations

from collections.abc import Generator
from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, text
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from review_bot.config import get_settings


class Base(DeclarativeBase):
    pass


settings = get_settings()
connect_args: dict[str, object]
if settings.database_url.startswith("sqlite"):
    connect_args = {"check_same_thread": False}
elif settings.database_url.startswith("postgresql+psycopg"):
    connect_args = {"prepare_threshold": None}
else:
    connect_args = {}
engine = create_engine(settings.database_url, future=True, connect_args=connect_args)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)


def get_session() -> Generator[Session, None, None]:
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


def init_db() -> None:
    config = Config(str(_alembic_ini_path()))
    config.set_main_option("script_location", str(settings.project_root / "alembic"))
    config.set_main_option("sqlalchemy.url", settings.database_url)
    with engine.begin() as connection:
        if connection.dialect.name == "postgresql":
            connection.execute(text("SELECT pg_advisory_xact_lock(914241)"))
        config.attributes["connection"] = connection
        command.upgrade(config, "head")


def _alembic_ini_path() -> Path:
    return settings.project_root / "alembic.ini"
