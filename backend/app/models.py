"""Модели хранения заявок."""

from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import Boolean, DateTime, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from .database import Base


class AutomationRequest(Base):
    """Заявка посетителя на разбор задачи автоматизации."""

    __tablename__ = "automation_requests"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )
    status: Mapped[str] = mapped_column(String(32), default="new", nullable=False)

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
