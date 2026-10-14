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

TOKEN = "8868573467:AAF3pyHlAAf7I-uU3kbiFaBvkb2Y6M-pv0A"

logging.basicConfig(level=logging.INFO)

# --- SQLite Ma'lumotlar Ba'zasi ---
def init_db():
    conn = sqlite3.connect("bolajon_bot.db")
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            language TEXT DEFAULT 'uz'
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

# --- Matnlar va Tugmalar ---
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
        "lang_select": "Iltimos, tilni tanlang / Пожалуйста, выберите язык:",
        "back": "⬅️ Orqaga"
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
        "lang_select": "Выберите язык / Select language:",
        "back": "⬅️ Назад"
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
        "back": "⬅️ Back"
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
        TEXTS["uz"]["lang_select"],
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

# --- 🚨 Shoshilinch Holatlar ---
@router.message(F.text.in_([TEXTS["uz"]["emergency"], TEXTS["ru"]["emergency"], TEXTS["en"]["emergency"]]))
async def menu_emergency(message: Message):
    lang = get_user_lang(message.from_user.id)
    if lang == "ru":
        text = (
            "🚨 **НЕОТЛОЖНАЯ ПОМОЩЬ В ПЕДИАТРИИ:**\n\n"
            "🔥 **Гипертермия:** Парацетамол 10-15 мг/кг или Ибупрофен 5-10 мг/кг\n"
            "⚡ **Судороги:** Диазепам 0.1-0.3 мг/кг в/в или ректально\n"
            "💨 **Круп (Стеноз гортани):** Дексаметазон 0.3-0.6 мг/кг в/м\n"
            "💧 **Острая дегидратация:** Оральная регидратация (Регидрон) 50-100 мл/кг за 4 часа"
        )
    elif lang == "en":
        text = (
            "🚨 **PEDIATRIC EMERGENCY ALGORITHMS:**\n\n"
            "🔥 **Hyperthermia:** Paracetamol 10-15 mg/kg or Ibuprofen 5-10 mg/kg\n"
            "⚡ **Seizures:** Diazepam 0.1-0.3 mg/kg IV/rectally\n"
            "💨 **Croup:** Dexamethasone 0.3-0.6 mg/kg IM\n"
            "💧 **Dehydration:** Oral rehydration solution (ORS) 50-100 ml/kg over 4 hours"
        )
    else:
        text = (
            "🚨 **SHOSHILINCH HOLATLAR ALGORITMI:**\n\n"
            "🔥 **Gipertermiya:** Paratsetamol 10-15 mg/kg yoki Ibuprofen 5-10 mg/kg\n"
            "⚡ **Tutqanoq (Talvasa):** Diazepam 0.1-0.3 mg/kg v/v yoki rektal\n"
            "💨 **Laringospazm / Krup:** Deksametazon 0.3-0.6 mg/kg m/o\n"
            "💧 **O'tkir degidratatsiya:** Oral regidratatsiya (Regidron) 4 soatda 50-100 ml/kg"
        )
    await message.answer(text, parse_mode="Markdown")

# --- 📚 O'quv Materiallari ---
@router.message(F.text.in_([TEXTS["uz"]["menu_edu"], TEXTS["ru"]["menu_edu"], TEXTS["en"]["menu_edu"]]))
async def menu_edu(message: Message):
    text = (
        "📚 **PEDIATRIYA O'QUV MATERIALLARI:**\n\n"
        "1️⃣ **Anatomik-fiziologik xususiyatlar (AFX):** Bolalarda nafas, yurak-qon tomir va xazm tizimi kattalardan tubdan farq qiladi.\n"
        "2️⃣ **Ko'krak yoshidagi bolalarni ovqatlantirish:** Tabiiy (ona suti), aralash va sun'iy ovqatlantirish qoidalari.\n"
        "3️⃣ **Raxit va Anemiya:** Profilaktika, D3 vitamini va temir preparatlari dozasini to'g'ri belgilash."
    )
    await message.answer(text, parse_mode="Markdown")

# --- 👶 Bolalar Rivojlanishi ---
@router.message(F.text.in_([TEXTS["uz"]["menu_dev"], TEXTS["ru"]["menu_dev"], TEXTS["en"]["menu_dev"]]))
async def menu_dev(message: Message):
    text = (
        "👶 **BOLALAR RIVOJLANISHI BOSQICHLARI:**\n\n"
        "🔹 **1 oy:** Boshini vaqtincha ushlaydi, tovushga munosabat bildiradi.\n"
        "🔹 **3 oy:** Boshini tik ushlaydi, "kula boshlaydi" (guleniyediy).\n"
        "🔹 **6 oy:** O'zi ag'dariladi, yordam bilan o'tiradi, o'yinchoqni ushlaydi.\n"
        "🔹 **9 oy:** Mustaqil o'tiradi, emaklaydi, ilk bo'g'inlarni aytadi.\n"
        "🔹 **12 oy:** Mustaqil yuradi, 3-5 ta sodda so'zlarni aytadi."
    )
    await message.answer(text, parse_mode="Markdown")

# --- 🏥 Klinik Yordam ---
@router.message(F.text.in_([TEXTS["uz"]["menu_clinic"], TEXTS["ru"]["menu_clinic"], TEXTS["en"]["menu_clinic"]]))
async def menu_clinic(message: Message):
    text = (
        "🏥 **KLINIK YORDAM VA DIAGNOSTIKA:**\n\n"
        "🫁 **O'tkir Bronxit va Pnevmoniya:**\n- Havo yetishmasligi, hansirash, auskultatsiyada nam xirillashlar.\n"
        "🩸 **Temir tanqisligi anemiyasi:**\n- Terining oqarishi, darmonsizlik, HB < 110 g/l.\n"
        "🤢 **O'tkir ichak infeksiyalari:**\n- Ko'ngil aynishi, qusish, ich ketishi. Asosiy maqsad — suvsizlanishning oldini olish!"
    )
    await message.answer(text, parse_mode="Markdown")

# --- 🧮 Kalkulyatorlar ---
@router.message(F.text.in_([TEXTS["uz"]["menu_calc"], TEXTS["ru"]["menu_calc"], TEXTS["en"]["menu_calc"]]))
async def menu_calc(message: Message, state: FSMContext):
    await state.set_state(CalcState.waiting_for_weight)
    await message.answer("🧮 **Dori dozasini hisoblash:**\n\nIltimos, bolaning vaznini (kg da) kiriting (Masalan: `12`):", parse_mode="Markdown")

@router.message(CalcState.waiting_for_weight)
async def process_calc_weight(message: Message, state: FSMContext):
    try:
        weight = float(message.text.replace(",", "."))
        if weight <= 0 or weight > 80:
            await message.answer("⚠️ Iltimos, to'g'ri vazn kiriting (masalan: 10 yoki 12.5)!")
            return
            
        p_min = weight * 10
        p_max = weight * 15
        i_min = weight * 5
        i_max = weight * 10

        res = (
            f"⚖️ **Bolanining vazni:** {weight} kg\n\n"
            f"💊 **Paratsetamol (bir martalik doza):**\n- Minimal: **{p_min:.1f} mg**\n- Maksimal: **{p_max:.1f} mg**\n\n"
            f"🧪 **Ibuprofen (bir martalik doza):**\n- Minimal: **{i_min:.1f} mg**\n- Maksimal: **{i_max:.1f} mg**\n\n"
            f"📌 *Siroplar uchun preparat qutisidagi mg/ml nisbatiga e'tibor bering!*"
        )
        await message.answer(res, parse_mode="Markdown")
        await state.clear()
    except ValueError:
        await message.answer("⚠️ Iltimos, faqat raqam kiriting (Masalan: 8.5 yoki 14)!")

# --- 📝 Imtihonga Tayyorlov ---
@router.message(F.text.in_([TEXTS["uz"]["menu_exam"], TEXTS["ru"]["menu_exam"], TEXTS["en"]["menu_exam"]]))
async def menu_exam(message: Message):
    text = (
        "📝 **PED IATRIYADAN SAVOL-JAVOBLAR:**\n\n"
        "❓ **Savol:** Yangi tug'ilgan chaqaloqning normal nafas olish chastotasi daqiqasiga nechtani tashkil qiladi?\n"
        "💡 **Javob:** Daqiqasiga 40-60 marta.\n\n"
        "❓ **Savol:** Kattalashgan katta liqildiq qaysi kasallik belgilari hisoblanadi?\n"
        "💡 **Javob:** Raxit, gidrotsefaliya, gipotireoz."
    )
    await message.answer(text, parse_mode="Markdown")

# --- 📋 Amaliyot va Anamnez ---
@router.message(F.text.in_([TEXTS["uz"]["menu_practice"], TEXTS["ru"]["menu_practice"], TEXTS["en"]["menu_practice"]]))
async def menu_practice(message: Message):
    text = (
        "📋 **ANAMNEZ YIG'ISH VA AMALIYOT SXEMASI:**\n\n"
        "1️⃣ **Pasport qismi:** Ismi, yoshi, tug'ilgan sanasi.\n"
        "2️⃣ **Shikoyatlari:** Asosiy va ikkinchi darajali shikoyatlar.\n"
        "3️⃣ **Kasallik tarixi (Anamnesis morbi):** Qachon va qanday boshlandi?\n"
        "4️⃣ **Hayot tarixi (Anamnesis vitae):** Homiladorlik kechishi, tug'uruq, emlashlar statusi va allergiyalar."
    )
    await message.answer(text, parse_mode="Markdown")

# --- ⚙️ Sozlamalar va Til ---
@router.message(F.text.in_([TEXTS["uz"]["menu_tools"], TEXTS["ru"]["menu_tools"], TEXTS["en"]["menu_tools"]]))
async def menu_tools(message: Message):
    await message.answer(
        "⚙️ **Sozlamalar / Настройки:**\n\nTilni o'zgartirish uchun pastdagi tugmalardan birini tanlang:",
        reply_markup=get_lang_inline()
    )

# --- Render Health Check va Main ---
async def handle(request):
    return web.Response(text="Bolajon Bot 24/7 rejimida muvaffaqiyatli ishlamoqda!")

async def main():
    bot = Bot(token=TOKEN)
    dp = Dispatcher(storage=MemoryStorage())
    dp.include_router(router)
    
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

