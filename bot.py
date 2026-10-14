import os
import asyncio
import logging
import sqlite3
from aiohttp import web
from aiogram import Bot, Dispatcher, F, Router
from aiogram.filters import CommandStart
from aiogram.types import (
    Message, CallbackQuery, 
    ReplyKeyboardMarkup, KeyboardButton, 
    InlineKeyboardMarkup, InlineKeyboardButton
)
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage

# API Token
TOKEN = "8868573467:AAF3pyHlAAf7I-uU3kbiFaBvkb2Y6M-pv0A"

logging.basicConfig(level=logging.INFO)

# --- SQLite Ma'lumotlar Ba'zasi ---
def init_db():
    conn = sqlite3.connect("bolajon_bot.db")
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            language TEXT DEFAULT 'uz',
            favorites TEXT DEFAULT ''
        )
    """)
    conn.commit()
    conn.close()

def set_user_lang(user_id: int, lang: str):
    conn = sqlite3.connect("bolajon_bot.db")
    cursor = conn.cursor()
    cursor.execute("INSERT OR REPLACE INTO users (user_id, language) VALUES (?, ?)", (user_id, lang))
    conn.commit()
    conn.close()

def get_user_lang(user_id: int) -> str:
    conn = sqlite3.connect("bolajon_bot.db")
    cursor = conn.cursor()
    cursor.execute("SELECT language FROM users WHERE user_id = ?", (user_id,))
    res = cursor.fetchone()
    conn.close()
    return res[0] if res else "uz"

# --- Matnlar ---
TEXTS = {
    "uz": {
        "welcome": "👶 **'Bolajon' pediatriya va tibbiy ta'lim botiga xush kelibsiz!**\n\nBo'limni tanlang:",
        "disclaimer": "⚠️ **XAVFSIZLIK OGOHLANTIRISHI:**\nUshbu bot faqat ta'lim va ma'lumot olish maqsadida yaratilgan. Bot bergan ma'lumotlar asosida mustaqil tashxis qo'yish va davolash taqiqlanadi!",
        "menu_edu": "📚 O'quv materiallari",
        "menu_dev": "👶 Bolalar rivojlanishi",
        "menu_clinic": "🏥 Klinik yordam",
        "menu_calc": "🧮 Kalkulyatorlar",
        "menu_exam": "📝 Imtihonga tayyorlov",
        "menu_practice": "📋 Amaliyot va Anamnez",
        "menu_tools": "⚙️ Sozlamalar va Til",
        "emergency": "🚨 Shoshilinch holatlar",
        "lang_select": "Iltimos, tilni tanlang:",
    },
    "ru": {
        "welcome": "👶 **Добро пожаловать в бот медицинского образования 'Bolajon'!**\n\nВыберите раздел:",
        "disclaimer": "⚠️ **ПРЕДУПРЕЖДЕНИЕ:**\nЭтот бот предназначен только для образовательных целей. Самолечение и постановка диагноза запрещены!",
        "menu_edu": "📚 Учебные материалы",
        "menu_dev": "👶 Развитие ребенка",
        "menu_clinic": "🏥 Клиническая помощь",
        "menu_calc": "🧮 Калькуляторы",
        "menu_exam": "📝 Подготовка к экзаменам",
        "menu_practice": "📋 Практика и Анамнез",
        "menu_tools": "⚙️ Настройки и Язык",
        "emergency": "🚨 Неотложная помощь",
        "lang_select": "Выберите язык:",
    },
    "en": {
        "welcome": "👶 **Welcome to the 'Bolajon' Pediatric Educational Bot!**\n\nSelect a section:",
        "disclaimer": "⚠️ **DISCLAIMER:**\nThis bot is for educational purposes only. Self-diagnosis and treatment are strictly prohibited.",
        "menu_edu": "📚 Educational Materials",
        "menu_dev": "👶 Child Development",
        "menu_clinic": "🏥 Clinical Care",
        "menu_calc": "🧮 Calculators",
        "menu_exam": "📝 Exam Preparation",
        "menu_practice": "📋 Practice & History",
        "menu_tools": "⚙️ Settings & Language",
        "emergency": "🚨 Emergency Algorithms",
        "lang_select": "Choose language:",
    }
}

def get_main_keyboard(lang: str) -> ReplyKeyboardMarkup:
    t = TEXTS[lang]
    kb = [
        [KeyboardButton(text=t["menu_edu"]), KeyboardButton(text=t["menu_dev"])],
        [KeyboardButton(text=t["menu_clinic"]), KeyboardButton(text=t["menu_calc"])],
        [KeyboardButton(text=t["menu_exam"]), KeyboardButton(text=t["menu_practice"])],
        [KeyboardButton(text=t["emergency"]), KeyboardButton(text=t["menu_tools"])]
    ]
    return ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True)

def get_lang_inline() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🇺🇿 O'zbekcha", callback_data="setlang_uz"),
            InlineKeyboardButton(text="🇷🇺 Русский", callback_data="setlang_ru"),
            InlineKeyboardButton(text="🇬🇧 English", callback_data="setlang_en")
        ]
    ])

class CalcState(StatesGroup):
    waiting_for_weight = State()

router = Router()

@router.message(CommandStart())
async def cmd_start(message: Message):
    init_db()
    await message.answer(
        "Xush kelibsiz / Добро пожаловать!\n\n" + TEXTS["uz"]["lang_select"],
        reply_markup=get_lang_inline()
    )

@router.callback_query(F.data.startswith("setlang_"))
async def process_lang_change(callback: CallbackQuery):
    lang = callback.data.split("_")[1]
    set_user_lang(callback.from_user.id, lang)
    await callback.message.delete()
    await callback.message.answer(
        TEXTS[lang]["welcome"], 
        reply_markup=get_main_keyboard(lang),
        parse_mode="Markdown"
    )
    await callback.message.answer(TEXTS[lang]["disclaimer"], parse_mode="Markdown")

@router.message(F.text.in_([TEXTS["uz"]["emergency"], TEXTS["ru"]["emergency"], TEXTS["en"]["emergency"]]))
async def menu_emergency(message: Message):
    text = (
        "🚨 **SHOSHILINCH HOLATLAR ALGORITMI:**\n\n"
        "🔥 **Gipertermiya:** Paratsetamol 10-15 mg/kg\n"
        "⚡ **Tutqanoq:** Diazepam 0.1-0.3 mg/kg\n"
        "💨 **Bo'g'ilish:** Deksametazon 0.3-0.6 mg/kg\n"
        "💧 **Degidratatsiya:** Regidron bilan oral regidratatsiya"
    )
    await message.answer(text, parse_mode="Markdown")

# Render.com salomatlik tekshiruvi (Health Check) uchun handler
async def handle(request):
    return web.Response(text="Bolajon Bot 24/7 rejimida muvaffaqiyatli ishlamoqda!")

async def main():
    bot = Bot(token=TOKEN)
    dp = Dispatcher(storage=MemoryStorage())
    dp.include_router(router)
    
    # Render avtomatik beradigan dinamik PORT sozlamasi
    app = web.Application()
    app.router.add_get("/", handle)
    runner = web.AppRunner(app)
    await runner.setup()
    
    port = int(os.environ.get("PORT", 10000))
    site = web.TCPSite(runner, "0.0.0.0", port)
    asyncio.create_task(site.start())

    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logging.info("Bot to'xtatildi!")

