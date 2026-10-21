"use strict";

const header = document.querySelector("[data-header]");
const menuButton = document.querySelector(".menu-button");
const navigation = document.querySelector("#site-nav");
const revealItems = document.querySelectorAll(".reveal");

const updateHeader = () => header?.classList.toggle("is-scrolled", window.scrollY > 20);
updateHeader();
window.addEventListener("scroll", updateHeader, { passive: true });

menuButton?.addEventListener("click", () => {
  const isOpen = navigation.classList.toggle("is-open");
  menuButton.setAttribute("aria-expanded", String(isOpen));
});

navigation?.querySelectorAll("a").forEach((link) => {
  link.addEventListener("click", () => {
    navigation.classList.remove("is-open");
    menuButton?.setAttribute("aria-expanded", "false");
  });
});

if ("IntersectionObserver" in window) {
  const observer = new IntersectionObserver(
    (entries) => {
      entries.forEach((entry) => {
        if (entry.isIntersecting) {
          entry.target.classList.add("is-visible");
          observer.unobserve(entry.target);
        }
      });
    },
    { threshold: 0.12 }
  );
  revealItems.forEach((item) => observer.observe(item));
} else {
  revealItems.forEach((item) => item.classList.add("is-visible"));
}

const form = document.querySelector("#request-form");

if (form) {
  const steps = Array.from(form.querySelectorAll("[data-step]"));
  const nextButton = form.querySelector("[data-next]");
  const backButton = form.querySelector("[data-back]");
  const submitButton = form.querySelector("[data-submit]");
  const status = form.querySelector("[data-form-status]");
  const progressBar = document.querySelector("[data-progress-bar]");
  const progressValue = document.querySelector("[data-progress-value]");
  const stepTitle = document.querySelector("#step-title");
  const successState = document.querySelector("[data-success]");
  const requestId = document.querySelector("[data-request-id]");
  const newRequestButton = document.querySelector("[data-new-request]");
  let currentStep = 0;

  const setStatus = (message = "", type = "error") => {
    status.textContent = message;
    status.style.color = type === "success" ? "var(--accent-soft)" : "var(--danger)";
  };

  const showStep = (index) => {
    currentStep = index;
    steps.forEach((step, stepIndex) => {
      const isCurrent = stepIndex === index;
      step.hidden = !isCurrent;
      step.classList.toggle("is-active", isCurrent);
    });

    const progress = Math.round(((index + 1) / steps.length) * 100);
    progressBar.style.width = `${progress}%`;
    progressValue.textContent = `${progress}%`;
    stepTitle.textContent = `Шаг ${index + 1} из ${steps.length}`;
    backButton.hidden = index === 0;
    nextButton.hidden = index === steps.length - 1;
    submitButton.hidden = index !== steps.length - 1;
    setStatus();
  };

  const validateStep = (index) => {
    const step = steps[index];
    const fields = Array.from(step.querySelectorAll("input, textarea, select"));
    let firstInvalid = null;

    fields.forEach((field) => {
      field.removeAttribute("aria-invalid");
      if (!field.checkValidity()) {
        field.setAttribute("aria-invalid", "true");
        firstInvalid ??= field;
      }
    });

    const requiredRadio = step.querySelector('input[type="radio"][required]');
    if (requiredRadio && !step.querySelector('input[type="radio"]:checked')) {
      firstInvalid ??= requiredRadio;
    }

    if (firstInvalid) {
      setStatus("Проверьте обязательные поля этого шага.");
      firstInvalid.focus({ preventScroll: true });
      firstInvalid.closest(".choice-grid, .field, .consent")?.scrollIntoView({ behavior: "smooth", block: "center" });
      return false;
    }
    return true;
  };

  nextButton.addEventListener("click", () => {
    if (validateStep(currentStep)) showStep(Math.min(currentStep + 1, steps.length - 1));
  });

  backButton.addEventListener("click", () => showStep(Math.max(currentStep - 1, 0)));

  form.addEventListener("input", (event) => {
    event.target.removeAttribute("aria-invalid");
    setStatus();
  });

  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    if (!validateStep(currentStep)) return;

    const data = Object.fromEntries(new FormData(form).entries());
    data.consent = data.consent === "on";
    data.source = "zag-flow-landing";

    submitButton.disabled = true;
    submitButton.textContent = "Отправляем…";
    setStatus("Отправляем заявку…", "success");

    try {
      const response = await fetch("/api/requests", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(data),
      });
      const payload = await response.json().catch(() => ({}));

      if (!response.ok) {
        throw new Error(payload.detail || "Не удалось отправить заявку.");
      }

      form.hidden = true;
      successState.hidden = false;
      requestId.textContent = payload.request_id;
      setStatus();
      successState.focus?.();
    } catch (error) {
      setStatus(error.message || "Сервис временно недоступен. Попробуйте ещё раз позже.");
    } finally {
      submitButton.disabled = false;
      submitButton.innerHTML = 'Отправить заявку <span aria-hidden="true">↗</span>';
    }
  });

  newRequestButton?.addEventListener("click", () => {
    form.reset();
    form.hidden = false;
    successState.hidden = true;
    showStep(0);
  });

  showStep(0);
}
