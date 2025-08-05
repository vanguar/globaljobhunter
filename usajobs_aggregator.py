#!/usr/bin/env python3
"""
USAJobs API Aggregator - Официальные государственные вакансии США
API: https://developer.usajobs.gov/
"""

import requests
import time
from typing import List, Dict, Optional
from base_aggregator import BaseJobAggregator, JobVacancy

class USAJobsAggregator(BaseJobAggregator):
    def __init__(self, api_key: str = None):
        super().__init__("USAJobs")
        self.api_key = api_key  # Опциональный API ключ для увеличения лимитов
        self.base_url = "https://data.usajobs.gov/api/search"
        
    def get_supported_countries(self) -> Dict[str, Dict]:
        return {
            'us': {'name': 'США', 'currency': '$', 'government_jobs': True}
        }
    
    def search_jobs(self, preferences: Dict) -> List[JobVacancy]:
        """Поиск государственных вакансий США"""
        # Проверяем, выбраны ли США
        countries = preferences.get('countries', [])
        if 'us' not in countries:
            return []
        
        all_jobs = []
        selected_jobs = preferences.get('selected_jobs', [])
        
        for job_category in selected_jobs:
            search_terms = self._convert_to_search_terms(job_category)
            
            for term in search_terms:
                try:
                    jobs = self._fetch_jobs(term)
                    all_jobs.extend(jobs)
                    time.sleep(1)  # USAJobs требует вежливого ограничения
                except Exception as e:
                    print(f"🔴 USAJobs ошибка для '{term}': {e}")
                    continue
        
        return self._deduplicate_jobs(all_jobs)
    
    def _fetch_jobs(self, search_term: str) -> List[JobVacancy]:
        """Получение вакансий от USAJobs API"""
        headers = {
            'Host': 'data.usajobs.gov',
            'User-Agent': 'your-email@example.com'  # USAJobs требует email в User-Agent
        }
        
        params = {
            'Keyword': search_term,
            'ResultsPerPage': 10,
            'Page': 1
        }
        
        response = requests.get(self.base_url, headers=headers, params=params, timeout=15)
        
        if response.status_code == 200:
            data = response.json()
            search_result = data.get('SearchResult', {})
            jobs_data = search_result.get('SearchResultItems', [])
            
            normalized_jobs = []
            for item in jobs_data:
                job_data = item.get('MatchedObjectDescriptor', {})
                job = self._normalize_job_data(job_data, search_term)
                if job:
                    normalized_jobs.append(job)
            
            return normalized_jobs
        else:
            print(f"🔴 USAJobs детали ошибки: {response.text}")
            raise Exception(f"API вернул {response.status_code}")
    
    def _is_job_relevant(self, job_data: Dict, search_term: str) -> bool:
        """Проверка релевантности"""
        title = job_data.get('PositionTitle', '').lower()
        summary = job_data.get('UserArea', {}).get('Details', {}).get('JobSummary', '').lower()
        
        return self.is_relevant_job(title, summary, search_term)
    
    def _normalize_job_data(self, raw_job: Dict, search_term: str) -> Optional[JobVacancy]:
        """Нормализация данных USAJobs"""
        try:
            job_id = raw_job.get('PositionID', '')
            title = raw_job.get('PositionTitle', 'No title')
            
            org_data = raw_job.get('OrganizationName', '')
            company = org_data if isinstance(org_data, str) else 'US Government'
            
            location_data = raw_job.get('PositionLocationDisplay', '')
            location = location_data if location_data else 'USA'
            
            user_area = raw_job.get('UserArea', {})
            details = user_area.get('Details', {})
            
            description = details.get('JobSummary', 'No description')
            apply_url = details.get('ApplyURI', [''])[0] if details.get('ApplyURI') else ''
            
            # Форматируем зарплату
            salary_data = raw_job.get('PositionRemuneration', [])
            salary = self._format_usa_salary(salary_data)
            
            posted_date = raw_job.get('PublicationStartDate', 'Unknown date')
            
            language_req = self.determine_language_requirement(title, description)
            refugee_friendly = self.is_refugee_friendly(title, description, search_term)
            
            return JobVacancy(
                id=f"usajobs_{job_id}",
                title=title,
                company=company,
                location=location,
                salary=salary,
                description=description,
                apply_url=apply_url,
                source="USAJobs",
                posted_date=posted_date,
                country="США",
                job_type="Government",
                language_requirement=language_req,
                refugee_friendly=refugee_friendly
            )
            
        except Exception as e:
            print(f"🔴 USAJobs нормализация ошибка: {e}")
            return None
    
    def _format_usa_salary(self, salary_data: List) -> Optional[str]:
        """Форматирование зарплаты USAJobs"""
        if not salary_data:
            return None
        
        try:
            salary_info = salary_data[0]
            min_salary = salary_info.get('MinimumRange')
            max_salary = salary_info.get('MaximumRange')
            
            if min_salary and max_salary:
                return f"${min_salary:,.0f} - ${max_salary:,.0f}"
            elif min_salary:
                return f"От ${min_salary:,.0f}"
            elif max_salary:
                return f"До ${max_salary:,.0f}"
                
        except Exception:
            pass
        
        return None
    
    def _convert_to_search_terms(self, job_category: str) -> List[str]:
        """Конвертация в термины для USAJobs"""
        mapping = {
            'Программист': ['software developer', 'programmer', 'IT specialist'],
            'Дата-аналитик': ['data analyst', 'statistician'],
            'Системный администратор': ['system administrator', 'IT specialist'],
            'Менеджер': ['manager', 'program manager'],
            'Администратор': ['administrative', 'clerk'],
            'Координатор': ['coordinator', 'program coordinator']
        }
        
        return mapping.get(job_category, [job_category.lower()])
    
    def is_relevant_job(self, job_title: str, job_description: str, search_term: str) -> bool:
        """Проверка релевантности для государственных вакансий"""
        title_lower = job_title.lower()
        search_lower = search_term.lower()
        
        # Базовая проверка содержания поискового термина
        return search_lower in title_lower or search_lower in job_description.lower()
    
    def _deduplicate_jobs(self, jobs: List[JobVacancy]) -> List[JobVacancy]:
        """Дедупликация"""
        seen = set()
        unique_jobs = []
        
        for job in jobs:
            key = f"{job.title.lower()}|{job.company.lower()}|{job.location.lower()}"
            if key not in seen:
                seen.add(key)
                unique_jobs.append(job)
        
        return unique_jobs