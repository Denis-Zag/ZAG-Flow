"""Проверки доступа, целостности каталога, метрик и приоритетов."""

from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from uuid import uuid4

import jwt
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select, text

from app.demo_data import demo_requests
from app.main import create_app
from app.models import Admin
from app.scoring import score_request
from app.security import ISSUER

SECRET = "test-signing-secret-at-least-32-bytes-long"
SETUP = "test-setup-key"
CREDENTIALS = {"username": "manager", "password": "long-test-password-123"}
SERVICE = {"name": "Форма обращений", "budget_min": 1000, "budget_max": 200000}


def client_for(tmp_path, root_path=""):
    """Изолировать базу каждого сценария от проекта и сервера."""

    url = f"sqlite+pysqlite:///{(tmp_path / 'admin.db').as_posix()}"
    return TestClient(create_app(url, SETUP, SECRET), root_path=root_path), url


def register(client):
    response = client.post("/api/auth/register", json={**CREDENTIALS, "setup_token": SETUP})
    assert response.status_code == 201
    response = client.post("/api/auth/login", json=CREDENTIALS)
    assert response.status_code == 200
    return {"Authorization": "Bearer " + response.json()["access_token"]}


def test_registration_login_and_password_hash(tmp_path):
    client, url = client_for(tmp_path)
    with client:
        assert client.get("/api/auth/check").json()["registration_available"]
        assert client.post("/api/auth/register", json={**CREDENTIALS, "setup_token": "wrong"}).status_code == 403
        headers = register(client)
        assert not client.get("/api/auth/check").json()["registration_available"]
        assert client.post("/api/auth/register", json={**CREDENTIALS, "setup_token": SETUP}).status_code == 409
        assert client.get("/api/auth/me", headers=headers).json() == {"username": "manager"}
        assert client.post("/api/auth/login", json={**CREDENTIALS, "password": "wrong-password-123"}).status_code == 401
        assert client.post("/api/auth/login", json={**CREDENTIALS, "username": "unknown"}).status_code == 401
    engine = create_engine(url)
    with engine.connect() as conn:
        stored = conn.scalar(select(Admin.password_hash))
        assert stored.startswith("scrypt$") and CREDENTIALS["password"] not in stored
    engine.dispose()
    with TestClient(create_app(url, SETUP, SECRET)) as restarted:
        assert not restarted.get("/api/auth/check").json()["registration_available"]
        assert restarted.post("/api/auth/login", json=CREDENTIALS).status_code == 200


def test_concurrent_first_registration_creates_only_one_admin(tmp_path):
    client, url = client_for(tmp_path)
    with client:
        def attempt(index):
            return client.post("/api/auth/register", json={
                **CREDENTIALS, "username": f"manager{index}", "setup_token": SETUP,
            }).status_code
        with ThreadPoolExecutor(max_workers=2) as pool:
            assert sorted(pool.map(attempt, [1, 2])) == [201, 409]
    engine = create_engine(url)
    with engine.connect() as conn:
        assert conn.scalar(text("SELECT COUNT(*) FROM admins")) == 1
    engine.dispose()


def test_invalid_expired_and_service_tokens_are_rejected(tmp_path):
    client, _ = client_for(tmp_path)
    with client:
        register(client)
        for path in ("/api/auth/me", "/api/requests", "/api/behavior-metrics"):
            assert client.get(path).status_code == 401
        expired = jwt.encode({
            "sub": "manager", "iss": ISSUER, "iat": datetime.now(timezone.utc) - timedelta(hours=2),
            "exp": datetime.now(timezone.utc) - timedelta(hours=1), "jti": "expired",
        }, SECRET, algorithm="HS256")
        for value in (expired, "damaged.jwt.token", SETUP):
            headers = {"Authorization": f"Bearer {value}"}
            assert client.get("/api/auth/me", headers=headers).status_code == 401
            assert client.post("/api/services", json=SERVICE, headers=headers).status_code == 401


def test_service_crud_and_linked_request_preserved(tmp_path):
    client, _ = client_for(tmp_path)
    with client:
        headers = register(client)
        first = client.post("/api/services", json=SERVICE, headers=headers).json()
        updated = {**SERVICE, "name": "Новая форма", "budget_max": 300000}
        assert client.put(f"/api/services/{first['id']}", json=updated).status_code == 401
        assert client.put(f"/api/services/{first['id']}", json=updated, headers=headers).json()["name"] == "Новая форма"
        assert client.delete(f"/api/services/{first['id']}").status_code == 401
        assert client.delete(f"/api/services/{first['id']}", headers=headers).status_code == 204
        assert client.get("/api/services").json() == []
        service = client.post("/api/services", json=SERVICE, headers=headers).json()
        sample = dict(demo_requests()[0])
        for field in ("id", "status", "task_type", "expected_priority"):
            sample.pop(field)
        sample["budget"] = 20000
        sample["service_id"] = service["id"]
        created = client.post("/api/requests", json=sample)
        assert created.status_code == 201
        assert client.delete(f"/api/services/{service['id']}", headers=headers).status_code == 409
        detail = client.get(f"/api/requests/{created.json()['request_id']}", headers=headers)
        assert detail.status_code == 200 and detail.json()["task_type"] == SERVICE["name"]
        assert client.get(f"/api/requests/{created.json()['request_id']}").status_code == 401


def metric(session_id, sequence, duration, clicks=1):
    return {"session_id": session_id, "sequence": sequence, "time_on_page": duration,
            "buttons_clicked": {"Продолжить": clicks}, "cursor_positions": [{"x": .3, "y": .6}]}


def test_metrics_deduplicate_and_average_by_visit(tmp_path):
    client, url = client_for(tmp_path)
    with client:
        headers = register(client)
        assert client.get("/api/behavior-metrics", headers=headers).json()["periods"]["day"]["visits"] == 0
        visit = str(uuid4())
        # Более старый снимок приходит последним: клики берём из максимального sequence.
        for seq, seconds, clicks in ((1, 10, 1), (3, 30, 3), (2, 20, 2)):
            assert client.post("/api/behavior-metrics", json=metric(visit, seq, seconds, clicks)).status_code == 201
        assert client.post("/api/behavior-metrics", json=metric(visit, 3, 30, 3)).json()["duplicate"]
        client.post("/api/behavior-metrics", json=metric(str(uuid4()), 1, 10, 2))
        result = client.get("/api/behavior-metrics", headers=headers).json()
        assert result["periods"]["day"] == {"visits": 2, "average_seconds": 20.0, "max_seconds": 30}
        assert result["clicks"]["Продолжить"] == 5
        assert len(result["points"]) == 4
        invalid = metric(str(uuid4()), 1, 10)
        invalid["cursor_positions"] = [{"x": 2, "y": .5}]
        assert client.post("/api/behavior-metrics", json=invalid).status_code == 422
    engine = create_engine(url)
    with engine.begin() as conn:
        assert conn.scalar(text("SELECT COUNT(*) FROM behavior_metrics")) == 4
        old = datetime.now(timezone.utc) - timedelta(days=8)
        conn.execute(text("UPDATE behavior_metrics SET created_at=:old WHERE session_id=:id"),
                     {"old": old.isoformat(sep=" "), "id": visit})
    engine.dispose()
    with TestClient(create_app(url, SETUP, SECRET)) as client:
        token = client.post("/api/auth/login", json=CREDENTIALS).json()["access_token"]
        data = client.get("/api/behavior-metrics", headers={"Authorization": f"Bearer {token}"}).json()
        assert data["periods"]["day"]["visits"] == 1
        assert data["periods"]["week"]["visits"] == 1
        assert data["periods"]["month"]["visits"] == 2


def test_demo_priorities_are_4_3_3_without_using_status():
    rows = demo_requests()
    results = [score_request(SimpleNamespace(**row)) for row in rows]
    assert [r["priority"] for r in results] == [r["expected_priority"] for r in rows]
    assert Counter(r["priority"] for r in results) == {"high": 4, "medium": 3, "low": 3}
    assert {row["status"] for row in rows} == {"new"}
    assert len({tuple(result["reasons"]) for result in results[:4]}) == 4
    without_urgency = SimpleNamespace(**{
        **rows[-1], "deadline": "Не срочно, без спешки", "budget": "5000",
    })
    assert score_request(without_urgency)["priority"] == "low"


def test_request_ranking_pagination_and_private_details(tmp_path):
    from sqlalchemy.orm import Session
    from app.models import AutomationRequest

    client, url = client_for(tmp_path)
    with client:
        headers = register(client)
        engine = create_engine(url)
        with Session(engine) as session:
            for data in demo_requests():
                data.pop("expected_priority")
                session.add(AutomationRequest(**data))
            session.commit()
        engine.dispose()
        result = client.get("/api/requests", headers=headers).json()
        assert result["total"] == 10
        assert result["counts"] == {"high": 4, "medium": 3, "low": 3}
        scores = [row["score"] for row in result["items"]]
        assert scores == sorted(scores, reverse=True)
        page = client.get("/api/requests?skip=3&limit=2", headers=headers).json()
        assert [r["id"] for r in page["items"]] == [r["id"] for r in result["items"][3:5]]
        assert client.get("/api/requests?skip=-1", headers=headers).status_code == 422


def test_token_required_claims_and_signature(tmp_path):
    client, _ = client_for(tmp_path)
    with client:
        register(client)
        now = datetime.now(timezone.utc)
        payload = {"sub": "manager", "iss": ISSUER, "iat": now,
                   "exp": now + timedelta(hours=1), "jti": "test"}
        unsigned_claims = dict(payload)
        unsigned_claims.pop("exp")
        values = [jwt.encode(unsigned_claims, SECRET, algorithm="HS256"),
                  jwt.encode(payload, "wrong-signing-secret-at-least-32-bytes", algorithm="HS256")]
        for value in values:
            assert client.get("/api/auth/me", headers={"Authorization": f"Bearer {value}"}).status_code == 401


def test_prefixed_swagger_and_private_cache_headers(tmp_path):
    client, _ = client_for(tmp_path, root_path="/next")
    with client:
        assert "/next/api/openapi.json" in client.get("/api/docs").text
        description = client.get("/api/openapi.json").json()
        assert {"url": "/next"} in description["servers"]
        denied = client.get("/api/requests")
        assert denied.status_code == 401
        assert denied.headers["cache-control"] == "no-store"
