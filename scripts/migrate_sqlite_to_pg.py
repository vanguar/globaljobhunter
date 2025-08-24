# scripts/migrate_sqlite_to_pg.py
import os, sqlite3, json
from datetime import datetime
from app import app, db, Subscriber, EmailLog  # модели из твоего app.py

SQLITE_PATH = os.path.join("instance", "globaljobhunter.db")

def row_exists(model, pk_val):
    return db.session.get(model, pk_val) is not None

def as_bool(x):
    if x in (1, "1", True, "true", "True", "t", "y", "yes"):
        return True
    if x in (0, "0", False, "false", "False", "f", "n", "no"):
        return False
    return bool(x)

def load_json(x):
    if x is None or x == '':
        return None
    try:
        return json.loads(x)
    except:
        return None

def migrate():
    if not os.path.exists(SQLITE_PATH):
        print(f"SQLite file not found: {SQLITE_PATH}")
        return

    con = sqlite3.connect(SQLITE_PATH)
    con.row_factory = sqlite3.Row
    cur = con.cursor()

    with app.app_context():
        # 1) Subscribers
        try:
            cur.execute("SELECT * FROM subscriber")
            rows = cur.fetchall()
        except sqlite3.Error:
            # иногда таблица названа Subscribers/Subscriber — поправьте имя при необходимости
            cur.execute("SELECT * FROM Subscriber")
            rows = cur.fetchall()

        for r in rows:
            # предполагаемые поля; пропускаем, если чего-то нет
            data = dict(r)
            sid = data.get("id")
            if row_exists(Subscriber, sid):
                continue

            s = Subscriber(
                id=sid,
                email=data.get("email"),
                is_refugee=as_bool(data.get("is_refugee", True)),
                city=data.get("city"),
                frequency=data.get("frequency") or "weekly",
                is_active=as_bool(data.get("is_active", True)),
                lang=(data.get("lang") or "ru"),
                created_at=data.get("created_at"),
                updated_at=data.get("updated_at"),
            )

            # перенос списков (если хранились как JSON)
            jobs = load_json(data.get("selected_jobs"))
            countries = load_json(data.get("countries"))
            if jobs:
                try:
                    s.set_selected_jobs(jobs)
                except Exception:
                    # если нет метода — положим как есть
                    s.selected_jobs = json.dumps(jobs, ensure_ascii=False)
            if countries:
                try:
                    s.set_countries(countries)
                except Exception:
                    s.countries = json.dumps(countries, ensure_ascii=False)

            db.session.add(s)

        db.session.commit()
        print(f"Subscribers migrated: {len(rows)}")

        # 2) EmailLog (если есть)
        try:
            cur.execute("SELECT * FROM email_log")
            rows = cur.fetchall()
        except sqlite3.Error:
            try:
                cur.execute("SELECT * FROM EmailLog")
                rows = cur.fetchall()
            except sqlite3.Error:
                rows = []

        for r in rows:
            data = dict(r)
            lid = data.get("id")
            if row_exists(EmailLog, lid):
                continue
            e = EmailLog(
                id=lid,
                subscriber_id=data.get("subscriber_id"),
                email=data.get("email"),
                subject=data.get("subject"),
                jobs_count=data.get("jobs_count") or 0,
                status=data.get("status") or "sent",
                error_message=data.get("error_message"),
                sent_at=data.get("sent_at"),
                created_at=data.get("created_at"),
            )
            db.session.add(e)

        db.session.commit()
        print(f"EmailLog migrated: {len(rows)}")

    con.close()
    print("DONE.")

if __name__ == "__main__":
    migrate()
