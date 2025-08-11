#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Jooble Aggregator — официальный API
Документация: https://jooble.org/api/about

Зависимости:
  - requests
  - python-dotenv

Ожидания:
  - В проекте уже есть:
      from base_aggregator import BaseJobAggregator
      from adzuna_aggregator import JobVacancy   # общий формат вакансий
  - В .env прописан ключ:
      JOOBLE_API_KEY=...                  # обязателен
  - Необязательные настройки:
      JOOBLE_MAX_PAGES=3                  # страниц на одну поисковую фразу
      JOOBLE_TIMEOUT_CONNECT=5            # таймаут соединения (сек)
      JOOBLE_TIMEOUT_READ=15              # таймаут чтения (сек)
      JOOBLE_USER_AGENT=YourSiteBot/1.0 (+contact@example.com)
      JOOBLE_MAX_TERMS=5                  # макс. число поисковых фраз после расширений
      JOOBLE_STRICT_COUNTRY=1             # строгая фильтрация по стране (1|0)
"""

from __future__ import annotations

import os
import time
import random
from datetime import datetime
from typing import Dict, List, Optional
from uuid import uuid5, NAMESPACE_URL

import requests
from dotenv import load_dotenv

from base_aggregator import BaseJobAggregator
from adzuna_aggregator import JobVacancy  # общий тип

load_dotenv()


class JoobleAggregator(BaseJobAggregator):
    # Публичная карта (код -> русское имя) — используется фронтом/метаданными
    COUNTRIES_MAP: Dict[str, str] = {
        "de": "Германия", "pl": "Польша", "gb": "Великобритания", "fr": "Франция",
        "it": "Италия", "es": "Испания", "nl": "Нидерланды", "at": "Австрия",
        "be": "Бельгия", "ch": "Швейцария", "se": "Швеция", "no": "Норвегия",
        "dk": "Дания", "cz": "Чехия", "us": "США", "ca": "Канада", "au": "Австралия"
    }

    # Английские имена стран — именно их безопасно слать в Jooble в поле "location", когда города нет
    COUNTRY_EN: Dict[str, str] = {
        "de": "Germany", "pl": "Poland", "gb": "United Kingdom", "fr": "France",
        "it": "Italy", "es": "Spain", "nl": "Netherlands", "at": "Austria",
        "be": "Belgium", "ch": "Switzerland", "se": "Sweden", "no": "Norway",
        "dk": "Denmark", "cz": "Czech Republic", "us": "United States",
        "ca": "Canada", "au": "Australia"
    }

    # Алиасы/синонимы названий стран для матчинга по location (минимально достаточный набор)
    COUNTRY_ALIASES: Dict[str, List[str]] = {
        "de": ["germany", "deutschland", "alemania", "allemagne", "germania"],
        "pl": ["poland", "polska", "polonie"],
        "gb": ["united kingdom", "uk", "england", "scotland", "wales", "northern ireland", "great britain", "britain"],
        "fr": ["france", "francia", "frankreich"],
        "it": ["italy", "italia"],
        "es": ["spain", "españa"],
        "nl": ["netherlands", "holland", "nederland"],
        "at": ["austria", "österreich", "osterreich"],
        "be": ["belgium", "belgique", "belgië", "belgie"],
        "ch": ["switzerland", "schweiz", "suisse", "svizzera"],
        "se": ["sweden", "sverige"],
        "no": ["norway", "norge"],
        "dk": ["denmark", "danmark"],
        "cz": ["czech republic", "czechia", "česko", "cesko"],
        "us": ["united states", "usa", "u.s.a.", "us"],
        "ca": ["canada"],
        "au": ["australia"]
    }

    # Fallback: если фронт не прислал selected_jobs_multilang/language_variants, на стороне бэка не
    # «переводим» термины (переводы у тебя уже собраны на фронте — categories.js).
    # Здесь только собираем фразы и фильтруем результаты.

    def __init__(self) -> None:
        # Поля, к которым может обратиться базовый ctor
        self._countries: Dict[str, str] = dict(self.COUNTRIES_MAP)

        # --- Ключ и параметры ---
        self.api_key: str = os.getenv("JOOBLE_API_KEY", "")
        if not self.api_key:
            raise ValueError("JOOBLE_API_KEY не найден. Получите ключ на https://jooble.org/api/about")

        self.max_pages: int = int(os.getenv("JOOBLE_MAX_PAGES", "3"))
        self.timeout_connect: int = int(os.getenv("JOOBLE_TIMEOUT_CONNECT", "5"))
        self.timeout_read: int = int(os.getenv("JOOBLE_TIMEOUT_READ", "15"))
        self.user_agent: str = os.getenv("JOOBLE_USER_AGENT", "YourSiteBot/1.0 (+contact@example.com)")
        self.max_terms: int = int(os.getenv("JOOBLE_MAX_TERMS", "5"))
        self.strict_country: bool = os.getenv("JOOBLE_STRICT_COUNTRY", "1") not in ("0", "false", "False")

        # --- HTTP сессия ---
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": self.user_agent,
            "Accept": "application/json",
            "Content-Type": "application/json",
        })

        self.endpoint = f"https://jooble.org/api/{self.api_key}"

        super().__init__("Jooble")

    # ---------- Публичные методы ----------

    def get_supported_countries(self) -> Dict[str, Dict]:
        """Совместимость с остальными агрегаторами: код -> объект с name."""
        return {code: {"name": name} for code, name in self._countries.items()}

    def search_jobs(self, preferences: Dict) -> List[JobVacancy]:
        """
        preferences:
          - selected_jobs: list[str]
          - selected_jobs_multilang: list[str]
          - language_variants: dict[str, list[str]]
          - cities: list[str]
          - countries: list[str] (коды стран)
        """
        jobs: List[JobVacancy] = []

        # 1) Сбор поисковых фраз (мультиязычность — с фронта/из словаря)
        selected_jobs: List[str] = self._expand_queries(preferences)

        # 2) География
        cities = preferences.get("cities") or []
        countries = preferences.get("countries") or []

        # В запрос в Jooble кладём:
        #  - если есть город — его;
        #  - иначе английское имя страны (если выбрана страна);
        default_location = ""
        if cities:
            default_location = (cities[0] or "").strip()
        elif countries:
            default_location = self.COUNTRY_EN.get(countries[0], "").strip()

        # Лог для отладки
        print(f"Jooble: terms={selected_jobs[:self.max_terms]} | location={default_location!r} | strict_country={self.strict_country}")

        # 3) Поиск с пагинацией
        for query in selected_jobs[: self.max_terms]:
            if not query:
                continue

            page = 1
            while page <= self.max_pages:
                body = {"keywords": query, "location": default_location, "page": page}
                data = self._safe_post(self.endpoint, json=body)

                items = (data or {}).get("jobs") or []
                if not items:
                    break

                for item in items:
                    # Строгая фильтрация по стране (по location и алиасам)
                    if self.strict_country and not self._passes_country_filter(item, countries):
                        continue

                    job = self._to_jobvacancy(item, query, countries)
                    if job and self.is_relevant_job(job.title, job.description, query):
                        jobs.append(job)

                page += 1

        return jobs

    # ---------- Внутренние утилиты ----------

    def _expand_queries(self, preferences: Dict) -> List[str]:
        """
        Формирует список поисковых фраз.
        Приоритет:
          1) selected_jobs_multilang (фронт уже дал готовые варианты на языках страны — ИХ и используем)
          2) language_variants (серверный словарь: term -> [варианты])
          3) selected_jobs как есть
        """
        # (1) фронт собрал варианты — используем их
        if preferences.get("selected_jobs_multilang"):
            uniq = list(dict.fromkeys([s.strip() for s in preferences["selected_jobs_multilang"] if s and s.strip()]))
            return uniq

        # (2) базовые термины
        base: List[str] = [s.strip() for s in (preferences.get("selected_jobs") or []) if s and s.strip()]

        # (2.1) серверные варианты (если есть)
        lang_variants: Dict[str, List[str]] = preferences.get("language_variants") or {}
        if lang_variants:
            expanded: List[str] = []
            for term in base:
                expanded.append(term)
                variants = lang_variants.get(term) or lang_variants.get(term.lower()) or []
                for v in variants:
                    v = (v or "").strip()
                    if v:
                        expanded.append(v)
            return list(dict.fromkeys(expanded))

        # (3) просто базовые
        return base

    def _safe_post(self, url: str, *, json: dict) -> Optional[dict]:
        """POST с ретраями на 429/5xx."""
        for attempt in range(3):
            try:
                resp = self.session.post(url, json=json, timeout=(self.timeout_connect, self.timeout_read))
                if resp.status_code in (429, 500, 502, 503, 504):
                    time.sleep((2 ** attempt) + random.uniform(0, 0.5))
                    continue
                resp.raise_for_status()
                return resp.json()
            except requests.RequestException as e:
                if attempt == 2:
                    print(f"⚠️ Jooble API error: {e}")
                else:
                    time.sleep(0.5)
        return None

    def _stable_id(self, link: str) -> str:
        """Стабильный ID на основе URL, чтобы дедуп работал при рестартах."""
        if not link:
            return f"jooble_{uuid5(NAMESPACE_URL, str(datetime.utcnow().timestamp()))}"
        return f"jooble_{uuid5(NAMESPACE_URL, link)}"

    def _format_salary(self, salary_data) -> Optional[str]:
        """Приводим зарплату к читаемой строке."""
        if isinstance(salary_data, dict):
            min_sal = salary_data.get("min")
            max_sal = salary_data.get("max")
            currency = salary_data.get("currency", "")
            if min_sal and max_sal:
                return f"{min_sal}–{max_sal} {currency}".strip()
            if min_sal:
                return f"от {min_sal} {currency}".strip()
            if max_sal:
                return f"до {max_sal} {currency}".strip()
        elif isinstance(salary_data, (int, float, str)):
            return str(salary_data)
        return None

    def _passes_country_filter(self, item: Dict, countries: List[str]) -> bool:
        """
        Возвращает True, если вакансия из нужной страны.
        Проверяем по 'location' и алиасам страны. Если страна не выбрана — пропускаем.
        """
        if not countries:
            return True

        country_code = countries[0]
        aliases = self.COUNTRY_ALIASES.get(country_code, [])
        location = (item.get("location") or "").strip().lower()

        if not location:
            # Если локация пустая — безопаснее отбраковать
            return False

        # Простая эвристика: наличие любого алиаса в строке локации
        for token in aliases:
            if token in location:
                return True

        # Допуск: иногда Jooble кладёт сам код страны в конце/скобках (редко)
        if country_code in location.split():
            return True

        return False

    def _to_jobvacancy(self, d: Dict, search_term: str, countries: List[str]) -> Optional[JobVacancy]:
        """Маппинг Jooble -> JobVacancy."""
        link = (d.get("link") or "").strip()
        title = (d.get("title") or "").strip()
        company = (d.get("company") or "Unknown").strip()
        location = (d.get("location") or "").strip()
        salary = self._format_salary(d.get("salary"))
        snippet = d.get("snippet") or ""
        job_type = d.get("type") or None

        posted_raw = d.get("updated") or datetime.utcnow().strftime("%Y-%m-%d")
        try:
            posted = datetime.fromisoformat(posted_raw.split("T")[0]).strftime("%Y-%m-%d")
        except Exception:
            posted = datetime.utcnow().strftime("%Y-%m-%d")

        country_name = ""
        if countries:
            code = countries[0]
            country_name = self._countries.get(code, code)

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
            language_requirement=self.determine_language_requirement(title or "", snippet or ""),
            refugee_friendly=self.is_refugee_friendly(title or "", snippet or "", search_term or ""),
        )

    def is_relevant_job(self, job_title: str, job_description: str, search_term: str) -> bool:
        """Фильтрация релевантности: слова запроса должны встречаться в заголовке."""
        q_words = (search_term or "").lower().split()
        title_lower = (job_title or "").lower()
        return any(w for w in q_words if w and w in title_lower)
