#!/usr/bin/env python3
"""
GlobalJobAggregator v2.4 - С УМНЫМ КЕШИРОВАНИЕМ
Кеширование результатов на Redis + файловый кеш как fallback
"""

import os
import requests
import json
import time
import hashlib
from datetime import datetime, timedelta
from typing import List, Dict, Optional
from dataclasses import dataclass, asdict
from dotenv import load_dotenv
import pickle
from urllib.parse import urlparse
import random
from typing import Dict

# --- circuit breaker + микро-пауза ---
class RateLimitedError(Exception):
    """Источник временно ограничил нас (429). Останавливаем этот источник до истечения cooldown."""

import random
def yield_briefly(base_ms: int = 200, jitter_ms: int = 120, cancel_check=None) -> bool:
    delay = (base_ms + (random.randint(0, jitter_ms) if jitter_ms > 0 else 0)) / 1000.0
    end = time.time() + delay
    while True:
        if cancel_check and cancel_check():
            return False
        remain = end - time.time()
        if remain <= 0:
            break
        time.sleep(min(0.05, remain))  # шаг 50мс
    return True



# Попытка импорта Redis (опционально)
try:
    import redis
    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False
    print("⚠️ Redis не установлен, используется файловый кеш")

load_dotenv()

@dataclass
class JobVacancy:
    id: str
    title: str
    company: str
    location: str
    salary: Optional[str]
    description: str
    apply_url: str
    source: str
    posted_date: str
    country: str
    job_type: Optional[str] = None
    language_requirement: str = "unknown"
    refugee_friendly: bool = False

@dataclass
class CachedResult:
    """Структура для кешированного результата"""
    data: List[Dict]
    timestamp: datetime
    search_params: Dict
    expires_at: datetime

class CacheManager:
    """Менеджер кеширования с поддержкой Redis и файлового кеша"""
    
    def __init__(self, cache_duration_hours: Optional[int] = None):
        """
        TTL приоритет: явный аргумент > CACHE_TTL_HOURS > 24ч по умолчанию.
        Один CacheManager используют все агрегаторы → единая политика протухания.
        """
        try:
            default_hours = int(os.getenv('CACHE_TTL_HOURS', '24'))
        except Exception:
            default_hours = 24
        hours = cache_duration_hours if cache_duration_hours is not None else default_hours

        self.cache_duration = timedelta(hours=hours)
        self.file_cache_dir = "cache"
        
        # Инициализация Redis (если доступен)
        self.redis_client = None
        if REDIS_AVAILABLE:
            try:
                url = os.getenv('REDIS_TLS_URL') or os.getenv('REDIS_URL')
                print(f"ℹ️ CacheManager: using {'REDIS_TLS_URL/REDIS_URL' if url else 'REDIS_HOST/PORT/DB'}")
                if url:
                    u = urlparse(url)
                    self.redis_client = redis.Redis(
                        host=u.hostname,
                        port=u.port or 6379,
                        password=u.password,
                        db=int((u.path or '/0').lstrip('/')),
                        ssl=(u.scheme == 'rediss'),
                        ssl_cert_reqs=None,
                        decode_responses=False  # Для работы с pickle (байты)
                    )
                else:
                    self.redis_client = redis.Redis(
                        host=os.getenv('REDIS_HOST', 'localhost'),
                        port=int(os.getenv('REDIS_PORT', 6379)),
                        db=int(os.getenv('REDIS_DB', 0)),
                        decode_responses=False
                    )
                # Проверяем соединение
                try:
                    info_host = self.redis_client.connection_pool.connection_kwargs.get('host')
                    info_port = self.redis_client.connection_pool.connection_kwargs.get('port')
                    print(f"🔌 CacheManager: target {info_host}:{info_port}")
                except Exception:
                    pass

                self.redis_client.ping()
                print("✅ Redis подключен (CacheManager)")
            except Exception as e:
                print(f"⚠️ Redis недоступен: {e}, используется файловый кеш")
                self.redis_client = None

        
        # Создаем директорию для файлового кеша
        os.makedirs(self.file_cache_dir, exist_ok=True)

    
    def _generate_cache_key(self, search_params: Dict) -> str:
        """Генерация уникального ключа кеша на основе параметров поиска"""
        explicit = search_params.get("key")
        if isinstance(explicit, str) and explicit:
            return explicit
        sorted_params = json.dumps(search_params, sort_keys=True)
        return hashlib.md5(sorted_params.encode()).hexdigest()
    
    def get_cached_result(self, search_params: Dict) -> Optional[List[JobVacancy]]:
        """Получение результата из кеша"""
        cache_key = self._generate_cache_key(search_params)
        
        # Сначала пробуем Redis
        if self.redis_client:
            try:
                cached_data = self.redis_client.get(f"job_search:{cache_key}")
                if cached_data:
                    cached_result = pickle.loads(cached_data)
                    if datetime.now() < cached_result.expires_at:
                        print(f"🎯 Cache HIT (Redis): {cache_key[:8]}... ({len(cached_result.data)} jobs)")
                        return (cached_result.data if search_params.get("raw") else
                               [JobVacancy(**job_data) for job_data in cached_result.data])
                    else:
                        # Кеш истек, удаляем
                        self.redis_client.delete(f"job_search:{cache_key}")
            except Exception as e:
                print(f"⚠️ Ошибка Redis: {e}")
        
        # Если Redis недоступен, используем файловый кеш
        return self._get_file_cache(cache_key, search_params)
    
    def _get_file_cache(self, cache_key: str, search_params: Dict) -> Optional[List[JobVacancy]]:
        """Получение из файлового кеша"""
        cache_file = os.path.join(self.file_cache_dir, f"{cache_key}.pkl")
        
        if os.path.exists(cache_file):
            try:
                with open(cache_file, 'rb') as f:
                    cached_result = pickle.load(f)
                
                if datetime.now() < cached_result.expires_at:
                    print(f"🎯 Cache HIT (File): {cache_key[:8]}... ({len(cached_result.data)} jobs)")
                    return (cached_result.data if search_params.get("raw") else
                           [JobVacancy(**job_data) for job_data in cached_result.data])
                else:
                    # Кеш истек, удаляем файл
                    os.remove(cache_file)
            except Exception as e:
                print(f"⚠️ Ошибка файлового кеша: {e}")
                # Удаляем поврежденный файл
                try:
                    os.remove(cache_file)
                except:
                    pass
        
        return None
    
    def cache_result(self, search_params: Dict, jobs: List[JobVacancy]):
        """Сохранение результата в кеш"""
        if not jobs:  # Не кешируем пустые результаты
            return
        
        cache_key = self._generate_cache_key(search_params)
        expires_at = datetime.now() + self.cache_duration
        
        cached_result = CachedResult(
            data=(jobs if search_params.get("raw") else
                  [asdict(job) for job in jobs]),
            timestamp=datetime.now(),
            search_params=search_params,
            expires_at=expires_at
        )
        
        # Сохраняем в Redis
        if self.redis_client:
            try:
                self.redis_client.setex(
                    f"job_search:{cache_key}",
                    int(self.cache_duration.total_seconds()),
                    pickle.dumps(cached_result)
                )
                print(f"💾 Cache SAVE (Redis): {cache_key[:8]}... ({len(jobs)} jobs, TTL: {self.cache_duration})")
            except Exception as e:
                print(f"⚠️ Ошибка сохранения в Redis: {e}")
        
        # Сохраняем в файловый кеш как fallback
        self._save_file_cache(cache_key, cached_result)
    
    def _save_file_cache(self, cache_key: str, cached_result: CachedResult):
        """Сохранение в файловый кеш"""
        cache_file = os.path.join(self.file_cache_dir, f"{cache_key}.pkl")
        
        try:
            with open(cache_file, 'wb') as f:
                pickle.dump(cached_result, f)
            print(f"💾 Cache SAVE (File): {cache_key[:8]}... ({len(cached_result.data)} jobs)")
        except Exception as e:
            print(f"⚠️ Ошибка сохранения файлового кеша: {e}")

        # === СУБ-КЕШ по (country, location, keywords) ===
    def _term_cache_key(self, country: str, location: str, keywords: str) -> str:
        payload = json.dumps(
            {'c': (country or '').strip().lower(),
             'l': (location or '').strip(),
             'k': (keywords or '').strip().lower()},
            sort_keys=True
        )
        return "job_term:" + hashlib.md5(payload.encode()).hexdigest()

    def get_term_cached_result(self, country: str, location: str, keywords: str) -> Optional[List['JobVacancy']]:
        """
        Вернёт:
        - list[JobVacancy] — если в суб-кеше есть НЕПУСТОЙ свежий список,
        - None — если записи нет/протухла/пустая (пустые записи при чтении удаляем).
        """
        cache_key = self._term_cache_key(country, location, keywords)

        # Redis
        if self.redis_client:
            try:
                cached_data = self.redis_client.get(cache_key)
                if cached_data:
                    cached_result = pickle.loads(cached_data)
                    # Если когда-то закешировали пустой список — не считаем хитом
                    data_list = cached_result.data or []
                    if not data_list:
                        try:
                            self.redis_client.delete(cache_key)
                        except Exception:
                            pass
                        return None
                    if datetime.now() < cached_result.expires_at:
                        return [JobVacancy(**job_data) for job_data in data_list]
                    else:
                        self.redis_client.delete(cache_key)
                        return None
            except Exception:
                pass  # безопасно падаем на файловый кеш

        # Файловый кеш
        cache_file = os.path.join(self.file_cache_dir, f"{cache_key}.pkl")
        if os.path.exists(cache_file):
            try:
                with open(cache_file, 'rb') as f:
                    cached_result = pickle.load(f)
                data_list = cached_result.data or []
                # Пустой — очищаем и считаем, что записи нет
                if not data_list:
                    try:
                        os.remove(cache_file)
                    except Exception:
                        pass
                    return None
                if datetime.now() < cached_result.expires_at:
                    return [JobVacancy(**job_data) for job_data in data_list]
                else:
                    os.remove(cache_file)
            except Exception:
                return None
        return None


    def cache_term_result(self, country: str, location: str, keywords: str, jobs: List['JobVacancy']) -> None:
        """
        Сохраняет результат по одному термину в суб-кеш.
        ВАЖНО: пустые списки НЕ кешируем (чтобы не «застывали нули»).
        """
        if not jobs:
            # тихо выходим — следующая попытка по этому термину снова пойдёт в API
            return

        cache_key = self._term_cache_key(country, location, keywords)
        expires_at = datetime.now() + self.cache_duration
        cached_result = CachedResult(
            data=[asdict(job) for job in jobs],
            timestamp=datetime.now(),
            search_params={'c': country, 'l': location, 'k': keywords},
            expires_at=expires_at
        )
        # Redis
        if self.redis_client:
            try:
                self.redis_client.setex(
                    cache_key,
                    int(self.cache_duration.total_seconds()),
                    pickle.dumps(cached_result)
                )
            except Exception:
                pass
        # File
        try:
            os.makedirs(self.file_cache_dir, exist_ok=True)
            with open(os.path.join(self.file_cache_dir, f"{cache_key}.pkl"), 'wb') as f:
                pickle.dump(cached_result, f)
        except Exception:
            pass

        
    
    def cleanup_expired_cache(self):
        """Очистка истекшего кеша"""
        print("🧹 Очистка истекшего кеша...")
        
        # Очистка файлового кеша
        if os.path.exists(self.file_cache_dir):
            for filename in os.listdir(self.file_cache_dir):
                if filename.endswith('.pkl'):
                    filepath = os.path.join(self.file_cache_dir, filename)
                    try:
                        with open(filepath, 'rb') as f:
                            cached_result = pickle.load(f)
                        
                        if datetime.now() >= cached_result.expires_at:
                            os.remove(filepath)
                            print(f"🗑️ Удален истекший кеш: {filename}")
                    except Exception as e:
                        # Удаляем поврежденные файлы
                        try:
                            os.remove(filepath)
                            print(f"🗑️ Удален поврежденный кеш: {filename}")
                        except:
                            pass

class RateLimiter:
    """Ограничитель скорости запросов к API"""

    def __init__(self, requests_per_minute: int = 20):
        self.requests_per_minute = requests_per_minute
        self.requests = []

    def wait_if_needed(self, cancel_check=None) -> bool:
        """FAST MODE: не ждём вообще (всегда сразу продолжаем)."""
        # просто фиксируем «запрос», чтобы статистика не ломалась
        try:
            now = time.time()
            self.requests = [t for t in getattr(self, "requests", []) if now - t < 60]
            self.requests.append(now)
        except Exception:
            pass
        return True


class GlobalJobAggregator:
    def __init__(self, cache_duration_hours: Optional[int] = None):
        """
        TTL для Adzuna берём из ADZUNA_CACHE_HOURS или из общего CACHE_TTL_HOURS (по умолчанию 24).
        """
        self.cooldown_until = 0  # до этого времени Adzuna пропускается

        self.app_id = os.getenv('ADZUNA_APP_ID')
        self.app_key = os.getenv('ADZUNA_APP_KEY')
        if not self.app_id or not self.app_key:
            raise ValueError("Adzuna API ключи не найдены!")

        # TTL
        if cache_duration_hours is None:
            try:
                cache_duration_hours = int(os.getenv('ADZUNA_CACHE_HOURS', os.getenv('CACHE_TTL_HOURS', '24')))
            except Exception:
                cache_duration_hours = 24

        # Кеш и rate limiter
        self.cache_manager = CacheManager(cache_duration_hours)
        self.rate_limiter = RateLimiter()

        # Статистика для мониторинга
        self.stats = {
            'cache_hits': 0,
            'cache_misses': 0,
            'api_requests': 0,
            'total_jobs_found': 0
        }
        
        # Ваши существующие данные
        self.countries = {
            'de': {'name': 'Германия', 'currency': '€', 'refugee_support': True, 'work_without_language': True},
            'gb': {'name': 'Великобритания', 'currency': '£', 'refugee_support': True, 'work_without_language': True},
            'pl': {'name': 'Польша', 'currency': 'PLN', 'refugee_support': True, 'work_without_language': True},
            'nl': {'name': 'Нидерланды', 'currency': '€', 'refugee_support': True, 'work_without_language': True},
            'fr': {'name': 'Франция', 'currency': '€', 'refugee_support': True, 'work_without_language': False},
            'at': {'name': 'Австрия', 'currency': '€', 'refugee_support': True, 'work_without_language': True},
            'us': {'name': 'США', 'currency': '$', 'refugee_support': True, 'work_without_language': True},
            'ca': {'name': 'Канада', 'currency': 'C$', 'refugee_support': True, 'work_without_language': True},
            'au': {'name': 'Австралия', 'currency': 'A$', 'refugee_support': True, 'work_without_language': True},
            'it': {'name': 'Италия', 'currency': '€', 'refugee_support': True, 'work_without_language': True},
            'es': {'name': 'Испания', 'currency': '€', 'refugee_support': True, 'work_without_language': True},
            'ch': {'name': 'Швейцария', 'currency': 'CHF', 'refugee_support': True, 'work_without_language': True},
            'be': {'name': 'Бельгия', 'currency': '€', 'refugee_support': True, 'work_without_language': True},
            'se': {'name': 'Швеция', 'currency': 'SEK', 'refugee_support': True, 'work_without_language': True},
            'no': {'name': 'Норвегия', 'currency': 'NOK', 'refugee_support': True, 'work_without_language': True},
            'dk': {'name': 'Дания', 'currency': 'DKK', 'refugee_support': True, 'work_without_language': True},
            'cz': {'name': 'Чехия', 'currency': 'CZK', 'refugee_support': True, 'work_without_language': True},
            'sk': {'name': 'Словакия', 'currency': '€', 'refugee_support': True, 'work_without_language': True}
        }
        
        # Добавлен словарь для исправления частых опечаток в названиях городов
        self.CITY_CORRECTIONS = {
            'rostok': 'Rostock',
            'berlinn': 'Berlin',
            'munhen': 'Munich',
            'мюнхен': 'Munich',
            'stralsund': 'Stralsund',
            'варшава': 'Warsaw',
            'kiev': 'Kyiv',
            'киев': 'Kyiv',
            'londonn': 'London',
            'лондон': 'London',
            'париж': 'Paris'
        }
        
        # В классе GlobalJobAggregator замените self.specific_jobs на:
        self.specific_jobs = {
            '🚗 ТРАНСПОРТ И ДОСТАВКА': {
                'Водитель такси': [
                    # Английский (0-2)
                    'taxi driver', 'cab driver', 'uber driver',
                    # Немецкий (3-5)
                    'taxifahrer', 'taxi fahrer', 'fahrdienst',
                    # Французский (6-8)
                    'chauffeur de taxi', 'conducteur de taxi', 'vtc',
                    # Испанский (9-11)
                    'conductor de taxi', 'taxista', 'conductor vtc',
                    # Итальянский (12-14)
                    'tassista', 'autista taxi', 'conducente taxi',
                    # Нидерландский (15-17)
                    'taxichauffeur', 'taxi bestuurder', 'uber chauffeur',
                    # Польский (18-20)
                    'taksówkarz', 'kierowca taxi', 'przewoźnik',
                    # Чешский (21-23)
                    'taxikář', 'řidič taxi', 'dopravce'
                ],
                
                'Водитель категории B': [
                    # Английский
                    'car driver', 'personal driver', 'chauffeur',
                    # Немецкий
                    'pkw fahrer', 'autofahrer', 'fahrdienst fahrer',
                    # Французский
                    'conducteur', 'chauffeur particulier', 'conducteur vpn',
                    # Испанский
                    'conductor', 'chofer personal', 'conductor particular',
                    # Итальянский
                    'autista', 'conducente', 'autista personale',
                    # Нидерландский
                    'automobilist', 'chauffeur', 'bestuurder',
                    # Польский
                    'kierowca', 'szofer', 'kierowca osobowy',
                    # Чешский
                    'řidič', 'šofér', 'osobní řidič'
                ],

                
                
                'Водитель категории C': [
                    # Английский
                    'truck driver', 'HGV driver', 'lorry driver',
                    # Немецкий
                    'lkw fahrer', 'fernfahrer', 'kraftfahrer',
                    # Французский
                    'conducteur poids lourd', 'chauffeur pl', 'routier',
                    # Испанский
                    'conductor camión', 'camionero', 'transportista',
                    # Итальянский
                    'camionista', 'autista camion', 'trasportatore',
                    # Нидерландский
                    'vrachtwagenchauffeur', 'trucker', 'transporteur',
                    # Польский
                    'kierowca ciężarówki', 'kierowca tir', 'przewoźnik',
                    # Чешский
                    'řidič nákladního', 'kamionář', 'dopravce'
                ],
                
                'Водитель-курьер': [
                    # Английский
                    'delivery driver', 'courier driver', 'van driver',
                    # Немецкий
                    'lieferfahrer', 'kurier fahrer', 'paket fahrer',
                    # Французский
                    'chauffeur-livreur', 'conducteur livreur', 'livreur auto',
                    # Испанский
                    'conductor reparto', 'repartidor auto', 'mensajero auto',
                    # Итальянский
                    'autista consegne', 'conducente corriere', 'fattorino auto',
                    # Нидерландский
                    'bezorgchauffeur', 'koerier bestuurder', 'pakket chauffeur',
                    # Польский
                    'kierowca kurierski', 'dostawca', 'kierowca dostawczy',
                    # Чешский
                    'řidič kurýr', 'rozvozce', 'doručovatel'
                ],
                
                'Курьер пешком': [
                    # Английский
                    'bicycle courier', 'bike courier', 'foot courier',
                    # Немецкий
                    'fahrradkurier', 'radkurier', 'fußkurier',
                    # Французский
                    'coursier vélo', 'livreur vélo', 'messager vélo',
                    # Испанский
                    'mensajero bicicleta', 'repartidor bici', 'ciclomensajero',
                    # Итальянский
                    'fattorino bici', 'corriere bici', 'rider',
                    # Нидерландский
                    'fietskoerier', 'fietsbezorger', 'rijder',
                    # Польский
                    'kurier rowerowy', 'rowerzysta', 'dostawca rower',
                    # Чешский
                    'cyklo kurýr', 'jízdní kurýr', 'cyklista'
                ],
                
                'Курьер-доставщик еды': [
                    # Английский
                    'food delivery driver', 'uber eats driver', 'deliveroo rider',
                    # Немецкий
                    'essenslieferant', 'lieferando fahrer', 'food kurier',
                    # Французский
                    'livreur repas', 'uber eats', 'deliveroo livreur',
                    # Испанский
                    'repartidor comida', 'glovo repartidor', 'uber eats',
                    # Итальянский
                    'rider cibo', 'glovo rider', 'fattorino food',
                    # Нидерландский
                    'maaltijdbezorger', 'uber eats', 'thuisbezorgd',
                    # Польский
                    'dostawa jedzenia', 'uber eats', 'glovo kurier',
                    # Чешский
                    'rozvoz jídla', 'uber eats', 'bolt food'
                ],
                
                'Водитель автобуса': [
                    # Английский
                    'bus driver', 'coach driver', 'transit driver',
                    # Немецкий
                    'busfahrer', 'omnibusfahrer', 'nahverkehr fahrer',
                    # Французский
                    'conducteur bus', 'chauffeur autobus', 'machiniste',
                    # Испанский
                    'conductor autobús', 'chofer bus', 'conductor transporte',
                    # Итальянский
                    'autista autobus', 'conducente bus', 'autista mezzi',
                    # Нидерландский
                    'buschauffeur', 'ov chauffeur', 'bestuurder bus',
                    # Польский
                    'kierowca autobusu', 'motorniczej', 'przewoźnik',
                    # Чешский
                    'řidič autobusu', 'autobusák', 'dopravce'
                ],
                
                'Водитель грузовика': [
                    # Английский
                    'truck driver', 'freight driver', 'haulage driver',
                    # Немецкий
                    'lkw fahrer', 'speditionsfahrer', 'transportfahrer',
                    # Французский
                    'conducteur camion', 'transporteur', 'livreur camion',
                    # Испанский
                    'camionero', 'conductor transporte', 'operador logístico',
                    # Итальянский
                    'camionista', 'autotrasportatore', 'operatore logistico',
                    # Нидерландский
                    'vrachtwagenchauffeur', 'logistiek chauffeur', 'transport',
                    # Польский
                    'kierowca ciężarowy', 'spedytor', 'logistyk',
                    # Чешский
                    'řidič nákladní', 'spedice řidič', 'logistik'
                ]
            },

            '🔧 АВТОСЕРВИС И ТЕХОБСЛУЖИВАНИЕ': {
                'Автомеханик': [
                    # Английский
                    'auto mechanic', 'car mechanic', 'vehicle technician', 'automotive technician',
                    'motor mechanic', 'garage mechanic', 'auto repair technician',
                    # Немецкий
                    'kfz mechaniker', 'kfz mechatroniker', 'automechaniker', 'fahrzeugmechaniker',
                    'kraftfahrzeugmechaniker', 'autowerkstatt mechaniker',
                    # Французский
                    'mécanicien automobile', 'mécanicien auto', 'technicien automobile',
                    'réparateur automobile', 'garagiste mécanicien',
                    # Испанский
                    'mecánico automotriz', 'mecánico de autos', 'técnico automotriz',
                    'mecánico de vehículos', 'reparador de autos',
                    # Итальянский
                    'meccanico auto', 'meccanico automobilistico', 'tecnico automotive',
                    'riparatore auto', 'meccanico officina',
                    # Нидерландский
                    'automonteur', 'auto mechaniker', 'voertuig technicus',
                    'garage monteur', 'auto reparateur',
                    # Польский
                    'mechanik samochodowy', 'automechanik', 'technik motoryzacyjny',
                    'mechanik pojazdów', 'serwisant samochodowy',
                    # Чешский
                    'automechanik', 'mechanik vozidel', 'technik automotive',
                    'opravář automobilů', 'servisní technik'
                ],
                
                'Автослесарь': [
                    # Английский
                    'automotive fitter', 'car repair specialist', 'mechanical fitter',
                    'auto service technician', 'vehicle fitter',
                    # Немецкий
                    'kfz schlosser', 'fahrzeugschlosser', 'auto schlosser',
                    'kfz servicetechniker',
                    # Французский
                    'ajusteur automobile', 'monteur auto', 'réparateur mécanique',
                    # Испанский
                    'ajustador automotriz', 'técnico de reparación', 'montador auto',
                    # Итальянский
                    'montatore auto', 'aggiustatore veicoli', 'tecnico riparazioni',
                    # Нидерландский
                    'auto fitter', 'voertuig monteur', 'mechanisch monteur',
                    # Польский
                    'ślusarz samochodowy', 'monterz samochodowy', 'fitter automotive',
                    # Чешский
                    'automontér', 'zámečník automotive', 'montážník vozidel'
                ],
                
                'Шиномонтажник': [
                    # Английский
                    'tire fitter', 'tyre fitter', 'tire technician', 'wheel fitter',
                    'tire service technician', 'tire installer',
                    # Немецкий
                    'reifenmonteur', 'reifen service techniker', 'reifenwechsler',
                    'reifenservice mitarbeiter',
                    # Французский
                    'monteur pneus', 'technicien pneumatique', 'spécialiste pneus',
                    # Испанский
                    'montador neumáticos', 'técnico de llantas', 'especialista neumáticos',
                    # Итальянский
                    'gommista', 'montatore pneumatici', 'tecnico gomme',
                    # Нидерландский
                    'bandenmonteur', 'bandenservice monteur', 'banden technicus',
                    # Польский
                    'wulkanizator', 'monterz opon', 'serwisant opon',
                    # Чешский
                    'pneuservis technik', 'montér pneumatik', 'pneumatikář'
                ],
                
                'Диагност': [
                    # Английский
                    'diagnostic technician', 'auto diagnostician', 'vehicle diagnostics',
                    'automotive diagnostic specialist', 'car diagnostic expert',
                    # Немецкий
                    'kfz diagnostiker', 'fahrzeugdiagnostiker', 'diagnose techniker',
                    # Французский
                    'technicien diagnostic', 'diagnostiqueur automobile', 'expert diagnostic',
                    # Испанский
                    'técnico diagnóstico', 'diagnosticador automotriz', 'especialista diagnóstico',
                    # Итальянский
                    'diagnostico auto', 'tecnico diagnosi', 'specialista diagnostica',
                    # Нидерландский
                    'diagnose technicus', 'auto diagnose specialist', 'voertuig diagnose',
                    # Польский
                    'diagnostyk samochodowy', 'technik diagnostyki', 'specjalista diagnoza',
                    # Чешский
                    'diagnostik vozidel', 'technik diagnostiky', 'specialista diagnóza'
                ],
                
                'Мастер-приёмщик': [
                    # Английский
                    'service advisor', 'automotive service advisor', 'service reception',
                    'customer service automotive', 'service consultant',
                    # Немецкий
                    'serviceberater', 'kfz serviceberater', 'kundenberater automotive',
                    'annahme mitarbeiter',
                    # Французский
                    'conseiller service', 'réceptionnaire atelier', 'conseiller clientèle auto',
                    # Испанский
                    'asesor de servicio', 'recepcionista taller', 'consultor automotriz',
                    # Итальянский
                    'consulente servizio', 'addetto accettazione', 'consulente automotive',
                    # Нидерландский
                    'service adviseur', 'auto service consultant', 'klanten adviseur',
                    # Польский
                    'doradca serwisowy', 'konsultant serwisu', 'przyjmujący zlecenia',
                    # Чешский
                    'servisní poradce', 'poradce servisu', 'konzultant automotive'
                ],
                
                'Кузовщик': [
                    # Английский
                    'panel beater', 'body repair technician', 'bodyshop technician',
                    'auto body repairer', 'collision repair specialist',
                    # Немецкий
                    'karosseriebauer', 'karosserie und fahrzeugbaumechaniker', 'unfallreparatur',
                    'karosserie techniker',
                    # Французский
                    'carrossier', 'réparateur carrosserie', 'technicien carrosserie',
                    # Испанский
                    'chapista', 'técnico carrocería', 'reparador carrocería',
                    # Итальянский
                    'carrozziere', 'tecnico carrozzeria', 'riparatore carrozzeria',
                    # Нидерландский
                    'carrosserie monteur', 'plaatwerker auto', 'bodywork technicus',
                    # Польский
                    'blacharz samochodowy', 'karoser', 'specjalista karoserii',
                    # Чешский
                    'karosář', 'technik karoserie', 'opravář karoserie'
                ],
                
                'Маляр по авто': [
                    # Английский
                    'car painter', 'automotive painter', 'bodyshop painter',
                    'vehicle painter', 'auto refinisher',
                    # Немецкий
                    'fahrzeuglackierer', 'auto lackierer', 'karosserie lackierer',
                    # Французский
                    'peintre automobile', 'peintre carrossier', 'laqueur auto',
                    # Испанский
                    'pintor automotriz', 'pintor de autos', 'laqueador automotriz',
                    # Итальянский
                    'verniciatore auto', 'pittore carrozzeria', 'laccatore automotive',
                    # Нидерландский
                    'autospuiter', 'voertuig schilder', 'carrosserie spuiter',
                    # Польский
                    'lakiernik samochodowy', 'malarz samochodowy', 'lakiernik automotive',
                    # Чешский
                    'lakýrník vozidel', 'natěrač automotive', 'malíř karoserie'
                ]
            },
            
            '⛽ АЗС И ТОПЛИВО': {
                'Заправщик на АЗС': [
                    # Английский
                    'gas station attendant', 'fuel attendant', 'pump attendant',
                    'petrol station worker', 'service station attendant', 'fuel station operator',
                    # Немецкий
                    'tankstellenmitarbeiter', 'mitarbeiter tankstelle', 'tankwart',
                    'tankstellen verkäufer', 'zapfsäulen bediener',
                    # Французский
                    'employé station-service', 'pompiste', 'agent station essence',
                    'vendeur carburant', 'opérateur station',
                    # Испанский
                    'empleado gasolinera', 'despachador combustible', 'operador estación',
                    'vendedor gasolina', 'asistente estación servicio',
                    # Итальянский
                    'addetto distributore', 'benzinai', 'operatore stazione servizio',
                    'addetto carburanti', 'impiegato stazione',
                    # Нидерландский
                    'tankstation medewerker', 'pompbediende', 'benzinestation bediende',
                    'brandstof verkoper', 'service station medewerker',
                    # Польский
                    'pracownik stacji paliw', 'dystrybutor paliw', 'obsługa stacji benzynowej',
                    'sprzedawca paliw', 'operator stacji',
                    # Чешский
                    'čerpač pohonných hmot', 'obsluha čerpací stanice', 'prodavač paliv',
                    'pracovník benzínky', 'operátor čerpací stanice'
                ],
                
                'Оператор АЗС': [
                    # Английский
                    'fuel station operator', 'gas station operator', 'fuel station supervisor',
                    'petrol station manager', 'fuel depot operator',
                    # Немецкий
                    'tankstellen operator', 'tankstellenleiter', 'tankstellen supervisor',
                    # Французский
                    'opérateur station-service', 'responsable station essence', 'superviseur station',
                    # Испанский
                    'operador estación servicio', 'supervisor gasolinera', 'encargado estación',
                    # Итальянский
                    'operatore stazione servizio', 'responsabile distributore', 'supervisore stazione',
                    # Нидерландский
                    'tankstation operator', 'benzinestation supervisor', 'station manager',
                    # Польский
                    'operator stacji paliw', 'kierownik stacji', 'nadzorca stacji',
                    # Чешский
                    'operátor čerpací stanice', 'vedoucí benzínky', 'supervizor stanice'
                ],
                
                'Кассир на АЗС': [
                    # Английский
                    'gas station cashier', 'fuel station cashier', 'petrol station cashier',
                    'service station cashier', 'pump cashier',
                    # Немецкий
                    'kassierer tankstelle', 'tankstellen kassierer', 'verkäufer tankstelle',
                    # Французский
                    'caissier station-service', 'caissière station essence', 'vendeur station',
                    # Испанский
                    'cajero gasolinera', 'cajera estación servicio', 'vendedor estación',
                    # Итальянский
                    'cassiere stazione servizio', 'cassiera distributore', 'addetto cassa stazione',
                    # Нидерландский
                    'kassier tankstation', 'kassa medewerker benzinestation', 'verkoper station',
                    # Польский
                    'kasjer stacji paliw', 'sprzedawca stacji', 'obsługa kasy stacji',
                    # Чешский
                    'pokladní čerpací stanice', 'prodavač benzínky', 'kassier stanice'
                ]
            },
            
            '🛢️ НЕФТЬ И ГАЗ': {
                'Оператор добычи': [
                    # Английский
                    'oilfield operator', 'production operator', 'oil & gas operator',
                    'well operator', 'drilling operator', 'field operator',
                    'roustabout', 'roughneck', 'derrickhand', 'oil rig worker',
                    # Немецкий
                    'öl und gas operator', 'förderanlagenbediener', 'bohrinsel arbeiter',
                    'erdöl techniker', 'produktions operator',
                    # Французский
                    'opérateur pétrolier', 'technicien pétrole gaz', 'foreur pétrolier',
                    'ouvrier plateforme', 'opérateur production',
                    # Испанский
                    'operador petrolífero', 'técnico petróleo gas', 'perforador petrolero',
                    'operario plataforma', 'operador producción',
                    # Итальянский
                    'operatore petrolifero', 'tecnico petrolio gas', 'perforatore petrolifero',
                    'operaio piattaforma', 'operatore produzione',
                    # Нидерландский
                    'olie gas operator', 'booreiland werker', 'productie operator',
                    'oliefield operator', 'petroleum technicus',
                    # Польский
                    'operator wydobycia', 'pracownik ropy naftowej', 'operator wiertniczy',
                    'technik naftowy', 'operator produkcji',
                    # Чешский
                    'operátor těžby', 'pracovník ropy plynu', 'vrtný operátor',
                    'technik ropný', 'operátor produkce'
                ],
                
                'Помощник бурильщика': [
                    # Английский
                    'floorhand', 'derrickman', 'drilling assistant', 'roughneck',
                    'drilling helper', 'rig worker', 'drilling crew',
                    # Немецкий
                    'bohrhelfer', 'helfer bohranlage', 'bohrassistent',
                    'bohrarbeiter', 'bohrmannschaft',
                    # Французский
                    'aide foreur', 'assistant forage', 'ouvrier forage',
                    'manoeuvre forage', 'équipe forage',
                    # Испанский
                    'ayudante perforador', 'asistente perforación', 'obrero perforación',
                    'auxiliar perforador', 'equipo perforación',
                    # Итальянский
                    'assistente perforatore', 'aiuto perforazione', 'operaio perforazione',
                    'ausiliario perforatore', 'squadra perforazione',
                    # Нидерландский
                    'boor assistent', 'boor helper', 'boring medewerker',
                    'boorploeg werker', 'drilling assistent',
                    # Польский
                    'pomocnik wiertacza', 'asystent wiercenia', 'robotnik wiertniczy',
                    'pomocniczy wiertacz', 'ekipa wiertnicza',
                    # Чешский
                    'pomocník vrtače', 'asistent vrtání', 'pracovník vrtání',
                    'pomocný vrtač', 'vrtná četa'
                ],
                
                'Рабочий нефтебазы': [
                    # Английский
                    'oil depot worker', 'petroleum terminal operator', 'tank farm operator',
                    'fuel terminal worker', 'oil storage worker', 'refinery worker',
                    # Немецкий
                    'erdöllager arbeiter', 'terminalmitarbeiter', 'tanklager operator',
                    'raffinerie arbeiter', 'kraftstofflager mitarbeiter',
                    # Французский
                    'ouvrier dépôt pétrolier', 'employé terminal', 'opérateur terminal',
                    'agent dépôt carburant', 'travailleur raffinerie',
                    # Испанский
                    'trabajador depósito petróleo', 'operario terminal', 'operador terminal',
                    'empleado depósito combustible', 'obrero refinería',
                    # Итальянский
                    'operaio deposito petrolio', 'addetto terminal', 'operatore terminal',
                    'lavoratore deposito carburante', 'operaio raffineria',
                    # Нидерландский
                    'olie depot werker', 'terminal operator', 'brandstof depot medewerker',
                    'raffinaderij werker', 'tank park operator',
                    # Польский
                    'pracownik bazy paliwowej', 'operator terminalu', 'robotnik rafinerii',
                    'magazynier paliw', 'operator składu',
                    # Чешский
                    'pracovník ropné základny', 'operátor terminálu', 'dělník rafinerie',
                    'skladník paliv', 'operátor skladu'
                ]
            },
            
            
            
            '🏗️ СТРОИТЕЛЬСТВО И ПРОИЗВОДСТВО': {
                'Строитель-разнорабочий': [
                    # Английский
                    'construction worker', 'builder', 'construction labourer',
                    # Немецкий
                    'bauarbeiter', 'handwerker', 'bauhilfsarbeiter',
                    # Французский
                    'ouvrier bâtiment', 'manoeuvre', 'ouvrier construction',
                    # Испанский
                    'obrero construcción', 'peón', 'albañil ayudante',
                    # Итальянский
                    'operaio edile', 'manovale', 'operaio cantiere',
                    # Нидерландский
                    'bouwvakker', 'grondwerker', 'bouw medewerker',
                    # Польский
                    'robotnik budowlany', 'pracownik budowy', 'pomocnik',
                    # Чешский
                    'stavební dělník', 'pracovník stavby', 'pomocník'
                ],
                
                'Грузчик': [
                    # Английский
                    'warehouse worker', 'loader', 'packer',
                    # Немецкий
                    'lagerarbeiter', 'kommissionierer', 'packer',
                    # Французский
                    'manutentionnaire', 'préparateur commandes', 'magasinier',
                    # Испанский
                    'operario almacén', 'mozo', 'preparador pedidos',
                    # Итальянский
                    'magazziniere', 'addetto picking', 'operatore',
                    # Нидерландский
                    'magazijnmedewerker', 'orderpicker', 'lader',
                    # Польский
                    'magazynier', 'pakowacz', 'pracownik magazynu',
                    # Чешский
                    'skladník', 'balič', 'pracovník skladu'
                ],
                
                'Складской работник': [
                    # Английский
                    'warehouse operative', 'stock handler', 'logistics worker',
                    # Немецкий
                    'lagermitarbeiter', 'logistikmitarbeiter', 'lagerist',
                    # Французский
                    'agent logistique', 'employé entrepôt', 'gestionnaire stock',
                    # Испанский
                    'operario logística', 'empleado almacén', 'gestor stock',
                    # Итальянский
                    'addetto logistica', 'operatore magazzino', 'addetto stock',
                    # Нидерландский
                    'logistiek medewerker', 'voorraad beheerder', 'warehouse',
                    # Польский
                    'logistyk', 'pracownik logistyczny', 'operator magazynu',
                    # Чешский
                    'logistik', 'skladový pracovník', 'operátor skladu'
                ],
                
                'Разнорабочий': [
                    # Английский
                    'general worker', 'manual worker', 'helper',
                    # Немецкий
                    'hilfsarbeiter', 'allrounder', 'arbeiter',
                    # Французский
                    'ouvrier polyvalent', 'manoeuvre', 'aide général',
                    # Испанский
                    'peón general', 'auxiliar', 'trabajador manual',
                    # Итальянский
                    'operaio generico', 'tuttofare', 'ausiliario',
                    # Нидерландский
                    'algemeen medewerker', 'handwerker', 'hulpkracht',
                    # Польский
                    'robotnik', 'pracownik fizyczny', 'pomocnik',
                    # Чешский
                    'dělník', 'pomocný pracovník', 'manuální pracovník'
                ],
                
                'Рабочий на производстве': [
                    # Английский
                    'factory worker', 'production worker', 'manufacturing operative',
                    # Немецкий
                    'produktionsmitarbeiter', 'fabrikarbeiter', 'fertigungsmitarbeiter',
                    # Французский
                    'ouvrier production', 'opérateur machine', 'agent fabrication',
                    # Испанский
                    'operario producción', 'trabajador fábrica', 'operador máquina',
                    # Итальянский
                    'operaio produzione', 'addetto produzione', 'operatore macchine',
                    # Нидерландский
                    'productiemedewerker', 'fabriekarbeider', 'machine operator',
                    # Польский
                    'robotnik produkcyjny', 'operator maszyn', 'pracownik fabryki',
                    # Чешский
                    'výrobní dělník', 'operátor strojů', 'tovární dělník'
                ]
            },
            
            '🍽️ ОБЩЕПИТ И СЕРВИС': {
                'Официант': [
                    # Английский
                    'waiter', 'waitress', 'server',
                    # Немецкий
                    'kellner', 'kellnerin', 'bedienung',
                    # Французский
                    'serveur', 'serveuse', 'garçon de café',
                    # Испанский
                    'camarero', 'camarera', 'mesero',
                    # Итальянский
                    'cameriere', 'cameriera', 'addetto sala',
                    # Нидерландский
                    'ober', 'serveerster', 'bediening',
                    # Польский
                    'kelner', 'kelnerka', 'obsługa',
                    # Чешский
                    'číšník', 'číšnice', 'obsluha'
                ],
                
                'Бармен': [
                    # Английский
                    'bartender', 'barman', 'mixologist',
                    # Немецкий
                    'barkeeper', 'barmann', 'barmixer',
                    # Французский
                    'barman', 'barmaid', 'mixologue',
                    # Испанский
                    'barman', 'cantinero', 'coctelero',
                    # Итальянский
                    'barista', 'barman', 'addetto bar',
                    # Нидерландский
                    'barkeeper', 'barman', 'bartender',
                    # Польский
                    'barman', 'barista', 'obsługa baru',
                    # Чешский
                    'barman', 'barmanka', 'obsluha baru'
                ],
                
                'Повар': [
                    # Английский
                    'chef', 'cook', 'kitchen chef',
                    # Немецкий
                    'koch', 'küchenchef', 'chefkoch',
                    # Французский
                    'cuisinier', 'chef cuisinier', 'commis cuisine',
                    # Испанский
                    'cocinero', 'chef', 'cocinero jefe',
                    # Итальянский
                    'cuoco', 'chef', 'addetto cucina',
                    # Нидерландский
                    'kok', 'chef-kok', 'keukenhulp',
                    # Польский
                    'kucharz', 'szef kuchni', 'pracownik kuchni',
                    # Чешский
                    'kuchař', 'šéfkuchař', 'kuchařka'
                ],
                
                'Помощник повара': [
                    # Английский
                    'kitchen assistant', 'commis chef', 'prep cook',
                    # Немецкий
                    'küchenhilfe', 'küchengehilfe', 'hilfskoch',
                    # Французский
                    'aide cuisinier', 'commis cuisine', 'assistant cuisine',
                    # Испанский
                    'ayudante cocina', 'auxiliar cocina', 'pinche',
                    # Итальянский
                    'aiuto cuoco', 'commis', 'assistente cucina',
                    # Нидерландский
                    'keukenhulp', 'kok assistent', 'keuken medewerker',
                    # Польский
                    'pomoc kuchenna', 'pomocnik kucharza', 'kucharz pomocniczy',
                    # Чешский
                    'kuchařka pomocná', 'pomocník kuchaře', 'kuchyňský pomocník'
                ],
                
                'Посудомойщик': [
                    # Английский
                    'dishwasher', 'kitchen porter', 'pot washer',
                    # Немецкий
                    'spüler', 'abwäscher', 'geschirrspüler',
                    # Французский
                    'plongeur', 'laveur vaisselle', 'aide plonge',
                    # Испанский
                    'friegaplatos', 'lavavajillas', 'ayudante cocina',
                    # Итальянский
                    'lavapiatti', 'sguattero', 'addetto pulizie',
                    # Нидерландский
                    'afwasser', 'spoeler', 'keuken hulp',
                    # Польский
                    'zmywacz', 'pomywacz', 'pracownik kuchni',
                    # Чешский
                    'umývač nádoba', 'pomocník kuchyně', 'dishwasher'
                ],
                
                'Кассир': [
                    # Английский
                    'cashier', 'till operator', 'checkout operator',
                    # Немецкий
                    'kassierer', 'kassiererin', 'kasse',
                    # Французский
                    'caissier', 'caissière', 'hôtesse caisse',
                    # Испанский
                    'cajero', 'cajera', 'operador caja',
                    # Итальянский
                    'cassiere', 'cassiera', 'addetto cassa',
                    # Нидерландский
                    'kassière', 'kassamedewerker', 'caissier',
                    # Польский
                    'kasjer', 'kasjerka', 'obsługa kasy',
                    # Чешский
                    'pokladník', 'pokladní', 'obsluha pokladny'
                ],
                
                'Продавец': [
                    # Английский
                    'shop assistant', 'sales assistant', 'retail assistant',
                    # Немецкий
                    'verkäufer', 'verkäuferin', 'einzelhandel',
                    # Французский
                    'vendeur', 'vendeuse', 'conseiller vente',
                    # Испанский
                    'vendedor', 'dependiente', 'auxiliar ventas',
                    # Итальянский
                    'commesso', 'commessa', 'addetto vendite',
                    # Нидерландский
                    'verkoper', 'winkelmedewerker', 'verkoopster',
                    # Польский
                    'sprzedawca', 'sprzedawczyni', 'konsultant',
                    # Чешский
                    'prodavač', 'prodavačka', 'obsluha'
                ]
            },
            
            '🏡 СЕРВИС И ОБСЛУЖИВАНИЕ': {
                'Уборщик': [
                    # Английский
                    'cleaner', 'janitor', 'cleaning operative',
                    # Немецкий
                    'reinigungskraft', 'putzkraft', 'hausmeister',
                    # Французский
                    'agent entretien', 'femme ménage', 'nettoyeur',
                    # Испанский
                    'limpiador', 'conserje', 'empleada limpieza',
                    # Итальянский
                    'addetto pulizie', 'operatore ecologico', 'pulitore',
                    # Нидерландский
                    'schoonmaker', 'huishoudelijke hulp', 'cleaner',
                    # Польский
                    'sprzątacz', 'sprzątaczka', 'pracownik sprzątający',
                    # Чешский
                    'uklízečka', 'údržbář', 'čistič'
                ],
                
                'Садовник': [
                    # Английский
                    'gardener', 'landscaper', 'groundskeeper',
                    # Немецкий
                    'gärtner', 'landschaftsgärtner', 'gartenpfleger',
                    # Французский
                    'jardinier', 'paysagiste', 'espaces verts',
                    # Испанский
                    'jardinero', 'paisajista', 'jardinero mantenimiento',
                    # Итальянский
                    'giardiniere', 'paesaggista', 'manutentore verde',
                    # Нидерландский
                    'tuinman', 'hovenier', 'groenvoorziening',
                    # Польский
                    'ogrodnik', 'architekt krajobrazu', 'pracownik zieleni',
                    # Чешский
                    'zahradník', 'krajinář', 'údržba zeleně'
                ],
                
                'Домработница': [
                    # Английский
                    'housekeeper', 'domestic worker', 'home help',
                    # Немецкий
                    'haushälterin', 'haushaltshilfe', 'putzfrau',
                    # Французский
                    'femme ménage', 'aide ménagère', 'employée maison',
                    # Испанский
                    'empleada doméstica', 'asistenta hogar', 'limpiadora',
                    # Итальянский
                    'domestica', 'colf', 'addetta domestica',
                    # Нидерландский
                    'huishoudster', 'huishoudelijke hulp', 'inwonende hulp',
                    # Польский
                    'gospodyni', 'pomoc domowa', 'sprzątaczka domowa',
                    # Чешский
                    'hospodyně', 'domácí pomocnice', 'uklízečka'
                ],
                
                'Массажист': [
                    # Английский
                    'massage therapist', 'masseur', 'physiotherapist',
                    # Немецкий
                    'masseur', 'physiotherapeut', 'wellness therapeut',
                    # Французский
                    'masseur', 'kinésithérapeute', 'thérapeute',
                    # Испанский
                    'masajista', 'fisioterapeuta', 'terapeuta',
                    # Итальянский
                    'massaggiatore', 'fisioterapista', 'operatore wellness',
                    # Нидерландский
                    'masseur', 'fysiotherapeut', 'wellness therapeut',
                    # Польский
                    'masażysta', 'fizjoterapeuta', 'terapeuta',
                    # Чешский
                    'masér', 'fyzioterapeut', 'wellness terapeut'
                ]
            },

            '👥 УХОД И МЕДИЦИНА': {
                'Медсестра': [
                    # Английский
                    'nurse', 'healthcare assistant', 'nursing assistant',
                    # Немецкий
                    'krankenschwester', 'pflegekraft', 'gesundheitspfleger',
                    # Французский
                    'infirmier', 'infirmière', 'aide soignant',
                    # Испанский
                    'enfermero', 'enfermera', 'auxiliar enfermería',
                    # Итальянский
                    'infermiere', 'infermiera', 'operatore sanitario',
                    # Нидерландский
                    'verpleegkundige', 'zorgverlener', 'nurse',
                    # Польский
                    'pielęgniarka', 'opiekun medyczny', 'asystent pielęgniarki',
                    # Чешский
                    'zdravotní sestra', 'ošetřovatel', 'zdravotník'
                ],
                
                'Сиделка': [
                    # Английский
                    'caregiver', 'care worker', 'support worker',
                    # Немецкий
                    'betreuer', 'altenpfleger', 'pflegehelfer',
                    # Французский
                    'aide à domicile', 'auxiliaire vie', 'accompagnant',
                    # Испанский
                    'cuidador', 'auxiliar ayuda domicilio', 'asistente personal',
                    # Итальянский
                    'badante', 'assistente domiciliare', 'operatore socio',
                    # Нидерландский
                    'verzorgende', 'thuiszorg', 'zorgverlener',
                    # Польский
                    'opiekun', 'opiekunka', 'asystent osoby',
                    # Чешский
                    'pečovatel', 'ošetřovatel', 'asistent'
                ],
                
                'Няня': [
                    # Английский
                    'nanny', 'babysitter', 'childcare worker',
                    # Немецкий
                    'kindermädchen', 'babysitter', 'kinderbetreuung',
                    # Французский
                    'nounou', 'garde enfants', 'assistante maternelle',
                    # Испанский
                    'niñera', 'cuidadora niños', 'educadora infantil',
                    # Итальянский
                    'babysitter', 'tata', 'educatrice',
                    # Нидерландский
                    'kinderopvang', 'babysit', 'oppas',
                    # Польский
                    'opiekunka dzieci', 'niania', 'wychowawca',
                    # Чешский
                    'chůva', 'babysitter', 'pečovatelka'
                ],
                
                'Гувернантка': [
                    # Английский
                    'governess', 'au pair', 'childminder',
                    # Немецкий
                    'gouvernante', 'au pair', 'erzieherin',
                    # Французский
                    'gouvernante', 'au pair', 'préceptrice',
                    # Испанский
                    'institutriz', 'au pair', 'cuidadora interna',
                    # Итальянский
                    'governante', 'au pair', 'istitutrice',
                    # Нидерландский
                    'gouvernante', 'au pair', 'kindjuf',
                    # Польский
                    'guwernantka', 'au pair', 'opiekunka',
                    # Чешский
                    'vychovatelka', 'au pair', 'guvernantka'
                ],
                
                'Уход за пенсионерами': [
                    # Английский
                    'elderly care', 'senior care', 'care home worker',
                    # Немецкий
                    'altenpflege', 'seniorenbetreuung', 'altenheim',
                    # Французский
                    'aide personnes âgées', 'gériatrie', 'ehpad',
                    # Испанский
                    'cuidado ancianos', 'geriátrico', 'residencia mayores',
                    # Итальянский
                    'assistenza anziani', 'casa riposo', 'operatore geriatrico',
                    # Нидерландский
                    'ouderenzorg', 'bejaardenzorg', 'verzorgingshuis',
                    # Польский
                    'opieka nad seniorami', 'dom opieki', 'geriatria',
                    # Чешский
                    'péče o seniory', 'domov důchodců', 'geriatrie'
                ]
            },
            
            '💻 IT И ТЕХНОЛОГИИ': {
                'Python разработчик': [
                    # Английский
                    'python developer', 'python programmer', 'python engineer',
                    # Немецкий
                    'python entwickler', 'python programmierer', 'software entwickler python',
                    # Французский
                    'développeur python', 'programmeur python', 'ingénieur python',
                    # Испанский
                    'desarrollador python', 'programador python', 'ingeniero python',
                    # Итальянский
                    'sviluppatore python', 'programmatore python', 'python developer',
                    # Нидерландский
                    'python ontwikkelaar', 'python programmeur', 'software developer',
                    # Польский
                    'programista python', 'developer python', 'inżynier python',
                    # Чешский
                    'python vývojář', 'python programátor', 'software developer'
                ],
                
                'Веб-разработчик': [
                    # Английский
                    'web developer', 'frontend developer', 'full stack developer',
                    # Немецкий
                    'webentwickler', 'frontend entwickler', 'web programmierer',
                    # Французский
                    'développeur web', 'développeur frontend', 'programmeur web',
                    # Испанский
                    'desarrollador web', 'frontend developer', 'programador web',
                    # Итальянский
                    'sviluppatore web', 'web developer', 'programmatore web',
                    # Нидерландский
                    'web ontwikkelaar', 'frontend developer', 'webprogrammeur',
                    # Польский
                    'programista web', 'frontend developer', 'web developer',
                    # Чешский
                    'web vývojář', 'frontend developer', 'webový programátor'
                ],
                
                'Программист': [
                    # Английский
                    'software developer', 'programmer', 'software engineer',
                    # Немецкий
                    'software entwickler', 'programmierer', 'informatiker',
                    # Французский
                    'développeur logiciel', 'programmeur', 'ingénieur logiciel',
                    # Испанский
                    'desarrollador software', 'programador', 'ingeniero software',
                    # Итальянский
                    'sviluppatore software', 'programmatore', 'ingegnere software',
                    # Нидерландский
                    'software ontwikkelaar', 'programmeur', 'software engineer',
                    # Польский
                    'programista', 'developer', 'inżynier oprogramowania',
                    # Чешский
                    'programátor', 'vývojář software', 'software developer'
                ],
                
                'Дата-аналитик': [
                    # Английский
                    'data analyst', 'data scientist', 'business analyst',
                    # Немецкий
                    'datenanalyst', 'data scientist', 'business analyst',
                    # Французский
                    'analyste données', 'data scientist', 'analyste business',
                    # Испанский
                    'analista datos', 'científico datos', 'analista negocio',
                    # Итальянский
                    'analista dati', 'data scientist', 'business analyst',
                    # Нидерландский
                    'data analist', 'data scientist', 'business analist',
                    # Польский
                    'analityk danych', 'data scientist', 'analityk biznesowy',
                    # Чешский
                    'datový analytik', 'data scientist', 'business analytik'
                ],
                
                'Системный администратор': [
                    # Английский
                    'system administrator', 'sysadmin', 'IT support',
                    # Немецкий
                    'systemadministrator', 'it administrator', 'system admin',
                    # Французский
                    'administrateur système', 'admin système', 'support technique',
                    # Испанский
                    'administrador sistemas', 'sysadmin', 'soporte técnico',
                    # Итальянский
                    'amministratore sistema', 'sysadmin', 'supporto tecnico',
                    # Нидерландский
                    'systeembeheerder', 'it beheerder', 'technisch support',
                    # Польский
                    'administrator systemu', 'sysadmin', 'wsparcie techniczne',
                    # Чешский
                    'správce systému', 'sysadmin', 'technická podpora'
                ],
            
                'Тестировщик': [
                    # Английский  
                    'QA engineer', 'software tester', 'quality assurance',
                    # Немецкий
                    'software tester', 'qa engineer', 'qualitätssicherung',
                    # Французский
                    'testeur logiciel', 'ingénieur qa', 'assurance qualité',
                    # Испанский
                    'tester software', 'ingeniero qa', 'control calidad',
                    # Итальянский
                    'tester software', 'qa engineer', 'controllo qualità',
                    # Нидерландский
                    'software tester', 'qa engineer', 'kwaliteitscontrole',
                    # Польский
                    'tester oprogramowania', 'inżynier qa', 'kontrola jakości',
                    # Чешский
                    'tester software', 'qa inženýr', 'kontrola kvality'
                ]
            },

            '👔 ОФИС И УПРАВЛЕНИЕ': {
                'Менеджер': [
                    # Английский
                    'manager', 'management', 'team leader',
                    # Немецкий
                    'manager', 'teamleiter', 'führungskraft',
                    # Французский
                    'manager', 'responsable', 'chef équipe',
                    # Испанский
                    'manager', 'gerente', 'jefe equipo',
                    # Итальянский
                    'manager', 'responsabile', 'capo squadra',
                    # Нидерландский
                    'manager', 'teamleider', 'leidinggevende',
                    # Польский
                    'manager', 'kierownik', 'lider zespołu',
                    # Чешский
                    'manažer', 'vedoucí', 'vedoucí týmu'
                ],
            
                'Администратор': [
                    # Английский
                    'administrator', 'admin', 'office manager',
                    # Немецкий
                    'administrator', 'bürokaufmann', 'verwaltung',
                    # Французский
                    'administrateur', 'gestionnaire bureau', 'secrétaire',
                    # Испанский
                    'administrador', 'gestor oficina', 'administrativo',
                    # Итальянский
                    'amministratore', 'impiegato', 'segretario',
                    # Нидерландский
                    'administrateur', 'kantoormedewerker', 'beheerder',
                    # Польский
                    'administrator', 'pracownik biurowy', 'sekretarz',
                    # Чешский
                    'administrátor', 'úředník', 'sekretář'
                ],
            
                'Координатор': [
                    # Английский
                    'coordinator', 'project coordinator', 'team coordinator',
                    # Немецкий
                    'koordinator', 'projektkoordinator', 'sachbearbeiter',
                    # Французский
                    'coordinateur', 'coordinateur projet', 'chargé mission',
                    # Испанский
                    'coordinador', 'coordinador proyecto', 'gestor proyectos',
                    # Итальянский
                    'coordinatore', 'coordinatore progetto', 'responsabile',
                    # Нидерландский
                    'coördinator', 'projectcoördinator', 'teamcoördinator',
                    # Польский
                    'koordynator', 'koordynator projektu', 'specjalista',
                    # Чешский
                    'koordinátor', 'projektový koordinátor', 'specialista'
                ],
            
                'Аналитик': [
                    # Английский
                    'business analyst', 'data analyst', 'analyst',
                    # Немецкий
                    'business analyst', 'analyst', 'sachbearbeiter',
                    # Французский
                    'analyste business', 'analyste', 'chargé études',
                    # Испанский
                    'analista negocio', 'analista', 'consultor',
                    # Итальянский
                    'business analyst', 'analista', 'consulente',
                    # Нидерландский
                    'business analist', 'analist', 'consultant',
                    # Польский
                    'analityk biznesowy', 'analityk', 'konsultant',
                    # Чешский
                    'business analytik', 'analytik', 'konzultant'
                ]
            },
        
            '🇺🇦 ДЛЯ УКРАИНСКИХ БЕЖЕНЦЕВ': {
                'Работа для украинцев': [
                    # Английский
                    'ukrainian speaker', 'ukrainian support', 'ukraine refugee',
                    # Немецкий
                    'ukrainisch sprecher', 'ukraine hilfe', 'flüchtling',
                    # Французский
                    'ukrainien locuteur', 'aide ukraine', 'réfugié',
                    # Испанский
                    'hablante ucraniano', 'ayuda ucrania', 'refugiado',
                    # Итальянский
                    'parlante ucraino', 'aiuto ucraina', 'profugo',
                    # Нидерландский
                    'oekraïens spreker', 'oekraïne hulp', 'vluchteling',
                    # Польский
                    'mówiący ukraiński', 'pomoc ukraina', 'uchodźca',
                    # Чешский
                    'ukrajinsky mluvčí', 'pomoc ukrajina', 'uprchlík'
                ],
            
                'Программы поддержки': [
                    # Английский
                    'refugee support', 'integration program', 'newcomer program',
                    # Немецкий
                    'flüchtlingshilfe', 'integrationsprogramm', 'newcomer',
                    # Французский
                    'aide réfugiés', 'programme intégration', 'accueil',
                    # Испанский
                    'ayuda refugiados', 'programa integración', 'acogida',
                    # Итальянский
                    'aiuto profughi', 'programma integrazione', 'accoglienza',
                    # Нидерландский
                    'vluchtelingenhulp', 'integratieprogramma', 'opvang',
                    # Польский
                    'pomoc uchodźcom', 'program integracyjny', 'wsparcie',
                    # Чешский
                    'pomoc uprchlíkům', 'integrační program', 'podpora'
                ],
            
                'Переводчик украинского': [
                    # Английский
                    'ukrainian translator', 'ukrainian interpreter', 'translator',
                    # Немецкий
                    'ukrainisch übersetzer', 'dolmetscher', 'sprachmittler',
                    # Французский
                    'traducteur ukrainien', 'interprète', 'traducteur',
                    # Испанский
                    'traductor ucraniano', 'intérprete', 'traductor',
                    # Итальянский
                    'traduttore ucraino', 'interprete', 'traduttore',
                    # Нидерландский
                    'oekraïens vertaler', 'tolk', 'vertaler',
                    # Польский
                    'tłumacz ukraiński', 'tłumacz', 'interpreter',
                    # Чешский
                    'ukrajinsky překladatel', 'tlumočník', 'překladatel'
                ],
            
                'Поддержка беженцев': [
                    # Английский
                    'refugee assistance', 'asylum support', 'humanitarian aid',
                    # Немецкий
                    'flüchtlingsbetreuung', 'asylhilfe', 'humanitäre hilfe',
                    # Французский
                    'assistance réfugiés', 'aide asile', 'aide humanitaire',
                    # Испанский
                    'asistencia refugiados', 'apoyo asilo', 'ayuda humanitaria',
                    # Итальянский
                    'assistenza profughi', 'supporto asilo', 'aiuto umanitario',
                    # Нидерландский
                    'vluchtelingenopvang', 'asielzoekers', 'humanitaire hulp',
                    # Польский
                    'pomoc uchodźcom', 'wsparcie azyl', 'pomoc humanitarna',
                    # Чешский
                    'pomoc uprchlíkům', 'azylová pomoc', 'humanitární pomoc'
                ],
            
                'Работа без языка для украинцев': [
                    # Английский
                    'no language ukrainian', 'physical work ukraine', 'manual work',
                    # Немецкий
                    'ohne sprache ukraine', 'körperliche arbeit', 'hilfstätigkeit',
                    # Французский
                    'sans langue ukraine', 'travail physique', 'travail manuel',
                    # Испанский
                    'sin idioma ucrania', 'trabajo físico', 'trabajo manual',
                    # Итальянский
                    'senza lingua ucraina', 'lavoro fisico', 'lavoro manuale',
                    # Нидерландский
                    'zonder taal oekraïne', 'fysiek werk', 'handwerk',
                    # Польский
                    'bez języka ukraina', 'praca fizyczna', 'praca manualna',
                    # Чешский
                    'bez jazyka ukrajina', 'fyzická práce', 'manuální práce'
                ]
            },
        
            '🔍 ДРУГОЕ': {
                "Другие вакансии": [
                    # Английский
                    'general worker', 'manual worker', 'unskilled', 'labourer', 'warehouse worker',
                    'cleaner', 'janitor', 'kitchen assistant', 'waiter', 'shop assistant', 'packer',
                    # Немецкий
                    'helfer', 'aushilfe', 'ungelernt', 'hilfsarbeiter', 'lagerarbeiter', 'reiniger',
                    'küchenhilfe', 'servicekraft', 'verkaufsmitarbeiter', 'packer',
                    # Французский
                    'manutentionnaire', 'ouvrier', 'agent de nettoyage', 'agent d\'entretien', 'magasinier',
                    # Испанский
                    'trabajador general', 'peón', 'limpiador', 'mozo de almacén', 'camarero', 'ayudante de cocina',
                    # Итальянский
                    'operaio', 'lavoratore generico', 'addetto pulizie', 'magazziniere', 'cameriere',
                    # Нидерландский
                    'algemene werknemer', 'magazijnmedewerker', 'schoonmaker', 'keukenhulp',
                    # Польский
                    'pracownik fizyczny', 'magazynier', 'sprzątacz', 'pomoc kuchenna', 'kelner',
                    # Чешский
                    'dělník', 'skladník', 'uklízeč', 'pomocná síla', 'číšník'
                ],

            }
        }

        # Карта языков по странам
        self.COUNTRY_LANGUAGES = {
            'de': ['english', 'german'],
            'fr': ['english', 'french'],
            'es': ['english', 'spanish'],
            'it': ['english', 'italian'],
            'nl': ['english', 'dutch'],
            'pl': ['english', 'polish'],
            'cz': ['english', 'czech'],
            'gb': ['english'],
            'us': ['english'],
            'ca': ['english', 'french'],
            'au': ['english'],
            'at': ['english', 'german'],
            'ch': ['english', 'german', 'french'],
            'be': ['english', 'dutch', 'french'],
            'se': ['english'],
            'no': ['english'],
            'dk': ['english'],
            'sk': ['english', 'czech']
        }

        # Индексы языков в массивах терминов
        self.LANGUAGE_INDICES = {
            'english': 0,
            'german': 3,
            'french': 6,
            'spanish': 9,
            'italian': 12,
            'dutch': 15,
            'polish': 18,
            'czech': 21
        }
        
        print(f"🌍 GlobalJobAggregator v2.4 с умным кешированием")
        print(f"🔑 App ID: {self.app_id}")
        print(f"💾 Кеш: {'Redis + File' if self.cache_manager.redis_client else 'File only'}")
        print(f"🌍 Стран: {len(self.countries)} | Профессий: {sum(len(jobs) for jobs in self.specific_jobs.values())}")

    # Добавьте в класс GlobalJobAggregator после self.specific_jobs:

    def _inc_metric(self, field: str, n: int = 1):
        """Атомарно увеличивает метрику локально и в Redis (если он есть).
        Делает fallback: если CacheManager.redis_client отсутствует, создаём клиент из REDIS_URL/REDIS_TLS_URL.
        """
        # локально (как было)
        self.stats[field] = int(self.stats.get(field, 0)) + int(n)

        # глобально в Redis
        r = getattr(self.cache_manager, "redis_client", None)
        if r is None:
            try:
                import os, redis as _r
                _url = os.getenv("REDIS_TLS_URL") or os.getenv("REDIS_URL")
                if _url:
                    r = _r.from_url(_url, decode_responses=False)
            except Exception:
                r = None

        if r:
            try:
                r.hincrby("gjh:metrics:v1", field, int(n))
            except Exception:
                # не роняем поток поиска
                pass  
    
    def search_specific_jobs(self, preferences: Dict, progress_callback=None, cancel_check=None) -> List[JobVacancy]:
        """
        Поиск конкретных профессий:
        - Если есть общий кеш по всему запросу — берём как стартовый набор (и можем отдать в progress_callback),
        НО всё равно докачиваем недостающее через суб-кеш/онлайн.
        - Никогда не «только кеш», если нет глобального cooldown.
        """
        # 0) Стартовый набор из общего кеша (если есть)
        job_map: Dict[str, JobVacancy] = {}
        cached_full = self.cache_manager.get_cached_result(preferences)

        # --- НАЧАЛО ИЗМЕНЕНИЙ ---
        if cached_full:
            # ✅ СЧИТАЕМ ПОПАДАНИЕ В КЕШ
            self._inc_metric('cache_hits', 1)
            
            print(f"🎯 Общий кеш: {len(cached_full)} вакансий (стартовый набор)")
            for j in cached_full:
                url = getattr(j, 'apply_url', None)
                if url:
                    job_map[url] = j
            # по желанию — шевельнём прогресс небольшой партией
            if progress_callback and job_map:
                try:
                    progress_callback(list(job_map.values())[:10])
                except Exception:
                    pass
        else:
            # ❌ СЧИТАЕМ ПРОМАХ КЕША
            self._inc_metric('cache_misses', 1)
        # --- КОНЕЦ ИЗМЕНЕНИЙ ---

        # 1) Реальный поиск с суб-кешем (внутри _batch_search_jobs)
        #    ВАЖНО: progress_callback сюда не передаём — внутри он числовой,
        #    а в app.py ожидается список вакансий.
        all_jobs = self._perform_search(preferences, progress_callback=None, cancel_check=cancel_check)

        # 2) Склейка и финальный общий кеш
        for j in (all_jobs or []):
            url = getattr(j, 'apply_url', None)
            if url and url not in job_map:
                job_map[url] = j

        final_list = list(job_map.values())
        if final_list:
            self.cache_manager.cache_result(preferences, final_list)
            self._inc_metric('total_jobs_found', len(final_list))

        return final_list

    
    def _perform_search(self, preferences: Dict, progress_callback=None, cancel_check=None) -> List[JobVacancy]:
        """Выполнение поиска через API с поддержкой нескольких городов + circuit breaker + cancel_check."""
        all_jobs: List[JobVacancy] = []

        # если источник в cooldown — выходим сразу
        now = time.time()
        if getattr(self, "cooldown_until", 0) > now:
            left = int(self.cooldown_until - now)
            print(f"⛔ Adzuna: на cooldown ещё {left}s — пропускаем источник.")
            return self._deduplicate_jobs(all_jobs) if hasattr(self, '_deduplicate_jobs') else all_jobs

        selected_jobs = preferences['selected_jobs']
        countries = preferences['countries']

        # города из preferences (список)
        raw_cities = preferences.get('cities') or []
        if not raw_cities and preferences.get('city'):
            raw_cities = [preferences.get('city')]

        cities: List[str] = []
        for c in raw_cities:
            if not c:
                continue
            c_stripped = c.strip()
            if not c_stripped:
                continue
            c_key = c_stripped.lower()
            corrected = self.CITY_CORRECTIONS.get(c_key, c_stripped)
            if corrected != c_stripped:
                print(f"📍 Город '{c_stripped}' автоматически исправлен на '{corrected}'")
            cities.append(corrected)

        tasks = self._optimize_search_tasks(selected_jobs, countries)
        total_searches = sum(len(t['terms']) for t in tasks)
        current_search = 0

        try:
            for task in tasks:
                if cancel_check and cancel_check():
                    break
                country = task['country']
                terms = task['terms']

                cities_to_use = cities if cities else [None]
                for city in cities_to_use:
                    if cancel_check and cancel_check():
                        break

                    # ⚠️ прокидываем cancel_check вниз
                    jobs = self._batch_search_jobs(terms, country, city or '', 25, cancel_check=cancel_check)
                    current_search += 1

                    if jobs:
                        all_jobs.extend(jobs)
                        print(f"     ✅ Найдено: {len(jobs)} вакансий (страна={country}, город={city or '—'})")
                    else:
                        print(f"     ℹ️ Вакансий не найдено (страна={country}, город={city or '—'}) — продолжаем")

                    # Здесь progress_callback (если был) числовой; но в search_specific_jobs мы его не передаём.
                    if progress_callback:
                        progress_callback(min(current_search, total_searches), total_searches)

        except RateLimitedError:
            print("⛔ Adzuna: источник переведён в cooldown, завершаем поиск по Adzuna.")

        return self._deduplicate_jobs(all_jobs) if hasattr(self, '_deduplicate_jobs') else all_jobs



    
    def _optimize_search_tasks(self, selected_jobs: List[str], countries: List[str]) -> List[Dict]:
        """Оптимизация поисковых задач с учетом языков"""
        tasks = []
        
        search_other_jobs = 'Другие вакансии' in selected_jobs
        
        # Группируем все термины по странам для локализованного поиска
        for country in countries:
            country_terms = []
            
            # Собираем все термины для обычных профессий
            for job_name in selected_jobs:
                if job_name == 'Другие вакансии':
                    continue
                    
                for category, jobs in self.specific_jobs.items():
                    if job_name in jobs:
                        # Используем ВСЕ термины для локализации
                        country_terms.extend(jobs[job_name])
                        break
            
            # Добавляем задачу для обычных профессий
            if country_terms:
                tasks.append({
                    'job_name': 'Combined Localized Search',
                    'terms': country_terms,  # Все термины для локализации
                    'country': country
                })
            
            # Добавляем поиск "других вакансий"
            if search_other_jobs:
                tasks.append({
                    'job_name': 'Другие вакансии',
                    'terms': ['search_for_other_jobs'],
                    'country': country
                })
        
        return tasks
    
    def _get_localized_terms(self, job_terms: List[str], country: str) -> List[str]:
        """Выбор терминов поиска в зависимости от страны и языка"""
        if country not in self.COUNTRY_LANGUAGES:
            # Если страна не поддерживается, используем только английский
            return job_terms[:3]
        
        country_languages = self.COUNTRY_LANGUAGES[country]
        selected_terms = []
        
        # Для каждого поддерживаемого языка в стране выбираем термины
        for language in country_languages:
            if language in self.LANGUAGE_INDICES:
                start_idx = self.LANGUAGE_INDICES[language]
                end_idx = start_idx + 3  # Берем 3 термина на язык
                
                # Добавляем термины, если они существуют
                language_terms = job_terms[start_idx:end_idx]
                selected_terms.extend([term for term in language_terms if term])
        
        # Возвращаем максимум 6 терминов
        return selected_terms[:6]
    
    def _batch_search_jobs(self, terms: List[str], country: str, location: str = '', max_results: int = 25, cancel_check=None) -> List[JobVacancy]:
        """Поиск по списку терминов для одной страны/города + прерывание при 429/cancel + суб-кеш по термам."""
        if cancel_check and cancel_check():
            return []

        # если уже в cooldown — не ходим
        now = time.time()
        if getattr(self, "cooldown_until", 0) > now:
            left = int(self.cooldown_until - now)
            print(f"⛔ Adzuna: cooldown ещё {left}s — пропускаем batch.")
            raise RateLimitedError("ADZUNA_COOLDOWN")

        if country not in self.countries:
            return []

        all_jobs: List[JobVacancy] = []
        seen_urls = set()
        location = location or ''

        # какие именно термы реально пойдут в API для страны
        localized_terms = self._get_localized_terms(terms, country)
        country_name = self.countries[country]['name']
        languages = ', '.join(self.COUNTRY_LANGUAGES.get(country, ['english']))
        print(f"\n     🌍 Страна: {country_name}, языки поиска: {languages}")

        # 1) Сначала пытаемся вытащить из суб-кеша
        terms_to_fetch: List[str] = []
        for term in localized_terms:
            if cancel_check and cancel_check():
                break
            cached = self.cache_manager.get_term_cached_result(country, location, term)
            if cached is None:
                # нет записи — надо реально сходить в API
                terms_to_fetch.append(term)
                continue
            # есть запись (в том числе пустая) — подмешиваем, но не идём в API
            if cached:
                print(f"     💾 Subcache HIT для '{term}': {len(cached)}")
                for j in cached:
                    url = getattr(j, 'apply_url', None)
                    if not url or url in seen_urls:
                        continue
                    seen_urls.add(url)
                    all_jobs.append(j)
            else:
                print(f"     💾 Subcache HIT для '{term}': 0 (пропускаем запрос)")

        # 2) Для отсутствующих в суб-кеше терминов — реальные запросы в API
        for i, term in enumerate(terms_to_fetch, 1):
            if cancel_check and cancel_check():
                break
            print(f"     🔍 API-запрос {i}/{len(terms_to_fetch)}: '{term}'")
            try:
                chunk = self._search_single_term(term, country, location, 10, cancel_check=cancel_check)
            except RateLimitedError:
                # наверх — чтобы _perform_search завершил источник и включил переключение
                raise

            # Сохраняем в суб-кеш вне зависимости от результата (включая пустой список)
            try:
                self.cache_manager.cache_term_result(country, location, term, chunk or [])
            except Exception:
                pass

            if chunk:
                print(f"     📊 Найдено для '{term}': {len(chunk)} вакансий")
                for j in chunk:
                    url = getattr(j, 'apply_url', None)
                    if not url or url in seen_urls:
                        continue
                    seen_urls.add(url)
                    all_jobs.append(j)
            else:
                print(f"     ❌ Ничего не найдено для '{term}'")

            # Небольшая уступка UI (не «усыпляем» на минуты)
            yield_briefly(base_ms=120, jitter_ms=80, cancel_check=cancel_check)

        return all_jobs

    
    def normalize_city_name(self, city, country_code):
        """
        Умная нормализация названий городов
        Покрывает ТОП-15 городов по каждой стране + fallback
        """
        if not city or not isinstance(city, str):
            return None
        
        city_clean = city.strip().lower()
        if not city_clean:
            return None
        
        # ТОП популярные города по странам (русский → английский)
        POPULAR_CITIES = {
            'de': {  # Германия
                'берлин': 'Berlin',
                'мюнхен': 'Munich', 
                'гамбург': 'Hamburg',
                'кельн': 'Cologne',
                'франкфурт': 'Frankfurt',
                'дюссельдорф': 'Düsseldorf',
                'дортмунд': 'Dortmund',
                'эссен': 'Essen',
                'лейпциг': 'Leipzig',
                'бремен': 'Bremen',
                'дрезден': 'Dresden',
                'ганновер': 'Hannover',
                'нюрнберг': 'Nuremberg',
                'штутгарт': 'Stuttgart'
            },
            'pl': {  # Польша
                'варшава': 'Warsaw',
                'краков': 'Krakow',
                'гданьск': 'Gdansk',
                'вроцлав': 'Wroclaw',
                'познань': 'Poznan',
                'лодзь': 'Lodz',
                'катовице': 'Katowice',
                'белостоко': 'Bialystok',
                'гдыня': 'Gdynia',
                'ченстохова': 'Czestochowa',
                'радом': 'Radom',
                'сосновец': 'Sosnowiec',
                'торунь': 'Torun'
            },
            'gb': {  # Великобритания
                'лондон': 'London',
                'манчестер': 'Manchester',
                'бирмингем': 'Birmingham',
                'ливерпуль': 'Liverpool',
                'лидс': 'Leeds',
                'шеффилд': 'Sheffield',
                'бристоль': 'Bristol',
                'эдинбург': 'Edinburgh',
                'глазго': 'Glasgow',
                'кардифф': 'Cardiff',
                'белфаст': 'Belfast',
                'ньюкасл': 'Newcastle',
                'ноттингем': 'Nottingham'
            },
            'nl': {  # Нидерланды
                'амстердам': 'Amsterdam',
                'роттердам': 'Rotterdam', 
                'гаага': 'The Hague',
                'утрехт': 'Utrecht',
                'эйндховен': 'Eindhoven',
                'тилбург': 'Tilburg',
                'гронинген': 'Groningen',
                'алмере': 'Almere',
                'бреда': 'Breda',
                'неймеген': 'Nijmegen'
            },
            'fr': {  # Франция
                'париж': 'Paris',
                'марсель': 'Marseille',
                'лион': 'Lyon',
                'тулуза': 'Toulouse',
                'ницца': 'Nice',
                'нант': 'Nantes',
                'монпелье': 'Montpellier',
                'страсбург': 'Strasbourg',
                'бордо': 'Bordeaux',
                'лилль': 'Lille',
                'ренн': 'Rennes',
                'реймс': 'Reims',
                'тур': 'Tours'
            },
            'at': {  # Австрия
                'вена': 'Vienna',
                'грац': 'Graz',
                'линц': 'Linz',
                'зальцбург': 'Salzburg',
                'инсбрук': 'Innsbruck',
                'клагенфурт': 'Klagenfurt'
            },
            'us': {  # США
                'нью-йорк': 'New York',
                'лос-анджелес': 'Los Angeles',
                'чикаго': 'Chicago',
                'хьюстон': 'Houston',
                'финикс': 'Phoenix',
                'филадельфия': 'Philadelphia',
                'сан-антонио': 'San Antonio',
                'сан-диего': 'San Diego',
                'даллас': 'Dallas',
                'сан-хосе': 'San Jose',
                'остин': 'Austin',
                'майами': 'Miami',
                'сиэтл': 'Seattle',
                'бостон': 'Boston'
            },
            'ca': {  # Канада
                'торонто': 'Toronto',
                'монреаль': 'Montreal',
                'ванкувер': 'Vancouver',
                'калгари': 'Calgary',
                'эдмонтон': 'Edmonton',
                'оттава': 'Ottawa',
                'виннипег': 'Winnipeg',
                'квебек': 'Quebec City'
            },
            'au': {  # Австралия
                'сидней': 'Sydney',
                'мельбурн': 'Melbourne',
                'брисбен': 'Brisbane',
                'перт': 'Perth',
                'аделаида': 'Adelaide',
                'канберра': 'Canberra'
            },
            'it': {  # Италия
                'рим': 'Rome',
                'милан': 'Milan',
                'неаполь': 'Naples',
                'турин': 'Turin',
                'палермо': 'Palermo',
                'генуя': 'Genoa',
                'болонья': 'Bologna',
                'флоренция': 'Florence',
                'венеция': 'Venice'
            },
            'es': {  # Испания
                'мадрид': 'Madrid',
                'барселона': 'Barcelona',
                'валенсия': 'Valencia',
                'севилья': 'Seville',
                'сарагоса': 'Zaragoza',
                'малага': 'Malaga',
                'мурсия': 'Murcia',
                'пальма': 'Palma',
                'бильбао': 'Bilbao'
            }
        }
        
        # 1. Проверяем точное совпадение в нашем словаре
        country_cities = POPULAR_CITIES.get(country_code, {})
        if city_clean in country_cities:
            normalized = country_cities[city_clean]
            print(f"🌍 Город нормализован: '{city}' → '{normalized}' для {country_code}")
            return normalized
        
        # 2. Проверяем частичные совпадения (для опечаток)
        for ru_name, en_name in country_cities.items():
            if city_clean in ru_name or ru_name in city_clean:
                print(f"🌍 Город найден частично: '{city}' → '{en_name}' для {country_code}")
                return en_name
        
        # 3. Если уже на английском - возвращаем как есть
        if city.encode('ascii', errors='ignore').decode('ascii') == city:
            print(f"🌍 Город уже на латинице: '{city}' для {country_code}")
            return city
        
        # 4. Fallback - возвращаем оригинал (пусть API попробует)
        print(f"⚠️ Город не найден в словаре: '{city}' для {country_code}, передаем как есть")
        return city
        
    def _search_single_term(
    self,
    keywords: str,
    country: str,
    location: str = '',
    max_results: int = 25,
    filter_term: str = None,
    cancel_check=None
) -> List[JobVacancy]:
        """По одному термину. При 429 — включаем cooldown и роняем RateLimitedError; поддерживаем cancel_check."""
        if cancel_check and cancel_check():
            return []

        # если уже в cooldown — не ходим
        now = time.time()
        if getattr(self, "cooldown_until", 0) > now:
            left = int(self.cooldown_until - now)
            print(f"⛔ Adzuna: cooldown ещё {left}s — пропускаем term.")
            raise RateLimitedError("ADZUNA_COOLDOWN")

        url = f"https://api.adzuna.com/v1/api/jobs/{country}/search/1"
        params = {
            'app_id': self.app_id,
            'app_key': self.app_key,
            'what': keywords,
            'results_per_page': min(max_results, 50),
            'sort_by': 'date'
        }
        if location:
            normalized_location = self.normalize_city_name(location, country)
            params['where'] = normalized_location

        print(f"     🌐 API URL: {url}")
        print(f"     📝 Параметры: what='{keywords}', where='{location}'")

        ok = self.rate_limiter.wait_if_needed(cancel_check=cancel_check)
        if ok is False or (cancel_check and cancel_check()):
            return []

        try:
            response = requests.get(url, params=params, timeout=12)
            self._inc_metric('api_requests', 1)
            print(f"     📡 API ответ: {response.status_code}")

            if response.status_code == 200:
                data = response.json()
                results = data.get('results', [])
                print(f"     📊 Получено от API: {len(results)} вакансий")

                jobs: List[JobVacancy] = []
                for job_data in results:
                    if cancel_check and cancel_check():
                        break
                    job = self._normalize_job_data(job_data, country, filter_term or keywords)
                    if job:
                        jobs.append(job)
                return jobs

            if response.status_code == 429:
                cooldown = int(os.getenv("ADZUNA_COOLDOWN_SEC", "180"))
                self.cooldown_until = time.time() + cooldown
                print(f"⛔ Adzuna: 429 Too Many Requests — включаем cooldown {cooldown}s и переключаемся на другой источник")
                yield_briefly(base_ms=180, jitter_ms=120, cancel_check=cancel_check)
                raise RateLimitedError("ADZUNA_RATE_LIMITED")

            # прочие статусы — без ретраев
            try:
                data = response.json()
            except Exception:
                data = {}
            exc = (data or {}).get("exception", "")
            if exc == "UNSUPPORTED_COUNTRY" or "UNSUPPORTED_COUNTRY" in response.text:
                print(f"⚠️ Страна '{country}' не поддерживается Adzuna API. Пропускаем…")
                return []
            print(f"❌ API вернул {response.status_code}: {response.text[:200]}")
            return []

        except requests.Timeout:
            print("⚠️ Adzuna: таймаут запроса — пропускаем term")
            return []
        except RateLimitedError:
            raise
        except Exception as e:
            print(f"❌ Adzuna: критическая ошибка: {e}")
            return []




    # Остальные методы остаются без изменений...
    def _normalize_job_data(self, raw_job: Dict, country: str, search_term: str) -> Optional[JobVacancy]:
        """Нормализация данных С ПРОВЕРКОЙ РЕЛЕВАНТНОСТИ"""
        try:
            job_id = str(raw_job.get('id', ''))
            title = raw_job.get('title', 'No title')
            
            company_data = raw_job.get('company', {})
            company = company_data.get('display_name', 'No company') if company_data else 'No company'
            
            location_data = raw_job.get('location', {})
            location = location_data.get('display_name', 'No location') if location_data else 'No location'
            
            description = raw_job.get('description', raw_job.get('snippet', 'No description'))
            
            # Проверка релевантности (ваша существующая логика)
            if not self._is_relevant_job(title, description, search_term):
                return None
            
            salary = self._format_salary(raw_job, country)
            apply_url = raw_job.get('redirect_url', '')
            posted_date = raw_job.get('created', 'Unknown date')
            job_type = raw_job.get('contract_type', raw_job.get('contract_time', 'Not specified'))
            
            language_req = self._determine_language_requirement(title, description, search_term)
            refugee_friendly = self._is_refugee_friendly(title, description, search_term)
            
            return JobVacancy(
                id=job_id,
                title=title,
                company=company,
                location=location,
                salary=salary,
                description=description,
                apply_url=apply_url,
                source='adzuna',
                posted_date=posted_date,
                country=self.countries[country]['name'],
                job_type=job_type,
                language_requirement=language_req,
                refugee_friendly=refugee_friendly
            )
            
        except Exception as e:
            return None
    
    def _is_relevant_job(self, job_title: str, job_description: str, search_term: str) -> bool:
        """
        🌍 ПОЛНАЯ МУЛЬТИЯЗЫЧНАЯ ПРОВЕРКА РЕЛЕВАНТНОСТИ v8
        Поддержка 18 стран и 12 языков: EN, DE, FR, ES, IT, NL, PL, CZ, SK, SE, NO, DK
        """
        if search_term == 'search_for_other_jobs':
            return True

        title_lower = job_title.lower()
        description_lower = job_description.lower()
        search_lower = search_term.lower()
        combined_text = f"{title_lower} {description_lower}"

        # ===== 🇺🇦 УКРАИНСКИЕ БЕЖЕНЦЫ (ВСЕ ЯЗЫКИ) =====
        refugee_terms = [
            # Английский
            'ukrain', 'refugee', 'asylum', 'displaced', 'humanitarian',
            # Немецкий  
            'flüchtling', 'ukraine', 'ukrainisch', 'asyl', 'geflüchtet',
            # Французский
            'réfugié', 'ukrainien', 'demandeur asile', 'déplacé',
            # Испанский
            'refugiado', 'ucraniano', 'asilo', 'desplazado',
            # Итальянский
            'profugo', 'rifugiato', 'ucraino', 'richiedente asilo',
            # Нидерландский
            'vluchteling', 'oekraïens', 'asielzoeker',
            # Польский
            'uchodźca', 'ukraiński', 'azylant', 'przesiedlony',
            # Чешский
            'uprchlík', 'ukrajinský', 'azylant', 'přesídlený',
            # Словацкий
            'utečenec', 'ukrajinský', 'azylant',
            # Шведский
            'flykting', 'ukrainsk', 'asylsökande',
            # Норвежский
            'flyktning', 'ukrainsk', 'asylsøker',
            # Датский
            'flygtning', 'ukrainsk', 'asylansøger'
        ]
        if any(term in search_lower for term in refugee_terms):
            if any(term in combined_text for term in refugee_terms):
                return True

        # ===== 🍽️ ОБЩЕПИТ И ТОРГОВЛЯ (18 СТРАН) =====
        food_retail_searches = [
            # Английский (GB, US, CA, AU)
            'waiter', 'waitress', 'server', 'cashier', 'shop assistant', 'sales assistant', 
            'dishwasher', 'cook', 'chef', 'bartender', 'retail',
            # Немецкий (DE, AT, CH)
            'kellner', 'kellnerin', 'bedienung', 'kassierer', 'verkäufer', 'spüler', 
            'koch', 'barkeeper', 'einzelhandel',
            # Французский (FR, BE, CH, CA)
            'serveur', 'serveuse', 'caissier', 'vendeur', 'plongeur', 'cuisinier', 
            'barman', 'commerce',
            # Испанский (ES)
            'camarero', 'camarera', 'cajero', 'vendedor', 'friegaplatos', 'cocinero', 
            'barman', 'comercio',
            # Итальянский (IT)
            'cameriere', 'cameriera', 'cassiere', 'commesso', 'lavapiatti', 'cuoco', 
            'barista', 'commercio',
            # Нидерландский (NL, BE)
            'ober', 'serveerster', 'kassière', 'verkoper', 'afwasser', 'kok', 
            'barkeeper', 'winkel',
            # Польский (PL)
            'kelner', 'kelnerka', 'kasjer', 'sprzedawca', 'zmywacz', 'kucharz', 
            'barman', 'handel',
            # Чешский (CZ)
            'číšník', 'číšnice', 'pokladník', 'prodavač', 'umývač', 'kuchař', 
            'barman', 'obchod',
            # Словацкий (SK)
            'čašník', 'čašníčka', 'pokladník', 'predavač', 'umývač', 'kuchár',
            # Шведский (SE)
            'servitör', 'servitris', 'kassör', 'säljare', 'diskare', 'kock', 'bartender',
            # Норвежский (NO)
            'servitør', 'kasserer', 'selger', 'oppvasker', 'kokk', 'bartender',
            # Датский (DK)
            'tjener', 'kasserer', 'sælger', 'opvasker', 'kok', 'bartender'
        ]
        
        if any(term in search_lower for term in food_retail_searches):
            relevant = [
                # ========== ОФИЦИАНТЫ/СЕРВИС ==========
                # Английский (GB, US, CA, AU)
                'waiter', 'waitress', 'server', 'food service', 'restaurant staff', 
                'hospitality', 'front of house', 'dining', 'service staff', 'table service',
                'host', 'hostess', 'floor staff', 'waiting staff',
                
                # Немецкий (DE, AT, CH)
                'kellner', 'kellnerin', 'bedienung', 'servicekraft', 'servicemitarbeiter', 
                'gastronomie', 'restaurant', 'cafe', 'bistro', 'service', 'bewirtung',
                'gastronomiemitarbeiter', 'restaurantmitarbeiter', 'servierkraft',
                
                # Французский (FR, BE, CH, CA)
                'serveur', 'serveuse', 'garçon', 'service', 'restauration', 'brasserie', 
                'café', 'bistrot', 'personnel salle', 'agent service', 'hôtesse',
                'commis salle', 'aide serveur',
                
                # Испанский (ES)
                'camarero', 'camarera', 'mesero', 'mesera', 'servicio', 'restaurante',
                'hostelería', 'bar', 'cafetería', 'personal sala', 'atención cliente',
                'auxiliar hostelería',
                
                # Итальянский (IT)
                'cameriere', 'cameriera', 'addetto sala', 'servizio', 'ristorazione',
                'ristorante', 'bar', 'caffè', 'personale sala', 'addetto servizio',
                'commesso bar',
                
                # Нидерландский (NL, BE)
                'ober', 'serveerster', 'bediening', 'horeca', 'restaurant', 'café',
                'servicemedewerker', 'gastheer', 'gastvrouw', 'horecamedewerker',
                
                # Польский (PL)
                'kelner', 'kelnerka', 'obsługa', 'serwis', 'restauracja', 'gastronomia',
                'bar', 'kawiarnia', 'pracownik sali', 'obsługa klienta',
                
                # Чешский (CZ)
                'číšník', 'číšnice', 'obsluha', 'servis', 'restaurace', 'gastronomie',
                'bar', 'kavárna', 'obsluha hostů', 'personál',
                
                # Словацкий (SK)
                'čašník', 'čašníčka', 'obsluha', 'servis', 'reštaurácia', 'gastronómia',
                
                # Шведский (SE)
                'servitör', 'servitris', 'serverare', 'restaurang', 'café', 'service',
                'värd', 'värdinna', 'serveringspersonal',
                
                # Норвежский (NO)
                'servitør', 'tjener', 'restaurant', 'kafé', 'service', 'vertskap',
                'serveringspersonale',
                
                # Датский (DK)
                'tjener', 'serveringspersonale', 'restaurant', 'café', 'service',
                'vært', 'værtinde',

                # ========== КАССИРЫ/ПРОДАВЦЫ ==========
                # Английский
                'cashier', 'till operator', 'checkout', 'shop assistant', 'sales assistant',
                'retail assistant', 'store clerk', 'sales associate', 'shop worker',
                'customer service', 'retail', 'supermarket', 'store',
                
                # Немецкий
                'kassierer', 'kassiererin', 'verkäufer', 'verkäuferin', 'einzelhandel',
                'verkaufsmitarbeiter', 'handelsmitarbeiter', 'supermarkt', 'laden',
                'verkaufsaushilfe', 'kassenkraft', 'filialarbeiter',
                
                # Французский
                'caissier', 'caissière', 'vendeur', 'vendeuse', 'commerce', 'magasin',
                'grande distribution', 'supermarché', 'employé libre service',
                'conseiller vente', 'hôtesse caisse',
                
                # Испанский
                'cajero', 'cajera', 'vendedor', 'vendedora', 'dependiente', 'comercio',
                'supermercado', 'tienda', 'auxiliar ventas', 'reponedor',
                
                # Итальянский
                'cassiere', 'cassiera', 'commesso', 'commessa', 'addetto vendite',
                'commercio', 'supermercato', 'negozio', 'addetto cassa',
                
                # Нидерландский
                'kassière', 'kassamedewerker', 'verkoper', 'verkoopster', 'winkelmedewerker',
                'retail', 'supermarkt', 'winkel', 'caissier',
                
                # Польский
                'kasjer', 'kasjerka', 'sprzedawca', 'sprzedawczyni', 'handel',
                'sklep', 'supermarket', 'obsługa kasy', 'pracownik sklepu',
                
                # Чешский
                'pokladník', 'pokladní', 'prodavač', 'prodavačka', 'obchod',
                'supermarket', 'prodejna', 'obsluha pokladny',
                
                # Словацкий
                'pokladník', 'predavač', 'predavačka', 'obchod', 'supermarket',
                
                # Шведский
                'kassör', 'kassörska', 'säljare', 'butik', 'affär', 'ICA', 'Coop',
                'butikspersonal', 'butiksbiträde',
                
                # Норвежский
                'kasserer', 'selger', 'butikk', 'handel', 'Rema', 'KIWI',
                'butikkmedarbeider',
                
                # Датский
                'kasserer', 'sælger', 'butik', 'Netto', 'Bilka', 'butikspersonale',

                # ========== КУХНЯ ==========
                # Английский
                'cook', 'chef', 'kitchen assistant', 'prep cook', 'line cook', 'dishwasher',
                'kitchen porter', 'kitchen staff', 'commis chef', 'sous chef',
                
                # Немецкий
                'koch', 'köchin', 'küchenhilfe', 'küchenhelfer', 'spüler', 'spülkraft',
                'küchenmitarbeiter', 'chefkoch', 'hilfskoch',
                
                # Французский
                'cuisinier', 'cuisinière', 'commis cuisine', 'aide cuisinier', 'plongeur',
                'personnel cuisine', 'chef cuisine', 'second cuisine',
                
                # Испанский
                'cocinero', 'cocinera', 'ayudante cocina', 'friegaplatos', 'personal cocina',
                'pinche cocina', 'jefe cocina',
                
                # Итальянский
                'cuoco', 'cuoca', 'aiuto cuoco', 'lavapiatti', 'addetto cucina',
                'commis', 'chef', 'sous chef',
                
                # Нидерландский
                'kok', 'keukenhulp', 'afwasser', 'keukenmedewerker', 'chef-kok',
                'keukenassistent',
                
                # Польский
                'kucharz', 'kucharka', 'pomoc kuchenna', 'zmywacz', 'pracownik kuchni',
                'pomocnik kucharza', 'szef kuchni',
                
                # Чешский
                'kuchař', 'kuchařka', 'kuchyňský pomocník', 'umývač', 'kuchyně',
                'pomocník kuchaře', 'šéfkuchař',
                
                # Словацкий
                'kuchár', 'kuchárka', 'kuchynský pomocník', 'umývač',
                
                # Скандинавские языки
                'kock', 'kökspersonal', 'diskare', 'köksbistrånd', # Шведский
                'kokk', 'kjøkkenpersonell', 'oppvasker', # Норвежский  
                'kok', 'køkkenpersonale', 'opvasker', # Датский

                # ========== БАРМЕНЫ ==========
                # Английский
                'bartender', 'barman', 'barmaid', 'mixologist', 'bar staff',
                # Немецкий
                'barkeeper', 'barmann', 'barmixer', 'barkraft',
                # Французский
                'barman', 'barmaid', 'mixologue', 'serveur bar',
                # Испанский
                'barman', 'cantinero', 'coctelero', 'camarero bar',
                # Итальянский
                'barista', 'barman', 'addetto bar', 'bartender',
                # Нидерландский
                'barkeeper', 'barman', 'bartender', 'barmedewerker',
                # Польский
                'barman', 'barista', 'obsługa baru', 'bartender',
                # Чешский
                'barman', 'barmanka', 'obsluha baru', 'bartender',
                # Остальные языки
                'bartender', 'barman', 'barmanka', # Универсальные

                # ========== ОБЩИЕ ТЕРМИНЫ ==========
                # Английский
                'part time', 'full time', 'student job', 'temporary', 'seasonal',
                'entry level', 'no experience', 'trainee',
                # Немецкий
                'aushilfe', 'teilzeit', 'vollzeit', 'nebenjob', 'minijob', 'student',
                'ungelernt', 'ohne erfahrung', 'praktikant',
                # Французский
                'temps partiel', 'temps plein', 'saisonnier', 'étudiant', 'débutant',
                'sans expérience', 'stagiaire',
                # Испанский
                'tiempo parcial', 'jornada completa', 'estudiante', 'temporal',
                'sin experiencia', 'principiante', 'becario',
                # Итальянский
                'part-time', 'tempo pieno', 'studente', 'stagionale', 'senza esperienza',
                'principiante', 'stagista',
                # Нидерландский
                'parttime', 'fulltime', 'student', 'tijdelijk', 'zonder ervaring',
                'starter', 'stagiair',
                # Польский
                'praca tymczasowa', 'etat', 'student', 'sezonowa', 'bez doświadczenia',
                'początkujący', 'praktykant',
                # Чешский
                'částečný úvazek', 'plný úvazek', 'student', 'sezónní',
                'bez zkušeností', 'začátečník', 'praktikant',
                # Скандинавские
                'deltid', 'heltid', 'student', 'tillfällig', 'utan erfarenhet', # Шведский
                'deltid', 'heltid', 'student', 'midlertidig', 'uten erfaring', # Норвежский
                'deltid', 'fuldtid', 'studerende', 'midlertidig', 'uden erfaring' # Датский
            ]
            
            # ========== УНИВЕРСАЛЬНЫЙ BLACKLIST ==========
            irrelevant = [
                # === УПРАВЛЕНЧЕСКИЕ ДОЛЖНОСТИ ===
                # Английский
                'manager', 'director', 'head of', 'chief', 'supervisor', 'coordinator',
                'team leader', 'team lead', 'senior manager', 'general manager',
                'assistant manager', 'deputy manager', 'area manager', 'regional manager',
                
                # Немецкий
                'manager', 'leiter', 'führung', 'teamleiter', 'abteilungsleiter',
                'geschäftsführer', 'bereichsleiter', 'stellvertretender leiter',
                'regionalleiter', 'filialleiter', 'verkaufsleiter',
                
                # Французский
                'directeur', 'responsable', 'chef équipe', 'coordinateur', 'superviseur',
                'directeur adjoint', 'chef service', 'responsable secteur',
                
                # Испанский
                'director', 'jefe', 'gerente', 'coordinador', 'supervisor',
                'responsable', 'encargado', 'jefe equipo', 'jefe ventas',
                
                # Итальянский
                'direttore', 'responsabile', 'capo', 'coordinatore', 'supervisore',
                'capo reparto', 'capo squadra', 'responsabile vendite',
                
                # Нидерландский
                'manager', 'leidinggevende', 'teamleider', 'afdelingshoofd',
                'regiomanager', 'filiaalmanager', 'verkoopleider',
                
                # Польский
                'kierownik', 'dyrektor', 'szef', 'koordynator', 'manager',
                'kierownik zespołu', 'kierownik sprzedaży', 'lider',
                
                # Чешский
                'vedoucí', 'ředitel', 'manažer', 'koordinátor', 'supervizor',
                'vedoucí týmu', 'vedoucí prodeje',
                
                # Словацкий
                'vedúci', 'riaditeľ', 'manažér', 'koordinátor',
                
                # Скандинавские
                'chef', 'ledare', 'ansvarig', 'föreståndare', # Шведский
                'leder', 'sjef', 'ansvarlig', # Норвежский
                'leder', 'chef', 'ansvarlig', # Датский

                # === IT И ТЕХНИЧЕСКИЕ ===
                # Английский
                'software', 'developer', 'programmer', 'engineer', 'technical', 'it ',
                'system', 'network', 'database', 'web developer', 'software engineer',
                
                # Немецкий
                'software', 'entwickler', 'programmierer', 'ingenieur', 'technisch',
                'system', 'netzwerk', 'datenbank', 'it-', 'informatik',
                
                # Французский
                'logiciel', 'développeur', 'programmeur', 'ingénieur', 'technique',
                'système', 'réseau', 'informatique',
                
                # Испанский
                'software', 'desarrollador', 'programador', 'ingeniero', 'técnico',
                'sistema', 'informático',
                
                # Итальянский
                'software', 'sviluppatore', 'programmatore', 'ingegnere', 'tecnico',
                'sistema', 'informatico',
                
                # Нидерландский
                'software', 'ontwikkelaar', 'programmeur', 'ingenieur', 'technisch',
                'systeem', 'netwerk',
                
                # Польский
                'software', 'programista', 'developer', 'inżynier', 'techniczny',
                'system', 'informatyk',
                
                # Чешский
                'software', 'vývojář', 'programátor', 'inženýr', 'technický',
                'systém', 'informatik',

                # === ПРОДАЖИ B2B И ВЫСОКИЙ УРОВЕНЬ ===
                # Английский
                'account manager', 'sales manager', 'business development', 'key account',
                'sales representative', 'account executive', 'commercial',
                
                # Немецкий
                'account manager', 'vertriebsleiter', 'verkaufsleiter', 'key account',
                'außendienst', 'vertriebsmitarbeiter', 'business development',
                
                # Французский
                'account manager', 'commercial', 'business development', 'grands comptes',
                'responsable commercial', 'chargé affaires',
                
                # Испанский
                'account manager', 'comercial', 'desarrollo negocio', 'cuentas clave',
                'representante ventas', 'ejecutivo cuentas',
                
                # Итальянский
                'account manager', 'commerciale', 'sviluppo business', 'account',
                'responsabile vendite', 'agente commerciale',
                
                # Польский
                'account manager', 'handlowiec', 'przedstawiciel', 'sprzedaż zewnętrzna',
                'key account', 'business development',
                
                # Чешский
                'account manager', 'obchodník', 'obchodní zástupce', 'key account',

                # === СПЕЦИАЛИЗИРОВАННЫЕ/ПРОФЕССИОНАЛЬНЫЕ ===
                'consultant', 'specialist', 'expert', 'professional', 'senior',
                'konsultant', 'spezialist', 'experte', 'fachkraft', 'senior',
                'consultant', 'spécialiste', 'expert', 'professionnel',
                'consultor', 'especialista', 'experto', 'profesional',
                'consulente', 'specialista', 'esperto', 'professionista',
                'consultant', 'specialist', 'expert', 'professional',
                'konsultant', 'specjalista', 'ekspert', 'profesjonalista',
                'konzultant', 'specialista', 'expert', 'profesionál'
            ]
            
            has_relevant = any(term in title_lower for term in relevant)
            has_irrelevant = any(term in title_lower for term in irrelevant)
            
            if has_relevant and not has_irrelevant:
                return True

        # ===== 🚗 ТРАНСПОРТ И ДОСТАВКА (18 СТРАН) =====
        transport_searches = [
            # Английский
            'driver', 'taxi driver', 'delivery driver', 'courier', 'truck driver', 'bus driver',
            # Немецкий
            'fahrer', 'taxifahrer', 'lieferfahrer', 'kurier', 'lkw fahrer', 'busfahrer',
            # Французский
            'chauffeur', 'conducteur', 'livreur', 'coursier', 'routier', 'chauffeur bus',
            # Испанский
            'conductor', 'taxista', 'repartidor', 'mensajero', 'camionero', 'conductor autobús',
            # Итальянский
            'autista', 'tassista', 'corriere', 'fattorino', 'camionista', 'autista autobus',
            # Нидерландский
            'chauffeur', 'taxichauffeur', 'bezorger', 'koerier', 'vrachtwagenchauffeur', 'buschauffeur',
            # Польский
            'kierowca', 'taksówkarz', 'kurier', 'dostawca', 'kierowca ciężarówki', 'kierowca autobusu',
            # Чешский
            'řidič', 'taxikář', 'kurýr', 'rozvozce', 'řidič nákladního', 'řidič autobusu',
            # Словацкий
            'vodič', 'taxikár', 'kuriér', 'rozvozca', 'vodič nákladného',
            # Шведский
            'förare', 'taxiförare', 'budförare', 'kurír', 'lastbilsförare', 'bussförare',
            # Норвежский
            'sjåfør', 'taxisjåfør', 'budsjåfør', 'kurér', 'lastebilsjåfør', 'bussjåfør',
            # Датский
            'chauffør', 'taxichauffør', 'budchauffør', 'kurér', 'lastbilchauffør', 'buschauffør'
        ]
        
        if any(term in search_lower for term in transport_searches):
            relevant = [
                # ========== ВОДИТЕЛИ ==========
                # Английский
                'driver', 'chauffeur', 'operator', 'delivery', 'transport', 'logistics',
                'taxi', 'uber', 'lyft', 'van', 'truck', 'lorry', 'hgv', 'bus', 'coach',
                'driving', 'courier', 'freight', 'haulage',
                
                # Немецкий
                'fahrer', 'kraftfahrer', 'berufskraftfahrer', 'fahrzeugführer',
                'taxifahrer', 'busfahrer', 'lkwfahrer', 'lieferfahrer', 'kurier',
                'speditionsfahrer', 'transportfahrer', 'auslieferungsfahrer',
                'spedition', 'logistik', 'transport', 'fahrdienst', 'mobilität',
                
                # Французский
                'chauffeur', 'conducteur', 'livreur', 'coursier', 'transporteur',
                'taxi', 'camion', 'poids lourd', 'livraison', 'logistique',
                'transport', 'distribution', 'véhicule', 'conduite',
                
                # Испанский
                'conductor', 'chofer', 'taxista', 'repartidor', 'mensajero',
                'camionero', 'transportista', 'logística', 'reparto', 'distribución',
                'vehículo', 'conducción', 'entrega',
                
                # Итальянский
                'autista', 'conducente', 'tassista', 'corriere', 'fattorino',
                'camionista', 'autotrasportatore', 'trasporto', 'logistica', 'consegne',
                'distribuzione', 'veicolo', 'guida',
                
                # Нидерландский
                'chauffeur', 'bestuurder', 'taxichauffeur', 'bezorger', 'koerier',
                'vrachtwagenchauffeur', 'buschauffeur', 'logistiek', 'transport',
                'bezorging', 'distributie', 'voertuig', 'rijden',
                
                # Польский
                'kierowca', 'szofer', 'taksówkarz', 'kurier', 'dostawca',
                'przewoźnik', 'spedytor', 'transport', 'logistyka', 'spedycja',
                'dostawa', 'dystrybucja', 'pojazd', 'jazda',
                
                # Чешский
                'řidič', 'šofér', 'taxikář', 'kurýr', 'rozvozce',
                'dopravce', 'spedice', 'logistik', 'přeprava', 'doprava',
                'distribuce', 'vozidlo', 'řízení',
                
                # Словацкий
                'vodič', 'šofér', 'taxikár', 'kuriér', 'rozvozca',
                'dopravca', 'logistika', 'preprava', 'distribúcia',
                
                # Шведский
                'förare', 'chaufför', 'taxiförare', 'budförare', 'kurír',
                'lastbilsförare', 'bussförare', 'transport', 'logistik',
                'leverans', 'distribution', 'fordon', 'körning',
                
                # Норвежский
                'sjåfør', 'taxisjåfør', 'budsjåfør', 'kurér', 'lastebilsjåfør',
                'bussjåfør', 'transport', 'logistikk', 'levering', 'distribusjon',
                
                # Датский
                'chauffør', 'taxichauffør', 'budchauffør', 'kurér', 'lastbilchauffør',
                'buschauffør', 'transport', 'logistik', 'levering', 'distribution',

                # ========== ДОСТАВКА И КУРЬЕРЫ ==========
                # Глобальные бренды
                'uber', 'bolt', 'glovo', 'deliveroo', 'foodora', 'wolt', 'just eat',
                'dhl', 'ups', 'fedex', 'dpd', 'gls', 'hermes', 'amazon',
                
                # Доставка еды
                'food delivery', 'meal delivery', 'restaurant delivery',
                'essenslieferung', 'pizza lieferung', 'essen fahren',
                'livraison repas', 'livraison restauration', 'livraison pizza',
                'entrega comida', 'reparto comida', 'entrega pizza',
                'consegna cibo', 'consegna pizza', 'delivery food',
                'bezorging eten', 'maaltijdbezorging', 'pizza bezorging',
                'dostawa jedzenia', 'dostawa pizzy', 'rozwożenie jedzenia',
                'rozvoz jídla', 'rozvoz pizzy', 'donáška jedla',
                'matleverans', 'pizzaleverans', 'mat levering', 'pizza levering',
                'madlevering', 'pizza levering',

                # ========== СПЕЦИАЛЬНЫЕ КАТЕГОРИИ ==========
                # Велокурьеры
                'bicycle', 'bike', 'cyclist', 'rider', 'fahrrad', 'rad', 'vélo',
                'bicicleta', 'bici', 'fiets', 'rower', 'kolo', 'cykel', 'sykkel',
                
                # Мотокурьеры
                'motorcycle', 'motorbike', 'scooter', 'motorrad', 'roller',
                'moto', 'scooter', 'moto', 'motor', 'motocykl', 'motocykl',
                'motorcykel', 'motorsykkel', 'motorcykel'
            ]
            
            irrelevant = [
                # Управление и офис
                'dispatcher', 'coordinator', 'manager', 'office', 'planning', 'admin',
                'disponent', 'koordinator', 'büro', 'verwaltung', 'planung',
                'répartiteur', 'coordinateur', 'bureau', 'planning', 'administration',
                'coordinador', 'oficina', 'planificación', 'administración',
                'coordinatore', 'ufficio', 'pianificazione', 'amministrazione',
                'coördinator', 'kantoor', 'planning', 'administratie',
                'dyspozytor', 'koordynator', 'biuro', 'planowanie', 'administracja',
                'dispečer', 'koordinátor', 'kancelář', 'plánování', 'správa',
                
                # Техническое обслуживание
                'mechanic', 'maintenance', 'repair', 'technician',
                'mechaniker', 'wartung', 'reparatur', 'techniker',
                'mécanicien', 'entretien', 'réparation', 'technicien',
                'mecánico', 'mantenimiento', 'reparación', 'técnico',
                'meccanico', 'manutenzione', 'riparazione', 'tecnico',
                'monteur', 'onderhoud', 'reparatie', 'technicus',
                'mechanik', 'konserwacja', 'naprawa', 'technik',
                'mechanik', 'údržba', 'oprava', 'technik'
            ]
            
            has_relevant = any(term in title_lower for term in relevant)
            has_irrelevant = any(term in title_lower for term in irrelevant)
            
            if has_relevant and not has_irrelevant:
                return True

        # ===== 🏗️ СТРОИТЕЛЬСТВО И СКЛАД (18 СТРАН) =====
        construction_searches = [
            # Английский
            'construction worker', 'builder', 'warehouse worker', 'packer', 'loader',
            'factory worker', 'production worker', 'labourer', 'helper',
            # Немецкий
            'bauarbeiter', 'handwerker', 'lagerarbeiter', 'kommissionierer', 'packer',
            'produktionsarbeiter', 'fabrikarbeiter', 'hilfsarbeiter', 'helfer',
            # Французский
            'ouvrier', 'manutentionnaire', 'préparateur', 'magasinier', 'manoeuvre',
            'ouvrier production', 'employé entrepôt',
            # Испанский
            'obrero', 'operario', 'mozo', 'preparador', 'operario almacén',
            'trabajador construcción', 'peón',
            # Итальянский
            'operaio', 'magazziniere', 'addetto', 'manovale', 'operaio edile',
            'addetto produzione',
            # Нидерландский
            'bouwvakker', 'magazijnmedewerker', 'orderpicker', 'productiemedewerker',
            'lader', 'helper',
            # Польский
            'robotnik', 'pracownik', 'magazynier', 'pakowacz', 'operator',
            'robotnik budowlany', 'pracownik produkcji',
            # Чешский
            'dělník', 'pracovník', 'skladník', 'balič', 'operátor',
            'stavební dělník', 'výrobní dělník',
            # Остальные языки аналогично...
        ]
        
        if any(term in search_lower for term in construction_searches):
            relevant = [
                # ========== СТРОИТЕЛЬСТВО ==========
                # Английский
                'construction', 'builder', 'building', 'site', 'trades', 'labourer',
                'groundworker', 'general operative', 'site operative', 'handyman',
                
                # Немецкий
                'bau', 'bauarbeiter', 'bauhilfsarbeiter', 'bauhelfer', 'handwerker',
                'baugewerbe', 'baubranche', 'baustelle', 'monteur', 'baustellenhelfer',
                
                # Французский
                'bâtiment', 'construction', 'ouvrier bâtiment', 'manoeuvre', 'chantier',
                'travaux', 'maçon', 'aide maçon', 'ouvrier polyvalent',
                
                # Испанский
                'construcción', 'obrero construcción', 'peón', 'albañil', 'oficial',
                'ayudante', 'obra', 'edificación',
                
                # Итальянский
                'edile', 'costruzioni', 'operaio edile', 'manovale', 'muratore',
                'cantiere', 'addetto cantiere', 'operaio generico',
                
                # Нидерландский
                'bouw', 'bouwvakker', 'bouwplaats', 'grondwerker', 'hulpkracht',
                'bouwmedewerker', 'allround medewerker',
                
                # Польский
                'budowa', 'robotnik budowlany', 'pracownik budowy', 'pomocnik',
                'budowlaniec', 'robotnik', 'pracownik fizyczny',
                
                # Чешский
                'stavba', 'stavební dělník', 'pracovník stavby', 'pomocník',
                'stavebnictví', 'dělník', 'pomocný pracovník',

                # ========== СКЛАД И ЛОГИСТИКА ==========
                # Английский
                'warehouse', 'picker', 'packer', 'loader', 'operative', 'handler',
                'order picker', 'stock', 'dispatch', 'goods in', 'fulfillment',
                'logistics', 'distribution', 'freight',
                
                # Немецкий
                'lager', 'lagerarbeiter', 'lagermitarbeiter', 'lagerhelfer',
                'kommissionierer', 'kommissionierung', 'picker', 'packer',
                'versand', 'wareneingang', 'logistik', 'distribution',
                
                # Французский
                'entrepôt', 'magasinier', 'préparateur commandes', 'manutentionnaire',
                'agent logistique', 'employé entrepôt', 'cariste', 'conditionnement',
                'expédition', 'réception',
                
                # Испанский
                'almacén', 'operario almacén', 'mozo', 'preparador pedidos',
                'operador logística', 'reponedor', 'expedición', 'recepción',
                
                # Итальянский
                'magazzino', 'magazziniere', 'addetto picking', 'operatore',
                'addetto logistica', 'preparazione ordini', 'spedizioni',
                
                # Нидерландский
                'magazijn', 'magazijnmedewerker', 'orderpicker', 'picker',
                'logistiek medewerker', 'inpakker', 'expeditie', 'ontvangst',
                
                # Польский
                'magazyn', 'magazynier', 'pracownik magazynu', 'pakowacz',
                'operator magazynu', 'kompletacja', 'logistyk', 'ekspedycja',
                
                # Чешский
                'sklad', 'skladník', 'skladový pracovník', 'balič',
                'operátor skladu', 'kompletace', 'expedice', 'příjem',

                # ========== ПРОИЗВОДСТВО ==========
                # Английский
                'production', 'factory', 'manufacturing', 'assembly', 'operator',
                'machine operator', 'line worker', 'process worker',
                
                # Немецкий
                'produktion', 'produktionsmitarbeiter', 'fabrik', 'fabrikarbeiter',
                'fertigung', 'fertigungsmitarbeiter', 'montage', 'maschinenarbeiter',
                'fließband', 'industriearbeiter',
                
                # Французский
                'production', 'ouvrier production', 'usine', 'fabrication',
                'opérateur machine', 'agent production', 'chaîne production',
                
                # Испанский
                'producción', 'operario producción', 'fábrica', 'fabricación',
                'operador máquina', 'cadena montaje', 'industrial',
                
                # Итальянский
                'produzione', 'operaio produzione', 'fabbrica', 'manifattura',
                'operatore macchine', 'catena montaggio', 'industriale',
                
                # Нидерландский
                'productie', 'productiemedewerker', 'fabriek', 'fabricage',
                'machine operator', 'assemblage', 'industrie',
                
                # Польский
                'produkcja', 'robotnik produkcyjny', 'fabryka', 'wytwarzanie',
                'operator maszyn', 'montaż', 'przemysł',
                
                # Чешский
                'výroba', 'výrobní dělník', 'továrna', 'výrobní',
                'operátor strojů', 'montáž', 'průmysl',

                # ========== ОБЩИЕ ТЕРМИНЫ ==========
                # Английский
                'entry level', 'no experience', 'unskilled', 'manual', 'physical',
                'general worker', 'temp worker', 'casual', 'seasonal',
                
                # Немецкий
                'ungelernt', 'ohne erfahrung', 'hilfsarbeiter', 'körperlich',
                'zeitarbeit', 'leiharbeit', 'aushilfe', 'saisonarbeit',
                
                # Французский
                'non qualifié', 'sans expérience', 'travail physique', 'manuel',
                'intérim', 'temporaire', 'saisonnier',
                
                # Испанский
                'sin experiencia', 'trabajo físico', 'manual', 'temporal',
                'operario', 'peón', 'eventual',
                
                # Итальянский
                'senza esperienza', 'lavoro fisico', 'manuale', 'temporaneo',
                'operaio generico', 'stagionale',
                
                # Нидерландский
                'zonder ervaring', 'fysiek werk', 'handmatig', 'tijdelijk',
                'uitzendkracht', 'seizoenswerk',
                
                # Польский
                'bez doświadczenia', 'praca fizyczna', 'fizyczny', 'tymczasowy',
                'robotnik', 'sezonowy',
                
                # Чешский
                'bez zkušeností', 'fyzická práce', 'manuální', 'dočasný',
                'sezónní', 'brigádník'
            ]
            
            irrelevant = [
                # Управление
                'manager', 'supervisor', 'coordinator', 'engineer', 'technician',
                'team leader', 'foreman', 'shift leader',
                'leiter', 'meister', 'vorarbeiter', 'techniker', 'ingenieur',
                'responsable', 'chef équipe', 'contremaître', 'technicien',
                'supervisor', 'capataz', 'jefe equipo', 'técnico', 'ingeniero',
                'responsabile', 'capo squadra', 'tecnico', 'ingegnere',
                'ploegbaas', 'voorman', 'technicus', 'ingenieur',
                'kierownik', 'brygadzista', 'technik', 'inżynier',
                'vedoucí', 'mistr', 'technik', 'inženýr',
                
                # Специалисты
                'specialist', 'expert', 'skilled', 'qualified', 'professional',
                'fachkraft', 'spezialist', 'qualifiziert', 'erfahren',
                'spécialiste', 'qualifié', 'expérimenté',
                'especialista', 'cualificado', 'experimentado',
                'specialista', 'qualificato', 'esperto',
                'specialist', 'gekwalificeerd', 'ervaren',
                'specjalista', 'wykwalifikowany', 'doświadczony',
                'specialista', 'kvalifikovaný', 'zkušený'
            ]
            
            has_relevant = any(term in title_lower for term in relevant)
            has_irrelevant = any(term in title_lower for term in irrelevant)
            
            if has_relevant and not has_irrelevant:
                return True

        # ===== 🏥 УХОД И СЕРВИС (18 СТРАН) =====
        care_searches = [
            # Английский
            'nurse', 'caregiver', 'care worker', 'cleaner', 'housekeeper', 'nanny',
            'babysitter', 'elderly care', 'massage', 'gardener',
            # Немецкий
            'pflege', 'krankenschwester', 'betreuer', 'reinigung', 'haushalt',
            'babysitter', 'altenpflege', 'massage', 'gärtner',
            # Французский
            'infirmier', 'aide', 'soignant', 'ménage', 'nounou', 'garde',
            'nettoyage', 'massage', 'jardinier',
            # Остальные языки...
        ]
        
        if any(term in search_lower for term in care_searches):
            relevant = [
                # ========== МЕДИЦИНА И УХОД ==========
                # Английский
                'nurse', 'nursing', 'healthcare', 'caregiver', 'care worker',
                'support worker', 'healthcare assistant', 'nursing assistant',
                'elderly care', 'senior care', 'home care', 'personal care',
                
                # Немецкий
                'pflege', 'pflegekraft', 'pflegehelfer', 'krankenpflege', 'altenpflege',
                'krankenschwester', 'gesundheitspflege', 'betreuung', 'betreuer',
                'seniorenbetreuung', 'häusliche pflege', 'pflegeassistent',
                
                # Французский
                'infirmier', 'infirmière', 'aide soignant', 'soins', 'assistance',
                'aide à domicile', 'auxiliaire vie', 'accompagnant', 'gériatrie',
                'personnes âgées', 'aide familiale',
                
                # Испанский
                'enfermero', 'enfermera', 'cuidador', 'asistencia', 'cuidados',
                'auxiliar enfermería', 'ayuda domicilio', 'geriátrico', 'ancianos',
                
                # Итальянский
                'infermiere', 'infermiera', 'badante', 'assistenza', 'cura',
                'operatore sanitario', 'assistente domiciliare', 'anziani',
                
                # Нидерландский
                'verpleegkundige', 'verzorgende', 'zorgverlener', 'thuiszorg',
                'ouderenzorg', 'zorgassistent', 'persoonlijke verzorging',
                
                # Польский
                'pielęgniarka', 'opiekun', 'opiekunka', 'opieka', 'asystent',
                'opieka domowa', 'opieka nad seniorami', 'pielęgnacja',
                
                # Чешский
                'zdravotní sestra', 'ošetřovatel', 'pečovatel', 'péče',
                'domácí péče', 'péče o seniory', 'asistent',

                # ========== УБОРКА И ДОМАШНИЙ СЕРВИС ==========
                # Английский
                'cleaner', 'cleaning', 'janitor', 'housekeeper', 'housekeeping',
                'domestic', 'facility management', 'maintenance', 'office cleaning',
                'commercial cleaning', 'cleaning operative',
                
                # Немецкий
                'reinigung', 'reinigungskraft', 'putzkraft', 'hausmeister',
                'gebäudereinigung', 'objektreinigung', 'facility management',
                'haushälterin', 'haushaltshilfe', 'putzfrau',
                
                # Французский
                'nettoyage', 'agent entretien', 'femme ménage', 'employé ménage',
                'aide ménagère', 'entretien', 'facility management',
                'nettoyeur', 'technicien surface',
                
                # Испанский
                'limpieza', 'limpiador', 'conserje', 'empleada limpieza',
                'empleada hogar', 'mantenimiento', 'servicios generales',
                
                # Итальянский
                'pulizie', 'addetto pulizie', 'operatore ecologico', 'domestica',
                'colf', 'addetta domestica', 'facility management',
                
                # Нидерландский
                'schoonmaak', 'schoonmaker', 'huishoudster', 'facility',
                'schoonmaakmedewerker', 'huishoudelijke hulp',
                
                # Польский
                'sprzątanie', 'sprzątacz', 'sprzątaczka', 'konserwator',
                'pracownik sprzątający', 'pomoc domowa', 'gospodyni',
                
                # Чешский
                'úklid', 'uklízečka', 'údržbář', 'facility', 'úklidová služba',
                'domácí pomocnice', 'hospodyně',

                # ========== ДЕТИ И СЕМЬЯ ==========
                # Английский
                'nanny', 'babysitter', 'childcare', 'childminder', 'au pair',
                'nursery', 'kindergarten', 'daycare', 'family support',
                
                # Немецкий
                'kindermädchen', 'babysitter', 'kinderbetreuung', 'au pair',
                'kindergarten', 'kita', 'tagesmutter', 'familienhelfer',
                
                # Французский
                'nounou', 'garde enfants', 'assistante maternelle', 'au pair',
                'crèche', 'garderie', 'aide familiale', 'puéricultrice',
                
                # Испанский
                'niñera', 'cuidadora niños', 'au pair', 'guardería',
                'educadora infantil', 'canguro',
                
                # Итальянский
                'babysitter', 'tata', 'educatrice', 'au pair', 'asilo',
                'assistente infanzia',
                
                # Нидерландский
                'kinderopvang', 'oppas', 'au pair', 'crèche', 'kinderdagverblijf',
                'pedagogisch medewerker',
                
                # Польский
                'opiekunka dzieci', 'niania', 'au pair', 'żłobek', 'przedszkole',
                'wychowawca',
                
                # Чешский
                'chůva', 'babysitter', 'au pair', 'jesle', 'školka',
                'vychovatelka',

                # ========== САД И ЛАНДШАФТ ==========
                # Английский
                'gardener', 'landscaper', 'groundskeeper', 'horticulture',
                'garden maintenance', 'lawn care', 'tree surgery',
                
                # Немецкий
                'gärtner', 'landschaftsgärtner', 'gartenpflege', 'gartenbau',
                'grünpflege', 'landschaftspflege', 'baumpflege',
                
                # Французский
                'jardinier', 'paysagiste', 'espaces verts', 'horticulture',
                'entretien jardins', 'élagage',
                
                # Испанский
                'jardinero', 'paisajista', 'jardinería', 'mantenimiento jardines',
                'espacios verdes',
                
                # Итальянский
                'giardiniere', 'paesaggista', 'giardinaggio', 'manutenzione verde',
                'cura giardini',
                
                # Нидерландский
                'tuinman', 'hovenier', 'groenvoorziening', 'tuinonderhoud',
                'landschapsarchitect',
                
                # Польский
                'ogrodnik', 'architekt krajobrazu', 'zieleń', 'pielęgnacja ogrodów',
                
                # Чешский
                'zahradník', 'krajinář', 'údržba zeleně', 'zahradnictví',

                # ========== МАССАЖ И ВЕЛНЕС ==========
                # Английский
                'massage', 'masseur', 'masseuse', 'therapist', 'spa', 'wellness',
                'beauty', 'physiotherapy', 'relaxation',
                
                # Немецкий
                'massage', 'masseur', 'physiotherapie', 'wellness', 'spa',
                'entspannung', 'beauty', 'kosmetik',
                
                # Французский
                'massage', 'masseur', 'kinésithérapie', 'spa', 'bien-être',
                'détente', 'beauté', 'esthétique',
                
                # Остальные языки аналогично...
            ]
            
            irrelevant = [
                'manager', 'director', 'coordinator', 'supervisor', 'head',
                'chief nurse', 'senior nurse', 'nurse manager',
                'facility manager', 'cleaning supervisor',
                'head gardener', 'landscape architect'
            ]
            
            has_relevant = any(term in title_lower for term in relevant)
            has_irrelevant = any(term in title_lower for term in irrelevant)
            
            if has_relevant and not has_irrelevant:
                return True

        # ===== 💻 IT И ТЕХНОЛОГИИ (18 СТРАН) =====
        it_searches = [
            'python', 'developer', 'programmer', 'software', 'web', 'frontend',
            'backend', 'fullstack', 'qa', 'tester', 'analyst', 'admin',
            'entwickler', 'programmierer', 'développeur', 'desarrollador',
            'sviluppatore', 'ontwikkelaar', 'programista', 'vývojář'
        ]
        
        if any(term in search_lower for term in it_searches):
            relevant = [
                # Английский
                'developer', 'programmer', 'engineer', 'software', 'web', 'mobile',
                'python', 'java', 'javascript', 'react', 'node', 'angular',
                'frontend', 'backend', 'fullstack', 'qa', 'tester', 'devops',
                'analyst', 'data', 'admin', 'administrator', 'sysadmin',
                
                # Немецкий
                'entwickler', 'programmierer', 'software', 'web', 'it',
                'informatik', 'system', 'daten', 'qualitätssicherung',
                
                # Французский
                'développeur', 'programmeur', 'informatique', 'logiciel',
                'système', 'données', 'qualité',
                
                # Остальные языки...
            ]
            
            irrelevant = [
                'sales', 'marketing', 'recruiter', 'hr', 'business development',
                'account manager', 'consultant', 'trainer'
            ]
            
            has_relevant = any(term in title_lower for term in relevant)
            has_irrelevant = any(term in title_lower for term in irrelevant)
            
            if has_relevant and not has_irrelevant:
                return True

        # ===== 👔 ОФИС И УПРАВЛЕНИЕ (18 СТРАН) =====
        office_searches = [
            'manager', 'administrator', 'coordinator', 'analyst', 'assistant',
            'leiter', 'verwaltung', 'koordinator', 'responsable', 'administrateur',
            'gerente', 'administrador', 'responsabile', 'manager', 'kierownik',
            'vedoucí', 'administrátor'
        ]
        
        if any(term in search_lower for term in office_searches):
            relevant = [
                # Английский
                'manager', 'administrator', 'coordinator', 'analyst', 'assistant',
                'office', 'administration', 'management', 'business', 'operations',
                
                # Немецкий
                'manager', 'leiter', 'administrator', 'koordinator', 'sachbearbeiter',
                'verwaltung', 'büro', 'geschäftsführung', 'assistenz',
                
                # Остальные языки...
            ]
            
            irrelevant = [
                'software engineer', 'technical manager', 'it administrator',
                'sales manager', 'account manager'
            ]
            
            has_relevant = any(term in title_lower for term in relevant)
            has_irrelevant = any(term in title_lower for term in irrelevant)
            
            if has_relevant and not has_irrelevant:
                return True

        # ===== FALLBACK: МЯГКАЯ ПРОВЕРКА =====
        # Если ничего не подошло, делаем последнюю попытку с более мягкими критериями
        if len(search_term) > 4:  # Избегаем слишком коротких терминов
            core_terms = search_term.lower().split()[:2]  # Берем первые 2 слова
            
            # Проверяем, есть ли хотя бы одно из ключевых слов в заголовке
            if any(term in title_lower and len(term) > 3 for term in core_terms):
                # Строгий blacklist для исключения явно неподходящих
                strict_blacklist = [
                    'senior manager', 'director', 'head of', 'chief executive',
                    'principal engineer', 'lead architect', 'vice president',
                    'geschäftsführer', 'vorstandsvorsitzender', 'hauptgeschäftsführer',
                    'directeur général', 'président directeur', 'directeur exécutif',
                    'director general', 'director ejecutivo', 'consejero delegado',
                    'amministratore delegato', 'direttore generale',
                    'algemeen directeur', 'uitvoerend directeur',
                    'dyrektor generalny', 'prezes zarządu',
                    'generální ředitel', 'výkonný ředitel'
                ]
                
                if not any(bad in title_lower for bad in strict_blacklist):
                    return True

        # По умолчанию отклоняем
        return False
    
    def _determine_language_requirement(self, title: str, description: str, search_term: str) -> str:
        """Определение языковых требований"""
        text = f"{title} {description}".lower()
        
        no_language = ['no language', 'без языка', 'driver', 'delivery', 'warehouse', 'physical']
        if any(indicator in text for indicator in no_language):
            return "no_language_required"
        
        return "unknown"
    
    def _is_refugee_friendly(self, title: str, description: str, search_term: str) -> bool:
        """Определение дружелюбности к беженцам"""
        text = f"{title} {description} {search_term}".lower()
        
        refugee_indicators = [
            # Английский
            'refugee', 'ukrainian', 'ukraine', 'asylum', 'integration',
            'newcomer', 'immigrant', 'migration', 'no language required',
            # Немецкий
            'ukrainisch willkommen', 'flüchtling willkommen', 'ohne deutschkenntnisse', 'arbeit ohne sprache',
            # Украинский / русский
            'українським біженцям', 'українці вітаються', 'без знання мови',
            'для беженцев', 'украинцам рады', 'без знания языка',
            # Польский
            'ukraińców mile widziane', 'bez znajomości języka',
            # Чешский
            'ukrajinci vítáni', 'bez znalosti jazyka'
        ]

        return any(indicator in text for indicator in refugee_indicators)
    
    def _format_salary(self, job_data: Dict, country: str) -> Optional[str]:
        """Форматирование зарплаты"""
        salary_min = job_data.get('salary_min')
        salary_max = job_data.get('salary_max')
        currency = self.countries[country]['currency']
        
        if salary_min and salary_max:
            if salary_min == salary_max:
                return f"{currency}{salary_min:,.0f}"
            else:
                return f"{currency}{salary_min:,.0f} - {currency}{salary_max:,.0f}"
        elif salary_min:
            return f"От {currency}{salary_min:,.0f}"
        elif salary_max:
            return f"До {currency}{salary_max:,.0f}"
        else:
            return None
    
    def _deduplicate_jobs(self, jobs: List[JobVacancy]) -> List[JobVacancy]:
        """Дедупликация"""
        seen = set()
        unique_jobs = []
        
        for job in jobs:
            key = f"{job.title.lower()}|{job.company.lower()}|{job.location.lower()}"
            if key not in seen:
                seen.add(key)
                unique_jobs.append(job)
        
        return unique_jobs
    
    def get_cache_stats(self) -> Dict:
        """Статистика кеша и запросов: читаем Redis (gjh:metrics:v1) с fallback на локальные self.stats."""
        local = {
            "cache_hits": int(self.stats.get("cache_hits", 0)),
            "cache_misses": int(self.stats.get("cache_misses", 0)),
            "api_requests": int(self.stats.get("api_requests", 0)),
            "total_jobs_found": int(self.stats.get("total_jobs_found", 0)),
        }

        r = getattr(self.cache_manager, "redis_client", None)
        if r is None:
            try:
                import os, redis as _r
                _url = os.getenv("REDIS_TLS_URL") or os.getenv("REDIS_URL")
                if _url:
                    r = _r.from_url(_url, decode_responses=False)
            except Exception:
                r = None

        if r:
            try:
                raw = r.hgetall("gjh:metrics:v1")
                for k, v in raw.items():
                    key = k.decode() if isinstance(k, (bytes, bytearray)) else k
                    if key in local:
                        try:
                            local[key] = int(v if not isinstance(v, (bytes, bytearray)) else v.decode())
                        except Exception:
                            pass
            except Exception:
                pass

        hits, misses = local["cache_hits"], local["cache_misses"]
        total = hits + misses
        hit_rate = f"{(hits/total*100):.1f}%" if total else "0.0%"

        return {
            "cache_hits": hits,
            "cache_misses": misses,
            "cache_hit_rate": hit_rate,
            "api_requests": local["api_requests"],
            "total_jobs_found": local["total_jobs_found"],
        }
    
    def cleanup_cache(self):
        """Очистка кеша"""
        self.cache_manager.cleanup_expired_cache()

def main():
    """Главная функция с демонстрацией кеширования"""
    print("🌍 GLOBAL JOB AGGREGATOR v2.4")
    print("💾 С УМНЫМ КЕШИРОВАНИЕМ")
    print("=" * 50)
    
    try:
        aggregator = GlobalJobAggregator(cache_duration_hours=12)  # Увеличили до 12 часов
        
        # Пример поиска
        preferences = {
            'is_refugee': True,
            'selected_jobs': ['Водитель такси', 'Курьер пешком'],
            'countries': ['de', 'pl'],
            'city': 'Berlin'
        }
        
        print(f"\n✅ ТЕСТОВЫЙ ПОИСК:")
        print(f"💼 Профессии: {', '.join(preferences['selected_jobs'])}")
        print(f"🌍 Страны: {', '.join(preferences['countries'])}")
        print(f"📍 Город: {preferences['city']}")
        
        start_time = time.time()
        
        # Первый поиск (будет кешироваться)
        print(f"\n🚀 ПЕРВЫЙ ПОИСК (API)...")
        jobs1 = aggregator.search_specific_jobs(preferences)
        search_time1 = time.time() - start_time
        
        print(f"⏱️ Время: {search_time1:.1f}с, найдено: {len(jobs1)} вакансий")
        
        # Второй поиск (из кеша)
        print(f"\n🚀 ВТОРОЙ ПОИСК (КЕШИРОВАНИЕ)...")
        start_time2 = time.time()
        jobs2 = aggregator.search_specific_jobs(preferences)
        search_time2 = time.time() - start_time2
        
        print(f"⏱️ Время: {search_time2:.1f}с, найдено: {len(jobs2)} вакансий")
        print(f"🚀 Ускорение: {search_time1/search_time2:.1f}x")
        
        # Статистика
        stats = aggregator.get_cache_stats()
        print(f"\n📊 СТАТИСТИКА КЕШИРОВАНИЯ:")
        for key, value in stats.items():
            print(f"   {key}: {value}")
        
        # Очистка
        aggregator.cleanup_cache()
        
    except KeyboardInterrupt:
        print("\n⏹️ Остановлено")
    except Exception as e:
        print(f"\n❌ Ошибка: {e}")

if __name__ == "__main__":
    main()