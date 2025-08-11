#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Jooble Aggregator — официальный API
Документация: https://jooble.org/api/about

Фишки:
- Авто-расширение запросов на языки/синонимы (fallback, если фронт не дал selected_jobs_multilang)
- Перебор по городам (из формы или дефолтные по стране), чтобы Jooble не искал «везде»
- Ретраи на 429/5xx, устойчивый парс дат
- Жёсткий пост‑фильтр по стране (отсечёт «Киев/Китай», если выбрана Германия)

ENV:
  JOOBLE_API_KEY=...
  JOOBLE_MAX_PAGES=3
  JOOBLE_TIMEOUT_CONNECT=5
  JOOBLE_TIMEOUT_READ=15
  JOOBLE_USER_AGENT=YourSiteBot/1.0 (+contact@example.com)
  JOOBLE_MAX_TERMS=6
"""

from __future__ import annotations

import os
import time
import random
import unicodedata
from datetime import datetime
from typing import Dict, List, Optional
from uuid import uuid5, NAMESPACE_URL

import requests
from dotenv import load_dotenv

from base_aggregator import BaseJobAggregator
from adzuna_aggregator import JobVacancy  # единый тип вакансии

load_dotenv()


class JoobleAggregator(BaseJobAggregator):
    # Отображаемые имена стран (для UI/метаданных)
    COUNTRIES_MAP: Dict[str, str] = {
        "de": "Германия", "pl": "Польша", "gb": "Великобритания", "fr": "Франция",
        "it": "Италия", "es": "Испания", "nl": "Нидерланды", "at": "Австрия",
        "be": "Бельгия", "ch": "Швейцария", "se": "Швеция", "no": "Норвегия",
        "dk": "Дания", "cz": "Чехия", "us": "США", "ca": "Канада", "au": "Австралия"
    }

    # Английские названия стран (для подстановки в location при отсутствии города)
    COUNTRY_NAME_EN: Dict[str, str] = {
        "de": "Germany", "pl": "Poland", "gb": "United Kingdom", "fr": "France",
        "it": "Italy", "es": "Spain", "nl": "Netherlands", "at": "Austria",
        "be": "Belgium", "ch": "Switzerland", "se": "Sweden", "no": "Norway",
        "dk": "Denmark", "cz": "Czechia", "us": "United States", "ca": "Canada", "au": "Australia"
    }

    # Дефолтные города: используем, если пользователь город не указал
    DEFAULT_CITIES: Dict[str, List[str]] = {
        "de": ["Berlin", "Munich", "Hamburg", "Cologne", "Frankfurt", "Stuttgart"],
        "pl": ["Warsaw", "Krakow", "Wroclaw", "Gdansk", "Poznan", "Lodz"],
        "fr": ["Paris", "Lyon", "Marseille", "Toulouse", "Bordeaux", "Lille"],
        "it": ["Rome", "Milan", "Turin", "Naples", "Bologna", "Florence"],
        "es": ["Madrid", "Barcelona", "Valencia", "Seville", "Zaragoza", "Malaga"],
        "nl": ["Amsterdam", "Rotterdam", "The Hague", "Utrecht", "Eindhoven", "Tilburg"],
        "at": ["Vienna", "Graz", "Linz", "Salzburg", "Innsbruck", "Klagenfurt"],
        "be": ["Brussels", "Antwerp", "Ghent", "Liege", "Bruges", "Namur"],
        "ch": ["Zurich", "Geneva", "Basel", "Bern", "Lausanne", "Lucerne"],
        "cz": ["Prague", "Brno", "Ostrava", "Pilsen", "Olomouc", "Liberec"],
        "se": ["Stockholm", "Gothenburg", "Malmo", "Uppsala", "Vasteras", "Orebro"],
        "dk": ["Copenhagen", "Aarhus", "Odense", "Aalborg", "Esbjerg", "Randers"],
        "no": ["Oslo", "Bergen", "Trondheim", "Stavanger", "Drammen", "Kristiansand"],
        "gb": ["London", "Manchester", "Birmingham", "Leeds", "Glasgow", "Bristol"],
        "us": ["New York", "Los Angeles", "Chicago", "Houston", "San Francisco", "Boston"],
        "ca": ["Toronto", "Vancouver", "Montreal", "Calgary", "Ottawa", "Edmonton"],
        "au": ["Sydney", "Melbourne", "Brisbane", "Perth", "Adelaide", "Canberra"],
    }

    # Языки по умолчанию для стран (fallback, если фронт не пришлёт multilang)
    COUNTRY_LANGS_FALLBACK: Dict[str, List[str]] = {
        "de": ["de", "en"], "pl": ["pl", "en"], "cz": ["cs", "en"], "sk": ["sk", "cs", "en"],
        "it": ["it", "en"], "es": ["es", "en"], "pt": ["pt", "en"], "nl": ["nl", "en"],
        "ro": ["ro", "en"], "bg": ["bg", "en"], "hu": ["hu", "en"], "si": ["sl", "en"],
        "hr": ["hr", "en"], "lt": ["lt", "en"], "lv": ["lv", "en"], "ee": ["et", "en"],
        "el": ["el", "en"], "fi": ["fi", "en"], "se": ["sv", "en"], "dk": ["da", "en"],
        "be": ["nl", "fr", "en"], "ie": ["en", "ga"], "mt": ["en"], "at": ["de", "en"], "lu": ["fr", "de", "en"]
    }

    # Частые многоязычные синонимы (ключ можно дать на любом языке — ru/en/de/…)
    BUILTIN_VARIANTS: Dict[str, List[str]] = {
        # Ресторан / сервис
        "официант": ["waiter", "waitress", "server", "kellner", "kellnerin", "bedienung",
                     "serveur", "serveuse", "camarero", "cameriere", "ober", "kelner"],
        "waiter":   ["waiter", "waitress", "server", "kellner", "kellnerin", "bedienung",
                     "serveur", "serveuse", "camarero", "cameriere", "ober", "kelner"],
        "повар":    ["cook", "chef", "kitchen chef", "koch", "küchenchef", "cuisinier",
                     "cocinero", "cuoco", "kok", "kucharz"],
        "кассир":   ["cashier", "till operator", "checkout operator",
                     "kassierer", "caissier", "cajero", "cassiere", "kassamedewerker", "kasjer"],
        "уборщик":  ["cleaner", "janitor", "cleaning operative",
                     "reinigungskraft", "agent entretien", "limpiador", "addetto pulizie",
                     "schoonmaker", "sprzątacz"],

        # Транспорт / логистика
        "таксист":  ["taxi driver", "cab driver", "uber driver", "taxifahrer", "tassista",
                     "chauffeur de taxi", "taxista", "taxichauffeur", "taksówkarz"],
        "taxi driver": ["taxi driver", "cab driver", "uber driver", "taxifahrer", "tassista",
                        "chauffeur de taxi", "taxista", "taxichauffeur", "taksówkarz"],
        "водитель c": ["truck driver", "hgv driver", "lorry driver", "lkw fahrer",
                       "conducteur poids lourd", "camionero", "camionista", "vrachtwagenchauffeur",
                       "kierowca ciężarówki"],
        "курьер":   ["delivery driver", "courier driver", "van driver",
                     "lieferfahrer", "chauffeur-livreur", "repartidor", "autista consegne",
                     "bezorgchauffeur", "kierowca dostawca"],

        # Строительство / склад
        "грузчик":  ["warehouse worker", "loader", "packer", "magazijnmedewerker",
                     "lagerarbeiter", "manutentionnaire", "mozo", "magazziniere", "magazynier"],
        "складской работник": ["warehouse operative", "stock handler", "logistics worker",
                               "lagermitarbeiter", "agent logistique", "operario almacén",
                               "operatore magazzino", "logistiek medewerker"],
        "разнорабочий": ["general worker", "manual worker", "helper",
                         "hilfsarbeiter", "ouvrier polyvalent", "peón general",
                         "operaio generico", "algemeen medewerker", "pracownik fizyczny"],
    }

    # Алиасы стран для жёсткого пост‑фильтра (смотрим в location)
    COUNTRY_ALIASES: Dict[str, List[str]] = {
        "de": ["germany", "deutschland"],
        "pl": ["poland", "polska"],
        "gb": ["united kingdom", "uk", "great britain", "britain", "england", "scotland", "wales", "northern ireland"],
        "fr": ["france", "frankreich"],
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
        "au": ["australia"],
    }

    def __init__(self) -> None:
        # нужно до super().__init__, базовый ctor читает список стран
        self._countries: Dict[str, str] = dict(self.COUNTRIES_MAP)

        # --- Ключ и параметры ---
        self.api_key: str = os.getenv("JOOBLE_API_KEY", "")
        if not self.api_key:
            raise ValueError("JOOBLE_API_KEY не найден. Получите ключ на https://jooble.org/api/about")

        self.max_pages: int = int(os.getenv("JOOBLE_MAX_PAGES", "3"))
        self.timeout_connect: int = int(os.getenv("JOOBLE_TIMEOUT_CONNECT", "5"))
        self.timeout_read: int = int(os.getenv("JOOBLE_TIMEOUT_READ", "15"))
        self.user_agent: str = os.getenv("JOOBLE_USER_AGENT", "YourSiteBot/1.0 (+contact@example.com)")
        self.max_terms: int = int(os.getenv("JOOBLE_MAX_TERMS", "6"))

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
        jobs: List[JobVacancy] = []

        # 1) Мультиязычные термины
        selected_jobs: List[str] = self._expand_queries(preferences)

        # 2) География (города/страна)
        cities = preferences.get("cities") or []
        countries = preferences.get("countries") or []
        country_code = (countries[0] if countries else "").lower()

        # Список локаций для перебора.
        # Если пользователь дал города — берём их (макс 3), иначе дефолтные по стране (макс 6).
        if cities:
            locations: List[str] = [c for c in cities if c and c.strip()][:3]
        else:
            locations = list(self.DEFAULT_CITIES.get(country_code, []))[:6]

        # Если вообще нет локаций — как последний шанс подставляем англ. имя страны (лучше, чем пусто).
        if not locations:
            fallback_country = self.COUNTRY_NAME_EN.get(country_code, "")
            locations = [fallback_country] if fallback_country else [""]

        print(f"Jooble: terms={selected_jobs[:self.max_terms]} | locations={locations} | country='{country_code}'")

        # 3) Поисковые запросы: по каждой локации и с пагинацией
        for loc in locations:
            loc = loc.strip()
            for query in selected_jobs[: self.max_terms]:
                if not query:
                    continue

                page = 1
                while page <= self.max_pages:
                    body = {"keywords": query, "location": loc, "page": page}
                    data = self._safe_post(self.endpoint, json=body)

                    items = (data or {}).get("jobs") or []
                    print(f"Jooble: loc='{loc}' q='{query}' page={page} -> {len(items)} items")

                    if not items:
                        break

                    for item in items:
                        # Жёсткий пост‑фильтр по стране (отсечёт «левые» регионы)
                        if country_code and not self._passes_country_filter(item, country_code):
                            continue

                        job = self._to_jobvacancy(item, query, countries)
                        if job and self.is_relevant_job(job.title, job.description, query):
                            jobs.append(job)

                    page += 1

        return jobs

    # ---------- Внутренние утилиты ----------

    def _expand_queries(self, preferences: Dict) -> List[str]:
        """
        Итоговый список поисковых фраз с учетом мультиязычия.
        Приоритет:
          1) selected_jobs_multilang (из фронта)
          2) language_variants (серверный словарь: term -> [варианты])
          3) fallback: встроенные синонимы (если термин распознали)
          4) просто базовые selected_jobs
        """
        # 1) фронт отдал уже расширенный набор
        if preferences.get("selected_jobs_multilang"):
            uniq = list(dict.fromkeys([s.strip() for s in preferences["selected_jobs_multilang"] if s and s.strip()]))
            return uniq

        # 2) серверные варианты
        base: List[str] = [s.strip() for s in (preferences.get("selected_jobs") or []) if s and s.strip()]
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

        # 3) fallback — добавим встроенные синонимы, если знаем термин
        expanded: List[str] = []
        for term in base:
            t = term.strip()
            if not t:
                continue
            expanded.append(t)
            key = t.lower()
            if key in self.BUILTIN_VARIANTS:
                expanded.extend(self.BUILTIN_VARIANTS[key])

        # нормализуем и вернём
        uniq = list(dict.fromkeys([s for s in (w.strip() for w in expanded) if s]))
        return uniq

    def _passes_country_filter(self, item: Dict, country_code: str) -> bool:
        """
        True только если в location явный индикатор выбранной страны (по алиасам).
        Пустой location считаем НЕ прошёл (лучше отрезать мусор).
        """
        loc = (item.get("location") or "").strip()
        if not loc:
            return False

        # Нормализуем: приводим к ASCII‑приближению и нижнему регистру
        loc_norm = unicodedata.normalize("NFKD", loc).encode("ascii", "ignore").decode("ascii").lower()

        for token in self.COUNTRY_ALIASES.get(country_code, []):
            if token in loc_norm:
                return True

        # Иногда страна после запятой/в скобках
        parts = [p.strip() for p in loc_norm.replace("(", ",").replace(")", ",").split(",")]
        for p in reversed(parts):
            for token in self.COUNTRY_ALIASES.get(country_code, []):
                if token in p:
                    return True

        return False

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
            currency = (salary_data.get("currency") or "").strip()
            if min_sal and max_sal:
                return f"{min_sal}–{max_sal} {currency}".strip()
            if min_sal:
                return f"от {min_sal} {currency}".strip()
            if max_sal:
                return f"до {max_sal} {currency}".strip()
        elif isinstance(salary_data, (int, float, str)):
            return str(salary_data)
        return None

    @staticmethod
    def _parse_date_safe(value: str) -> str:
        """Устойчивый парсинг даты Jooble."""
        if not value:
            return datetime.utcnow().strftime("%Y-%m-%d")
        candidates = [value, value.split("T")[0], value.replace("/", "-")]
        fmts = ["%Y-%m-%d", "%Y/%m/%d", "%Y-%m-%d %H:%M:%S", "%d-%m-%Y", "%d/%m/%Y"]
        for c in candidates:
            for fmt in fmts:
                try:
                    return datetime.strptime(c, fmt).strftime("%Y-%m-%d")
                except Exception:
                    pass
        return datetime.utcnow().strftime("%Y-%m-%d")

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
        posted = self._parse_date_safe(posted_raw)

        country_name = ""
        if countries:
            code = (countries[0] or "").lower()
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
        """Фильтрация релевантности по заголовку/описанию."""
        q_words = (search_term or "").lower().split()
        t = (job_title or "").lower()
        d = (job_description or "").lower()
        return any(w for w in q_words if w and (w in t or w in d))
