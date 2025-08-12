#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Jooble Aggregator — ПОЛНОСТЬЮ ИСПРАВЛЕННАЯ ВЕРСИЯ

Что исправлено (строго то, о чём договорились):
1) Форматы локаций и порядок fallback:
   "City, Country" → "City" → "Country" → "" (без ISO-кодов вроде "DE" в location)
2) Позитивный фильтр страны + анти‑шум:
   - учитываем маркеры нашей страны/городов
   - режем явные US/CA, в т.ч. паттерны US‑штатов ("Hamburg, PA")
   - спец‑кейс: защита от Delaware (DE) при country=de
3) Приоритет локальных результатов над глобальными
4) Расширены синонимы для DE/NL (англ. приоритет остаётся)
5) Нормализация URL в _stable_id для стабильной дедупликации
6) Убраны недокументированные параметры (dateRange), оставлен ResultOnPage (через .env)

Переменные окружения:
- JOOBLE_API_KEY (обязательно)
- JOOBLE_DEBUG=1|0
- JOOBLE_MAX_PAGES=2
- JOOBLE_MAX_TERMS=4
- JOOBLE_TERM_CAP=15         (сколько максимум брать на термин в рамках одной серии запросов)
- JOOBLE_RESULT_ON_PAGE=25   (будет добавлен, когда location непустой)
- JOOBLE_TIMEOUT_CONNECT=5
- JOOBLE_TIMEOUT_READ=15
- JOOBLE_USER_AGENT=GlobalJobHunter/1.0
"""

from __future__ import annotations

import os
import re
import time
import random
import unicodedata
from datetime import datetime
from typing import Dict, List, Optional, Tuple
from uuid import uuid5, NAMESPACE_URL
from urllib.parse import urlparse

import requests
from dotenv import load_dotenv

from base_aggregator import BaseJobAggregator
from adzuna_aggregator import JobVacancy

load_dotenv()


class JoobleAggregator(BaseJobAggregator):
    # Отображаемые имена стран (для UI/метаданных)
    COUNTRIES_MAP: Dict[str, str] = {
        "de": "Германия", "pl": "Польша", "gb": "Великобритания", "fr": "Франция",
        "it": "Италия", "es": "Испания", "nl": "Нидерланды", "at": "Австрия",
        "be": "Бельгия", "ch": "Швейцария", "se": "Швеция", "no": "Норвегия",
        "dk": "Дания", "cz": "Чехия", "us": "США", "ca": "Канада", "au": "Австралия"
    }

    # Англоязычные названия стран для формата "City, Country"
    LOCATION_FORMATS: Dict[str, str] = {
        "de": "Germany", "pl": "Poland", "gb": "United Kingdom", "fr": "France",
        "it": "Italy", "es": "Spain", "nl": "Netherlands", "at": "Austria",
        "be": "Belgium", "ch": "Switzerland", "se": "Sweden", "no": "Norway",
        "dk": "Denmark", "cz": "Czech Republic", "us": "United States",
        "ca": "Canada", "au": "Australia"
    }

    # Дефолтные города по странам
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

    # Доп. ASCII‑алиасы городов (для фильтра)
    EXTRA_CITY_ALIASES: Dict[str, List[str]] = {
        "de": ["munchen", "muenchen", "koln", "koeln", "nurnberg", "nuernberg", "dusseldorf"],
        "nl": ["den haag", "the hague", "s-gravenhage"],
    }

    # Языковые маркеры DE в текстах вакансий
    DE_LANGUAGE_MARKERS: List[str] = [
        "befristet", "unbefristet", "vollzeit", "teilzeit", "schicht", "zeitarbeit",
        "lager", "kommissionierer", "verpacker", "helfer", "produktionshelfer", "versandmitarbeiter"
    ]

    # Термин → варианты (расширили DE/NL, англ — в приоритете)
    TERM_TRANSLATIONS: Dict[str, List[str]] = {
        # Русские → английские (+ нем.)
        "официант": ["waiter", "waitress", "server", "restaurant worker", "kellner", "kellnerin"],
        "повар": ["cook", "chef", "kitchen worker", "kitchen assistant", "koch", "küchenhilfe"],
        "кассир": ["cashier", "till operator", "checkout operator", "sales assistant", "kassierer"],
        "уборщик": ["cleaner", "janitor", "cleaning worker", "housekeeping", "reinigungskraft"],
        "охранник": ["security guard", "security officer", "guard", "sicherheitsdienst"],

        # Водители и курьеры
        "таксист": ["taxi driver", "cab driver", "driver", "taxifahrer"],
        "водитель": ["driver", "delivery driver", "truck driver", "fahrer", "kraftfahrer"],
        "курьер": ["courier", "delivery driver", "messenger", "kurier", "lieferfahrer"],

        # Склад и логистика (+ нем.)
        "грузчик": ["warehouse worker", "loader", "packer", "material handler",
                    "lagerarbeiter", "kommissionierer", "lagerhelfer", "versandmitarbeiter"],
        "складской работник": ["warehouse operative", "stock handler", "logistics worker",
                               "lagerarbeiter", "lagermitarbeiter", "kommissionierer"],
        "разнорабочий": ["general worker", "manual worker", "helper", "laborer",
                         "helfer", "produktionshelfer", "arbeiter"],
        "строитель": ["construction worker", "builder", "construction assistant",
                      "bauarbeiter", "bauhelfer"],

        # Английские → смежные (+ нем.)
        "warehouse worker": ["warehouse operative", "stock handler", "logistics worker", "packer",
                             "lagerarbeiter", "kommissionierer", "lagerhelfer"],
        "driver": ["delivery driver", "truck driver", "van driver", "fahrer", "kraftfahrer"],
        "cleaner": ["janitor", "cleaning worker", "housekeeping", "reinigungskraft"],
        "cook": ["chef", "kitchen worker", "kitchen assistant", "koch", "küchenhilfe"],

        # NL → английские (+ местные)
        "magazijnmedewerker": ["warehouse worker", "warehouse operative", "stock handler", "orderpicker"],
        "schoonmaker": ["cleaner", "janitor", "cleaning worker", "reinigungskraft"],
        "kok": ["cook", "chef", "kitchen worker", "koch"],
        "chauffeur": ["driver", "delivery driver", "fahrer"],

        # Немецкие → английские
        "lagerarbeiter": ["warehouse worker", "warehouse operative", "stock handler"],
        "kommissionierer": ["warehouse worker", "picker", "order picker", "stock handler"],
        "fahrer": ["driver", "delivery driver", "truck driver"],
        "koch": ["cook", "chef", "kitchen worker"],
        "reinigungskraft": ["cleaner", "janitor", "cleaning worker"],
        "verpacker": ["packer", "warehouse worker"],
        "lagerhelfer": ["warehouse helper", "warehouse worker"],
        "produktionshelfer": ["production helper", "production worker", "warehouse worker"],
        "versandmitarbeiter": ["shipping clerk", "warehouse worker", "picker packer"],
        "orderpicker": ["order picker", "warehouse operative", "warehouse worker"],
        "inpakker": ["packer", "warehouse worker"],
        "reachtruckchauffeur": ["reach truck driver", "forklift driver", "warehouse driver"],
        "heftruckchauffeur": ["forklift driver", "warehouse driver"],
    }

    # Жёсткий стоп‑лист по компаниям (фейковые/нерелевантные для вакансий рабочих)
    HARD_NEGATIVE_COMPANIES: List[str] = [
        "scandinavian tobacco group",   # по логам лезет в DE с нерелевантными ролями
        "tradebe",                      # operations driver и прочее нерелевантное
        "stg",                          # сокращение того же бренда
    ]



    # — положительные маркеры для «склад/логистика»
    WAREHOUSE_POSITIVE = {
        "warehouse","operative","order picker","picker","packer","loader",
        "material handler","forklift","reach truck","pallet","logistics",
        "lager","lagerarbeiter","lagermitarbeiter","kommissionierer",
        "staplerfahrer","gabelstapler","versand","wareneingang","warenausgang",
        "magazijn","orderpicker","heftruck","reachtruck","logistiek",
        "magazyn","magazynier","kompletacja","pakowacz","operator wózka",
        "склад","кладовщик","грузчик","упаковщик","комплектовщик","погрузчик",
    }

    # — жёсткие «минусы» по нерелевантным доменам ролей
    NEGATIVE_GLOBAL = {
        "taco bell","barista","bar associate","bartender","server","waiter",
        "cashier","restaurant","kitchen","cook","chef","food service",
        "nurse","nursing","teacher","assistant director of nursing",
        "virtual assistant","office manager","receptionist",
    }

    # — можно отстреливать по компаниям (добавляй при надобности)
    HARD_NEGATIVE_COMPANIES = {"taco bell","mcdonald","kfc","starbucks"}


    # Алиасы стран/городов для фильтрации
    COUNTRY_ALIASES: Dict[str, List[str]] = {
        "de": ["germany", "deutschland", "german", "berlin", "munich", "münchen", "hamburg", "cologne", "köln",
               "frankfurt", "stuttgart", "düsseldorf", "leipzig", "hannover", "nuremberg", "nürnberg",
               "bremen", "dresden", "bonn", "essen", "dortmund", "mannheim", "freiburg", "karlsruhe", "wiesbaden",
               "münster", "augsburg", "mönchengladbach"],
        "pl": ["poland", "polska", "polish", "warsaw", "krakow", "wroclaw", "gdansk", "poznan"],
        "gb": ["united kingdom", "uk", "great britain", "britain", "england", "scotland", "wales", "london", "manchester"],
        "fr": ["france", "frankreich", "french", "paris", "lyon", "marseille"],
        "it": ["italy", "italia", "italian", "rome", "milan", "turin"],
        "es": ["spain", "españa", "spanish", "madrid", "barcelona", "valencia"],
        "nl": ["netherlands", "holland", "nederland", "dutch", "amsterdam", "rotterdam", "utrecht"],
        "at": ["austria", "österreich", "osterreich", "austrian", "vienna", "graz"],
        "be": ["belgium", "belgique", "belgië", "belgie", "belgian", "brussels", "antwerp"],
        "ch": ["switzerland", "schweiz", "suisse", "svizzera", "swiss", "zurich", "geneva"],
        "se": ["sweden", "sverige", "swedish", "stockholm", "gothenburg"],
        "no": ["norway", "norge", "norwegian", "oslo", "bergen"],
        "dk": ["denmark", "danmark", "danish", "copenhagen", "aarhus"],
        "cz": ["czech republic", "czechia", "česko", "cesko", "czech", "prague", "brno"],
        "us": ["united states", "usa", "u.s.a.", "american", "america",
               "alabama", "nevada", "california", "texas", "new york", "florida", "delaware",
               "al", "nv", "ca", "tx", "ny", "fl", "pa", "oh", "wa", "or", "il", "az"] + [
        "al","ak","az","ar","ca","co","ct","de","fl","ga","hi","id","il","in","ia","ks","ky","la","me","md",
        "ma","mi","mn","ms","mo","mt","ne","nv","nh","nj","nm","ny","nc","nd","oh","ok","or","pa","ri","sc",
        "sd","tn","tx","ut","vt","va","wa","wv","wi","wy","dc"
    ],
        "ca": ["canada", "canadian", "toronto", "vancouver", "montreal"] + 
          ["ab","bc","mb","nb","nl","ns","nt","nu","on","pe","qc","sk","yt"],
        "au": ["australia", "australian", "sydney", "melbourne"],
    }

    COUNTRY_NAME_EN: Dict[str, str] = LOCATION_FORMATS

    def __init__(self) -> None:
        self._countries: Dict[str, str] = dict(self.COUNTRIES_MAP)

        # Параметры API
        self.api_key: str = os.getenv("JOOBLE_API_KEY", "")
        if not self.api_key:
            raise ValueError("JOOBLE_API_KEY не найден. Получите ключ на https://jooble.org/api/about")

        self.max_pages: int = int(os.getenv("JOOBLE_MAX_PAGES", "2"))
        self.timeout_connect: int = int(os.getenv("JOOBLE_TIMEOUT_CONNECT", "5"))
        self.timeout_read: int = int(os.getenv("JOOBLE_TIMEOUT_READ", "15"))
        self.user_agent: str = os.getenv("JOOBLE_USER_AGENT", "GlobalJobHunter/1.0")
        self.max_terms: int = int(os.getenv("JOOBLE_MAX_TERMS", "4"))
        self.term_cap: int = int(os.getenv("JOOBLE_TERM_CAP", "15"))              # лимит на термин
        self.result_on_page: int = int(os.getenv("JOOBLE_RESULT_ON_PAGE", "25"))  # официальный параметр
        self.debug: bool = os.getenv("JOOBLE_DEBUG", "1").lower() in ("1", "true", "yes")

        # HTTP сессия
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": self.user_agent,
            "Accept": "application/json",
            "Content-Type": "application/json",
        })
        self.endpoint = f"https://jooble.org/api/{self.api_key}"

        super().__init__("Jooble")

    def get_supported_countries(self) -> Dict[str, Dict]:
        return {code: {"name": name} for code, name in self._countries.items()}

    # ---------- ОСНОВНОЙ ПОИСК ----------

    def search_jobs(self, preferences: Dict) -> List[JobVacancy]:
        """
        Порядок локаций: "City, Country" → "City" → "Country" → "".
        Без ISO-кодов. ResultOnPage передаём только если location непустой.
        Позитивный фильтр страны; глобальный поиск — только если локально мало результатов.
        """
        jobs: List[JobVacancy] = []

        # 1) Термины (приоритет англ. вариантов)
        selected_jobs: List[str] = self._get_translated_terms(preferences)

        # 2) География
        countries = preferences.get("countries") or []
        country_code = (countries[0] if countries else "").lower()
        cities = preferences.get("cities") or []
        country_name_en = self.COUNTRY_NAME_EN.get(country_code, "")

        if not country_code or country_code not in self.COUNTRIES_MAP:
            if self.debug:
                print(f"⚠️ Jooble: неподдерживаемая страна '{country_code}', пропускаем")
            return jobs

        # Базовые города
        if cities:
            base_locations: List[str] = [c.strip() for c in cities if c and c.strip()][:3]
        else:
            base_locations = list(self.DEFAULT_CITIES.get(country_code, []))[:6]

        # Конструируем варианты локаций (без ISO)
        loc_variants: List[Tuple[str, str]] = []
        for city in base_locations:
            if not city:
                continue
            if country_name_en:
                loc_variants.append((f"{city}, {country_name_en}", "city_full"))
            loc_variants.append((city, "city_short"))

        if country_name_en:
            loc_variants.append((country_name_en, "country_only"))

        loc_variants.append(("", "global"))

        if self.debug:
            print(f"Jooble: terms={selected_jobs[:self.max_terms]} | "
                  f"locations={[l for l, _ in loc_variants]} | country='{country_code}'")

        # 3) Поиск: приоритет локальным результатам
        for query in selected_jobs[: self.max_terms]:
            if not query:
                continue

            term_collected = 0

            # Сначала — локальные локации
            for loc, loc_type in [lv for lv in loc_variants if lv[1] != "global"]:
                page = 1
                while page <= self.max_pages and term_collected < self.term_cap:
                    body = {"keywords": query, "location": loc, "page": page}
                    if self.result_on_page and loc:
                        body["ResultOnPage"] = self.result_on_page

                    data = self._safe_post(self.endpoint, json=body)
                    items = (data or {}).get("jobs") or []

                    if self.debug or items:
                        print(f"Jooble: loc='{loc}' q='{query}' page={page} -> {len(items)} items")

                    if not items:
                        break

                    accepted = 0
                    for item in items:
                        if country_code and not self._passes_country_filter(item, country_code):
                            if self.debug:
                                print(f"  🚫 Отклонено фильтром страны: "
                                      f"title='{(item.get('title') or '')[:60]}' | loc='{item.get('location')}'")
                            continue

                        job = self._to_jobvacancy(item, query, countries)
                        if job and self.is_relevant_job(job.title, job.description, query):
                            jobs.append(job)
                            accepted += 1
                            term_collected += 1
                            if term_collected >= self.term_cap:
                                break

                    if self.debug and accepted:
                        print(f"  ✅ Принято после фильтров: {accepted}")

                    page += 1

                if term_collected >= self.term_cap:
                    break

            # Глобальный поиск — только если локально почти ничего не нашли
            if (not country_code) and term_collected < 2:
                loc, loc_type = ("", "global")
                page = 1
                while page <= self.max_pages and term_collected < self.term_cap:
                    body = {"keywords": query, "location": loc, "page": page}
                    data = self._safe_post(self.endpoint, json=body)
                    items = (data or {}).get("jobs") or []

                    if self.debug or items:
                        print(f"Jooble: loc='' q='{query}' page={page} -> {len(items)} items")

                    if not items:
                        break

                    accepted = 0
                    for item in items:
                        if country_code and not self._passes_country_filter(item, country_code):
                            if self.debug:
                                print(f"  🚫 Отклонено фильтром страны: "
                                      f"title='{(item.get('title') or '')[:60]}' | loc='{item.get('location')}'")
                            continue

                        job = self._to_jobvacancy(item, query, countries)
                        if job and self.is_relevant_job(job.title, job.description, query):
                            jobs.append(job)
                            accepted += 1
                            term_collected += 1
                            if term_collected >= self.term_cap:
                                break

                    if self.debug and accepted:
                        print(f"  ✅ Принято после фильтров (global): {accepted}")

                    page += 1

        # Дедуп по ID
        return self._deduplicate_jobs(jobs)

    # ---------- ВСПОМОГАТЕЛЬНЫЕ МЕТОДЫ ----------

    def _get_translated_terms(self, preferences: Dict) -> List[str]:
        """
        Собирает поисковые термины:
        • если фронт дал selected_jobs_multilang — используем их как есть (с дедупликацией);
        • иначе: берём selected_jobs, расширяем через TERM_TRANSLATIONS;
        • англ. термины идут первыми;
        • при country='de' поднимаем наверх локальные DE-синонимы.
        """
        if preferences.get("selected_jobs_multilang"):
            multilang = [s.strip() for s in preferences["selected_jobs_multilang"] if s and s.strip()]
            return list(dict.fromkeys(multilang))

        base_terms = [s.strip() for s in (preferences.get("selected_jobs") or []) if s and s.strip()]
        translated: List[str] = []
        for term in base_terms:
            translated.append(term)
            translated.extend(self.TERM_TRANSLATIONS.get(term.lower(), []))

        unique = list(dict.fromkeys(translated))

        english_first, non_english = [], []
        for t in unique:
            (english_first if self._is_likely_english(t) else non_english).append(t)
        ordered = english_first + non_english

        country = ((preferences.get("countries") or [None])[0] or "").lower()
        if country == "de":
            prefer_de = {
                "lagermitarbeiter", "lagerarbeiter", "kommissionierer", "staplerfahrer", "versandmitarbeiter"
            }
            head = [t for t in ordered if t.lower() in prefer_de]
            tail = [t for t in ordered if t.lower() not in prefer_de]
            ordered = head + tail

        return ordered




    def _is_likely_english(self, term: str) -> bool:
        if not term or not term.isascii():
            return False
        english_words = {
            "worker", "driver", "cook", "chef", "waiter", "server", "cleaner",
            "janitor", "guard", "security", "warehouse", "delivery", "truck",
            "construction", "helper", "assistant", "operative", "handler",
            "manager", "supervisor", "technician", "specialist", "packer",
            "picker",
        }
        return bool(set(term.lower().split()).intersection(english_words))

    def _has_foreign_markers_in_text(self, text_norm: str, target_country_code: str) -> bool:
        """True, если видны маркеры другой страны (US/CA)."""
        def has_word(hay: str, needle: str) -> bool:
            return re.search(rf"\b{re.escape(needle)}\b", hay) is not None

        foreign_words = {
            "us": ["united states", "usa", "u.s.a.", "america", "american",
                "california", "texas", "new york", "florida", "pennsylvania", "delaware"],
            "ca": ["canada", "canadian", "ontario", "quebec", "british columbia", "alberta"],
        }
        for code, words in foreign_words.items():
            if code != target_country_code and any(has_word(text_norm, w) for w in words):
                return True

        safe_us_states = {
            "ak","al","ar","az","ca","co","ct","dc","de","fl","ga","hi","ia","id","il","in","ks","ky","la","ma","md",
            "mi","mn","mo","ms","mt","nc","nd","ne","nh","nj","nm","nv","ny","oh","ok","or","pa","ri","sc","sd","tn",
            "tx","ut","va","vt","wa","wi","wv","wy"
        }
        if target_country_code == "de" and "de" in safe_us_states:
            safe_us_states = set(safe_us_states) - {"de"}

        tokens = set(re.findall(r"[a-z]+", text_norm))
        if target_country_code != "us" and tokens.intersection(safe_us_states):
            return True

        canadian_provinces = {"ontario","quebec","manitoba","saskatchewan","alberta","yukon","nunavut",
                            "newfoundland","labrador","nova","scotia","new","brunswick","british","columbia",
                            "prince","edward","island"}
        if target_country_code != "ca" and tokens.intersection(canadian_provinces):
            return True

        return False

    
    def _build_loc_variants(self, country_code: str, cities: List[str]) -> List[Tuple[str, str]]:
        """
        "City, CountryEN" → "City, CountryLocal" → "City" → "CountryEN" → "CountryLocal" → "" (global).
        Для DE добавляем 'Deutschland'.
        """
        country_name_en = self.COUNTRY_NAME_EN.get(country_code, "")
        country_name_local = {
            "de": "Deutschland",
            "at": "Österreich",
            "ch": "Schweiz",
        }.get(country_code, "")

        if cities:
            base_locations = [c.strip() for c in cities if c and c.strip()][:3]
        else:
            base_locations = list(self.DEFAULT_CITIES.get(country_code, []))[:6]

        loc_variants: List[Tuple[str, str]] = []
        for city in base_locations:
            if not city:
                continue
            if country_name_en:
                loc_variants.append((f"{city}, {country_name_en}", "city_full"))
            if country_name_local:
                loc_variants.append((f"{city}, {country_name_local}", "city_full_local"))
            loc_variants.append((city, "city_short"))

        if country_name_en:
            loc_variants.append((country_name_en, "country_only"))
        if country_name_local:
            loc_variants.append((country_name_local, "country_only_local"))

        loc_variants.append(("", "global"))
        return loc_variants




    def _passes_country_filter(self, item: Dict, country_code: str) -> bool:
        """
        Позитивный матч по нашей стране/городам + отсев явных US/CA.
        """
        def _norm(s: str) -> str:
            return unicodedata.normalize("NFKD", s or "").encode("ascii", "ignore").decode("ascii").lower().strip()

        def _tokens(s: str) -> List[str]:
            return re.findall(r"[a-z]+", s or "")

        location = (item.get("location") or "")
        title    = (item.get("title") or "")
        snippet  = (item.get("snippet") or "")

        loc_norm  = _norm(location)
        # ВАЖНО: учитываем location в тексте — ловим кейсы вроде "Hamburg, PA"
        text_norm = _norm(f"{title} {snippet} {location}")

        # 1) Отсев по маркерам других стран (сначала по локации)
        other_single: Set[str] = set()   # однословные токены (точные)
        other_multi:  List[str] = []     # многословные фразы

        for code, toks in self.COUNTRY_ALIASES.items():
            if code == country_code:
                continue
            for tok in toks:
                tok_n = _norm(tok)
                if " " in tok_n:
                    other_multi.append(tok_n)   # список → append ОК
                else:
                    other_single.add(tok_n)     # множество → add ОК

        loc_tokens = set(_tokens(loc_norm))

        # многословные — по границам слов
        for phrase in other_multi:
            if re.search(rf"\b{re.escape(phrase)}\b", loc_norm):
                return False

        # однословные — как точные токены
        if any(tok in loc_tokens for tok in other_single):
            return False

        # 2) Позитив по нашей стране/городам
        allowed = set(self.COUNTRY_ALIASES.get(country_code, []))
        city_aliases = {_norm(c) for c in self.DEFAULT_CITIES.get(country_code, [])}
        # если у тебя есть EXTRA_CITY_ALIASES — тоже подключи
        if hasattr(self, "EXTRA_CITY_ALIASES"):
            city_aliases.update(self.EXTRA_CITY_ALIASES.get(country_code, []))
        allowed |= city_aliases

        positive_match = False

        # многословные разрешающие — в локации
        for phrase in (t for t in allowed if " " in t):
            if re.search(rf"\b{re.escape(phrase)}\b", loc_norm):
                positive_match = True
                break

        # однословные разрешающие — как точные токены
        if not positive_match and any(t in loc_tokens for t in (t for t in allowed if " " not in t)):
            positive_match = True

        # если локация пустая/слабая — ищем маркеры в тексте
        if not positive_match and (not loc_norm or len(loc_norm) < 3):
            text_tokens = set(_tokens(text_norm))
            if any(re.search(rf"\b{re.escape(phrase)}\b", text_norm) for phrase in (t for t in allowed if " " in t)):
                positive_match = True
            elif any(t in text_tokens for t in (t for t in allowed if " " not in t)):
                positive_match = True

        if not positive_match:
            return False

        # 3) Отсев US/CA по всему тексту
        if self._has_foreign_markers_in_text(text_norm, country_code):
            return False

        # 4) Минус-слова/компании (если используются)
        title_lc = _norm(title)
        if any(bad in title_lc for bad in self.NEGATIVE_GLOBAL):
            return False

        comp_norm = (getattr(self, "_last_company_norm", "") or "").lower()
        if comp_norm and any(bad in comp_norm for bad in self.HARD_NEGATIVE_COMPANIES):
            return False

        return True

    def _safe_post(self, url: str, *, json: dict) -> Optional[dict]:
        """
        Пост с повторными попытками и логами
        """
        for attempt in range(3):
            try:
                resp = self.session.post(
                    url,
                    json=json,
                    timeout=(self.timeout_connect, self.timeout_read)
                )

                if self.debug:
                    print(f"📡 Jooble API ответ: {resp.status_code}")

                if resp.status_code == 429:
                    wait_time = (2 ** attempt) + random.uniform(0, 1)
                    if self.debug:
                        print(f"⏳ Rate limit, ждем {wait_time:.1f}s...")
                    time.sleep(wait_time)
                    continue

                if resp.status_code in (500, 502, 503, 504):
                    if self.debug:
                        print(f"🔄 Серверная ошибка {resp.status_code}, повтор {attempt+1}/3")
                    time.sleep(1 + attempt)
                    continue

                if resp.status_code == 400:
                    if self.debug:
                        print(f"❌ Неверный запрос (400): {resp.text[:200]}")
                    return None

                resp.raise_for_status()
                result = resp.json()

                if self.debug:
                    total_jobs = result.get("totalCount", 0)
                    print(f"📊 Jooble: totalCount={total_jobs}")

                return result

            except requests.RequestException as e:
                if self.debug:
                    print(f"🚫 Jooble сетевая ошибка (попытка {attempt+1}): {e}")
                if attempt == 2:
                    print(f"❌ Jooble финальная ошибка: {e}")
                else:
                    time.sleep(0.5 + attempt * 0.5)

        return None

    def _stable_id(self, link: str) -> str:
        """
        Нормализация URL перед генерацией ID (чистим трекинги/utm).
        """
        if not link:
            return f"jooble_{uuid5(NAMESPACE_URL, str(datetime.utcnow().timestamp()))}"

        clean_link = link
        utm_params = {
            "utm_source", "utm_medium", "utm_campaign", "utm_content", "utm_term",
            "ref", "source", "track", "campaign"
        }

        if "?" in clean_link:
            base_url, query_string = clean_link.split("?", 1)
            params = []
            if query_string:
                for param in query_string.split("&"):
                    if "=" in param:
                        key = param.split("=")[0].lower()
                        if key not in utm_params:
                            params.append(param)
            clean_link = base_url + ("?" + "&".join(params) if params else "")

        # фрагмент тоже не влияет на сущность вакансии
        if "#" in clean_link:
            clean_link = clean_link.split("#", 1)[0]

        return f"jooble_{uuid5(NAMESPACE_URL, clean_link)}"

    def _to_jobvacancy(self, d: Dict, search_term: str, countries: List[str]) -> Optional[JobVacancy]:
        """Конвертация Jooble item -> JobVacancy"""
        link = (d.get("link") or "").strip()
        title = (d.get("title") or "").strip()
        company = (d.get("company") or "Unknown").strip()
        location = (d.get("location") or "").strip()
        snippet = d.get("snippet") or ""
        job_type = d.get("type") or None

        # Зарплата
        salary = None
        if d.get("salary"):
            salary = self._format_salary(d["salary"])

        # Дата
        posted_raw = d.get("updated") or datetime.utcnow().strftime("%Y-%m-%d")
        posted = self._parse_date_safe(posted_raw)

        # Страна для отображения
        country_name = ""
        if countries:
            code = (countries[0] or "").lower()
            country_name = self._countries.get(code, code.upper())

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

    def _format_salary(self, salary_data) -> Optional[str]:
        """Форматирование зарплаты"""
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
        elif isinstance(salary_data, (int, float)):
            return str(int(salary_data))
        elif isinstance(salary_data, str):
            return salary_data.strip()
        return None

    @staticmethod
    def _parse_date_safe(value: str) -> str:
        """Парсинг даты с fallback"""
        if not value:
            return datetime.utcnow().strftime("%Y-%m-%d")

        formats = [
            "%Y-%m-%d",
            "%Y/%m/%d",
            "%d-%m-%Y",
            "%d/%m/%Y",
            "%Y-%m-%d %H:%M:%S",
            "%Y-%m-%dT%H:%M:%S",
        ]
        candidates = [
            value,
            value.split("T")[0],
            value.replace("/", "-"),
            value.split(" ")[0],
        ]

        for candidate in candidates:
            for fmt in formats:
                try:
                    parsed = datetime.strptime(candidate, fmt)
                    return parsed.strftime("%Y-%m-%d")
                except ValueError:
                    continue

        return datetime.utcnow().strftime("%Y-%m-%d")
    
    @staticmethod
    def _norm_txt(s: str) -> str:
        s = (s or "").strip().lower()
        s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode("ascii")
        s = re.sub(r"[^\w\s]", " ", s)
        return re.sub(r"\s+", " ", s).strip()

    @staticmethod
    def _city_part(loc: str) -> str:
        loc = (loc or "").lower()
        parts = re.split(r"[,/()|\-\u2013]", loc)
        for p in parts:
            p = p.strip()
            if p and len(p) > 1:
                return p
        return ""

    @staticmethod
    def _domain(u: str) -> str:
        try:
            d = urlparse(u).netloc.lower()
            return d[4:] if d.startswith("www.") else d
        except Exception:
            return ""


    def _deduplicate_jobs(self, jobs: List[JobVacancy]) -> List[JobVacancy]:
        """
        Усиленный дедуп внутри Jooble:
          K1: (norm_title, norm_company, city)
          K2: (domain(apply_url), norm_title)
        Выбираем «лучший» экземпляр: свежая дата выше, наличие зарплаты выше.
        """
        if not jobs:
            return jobs

        def score(j: JobVacancy) -> int:
            s = 0
            # зарплата – небольшой буст
            if getattr(j, "salary", None):
                s += 10
            # свежесть
            try:
                ts = datetime.strptime(j.posted_date, "%Y-%m-%d").timestamp()
                # делим, чтобы не раздувать счёт
                s += int(ts // (24 * 3600))
            except Exception:
                pass
            return s

        seen_tuple = {}         # K1 -> JobVacancy
        seen_domain_title = {}  # K2 -> JobVacancy

        for j in jobs:
            k1 = (self._norm_txt(j.title), self._norm_txt(j.company), self._city_part(j.location))
            k2 = (self._domain(j.apply_url), self._norm_txt(j.title))

            # по K1
            cur = seen_tuple.get(k1)
            if cur is None or score(j) > score(cur):
                seen_tuple[k1] = j

            # по K2 (ловим трекинг-ссылки от одного и того же источника)
            if k2[0]:  # домен известен
                cur2 = seen_domain_title.get(k2)
                if cur2 is None or score(j) > score(cur2):
                    seen_domain_title[k2] = j

        # собрать лучшие экземпляры
        picked = {}
        for v in seen_tuple.values():
            picked[v.id] = v
        for v in seen_domain_title.values():
            picked[v.id] = v

        result = list(picked.values())
        if self.debug and len(result) < len(jobs):
            print(f"🔄 Jooble: удалено {len(jobs) - len(result)} дубликатов (усиленный дедуп)")

        return result
    
    def _infer_role_from_term(self, term: str) -> str:
        t = (term or "").lower()
        warehouse_markers = {
            "warehouse","operative","picker","packer","loader","material handler",
            "magazijn","orderpicker","lager","kommissionierer","magazyn","грузчик","склад"
        }
        if any(m in t for m in warehouse_markers):
            return "warehouse"
        for k, variants in self.TERM_TRANSLATIONS.items():
            if t == k or t in (v.lower() for v in variants):
                if any("warehouse" in v.lower() or "lager" in v.lower()
                    or "magaz" in v.lower() or "kommissionierer" in v.lower()
                    for v in ([k] + variants)):
                    return "warehouse"
        return "generic"


    def is_relevant_job(self, job_title: str, job_description: str, search_term: str) -> bool:
        title = (job_title or "").lower()
        desc  = (job_description or "").lower()
        company_norm = (getattr(self, "_last_company_norm", "") or "").lower()
        text_norm = re.sub(r"[^a-zа-яё0-9 ]", " ", title).lower()
        if any(bad in company_norm for bad in self.HARD_NEGATIVE_COMPANIES):
            return False

        role = self._infer_role_from_term(search_term)

        # — для «склада» требуем ПОЛОЖИТЕЛЬНЫЕ маркеры
        if role == "warehouse":
            if any(pos in title or pos in desc for pos in self.WAREHOUSE_POSITIVE):
                return True
            return False  # нет складских маркеров — нерелевант

        # — остальное оставляем мягким (как было)
        if not search_term:
            return True
        t = search_term.lower()
        if t in title:
            return True
        words = [w for w in re.findall(r"[a-zа-яё\-]+", t) if len(w) > 2]
        if not words:
            return t in desc
        found = sum(1 for w in words if w in title or w in desc)
        return found >= max(1, int(len(words) * 0.5))



# ---------- DEBUG / ТЕСТЫ ----------

class JoobleDebugTester:
    def __init__(self):
        self.api_key = os.getenv("JOOBLE_API_KEY", "")
        self.endpoint = f"https://jooble.org/api/{self.api_key}"

    def test_location_formats(self):
        """Проверяем форматы (без ISO) и ResultOnPage только при непустой location."""
        test_cases = [
            {"keywords": "warehouse worker", "location": "Berlin"},
            {"keywords": "warehouse worker", "location": "Berlin, Germany"},
            {"keywords": "warehouse worker", "location": "Germany"},
            {"keywords": "warehouse worker", "location": ""},
            {"keywords": "Грузчик", "location": "Berlin, Germany"},
            {"keywords": "warehouse worker", "location": "Berlin, Germany"},
            {"keywords": "lagerarbeiter", "location": "Berlin, Germany"},
            {"keywords": "kommissionierer", "location": "Berlin"},
            {"keywords": "warehouse worker", "location": "Berlin, Germany", "ResultOnPage": 30},
            {"keywords": "driver", "location": "Germany", "ResultOnPage": 20},
        ]

        print("🧪 Тестирование форматов Jooble API...")
        print("=" * 60)

        for i, body in enumerate(test_cases, 1):
            try:
                print(f"\n📋 Тест {i}: {body}")
                resp = requests.post(
                    self.endpoint,
                    json=body,
                    headers={"Content-Type": "application/json"},
                    timeout=10
                )
                if resp.status_code == 200:
                    data = resp.json()
                    jobs = data.get("jobs", [])
                    total = data.get("totalCount", 0)
                    print(f"✅ Результат: {len(jobs)} jobs, totalCount: {total}")
                    if jobs:
                        locations_sample = list(set([(job.get("location") or "")[:50] for job in jobs[:5]]))
                        print(f"📍 Примеры локаций: {locations_sample}")
                else:
                    print(f"❌ HTTP {resp.status_code}: {resp.text[:200]}")
            except Exception as e:
                print(f"🚫 Ошибка: {e}")

        print("\n" + "=" * 60)
        print("🏁 Тестирование завершено")

    def test_term_variants(self):
        terms_to_test = [
            "Строитель-разнорабочий", "Грузчик", "magazijnmedewerker",
            "construction worker", "warehouse worker", "loader", "packer",
            "lagerarbeiter", "kommissionierer", "fahrer",
            "driver", "cook", "cleaner"
        ]
        print("🔤 Тестирование терминов...")
        print("=" * 60)
        for term in terms_to_test:
            body = {"keywords": term, "location": "Berlin, Germany", "page": 1, "ResultOnPage": 20}
            try:
                resp = requests.post(self.endpoint, json=body, timeout=10)
                if resp.status_code == 200:
                    data = resp.json()
                    jobs_count = len(data.get("jobs", []))
                    total_count = data.get("totalCount", 0)
                    print(f"📝 '{term}': {jobs_count} jobs (total: {total_count})")
                else:
                    print(f"❌ '{term}': HTTP {resp.status_code}")
            except Exception as e:
                print(f"🚫 '{term}': ошибка {e}")
        print("=" * 60)


def quick_jooble_test():
    """
    Быстрое тестирование Jooble для отладки
    Запуск: python -c "from jooble_aggregator import quick_jooble_test; quick_jooble_test()"
    """
    print("🚀 Быстрое тестирование Jooble API...")

    api_key = os.getenv("JOOBLE_API_KEY")
    if not api_key:
        print("❌ JOOBLE_API_KEY не найден в .env")
        print("📝 Добавьте в .env:")
        print("JOOBLE_API_KEY=ваш_ключ")
        print("JOOBLE_DEBUG=1")
        print("JOOBLE_MAX_PAGES=2")
        print("JOOBLE_MAX_TERMS=4")
        print("JOOBLE_TERM_CAP=15")
        print("JOOBLE_RESULT_ON_PAGE=25")
        return

    print(f"🔑 API ключ: {api_key[:10]}...")

    tester = JoobleDebugTester()
    tester.test_location_formats()
    tester.test_term_variants()

    print("\n🔗 Тестирование интеграции...")
    try:
        aggregator = JoobleAggregator()
        test_preferences = {
            "selected_jobs": ["Грузчик", "warehouse worker", "magazijnmedewerker"],
            "countries": ["de"],
            "cities": ["Berlin"],
            "is_refugee": True
        }
        print(f"🔍 Тест поиска: {test_preferences}")
        jobs = aggregator.search_jobs(test_preferences)
        print(f"✅ Найдено {len(jobs)} вакансий через интеграцию")
        for i, job in enumerate(jobs[:5]):
            print(f"  {i+1}. {job.title} | {job.company} | {job.location}")
    except Exception as e:
        print(f"❌ Ошибка интеграции: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    quick_jooble_test()
