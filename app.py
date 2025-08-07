#!/usr/bin/env python3
"""
GlobalJobHunter Web Interface v3.3 - С КЕШИРОВАНИЕМ
Интеграция с умным кешированием и мониторингом
"""

import os
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
from flask import Flask, render_template, request, jsonify, session, redirect, url_for, flash, render_template_string
from email_service import mail, send_welcome_email, send_preferences_update_email, send_job_notifications

# Добавить эти импорты ПОСЛЕ существующих
from flask_mail import Mail
from database import db, Subscriber, EmailLog  
from email_service import mail, send_welcome_email, send_preferences_update_email
from flask_migrate import Migrate

from threading import Thread
import schedule

# Импортируем существующий агрегатор
from adzuna_aggregator import GlobalJobAggregator, JobVacancy

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
            # 🔧 ИСПРАВЛЕНИЕ: всегда возвращаем defaultdict!
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
        return False, MAX_SEARCHES_PER_DAY - len(recent_searches)
    
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

app = Flask(__name__)
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

# Инициализация расширений
db.init_app(app)
mail.init_app(app)
migrate = Migrate(app, db)

# Инициализация основного агрегатора (БЕЗ ИЗМЕНЕНИЙ)
try:
    aggregator = GlobalJobAggregator(cache_duration_hours=12)  # Увеличили до 12 часов
    aggregator.search_cache = {}
    app.logger.info("✅ GlobalJobAggregator с кешированием инициализирован")
except Exception as e:
    app.logger.error(f"❌ Ошибка инициализации: {e}")
    aggregator = None

# ДОБАВЛЕНИЕ: инициализация дополнительных источников
additional_aggregators = {}
if ADDITIONAL_SOURCES_AVAILABLE:
    try:
        additional_aggregators['jobicy'] = JobicyAggregator()
        # additional_aggregators['usajobs'] = USAJobsAggregator()  # Нужен API ключ
        app.logger.info(f"✅ Дополнительные источники: {list(additional_aggregators.keys())}")
    except Exception as e:
        app.logger.warning(f"⚠️ Дополнительные источники недоступны: {e}")

# ВСЕ ОСТАЛЬНЫЕ МЕТОДЫ ОСТАЮТСЯ БЕЗ ИЗМЕНЕНИЙ
@app.route('/')
def index():
   """Главная страница с современным дизайном"""
   if not aggregator:
       return render_template('error.html', 
                            error="API ключи не настроены. Обратитесь к администратору.")
   
   job_categories = aggregator.specific_jobs
   total_jobs = sum(len(jobs) for jobs in job_categories.values())
   
   session.pop('results_id', None)
   session.pop('last_search_preferences', None)
   
   return render_template('index.html', 
                        job_categories=job_categories,
                        total_jobs=total_jobs,
                        countries=aggregator.countries)

@app.route('/search', methods=['POST'])
def search_jobs():
   """API для поиска с кешированием"""
   if not aggregator:
       return jsonify({'error': 'Сервис временно недоступен'}), 500
   
   # НОВОЕ: Проверка rate limiting
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
       
       preferences = {
           'is_refugee': form_data.get('is_refugee') == 'true',
           'selected_jobs': form_data.get('selected_jobs', []),
           'countries': form_data.get('countries', ['de']),
           'city': form_data.get('city', '').strip() or None
       }
       
       if not preferences['selected_jobs']:
           return jsonify({'error': 'Выберите хотя бы одну профессию'}), 400
       
       if isinstance(preferences['selected_jobs'], str):
           preferences['selected_jobs'] = [preferences['selected_jobs']]
       
       app.logger.info(f"🔍 Начинаем поиск: {preferences}")
       start_time = time.time()
       
       # ОСНОВНОЙ поиск через Adzuna (БЕЗ ИЗМЕНЕНИЙ)
       jobs = aggregator.search_specific_jobs(preferences)
       
       # ДОБАВЛЕНИЕ: поиск через дополнительные источники
       if additional_aggregators:
           for source_name, source_aggregator in additional_aggregators.items():
               try:
                   app.logger.info(f"🔄 Дополнительный поиск через {source_name}")
                   additional_jobs = source_aggregator.search_jobs(preferences)
                   jobs.extend(additional_jobs)
                   app.logger.info(f"✅ {source_name}: +{len(additional_jobs)} вакансий")
               except Exception as e:
                   app.logger.warning(f"⚠️ {source_name} ошибка: {e}")
                   continue
       
       search_time = time.time() - start_time
       
       # Логируем статистику кеширования (БЕЗ ИЗМЕНЕНИЙ)
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
           'sources_used': ['adzuna'] + list(additional_aggregators.keys()),  # ДОБАВЛЕНИЕ
           'remaining_searches': remaining,
           'redirect_url': url_for('results')
       })
       
   except Exception as e:
       app.logger.error(f"❌ Ошибка поиска: {e}", exc_info=True)
       return jsonify({'error': f'Внутренняя ошибка сервера: {str(e)}'}), 500

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
                'error': 'Сначала выберите профессии и страны, затем нажмите "Найти работу", а потом подписывайтесь'
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
            subscriber = existing
        else:
            print("➕ Создаем нового подписчика...")
            subscriber = Subscriber(
                email=email,
                is_refugee=preferences.get('is_refugee', True),
                city=preferences.get('city'),
                frequency='weekly'
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
            email_success = send_welcome_email(app, email)
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
                
                return jsonify({
                    'success': True, 
                    'message': 'Подписка оформлена! Проверьте email.'
                })
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
                
                return jsonify({
                    'success': True, 
                    'message': 'Подписка оформлена! (Email может быть отправлен с задержкой)'
                })
                
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
            
            return jsonify({
                'success': True, 
                'message': 'Подписка оформлена! (Email может быть отправлен с задержкой)'
            })
        
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
        <html>
        <head>
            <meta charset="utf-8">
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
        <html>
        <head>
            <meta charset="utf-8">
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
                <h1>Вы успешно отписались!</h1>
                <p>Подписка на email-уведомления для адреса</p>
                <div class="email-highlight">{{ email }}</div>
                <p>была деактивирована.</p>
                
                <div class="info-box">
                    <h4>📧 Что это означает:</h4>
                    <ul>
                        <li>Вы больше не будете получать уведомления о новых вакансиях</li>
                        <li>Ваши данные остаются в системе (на случай повторной подписки)</li>
                        <li>Вы можете в любое время подписаться снова через главную страницу</li>
                    </ul>
                </div>
                
                <div>
                    <a href="/" class="btn">🏠 Вернуться на главную</a>
                    <a href="mailto:tzvanguardia@gmail.com?subject=Вопрос по GlobalJobHunter" class="btn btn-secondary">📧 Связаться с нами</a>
                </div>
                
                <div style="margin-top: 30px; padding-top: 20px; border-top: 1px solid #dee2e6;">
                    <small style="color: #6c757d;">
                        <strong>Передумали?</strong> Вы всегда можете подписаться снова на 
                        <a href="/" style="color: #007bff;">главной странице</a>
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
        <html>
        <head>
            <meta charset="utf-8">
            <title>Уже отписан</title>
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
                <h1>Вы уже отписаны</h1>
                <p>Подписка для адреса</p>
                <div class="email-highlight">{{ email }}</div>
                <p>уже была деактивирована ранее.</p>
                <p style="color: #6c757d; margin-top: 25px;">
                    Хотите снова получать уведомления о вакансиях? 
                    Подпишитесь на главной странице!
                </p>
                <a href="/" class="btn">🏠 Вернуться на главную</a>
            </div>
        </body>
        </html>
        """, email=email)
    
    else:
        # Подписчик не найден
        return render_template_string("""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="utf-8">
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
                <a href="/" class="btn">🏠 Вернуться на главную!</a>
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
        <html>
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
    <html>
    <head>
        <title>Админка подписчиков</title>
        <meta charset="utf-8">
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
    <html>
    <head>
        <title>Статистика GlobalJobHunter</title>
        <meta charset="utf-8">
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

@app.route('/health')
def health_check():
    """Простая проверка здоровья системы БЕЗ админских ссылок"""
    try:
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
        
        return f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>Статус системы</title>
            <meta charset="utf-8">
            <style>
                body {{ font-family: Arial, sans-serif; margin: 20px; background: #f8f9fa; }}
                .container {{ max-width: 600px; margin: 0 auto; }}
                .status-card {{ background: white; padding: 20px; border-radius: 8px; margin: 20px 0; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }}
                .status-good {{ border-left: 5px solid #28a745; }}
                .status-item {{ display: flex; justify-content: space-between; margin: 10px 0; }}
                .status-ok {{ color: #28a745; font-size: 1.5em; }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="status-card status-good">
                    <h2 class="status-ok">🟢 Система работает нормально</h2>
                    <div class="status-item">
                        <span>Основной агрегатор:</span>
                        <span>{'✅ Работает' if aggregator else '❌ Недоступен'}</span>
                    </div>
                    <div class="status-item">
                        <span>Дополнительные источники:</span>
                        <span>{', '.join(additional_sources) if additional_sources else 'Нет'}</span>
                    </div>
                    <div class="status-item">
                        <span>API запросов:</span>
                        <span>{cache_stats.get('api_requests', 0)}</span>
                    </div>
                    <div class="status-item">
                        <span>Попаданий в кеш:</span>
                        <span>{cache_stats.get('cache_hits', 0)}</span>
                    </div>
                    <div class="status-item">
                        <span>Промахов кеша:</span>
                        <span>{cache_stats.get('cache_misses', 0)}</span>
                    </div>
                    <div class="status-item">
                        <span>Эффективность кеша:</span>
                        <span>{cache_stats.get('cache_hit_rate', '0.0%')}</span>
                    </div>
                    <div class="status-item">
                        <span>Всего найдено вакансий:</span>
                        <span>{cache_stats.get('total_jobs_found', 0)}</span>
                    </div>
                    <div class="status-item">
                        <span>Время проверки:</span>
                        <span>{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</span>
                    </div>
                </div>
            </div>
        </body>
        </html>
        """
    except Exception as e:
        return f"""
        <html>
        <body style="font-family: Arial; padding: 40px; text-align: center;">
            <h1 style="color: red;">❌ Ошибка системы</h1>
            <p>Ошибка: {str(e)}</p>
        </body>
        </html>
        """, 500
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
    <html>
    <head>
        <title>Вход в админку</title>
        <meta charset="utf-8">
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

@app.route('/admin/dashboard')
def admin_dashboard():
    """Главная страница админки"""
    if not session.get('admin_logged_in'):
        return redirect(url_for('admin_login_page'))
    
    return f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>Админка GlobalJobHunter</title>
        <meta charset="utf-8">
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
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>🛠️ Админка GlobalJobHunter</h1>
                <div class="nav">
                    <a href="/admin/subscribers_secure">👥 Подписчики</a>
                    <a href="/admin/stats_secure">📊 Статистика</a>
                    <a href="/health">💚 Здоровье системы</a>
                    <a href="/admin/logout" class="logout">🚪 Выйти</a>
                </div>
            </div>
            
            <div style="background: white; padding: 30px; border-radius: 8px; text-align: center;">
                <h2>Добро пожаловать в админку!</h2>
                <p>Выберите нужный раздел в меню выше</p>
            </div>
        </div>
    </body>
    </html>
    """

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
        <html>
        <head>
            <title>Подписчики - Админка</title>
            <meta charset="utf-8">
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
        <html>
        <body style="font-family: Arial; padding: 40px;">
            <h1 class="error">❌ Ошибка загрузки админки</h1>
            <p>Ошибка: {str(e)}</p>
            <a href="/admin/dashboard">🏠 Вернуться в админку</a>
        </body>
        </html>
        """, 500

@app.route('/admin/stats_secure')
def admin_stats_secure():
    """Защищенная страница статистики"""
    if not session.get('admin_logged_in'):
        return redirect(url_for('admin_login_page'))
    
    if not aggregator:
        return "Сервис недоступен", 500
    
    stats = aggregator.get_cache_stats()
    
    return f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>Статистика - Админка</title>
        <meta charset="utf-8">
        <style>
            body {{ font-family: Arial; background: #f8f9fa; margin: 0; padding: 20px; }}
            .container {{ max-width: 1200px; margin: 0 auto; }}
            .nav {{ display: flex; gap: 15px; margin: 20px 0; }}
            .nav a {{ background: #007bff; color: white; padding: 10px 20px; text-decoration: none; border-radius: 4px; }}
            .stats-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(250px, 1fr)); gap: 20px; }}
            .stat-card {{ background: white; padding: 25px; border-radius: 8px; text-align: center; }}
            .stat-number {{ font-size: 2em; font-weight: bold; color: #007bff; }}
        </style>
    </head>
    <body>
        <div class="container">
            <h1>📊 Статистика системы</h1>
            
            <div class="nav">
                <a href="/admin/dashboard">🏠 Главная админки</a>
                <a href="/admin/subscribers_secure">👥 Подписчики</a>
                <a href="/admin/logout">🚪 Выйти</a>
            </div>
            
            <div class="stats-grid">
                <div class="stat-card">
                    <div class="stat-number">{stats['cache_hits']}</div>
                    <h3>Cache Hits</h3>
                </div>
                <div class="stat-card">
                    <div class="stat-number">{stats['api_requests']}</div>
                    <h3>API Requests</h3>
                </div>
                <div class="stat-card">
                    <div class="stat-number">{stats['total_jobs_found']}</div>
                    <h3>Jobs Found</h3>
                </div>
            </div>
        </div>
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
        sent_count = send_job_notifications(app, aggregator)
        
        debug_info.append(f"📧 Отправлено: {sent_count}")
        
        return "<br>".join(debug_info)
        
    except Exception as e:
        return f"❌ Ошибка: {str(e)}"
    
@app.route('/support')
def support():
    return render_template('support.html')  # или 'support_page.html' 

def email_scheduler():
    """Планировщик email рассылки"""
    print("📅 Планировщик email рассылки запущен")
    
    # Ежедневно в 9:00
    schedule.every().day.at("09:00").do(send_daily_notifications)
    
    # Еженедельно по понедельникам в 9:00  
    schedule.every().monday.at("09:00").do(send_weekly_notifications)
    
    # Ежемесячно 1 числа в 9:00 (приблизительно)
    schedule.every(30).days.at("09:00").do(send_monthly_notifications)
    
    # Для тестирования - каждые 2 минуты (УДАЛИТЬ В ПРОДАКШЕНЕ)
    # schedule.every(2).minutes.do(send_test_notifications)
    
    while True:
        schedule.run_pending()
        time.sleep(60)  # Проверяем каждую минуту

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
    
# Автоматическая инициализация БД для Railway
if os.getenv('RAILWAY_ENVIRONMENT'):
    with app.app_context():
        try:
            # Проверяем существование таблиц
            from sqlalchemy import inspect
            inspector = inspect(db.engine)
            existing_tables = inspector.get_table_names()
            
            if not existing_tables:
                print("🔄 Таблицы не найдены, создаем новые...")
                db.create_all()
                print("✅ Таблицы созданы")
            else:
                print(f"✅ БД уже существует с таблицами: {existing_tables}")
                
        except Exception as e:
            print(f"⚠️ Ошибка инициализации БД: {e}")
            # НЕ вызываем db.create_all() здесь!   

if __name__ == '__main__':
    # Запускаем планировщик в отдельном потоке
    print("🚀 Запуск планировщика email рассылки...")
    scheduler_thread = Thread(target=email_scheduler, daemon=True)
    scheduler_thread.start()
    
    # Запускаем Flask
    port = int(os.environ.get('PORT', 5000))
    debug = os.environ.get('FLASK_ENV') == 'development'
    
    print("🌍 Запуск Flask сервера...")
    app.run(host='0.0.0.0', port=port, debug=debug)


