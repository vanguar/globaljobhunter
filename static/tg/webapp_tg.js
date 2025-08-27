// static/tg/webapp_tg.js
(function(){
  const tg = window.Telegram?.WebApp;
  const API_BASE = location.origin; // https://globaljobhunter.vip

  // НАСТРОЙКА
  const FULL_SITE_URL = "https://globaljobhunter.vip";                     // ссылка на полный сайт
  const REMOTIVE_REF_URL = "https://remotive.com/accelerator?ref=YOUR_ID"; // ← подставь свою рефку
  const SHOW_REMOTIVE = true;           // включить/выключить баннер
  const REMOTIVE_AFTER_N_JOBS = 8;      // показать баннер после N карточек

  let currentSearchId = null;
  let pollTimer = null;
  let jobsRendered = 0;
  let bannerShown = false;

  document.addEventListener("DOMContentLoaded", () => {
    const btnSearch = document.getElementById('btnSearch');
    const btnStop = document.getElementById('btnStop');
    const fullSiteLink = document.getElementById('full-site-link');
    const remLink = document.getElementById('remotive-link');

    if (fullSiteLink) fullSiteLink.href = FULL_SITE_URL;
    if (remLink) remLink.href = REMOTIVE_REF_URL;

    btnSearch?.addEventListener('click', startSearch);
    btnStop?.addEventListener('click', stopSearch);

    if (tg) {
      tg.BackButton.show();
      tg.BackButton.onClick(() => tg.close());
    }
  });

  function setStatus(t){ const el = document.getElementById('status'); if (el) el.textContent = t || ""; }
  function t(key, fallback){
    const map = {
      apply: { en: "Apply", uk: "Відгукнутись", ru: "Отклик" },
      searching: { en: "Starting search…", uk: "Починаємо пошук…", ru: "Стартуем поиск…" },
      in_progress: { en: "Searching…", uk: "Йде пошук…", ru: "Идёт поиск…" },
      start_error: { en: "Failed to start search", uk: "Не вдалося почати пошук", ru: "Ошибка запуска поиска" },
      network_error: { en: "Network error, try again", uk: "Помилка мережі, спробуйте ще", ru: "Сетевая ошибка, попробуйте снова" },
      done: { en: "Done", uk: "Готово", ru: "Готово" },
      stopped: { en: "Stopped", uk: "Зупинено", ru: "Остановлено" }
    };
    const lang = localStorage.getItem("gjh_lang") || "en";
    return (map[key] && map[key][lang]) || fallback || key;
  }
  function escapeHTML(s){
    return String(s).replace(/[&<>"']/g, m => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[m]));
  }

  function addJobs(jobs){
    const wrap = document.getElementById('list');
    if (!wrap) return;
    for(const j of (jobs || [])){
      const card = document.createElement('div');
      card.className = 'job';
      card.innerHTML = `
        <div class="d-flex justify-content-between align-items-start">
          <div>
            <div class="fw-semibold">${escapeHTML(j.title || "")}</div>
            <div class="muted">${escapeHTML(j.company || "")} · ${escapeHTML(j.location || "")}</div>
          </div>
          <a class="btn btn-sm btn-outline-primary" href="${j.apply_url}" target="_blank" rel="noopener">${t('apply','Apply')}</a>
        </div>
        <div class="muted mt-1">${escapeHTML(j.source || "")}${j.posted_date ? " · " + escapeHTML(j.posted_date) : ""}</div>
      `;
      wrap.appendChild(card);
      jobsRendered++;
      maybeShowRemotiveBanner();
    }
  }

  function maybeShowRemotiveBanner(){
    if (!SHOW_REMOTIVE || bannerShown) return;
    if (jobsRendered >= REMOTIVE_AFTER_N_JOBS) {
      const banner = document.getElementById('remotive-banner');
      if (banner) { banner.style.display = "block"; bannerShown = true; }
    }
  }
  function showRemotiveIfNotShown(){
    if (!SHOW_REMOTIVE || bannerShown) return;
    const banner = document.getElementById('remotive-banner');
    if (banner) { banner.style.display = "block"; bannerShown = true; }
  }

  async function startSearch(){
    const qEl = document.getElementById('q');
    const countryEl = document.getElementById('country');
    const btnSearch = document.getElementById('btnSearch');
    const btnStop = document.getElementById('btnStop');
    const listEl = document.getElementById('list');

    jobsRendered = 0; bannerShown = false;
    if (listEl) listEl.innerHTML = "";
    setStatus(t('searching','Starting search…'));
    if (btnSearch) btnSearch.disabled = true;
    if (btnStop) btnStop.disabled = false;

    const payload = {
      country: countryEl?.value || null,
      query: (qEl?.value || "").trim() || null
      // при необходимости добавь поля под твой бэк (selected_jobs, languages…)
    };

    try{
      const r = await fetch(`${API_BASE}/search/start`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-TG-InitData": tg?.initData || ""
        },
        body: JSON.stringify(payload)
      });
      const data = await r.json();
      if(!r.ok || !data.search_id){
        setStatus(t('start_error','Failed to start search'));
        if (btnSearch) btnSearch.disabled = false;
        if (btnStop) btnStop.disabled = true;
        return;
      }
      currentSearchId = data.search_id;
      setStatus(t('in_progress','Searching…'));
      poll();
    }catch(e){
      setStatus(t('network_error','Network error, try again'));
      if (btnSearch) btnSearch.disabled = false;
      if (btnStop) btnStop.disabled = true;
    }
  }

  async function poll(){
    if(!currentSearchId) return;
    try{
      const r = await fetch(`${API_BASE}/search/progress?id=${encodeURIComponent(currentSearchId)}`, {
        headers: { "X-TG-InitData": tg?.initData || "" }
      });
      const data = await r.json();

      if(Array.isArray(data.new_jobs) && data.new_jobs.length){
        addJobs(data.new_jobs);
      }
      if(data.status === "done"){
        setStatus(t('done','Done'));
        finalize();
        showRemotiveIfNotShown(); // если результатов мало — показать баннер в конце
        return;
      }
      if(currentSearchId) pollTimer = setTimeout(poll, 1200);
    }catch(e){
      // мягкий ретрай
      pollTimer = setTimeout(poll, 2000);
    }
  }

  async function stopSearch(){
    if(!currentSearchId) return finalize(true);
    try{
      await fetch(`${API_BASE}/search/stop`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-TG-InitData": tg?.initData || ""
        },
        body: JSON.stringify({ search_id: currentSearchId })
      });
    }catch(_) {}
    setStatus(t('stopped','Stopped'));
    finalize(true);
  }

  function finalize(resetId=false){
    const btnSearch = document.getElementById('btnSearch');
    const btnStop = document.getElementById('btnStop');
    if (btnSearch) btnSearch.disabled = false;
    if (btnStop) btnStop.disabled = true;
    if (resetId) currentSearchId = null;
    clearTimeout(pollTimer);
  }
})();
