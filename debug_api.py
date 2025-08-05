import requests

app_id = "1c4dfdde"
app_key = "e3e606e08b03d56b8a215327cc448ab8"

# Тест простого запроса
url = "https://api.adzuna.com/v1/api/jobs/de/search/1"
params = {
    'app_id': app_id,
    'app_key': app_key,
    'what': 'python',
    'results_per_page': 5
}

print("🧪 Тестируем простой запрос...")
response = requests.get(url, params=params)
print(f"Status: {response.status_code}")
print(f"Response: {response.text[:500]}")