#!/usr/bin/env python3
"""
Remotive Aggregator for GlobalJobHunter v1.3
"""

import os
import requests
import time
from datetime import datetime
from typing import List, Dict, Optional
import hashlib
import re


# --- Переиспользуемые компоненты из adzuna_aggregator ---
from adzuna_aggregator import JobVacancy, CacheManager, RateLimiter

# --- Базовый класс для соблюдения архитектуры ---
from base_aggregator import BaseJobAggregator

try:
    from adzuna_aggregator import RateLimitedError, yield_briefly
except Exception:
    class RateLimitedError(Exception):
        pass
    import random, time
    def yield_briefly(base_ms: int = 200, jitter_ms: int = 120, cancel_check=None) -> bool:
        delay = (base_ms + (random.randint(0, jitter_ms) if jitter_ms > 0 else 0)) / 1000.0
        end = time.time() + delay
        while True:
            remain = end - time.time()
            if remain <= 0:
                break
            time.sleep(min(0.05, remain))
        return True


class RemotiveAggregator(BaseJobAggregator):
    """
    Поиск удалённых вакансий через Remotive API.
    Особенности:
      • Сначала пробуем ?category=<slug> (по доке Remotive), затем fallback на ?search=... (EN-ключи).
      • Кеш бережный: непустой — используем, пустой — не цементируем и не возвращаем.
      • Повторы на таймаут/сетевые/5xx. На 429 — cooldown.
      • Мягкая фильтрация офлайн-ролей: если всё офлайн — всё равно пробуем поиск.
    """

    # Профессии, которые обычно офлайн — не ограничиваем насмерть (см. мягкий фильтр в search_jobs)
    NON_REMOTE_JOBS = {
        # Примеры “реально офлайн”:
        'Водитель такси', 'Курьер пешком', 'Курьер-доставщик еды',
        'Водитель автобуса', 'Водитель грузовика',
        'Автомеханик', 'Автослесарь', 'Шиномонтажник', 'Диагност',
        'Заправщик на АЗС', 'Оператор АЗС', 'Кассир на АЗС',
        'Оператор добычи', 'Помощник бурильщика', 'Рабочий нефтебазы',
        'Строитель-разнорабочий', 'Грузчик', 'Складской работник',
        'Разнорабочий', 'Рабочий на производстве',
        'Официант', 'Бармен', 'Повар', 'Помощник повара', 'Посудомойщик',
        'Кассир', 'Продавец',
        'Уборщик', 'Садовник', 'Домработница', 'Массажист',
        'Медсестра', 'Сиделка', 'Няня', 'Гувернантка', 'Уход за пенсионерами'
    }

    def __init__(self, specific_jobs_map: Dict, cache_duration_hours: Optional[int] = None):
        super().__init__(source_name='Remotive')
        self.base_url = "https://remotive.com/api/remote-jobs"
        self.specific_jobs_map = specific_jobs_map
        self.cooldown_until = 0

        # TTL кеша (по умолчанию 24ч, можно пробросить REMOTIVE_CACHE_HOURS или общий CACHE_TTL_HOURS)
        if cache_duration_hours is None:
            try:
                cache_duration_hours = int(os.getenv('REMOTIVE_CACHE_HOURS', os.getenv('CACHE_TTL_HOURS', '24')))
            except Exception:
                cache_duration_hours = 24

        self.cache_manager = CacheManager(cache_duration_hours=cache_duration_hours)
        self.rate_limiter = RateLimiter(requests_per_minute=2)

        # Небольшая карта термин→категория (используется в старом коде is_relevant_job)
        self.job_to_category_map = {
            'python developer': 'software-dev',
            'web developer': 'software-dev',
            'programmer': 'software-dev',
            'software developer': 'software-dev',
            'qa engineer': 'software-dev',
            'software tester': 'software-dev',
            'data analyst': 'data',
            'data scientist': 'data',
            'designer': 'design',
            'product manager': 'product',
            'manager': 'management',
            'sales assistant': 'sales-marketing',
            'marketer': 'sales-marketing',
            'recruiter': 'hr',
            'customer support': 'customer-service'
        }

        print(f"✅ Remotive Aggregator инициализирован (TTL={cache_duration_hours}ч, RL=2/min).")

    # --- ПУБЛИЧНЫЕ МЕТОДЫ ---

    def get_supported_countries(self) -> Dict[str, Dict]:
        return {}  # Remotive — глобальный/remote

    def search_jobs(self, preferences: Dict, progress_callback=None, cancel_check=None) -> List[JobVacancy]:
        """
        Стратегия:
          1) Угадываем slug категории и пробуем ?category=<slug> (один крупный запрос).
          2) Если по категории пусто/мало — fallback на ?search=... (EN ключи по выбранным профессиям).
          3) Дедупликация; кеш/ретраи внутри низкоуровневого метода.
        """
        all_jobs: List[JobVacancy] = []

        selected = preferences.get('selected_jobs') or []
        if not selected:
            return []

        # Мягкая фильтрация офлайн-ролей
        initial_count = len(selected)
        filtered = [j for j in selected if j not in self.NON_REMOTE_JOBS]
        if not filtered:
            print(f"ℹ️ Remotive: все {initial_count} выбранных профессий помечены как офлайн — всё же пробуем по ним (fallback).")
            filtered = selected
        else:
            dropped = set(selected) - set(filtered)
            if dropped:
                print(f"ℹ️ Remotive: исключил офлайн-списки: {', '.join(dropped)}")
        selected = filtered

        try:
            # 1) Категория (slug) по выбранным RU-ролям
            slug = self._guess_category_slug(selected)
            cat_jobs: List[JobVacancy] = []
            if slug:
                cat_jobs = self._query_remotive({"category": slug}, progress_callback=progress_callback, cancel_check=cancel_check)

            if cancel_check and cancel_check():
                out = self._deduplicate_jobs(cat_jobs)
                print(f"✅ {self.source_name}: Поиск завершен. Найдено всего: {len(out)} вакансий.")
                return out

            # 2) Fallback: точечные search-запросы по EN-ключам, если по категории маловато
            search_jobs_total: List[JobVacancy] = []
            if len(cat_jobs) < 10:  # порог можно подстроить
                for ru_title in selected:
                    if cancel_check and cancel_check():
                        break
                    terms = self._get_english_keywords(ru_title)
                    if not terms:
                        continue
                    search_jobs_total.extend(
                        self._query_remotive(terms, progress_callback=progress_callback, cancel_check=cancel_check)
                    )

            all_jobs.extend(cat_jobs)
            all_jobs.extend(search_jobs_total)

        except RateLimitedError:
            print(f"⛔ {self.source_name}: источник переведён в cooldown (429).")
        except Exception as e:
            print(f"❌ {self.source_name}: ошибка поиска — {e}")

        deduped = self._deduplicate_jobs(all_jobs)
        print(f"✅ {self.source_name}: Поиск завершен. Найдено всего: {len(deduped)} вакансий.")
        return deduped

    # --- ВСПОМОГАТЕЛЬНЫЕ МЕТОДЫ ---

    def _guess_category_slug(self, ru_titles: List[str]) -> Optional[str]:
        """
        Пробуем угадать slug категории Remotive по выбранным RU-профессиям.
        Возвращаем None, если уверенности нет (тогда используем search).
        """
        text = " ".join(ru_titles).lower()
        # Мини-карта подсказок (дополняй по нужде)
        m = {
            "software-dev":   ["разработ", "программист", "developer", "инженер по по", "qa", "тестиров", "backend", "frontend", "fullstack"],
            "data":           ["аналитик", "data", "данн", "scientist", "ml", "ai"],
            "design":         ["дизайн", "ui", "ux", "дизайнер", "product designer", "ui/ux"],
            "product":        ["продакт", "product manager", "продукт"],
            "management":     ["менеджер", "руковод", "project", "team lead", "координатор", "администратор"],
            "sales-marketing":["маркет", "smm", "seo", "контент", "продаж", "sales", "marketing", "ppc"],
            "hr":             ["hr", "рекрутер", "кадров", "talent", "recruiter"],
            "customer-service":["поддержк", "саппорт", "support", "customer", "helpdesk"],
            "devops":         ["devops", "sre", "админ", "инфра", "platform"],
            "finance-legal":  ["бухгалт", "финанс", "юрист", "legal", "compliance"],
            "writing":        ["копирайт", "writer", "редактор", "контентмейкер"],
            "education":      ["учител", "преподав", "education", "coach", "тренер"],
            "sales":          ["sales", "аккаунт", "account"],
        }
        for slug, cues in m.items():
            if any(cue in text for cue in cues):
                return slug
        return None

    def _get_english_keywords(self, russian_job_title: str) -> List[str]:
        """
        Берём из nested self.specific_jobs_map термы и оставляем ТОЛЬКО англ. ASCII.
        Ограничиваем до 8, чтобы не раздувать URL.
        """
        import re  # локальный импорт, чтобы не ловить NameError
        for category in self.specific_jobs_map.values():
            terms = category.get(russian_job_title)
            if terms:
                en = [t for t in terms if t and re.match(r'^[A-Za-z0-9 .,+\-]+$', t)]
                return en[:8]
        return []

    def _query_remotive(self, terms_or_params, progress_callback=None, cancel_check=None, fresh: bool = False) -> List[JobVacancy]:
        """
        Универсальная обёртка поверх _fetch_jobs:
          • dict {'category': slug} → один запрос по категории.
          • list/tuple/str → 1..N запросов по search с батчингом (3–4 слова, <=80 символов).
        """
        def _run_one(params: Dict) -> List[JobVacancy]:
            jobs = self._fetch_jobs(params, fresh=fresh, max_retries=2)
            if jobs and progress_callback:
                try:
                    progress_callback(list(jobs))
                except Exception:
                    pass
            return jobs or []

        # Ветка категории
        if isinstance(terms_or_params, dict) and terms_or_params.get("category"):
            return _run_one({"category": terms_or_params["category"]})

        # Ветка search
        if isinstance(terms_or_params, (list, tuple)):
            cleaned = [str(t).strip() for t in terms_or_params if str(t).strip()]
        else:
            cleaned = [str(terms_or_params or "").strip()] if str(terms_or_params or "").strip() else []

        if not cleaned:
            return []

        results: List[JobVacancy] = []
        batch: List[str] = []
        curr_len = 0
        MAX_TERMS = 4
        MAX_LEN = 80

        for t in cleaned:
            add_len = (1 if batch else 0) + len(t)
            if len(batch) >= MAX_TERMS or (curr_len + add_len) > MAX_LEN:
                results.extend(_run_one({'search': " ".join(batch)}))
                batch, curr_len = [t], len(t)
            else:
                batch.append(t)
                curr_len += add_len

        if batch:
            results.extend(_run_one({'search': " ".join(batch)}))

        return results

    def _fetch_jobs(self, params: Dict, fresh: bool = False, max_retries: int = 2) -> List[JobVacancy]:
        """
        Один запрос к Remotive (кеш + повторы).
        Кеш:
          • fresh=True → игнорировать чтение кеша (запись остаётся).
          • непустой кеш → возвращаем.
          • пустой кеш → НЕ возвращаем, идём в API.
          • пустой ответ из API НЕ кешируем.
        Повторы:
          • таймаут/сетевая/5xx → retry с лёгким джиттером.
          • 429 → cooldown и исключение.
        """
        # Respect cooldown
        now = time.time()
        if getattr(self, "cooldown_until", 0) > now:
            left = int(self.cooldown_until - now)
            print(f"⛔ {self.source_name}: cooldown ещё {left}s — пропускаем {params}.")
            raise RateLimitedError("REMOTIVE_COOLDOWN")

        tag = params.get('search') or params.get('category')

        # Чтение кеша
        if not fresh:
            cached = self.cache_manager.get_cached_result(params)
            if cached is not None:
                if cached:
                    print(f"    💾 Cache HIT Remotive для '{tag}': {len(cached)}")
                    return cached
                else:
                    print(f"    💾 Cache HIT Remotive (empty) для '{tag}', пробуем API...")

        attempts = 1 + max(0, int(max_retries))
        last_err = None

        for attempt in range(1, attempts + 1):
            # Rate limit
            self.rate_limiter.wait_if_needed()

            try:
                r = requests.get(self.base_url, params=params, timeout=12)
                if r.status_code == 200:
                    data = r.json() or {}
                    jobs_raw = data.get('jobs') or []
                    out: List[JobVacancy] = []
                    for raw in jobs_raw:
                        j = self._normalize_job_data(raw, tag or "")
                        if j:
                            out.append(j)

                    # НЕ кешируем пустой результат
                    if out:
                        self.cache_manager.cache_result(params, out)
                        print(f"    🌐 Remotive '{tag}': +{len(out)} (cached)")
                    else:
                        print(f"    🌐 Remotive '{tag}': +0 (not cached)")
                    return out

                if r.status_code == 429:
                    cooldown = int(os.getenv("REMOTIVE_COOLDOWN_SEC", "120"))
                    self.cooldown_until = time.time() + cooldown
                    print(f"⛔ Remotive 429 → cooldown {cooldown}s для '{tag}'")
                    raise RateLimitedError("REMOTIVE_RATE_LIMIT")

                if 500 <= r.status_code <= 599:
                    last_err = RuntimeError(f"HTTP {r.status_code}")
                    print(f"⚠️ {self.source_name}: HTTP {r.status_code} для '{tag}', попытка {attempt}/{attempts}")
                    self._sleep_jitter(0.3, 0.6)
                    if attempt < attempts:
                        continue
                    return []

                print(f"❌ {self.source_name} HTTP {r.status_code}: {r.text[:200]}")
                return []

            except requests.Timeout as e:
                last_err = e
                print(f"⚠️ {self.source_name}: таймаут запроса для '{tag}', попытка {attempt}/{attempts}")
                self._sleep_jitter(0.3, 0.6)
                if attempt < attempts:
                    continue
                return []
            except requests.RequestException as e:
                last_err = e
                print(f"⚠️ {self.source_name}: сетевая ошибка для '{tag}': {e}, попытка {attempt}/{attempts}")
                self._sleep_jitter(0.3, 0.6)
                if attempt < attempts:
                    continue
                return []
            except RateLimitedError:
                raise
            except Exception as e:
                last_err = e
                print(f"❌ {self.source_name}: ошибка запроса '{tag}': {e}")
                return []

        if last_err:
            print(f"❌ {self.source_name}: исчерпаны попытки для '{tag}': {last_err}")
        return []

    # --- НОРМАЛИЗАЦИЯ/УТИЛИТЫ ---

    def _normalize_job_data(self, raw_job: Dict, search_term: str) -> Optional[JobVacancy]:
        try:
            title = raw_job.get('title', '')
            description = raw_job.get('description', '')

            url = raw_job.get('url')
            if not url:
                return None
            job_id = hashlib.md5(url.encode()).hexdigest()

            date_str = raw_job.get('publication_date', '')
            try:
                posted_date = datetime.fromisoformat(date_str.replace('Z', '+00:00')).strftime('%Y-%m-%d')
            except (ValueError, TypeError):
                posted_date = datetime.now().strftime('%Y-%m-%d')

            return JobVacancy(
                id=f"remotive_{job_id}",
                title=title,
                company=raw_job.get('company_name', 'Not specified'),
                location=raw_job.get('candidate_required_location', 'Worldwide'),
                salary=raw_job.get('salary'),
                description=description,
                apply_url=url,
                source=self.source_name,
                posted_date=posted_date,
                country='Remote',
                job_type=raw_job.get('job_type'),
                language_requirement=self.determine_language_requirement(title, description),
                refugee_friendly=self.is_refugee_friendly(title, description, search_term)
            )
        except Exception as e:
            print(f"⚠️ {self.source_name}: Ошибка нормализации вакансии: {e}")
            return None

    def is_relevant_job(self, job_title: str, job_description: str, search_term: str) -> bool:
        # Сохраняем старую “простую” проверку для совместимости
        if search_term in self.job_to_category_map.values():
            return True
        search_keywords = str(search_term or '').lower().split()
        title_lower = (job_title or '').lower()
        return any(keyword in title_lower for keyword in search_keywords)

    def _deduplicate_jobs(self, jobs: List[JobVacancy]) -> List[JobVacancy]:
        seen = set()
        unique_jobs = []
        for job in jobs:
            if job.apply_url not in seen:
                seen.add(job.apply_url)
                unique_jobs.append(job)
        return unique_jobs

    # Локальный “бэкофф”, если нет глобального yield_briefly
    @staticmethod
    def _sleep_jitter(min_sec: float, max_sec: float) -> None:
        try:
            import random, time as _t
            _t.sleep(random.uniform(min_sec, max_sec))
        except Exception:
            pass
