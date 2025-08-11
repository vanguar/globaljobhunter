#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Jooble Aggregator — официальный API
Документация: https://jooble.org/api/about

Фишки:
- Авто-расширение запросов на языки страны (fallback, если фронт не дал selected_jobs_multilang)
- Пагинация и ретраи на 429/5xx
- Жёсткий пост‑фильтр по стране (в location должны быть алиасы выбранной страны)
- Устойчивый парсинг даты

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
from datetime import datetime
from typing import Dict, List, Optional
from uuid import uuid5, NAMESPACE_URL

import requests
from dotenv import load_dotenv

from base_aggregator import BaseJobAggregator
from adzuna_aggregator import JobVacancy  # общий тип

load_dotenv()


class JoobleAggregator(BaseJobAggregator):
    # Отображаемые имена стран (для UI/мета)
    COUNTRIES_MAP: Dict[str, str] = {
        "de": "Германия", "pl": "Польша", "gb": "Великобритания", "fr": "Франция",
        "it": "Италия", "es": "Испания", "nl": "Нидерланды", "at": "Австрия",
        "be": "Бельгия", "ch": "Швейцария", "se": "Швеция", "no": "Норвегия",
        "dk": "Дания", "cz": "Чехия", "us": "США", "ca": "Канада", "au": "Австралия"
    }

    # Английские названия стран (для location и матчинга)
    COUNTRY_NAME_EN: Dict[str, str] = {
        "de": "Germany", "pl": "Poland", "gb": "United Kingdom", "fr": "France",
        "it": "Italy", "es": "Spain", "nl": "Netherlands", "at": "Austria",
        "be": "Belgium", "ch": "Switzerland", "se": "Sweden", "no": "Norway",
        "dk": "Denmark", "cz": "Czechia", "us": "United States", "ca": "Canada", "au": "Australia"
    }

        # Города по умолчанию для поиска, когда пользователь город не указал
    DEFAULT_CITIES: Dict[str, List[str]] = {
        "de": ["Berlin", "München", "Hamburg", "Köln", "Frankfurt am Main", "Stuttgart"],
        "pl": ["Warszawa", "Kraków", "Wrocław", "Gdańsk", "Poznań", "Łódź"],
        "fr": ["Paris", "Lyon", "Marseille", "Toulouse", "Bordeaux", "Lille"],
        "it": ["Roma", "Milano", "Torino", "Napoli", "Bologna", "Firenze"],
        "es": ["Madrid", "Barcelona", "Valencia", "Sevilla", "Zaragoza", "Málaga"],
        "nl": ["Amsterdam", "Rotterdam", "Den Haag", "Utrecht", "Eindhoven", "Tilburg"],
        "at": ["Wien", "Graz", "Linz", "Salzburg", "Innsbruck", "Klagenfurt"],
        "be": ["Bruxelles", "Antwerpen", "Gent", "Liège", "Brugge", "Namur"],
        "ch": ["Zürich", "Genève", "Basel", "Bern", "Lausanne", "Luzern"],
        "cz": ["Praha", "Brno", "Ostrava", "Plzeň", "Olomouc", "Liberec"],
        "se": ["Stockholm", "Göteborg", "Malmö", "Uppsala", "Västerås", "Örebro"],
        "dk": ["København", "Aarhus", "Odense", "Aalborg", "Esbjerg", "Randers"],
        "no": ["Oslo", "Bergen", "Trondheim", "Stavanger", "Drammen", "Kristiansand"],
        "gb": ["London", "Manchester", "Birmingham", "Leeds", "Glasgow", "Bristol"],
        "us": ["New York", "Los Angeles", "Chicago", "Houston", "San Francisco", "Boston"],
        "ca": ["Toronto", "Vancouver", "Montréal", "Calgary", "Ottawa", "Edmonton"],
        "au": ["Sydney", "Melbourne", "Brisbane", "Perth", "Adelaide", "Canberra"],
    }


    # Языки по умолчанию для стран (fallback, если фронт не пришлёт)
    COUNTRY_LANGS_FALLBACK: Dict[str, List[str]] = {
        "de": ["de", "en"], "pl": ["pl", "en"], "cz": ["cs", "en"], "sk": ["sk", "cs", "en"],
        "it": ["it", "en"], "es": ["es", "en"], "pt": ["pt", "en"], "nl": ["nl", "en"],
        "ro": ["ro", "en"], "bg": ["bg", "en"], "hu": ["hu", "en"], "si": ["sl", "en"],
        "hr": ["hr", "en"], "lt": ["lt", "en"], "lv": ["lv", "en"], "ee": ["et", "en"],
        "el": ["el", "en"], "fi": ["fi", "en"], "se": ["sv", "en"], "dk": ["da", "en"],
        "be": ["nl", "fr", "en"], "ie": ["en", "ga"], "mt": ["en"], "at": ["de", "en"], "lu": ["fr", "de", "en"]
    }

    # Частые многоязычные синонимы: ключи — ЛЮБОЙ из вариантов (ru/en/de/…),
    # значения — расширенный список запросов, который отправим в Jooble
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

    # Алиасы стран для жёсткого пост‑фильтра location
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
        # нужно до super().__init__ чтобы базовый ctor мог обратиться
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

    # ---------------- Публичные методы ----------------

    def get_supported_countries(self) -> Dict[str, Dict]:
        """Совместимость с остальными агрегаторами: код -> объект с name."""
        return {code: {"name": name} for code, name in self._countries.items()}

    def search_jobs(self, preferences: Dict) -> List[JobVacancy]:
        jobs: List[JobVacancy] = []

        # 1) Языковые варианты (мультиязычие)
        selected_jobs: List[str] = self._expand_queries(preferences)

        # 2) География
        cities = preferences.get("cities") or []
        countries = preferences.get("countries") or []
        country_code = (countries[0] if countries else "").lower()

        # Список локаций для перебора:
        #   - если пользователь указал город(а) — берём их (ограничим до 3)
        #   - иначе берём дефолтные города для страны (ограничим до 6)
        if cities:
            locations: List[str] = [c for c in cities if c and c.strip()][:3]
        else:
            locations = list(self.DEFAULT_CITIES.get(country_code, []))[:6]

        # Если вообще нет локаций (неизвестная страна) — не задаём location (но тогда меньше шансов на попадания).
        if not locations:
            locations = [""]

        print(f"Jooble: terms={selected_jobs[:self.max_terms]} | locations={locations} | country={country_code!r}")

        # 3) Поисковые запросы: перебор по городам и пагинация
        for loc in locations:
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
                        # Жёсткий пост‑фильтр по стране (отсечёт «Киев/Китай»)
                        if country_code and not self._passes_country_filter(item, country_code):
                            continue

                        job = self._to_jobvacancy(item, query, countries)
                        if job and self.is_relevant_job(job.title, job.description, query):
                            jobs.append(job)

                    page += 1

        return jobs

    # ---------------- Внутренние утилиты ----------------

    def _expand_queries(self, preferences: Dict) -> List[str]:
        """
        Итоговый список поисковых фраз с учетом мультиязычности.
        Приоритет:
          1) selected_jobs_multilang (из фронта)
          2) language_variants (сервером прокинутый словарь term -> [варианты])
          3) server-side fallback: добавляем встроенные синонимы (если знаем термин)
          4) просто базовые selected_jobs
        """
        # 1) фронт собрал варианты
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

        # 3) fallback — подключаем встроенные синонимы (если знаем термин)
        expanded: List[str] = []
        for term in base:
            t = term.strip()
            if not t:
                continue
            expanded.append(t)

            key = t.lower()
            if key in self.BUILTIN_VARIANTS:
                expanded.extend(self.BUILTIN_VARIANTS[key])

        # нормализуем и ограничим количество
        uniq = list(dict.fromkeys([s for s in (w.strip() for w in expanded) if s]))
        return uniq

    def _passes_country_filter(self, item: Dict, country_code: str) -> bool:
        """
        True только если в location явно встречается выбранная страна (по алиасам).
        Если location пуст/мутный — считаем НЕ прошёл (лучше отсечь мусор).
        """
        loc = (item.get("location") or "").strip().lower()
        if not loc:
            return False

        # нормализация некоторых символов
        loc = (loc
               .replace("ö", "o")
               .replace("ä", "a")
               .replace("ü", "u")
               .replace("ß", "ss"))

        # прямая проверка по алиасам
        for token in self.COUNTRY_ALIASES.get(country_code, []):
            if token in loc:
                return True

        # иногда страна идёт после запятой/в скобках
        parts = [p.strip() for p in loc.replace("(", ",").replace(")", ",").split(",")]
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
        for candidate in candidates:
            for fmt in fmts:
                try:
                    return datetime.strptime(candidate, fmt).strftime("%Y-%m-%d")
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
