"""Настройка подключения к базе данных."""

from sqlalchemy import create_engine, event, inspect, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker


class Base(DeclarativeBase):
    """Базовый класс моделей SQLAlchemy."""


def create_database(database_url: str) -> tuple[Engine, sessionmaker]:
    """Создать движок и фабрику сессий для выбранной базы данных."""

    connect_args = {"check_same_thread": False} if database_url.startswith("sqlite") else {}
    engine = create_engine(database_url, pool_pre_ping=True, connect_args=connect_args)
    if database_url.startswith("sqlite"):
        @event.listens_for(engine, "connect")
        def enable_foreign_keys(connection, _):
            """Соблюдать связи и в локальной SQLite-базе."""

            connection.execute("PRAGMA foreign_keys=ON")
    session_factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    return engine, session_factory


def initialize_database(engine: Engine) -> None:
    """Создать таблицы и сохранить совместимость с предыдущей схемой базы."""

    Base.metadata.create_all(bind=engine)
    columns = {column["name"] for column in inspect(engine).get_columns("automation_requests")}
    if "service_id" not in columns:
        with engine.begin() as connection:
            connection.execute(text(
                "ALTER TABLE automation_requests "
                "ADD COLUMN service_id INTEGER REFERENCES services(id)"
            ))
