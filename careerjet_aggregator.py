#!/usr/bin/env python3
"""
Careerjet Aggregator for GlobalJobHunter
"""

import os
import requests
import time
from datetime import datetime
from typing import List, Dict, Optional, Set
import hashlib
from dotenv import load_dotenv
import logging

# --- Переиспользуемые компоненты из adzuna_aggregator ---
from adzuna_aggregator import JobVacancy, CacheManager, RateLimiter, GlobalJobAggregator

# --- Базовый класс для соблюдения архитектуры ---
from base_aggregator import BaseJobAggregator

# Загружаем переменные окружения из .env файла
load_dotenv()

# Настройка логирования
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class CareerjetAggregator(BaseJobAggregator):
    """
    Агрегатор для поиска вакансий через Careerjet API.
    - Поддерживает поиск как по стране, так и по городу.
    - Выполняет отдельные запросы для каждой профессии для большей точности.
    """
    
    # Константы для конфигурации
    MAX_PAGES_PER_SEARCH = 10  # Ограничение на количество страниц
    JOBS_PER_PAGE = 50  # Ожидаемое количество вакансий на странице
    REQUEST_TIMEOUT = 15  # Таймаут запроса в секундах
    DELAY_BETWEEN_PAGES = 0.5  # Задержка между страницами
    
    def __init__(self, adzuna_countries: Dict, specific_jobs_map: Dict, cache_duration_hours: int = 12):
        """
        Инициализация агрегатора.
        """
        super().__init__(source_name='Careerjet')
        # Можно попробовать https если API поддерживает
        self.base_url = "http://public.api.careerjet.net/search"
        
        self.affid = os.getenv('CAREERJET_AFFID')
        if not self.affid:
            raise ValueError("CAREERJET_AFFID не найден в .env файле!")

        self.cache_manager = CacheManager(cache_duration_hours=cache_duration_hours)
        self.rate_limiter = RateLimiter(requests_per_minute=25)
        
        # Используем frozenset для неизменяемости и быстрого поиска
        self.country_map = {
            'gb': 'United Kingdom', 'us': 'United States', 'de': 'Germany',
            'fr': 'France', 'es': 'Spain', 'it': 'Italy', 'nl': 'Netherlands',
            'pl': 'Poland', 'ca': 'Canada', 'au': 'Australia', 'at': 'Austria',
            'ch': 'Switzerland', 'be': 'Belgium', 'se': 'Sweden', 'no': 'Norway',
            'dk': 'Denmark', 'cz': 'Czech Republic', 'sk': 'Slovakia'
        }

        self.adzuna_countries = adzuna_countries
        self.specific_jobs_map = specific_jobs_map
        
        # Предварительно создаем user-agent для повторного использования
        self.user_agent = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/108.0.0.0 Safari/537.36'
        
        # Создаем Session для повторного использования соединений
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": self.user_agent})

        logger.info(f"✅ Careerjet Aggregator инициализирован (affid: ...{self.affid[-4:]})")

    def get_supported_countries(self) -> Dict[str, Dict]:
        """Возвращает словарь стран, поддерживаемых этим агрегатором."""
        return {
            code: self.adzuna_countries.get(code, {"name": name})
            for code, name in self.country_map.items()
        }

    def search_jobs(self, preferences: Dict) -> List[JobVacancy]:
        """
        Основной метод поиска. Ищет по стране, и если указан город - уточняет поиск.
        Выполняет поиск для каждой профессии отдельно.
        """
        logger.info(f"🔍 {self.source_name}: Начинаем поиск...")
        all_jobs: List[JobVacancy] = []
        
        selected_jobs = preferences.get('selected_jobs', [])
        countries = preferences.get('countries', [])
        cities = preferences.get('cities', [])

        if not selected_jobs or not countries:
            return []

        # Подсчитываем общее количество запросов для информирования пользователя
        total_searches = len(selected_jobs) * len(countries) * (len(cities) if cities else 1)
        current_search = 0

        for russian_job_title in selected_jobs:
            # Получаем английские ключевые слова для профессии
            english_keywords = self._get_english_keywords(russian_job_title)
            if not english_keywords:
                continue

            keywords = " ".join(english_keywords)
            logger.info(f"ℹ️ {self.source_name}: Ищем профессию '{russian_job_title}' по словам: '{keywords}'")

            for country_code in countries:
                country_name_for_api = self.country_map.get(country_code)
                if not country_name_for_api:
                    logger.warning(f"Страна {country_code} не поддерживается")
                    continue

                if cities:
                    for city in cities:
                        current_search += 1
                        search_location = f"{city}, {country_name_for_api}"
                        logger.info(f"📍 Поиск {current_search}/{total_searches}: {search_location}")
                        jobs = self._fetch_all_pages(keywords, search_location, country_code)
                        all_jobs.extend(jobs)
                else:
                    current_search += 1
                    search_location = country_name_for_api
                    logger.info(f"📍 Поиск {current_search}/{total_searches}: {search_location}")
                    jobs = self._fetch_all_pages(keywords, search_location, country_code)
                    all_jobs.extend(jobs)

        unique_jobs = self._deduplicate_jobs(all_jobs)
        logger.info(f"✅ {self.source_name}: Поиск завершен. Найдено уникальных вакансий: {len(unique_jobs)} из {len(all_jobs)} общих.")
        return unique_jobs

    def _get_english_keywords(self, russian_job_title: str) -> List[str]:
        """
        Извлекает английские ключевые слова для русского названия профессии.
        """
        english_keywords = []
        
        for category in self.specific_jobs_map.values():
            if russian_job_title in category:
                # Берем первые 3 термина (они всегда на английском)
                english_terms = category[russian_job_title][:3]
                english_keywords.extend([term for term in english_terms if term])
                break
        
        # Если не нашли, используем само название
        if not english_keywords:
            english_keywords.append(russian_job_title)
        
        # Убираем дубликаты, сохраняя порядок
        seen = set()
        unique_keywords = []
        for keyword in english_keywords:
            if keyword not in seen:
                seen.add(keyword)
                unique_keywords.append(keyword)
        
        return unique_keywords

    def _fetch_all_pages(self, keywords: str, location: str, country_code: str) -> List[JobVacancy]:
        """
        Получает вакансии со всех доступных страниц пагинации.
        """
        page = 1
        total_jobs: List[JobVacancy] = []
        consecutive_empty_pages = 0  # Счетчик пустых страниц подряд
        
        while page <= self.MAX_PAGES_PER_SEARCH:
            # Формируем параметры запроса
            search_params = self._build_search_params(keywords, location, page)
            
            # Проверяем кеш
            cache_key_params = {k: v for k, v in search_params.items() if k not in ['user_ip', 'user_agent']}
            cached_result = self.cache_manager.get_cached_result(cache_key_params)
            
            if cached_result:
                total_jobs.extend(cached_result)
                if len(cached_result) < self.JOBS_PER_PAGE:
                    break  # Последняя страница
                page += 1
                continue

            # Выполняем запрос с rate limiting
            self.rate_limiter.wait_if_needed()
            
            jobs_on_page = self._fetch_single_page(search_params, country_code, keywords)
            
            if jobs_on_page is None:
                # Ошибка при запросе
                break
            
            if not jobs_on_page:
                # Пустая страница
                consecutive_empty_pages += 1
                if consecutive_empty_pages >= 2:
                    break  # Прекращаем, если 2 пустые страницы подряд
            else:
                consecutive_empty_pages = 0
                total_jobs.extend(jobs_on_page)
                self.cache_manager.cache_result(cache_key_params, jobs_on_page)
                logger.info(f"📄 {self.source_name}: Страница {page} - найдено {len(jobs_on_page)} вакансий")
                
                if len(jobs_on_page) < self.JOBS_PER_PAGE:
                    break  # Последняя страница
            
            page += 1
            if page <= self.MAX_PAGES_PER_SEARCH:
                time.sleep(self.DELAY_BETWEEN_PAGES)
                
        return total_jobs

    def _build_search_params(self, keywords: str, location: str, page: int) -> Dict:
        """Формирует параметры для API запроса."""
        return {
            'affid': self.affid,
            'keywords': keywords,
            'location': location,
            'page': page,
            'sort': 'date',
            'user_ip': '127.0.0.1',
            'user_agent': self.user_agent
        }

    def _fetch_single_page(self, search_params: Dict, country_code: str, keywords: str) -> Optional[List[JobVacancy]]:
        """
        Выполняет запрос для одной страницы и возвращает нормализованные вакансии.
        Возвращает None при ошибке, пустой список если нет вакансий.
        """
        try:
            response = self.session.get(
                self.base_url, 
                params=search_params, 
                timeout=self.REQUEST_TIMEOUT
            )
            
            if response.status_code != 200:
                logger.error(f"{self.source_name} API ошибка {response.status_code}: {response.text[:200]}")
                return None

            data = response.json()
            
            if data.get('type') == 'ERROR':
                logger.error(f"{self.source_name} API вернуло ошибку: {data.get('error')}")
                return None

            jobs_on_page_raw = data.get('jobs', [])
            if not jobs_on_page_raw:
                return []
            
            # Нормализуем вакансии
            country_name = self._get_country_name_by_code(country_code)
            normalized_jobs = []
            
            for job_data in jobs_on_page_raw:
                job = self._normalize_job_data(job_data, country_name, keywords)
                if job:
                    normalized_jobs.append(job)
            
            return normalized_jobs

        except requests.Timeout:
            logger.warning(f"{self.source_name}: Таймаут запроса для {search_params.get('location')}")
            return None
        except requests.RequestException as e:
            logger.error(f"{self.source_name}: Ошибка сети при запросе: {e}")
            return None
        except Exception as e:
            logger.error(f"{self.source_name}: Критическая ошибка при запросе: {e}")
            return None

    def _normalize_job_data(self, raw_job: Dict, country_name: str, search_term: str) -> Optional[JobVacancy]:
        """
        Преобразует сырые данные от API в стандартизированный объект JobVacancy.
        """
        try:
            title = raw_job.get('title', '').strip()
            description = raw_job.get('description', '').strip()
            
            # Проверка релевантности
            if not self.is_relevant_job(title, description, search_term):
                return None

            url = raw_job.get('url')
            if not url:
                return None
            
            # Генерируем уникальный ID
            job_id = hashlib.md5(url.encode()).hexdigest()

            # Парсим дату
            posted_date = self._parse_date(raw_job.get('date', ''))

            return JobVacancy(
                id=f"careerjet_{job_id}",
                title=title,
                company=(raw_job.get('company') or 'Not specified').strip(),
                location=(raw_job.get('locations') or 'Not specified').strip(),
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
            logger.warning(f"{self.source_name}: Ошибка нормализации вакансии: {e}")
            return None

    def _parse_date(self, date_str: str) -> str:
        """Парсит дату из различных форматов."""
        if not date_str:
            return datetime.now().strftime('%Y-%m-%d')
        
        try:
            # Основной формат Careerjet
            return datetime.strptime(date_str, '%a, %d %b %Y %H:%M:%S %Z').strftime('%Y-%m-%d')
        except (ValueError, TypeError):
            # Пробуем альтернативные форматы
            for fmt in ['%Y-%m-%d', '%d/%m/%Y', '%m/%d/%Y']:
                try:
                    return datetime.strptime(date_str[:10], fmt).strftime('%Y-%m-%d')
                except:
                    continue
            return datetime.now().strftime('%Y-%m-%d')

    def is_relevant_job(self, job_title: str, job_description: str, search_term: str) -> bool:
        """
        Улучшенная проверка на релевантность с учетом описания.
        """
        search_terms = set(term.lower() for term in search_term.split() if len(term) > 2)
        title_lower = job_title.lower()
        description_lower = job_description.lower()[:500]  # Проверяем только начало описания
        
        # Проверяем наличие хотя бы одного термина в заголовке
        title_match = any(term in title_lower for term in search_terms)
        
        # Если нет совпадения в заголовке, проверяем описание (но требуем больше совпадений)
        if not title_match and len(search_terms) > 1:
            description_matches = sum(1 for term in search_terms if term in description_lower)
            return description_matches >= len(search_terms) // 2
        
        return title_match

    def _get_country_name_by_code(self, country_code: str) -> str:
        """
        Вспомогательный метод для получения полного имени страны по коду.
        """
        return self.adzuna_countries.get(country_code, {}).get('name', country_code.upper())

    def _deduplicate_jobs(self, jobs: List[JobVacancy]) -> List[JobVacancy]:
        """
        Удаление дубликатов по уникальному ключу с сохранением порядка.
        Использует более эффективный подход.
        """
        seen: Set[str] = set()
        unique_jobs: List[JobVacancy] = []
        
        for job in jobs:
            # Используем URL как уникальный ключ
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
            'cities': []  # Тестируем без города
        }
        
        start_time = time.time()
        found_jobs = aggregator.search_jobs(test_preferences)
        end_time = time.time()
        
        print(f"\n\n--- РЕЗУЛЬТАТЫ ТЕСТА ---")
        print(f"⏱️ Время выполнения: {end_time - start_time:.2f} секунд")
        print(f"📊 Найдено вакансий: {len(found_jobs)}")
        
        if found_jobs:
            print("\n📝 Пример 5 найденных вакансий:")
            for i, job in enumerate(found_jobs[:5], 1):
                print(f"  {i}. {job.title} в {job.company} ({job.location})")
                print(f"     Ссылка: {job.apply_url}")
                print(f"     Дата: {job.posted_date}")