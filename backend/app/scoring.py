"""Объяснимая оценка приоритета по фактически собираемым полям заявки."""

import re


def score_request(row) -> dict:
    """Вернуть балл, категорию и причины без изменения технического статуса."""

    score = 0
    reasons = []
    deadline = (row.deadline or "").lower()
    deadline = re.sub(r"не\s*сроч\w*", "", deadline)
    if re.search(r"сроч|сегодня|завтра|немедлен|за [123] д|[123] дня", deadline):
        score += 50
        reasons.append("Срочный срок: +50")
    elif re.search(r"недел|7 д|10 д|14 д", deadline):
        score += 30
        reasons.append("Срок в пределах двух недель: +30")
    elif "месяц" in deadline:
        score += 10
        reasons.append("Срок около месяца: +10")

    try:
        budget = int(row.budget)
    except (ValueError, TypeError):
        budget = 0
    budget_score = 30 if budget >= 100000 else 20 if budget >= 50000 else 10 if budget >= 20000 else 0
    if budget_score:
        score += budget_score
        reasons.append(f"Бюджет {budget:,} ₽: +{budget_score}".replace(",", " "))

    impact = f"{row.task_description} {row.expected_result}".lower()
    if re.search(r"теря[ею]|потер[яи]|останов|сбой|не поступ", impact):
        score += 20
        reasons.append("Описаны потери или остановка процесса: +20")
    if len(row.task_description) >= 80 and len(row.expected_result) >= 40:
        score += 10
        reasons.append("Подробно описаны задача и ожидаемый результат: +10")
    priority = "high" if score >= 60 else "medium" if score >= 30 else "low"
    return {
        "score": score, "priority": priority,
        "reasons": reasons or ["Срочность и высокий бюджет не указаны: 0"],
        "personal_manager": priority == "high",
        "department": row.task_type,
    }
