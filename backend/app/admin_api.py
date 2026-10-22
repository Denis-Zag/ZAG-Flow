"""Авторизация, чтение заявок и агрегированная статистика панели управления."""

import secrets
from datetime import datetime, timedelta, timezone

from fastapi import Depends, HTTPException, Query
from sqlalchemy import func, select, tuple_
from sqlalchemy.exc import IntegrityError

from .models import Admin, AutomationRequest, BehaviorMetric
from .schemas import AdminCredentials, AdminRegistration, MetricCreate
from .scoring import score_request
from .security import hash_password, issue_token, verify_password


def request_data(row: AutomationRequest) -> dict:
    """Подготовить заявку и вычислить приоритет по текущим данным."""

    return {
        column.name: getattr(row, column.name)
        for column in AutomationRequest.__table__.columns
    } | score_request(row)


def install_admin_routes(app, get_session, require_admin, secret, setup_token):
    """Подключить маршруты к приложению с его собственной базой и настройками."""

    def require_auth_config():
        if len(secret.encode()) < 32:
            raise HTTPException(503, "Авторизация не настроена: нужен SECRET_KEY от 32 байт")

    @app.get("/api/auth/check", tags=["auth"])
    def auth_check(session=Depends(get_session)):
        return {"registration_available": session.get(Admin, 1) is None}

    @app.post("/api/auth/register", status_code=201, tags=["auth"])
    def register(payload: AdminRegistration, session=Depends(get_session)):
        require_auth_config()
        if session.get(Admin, 1) is not None:
            raise HTTPException(409, "Администратор уже зарегистрирован")
        if not setup_token or not secrets.compare_digest(
            payload.setup_token.encode(), setup_token.encode()
        ):
            raise HTTPException(403, "Неверный ключ первичной настройки")
        row = Admin(id=1, username=payload.username, password_hash=hash_password(payload.password))
        session.add(row)
        try:
            session.commit()
        except IntegrityError as error:
            session.rollback()
            raise HTTPException(409, "Администратор уже зарегистрирован") from error
        return {"username": row.username}

    @app.post("/api/auth/login", tags=["auth"])
    def login(payload: AdminCredentials, session=Depends(get_session)):
        require_auth_config()
        admin = session.get(Admin, 1)
        # Одинаковая работа хеширования для неизвестного и известного логина.
        encoded = admin.password_hash if admin else hash_password("unavailable-account")
        valid = verify_password(payload.password, encoded)
        if not admin or not valid or not secrets.compare_digest(
            payload.username.encode(), admin.username.encode()
        ):
            raise HTTPException(401, "Неверный логин или пароль")
        return {"access_token": issue_token(admin.username, secret),
                "token_type": "bearer", "expires_in": 3600}

    @app.get("/api/auth/me", tags=["auth"])
    def profile(admin=Depends(require_admin)):
        return {"username": admin.username}

    @app.get("/api/requests", tags=["administration"], dependencies=[Depends(require_admin)])
    def requests(
        skip: int = Query(0, ge=0), limit: int = Query(100, ge=1, le=500),
        session=Depends(get_session),
    ):
        rows = [request_data(row) for row in session.scalars(select(AutomationRequest))]
        rows.sort(key=lambda row: (row["score"], row["created_at"], row["id"]), reverse=True)
        counts = {priority: sum(row["priority"] == priority for row in rows)
                  for priority in ("high", "medium", "low")}
        return {"total": len(rows), "counts": counts, "items": rows[skip:skip + limit]}

    @app.get("/api/requests/{request_id}", tags=["administration"],
             dependencies=[Depends(require_admin)])
    def request_detail(request_id: str, session=Depends(get_session)):
        row = session.get(AutomationRequest, request_id)
        if row is None:
            raise HTTPException(404, "Заявка не найдена")
        return request_data(row)

    @app.post("/api/behavior-metrics", status_code=201, tags=["metrics"])
    def save_metric(payload: MetricCreate, session=Depends(get_session)):
        data = payload.model_dump(mode="json")
        row = BehaviorMetric(**data)
        session.add(row)
        try:
            session.commit()
        except IntegrityError:
            session.rollback()
            existing = session.scalar(select(BehaviorMetric).where(
                BehaviorMetric.session_id == str(payload.session_id),
                BehaviorMetric.sequence == payload.sequence,
            ))
            if existing is None:
                raise HTTPException(503, "Не удалось сохранить метрики")
            return {"id": existing.id, "duplicate": True}
        return {"id": row.id, "duplicate": False}

    @app.get("/api/behavior-metrics", tags=["metrics"],
             dependencies=[Depends(require_admin)])
    def metrics(session=Depends(get_session)):
        now = datetime.now(timezone.utc)
        visits = session.execute(select(
            BehaviorMetric.session_id,
            func.min(BehaviorMetric.created_at).label("started"),
            func.max(BehaviorMetric.time_on_page).label("duration"),
            func.max(BehaviorMetric.sequence).label("last_sequence"),
        ).group_by(BehaviorMetric.session_id)).all()
        periods = {}
        for name, days in (("day", 1), ("week", 7), ("month", 30)):
            selected = [v for v in visits
                        if v.started.replace(tzinfo=timezone.utc) >= now - timedelta(days=days)]
            durations = [v.duration for v in selected]
            periods[name] = {
                "visits": len(selected),
                "average_seconds": round(sum(durations) / len(durations), 1) if durations else 0,
                "max_seconds": max(durations, default=0),
            }
        latest_ids = [(v.session_id, v.last_sequence) for v in visits
                      if v.started.replace(tzinfo=timezone.utc) >= now - timedelta(days=30)]
        clicks = {}
        # Пакеты ограничивают размер IN-запросов, в том числе в SQLite.
        for offset in range(0, len(latest_ids), 500):
            for row in session.scalars(select(BehaviorMetric).where(
                tuple_(BehaviorMetric.session_id, BehaviorMetric.sequence).in_(
                    latest_ids[offset:offset + 500]
                )
            )):
                for label, count in row.buttons_clicked.items():
                    clicks[label] = clicks.get(label, 0) + count
        points = []
        sampled_rows = list(session.scalars(select(BehaviorMetric).where(
            BehaviorMetric.created_at >= now - timedelta(days=30)
        ).order_by(BehaviorMetric.id.desc()).limit(2000)))
        for row in sampled_rows:
            points.extend(row.cursor_positions)
        return {
            "periods": periods, "clicks": clicks, "points": points,
            "sample_limit": 2000, "sample_rows": len(sampled_rows),
            "period_definition": "Последние 24 часа / 7 дней / 30 дней по началу посещения, UTC",
        }
