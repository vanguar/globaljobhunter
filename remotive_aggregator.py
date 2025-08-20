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
    
    # исправленный алиас для обратной совместимости
    def _query_remotive(self, terms, progress_callback=None, cancel_check=None):
        """
        Реальный запрос в Remotive: через _fetch_jobs.
        """
        params = {}
        if isinstance(terms, list):
            # если список — склеиваем в строку
            params['search'] = " ".join(terms)
        else:
            params['search'] = str(terms)

        return self._fetch_jobs(params)

    
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


    def get_supported_countries(self) -> Dict[str, Dict]:
        return {}

    def search_jobs(self, preferences: Dict, progress_callback=None, cancel_check=None) -> List[JobVacancy]:
        """
        Remotive: ищем ТОЛЬКО по выбранным профессиям.
        Нерелевантные (NON_REMOTE_JOBS) — пропускаем полностью.
        """
        all_jobs: List[JobVacancy] = []

        selected = preferences.get('selected_jobs') or []
        if not selected:
            return []

        # только удалённо пригодные профессии
        selected = [j for j in selected if j not in self.NON_REMOTE_JOBS]
        if not selected:
            print("ℹ️ Remotive: среди выбранных нет удалённых профессий")
            return []

        try:
            # для каждой выбранной профессии строим набор англ. термов
            for ru_title in selected:
                if cancel_check and cancel_check():
                    break

                terms = self._get_english_keywords(ru_title)
                if not terms:
                    continue

                # основной запрос Remotive — через параметр search / category
                jobs = self._query_remotive(terms, progress_callback=progress_callback, cancel_check=cancel_check)
                if jobs:
                    all_jobs.extend(jobs)

        except RateLimitedError:
            print(f"⛔ {self.source_name}: источник переведён в cooldown (429).")
        except Exception as e:
            print(f"❌ {self.source_name}: ошибка поиска — {e}")

        print(f"✅ {self.source_name}: Поиск завершен. Найдено всего: {len(all_jobs)} вакансий.")
        return self._deduplicate_jobs(all_jobs)


    def _get_english_keywords(self, russian_job_title: str) -> List[str]:
        for category in self.specific_jobs_map.values():
            jobs = category.get(russian_job_title)
            if jobs:
                # берём первые 8 наиболее характерных термов
                return [t for t in jobs if t][:8]
        return []


    def _fetch_jobs(self, params: Dict) -> List[JobVacancy]:
        """
        Один запрос к Remotive (с кешем).
        Возвращает list[JobVacancy]. При 429 бросает RateLimitedError.
        """
        # если уже в cooldown — не ходим
        now = time.time()
        if getattr(self, "cooldown_until", 0) > now:
            left = int(self.cooldown_until - now)
            print(f"⛔ {self.source_name}: cooldown ещё {left}s — пропускаем {params}.")
            raise RateLimitedError("REMOTIVE_COOLDOWN")

        # кеш по параметрам запроса
        cached = self.cache_manager.get_cached_result(params)
        if cached is not None:
            tag = params.get('search') or params.get('category')
            print(f"    💾 Cache HIT Remotive для '{tag}': {len(cached)}")
            return cached

        # локальный лимитер
        self.rate_limiter.wait_if_needed()

        tag = params.get('search') or params.get('category')
        try:
            r = requests.get(self.base_url, params=params, timeout=10)
            if r.status_code == 200:
                data = r.json() or {}
                jobs_raw = data.get('jobs') or []
                out: List[JobVacancy] = []
                for raw in jobs_raw:
                    j = self._normalize_job_data(raw, tag or "")
                    if j:
                        out.append(j)
                self.cache_manager.cache_result(params, out)
                print(f"    🌐 Remotive '{tag}': +{len(out)} (cached)")
                return out

            if r.status_code == 429:
                cooldown = int(os.getenv("REMOTIVE_COOLDOWN_SEC", "120"))
                self.cooldown_until = time.time() + cooldown
                print(f"⛔ Remotive 429 → cooldown {cooldown}s для '{tag}'")
                raise RateLimitedError("REMOTIVE_RATE_LIMIT")

            print(f"❌ {self.source_name} HTTP {r.status_code}: {r.text[:200]}")
            return []

        except requests.Timeout:
            print(f"⚠️ {self.source_name}: таймаут запроса для '{tag}'")
            return []
        except RateLimitedError:
            raise
        except Exception as e:
            print(f"❌ {self.source_name}: ошибка запроса '{tag}': {e}")
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