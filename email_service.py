from flask_mail import Mail, Message
from database import db, Subscriber, EmailLog
from datetime import datetime, timedelta
import os
from threading import Thread
import time

mail = Mail()

def send_async_email(app, msg):
    """Отправка email в отдельном потоке"""
    with app.app_context():
        try:
            print(f"📧 Отправляем email на {msg.recipients[0]}...")
            mail.send(msg)
            print(f"✅ Email успешно отправлен на {msg.recipients[0]}")
            return True
        except Exception as e:
            print(f"❌ Ошибка отправки email на {msg.recipients[0]}: {e}")
            return False

def send_job_notifications(app, aggregator):
    """Отправка уведомлений всем подписчикам - ИСПРАВЛЕННАЯ ВЕРСИЯ"""
    with app.app_context():
        print("=" * 60)
        print("📧 НАЧИНАЕМ ОТПРАВКУ УВЕДОМЛЕНИЙ...")
        print("=" * 60)
        
        subscribers = Subscriber.query.filter_by(is_active=True).all()
        print(f"👥 Найдено {len(subscribers)} активных подписчиков")
        
        if not subscribers:
            print("ℹ️ Нет активных подписчиков для рассылки")
            return 0
        
        sent_count = 0
        
        for i, subscriber in enumerate(subscribers, 1):
            try:
                print(f"\n🔄 ({i}/{len(subscribers)}) Обрабатываем {subscriber.email}...")
                
                preferences = {
                    'is_refugee': subscriber.is_refugee,
                    'selected_jobs': subscriber.get_selected_jobs(),
                    'countries': subscriber.get_countries(),
                    'city': subscriber.city
                }
                
                print(f"   ⚙️ Предпочтения: профессии={len(preferences['selected_jobs'])}, страны={len(preferences['countries'])}")
                
                if not preferences['selected_jobs'] or not preferences['countries']:
                    print(f"   ⚠️ У {subscriber.email} отсутствуют профессии или страны - пропускаем")
                    continue
                
                # 🔧 ИСПРАВЛЕНИЕ: ПОИСК РЕАЛЬНЫХ ВАКАНСИЙ
                print(f"   🔍 Ищем вакансии через агрегатор...")
                
                if aggregator:
                    # Используем РЕАЛЬНЫЙ поиск вакансий
                    real_jobs = aggregator.search_specific_jobs(preferences)
                    print(f"   ✅ Найдено {len(real_jobs)} реальных вакансий")
                    
                    if len(real_jobs) == 0:
                        print(f"   ℹ️ Нет новых вакансий для {subscriber.email} - пропускаем отправку")
                        continue
                        
                else:
                    print(f"   ⚠️ Агрегатор недоступен - создаем тестовые вакансии")
                    real_jobs = create_fallback_jobs(preferences)
                
                # Отправляем email с найденными вакансиями
                if len(real_jobs) > 0:
                    print(f"   📤 Отправляем email с {len(real_jobs)} вакансиями...")
                    
                    success = send_job_email(app, subscriber, real_jobs[:20], preferences)
                    
                    if success:
                        log = EmailLog(
                            subscriber_id=subscriber.id,
                            email=subscriber.email,
                            subject=f"🎯 ТОП-{min(5, len(real_jobs))} новых вакансий (из {len(real_jobs)} найденных)",
                            jobs_count=len(real_jobs),
                            status='sent',
                            sent_at=datetime.now()
                        )
                        db.session.add(log)
                        subscriber.last_sent = datetime.now()
                        sent_count += 1
                        print(f"   ✅ Email успешно отправлен на {subscriber.email}")
                        time.sleep(3)
                    else:
                        print(f"   ❌ Не удалось отправить email на {subscriber.email}")
                
            except Exception as e:
                print(f"   ❌ ОШИБКА для {subscriber.email}: {e}")
                import traceback
                traceback.print_exc()
        
        db.session.commit()
        print("=" * 60)
        print(f"🎉 ОТПРАВКА ЗАВЕРШЕНА: {sent_count}/{len(subscribers)} писем отправлено")
        print("=" * 60)
        return sent_count

def create_fallback_jobs(preferences):
    """Создание fallback вакансий только при недоступности агрегатора"""
    fallback_jobs = []
    
    for i, job_title in enumerate(preferences['selected_jobs'][:2]):
        for j, country_code in enumerate(preferences['countries'][:2]):
            country_names = {'de': 'Германия', 'pl': 'Польша', 'gb': 'Великобритания', 'us': 'США', 'ca': 'Канада'}
            country_name = country_names.get(country_code, country_code.upper())
            
            fake_job = type('FallbackJob', (), {
                'id': f'fallback_{i}_{j}',
                'title': f"{job_title}",
                'company': f'Компания #{i+j+1}',
                'location': f"{country_name}",
                'country': country_name,
                'salary': '€2500-3500' if country_code in ['de'] else '$3000-4500',
                'description': f'Вакансия {job_title} в {country_name}. Рассматриваем кандидатов из Украины.',
                'apply_url': f'https://jobs-example.com/apply/{i}{j}',
                'source': 'fallback',
                'posted_date': datetime.now().strftime('%Y-%m-%d'),
                'job_type': 'full_time',
                'refugee_friendly': preferences.get('is_refugee', True),
                'language_requirement': 'no_language_required' if preferences.get('is_refugee') else 'basic'
            })()
            
            fallback_jobs.append(fake_job)
    
    print(f"🧪 Создано {len(fallback_jobs)} fallback вакансий")
    return fallback_jobs

def should_send_notification(subscriber):
    """Проверяем, нужно ли отправлять уведомление"""
    if not subscriber.last_sent:
        return True
    
    now = datetime.utcnow()
    
    if subscriber.frequency == 'daily':
        return now - subscriber.last_sent > timedelta(days=1)
    elif subscriber.frequency == 'weekly':
        return now - subscriber.last_sent > timedelta(days=7)
    elif subscriber.frequency == 'monthly':
        return now - subscriber.last_sent > timedelta(days=30)
    
    return False

def send_job_email(app, subscriber, jobs, preferences):
    """Отправка email с вакансиями"""
    try:
        print(f"📤 Отправляем email на {subscriber.email} с {len(jobs)} вакансиями")
        
        # Формируем HTML контент
        html_content = generate_email_html(subscriber, jobs, preferences)
        
        # ИСПРАВЛЕННЫЙ SUBJECT - убираем "ТОП-5"
        total_count = len(jobs)
        if total_count == 1:
            subject = f"🎯 Найдена 1 новая вакансия"
        elif 2 <= total_count <= 4:
            subject = f"🎯 Найдено {total_count} новые вакансии"
        else:
            subject = f"🎯 Найдено {total_count} новых вакансий"
        
        msg = Message(
            subject=subject,
            sender=os.getenv('MAIL_DEFAULT_SENDER'),
            recipients=[subscriber.email],
            html=html_content
        )
        
        # Отправляем СИНХРОННО
        with app.app_context():
            mail.send(msg)
            print(f"✅ Email успешно отправлен на {subscriber.email}")
            return True
        
    except Exception as e:
        print(f"❌ Ошибка отправки email на {subscriber.email}: {e}")
        return False

def generate_email_html(subscriber, jobs, preferences):
    """Генерируем HTML для email - ВСЕ ВАКАНСИИ СРАЗУ БЕЗ JavaScript"""
    
    total_jobs = len(jobs)
    
    # Группируем ВСЕ вакансии по странам
    jobs_by_country = {}
    for job in jobs:
        country = job.country
        if country not in jobs_by_country:
            jobs_by_country[country] = []
        jobs_by_country[country].append(job)
    
    # ИСПРАВЛЕННЫЙ заголовок
    if total_jobs == 1:
        jobs_title = "Найдена 1 вакансия"
    elif 2 <= total_jobs <= 4:
        jobs_title = f"Найдено {total_jobs} вакансии"
    else:
        jobs_title = f"Найдено {total_jobs} вакансий"
    
    # Формируем HTML БЕЗ JavaScript
    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
        <title>Новые вакансии от GlobalJobHunter</title>
        <style>
            body {{ font-family: Arial, sans-serif; margin: 0; padding: 20px; background-color: #f8f9fa; }}
            .container {{ max-width: 600px; margin: 0 auto; background: white; border-radius: 10px; overflow: hidden; }}
            .header {{ background: #0057B7; color: white; padding: 30px 20px; text-align: center; }}
            .content {{ padding: 20px; }}
            .job-card {{ border: 1px solid #dee2e6; border-radius: 8px; padding: 15px; margin: 15px 0; }}
            .job-title {{ font-weight: bold; color: #0057B7; font-size: 16px; }}
            .job-company {{ color: #6c757d; margin: 5px 0; }}
            .job-location {{ color: #28a745; font-size: 14px; }}
            .country-header {{ background: #e9ecef; padding: 15px; margin: 20px 0 10px 0; border-radius: 5px; font-weight: bold; }}
            .footer {{ background: #f8f9fa; padding: 20px; text-align: center; font-size: 12px; color: #6c757d; }}
            .btn {{ background: #0057B7; color: white !important; padding: 10px 20px; text-decoration: none; border-radius: 5px; display: inline-block; }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>🌍 GlobalJobHunter</h1>
                <p>📍 {jobs_title}</p>
            </div>
            
            <div class="content">
                <p>Привет! Мы нашли для вас новые вакансии по вашим предпочтениям:</p>
                <ul>
                    <li><strong>Профессии:</strong> {', '.join(preferences['selected_jobs'][:3])}{'...' if len(preferences['selected_jobs']) > 3 else ''}</li>
                    <li><strong>Страны:</strong> {', '.join(preferences['countries'])}</li>
                    {f"<li><strong>Город:</strong> {preferences['city']}</li>" if preferences.get('city') else ''}
                </ul>
                
                <h3>🎯 Все найденные вакансии:</h3>
    """
    
    # Добавляем ВСЕ вакансии сразу, сгруппированные по странам
    for country, country_jobs in jobs_by_country.items():
        html += f'<div class="country-header">🌍 {country} ({len(country_jobs)} вакансий)</div>'
        
        for job in country_jobs:
            salary_text = f"<br><strong>💰 {job.salary}</strong>" if job.salary else ""
            badges = ""
            if job.refugee_friendly:
                badges += '<span style="background: #28a745; color: white; padding: 2px 8px; border-radius: 10px; font-size: 11px; margin-right: 5px;">🏠 Для беженцев</span>'
            if job.language_requirement == 'no_language_required':
                badges += '<span style="background: #17a2b8; color: white; padding: 2px 8px; border-radius: 10px; font-size: 11px;">🔇 Без языка</span>'
            
            html += f"""
            <div class="job-card">
                <div class="job-title">{job.title}</div>
                <div class="job-company">🏢 {job.company}</div>
                <div class="job-location">📍 {job.location}</div>
                {salary_text}
                <div style="margin: 10px 0;">{badges}</div>
                <a href="{job.apply_url}" class="btn" target="_blank" style="color: white !important; text-decoration: none;">Откликнуться</a>
            </div>
            """
    
    html += f"""
            </div>
            
            <div class="footer">
                <p>Это автоматическое уведомление от GlobalJobHunter</p>
                <p><a href="{os.getenv('BASE_URL', 'https://web-production-2928e.up.railway.app')}/subscription/manage?email={subscriber.email}">⚙️ Настроить подписку</a> | 
                <a href="{os.getenv('BASE_URL', 'https://web-production-2928e.up.railway.app')}/unsubscribe?email={subscriber.email}">Отписаться от рассылки</a></p>
                <p>© 2025 GlobalJobHunter.</p>
            </div>
        </div>
    </body>
    </html>
    """
    
    return html

def send_welcome_email(app, email):
    """Отправка приветственного email"""
    try:
        print(f"🔄 Подготавливаем welcome email для {email}...")
        
        # Определяем базовый URL
        base_url = os.getenv('BASE_URL', 'http://localhost:5000')
        manage_url = f"{base_url}/subscription/manage?email={email}"
        unsubscribe_url = f"{base_url}/unsubscribe?email={email}"
        
        html_content = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="utf-8">
            <style>
                body {{ font-family: Arial, sans-serif; margin: 0; padding: 20px; background-color: #f8f9fa; }}
                .container {{ max-width: 600px; margin: 0 auto; background: white; border-radius: 15px; overflow: hidden; box-shadow: 0 4px 20px rgba(0,0,0,0.1); }}
                .header {{ background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 40px 20px; text-align: center; }}
                .content {{ padding: 30px; }}
                .button {{ display: inline-block; background: #667eea; color: white; text-decoration: none; padding: 12px 25px; border-radius: 25px; font-weight: bold; margin: 10px 5px; }}
                .footer {{ background: #f8f9fa; padding: 20px; text-align: center; font-size: 12px; color: #666; }}
                .info-box {{ background: #e3f2fd; border-left: 4px solid #2196f3; padding: 15px; margin: 20px 0; border-radius: 5px; }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h1>🌍 Добро пожаловать в GlobalJobHunter!</h1>
                    <p>Ваш помощник в поиске работы по всему миру</p>
                </div>
                <div class="content">
                    <h2>🎉 Спасибо за подписку!</h2>
                    <p>Теперь вы будете получать персональные подборки вакансий прямо на ваш email.</p>
                    
                    <div class="info-box">
                        <h4>📧 Что вас ждет:</h4>
                        <ul>
                            <li>Еженедельные подборки актуальных вакансий</li>
                            <li>Персональные рекомендации на основе ваших предпочтений</li>
                            <li>Специальные предложения для украинских беженцев</li>
                            <li>Вакансии без требований к языку</li>
                        </ul>
                    </div>
                    
                    <div style="text-align: center; margin: 30px 0;">
                        <a href="{manage_url}" class="button">⚙️ Управлять подпиской</a>
                        <a href="{base_url}" class="button" style="background: #28a745;">🔍 Найти работу сейчас</a>
                    </div>
                    
                    <div style="background: #fff3cd; border: 1px solid #ffeaa7; border-radius: 8px; padding: 15px; margin: 20px 0;">
                        <h5 style="margin-top: 0; color: #856404;">🛠️ Управление подпиской</h5>
                        <p style="margin: 10px 0; color: #856404; font-size: 14px;">
                            <strong>Вы можете в любое время:</strong><br>
                            • Изменить профессии и страны поиска<br>
                            • Настроить частоту уведомлений<br>
                            • Добавить или убрать города<br>
                            • Полностью отписаться от рассылки
                        </p>
                        <p style="margin: 10px 0; color: #856404; font-size: 14px;">
                            <strong>Для этого:</strong> нажмите кнопку "Управлять подпиской" выше или используйте ссылку в письмах с вакансиями.
                        </p>
                    </div>
                    
                    <p><small>Ваш email: {email}</small></p>
                    <p><small>Частота уведомлений: еженедельно</small></p>
                    <p><small>Дата подписки: {datetime.now().strftime('%d.%m.%Y %H:%M')}</small></p>
                </div>
                <div class="footer">
                    <p><a href="{manage_url}">Управление подпиской</a> | <a href="{unsubscribe_url}">Отписаться</a> | <a href="{base_url}">Найти работу</a></p>
                    <p>© 2025 GlobalJobHunter.</p>
                </div>
            </div>
        </body>
        </html>
        """
        
        msg = Message(
            subject="🎉 Добро пожаловать в GlobalJobHunter!",
            sender=os.getenv('MAIL_DEFAULT_SENDER'),
            recipients=[email],
            html=html_content
        )
        
        print(f"📤 Отправляем welcome email...")
        
        # ИСПРАВЛЕНИЕ: Отправляем БЕЗ потоков для тестирования
        with app.app_context():
            mail.send(msg)
            print(f"✅ Welcome email отправлен на {email}")
            
            # Логируем успешную отправку
            # Находим подписчика
            subscriber = Subscriber.query.filter_by(email=email).first()
            if subscriber:
                log = EmailLog(
                    subscriber_id=subscriber.id,  # ← ПРАВИЛЬНО
                    subject="Добро пожаловать в GlobalJobHunter!",
                    jobs_count=0,
                    status='sent',
                    sent_at=datetime.now()
                )
                db.session.add(log)
            db.session.add(log)
            db.session.commit()
            print(f"📝 Лог записан в базу")
            
            return True
        
    except Exception as e:
        print(f"❌ Ошибка отправки welcome email на {email}: {str(e)}")
        
        # Логируем ошибку
        try:
            with app.app_context():
                log = EmailLog(
                    email=email,
                    status='failed',
                    error_message=str(e),
                    sent_at=datetime.now()
                )
                db.session.add(log)
                db.session.commit()
                print(f"📝 Лог ошибки записан в базу")
        except Exception as log_error:
            print(f"❌ Ошибка записи лога: {log_error}")
            
        return False
    
def send_preferences_update_email(app, subscriber):
    """Отправка email о изменении предпочтений"""
    print(f"📧 send_preferences_update_email вызвана для {subscriber.email}")  # ДОБАВЛЕНО
    
    try:
        print("🔄 Подготавливаем email...")  # ДОБАВЛЕНО
        
        base_url = os.getenv('BASE_URL', 'http://localhost:5000')
        manage_url = f"{base_url}/subscription/manage?email={subscriber.email}"
        
        print(f"🔗 manage_url: {manage_url}")  # ДОБАВЛЕНО
        
        html_content = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="utf-8">
            <style>
                body {{ font-family: Arial, sans-serif; margin: 0; padding: 20px; background-color: #f8f9fa; }}
                .container {{ max-width: 500px; margin: 0 auto; background: white; border-radius: 10px; overflow: hidden; }}
                .header {{ background: #28a745; color: white; padding: 20px; text-align: center; }}
                .content {{ padding: 20px; }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h2>✅ Настройки обновлены!</h2>
                </div>
                <div class="content">
                    <p>Ваши предпочтения для поиска вакансий успешно обновлены:</p>
                    <ul>
                        <li><strong>Профессии:</strong> {', '.join(subscriber.get_selected_jobs()[:3])}{'...' if len(subscriber.get_selected_jobs()) > 3 else ''}</li>
                        <li><strong>Страны:</strong> {', '.join(subscriber.get_countries())}</li>
                        <li><strong>Город:</strong> {subscriber.city or 'Не указан'}</li>
                        <li><strong>Частота:</strong> {subscriber.frequency}</li>
                    </ul>
                    <p><a href="{manage_url}">Изменить снова</a></p>
                </div>
            </div>
        </body>
        </html>
        """
        
        print("🔄 Создаем Message...")  # ДОБАВЛЕНО
        
        msg = Message(
            subject="✅ Настройки подписки обновлены",
            sender=os.getenv('MAIL_DEFAULT_SENDER'),
            recipients=[subscriber.email],
            html=html_content
        )
        
        print(f"📧 Отправляем email от {msg.sender} на {msg.recipients}...")  # ДОБАВЛЕНО
        
        with app.app_context():
            mail.send(msg)
            print("✅ mail.send() выполнено успешно")  # ДОБАВЛЕНО
            
            # Логируем в базу
            print("🔄 Записываем лог в БД...")  # ДОБАВЛЕНО
            log = EmailLog(
                subscriber_id=subscriber.id,
                subject="Настройки подписки обновлены",
                jobs_count=0,
                status='sent',
                sent_at=datetime.now()
            )
            db.session.add(log)
            db.session.commit()
            print("✅ Лог записан в БД")  # ДОБАВЛЕНО
            
            return True
            
    except Exception as e:
        print(f"❌ Ошибка отправки email об изменениях: {e}")
        import traceback
        traceback.print_exc()  # ДОБАВЛЕНО
        return False   