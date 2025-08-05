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
        return json.loads(self.selected_jobs) if self.selected_jobs else []
    
    def set_selected_jobs(self, jobs_list):
        self.selected_jobs = json.dumps(jobs_list)
    
    def get_countries(self):
        return json.loads(self.countries) if self.countries else []
    
    def set_countries(self, countries_list):
        self.countries = json.dumps(countries_list)
    
    def __repr__(self):
        return f'<Subscriber {self.email}>'

class EmailLog(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    subscriber_id = db.Column(db.Integer, db.ForeignKey('subscriber.id'), nullable=False)
    subject = db.Column(db.String(200))
    jobs_count = db.Column(db.Integer, default=0)
    sent_at = db.Column(db.DateTime, default=datetime.utcnow)
    status = db.Column(db.String(20), default='sent')  # sent, failed
    
    subscriber = db.relationship('Subscriber', backref=db.backref('email_logs', lazy=True))