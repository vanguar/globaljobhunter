#!/usr/bin/env python3
"""
Careerjet Aggregator for GlobalJobHunter
"""

import os
import requests
import time
from datetime import datetime
from typing import List, Dict, Optional
from dataclasses import asdict
import hashlib
from dotenv import load_dotenv

# --- Переиспользуемые компоненты из adzuna_aggregator ---
from adzuna_aggregator import JobVacancy, CacheManager, RateLimiter, GlobalJobAggregator

# --- Базовый класс для соблюдения архитектуры ---
from base_aggregator import BaseJobAggregator

# Загружаем переменные окружения из .env файла
load_dotenv()

class CareerjetAggregator(BaseJobAggregator):
    """
    Агрегатор для поиска вакансий через Careerjet API.
    - Поддерживает поиск как по стране, так и по городу.
    - **Новая логика:** Выполняет отдельные запросы для каждой профессии для большей точности.
    """
    def __init__(self, adzuna_countries: Dict, specific_jobs_map: Dict, cache_duration_hours: int = 12):
        """
        Инициализация агрегатора.
        """
        super().__init__(source_name='Careerjet')
        self.base_url = "http://public.api.careerjet.net/search"
        
        self.affid = os.getenv('CAREERJET_AFFID')
        if not self.affid:
            raise ValueError("CAREERJET_AFFID не найден в .env файле!")

        self.cache_manager = CacheManager(cache_duration_hours=cache_duration_hours)
        self.rate_limiter = RateLimiter(requests_per_minute=25)
        
        self.country_map = {
            'gb': 'United Kingdom', 'us': 'United States', 'de': 'Germany',
            'fr': 'France', 'es': 'Spain', 'it': 'Italy', 'nl': 'Netherlands',
            'pl': 'Poland', 'ca': 'Canada', 'au': 'Australia', 'at': 'Austria',
            'ch': 'Switzerland', 'be': 'Belgium', 'se': 'Sweden', 'no': 'Norway',
            'dk': 'Denmark', 'cz': 'Czech Republic', 'sk': 'Slovakia'
        }

        self.adzuna_countries = adzuna_countries
        self.specific_jobs_map = specific_jobs_map

        print(f"✅ Careerjet Aggregator инициализирован (affid: ...{self.affid[-4:]})")

    def get_supported_countries(self) -> Dict[str, Dict]:
        """Возвращает словарь стран, поддерживаемых этим агрегатором."""
        return {}

    def search_jobs(self, preferences: Dict, progress_callback=None, cancel_check=None) -> List[JobVacancy]:
        """Ищем по каждой выбранной профессии/стране/городу. Прогресс и отмена поддерживаются."""
        print(f"📡 {self.source_name}: начинаем поиск...")
        all_jobs: List[JobVacancy] = []

        selected_jobs = preferences.get('selected_jobs', [])
        countries = preferences.get('countries', [])
        cities = preferences.get('cities', [])

        if not selected_jobs or not countries:
            return []

        for russian_job_title in selected_jobs:
            english_keywords = self._get_english_keywords(russian_job_title)
            if not english_keywords:
                print(f"⚠️ {self.source_name}: нет словаря для '{russian_job_title}', пропускаем")
                continue

            keywords = " ".join(sorted(set(english_keywords)))
            print(f"ℹ️ {self.source_name}: '{russian_job_title}' → '{keywords}'")

            for country_code in countries:
                country_name_for_api = self.country_map.get(country_code)
                if not country_name_for_api:
                    continue

                if cities:
                    for city in cities:
                        search_location = f"{city}, {country_name_for_api}"
                        jobs = self._fetch_all_pages(keywords, search_location, country_code, progress_callback=progress_callback, cancel_check=cancel_check)
                        if jobs:
                            all_jobs.extend(jobs)
                else:
                    search_location = country_name_for_api
                    jobs = self._fetch_all_pages(keywords, search_location, country_code, progress_callback=progress_callback, cancel_check=cancel_check)
                    if jobs:
                        all_jobs.extend(jobs)

        print(f"✅ {self.source_name}: завершено. Всего: {len(all_jobs)}")
        return self._deduplicate_jobs(all_jobs)



    def _fetch_all_pages(self, keywords: str, location: str, country_code: str, progress_callback=None, cancel_check=None) -> List[JobVacancy]:
        """Получает вакансии со всех страниц пагинации, отдавая прогресс порциями."""
        page = 1
        total_jobs: List[JobVacancy] = []

        while True:
            if cancel_check and cancel_check():
                break

            search_params = {
                'affid': self.affid,
                'keywords': keywords,
                'location': location,
                'page': page,
                'sort': 'date',
                'user_ip': '127.0.0.1',
            }

            try:
                response = requests.get(self.base_url, params=search_params, timeout=15)
            except Exception as e:
                print(f"❌ {self.source_name}: ошибка запроса: {e}")
                break

            try:
                data = response.json()
            except Exception:
                data = {}

            if data.get('type') == 'ERROR':
                print(f"❌ {self.source_name} API вернуло ошибку: {data.get('error')}")
                break

            jobs_on_page_raw = (data or {}).get('jobs', []) or []
            if not jobs_on_page_raw:
                break

            normalized_jobs: List[JobVacancy] = []
            for job_data in jobs_on_page_raw:
                country_name = self._get_country_name_by_code(country_code)
                job = self._normalize_job_data(job_data, country_name, keywords)
                if job:
                    normalized_jobs.append(job)

            total_jobs.extend(normalized_jobs)

            # Кладём порцию в кеш и пушим прогресс на UI
            cache_key_params = {'keywords': keywords, 'location': location, 'country_code': country_code, 'page': page}
            self.cache_manager.cache_result(cache_key_params, normalized_jobs)
            print(f"📄 {self.source_name}: {location} — стр. {page}, найдено: {len(normalized_jobs)}")

            if progress_callback and normalized_jobs:
                try:
                    progress_callback(normalized_jobs)
                except Exception:
                    pass

            # Пагинация
            if len(jobs_on_page_raw) < (data.get('pagesize') or 50):
                break
            page += 1
            time.sleep(0.3)

        return total_jobs



    def _normalize_job_data(self, raw_job: Dict, country_name: str, search_term: str) -> Optional[JobVacancy]:
        """
        Преобразует сырые данные от API в стандартизированный объект JobVacancy.
        """
        try:
            title = raw_job.get('title', '')
            description = raw_job.get('description', '')
            if not self.is_relevant_job(title, description, search_term):
                return None

            url = raw_job.get('url')
            if not url:
                return None
            job_id = hashlib.md5(url.encode()).hexdigest()

            date_str = raw_job.get('date', '')
            try:
                posted_date = datetime.strptime(date_str, '%a, %d %b %Y %H:%M:%S %Z').strftime('%Y-%m-%d')
            except (ValueError, TypeError):
                posted_date = datetime.now().strftime('%Y-%m-%d')

            return JobVacancy(
                id=f"careerjet_{job_id}",
                title=title,
                company=raw_job.get('company', 'Not specified'),
                location=raw_job.get('locations', 'Not specified'),
                salary=raw_job.get('salary'),
                description=description,
                apply_url=url,
                source=self.source_name,
                posted_date=posted_date,
                country=country_name,
                job_type=None,
                language_requirement=self.determine_language_requirement(title, description),
                refugee_friendly=self.is_refugee_friendly(title, description, search_term)
            )
        except Exception as e:
            print(f"⚠️ {self.source_name}: Ошибка нормализации вакансии: {e}")
            return None

    def is_relevant_job(self, job_title: str, job_description: str, search_term: str) -> bool:
        """
        Простая проверка на релевантность.
        """
        search_terms = search_term.lower().split()
        title_lower = job_title.lower()
        
        return any(term in title_lower for term in search_terms if len(term) > 2)

    def _get_country_name_by_code(self, country_code: str) -> str:
        """
        Вспомогательный метод для получения полного имени страны по коду.
        """
        return self.adzuna_countries.get(country_code, {}).get('name', country_code.upper())

    def _deduplicate_jobs(self, jobs: List[JobVacancy]) -> List[JobVacancy]:
        """Удаление дубликатов по уникальному ключу."""
        seen = set()
        unique_jobs = []
        for job in jobs:
            if job.apply_url not in seen:
                seen.add(job.apply_url)
                unique_jobs.append(job)
        return unique_jobs

if __name__ == '__main__':
    print("🚀 Тестовый запуск CareerjetAggregator...")
    
    try:
        main_aggregator_for_test = GlobalJobAggregator()
        aggregator = CareerjetAggregator(
            adzuna_countries=main_aggregator_for_test.countries,
            specific_jobs_map=main_aggregator_for_test.specific_jobs
        )
    except Exception as e:
        print(f"❌ Не удалось инициализировать агрегаторы для теста: {e}")
        aggregator = None

    if aggregator:
        test_preferences = {
            'selected_jobs': ['Заправщик на АЗС', 'Оператор АЗС'],
            'countries': ['us'],
            'cities': [] # <-- Тестируем без города
        }
        
        start_time = time.time()
        found_jobs = aggregator.search_jobs(test_preferences)
        end_time = time.time()
        
        print(f"\n\n--- РЕЗУЛЬТАТЫ ТЕСТА ---")
        print(f"⏱️ Время выполнения: {end_time - start_time:.2f} секунд")
        print(f"📊 Найдено вакансий: {len(found_jobs)}")
        
        if found_jobs:
            print("\n📝 Пример 5 найденных вакансий:")
            for i, job in enumerate(found_jobs[:5]):
                print(f"  {i+1}. {job.title} в {job.company} ({job.location})")
                print(f"     Ссылка: {job.apply_url}")
