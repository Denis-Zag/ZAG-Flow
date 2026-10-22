"""Интеграционная проверка только на отдельной временной PostgreSQL-базе."""

import os
from pathlib import Path
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text

from app.main import create_app

URL = os.getenv("POSTGRES_TEST_URL", "")
pytestmark = pytest.mark.skipif(not URL, reason="Нужна отдельная POSTGRES_TEST_URL")


def test_postgresql_schema_sql_repeatability_and_metrics():
    """Не допустить запуска интеграционного сценария на рабочей базе."""

    from sqlalchemy.engine import make_url

    assert make_url(URL).database == "zag_flow_admin_check"
    secret = "postgres-check-signing-secret-at-least-32-bytes"
    credentials = {"username": "pgmanager", "password": "postgres-check-password"}
    with TestClient(create_app(URL, "postgres-setup", secret)) as client:
        assert client.get("/api/health").status_code == 200
        assert client.post("/api/auth/register", json={**credentials, "setup_token": "postgres-setup"}).status_code == 201
        login = client.post("/api/auth/login", json=credentials)
        headers = {"Authorization": "Bearer " + login.json()["access_token"]}
        engine = create_engine(URL)
        sql = Path(os.environ["DEMO_SQL_PATH"]).read_text(encoding="utf-8")
        for _ in range(2):
            raw = engine.raw_connection()
            try:
                with raw.cursor() as cursor:
                    cursor.execute(sql)
                raw.commit()
            finally:
                raw.close()
        with engine.connect() as conn:
            assert conn.scalar(text("SELECT COUNT(*) FROM automation_requests")) == 10
        result = client.get("/api/requests", headers=headers).json()
        assert result["counts"] == {"high": 4, "medium": 3, "low": 3}
        assert {row["status"] for row in result["items"]} == {"new"}
        sid = str(uuid4())
        for sequence, duration in ((1, 10), (2, 20)):
            sample = {"session_id": sid, "sequence": sequence, "time_on_page": duration,
                      "cursor_positions": [{"x": .4, "y": .7}], "buttons_clicked": {"Далее": sequence}}
            assert client.post("/api/behavior-metrics", json=sample).status_code == 201
        stats = client.get("/api/behavior-metrics", headers=headers).json()
        assert stats["periods"]["day"]["average_seconds"] == 20
        assert stats["periods"]["day"]["visits"] == 1
        assert stats["clicks"]["Далее"] == 2
        service = client.post("/api/services", json={"name": "Удаляемая услуга", "budget_min": 0, "budget_max": 10}, headers=headers).json()
        assert client.delete(f"/api/services/{service['id']}", headers=headers).status_code == 204
        engine.dispose()
