"""Вымышленные заявки для независимой проверки распределения приоритетов 4/3/3."""

from uuid import UUID

LONG_TASK = (
    "Нужно собрать обращения из формы, распределять их между сотрудниками "
    "и показывать руководителю понятный список текущих задач."
)
LONG_RESULT = "Получить единый список обращений и сократить ручное переключение между таблицами."
SHORT_TASK = "Нужно настроить удобную форму для новых обращений."
SHORT_RESULT = "Собирать обращения на сайте."

CASES = [
    ("Ирина", "Мастерская Сосна", "Сегодня", 20000, SHORT_TASK, SHORT_RESULT, "high"),
    ("Павел", "Студия Вектор", "За неделю", 50000, LONG_TASK, LONG_RESULT, "high"),
    ("Ольга", "Сервис Маяк", "Срок согласуем", 100000,
     "Сбой при передаче обращений мешает команде: нужно собрать заявки из формы "
     "в одном списке и распределять их по ответственным сотрудникам.", LONG_RESULT, "high"),
    ("Максим", "Проект Линия", "Завтра", 5000,
     "Теряем обращения при переносе, нужна единая форма.", SHORT_RESULT, "high"),
    ("Анна", "Бюро Север", "Сегодня", 5000, SHORT_TASK, SHORT_RESULT, "medium"),
    ("Денис", "Команда Ритм", "За неделю", 10000, SHORT_TASK, SHORT_RESULT, "medium"),
    ("Мария", "Студия Берег", "В течение месяца", 50000, SHORT_TASK, SHORT_RESULT, "medium"),
    ("Виктор", "Проект Контур", "Когда будет удобно", 10000, SHORT_TASK, SHORT_RESULT, "low"),
    ("Елена", "Мастерская Точка", "В течение месяца", 5000, SHORT_TASK, SHORT_RESULT, "low"),
    ("Алексей", "Бюро Парус", "Без спешки", 20000, SHORT_TASK, SHORT_RESULT, "low"),
]


def demo_requests() -> list[dict]:
    """Сформировать стабильные идентификаторы и заведомо вымышленные контакты."""

    rows = []
    for index, (name, business, deadline, budget, task, result, priority) in enumerate(CASES, 1):
        rows.append({
            "id": str(UUID(int=0x5A6F0000000000000000000000000000 + index)),
            "status": "new", "task_type": "Автоматизация обращений",
            "task_description": task, "business_name": business,
            "business_niche": "Сервисные услуги", "expected_result": result,
            "budget": str(budget), "deadline": deadline, "contact_name": name,
            "contact_email": f"demo{index}@example.com", "contact_phone": None,
            "contact_method": "Email", "comments": "Демонстрационные вымышленные данные.",
            "consent": True, "source": "zag-flow-demo", "expected_priority": priority,
        })
    return rows
