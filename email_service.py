# -*- coding: utf-8 -*-
from flask_mail import Mail, Message
from database import db, Subscriber, EmailLog
from datetime import datetime, timedelta
import os
from threading import Thread
import time
import json

_UI_DICT_CACHE = {}

def _front_tr(lang: str, s: str) -> str:
    """Переводит русскую фразу s с помощью фронтового словаря /static/i18n/<lang>.json.
       Если ключа нет — возвращает исходное s."""
    if not s or lang == 'ru':
        return s
    try:
        d = _UI_DICT_CACHE.get(lang)
        if d is None:
            base = os.path.join(os.path.dirname(__file__), 'static', 'i18n', f'{lang}.json')
            with open(base, 'r', encoding='utf-8') as f:
                d = json.load(f)
            _UI_DICT_CACHE[lang] = d
        return d.get(s, s)
    except Exception:
        return s

# -----------------------------------------------------------------------------
# Server-side i18n для писем (минимальный словарь; расширяйте по надобности)
# -----------------------------------------------------------------------------

I18N = {
    "ru": {
        "app_name": "GlobalJobHunter",

        # subjects / headings
        "digest_subject": "🎯 Найдено {n} {vac_forms}",
        "digest_subject_1": "🎯 Найдена 1 новая вакансия",
        "welcome_subject": "🎉 Добро пожаловать в GlobalJobHunter!",
        "prefs_subject": "✅ Настройки подписки обновлены",

        # plural forms base words
        "vacancy_forms": ("новых вакансий", "новые вакансии", "новых вакансий"),  # many, few(2-4), many(5+)
        "vacancy_forms_short": ("вакансий", "вакансии", "вакансий"),

        # digest header/subheader
        "digest_title": "Найдено {n} {vac_short}",
        "digest_intro": "Привет! Мы нашли для вас новые вакансии по вашим предпочтениям:",
        "pref_professions": "Профессии",
        "pref_countries": "Страны",
        "pref_city": "Город",
        "digest_all_jobs": "🎯 Все найденные вакансии:",

        # job card
        "badge_refugee": "🏠 Для беженцев",
        "badge_no_lang": "🔇 Без языка",
        "btn_apply": "Откликнуться",

        # digest footer
        "auto_notice": "Это автоматическое уведомление от GlobalJobHunter",
        "manage": "⚙️ Настроить подписку",
        "unsubscribe": "Отписаться от рассылки",
        "find_job_now": "🔍 Найти работу сейчас",
        "copyright": "© {year} GlobalJobHunter.",

        # welcome email
        "welcome_title": "🌍 Добро пожаловать в GlobalJobHunter!",
        "welcome_tagline": "Ваш помощник в поиске работы по всему миру",
        "welcome_thanks": "🎉 Спасибо за подписку!",
        "welcome_you_will_get": "📧 Что вас ждет:",
        "welcome_bul_1": "Еженедельные подборки актуальных вакансий",
        "welcome_bul_2": "Персональные рекомендации на основе ваших предпочтений",
        "welcome_bul_3": "Специальные предложения для украинских беженцев",
        "welcome_bul_4": "Вакансии без требований к языку",
        "welcome_manage": "⚙️ Управлять подпиской",
        "welcome_find_now": "🔍 Найти работу сейчас",
        "welcome_box_title": "🛠️ Управление подпиской",
        "welcome_box_text_1": "Вы можете в любое время:",
        "welcome_box_list": [
            "Изменить профессии и страны поиска",
            "Настроить частоту уведомлений",
            "Добавить или убрать города",
            "Полностью отписаться от рассылки"
        ],
        "welcome_box_text_2": "Для этого: нажмите кнопку «Управлять подпиской» выше или используйте ссылку в письмах с вакансиями.",
        "welcome_email": "Ваш email",
        "welcome_freq": "Частота уведомлений",
        "welcome_weekly": "еженедельно",
        "nav_manage": "Управление подпиской",
        "nav_unsub": "Отписаться",
        "nav_find": "Найти работу",

        # preferences updated
        "prefs_title": "✅ Настройки обновлены!",
        "prefs_intro": "Ваши предпочтения для поиска вакансий успешно обновлены:",
        "prefs_professions": "Профессии",
        "prefs_countries": "Страны",
        "prefs_city": "Город",
        "prefs_city_none": "Не указан",
        "prefs_frequency": "Частота",
        "prefs_change_again": "Изменить снова",

        # countries header in digest list
        "country_header": "🌍 {country} ({n} {vac_short})"
    },

    "en": {
        "app_name": "GlobalJobHunter",

        "digest_subject": "🎯 Found {n} {vac_forms}",
        "digest_subject_1": "🎯 1 new job found",
        "welcome_subject": "🎉 Welcome to GlobalJobHunter!",
        "prefs_subject": "✅ Subscription settings updated",

        "vacancy_forms": ("new jobs", "new jobs", "new jobs"),
        "vacancy_forms_short": ("jobs", "jobs", "jobs"),

        "digest_title": "Found {n} {vac_short}",
        "digest_intro": "Hi! We’ve found new jobs based on your preferences:",
        "pref_professions": "Professions",
        "pref_countries": "Countries",
        "pref_city": "City",
        "digest_all_jobs": "🎯 All found vacancies:",

        "badge_refugee": "🏠 Refugee-friendly",
        "badge_no_lang": "🔇 No language required",
        "btn_apply": "Apply",

        "auto_notice": "This is an automated notification from GlobalJobHunter",
        "manage": "⚙️ Manage subscription",
        "unsubscribe": "Unsubscribe",
        "find_job_now": "🔍 Find a job now",
        "copyright": "© {year} GlobalJobHunter.",

        "welcome_title": "🌍 Welcome to GlobalJobHunter!",
        "welcome_tagline": "Your assistant for finding jobs worldwide",
        "welcome_thanks": "🎉 Thanks for subscribing!",
        "welcome_you_will_get": "📧 What you’ll get:",
        "welcome_bul_1": "Weekly digests of fresh vacancies",
        "welcome_bul_2": "Personalized suggestions based on your preferences",
        "welcome_bul_3": "Special options for Ukrainian refugees",
        "welcome_bul_4": "Jobs that don’t require local language",
        "welcome_manage": "⚙️ Manage subscription",
        "welcome_find_now": "🔍 Start job search",
        "welcome_box_title": "🛠️ Subscription management",
        "welcome_box_text_1": "You can at any time:",
        "welcome_box_list": [
            "Change professions and countries",
            "Adjust notification frequency",
            "Add or remove cities",
            "Unsubscribe completely"
        ],
        "welcome_box_text_2": "Click “Manage subscription” above or use the link in job emails.",
        "welcome_email": "Your email",
        "welcome_freq": "Frequency",
        "welcome_weekly": "weekly",
        "nav_manage": "Manage subscription",
        "nav_unsub": "Unsubscribe",
        "nav_find": "Find jobs",

        "prefs_title": "✅ Settings updated!",
        "prefs_intro": "Your job search preferences were updated successfully:",
        "prefs_professions": "Professions",
        "prefs_countries": "Countries",
        "prefs_city": "City",
        "prefs_city_none": "Not specified",
        "prefs_frequency": "Frequency",
        "prefs_change_again": "Change again",

        "country_header": "🌍 {country} ({n} {vac_short})"
    },

    "uk": {
        "app_name": "GlobalJobHunter",

        "digest_subject": "🎯 Знайдено {n} {vac_forms}",
        "digest_subject_1": "🎯 Знайдена 1 нова вакансія",
        "welcome_subject": "🎉 Ласкаво просимо до GlobalJobHunter!",
        "prefs_subject": "✅ Налаштування підписки оновлено",

        "vacancy_forms": ("нових вакансій", "нові вакансії", "нових вакансій"),
        "vacancy_forms_short": ("вакансій", "вакансії", "вакансій"),

        "digest_title": "Знайдено {n} {vac_short}",
        "digest_intro": "Вітаємо! Ми знайшли для вас нові вакансії за вашими налаштуваннями:",
        "pref_professions": "Професії",
        "pref_countries": "Країни",
        "pref_city": "Місто",
        "digest_all_jobs": "🎯 Усі знайдені вакансії:",

        "badge_refugee": "🏠 Для біженців",
        "badge_no_lang": "🔇 Без мови",
        "btn_apply": "Відгукнутися",

        "auto_notice": "Це автоматичне сповіщення від GlobalJobHunter",
        "manage": "⚙️ Керувати підпискою",
        "unsubscribe": "Відписатися",
        "find_job_now": "🔍 Знайти роботу зараз",
        "copyright": "© {year} GlobalJobHunter.",

        "welcome_title": "🌍 Ласкаво просимо до GlobalJobHunter!",
        "welcome_tagline": "Ваш помічник у пошуку роботи у будь-якій точці світу",
        "welcome_thanks": "🎉 Дякуємо за підписку!",
        "welcome_you_will_get": "📧 Що на вас чекає:",
        "welcome_bul_1": "Щотижневі добірки актуальних вакансій",
        "welcome_bul_2": "Персональні рекомендації на основі ваших вподобань",
        "welcome_bul_3": "Спеціальні пропозиції для українських біженців",
        "welcome_bul_4": "Вакансії без вимог до мови",
        "welcome_manage": "⚙️ Керувати підпискою",
        "welcome_find_now": "🔍 Знайти роботу зараз",
        "welcome_box_title": "🛠️ Керування підпискою",
        "welcome_box_text_1": "Ви можете в будь-який час:",
        "welcome_box_list": [
            "Змінити професії та країни пошуку",
            "Налаштувати частоту сповіщень",
            "Додати або прибрати міста",
            "Повністю відписатися"
        ],
        "welcome_box_text_2": "Натисніть «Керувати підпискою» вище або скористайтеся посиланням у листах.",
        "welcome_email": "Ваш email",
        "welcome_freq": "Частота",
        "welcome_weekly": "щотижня",
        "nav_manage": "Керування підпискою",
        "nav_unsub": "Відписатися",
        "nav_find": "Знайти роботу",

        "prefs_title": "✅ Налаштування оновлено!",
        "prefs_intro": "Ваші налаштування пошуку вакансій успішно оновлено:",
        "prefs_professions": "Професії",
        "prefs_countries": "Країни",
        "prefs_city": "Місто",
        "prefs_city_none": "Не вказано",
        "prefs_frequency": "Частота",
        "prefs_change_again": "Змінити знову",

        "country_header": "🌍 {country} ({n} {vac_short})"
    }
}


def _get_lang(subscriber, fallback='ru'):
    """Определяем язык письма: поле subscriber.lang -> cookie/lang на клиенте, иначе RU."""
    try:
        lang = (subscriber.lang or "").lower().strip()
        return lang if lang in I18N else fallback
    except Exception:
        return fallback


def _pf_ru(n):
    # формы 1, few(2-4), many(5+)
    n = abs(int(n))
    if n % 10 == 1 and n % 100 != 11:
        return 1
    if 2 <= (n % 10) <= 4 and not (12 <= (n % 100) <= 14):
        return 2
    return 0  # many


def _pf_uk(n):
    # похожие правила для украинского
    n = abs(int(n))
    if n % 10 == 1 and n % 100 != 11:
        return 1
    if 2 <= (n % 10) <= 4 and not (12 <= (n % 100) <= 14):
        return 2
    return 0


def _pf_en(n):
    # английский – фактически одна форма
    return 0


def _plural_form_index(lang, n):
    if lang == 'ru':
        return _pf_ru(n)
    if lang == 'uk':
        return _pf_uk(n)
    return _pf_en(n)


def _tr(lang, key, **kwargs):
    """Простой переводчик с подстановками."""
    d = I18N.get(lang, I18N['ru'])
    s = d.get(key, I18N['ru'].get(key, key))
    try:
        return s.format(**kwargs)
    except Exception:
        return s


def _vacancy_forms(lang, n, long=True):
    """Возвращает строку с правильной формой слова 'вакансия'."""
    idx = _plural_form_index(lang, n)
    arr = I18N[lang]['vacancy_forms' if long else 'vacancy_forms_short']
    return arr[idx]

# --- Remote-only sources gating for e-mail ---
REMOTE_OK_CATS = {
    '💻 IT И ТЕХНОЛОГИИ',
    '👔 ОФИС И УПРАВЛЕНИЕ',
    '🔍 ДРУГОЕ',
}
REMOTE_OK_TITLES = {
    'Переводчик украинского',
    'Перекладач української',
}

def _remote_allowed_email(preferences: dict, specific_jobs_map: dict) -> bool:
    selected = set(preferences.get('selected_jobs') or [])
    if not selected:
        return False
    sj = specific_jobs_map or {}
    for cat, ru_map in sj.items():
        if isinstance(ru_map, dict) and cat in REMOTE_OK_CATS:
            if any(ru in ru_map for ru in selected):
                return True
    if any(t in selected for t in REMOTE_OK_TITLES):
        return True
    return False

# -----------------------------------------------------------------------------
# Поиск/агрегация (ваш код — только слегка отрефакторен под lang)
# -----------------------------------------------------------------------------

def _search_all_sources(main_aggregator, additional_aggregators, preferences):
    """
    Поиск по ВСЕМ источникам и дедупликация.
    """
    print(f"   🔍 Ищем вакансии через все доступные источники...")
    all_found_jobs = []

    # 1) Основной агрегатор (Adzuna)
    if main_aggregator:
        try:
            adzuna_jobs = main_aggregator.search_specific_jobs(preferences)
            all_found_jobs.extend(adzuna_jobs)
            print(f"   ✅ Adzuna: найдено {len(adzuna_jobs)} вакансий")
        except Exception as e:
            print(f"   ⚠️ Adzuna ошибка: {e}")

    # 2) Дополнительные агрегаторы
    use_remote = _remote_allowed_email(preferences, getattr(main_aggregator, 'specific_jobs', {}))
    for source_name, aggregator in additional_aggregators.items():
        # Скипаем remote-only источники при не-удалённых профессиях
        if source_name in ('remotive', 'jobicy') and not use_remote:
            print(f"   ⛔ Пропуск {source_name}: выбранные профессии не допускают удалёнку")
            continue
        try:
            additional_jobs = aggregator.search_jobs(preferences)
            all_found_jobs.extend(additional_jobs)
            print(f"   ✅ {source_name.title()}: найдено {len(additional_jobs)} вакансий")
        except Exception as e:
            print(f"   ⚠️ {source_name.title()} ошибка: {e}")


    # 3) Дедупликация по apply_url
    seen_urls = set()
    final_jobs = []
    for job in all_found_jobs:
        if hasattr(job, 'apply_url') and job.apply_url and job.apply_url not in seen_urls:
            seen_urls.add(job.apply_url)
            final_jobs.append(job)

    print(f"   📊 Итого уникальных вакансий: {len(final_jobs)}")
    return final_jobs


# -----------------------------------------------------------------------------
# Отправка для одного подписчика
# -----------------------------------------------------------------------------

def _send_notification_for_subscriber(app, subscriber, main_aggregator, additional_aggregators):
    """
    Ищет и отправляет уведомление для ОДНОГО подписчика.
    """
    try:
        preferences = {
            'is_refugee': subscriber.is_refugee,
            'selected_jobs': subscriber.get_selected_jobs(),
            'countries': subscriber.get_countries(),
            'cities': [subscriber.city] if subscriber.city else []
        }

        if not preferences['selected_jobs'] or not preferences['countries']:
            print(f"   ⚠️ У {subscriber.email} отсутствуют профессии или страны - пропускаем")
            return False

        final_jobs = _search_all_sources(main_aggregator, additional_aggregators, preferences)
        if not final_jobs:
            print(f"   ℹ️ Нет новых вакансий для {subscriber.email} - пропускаем отправку")
            return False

        lang = _get_lang(subscriber)

        print(f"   📤 Отправляем email ({lang}) с {len(final_jobs)} вакансиями...")
        success = send_job_email(app, subscriber, final_jobs[:20], preferences, lang=lang)  # лимит 20

        if success:
            subject = _digest_subject(lang, len(final_jobs))
            log = EmailLog(
                subscriber_id=subscriber.id,
                email=subscriber.email,
                subject=subject,
                jobs_count=len(final_jobs),
                status='sent',
                sent_at=datetime.now()
            )
            db.session.add(log)
            subscriber.last_sent = datetime.now()
            print(f"   ✅ Email успешно отправлен на {subscriber.email}")
            return True
        else:
            print(f"   ❌ Не удалось отправить email на {subscriber.email}")
            return False

    except Exception as e:
        print(f"   ❌ КРИТИЧЕСКАЯ ОШИБКА для {subscriber.email}: {e}")
        import traceback
        traceback.print_exc()
        return False


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


# -----------------------------------------------------------------------------
# Пакетные отправки (ручной запуск / планировщик)
# -----------------------------------------------------------------------------

def send_job_notifications(app, main_aggregator, additional_aggregators={}):
    """
    Ручная отправка уведомлений всем подписчикам (из админки).
    """
    with app.app_context():
        print("=" * 60)
        print("📧 НАЧИНАЕМ РУЧНУЮ ОТПРАВКУ УВЕДОМЛЕНИЙ...")
        print("=" * 60)

        subscribers = Subscriber.query.filter_by(is_active=True).all()
        print(f"👥 Найдено {len(subscribers)} активных подписчиков")

        if not subscribers:
            return 0

        sent_count = 0
        for i, subscriber in enumerate(subscribers, 1):
            print(f"\n🔄 ({i}/{len(subscribers)}) Обрабатываем {subscriber.email}...")
            if _send_notification_for_subscriber(app, subscriber, main_aggregator, additional_aggregators):
                sent_count += 1
            time.sleep(3)  # пауза между отправками

        db.session.commit()
        print("=" * 60)
        print(f"🎉 РУЧНАЯ ОТПРАВКА ЗАВЕРШЕНА: {sent_count}/{len(subscribers)} писем отправлено")
        print("=" * 60)
        return sent_count


def run_scheduled_notifications(app, main_aggregator, additional_aggregators):
    """
    Планировщик: отправлять по расписанию.
    """
    with app.app_context():
        print("="*60)
        print(f"📅 ПЛАНИРОВЩИК: Проверка подписчиков в {datetime.now().strftime('%H:%M:%S')}")
        print("="*60)

        subscribers_to_notify = []
        all_active_subscribers = Subscriber.query.filter_by(is_active=True).all()

        for sub in all_active_subscribers:
            if should_send_notification(sub):
                subscribers_to_notify.append(sub)

        if not subscribers_to_notify:
            print("ℹ️ ПЛАНИРОВЩИК: Нет подписчиков для отправки уведомлений.")
            return

        print(f"📬 ПЛАНИРОВЩИК: Найдено {len(subscribers_to_notify)} подписчиков для уведомления.")

        sent_count = 0
        for i, subscriber in enumerate(subscribers_to_notify, 1):
            print(f"\n🔄 ({i}/{len(subscribers_to_notify)}) Отправка для {subscriber.email}...")
            if _send_notification_for_subscriber(app, subscriber, main_aggregator, additional_aggregators):
                sent_count += 1
            time.sleep(5)

        db.session.commit()
        print("=" * 60)
        print(f"🎉 ПЛАНИРОВЩИК ЗАВЕРШЕН: {sent_count}/{len(subscribers_to_notify)} писем отправлено")
        print("=" * 60)


# -----------------------------------------------------------------------------
# Fallback-вакансии (оставил как у вас; используется только при недоступности)
# -----------------------------------------------------------------------------

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


# -----------------------------------------------------------------------------
# Вспомогательные
# -----------------------------------------------------------------------------

def should_send_notification(subscriber):
    """Нужно ли отправлять уведомление по частоте."""
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


def _digest_subject(lang, total_count):
    """Локализованный subject для дайджеста."""
    if total_count == 1:
        return _tr(lang, "digest_subject_1")
    vac_forms = _vacancy_forms(lang, total_count, long=True)
    return _tr(lang, "digest_subject", n=total_count, vac_forms=vac_forms)


# -----------------------------------------------------------------------------
# Основные отправки (локализованные)
# -----------------------------------------------------------------------------

def send_job_email(app, subscriber, jobs, preferences, lang=None):
    """Отправка email с вакансиями (локализовано)."""
    try:
        lang = lang or _get_lang(subscriber)
        print(f"📤 Отправляем email на {subscriber.email} ({lang}) с {len(jobs)} вакансиями")

        html_content = generate_email_html(subscriber, jobs, preferences, lang=lang)
        subject = _digest_subject(lang, len(jobs))

        msg = Message(
            subject=subject,
            sender=os.getenv('MAIL_DEFAULT_SENDER'),
            recipients=[subscriber.email],
            html=html_content
        )

        with app.app_context():
            mail.send(msg)
            print(f"✅ Email успешно отправлен на {subscriber.email}")
            return True

    except Exception as e:
        print(f"❌ Ошибка отправки email на {subscriber.email}: {e}")
        return False


def generate_email_html(subscriber, jobs, preferences, lang='ru'):
    """Генерация HTML (локализовано)."""
    total_jobs = len(jobs)

    # Группируем по странам
    jobs_by_country = {}
    for job in jobs:
        country = getattr(job, 'country', getattr(job, 'location', '')) or ''
        jobs_by_country.setdefault(country, []).append(job)

    vac_short = _vacancy_forms(lang, total_jobs, long=False)
    jobs_title = _tr(lang, "digest_title", n=total_jobs, vac_short=vac_short)

    base_url = os.getenv('BASE_URL', 'http://localhost:5000')
    manage_url = f"{base_url}/subscription/manage?email={subscriber.email}"
    unsub_url = f"{base_url}/unsubscribe?email={subscriber.email}"


    # --- ЛОКАЛИЗАЦИЯ СПИСКА ПРОФЕССИЙ В ШАПКЕ ДАЙДЖЕСТА ---
    jobs_src = (preferences.get('selected_jobs') or [])
    jobs_disp = ', '.join(_front_tr(lang, j) for j in jobs_src[:3])
    li_prof  = f"<li><strong>{_tr(lang, 'pref_professions')}:</strong> {jobs_disp}{'...' if len(jobs_src) > 3 else ''}</li>"
    # ------------------------------------------------------

    # HTML
    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
        <title>{I18N[lang]['app_name']}</title>
        <style>
            body {{ font-family: Arial, sans-serif; margin: 0; padding: 20px; background-color: #f8f9fa; }}
            .container {{ max-width: 680px; margin: 0 auto; background: white; border-radius: 12px; overflow: hidden; }}
            .header {{ background: #0057B7; color: white; padding: 28px 20px; text-align: center; }}
            .content {{ padding: 20px; }}
            .job-card {{ border: 1px solid #e5e7eb; border-radius: 10px; padding: 14px; margin: 14px 0; }}
            .job-title {{ font-weight: bold; color: #0d47a1; font-size: 16px; }}
            .job-company {{ color: #6b7280; margin: 5px 0; }}
            .job-location {{ color: #1b5e20; font-size: 14px; }}
            .country-header {{ background: #eff6ff; padding: 12px 14px; margin: 20px 0 8px 0; border-radius: 8px; font-weight: bold; }}
            .footer {{ background: #f8f9fa; padding: 18px; text-align: center; font-size: 12px; color: #6b7280; }}
            .btn {{ background: #0057B7; color: white !important; padding: 10px 18px; text-decoration: none; border-radius: 6px; display: inline-block; }}
            .badge {{ display:inline-block; margin-right:6px; padding:2px 8px; border-radius:10px; font-size:11px; color:#fff; }}
            .bg-green {{ background:#28a745; }}
            .bg-cyan {{ background:#17a2b8; }}
            ul.inline li {{ margin-bottom: 4px; }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>🌍 {I18N[lang]['app_name']}</h1>
                <p>📍 {jobs_title}</p>
            </div>

            <div class="content">
                <p>{_tr(lang, "digest_intro")}</p>
                <ul class="inline">
                    {li_prof}
                    <li><strong>{_tr(lang, "pref_countries")}:</strong> {', '.join(preferences['countries'])}</li>
                    {f"<li><strong>{_tr(lang, 'pref_city')}:</strong> {preferences['cities'][0]}</li>" if preferences.get('cities') else ''}
                </ul>


                <h3>{_tr(lang, "digest_all_jobs")}</h3>
    """

    # Страны
    for country, country_jobs in jobs_by_country.items():
        vac_short_c = _vacancy_forms(lang, len(country_jobs), long=False)
        country_disp = country  # или _front_tr(lang, country), если сделаешь словарь стран
        html += f'<div class="country-header">{country_disp} ({len(country_jobs)} {vac_short_c})</div>'


        for job in country_jobs:
            title = getattr(job, 'title', '')
            company = getattr(job, 'company', '')
            location = getattr(job, 'location', '')
            # Нормализуем/локализуем "Удаленно"
            if location and ('Удаленно' in location or location.strip().lower().startswith('remote')):
                location = f"Remote ({_front_tr(lang, 'Удаленно')})"

            apply_url = getattr(job, 'apply_url', '')
            salary = getattr(job, 'salary', None)
            refugee = getattr(job, 'refugee_friendly', False)
            no_lang = getattr(job, 'language_requirement', '') == 'no_language_required'

            salary_html = f"<br><strong>💰 {salary}</strong>" if salary else ""
            badges = ""
            if refugee:
                badges += f'<span class="badge bg-green">{_tr(lang, "badge_refugee")}</span>'
            if no_lang:
                badges += f'<span class="badge bg-cyan">{_tr(lang, "badge_no_lang")}</span>'

            html += f"""
            <div class="job-card">
                <div class="job-title">{title}</div>
                <div class="job-company">🏢 {company}</div>
                <div class="job-location">📍 {location}</div>
                {salary_html}
                <div style="margin: 10px 0;">{badges}</div>
                <a href="{apply_url}" class="btn" target="_blank" style="color: white !important; text-decoration: none;">{_tr(lang, "btn_apply")}</a>
            </div>
            """

    year = datetime.now().year
    html += f"""
            </div>

            <div class="footer">
                <p>{_tr(lang, "auto_notice")}</p>
                <p>
                    <a href="{manage_url}">{_tr(lang, "manage")}</a> |
                    <a href="{unsub_url}">{_tr(lang, "unsubscribe")}</a>
                </p>
                <p>{_tr(lang, "copyright", year=year)}</p>
            </div>
        </div>
    </body>
    </html>
    """
    return html


def send_welcome_email(app, email, lang=None, *_, **__):
    """
    Отправка приветственного email.
    Совместима с обоими стилями вызова:
      - send_welcome_email(app, email)
      - send_welcome_email(app, email, lang='en')
    Если lang не передан или невалиден — берём из Subscriber.lang, иначе 'ru'.
    """
    try:
        # Можем логировать и использовать subscriber дальше (лог успеха с id)
        subscriber = Subscriber.query.filter_by(email=email).first()

        # Определяем язык
        SUPPORTED_LANGS = {'ru', 'uk', 'en'}
        if lang is None:
            lang = _get_lang(subscriber) if subscriber else 'ru'
        else:
            lang = (lang or 'ru').lower()
            if lang not in SUPPORTED_LANGS:
                lang = 'ru'

        print(f"🔄 Подготавливаем welcome email для {email} (lang={lang})...")

        base_url = os.getenv('BASE_URL', 'http://localhost:5000')
        manage_url = f"{base_url}/subscription/manage?email={email}"
        unsubscribe_url = f"{base_url}/unsubscribe?email={email}"

        # HTML фрагменты
        list_items = "".join(
            f"<li>{_tr(lang,'welcome_box_list')[i]}</li>"
            for i in range(len(_tr(lang,'welcome_box_list')))
        )

        html_content = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="utf-8">
            <style>
                body {{ font-family: Arial, sans-serif; margin: 0; padding: 20px; background-color: #f8f9fa; }}
                .container {{ max-width: 680px; margin: 0 auto; background: white; border-radius: 15px; overflow: hidden; box-shadow: 0 4px 20px rgba(0,0,0,0.08); }}
                .header {{ background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 36px 24px; text-align: center; }}
                .content {{ padding: 28px; }}
                .button {{ display: inline-block; background: #667eea; color: #ffffff !important;text-decoration: none; padding: 12px 20px; border-radius: 24px; font-weight: bold; margin: 8px 6px; }}
                .footer {{ background: #f8f9fa; padding: 18px; text-align: center; font-size: 12px; color: #666; }}
                .info-box {{ background: #e3f2fd; border-left: 4px solid #2196f3; padding: 14px; margin: 16px 0; border-radius: 6px; }}
                ul {{ margin: 10px 0 0 18px; }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h1>{_tr(lang, "welcome_title")}</h1>
                    <p>{_tr(lang, "welcome_tagline")}</p>
                </div>
                <div class="content">
                    <h2>{_tr(lang, "welcome_thanks")}</h2>
                    <p>{_tr(lang, "welcome_you_will_get")}</p>

                    <div class="info-box">
                        <ul>
                            <li>{_tr(lang, "welcome_bul_1")}</li>
                            <li>{_tr(lang, "welcome_bul_2")}</li>
                            <li>{_tr(lang, "welcome_bul_3")}</li>
                            <li>{_tr(lang, "welcome_bul_4")}</li>
                        </ul>
                    </div>

                    <div style="text-align:center; margin: 24px 0;">
                        <a href="{manage_url}" class="button">{_tr(lang, "welcome_manage")}</a>
                        <a href="{base_url}" class="button" style="background:#28a745;">{_tr(lang, "welcome_find_now")}</a>
                    </div>

                    <div style="background:#fff3cd; border:1px solid #ffeaa7; border-radius:8px; padding:14px; margin:18px 0;">
                        <h4 style="margin:0 0 6px 0; color:#856404;">{_tr(lang, "welcome_box_title")}</h4>
                        <p style="margin: 6px 0; color:#856404; font-size:14px;">
                            <strong>{_tr(lang, "welcome_box_text_1")}</strong><br>
                            <ul style="margin-top:8px;">{list_items}</ul>
                        </p>
                        <p style="margin: 6px 0; color:#856404; font-size:14px;">
                            {_tr(lang, "welcome_box_text_2")}
                        </p>
                    </div>

                    <p><small>{_tr(lang, "welcome_email")}: {email}</small></p>
                    <p><small>{_tr(lang, "welcome_freq")}: {_tr(lang, "welcome_weekly")}</small></p>
                    <p><small>{datetime.now().strftime('%d.%m.%Y %H:%M')}</small></p>
                </div>
                <div class="footer">
                    <p><a href="{manage_url}">{_tr(lang, "nav_manage")}</a> | <a href="{unsubscribe_url}">{_tr(lang, "nav_unsub")}</a> | <a href="{base_url}">{_tr(lang, "nav_find")}</a></p>
                    <p>{_tr(lang, "copyright", year=datetime.now().year)}</p>
                </div>
            </div>
        </body>
        </html>
        """

        msg = Message(
            subject=_tr(lang, "welcome_subject"),
            sender=os.getenv('MAIL_DEFAULT_SENDER'),
            recipients=[email],
            html=html_content
        )

        print("📤 Отправляем welcome email...")
        with app.app_context():
            mail.send(msg)
            print(f"✅ Welcome email отправлен на {email}")

            # Логируем успешную отправку
            if subscriber:
                log = EmailLog(
                    subscriber_id=subscriber.id,
                    email=email,
                    subject=_tr(lang, "welcome_subject"),
                    jobs_count=0,
                    status='sent',
                    sent_at=datetime.now()
                )
                db.session.add(log)
                db.session.commit()
                print("📝 Лог записан в базу")
            return True

    except Exception as e:
        print(f"❌ Ошибка отправки welcome email на {email}: {str(e)}")
        # Лог ошибки (без subscriber_id)
        try:
            with app.app_context():
                log = EmailLog(
                    email=email,
                    subject="welcome_failed",
                    jobs_count=0,
                    status='failed',
                    error_message=str(e),
                    sent_at=datetime.now()
                )
                db.session.add(log)
                db.session.commit()
        except Exception as log_error:
            print(f"❌ Ошибка записи лога: {log_error}")
        return False



def send_preferences_update_email(app, subscriber):
    """Отправка email об изменении предпочтений (локализовано)."""
    print(f"📧 send_preferences_update_email -> {subscriber.email}")

    try:
        lang = _get_lang(subscriber)
        base_url = os.getenv('BASE_URL', 'http://localhost:5000')
        manage_url = f"{base_url}/subscription/manage?email={subscriber.email}"

        # --- локализация профессий для шапки письма ---
        profs = subscriber.get_selected_jobs() or []
        profs_disp = ', '.join(_front_tr(lang, p) for p in profs[:3])


        html_content = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="utf-8">
            <style>
                body {{ font-family: Arial, sans-serif; margin: 0; padding: 20px; background-color: #f8f9fa; }}
                .container {{ max-width: 560px; margin: 0 auto; background: white; border-radius: 10px; overflow: hidden; }}
                .header {{ background: #28a745; color: white; padding: 20px; text-align: center; }}
                .content {{ padding: 20px; }}
                .muted {{ color:#6b7280; }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h2>{_tr(lang, "prefs_title")}</h2>
                </div>
                <div class="content">
                    <p>{_tr(lang, "prefs_intro")}</p>
                    <ul>
                        {f'<li><strong>{_tr(lang,"pref_professions")}:</strong> {profs_disp}{"..." if len(profs) > 3 else ""}</li>'}

                        <li><strong>{_tr(lang,"prefs_countries")}:</strong> {', '.join(subscriber.get_countries())}</li>
                        <li><strong>{_tr(lang,"prefs_city")}:</strong> {subscriber.city or _tr(lang,"prefs_city_none")}</li>
                        <li><strong>{_tr(lang,"prefs_frequency")}:</strong> {subscriber.frequency}</li>
                    </ul>
                    <p><a href="{manage_url}">{_tr(lang, "prefs_change_again")}</a></p>
                </div>
            </div>
        </body>
        </html>
        """

        msg = Message(
            subject=_tr(lang, "prefs_subject"),
            sender=os.getenv('MAIL_DEFAULT_SENDER'),
            recipients=[subscriber.email],
            html=html_content
        )

        with app.app_context():
            mail.send(msg)
            log = EmailLog(
                subscriber_id=subscriber.id,
                email=subscriber.email,
                subject=_tr(lang, "prefs_subject"),
                jobs_count=0,
                status='sent',
                sent_at=datetime.now()
            )
            db.session.add(log)
            db.session.commit()
            return True

    except Exception as e:
        print(f"❌ Ошибка отправки email об изменениях: {e}")
        import traceback
        traceback.print_exc()
        return False
