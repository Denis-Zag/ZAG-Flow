"""HTTP API для приёма заявок ZAG Flow."""

import os
from collections.abc import Generator
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, HTTPException, status
from sqlalchemy import select, text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from .database import Base, create_database
from .models import AutomationRequest
from .schemas import AutomationRequestAccepted, AutomationRequestCreate, HealthResponse

DEFAULT_DATABASE_URL = "sqlite+pysqlite:///./data/zag_flow.db"


def create_app(database_url: str | None = None) -> FastAPI:
    """Создать приложение с отдельным подключением к базе данных."""

    selected_url = database_url or os.getenv("DATABASE_URL", DEFAULT_DATABASE_URL)
    engine, session_factory = create_database(selected_url)

    @asynccontextmanager
    async def lifespan(_: FastAPI):
        Base.metadata.create_all(bind=engine)
        yield
        engine.dispose()

    application = FastAPI(
        title="ZAG Flow API",
        description="API приёма заявок на автоматизацию",
        version="0.1.0",
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

        request_row = AutomationRequest(**payload.model_dump(exclude={"website"}))
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
