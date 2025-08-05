from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.keys import Keys
import time
import random
import os
from typing import Dict, List, Optional

class JobApplier:
    def __init__(self, headless: bool = False):
        """
        Автоматический отправщик откликов на вакансии
        """
        self.headless = headless
        self.driver = None
        self.wait = None
        
        # Данные для откликов
        self.user_data = {
            "first_name": "Владимир",
            "last_name": "Иванов", 
            "email": "vladimir.ivanov@example.com",
            "phone": "+49 123 456789",
            "cover_letter": """Здравствуйте!

Меня заинтересовала ваша вакансия Python Developer. 

У меня есть опыт работы с:
- Python (Django, Flask, FastAPI)
- Базы данных (PostgreSQL, MySQL)
- Git, Docker
- Frontend (HTML, CSS, JavaScript)

Готов приступить к работе в ближайшее время.

С уважением,
Владимир Иванов"""
        }
    
    def setup_driver(self):
        """Настройка драйвера для откликов"""
        print("📝 Настраиваем драйвер для откликов...")
        
        chrome_options = Options()
        
        if self.headless:
            chrome_options.add_argument("--headless")
        
        chrome_options.add_argument("--disable-blink-features=AutomationControlled")
        chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
        chrome_options.add_experimental_option('useAutomationExtension', False)
        chrome_options.add_argument("--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--window-size=1366,768")
        
        try:
            self.driver = webdriver.Chrome(options=chrome_options)
            self.driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
            self.wait = WebDriverWait(self.driver, 15)
            print("✅ Драйвер для откликов готов!")
            
        except Exception as e:
            print(f"❌ Ошибка создания драйвера: {e}")
            raise
    
    def apply_to_job(self, job_url: str, job_title: str) -> Dict:
        """
        Подача заявки на конкретную вакансию
        
        Args:
            job_url: Ссылка на вакансию
            job_title: Название вакансии
            
        Returns:
            Результат подачи заявки
        """
        if not self.driver:
            self.setup_driver()
        
        result = {
            "job_title": job_title,
            "job_url": job_url,
            "status": "failed",
            "message": "",
            "applied_at": time.strftime("%Y-%m-%d %H:%M:%S")
        }
        
        try:
            print(f"📝 Подаем заявку на: {job_title}")
            print(f"🔗 URL: {job_url}")
            
            # Переходим на страницу вакансии
            self.driver.get(job_url)
            time.sleep(random.uniform(3, 5))
            
            # Анализируем тип сайта
            current_url = self.driver.current_url
            page_title = self.driver.title
            
            print(f"📄 Попали на: {page_title}")
            print(f"🌐 Текущий URL: {current_url}")
            
            # Определяем тип сайта и стратегию подачи заявки
            if "stepstone" in current_url.lower():
                result = self._apply_stepstone()
            elif "xing" in current_url.lower():
                result = self._apply_xing()
            elif "indeed" in current_url.lower():
                result = self._apply_indeed()
            elif "linkedin" in current_url.lower():
                result = self._apply_linkedin()
            else:
                # Универсальная стратегия
                result = self._apply_universal()
            
            result["job_title"] = job_title
            result["job_url"] = job_url
            result["applied_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
            
        except Exception as e:
            result["message"] = f"Ошибка подачи заявки: {str(e)}"
            print(f"❌ Ошибка: {e}")
        
        return result
    
    def _apply_universal(self) -> Dict:
        """Универсальная стратегия подачи заявки"""
        print("🎯 Используем универсальную стратегию...")
        
        try:
            # Ищем кнопки подачи заявки
            apply_buttons = self._find_apply_buttons()
            
            if not apply_buttons:
                return {"status": "no_apply_button", "message": "Кнопка подачи заявки не найдена"}
            
            # Пробуем нажать на первую найденную кнопку
            button = apply_buttons[0]
            button_text = button.text.strip()
            print(f"🎯 Нажимаем кнопку: '{button_text}'")
            
            button.click()
            time.sleep(random.uniform(2, 4))
            
            # Ищем форму для заполнения
            form_filled = self._fill_application_form()
            
            if form_filled:
                return {"status": "success", "message": f"Заявка подана через кнопку '{button_text}'"}
            else:
                return {"status": "partial", "message": f"Кнопка нажата, но форма не найдена. Возможно, перенаправили на внешний сайт."}
                
        except Exception as e:
            return {"status": "error", "message": f"Ошибка универсальной подачи: {str(e)}"}
    
    def _find_apply_buttons(self) -> List:
        """Поиск кнопок подачи заявки"""
        apply_selectors = [
            # Немецкие кнопки
            "//button[contains(text(), 'Bewerben')]",
            "//a[contains(text(), 'Bewerben')]",
            "//button[contains(text(), 'Jetzt bewerben')]",
            "//a[contains(text(), 'Jetzt bewerben')]",
            "//button[contains(text(), 'Bewerbung')]",
            
            # Английские кнопки
            "//button[contains(text(), 'Apply')]",
            "//a[contains(text(), 'Apply')]", 
            "//button[contains(text(), 'Apply now')]",
            "//a[contains(text(), 'Apply now')]",
            
            # CSS селекторы
            "button[class*='apply']",
            "a[class*='apply']",
            "button[data-test*='apply']",
            ".apply-button",
            ".btn-apply"
        ]
        
        found_buttons = []
        
        for selector in apply_selectors:
            try:
                if selector.startswith("//"):
                    buttons = self.driver.find_elements(By.XPATH, selector)
                else:
                    buttons = self.driver.find_elements(By.CSS_SELECTOR, selector)
                
                for button in buttons:
                    if button.is_displayed() and button.is_enabled():
                        found_buttons.append(button)
                        print(f"✅ Найдена кнопка: '{button.text.strip()}'")
                        
            except Exception as e:
                continue
        
        return found_buttons
    
    def _fill_application_form(self) -> bool:
        """Заполнение формы подачи заявки"""
        print("📋 Ищем и заполняем форму...")
        
        try:
            # Ждем появления формы
            time.sleep(2)
            
            # Ищем поля формы
            form_filled = False
            
            # Имя
            name_fields = self._find_form_fields(["name", "vorname", "first", "firstName"])
            for field in name_fields:
                self._fill_field(field, self.user_data["first_name"])
                form_filled = True
            
            # Фамилия
            lastname_fields = self._find_form_fields(["lastname", "nachname", "last", "lastName", "surname"])
            for field in lastname_fields:
                self._fill_field(field, self.user_data["last_name"])
                form_filled = True
            
            # Email
            email_fields = self._find_form_fields(["email", "e-mail", "mail"])
            for field in email_fields:
                self._fill_field(field, self.user_data["email"])
                form_filled = True
            
            # Телефон
            phone_fields = self._find_form_fields(["phone", "telefon", "tel", "mobile"])
            for field in phone_fields:
                self._fill_field(field, self.user_data["phone"])
                form_filled = True
            
            # Сопроводительное письмо
            message_fields = self._find_form_fields(["message", "cover", "letter", "anschreiben", "motivation"])
            for field in message_fields:
                self._fill_field(field, self.user_data["cover_letter"])
                form_filled = True
            
            if form_filled:
                # Ищем кнопку отправки
                submit_buttons = self._find_submit_buttons()
                if submit_buttons:
                    print("📤 Отправляем форму...")
                    submit_buttons[0].click()
                    time.sleep(2)
                    return True
            
            return form_filled
            
        except Exception as e:
            print(f"❌ Ошибка заполнения формы: {e}")
            return False
    
    def _find_form_fields(self, field_keywords: List[str]) -> List:
        """Поиск полей формы по ключевым словам"""
        fields = []
        
        for keyword in field_keywords:
            try:
                # Поиск по атрибутам
                selectors = [
                    f"input[name*='{keyword}']",
                    f"input[id*='{keyword}']",
                    f"input[placeholder*='{keyword}']",
                    f"textarea[name*='{keyword}']",
                    f"textarea[id*='{keyword}']",
                    f"textarea[placeholder*='{keyword}']"
                ]
                
                for selector in selectors:
                    elements = self.driver.find_elements(By.CSS_SELECTOR, selector)
                    for element in elements:
                        if element.is_displayed() and element.is_enabled():
                            fields.append(element)
                            
            except:
                continue
        
        return fields
    
    def _find_submit_buttons(self) -> List:
        """Поиск кнопок отправки формы"""
        submit_selectors = [
            "//button[@type='submit']",
            "//input[@type='submit']",
            "//button[contains(text(), 'Senden')]",
            "//button[contains(text(), 'Absenden')]", 
            "//button[contains(text(), 'Submit')]",
            "//button[contains(text(), 'Send')]",
            ".btn-submit",
            "button[class*='submit']"
        ]
        
        buttons = []
        for selector in submit_selectors:
            try:
                if selector.startswith("//"):
                    elements = self.driver.find_elements(By.XPATH, selector)
                else:
                    elements = self.driver.find_elements(By.CSS_SELECTOR, selector)
                    
                for element in elements:
                    if element.is_displayed() and element.is_enabled():
                        buttons.append(element)
            except:
                continue
                
        return buttons
    
    def _fill_field(self, field, value: str):
        """Заполнение поля формы"""
        try:
            field.clear()
            field.send_keys(value)
            time.sleep(random.uniform(0.5, 1))
            print(f"✅ Заполнено поле: {value[:20]}...")
        except Exception as e:
            print(f"⚠️ Ошибка заполнения поля: {e}")
    
    def batch_apply(self, job_list: List[Dict]) -> List[Dict]:
        """Массовая подача заявок"""
        results = []
        
        print(f"📝 Начинаем массовую подачу заявок на {len(job_list)} вакансий...")
        
        for i, job in enumerate(job_list, 1):
            print(f"\n📝 Обрабатываем вакансию {i}/{len(job_list)}")
            
            result = self.apply_to_job(job["link"], job["title"])
            results.append(result)
            
            print(f"📊 Результат: {result['status']} - {result['message']}")
            
            # Пауза между заявками
            if i < len(job_list):
                pause = random.uniform(10, 20)
                print(f"⏳ Пауза {pause:.1f} секунд до следующей заявки...")
                time.sleep(pause)
        
        return results
    
    def close(self):
        """Закрытие браузера"""
        if self.driver:
            self.driver.quit()
            print("🔄 Браузер для откликов закрыт")
    
    def __enter__(self):
        return self
        
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

# Тест автоматической подачи заявок
if __name__ == "__main__":
    print("📝 Тестируем автоматическую подачу заявок...")
    
    # Тестовые вакансии (из наших предыдущих результатов)
    test_jobs = [
        {
            "title": "Python Software Developer (m/w/d)",
            "link": "https://de.jooble.org/desc/4764556835030060670?ckey=python-developer&rgn=-1&pos=13&groupId=23225&elckey=8874001905807250025&pageType=20&p=1&sid=-5635208274577246269&jobAge=607&relb=110&brelb=110&bscr=14962.41979583679&scr=14962.41979583679&searchTestGroup=1_2_1&iid=3912385943312688486"
        }
    ]
    
    with JobApplier(headless=False) as applier:
        results = applier.batch_apply(test_jobs)
        
        print(f"\n📊 РЕЗУЛЬТАТЫ ПОДАЧИ ЗАЯВОК:")
        for result in results:
            print(f"📝 {result['job_title']}")
            print(f"   📊 Статус: {result['status']}")
            print(f"   💬 Сообщение: {result['message']}")
            print(f"   ⏰ Время: {result['applied_at']}")