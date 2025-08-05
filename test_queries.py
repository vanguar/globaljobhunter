import requests
import os
from dotenv import load_dotenv

load_dotenv()

app_id = "1c4dfdde"
app_key = "e3e606e08b03d56b8a215327cc448ab8"

# Тестируем проблемные запросы
test_queries = [
    'lieferfahrer OR bicycle courier OR bike courier',  # Ваш запрос
    'lieferfahrer',  # Простой немецкий
    'bicycle courier',  # Простой английский
    'delivery driver',  # Еще проще
    'courier',  # Самый простой
    'driver',  # Максимально простой
]

for query in test_queries:
    url = "https://api.adzuna.com/v1/api/jobs/de/search/1"
    params = {
        'app_id': app_id,
        'app_key': app_key,
        'what': query,
        'results_per_page': 5
    }
    
    print(f"\n🧪 Тест: '{query}'")
    try:
        response = requests.get(url, params=params, timeout=10)
        if response.status_code == 200:
            data = response.json()
            results = data.get('results', [])
            print(f"✅ Найдено: {len(results)} вакансий")
            
            if len(results) > 0:
                print(f"📋 Примеры:")
                for i, job in enumerate(results[:2]):
                    print(f"  {i+1}. {job.get('title', 'No title')}")
        else:
            print(f"❌ Ошибка {response.status_code}: {response.text[:200]}")
    except Exception as e:
        print(f"❌ Исключение: {e}")