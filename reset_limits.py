import json
import os

# Проверяем существует ли файл
if os.path.exists('rate_limits.json'):
    # Очищаем лимиты
    with open('rate_limits.json', 'w') as f:
        json.dump({}, f)
    print("✅ Rate limits сброшены!")
else:
    print("ℹ️ Файл rate_limits.json не найден - лимиты уже сброшены")