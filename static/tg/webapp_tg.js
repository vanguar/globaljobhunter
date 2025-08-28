// /static/tg/webapp_tg.js
// Telegram WebApp клиент поиска: старт -> прогресс -> открыть /results в этой же webview.
// ГЛАВНОЕ: всегда держим и применяем текущий язык (?lang=..), слушаем клики по data-lang.

(function () {
  "use strict";

  const tg = window.Telegram?.WebApp;

  // ---------- helpers ----------
  const $  = (s) => document.querySelector(s);
  const $$ = (s) => Array.from(document.querySelectorAll(s));

  const normalizeLang = (code) => {
    const c = String(code || "ru").toLowerCase();
    return c === "ua" ? "uk" : c;
  };

  // URL <-> localStorage('gjh_lang')
  const getLang = () => {
    try {
      const p = new URLSearchParams(location.search);
      const urlLang = p.get("lang");
      if (urlLang) return normalizeLang(urlLang);
    } catch (_) {}
    try {
      const saved = localStorage.getItem("gjh_lang");
      if (saved) return normalizeLang(saved);
    } catch (_) {}
    return "ru";
  };

  // На старте — синхронизируем URL с текущим языком (без перезагрузки)
  (function ensureLangParam() {
    const lang = getLang();
    try {
      const u = new URL(location.href);
      if (u.searchParams.get("lang") !== lang) {
        u.searchParams.set("lang", lang);
        history.replaceState(null, "", u.toString());
      }
      try { localStorage.setItem("gjh_lang", lang); } catch (_) {}
    } catch (_) {}
  })();

  // Добавить/заменить ?lang= в любом URL
  const withLang = (url) => {
    try {
      const u = new URL(url, location.origin);
      u.searchParams.set("lang", getLang());
      return u.toString();
    } catch {
      return url;
    }
  };

  // Локальный i18n только для текста, который генерит ЭТОТ файл
  const I18N = {
    ru: {
      ready: "Готово к поиску",
      start: "Запускаем поиск…",
      searching: "Ищем…",
      results_opening: "Готово. Открываем результаты…",
      choose_job: "Выберите хотя бы одну профессию.",
      choose_country: "Выберите хотя бы одну страну.",
      net_error: "Сеть недоступна. Повторите позже.",
      poll_net_error: "Ошибка сети при получении прогресса.",
      stop_net_error: "Ошибка сети при остановке.",
      stopped: "Остановлено.",
      found: "Найдено вакансий:",
      sources_queue: "Источники в очереди…",
      open_results: "Открыть результаты",
      full_ver_hint: "Полная версия: карточки, фильтры, сортировка и e-mail."
    },
    uk: {
      ready: "Готово до пошуку",
      start: "Запускаємо пошук…",
      searching: "Шукаємо…",
      results_opening: "Готово. Відкриваємо результати…",
      choose_job: "Оберіть хоча б одну професію.",
      choose_country: "Оберіть хоча б одну країну.",
      net_error: "Мережа недоступна. Спробуйте пізніше.",
      poll_net_error: "Помилка мережі під час отримання прогресу.",
      stop_net_error: "Помилка мережі під час зупинки.",
      stopped: "Зупинено.",
      found: "Знайдено вакансій:",
      sources_queue: "Джерела в черзі…",
      open_results: "Відкрити результати",
      full_ver_hint: "Повна версія: картки, фільтри, сортування та e-mail."
    },
    en: {
      ready: "Ready to search",
      start: "Starting search…",
      searching: "Searching…",
      results_opening: "Done. Opening results…",
      choose_job: "Select at least one profession.",
      choose_country: "Select at least one country.",
      net_error: "Network unavailable. Try again later.",
      poll_net_error: "Network error while polling progress.",
      stop_net_error: "Network error while stopping.",
      stopped: "Stopped.",
      found: "Jobs found:",
      sources_queue: "Sources in queue…",
      open_results: "Open results",
      full_ver_hint: "Full version: cards, filters, sorting & e-mail."
    }
  };
  const t = (key) => (I18N[getLang()]?.[key] ?? I18N.ru[key] ?? key);

  // ---------- состояние ----------
  let currentSearchId = null;
  let pollTimer = null;
  let bannerTimer = null;

  // ---------- Remotive banner (по желанию) ----------
  const REMOTIVE_URL = "https://remotive.com/accelerator?ref=YOUR_ID";
  const SHOW_REMOTIVE = true;
  const REMOTIVE_AFTER_N_SECONDS = 20;

  // ---------- UI ----------
  function setStatus(text) {
    const el = $("#status");
    if (el) el.textContent = text;
  }

  function disableUI(searching) {
    const btnSearch = $("#btnSearch");
    const btnStop = $("#btnStop");
    if (btnSearch) btnSearch.disabled = searching;
    if (btnStop) btnStop.disabled = !searching;
  }

  function getSelectedJobs()      { return $$(".job-check:checked").map(i => i.value); }
  function getSelectedCountries() { return $$(".country-check:checked").map(i => i.value); }

  function renderProgress(data) {
    const box = $("#progress");
    if (!box) return;

    const statuses = data?.sites_status || {};
    const items = Object.entries(statuses).map(([name, st]) => {
      let cls = "status-pending";
      if (st === "active") cls = "status-active";
      else if (st === "done") cls = "status-done";
      else if (st === "error") cls = "status-error";
      return `<div class="d-flex justify-content-between border rounded p-2 mb-1">
        <div>${name}</div>
        <div class="status-pill ${cls}">${st}</div>
      </div>`;
    }).join("");

    const jobsCount = data?.jobs_found ?? 0;
    box.innerHTML = `
      <div class="muted">${t("found")} <b>${jobsCount}</b></div>
      ${items || `<div class="muted">${t("sources_queue")}</div>`}
    `;
  }

  // ---------- прогресс ----------
  async function pollProgress() {
    if (!currentSearchId) return;

    try {
      const resp = await fetch(`/search/progress?id=${encodeURIComponent(currentSearchId)}`);
      const data = await resp.json();

      if (data?.error) {
        console.error("[WebApp] progress error:", data.error);
        setStatus(data.error);
        finalize();
        return;
      }

      renderProgress(data);

      if (data?.redirect_url) {
        const finalUrl = withLang(data.redirect_url);
        setStatus(t("results_opening"));
        showOpenResults(finalUrl);
        finalize();
        return;
      }

      clearTimeout(pollTimer);
      pollTimer = setTimeout(pollProgress, 1200);
    } catch (e) {
      console.error("[WebApp] poll error:", e);
      setStatus(t("poll_net_error"));
      finalize();
    }
  }

  // Кнопка "Открыть результаты" внутри WebApp (в этой же webview)
  function showOpenResults(url) {
    const tEl = $("#open-results");
    if (!tEl) return;

    const finalUrl = withLang(url);
    const btnText = t("open_results");
    const hint    = t("full_ver_hint");

    tEl.innerHTML = `
      <a class="btn btn-success w-100" id="open-inplace" href="${finalUrl}">${btnText}</a>
      <div class="muted mt-1">${hint}</div>
    `;

    $("#open-inplace")?.addEventListener("click", (e) => {
      e.preventDefault();
      try {
        if (tg?.openLink) {
          tg.openLink(finalUrl, { try_instant_view: false });
        } else {
          location.href = finalUrl;
        }
      } catch {
        location.href = finalUrl;
      }
    });
  }

  function showRemotiveLater() {
    if (!SHOW_REMOTIVE) return;
    clearTimeout(bannerTimer);
    bannerTimer = setTimeout(() => {
      const b = $("#remotive-banner");
      const a = $("#remotive-link");
      if (b && a) {
        a.href = REMOTIVE_URL;
        b.style.display = "block";
      }
    }, REMOTIVE_AFTER_N_SECONDS * 1000);
  }

  // ---------- действия ----------
  async function startSearch(ev) {
    if (ev) ev.preventDefault();

    const jobs = getSelectedJobs();
    const countries = getSelectedCountries();
    const is_refugee = $("#is_refugee")?.checked || false;

    if (!jobs.length) {
      setStatus(t("choose_job"));
      return;
    }
    if (!countries.length) {
      setStatus(t("choose_country"));
      return;
    }

    disableUI(true);
    setStatus(t("start"));
    $("#open-results").innerHTML = "";
    $("#progress").innerHTML = "";

    const payload = {
      is_refugee,
      selected_jobs: jobs,
      countries,
      city: ""
      // можно добавить: lang: getLang()
    };

    try {
      const resp = await fetch("/search/start", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload)
      });
      const data = await resp.json();

      if (!resp.ok || !data?.ok || !data?.search_id) {
        console.error("[WebApp] start error:", data);
        setStatus(data?.error || "Ошибка старта поиска.");
        disableUI(false);
        return;
      }

      currentSearchId = data.search_id;
      setStatus(t("searching"));
      showRemotiveLater();
      pollProgress();
    } catch (e) {
      console.error("[WebApp] start network error:", e);
      setStatus(t("net_error"));
      disableUI(false);
    }
  }

  async function stopSearch() {
    if (!currentSearchId) return;
    disableUI(false);
    setStatus("Останавливаем поиск…");

    try {
      const resp = await fetch("/search/stop", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ search_id: currentSearchId })
      });
      const data = await resp.json();

      const url = data?.redirect_url ? withLang(data.redirect_url) : null;
      if (url) showOpenResults(url);

      setStatus(t("stopped"));
      finalize(true);
    } catch (e) {
      console.error("[WebApp] stop network error:", e);
      setStatus(t("stop_net_error"));
      finalize(true);
    }
  }

  function finalize(reset = false) {
    disableUI(false);
    clearTimeout(pollTimer);
    clearTimeout(bannerTimer);
    if (reset) currentSearchId = null;
  }

  // ---------- события ----------
  document.addEventListener("DOMContentLoaded", () => {
    // Кнопки
    $("#btnSearch")?.addEventListener("click", startSearch);
    $("#btnStop")?.addEventListener("click",  stopSearch);
    setStatus(t("ready"));

    // Переключение языка (если вдруг localization_tg.js не отработал)
    document.addEventListener("click", (e) => {
      const el = e.target.closest('.dropdown-item[data-lang], .lang-option[data-lang], [data-lang].dropdown-item');
      if (!el) return;
      e.preventDefault();
      const code = normalizeLang(el.getAttribute("data-lang") || "ru");
      try { localStorage.setItem("gjh_lang", code); } catch (_) {}
      const u = new URL(location.href);
      u.searchParams.set("lang", code);
      location.href = u.toString(); // намеренно перезагружаем, чтобы подтянулись переводы
    });

    console.log("[WebApp] Init language =", getLang());
  });

})();
