#!/usr/bin/env python3
"""
Remotive Aggregator for GlobalJobHunter v1.1
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
    - Улучшено: Использует поиск по категориям и исправлен Rate Limiter.
    """
    def __init__(self, specific_jobs_map: Dict, cache_duration_hours: int = 12):
        """
        Инициализация агрегатора.
        :param specific_jobs_map: Словарь для перевода русских названий профессий в английские.
        :param cache_duration_hours: Время жизни кеша в часах.
        """
        super().__init__(source_name='Remotive')
        self.base_url = "https://remotive.com/api/remote-jobs"
        self.specific_jobs_map = specific_jobs_map
        self.cache_manager = CacheManager(cache_duration_hours=cache_duration_hours)
        # ИСПРАВЛЕНО: Устанавливаем лимит в 2 запроса в минуту согласно документации
        self.rate_limiter = RateLimiter(requests_per_minute=2) 

        # Карта категорий для Remotive API (можно дополнять)
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
        print(f"✅ Remotive Aggregator v1.1 инициализирован (Rate Limit: 2/min).")

    def get_supported_countries(self) -> Dict[str, Dict]:
        """Remotive - это только удаленные вакансии, поэтому список стран пуст."""
        return {}

    def search_jobs(self, preferences: Dict) -> List[JobVacancy]:
        """
        Основной метод поиска. Выполняет поиск для каждой выбранной профессии.
        """
        print(f"📡 {self.source_name}: Начинаем поиск удаленных вакансий...")
        all_jobs: List[JobVacancy] = []
        
        selected_jobs = preferences.get('selected_jobs', [])

        if not selected_jobs:
            return []

        for russian_job_title in selected_jobs:
            english_keywords = self._get_english_keywords(russian_job_title)
            
            if not english_keywords:
                continue

            # Пробуем найти по категории для первого ключевого слова
            primary_keyword = english_keywords[0]
            category = self.job_to_category_map.get(primary_keyword.lower())
            
            if category:
                print(f"    - Ищем по категории '{category}' для '{russian_job_title}'")
                jobs = self._fetch_jobs(params={'category': category})
                all_jobs.extend(jobs)
            else:
                # Если категории нет, ищем по ключевым словам
                for keyword in english_keywords:
                    print(f"    - Ищем по ключевому слову: '{keyword}'")
                    jobs = self._fetch_jobs(params={'search': keyword})
                    all_jobs.extend(jobs)
        
        print(f"✅ {self.source_name}: Поиск завершен. Найдено всего: {len(all_jobs)} вакансий.")
        return self._deduplicate_jobs(all_jobs)

    def _get_english_keywords(self, russian_job_title: str) -> List[str]:
        """Извлекает английские ключевые слова для русской профессии."""
        for category in self.specific_jobs_map.values():
            if russian_job_title in category:
                return [term for term in category[russian_job_title][:3] if term]
        return []

    def _fetch_jobs(self, params: Dict) -> List[JobVacancy]:
        """Получает вакансии по заданным параметрам с кешированием."""
        cached_result = self.cache_manager.get_cached_result(params)
        if cached_result:
            return cached_result

        self.rate_limiter.wait_if_needed()
        
        try:
            response = requests.get(self.base_url, params=params, timeout=15)
            
            if response.status_code != 200:
                print(f"❌ {self.source_name} API ошибка {response.status_code}: {response.text}")
                return []

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

        except requests.Timeout:
            print(f"⚠️ {self.source_name}: Таймаут запроса для '{params}'.")
            return []
        except Exception as e:
            print(f"❌ {self.source_name}: Критическая ошибка при запросе: {e}")
            return []

    def _normalize_job_data(self, raw_job: Dict, search_term: str) -> Optional[JobVacancy]:
        """
        Преобразует сырые данные от API в стандартизированный объект JobVacancy.
        """
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
        # Для категорий не нужна дополнительная проверка, т.к. они уже релевантны
        if search_term in self.job_to_category_map.values():
             return True
        return search_term.lower() in job_title.lower()

    def _deduplicate_jobs(self, jobs: List[JobVacancy]) -> List[JobVacancy]:
        """Удаление дубликатов по URL вакансии."""
        seen = set()
        unique_jobs = []
        for job in jobs:
            if job.apply_url not in seen:
                seen.add(job.apply_url)
                unique_jobs.append(job)
        return unique_jobs
