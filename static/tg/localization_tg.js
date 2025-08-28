/* Default RU when nothing set */
(function () {
  try {
    const hasUrlLang = new URLSearchParams(location.search).has('lang');
    if (!hasUrlLang && !localStorage.getItem('gjh_lang')) {
      localStorage.setItem('gjh_lang', 'ru');
    }
  } catch (e) {}
})();


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
      window.location.href = data.redirect_url;
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

  // ▼ ДОБАВЬ ВОТ ЭТО ПОД ИНИЦИАЛИЗАЦИЕЙ ▼
  document.addEventListener('click', function (e) {
    const item = e.target.closest('.dropdown-item[data-lang], .lang-option[data-lang], [data-lang].dropdown-item');
    if (!item) return;
    e.preventDefault();
    const code = (item.getAttribute('data-lang') || 'ru').toLowerCase();
    try { localStorage.setItem('gjh_lang', code); } catch (_) {}
    if (window.gjhSetLang) { window.gjhSetLang(code); return; }
    const u = new URL(location.href);
    u.searchParams.set('lang', code);
    location.href = u.toString();
  });
  // ▲ ДОБАВИЛИ ЗДЕСЬ ▲
