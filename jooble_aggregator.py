#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Jooble Aggregator — официальный API
Документация: https://jooble.org/api/about

Зависимости:
  - python-dotenv (для чтения .env)
  - requests

Ожидания:
  - В проекте уже есть:
      from base_aggregator import BaseJobAggregator
      from adzuna_aggregator import JobVacancy   # общий формат вакансий
  - В .env прописан ключ:
      JOOBLE_API_KEY=...            # обязателен
  - Необязательные настройки:
      JOOBLE_MAX_PAGES=3            # сколько страниц тянуть на одну поисковую фразу
      JOOBLE_TIMEOUT_CONNECT=5      # таймаут соединения (сек)
      JOOBLE_TIMEOUT_READ=15        # таймаут чтения (сек)
      JOOBLE_USER_AGENT=YourSiteJobBot/1.0 (+contact@example.com)
"""

from __future__ import annotations

import os
import time
import random
from datetime import datetime
from typing import Dict, List, Optional

import requests
from dotenv import load_dotenv
from uuid import uuid5, NAMESPACE_URL

from base_aggregator import BaseJobAggregator
from adzuna_aggregator import JobVacancy  # используем общий тип, чтобы не менять остальной код

load_dotenv()


class JoobleAggregator(BaseJobAggregator):
    def __init__(self) -> None:
        super().__init__("Jooble")

        # --- Ключ и параметры ---
        self.api_key: str = os.getenv("JOOBLE_API_KEY", "")
        if not self.api_key:
            raise ValueError(
                "JOOBLE_API_KEY не найден. Получите ключ на https://jooble.org/api/about"
            )

        self.max_pages: int = int(os.getenv("JOOBLE_MAX_PAGES", "3"))
        self.timeout_connect: int = int(os.getenv("JOOBLE_TIMEOUT_CONNECT", "5"))
        self.timeout_read: int = int(os.getenv("JOOBLE_TIMEOUT_READ", "15"))
        self.user_agent: str = os.getenv(
            "JOOBLE_USER_AGENT", "YourSiteJobBot/1.0 (+contact@example.com)"
        )

        # --- HTTP сессия ---
        self.session = requests.Session()
        self.session.headers.update(
            {
                "User-Agent": self.user_agent,
                "Accept": "application/json",
                "Content-Type": "application/json",
            }
        )

        # --- Справочник стран (для косметики/валидации локаций) ---
        self._countries = {
            "de": "Германия",
            "pl": "Польша",
            "gb": "Великобритания",
            "fr": "Франция",
            "it": "Италия",
            "es": "Испания",
            "nl": "Нидерланды",
            "at": "Австрия",
            "be": "Бельгия",
            "ch": "Швейцария",
            "se": "Швеция",
            "no": "Норвегия",
            "dk": "Дания",
            "cz": "Чехия",
            "us": "США",
            "ca": "Канада",
            "au": "Австралия",
        }

        self.endpoint = f"https://jooble.org/api/{self.api_key}"

    # --- Публичные методы ----------------------------------------------------

    def get_supported_countries(self) -> Dict[str, Dict]:
        """Возвращает карту кода страны -> объект с именем (для совместимости с другими агрегаторами)."""
        return {code: {"name": name} for code, name in self._countries.items()}

    def search_jobs(self, preferences: Dict) -> List[JobVacancy]:
        """
        Основной метод поиска.
        preferences ожидает ключи:
          - selected_jobs: list[str]  (поисковые фразы)
          - cities:        list[str]  (приоритетные города)
          - countries:     list[str]  (коды стран; используем как подсказку к локации, если город не задан)
        """
        jobs: List[JobVacancy] = []

        selected_jobs = (preferences.get("selected_jobs") or [])[:3]  # ограничим до 3 фраз
        cities = preferences.get("cities") or []
        countries = preferences.get("countries") or []

        # Локация по умолчанию:
        default_location = ""
        if cities:
            default_location = cities[0]
        elif countries:
            default_location = self._countries.get(countries[0], "")

        for query in selected_jobs:
            if not query:
                continue

            page = 1
            while page <= self.max_pages:
                body = {"keywords": query, "location": default_location, "page": page}
                data = self._safe_post(self.endpoint, json=body)

                items = (data or {}).get("jobs") or []
                if not items:
                    break  # дальше страниц пусто — выходим из пагинации

                for item in items:
                    job = self._to_jobvacancy(item, query, countries)
                    if job and self.is_relevant_job(job.title, job.description, query):
                        jobs.append(job)

                page += 1

        return jobs

    # --- Внутренние утилиты --------------------------------------------------

    def _safe_post(self, url: str, *, json: dict) -> Optional[dict]:
        """
        POST с ретраями на 429/5xx. Возвращает json-словарь или None.
        """
        for attempt in range(3):
            try:
                resp = self.session.post(
                    url, json=json, timeout=(self.timeout_connect, self.timeout_read)
                )
                # Повторяем при «транзитных» кодах
                if resp.status_code in (429, 500, 502, 503, 504):
                    sleep_s = (2**attempt) + random.uniform(0, 0.5)
                    time.sleep(sleep_s)
                    continue

                resp.raise_for_status()
                return resp.json()
            except requests.RequestException as e:
                # на последней попытке просто логируем (print — для совместимости)
                if attempt == 2:
                    print(f"⚠️ Jooble API error: {e}")
                else:
                    time.sleep(0.5)
        return None

    def _stable_id(self, link: str) -> str:
        """Стабильный ID на основе URL, чтобы дедуп работал при рестартах."""
        if not link:
            # fallback, но лучше всегда иметь ссылку
            return f"jooble_{uuid5(NAMESPACE_URL, str(datetime.utcnow().timestamp()))}"
        return f"jooble_{uuid5(NAMESPACE_URL, link)}"

    def _to_jobvacancy(
        self, d: Dict, search_term: str, countries: List[str]
    ) -> Optional[JobVacancy]:
        """
        Маппинг Jooble -> общий JobVacancy.
        Поля Jooble: title, company, location, salary, snippet, link, updated, type
        """
        link = (d.get("link") or "").strip()
        title = (d.get("title") or "").strip()
        company = (d.get("company") or "Unknown").strip()
        location = (d.get("location") or "").strip()
        salary = d.get("salary") or None
        snippet = d.get("snippet") or ""
        job_type = d.get("type") or None
        posted = d.get("updated") or datetime.utcnow().strftime("%Y-%m-%d")

        # Если страна не указана в preferences — оставим пусто, front может отобразить из location
        country_name = countries[0] if countries else ""

        return JobVacancy(
            id=self._stable_id(link),
            title=title,
            company=company,
            location=location,
            salary=salary,
            description=snippet,
            apply_url=link,
            source="Jooble",
            posted_date=posted,
            country=country_name,
            job_type=job_type,
            language_requirement=self.determine_language_requirement(title, snippet),
            refugee_friendly=self.is_refugee_friendly(title, snippet, search_term),
        )

    def is_relevant_job(self, job_title: str, job_description: str, search_term: str) -> bool:
        """Простая фильтрация релевантности по включению слов запроса в заголовок."""
        q_words = (search_term or "").lower().split()
        title_lower = (job_title or "").lower()
        return any(w for w in q_words if w and w in title_lower)
