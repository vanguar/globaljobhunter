#!/usr/bin/env python3
"""
Jobicy API Aggregator - Бесплатные удаленные вакансии
С соблюдением rate limits (1 запрос в час)
"""

import requests
import time
import json
import os
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional
from dataclasses import dataclass
from adzuna_aggregator import JobVacancy, CacheManager


class JobicyAggregator:
    """
    Jobicy — один общий дамп удалённых вакансий.
    Логика:
      - Кешируем JSON-дамп на N часов (JOBICY_CACHE_HOURS > CACHE_TTL_HOURS > 24).
      - На каждом поиске фильтруем по выбранным профессиям.
      - Отдаём прогресс батчами по 5 шт., уважаем cancel_check().
    """
    def __init__(self):
        self.source_name = "Jobicy"
        self.base_url = "https://jobicy.com/api/v2/remote-jobs"
        self.cache_manager = CacheManager(
            cache_duration_hours=int(os.getenv('JOBICY_CACHE_HOURS', os.getenv('CACHE_TTL_HOURS', '24')))
        )
        self.cache_key = "jobicy:all_jobs:v1"
                
        # TTL кеша
        try:
            self.cache_duration_hours = int(os.getenv('JOBICY_CACHE_HOURS', os.getenv('CACHE_TTL_HOURS', '24')))
        except Exception:
            self.cache_duration_hours = 24

    # === ПУБЛИЧНЫЙ ПОИСК ===
    def search_jobs(self, preferences: Dict, progress_callback=None, cancel_check=None) -> List[JobVacancy]:
        """
        Jobicy: берём общий дамп, но фильтруем ТОЛЬКО по выбранным профессиям.
        Профессии и их англ. термы берём из self.specific_jobs_map (если есть).
        """
        selected = preferences.get('selected_jobs') or []
        if not selected:
            return []

        try:
            if cancel_check and cancel_check():
                return []
            all_jobs_raw = self._fetch_jobs_cached()
            filtered = self._filter_relevant_jobs(
                jobs_data=all_jobs_raw,
                preferences=preferences,
                progress_callback=progress_callback,
                cancel_check=cancel_check,
            )
            print(f"✅ {self.source_name}: релевантных вакансий — {len(filtered)}")
            return filtered
        except Exception as e:
            print(f"❌ {self.source_name}: ошибка — {e}")
            return []

        
    def _filter_relevant_jobs(
    self,
    jobs_data: List[Dict[str, Any]],
    preferences: Dict,
    progress_callback=None,
    cancel_check=None
) -> List[JobVacancy]:
        """
        Фильтр релевантности под выбранные профессии:
        • Берём EN-термы из nested self.specific_jobs_map (категория -> {RU: [EN...]}).
        • Если EN-термов не нашли — выходим (Jobicy плохо матчится по RU).
        • Прогресс отдаём порциями по 5 вакансий (списком JobVacancy).
        """
        selected_jobs: List[str] = preferences.get("selected_jobs") or []
        if not selected_jobs:
            return []

        import re
        positive_terms: set[str] = set()
        specific_map: Dict[str, Dict[str, List[str]]] = getattr(self, "specific_jobs_map", {}) or {}

        # собираем англ. ключи для выбранных RU-профессий
        for ru_title in selected_jobs:
            terms = None
            for cat_dict in specific_map.values():
                if isinstance(cat_dict, dict) and ru_title in cat_dict:
                    terms = cat_dict.get(ru_title)
                    break
            if terms:
                for t in terms:
                    t = (t or "").strip()
                    if t and re.match(r'^[A-Za-z0-9 .,+\-]+$', t):
                        positive_terms.add(t.lower())

        if not positive_terms:
            return []

        relevant: List[JobVacancy] = []
        batch: List[JobVacancy] = []

        for raw in jobs_data:
            if cancel_check and cancel_check():
                break

            title = (raw.get("jobTitle") or raw.get("title") or "").strip()
            desc  = (raw.get("jobDescription") or raw.get("description") or "").strip()
            tl, dl = title.lower(), desc.lower()

            if not any(term in tl or term in dl for term in positive_terms):
                continue

            job = self._normalize_job(raw)
            if not job:
                continue

            relevant.append(job)
            batch.append(job)

            if progress_callback and len(batch) >= 5:
                try:
                    progress_callback(list(batch))  # важно: список JobVacancy
                except Exception:
                    pass
                batch.clear()

        if progress_callback and batch:
            try:
                progress_callback(list(batch))
            except Exception:
                pass

        return relevant




    # === КЕШ/АПИ ===
    def _fetch_jobs_cached(self) -> List[Dict]:
        """
        Дамп Jobicy с общим CacheManager.
        Кладём и достаём СЫРОЙ JSON (list[dict]) — флаг raw=True.
        Ключ: jobicy:all_jobs:v1
        """
        # 1) Пробуем из кеша (Redis/файл через CacheManager)
        cached = self.cache_manager.get_cached_result({"key": self.cache_key, "raw": True})
        if isinstance(cached, list):
            print(f"💾 {self.source_name}: Cache HIT, записей {len(cached)}")
            return cached

        # 2) Cache MISS → запрос к API и запись в кеш (не кешируем пустое)
        print(f"🌐 {self.source_name}: Cache MISS — запрашиваем дамп")
        try:
            r = requests.get(self.base_url, timeout=15)
            if r.status_code != 200:
                print(f"❌ {self.source_name}: HTTP {r.status_code}")
                return []
            data = r.json() or {}
            jobs = data.get('jobs') or []

            if jobs:
                self.cache_manager.cache_result({"key": self.cache_key, "raw": True}, jobs)
                print(f"📥 {self.source_name}: получено {len(jobs)}, сохранено в кеш (Redis/File)")
            else:
                print(f"📥 {self.source_name}: получено 0 записей (not cached)")

            return jobs
        except requests.Timeout:
            print(f"⚠️ {self.source_name}: таймаут запроса")
            return []
        except Exception as e:
            print(f"❌ {self.source_name}: ошибка API: {e}")
            return []



    
    # === УТИЛИТЫ ФИЛЬТРА ===
    def _is_it_related(self, job_name: str) -> bool:
        remote_friendly = [
            # IT
            'python', 'программист', 'разработчик', 'веб-разработчик',
            'дата-аналитик', 'системный администратор', 'тестировщик',
            'it', 'технологии',
            # Офисные (часто удалённые)
            'менеджер', 'маркетинг', 'дизайн', 'контент', 'сео',
            'переводчик', 'копирайтер', 'аналитик', 'консультант',
            'hr', 'рекрутер', 'финансы', 'бухгалтер', 'поддержка',
            'продажи', 'координатор', 'ассистент', 'секретарь',
            'журналист', 'редактор', 'smm', 'pr', 'реклама'
        ]
        return any(k in job_name.lower() for k in remote_friendly)

    def _build_keywords(self, it_jobs: List[str]) -> tuple[list[str], list[str]]:
        """
        ВСЕГДА возвращаем пару (include, exclude), даже если пусто.
        """
        include: list[str] = []
        exclude: list[str] = [
            'sales', 'marketing', 'customer service', 'support representative',
            'account executive', 'business development'
        ]
        for name in it_jobs:
            nl = name.lower().strip()
            if nl:
                include.append(nl)
        if not include:
            include = ['developer']
        return include, exclude

    # === НОРМАЛИЗАЦИЯ ===
    def _normalize_job(self, raw_job: Dict) -> Optional[JobVacancy]:
        try:
            job_id = str(raw_job.get('id', '') or '')
            title = raw_job.get('jobTitle', '') or 'No title'
            company = raw_job.get('companyName', '') or 'No company'
            description = raw_job.get('jobExcerpt', '') or ''
            apply_url = raw_job.get('url', '') or ''
            posted_date = raw_job.get('pubDate', '') or 'Unknown'

            return JobVacancy(
                id=f"jobicy_{job_id}",
                title=title,
                company=company,
                location="Remote",
                salary=None,
                description=description,
                apply_url=apply_url,
                source=self.source_name,
                posted_date=posted_date,
                country="Remote",
                job_type="Remote",
                language_requirement="unknown",
                refugee_friendly=False
            )
        except Exception as e:
            print(f"❌ {self.source_name}: ошибка нормализации: {e}")
            return None
