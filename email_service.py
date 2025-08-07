from flask_mail import Mail, Message
from database import db, Subscriber, EmailLog
from datetime import datetime, timedelta
import os
from threading import Thread

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
    """Отправка уведомлений всем подписчикам"""
    with app.app_context():
        print("📧 Начинаем отправку уведомлений...")
        
        subscribers = Subscriber.query.filter_by(is_active=True).all()
        print(f"👥 Найдено {len(subscribers)} активных подписчиков")
        
        sent_count = 0
        
        for subscriber in subscribers:
            try:
                print(f"📧 Обрабатываем {subscriber.email}...")
                
                preferences = {
                    'is_refugee': subscriber.is_refugee,
                    'selected_jobs': subscriber.get_selected_jobs(),
                    'countries': subscriber.get_countries(),
                    'city': subscriber.city
                }
                
                if not preferences['selected_jobs'] or not preferences['countries']:
                    print(f"⚠️ У {subscriber.email} нет профессий или стран")
                    continue
                
                # 🔧 ИЗМЕНЕНИЕ: ИСПОЛЬЗУЕМ РЕАЛЬНЫЙ ПОИСК ВМЕСТО ТЕСТОВЫХ ВАКАНСИЙ
                if aggregator:
                    real_jobs = aggregator.search_specific_jobs(preferences)
                    print(f"🎯 Найдено {len(real_jobs)} реальных вакансий для {subscriber.email}")
                else:
                    print(f"⚠️ Агрегатор недоступен, создаем тестовые вакансии для {subscriber.email}")
                    # Fallback на тестовые вакансии если агрегатор не работает
                    real_jobs = []
                    for i, job in enumerate(preferences['selected_jobs'][:3]):
                        for j, country_code in enumerate(preferences['countries'][:2]):
                            country_names = {'de': 'Германия', 'pl': 'Польша', 'us': 'США', 'ca': 'Канада'}
                            country_name = country_names.get(country_code, country_code)
                            
                            fake_job = type('Job', (), {
                                'title': f"{job}",
                                'company': f'Европейская компания #{i+1}',
                                'location': f"Главный офис, {country_name}",
                                'country': country_name,
                                'salary': '€2000-3000' if country_code in ['de', 'pl'] else '$3000-4000',
                                'description': f'Отличная возможность для работы в должности {job}. Мы рассматриваем украинских беженцев и предоставляем поддержку.',
                                'apply_url': f'https://example.com/apply/{i}{j}',
                                'refugee_friendly': True,
                                'language_requirement': 'no_language_required' if subscriber.is_refugee else 'basic_required'
                            })()
                            real_jobs.append(fake_job)
                
                if len(real_jobs) > 0:
                    print(f"📤 Пытаемся отправить email на {subscriber.email}")
                    success = send_job_email(app, subscriber, real_jobs, preferences)
                    
                    if success:
                        log = EmailLog(
                            subscriber_id=subscriber.id,
                            subject=f"🎯 ТОП-{min(5, len(real_jobs))} новых вакансий (из {len(real_jobs)} найденных)",
                            jobs_count=len(real_jobs),
                            status='sent',
                            sent_at=datetime.now()
                        )
                        db.session.add(log)
                        subscriber.last_sent = datetime.now()
                        sent_count += 1
                        print(f"✅ Успешно отправлено на {subscriber.email}")
                        time.sleep(2)  # 2 секунды между письмами
                    else:
                        print(f"❌ Не удалось отправить на {subscriber.email}")
                
            except Exception as e:
                print(f"❌ Ошибка для {subscriber.email}: {e}")
                import traceback
                traceback.print_exc()
        
        db.session.commit()
        print(f"✅ Итого отправлено {sent_count} уведомлений")
        return sent_count

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
        
        # ИЗМЕНИЛИ SUBJECT
        top_count = min(5, len(jobs))
        total_count = len(jobs)
        subject = f"🎯 ТОП-{top_count} новых вакансий (из {total_count} найденных)"
        
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
    """Генерируем HTML для email с кнопкой 'Показать еще'"""
    
    # Разделяем на ТОП-5 и остальные
    top_jobs = jobs[:5]
    remaining_jobs = jobs[5:] if len(jobs) > 5 else []
    
    # Группируем ТОП-5 по странам
    top_jobs_by_country = {}
    for job in top_jobs:
        country = job.country
        if country not in top_jobs_by_country:
            top_jobs_by_country[country] = []
        top_jobs_by_country[country].append(job)
    
    # Группируем остальные по странам
    remaining_jobs_by_country = {}
    for job in remaining_jobs:
        country = job.country
        if country not in remaining_jobs_by_country:
            remaining_jobs_by_country[country] = []
        remaining_jobs_by_country[country].append(job)
    
    # Формируем HTML
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
            .show-more-btn {{ 
                background: #28a745; color: white; padding: 12px 25px; 
                border: none; border-radius: 25px; cursor: pointer; margin: 20px 0;
                font-size: 16px; width: 100%; text-align: center;
            }}
            .show-more-btn:hover {{ background: #218838; }}
            .hidden-jobs {{ display: none; }}
        </style>
        <script>
            function toggleHiddenJobs() {{
                var hiddenJobs = document.getElementById('hidden-jobs');
                var button = document.getElementById('show-more-btn');
                
                if (hiddenJobs.style.display === 'none' || hiddenJobs.style.display === '') {{
                    hiddenJobs.style.display = 'block';
                    button.innerHTML = '▲ Скрыть дополнительные вакансии';
                    button.style.background = '#dc3545';
                }} else {{
                    hiddenJobs.style.display = 'none';
                    button.innerHTML = '▼ Показать остальные {len(remaining_jobs)} вакансий';
                    button.style.background = '#28a745';
                }}
            }}
        </script>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>🌍 GlobalJobHunter</h1>
                <p>🎯 ТОП-{len(top_jobs)} новых вакансий (из {len(jobs)} найденных)</p>
            </div>
            
            <div class="content">
                <p>Привет! Мы отобрали для вас лучшие вакансии по вашим предпочтениям:</p>
                <ul>
                    <li><strong>Профессии:</strong> {', '.join(preferences['selected_jobs'][:3])}{'...' if len(preferences['selected_jobs']) > 3 else ''}</li>
                    <li><strong>Страны:</strong> {', '.join(preferences['countries'])}</li>
                    {f"<li><strong>Город:</strong> {preferences['city']}</li>" if preferences.get('city') else ''}
                </ul>
                
                <h3>🏆 Лучшие {len(top_jobs)} вакансий:</h3>
    """
    
    # Добавляем ТОП-5 вакансий по странам
    for country, country_jobs in top_jobs_by_country.items():
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
    
    # Добавляем кнопку "Показать еще" если есть скрытые вакансии
    if remaining_jobs:
        html += f"""
        <div style="text-align: center; margin: 30px 0;">
            <button class="show-more-btn" id="show-more-btn" onclick="toggleHiddenJobs()">
                ▼ Показать остальные {len(remaining_jobs)} вакансий
            </button>
        </div>
        """
        
        # Добавляем скрытые вакансии
        html += '<div id="hidden-jobs" class="hidden-jobs">'
        html += f'<h3>📋 Остальные {len(remaining_jobs)} вакансий:</h3>'
        
        for country, country_jobs in remaining_jobs_by_country.items():
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
        
        html += '</div>'  # Закрываем hidden-jobs
    
    html += f"""
            </div>
            
            <div class="footer">
                <p>Это автоматическое уведомление от GlobalJobHunter</p>
                <p><a href="http://localhost:5000/subscription/manage?email={subscriber.email}">⚙️ Настроить подписку</a> | 
                <a href="http://localhost:5000/subscription/manage?email={subscriber.email}">Отписаться от рассылки</a></p>
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