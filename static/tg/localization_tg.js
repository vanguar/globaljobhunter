// /static/tg/localization_tg.js
// Локализация мини-приложения (WebApp).
// Работает и с кнопками `.lang-btn`, и с кнопками, у которых просто есть [data-lang].
// Загружает /static/{lang}.json и применяет переводы к элементам с data-i18n.
// Поддерживает data-i18n="attr=placeholder:key" для плейсхолдеров и др. атрибутов.

(function(){
  const LS_KEY = "gjh_lang";
  let currentLang = null;
  let translations = {};

  // 1) Прочитаем язык: URL ?lang= → localStorage → 'ru'
  try {
    const params = new URLSearchParams(location.search);
    const fromUrl = params.get("lang");
    if (fromUrl) {
      currentLang = fromUrl;
      localStorage.setItem(LS_KEY, fromUrl);
    }
  } catch(_) {}

  if (!currentLang) {
    try { currentLang = localStorage.getItem(LS_KEY) || "ru"; } catch(_) { currentLang = "ru"; }
  }

  // 2) Выставим <html lang="..">
  try { document.documentElement.setAttribute("lang", currentLang); } catch(_) {}

  // 3) Глобальный API (по желанию)
  window.GJH_I18N = {
    getLang: () => currentLang,
    setLang: async (lang) => {
      await setLangInternal(lang);
    },
    t: (key) => translations[key] || key,
    applyNow: () => applyTranslations()
  };

  // 4) Инициализация
  document.addEventListener("DOMContentLoaded", async () => {
    await loadLanguage(currentLang);
    wireLanguageButtons();
  });

  // --- обработчики языковых кнопок ---
  function wireLanguageButtons(){
    const handler = async (lang) => {
      await setLangInternal(lang);
      // Синхронизируем URL (оставляем в той же webview, без reload)
      try {
        const qs = new URLSearchParams(location.search);
        qs.set("lang", lang);
        history.replaceState(null, "", location.pathname + "?" + qs.toString());
      } catch(_) {}
    };

    // Кнопки с классом .lang-btn
    document.querySelectorAll(".lang-btn").forEach(btn => {
      btn.addEventListener("click", () => handler(btn.dataset.lang));
    });

    // Любые элементы с атрибутом [data-lang] (например, button[data-lang])
    document.querySelectorAll("[data-lang]").forEach(btn => {
      // если уже повесили через .lang-btn — не дублируем
      if (btn.classList && btn.classList.contains("lang-btn")) return;
      btn.addEventListener("click", () => handler(btn.getAttribute("data-lang")));
    });
  }

  async function setLangInternal(lang){
    currentLang = lang || "ru";
    try { localStorage.setItem(LS_KEY, currentLang); } catch(_) {}
    try { document.documentElement.setAttribute("lang", currentLang); } catch(_) {}
    await loadLanguage(currentLang);
  }

  async function loadLanguage(lang){
    try {
      const resp = await fetch(`/static/${lang}.json`, { cache: "no-store" });
      translations = await resp.json();
      applyTranslations();
      console.log(`[i18n] Loaded ${lang}`);
    } catch (e) {
      console.error("[i18n] loadLanguage failed", e);
    }
  }

  function applyTranslations(){
    document.querySelectorAll("[data-i18n]").forEach(el => {
      const key = el.getAttribute("data-i18n");
      if (!key) return;

      // attr=placeholder:key  /  attr=title:key  и т.п.
      if (key.startsWith("attr=")) {
        const body = key.slice(5); // placeholder:key
        const [attrName, tkey] = body.split(":");
        if (attrName && tkey && translations[tkey]) {
          el.setAttribute(attrName, translations[tkey]);
        }
        return;
      }

      if (translations[key] !== undefined) {
        el.innerHTML = translations[key];
      }
    });
  }
})();
