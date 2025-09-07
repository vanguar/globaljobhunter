#!/usr/bin/env python3
"""
GlobalJobHunter Web Interface v3.3 - С КЕШИРОВАНИЕМ
Интеграция с умным кешированием и мониторингом
"""

import os, sys
os.environ.setdefault('PYTHONUNBUFFERED', '1')
try:
    sys.stdout.reconfigure(line_buffering=True)
    sys.stderr.reconfigure(line_buffering=True)
except Exception:
    pass
import json
import time
from datetime import datetime
from flask import Flask, render_template, request, jsonify, session, redirect, url_for, flash
from dotenv import load_dotenv
from datetime import datetime, timedelta  # ← ДОБАВИТЬ timedelta!
from collections import defaultdict        # ← ДОБАВИТЬ это!
import secrets
import uuid
from dataclasses import asdict
from flask import Flask, render_template, request, jsonify, session, redirect, url_for, flash, render_template_string,  Response
from email_service import mail, send_welcome_email, send_preferences_update_email, send_job_notifications, run_scheduled_notifications

# Добавить эти импорты ПОСЛЕ существующих
from flask_mail import Mail
from database import db, Subscriber, EmailLog  
from email_service import mail, send_welcome_email, send_preferences_update_email
from flask_migrate import Migrate
from pathlib import Path
import time
from sqlalchemy import func
from datetime import datetime, timezone

from threading import Thread
import schedule
SUPPORTED_LANGS = {'ru', 'uk', 'en'}
from flask import request

# Импортируем существующий агрегатор
from adzuna_aggregator import GlobalJobAggregator, JobVacancy
from careerjet_aggregator import CareerjetAggregator
from remotive_aggregator import RemotiveAggregator
# === Live progress state (для живого прогресса/остановки) ===
active_searches = {}  # sid -> state dict

import threading, inspect
from dataclasses import asdict
from pathlib import Path
import time

from flask import Flask, render_template
# === трекинг-логика (минимальные правки) ===
from analytics import analytics_bp, log_search_click, pretty_json, h as html_escape


app = Flask(__name__)
app.register_blueprint(analytics_bp)

# === SEO: robots.txt и sitemap.xml (AUTO) ==========================
# Явно укажем важные публичные URL, которые хотим видеть в индексе всегда.
# Если у тебя есть /support — оставь строку. Если нет — просто удали её.
EXTRA_PUBLIC_URLS = [
    "/",                # главная
    "/support",         # страница поддержки проекта (если есть роут)
    "/tg",              # лендинг для TG WebApp (если пусть индексируется)
]

# Блэклист — эти разделы и страницы НЕЛЬЗЯ индексировать и в sitemap они не попадут
SEO_DISALLOW_PREFIXES = (
    "/results", "/search", "/api", "/admin", "/subscription", "/unsubscribe",
    "/subscribe", "/analytics", "/health", "/static"
)
SEO_DISALLOW_EXACT = {
    "/favicon.ico", "/robots.txt", "/sitemap.xml",
    "/send-notifications"
}

def _xml_escape(s: str) -> str:
    return (s.replace("&", "&amp;")
             .replace("<", "&lt;")
             .replace(">", "&gt;")
             .replace('"', "&quot;")
             .replace("'", "&apos;"))

BASE_URL = "https://www.globaljobhunter.vip"   # <- канон. домен + HTTPS

def _absolute_url(path: str) -> str:
    return f"{BASE_URL}{path}"

def _collect_public_paths() -> list[str]:
    """Берём все GET-роуты БЕЗ параметров и фильтруем внутренние/служебные."""
    out = set()

    # 1) из карты маршрутов Flask
    for rule in app.url_map.iter_rules():
        if "GET" not in rule.methods:
            continue
        if rule.arguments:  # у правил есть <param>? — такие не берём
            continue
        path = str(rule.rule)
        if path in SEO_DISALLOW_EXACT:
            continue
        if path.startswith(SEO_DISALLOW_PREFIXES):
            continue
        out.add(path)

    # 2) добавим принудительно важные страницы (если они есть в приложении)
    for path in EXTRA_PUBLIC_URLS:
        out.add(path)

    # Нормализуем: корень — первым, остальные по алфавиту
    paths = sorted(out)
    if "/" in paths:
        paths.remove("/")
        paths.insert(0, "/")
    return paths

def _render_sitemap(paths: list[str]) -> str:
    today = datetime.utcnow().date().isoformat()
    lines = ['<?xml version="1.0" encoding="UTF-8"?>',
             '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">']
    for p in paths:
        loc = _xml_escape(_absolute_url(p))
        # Простая логика: корень — priority 1.0, остальное — 0.5
        prio = "1.0" if p == "/" else "0.5"
        lines += [
            "  <url>",
            f"    <loc>{loc}</loc>",
            f"    <lastmod>{today}</lastmod>",
            f"    <changefreq>daily</changefreq>",
            f"    <priority>{prio}</priority>",
            "  </url>"
        ]
    lines.append("</urlset>")
    return "\n".join(lines)

from flask import Response

VERIFICATION_FILENAME = "googleab1f551714c95e9d.html"  # замени на свой

@app.route(f"/{VERIFICATION_FILENAME}")
def google_site_verification():
    body = f"google-site-verification: {VERIFICATION_FILENAME}"
    return Response(body, mimetype="text/plain; charset=utf-8")


@app.route("/robots.txt")
def robots_txt():
    body = (
        "User-agent: *\n"
        "Allow: /\n"
        # Результаты поиска/служебка — не индексируем
        "Disallow: /results\n"
        "Disallow: /results/\n"
        "Disallow: /search\n"
        "Disallow: /search/\n"
        "Disallow: /api\n"
        "Disallow: /api/\n"
        "Disallow: /admin\n"
        "Disallow: /admin/\n"
        "Disallow: /subscription\n"
        "Disallow: /subscription/\n"
        "Disallow: /subscribe\n"
        "Disallow: /unsubscribe\n"
        "Disallow: /analytics\n"
        "Disallow: /analytics/\n"
        "Disallow: /health\n"
        # Уберём дубли по языкам: /?lang=ru|uk|en и т.п.
        "Disallow: /*?lang=\n"
        "Disallow: /*&lang=\n"
        # Ссылка на карту сайта
        "Sitemap: https://www.globaljobhunter.vip/sitemap.xml\n"
    )
    return Response(body, mimetype="text/plain; charset=utf-8")

@app.route("/sitemap.xml")
def sitemap_xml():
    paths = _collect_public_paths()
    xml = _render_sitemap(paths)
    return Response(xml, mimetype="application/xml; charset=utf-8")
# === /SEO ===========================================================


# в app.py (не ломая ничего существующего)
from flask import send_from_directory

@app.route("/tg")
def tg_index_alias():
    return send_from_directory("static/tg", "index.html")


# Rate limiting
RATE_LIMIT_FILE = "rate_limits.json"
MAX_SEARCHES_PER_DAY = 5

def load_rate_limits():
    """Загрузка ограничений по IP"""
    try:
        with open(RATE_LIMIT_FILE, 'r') as f:
            data = json.load(f)
            # Конвертируем строки обратно в datetime
            for ip, searches in data.items():
                data[ip] = [datetime.fromisoformat(dt) for dt in searches]
            # 🔧 ИСПРАВЛЕНИЕ: всегда возвращаем defaultdict
            return defaultdict(list, data)
    except FileNotFoundError:
        return defaultdict(list)
    except Exception as e:
        print(f"❌ Ошибка загрузки rate limits: {e}")
        return defaultdict(list)

def save_rate_limits(limits):
   """Сохранение ограничений по IP"""
   # Конвертируем datetime в строки для JSON
   serializable_data = {}
   for ip, searches in limits.items():
       serializable_data[ip] = [dt.isoformat() for dt in searches]
   
   with open(RATE_LIMIT_FILE, 'w') as f:
       json.dump(serializable_data, f)

def check_rate_limit(ip_address):
    """Проверка лимита поисков для IP"""
    limits = load_rate_limits()
    now = datetime.now()
    day_ago = now - timedelta(days=1)
    
    # 🔧 ДОБАВЛЕНА ТОЛЬКО ЭТА ПРОВЕРКА:
    if ip_address not in limits:
        limits[ip_address] = []
    
    # Очищаем старые записи (старше суток)
    recent_searches = [dt for dt in limits[ip_address] if dt > day_ago]
    limits[ip_address] = recent_searches
    
    # Проверяем лимит
    if len(recent_searches) >= MAX_SEARCHES_PER_DAY:
        # TEMP OFF: отключили суточный лимит
        #return False, MAX_SEARCHES_PER_DAY - len(recent_searches)
        pass
    
    # Добавляем текущий поиск
    limits[ip_address].append(now)
    save_rate_limits(limits)
    
    return True, MAX_SEARCHES_PER_DAY - len(limits[ip_address])

# Импортируем дополнительные источники (опционально)
try:
    from jobicy_aggregator import JobicyAggregator
    from usajobs_aggregator import USAJobsAggregator
    ADDITIONAL_SOURCES_AVAILABLE = True
    print("✅ Дополнительные источники доступны")
except ImportError as e:
    ADDITIONAL_SOURCES_AVAILABLE = False
    print(f"ℹ️ Дополнительные источники недоступны: {e}")

load_dotenv()

app.secret_key = secrets.token_hex(16)

# Настройки базы данных
app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('DATABASE_URL', 'sqlite:///globaljobhunter.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Настройки email 
app.config['MAIL_SERVER'] = os.getenv('MAIL_SERVER', 'smtp.gmail.com')
app.config['MAIL_PORT'] = int(os.getenv('MAIL_PORT', 587))
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USERNAME'] = os.getenv('MAIL_USERNAME')
app.config['MAIL_PASSWORD'] = os.getenv('MAIL_PASSWORD')
app.config['MAIL_DEFAULT_SENDER'] = os.getenv('MAIL_DEFAULT_SENDER', os.getenv('MAIL_USERNAME'))

# ==== База данных: PostgreSQL через ENV, иначе SQLite fallback ====
def _build_db_uri():
    # локальный/резервный SQLite (если не задан DATABASE_URL)
    return "sqlite:///globaljobhunter.db"

def _current_db_url():
    url = os.getenv("DATABASE_URL") or _build_db_uri()
    return url.replace("postgres://", "postgresql://")

app.config.update(
    SQLALCHEMY_DATABASE_URI=_current_db_url(),
    SQLALCHEMY_TRACK_MODIFICATIONS=False,
    SQLALCHEMY_ENGINE_OPTIONS={
        "pool_pre_ping": True,
        "pool_size": 5,       # опционально
        "max_overflow": 10,   # опционально
        "pool_recycle": 1800, # опционально
    },
)


# Инициализация расширений
db.init_app(app)
mail.init_app(app)
migrate = Migrate(app, db)

# Инициализация основного агрегатора
try:
    adzuna_ttl = int(os.getenv('ADZUNA_CACHE_HOURS', os.getenv('CACHE_TTL_HOURS', '24')))
    aggregator = GlobalJobAggregator(cache_duration_hours=adzuna_ttl)
    aggregator.search_cache = {}
    app.logger.info(f"✅ GlobalJobAggregator инициализирован (TTL={adzuna_ttl}ч)")
except Exception as e:
    app.logger.error(f"❌ Ошибка инициализации GlobalJobAggregator: {e}")
    aggregator = None


# ДОБАВЛЕНИЕ: инициализация дополнительных источников
additional_aggregators = {}
if ADDITIONAL_SOURCES_AVAILABLE and aggregator:
    try:
        # Jobicy
        jobicy = JobicyAggregator()
        # ← ВАЖНАЯ СТРОКА: отдаём ту же карту терминов, что использует Adzuna/основной агрегатор
        jobicy.specific_jobs_map = aggregator.specific_jobs

        # Careerjet — уже получает карту в конструкторе
        careerjet = CareerjetAggregator(
            adzuna_countries=aggregator.countries,
            specific_jobs_map=aggregator.specific_jobs
        )

        # Remotive — тоже фильтруется той же картой
        remotive = RemotiveAggregator(
            specific_jobs_map=aggregator.specific_jobs
        )

        additional_aggregators['jobicy'] = jobicy
        additional_aggregators['careerjet'] = careerjet
        additional_aggregators['remotive'] = remotive

        app.logger.info("✅ Дополнительные агрегаторы инициализированы: Jobicy, Careerjet, Remotive")
    except Exception as e:
        app.logger.warning(f"⚠️ Не удалось инициализировать дополнительные агрегаторы: {e}")
else:
    app.logger.info("ℹ️ Дополнительные источники отключены или основной агрегатор не инициализирован")

# --- Remote-only sources gating (Jobicy/Remotive) ---
# Разрешаем remote только для этих категорий/позиций:
REMOTE_OK_CATS = {
    '💻 IT И ТЕХНОЛОГИИ',
    '👔 ОФИС И УПРАВЛЕНИЕ',
    '🔍 ДРУГОЕ',
}
# Точные позиции, которые тоже допускают remote (рус/укр)
REMOTE_OK_TITLES = {
    'Переводчик украинского',
    'Перекладач української',
}

def _remote_allowed(preferences: dict) -> bool:
    """
    Возвращает True, если ИЗ ВЫБРАННЫХ ПРОФЕССИЙ есть хотя бы одна,
    которая допускает remote (по нашим правилам выше).
    """
    selected = set(preferences.get('selected_jobs') or [])
    if not selected:
        return False
    # Категория -> {ru_title: [...keywords...]}
    sj = getattr(aggregator, 'specific_jobs', {}) or {}
    for cat, ru_map in sj.items():
        if isinstance(ru_map, dict) and cat in REMOTE_OK_CATS:
            # попадает ли выбранная профессия в разрешённую категорию
            if any(ru in ru_map for ru in selected):
                return True
    # точечные допуски по названию
    if any(t in selected for t in REMOTE_OK_TITLES):
        return True
    return False


# В файле app.py найдите функцию index() и замените её на эту версию:

# app.py

@app.route('/')
def index():
    """Главная страница с современным дизайном"""
    if not aggregator:
        return render_template('error.html', 
                             error="API ключи не настроены. Обратитесь к администратору.")
    
    # Получаем категории напрямую из агрегатора
    job_categories = aggregator.specific_jobs
    
    # ❌ ПРОБЛЕМНЫЙ БЛОК УДАЛЁН ❌
    
    total_jobs = sum(len(jobs) for jobs in job_categories.values())
    
    session.pop('results_id', None)
    session.pop('last_search_preferences', None)
    
    return render_template('index.html', 
                         job_categories=job_categories,
                         total_jobs=total_jobs,
                         countries=aggregator.countries)

@app.route('/search', methods=['POST'])
def search_jobs():
    """API для поиска с кешированием + поддержка нескольких городов через запятую"""
    if not aggregator:
        return jsonify({'error': 'Сервис временно недоступен'}), 500
    
    # Rate limiting
    client_ip = request.environ.get('HTTP_X_FORWARDED_FOR', request.environ.get('REMOTE_ADDR', 'unknown'))
    allowed, remaining = check_rate_limit(client_ip)
    if not allowed:
        app.logger.warning(f"🚫 Rate limit exceeded for IP: {client_ip}")
        return jsonify({
            'error': f'Превышен лимит поисков. Максимум {MAX_SEARCHES_PER_DAY} поисков в день.',
            'remaining_searches': 0,
            'reset_time': '24 часа'
        }), 429
    
    app.logger.info(f"✅ Rate limit OK for IP: {client_ip}, remaining: {remaining}")
    
    try:
        form_data = request.json or request.form.to_dict()
        
        # === корректный разбор нескольких городов через запятую ===
        raw_city = (form_data.get('city') or '').strip()
        if raw_city:
            cities = [c.strip() for c in raw_city.split(',') if c.strip()]
        else:
            cities = []
        # ==========================================================
        
        preferences = {
            'is_refugee': form_data.get('is_refugee') == 'true',
            'selected_jobs': form_data.get('selected_jobs', []),
            'countries': form_data.get('countries', ['de']),
            # оставляем старое поле для обратной совместимости (UI/шаблоны)
            'city': None,
            # новое поле — список городов
            'cities': cities
        }
        
        if not preferences['selected_jobs']:
            return jsonify({'error': 'Выберите хотя бы одну профессию'}), 400
        
        if isinstance(preferences['selected_jobs'], str):
            preferences['selected_jobs'] = [preferences['selected_jobs']]
        
        # === analytics: лог клика "Найти работу" (не влияет на основной поток) ===
        try:
            log_search_click(preferences)
        except Exception as e:
            app.logger.warning(f"analytics log_search_click failed: {e}")
        # =======================================================================
        
        app.logger.info(f"🔍 Начинаем поиск: {preferences}")
        start_time = time.time()

        # Основной поиск (Adzuna)
        jobs = aggregator.search_specific_jobs(preferences)
        
        # Доп. источники (если подключены)
        if additional_aggregators:
            use_remote = _remote_allowed(preferences)
            for source_name, source_aggregator in additional_aggregators.items():
                # Блокируем remote-only источники, если выбранные профессии не допускают удалёнку
                if source_name in ('remotive', 'jobicy') and not use_remote:
                    app.logger.info(f"⛔ Пропускаем {source_name}: выбранные профессии не допускают удалёнку")
                    continue
                try:
                    app.logger.info(f"🔄 Дополнительный поиск через {source_name}")
                    additional_jobs = source_aggregator.search_jobs(preferences)
                    jobs.extend(additional_jobs)
                    app.logger.info(f"✅ {source_name}: +{len(additional_jobs)} вакансий")
                except Exception as e:
                    app.logger.warning(f"⚠️ {source_name} ошибка: {e}")
                    continue
        
        search_time = time.time() - start_time
        
        cache_stats = aggregator.get_cache_stats()
        app.logger.info(f"⏱️ Поиск завершен за {search_time:.1f}с, найдено {len(jobs)} вакансий")
        app.logger.info(f"📊 Cache hit rate: {cache_stats['cache_hit_rate']}, API requests: {cache_stats['api_requests']}")
        
        if jobs:
            results_id = str(uuid.uuid4())
            job_details_map = {job.id: asdict(job) for job in jobs}
            aggregator.search_cache[results_id] = job_details_map
            
            session['results_id'] = results_id
            session['last_search_preferences'] = preferences
            session['search_time'] = search_time
        else:
            session['results_id'] = None
            session['last_search_preferences'] = preferences
            session['search_time'] = search_time

        return jsonify({
            'success': True,
            'jobs_count': len(jobs),
            'search_time': round(search_time, 1),
            'cached': cache_stats['cache_hits'] > 0,
            'sources_used': ['adzuna'] + list(additional_aggregators.keys()),
            'remaining_searches': remaining,
            'redirect_url': url_for('results')
        })
    
    except Exception as e:
        app.logger.error(f"❌ Ошибка поиска: {e}", exc_info=True)
        return jsonify({'error': f'Внутренняя ошибка сервера: {str(e)}'}), 500


# ---- LIVE SEARCH: старт → прогресс → стоп ---------------------------------

def _sources_iter():
    # Имя для UI -> объект
    yield ("Adzuna", aggregator)
    try:
        if additional_aggregators:
            if 'careerjet' in additional_aggregators:
                yield ("Careerjet", additional_aggregators['careerjet'])
            if 'remotive' in additional_aggregators:
                yield ("Remotive", additional_aggregators['remotive'])
            if 'jobicy' in additional_aggregators:
                yield ("Jobicy", additional_aggregators['jobicy'])
    except NameError:
        pass

@app.route('/search/start', methods=['POST'])
def search_start():
    """Старт фонового поиска с живым прогрессом."""
    if not aggregator:
        return jsonify({'error': 'Сервис временно недоступен'}), 500

    # rate limit — как в /search
    client_ip = request.environ.get('HTTP_X_FORWARDED_FOR', request.environ.get('REMOTE_ADDR', 'unknown'))
    allowed, remaining = check_rate_limit(client_ip)
    if not allowed:
        return jsonify({
            'error': f'Превышен лимит поисков. Максимум {MAX_SEARCHES_PER_DAY} поисков в день.',
            'remaining_searches': 0,
            'reset_time': '24 часа'
        }), 429

    form_data = request.json or request.form.to_dict()
    raw_city = (form_data.get('city') or '').strip()
    cities = [c.strip() for c in raw_city.split(',') if c.strip()] if raw_city else []

    preferences = {
        'is_refugee': form_data.get('is_refugee') == 'true',
        'selected_jobs': form_data.get('selected_jobs', []),
        'countries': form_data.get('countries', ['de']),
        'city': None,
        'cities': cities
    }

    if isinstance(preferences['selected_jobs'], str):
        preferences['selected_jobs'] = [preferences['selected_jobs']]
    if not preferences['selected_jobs']:
        return jsonify({'error': 'Выберите хотя бы одну профессию'}), 400

    # === analytics: лог клика "Найти работу" (не влияет на основной поток) ===
    try:
        log_search_click(preferences)
    except Exception as e:
        app.logger.warning(f"analytics log_search_click failed: {e}")
    # =======================================================================

    sid = str(uuid.uuid4())
    active_searches[sid] = {
        'sid': sid,
        'started_at': time.time(),
        'cancel': False,
        'current_source': None,
        'completed_sources': [],
        'sites_status': {},            # name -> pending|active|done|error
        'job_map': {},                 # id -> job dict
        'jobs_count': 0,
        'results_id': None,
        'status': 'running',
        'preferences': preferences,
    }

    t = Thread(target=_search_worker, args=(sid,), daemon=True)
    t.start()
    return jsonify({'ok': True, 'search_id': sid, 'remaining_searches': remaining})


def _search_worker(sid: str):
    """Фоновый поток: проходит по источникам и наполняет active_searches[sid]['job_map'].
       ВАЖНО: НИЧЕГО не пишем в flask.session (нет request context)!
    """
    st = active_searches.get(sid)
    if not st:
        return
    prefs = st['preferences']

    for name, src in _sources_iter():
        # Скипаем remote-only источники, если профессии не допускают удалёнку
        if name in ('Remotive', 'Jobicy') and not _remote_allowed(prefs):
            st['sites_status'][name] = 'skipped'
            st['completed_sources'].append(name)
            app.logger.info(f"⛔ Пропускаем {name}: выбранные профессии не допускают удалёнку")
            continue

        if st.get('cancel'):
            break

        st['current_source'] = name
        st['sites_status'][name] = 'active'
        try:
            def cancel_check():
                s = active_searches.get(sid)
                return (s is None) or s.get('cancel', False)

            def progress_callback(batch_jobs):
                if not batch_jobs:
                    return
                s = active_searches.get(sid)
                if not s or s.get('cancel'):
                    return
                added = 0
                for j in batch_jobs:
                    jid = getattr(j, 'id', None)
                    if not jid:
                        continue
                    if jid not in s['job_map']:
                        s['job_map'][jid] = asdict(j)
                        added += 1
                if added:
                    s['jobs_count'] = len(s['job_map'])
                    s['current_source'] = name

            # Вызываем с поддержкой прогресса/отмены, если сигнатура позволяет
            jobs = None
            try:
                jobs = src.search_specific_jobs(prefs, progress_callback=progress_callback, cancel_check=cancel_check)
            except Exception:
                try:
                    jobs = src.search_jobs(prefs, progress_callback=progress_callback, cancel_check=cancel_check)
                except TypeError:
                    jobs = src.search_jobs(prefs)

            if jobs:
                for j in jobs:
                    jid = getattr(j, 'id', None)
                    if not jid:
                        continue
                    if jid not in st['job_map']:
                        st['job_map'][jid] = asdict(j)
                st['jobs_count'] = len(st['job_map'])

            st['sites_status'][name] = 'done'
            st['completed_sources'].append(name)

        except Exception as e:
            app.logger.warning(f"{name} error: {e}")
            st['sites_status'][name] = 'error'
            st['completed_sources'].append(name)

    # ФИНАЛИЗАЦИЯ БЕЗ session: просто запишем в кэш и отметим результат
    if st['job_map']:
        st['results_id'] = str(uuid.uuid4())
        aggregator.search_cache[st['results_id']] = st['job_map']
    st['status'] = 'done'

@app.route('/search/progress')
def search_progress():
    sid = request.args.get('id')
    st = active_searches.get(sid)
    if not sid or not st:
        return jsonify({'error': 'search_id not found'}), 404

    # КОГДА всё готово — теперь МОЖНО положить в session (мы в request context)
    if st['status'] == 'done' and st.get('results_id'):
        session['results_id'] = st['results_id']
        session['last_search_preferences'] = st['preferences']

    payload = {
        'status': st['status'],
        'search_id': sid,
        'jobs_found': st['jobs_count'],
        'current_source': st['current_source'],
        'completed_sources': st['completed_sources'],
        'sites_status': st['sites_status'],
    }
    if st['status'] == 'done':
        payload['redirect_url'] = url_for('results')
    return jsonify(payload)


@app.route('/search/stop', methods=['POST'])
def search_stop():
    """Мягкая остановка: сразу финализируем, чтобы UI мгновенно ушёл на /results."""
    payload = request.get_json(silent=True) or {}
    sid = payload.get('search_id') or request.args.get('id')
    if not sid:
        return jsonify({'error': 'search_id is required'}), 400
    st = active_searches.get(sid)
    if not st:
        return jsonify({'error': 'search_id not found'}), 404

    # Ставим флаг отмены
    st['cancel'] = True

    # Финализируем прямо здесь (даже если поток где-то ждёт rate-limit)
    if not st.get('results_id') and st['job_map']:
        st['results_id'] = str(uuid.uuid4())
        aggregator.search_cache[st['results_id']] = st['job_map']

    st['status'] = 'done'

    # Здесь можно работать с session (есть request context)
    if st.get('results_id'):
        session['results_id'] = st['results_id']
        session['last_search_preferences'] = st['preferences']
        return jsonify({'ok': True, 'redirect_url': url_for('results')})
    else:
        # Ничего не нашли — пошлём на results, пусть покажет "0"
        return jsonify({'ok': True, 'redirect_url': url_for('results')})

# ---------------------------------------------------------------------------


# ВСЕ ОСТАЛЬНЫЕ МЕТОДЫ ПОЛНОСТЬЮ БЕЗ ИЗМЕНЕНИЙ
@app.route('/results')
def results():
   """Страница результатов"""
   results_id = session.get('results_id')
   preferences = session.get('last_search_preferences', {})
   search_time = session.get('search_time', 0)
   
   jobs_data = []
   
   if results_id and aggregator and results_id in aggregator.search_cache:
       job_details_map = aggregator.search_cache[results_id]
       jobs_data = list(job_details_map.values())
   elif results_id is None:
       jobs_data = []
   else:
       return redirect(url_for('index'))

   # Статистика
   stats = {
       'total': len(jobs_data),
       'with_salary': len([j for j in jobs_data if j.get('salary')]),
       'refugee_friendly': len([j for j in jobs_data if j.get('refugee_friendly')]),
       'no_language': len([j for j in jobs_data if j.get('language_requirement') == 'no_language_required'])
   }
   
   # НОВАЯ СОРТИРОВКА: Сначала группируем по странам, потом сортируем внутри каждой страны
   def sort_key(job):
       country = job.get('country', '')
       refugee_friendly = job.get('refugee_friendly', False)
       no_language = job.get('language_requirement') == 'no_language_required'
       has_salary = job.get('salary') is not None
       posted_date = job.get('posted_date', '')
       
       # Сначала по стране, потом по приоритетам внутри страны
       return (
           country,              # Группируем по стране
           not refugee_friendly, # Сначала для беженцев
           not no_language,      # Потом без языка
           not has_salary,       # Потом с зарплатой
           posted_date          # По дате
       )
   
   jobs_sorted = sorted(jobs_data, key=sort_key)
   
   # Группируем вакансии по странам для отображения разделителей
   jobs_by_country = {}
   for job in jobs_sorted:
       country = job.get('country', 'Неизвестно')
       if country not in jobs_by_country:
           jobs_by_country[country] = []
       jobs_by_country[country].append(job)
   
   return render_template('results.html',
                        jobs=jobs_sorted,
                        jobs_by_country=jobs_by_country,  # Добавляем группировку
                        preferences=preferences,
                        stats=stats,
                        search_time=round(search_time, 1),
                        countries=aggregator.countries if aggregator else {})

@app.route('/subscribe', methods=['POST'])
def subscribe():
    
    """Подписка на email уведомления с детальным логированием"""
    print("="*60)
    print("🔍 НАЧАЛО ФУНКЦИИ SUBSCRIBE")
    print(f"📧 Method: {request.method}")
    print(f"📧 Content-Type: {request.content_type}")
    print(f"📧 Request data: {request.data}")
    print("="*60)
    
    try:
        # Получаем данные из запроса
        if request.is_json:
            data = request.get_json()
            print(f"📧 JSON данные получены: {data}")
        else:
            data = request.form.to_dict()
            print(f"📧 Form данные получены: {data}")
        
        if not data:
            print("❌ Нет данных в запросе")
            return jsonify({'error': 'Нет данных в запросе'}), 400
        
        email = data.get('email', '').strip().lower()
        print(f"📧 Email из запроса: '{email}'")
        # >>> ЯЗЫК ПОДПИСКИ (вставить СРАЗУ ПОСЛЕ определения email)
        SUPPORTED_LANGS = {'ru', 'uk', 'en'}
        lang = (data.get('lang')
                or request.cookies.get('lang')
                or request.headers.get('X-Lang')
                or 'ru').lower()
        if lang not in SUPPORTED_LANGS:
            lang = 'ru'
        print(f"🌐 Язык подписки: {lang}")
        # <<< конец вставки
        # --- локализованные тексты для ответов этого метода
        MSG = {
        'ru': {
            'ok': 'Подписка оформлена! Проверьте email.',
            'ok_slow': 'Подписка оформлена! (Email может быть отправлен с задержкой)'
        },
        'en': {
            'ok': 'Subscription created! Check your email.',
            'ok_slow': 'Subscription created! (Email may be delayed)'
        },
        'uk': {
            'ok': 'Підписку оформлено! Перевірте email.',
            'ok_slow': 'Підписку оформлено! (Лист може надійти із затримкою)'
        }
        }
        # ---


        
        if not email or '@' not in email:
            print("❌ Неверный email")
            return jsonify({'error': 'Неверный email адрес'}), 400
        
        # Получаем предпочтения из сессии
        preferences = session.get('last_search_preferences', {})
        print(f"⚙️ Предпочтения из сессии: {preferences}")

        # ПРОВЕРКА: Есть ли выбранные профессии?
        if not preferences.get('selected_jobs') or not preferences.get('countries'):
            print("❌ Нет профессий или стран в сессии")
            return jsonify({
                'error': 'Сначала выберите профессии и страны, затем нажмите Найти работу, а потом подписывайтесь'
            }), 400
        
        print("🔍 Ищем существующего подписчика в БД...")
        existing = Subscriber.query.filter_by(email=email).first()
        print(f"👤 Результат поиска: {existing}")
        
        # ЛОГИКА: Если подписка существует и активна
        if existing and existing.is_active:
            print("✅ Найден активный подписчик, проверяем отличия...")
            
            # Получаем текущие предпочтения пользователя
            current_jobs = set(existing.get_selected_jobs() or [])
            current_countries = set(existing.get_countries() or [])
            
            # Получаем новые предпочтения из поиска
            new_jobs = set(preferences.get('selected_jobs', []))
            new_countries = set(preferences.get('countries', []))
            
            print(f"🔄 Текущие профессии: {current_jobs}")
            print(f"🔄 Новые профессии: {new_jobs}")
            print(f"🔄 Текущие страны: {current_countries}")
            print(f"🔄 Новые страны: {new_countries}")
            
            # Проверяем есть ли отличия
            if current_jobs == new_jobs and current_countries == new_countries:
                print("❌ Подписка с такими же параметрами уже существует")
                return jsonify({
                    'error': 'Вы уже подписаны на уведомления с такими же параметрами'
                }), 400
            
            # Есть отличия - отправляем информацию о конфликте
            print("🔄 Есть отличия, отправляем конфликт (409)...")
            return jsonify({
                'subscription_exists': True,
                'current_subscription': {
                    'jobs': list(current_jobs),
                    'countries': list(current_countries),
                    'city': existing.city,
                    'is_refugee': existing.is_refugee
                },
                'new_subscription': {
                    'jobs': list(new_jobs),
                    'countries': list(new_countries),
                    'city': preferences.get('city'),
                    'is_refugee': preferences.get('is_refugee', True)
                },
                'message': 'У вас уже есть подписка. Выберите действие:'
            }), 409  # 409 Conflict
        
        # Создаем новую подписку или активируем существующую
        print("🆕 Создаем новую подписку или активируем существующую...")
        
        if existing:
            print("🔄 Обновляем существующего подписчика...")
            existing.is_active = True
            if preferences.get('selected_jobs'):
                existing.set_selected_jobs(preferences['selected_jobs'])
            if preferences.get('countries'):
                existing.set_countries(preferences['countries'])
            existing.city = preferences.get('city')
            existing.is_refugee = preferences.get('is_refugee', True)
            existing.lang = lang
            subscriber = existing
        else:
            print("➕ Создаем нового подписчика...")
            subscriber = Subscriber(
                email=email,
                is_refugee=preferences.get('is_refugee', True),
                city=preferences.get('city'),
                frequency='weekly',
                lang=lang
            )
            if preferences.get('selected_jobs'):
                subscriber.set_selected_jobs(preferences['selected_jobs'])
            if preferences.get('countries'):
                subscriber.set_countries(preferences['countries'])
            db.session.add(subscriber)
        
        print("💾 Сохраняем в базу данных...")
        db.session.commit()
        print("✅ Подписчик сохранен в БД")
        
        # Отправляем welcome email с обработкой ошибок
        print("📧 Отправляем welcome email...")
        email_success = False
        try:
            from email_service import send_welcome_email
            email_success = send_welcome_email(app, email, lang=subscriber.lang)
            print(f"📧 Результат отправки email: {email_success}")
            
            if email_success:
                print("✅ Welcome email отправлен успешно")
                
                # Логируем успешную отправку
                log = EmailLog(
                    subscriber_id=subscriber.id,
                    email=email,
                    subject="Добро пожаловать в GlobalJobHunter!",
                    jobs_count=0,
                    status='sent',
                    sent_at=datetime.now()
                )
                db.session.add(log)
                db.session.commit()
                print("📝 Лог успешной отправки записан")
                
                return jsonify({'success': True, 'message': MSG[lang]['ok']})

            else:
                print("❌ Ошибка отправки welcome email")
                
                # Логируем ошибку отправки
                log = EmailLog(
                    subscriber_id=subscriber.id,
                    email=email,
                    subject="Добро пожаловать в GlobalJobHunter!",
                    jobs_count=0,
                    status='failed',
                    error_message='Failed to send welcome email',
                    sent_at=datetime.now()
                )
                db.session.add(log)
                db.session.commit()
                print("📝 Лог ошибки записан")
                
                return jsonify({'success': True, 'message': MSG[lang]['ok_slow']})

        except Exception as email_error:
            print(f"❌ ИСКЛЮЧЕНИЕ при отправке welcome email: {email_error}")
            import traceback
            traceback.print_exc()
            
            # Логируем исключение
            try:
                log = EmailLog(
                    subscriber_id=subscriber.id,
                    email=email,
                    subject="Добро пожаловать в GlobalJobHunter!",
                    jobs_count=0,
                    status='failed',
                    error_message=str(email_error),
                    sent_at=datetime.now()
                )
                db.session.add(log)
                db.session.commit()
                print("📝 Лог исключения записан")
            except Exception as log_error:
                print(f"❌ Ошибка записи лога: {log_error}")
            
            return jsonify({'success': True, 'message': MSG[lang]['ok_slow']})

        
    except Exception as e:
        print(f"❌ КРИТИЧЕСКОЕ ИСКЛЮЧЕНИЕ В SUBSCRIBE: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': f'Внутренняя ошибка сервера: {str(e)}'}), 500
    
    finally:
        print("="*60)
        print("🏁 КОНЕЦ ФУНКЦИИ SUBSCRIBE")
        print("="*60)

@app.route('/unsubscribe')
def unsubscribe():
    """Улучшенная отписка с уведомлением пользователя"""
    email = request.args.get('email')
    
    if not email:
        return render_template_string("""
        <!DOCTYPE html>
        <html lang="{{ request.cookies.get('lang','ru') }}">
        <head>
            <meta charset="utf-8">
            <script defer src="{{ url_for('static', filename='js/localization.js') }}"></script>                          
            <title>Ошибка отписки</title>
            <style>
                body { font-family: Arial; padding: 40px; text-align: center; background: #f8f9fa; }
                .card { background: white; padding: 40px; border-radius: 15px; box-shadow: 0 4px 20px rgba(0,0,0,0.1); max-width: 500px; margin: 0 auto; }
                .error { color: #dc3545; font-size: 3rem; margin-bottom: 20px; }
                h1 { color: #343a40; margin-bottom: 15px; }
                .btn { background: #007bff; color: white; padding: 12px 25px; text-decoration: none; border-radius: 8px; display: inline-block; margin-top: 20px; }
            </style>
        </head>
        <body>
            <div class="card">
                <div class="error">❌</div>
                <h1>Неверная ссылка</h1>
                <p>Email адрес не указан в ссылке для отписки.</p>
                <a href="/" class="btn">Вернуться на главную</a>
            </div>
        </body>
        </html>
        """)
    
    # Ищем подписчика
    subscriber = Subscriber.query.filter_by(email=email).first()
    
    if subscriber and subscriber.is_active:
        # Деактивируем подписку
        subscriber.is_active = False
        db.session.commit()
        
        print(f"✅ Пользователь {email} успешно отписался")
        
        # Показываем страницу успешной отписки
        return render_template_string("""
        <!DOCTYPE html>
        <html lang="{{ request.cookies.get('lang','ru') }}"
        <head>
            <meta charset="utf-8">
            <script defer src="{{ url_for('static', filename='js/localization.js') }}"></script>                          
            <title>Отписка выполнена</title>
            <style>
                body { 
                    font-family: 'Inter', -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; 
                    padding: 40px; text-align: center; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); 
                    min-height: 100vh; display: flex; align-items: center; justify-content: center; margin: 0;
                }
                .card { 
                    background: white; padding: 50px; border-radius: 20px; 
                    box-shadow: 0 20px 60px rgba(0,0,0,0.2); max-width: 600px; width: 100%;
                }
                .success { color: #28a745; font-size: 4rem; margin-bottom: 20px; }
                h1 { color: #343a40; margin-bottom: 20px; font-weight: 600; }
                p { color: #6c757d; line-height: 1.6; margin-bottom: 15px; }
                .email-highlight { 
                    background: #e3f2fd; color: #1976d2; padding: 8px 15px; 
                    border-radius: 20px; font-weight: 600; display: inline-block; margin: 10px 0;
                }
                .btn { 
                    background: #007bff; color: white; padding: 15px 30px; text-decoration: none; 
                    border-radius: 10px; display: inline-block; margin: 25px 10px 0; font-weight: 600;
                    transition: all 0.3s ease; box-shadow: 0 4px 15px rgba(0, 123, 255, 0.3);
                }
                .btn:hover { 
                    background: #0056b3; transform: translateY(-2px); text-decoration: none; color: white;
                    box-shadow: 0 8px 25px rgba(0, 123, 255, 0.4);
                }
                .btn-secondary { 
                    background: #6c757d; box-shadow: 0 4px 15px rgba(108, 117, 125, 0.3);
                }
                .btn-secondary:hover { 
                    background: #545b62; box-shadow: 0 8px 25px rgba(108, 117, 125, 0.4);
                }
                .info-box {
                    background: #f8f9fa; border: 1px solid #dee2e6; border-radius: 10px; 
                    padding: 20px; margin: 25px 0; text-align: left;
                }
                .info-box h4 { color: #495057; margin-bottom: 10px; }
                .info-box ul { margin: 10px 0; padding-left: 20px; }
                .info-box li { margin: 5px 0; color: #6c757d; }
            </style>
        </head>
        <body>
            <div class="card">
                <div class="success">✅</div>
                <h1 data-i18n="Вы успешно отписались!">Вы успешно отписались!</h1>
                <p data-i18n="Подписка на email-уведомления для адреса">Подписка на email-уведомления для адреса</p>
                <div class="email-highlight">{{ email }}</div>
                <p data-i18n="была деактивирована.">была деактивирована.</p>
                
                <div class="info-box">
                    <h4 data-i18n="📧 Что это означает:">📧 Что это означает:</h4>
                    <ul>
                        <li data-i18n="Вы больше не будете получать уведомления о новых вакансиях">Вы больше не будете получать уведомления о новых вакансиях</li>
                        <li data-i18n="Ваши данные остаются в системе (на случай повторной подписки)">Ваши данные остаются в системе (на случай повторной подписки)</li>
                        <li data-i18n="Вы можете в любое время подписаться снова через главную страницу">Вы можете в любое время подписаться снова через главную страницу</li>
                    </ul>
                </div>
                
                <div>
                    <a href="/" class="btn" data-i18n="🏠 Вернуться на главную">🏠 Вернуться на главную</a>
                    <a href="mailto:tzvanguardia@gmail.com?subject=Support%20GlobalJobHunter" class="btn btn-secondary" data-i18n="📬 Связаться с нами">📬 Связаться с нами</a>

                </div>
                
                <div style="margin-top: 30px; padding-top: 20px; border-top: 1px solid #dee2e6;">
                    <small style="color: #6c757d;">
                        <strong data-i18n="Передумали?">Передумали?</strong>
                        <span data-i18n="Вы всегда можете подписаться снова на">Вы всегда можете подписаться снова на</span>
                        <a href="/" style="color: #007bff;" data-i18n="на главной странице">на главной странице</a>
                    </small>

                </div>
            </div>
        </body>
        </html>
        """, email=email)
    
    elif subscriber and not subscriber.is_active:
        # Пользователь уже отписан
        return render_template_string("""
        <!DOCTYPE html>
        <html lang="{{ request.cookies.get('lang') or request.args.get('lang','ru') }}">
        <head>
            <meta charset="utf-8">
            <script defer src="{{ url_for('static', filename='js/localization.js') }}"></script>                          
            <title>Уже отписан</title>
            <script defer src="{{ url_for('static', filename='js/localization.js') }}"></script>
                          
            <style>
                body { 
                    font-family: 'Inter', Arial, sans-serif; padding: 40px; text-align: center; 
                    background: linear-gradient(135deg, #ffeaa7 0%, #fab1a0 100%); 
                    min-height: 100vh; display: flex; align-items: center; justify-content: center; margin: 0;
                }
                .card { 
                    background: white; padding: 50px; border-radius: 20px; 
                    box-shadow: 0 20px 60px rgba(0,0,0,0.2); max-width: 500px; width: 100%;
                }
                .info { color: #f39c12; font-size: 4rem; margin-bottom: 20px; }
                h1 { color: #343a40; margin-bottom: 20px; font-weight: 600; }
                .email-highlight { 
                    background: #fff3cd; color: #856404; padding: 8px 15px; 
                    border-radius: 20px; font-weight: 600; display: inline-block; margin: 10px 0;
                }
                .btn { 
                    background: #007bff; color: white; padding: 15px 30px; text-decoration: none; 
                    border-radius: 10px; display: inline-block; margin: 25px 10px 0; font-weight: 600;
                    transition: all 0.3s ease;
                }
                .btn:hover { background: #0056b3; transform: translateY(-2px); text-decoration: none; color: white; }
            </style>
        </head>
        <body>
            <div class="card">
                <div class="info">ℹ️</div>
                <h1 data-i18n="Вы уже отписаны">Вы уже отписаны</h1>

                <p data-i18n="Подписка для адреса">Подписка для адреса</p>

                <div class="email-highlight">{{ email }}</div>
                <p data-i18n="уже была деактивирована ранее.">уже была деактивирована ранее.</p>

                <p style="color: #6c757d; margin-top: 25px;" data-i18n="Хотите снова получать уведомления о вакансиях? Подпишитесь на главной странице!">Хотите снова получать уведомления о вакансиях? Подпишитесь на главной странице!</p>

                <a href="/" class="btn" data-i18n="🏠 Вернуться на главную">🏠 Вернуться на главную</a>
            </div>
        </body>
        </html>
        """, email=email)
    
    else:
        # Подписчик не найден
        return render_template_string("""
        <!DOCTYPE html>
        <html lang="{{ request.cookies.get('lang','ru') }}"
        <head>
            <meta charset="utf-8">
            <script defer src="{{ url_for('static', filename='js/localization.js') }}"></script>                          
            <title>Подписка не найдена</title>
            <style>
                body { 
                    font-family: 'Inter', Arial, sans-serif; padding: 40px; text-align: center; 
                    background: linear-gradient(135deg, #fdcb6e 0%, #e17055 100%); 
                    min-height: 100vh; display: flex; align-items: center; justify-content: center; margin: 0;
                }
                .card { 
                    background: white; padding: 50px; border-radius: 20px; 
                    box-shadow: 0 20px 60px rgba(0,0,0,0.2); max-width: 500px; width: 100%;
                }
                .warning { color: #e17055; font-size: 4rem; margin-bottom: 20px; }
                h1 { color: #343a40; margin-bottom: 20px; font-weight: 600; }
                .btn { 
                    background: #007bff; color: white; padding: 15px 30px; text-decoration: none; 
                    border-radius: 10px; display: inline-block; margin: 25px 10px 0; font-weight: 600;
                    transition: all 0.3s ease;
                }
                .btn:hover { background: #0056b3; transform: translateY(-2px); text-decoration: none; color: white; }
            </style>
        </head>
        <body>
            <div class="card">
                <div class="warning">⚠️</div>
                <h1>Подписка не найдена</h1>
                <p>Подписка для адреса <strong>{{ email }}</strong> не существует в нашей системе.</p>
                <p style="color: #6c757d; margin-top: 25px;">
                    Возможно, вы уже были отписаны ранее, или email адрес указан неверно.
                </p>
                <a href="/" class="btn" data-i18n="🏠 Вернуться на главную">🏠 Вернуться на главную</a>

            </div>
        </body>
        </html>
        """, email=email)

@app.route('/api/cache/stats')
def cache_stats():
   """API для получения статистики кеширования"""
   if not aggregator:
       return jsonify({'error': 'Сервис недоступен'}), 500
   
   stats = aggregator.get_cache_stats()
   return jsonify(stats)

@app.route('/api/cache/cleanup', methods=['POST'])
def cleanup_cache():
    """API для очистки кеша"""
    if not aggregator:
        return jsonify({'error': 'Сервис недоступен'}), 500
    
    try:
        aggregator.cleanup_cache()
        return """
        <html lang="{{ request.cookies.get('lang','ru') }}"
        <head><title>Кеш очищен</title><meta charset="utf-8"></head>
        <body style="font-family: Arial; padding: 40px; text-align: center;">
            <h1>✅ Кеш успешно очищен!</h1>
            <p>Все кешированные данные удалены</p>
            <a href="/admin/subscribers?key={}" style="background: #007bff; color: white; padding: 10px 20px; text-decoration: none; border-radius: 4px;">← Вернуться в админку</a>
        </body>
        </html>
        """.format(os.getenv('ADMIN_KEY'))
    except Exception as e:
        return f"Ошибка: {str(e)}", 500
   
@app.route('/admin/subscribers')
def admin_subscribers():
    """Расширенная админка для просмотра подписчиков"""
    admin_key = request.args.get('key')
    if admin_key != os.getenv('ADMIN_KEY'):
        return "Access Denied", 403
    
    subscribers = Subscriber.query.order_by(Subscriber.created_at.desc()).all()
    email_logs = EmailLog.query.order_by(EmailLog.sent_at.desc()).limit(10).all()
    
    stats = {
        'total': Subscriber.query.count(),
        'active': Subscriber.query.filter_by(is_active=True).count(),
        'inactive': Subscriber.query.filter_by(is_active=False).count(),
        'emails_sent': EmailLog.query.filter_by(status='sent').count(),
        'emails_failed': EmailLog.query.filter_by(status='failed').count()
    }
    
    html = f"""
    <!DOCTYPE html>
    <html lang="{{ request.cookies.get('lang','ru') }}"
    <head>
        <title>Админка подписчиков</title>
        <meta charset="utf-8">
        <script defer src="{{ url_for('static', filename='js/localization.js') }}"></script>
        <style>
            body {{ font-family: Arial, sans-serif; margin: 20px; background: #f8f9fa; }}
            .container {{ max-width: 1200px; margin: 0 auto; }}
            table {{ border-collapse: collapse; width: 100%; margin: 20px 0; background: white; }}
            th, td {{ border: 1px solid #ddd; padding: 12px; text-align: left; }}
            th {{ background-color: #007bff; color: white; }}
            .stats {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 20px; margin: 20px 0; }}
            .stat-card {{ background: white; padding: 20px; border-radius: 8px; text-align: center; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }}
            .stat-number {{ font-size: 2em; font-weight: bold; color: #007bff; }}
            .email-logs {{ background: white; padding: 20px; border-radius: 8px; margin: 20px 0; }}
            .nav {{ display: flex; gap: 20px; margin: 20px 0; }}
            .nav a {{ background: #007bff; color: white; padding: 10px 20px; text-decoration: none; border-radius: 4px; }}
            .job-list {{ font-size: 0.9em; color: #666; }}
        </style>
    </head>
    <body>
        <div class="container">
            <h1>📧 Админка подписчиков GlobalJobHunter</h1>
            
            <div class="nav">
                <a href="/">🏠 Главная</a>
                <a href="/admin/stats?key={admin_key}">📊 Статистика кеша</a>
                <a href="/health">💚 Здоровье системы</a>
                <a href="/admin/cache">🧹 Кэш</a>
            </div>
            
            <div class="stats">
                <div class="stat-card">
                    <div class="stat-number">{stats['total']}</div>
                    <p>Всего подписчиков</p>
                </div>
                <div class="stat-card">
                    <div class="stat-number">{stats['active']}</div>
                    <p>Активных</p>
                </div>
                <div class="stat-card">
                    <div class="stat-number">{stats['inactive']}</div>
                    <p>Неактивных</p>
                </div>
                <div class="stat-card">
                    <div class="stat-number">{stats['emails_sent']}</div>
                    <p>Email отправлено</p>
                </div>
                <div class="stat-card">
                    <div class="stat-number">{stats['emails_failed']}</div>
                    <p>Email ошибок</p>
                </div>
            </div>
            
            <h2>📋 Подписчики</h2>
            <table>
                <tr>
                    <th>Email</th>
                    <th>Статус</th>
                    <th>Беженец</th>
                    <th>Профессии</th>
                    <th>Страны</th>
                    <th>Город</th>
                    <th>Частота</th>
                    <th>Дата регистрации</th>
                </tr>
    """
    
    for sub in subscribers:
        status = "✅ Активен" if sub.is_active else "❌ Неактивен"
        refugee = "✅ Да" if sub.is_refugee else "❌ Нет"
        created = sub.created_at.strftime('%Y-%m-%d %H:%M')
        
        # Получаем профессии и страны
        jobs = ', '.join(sub.get_selected_jobs()[:3]) if sub.get_selected_jobs() else 'Не указано'
        if len(sub.get_selected_jobs()) > 3:
            jobs += f' (+{len(sub.get_selected_jobs())-3})'
            
        countries = ', '.join(sub.get_countries()) if sub.get_countries() else 'Не указано'
        city = sub.city or 'Не указан'
        frequency = sub.frequency or 'weekly'
        
        html += f"""
            <tr>
                <td>{sub.email}</td>
                <td>{status}</td>
                <td>{refugee}</td>
                <td class="job-list">{jobs}</td>
                <td>{countries}</td>
                <td>{city}</td>
                <td>{frequency}</td>
                <td>{created}</td>
            </tr>
        """
    
    html += """
        </table>
        
        <div class="email-logs">
            <h2>📨 Последние email логи</h2>
            <table>
                <tr>
                    <th>Email</th>
                    <th>Статус</th>
                    <th>Дата</th>
                </tr>
    """
    
    for log in email_logs:
        status_icon = "✅" if log.status == 'sent' else "❌"
        sent_time = log.sent_at.strftime('%Y-%m-%d %H:%M')
        html += f"""
            <tr>
                <td>{log.email}</td>
                <td>{status_icon} {log.status}</td>
                <td>{sent_time}</td>
            </tr>
        """
    
    html += """
            </table>
        </div>
        
        </div>
    </body>
    </html>
    """
    
    return html  

@app.route('/admin/stats')
def admin_stats():
    """Красивая админская статистика"""
    if not aggregator:
        return "Сервис недоступен", 500
    
    stats = aggregator.get_cache_stats()
    
    return f"""
    <!DOCTYPE html>
    <html lang="{{ request.cookies.get('lang','ru') }}"
    <head>
        <title>Статистика GlobalJobHunter</title>
        <meta charset="utf-8">
        <script defer src="{{ url_for('static', filename='js/localization.js') }}"></script>
        <style>
            body {{ font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; margin: 0; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: #333; }}
            .container {{ max-width: 1200px; margin: 0 auto; padding: 20px; }}
            .header {{ text-align: center; color: white; margin-bottom: 30px; }}
            .stats-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(250px, 1fr)); gap: 20px; margin: 30px 0; }}
            .stat-card {{ background: white; border-radius: 15px; padding: 25px; text-align: center; box-shadow: 0 8px 32px rgba(0,0,0,0.1); transition: transform 0.3s ease; }}
            .stat-card:hover {{ transform: translateY(-5px); }}
            .stat-number {{ font-size: 3em; font-weight: bold; margin: 10px 0; }}
            .stat-number.cache-hits {{ color: #28a745; }}
            .stat-number.cache-misses {{ color: #dc3545; }}
            .stat-number.api-requests {{ color: #007bff; }}
            .stat-number.jobs-found {{ color: #ffc107; }}
            .stat-number.hit-rate {{ color: #17a2b8; }}
            .sources-card {{ background: white; border-radius: 15px; padding: 25px; margin: 20px 0; box-shadow: 0 8px 32px rgba(0,0,0,0.1); }}
            .nav {{ display: flex; gap: 15px; justify-content: center; margin: 20px 0; flex-wrap: wrap; }}
            .nav a {{ background: rgba(255,255,255,0.2); color: white; padding: 12px 25px; text-decoration: none; border-radius: 25px; backdrop-filter: blur(10px); transition: background 0.3s ease; }}
            .nav a:hover {{ background: rgba(255,255,255,0.3); }}
            .cleanup-btn {{ background: linear-gradient(45deg, #ff6b6b, #ee5a24); color: white; padding: 12px 30px; border: none; border-radius: 25px; font-size: 16px; cursor: pointer; transition: transform 0.3s ease; }}
            .cleanup-btn:hover {{ transform: scale(1.05); }}
            .source-tag {{ display: inline-block; background: #007bff; color: white; padding: 5px 15px; border-radius: 20px; margin: 5px; font-size: 0.9em; }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>📊 Статистика GlobalJobHunter</h1>
                <p>Мониторинг производительности и кеширования</p>
            </div>
            
            <div class="nav">
                <a href="/">🏠 Главная</a>
                <a href="/admin/subscribers?key={os.getenv('ADMIN_KEY')}">👥 Подписчики</a>
                <a href="/health">💚 Здоровье системы</a>
                <a href="/admin/cache">🧹 Кэш</a>
            </div>
            
            <div class="sources-card">
                <h2>🔗 Активные источники вакансий</h2>
                <div>
                    <span class="source-tag">📋 Adzuna API</span>
                    {"".join([f'<span class="source-tag">🌐 {source.title()}</span>' for source in additional_aggregators.keys()])}
                </div>
            </div>
            
            <div class="stats-grid">
                <div class="stat-card">
                    <div class="stat-number cache-hits">{stats['cache_hits']}</div>
                    <h3>Cache Hits</h3>
                    <p>Успешные попадания в кеш</p>
                </div>
                
                <div class="stat-card">
                    <div class="stat-number cache-misses">{stats['cache_misses']}</div>
                    <h3>Cache Misses</h3>
                    <p>Промахи кеша</p>
                </div>
                
                <div class="stat-card">
                    <div class="stat-number hit-rate">{stats['cache_hit_rate']}</div>
                    <h3>Hit Rate</h3>
                    <p>Эффективность кеша</p>
                </div>
                
                <div class="stat-card">
                    <div class="stat-number api-requests">{stats['api_requests']}</div>
                    <h3>API Requests</h3>
                    <p>Запросы к внешним API</p>
                </div>
                
                <div class="stat-card">
                    <div class="stat-number jobs-found">{stats['total_jobs_found']}</div>
                    <h3>Jobs Found</h3>
                    <p>Всего найдено вакансий</p>
                </div>
            </div>
            
            <div style="text-align: center; margin: 30px 0;">
                <form method="post" action="/api/cache/cleanup" style="display: inline;">
                    <button type="submit" class="cleanup-btn">
                        🗑️ Очистить кеш
                    </button>
                </form>
            </div>
        </div>
    </body>
    </html>
    """

@app.route('/api/jobs/<job_id>')
def job_details(job_id):
   """API для получения деталей вакансии"""
   results_id = session.get('results_id')
   if not results_id or not aggregator or results_id not in aggregator.search_cache:
       return jsonify({'error': 'Результаты поиска не найдены или устарели'}), 404
       
   job = aggregator.search_cache[results_id].get(job_id)
   
   if not job:
       return jsonify({'error': 'Вакансия не найдена'}), 404
   
   return jsonify(job)

@app.route('/favicon.ico')
def favicon():
   """Обработка favicon"""
   return '', 204

# app.py
@app.route('/health')
def health_check():
    """Статус системы — локализованная страница для модалки."""
    try:
        # 1) Язык интерфейса
        lang = (request.args.get('lang') or request.cookies.get('lang') or 'ru').lower()
        if lang not in ('ru', 'uk', 'en'):
            lang = 'ru'

        # 2) Данные
        if aggregator:
            cache_stats = aggregator.get_cache_stats()
        else:
            cache_stats = {
                'api_requests': 0,
                'cache_hits': 0,
                'cache_misses': 0,
                'cache_hit_rate': '0.0%',
                'total_jobs_found': 0
            }
        additional_sources = list(additional_aggregators.keys()) if additional_aggregators else []

        # 3) Словарь
        T = {
            'ru': {
                'status_ok': 'Система работает нормально',
                'main_agg': 'Основной агрегатор',
                'online': 'Работает',
                'offline': 'Недоступен',
                'add_sources': 'Дополнительные источники',
                'none': 'Нет',
                'api_requests': 'API запросов',
                'cache_hits': 'Попаданий в кеш',
                'cache_misses': 'Промахов кеша',
                'cache_eff': 'Эффективность кеша',
                'total_found': 'Всего найдено вакансий',
                'checked_at': 'Время проверки'
            },
            'en': {
                'status_ok': 'System is operating normally',
                'main_agg': 'Main aggregator',
                'online': 'Online',
                'offline': 'Offline',
                'add_sources': 'Additional sources',
                'none': 'None',
                'api_requests': 'API requests',
                'cache_hits': 'Cache hits',
                'cache_misses': 'Cache misses',
                'cache_eff': 'Cache hit rate',
                'total_found': 'Total jobs found',
                'checked_at': 'Checked at'
            },
            'uk': {
                'status_ok': 'Система працює нормально',
                'main_agg': 'Основний агрегатор',
                'online': 'Працює',
                'offline': 'Недоступний',
                'add_sources': 'Додаткові джерела',
                'none': 'Немає',
                'api_requests': 'Запити до API',
                'cache_hits': 'Влучань у кеш',
                'cache_misses': 'Промахів кешу',
                'cache_eff': 'Ефективність кешу',
                'total_found': 'Всього знайдено вакансій',
                'checked_at': 'Час перевірки'
            }
        }
        t = T[lang]

        # 4) HTML
        html = f"""
        <!DOCTYPE html>
        <html lang="{lang}">
        <head>
            <meta charset="utf-8">
            <script defer src="{{ url_for('static', filename='js/localization.js') }}"></script>
            <style>
                body {{ font-family: -apple-system, Segoe UI, Roboto, Arial; margin:0; padding:16px; background:#f7f7f9; }}
                .container {{ max-width: 720px; margin:0 auto; }}
                .status-card {{ background:#fff; border-radius:12px; padding:20px; box-shadow:0 4px 14px rgba(0,0,0,.06); }}
                .status-ok {{ color:#28a745; font-size:1.2rem; margin:0 0 12px; }}
                .status-item {{ display:flex; justify-content:space-between; gap:12px; padding:6px 0; border-bottom:1px solid #eee; }}
                .status-item:last-child {{ border-bottom:0; }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="status-card">
                    <h2 class="status-ok">🟢 {t['status_ok']}</h2>
                    <div class="status-item">
                        <span>{t['main_agg']}:</span>
                        <span>{'✅ ' + t['online'] if aggregator else '❌ ' + t['offline']}</span>
                    </div>
                    <div class="status-item">
                        <span>{t['add_sources']}:</span>
                        <span>{', '.join(additional_sources) if additional_sources else t['none']}</span>
                    </div>
                    <div class="status-item"><span>{t['api_requests']}:</span><span>{cache_stats.get('api_requests', 0)}</span></div>
                    <div class="status-item"><span>{t['cache_hits']}:</span><span>{cache_stats.get('cache_hits', 0)}</span></div>
                    <div class="status-item"><span>{t['cache_misses']}:</span><span>{cache_stats.get('cache_misses', 0)}</span></div>
                    <div class="status-item"><span>{t['cache_eff']}:</span><span>{cache_stats.get('cache_hit_rate', '0.0%')}</span></div>
                    <div class="status-item"><span>{t['total_found']}:</span><span>{cache_stats.get('total_jobs_found', 0)}</span></div>
                    <div class="status-item"><span>{t['checked_at']}:</span><span>{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</span></div>
                </div>
            </div>
        </body>
        </html>
        """
        return html
    except Exception as e:
        return f"<pre>health error: {e}</pre>", 500

@app.errorhandler(404)
def not_found(error):
   return render_template('error.html', error="Страница не найдена"), 404

@app.errorhandler(500)
def internal_error(error):
   return render_template('error.html', error="Внутренняя ошибка сервера"), 500

@app.route('/subscription/manage')
def manage_subscription():
    """Страница управления подпиской"""
    email = request.args.get('email')
    if not email:
        flash('Неверная ссылка', 'error')
        return redirect(url_for('index'))
    
    subscriber = Subscriber.query.filter_by(email=email, is_active=True).first()
    if not subscriber:
        flash('Подписка не найдена', 'error')
        return redirect(url_for('index'))
    
    return render_template('manage_subscription.html', 
                         subscriber=subscriber,
                         job_categories=aggregator.specific_jobs if aggregator else {},
                         countries=aggregator.countries if aggregator else {})

@app.route('/subscription/update_preferences', methods=['POST'])
def update_subscription_preferences():
    """Обновление предпочтений подписки со страницы управления"""
    try:
        email = request.form.get('email')
        if not email:
            return jsonify({'error': 'Email не указан'}), 400
        
        subscriber = Subscriber.query.filter_by(email=email, is_active=True).first()
        if not subscriber:
            return jsonify({'error': 'Подписка не найдена'}), 404
        # --- ЯЗЫК ИНТЕРФЕЙСА: берём из формы / cookie / заголовка и сохраняем в подписчике
        lang = (request.form.get('lang') or
                request.cookies.get('lang') or
                request.headers.get('X-Lang') or 'ru').lower()
        if lang in ('ru', 'en', 'uk'):
            subscriber.lang = lang
        # --- конец вставки

        
        # Обновляем данные
        subscriber.is_refugee = request.form.get('is_refugee') == 'on'
        
        # Обновляем профессии
        selected_jobs = request.form.getlist('selected_jobs')
        if selected_jobs:
            subscriber.set_selected_jobs(selected_jobs)
        
        # Обновляем страны
        countries = request.form.getlist('countries')
        if countries:
            subscriber.set_countries(countries)
        
        # Обновляем город и частоту
        subscriber.city = request.form.get('city', '').strip() or None
        subscriber.frequency = request.form.get('frequency', 'weekly')
        
        db.session.commit()
        
        # ✅ ОТПРАВЛЯЕМ EMAIL О ИЗМЕНЕНИЯХ
        try:
            send_preferences_update_email(app, subscriber)
            print(f"✅ Email об изменении настроек отправлен на {email}")
            message = 'Настройки успешно обновлены! Проверьте email для подтверждения.'
        except Exception as e:
            print(f"❌ Ошибка отправки email: {e}")
            message = 'Настройки обновлены, но email не отправлен из-за технической ошибки.'
        
        return jsonify({'success': True, 'message': message})
        
    except Exception as e:
        print(f"❌ Ошибка обновления предпочтений: {e}")
        return jsonify({'error': 'Ошибка при сохранении изменений'}), 500
        
    

@app.route('/subscribe/update', methods=['POST'])
def update_existing_subscription():
    """Обновление существующей подписки"""
    print("🚨 ФУНКЦИЯ ВЫЗВАНА! 🚨")  # ДОБАВИТЬ ЭТУ СТРОКУ В САМОЕ НАЧАЛО
    try:
        data = request.json or request.form.to_dict()
        email = data.get('email', '').strip().lower()
        action = data.get('action')  # 'replace' или 'merge'
        
        print(f"🔄 Обновляем подписку: email={email}, action={action}")  # ДОБАВЛЕНО
        
        preferences = session.get('last_search_preferences', {})
        existing = Subscriber.query.filter_by(email=email).first()
        
        if not existing:
            return jsonify({'error': 'Подписка не найдена'}), 404
        
        print(f"✅ Подписчик найден: {existing.email}")  # ДОБАВЛЕНО
        
        if action == 'replace':
            print("🔄 Выполняем замену подписки...")  # ДОБАВЛЕНО
            # Заменяем подписку
            existing.set_selected_jobs(preferences.get('selected_jobs', []))
            existing.set_countries(preferences.get('countries', []))
            existing.city = preferences.get('city')
            existing.is_refugee = preferences.get('is_refugee', True)
            
            db.session.commit()
            print("✅ Данные сохранены в БД")  # ДОБАВЛЕНО
            
            # ОТПРАВЛЯЕМ EMAIL
            print(f"📧 Пытаемся отправить email на {email}...")  # ДОБАВЛЕНО
            try:
                result = send_preferences_update_email(app, existing)
                print(f"📧 Результат отправки email: {result}")  # ДОБАВЛЕНО
                if result:
                    print(f"✅ Email об обновлении отправлен на {email}")
                else:
                    print(f"❌ Email НЕ отправлен на {email}")
            except Exception as e:
                print(f"❌ ИСКЛЮЧЕНИЕ при отправке email: {e}")
                import traceback
                traceback.print_exc()  # ДОБАВЛЕНО
            
            return jsonify({'success': True, 'message': 'Подписка обновлена! Старые параметры заменены новыми. Проверьте email для подтверждения.'})
            
        elif action == 'merge':
            print("🔄 Выполняем объединение подписки...")  # ДОБАВЛЕНО
            # Объединяем подписки
            current_jobs = set(existing.get_selected_jobs() or [])
            current_countries = set(existing.get_countries() or [])
            
            new_jobs = set(preferences.get('selected_jobs', []))
            new_countries = set(preferences.get('countries', []))
            
            # Объединяем списки
            merged_jobs = list(current_jobs.union(new_jobs))
            merged_countries = list(current_countries.union(new_countries))
            
            existing.set_selected_jobs(merged_jobs)
            existing.set_countries(merged_countries)
            
            db.session.commit()
            print("✅ Данные объединены и сохранены в БД")  # ДОБАВЛЕНО
            
            # ОТПРАВЛЯЕМ EMAIL
            print(f"📧 Пытаемся отправить email на {email}...")  # ДОБАВЛЕНО
            try:
                result = send_preferences_update_email(app, existing)
                print(f"📧 Результат отправки email: {result}")  # ДОБАВЛЕНО
                if result:
                    print(f"✅ Email об объединении отправлен на {email}")
                else:
                    print(f"❌ Email НЕ отправлен на {email}")
            except Exception as e:
                print(f"❌ ИСКЛЮЧЕНИЕ при отправке email: {e}")
                import traceback
                traceback.print_exc()  # ДОБАВЛЕНО
            
            return jsonify({'success': True, 'message': f'Подписка расширена! Теперь вы получаете уведомления по {len(merged_jobs)} профессиям в {len(merged_countries)} странах. Проверьте email для подтверждения.'})
        
        return jsonify({'error': 'Неверное действие'}), 400
        
    except Exception as e:
        print(f"❌ ОБЩАЯ ошибка обновления подписки: {e}")
        import traceback
        traceback.print_exc()  # ДОБАВЛЕНО
        return jsonify({'error': 'Ошибка при обновлении подписки'}), 500
   
@app.route('/admin')
def admin_login_page():
    """Страница входа в админку"""
    error_message = '<div class="error">❌ Неверный логин или пароль</div>' if request.args.get('error') else ''
    
    return f"""
    <!DOCTYPE html>
    <html lang="{{ request.cookies.get('lang','ru') }}"
    <head>
        <title>Вход в админку</title>
        <meta charset="utf-8">
        <script defer src="{{ url_for('static', filename='js/localization.js') }}"></script>
        <style>
            body {{ font-family: Arial; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); 
                   height: 100vh; display: flex; align-items: center; justify-content: center; margin: 0; }}
            .login-form {{ background: white; padding: 40px; border-radius: 15px; box-shadow: 0 10px 30px rgba(0,0,0,0.3); 
                         width: 400px; text-align: center; }}
            .form-group {{ margin: 20px 0; text-align: left; }}
            label {{ display: block; margin-bottom: 5px; font-weight: bold; }}
            input[type="text"], input[type="password"] {{ width: 100%; padding: 12px; border: 1px solid #ddd; 
                                                        border-radius: 8px; font-size: 16px; box-sizing: border-box; }}
            .btn-login {{ background: #007bff; color: white; padding: 12px 30px; border: none; 
                        border-radius: 8px; font-size: 16px; cursor: pointer; width: 100%; }}
            .btn-login:hover {{ background: #0056b3; }}
            .error {{ color: red; margin-top: 10px; }}
            h2 {{ color: #333; margin-bottom: 30px; }}
        </style>
    </head>
    <body>
        <div class="login-form">
            <h2>🔐 Вход в админку</h2>
            <form method="POST" action="/admin/login">
                <div class="form-group">
                    <label for="username">Логин:</label>
                    <input type="text" id="username" name="username" required>
                </div>
                <div class="form-group">
                    <label for="password">Пароль:</label>
                    <input type="password" id="password" name="password" required>
                </div>
                <button type="submit" class="btn-login">Войти</button>
                {error_message}
            </form>
        </div>
    </body>
    </html>
    """

@app.route('/admin/login', methods=['POST'])
def admin_login():
    """Обработка входа в админку"""
    username = request.form.get('username')
    password = request.form.get('password')
    
    # Проверяем учетные данные
    if username == 'admin' and password == 'VsemSosat':
        # Сохраняем в сессии что пользователь авторизован
        session['admin_logged_in'] = True
        return redirect(url_for('admin_dashboard'))
    else:
        return redirect(url_for('admin_login_page') + '?error=1')
    
@app.route('/admin/send-emails', methods=['POST'])
def admin_send_emails():
    """Принудительная отправка email рассылки с улучшенной диагностикой"""
    try:
        print("🔄 Админ запустил принудительную отправку рассылки...")
        
        # Проверяем количество активных подписчиков
        active_subscribers = Subscriber.query.filter_by(is_active=True).all()
        total_subscribers = Subscriber.query.count()
        
        print(f"👥 Найдено подписчиков: всего={total_subscribers}, активных={len(active_subscribers)}")
        
        if len(active_subscribers) == 0:
            if total_subscribers == 0:
                flash('ℹ️ В базе данных нет ни одного подписчика. Добавьте тестовую подписку через главную страницу.', 'info')
            else:
                flash(f'ℹ️ Найдено {total_subscribers} подписчиков, но все неактивны. Рассылка не отправлена.', 'warning')
            
            print("ℹ️ Нет активных подписчиков для рассылки")
            return redirect('/admin/dashboard')
        
        # Если есть активные подписчики - отправляем
        from email_service import send_job_notifications
        # Передаем основной и дополнительные агрегаторы
        sent_count = send_job_notifications(app, aggregator, additional_aggregators)
        
        if sent_count > 0:
            flash(f'✅ Рассылка завершена! Отправлено {sent_count} из {len(active_subscribers)} писем', 'success')
            print(f"✅ Принудительная рассылка завершена: {sent_count} писем")
        else:
            flash(f'⚠️ Рассылка завершена, но ни одно письмо не отправлено. Проверьте настройки email или предпочтения подписчиков.', 'warning')
            print(f"⚠️ Принудительная рассылка завершена: 0 писем отправлено")
        
    except Exception as e:
        flash(f'❌ Ошибка отправки рассылки: {str(e)}', 'error')
        print(f"❌ Ошибка принудительной рассылки: {e}")
        
    return redirect('/admin/dashboard')

@app.route('/admin/test-email', methods=['GET', 'POST'])  
def admin_test_email():
    """Отправка тестового email на указанный адрес"""
    if not session.get('admin_logged_in'):
        return redirect(url_for('admin_login_page'))
    
    if request.method == 'GET':
        # Показываем форму для ввода email
        return """
        <!DOCTYPE html>
        <html lang="{{ request.cookies.get('lang','ru') }}"
        <head>
            <title>Тестовая отправка</title>
            <meta charset="utf-8">
            <script defer src="{{ url_for('static', filename='js/localization.js') }}"></script>
            <style>
                body { font-family: Arial; background: #f8f9fa; padding: 20px; }
                .container { max-width: 600px; margin: 0 auto; background: white; padding: 30px; border-radius: 10px; }
                .btn { background: #007bff; color: white; padding: 12px 25px; border: none; border-radius: 5px; cursor: pointer; text-decoration: none; display: inline-block; margin: 10px 5px; }
                .btn-secondary { background: #6c757d; }
                .form-group { margin: 20px 0; }
                label { display: block; margin-bottom: 5px; font-weight: bold; }
                input[type="email"] { width: 100%; padding: 10px; border: 1px solid #ddd; border-radius: 5px; box-sizing: border-box; }
                .alert { padding: 15px; margin: 20px 0; border-radius: 5px; background: #d1ecf1; border: 1px solid #bee5eb; color: #0c5460; }
            </style>
        </head>
        <body>
            <div class="container">
                <h2>📧 Тестовая отправка email</h2>
                
                <div class="alert">
                    <strong>ℹ️ Информация:</strong><br>
                    Эта функция отправит тестовое письмо с несколькими вакансиями на указанный email адрес.
                    Полезно для проверки работы email системы и внешнего вида писем.
                </div>
                
                <form method="post">
                    <div class="form-group">
                        <label for="test_email">Email для тестовой отправки:</label>
                        <input type="email" id="test_email" name="test_email" required placeholder="test@example.com">
                    </div>
                    
                    <button type="submit" class="btn">📧 Отправить тестовое письмо</button>
                    <a href="/admin/dashboard" class="btn btn-secondary">❌ Отмена</a>
                </form>
            </div>
        </body>
        </html>
        """
    
    else:
        # Обрабатываем отправку тестового email
        try:
            test_email = request.form.get('test_email', '').strip()
            
            if not test_email or '@' not in test_email:
                flash('❌ Введите корректный email адрес', 'error')
                return redirect('/admin/test-email')
            
            # Создаем временного тестового подписчика
            test_preferences = {
                'is_refugee': True,
                'selected_jobs': ['Водитель', 'Разнорабочий', 'Официант'],
                'countries': ['de', 'pl'],
                'city': 'Berlin'
            }
            
            # Ищем несколько тестовых вакансий
            if aggregator:
                test_jobs = aggregator.search_specific_jobs(test_preferences)
                if not test_jobs:
                    # Если реальных вакансий нет, создаем тестовые
                    from email_service import create_fallback_jobs
                    test_jobs = create_fallback_jobs(test_preferences)
            else:
                from email_service import create_fallback_jobs
                test_jobs = create_fallback_jobs(test_preferences)
            
            # Отправляем тестовый email
            from email_service import send_job_email
            
            # Создаем временный объект подписчика для тестирования!
            class TestSubscriber:
                def __init__(self, email):
                    self.email = email
                    self.id = 'test'
            
            test_subscriber = TestSubscriber(test_email)
            
            success = send_job_email(app, test_subscriber, test_jobs[:10], test_preferences)
            
            if success:
                flash(f'✅ Тестовое письмо успешно отправлено на {test_email}!', 'success')
                print(f"✅ Тестовое письмо отправлено на {test_email}")
            else:
                flash(f'❌ Не удалось отправить тестовое письмо на {test_email}', 'error')
                print(f"❌ Ошибка отправки тестового письма на {test_email}")
                
        except Exception as e:
            flash(f'❌ Ошибка тестовой отправки: {str(e)}', 'error')
            print(f"❌ Ошибка тестовой отправки: {e}")
        
        return redirect('/admin/dashboard')   

@app.route('/admin/dashboard')
def admin_dashboard():
    """Главная страница админки с flash сообщениями"""
    if not session.get('admin_logged_in'):
        return redirect(url_for('admin_login_page'))
    
    # Получаем статистику для отображения
    try:
        total_subscribers = Subscriber.query.count()
        active_subscribers = Subscriber.query.filter_by(is_active=True).count()
    except:
        total_subscribers = 0
        active_subscribers = 0
    
    return render_template_string(f"""
    <!DOCTYPE html>
    <html lang="{{ request.cookies.get('lang','ru') }}"
    <head>
        <title>Админка GlobalJobHunter</title>
        <meta charset="utf-8">
        <script defer src="{{ url_for('static', filename='js/localization.js') }}"></script>
        <style>
            body {{ font-family: Arial; background: #f8f9fa; margin: 0; padding: 20px; }}
            .container {{ max-width: 1200px; margin: 0 auto; }}
            .header {{ background: white; padding: 20px; border-radius: 8px; margin-bottom: 20px; 
                       display: flex; justify-content: space-between; align-items: center; }}
            .nav {{ display: flex; gap: 15px; }}
            .nav a {{ background: #007bff; color: white; padding: 10px 20px; text-decoration: none; 
                     border-radius: 5px; transition: background 0.3s; }}
            .nav a:hover {{ background: #0056b3; }}
            .logout {{ background: #dc3545; }}
            .logout:hover {{ background: #c82333; }}
            .backup-section {{ background: white; padding: 30px; border-radius: 8px; margin: 20px 0; }}
            .backup-btn {{ display: inline-block; padding: 12px 25px; margin: 10px; text-decoration: none; 
                          border-radius: 5px; font-weight: bold; transition: all 0.3s; border: none; cursor: pointer; font-size: 16px; }}
            .btn-download {{ background: #28a745; color: white; }}
            .btn-download:hover {{ background: #218838; color: white; }}
            .btn-upload {{ background: #ffc107; color: #000; }}
            .btn-upload:hover {{ background: #e0a800; color: #000; }}
            .stats-info {{ background: #e3f2fd; padding: 15px; border-radius: 8px; margin: 15px 0; 
                          border-left: 4px solid #2196f3; }}
        </style>
    </head>
    <body>
        <div class="container">
            <!-- Flash сообщения -->
            {{% with messages = get_flashed_messages(with_categories=true) %}}
                {{% if messages %}}
                    <div style="margin: 20px 0;">
                        {{% for category, message in messages %}}
                            <div class="alert alert-{{{{ 'success' if category == 'success' else 'danger' if category == 'error' else 'warning' if category == 'warning' else 'info' }}}}" 
                                 style="padding: 15px; margin: 10px 0; border-radius: 8px; 
                                        background: {{{{ '#d4edda' if category == 'success' else '#f8d7da' if category == 'error' else '#fff3cd' if category == 'warning' else '#d1ecf1' }}}}; 
                                        color: {{{{ '#155724' if category == 'success' else '#721c24' if category == 'error' else '#856404' if category == 'warning' else '#0c5460' }}}}; 
                                        border: 1px solid {{{{ '#c3e6cb' if category == 'success' else '#f5c6cb' if category == 'error' else '#ffeaa7' if category == 'warning' else '#bee5eb' }}}};">
                                <strong>
                                    {{{{ '✅' if category == 'success' else '❌' if category == 'error' else '⚠️' if category == 'warning' else 'ℹ️' }}}}
                                </strong>
                                {{{{ message }}}}
                            </div>
                        {{% endfor %}}
                    </div>
                {{% endif %}}
            {{% endwith %}}
            
            <div class="header">
                <h1>🛠️ Админка GlobalJobHunter</h1>
                <div class="nav">
                    <a href="/admin/subscribers_secure">👥 Подписчики</a>
                    <a href="/admin/stats_secure">📊 Статистика</a>
                    <a href="/health">💚 Здоровье системы</a>
                    <a href="/admin/cache">🧹 Кэш</a>              
                    <a href="/admin/logout" class="logout">🚪 Выйти</a>
                </div>
            </div>
            
            <div style="background: white; padding: 30px; border-radius: 8px; text-align: center;">
                <h2>Добро пожаловать в админку!</h2>
                <p>Выберите нужный раздел в меню выше</p>
                
                <div class="stats-info">
                    <strong>📊 Текущая статистика:</strong><br>
                    👥 Всего подписчиков: {total_subscribers} | 
                    ✅ Активных: {active_subscribers} | 
                    ❌ Неактивных: {total_subscribers - active_subscribers}
                </div>
            </div>
            
            <!-- Секция Email рассылки -->
            <div class="backup-section">
                <h3>📧 Email рассылка</h3>
                <p>Отправить уведомления всем активным подписчикам или протестировать систему</p>
                <div style="text-align: center;">
                    <form method="POST" action="/admin/send-emails" style="display: inline;">
                        <button type="submit" class="backup-btn" 
                                onclick="return confirm('Отправить email всем активным подписчикам прямо сейчас?\\n\\nАктивных подписчиков: {active_subscribers}')"
                                style="background: #007bff; color: white;">
                            📧 Отправить рассылку сейчас ({active_subscribers} подписчиков)
                        </button>
                    </form>
                    <a href="/admin/test-email" class="backup-btn" 
                       style="background: #28a745; color: white; text-decoration: none;">
                        🧪 Тестовая отправка
                    </a>
                </div>
            </div>
            
            <div class="backup-section">
                <h3>🗄️ Управление базой данных</h3>
                <p>Скачайте текущую базу данных или загрузите резервную копию</p>
                <div style="text-align: center;">
                    <a href="/admin/download_backup" class="backup-btn btn-download">📦 Скачать базу</a>
                    <a href="/admin/upload_backup" class="backup-btn btn-upload">📁 Загрузить базу</a>
                </div>
            </div>
        </div>
    </body>
    </html>
    """)
# ====== КЭШ: каталоги и утилиты ======
CACHE_DIRS = [
    Path("cache"),
    Path("search_cache"),
    Path("temp_jobs"),
]
CACHE_PATTERNS = ("*.pkl", "*.json", "*.cache", "*.tmp")

def _human_bytes(n: int) -> str:
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if n < 1024:
            return f"{n:.1f} {unit}"
        n /= 1024
    return f"{n:.1f} PB"

def _iter_cache_files():
    """Итерирует по всем файлам кэша во всех каталогах."""
    for base in CACHE_DIRS:
        if not base.exists():
            continue
        for pattern in CACHE_PATTERNS:
            yield from base.rglob(pattern)

def cleanup_old_cache(days: int = 3):
    """Удаляет файлы старше N дней. Возвращает статистику."""
    cutoff = time.time() - days * 86400
    stat = {"deleted": 0, "kept": 0, "freed": 0, "errors": 0}

    for f in _iter_cache_files():
        try:
            mtime = f.stat().st_mtime
            if mtime < cutoff:
                size = f.stat().st_size
                f.unlink()
                stat["deleted"] += 1
                stat["freed"] += size
            else:
                stat["kept"] += 1
        except Exception:
            stat["errors"] += 1

    # подчистим пустые папки
    for base in CACHE_DIRS:
        if base.exists():
            for d in sorted([p for p in base.rglob("*") if p.is_dir()], reverse=True):
                try:
                    next(d.iterdir())
                except StopIteration:
                    d.rmdir()
                except Exception:
                    pass
    return stat

@app.route("/admin/cache", methods=["GET", "POST"])
def admin_cache_page():
    # тот же флаг, что и в твоей админке
    if not session.get('admin_logged_in'):
        return redirect(url_for('admin_login_page'))

    message = ""
    if request.method == "POST":
        mode = request.form.get("mode", "old")
        days = int(request.form.get("days", 3) or 3)

        if mode == "all":
            st = purge_all_cache()
            message = f"Удалено {st['deleted']} файлов, освобождено {_human_bytes(st['freed'])}. Ошибок: {st['errors']}."
        else:
            st = cleanup_old_cache(days=days)
            message = (
                f"Удалено {st['deleted']} старых файлов, освобождено {_human_bytes(st['freed'])}. "
                f"Оставлено {st['kept']}. Ошибок: {st['errors']}."
            )

    return render_template_string(f"""
    <!DOCTYPE html>
    <html lang="{{ request.cookies.get('lang','ru') }}"
    <head>
        <meta charset="utf-8">
        <script defer src="{{ url_for('static', filename='js/localization.js') }}"></script>
        <title>Управление кэшем — Admin</title>
        <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.2/dist/css/bootstrap.min.css" rel="stylesheet">
    </head>
    <body class="p-4">
      <div class="container">
        <div class="d-flex justify-content-between align-items-center mb-3">
          <h2>Управление кэшем</h2>
          <div>
            <a class="btn btn-secondary" href="{url_for('admin_dashboard')}">← В админку</a>
          </div>
        </div>

        {f"<div class='alert alert-info'>{message}</div>" if message else ""}

        <div class="card mb-4">
          <div class="card-body">
            <h5>Очистить старый кэш</h5>
            <form method="post" class="row g-2 align-items-center" onsubmit="return confirm('Удалить кэш старше N дней?');">
              <input type="hidden" name="mode" value="old">
              <div class="col-auto">
                <label for="days" class="col-form-label">Старше (дней):</label>
              </div>
              <div class="col-auto">
                <input id="days" name="days" type="number" value="3" min="1" class="form-control">
              </div>
              <div class="col-auto">
                <button class="btn btn-warning" type="submit">Очистить</button>
              </div>
            </form>
          </div>
        </div>

        <div class="card">
          <div class="card-body">
            <h5>Удалить весь кэш</h5>
            <form method="post" onsubmit="return confirm('Точно удалить ВСЁ? Действие необратимо.');">
              <input type="hidden" name="mode" value="all">
              <button class="btn btn-danger" type="submit">Удалить всё</button>
            </form>
          </div>
        </div>
      </div>
    </body>
    </html>
    """)


def purge_all_cache():
    """Удаляет вообще все файлы кэша во всех каталогах."""
    stat = {"deleted": 0, "freed": 0, "errors": 0}
    for f in _iter_cache_files():
        try:
            size = f.stat().st_size
            f.unlink()
            stat["deleted"] += 1
            stat["freed"] += size
        except Exception:
            stat["errors"] += 1

    for base in CACHE_DIRS:
        if base.exists():
            for d in sorted([p for p in base.rglob("*") if p.is_dir()], reverse=True):
                try:
                    next(d.iterdir())
                except StopIteration:
                    d.rmdir()
                except Exception:
                    pass
    return stat

@app.route('/admin/logout')
def admin_logout():
    """Выход из админки"""
    session.pop('admin_logged_in', None)
    return redirect(url_for('index'))

@app.route('/admin/subscribers_secure')
def admin_subscribers_secure():
    """Защищенная страница подписчиков"""
    if not session.get('admin_logged_in'):
        return redirect(url_for('admin_login_page'))
    
    try:
        subscribers = Subscriber.query.order_by(Subscriber.created_at.desc()).all()
        email_logs = EmailLog.query.order_by(EmailLog.sent_at.desc()).limit(10).all()
        
        stats = {
            'total': Subscriber.query.count(),
            'active': Subscriber.query.filter_by(is_active=True).count(),
            'inactive': Subscriber.query.filter_by(is_active=False).count(),
            'emails_sent': EmailLog.query.filter_by(status='sent').count(),
            'emails_failed': EmailLog.query.filter_by(status='failed').count()
        }
        
        # Создаем строки подписчиков
        subscribers_rows = ""
        for sub in subscribers:
            try:
                status = "✅ Активен" if sub.is_active else "❌ Неактивен"
                refugee = "✅ Да" if sub.is_refugee else "❌ Нет"
                created = sub.created_at.strftime('%Y-%m-%d %H:%M')
                
                # Получаем профессии и страны БЕЗОПАСНО
                try:
                    jobs_list = sub.get_selected_jobs()
                    jobs = ', '.join(jobs_list[:3]) if jobs_list else 'Не указано'
                    if len(jobs_list) > 3:
                        jobs += f' (+{len(jobs_list)-3})'
                except Exception as e:
                    jobs = 'Ошибка загрузки'
                    print(f"❌ Ошибка получения профессий для {sub.email}: {e}")
                
                try:
                    countries_list = sub.get_countries()
                    countries = ', '.join(countries_list) if countries_list else 'Не указано'
                except Exception as e:
                    countries = 'Ошибка загрузки'
                    print(f"❌ Ошибка получения стран для {sub.email}: {e}")
                
                city = sub.city or 'Не указан'
                
                subscribers_rows += f"""
                    <tr>
                        <td>{sub.email}</td>
                        <td>{status}</td>
                        <td>{refugee}</td>
                        <td class="job-list">{jobs}</td>
                        <td>{countries}</td>
                        <td>{city}</td>
                        <td>{created}</td>
                    </tr>"""
                    
            except Exception as e:
                print(f"❌ Ошибка обработки подписчика {sub.id}: {e}")
                subscribers_rows += f"""
                    <tr>
                        <td>{sub.email}</td>
                        <td>❌ Ошибка</td>
                        <td>-</td>
                        <td>-</td>
                        <td>-</td>
                        <td>-</td>
                        <td>-</td>
                    </tr>"""
        
        # Создаем строки email логов БЕЗОПАСНО
        email_logs_rows = ""
        for log in email_logs:
            try:
                status_icon = "✅" if log.status == 'sent' else "❌"
                sent_time = log.sent_at.strftime('%Y-%m-%d %H:%M')
                
                # ИСПРАВЛЕНИЕ: Безопасное получение email
                if log.subscriber:
                    email = log.subscriber.email
                else:
                    # Если subscriber удален, показываем ID или email из лога
                    email = f"Удаленный подписчик (ID: {log.subscriber_id})"
                
                email_logs_rows += f"""
                    <tr>
                        <td>{email}</td>
                        <td>{status_icon} {log.status}</td>
                        <td>{sent_time}</td>
                    </tr>"""
                    
            except Exception as e:
                print(f"❌ Ошибка обработки лога {log.id}: {e}")
                email_logs_rows += f"""
                    <tr>
                        <td>Ошибка загрузки</td>
                        <td>❌ Ошибка</td>
                        <td>-</td>
                    </tr>"""
                
        # Теперь создаем полный HTML
        html = f"""
        <!DOCTYPE html>
        <html lang="{{ request.cookies.get('lang','ru') }}"
        <head>
            <title>Подписчики - Админка</title>
            <meta charset="utf-8">
            <script defer src="{{ url_for('static', filename='js/localization.js') }}"></script>
            <style>
                body {{ font-family: Arial, sans-serif; margin: 20px; background: #f8f9fa; }}
                .container {{ max-width: 1200px; margin: 0 auto; }}
                table {{ border-collapse: collapse; width: 100%; margin: 20px 0; background: white; }}
                th, td {{ border: 1px solid #ddd; padding: 12px; text-align: left; }}
                th {{ background-color: #007bff; color: white; }}
                .stats {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 20px; margin: 20px 0; }}
                .stat-card {{ background: white; padding: 20px; border-radius: 8px; text-align: center; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }}
                .stat-number {{ font-size: 2em; font-weight: bold; color: #007bff; }}
                .nav {{ display: flex; gap: 20px; margin: 20px 0; }}
                .nav a {{ background: #007bff; color: white; padding: 10px 20px; text-decoration: none; border-radius: 4px; }}
                .job-list {{ font-size: 0.9em; color: #666; }}
                .error {{ color: #dc3545; font-weight: bold; }}
            </style>
        </head>
        <body>
            <div class="container">
                <h1>📧 Подписчики GlobalJobHunter</h1>
                
                <div class="nav">
                    <a href="/admin/dashboard">🏠 Главная админки</a>
                    <a href="/admin/stats_secure">📊 Статистика</a>
                    <a href="/admin/cache">🧹 Кэш</a>
                    <a href="/admin/logout">🚪 Выйти</a>
                </div>
                
                <div class="stats">
                    <div class="stat-card">
                        <div class="stat-number">{stats['total']}</div>
                        <p>Всего подписчиков</p>
                    </div>
                    <div class="stat-card">
                        <div class="stat-number">{stats['active']}</div>
                        <p>Активных</p>
                    </div>
                    <div class="stat-card">
                        <div class="stat-number">{stats['inactive']}</div>
                        <p>Неактивных</p>
                    </div>
                    <div class="stat-card">
                        <div class="stat-number">{stats['emails_sent']}</div>
                        <p>Email отправлено</p>
                    </div>
                    <div class="stat-card">
                        <div class="stat-number">{stats['emails_failed']}</div>
                        <p>Email ошибок</p>
                    </div>
                </div>
                
                <h2>📋 Подписчики</h2>
                <table>
                    <tr>
                        <th>Email</th>
                        <th>Статус</th>
                        <th>Беженец</th>
                        <th>Профессии</th>
                        <th>Страны</th>
                        <th>Город</th>
                        <th>Дата регистрации</th>
                    </tr>
                    {subscribers_rows}
                </table>
                
                <h2>📨 Последние email логи</h2>
                <table>
                    <tr>
                        <th>Email</th>
                        <th>Статус</th>
                        <th>Дата</th>
                    </tr>
                    {email_logs_rows}
                </table>
            </div>
        </body>
        </html>"""
        
        return html
        
    except Exception as e:
        print(f"❌ КРИТИЧЕСКАЯ ОШИБКА в admin_subscribers_secure: {e}")
        import traceback
        traceback.print_exc()
        return f"""
        <html lang="{{ request.cookies.get('lang','ru') }}"
        <body style="font-family: Arial; padding: 40px;">
            <h1 class="error">❌ Ошибка загрузки админки</h1>
            <p>Ошибка: {str(e)}</p>
            <a href="/admin/dashboard">🏠 Вернуться в админку</a>
        </body>
        </html>
        """, 500
    
def _pretty_json(value):
    """Возвращает человекочитаемую строку из JSON/списка/словаря."""
    try:
        if value is None or value == "":
            return ""
        # если передана строка с JSON — распарсим
        if isinstance(value, str):
            s = value.strip()
            if (s.startswith('[') and s.endswith(']')) or (s.startswith('{') and s.endswith('}')):
                value = json.loads(s)
        if isinstance(value, (list, tuple, set)):
            return ", ".join(map(str, value))
        if isinstance(value, dict):
            return ", ".join(f"{k}: {v}" for k, v in value.items())
        return str(value)
    except Exception:
        return str(value)


@app.route('/admin/stats_secure')
def admin_stats_secure():
    # доступ
    if not session.get('admin_logged_in'):
        return redirect(url_for('admin_login_page'))

    # метрики кеша/аггрегатора
    stats = aggregator.get_cache_stats() if aggregator else {
        'cache_hits': 0, 'api_requests': 0, 'total_jobs_found': 0
    }

    # путь к статике без Jinja в HTML-строке
    script_src = url_for('static', filename='js/localization.js')

    # последние события (100) и счётчик по партнёрам для пирога
    try:
        from analytics import recent_events, SearchClick, PartnerClick
        from database import db
        sc, pc = recent_events(limit=100)
        partner_clicks_count_last = len(pc)

        # Итоги по БД (всё время)
        total_search_clicks = db.session.query(func.count(SearchClick.id)).scalar() or 0
        total_partner_clicks = db.session.query(func.count(PartnerClick.id)).scalar() or 0

        # Сейчас все исходящие клики идут на сайты-партнёры (логируются в PartnerClick),
        # поэтому итог по исходящим = итог по партнёрам
        total_out_clicks = total_partner_clicks

        # распределение по партнёрам
        from collections import Counter
        partner_counter = Counter((p.partner or p.target_domain or 'unknown').strip() for p in pc)
        import json as _json
        labels_json = _json.dumps(list(partner_counter.keys()), ensure_ascii=False)
        values_json = _json.dumps([partner_counter[k] for k in partner_counter], ensure_ascii=False)

    except Exception as e:
        app.logger.exception("analytics.recent_events failed: %s", e)
        sc, pc = [], []
        partner_clicks_count_last = 0
        total_search_clicks = 0
        total_partner_clicks = 0
        total_out_clicks = 0
        labels_json = "[]"
        values_json = "[]"

    h = html_escape  # короткий алиас

    # === таблица «Найти работу» с разворотом ===
    def _details_city_query(c):
        v = getattr(c, "city_query", None)
        return f'<div><strong>City query:</strong> {h(v)}</div>' if v else ''

    def _details_ua(obj):
        ua = getattr(obj, "user_agent", None)
        return f'<div><strong>User-Agent:</strong> <span class="mono small-ua">{h(ua)}</span></div>' if ua else ''

    search_rows_parts = []
    for i, c in enumerate(sc):
        row_id = f"details-s-{i}"
        countries_txt = pretty_json(c.countries)
        jobs_txt = pretty_json(c.jobs)
        search_rows_parts.append(f"""
<tr>
  <td class="mono">
    <button class="toggle btn btn-link p-0" data-target="{row_id}" aria-expanded="false" title="Показать подробности">
      {c.created_at:%Y-%m-%d}<br>{c.created_at:%H:%M:%S}
    </button>
  </td>
  <td class="mono">{h(c.ip)}</td>
  <td>{h(c.country or '')}</td>
  <td>{h(c.city or '')}</td>
  <td class="mono">{h(c.lang or '')}</td>
  <td><span class="badge {'bg-success' if getattr(c,'is_refugee',False) else 'bg-secondary'}">{'Да' if getattr(c,'is_refugee',False) else 'Нет'}</span></td>
  <td><div class="line-clamp-2" title="{h(countries_txt)}">{h(countries_txt)}</div></td>
  <td><div class="line-clamp-2" title="{h(jobs_txt)}">{h(jobs_txt)}</div></td>
</tr>
<tr id="{row_id}" class="details-row">
  <td colspan="8">
    <div class="details">
      <div><strong>IP:</strong> {h(c.ip)} | <strong>Язык:</strong> {h(c.lang or '')}</div>
      <div><strong>Страна:</strong> {h(c.country or '')} | <strong>Город:</strong> {h(c.city or '')}</div>
      <div><strong>Страны поиска:</strong> {h(countries_txt)}</div>
      <div><strong>Профессии:</strong> {h(jobs_txt)}</div>
      {_details_city_query(c)}{_details_ua(c)}
    </div>
  </td>
</tr>
""")
    search_rows = "".join(search_rows_parts) or '<tr><td colspan="8" class="text-center text-muted">нет данных</td></tr>'

    # === таблица «Переходы к партнёрам» с разворотом ===
    partner_rows_parts = []
    for i, p in enumerate(pc):
        row_id = f"details-p-{i}"
        link = (p.target_url or '').strip()
        partner_name = (p.partner or p.target_domain or '').strip()
        title = p.job_title or ''
        link_html = f'<div><strong>Глубокая ссылка:</strong> <a href="{h(link)}" target="_blank" rel="noopener">{h(link)}</a></div>' if link else ''
        partner_rows_parts.append(f"""
<tr>
  <td class="mono">
    <button class="toggle btn btn-link p-0" data-target="{row_id}" aria-expanded="false" title="Показать подробности">
      {p.created_at:%Y-%m-%d}<br>{p.created_at:%H:%M:%S}
    </button>
  </td>
  <td class="mono">{h(p.ip)}</td>
  <td>{h(p.country or '')}</td>
  <td>{h(p.city or '')}</td>
  <td class="mono">{h(p.lang or '')}</td>
  <td>{h(partner_name)}</td>
  <td class="mono">{h(p.job_id or '')}</td>
  <td><div class="line-clamp-2" title="{h(title)}">{h(title)}</div></td>
  <td>{(f'<a class="btn btn-sm btn-outline-primary" href="{h(link)}" target="_blank" rel="noopener">Открыть</a>') if link else ''}</td>
</tr>
<tr id="{row_id}" class="details-row">
  <td colspan="9">
    <div class="details">
      <div><strong>Партнёр:</strong> {h(partner_name)}</div>
      <div><strong>Job ID:</strong> <span class="mono">{h(p.job_id or '')}</span></div>
      {link_html}{_details_ua(p)}
    </div>
  </td>
</tr>
""")
    partner_rows = "".join(partner_rows_parts) or '<tr><td colspan="9" class="text-center text-muted">нет данных</td></tr>'

    # карточки-метрики
    cache_hits = stats.get('cache_hits', 0)
    api_requests = stats.get('api_requests', 0)
    total_jobs_found = stats.get('total_jobs_found', 0)

    return f"""
<!doctype html>
<html lang="ru">
<head>
  <meta charset="utf-8">
  <title>Статистика — Админка</title>
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.2/dist/css/bootstrap.min.css" rel="stylesheet">
  <script defer src="{script_src}"></script>
  <script src="https://cdn.jsdelivr.net/npm/chart.js@4"></script>
  <style>
    body {{ background:#f6f7fb; }}
    .stat-card, .chart-card {{ background:#fff; border:1px solid #eaeefc; border-radius:12px; }}
    .card-num {{ font-size:32px; font-weight:700; }}
    .mono {{ font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono", "Courier New", monospace; }}
    .table thead th {{ position: sticky; top: 0; background: #fff; z-index: 2; }}
    .table td, .table th {{ vertical-align: middle; }}
    .table-bordered > :not(caption) > * > * {{ border-color: #e5e9ff; }}
    .table-striped>tbody>tr:nth-of-type(odd) > * {{ background: #fafbff; }}
    .line-clamp-2 {{ display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden; }}
    .small-ua {{ font-size: 12px; word-break: break-all; }}
    .details-row {{ display: none; background: #fff; }}
    .details-row.open {{ display: table-row; }}
    .details {{ padding: 12px 8px; border: 1px dashed #d9e1ff; border-radius: 8px; background: #f9fbff; }}
    .btn-link.toggle {{ text-decoration: none; }}
    .btn-link.toggle::after {{ content: " ▾"; font-size: 12px; transition: transform .2s ease; display: inline-block; transform: rotate(-90deg); }}
    .btn-link.toggle[aria-expanded="true"]::after {{ transform: rotate(0deg); }}
  </style>
</head>
<body>
<div class="container py-4">

  <!-- Навигация -->
  <div class="d-flex gap-2 flex-wrap mb-3">
    <a class="btn btn-outline-primary" href="/admin/subscribers?key={h(os.getenv('ADMIN_KEY') or '')}">👥 Подписчики</a>
    <a class="btn btn-primary" href="/admin/stats_secure">📈 Статистика</a>
    <a class="btn btn-outline-success" href="/health">💚 Здоровье</a>
    <a class="btn btn-outline-warning" href="/admin/cache">🧹 Кэш</a>
    <a class="btn btn-outline-secondary" href="/">🏠 Выйти</a>
  </div>

  <!-- Карточки (системные) -->
  <div class="row g-3 mb-3">
    <div class="col-6 col-md-3"><div class="p-3 text-center stat-card"><div class="card-num text-primary">{cache_hits}</div><div>Cache Hits</div></div></div>
    <div class="col-6 col-md-3"><div class="p-3 text-center stat-card"><div class="card-num text-primary">{api_requests}</div><div>API Requests</div></div></div>
    <div class="col-6 col-md-3"><div class="p-3 text-center stat-card"><div class="card-num text-primary">{total_jobs_found}</div><div>Jobs Found</div></div></div>
    <div class="col-6 col-md-3"><div class="p-3 text-center stat-card"><div class="card-num text-primary">{partner_clicks_count_last}</div><div>Переходы к партнёрам (последние 100)</div></div></div>
  </div>

  <!-- Карточки (ИТОГО) -->
  <div class="row g-3 mb-4">
    <div class="col-12 col-md-4"><div class="p-3 text-center stat-card"><div class="card-num text-primary">{total_search_clicks}</div><div>Итого «Найти работу»</div></div></div>
    <div class="col-12 col-md-4"><div class="p-3 text-center stat-card"><div class="card-num text-primary">{total_partner_clicks}</div><div>Итого переходов к партнёрам</div></div></div>
    <div class="col-12 col-md-4"><div class="p-3 text-center stat-card"><div class="card-num text-primary">{total_out_clicks}</div><div>Итого исходящих кликов</div></div></div>
  </div>

  <!-- Круговая диаграмма -->
  <div class="row mb-4">
    <div class="col-12 col-lg-6">
      <div class="p-3 chart-card">
        <div class="d-flex justify-content-between align-items-center mb-2">
          <h5 class="mb-0">Распределение переходов по партнёрам</h5>
          <span class="text-muted">последние {partner_clicks_count_last}</span>
        </div>
        <canvas id="partnersPie" height="220"></canvas>
      </div>
    </div>
  </div>

  <h4 class="mt-2 mb-2">🔎 Нажатия «Найти работу» (последние 100)</h4>
  <div class="table-responsive">
    <table class="table table-sm table-striped table-bordered align-middle">
      <thead>
        <tr>
          <th style="min-width:120px">Время</th>
          <th style="min-width:120px">IP</th>
          <th style="min-width:80px">Страна</th>
          <th style="min-width:120px">Город</th>
          <th style="min-width:80px">Язык</th>
          <th style="min-width:90px">Беженец</th>
          <th style="min-width:220px">Страны поиска</th>
          <th style="min-width:320px">Профессии</th>
        </tr>
      </thead>
      <tbody>{search_rows}</tbody>
    </table>
  </div>

  <h4 class="mt-4 mb-2">↗ Переходы на сайты-партнёры (последние 100)</h4>
  <div class="table-responsive">
    <table class="table table-sm table-striped table-bordered align-middle">
      <thead>
        <tr>
          <th style="min-width:120px">Время</th>
          <th style="min-width:120px">IP</th>
          <th style="min-width:80px">Страна</th>
          <th style="min-width:120px">Город</th>
          <th style="min-width:80px">Язык</th>
          <th style="min-width:120px">Партнёр</th>
          <th style="min-width:160px">Job ID</th>
          <th style="min-width:300px">Заголовок</th>
          <th style="min-width:120px">Ссылка</th>
        </tr>
      </thead>
      <tbody>{partner_rows}</tbody>
    </table>
  </div>

</div>

<script>
  // Тогглер деталей
  document.addEventListener('click', function(e) {{
    const btn = e.target.closest('.toggle');
    if (!btn) return;
    const id = btn.getAttribute('data-target');
    const row = document.getElementById(id);
    if (!row) return;
    const nowOpen = !row.classList.contains('open');
    row.classList.toggle('open', nowOpen);
    btn.setAttribute('aria-expanded', nowOpen ? 'true' : 'false');
  }});

  // Круговая диаграмма (без JS-шаблонных строк — чтобы не конфликтовать с Python f-строкой)
  (function() {{
    const labels = {labels_json};
    const values = {values_json};
    const el = document.getElementById('partnersPie');
    if (!el || !labels.length) return;
    const ctx = el.getContext('2d');
    new Chart(ctx, {{
      type: 'doughnut',
      data: {{ labels: labels, datasets: [{{ data: values }}] }},
      options: {{
        responsive: true,
        plugins: {{
          legend: {{ position: 'bottom' }},
          tooltip: {{
            callbacks: {{
              label: function(ct) {{
                const total = values.reduce((a,b)=>a+b,0) || 1;
                const v = ct.parsed;
                const pct = Math.round((v*100)/total);
                return ' ' + ct.label + ': ' + v + ' (' + pct + '%)';
              }}
            }}
          }}
        }}
      }}
    }});
  }})();
</script>
</body>
</html>
"""


    
@app.route('/send-notifications')
def send_notifications():
    """Отправка уведомлений подписчикам"""
    try:
        from email_service import send_job_notifications
        
        # Диагностика
        subscribers = Subscriber.query.filter_by(is_active=True).all()
        debug_info = []
        
        debug_info.append(f"📊 Всего активных подписчиков: {len(subscribers)}")
        
        for sub in subscribers:
            jobs = sub.get_selected_jobs()
            countries = sub.get_countries()
            debug_info.append(f"👤 {sub.email}: профессий={len(jobs)}, стран={len(countries)}")
            debug_info.append(f"   Профессии: {jobs[:3]}")
            debug_info.append(f"   Страны: {countries}")
        
        # Попытка отправки
        # Передаем основной и дополнительные агрегаторы
        sent_count = send_job_notifications(app, aggregator, additional_aggregators)
        
        debug_info.append(f"📧 Отправлено: {sent_count}")
        
        return "<br>".join(debug_info)
        
    except Exception as e:
        return f"❌ Ошибка: {str(e)}"
    
@app.route('/support')
def support():
    return render_template('support.html')  # или 'support_page.html' 

def email_scheduler(app, main_aggregator, additional_aggregators):
    """Планировщик email рассылки, который знает обо всех агрегаторах."""
    print("📅 Планировщик email рассылки запущен со всеми агрегаторами")

    # Передаем все агрегаторы в функцию, которую будет вызывать schedule
    job_func = lambda: run_scheduled_notifications(app, main_aggregator, additional_aggregators)

    # Запускаем проверку каждый час
    schedule.every().hour.do(job_func)
    
    # Для тестирования - запуск каждые 5 минут. ЗАКОММЕНТИРОВАТЬ В ПРОДАКШЕНЕ!
    # schedule.every(5).minutes.do(job_func)

    while True:
        schedule.run_pending()
        time.sleep(60)

def send_daily_notifications():
    """Ежедневная рассылка"""
    try:
        print("📧 Запуск ежедневной рассылки...")
        with app.app_context():
            subscribers = Subscriber.query.filter_by(is_active=True, frequency='daily').all()
            print(f"👥 Найдено {len(subscribers)} подписчиков с ежедневной частотой")
            
            if not subscribers:
                print("ℹ️ Нет подписчиков для ежедневной рассылки")
                return
            
            sent_count = 0
            for subscriber in subscribers:
                try:
                    # Проверяем, нужно ли отправлять (не отправляли сегодня)
                    if subscriber.last_sent:
                        last_sent_date = subscriber.last_sent.date()
                        today = datetime.now().date()
                        if last_sent_date >= today:
                            print(f"⏭️ {subscriber.email}: уже отправлено сегодня")
                            continue
                    
                    # Отправляем уведомления
                    result = send_job_notifications_for_subscriber(app, aggregator, subscriber)
                    if result:
                        sent_count += 1
                        
                except Exception as e:
                    print(f"❌ Ошибка отправки для {subscriber.email}: {e}")
            
            print(f"✅ Ежедневная рассылка завершена: {sent_count}/{len(subscribers)}")
            
    except Exception as e:
        print(f"❌ Ошибка ежедневной рассылки: {e}")

def send_weekly_notifications():
    """Еженедельная рассылка"""
    try:
        print("📧 Запуск еженедельной рассылки...")
        with app.app_context():
            subscribers = Subscriber.query.filter_by(is_active=True, frequency='weekly').all()
            print(f"👥 Найдено {len(subscribers)} подписчиков с еженедельной частотой")
            
            if not subscribers:
                print("ℹ️ Нет подписчиков для еженедельной рассылки")
                return
            
            sent_count = 0
            for subscriber in subscribers:
                try:
                    # Проверяем, нужно ли отправлять (не отправляли на этой неделе)
                    if subscriber.last_sent:
                        days_since_last = (datetime.now() - subscriber.last_sent).days
                        if days_since_last < 7:
                            print(f"⏭️ {subscriber.email}: отправлено {days_since_last} дней назад")
                            continue
                    
                    # Отправляем уведомления
                    result = send_job_notifications_for_subscriber(app, aggregator, subscriber)
                    if result:
                        sent_count += 1
                        
                except Exception as e:
                    print(f"❌ Ошибка отправки для {subscriber.email}: {e}")
            
            print(f"✅ Еженедельная рассылка завершена: {sent_count}/{len(subscribers)}")
            
    except Exception as e:
        print(f"❌ Ошибка еженедельной рассылки: {e}")

def send_monthly_notifications():
    """Ежемесячная рассылка"""
    try:
        print("📧 Запуск ежемесячной рассылки...")
        with app.app_context():
            subscribers = Subscriber.query.filter_by(is_active=True, frequency='monthly').all()
            print(f"👥 Найдено {len(subscribers)} подписчиков с ежемесячной частотой")
            
            if not subscribers:
                print("ℹ️ Нет подписчиков для ежемесячной рассылки")
                return
            
            sent_count = 0
            for subscriber in subscribers:
                try:
                    # Проверяем, нужно ли отправлять (не отправляли в этом месяце)
                    if subscriber.last_sent:
                        days_since_last = (datetime.now() - subscriber.last_sent).days
                        if days_since_last < 30:
                            print(f"⏭️ {subscriber.email}: отправлено {days_since_last} дней назад")
                            continue
                    
                    # Отправляем уведомления
                    result = send_job_notifications_for_subscriber(app, aggregator, subscriber)
                    if result:
                        sent_count += 1
                        
                except Exception as e:
                    print(f"❌ Ошибка отправки для {subscriber.email}: {e}")
            
            print(f"✅ Ежемесячная рассылка завершена: {sent_count}/{len(subscribers)}")
            
    except Exception as e:
        print(f"❌ Ошибка ежемесячной рассылки: {e}")

def send_test_notifications():
    """Тестовая рассылка (для отладки)"""
    print("🧪 Тестовая рассылка...")
    with app.app_context():
        # Отправляем только первому активному подписчику
        subscriber = Subscriber.query.filter_by(is_active=True).first()
        if subscriber:
            print(f"📧 Тестовая отправка на {subscriber.email}")
            send_job_notifications_for_subscriber(app, aggregator, subscriber)
        else:
            print("ℹ️ Нет активных подписчиков для тестирования")

def send_job_notifications_for_subscriber(app, aggregator, subscriber):
    """Отправка уведомлений конкретному подписчику"""
    try:
        preferences = {
            'is_refugee': subscriber.is_refugee,
            'selected_jobs': subscriber.get_selected_jobs(),
            'countries': subscriber.get_countries(),
            'city': subscriber.city
        }
        
        if not preferences['selected_jobs'] or not preferences['countries']:
            print(f"⚠️ У {subscriber.email} нет профессий или стран")
            return False
        
        # Ищем вакансии
        jobs = aggregator.search_specific_jobs(preferences)
        
        if len(jobs) > 0:
            print(f"🎯 Найдено {len(jobs)} вакансий для {subscriber.email}")
            
            # Отправляем email
            from email_service import send_job_email
            success = send_job_email(app, subscriber, jobs[:20], preferences)  # Максимум 20 вакансий
            
            if success:
                # Обновляем время последней отправки
                subscriber.last_sent = datetime.now()
                
                # Логируем отправку
                log = EmailLog(
                    subscriber_id=subscriber.id,
                    subject=f"Найдено {len(jobs)} новых вакансий",
                    jobs_count=len(jobs),
                    status='sent',
                    sent_at=datetime.now()
                )
                db.session.add(log)
                db.session.commit()
                
                print(f"✅ Email отправлен на {subscriber.email}")
                return True
            else:
                print(f"❌ Не удалось отправить email на {subscriber.email}")
                return False
        else:
            print(f"ℹ️ Нет новых вакансий для {subscriber.email}")
            return False
            
    except Exception as e:
        print(f"❌ Ошибка отправки для {subscriber.email}: {e}")
        return False   
    
# Автоматическая инициализация БД ТОЛЬКО если таблиц нет
if os.getenv('RAILWAY_ENVIRONMENT') or os.getenv('DATABASE_URL'):
    with app.app_context():
        try:
            from sqlalchemy import inspect, text
            
            # Логируем подключение к БД для отладки
            print(f"🛠 Подключено к БД: {db.engine.url}")
            
            # Проверяем существование таблиц БЕЗ их создания
            inspector = inspect(db.engine)
            existing_tables = inspector.get_table_names()
            
            # Улучшенная проверка на пустые таблицы
            if not existing_tables or len(existing_tables) == 0:
                print("🔄 Таблицы не найдены, создаем новые...")
                db.create_all()
                print("✅ Таблицы созданы")
            else:
                print(f"✅ БД уже существует с таблицами: {existing_tables}")
                
                # ВАЖНО: Только проверяем данные, НЕ пересоздаем таблицы
                try:
                    with db.engine.connect() as conn:
                        if 'subscriber' in existing_tables:
                            result = conn.execute(text("SELECT COUNT(*) as count FROM subscriber"))
                            count = result.fetchone()[0]
                            print(f"👥 Найдено подписчиков в БД: {count}")
                        
                        if 'email_log' in existing_tables:
                            result = conn.execute(text("SELECT COUNT(*) as count FROM email_log"))
                            count = result.fetchone()[0]
                            print(f"📧 Найдено email логов в БД: {count}")
                except Exception as data_error:
                    print(f"⚠️ Ошибка проверки данных: {data_error}")
                    
        except Exception as e:
            print(f"⚠️ Ошибка инициализации БД: {e}")
            # НЕ создаем таблицы при ошибке соединения!

@app.route('/admin/download_backup')
def download_backup():
    """Скачать бекап базы данных в JSON"""
    if not session.get('admin_logged_in'):
        return redirect(url_for('admin_login_page'))
    
    try:
        # Собираем всех подписчиков
        subscribers = Subscriber.query.all()
        subscribers_data = []
        
        for sub in subscribers:
            subscribers_data.append({
                'email': sub.email,
                'is_active': sub.is_active,
                'created_at': sub.created_at.isoformat() if sub.created_at else None,
                'is_refugee': sub.is_refugee,
                'selected_jobs': sub.get_selected_jobs(),
                'countries': sub.get_countries(),
                'city': sub.city,
                'frequency': sub.frequency,
                'last_sent': sub.last_sent.isoformat() if sub.last_sent else None
            })
        
        # Собираем email логи
        email_logs = EmailLog.query.order_by(EmailLog.sent_at.desc()).limit(1000).all()
        logs_data = []
        
        for log in email_logs:
            logs_data.append({
                'email': log.email,
                'subject': log.subject,
                'jobs_count': log.jobs_count,
                'status': log.status,
                'sent_at': log.sent_at.isoformat() if log.sent_at else None,
                'error_message': log.error_message
            })
        
        # Формируем JSON
        backup_data = {
            'backup_date': datetime.now().isoformat(),
            'subscribers': subscribers_data,
            'email_logs': logs_data,
            'stats': {
                'total_subscribers': len(subscribers_data),
                'active_subscribers': len([s for s in subscribers_data if s['is_active']]),
                'total_logs': len(logs_data)
            }
        }
        
        # Возвращаем файл для скачивания
        filename = f"globaljobhunter_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        
        from flask import Response
        return Response(
            json.dumps(backup_data, indent=2, ensure_ascii=False),
            mimetype='application/json',
            headers={'Content-Disposition': f'attachment; filename={filename}'}
        )
        
    except Exception as e:
        return f"❌ Ошибка создания бекапа: {str(e)}", 500

@app.route('/admin/upload_backup', methods=['GET', 'POST'])
def upload_backup():
    """Загрузить бекап базы данных"""
    if not session.get('admin_logged_in'):
        return redirect(url_for('admin_login_page'))
    
    if request.method == 'GET':
        # Показываем форму загрузки
        return """
        <!DOCTYPE html>
        <html lang="{{ request.cookies.get('lang','ru') }}"
        <head>
            <title>Загрузка бекапа</title>
            <meta charset="utf-8">
            <script defer src="{{ url_for('static', filename='js/localization.js') }}"></script>
            <style>
                body { font-family: Arial; background: #f8f9fa; padding: 20px; }
                .container { max-width: 600px; margin: 0 auto; background: white; padding: 30px; border-radius: 10px; }
                .btn { background: #007bff; color: white; padding: 12px 25px; border: none; border-radius: 5px; cursor: pointer; text-decoration: none; display: inline-block; margin: 10px 5px; }
                .btn-danger { background: #dc3545; }
                .alert { padding: 15px; margin: 20px 0; border-radius: 5px; background: #fff3cd; border: 1px solid #ffeaa7; color: #856404; }
                input[type="file"] { width: 100%; padding: 10px; border: 1px solid #ddd; border-radius: 5px; margin: 10px 0; }
            </style>
        </head>
        <body>
            <div class="container">
                <h2>📁 Загрузка бекапа базы данных</h2>
                
                <div class="alert">
                    <strong>⚠️ ВНИМАНИЕ!</strong><br>
                    Загрузка заменит ВСЕ текущие данные в базе.<br>
                    Убедитесь, что загружаете правильный файл!
                </div>
                
                <form method="post" enctype="multipart/form-data">
                    <label><strong>Выберите JSON файл бекапа:</strong></label>
                    <input type="file" name="backup_file" accept=".json" required>
                    
                    <div style="margin: 20px 0;">
                        <label>
                            <input type="checkbox" name="confirm_restore" required>
                            Я понимаю, что все данные будут заменены
                        </label>
                    </div>
                    
                    <button type="submit" class="btn btn-danger">🔄 Загрузить бекап</button>
                    <a href="/admin/dashboard" class="btn">❌ Отмена</a>
                </form>
            </div>
        </body>
        </html>
        """
    
    else:
        # Обрабатываем загрузку файла
        try:
            if 'backup_file' not in request.files:
                return "❌ Файл не выбран", 400
            
            file = request.files['backup_file']
            if file.filename == '' or not file.filename.endswith('.json'):
                return "❌ Выберите JSON файл", 400
            
            # Читаем и парсим JSON
            backup_data = json.loads(file.read().decode('utf-8'))
            
            # Очищаем существующие данные
            db.session.query(EmailLog).delete()
            db.session.query(Subscriber).delete()
            
            # Восстанавливаем подписчиков
            restored_subscribers = 0
            for sub_data in backup_data.get('subscribers', []):
                try:
                    subscriber = Subscriber(
                        email=sub_data['email'],
                        is_active=sub_data.get('is_active', True),
                        is_refugee=sub_data.get('is_refugee', True),
                        city=sub_data.get('city'),
                        frequency=sub_data.get('frequency', 'weekly')
                    )
                    
                    if sub_data.get('created_at'):
                        subscriber.created_at = datetime.fromisoformat(sub_data['created_at'])
                    
                    if sub_data.get('last_sent'):
                        subscriber.last_sent = datetime.fromisoformat(sub_data['last_sent'])
                    
                    if sub_data.get('selected_jobs'):
                        subscriber.set_selected_jobs(sub_data['selected_jobs'])
                    
                    if sub_data.get('countries'):
                        subscriber.set_countries(sub_data['countries'])
                    
                    db.session.add(subscriber)
                    restored_subscribers += 1
                    
                except Exception as e:
                    print(f"⚠️ Ошибка восстановления подписчика: {e}")
            
            # Восстанавливаем email логи
            restored_logs = 0
            for log_data in backup_data.get('email_logs', []):
                try:
                    email_log = EmailLog(
                        email=log_data.get('email'),
                        subject=log_data.get('subject'),
                        jobs_count=log_data.get('jobs_count', 0),
                        status=log_data.get('status', 'unknown'),
                        error_message=log_data.get('error_message')
                    )
                    
                    if log_data.get('sent_at'):
                        email_log.sent_at = datetime.fromisoformat(log_data['sent_at'])
                    
                    db.session.add(email_log)
                    restored_logs += 1
                    
                except Exception as e:
                    print(f"⚠️ Ошибка восстановления лога: {e}")
            
            # Сохраняем изменения
            db.session.commit()
            
            return f"""
            <html lang="{{ request.cookies.get('lang','ru') }}"
            <head><title>Восстановление завершено</title><meta charset="utf-8"></head>
            <body style="font-family: Arial; padding: 40px; text-align: center; background: #f8f9fa;">
                <div style="background: white; padding: 40px; border-radius: 10px; max-width: 500px; margin: 0 auto;">
                    <h1 style="color: #28a745;">✅ Восстановление завершено!</h1>
                    <p>Подписчиков восстановлено: <strong>{restored_subscribers}</strong></p>
                    <p>Email логов восстановлено: <strong>{restored_logs}</strong></p>
                    <a href="/admin/dashboard" style="background: #007bff; color: white; padding: 15px 30px; text-decoration: none; border-radius: 5px;">Вернуться в админку</a>
                </div>
            </body>
            </html>
            """
            
        except Exception as e:
            return f"❌ Ошибка восстановления: {str(e)}", 500            

if __name__ == '__main__':
    # Запускаем планировщик в отдельном потоке
    print("🚀 Запуск планировщика email рассылки...")
    # Передаем в поток планировщика все, что ему нужно для работы
    scheduler_thread = Thread(target=email_scheduler, args=(app, aggregator, additional_aggregators), daemon=True)
    scheduler_thread.start()
    
    # Запускаем Flask
    port = int(os.environ.get('PORT', 5000))
    debug = os.environ.get('FLASK_ENV') == 'development'
    
    print("🌍 Запуск Flask сервера...")
    app.run(host='0.0.0.0', port=port, debug=debug)


