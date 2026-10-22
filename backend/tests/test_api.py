"""Офлайн-проверки API приёма заявок."""

from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text

from app.main import create_app

SERVICE = {"name": "Приём и обработка заявок", "budget_min": 10000, "budget_max": 30000}


def authorize(client: TestClient) -> dict[str, str]:
    """Получить действующий JWT для проверок каталога."""

    cached = getattr(client, "admin_headers", None)
    if cached:
        return cached
    credentials = {"username": "admin", "password": "offline-password-123"}
    client.post("/api/auth/register", json={**credentials, "setup_token": "offline-service-key"})
    response = client.post("/api/auth/login", json=credentials)
    assert response.status_code == 200
    client.admin_headers = {"Authorization": f"Bearer {response.json()['access_token']}"}
    return client.admin_headers

def make_payload() -> dict[str, object]:
    """Вернуть корректный пример заявки."""

    return {
        "service_id": 1,
        "task_description": "Заявки приходят из нескольких каналов и вручную переносятся в таблицу.",
        "business_name": "Тестовый проект",
        "business_niche": "Сервисные услуги",
        "expected_result": "Собирать все обращения в одном месте и не терять новые заявки.",
        "budget": 20000,
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
    return TestClient(create_app(
        database_url, admin_token="offline-service-key", jwt_secret="offline-secret-" * 4,
    )), database_url


def test_health_checks_database(tmp_path: Path) -> None:
    client, _ = create_client(tmp_path)

    with client:
        response = client.get("/api/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "database": "ok"}


def test_create_request_and_read_public_status(tmp_path: Path) -> None:
    client, database_url = create_client(tmp_path)

    with client:
        assert client.post("/api/services", json=SERVICE, headers=authorize(client)).status_code == 201
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


def test_service_catalog_requires_key_and_returns_all_ranges(tmp_path: Path) -> None:
    client, _ = create_client(tmp_path)
    with client:
        assert client.get("/api/services").json() == []
        assert client.post("/api/services", json=SERVICE).status_code == 401
        for index in range(3):
            payload = {
                "name": f"Услуга {index + 1}",
                "budget_min": (index + 1) * 10000,
                "budget_max": (index + 1) * 30000,
            }
            response = client.post("/api/services", json=payload, headers=authorize(client))
            assert response.status_code == 201
            assert response.json() == {"id": index + 1, **payload}
        catalog = client.get("/api/services")
    assert catalog.status_code == 200
    assert len(catalog.json()) == 3


def test_invalid_range_and_duplicate_service_rejected(tmp_path: Path) -> None:
    client, _ = create_client(tmp_path)
    with client:
        assert client.post("/api/services", json=SERVICE, headers=authorize(client)).status_code == 201
        assert client.post("/api/services", json=SERVICE, headers=authorize(client)).status_code == 409
        invalid = {**SERVICE, "budget_min": 40000}
        assert client.post("/api/services", json=invalid, headers=authorize(client)).status_code == 422


def test_unknown_service_and_out_of_range_budget_not_saved(tmp_path: Path) -> None:
    client, database_url = create_client(tmp_path)
    with client:
        assert client.post("/api/services", json=SERVICE, headers=authorize(client)).status_code == 201
        for changes in [{"service_id": 999}, {"budget": 9999}, {"budget": 30001}]:
            response = client.post("/api/requests", json={**make_payload(), **changes})
            assert response.status_code == 422
    engine = create_engine(database_url)
    with engine.connect() as connection:
        assert connection.scalar(text("SELECT COUNT(*) FROM automation_requests")) == 0
    engine.dispose()


def test_service_and_budget_are_saved_with_request(tmp_path: Path) -> None:
    client, database_url = create_client(tmp_path)
    with client:
        client.post("/api/services", json=SERVICE, headers=authorize(client))
        response = client.post("/api/requests", json=make_payload())
        assert response.status_code == 201
    engine = create_engine(database_url)
    with engine.connect() as connection:
        row = connection.execute(text(
            "SELECT service_id, task_type, budget FROM automation_requests"
        )).one()
        assert tuple(row) == (1, SERVICE["name"], "20000")
    engine.dispose()


def test_upgrade_preserves_existing_row_and_is_repeatable(tmp_path: Path) -> None:
    database_url = f"sqlite+pysqlite:///{(tmp_path / 'legacy.db').as_posix()}"
    engine = create_engine(database_url)
    # Минимальная старая таблица нужна для проверки добавления столбца без потери строки.
    with engine.begin() as connection:
        connection.execute(text("CREATE TABLE automation_requests (id VARCHAR(36) PRIMARY KEY)"))
        connection.execute(text("INSERT INTO automation_requests (id) VALUES ('legacy-request')"))
    engine.dispose()
    for _ in range(2):
        with TestClient(create_app(database_url)) as client:
            assert client.get("/api/health").status_code == 200
    engine = create_engine(database_url)
    with engine.connect() as connection:
        row = connection.execute(text("SELECT id, service_id FROM automation_requests")).one()
        assert tuple(row) == ("legacy-request", None)
    engine.dispose()


def test_service_writes_disabled_without_configuration(tmp_path: Path) -> None:
    database_url = f"sqlite+pysqlite:///{(tmp_path / 'disabled.db').as_posix()}"
    with TestClient(create_app(database_url, admin_token="")) as client:
        assert client.post("/api/services", json=SERVICE, headers={"Authorization": "Bearer disabled"}).status_code == 503


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
