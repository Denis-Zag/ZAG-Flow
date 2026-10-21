"""Схемы проверки входных и выходных данных API."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator, model_validator


class ServiceCreate(BaseModel):
    """Название услуги и допустимый диапазон бюджета в рублях."""

    name: str = Field(min_length=2, max_length=80)
    budget_min: int = Field(ge=0, le=100_000_000)
    budget_max: int = Field(ge=0, le=100_000_000)

    @field_validator("name", mode="before")
    @classmethod
    def normalize_name(cls, value: object) -> object:
        """Нормализовать пробелы до проверки длины названия."""

        return " ".join(value.split()) if isinstance(value, str) else value

    @model_validator(mode="after")
    def validate_budget(self) -> "ServiceCreate":
        """Не принимать перевёрнутый диапазон бюджета."""

        if self.budget_max < self.budget_min:
            raise ValueError("Максимальный бюджет должен быть не меньше минимального")
        return self


class ServiceRead(ServiceCreate):
    """Публичная карточка услуги без служебных данных."""

    model_config = ConfigDict(from_attributes=True)
    id: int


class AutomationRequestCreate(BaseModel):
    """Данные, которые принимает форма заявки."""

    service_id: int = Field(gt=0)
    task_description: str = Field(min_length=30, max_length=2000)
    business_name: str | None = Field(default=None, max_length=120)
    business_niche: str = Field(min_length=2, max_length=120)
    expected_result: str = Field(min_length=15, max_length=1000)
    budget: int = Field(ge=0, le=100_000_000)
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
        "task_description",
        "business_name",
        "business_niche",
        "expected_result",
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
