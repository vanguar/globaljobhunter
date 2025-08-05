#!/usr/bin/env python3
"""
GlobalJobHunterBot v3.0 - Глобальная система поиска работы
Для всех соискателей с учетом языковых возможностей
"""

import os
import json
import time
import random
from datetime import datetime
from typing import List, Dict, Optional
from dataclasses import dataclass
from src.scraper.final_scraper import FinalJoobleScaper

@dataclass
class Country:
    name: str
    code: str
    language: str
    currency: str
    major_cities: List[str]
    job_sites: List[str]
    popular_jobs: List[str]
    refugee_support: bool = False  # Поддержка беженцев
    jobs_without_language: bool = False  # Работа без языка доступна

class GlobalJobHunterBot:
    def __init__(self):
        """Глобальная система поиска работы для всех"""
        self.config = {
            "max_jobs_per_search": 30,
            "max_pages_per_site": 2,
            "delay_between_searches": 8,
            "save_results": True,
            "language_filter": None,  # Будет установлен при выборе
            "include_refugee_jobs": False  # Специальные вакансии для беженцев
        }
        
        self.countries = self._init_countries()
        self.job_categories = self._init_job_categories()
        self.results_file = "data/global_job_search_results.json"
        self.ensure_data_directory()
    
    def _init_countries(self) -> Dict[str, Country]:
        """ВСЕ страны мира с информацией о языковых требованиях"""
        return {
            # ЕВРОПА
            "DE": Country("Германия", "DE", "Немецкий", "EUR",
                          ["Берлин", "Мюнхен", "Гамбург", "Франкфурт", "Кёльн", "Штутгарт", "Дюссельдорф", "Дрезден"],
                          ["stepstone.de", "indeed.de", "xing.com", "monster.de"],
                          ["Водитель", "Курьер", "Разнорабочий", "Официант", "Медсестра", "Программист"],
                          refugee_support=True, jobs_without_language=True),
            
            "PL": Country("Польша", "PL", "Польский", "PLN",
                          ["Варшава", "Краков", "Гданьск", "Вроцлав", "Познань", "Лодзь", "Катовице", "Люблин"],
                          ["indeed.pl", "pracuj.pl", "olx.pl"],
                          ["Kierowca", "Kurier", "Pracownik fizyczny", "Kelner", "Pielęgniarka", "Programista"],
                          refugee_support=True, jobs_without_language=True),
            
            "CZ": Country("Чехия", "CZ", "Чешский", "CZK",
                          ["Прага", "Брно", "Острава", "Пльзень", "Либерец", "Оломоуц"],
                          ["indeed.cz", "jobs.cz", "prace.cz"],
                          ["Řidič", "Kurýr", "Dělník", "Číšník", "Sestřička", "Programátor"],
                          refugee_support=True, jobs_without_language=True),
            
            "SK": Country("Словакия", "SK", "Словацкий", "EUR",
                          ["Братислава", "Кошице", "Прешов", "Жилина", "Банска-Бистрица"],
                          ["indeed.sk", "profesia.sk", "jobs.sk"],
                          ["Vodič", "Kuriér", "Robotník", "Čašník", "Zdravotná sestra", "Programátor"],
                          refugee_support=True, jobs_without_language=True),
            
            "IT": Country("Италия", "IT", "Итальянский", "EUR",
                          ["Рим", "Милан", "Неаполь", "Турин", "Флоренция", "Болонья", "Венеция"],
                          ["indeed.it", "infojobs.it", "monster.it"],
                          ["Autista", "Corriere", "Operaio", "Cameriere", "Badante", "Programmatore"],
                          refugee_support=True, jobs_without_language=True),
            
            "ES": Country("Испания", "ES", "Испанский", "EUR",
                          ["Мадрид", "Барселона", "Валенсия", "Севилья", "Бильбао", "Малага"],
                          ["indeed.es", "infojobs.net", "infoempleo.com"],
                          ["Conductor", "Repartidor", "Obrero", "Camarero", "Cuidador", "Programador"],
                          refugee_support=True, jobs_without_language=True),
            
            "FR": Country("Франция", "FR", "Французский", "EUR",
                          ["Париж", "Лион", "Марсель", "Тулуза", "Бордо", "Ницца", "Страсбург"],
                          ["indeed.fr", "leboncoin.fr", "poleemploi.fr"],
                          ["Chauffeur", "Livreur", "Ouvrier", "Serveur", "Aide à domicile", "Développeur"],
                          refugee_support=True, jobs_without_language=True),
            
            "GB": Country("Великобритания", "GB", "Английский", "GBP",
                          ["Лондон", "Манчестер", "Бирмингем", "Эдинбург", "Бристоль", "Глазго"],
                          ["indeed.co.uk", "reed.co.uk", "totaljobs.com"],
                          ["Driver", "Courier", "Labourer", "Waiter", "Carer", "Developer"],
                          refugee_support=True, jobs_without_language=True),
            
            "NL": Country("Нидерланды", "NL", "Голландский", "EUR",
                          ["Амстердам", "Роттердам", "Гаага", "Утрехт", "Эйндховен"],
                          ["indeed.nl", "nationale-vacaturebank.nl"],
                          ["Chauffeur", "Koerier", "Arbeider", "Ober", "Zorgverlener", "Ontwikkelaar"],
                          refugee_support=True, jobs_without_language=True),
            
            "CH": Country("Швейцария", "CH", "Немецкий", "CHF",
                          ["Цюрих", "Женева", "Базель", "Берн", "Лозанна"],
                          ["indeed.ch", "jobs.ch", "jobup.ch"],
                          ["Fahrer", "Kurier", "Arbeiter", "Kellner", "Betreuer", "Entwickler"],
                          refugee_support=True, jobs_without_language=False),
            
            "SE": Country("Швеция", "SE", "Шведский", "SEK",
                          ["Стокгольм", "Гётеборг", "Мальмё", "Уппсала"],
                          ["indeed.se", "thelocal.se", "arbetsformedlingen.se"],
                          ["Förare", "Kurir", "Arbetare", "Servitör", "Vårdare", "Utvecklare"],
                          refugee_support=True, jobs_without_language=True),
            
            "NO": Country("Норвегия", "NO", "Норвежский", "NOK",
                          ["Осло", "Берген", "Тронхейм", "Ставангер"],
                          ["indeed.no", "nav.no", "finn.no"],
                          ["Sjåfør", "Bud", "Arbeider", "Servitør", "Omsorgsperson", "Utvikler"],
                          refugee_support=True, jobs_without_language=True),
            
            "DK": Country("Дания", "DK", "Датский", "DKK",
                          ["Копенгаген", "Орхус", "Оденсе", "Ольборг"],
                          ["indeed.dk", "jobindex.dk", "thehub.dk"],
                          ["Chauffør", "Bud", "Arbejder", "Tjener", "Omsorgsmedarbejder", "Udvikler"],
                          refugee_support=True, jobs_without_language=True),
            
            "FI": Country("Финляндия", "FI", "Финский", "EUR",
                          ["Хельсинки", "Эспоо", "Тампере", "Турку"],
                          ["indeed.fi", "monster.fi", "te-palvelut.fi"],
                          ["Kuljettaja", "Kuriiri", "Työntekijä", "Tarjoilija", "Hoitaja", "Kehittäjä"],
                          refugee_support=True, jobs_without_language=True),
            
            "BE": Country("Бельгия", "BE", "Голландский", "EUR",
                          ["Брюссель", "Антверпен", "Гент", "Льеж"],
                          ["indeed.be", "stepstone.be", "monster.be"],
                          ["Chauffeur", "Koerier", "Arbeider", "Ober", "Verzorger", "Ontwikkelaar"],
                          refugee_support=True, jobs_without_language=True),
            
            "AT": Country("Австрия", "AT", "Немецкий", "EUR",
                          ["Вена", "Зальцбург", "Инсбрук", "Линц", "Грац"],
                          ["indeed.at", "stepstone.at", "karriere.at"],
                          ["Fahrer", "Kurier", "Arbeiter", "Kellner", "Betreuer", "Entwickler"],
                          refugee_support=True, jobs_without_language=True),
            
            "IE": Country("Ирландия", "IE", "Английский", "EUR",
                          ["Дублин", "Корк", "Голуэй", "Лимерик"],
                          ["indeed.ie", "jobs.ie", "irishjobs.ie"],
                          ["Driver", "Courier", "Labourer", "Waiter", "Carer", "Developer"],
                          refugee_support=True, jobs_without_language=True),
            
            "PT": Country("Португалия", "PT", "Португальский", "EUR",
                          ["Лиссабон", "Порту", "Брага", "Коимбра"],
                          ["indeed.pt", "net-empregos.com"],
                          ["Motorista", "Estafeta", "Operário", "Empregado", "Cuidador", "Programador"],
                          refugee_support=True, jobs_without_language=True),
            
            # СЕВЕРНАЯ АМЕРИКА
            "US": Country("США", "US", "Английский", "USD",
                          ["Нью-Йорк", "Лос-Анджелес", "Чикаго", "Сан-Франциско", "Сиэтл", "Бостон"],
                          ["indeed.com", "linkedin.com", "monster.com"],
                          ["Driver", "Delivery Worker", "Construction Worker", "Server", "Caregiver", "Developer"],
                          refugee_support=True, jobs_without_language=True),
            
            "CA": Country("Канада", "CA", "Английский", "CAD",
                          ["Торонто", "Ванкувер", "Монреаль", "Калгари", "Оттава"],
                          ["indeed.ca", "workopolis.com", "monster.ca"],
                          ["Driver", "Courier", "Labourer", "Server", "Caregiver", "Developer"],
                          refugee_support=True, jobs_without_language=True),
            
            # ОКЕАНИЯ
            "AU": Country("Австралия", "AU", "Английский", "AUD",
                          ["Сидней", "Мельбурн", "Брисбен", "Перт", "Аделаида"],
                          ["indeed.com.au", "seek.com.au"],
                          ["Driver", "Courier", "Labourer", "Waiter", "Care Worker", "Developer"],
                          refugee_support=True, jobs_without_language=True),
            
            "NZ": Country("Новая Зеландия", "NZ", "Английский", "NZD",
                          ["Окленд", "Веллингтон", "Крайстчерч"],
                          ["indeed.co.nz", "seek.co.nz", "trademe.co.nz"],
                          ["Driver", "Courier", "Labourer", "Waiter", "Support Worker", "Developer"],
                          refugee_support=True, jobs_without_language=True),
            
            # АЗИЯ
            "JP": Country("Япония", "JP", "Японский", "JPY",
                          ["Токио", "Осака", "Йокогама", "Нагоя"],
                          ["indeed.com", "rikunabi.com", "doda.jp"],
                          ["運転手", "配達員", "作業員", "ウェイター", "介護士", "プログラマー"],
                          refugee_support=False, jobs_without_language=False),
            
            "SG": Country("Сингапур", "SG", "Английский", "SGD",
                          ["Сингапур"],
                          ["indeed.com.sg", "jobsbank.gov.sg"],
                          ["Driver", "Delivery Person", "Worker", "Server", "Helper", "Engineer"],
                          refugee_support=False, jobs_without_language=True),
        }
    
    def _init_job_categories(self) -> Dict[str, List[str]]:
        """ВСЕ профессии с учетом языковых требований"""
        return {
            # РАБОТА БЕЗ ЯЗЫКА (физическая работа, минимальное общение)
            "Без знания языка": [
                "Водитель такси", "Водитель грузовика", "Курьер", "Доставщик еды", "Курьер-водитель",
                "Разнорабочий", "Строитель", "Грузчик", "Складской работник", "Уборщик", "Садовник",
                "Посудомойщик", "Помощник повара", "Кухонный работник", "Упаковщик", "Сортировщик",
                "Driver", "Delivery Driver", "Courier", "Labourer", "Warehouse Worker", "Cleaner",
                "Kitchen Assistant", "Dishwasher", "Packer", "Construction Worker", "Janitor"
            ],
            
            # МИНИМАЛЬНОЕ ЗНАНИЕ ЯЗЫКА (базовое общение)
            "Базовый язык": [
                "Официант", "Бармен", "Продавец", "Кассир", "Охранник", "Сиделка", "Няня",
                "Домработница", "Уход за пенсионерами", "Медсестра помощник", "Гувернантка",
                "Waiter", "Bartender", "Shop Assistant", "Cashier", "Security Guard", "Caregiver",
                "Nanny", "Housekeeper", "Care Worker", "Healthcare Assistant"
            ],
            
            # ХОРОШЕЕ ЗНАНИЕ ЯЗЫКА (профессиональное общение)
            "Профессиональный язык": [
                "Медсестра", "Учитель", "Переводчик", "Администратор", "Менеджер", "Продавец-консультант",
                "Nurse", "Teacher", "Translator", "Administrator", "Manager", "Sales Consultant",
                "Customer Service", "Receptionist", "Office Manager", "Account Manager"
            ],
            
            # IT И ТЕХНИЧЕСКИЕ (часто английский язык)
            "IT и технические": [
                "Программист", "Python Developer", "Java Developer", "Frontend Developer",
                "Backend Developer", "DevOps Engineer", "Data Scientist", "System Administrator",
                "Software Engineer", "Web Developer", "Mobile Developer", "QA Engineer",
                "Network Engineer", "Database Administrator", "Cybersecurity Specialist"
            ],
            
            # СПЕЦИАЛЬНЫЕ ПРОГРАММЫ ДЛЯ БЕЖЕНЦЕВ
            "Программы для беженцев": [
                "Refugee support program", "Integration job", "Language learning job",
                "Newcomer program", "Settlement worker", "Community support",
                "Програма для біженців", "Інтеграційна робота", "Програма адаптації"
            ]
        }
    
    def select_language_preferences(self) -> Dict:
        """Выбор языковых предпочтений соискателя"""
        print("🗣️ ЯЗЫКОВЫЕ ВОЗМОЖНОСТИ")
        print("=" * 40)
        print("Для более точного поиска работы укажите ваш уровень языка:")
        print()
        print("1. 🔇 Не знаю местный язык (ищем работу без языковых требований)")
        print("2. 🗨️ Базовый уровень (простое общение с клиентами)")
        print("3. 💼 Хороший уровень (профессиональное общение)")
        print("4. 🌐 Владею английским (IT и международные компании)")
        print("5. 🤷 Все варианты (покажи всё, что доступно)")
        
        choice = input("\nВаш выбор (1-5): ").strip()
        
        language_config = {
            "level": "all",
            "categories": [],
            "search_terms": [],
            "description": ""
        }
        
        if choice == "1":
            language_config.update({
                "level": "no_language",
                "categories": ["Без знания языка"],
                "search_terms": ["без языка", "no language", "physical work", "warehouse", "delivery"],
                "description": "Работа без знания местного языка"
            })
            
        elif choice == "2":
            language_config.update({
                "level": "basic",
                "categories": ["Без знания языка", "Базовый язык"],
                "search_terms": ["официант", "продавец", "waiter", "shop assistant", "basic"],
                "description": "Работа с базовым знанием языка"
            })
            
        elif choice == "3":
            language_config.update({
                "level": "professional",
                "categories": ["Базовый язык", "Профессиональный язык"],
                "search_terms": ["медсестра", "менеджер", "nurse", "manager", "administrator"],
                "description": "Работа для владеющих языком"
            })
            
        elif choice == "4":
            language_config.update({
                "level": "english",
                "categories": ["IT и технические"],
                "search_terms": ["developer", "engineer", "programmer", "analyst", "english"],
                "description": "IT и работа на английском"
            })
            
        else:  # choice == "5" или любое другое
            language_config.update({
                "level": "all",
                "categories": list(self.job_categories.keys()),
                "search_terms": ["all"],
                "description": "Все доступные вакансии"
            })
        
        return language_config
    
    def select_refugee_status(self) -> bool:
        """Выбор статуса беженца для специальных программ"""
        print("\n🏠 СТАТУС ПЕРЕСЕЛЕНИЯ")
        print("=" * 30)
        print("Являетесь ли вы беженцем или вынужденным переселенцем?")
        print("(Многие страны имеют специальные программы поддержки)")
        print()
        print("1. ✅ Да, нужны программы поддержки беженцев")
        print("2. ❌ Нет, обычный поиск работы")
        
        choice = input("\nВаш выбор (1-2): ").strip()
        
        if choice == "1":
            print("✅ Будем искать специальные программы для беженцев")
            return True
        else:
            print("✅ Обычный поиск работы")
            return False
    
    def select_global_search(self) -> bool:
        """Интерактивный выбор глобального поиска"""
        print("🌍 GlobalJobHunterBot v3.0")
        print("🌐 Глобальный поиск работы для всех соискателей")
        print("=" * 60)
        
        # Выбор языковых предпочтений
        language_config = self.select_language_preferences()
        self.config["language_config"] = language_config
        
        # Выбор статуса беженца
        refugee_status = self.select_refugee_status()
        self.config["include_refugee_jobs"] = refugee_status
        
        # Показать подходящие страны
        suitable_countries = []
        for code, country in self.countries.items():
            if language_config["level"] == "no_language":
                if country.jobs_without_language:
                    suitable_countries.append(code)
            elif language_config["level"] == "all":
                suitable_countries.append(code)
            else:
                suitable_countries.append(code)  # Все страны для других уровней
        
        print(f"\n🌍 ПОДХОДЯЩИЕ СТРАНЫ ({len(suitable_countries)} из {len(self.countries)}):")
        
        # Группируем по языковым возможностям
        for code in suitable_countries[:10]:  # Показываем первые 10
            country = self.countries[code]
            refugee_mark = "🏠" if country.refugee_support else ""
            lang_mark = "🔇" if country.jobs_without_language else "🗣️"
            print(f"   • {country.name} ({country.currency}) {lang_mark} {refugee_mark}")
        
        if len(suitable_countries) > 10:
            print(f"   ... и еще {len(suitable_countries) - 10} стран")
        
        # Выбор стран
        print(f"\n🌍 Выберите страны для поиска:")
        print("1. Все подходящие страны")
        print("2. Только страны с поддержкой беженцев") 
        print("3. Только страны с работой без языка")
        print("4. Конкретные страны")
        
        choice = input("Ваш выбор (1-4): ").strip()
        
        if choice == "1":
            selected_countries = suitable_countries
        elif choice == "2":
            selected_countries = [code for code in suitable_countries 
                                  if self.countries[code].refugee_support]
        elif choice == "3":
            selected_countries = [code for code in suitable_countries 
                                  if self.countries[code].jobs_without_language]
        else:
            print("Введите коды стран через запятую (DE,PL,CZ):")
            country_input = input().strip().upper()
            selected_countries = [c.strip() for c in country_input.split(",") 
                                  if c.strip() in self.countries]
        
        if not selected_countries:
            print("❌ Страны не выбраны")
            return False
        
        self.config["selected_countries"] = selected_countries
        
        # Выбор профессий на основе языкового уровня
        selected_jobs = []
        for category in language_config["categories"]:
            if category in self.job_categories:
                selected_jobs.extend(self.job_categories[category])
        
        # Добавляем программы для беженцев если нужно
        if refugee_status and "Программы для беженцев" in self.job_categories:
            selected_jobs.extend(self.job_categories["Программы для беженцев"])
        
        # Ограничиваем количество для начала
        self.config["selected_jobs"] = selected_jobs[:8]
        
        # Показать итоговые настройки
        country_names = [self.countries[code].name for code in selected_countries]
        print(f"\n✅ НАСТРОЙКИ ПОИСКА:")
        print(f"🗣️ Языковой уровень: {language_config['description']}")
        print(f"🏠 Поддержка беженцев: {'Да' if refugee_status else 'Нет'}")
        print(f"🌍 Стран: {len(selected_countries)} ({', '.join(country_names[:3])}{'...' if len(country_names) > 3 else ''})")
        print(f"💼 Типов вакансий: {len(self.config['selected_jobs'])}")
        print(f"🔍 Примеры: {', '.join(self.config['selected_jobs'][:3])}")
        
        confirm = input("\nПродолжить поиск? (Enter/да): ").strip()
        return True
    
    def run_global_search(self) -> List[Dict]:
        """Запуск глобального поиска"""
        if not self.select_global_search():
            return []
        
        all_jobs = []
        countries = self.config["selected_countries"]
        jobs = self.config["selected_jobs"]
        language_config = self.config["language_config"]
        
        print(f"\n🚀 Запускаем глобальный поиск...")
        print(f"🌍 {len(countries)} стран × {len(jobs)} профессий = {len(countries) * len(jobs)} поисков")
        print(f"🗣️ Фильтр: {language_config['description']}")
        
        search_count = 0
        total_searches = len(countries) * len(jobs)
        
        for country_code in countries:
            country = self.countries[country_code]
            print(f"\n🌍 === {country.name.upper()} ===")
            
            for job in jobs:
                search_count += 1
                print(f"\n🔍 Поиск {search_count}/{total_searches}: '{job}' в {country.name}")
                
                try:
                    # Используем наш проверенный скрапер
                    with FinalJoobleScaper(headless=False) as scraper:
                        # Поиск вакансий
                        country_jobs = scraper.search_jobs(
                            keywords=job,
                            location=country.major_cities[0],
                            max_pages=2
                        )
                        
                        if country_jobs:
                            # Добавляем метаданные
                            for cj in country_jobs:
                                cj["search_country"] = country.name
                                cj["search_job"] = job
                                cj["country_language"] = country.language
                                cj["refugee_support"] = country.refugee_support
                                cj["jobs_without_language"] = country.jobs_without_language
                                cj["language_filter"] = language_config["level"]
                            
                            all_jobs.extend(country_jobs)
                            print(f"✅ Найдено {len(country_jobs)} вакансий")
                        else:
                            print(f"⚠️ Вакансии не найдены")
                            
                except Exception as e:
                    print(f"❌ Ошибка поиска: {e}")
                
                # Пауза между поисками
                if search_count < total_searches:
                    time.sleep(self.config["delay_between_searches"])
        
        # Удаляем дубликаты
        unique_jobs = self._remove_duplicates(all_jobs)
        
        print(f"\n📊 ИТОГО:")
        print(f"🔍 Найдено: {len(unique_jobs)} уникальных вакансий")
        print(f"🗑️ Удалено дубликатов: {len(all_jobs) - len(unique_jobs)}")
        
        # Сохраняем и показываем результаты
        if self.config["save_results"]:
            self._save_global_results(unique_jobs)
        
        self._show_global_results(unique_jobs)
        
        return unique_jobs
    
    def _remove_duplicates(self, jobs: List[Dict]) -> List[Dict]:
        """Удаление дубликатов"""
        seen_links = set()
        unique_jobs = []
        
        for job in jobs:
            link = job.get("link", "")
            if link and link not in seen_links:
                seen_links.add(link)
                unique_jobs.append(job)
        
        return unique_jobs
    
    def _save_global_results(self, jobs: List[Dict]):
        """Сохранение глобальных результатов"""
        try:
            with open(self.results_file, 'w', encoding='utf-8') as f:
                json.dump(jobs, f, ensure_ascii=False, indent=2)
            
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            report_file = f"data/global_report_{timestamp}.txt"
            
            with open(report_file, 'w', encoding='utf-8') as f:
                f.write("🌍 GlobalJobHunterBot v3.0 - Отчет\n")
                f.write(f"📅 Время: {datetime.now()}\n")
                f.write(f"🗣️ Языковой фильтр: {self.config['language_config']['description']}\n")
                f.write(f"🔍 Всего вакансий: {len(jobs)}\n\n")
                
                # Группировка по странам
                by_country = {}
                refugee_jobs = 0
                no_language_jobs = 0
                
                for job in jobs:
                    country = job.get("search_country", "Неизвестно")
                    if country not in by_country:
                        by_country[country] = []
                    by_country[country].append(job)
                
                    if job.get("refugee_support"):
                        refugee_jobs += 1
                    if job.get("jobs_without_language"):
                        no_language_jobs += 1
                
                f.write("📊 СТАТИСТИКА:\n")
                f.write(f"🏠 Поддержка беженцев: {refugee_jobs} вакансий\n")
                f.write(f"🔇 Без знания языка: {no_language_jobs} вакансий\n\n")
                
                f.write("📊 ПО СТРАНАМ:\n")
                for country, country_jobs in by_country.items():
                    f.write(f"🌍 {country}: {len(country_jobs)} вакансий\n")
                
                f.write(f"\n{'='*50}\n")
                f.write("📋 ВСЕ ВАКАНСИИ:\n\n")
                
                for i, job in enumerate(jobs, 1):
                    refugee_mark = "🏠" if job.get("refugee_support") else ""
                    lang_mark = "🔇" if job.get("jobs_without_language") else "🗣️"
                    
                    f.write(f"{i}. {job['title']} {refugee_mark} {lang_mark}\n")
                    f.write(f"   🏢 {job['company']}\n") 
                    f.write(f"   📍 {job['location']}\n")
                    f.write(f"   💰 {job['salary']}\n")
                    f.write(f"   🌍 {job.get('search_country', 'N/A')}\n")
                    f.write(f"   🗣️ Язык: {job.get('country_language', 'N/A')}\n")
                    f.write(f"   🔗 {job['link']}\n\n")
            
            print(f"💾 Результаты сохранены:")
            print(f"   📊 {self.results_file}")
            print(f"   📋 {report_file}")
            
        except Exception as e:
            print(f"❌ Ошибка сохранения: {e}")
    
    def _show_global_results(self, jobs: List[Dict]):
        """Показ глобальных результатов с языковой фильтрацией"""
        if not jobs:
            print("❌ Вакансии не найдены")
            return
        
        language_config = self.config["language_config"]
        
        print(f"\n🏆 ТОП-15 НАЙДЕННЫХ ВАКАНСИЙ")
        print(f"🗣️ Фильтр: {language_config['description']}")
        print("=" * 80)
        
        for i, job in enumerate(jobs[:15], 1):
            # Иконки статуса
            refugee_mark = "🏠" if job.get("refugee_support") else ""
            lang_mark = "🔇" if job.get("jobs_without_language") else "🗣️"
            country_flag = self._get_country_flag(job.get("search_country", ""))
            
            print(f"\n{i}. {country_flag} {job['title']} {refugee_mark} {lang_mark}")
            print(f"   🏢 {job['company']}")
            print(f"   📍 {job['location']}")
            print(f"   💰 {job['salary']}")
            print(f"   🌍 {job.get('search_country', 'N/A')} ({job.get('country_language', 'N/A')})")
            print(f"   🔗 {job['link'][:70]}...")
        
        if len(jobs) > 15:
            print(f"\n... и еще {len(jobs) - 15} вакансий")
        
        # Подробная статистика
        if jobs:
            self._show_detailed_statistics(jobs)
        
        print("=" * 80)
    
    def _get_country_flag(self, country_name: str) -> str:
        """Получение флага страны"""
        flags = {
            "Германия": "🇩🇪", "Польша": "🇵🇱", "Чехия": "🇨🇿", "Словакия": "🇸🇰",
            "Италия": "🇮🇹", "Испания": "🇪🇸", "Франция": "🇫🇷", "Великобритания": "🇬🇧",
            "Нидерланды": "🇳🇱", "Швейцария": "🇨🇭", "Швеция": "🇸🇪", "Норвегия": "🇳🇴",
            "Дания": "🇩🇰", "Финляндия": "🇫🇮", "Бельгия": "🇧🇪", "Австрия": "🇦🇹",
            "Ирландия": "🇮🇪", "Португалия": "🇵🇹", "США": "🇺🇸", "Канада": "🇨🇦",
            "Австралия": "🇦🇺", "Новая Зеландия": "🇳🇿", "Япония": "🇯🇵", "Сингапур": "🇸🇬"
        }
        return flags.get(country_name, "🌍")
    
    def _show_detailed_statistics(self, jobs: List[Dict]):
        """Подробная статистика по языкам и странам"""
        if not jobs: return
        
        # Статистика по странам
        by_country = {}
        by_language = {}
        refugee_jobs = 0
        no_language_jobs = 0
        
        for job in jobs:
            country = job.get("search_country", "Неизвестно")
            by_country[country] = by_country.get(country, 0) + 1
            
            language = job.get("country_language", "Неизвестно")
            by_language[language] = by_language.get(language, 0) + 1
            
            if job.get("refugee_support"):
                refugee_jobs += 1
            if job.get("jobs_without_language"):
                no_language_jobs += 1
        
        print(f"\n📊 ПОДРОБНАЯ СТАТИСТИКА:")
        print(f"🏠 Поддержка беженцев: {refugee_jobs}/{len(jobs)} ({refugee_jobs/len(jobs)*100:.1f}%)")
        print(f"🔇 Работа без языка: {no_language_jobs}/{len(jobs)} ({no_language_jobs/len(jobs)*100:.1f}%)")
        
        print(f"\n🌍 ТОП-5 СТРАН:")
        top_countries = sorted(by_country.items(), key=lambda x: x[1], reverse=True)[:5]
        for country, count in top_countries:
            flag = self._get_country_flag(country)
            percentage = count/len(jobs)*100
            print(f"   {flag} {country}: {count} ({percentage:.1f}%)")
        
        print(f"\n🗣️ ПО ЯЗЫКАМ:")
        top_languages = sorted(by_language.items(), key=lambda x: x[1], reverse=True)[:5]
        for language, count in top_languages:
            percentage = count/len(jobs)*100
            print(f"   • {language}: {count} ({percentage:.1f}%)")
    
    def ensure_data_directory(self):
        """Создание папки данных"""
        os.makedirs("data", exist_ok=True)

def main():
    """Главная функция"""
    print("🌍 GlobalJobHunterBot v3.0")
    print("🌐 Глобальный поиск работы с учетом языковых возможностей")
    print("🏠 Включая специальные программы для беженцев")
    print("💼 Все профессии: от IT до физической работы")
    
    bot = GlobalJobHunterBot()
    
    try:
        jobs = bot.run_global_search()
        
        if jobs:
            print(f"\n🎉 Глобальный поиск завершен!")
            print(f"📊 Найдено: {len(jobs)} подходящих вакансий")
            print(f"💾 Все данные сохранены в папке data/")
            
            # Предложить показать все ссылки
            show_all = input(f"\nПоказать все {len(jobs)} ссылок? (y/n): ").strip().lower()
            if show_all in ['y', 'yes', 'да']:
                print(f"\n🔗 ВСЕ ССЫЛКИ:")
                for i, job in enumerate(jobs, 1):
                    country = job.get('search_country', 'N/A')
                    flag = bot._get_country_flag(country)
                    refugee_mark = "🏠" if job.get("refugee_support") else ""
                    lang_mark = "🔇" if job.get("jobs_without_language") else "🗣️"
                    
                    print(f"{i:2d}. {flag} [{country}] {job['title']} {refugee_mark} {lang_mark}")
                    print(f"     💰 {job['salary']} | 🏢 {job['company']}")
                    print(f"     🔗 {job['link']}")
                    print()
        else:
            print("\n❌ Подходящие вакансии не найдены")
            print("💡 Рекомендации:")
            print("   • Попробуйте расширить языковые требования")
            print("   • Выберите больше стран для поиска")
            print("   • Рассмотрите другие категории профессий")
            
    except KeyboardInterrupt:
        print("\n⏹️ Поиск остановлен пользователем")
    except Exception as e:
        print(f"\n❌ Ошибка: {e}")

if __name__ == "__main__":
    main()