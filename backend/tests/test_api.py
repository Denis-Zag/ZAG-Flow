"""Офлайн-проверки API приёма заявок."""

from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text

from app.main import create_app


def make_payload() -> dict[str, object]:
    """Вернуть корректный пример заявки."""

    return {
        "task_type": "Заявки и обращения",
        "task_description": "Заявки приходят из нескольких каналов и вручную переносятся в таблицу.",
        "business_name": "Тестовый проект",
        "business_niche": "Сервисные услуги",
        "expected_result": "Собирать все обращения в одном месте и не терять новые заявки.",
        "budget": "Нужно оценить",
        "deadline": "После согласования первого этапа",
        "contact_name": "Тест",
        "contact_email": "test@example.com",
        "contact_phone": "@test",
        "contact_method": "Telegram",
        "comments": "Только тестовые данные.",
        "consent": True,
        "source": "offline-test",
        "website": "",
    }


def create_client(tmp_path: Path) -> tuple[TestClient, str]:
    database_path = tmp_path / "zag_flow_test.db"
    database_url = f"sqlite+pysqlite:///{database_path.as_posix()}"
    return TestClient(create_app(database_url)), database_url


def test_health_checks_database(tmp_path: Path) -> None:
    client, _ = create_client(tmp_path)

    with client:
        response = client.get("/api/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "database": "ok"}


def test_create_request_and_read_public_status(tmp_path: Path) -> None:
    client, database_url = create_client(tmp_path)

    with client:
        response = client.post("/api/requests", json=make_payload())
        assert response.status_code == 201
        request_id = response.json()["request_id"]

        status_response = client.get(f"/api/requests/{request_id}/status")

    assert status_response.status_code == 200
    assert status_response.json() == {"request_id": request_id, "status": "new"}

    engine = create_engine(database_url)
    with engine.connect() as connection:
        count = connection.execute(text("SELECT COUNT(*) FROM automation_requests")).scalar_one()
    engine.dispose()
    assert count == 1


def test_short_description_is_rejected(tmp_path: Path) -> None:
    client, _ = create_client(tmp_path)
    payload = make_payload()
    payload["task_description"] = "Слишком коротко"

    with client:
        response = client.post("/api/requests", json=payload)

    assert response.status_code == 422


def test_honeypot_is_rejected(tmp_path: Path) -> None:
    client, _ = create_client(tmp_path)
    payload = make_payload()
    payload["website"] = "https://spam.example"

    with client:
        response = client.post("/api/requests", json=payload)

    assert response.status_code == 422
