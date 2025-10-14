# email_worker.py
from app import app, aggregator, additional_aggregators, email_scheduler

if __name__ == '__main__':
    print("⏰ Email worker: запускаю планировщик рассылки")
    email_scheduler(app, aggregator, additional_aggregators)
