#!/usr/bin/env python3
"""
Careerjet Aggregator for GlobalJobHunter
"""

import os
import requests
from requests.adapters import HTTPAdapter
try:
    from urllib3.util.retry import Retry
except Exception:
    Retry = None
import time
from datetime import datetime
from typing import List, Dict, Optional
from dataclasses import asdict
import hashlib
from dotenv import load_dotenv
import certifi

DEFAULT_CJ_REFERER = os.getenv("CAREERJET_REFERER", "https://globaljobhunter.vip/results")


# --- Переиспользуемые компоненты из adzuna_aggregator ---
from adzuna_aggregator import JobVacancy, CacheManager, RateLimiter, GlobalJobAggregator

# --- Базовый класс для соблюдения архитектуры ---
from base_aggregator import BaseJobAggregator

# Загружаем переменные окружения из .env файла
load_dotenv()

class CareerjetAggregator(BaseJobAggregator):
    """
    Агрегатор для поиска вакансий через Careerjet API.
    - Поддерживает поиск как по стране, так и по городу.
    - **Новая логика:** Выполняет отдельные запросы для каждой профессии для большей точности.
    """
    def __init__(self, adzuna_countries: Dict, specific_jobs_map: Dict, cache_duration_hours: Optional[int] = None):
        super().__init__(source_name='Careerjet')
        self.base_url = "https://search.api.careerjet.net/v4/query"

        self.api_key = os.getenv('CAREERJET_API_KEY')
        if not self.api_key:
            raise ValueError("CAREERJET_API_KEY is not set")

        # (опционально сохраняем affid, если где-то нужен)
        self.affid = os.getenv('CAREERJET_AFFID', '')

        # Всегда используем актуальный CA-бандл и закрепляем его в окружении
        self._cj_verify_path = os.getenv('REQUESTS_CA_BUNDLE') or os.getenv('SSL_CERT_FILE') or certifi.where()
        os.environ['SSL_CERT_FILE'] = self._cj_verify_path
        os.environ['REQUESTS_CA_BUNDLE'] = self._cj_verify_path
        print(f"🔐 Careerjet TLS bundle: {self._cj_verify_path}")

        # TTL кеша (часы)
        if cache_duration_hours is None:
            try:
                cache_duration_hours = int(os.getenv('CAREERJET_CACHE_HOURS', os.getenv('CACHE_TTL_HOURS', '24')))
            except Exception:
                cache_duration_hours = 24

        self.cache_manager = CacheManager(cache_duration_hours=cache_duration_hours)
        self.rate_limiter = RateLimiter(requests_per_minute=25)
        self.cooldown_until = 0  # глобальный кулдаун при 429

        # Страны и названия
        self.country_map = {
            'gb': 'United Kingdom', 'us': 'United States', 'de': 'Germany',
            'fr': 'France', 'es': 'Spain', 'it': 'Italy', 'nl': 'Netherlands',
            'pl': 'Poland', 'ca': 'Canada', 'au': 'Australia', 'at': 'Austria',
            'ch': 'Switzerland', 'be': 'Belgium', 'se': 'Sweden', 'no': 'Norway',
            'dk': 'Denmark', 'cz': 'Czech Republic', 'sk': 'Slovakia', 'ua': 'Ukraine'
        }

        # locale_code для Careerjet
        self.locale_map = {
            'gb': 'en_GB', 'us': 'en_US', 'de': 'de_DE', 'fr': 'fr_FR',
            'es': 'es_ES', 'it': 'it_IT', 'nl': 'nl_NL', 'pl': 'pl_PL',
            'ca': 'en_CA', 'au': 'en_AU', 'at': 'de_AT', 'ch': 'de_CH',
            'be': 'nl_BE', 'se': 'sv_SE', 'no': 'no_NO', 'dk': 'da_DK',
            'cz': 'cs_CZ', 'sk': 'sk_SK', 'ua': 'uk_UA'
        }

        self.adzuna_countries = adzuna_countries
        self.specific_jobs_map = specific_jobs_map

        # Сессия с ретраями для стабильности
        self.session = requests.Session()
        if Retry:
            retries = Retry(
                total=3,
                backoff_factor=0.6,
                status_forcelist=[429, 500, 502, 503, 504],
                allowed_methods=frozenset(["GET"])
            )
            self.session.mount("https://", HTTPAdapter(max_retries=retries))
        else:
            self.session.mount("https://", HTTPAdapter())

        print(f"✅ Careerjet Aggregator инициализирован (affid: ...{self.affid[-4:]})")

    def _terms_from_ru(self, ru_title: str) -> List[str]:
        """
        Возвращает список поисковых термов (EN и др.) для русского названия профессии.
        Работает с разными формами specific_jobs_map:
        - { <category>: { <ru_title>: [ "term1", "term2", ... ] } }
        - { <category>: { <ru_title>: { 'en': [...], 'keywords': { 'en': [...], 'de': [...], ... }, 'terms': [...] } } }
        """
        terms: List[str] = []

        # где лежит карта
        sj = getattr(self, "specific_jobs_map", None) or getattr(self, "specific_jobs", None) or {}

        # 1) прямое совпадение ключа ru_title
        if isinstance(sj, dict):
            for _cat, ru_map in sj.items():
                if not isinstance(ru_map, dict):
                    continue
                if ru_title in ru_map:
                    val = ru_map[ru_title]
                    if isinstance(val, list):
                        terms.extend(val)
                    elif isinstance(val, dict):
                        # возможные поля
                        if isinstance(val.get("en"), list):
                            terms.extend(val["en"])
                        kw = val.get("keywords")
                        if isinstance(kw, dict):
                            for lst in kw.values():
                                if isinstance(lst, list):
                                    terms.extend(lst)
                        elif isinstance(kw, list):
                            terms.extend(kw)
                        if isinstance(val.get("terms"), list):
                            terms.extend(val["terms"])
                    break

        # 2) fallback: если ru_title могли хранить в списке val['ru'] и т.п.
        if not terms and isinstance(sj, dict):
            for _cat, ru_map in sj.items():
                if not isinstance(ru_map, dict):
                    continue
                for _ru_key, val in ru_map.items():
                    if not isinstance(val, dict):
                        continue
                    ru_list = val.get("ru") or val.get("ru_terms")
                    if isinstance(ru_list, list) and ru_title in ru_list:
                        kw = val.get("keywords") or {}
                        if isinstance(kw, dict):
                            for lst in kw.values():
                                if isinstance(lst, list):
                                    terms.extend(lst)
                        if isinstance(val.get("en"), list):
                            terms.extend(val["en"])
                        if isinstance(val.get("terms"), list):
                            terms.extend(val["terms"])
                        break

        # нормализуем и уникализируем, сохраняя порядок
        seen = set()
        uniq = []
        for t in terms:
            t = (t or "").strip()
            if not t:
                continue
            key = t.lower()
            if key not in seen:
                uniq.append(t)
                seen.add(key)
        return uniq
    
    def get_supported_countries(self) -> Dict[str, Dict]:
        """Возвращает словарь стран, поддерживаемых этим агрегатором."""
        return {}

    def search_jobs(self, preferences: Dict, progress_callback=None, cancel_check=None,
                user_ip: str = '0.0.0.0', user_agent: str = 'Mozilla/5.0', page_url: str = '') -> List[JobVacancy]:
        """
        Поиск на Careerjet ПО КАЖДОМУ ТЕРМИНУ отдельно.
        - Жёстко уважаем выбранные профессии из preferences['selected_jobs'].
        - Не кешируем пустые результаты (чтобы не «застывали нули»).
        - Пагинация с ограничением по количеству страниц и защитой от дубликатов.
        - cancel_check() мягко прерывает цикл и возвращает уже найденное.
        """
        all_jobs: List[JobVacancy] = []

        # глобальный кулдаун источника
        now = time.time()
        if getattr(self, "cooldown_until", 0) > now:
            left = int(self.cooldown_until - now)
            print(f"⛔ Careerjet: на cooldown ещё {left}s — источник временно пропущен.")
            return []

        # входные предпочтения
        selected_jobs: List[str] = preferences.get('selected_jobs', []) or []
        countries: List[str] = preferences.get('countries', []) or []
        cities: List[str] = preferences.get('cities', []) or []

        if not selected_jobs or not countries:
            return []

        # лимит страниц на один term
        try:
            max_pages = int(os.getenv("CAREERJET_MAX_PAGES_PER_TERM", "15"))
        except Exception:
            max_pages = 15
        max_pages = min(max_pages, 10)
        
        # основной цикл
        for ru_title in selected_jobs:
            if cancel_check and cancel_check():
                break

            # === ВАЖНО: берём только термы этой профессии; если маппинга нет — пропускаем ===
            en_terms = list(dict.fromkeys([t for t in self._terms_from_ru(ru_title) if t]))
            if not en_terms:
                # нет маппинга — вообще не трогаем этот ru_title
                continue

            print(f"📡 Careerjet: '{ru_title}' → термы: {', '.join(en_terms)}")

            for cc in countries:
                if cancel_check and cancel_check():
                    break

                country_name = self.country_map.get(cc)
                if not country_name:
                    continue
                locale_code = self._get_locale_code(cc)

                locations = [f"{city}, {country_name}" for city in cities] if cities else [country_name]
                for loc in locations:
                    if cancel_check and cancel_check():
                        break

                    for idx, term in enumerate(en_terms, 1):
                        if cancel_check and cancel_check():
                            break

                        # 1) Попытка из субкеша (пустые мы там не храним)
                        cached = self.cache_manager.get_term_cached_result(cc, loc, term)
                        if cached is not None:
                            print(f"    💾 Subcache HIT Careerjet [{cc}/{loc}] term='{term}': {len(cached)}")
                            if cached and progress_callback:
                                try:
                                    progress_callback(cached)
                                except Exception:
                                    pass
                            all_jobs.extend(cached or [])
                            continue

                        print(f"    🔍 Careerjet [{cc}/{loc}] term {idx}/{len(en_terms)}: '{term}'")
                        page = 1
                        collected_for_term: List[JobVacancy] = []
                        seen_urls_for_term: set[str] = set()

                        while True:
                            if cancel_check and cancel_check():
                                break

                            batch = self._request_page(
                                term=term,
                                location=loc,
                                country_name=country_name,
                                locale_code=locale_code,
                                page=page,
                                user_ip=user_ip,
                                user_agent=user_agent,
                                page_url=page_url
                            )


                            # None → 429/cooldown — прекращаем по этому term
                            if batch is None:
                                break

                            # пустая страница — конец пагинации
                            if not batch:
                                if page == 1:
                                    print(f"    📄 Careerjet: {loc} term='{term}' page 1: +0")
                                break

                            # фильтрация дубликатов в рамках term
                            new_batch: List[JobVacancy] = []
                            for j in batch:
                                url_or_id = getattr(j, "apply_url", None) or getattr(j, "id", None)
                                if not url_or_id or url_or_id in seen_urls_for_term:
                                    continue
                                seen_urls_for_term.add(url_or_id)
                                new_batch.append(j)

                            if not new_batch:
                                print(f"🔁 Careerjet: {loc} term='{term}' page {page}: только дубликаты — стоп.")
                                break

                            # прогресс наружу
                            if progress_callback:
                                try:
                                    progress_callback(new_batch)
                                except Exception:
                                    pass

                            collected_for_term.extend(new_batch)
                            all_jobs.extend(new_batch)

                            page += 1
                            if page > max_pages:
                                print(f"⏹ Careerjet: достигнут лимит страниц {max_pages} для term='{term}' [{loc}]")
                                break

                        # 2) кешируем ТОЛЬКО если что-то нашли
                        if collected_for_term:
                            try:
                                self.cache_manager.cache_term_result(cc, loc, term, collected_for_term)
                            except Exception:
                                pass

        return self._deduplicate_jobs(all_jobs)




    
    def _request_page(self, term: str, location: str, country_name: str, locale_code: str, page: int,
                  *, user_ip: str, user_agent: str, page_url: str) -> Optional[List[JobVacancy]]:
        """
        Один запрос к Careerjet.
        Возвращает:
            - list[JobVacancy] — если страница содержит вакансии,
            - [] — если вакансий нет/страниц больше нет,
            - None — если получен 429 и включён cooldown.
        """
        # глобальный кулдаун после 429
        now = time.time()
        if getattr(self, "cooldown_until", 0) > now:
            return []

        params = {
            'locale_code': locale_code,
            'keywords': term,
            'location': location or '',
            'page': page,             # 1..10
            'page_size': 20,          # 1..100
            'user_ip': user_ip,       # ОБЯЗАТЕЛЬНО
            'user_agent': user_agent, # ОБЯЗАТЕЛЬНО
        }

        dbg = dict(params)
        dbg['user_ip'] = (str(dbg.get('user_ip'))[:7] + "xxx") if dbg.get('user_ip') else None
        print("CJ PARAMS =>", dbg, flush=True)

        headers = {
            'Accept': 'application/json',
            'Referer': page_url or os.getenv("CAREERJET_REFERER", "https://www.globaljobhunter.vip/results"),
            'User-Agent': user_agent or 'Mozilla/5.0',
        }

        def _do_get(p, verify_mode=None):
            if verify_mode is None:
                verify_mode = self._cj_verify_path  # pinned certifi bundle
            return self.session.get(
                self.base_url,
                params=p,
                auth=(self.api_key, ''),     # Basic Auth: username=API_KEY, пароль пустой
                headers=headers,
                timeout=15,
                verify=verify_mode,
            )

        try:
            self.rate_limiter.wait_if_needed()

            # Попытка 1: обычная с нашим pinned CA-бандлом
            try:
                r = _do_get(params)
            except requests.exceptions.SSLError as e1:
                print(f"⚠️ SSL error with pinned bundle → try certifi.where(): {e1}")
                # Попытка 2: явный certifi.where()
                try:
                    r = _do_get(params, verify_mode=certifi.where())
                except requests.exceptions.SSLError as e2:
                    print(f"⚠️ SSL still failing → try verify=False only if CJ_INSECURE=1: {e2}")
                    # Попытка 3: без верификации (только для диагностики)
                    if os.getenv("CJ_INSECURE") == "1":
                        r = _do_get(params, verify_mode=False)
                    else:
                        # Попытка 4: старый HTTP API как последний шанс (временный обход)
                        if os.getenv("CJ_USE_OLD_HTTP") == "1":
                            return self._fallback_old_api(term, location, locale_code, page, user_ip, user_agent, page_url)
                        # если фолбэк выключен — фиксируем ошибку и выходим
                        print(f"❌ Careerjet: SSL error page={page} [{location}] term='{term}': {e2}")
                        return []

            # 429 → кулдаун и повторить позже
            if r.status_code == 429:
                cd = float(os.getenv('CAREERJET_COOLDOWN_SEC', '150'))
                self.cooldown_until = time.time() + cd
                print(f"⛔ Careerjet: HTTP 429 → cooldown {int(cd)}s (term='{term}', loc='{location}')")
                return None

            if r.status_code != 200:
                print(f"❌ Careerjet: HTTP {r.status_code} page={page} [{location}] term='{term}'")
                # при не-200 можно попробовать старый HTTP, если разрешено
                if os.getenv("CJ_USE_OLD_HTTP") == "1":
                    return self._fallback_old_api(term, location, locale_code, page, user_ip, user_agent, page_url)
                return []

            data = r.json() or {}

            # Режим выбора локации
            if data.get('type') == 'LOCATIONS':
                locs = data.get('locations') or []
                if not locs:
                    return []
                params2 = dict(params)
                params2['location'] = locs[0]
                try:
                    r = _do_get(params2)
                except requests.exceptions.SSLError:
                    if os.getenv("CJ_USE_OLD_HTTP") == "1":
                        return self._fallback_old_api(term, locs[0], locale_code, page, user_ip, user_agent, page_url)
                    return []
                if r.status_code != 200:
                    if os.getenv("CJ_USE_OLD_HTTP") == "1":
                        return self._fallback_old_api(term, locs[0], locale_code, page, user_ip, user_agent, page_url)
                    return []
                data = r.json() or {}

            if data.get('type') != 'JOBS':
                # если новый API не даёт JOBS — попробуем старый, если разрешено
                if os.getenv("CJ_USE_OLD_HTTP") == "1":
                    return self._fallback_old_api(term, location, locale_code, page, user_ip, user_agent, page_url)
                return []

            jobs_raw = data.get('jobs') or []
            batch: List[JobVacancy] = []
            for raw in jobs_raw:
                job = self._normalize_job_data(raw, country_name, term)
                if job:
                    batch.append(job)

            print(f"📄 Careerjet: {location} term='{term}' page {page}: +{len(batch)}")
            return batch

        except requests.Timeout:
            print(f"⚠️ Careerjet: таймаут page={page} [{location}] term='{term}'")
            return []
        except Exception as e:
            print(f"❌ Careerjet: ошибка page={page} [{location}] term='{term}': {e}")
            return []



    def _fallback_old_api(self, term: str, location: str, locale_code: str, page: int,
                      user_ip: str, user_agent: str, page_url: str) -> List[JobVacancy]:
        """
        Временный обход на старый HTTP API (v3). Включается, если CJ_USE_OLD_HTTP=1.
        """
        try:
            old_url = "http://public.api.careerjet.net/search"
            old_params = {
                'affid': getattr(self, "affid", os.getenv('CAREERJET_AFFID', '')),
                'keywords': term,
                'location': location or '',
                'page': page,
                'pagesize': 20,
                'sort': 'date',
                'locale_code': locale_code,
                'user_ip': user_ip,
                'user_agent': user_agent,
                # Careerjet просит URL страницы-источника
                'url': page_url or os.getenv("CAREERJET_REFERER", "https://www.globaljobhunter.vip/results"),
            }
            r = self.session.get(old_url, params=old_params, timeout=15)
            if r.status_code != 200:
                return []
            data = r.json() or {}
            if data.get('type') != 'JOBS':
                return []
            jobs_raw = data.get('jobs') or []
            print(f"🟡 TEMP fallback to old public.api.careerjet.net/search succeeded (+{len(jobs_raw)})")
            # country_name нам уже передают в основной метод; тут не вычисляем заново
            # вернём нормализованные вакансии на базе того же терма
            out: List[JobVacancy] = []
            for raw in jobs_raw:
                job = self._normalize_job_data(raw, location, term)  # передаём location как country_name-плейсхолдер
                if job:
                    out.append(job)
            return out
        except Exception as e:
            print(f"❌ Old API fallback failed: {e}")
            return []
        

    def _get_locale_code(self, country_code: str) -> str:
        """Возвращает корректный locale_code для Careerjet."""
        return self.locale_map.get(country_code.lower(), 'en_GB')
        


    # DEPRECATED: legacy Careerjet v3.0 flow — not used with v4 API
    def _fetch_all_pages_legacy(
    self,
    keywords: str,
    location: str,
    country_code: str,
    progress_callback=None,
    cancel_check=None
) -> List[JobVacancy]:
        page = 1
        total_jobs: List[JobVacancy] = []

        while True:
            if cancel_check and cancel_check():
                break

            search_params = {
                'affid': self.affid,
                'keywords': keywords,
                'location': location,
                'page': page,
                'sort': 'date',
                'user_ip': '127.0.0.1',
                'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/108.0.0.0 Safari/537.36'
            }
            cache_key_params = {k: v for k, v in search_params.items() if k not in ['user_ip', 'user_agent']}

            cached_result = self.cache_manager.get_cached_result(cache_key_params)
            if cached_result:
                total_jobs.extend(cached_result)
                if progress_callback and cached_result:
                    try:
                        progress_callback(cached_result)
                    except Exception:
                        pass
                if len(cached_result) < 50:
                    break
                page += 1
                continue

            self.rate_limiter.wait_if_needed(cancel_check=cancel_check)
            if cancel_check and cancel_check():
                return total_jobs

            try:
                response = requests.get(self.base_url, params=search_params, timeout=15)
                if response.status_code != 200:
                    print(f"❌ {self.source_name} API {response.status_code}: {response.text}")
                    break

                data = response.json()
                if data.get('type') == 'ERROR':
                    print(f"❌ {self.source_name} API error: {data.get('error')}")
                    break

                jobs_on_page_raw = data.get('jobs', [])
                if not jobs_on_page_raw:
                    break

                normalized_jobs: List[JobVacancy] = []
                country_name = self._get_country_name_by_code(country_code)
                for job_data in jobs_on_page_raw:
                    job = self._normalize_job_data(job_data, country_name, keywords)
                    if job:
                        normalized_jobs.append(job)

                total_jobs.extend(normalized_jobs)
                # ⬇️ КЕШИРУЕМ ТОЛЬКО НЕПУСТЫЕ СТРАНИЦЫ
                if normalized_jobs:
                    self.cache_manager.cache_result(cache_key_params, normalized_jobs)

                print(f"📄 {self.source_name}: {location} — стр. {page}, найдено: {len(normalized_jobs)}")

                if progress_callback and normalized_jobs:
                    try:
                        progress_callback(normalized_jobs)
                    except Exception:
                        pass

                pagesize = data.get('pagesize') or len(jobs_on_page_raw)
                if len(jobs_on_page_raw) < pagesize:
                    break

                page += 1
                time.sleep(0.3)

            except requests.Timeout:
                print(f"⚠️ {self.source_name}: таймаут, прекращаем для '{location}'")
                break
            except Exception as e:
                print(f"❌ {self.source_name}: критическая ошибка: {e}")
                break

        return total_jobs



    def _normalize_job_data(self, raw_job: Dict, country_name: str, search_term: str) -> Optional[JobVacancy]:
        """
        Преобразует сырые данные от API в стандартизированный объект JobVacancy.
        """
        try:
            title = raw_job.get('title', '')
            description = raw_job.get('description', '')
            if not self.is_relevant_job(title, description, search_term):
                return None

            url = raw_job.get('url')
            if not url:
                return None
            job_id = hashlib.md5(url.encode()).hexdigest()

            date_str = raw_job.get('date', '')
            try:
                posted_date = datetime.strptime(date_str, '%a, %d %b %Y %H:%M:%S %Z').strftime('%Y-%m-%d')
            except (ValueError, TypeError):
                posted_date = datetime.now().strftime('%Y-%m-%d')

            return JobVacancy(
                id=f"careerjet_{job_id}",
                title=title,
                company=raw_job.get('company', 'Not specified'),
                location=raw_job.get('locations', 'Not specified'),
                salary=raw_job.get('salary'),
                description=description,
                apply_url=url,
                source=self.source_name,
                posted_date=posted_date,
                country=country_name,
                job_type=None,
                language_requirement=self.determine_language_requirement(title, description),
                refugee_friendly=self.is_refugee_friendly(title, description, search_term)
            )
        except Exception as e:
            print(f"⚠️ {self.source_name}: Ошибка нормализации вакансии: {e}")
            return None

    def is_relevant_job(self, job_title: str, job_description: str, search_term: str) -> bool:
        """
        Простая проверка на релевантность.
        """
        search_terms = search_term.lower().split()
        title_lower = job_title.lower()
        
        return any(term in title_lower for term in search_terms if len(term) > 2)

    def _get_country_name_by_code(self, country_code: str) -> str:
        """
        Вспомогательный метод для получения полного имени страны по коду.
        """
        return self.adzuna_countries.get(country_code, {}).get('name', country_code.upper())

    def _deduplicate_jobs(self, jobs: List[JobVacancy]) -> List[JobVacancy]:
        """Удаление дубликатов по уникальному ключу."""
        seen = set()
        unique_jobs = []
        for job in jobs:
            if job.apply_url not in seen:
                seen.add(job.apply_url)
                unique_jobs.append(job)
        return unique_jobs

if __name__ == '__main__':
    print("🚀 Тестовый запуск CareerjetAggregator...")
    
    try:
        main_aggregator_for_test = GlobalJobAggregator()
        aggregator = CareerjetAggregator(
            adzuna_countries=main_aggregator_for_test.countries,
            specific_jobs_map=main_aggregator_for_test.specific_jobs
        )
    except Exception as e:
        print(f"❌ Не удалось инициализировать агрегаторы для теста: {e}")
        aggregator = None

    if aggregator:
        test_preferences = {
            'selected_jobs': ['Заправщик на АЗС', 'Оператор АЗС'],
            'countries': ['us'],
            'cities': [] # <-- Тестируем без города
        }
        
        start_time = time.time()
        found_jobs = aggregator.search_jobs(test_preferences)
        end_time = time.time()
        
        print(f"\n\n--- РЕЗУЛЬТАТЫ ТЕСТА ---")
        print(f"⏱️ Время выполнения: {end_time - start_time:.2f} секунд")
        print(f"📊 Найдено вакансий: {len(found_jobs)}")
        
        if found_jobs:
            print("\n📝 Пример 5 найденных вакансий:")
            for i, job in enumerate(found_jobs[:5]):
                print(f"  {i+1}. {job.title} в {job.company} ({job.location})")
                print(f"     Ссылка: {job.apply_url}")
