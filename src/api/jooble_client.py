import requests
import json
from typing import Dict, List, Optional
import os
from dotenv import load_dotenv

load_dotenv()

class JoobleClient:
    def __init__(self, api_key: str = None):
        self.api_key = api_key or os.getenv('JOOBLE_API_KEY')
        self.base_url = "https://jooble.org/api"
    
    def search_jobs(self, 
                   keywords: str, 
                   location: str = "Deutschland",
                   page: int = 1,
                   results_per_page: int = 20,
                   radius: int = 40,
                   min_salary: int = None) -> Optional[Dict]:
        """
        Поиск вакансий через Jooble API
        """
        url = f"{self.base_url}/{self.api_key}"
        
        payload = {
            "keywords": keywords,
            "location": location,
            "page": page,
            "resultonpage": results_per_page,
            "radius": radius
        }
        
        if min_salary:
            payload["salary"] = min_salary
        
        try:
            response = requests.post(
                url, 
                json=payload,
                headers={'Content-Type': 'application/json'},
                timeout=30
            )
            response.raise_for_status()
            return response.json()
            
        except requests.exceptions.RequestException as e:
            print(f"Ошибка API запроса: {e}")
            return None
    
    def format_job_results(self, results: Dict) -> None:
        """Красивый вывод результатов поиска"""
        if not results or 'jobs' not in results:
            print("Нет результатов для отображения")
            return
        
        print(f"\n=== Найдено вакансий: {results.get('totalCount', 0)} ===\n")
        
        for i, job in enumerate(results['jobs'][:10], 1):
            print(f"{i}. {job.get('title', 'Без названия')}")
            print(f"   Компания: {job.get('company', 'Не указана')}")
            print(f"   Локация: {job.get('location', 'Не указана')}")
            print(f"   Зарплата: {job.get('salary', 'Не указана')}")
            print(f"   Тип: {job.get('type', 'Не указан')}")
            print(f"   Ссылка: {job.get('link', 'Нет ссылки')}")
            print(f"   Описание: {job.get('snippet', 'Нет описания')[:100]}...")
            print("-" * 60)

if __name__ == "__main__":
    # Тестирование API клиента
    client = JoobleClient()
    
    # Тестовый поиск
    print("Тестируем Jooble API...")
    results = client.search_jobs("Python Developer", "Berlin", results_per_page=5)
    
    if results:
        client.format_job_results(results)
        print(f"\nИспользовано запросов API: 1")
    else:
        print("Не удалось получить результаты")