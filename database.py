from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
import json

db = SQLAlchemy()

class Subscriber(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Предпочтения пользователя
    is_refugee = db.Column(db.Boolean, default=True)
    selected_jobs = db.Column(db.Text)  # JSON строка
    countries = db.Column(db.Text)      # JSON строка
    city = db.Column(db.String(100))
    
    # Настройки уведомлений
    frequency = db.Column(db.String(20), default='weekly')  # daily, weekly, monthly
    last_sent = db.Column(db.DateTime)
    
    def get_selected_jobs(self):
        """БЕЗОПАСНОЕ получение списка профессий"""
        try:
            if self.selected_jobs:
                return json.loads(self.selected_jobs)
            return []
        except (json.JSONDecodeError, TypeError) as e:
            print(f"❌ Ошибка парсинга selected_jobs для {self.email}: {e}")
            return []
    
    def set_selected_jobs(self, jobs_list):
        """БЕЗОПАСНОЕ сохранение списка профессий"""
        try:
            self.selected_jobs = json.dumps(jobs_list) if jobs_list else None
        except (TypeError, ValueError) as e:
            print(f"❌ Ошибка сериализации selected_jobs для {self.email}: {e}")
            self.selected_jobs = None
    
    def get_countries(self):
        """БЕЗОПАСНОЕ получение списка стран"""
        try:
            if self.countries:
                return json.loads(self.countries)
            return []
        except (json.JSONDecodeError, TypeError) as e:
            print(f"❌ Ошибка парсинга countries для {self.email}: {e}")
            return []
    
    def set_countries(self, countries_list):
        """БЕЗОПАСНОЕ сохранение списка стран"""
        try:
            self.countries = json.dumps(countries_list) if countries_list else None
        except (TypeError, ValueError) as e:
            print(f"❌ Ошибка сериализации countries для {self.email}: {e}")
            self.countries = None
    
    def __repr__(self):
        return f'<Subscriber {self.email}>'

class EmailLog(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    subscriber_id = db.Column(db.Integer, db.ForeignKey('subscriber.id'), nullable=True)  # Изменено на nullable=True
    email = db.Column(db.String(120))  # ДОБАВЛЕНО: дублируем email для случаев удаления подписчика
    subject = db.Column(db.String(200))
    jobs_count = db.Column(db.Integer, default=0)
    sent_at = db.Column(db.DateTime, default=datetime.utcnow)
    status = db.Column(db.String(20), default='sent')  # sent, failed
    error_message = db.Column(db.Text)  # ДОБАВЛЕНО: для хранения ошибок!
    
    # Используем backref с lazy='select' для избежания проблем с загрузкой
    subscriber = db.relationship('Subscriber', backref=db.backref('email_logs', lazy='select'), lazy='select')
    
    def __repr__(self):
        return f'<EmailLog {self.email} - {self.status}>'