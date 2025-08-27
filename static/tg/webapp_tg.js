// /static/tg/webapp_tg.js
(function(){
  const tg = window.Telegram?.WebApp;

  // --- язык из ?lang=... (бот его проставляет) ---
  try {
    const p = new URLSearchParams(location.search);
    const L = p.get("lang");
    if (L) localStorage.setItem("gjh_lang", L);
  } catch (_) {}

  // --- настройки ---
  const REMOTIVE_URL = "https://remotive.com/accelerator?ref=YOUR_ID"; // подставь рефку
  const SHOW_REMOTIVE = true;
  const REMOTIVE_AFTER_N_SECONDS = 20; // показ через N сек после старта

  let currentSearchId = null;
  let pollTimer = null;
  let bannerTimer = null;

  // --- утилиты ---
  const $ = (s) => document.querySelector(s);
  const $$ = (s) => Array.from(document.querySelectorAll(s));

  function setStatus(text){
    const el = $("#status");
    if (el) el.textContent = text;
  }

  function disableUI(searching){
    const btnSearch = $("#btnSearch");
    const btnStop = $("#btnStop");
    if (btnSearch) btnSearch.disabled = searching;
    if (btnStop) btnStop.disabled = !searching;
  }

  function getSelectedJobs(){
    return $$(".job-check:checked").map(i => i.value);
  }
  function getSelectedCountries(){
    return $$(".country-check:checked").map(i => i.value);
  }

  function renderProgress(data){
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
      <div class="muted">Найдено вакансий: <b>${jobsCount}</b></div>
      ${items || '<div class="muted">Источники в очереди…</div>'}
    `;
  }

  function showOpenResults(url){
  const t = document.querySelector("#open-results");
  if (t) {
    t.innerHTML = `
      <a class="btn btn-success w-100" id="open-inplace" href="${url}">Открыть результаты</a>
      <div class="muted mt-1">Совет: полнофункциональная версия с карточками, фильтрами, сортировкой и e-mail — на сайте.</div>
    `;
    // внутри Telegram-окна — переходим по ссылке, НЕ открываем внешний браузер
    const link = document.getElementById("open-inplace");
    link.addEventListener("click", (e) => {
      e.preventDefault();
      // просто меняем location внутри той же webview — сессия сохранится
      window.location.href = url; 
    });
  }

  // НИЧЕГО НЕ ДЕЛАТЬ: НЕ вызывать tg.openLink(url) — он откроет внешний браузер и потеряет куку
  // try { if (tg?.openLink) tg.openLink(url); } catch(_) {}
}


  function showRemotiveLater(){
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

  // --- действия ---
  async function startSearch(ev){
    if (ev) ev.preventDefault();

    const jobs = getSelectedJobs();
    const countries = getSelectedCountries();
    const is_refugee = $("#is_refugee")?.checked || false;

    if (!jobs.length) {
      setStatus("Выберите хотя бы одну профессию.");
      return;
    }
    if (!countries.length) {
      setStatus("Выберите хотя бы одну страну.");
      return;
    }

    disableUI(true);
    setStatus("Запускаем поиск…");
    $("#open-results").innerHTML = "";
    $("#progress").innerHTML = "";

    const payload = {
      is_refugee: is_refugee,
      selected_jobs: jobs,
      countries: countries,
      city: ""
    };

    let resp, data;
    try {
      resp = await fetch("/search/start", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload)
      });
      data = await resp.json();
    } catch (e) {
      setStatus("Сеть недоступна. Повторите позже.");
      disableUI(false);
      return;
    }

    if (!resp.ok || !data?.ok) {
      setStatus(data?.error || "Ошибка старта поиска.");
      disableUI(false);
      return;
    }

    currentSearchId = data.search_id;
    setStatus("Ищем…");
    showRemotiveLater();
    pollProgress();
  }

  async function pollProgress(){
    if (!currentSearchId) return;
    let data;
    try {
      const resp = await fetch(`/search/progress?id=${encodeURIComponent(currentSearchId)}`);
      data = await resp.json();
    } catch (e) {
      setStatus("Ошибка сети при получении прогресса.");
      finalize();
      return;
    }

    if (data?.error) {
      setStatus(data.error);
      finalize();
      return;
    }

    renderProgress(data);

    if (data?.redirect_url) {
      setStatus("Готово. Открываем результаты…");
      showOpenResults(data.redirect_url);
      finalize();
      return;
    }

    clearTimeout(pollTimer);
    pollTimer = setTimeout(pollProgress, 1200);
  }

  async function stopSearch(){
    if (!currentSearchId) return;
    disableUI(false);
    setStatus("Останавливаем поиск…");

    let data;
    try {
      const resp = await fetch("/search/stop", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ search_id: currentSearchId })
      });
      data = await resp.json();
    } catch (e) {
      setStatus("Ошибка сети при остановке.");
      finalize(true);
      return;
    }

    if (data?.redirect_url) {
      showOpenResults(data.redirect_url);
    }
    setStatus("Остановлено.");
    finalize(true);
  }

  function finalize(reset=false){
    disableUI(false);
    clearTimeout(pollTimer);
    clearTimeout(bannerTimer);
    if (reset) currentSearchId = null;
  }

  // --- мини-переключатель языка (для самой WebApp) ---
  document.addEventListener("click", (e) => {
    const btn = e.target.closest("button[data-lang]");
    if (!btn) return;
    const lang = btn.getAttribute("data-lang");
    try { localStorage.setItem("gjh_lang", lang); } catch(_) {}
    // простейший визуальный отклик
    btn.classList.add("btn-secondary");
    setTimeout(() => location.href = `?lang=${lang}`, 150);
  });

  // --- события ---
  document.addEventListener("DOMContentLoaded", () => {
    $("#btnSearch")?.addEventListener("click", startSearch);
    $("#btnStop")?.addEventListener("click", stopSearch);
    // инициализация
    setStatus("Готово к поиску");
  });
})();
