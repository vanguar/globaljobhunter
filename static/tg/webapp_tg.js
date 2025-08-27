// /static/tg/webapp_tg.js
// Мини-клиент поиска для Telegram WebApp.
// Делает старт поиска -> поллит прогресс -> открывает /results в той же webview.
// Прокидывает текущий язык в redirect_url (?lang=..). Не открывает внешний браузер.

(function(){
  const tg = window.Telegram?.WebApp;

  // --- helpers ---
  const $  = (s) => document.querySelector(s);
  const $$ = (s) => Array.from(document.querySelectorAll(s));
  const getLang = () => {
    try {
      const p = new URLSearchParams(location.search);
      return p.get("lang") || localStorage.getItem("gjh_lang") || "ru";
    } catch(_) { return "ru"; }
  };

  // --- состояние ---
  let currentSearchId = null;
  let pollTimer = null;
  let bannerTimer = null;

  // --- баннер Remotive (по желанию) ---
  const REMOTIVE_URL = "https://remotive.com/accelerator?ref=YOUR_ID"; // подставь свой рефкод
  const SHOW_REMOTIVE = true;
  const REMOTIVE_AFTER_N_SECONDS = 20;

  // --- UI ---
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

  function getSelectedJobs(){      return $$(".job-check:checked").map(i => i.value); }
  function getSelectedCountries(){ return $$(".country-check:checked").map(i => i.value); }

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
    const t = $("#open-results");
    if (!t) return;

    t.innerHTML = `
      <a class="btn btn-success w-100" id="open-inplace" href="${url}">Открыть результаты</a>
      <div class="muted mt-1">Полная версия: карточки, фильтры, сортировка и e-mail.</div>
    `;

    // Открываем результаты в ТЕКУЩЕМ webview, чтобы не потерять сессию/куки
    $("#open-inplace")?.addEventListener("click", (e) => {
      e.preventDefault();
      window.location.href = url;
    });

    // НИЧЕГО не делаем через tg.openLink — внешний браузер потеряет cookie
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
      // язык серверу не обязателен, но если хочешь — раскомментируй:
      // , lang: getLang()
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
      // Прокинем текущий язык в redirect_url
      const lang = getLang();
      const u = new URL(data.redirect_url, location.origin);
      u.searchParams.set("lang", lang);

      setStatus("Готово. Открываем результаты…");
      showOpenResults(u.toString());
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

    const lang = getLang();
    if (data?.redirect_url) {
      const u = new URL(data.redirect_url, location.origin);
      u.searchParams.set("lang", lang);
      showOpenResults(u.toString());
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

  // --- привязки событий ---
  document.addEventListener("DOMContentLoaded", () => {
    $("#btnSearch")?.addEventListener("click", startSearch);
    $("#btnStop")?.addEventListener("click",  stopSearch);
    setStatus("Готово к поиску");
  });

  // Язык: клики обрабатывает localization_tg.js (и .lang-btn, и [data-lang]).
  // Здесь доп. логики по смене языка нет, чтобы не конфликтовать.
})();
