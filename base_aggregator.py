#!/usr/bin/env python3
"""
Базовый класс для всех агрегаторов вакансий
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import List, Dict, Optional
from datetime import datetime

@dataclass
class JobVacancy:
    id: str
    title: str
    company: str
    location: str
    salary: Optional[str]
    description: str
    apply_url: str
    source: str  # Название источника (Adzuna, Jobicy, USAJobs, etc.)
    posted_date: str
    country: str
    job_type: Optional[str] = None
    language_requirement: str = "unknown"
    refugee_friendly: bool = False

class BaseJobAggregator(ABC):
    """Базовый класс для всех агрегаторов вакансий"""
    
    def __init__(self, source_name: str):
        self.source_name = source_name
        self.supported_countries = self.get_supported_countries()
    
    @abstractmethod
    def get_supported_countries(self) -> Dict[str, Dict]:
        """Возвращает список поддерживаемых стран"""
        pass
    
    @abstractmethod
    def search_jobs(self, preferences: Dict) -> List[JobVacancy]:
        """Поиск вакансий по предпочтениям"""
        pass
    
    @abstractmethod
    def is_relevant_job(self, job_title: str, job_description: str, search_term: str) -> bool:
        """Проверка релевантности вакансии"""
        pass
    
    def format_salary(self, salary_data: any, country: str) -> Optional[str]:
        """Форматирование зарплаты (базовая реализация)"""
        if not salary_data:
            return None
        
        # Базовая логика форматирования
        if isinstance(salary_data, (int, float)):
            return f"${salary_data:,.0f}"
        elif isinstance(salary_data, str):
            return salary_data
        
        return None
    
    def determine_language_requirement(self, title: str, description: str) -> str:
        """Определение языковых требований"""
        text = f"{title} {description}".lower()
        
        no_language_indicators = [
            'no language', 'без языка', 'physical work', 'manual work',
            'driver', 'delivery', 'warehouse', 'cleaning', 'kitchen'
        ]
        
        if any(indicator in text for indicator in no_language_indicators):
            return "no_language_required"
        
        return "unknown"
    
    def is_refugee_friendly(self, title: str, description: str, search_term: str) -> bool:
        """Определение дружелюбности к беженцам"""
        text = f"{title} {description} {search_term}".lower()
        
        refugee_indicators = [
            'refugee', 'ukrainian', 'ukraine', 'asylum', 'integration',
            'newcomer', 'immigrant', 'migration'
        ]
        
        return any(indicator in text for indicator in refugee_indicators)