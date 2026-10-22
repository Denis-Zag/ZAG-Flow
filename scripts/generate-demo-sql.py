"""Сформировать повторяемый PostgreSQL-скрипт и ожидаемые оценки заявок."""

import json
import sys
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
from app.demo_data import demo_requests
from app.scoring import score_request
from app.models import Admin
from sqlalchemy.dialects import postgresql
from sqlalchemy.schema import CreateTable


def literal(value):
    """Экранировать литералы SQL без исполнения запросов."""

    if value is None:
        return "NULL"
    if isinstance(value, bool):
        return "TRUE" if value else "FALSE"
    return "'" + str(value).replace("'", "''") + "'"


def main():
    """Записать SQL и ожидаемые категории; существующую базу не подключать."""

    target = ROOT / "docs" / "sql"
    target.mkdir(parents=True, exist_ok=True)
    admin_ddl = str(CreateTable(Admin.__table__, if_not_exists=True).compile(
        dialect=postgresql.dialect()
    ))
    clean_ddl = "\n".join(line.rstrip() for line in admin_ddl.strip().splitlines())
    (target / "admin-schema.sql").write_text(clean_ddl + ";\n", encoding="utf-8")
    chunks = [
        "-- Вымышленные заявки ZAG Flow. Повторный запуск не создаёт дубли.",
        "BEGIN;",
        "INSERT INTO services (name, budget_min, budget_max) "
        "VALUES ('Автоматизация обращений', 0, 200000) ON CONFLICT (name) DO NOTHING;",
    ]
    expected = []
    for source in demo_requests():
        row = dict(source)
        expected_priority = row.pop("expected_priority")
        score = score_request(SimpleNamespace(**row))
        assert score["priority"] == expected_priority, row["contact_name"]
        expected.append({"id": row["id"], "name": row["contact_name"], **score})
        columns = ", ".join(row)
        values = ", ".join(literal(value) for value in row.values())
        chunks.append(
            f"INSERT INTO automation_requests ({columns}, created_at, service_id) "
            f"SELECT {values}, CURRENT_TIMESTAMP, id FROM services "
            "WHERE name = 'Автоматизация обращений' ON CONFLICT (id) DO NOTHING;"
        )
    chunks.append("COMMIT;")
    (target / "demo-requests.sql").write_text("\n\n".join(chunks) + "\n", encoding="utf-8")
    (target / "expected-priorities.json").write_text(
        json.dumps(expected, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print("Подготовлены SQL и ожидаемые оценки: 4 высоких, 3 средних, 3 низких.")


if __name__ == "__main__":
    main()
