# analytics.py -- централизованная трекинг-логика (минимальные правки в проекте)
import json
from datetime import datetime
from typing import Optional, Tuple
from urllib.parse import urlparse

import requests
from flask import Blueprint, current_app, request, redirect, abort

from database import db  # используем уже сконфигурированный SQLAlchemy из проекта

# --- МОДЕЛИ ------------------------------------------------------------------

class SearchClick(db.Model):
    __tablename__ = "search_click"
    id = db.Column(db.Integer, primary_key=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    ip = db.Column(db.String(64), index=True)
    country = db.Column(db.String(2))      # ISO-2 (если удалось)
    city = db.Column(db.String(128))
    lat = db.Column(db.Float)
    lon = db.Column(db.Float)
    user_agent = db.Column(db.String(512))
    lang = db.Column(db.String(8))

    # Параметры поиска (для аналитики)
    is_refugee = db.Column(db.Boolean)
    countries = db.Column(db.Text)         # JSON-массив стран
    jobs = db.Column(db.Text)              # JSON-массив профессий
    city_query = db.Column(db.String(256)) # свободный текст города/первого города


class PartnerClick(db.Model):
    __tablename__ = "partner_click"
    id = db.Column(db.Integer, primary_key=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    ip = db.Column(db.String(64), index=True)
    country = db.Column(db.String(2))
    city = db.Column(db.String(128))
    lat = db.Column(db.Float)
    lon = db.Column(db.Float)
    user_agent = db.Column(db.String(512))
    lang = db.Column(db.String(8))

    partner = db.Column(db.String(32), index=True)    # Adzuna | Careerjet | Remotive | Jobicy
    target_domain = db.Column(db.String(128))          # хост партнёра
    target_url = db.Column(db.Text)                    # полный URL для отладки
    job_id = db.Column(db.String(128))                 # если есть
    job_title = db.Column(db.String(256))              # если передадим из шаблона


# --- BLUEPRINT ---------------------------------------------------------------
analytics_bp = Blueprint("analytics", __name__)


@analytics_bp.route("/out")
def outbound():
    """
    Безопасный редиректор на сайт-партнёр:
    /out?partner=Adzuna&u=<full url>&job_id=...&title=...
    Логируем клик и тут же делаем 302 на партнёра.
    """
    raw_url = request.args.get("u", "").strip()
    partner = (request.args.get("partner", "") or "").strip() or None
    job_id = request.args.get("job_id")
    title = request.args.get("title")

    if not raw_url:
        abort(400, "Missing 'u' parameter")

    # sanity-check URL
    try:
        parsed = urlparse(raw_url)
    except Exception:
        abort(400, "Bad URL")

    if parsed.scheme not in ("http", "https"):
        abort(400, "Invalid scheme")
    if not parsed.netloc:
        abort(400, "Invalid URL host")

    # логирование (не блокируем редирект)
    try:
        ip, ua, lang = _extract_request_meta(request)
        geo = _geolocate_ip(ip)
        pc = PartnerClick(
            ip=ip, user_agent=ua, lang=lang,
            country=(geo or {}).get("country"), city=(geo or {}).get("city"),
            lat=(geo or {}).get("lat"), lon=(geo or {}).get("lon"),
            partner=partner or _guess_partner_from_host(parsed.netloc),
            target_domain=parsed.netloc.lower(),
            target_url=raw_url,
            job_id=job_id, job_title=title,
        )
        db.session.add(pc)
        db.session.commit()
    except Exception as e:
        current_app.logger.exception("PartnerClick log failed: %s", e)

    return redirect(raw_url, code=302)


# --- ЛОГ ПОИСКА --------------------------------------------------------------

def log_search_click(preferences: dict):
    """
    Вызывать из /search или /search/start — логирует нажатие «Найти работу»
    с IP/гео/параметрами.
    """
    try:
        ip, ua, lang = _extract_request_meta(request)
        geo = _geolocate_ip(ip)
        sc = SearchClick(
            ip=ip, user_agent=ua, lang=lang,
            country=(geo or {}).get("country"), city=(geo or {}).get("city"),
            lat=(geo or {}).get("lat"), lon=(geo or {}).get("lon"),
            is_refugee=bool(preferences.get("is_refugee")),
            countries=json.dumps(preferences.get("countries") or []),
            jobs=json.dumps(preferences.get("selected_jobs") or []),
            city_query=(preferences.get("city") or (preferences.get("cities") or [None])[0])
            if isinstance(preferences.get("cities"), list) else (preferences.get("city") or None),
        )
        db.session.add(sc)
        db.session.commit()
    except Exception as e:
        current_app.logger.exception("SearchClick log failed: %s", e)


# --- УТИЛИТЫ -----------------------------------------------------------------

def _guess_partner_from_host(host: str) -> Optional[str]:
    h = (host or "").lower()
    if "adzuna" in h: return "Adzuna"
    if "careerjet" in h: return "Careerjet"
    if "jobicy" in h: return "Jobicy"
    if "remotive" in h: return "Remotive"
    return None


def _extract_request_meta(req) -> Tuple[str, str, str]:
    # IP с учётом прокси
    ip = req.headers.get("X-Forwarded-For", "").split(",")[0].strip() or \
         req.headers.get("X-Real-IP", "").strip() or \
         req.remote_addr or "0.0.0.0"
    ua = req.headers.get("User-Agent", "")[:500]
    lang = (req.cookies.get("lang") or req.headers.get("Accept-Language", "ru"))[:8]
    return ip, ua, lang


def _geolocate_ip(ip: str) -> Optional[dict]:
    """
    Бюджетная геолокация. Работает «по возможности»:
    - RFC1918/локальные IP — пропускаем
    - внешний сервис читаем из конфигов:
      GEOIP_URL (напр. https://ipapi.co/{ip}/json) и GEOIP_TOKEN (опционально)
    - по умолчанию пробуем ipapi.co без ключа (мягко, с timeout)
    """
    try:
        if not ip or ip.startswith(("10.", "192.168.", "127.", "172.")):
            return None
        template = (current_app.config.get("GEOIP_URL") or "https://ipapi.co/{ip}/json").strip()
        url = template.format(ip=ip)
        headers = {}
        token = current_app.config.get("GEOIP_TOKEN")
        if token:
            headers["Authorization"] = f"Bearer {token}"
        r = requests.get(url, headers=headers, timeout=1.8)
        if r.ok:
            j = r.json()
            country = (j.get("country") or j.get("country_code") or "").upper()[:2] or None
            city = j.get("city") or None
            lat = float(j.get("latitude") or j.get("lat") or 0) or None
            lon = float(j.get("longitude") or j.get("lon") or 0) or None
            return {"country": country, "city": city, "lat": lat, "lon": lon}
    except Exception:
        pass
    return None


# --- ДЛЯ АДМИНКИ -------------------------------------------------------------

from sqlalchemy import inspect

def recent_events(limit=50):
    """Последние записи по обоим типам кликов; безопасно работает, если таблиц ещё нет."""
    insp = inspect(db.engine)
    has_sc = insp.has_table("search_click")
    has_pc = insp.has_table("partner_click")

    sc = []
    pc = []
    if has_sc:
        sc = SearchClick.query.order_by(SearchClick.created_at.desc()).limit(limit).all()
    if has_pc:
        pc = PartnerClick.query.order_by(PartnerClick.created_at.desc()).limit(limit).all()
    return sc, pc
