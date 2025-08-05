#!/usr/bin/env python3
"""
JobHunterBot v2.1 - Интерактивная версия с выбором страны
"""

import os
import json
import time
from datetime import datetime
from typing import List, Dict
from src.scraper.final_scraper import FinalJoobleScaper
from src.applier.job_applier import JobApplier

class JobHunterBot:
    def __init__(self):
        """
        Главный класс JobHunterBot
        """
        self.config = {
            "search_keywords": [],
            "search_locations": [],
            "search_country": "Deutschland",
            "max_jobs_per_search": 15,
            "apply_enabled": False,
            "delay_between_applications": 30,
            "save_results": True,
            "max_pages": 1  # ЖЕСТКО ограничиваем 1 страницей - НЕТ БЛОКИРОВОК!
        }
        
        self.countries = {
            "1": {"name": "Германия", "domain": "de.jooble.org", "code": "Deutschland"},
            "2": {"name": "США", "domain": "us.jooble.org", "code": "United States"},
            "3": {"name": "Великобритания", "domain": "uk.jooble.org", "code": "United Kingdom"},
            "4": {"name": "Канада", "domain": "ca.jooble.org", "code": "Canada"},
            "5": {"name": "Австралия", "domain": "au.jooble.org", "code": "Australia"},
            "6": {"name": "Франция", "domain": "fr.jooble.org", "code": "France"},
            "7": {"name": "Нидерланды", "domain": "nl.jooble.org", "code": "Netherlands"}
        }
        
        self.results_file = "data/job_search_results.json"
        self.ensure_data_directory()
    
    def select_country(self):
        """Выбор страны для поиска"""
        print("\n🌍 Выберите страну для поиска:")
        print("=" * 40)
        
        for key, country in self.countries.items():
            print(f"{key}. {country['name']} ({country['domain']})")
        
        try:
            choice = input("\nВыберите страну (1-7, по умолчанию 1 - Германия): ").strip()
            
            if choice in self.countries:
                selected = self.countries[choice]
                self.config["search_country"] = selected["code"]
                self.config["country_domain"] = selected["domain"]
                print(f"✅ Выбрана страна: {selected['name']}")
                return selected
            else:
                # По умолчанию Германия
                self.config["search_country"] = "Deutschland"
                self.config["country_domain"] = "de.jooble.org"
                print("✅ Выбрана страна по умолчанию: Германия")
                return self.countries["1"]
                
        except:
            self.config["search_country"] = "Deutschland"
            self.config["country_domain"] = "de.jooble.org"
            print("✅ Выбрана страна по умолчанию: Германия")
            return self.countries["1"]
    
    def get_user_preferences(self):
        """Запрашиваем предпочтения пользователя"""
        print("🤖 JobHunterBot v2.1 - Интерактивная настройка")
        print("=" * 50)
        
        # Выбираем страну
        selected_country = self.select_country()
        
        # Запрашиваем вакансию
        print(f"\n🎯 Какую вакансию ищем в {selected_country['name']}?")
        print("Примеры популярных вакансий:")
        print("  • Python Developer")
        print("  • Java Developer") 
        print("  • Frontend Developer")
        print("  • Backend Developer")
        print("  • Data Analyst")
        print("  • Marketing Manager")
        print("  • DevOps Engineer")
        
        keywords_input = input("\nВведите название вакансии: ").strip()
        if keywords_input:
            self.config["search_keywords"] = [keywords_input]
        else:
            self.config["search_keywords"] = ["Python Developer"]
        
        # Запрашиваем города с примерами для выбранной страны
        city_examples = {
            "Deutschland": "Berlin, München, Hamburg, Frankfurt, Köln",
            "United States": "New York, Los Angeles, Chicago, San Francisco, Seattle",
            "United Kingdom": "London, Manchester, Birmingham, Edinburgh, Bristol",
            "Canada": "Toronto, Vancouver, Montreal, Calgary, Ottawa",
            "Australia": "Sydney, Melbourne, Brisbane, Perth, Adelaide",
            "France": "Paris, Lyon, Marseille, Toulouse, Bordeaux",
            "Netherlands": "Amsterdam, Rotterdam, The Hague, Utrecht, Eindhoven"
        }
        
        examples = city_examples.get(self.config["search_country"], "Any city")
        
        print(f"\n📍 В каких городах искать?")
        print(f"Примеры для {selected_country['name']}: {examples}")
        print("Можно ввести несколько через запятую или оставить пустым для поиска по всей стране")
        
        locations_input = input("Введите город(а): ").strip()
        if locations_input:
            locations = [loc.strip() for loc in locations_input.split(",") if loc.strip()]
            self.config["search_locations"] = locations
        else:
            self.config["search_locations"] = [self.config["search_country"]]
        
        # Показываем настройки
        print(f"\n✅ Настройки поиска:")
        print(f"🌍 Страна: {selected_country['name']}")
        print(f"🎯 Вакансия: {', '.join(self.config['search_keywords'])}")
        print(f"📍 Локации: {', '.join(self.config['search_locations'])}")
        print(f"📄 Страниц: {self.config['max_pages']} (ограничено для избежания блокировок)")
        
        # Подтверждение
        confirm = input("\nПродолжить с этими настройками? (Enter или 'да'): ").strip()
        if confirm.lower() not in ['', 'yes', 'y', 'да', 'да']:
            print("❌ Поиск отменен")
            return False
        
        return True
    
    def ensure_data_directory(self):
        """Создание папки для данных"""
        os.makedirs("data", exist_ok=True)
    
    def load_previous_results(self) -> List[Dict]:
        """Загрузка предыдущих результатов"""
        if os.path.exists(self.results_file):
            try:
                with open(self.results_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except:
                return []
        return []
    
    def save_results(self, jobs: List[Dict]):
        """Сохранение результатов"""
        if self.config["save_results"]:
            try:
                all_jobs = self.load_previous_results()
                existing_links = {job.get("link") for job in all_jobs}
                new_jobs = [job for job in jobs if job.get("link") not in existing_links]
                
                all_jobs.extend(new_jobs)
                
                with open(self.results_file, 'w', encoding='utf-8') as f:
                    json.dump(all_jobs, f, ensure_ascii=False, indent=2)
                
                print(f"💾 Сохранено {len(new_jobs)} новых вакансий (всего в базе: {len(all_jobs)})")
                
            except Exception as e:
                print(f"❌ Ошибка сохранения: {e}")
    
    def search_jobs_safe(self) -> List[Dict]:
        """Безопасный поиск БЕЗ блокировок"""
        all_jobs = []
        
        print("\n🔍 Начинаем БЕЗОПАСНЫЙ поиск вакансий...")
        print("🛡️ Только первые страницы - никаких блокировок!")
        print("=" * 60)
        
        total_searches = len(self.config["search_keywords"]) * len(self.config["search_locations"])
        current_search = 0
        
        for keyword in self.config["search_keywords"]:
            for location in self.config["search_locations"]:
                current_search += 1
                print(f"\n🔍 Поиск {current_search}/{total_searches}: '{keyword}' в '{location}'")
                
                try:
                    # Создаем скрапер с ограничением в 1 страницу
                    with FinalJoobleScaper(headless=False) as scraper:
                        # ПРИНУДИТЕЛЬНО только 1 страница
                        jobs = scraper.search_jobs(
                            keywords=keyword,
                            location=location,
                            max_pages=1  # ЖЕСТКО 1 страница - НЕТ БЛОКИРОВОК!
                        )
                        
                        if jobs:
                            print(f"✅ Найдено {len(jobs)} вакансий")
                            all_jobs.extend(jobs)
                            
                            # Показываем лучшие найденные вакансии
                            print("🏆 Лучшие найденные:")
                            for i, job in enumerate(jobs[:3], 1):
                                salary_info = f" - {job['salary']}" if job['salary'] != "Не указана" else ""
                                print(f"   {i}. {job['title']}{salary_info}")
                        else:
                            print("⚠️ Вакансии не найдены")
                            
                except Exception as e:
                    print(f"❌ Ошибка поиска '{keyword}' в '{location}': {e}")
                
                # Пауза между поисками для избежания блокировок
                if current_search < total_searches:
                    print("⏳ Пауза 8 секунд...")
                    time.sleep(8)
        
        # Убираем дубликаты
        unique_jobs = self._remove_duplicates(all_jobs)
        
        print(f"\n📊 ИТОГО: {len(unique_jobs)} уникальных вакансий")
        if len(all_jobs) > len(unique_jobs):
            print(f"📊 Удалено дубликатов: {len(all_jobs) - len(unique_jobs)}")
        
        return unique_jobs
    
    def _remove_duplicates(self, jobs: List[Dict]) -> List[Dict]:
        """Удаление дубликатов по ссылке"""
        seen_links = set()
        unique_jobs = []
        
        for job in jobs:
            link = job.get("link", "")
            if link and link not in seen_links:
                seen_links.add(link)
                unique_jobs.append(job)
        
        return unique_jobs
    
    def show_top_jobs(self, jobs: List[Dict], count: int = 10):
        """Показываем топ найденных вакансий"""
        if not jobs:
            print("❌ Нет вакансий для отображения")
            return
        
        print(f"\n🏆 ТОП-{min(count, len(jobs))} НАЙДЕННЫХ ВАКАНСИЙ:")
        print("=" * 80)
        
        for i, job in enumerate(jobs[:count], 1):
            print(f"\n{i}. 🎯 {job['title']}")
            print(f"   🏢 Компания: {job['company']}")
            print(f"   📍 Локация: {job['location']}")
            print(f"   💰 Зарплата: {job['salary']}")
            print(f"   📅 Дата: {job['date']}")
            print(f"   🔗 {job['link'][:70]}...")
            
            if job['snippet'] and len(job['snippet']) > 10:
                print(f"   📝 {job['snippet'][:120]}...")
        
        if len(jobs) > count:
            print(f"\n... и еще {len(jobs) - count} вакансий")
        
        print("=" * 80)
    
    def generate_smart_report(self, jobs: List[Dict]):
        """Умный отчет с анализом"""
        print("\n" + "=" * 80)
        print("📊 УМНЫЙ ОТЧЕТ JOBHUNTERBOT v2.1")
        print("=" * 80)
        
        print(f"🕒 Время: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"🌍 Страна: {self.config.get('search_country', 'Deutschland')}")
        print(f"🎯 Поиск: {', '.join(self.config['search_keywords'])}")
        print(f"📍 Локации: {', '.join(self.config['search_locations'])}")
        print(f"🔍 Найдено: {len(jobs)} вакансий")
        
        if jobs:
            # Анализ зарплат
            with_salary = [job for job in jobs if job.get('salary', 'Не указана') != 'Не указана']
            
            # Анализ компаний
            companies = {}
            locations = {}
            
            for job in jobs:
                company = job.get('company', 'Не указана')
                if company != 'Не указана':
                    companies[company] = companies.get(company, 0) + 1
                
                location = job.get('location', 'Не указана')
                if location != 'Не указана':
                    locations[location] = locations.get(location, 0) + 1
            
            print(f"\n📈 АНАЛИЗ:")
            print(f"💰 Вакансий с зарплатой: {len(with_salary)}/{len(jobs)} ({len(with_salary)/len(jobs)*100:.1f}%)")
            print(f"🏢 Уникальных компаний: {len(companies)}")
            print(f"📍 Разных локаций: {len(locations)}")
            
            # Зарплаты
            if with_salary:
                print(f"\n💰 ВАКАНСИИ С УКАЗАННОЙ ЗАРПЛАТОЙ:")
                for job in with_salary[:5]:
                    print(f"   • {job['title']} - {job['salary']}")
            
            # Топ компаний
            if companies:
                top_companies = sorted(companies.items(), key=lambda x: x[1], reverse=True)[:5]
                print(f"\n🏆 ТОП КОМПАНИЙ:")
                for company, count in top_companies:
                    print(f"   • {company}: {count} вакансий")
        
        # Сохраняем умный отчет
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        report_file = f"data/smart_report_{timestamp}.txt"
        
        try:
            with open(report_file, 'w', encoding='utf-8') as f:
                f.write(f"JobHunterBot v2.1 Smart Report\n")
                f.write(f"Generated: {datetime.now()}\n")
                f.write(f"Country: {self.config.get('search_country')}\n")
                f.write(f"Keywords: {', '.join(self.config['search_keywords'])}\n")
                f.write(f"Locations: {', '.join(self.config['search_locations'])}\n")
                f.write(f"Total jobs: {len(jobs)}\n")
                f.write(f"Jobs with salary: {len(with_salary)}\n\n")
                
                f.write("=== ALL JOBS ===\n\n")
                for i, job in enumerate(jobs, 1):
                    f.write(f"{i}. {job['title']}\n")
                    f.write(f"   Company: {job['company']}\n")
                    f.write(f"   Location: {job['location']}\n")
                    f.write(f"   Salary: {job['salary']}\n")
                    f.write(f"   Date: {job['date']}\n")
                    f.write(f"   Link: {job['link']}\n\n")
            
            print(f"💾 Умный отчет сохранен: {report_file}")
            
        except Exception as e:
            print(f"⚠️ Ошибка сохранения отчета: {e}")
        
        print("=" * 80)
    
    def run_smart_search(self):
        """Умный интерактивный поиск"""
        # Получаем настройки от пользователя
        if not self.get_user_preferences():
            return []
        
        print(f"\n🚀 Запускаем умный поиск...")
        
        # Безопасный поиск БЕЗ блокировок
        jobs = self.search_jobs_safe()
        
        # Обрабатываем результаты
        if jobs:
            self.save_results(jobs)
            self.show_top_jobs(jobs, 15)
            self.generate_smart_report(jobs)
            
            # Показать все ссылки?
            show_all = input(f"\nПоказать ссылки на все {len(jobs)} вакансий? (y/n): ").strip().lower()
            if show_all in ['y', 'yes', 'да']:
                print(f"\n🔗 ВСЕ ССЫЛКИ НА ВАКАНСИИ:")
                for i, job in enumerate(jobs, 1):
                    salary_info = f" ({job['salary']})" if job['salary'] != "Не указана" else ""
                    print(f"{i:2d}. {job['title']}{salary_info}")
                    print(f"     {job['link']}")
            
        else:
            print("❌ Вакансии не найдены")
            print("💡 Рекомендации:")
            print("   • Попробуйте другие ключевые слова")
            print("   • Выберите другие города или всю страну")
            print("   • Попробуйте другую страну")
            print("   • Запустите поиск позже")
        
        return jobs

def main():
    """Главная функция"""
    print("🤖 JobHunterBot v2.1")
    print("🌍 Умный поиск вакансий по всему миру")
    print("🛡️ Защита от блокировок")
    
    bot = JobHunterBot()
    
    try:
        jobs = bot.run_smart_search()
        
        if jobs:
            print(f"\n🎉 Поиск успешно завершен!")
            print(f"📊 Найдено: {len(jobs)} уникальных вакансий")
            print(f"💾 Все данные сохранены в папке data/")
            
            with_salary = len([j for j in jobs if j.get('salary', 'Не указана') != 'Не указана'])
            if with_salary > 0:
                print(f"💰 Из них с зарплатой: {with_salary}")
        
    except KeyboardInterrupt:
        print("\n\n⏹️ Поиск остановлен пользователем")
    except Exception as e:
        print(f"\n❌ Критическая ошибка: {e}")

if __name__ == "__main__":
    main()