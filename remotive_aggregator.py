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

    def __init__(self, specific_jobs_map: Dict, cache_duration_hours: int = 12):
        """
        Инициализация агрегатора.
        """
        
        super().__init__(source_name='Remotive')
        self.cooldown_until = 0
        self.base_url = "https://remotive.com/api/remote-jobs"
        self.specific_jobs_map = specific_jobs_map
        self.cache_manager = CacheManager(cache_duration_hours=cache_duration_hours)
        self.rate_limiter = RateLimiter(requests_per_minute=2) 

        self.job_to_category_map = {
            'python developer': 'software-dev', 'web developer': 'software-dev',
            'programmer': 'software-dev', 'software developer': 'software-dev',
            'qa engineer': 'qa', 'software tester': 'qa', 'data analyst': 'data',
            'data scientist': 'data', 'designer': 'design', 'product manager': 'product',
            'manager': 'management', 'sales assistant': 'sales-marketing',
            'marketer': 'sales-marketing', 'recruiter': 'hr',
            'customer support': 'customer-service'
        }
        print(f"✅ Remotive Aggregator v1.3 инициализирован (Rate Limit: 2/min, с фильтром профессий).")

    def get_supported_countries(self) -> Dict[str, Dict]:
        return {}

    def search_jobs(self, preferences: Dict) -> List[JobVacancy]:
        """Remotive с circuit breaker: при 429 выключаем источник и идём дальше."""
        print(f"📡 {self.source_name}: Начинаем поиск удаленных вакансий...")
        all_jobs: List[JobVacancy] = []

        # если источник в cooldown — пропускаем
        now = time.time()
        if getattr(self, "cooldown_until", 0) > now:
            left = int(self.cooldown_until - now)
            print(f"⛔ {self.source_name}: на cooldown ещё {left}s — пропускаем источник.")
            return []

        selected_jobs = preferences.get('selected_jobs', [])
        if not selected_jobs:
            return []

        try:
            for russian_job_title in selected_jobs:
                # чёрный список «не remote» как у тебя было
                if russian_job_title in self.NON_REMOTE_JOBS:
                    print(f"    - Пропускаем '{russian_job_title}', т.к. не является удаленной.")
                    continue

                english_keywords = self._get_english_keywords(russian_job_title)
                if not english_keywords:
                    continue

                primary_keyword = english_keywords[0]
                category = self.job_to_category_map.get(primary_keyword.lower())

                if category:
                    print(f"    - Ищем по категории '{category}' для '{russian_job_title}'")
                    jobs = self._fetch_jobs(params={'category': category})
                    all_jobs.extend(jobs)
                else:
                    search_query = " ".join(english_keywords)
                    print(f"    - Ищем по ключевым словам: '{search_query}'")
                    jobs = self._fetch_jobs(params={'search': search_query})
                    all_jobs.extend(jobs)

        except RateLimitedError:
            print(f"⛔ {self.source_name}: источник переведён в cooldown — завершаем Remotive.")

        print(f"✅ {self.source_name}: Поиск завершен. Найдено всего: {len(all_jobs)} вакансий.")
        return self._deduplicate_jobs(all_jobs)





    def _get_english_keywords(self, russian_job_title: str) -> List[str]:
        for category in self.specific_jobs_map.values():
            if russian_job_title in category:
                return [term for term in category[russian_job_title][:3] if term]
        return []

    def _fetch_jobs(self, params: Dict) -> List[JobVacancy]:
    # если уже в cooldown — не ходим
        now = time.time()
        if getattr(self, "cooldown_until", 0) > now:
            left = int(self.cooldown_until - now)
            print(f"⛔ {self.source_name}: cooldown ещё {left}s — пропускаем запрос {params}.")
            raise RateLimitedError("REMOTIVE_COOLDOWN")

        # КЕШ
        cached_result = self.cache_manager.get_cached_result(params)
        if cached_result:
            search_term_log = params.get('search') or params.get('category')
            print(f"    - Cache HIT для '{search_term_log}'. Найдено: {len(cached_result)}.")
            return cached_result

        # твой локальный лимитер
        self.rate_limiter.wait_if_needed()

        try:
            response = requests.get(self.base_url, params=params, timeout=8)
            if response.status_code == 200:
                data = response.json()
                jobs_raw = data.get('jobs', [])

                search_term = params.get('search') or params.get('category')
                normalized_jobs = [
                    job for job_data in jobs_raw
                    if (job := self._normalize_job_data(job_data, search_term)) is not None
                ]

                self.cache_manager.cache_result(params, normalized_jobs)
                print(f"    - Найдено и закешировано: {len(normalized_jobs)} вакансий для '{search_term}'.")
                return normalized_jobs

            if response.status_code == 429:
                cooldown = int(os.getenv("REMOTIVE_COOLDOWN_SEC", "120"))
                self.cooldown_until = time.time() + cooldown
                tag = params.get('search') or params.get('category')
                print(f"⛔ Remotive: 429 Too Many Requests — включаем cooldown {cooldown}s для '{tag}' и выходим из источника")
                yield_briefly(base_ms=200, jitter_ms=200)
                raise RateLimitedError("REMOTIVE_RATE_LIMITED")

            print(f"❌ {self.source_name} API ошибка {response.status_code}: {response.text[:200]}")
            return []

        except requests.Timeout:
            print(f"⚠️ {self.source_name}: Таймаут запроса для '{params}'.")
            return []
        except RateLimitedError:
            raise
        except Exception as e:
            print(f"❌ {self.source_name}: Критическая ошибка при запросе: {e}")
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