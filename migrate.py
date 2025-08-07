#!/usr/bin/env python3
import os
import sys
from flask_migrate import Migrate, init, migrate as create_migration, upgrade
from sqlalchemy import inspect, text

# Добавляем текущую директорию в Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import app, db

migrate_obj = Migrate(app, db)

def check_db_status():
    """Проверка состояния БД и миграций"""
    try:
        with app.app_context():
            # Проверяем соединение
            with db.engine.connect() as conn:
                print("✅ Соединение с БД работает")
            
            # Проверяем таблицы
            inspector = inspect(db.engine)
            tables = inspector.get_table_names()
            print(f"📊 Таблиц в БД: {len(tables)}")
            
            if tables:
                print(f"📋 Таблицы: {', '.join(tables)}")
                
                # Проверяем данные
                try:
                    with db.engine.connect() as conn:
                        if 'subscriber' in tables:
                            result = conn.execute(text("SELECT COUNT(*) as count FROM subscriber"))
                            count = result.fetchone()[0]
                            print(f"👥 Подписчиков: {count}")
                        
                        if 'email_log' in tables:
                            result = conn.execute(text("SELECT COUNT(*) as count FROM email_log"))
                            count = result.fetchone()[0]
                            print(f"📧 Email логов: {count}")
                except Exception as e:
                    print(f"⚠️ Ошибка проверки данных: {e}")
            else:
                print("📭 БД пустая")
                
            # Проверяем migrations
            migrations_dir = os.path.join(os.getcwd(), 'migrations')
            if os.path.exists(migrations_dir):
                versions_dir = os.path.join(migrations_dir, 'versions')
                if os.path.exists(versions_dir):
                    migration_files = [f for f in os.listdir(versions_dir) if f.endswith('.py')]
                    print(f"📂 Файлов миграций: {len(migration_files)}")
                else:
                    print("❌ Папка migrations/versions/ не найдена")
            else:
                print("❌ Папка migrations/ не найдена")
                
    except Exception as e:
        print(f"❌ Ошибка проверки БД: {e}")

if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("📖 Использование:")
        print("  python migrate.py status    - проверка состояния БД")
        print("  python migrate.py init      - инициализация миграций")  
        print("  python migrate.py migrate   - создание миграции")
        print("  python migrate.py upgrade   - применение миграций")
        print("  python migrate.py backup    - создание бекапа БД")
        sys.exit(1)
    
    command = sys.argv[1]
    
    try:
        with app.app_context():
            if command == 'status':
                check_db_status()
                
            elif command == 'init':
                if os.path.exists('migrations'):
                    print("⚠️ Папка migrations уже существует")
                else:
                    init()
                    print("✅ Миграции инициализированы")
                    
            elif command == 'migrate':
                message = sys.argv[2] if len(sys.argv) > 2 else "Auto migration"
                
                # Проверяем есть ли изменения
                import tempfile
                with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
                    try:
                        create_migration(message=message)
                        print(f"✅ Миграция создана: {message}")
                    except Exception as e:
                        if "No changes in schema detected" in str(e):
                            print("ℹ️ Изменений в схеме не обнаружено")
                        else:
                            raise
                        
            elif command == 'upgrade':
                # Безопасное применение миграций
                check_db_status()
                print("\n🔄 Применяем миграции...")
                upgrade()
                print("✅ Миграции применены")
                check_db_status()
                
            elif command == 'backup':
                # Простой бекап (только для SQLite)
                if 'sqlite' in str(db.engine.url):
                    import shutil
                    from datetime import datetime
                    
                    db_file = str(db.engine.url).replace('sqlite:///', '')
                    backup_name = f"backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.db"
                    
                    shutil.copy2(db_file, backup_name)
                    print(f"✅ Бекап создан: {backup_name}")
                else:
                    print("⚠️ Бекап доступен только для SQLite")
                    
            else:
                print(f"❌ Неизвестная команда: {command}")
                
    except Exception as e:
        print(f"❌ Ошибка: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)