"""Схемы проверки входных и выходных данных API."""

from typing import Literal

from pydantic import BaseModel, EmailStr, Field, field_validator


class AutomationRequestCreate(BaseModel):
    """Данные, которые принимает форма заявки."""

    task_type: str = Field(min_length=2, max_length=80)
    task_description: str = Field(min_length=30, max_length=2000)
    business_name: str | None = Field(default=None, max_length=120)
    business_niche: str = Field(min_length=2, max_length=120)
    expected_result: str = Field(min_length=15, max_length=1000)
    budget: str = Field(min_length=2, max_length=80)
    deadline: str | None = Field(default=None, max_length=100)

    contact_name: str = Field(min_length=2, max_length=100)
    contact_email: EmailStr
    contact_phone: str | None = Field(default=None, max_length=100)
    contact_method: Literal["Email", "Telegram", "Телефон"]
    comments: str | None = Field(default=None, max_length=1000)
    consent: Literal[True]
    source: str = Field(default="zag-flow-landing", max_length=80)
    website: str = Field(default="", max_length=200, exclude=True)

    @field_validator(
        "task_type",
        "task_description",
        "business_name",
        "business_niche",
        "expected_result",
        "budget",
        "deadline",
        "contact_name",
        "contact_phone",
        "comments",
        mode="before",
    )
    @classmethod
    def normalize_text(cls, value: object) -> object:
        """Убрать случайные пробелы и преобразовать пустые строки в None."""

        if isinstance(value, str):
            normalized = " ".join(value.split())
            return normalized or None
        return value

    @field_validator("website")
    @classmethod
    def reject_honeypot(cls, value: str) -> str:
        """Отклонить автоматическую отправку скрытого поля."""

        if value.strip():
            raise ValueError("Некорректная отправка формы")
        return ""


class AutomationRequestAccepted(BaseModel):
    """Короткое подтверждение приёма заявки."""

    request_id: str
    status: Literal["accepted"] = "accepted"
    message: str = "Заявка принята"


class HealthResponse(BaseModel):
    """Ответ проверки состояния Backend и базы данных."""

    status: Literal["ok"] = "ok"
    database: Literal["ok"] = "ok"
