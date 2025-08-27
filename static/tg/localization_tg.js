// static/tg/localization_tg.js
// --- автоподхват языка из ?lang=... ---
(function(){
  const params = new URLSearchParams(location.search);
  const urlLang = params.get("lang");
  if (urlLang) localStorage.setItem("gjh_lang", urlLang);
})();


(function(){
  const LS_KEY = "gjh_lang";
  let currentLang = localStorage.getItem(LS_KEY) || null;
  let translations = {};

  window.GJH_TG_I18N = { setLang, applyNow: applyTranslations };

  document.addEventListener("DOMContentLoaded", async () => {
    if (currentLang) {
      await loadLanguage(currentLang);
      showMainStep();
    }
    wireLanguageButtons();
  });

  function wireLanguageButtons(){
    document.querySelectorAll(".lang-btn").forEach(btn => {
      btn.addEventListener("click", async () => {
        const lang = btn.dataset.lang;
        await setLang(lang);
        showMainStep();
      });
    });
  }

  function showMainStep(){
    const langStep = document.getElementById("lang-step");
    const mainStep = document.getElementById("main-step");
    if (langStep) langStep.style.display = "none";
    if (mainStep) mainStep.style.display = "block";
  }

  async function setLang(lang){
    localStorage.setItem(LS_KEY, lang);
    currentLang = lang;
    await loadLanguage(lang);
  }

  async function loadLanguage(lang){
    try {
      const resp = await fetch(`/static/${lang}.json`, { cache: "no-store" });
      translations = await resp.json();
      applyTranslations();
    } catch (e) {
      console.error("Translation load failed", e);
    }
  }

  function applyTranslations(){
    document.querySelectorAll("[data-i18n]").forEach(el => {
      const key = el.getAttribute("data-i18n");
      if (translations[key]) el.innerHTML = translations[key];
    });
  }
})();
