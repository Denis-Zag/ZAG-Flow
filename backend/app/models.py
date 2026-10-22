"""Модели хранения заявок."""

from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import (
    JSON, Boolean, CheckConstraint, DateTime, ForeignKey, Integer, String,
    Text, UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from .database import Base


class Service(Base):
    """Доступная услуга с ориентировочным диапазоном бюджета в рублях."""

    __tablename__ = "services"
    __table_args__ = (
        CheckConstraint("budget_min >= 0 AND budget_max >= budget_min"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(80), nullable=False, unique=True)
    budget_min: Mapped[int] = mapped_column(Integer, nullable=False)
    budget_max: Mapped[int] = mapped_column(Integer, nullable=False)


class AutomationRequest(Base):
    """Заявка посетителя на разбор задачи автоматизации."""

    __tablename__ = "automation_requests"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )
    status: Mapped[str] = mapped_column(String(32), default="new", nullable=False)
    # В записях предыдущей версии связь с каталогом может отсутствовать.
    service_id: Mapped[int | None] = mapped_column(ForeignKey("services.id"))

    task_type: Mapped[str] = mapped_column(String(80), nullable=False)
    task_description: Mapped[str] = mapped_column(Text, nullable=False)
    business_name: Mapped[str | None] = mapped_column(String(120))
    business_niche: Mapped[str] = mapped_column(String(120), nullable=False)
    expected_result: Mapped[str] = mapped_column(Text, nullable=False)
    budget: Mapped[str] = mapped_column(String(80), nullable=False)
    deadline: Mapped[str | None] = mapped_column(String(100))

    contact_name: Mapped[str] = mapped_column(String(100), nullable=False)
    contact_email: Mapped[str] = mapped_column(String(254), nullable=False)
    contact_phone: Mapped[str | None] = mapped_column(String(100))
    contact_method: Mapped[str] = mapped_column(String(30), nullable=False)
    comments: Mapped[str | None] = mapped_column(Text)
    consent: Mapped[bool] = mapped_column(Boolean, nullable=False)
    source: Mapped[str] = mapped_column(String(80), default="zag-flow-landing", nullable=False)


class Admin(Base):
    """Единственный первичный администратор; ограничение защищает от гонки регистрации."""

    __tablename__ = "admins"
    __table_args__ = (CheckConstraint("id = 1"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, default=1)
    username: Mapped[str] = mapped_column(String(80), unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(300), nullable=False)


class BehaviorMetric(Base):
    """Секундный снимок анонимного посещения без содержимого полей формы."""

    __tablename__ = "behavior_metrics"
    __table_args__ = (UniqueConstraint("session_id", "sequence"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), index=True
    )
    session_id: Mapped[str] = mapped_column(String(36), index=True, nullable=False)
    sequence: Mapped[int] = mapped_column(Integer, nullable=False)
    time_on_page: Mapped[int] = mapped_column(Integer, nullable=False)
    buttons_clicked: Mapped[dict] = mapped_column(JSON, nullable=False)
    cursor_positions: Mapped[list] = mapped_column(JSON, nullable=False)
