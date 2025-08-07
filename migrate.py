#!/usr/bin/env python3
import os
import sys
from flask_migrate import Migrate, init, migrate as create_migration, upgrade

# Добавляем текущую директорию в Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import app, db

migrate_obj = Migrate(app, db)

if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("📖 Использование:")
        print("  python migrate.py init     - инициализация миграций")  
        print("  python migrate.py migrate  - создание миграции")
        print("  python migrate.py upgrade  - применение миграций")
        sys.exit(1)
    
    command = sys.argv[1]
    
    try:
        with app.app_context():
            if command == 'init':
                init()
                print("✅ Миграции инициализированы")
            elif command == 'migrate':
                message = sys.argv[2] if len(sys.argv) > 2 else "Auto migration"
                create_migration(message=message)
                print(f"✅ Миграция создана: {message}")
            elif command == 'upgrade':
                upgrade()
                print("✅ Миграция применена")
            else:
                print(f"❌ Неизвестная команда: {command}")
    except Exception as e:
        print(f"❌ Ошибка: {e}")
        sys.exit(1)