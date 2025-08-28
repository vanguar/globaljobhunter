// /static/tg/localization_tg.js
(function () {
  const LS_KEY = "gjh_lang";
  const SUPPORTED = ["ru", "en", "uk"];

  const normalize = (code) => {
    const c = String(code || "ru").toLowerCase();
    if (c === "ua") return "uk";
    return SUPPORTED.includes(c) ? c : "ru";
  };

  let currentLang = null;
  let translations = {};

  function getInitialLang() {
    try {
      const p = new URLSearchParams(location.search);
      const urlLang = p.get("lang");
      if (urlLang) return normalize(urlLang);
    } catch (_) {}
    try {
      const saved = localStorage.getItem(LS_KEY);
      if (saved) return normalize(saved);
    } catch (_) {}
    return "ru";
  }

  function writeLangToUrl(lang) {
    try {
      const u = new URL(location.href);
      u.searchParams.set("lang", lang);
      history.replaceState({}, "", u.toString());
    } catch (_) {}
  }

  async function loadAndApply(lang) {
    const code = normalize(lang);
    try {
      const res = await fetch(`/static/${code}.json`, { cache: "no-cache" });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      translations = await res.json();
      console.log("[i18n] Loaded", code);
      applyTranslations();
    } catch (e) {
      console.error("[i18n] loadLanguage failed", code, e);
    }
  }

  function applyTranslations() {
    document.querySelectorAll("[data-i18n]").forEach((el) => {
      const key = el.getAttribute("data-i18n");
      if (!key) return;

      if (key.startsWith("attr=")) {
        // data-i18n="attr=placeholder:key"
        const body = key.slice(5);
        const [attr, tkey] = body.split(":");
        if (attr && tkey && translations[tkey] != null) {
          el.setAttribute(attr, translations[tkey]);
        }
        return;
      }

      if (translations[key] != null) el.innerHTML = translations[key];
    });
  }

  function setLang(lang) {
    currentLang = normalize(lang);
    try { localStorage.setItem(LS_KEY, currentLang); } catch (_) {}
    writeLangToUrl(currentLang);
    console.log("[i18n] Switch →", currentLang);
    return loadAndApply(currentLang);
  }

  function bindButtons() {
    const onClick = (e) => {
      e.preventDefault();
      const lang = e.currentTarget.getAttribute("data-lang");
      if (lang) setLang(lang);
    };
    document.querySelectorAll(".lang-btn,[data-lang]").forEach((el) => {
      el.removeEventListener("click", onClick);
      el.addEventListener("click", onClick);
    });
  }

  document.addEventListener("DOMContentLoaded", () => {
    const start = getInitialLang();
    setLang(start);
    bindButtons();
    window.gjhSetLang = setLang; // вдруг пригодится
  });
})();
