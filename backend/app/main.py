"""HTTP API для приёма заявок ZAG Flow."""

import os
import secrets
from collections.abc import Generator
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from .database import create_database, initialize_database
from .models import AutomationRequest, Service
from .schemas import (
    AutomationRequestAccepted, AutomationRequestCreate, HealthResponse,
    ServiceCreate, ServiceRead,
)

DEFAULT_DATABASE_URL = "sqlite+pysqlite:///./data/zag_flow.db"


def create_app(database_url: str | None = None, admin_token: str | None = None) -> FastAPI:
    """Создать приложение с отдельным подключением к базе данных."""

    selected_url = database_url or os.getenv("DATABASE_URL", DEFAULT_DATABASE_URL)
    engine, session_factory = create_database(selected_url)
    selected_token = admin_token if admin_token is not None else os.getenv("SERVICE_ADMIN_TOKEN", "")
    bearer = HTTPBearer(auto_error=False, scheme_name="ServiceAdmin")

    @asynccontextmanager
    async def lifespan(_: FastAPI):
        initialize_database(engine)
        yield
        engine.dispose()

    application = FastAPI(
        title="ZAG Flow API",
        description="API приёма заявок на автоматизацию",
        version="0.2.0",
        docs_url="/api/docs",
        openapi_url="/api/openapi.json",
        redoc_url=None,
        lifespan=lifespan,
    )

    def get_session() -> Generator[Session, None, None]:
        session = session_factory()
        try:
            yield session
        finally:
            session.close()

    def require_admin(
        credentials: HTTPAuthorizationCredentials | None = Depends(bearer),
    ) -> None:
        """Разрешить изменение каталога только со служебным ключом."""

        if not selected_token:
            raise HTTPException(status_code=503, detail="Редактирование каталога отключено")
        if credentials is None or not secrets.compare_digest(
            credentials.credentials.encode(), selected_token.encode()
        ):
            raise HTTPException(
                status_code=401, detail="Нужен служебный ключ",
                headers={"WWW-Authenticate": "Bearer"},
            )

    @application.get("/api/services", response_model=list[ServiceRead], tags=["services"])
    def get_services(session: Session = Depends(get_session)) -> list[Service]:
        """Вернуть весь каталог услуг для клиентской формы."""

        return list(session.scalars(select(Service).order_by(Service.id)))

    @application.post(
        "/api/services", response_model=ServiceRead, status_code=status.HTTP_201_CREATED,
        tags=["services"], dependencies=[Depends(require_admin)],
    )
    def create_service(
        payload: ServiceCreate, session: Session = Depends(get_session),
    ) -> Service:
        """Добавить услугу через Swagger или авторизованный API-запрос."""

        row = Service(**payload.model_dump())
        try:
            session.add(row)
            session.commit()
        except IntegrityError as error:
            session.rollback()
            raise HTTPException(status_code=409, detail="Услуга с таким названием уже есть") from error
        except SQLAlchemyError as error:
            session.rollback()
            raise HTTPException(status_code=503, detail="Не удалось сохранить услугу") from error
        return row

    @application.get("/api/health", response_model=HealthResponse, tags=["service"])
    def health(session: Session = Depends(get_session)) -> HealthResponse:
        """Проверить доступность приложения и базы данных."""

        try:
            session.execute(text("SELECT 1"))
        except SQLAlchemyError as error:
            raise HTTPException(status_code=503, detail="База данных недоступна") from error
        return HealthResponse()

    @application.post(
        "/api/requests",
        response_model=AutomationRequestAccepted,
        status_code=status.HTTP_201_CREATED,
        tags=["requests"],
    )
    def create_request(
        payload: AutomationRequestCreate,
        session: Session = Depends(get_session),
    ) -> AutomationRequestAccepted:
        """Проверить и сохранить новую заявку."""

        service = session.get(Service, payload.service_id)
        if service is None:
            raise HTTPException(status_code=422, detail="Выбранная услуга недоступна")
        if not service.budget_min <= payload.budget <= service.budget_max:
            raise HTTPException(status_code=422, detail="Бюджет вне диапазона выбранной услуги")
        data = payload.model_dump(exclude={"website"})
        data["budget"] = str(payload.budget)
        request_row = AutomationRequest(**data, task_type=service.name)
        try:
            session.add(request_row)
            session.commit()
        except SQLAlchemyError as error:
            session.rollback()
            raise HTTPException(status_code=503, detail="Не удалось сохранить заявку") from error
        return AutomationRequestAccepted(request_id=request_row.id)

    @application.get("/api/requests/{request_id}/status", tags=["requests"])
    def get_request_status(
        request_id: str,
        session: Session = Depends(get_session),
    ) -> dict[str, str]:
        """Вернуть только технический статус заявки без контактных данных."""

        request_status = session.scalar(
            select(AutomationRequest.status).where(AutomationRequest.id == request_id)
        )
        if request_status is None:
            raise HTTPException(status_code=404, detail="Заявка не найдена")
        return {"request_id": request_id, "status": request_status}

    return application


app = create_app()
