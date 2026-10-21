"""Настройка подключения к базе данных."""

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker


class Base(DeclarativeBase):
    """Базовый класс моделей SQLAlchemy."""


def create_database(database_url: str) -> tuple[Engine, sessionmaker]:
    """Создать движок и фабрику сессий для выбранной базы данных."""

    connect_args = {"check_same_thread": False} if database_url.startswith("sqlite") else {}
    engine = create_engine(database_url, pool_pre_ping=True, connect_args=connect_args)
    session_factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    return engine, session_factory
