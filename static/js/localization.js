/* Robust client-side i18n (RU -> EN/UK)
 * - RU-текст = ключ (словари: /static/i18n/{en,uk}.json)
 * - Переключение без перезагрузки
 * - Переводит текстовые узлы и атрибуты (placeholder/title/aria/alt)
 * - Обрабатывает динамику: "Найдено 174 вакансий за 0с." и т.п.
 * - Подхватывает тосты/алерты, status-модалки
 * - Если вёрстка разрывает фразу (как "…точке <a>мира</a>") — мягкая замена подставит переведённые куски
 */
(function () {
  if (window.__i18nAlreadyInit) return;
  window.__i18nAlreadyInit = true;

  const SUPPORTED = ['ru', 'uk', 'en'];
  const I18N_PATH = '/static/i18n';
  const LOG_MISSES = false;

  const TEXT_ORIG = new WeakMap();
  const ATTR_ORIG = new WeakMap();
  const misses = new Set();

  // Паттерны для динамических строк
  const PATTERNS = [
    {
      // Найдено 174 вакансий за 0с.
      re: /^Найдено\s+(\d+)\s+вакансий\s+за\s+(\d+)с\.?$/,
      render(lang, m) {
        const n = m[1], s = m[2];
        if (lang === 'uk') return `Знайдено ${n} вакансій за ${s}с.`;
        if (lang === 'en') return `Found ${n} jobs in ${s}s.`;
        return m[0];
      }
    },
    {
      // Совпадений по категории "X" не найдено среди текущего набора
      re: /^Совпадений\s+по\s+категории\s+"(.+?)"\s+не\s+найдено\s+среди\s+текущего\s+набора\.?$/,
      render(lang, m) {
        const cat = m[1];
        if (lang === 'uk') return `Немає збігів за категорією «${cat}» у поточному наборі.`;
        if (lang === 'en') return `No matches for category "${cat}" in the current set.`;
        return m[0];
      }
    },
    {
  // Выбрано 6 профессий в категории "IT"
  re: /^Выбрано\s+(\d+)\s+профессий\s+в\s+категории\s+"(.+?)"$/,
  render(lang, m){
    const n = m[1], cat = m[2];
    if (lang === 'uk') return `Вибрано ${n} професій у категорії «${cat}»`;
    if (lang === 'en') return `Selected ${n} jobs in category "${cat}"`;
    return m[0];
  }
},
{
  // Категория "IT" отменена
  re: /^Категория\s+"(.+?)"\s+отменена\.?$/,
  render(lang, m){
    const cat = m[1];
    if (lang === 'uk') return `Категорію «${cat}» скасовано`;
    if (lang === 'en') return `Category "${cat}" cleared`;
    return m[0];
  }
},
{
  // 📍 Выбран город: Berlin
  re: /^(?:📍\s*)?Выбран\s+город:\s*(.+)$/,
  render(lang, m){
    const city = m[1];
    if (lang === 'uk') return `Обрано місто: ${city}`;
    if (lang === 'en') return `Selected city: ${city}`;
    return m[0];
  }
},
{
  // Подписка расширена! Теперь вы получаете уведомления по 5 профессиям в 1 странах. Проверьте email для подтверждения.
  re: /^Подписка\s+расширена!\s+Теперь вы получаете уведомления по\s+(\d+)\s+профессиям\s+в\s+(\d+)\s+странах\.?\s+Проверьте email для подтверждения\.?$/,
  render(lang, m){
    const n = m[1], k = m[2];
    if (lang === 'uk') return `Підписку розширено! Тепер ви отримуватимете сповіщення за ${n} професіями в ${k} країнах. Перевірте email для підтвердження.`;
    if (lang === 'en') return `Subscription expanded! You will now receive alerts for ${n} professions in ${k} countries. Check your email to confirm.`;
    return m[0];
  }
}

  ];

  let currentLang = (localStorage.getItem('lang') || getCookie('lang') || detectInitial()).toLowerCase();
  if (!SUPPORTED.includes(currentLang)) currentLang = 'ru';
  let dict = Object.create(null);

  document.addEventListener('DOMContentLoaded', init, { once: true });

  async function init() {
    await loadLang(currentLang);
    injectStyles();
    snapshotAndTranslate(document.body);
    setupLanguageSwitcher();
    observeMutations();
    hookRuntimeMessages();
    document.documentElement.setAttribute('lang', currentLang);
    if (LOG_MISSES) setTimeout(reportMisses, 3000);
  }

  function detectInitial(){
    const nav = (navigator.language || '').slice(0,2).toLowerCase();
    if (nav === 'uk' || nav === 'ua') return 'uk';
    if (nav === 'ru') return 'ru';
    return 'en';
  }
  function setCookie(name, value){
    document.cookie = `${name}=${value};path=/;max-age=${60*60*24*365*2}`;
  }
  function getCookie(name){
    const m = document.cookie.match(new RegExp('(?:^|;\\s*)'+name+'=([^;]+)'));
    return m ? m[1] : '';
  }

  function setLang(lang){
    if (!SUPPORTED.includes(lang) || lang === currentLang) return;
    currentLang = lang;
    localStorage.setItem('lang', lang);
    setCookie('lang', lang);
    document.documentElement.setAttribute('lang', lang);
    (lang === 'ru' ? Promise.resolve() : loadLang(lang)).then(()=>{
      applyTranslations(document.body);
      updateSwitcherUI(lang);
    });
  }

  async function loadLang(lang){
    if (lang === 'ru'){ dict = Object.create(null); return; }
    try{
      const res = await fetch(`${I18N_PATH}/${lang}.json`, { cache: 'no-store' });
      if (!res.ok) throw new Error('HTTP '+res.status);
      dict = await res.json();
    }catch(e){
      console.warn('[i18n] Failed to load dictionary:', lang, e);
      dict = Object.create(null);
    }
  }

  // ---- перевод (строгий + паттерны + мягкая замена)
  function tWS(s){
    if (!s || currentLang === 'ru') return s;
    const lead = (s.match(/^[\s\u00A0]*/)||[''])[0];
    const trail = (s.match(/[\s\u00A0]*$/)||[''])[0];
    const core  = s.slice(lead.length, s.length - trail.length);

    let out = (Object.prototype.hasOwnProperty.call(dict, s) && dict[s]) ||
              (Object.prototype.hasOwnProperty.call(dict, core) && dict[core]) ||
              dict[core.trim()];

    if (out == null){
      for (const p of PATTERNS){
        const m = core.match(p.re);
        if (m){ out = p.render(currentLang, m); break; }
      }
    }
    if (out == null){
      // мягкая подстановка известных кусочков (на случай разорванных фраз)
      out = core;
      for (const k in dict){
        if (!k || k.length < 2) continue;
        if (out.includes(k)) out = out.split(k).join(dict[k]);
      }
      if (out === core && LOG_MISSES) misses.add(core);
    }
    return lead + (out ?? core) + trail;
  }

  function snapshotAndTranslate(root){
    if (!root) return;
    const ATTRS = ['placeholder','title','aria-label','aria-placeholder','alt'];

    root.querySelectorAll('*').forEach(el=>{
      ATTRS.forEach(a=>{
        const v = el.getAttribute(a);
        if (v!=null) storeAttrOriginal(el, a, v);
      });
    });

    const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT, {
      acceptNode(n){
        const s = n.nodeValue;
        if (!s || !s.trim()) return NodeFilter.FILTER_REJECT;
        const p = n.parentElement;
        if (!p || p.closest('script,style,code,pre')) return NodeFilter.FILTER_REJECT;
        if (/^[\s\d.,:;!?\-–—()[\]{}@+%]+$/.test(s)) return NodeFilter.FILTER_REJECT;
        return NodeFilter.FILTER_ACCEPT;
      }
    });
    let n; while((n = walker.nextNode())) if(!TEXT_ORIG.has(n)) TEXT_ORIG.set(n, n.nodeValue);

    applyTranslations(root);
  }

  function applyTranslations(root){
    if (!root) return;

    ['placeholder','title','aria-label','aria-placeholder','alt'].forEach(attr=>{
      root.querySelectorAll(`[${attr}]`).forEach(el=>{
        const orig = getAttrOriginal(el, attr) ?? el.getAttribute(attr);
        if (orig) el.setAttribute(attr, tWS(orig));
      });
    });

    const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT, {
      acceptNode(n){
        const orig = TEXT_ORIG.get(n) || n.nodeValue;
        if (!orig || !orig.trim()) return NodeFilter.FILTER_REJECT;
        const p = n.parentElement;
        if (!p || p.closest('script,style,code,pre')) return NodeFilter.FILTER_REJECT;
        if (/^[\s\d.,:;!?\-–—()[\]{}@+%]+$/.test(orig)) return NodeFilter.FILTER_REJECT;
        return NodeFilter.FILTER_ACCEPT;
      }
    });
    let n; while((n = walker.nextNode())){
      const orig = TEXT_ORIG.get(n) || n.nodeValue;
      const out  = tWS(orig);
      if (n.nodeValue !== out) n.nodeValue = out;
    }
  }

  function storeAttrOriginal(el, attr, val){
    let map = ATTR_ORIG.get(el);
    if (!map){ map = new Map(); ATTR_ORIG.set(el, map); }
    if (!map.has(attr)) map.set(attr, val);
  }
  function getAttrOriginal(el, attr){
    const map = ATTR_ORIG.get(el);
    return map ? map.get(attr) : undefined;
  }

  function observeMutations(){
    const mo = new MutationObserver(muts=>{
      let need = false;
      for (const m of muts){
        if (m.type==='childList' && m.addedNodes.length) { need=true; break; }
        if (m.type==='attributes' && ['placeholder','title','aria-label','aria-placeholder','alt'].includes(m.attributeName)) { need=true; break; }
      }
      if (!need) return;
      muts.forEach(m=>{
        m.addedNodes && m.addedNodes.forEach(n=>{
          if (n.nodeType===Node.ELEMENT_NODE) snapshotAndTranslate(n);
        });
      });
    });
    mo.observe(document.body, { childList:true, subtree:true, attributes:true });
  }

  // перехват тостов/алертов, чтобы тоже переводились
  function hookRuntimeMessages(){
    const wrap = (name) => {
      const orig = window[name];
      if (typeof orig === 'function') {
        window[name] = function(...args){
          if (args[0]) args[0] = tWS(String(args[0]));
          return orig.apply(this, args);
        };
      }
    };
    wrap('showAlert'); wrap('showToast'); wrap('showTemporaryMessage');
    const native = window.alert;
    window.alert = function(msg){ native.call(window, tWS(String(msg||''))); };
  }

  // подключаем уже существующий переключатель в шапке
  function setupLanguageSwitcher(){
  document.querySelectorAll('.language-switcher').forEach(container => {
    container.addEventListener('click', (e)=>{
      const btn = e.target.closest('[data-lang]');
      if (!btn) return;
      e.preventDefault();
      setLang(btn.getAttribute('data-lang'));
    });
  });
  updateSwitcherUI(currentLang);
}


  function updateSwitcherUI(lang){
  document.querySelectorAll('.language-switcher').forEach(cont => {
    const main = cont.querySelector('.dropdown-toggle, .btn');
    if (main) {
      const map = { ru: 'fi fi-ru', uk: 'fi fi-ua', en: 'fi fi-gb' };
      main.innerHTML = `<span class="${map[lang]||'fi fi-ru'}"></span> ` + 
                       (lang === 'uk' ? 'Українська' : lang === 'en' ? 'English' : 'Русский');
    }
    cont.querySelectorAll('[data-lang]').forEach(a=>{
      a.classList.toggle('active', a.getAttribute('data-lang') === lang);
    });
  });
}


  function injectStyles(){
    if (document.getElementById('gzh-i18n-style')) return;
    const style = document.createElement('style');
    style.id = 'gzh-i18n-style';
    style.textContent = `.i18n-hidden{display:none!important}`;
    document.head.appendChild(style);
  }

  function reportMisses(){
    if (!misses.size) return;
    console.group('[i18n] Missing keys');
    misses.forEach(k => console.log(k));
    console.groupEnd();
  }

  window.i18n = {
    setLang,
    getLang: ()=> currentLang,
    t: (s)=> tWS(s),
    apply: ()=> applyTranslations(document.body)
  };
})();
