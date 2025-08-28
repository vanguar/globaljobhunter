# telegram_bot/bot.py
import os
import asyncio
import logging
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import CommandStart, Command
from aiogram.types import (
    ReplyKeyboardMarkup, KeyboardButton, WebAppInfo,
    InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery,
)

# Логи
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
)
log = logging.getLogger("gjh-bot")

BOT_TOKEN = os.getenv("BOT_TOKEN")
WEBAPP_BASE = os.getenv("WEBAPP_URL", "https://globaljobhunter.vip/static/tg/webapp.html")

if not BOT_TOKEN:
    log.error("BOT_TOKEN пуст. Установи переменную окружения BOT_TOKEN")
    raise SystemExit(1)

bot = Bot(BOT_TOKEN)
dp = Dispatcher()

# Память выбора языка (на старте достаточно in-memory)
USER_LANG: dict[int, str] = {}  # user_id -> "en"|"ru"|"uk"

# Простая i18n
T = {
    "btn_open": {
        "en": "🔎 Open GlobalJobHunter",
        "ru": "🔎 Открыть GlobalJobHunter",
        "uk": "🔎 Відкрити GlobalJobHunter",
    },
    "start": {
        "en": "Open the mini-site in Telegram 👇",
        "ru": "Открой мини-сайт прямо в Telegram 👇",
        "uk": "Відкрий міні-сайт у Telegram 👇",
    },
    "choose": {
        "en": "Choose language:",
        "ru": "Выберите язык:",
        "uk": "Оберіть мову:",
    },
    "lang_saved": {
        "en": "Language set to English ✅",
        "ru": "Язык переключен на русский ✅",
        "uk": "Мову перемкнено на українську ✅",
    },
    "change_lang": {
        "en": "Change language",
        "ru": "Сменить язык",
        "uk": "Змінити мову",
    },
}

# --- WebApp URL builder (нормализует 'ua' -> 'uk') ---
WEBAPP_URL = os.getenv("WEBAPP_URL", "").strip()

def _normalize_lang(code: str) -> str:
    c = (code or "").lower()
    if c == "ua":
        return "uk"
    return c if c in ("ru", "en", "uk") else "ru"

def build_webapp_url(lang: str) -> str:
    base = WEBAPP_URL or "https://<YOUR-DOMAIN>/static/tg/webapp.html"
    sep = "&" if "?" in base else "?"
    return f"{base}{sep}lang={_normalize_lang(lang)}"


def pick(lang: str | None, key: str) -> str:
    code = (lang or "en").split("-")[0]
    return T[key].get(code, T[key]["en"])

def _normalize_lang(code: str | None) -> str:
    c = (code or "ru").split("-")[0].lower()
    if c == "ua":
        return "uk"
    return c if c in ("ru", "en", "uk") else "ru"

def get_user_lang(user: types.User) -> str:
    if user.id in USER_LANG:
        return _normalize_lang(USER_LANG[user.id])
    return _normalize_lang(user.language_code)

def webapp_url_for(lang: str) -> str:
    return f"{WEBAPP_BASE}?lang={_normalize_lang(lang)}"


def lang_inline_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="English",    callback_data="setlang:en")],
        [InlineKeyboardButton(text="Українська", callback_data="setlang:uk")],
        [InlineKeyboardButton(text="Русский",    callback_data="setlang:ru")],
    ])

def open_button_kb(lang: str) -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        resize_keyboard=True,
        keyboard=[[KeyboardButton(
            text=pick(lang, "btn_open"),
            web_app=WebAppInfo(url=WEBAPP_BASE)  # без ?lang
        )]],
    )


def lang_menu_kb(lang: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=pick(lang, "change_lang"), callback_data="show_lang_menu")]
    ])

@dp.message(CommandStart())
async def on_start(m: types.Message):
    user = m.from_user
    lang = get_user_lang(user)
    log.info("START from @%s (id=%s) -> lang=%s", user.username, user.id, lang)

    kb = open_button_kb(lang)  # открываем мини-апп без ?lang
    await m.answer(
    "Привет! 👋 Я GlobalJobHunter Bot.\n\n"
    "Я делаю 🌐 глобальный поиск вакансий по разным странам и сайтам "
    "(Adzuna, Careerjet, Jobicy, Remotive). "
    "Запускай мини-приложение ниже, выбирай профессии и страны, и жми «Найти» 🔎.\n\n"
    "Готов? Поехали! 🚀",
    reply_markup=kb
)
# меню выбора языка больше не показываем


@dp.message(Command("lang"))
async def on_lang_cmd(m: types.Message):
    await m.answer("Переключение языка отключено.")


@dp.callback_query(F.data == "show_lang_menu")
async def on_show_lang_menu(cq: CallbackQuery):
    lang = get_user_lang(cq.from_user)
    await cq.message.answer(pick(lang, "choose"), reply_markup=lang_inline_keyboard())
    await cq.answer()

@dp.callback_query(F.data.startswith("setlang:"))
async def on_set_lang(cq: CallbackQuery):
    _, lang = cq.data.split(":", 1)
    USER_LANG[cq.from_user.id] = lang
    log.info("Set lang for id=%s -> %s", cq.from_user.id, lang)

    # уведомим
    await cq.message.answer(T["lang_saved"][lang])

    # новая WebApp-кнопка с языком
    await cq.message.answer(pick(lang, "start"), reply_markup=open_button_kb(lang))

    # показать меню «Сменить язык» (НЕ ПУСТОЙ ТЕКСТ!)
    await cq.message.answer(pick(lang, "choose"), reply_markup=lang_menu_kb(lang))

    await cq.answer()


@dp.errors()
async def on_error(event: types.ErrorEvent):
    logging.exception("Unhandled error: %s", event.exception)

async def main():
    log.info("Starting polling...")
    log.info("WEBAPP_URL = %s", WEBAPP_BASE)
    await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        log.info("KeyboardInterrupt — shutting down.")
