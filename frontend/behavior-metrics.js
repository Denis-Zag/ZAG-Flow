"use strict";

(() => {
  const sessionId = crypto.randomUUID();
  const clicks = {};
  let duration = 0;
  let sequence = 1;
  let pointer = null;
  let pending = null;
  let sending = false;
  let elapsedMs = 0;
  let activeStart = document.hidden ? null : performance.now();

  document.addEventListener("visibilitychange", () => {
    if (document.hidden && activeStart !== null) {
      elapsedMs += performance.now() - activeStart;
      activeStart = null;
    } else if (!document.hidden && activeStart === null) {
      activeStart = performance.now();
    }
  });

  document.addEventListener("pointermove", (event) => {
    pointer = { x: event.clientX, y: event.clientY };
  }, { passive: true });
  document.addEventListener("click", (event) => {
    const target = event.target.closest("button, a");
    if (!target) return;
    // Содержимое полей и текст, введённый посетителем, не используются.
    const label = target.hasAttribute("data-next") ? "Следующий шаг"
      : target.hasAttribute("data-back") ? "Предыдущий шаг"
      : target.type === "submit" ? "Отправить заявку"
      : (target.getAttribute("aria-label") || target.textContent).trim().replace(/\s+/g, " ").slice(0, 80);
    if (label && (label in clicks || Object.keys(clicks).length < 40)) clicks[label] = (clicks[label] || 0) + 1;
  });

  function sample() {
    const page = document.documentElement;
    const clamp = (value) => Math.max(0, Math.min(1, value));
    const point = pointer ? [{
      x: clamp((pointer.x + window.scrollX) / Math.max(page.scrollWidth, 1)),
      y: clamp((pointer.y + window.scrollY) / Math.max(page.scrollHeight, 1)),
    }] : [];
    return { session_id: sessionId, sequence, time_on_page: duration,
      buttons_clicked: { ...clicks }, cursor_positions: point };
  }

  async function tick() {
    if (document.hidden || duration >= 86400) return;
    duration = Math.min(86400, Math.floor((elapsedMs + (activeStart === null ? 0 : performance.now() - activeStart)) / 1000));
    if (sending) return;
    if (!pending) pending = sample();
    sending = true;
    try {
      const response = await fetch("/api/behavior-metrics", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify(pending), signal: AbortSignal.timeout(5000),
      });
      if (response.ok) { pending = null; sequence += 1; }
    } catch {
      // Повторяем тот же снимок; уникальная пара session_id/sequence не даст дубль.
    } finally { sending = false; }
  }
  window.setInterval(tick, 1000);
  window.addEventListener("pagehide", () => {
    if (!duration) return;
    const payload = pending || sample();
    navigator.sendBeacon("/api/behavior-metrics", new Blob([JSON.stringify(payload)], { type: "application/json" }));
  });
})();
