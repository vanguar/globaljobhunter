from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from selenium.common.exceptions import TimeoutException, NoSuchElementException
import time
import random
import re
from typing import List, Dict, Optional

class FinalJoobleScaper:
    def __init__(self, headless: bool = False):
        """
        Финальный веб-скрапер для Jooble с максимальным извлечением данных
        """
        self.headless = headless
        self.driver = None
        self.wait = None
        
    def setup_driver(self):
        """Настройка Chrome драйвера"""
        print("🚀 Настраиваем Chrome драйвер...")
        
        chrome_options = Options()
        
        if self.headless:
            chrome_options.add_argument("--headless")
        
        # Настройки для обхода детекции бота
        chrome_options.add_argument("--disable-blink-features=AutomationControlled")
        chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
        chrome_options.add_experimental_option('useAutomationExtension', False)
        chrome_options.add_argument("--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--disable-gpu")
        chrome_options.add_argument("--window-size=1920,1080")
        chrome_options.add_argument("--disable-extensions")
        
        try:
            self.driver = webdriver.Chrome(options=chrome_options)
            self.driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
            self.wait = WebDriverWait(self.driver, 15)
            print("✅ Chrome драйвер готов!")
            
        except Exception as e:
            print(f"❌ Ошибка создания драйвера: {e}")
            raise
        
    def close_popups(self):
        """Улучшенное закрытие всплывающих окон"""
        print("🗂️ Закрываем всплывающие окна...")
        
        # Закрываем основные всплывающие окна
        close_selectors = [
            "[role='dialog'] button",
            "button[aria-label='Close']",
            ".modal-close",
            "button:contains('×')",
            "button:contains('Nein')"
        ]
        
        for selector in close_selectors:
            try:
                elements = self.driver.find_elements(By.CSS_SELECTOR, selector)
                for element in elements:
                    if element.is_displayed() and element.is_enabled():
                        element.click()
                        time.sleep(1)
                        print(f"✅ Закрыто окно: {selector}")
            except:
                continue
        
        # Особые случаи для Jooble
        try:
            # Кнопка "Nein" для newsletter
            from selenium.webdriver.common.keys import Keys
            body = self.driver.find_element(By.TAG_NAME, "body")
            body.send_keys(Keys.ESCAPE)
            time.sleep(1)
            
            # Принимаем cookies
            cookie_buttons = self.driver.find_elements(By.XPATH, "//button[contains(text(), 'ALLE AKZEPTIEREN') or contains(text(), 'ALLE ABLEHNEN')]")
            for btn in cookie_buttons:
                if btn.is_displayed():
                    btn.click()
                    break
                    
        except:
            pass
            
        time.sleep(2)
    
    def search_jobs(self, keywords: str, location: str = "Deutschland", max_pages: int = 3) -> List[Dict]:
        """
        Поиск вакансий на Jooble с максимальным извлечением данных
        """
        if not self.driver:
            self.setup_driver()
            
        jobs = []
        
        try:
            # Формируем URL для поиска
            search_keywords = keywords.replace(' ', '+').lower()
            search_url = f"https://de.jooble.org/stellenangebote-{search_keywords}"
            
            if location and location.lower() != "deutschland":
                search_url += f"?l={location.replace(' ', '+')}"
                
            print(f"🔍 Ищем вакансии: {search_url}")
            
            for page in range(1, max_pages + 1):
                if page > 1:
                    page_url = search_url + ("&p=" if "?" in search_url else "?p=") + str(page)
                else:
                    page_url = search_url
                
                print(f"📄 Парсим страницу {page}...")
                
                # Переходим на страницу поиска
                self.driver.get(page_url)
                time.sleep(3)
                
                # Закрываем всплывающие окна
                self.close_popups()
                time.sleep(2)
                
                # Парсим вакансии на текущей странице
                page_jobs = self._parse_jobs_detailed()
                jobs.extend(page_jobs)
                
                print(f"✅ Найдено {len(page_jobs)} вакансий на странице {page}")
                
                # Пауза между страницами
                time.sleep(random.uniform(3, 5))
                
                # Если нашли мало вакансий, возможно это последняя страница
                if len(page_jobs) < 5:
                    print("📄 Мало вакансий на странице, возможно это конец")
                    break
                    
        except Exception as e:
            print(f"❌ Ошибка парсинга: {e}")
            
        return jobs
    
    def _parse_jobs_detailed(self) -> List[Dict]:
        """Детальный парсинг вакансий с извлечением всех данных"""
        jobs = []
        
        try:
            print(f"📄 Заголовок: {self.driver.title}")
            
            # Сначала ищем все статьи/карточки вакансий
            job_containers = []
            
            # Пробуем разные селекторы для контейнеров вакансий
            container_selectors = [
                "article",
                ".serp-item", 
                "[data-test*='vacancy']",
                "div[class*='job']",
                ".vacancy-serp__vacancy"
            ]
            
            for selector in container_selectors:
                elements = self.driver.find_elements(By.CSS_SELECTOR, selector)
                if len(elements) >= 5:  # Если нашли достаточно
                    job_containers = elements
                    print(f"✅ Используем контейнеры: {selector} ({len(elements)} шт.)")
                    break
            
            if not job_containers:
                # Альтернативный подход - ищем по ссылкам
                print("⚠️ Контейнеры не найдены, ищем по ссылкам...")
                return self._parse_by_links()
            
            # Парсим каждый контейнер
            for i, container in enumerate(job_containers[:25]):  # Максимум 25 вакансий
                try:
                    job_data = self._extract_detailed_job_data(container, i + 1)
                    if job_data:
                        jobs.append(job_data)
                except Exception as e:
                    print(f"⚠️ Ошибка обработки контейнера {i+1}: {e}")
                    continue
                    
        except Exception as e:
            print(f"❌ Ошибка детального парсинга: {e}")
            
        return jobs
    
    def _parse_by_links(self) -> List[Dict]:
        """Альтернативный парсинг через ссылки"""
        jobs = []
        
        try:
            # Ищем все ссылки на вакансии
            job_links = self.driver.find_elements(By.CSS_SELECTOR, "a[href*='/desc/']")
            print(f"📊 Найдено ссылок: {len(job_links)}")
            
            processed_links = set()
            
            for link in job_links[:30]:  # Максимум 30 ссылок
                try:
                    href = link.get_attribute("href")
                    if href in processed_links:
                        continue
                    processed_links.add(href)
                    
                    # Извлекаем данные из ссылки и её окружения
                    job_data = self._extract_from_link_context(link, len(jobs) + 1)
                    if job_data:
                        jobs.append(job_data)
                        
                except Exception as e:
                    continue
                    
        except Exception as e:
            print(f"❌ Ошибка парсинга по ссылкам: {e}")
            
        return jobs
    
    def _extract_detailed_job_data(self, container, index: int) -> Optional[Dict]:
        """Детальное извлечение данных из контейнера вакансии"""
        try:
            # Получаем весь текст контейнера
            full_text = container.text.strip()
            lines = [line.strip() for line in full_text.split('\n') if line.strip()]
            
            # Ищем ссылку и заголовок
            title = f"Python Developer {index}"
            link = "Нет ссылки"
            
            try:
                link_elem = container.find_element(By.CSS_SELECTOR, "a[href*='/desc/']")
                link = link_elem.get_attribute("href")
                
                # Заголовок часто в ссылке или рядом
                title_text = link_elem.text.strip()
                if title_text and len(title_text) > 5:
                    title = title_text
                else:
                    # Ищем заголовок в тегах h1, h2, h3
                    for tag in ['h1', 'h2', 'h3']:
                        try:
                            h_elem = container.find_element(By.TAG_NAME, tag)
                            if h_elem.text.strip():
                                title = h_elem.text.strip()
                                break
                        except:
                            continue
            except:
                pass
            
            # Извлекаем компанию, локацию, зарплату из текста
            company = self._extract_company(lines, title)
            location = self._extract_location(lines)
            salary = self._extract_salary(lines)
            date = self._extract_date(lines)
            
            # Создаем краткое описание
            snippet = self._create_snippet(lines, title)
            
            return {
                "title": title,
                "company": company,
                "location": location,
                "salary": salary,
                "snippet": snippet,
                "link": link,
                "date": date,
                "source": "jooble"
            }
            
        except Exception as e:
            print(f"⚠️ Ошибка детального извлечения: {e}")
            return None
    
    def _extract_from_link_context(self, link_elem, index: int) -> Optional[Dict]:
        """Извлечение данных из контекста ссылки"""
        try:
            title = link_elem.text.strip()
            if not title or len(title) < 3:
                title = f"Python Developer {index}"
                
            href = link_elem.get_attribute("href")
            
            # Ищем родительский контейнер с полной информацией
            try:
                # Поднимаемся вверх по DOM до контейнера с данными
                parent = link_elem
                for _ in range(3):  # Максимум 3 уровня вверх
                    parent = parent.find_element(By.XPATH, "..")
                    parent_text = parent.text.strip()
                    if len(parent_text) > len(title) + 50:  # Если в родителе больше данных
                        break
                
                lines = [line.strip() for line in parent_text.split('\n') if line.strip()]
                
            except:
                lines = [title]
            
            # Извлекаем данные
            company = self._extract_company(lines, title)
            location = self._extract_location(lines)
            salary = self._extract_salary(lines)
            date = self._extract_date(lines)
            snippet = self._create_snippet(lines, title)
            
            return {
                "title": title,
                "company": company,
                "location": location,
                "salary": salary,
                "snippet": snippet,
                "link": href,
                "date": date,
                "source": "jooble"
            }
            
        except Exception as e:
            return None
    
    def _extract_company(self, lines: List[str], title: str) -> str:
        """Извлечение названия компании"""
        for line in lines:
            # Пропускаем заголовок и слишком длинные строки
            if line == title or len(line) > 60:
                continue
                
            # Ищем строки, которые могут быть названием компании
            if (len(line) > 2 and 
                'developer' not in line.lower() and 
                'python' not in line.lower() and
                'software' not in line.lower() and
                '€' not in line and
                'vor' not in line.lower() and
                'empfohlen' not in line.lower() and
                'vollzeit' not in line.lower()):
                
                # Простая эвристика: короткие строки без ключевых слов
                if len(line.split()) <= 4:
                    return line
        
        return "Не указана"
    
    def _extract_location(self, lines: List[str]) -> str:
        """Извлечение локации"""
        # Немецкие города
        german_cities = ['berlin', 'münchen', 'hamburg', 'köln', 'frankfurt', 'düsseldorf', 
                        'stuttgart', 'dortmund', 'essen', 'leipzig', 'bremen', 'dresden',
                        'hannover', 'nürnberg', 'duisburg', 'bochum', 'wuppertal', 'bielefeld']
        
        for line in lines:
            line_lower = line.lower()
            # Проверяем наличие городов
            for city in german_cities:
                if city in line_lower:
                    return line
            
            # Ищем паттерны локации
            if any(keyword in line_lower for keyword in ['remote', 'homeoffice', 'deutschland', 'germany']):
                return line
                
        return "Не указана"
    
    def _extract_salary(self, lines: List[str]) -> str:
        """Извлечение зарплаты"""
        for line in lines:
            # Ищем символы валют и числа
            if re.search(r'[€$]\s*\d+|gehalt|\d+\s*[€$]|\d+\.\d+|\d+k', line.lower()):
                return line
                
        return "Не указана"
    
    def _extract_date(self, lines: List[str]) -> str:
        """Извлечение даты публикации"""
        for line in lines:
            if any(keyword in line.lower() for keyword in ['vor', 'tag', 'woche', 'monat', 'heute', 'gestern']):
                if len(line) < 30:  # Короткие строки с датой
                    return line
                    
        return "Не указана"
    
    def _create_snippet(self, lines: List[str], title: str) -> str:
        """Создание краткого описания"""
        # Берем первые несколько строк, исключая заголовок
        snippet_lines = []
        for line in lines:
            if line != title and len(line) > 10:
                snippet_lines.append(line)
                if len(' '.join(snippet_lines)) > 150:
                    break
        
        snippet = ' '.join(snippet_lines)
        if len(snippet) > 200:
            snippet = snippet[:200] + "..."
            
        return snippet if snippet else "Нет описания"
    
    def close(self):
        """Закрытие браузера"""
        if self.driver:
            self.driver.quit()
            print("🔄 Браузер закрыт")
            
    def __enter__(self):
        return self
        
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

# Тестирование финального скрапера
if __name__ == "__main__":
    print("🤖 Тестируем ФИНАЛЬНЫЙ Jooble скрапер...")
    
    with FinalJoobleScaper(headless=False) as scraper:
        jobs = scraper.search_jobs("Python Developer", "Berlin", max_pages=2)
        
        print(f"\n📊 ФИНАЛЬНЫЕ РЕЗУЛЬТАТЫ:")
        print(f"Всего найдено вакансий: {len(jobs)}")
        print("=" * 80)
        
        for i, job in enumerate(jobs[:10], 1):
            print(f"\n{i}. 🎯 {job['title']}")
            print(f"   🏢 Компания: {job['company']}")
            print(f"   📍 Локация: {job['location']}")
            print(f"   💰 Зарплата: {job['salary']}")
            print(f"   📅 Дата: {job['date']}")
            print(f"   🔗 Ссылка: {job['link'][:80]}...")
            print(f"   📝 Описание: {job['snippet'][:120]}...")
            print("-" * 80)