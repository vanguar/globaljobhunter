#!/usr/bin/env python3
"""
Планировщик для автоматического запуска JobHunterBot
"""

import schedule
import time
from datetime import datetime
from job_hunter_bot import JobHunterBot

def run_daily_job_search():
    """Ежедневный поиск вакансий"""
    print(f"\n⏰ Запуск ежедневного поиска - {datetime.now()}")
    
    bot = JobHunterBot()
    bot.config["apply_enabled"] = False  # Безопасный режим
    
    try:
        jobs = bot.run_search_only()
        print(f"✅ Ежедневный поиск завершен. Найдено {len(jobs)} вакансий")
    except Exception as e:
        print(f"❌ Ошибка ежедневного поиска: {e}")

def main():
    """Главная функция планировщика"""
    print("⏰ Запуск планировщика JobHunterBot")
    print("📅 Расписание: каждый день в 09:00")
    
    # Планируем запуск каждый день в 9 утра
    schedule.every().day.at("09:00").do(run_daily_job_search)
    
    # Дополнительно - каждые 6 часов
    # schedule.every(6).hours.do(run_daily_job_search)
    
    print("✅ Планировщик запущен. Нажмите Ctrl+C для остановки")
    
    try:
        while True:
            schedule.run_pending()
            time.sleep(60)  # Проверяем каждую минуту
            
    except KeyboardInterrupt:
        print("\n⏹️ Планировщик остановлен")

if __name__ == "__main__":
    main()