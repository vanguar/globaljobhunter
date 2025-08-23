#!/usr/bin/env python3
"""
Remotive Aggregator for GlobalJobHunter v1.3
"""

import os
import requests
import time
from datetime import datetime
from typing import List, Dict, Optional
import hashlib
import re


# --- Переиспользуемые компоненты из adzuna_aggregator ---
from adzuna_aggregator import JobVacancy, CacheManager, RateLimiter

# --- Базовый класс для соблюдения архитектуры ---
from base_aggregator import BaseJobAggregator

try:
    from adzuna_aggregator import RateLimitedError, yield_briefly
except Exception:
    class RateLimitedError(Exception):
        pass
    import random, time
    def yield_briefly(base_ms: int = 200, jitter_ms: int = 120, cancel_check=None) -> bool:
        delay = (base_ms + (random.randint(0, jitter_ms) if jitter_ms > 0 else 0)) / 1000.0
        end = time.time() + delay
        while True:
            remain = end - time.time()
            if remain <= 0:
                break
            time.sleep(min(0.05, remain))
        return True


class RemotiveAggregator(BaseJobAggregator):
    """
    Агрегатор для поиска удаленных вакансий через Remotive API.
    - УЛУЧШЕНО: Добавлен черный список профессий, которые не могут быть удаленными.
    - ИСПРАВЛЕНО: Объединение ключевых слов в один запрос для избежания Rate Limit.
    - Улучшено: Использует поиск по категориям и исправлен Rate Limiter.
    """
    
    # --- НОВОЕ: Список профессий, которые не ищем на этом сайте ---
    NON_REMOTE_JOBS = {
        # Транспорт и доставка
        'Водитель такси', 'Водитель категории B', 'Водитель категории C',
        'Водитель-курьер', 'Курьер пешком', 'Курьер-доставщик еды',
        'Водитель автобуса', 'Водитель грузовика',
        # Автосервис
        'Автомеханик', 'Автослесарь', 'Шиномонтажник', 'Диагност',
        'Мастер-приёмщик', 'Кузовщик', 'Маляр по авто',
        # АЗС и Топливо
        'Заправщик на АЗС', 'Оператор АЗС', 'Кассир на АЗС',
        # Нефть и газ
        'Оператор добычи', 'Помощник бурильщика', 'Рабочий нефтебазы',
        # Строительство и производство
        'Строитель-разнорабочий', 'Грузчик', 'Складской работник',
        'Разнорабочий', 'Рабочий на производстве',
        # Общепит и сервис
        'Официант', 'Бармен', 'Повар', 'Помощник повара', 'Посудомойщик',
        'Кассир', 'Продавец',
        # Сервис и обслуживание
        'Уборщик', 'Садовник', 'Домработница', 'Массажист',
        # Уход и медицина (требующие физического присутствия)
        'Медсестра', 'Сиделка', 'Няня', 'Гувернантка', 'Уход за пенсионерами'
    }
    
    def _get_english_keywords(self, text: str) -> str:
        """
        Back-compat: раньше вызывался этот приватный метод.
        Сейчас просто возвращаем text как есть (или нормализуем, если есть хелпер).
        """
        # Если есть уже существующий нормализатор — используй его:
        # return self._normalize_keywords(text)
        return text

    # 2) Запрос в Remotive: безопасный батчинг + возможность принудить свежий запрос
    def _query_remotive(self, terms_or_params, progress_callback=None, cancel_check=None, fresh: bool = False) -> List[JobVacancy]:
        """
        Универсальная обёртка:
        • dict с {'category': slug} → один запрос по категории.
        • list/tuple/str → запрос(ы) по search с батчингом 3–4 термина / <=80 символов.
        Внутри зовём _fetch_jobs(..., max_retries=2).
        """
        def _run_one(params: Dict) -> List[JobVacancy]:
            jobs = self._fetch_jobs(params, fresh=fresh, max_retries=2)
            if jobs and progress_callback:
                try:
                    progress_callback(list(jobs))
                except Exception:
                    pass
            return jobs or []

        # Ветка категории
        if isinstance(terms_or_params, dict) and terms_or_params.get("category"):
            return _run_one({"category": terms_or_params["category"]})

        # Ветка search
        if isinstance(terms_or_params, (list, tuple)):
            cleaned = [str(t).strip() for t in terms_or_params if str(t).strip()]
        else:
            cleaned = [str(terms_or_params or "").strip()] if str(terms_or_params or "").strip() else []

        if not cleaned:
            return []

        results: List[JobVacancy] = []
        batch: List[str] = []
        curr_len = 0
        MAX_TERMS = 4
        MAX_LEN = 80

        for t in cleaned:
            add_len = (1 if batch else 0) + len(t)
            if len(batch) >= MAX_TERMS or (curr_len + add_len) > MAX_LEN:
                results.extend(_run_one({'search': " ".join(batch)}))
                batch, curr_len = [t], len(t)
            else:
                batch.append(t)
                curr_len += add_len

        if batch:
            results.extend(_run_one({'search': " ".join(batch)}))

        return results

    
    def __init__(self, specific_jobs_map: Dict, cache_duration_hours: Optional[int] = None):
        """
        Инициализация Remotive.
        TTL: REMOTIVE_CACHE_HOURS > CACHE_TTL_HOURS > 24 (по умолчанию).
        """
        super().__init__(source_name='Remotive')
        self.cooldown_until = 0
        self.base_url = "https://remotive.com/api/remote-jobs"
        self.specific_jobs_map = specific_jobs_map

        # TTL кеша (часы)
        if cache_duration_hours is None:
            try:
                cache_duration_hours = int(os.getenv('REMOTIVE_CACHE_HOURS', os.getenv('CACHE_TTL_HOURS', '24')))
            except Exception:
                cache_duration_hours = 24

        self.cache_manager = CacheManager(cache_duration_hours=cache_duration_hours)
        self.rate_limiter = RateLimiter(requests_per_minute=2)

        # Маппинг популярных ключей → категорий Remotive
        self.job_to_category_map = {
            'python developer': 'software-dev',
            'web developer': 'software-dev',
            'programmer': 'software-dev',
            'software developer': 'software-dev',
            'qa engineer': 'qa',
            'software tester': 'qa',
            'data analyst': 'data',
            'data scientist': 'data',
            'designer': 'design',
            'product manager': 'product',
            'manager': 'management',
            'sales assistant': 'sales-marketing',
            'marketer': 'sales-marketing',
            'recruiter': 'hr',
            'customer support': 'customer-service'
        }

        print(f"✅ Remotive Aggregator инициализирован (TTL={cache_duration_hours}ч, RL=2/min).")

    def _guess_category_slug(self, ru_titles: List[str]) -> Optional[str]:
        """
        Пробуем угадать slug категории Remotive по выбранным RU-профессиям.
        Если не уверены — вернём None (тогда используем search).
        """
        text = " ".join(ru_titles).lower()

        # базовые соответствия (можешь дополнять при желании)
        m = {
            "software-dev":  ["разработ", "программист", "developer", "инженер по ПО", "qa", "тестиров"],
            "data":          ["аналитик", "data", "данн", "scientist"],
            "design":        ["дизайн", "ui", "ux", "product designer"],
            "product":       ["продакт", "product manager", "продукт"],
            "management":    ["менеджер", "руковод", "project", "team lead", "координатор", "администратор"],
            "sales-marketing":["маркет", "smm", "seo", "контент", "продаж", "sales", "marketing"],
            "hr":            ["hr", "рекрутер", "кадров", "talent"],
            "customer-service":["поддержк", "саппорт", "support", "customer"],
            "devops":        ["devops", "sre", "админ", "инфра"],
            "finance-legal": ["бухгалт", "финанс", "юрист", "legal"],
            "writing":       ["копирайт", "writer", "редактор", "контентмейкер"],
            "education":     ["учител", "преподав", "education", "coach", "тренер"],
            "sales":         ["sales", "аккаунт", "account"],
        }

        for slug, cues in m.items():
            if any(cue in text for cue in cues):
                return slug

        return None
        


    def get_supported_countries(self) -> Dict[str, Dict]:
        return {}

    def search_jobs(self, preferences: Dict, progress_callback=None, cancel_check=None) -> List[JobVacancy]:
        """
        Стратегия (по доке Remotive):
        1) Если можем угадать slug категории — сначала пробуем ?category=slug.
        2) Если мало/пусто — fallback на ?search=... (EN-ключи).
        3) Непустой кеш уважаем; пустой не цементируем. Есть ретраи.
        """
        all_jobs: List[JobVacancy] = []

        selected = preferences.get('selected_jobs') or []
        if not selected:
            return []

        # МЯГКАЯ фильтрация офлайн‑ролей (не обнуляем совсем)
        initial_count = len(selected)
        filtered = [j for j in selected if j not in self.NON_REMOTE_JOBS]
        if not filtered:
            print(f"ℹ️ Remotive: все {initial_count} выбранных профессий помечены как офлайн — всё же пробуем по ним (fallback).")
            filtered = selected
        else:
            dropped = set(selected) - set(filtered)
            if dropped:
                print(f"ℹ️ Remotive: исключил офлайн‑списки: {', '.join(dropped)}")
        selected = filtered

        try:
            # 1) Попытка через категорию (slug) — ОДИН запрос даёт много релевантного
            slug = self._guess_category_slug(selected)
            cat_jobs: List[JobVacancy] = []
            if slug:
                cat_jobs = self._query_remotive({"category": slug}, progress_callback=progress_callback, cancel_check=cancel_check)
                # _query_remotive понимает и dict params (category), и list/str terms

            # 2) Если по категории пусто/мало — дополнительно пробуем точечные search‑запросы
            if cancel_check and cancel_check():
                return self._deduplicate_jobs(cat_jobs)

            search_jobs_total: List[JobVacancy] = []
            if len(cat_jobs) < 10:  # порог можно подвинуть
                for ru_title in selected:
                    if cancel_check and cancel_check():
                        break
                    terms = self._get_english_keywords(ru_title)
                    if not terms:
                        continue
                    # аккуратный батчинг и ретраи — внутри _query_remotive
                    search_jobs_total.extend(
                        self._query_remotive(terms, progress_callback=progress_callback, cancel_check=cancel_check)
                    )

            all_jobs.extend(cat_jobs)
            all_jobs.extend(search_jobs_total)

        except RateLimitedError:
            print(f"⛔ {self.source_name}: источник переведён в cooldown (429).")
        except Exception as e:
            print(f"❌ {self.source_name}: ошибка поиска — {e}")

        deduped = self._deduplicate_jobs(all_jobs)
        print(f"✅ {self.source_name}: Поиск завершен. Найдено всего: {len(deduped)} вакансий.")
        return deduped

    # 3) Кеш: уважаем непустой кеш; пустой кеш не возвращаем и не сохраняем
    def _fetch_jobs(self, params: Dict, fresh: bool = False, max_retries: int = 2) -> List[JobVacancy]:
        """
        Один запрос к Remotive (с кешем + повторы).
        Кеш:
        • fresh=True → игнорировать чтение кеша (но писать можно).
        • непустой кеш → возвращаем.
        • пустой кеш → НЕ возвращаем, идём в API.
        • пустой ответ из API НЕ кешируем.
        Повторы:
        • таймаут/сетевая/5xx → retry с лёгким джиттером.
        • 429 → cooldown и исключение.
        """
        now = time.time()
        if getattr(self, "cooldown_until", 0) > now:
            left = int(self.cooldown_until - now)
            print(f"⛔ {self.source_name}: cooldown ещё {left}s — пропускаем {params}.")
            raise RateLimitedError("REMOTIVE_COOLDOWN")

        tag = params.get('search') or params.get('category')

        if not fresh:
            cached = self.cache_manager.get_cached_result(params)
            if cached is not None:
                if cached:
                    print(f"    💾 Cache HIT Remotive для '{tag}': {len(cached)}")
                    return cached
                else:
                    print(f"    💾 Cache HIT Remotive (empty) для '{tag}', пробуем API...")

        attempts = 1 + max(0, int(max_retries))
        last_err = None

        for attempt in range(1, attempts + 1):
            self.rate_limiter.wait_if_needed()
            try:
                r = requests.get(self.base_url, params=params, timeout=12)
                if r.status_code == 200:
                    data = r.json() or {}
                    jobs_raw = data.get('jobs') or []
                    out: List[JobVacancy] = []
                    for raw in jobs_raw:
                        j = self._normalize_job_data(raw, tag or "")
                        if j:
                            out.append(j)

                    if out:
                        self.cache_manager.cache_result(params, out)
                        print(f"    🌐 Remotive '{tag}': +{len(out)} (cached)")
                    else:
                        print(f"    🌐 Remotive '{tag}': +0 (not cached)")
                    return out

                if r.status_code == 429:
                    cooldown = int(os.getenv("REMOTIVE_COOLDOWN_SEC", "120"))
                    self.cooldown_until = time.time() + cooldown
                    print(f"⛔ Remotive 429 → cooldown {cooldown}s для '{tag}'")
                    raise RateLimitedError("REMOTIVE_RATE_LIMIT")

                if 500 <= r.status_code <= 599:
                    last_err = RuntimeError(f"HTTP {r.status_code}")
                    print(f"⚠️ {self.source_name}: HTTP {r.status_code} для '{tag}', попытка {attempt}/{attempts}")
                    if attempt < attempts:
                        yield_briefly(300, 300)
                        continue
                    return []

                print(f"❌ {self.source_name} HTTP {r.status_code}: {r.text[:200]}")
                return []

            except requests.Timeout as e:
                last_err = e
                print(f"⚠️ {self.source_name}: таймаут запроса для '{tag}', попытка {attempt}/{attempts}")
                if attempt < attempts:
                    yield_briefly(300, 300)
                    continue
                return []
            except requests.RequestException as e:
                last_err = e
                print(f"⚠️ {self.source_name}: сетевая ошибка для '{tag}': {e}, попытка {attempt}/{attempts}")
                if attempt < attempts:
                    yield_briefly(300, 300)
                    continue
                return []
            except RateLimitedError:
                raise
            except Exception as e:
                last_err = e
                print(f"❌ {self.source_name}: ошибка запроса '{tag}': {e}")
                return []

        if last_err:
            print(f"❌ {self.source_name}: исчерпаны попытки для '{tag}': {last_err}")
        return []



    def _normalize_job_data(self, raw_job: Dict, search_term: str) -> Optional[JobVacancy]:
        try:
            title = raw_job.get('title', '')
            description = raw_job.get('description', '')
            
            url = raw_job.get('url')
            if not url:
                return None
            job_id = hashlib.md5(url.encode()).hexdigest()

            date_str = raw_job.get('publication_date', '')
            try:
                posted_date = datetime.fromisoformat(date_str.replace('Z', '+00:00')).strftime('%Y-%m-%d')
            except (ValueError, TypeError):
                posted_date = datetime.now().strftime('%Y-%m-%d')

            return JobVacancy(
                id=f"remotive_{job_id}",
                title=title,
                company=raw_job.get('company_name', 'Not specified'),
                location=raw_job.get('candidate_required_location', 'Worldwide'),
                salary=raw_job.get('salary'),
                description=description,
                apply_url=url,
                source=self.source_name,
                posted_date=posted_date,
                country='Remote',
                job_type=raw_job.get('job_type'),
                language_requirement=self.determine_language_requirement(title, description),
                refugee_friendly=self.is_refugee_friendly(title, description, search_term)
            )
        except Exception as e:
            print(f"⚠️ {self.source_name}: Ошибка нормализации вакансии: {e}")
            return None

    def is_relevant_job(self, job_title: str, job_description: str, search_term: str) -> bool:
        """Простая проверка на релевантность."""
        if search_term in self.job_to_category_map.values():
             return True
        
        search_keywords = search_term.lower().split()
        title_lower = job_title.lower()
        return any(keyword in title_lower for keyword in search_keywords)

    def _deduplicate_jobs(self, jobs: List[JobVacancy]) -> List[JobVacancy]:
        """Удаление дубликатов по URL вакансии."""
        seen = set()
        unique_jobs = []
        for job in jobs:
            if job.apply_url not in seen:
                seen.add(job.apply_url)
                unique_jobs.append(job)
        return unique_jobs