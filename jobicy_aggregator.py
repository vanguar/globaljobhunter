#!/usr/bin/env python3
"""
Jobicy API Aggregator - Бесплатные удаленные вакансии
С соблюдением rate limits (1 запрос в час)
"""

import requests
import time
import json
import os
from datetime import datetime, timedelta
from typing import List, Dict, Optional
from dataclasses import dataclass

@dataclass
class JobVacancy:
    id: str
    title: str
    company: str
    location: str
    salary: Optional[str]
    description: str
    apply_url: str
    source: str
    posted_date: str
    country: str
    job_type: Optional[str] = None
    language_requirement: str = "unknown"
    refugee_friendly: bool = False

class JobicyAggregator:
    def __init__(self):
        self.source_name = "Jobicy"
        self.base_url = "https://jobicy.com/api/v2/remote-jobs"
        self.cache_file = "shared_jobicy_cache.json"  # Общий для всех
        self.cache_duration_hours = 12  # Кешируем на 12 часов
        
    def search_jobs(self, preferences: Dict, progress_callback=None, cancel_check=None) -> List[JobVacancy]:
        """
        Основной метод поиска вакансий на Jobicy с учетом выбранных профессий.
        """
        print(f"🔄 {self.source_name}: начинаем поиск удалённых вакансий")
        relevant_jobs: List[JobVacancy] = []

        # Скачиваем/читаем общую ленту
        raw_jobs = self._fetch_jobs_cached()

        selected_jobs = preferences.get('selected_jobs', [])
        if not selected_jobs:
            return []

        # Фильтрация по ключевым словам
        include_keywords, exclude_keywords = self._build_keywords(selected_jobs)
        print(f"🔍 {self.source_name}: ищем по словам: {include_keywords}")
        print(f"🚫 {self.source_name}: исключаем слова: {exclude_keywords}")

        for job in raw_jobs:
            normalized = self._normalize_job(job)
            if not normalized:
                continue
            text = f"{normalized.title} {normalized.company}".lower()
            if any(word in text for word in exclude_keywords):
                continue
            if not any(word in text for word in include_keywords):
                continue
            relevant_jobs.append(normalized)

            # отдаём прогресс порциями по мере накопления
            if progress_callback and len(relevant_jobs) % 10 == 0:
                try:
                    progress_callback(relevant_jobs[-10:])
                except Exception:
                    pass

        print(f"✅ {self.source_name}: найдено {len(relevant_jobs)} релевантных вакансий")
        return relevant_jobs


    
    def _is_it_related(self, job_name: str) -> bool:
        """Проверяем, подходит ли профессия для удаленной работы"""
        remote_friendly_keywords = [
            # IT
            'python', 'программист', 'разработчик', 'веб-разработчик', 
            'дата-аналитик', 'системный администратор', 'тестировщик',
            'it', 'технологии',
            
            # Офисные (могут быть удаленными)
            'менеджер', 'маркетинг', 'дизайн', 'контент', 'сео',
            'переводчик', 'копирайтер', 'аналитик', 'консультант',
            'hr', 'рекрутер', 'финансы', 'бухгалтер', 'поддержка',
            'продажи', 'координатор', 'ассистент', 'секретарь',
            'журналист', 'редактор', 'smm', 'pr', 'реклама'
        ]
        return any(keyword in job_name.lower() for keyword in remote_friendly_keywords)
    
    def _fetch_jobs_cached(self) -> List[Dict]:
        """ОДИН запрос с кешированием - соблюдаем rate limits"""
        # Проверяем кеш
        cached_data = self._load_cache()
        if cached_data:
            print(f"🎯 Jobicy: используем кешированные данные ({len(cached_data)} вакансий)")
            return cached_data
        
        # Кеш устарел - делаем ОДИН запрос
        print(f"🔍 Jobicy: кеш пуст, делаем ЕДИНСТВЕННЫЙ запрос к API")
        print(f"⏱️ Jobicy: соблюдаем rate limit - только 1 запрос на 2 часа")
        
        try:
            response = requests.get(self.base_url, timeout=15)
            
            if response.status_code == 200:
                data = response.json()
                jobs = data.get('jobs', [])
                print(f"🟢 Jobicy: получено {len(jobs)} вакансий с API")
                
                # Сохраняем в кеш
                self._save_cache(jobs)
                return jobs
            else:
                print(f"🔴 Jobicy ошибка {response.status_code}: {response.text}")
                return []
        except Exception as e:
            print(f"🔴 Jobicy ошибка: {e}")
            return []
    
    def _load_cache(self) -> Optional[List[Dict]]:
        """Загрузка данных из кеша"""
        try:
            if not os.path.exists(self.cache_file):
                return None
                
            with open(self.cache_file, 'r', encoding='utf-8') as f:
                cache_data = json.load(f)
            
            # Проверяем срок действия кеша
            cache_time = datetime.fromisoformat(cache_data['timestamp'])
            if datetime.now() - cache_time < timedelta(hours=self.cache_duration_hours):
                return cache_data['jobs']
            else:
                print(f"⏰ Jobicy: кеш устарел ({cache_time})")
                return None
                
        except Exception as e:
            print(f"⚠️ Jobicy: ошибка загрузки кеша: {e}")
            return None
    
    def _save_cache(self, jobs: List[Dict]):
        """Сохранение данных в кеш"""
        try:
            cache_data = {
                'timestamp': datetime.now().isoformat(),
                'jobs': jobs
            }
            with open(self.cache_file, 'w', encoding='utf-8') as f:
                json.dump(cache_data, f, ensure_ascii=False, indent=2)
            print(f"💾 Jobicy: данные сохранены в кеш")
        except Exception as e:
            print(f"⚠️ Jobicy: ошибка сохранения кеша: {e}")
    
    def _filter_relevant_jobs(self, jobs_data: List[Dict], selected_jobs: List[str], progress_callback=None, cancel_check=None) -> List[JobVacancy]:
        """
        Фильтрация релевантных вакансий по выбранным профессиям.
        Отдаёт батчи (по 5 штук) через progress_callback, уважает cancel_check().
        """
        relevant_jobs: List[JobVacancy] = []

        job_keywords = {
            'дата-аналитик': ['data analyst', 'business analyst', 'analytics', 'bi analyst', 'reporting analyst', 'data scientist'],
            'системный администратор': ['system administrator', 'sysadmin', 'system admin', 'infrastructure engineer', 'devops engineer', 'network admin', 'it admin', 'site reliability'],
            'python разработчик': ['python developer', 'python engineer', 'python programmer', 'django', 'flask'],
            'веб-разработчик': ['web developer', 'frontend developer', 'backend developer', 'fullstack developer', 'react', 'angular', 'vue'],
            'программист': ['software developer', 'software engineer', 'programmer', 'developer', 'engineer'],
            'тестировщик': ['qa engineer', 'qa tester', 'test engineer', 'quality assurance', 'automation tester']
        }
        negative_keywords = [
            'sales', 'marketing', 'customer service', 'support representative',
            'account executive', 'business development', 'product manager',
            'program manager', 'project manager', 'marketing expert',
            'sales specialist', 'customer success', 'account manager',
            'technical product manager', 'solutions sales'
        ]

        # собрать ключи для выбранных профессий
        search_keywords = []
        for job in selected_jobs:
            job_lower = job.lower()
            found = False
            for key, keywords in job_keywords.items():
                if key in job_lower or job_lower in key:
                    search_keywords.extend(keywords)
                    found = True
                    break
            if not found:
                search_keywords.append(job_lower)

        print(f"🔍 {self.source_name}: ищем по словам: {search_keywords}")
        print(f"🚫 {self.source_name}: исключаем слова: {negative_keywords}")

        batch: List[JobVacancy] = []
        for job_data in jobs_data:
            if cancel_check and cancel_check():
                # отдадим накопившийся батч перед выходом
                if progress_callback and batch:
                    try:
                        progress_callback(batch)
                    except Exception:
                        pass
                return relevant_jobs

            title = job_data.get('jobTitle', '').lower()
            description = job_data.get('jobExcerpt', '').lower()
            combined_text = f"{title} {description}"

            has_positive = any(keyword in combined_text for keyword in search_keywords)
            has_negative = any(negative in combined_text for negative in negative_keywords)

            if has_positive and not has_negative:
                job = self._normalize_job(job_data)
                if job:
                    relevant_jobs.append(job)
                    batch.append(job)
                    # отдаём батч каждые 5 позиций для "живого" счётчика
                    if progress_callback and len(batch) >= 5:
                        try:
                            progress_callback(batch)
                        except Exception:
                            pass
                        batch = []
            # при has_positive & has_negative — просто пропускаем

        # добросим хвост батча
        if progress_callback and batch:
            try:
                progress_callback(batch)
            except Exception:
                pass

        return relevant_jobs

    
        
    def _normalize_job(self, raw_job: Dict) -> Optional[JobVacancy]:
        """Нормализация данных"""
        try:
            job_id = str(raw_job.get('id', ''))
            title = raw_job.get('jobTitle', 'No title')
            company = raw_job.get('companyName', 'No company')
            description = raw_job.get('jobExcerpt', 'No description')
            apply_url = raw_job.get('url', '')
            posted_date = raw_job.get('pubDate', 'Unknown')
            
            return JobVacancy(
                id=f"jobicy_{job_id}",
                title=title,
                company=company,
                location="Remote (Удаленно)",
                salary=None,
                description=description,
                apply_url=apply_url,
                source="Jobicy",
                posted_date=posted_date,
                country="Remote",
                job_type="Remote",
                language_requirement="unknown",
                refugee_friendly=False
            )
            
        except Exception as e:
            print(f"❌ Jobicy нормализация ошибка: {e}")
            return None