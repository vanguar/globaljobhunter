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

    def search_jobs(self, preferences: Dict, progress_callback=None, cancel_check=None) -> List[JobVacancy]:
        """
        Remotive: быстрый режим.
        - Поддержка progress_callback(list[JobVacancy]) — отдаём батчи.
        - Поддержка cancel_check() — мягкая остановка.
        - Общий тайм-бюджет на источник (по умолчанию 20с, можно менять REMOTIVE_MAX_RUNTIME).
        """
        print(f"📡 {self.source_name}: Начинаем поиск удалённых вакансий...")
        all_jobs: List[JobVacancy] = []

        selected_jobs = preferences.get('selected_jobs', [])
        if not selected_jobs:
            return []

        # общий бюджет времени на Remotive
        MAX_RUNTIME_SEC = int(os.getenv("REMOTIVE_MAX_RUNTIME", "20"))
        started_at = time.time()

        for russian_job_title in selected_jobs:
            if cancel_check and cancel_check():
                return self._deduplicate_jobs(all_jobs)
            if time.time() - started_at > MAX_RUNTIME_SEC:
                print(f"⏳ {self.source_name}: превышен тайм-бюджет {MAX_RUNTIME_SEC}s — прерываем оставшиеся запросы")
                break

            # Игнорируем явные «не-удалённые» профессии
            if russian_job_title in self.NON_REMOTE_JOBS:
                print(f"    - Пропускаем '{russian_job_title}' (не remote)")
                continue

            english_keywords = self._get_english_keywords(russian_job_title)
            if not english_keywords:
                continue

            primary_keyword = english_keywords[0]
            category = self.job_to_category_map.get(primary_keyword.lower())

            if category:
                print(f"    - Ищем по категории '{category}' для '{russian_job_title}'")
                jobs = self._fetch_jobs(
                    params={'category': category},
                    progress_callback=progress_callback,
                    cancel_check=cancel_check,
                    started_at=started_at,
                    max_runtime_sec=MAX_RUNTIME_SEC
                )
            else:
                search_query = " ".join(english_keywords)
                print(f"    - Ищем по ключевым словам: '{search_query}'")
                jobs = self._fetch_jobs(
                    params={'search': search_query},
                    progress_callback=progress_callback,
                    cancel_check=cancel_check,
                    started_at=started_at,
                    max_runtime_sec=MAX_RUNTIME_SEC
                )

            if jobs:
                all_jobs.extend(jobs)

            if cancel_check and cancel_check():
                return self._deduplicate_jobs(all_jobs)

        print(f"✅ {self.source_name}: Поиск завершён. Найдено всего: {len(all_jobs)}.")
        return self._deduplicate_jobs(all_jobs)




    def _get_english_keywords(self, russian_job_title: str) -> List[str]:
        for category in self.specific_jobs_map.values():
            if russian_job_title in category:
                return [term for term in category[russian_job_title][:3] if term]
        return []

    def _fetch_jobs(
    self,
    params: Dict,
    progress_callback=None,
    cancel_check=None,
    started_at: float = None,
    max_runtime_sec: int = 20
) -> List[JobVacancy]:
        """
        Один запрос к API Remotive (быстрый режим):
        - Cache → отдать батч.
        - Короткий HTTP-таймаут.
        - 429/timeout: микропауза 150–400мс и сразу дальше (без долгих ожиданий и ретраев).
        """
        if cancel_check and cancel_check():
            return []
        if started_at and (time.time() - started_at > max_runtime_sec):
            return []

        # 0) кеш
        cached_result = self.cache_manager.get_cached_result(params)
        if cached_result:
            tag = params.get('search') or params.get('category')
            print(f"    - Cache HIT для '{tag}'. Найдено: {len(cached_result)}.")
            if progress_callback and cached_result:
                try:
                    progress_callback(cached_result)
                except Exception:
                    pass
            return cached_result

        # 1) кооперативный "лимитер" (у тебя он уже быстрый)
        ok = self.rate_limiter.wait_if_needed(cancel_check=cancel_check)
        if ok is False or (cancel_check and cancel_check()):
            return []
        if started_at and (time.time() - started_at > max_runtime_sec):
            return []

        HTTP_TIMEOUT = int(os.getenv("REMOTIVE_HTTP_TIMEOUT", "6"))

        try:
            response = requests.get(self.base_url, params=params, timeout=HTTP_TIMEOUT)
            if response.status_code == 200:
                data = response.json()
                jobs_raw = data.get('jobs', [])
                tag = params.get('search') or params.get('category')

                normalized_jobs: List[JobVacancy] = []
                for job_data in jobs_raw:
                    if cancel_check and cancel_check():
                        break
                    job = self._normalize_job_data(job_data, tag)
                    if job:
                        normalized_jobs.append(job)

                self.cache_manager.cache_result(params, normalized_jobs)
                print(f"    - Найдено и закешировано: {len(normalized_jobs)} для '{tag}'.")

                if progress_callback and normalized_jobs:
                    try:
                        progress_callback(normalized_jobs)
                    except Exception:
                        pass

                return normalized_jobs

            if response.status_code == 429:
                tag = params.get('search') or params.get('category')
                backoff_ms = 200 + random.randint(0, 200)  # 200–400мс
                print(f"⛔ Remotive: 429 Too Many Requests — микропауза {backoff_ms} мс для '{tag}' и двигаемся дальше")
                yield_briefly(base_ms=backoff_ms, jitter_ms=0, cancel_check=cancel_check)
                return []

            print(f"❌ {self.source_name} API ошибка {response.status_code}: {response.text[:200]}")
            return []

        except requests.Timeout:
            tag = params.get('search') or params.get('category')
            backoff_ms = 150 + random.randint(0, 200)  # 150–350мс
            print(f"⚠️ {self.source_name}: таймаут для '{tag}' — микропауза {backoff_ms} мс и дальше")
            yield_briefly(base_ms=backoff_ms, jitter_ms=0, cancel_check=cancel_check)
            return []
        except Exception as e:
            print(f"❌ {self.source_name}: критическая ошибка: {e}")
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