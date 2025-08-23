from app import app
from database import db, Subscriber
from sqlalchemy import text, inspect

with app.app_context():
    insp = inspect(db.engine)
    table_name = getattr(Subscriber, "__tablename__", "subscriber")
    cols = [c["name"] for c in insp.get_columns(table_name)]

    if "lang" in cols:
        print("✔ Поле 'lang' уже существует — миграция не нужна.")
    else:
        # Для Postgres можно было бы IF NOT EXISTS, но в SQLite его нет,
        # поэтому предварительно проверяем через inspect (см. выше).
        ddl = f"ALTER TABLE {table_name} ADD COLUMN lang VARCHAR(5) DEFAULT 'ru'"
        db.session.execute(text(ddl))
        db.session.commit()
        print("✅ Поле 'lang' добавлено в таблицу", table_name)
