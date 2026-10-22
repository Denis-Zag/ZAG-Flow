"use strict";

const $ = (selector) => document.querySelector(selector);
const money = new Intl.NumberFormat("ru-RU", { style: "currency", currency: "RUB", maximumFractionDigits: 0 });
const labels = { high: "Высокий", medium: "Средний", low: "Низкий" };
let token = "";
let registering = false;
let currentTab = "services";
let services = [];
let metricData = null;
let requestOffset = 0;

const element = (tag, text = "", className = "") => {
  const node = document.createElement(tag);
  node.textContent = text;
  if (className) node.className = className;
  return node;
};

async function api(path, options = {}) {
  const response = await fetch(path, {
    ...options,
    headers: { "Content-Type": "application/json", ...(token ? { Authorization: `Bearer ${token}` } : {}), ...options.headers },
    signal: AbortSignal.timeout(15000), cache: "no-store",
  });
  const payload = response.status === 204 ? null : await response.json().catch(() => ({}));
  if (!response.ok) {
    if (response.status === 401 && token) await logout();
    throw new Error(typeof payload?.detail === "string" ? payload.detail : "Проверьте введённые данные. Если ошибка повторяется, обновите страницу.");
  }
  return payload;
}

async function checkRegistration() {
  try {
    const data = await api("/api/auth/check");
    if (!data.registration_available && registering) setRegistration(false);
    $("#register-toggle").hidden = !data.registration_available;
  } catch (error) { $("#auth-message").textContent = error.message; }
}

function setRegistration(value) {
  registering = value;
  $("#setup-field").hidden = !value;
  $("[name=setup_token]").required = value;
  $("[name=password]").autocomplete = value ? "new-password" : "current-password";
  $("#auth-title").textContent = value ? "Создание администратора" : "Вход в управление";
  $("#auth-submit").textContent = value ? "Создать администратора →" : "Войти →";
  $("#register-toggle").textContent = value ? "Вернуться ко входу" : "Зарегистрироваться";
  $("#auth-message").textContent = "";
}

async function logout() {
  token = "";
  metricData = null;
  services = [];
  document.querySelectorAll("dialog[open]").forEach((dialog) => dialog.close());
  ["#requests-body", "#request-details", "#services-body", "#click-summary"].forEach((id) => $(id).replaceChildren());
  $("#workspace").hidden = true;
  $("#auth-view").hidden = false;
  $("#logout").hidden = true;
  $("#account").textContent = "";
  setRegistration(false);
  await checkRegistration();
}

$("#register-toggle").addEventListener("click", () => setRegistration(!registering));
$("#logout").addEventListener("click", logout);
$("#auth-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  const form = event.currentTarget;
  const values = Object.fromEntries(new FormData(form));
  $("#auth-submit").disabled = true;
  $("#auth-message").textContent = "";
  try {
    if (registering) await api("/api/auth/register", { method: "POST", body: JSON.stringify(values) });
    const data = await api("/api/auth/login", { method: "POST", body: JSON.stringify({ username: values.username, password: values.password }) });
    token = data.access_token;
    const profile = await api("/api/auth/me");
    form.reset();
    setRegistration(false);
    $("#account").textContent = profile.username;
    $("#logout").hidden = false;
    $("#auth-view").hidden = true;
    $("#workspace").hidden = false;
    await loadTab();
  } catch (error) {
    $("#auth-message").textContent = error.message;
    await checkRegistration();
  } finally { $("#auth-submit").disabled = false; }
});

function rowButton(text, action, danger = false) {
  const button = element("button", text, `row-button${danger ? " danger" : ""}`);
  button.type = "button";
  button.addEventListener("click", action);
  return button;
}

function openService(service = {}) {
  const form = $("#service-form");
  form.reset();
  ["id", "name", "budget_min", "budget_max"].forEach((key) => { form.elements[key].value = service[key] ?? ""; });
  $("#service-title").textContent = service.id ? "Редактирование услуги" : "Новая услуга";
  $("#service-message").textContent = "";
  $("#service-dialog").showModal();
}

async function loadServices() {
  services = await api("/api/services");
  const body = $("#services-body");
  body.replaceChildren();
  for (const service of services) {
    const row = element("tr");
    row.append(element("td", service.name), element("td", money.format(service.budget_min)), element("td", money.format(service.budget_max)));
    const actions = element("td");
    const wrap = element("div", "", "row-actions");
    wrap.append(rowButton("Изменить", () => openService(service)), rowButton("Удалить", async () => {
      if (!confirm(`Удалить услугу «${service.name}»?`)) return;
      try { await api(`/api/services/${service.id}`, { method: "DELETE" }); await loadServices(); }
      catch (error) { $("#workspace-message").textContent = error.message; }
    }, true));
    actions.append(wrap); row.append(actions); body.append(row);
  }
  if (!services.length) { const row = element("tr"); const cell = element("td", "Каталог пуст. Добавьте первую услугу."); cell.colSpan = 4; row.append(cell); body.append(row); }
}

$("#add-service").addEventListener("click", () => openService());
$("#service-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  const form = event.currentTarget;
  const id = form.elements.id.value;
  const payload = { name: form.elements.name.value, budget_min: Number(form.elements.budget_min.value), budget_max: Number(form.elements.budget_max.value) };
  const submit = form.querySelector("[type=submit]");
  submit.disabled = true;
  try {
    await api(id ? `/api/services/${id}` : "/api/services", { method: id ? "PUT" : "POST", body: JSON.stringify(payload) });
    $("#service-dialog").close(); await loadServices();
  } catch (error) { $("#service-message").textContent = error.message; }
  finally { submit.disabled = false; }
});

function summary(container, cards) {
  container.replaceChildren();
  cards.forEach(([title, value, caption]) => {
    const card = element("div", "", "summary-card");
    card.append(element("span", title), element("strong", String(value)), element("small", caption));
    container.append(card);
  });
}

async function showRequest(id) {
  try {
    const row = await api(`/api/requests/${encodeURIComponent(id)}`);
    const details = $("#request-details"); details.replaceChildren();
    const scoreBox = element("div", "", "score-box");
    scoreBox.append(element("span", `${labels[row.priority]} приоритет · ${row.score} баллов`, `badge ${row.priority}`));
    const reasons = element("ul"); row.reasons.forEach((reason) => reasons.append(element("li", reason)));
    scoreBox.append(reasons, element("p", row.personal_manager ? "Рекомендован персональный менеджер" : "Обычная очередь обработки"), element("p", `Направление: ${row.department}`));
    details.append(scoreBox);
    const list = element("dl", "", "detail-list");
    const fields = { id: "Номер", created_at: "Создана", status: "Статус", contact_name: "Имя", business_name: "Компания", business_niche: "Сфера", task_type: "Услуга", task_description: "Задача", expected_result: "Результат", budget: "Бюджет, ₽", deadline: "Срок", contact_email: "Email", contact_phone: "Телефон / Telegram", contact_method: "Способ связи", comments: "Комментарий" };
    Object.entries(fields).forEach(([key, title]) => list.append(element("dt", title), element("dd", row[key] == null ? "Не указано" : String(row[key]))));
    details.append(list); $("#request-dialog").showModal();
  } catch (error) { $("#workspace-message").textContent = error.message; }
}

async function loadRequests() {
  const data = await api(`/api/requests?skip=${requestOffset}&limit=100`);
  summary($("#priority-summary"), Object.keys(labels).map((key) => [labels[key], data.counts[key], "Обращений в очереди"]));
  $("#requests-count").textContent = `Всего: ${data.total}`;
  $("#page-label").textContent = data.total ? `${requestOffset + 1}–${Math.min(requestOffset + 100, data.total)} из ${data.total}` : "Заявок пока нет";
  $("#previous-page").disabled = requestOffset === 0;
  $("#next-page").disabled = requestOffset + 100 >= data.total;
  const body = $("#requests-body"); body.replaceChildren();
  data.items.forEach((item) => {
    const row = element("tr"); const contact = element("td", item.contact_name); contact.append(element("small", item.business_name || "Без компании"));
    const priority = element("td"); priority.append(element("span", `${labels[item.priority]} · ${item.score}`, `badge ${item.priority}`));
    const action = element("td"); action.append(rowButton("Просмотр →", () => showRequest(item.id)));
    row.append(contact, element("td", item.task_type), element("td", item.budget), element("td", item.deadline || "Не указан"), priority, action); body.append(row);
  });
}

$("#previous-page").addEventListener("click", () => { requestOffset = Math.max(0, requestOffset - 100); loadTab(); });
$("#next-page").addEventListener("click", () => { requestOffset += 100; loadTab(); });

function drawMap(canvas, points) {
  const ctx = canvas.getContext("2d"); const { width, height } = canvas;
  ctx.clearRect(0, 0, width, height); ctx.fillStyle = "#f6f4ed"; ctx.fillRect(0, 0, width, height);
  const padding = 45; const w = width - 2 * padding; const h = height - 2 * padding;
  ctx.font = "13px sans-serif";
  for (let i = 0; i <= 4; i++) {
    const x = padding + w * i / 4; const y = padding + h * i / 4;
    ctx.strokeStyle = "#ddd8ca"; ctx.beginPath(); ctx.moveTo(x, padding); ctx.lineTo(x, height - padding); ctx.moveTo(padding, y); ctx.lineTo(width - padding, y); ctx.stroke();
    ctx.fillStyle = "#64736b"; ctx.fillText(`${i * 25}%`, x - 12, height - 15); ctx.fillText(`${i * 25}%`, 4, y + 4);
  }
  points.forEach((point) => {
    const x = padding + point.x * w; const y = padding + point.y * h;
    const gradient = ctx.createRadialGradient(x, y, 0, x, y, 18);
    gradient.addColorStop(0, "rgba(196,110,43,.18)"); gradient.addColorStop(1, "rgba(198,164,95,0)");
    ctx.fillStyle = gradient; ctx.beginPath(); ctx.arc(x, y, 18, 0, Math.PI * 2); ctx.fill();
  });
  if (!points.length) { ctx.fillStyle = "#64736b"; ctx.fillText("Координаты пока не собраны", padding + 25, height / 2); }
}

async function loadAnalytics() {
  metricData = await api("/api/behavior-metrics");
  const periods = { day: "День · 24 часа", week: "Неделя · 7 дней", month: "Месяц · 30 дней" };
  summary($("#time-summary"), Object.entries(periods).map(([key, label]) => {
    const item = metricData.periods[key];
    return [label, `${item.average_seconds} с`, `Среднее · посещений: ${item.visits} · максимум: ${item.max_seconds} с`];
  }));
  $("#metric-period").textContent = metricData.period_definition;
  $("#map-caption").textContent = `Точек: ${metricData.points.length}. Карта по последним ${metricData.sample_rows} снимкам, максимум ${metricData.sample_limit}.`;
  drawMap($("#heatmap"), metricData.points);
  const list = $("#click-summary"); list.replaceChildren();
  Object.entries(metricData.clicks).sort((a, b) => b[1] - a[1]).forEach(([label, count]) => {
    const item = element("li"); item.append(element("span", label), element("strong", String(count))); list.append(item);
  });
  if (!list.children.length) list.append(element("li", "Нажатий пока нет"));
}

$("#expand-map").addEventListener("click", () => {
  if (!metricData) return;
  $("#map-dialog").showModal(); drawMap($("#large-heatmap"), metricData.points);
});
document.querySelectorAll(".close-dialog").forEach((button) => button.addEventListener("click", () => button.closest("dialog").close()));

async function loadTab() {
  $("#workspace-message").textContent = "";
  $("#refresh").disabled = true;
  try { await ({ services: loadServices, requests: loadRequests, analytics: loadAnalytics })[currentTab](); }
  catch (error) { $("#workspace-message").textContent = error.message; }
  finally { $("#refresh").disabled = false; }
}
document.querySelectorAll("[data-tab]").forEach((button) => button.addEventListener("click", () => {
  currentTab = button.dataset.tab;
  document.querySelectorAll("[data-tab]").forEach((tab) => tab.setAttribute("aria-selected", String(tab === button)));
  ["services", "requests", "analytics"].forEach((tab) => { $(`#${tab}-view`).hidden = tab !== currentTab; });
  loadTab();
}));
$("#refresh").addEventListener("click", loadTab);
checkRegistration();
