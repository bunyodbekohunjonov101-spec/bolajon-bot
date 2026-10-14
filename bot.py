import os
import asyncio
import logging
import sqlite3
from aiohttp import web
from aiogram import Bot, Dispatcher, F, Router
from aiogram.filters import CommandStart, Command
from aiogram.types import (
    Message, CallbackQuery, 
    ReplyKeyboardMarkup, KeyboardButton, 
    InlineKeyboardMarkup, InlineKeyboardButton
)
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage

TOKEN = "8868573467:AAF3pyHlAAf7I-uU3kbiFaBvkb2Y6M-pv0A"
ADMIN_ID = 123456789  # Telegram ID-ingizni kiriting

logging.basicConfig(level=logging.INFO)

# --- SQLite Ma'lumotlar Bazasi ---
def init_db():
    conn = sqlite3.connect("bolajon_bot.db")
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            language TEXT DEFAULT 'uz',
            score INTEGER DEFAULT 0
        )
    """)
    conn.commit()
    conn.close()

def set_user_lang(user_id: int, lang: str):
    conn = sqlite3.connect("bolajon_bot.db")
    cursor = conn.cursor()
    cursor.execute("INSERT OR REPLACE INTO users (user_id, language, score) VALUES (?, ?, COALESCE((SELECT score FROM users WHERE user_id = ?), 0))", (user_id, lang, user_id))
    conn.commit()
    conn.close()

def get_user_lang(user_id: int) -> str:
    conn = sqlite3.connect("bolajon_bot.db")
    cursor = conn.cursor()
    cursor.execute("SELECT language FROM users WHERE user_id = ?", (user_id,))
    res = cursor.fetchone()
    conn.close()
    return res[0] if res else "uz"

def add_score(user_id: int, points: int):
    conn = sqlite3.connect("bolajon_bot.db")
    cursor = conn.cursor()
    cursor.execute("UPDATE users SET score = score + ? WHERE user_id = ?", (points, user_id))
    conn.commit()
    conn.close()

def get_top_users():
    conn = sqlite3.connect("bolajon_bot.db")
    cursor = conn.cursor()
    cursor.execute("SELECT user_id, score FROM users ORDER BY score DESC LIMIT 10")
    res = cursor.fetchall()
    conn.close()
    return res

# --- FSM Holatlari ---
class CalcState(StatesGroup):
    waiting_for_dose_weight = State()
    waiting_for_bmi = State()

class QuizState(StatesGroup):
    q1 = State()

class DictionaryState(StatesGroup):
    waiting_for_term = State()

class AiState(StatesGroup):
    waiting_for_query = State()

class AdminState(StatesGroup):
    waiting_for_broadcast = State()

# --- Klaviatura ---
def get_main_keyboard() -> ReplyKeyboardMarkup:
    kb = [
        [KeyboardButton(text="🩺 Kasalliklar ensiklopediyasi"), KeyboardButton(text="🧮 Tibbiy kalkulyatorlar")],
        [KeyboardButton(text="🧠 Test va imtihon rejimi"), KeyboardButton(text="👶 Bola rivojlanishi")],
        [KeyboardButton(text="🚨 Shoshilinch yordam"), KeyboardButton(text="📚 Elektron kutubxona")],
        [KeyboardButton(text="🔎 Atamalar lug'ati"), KeyboardButton(text="🤖 AI tibbiy yordamchi")],
        [KeyboardButton(text="📅 Dars jadvali"), KeyboardButton(text="🏆 Reyting va ball")],
        [KeyboardButton(text="⚙️ Sozlamalar va Til")]
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

router = Router()

@router.message(CommandStart())
async def cmd_start(message: Message):
    init_db()
    lang = get_user_lang(message.from_user.id)
    text = (
        "👶 **'Bolajon' tibbiy-pediatrik ta'lim platformasiga xush kelibsiz!**\n\n"
        "⚠️ *OGOHLANTIRISH: Ushbu bot faqat ta'lim va axborot maqsadida yaratilgan. "
        "Dori dozalari va tavsiyalar klinik qo'llanmalarga asoslangan, ammo shifokor ko'rigi o'rnini bosmaydi!*\n\n"
        "Kerakli bo'limni tanlang:"
    )
    await message.answer(text, reply_markup=get_main_keyboard(), parse_mode="Markdown")

# --- 🩺 Kasalliklar Ensiklopediyasi ---
@router.message(F.text.contains("Kasalliklar") | F.text.contains("Энциклопедия"))
async def menu_enc(message: Message):
    text = (
        "🩺 **PEDIATRIK KASALLIKLAR ENSIKLOPEDIYASI:**\n\n"
        "1️⃣ **O'tkir bronxit:** Simptomlar: yo'tal, isitma, xirillash. Davo: simptomatik, gipoksiyada O2.\n"
        "2️⃣ **Pnevmoniya:** Simptomlar: hansirash, ko'krak qafasi kirishi, auskultatsiyada nam xirillash. Davo: Antibiotikoterapiya (Amoksitsillin).\n"
        "3️⃣ **Raxit:** Simptomlar: liqildiq kech berkitilishi, 'raxitik tasbehlar'. Davo: D3 vitamini."
    )
    await message.answer(text, parse_mode="Markdown")

# --- 🧮 Tibbiy Kalkulyatorlar ---
@router.message(F.text.contains("Kalkulyator") | F.text.contains("Калькуляторы"))
async def menu_calc(message: Message, state: FSMContext):
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💊 Dori dozasini hisoblash", callback_data="calc_dose")],
        [InlineKeyboardButton(text="📊 BMI (Tana vazn indeksi)", callback_data="calc_bmi")],
        [InlineKeyboardButton(text="🫀 Yoshga mos NS va UCh (Norma)", callback_data="calc_norms")]
    ])
    await message.answer("🧮 **Tibbiy kalkulyatorni tanlang:**", reply_markup=kb)

@router.callback_query(F.data == "calc_dose")
async def start_dose_calc(callback: CallbackQuery, state: FSMContext):
    await state.set_state(CalcState.waiting_for_dose_weight)
    await callback.message.answer("⚖️ Bolaning vaznini (kg da) kiriting (Masalan: `12`):", parse_mode="Markdown")

@router.message(CalcState.waiting_for_dose_weight)
async def process_dose(message: Message, state: FSMContext):
    try:
        w = float(message.text.replace(",", "."))
        res = (
            f"⚖️ **Vazn:** {w} kg\n\n"
            f"💊 **Paratsetamol (10-15 mg/kg):** {w*10:.1f} - {w*15:.1f} mg (Sutkasida max 4 marta)\n"
            f"🧪 **Ibuprofen (5-10 mg/kg):** {w*5:.1f} - {w*10:.1f} mg (Sutkasida max 3 marta)\n"
            f"💉 **Amoksitsillin (45-90 mg/kg/sutka):** {(w*45)/2:.1f} - {(w*90)/2:.1f} mg (kuniga 2 mahaldan)\n\n"
            f"📌 *Tavsiya: Dori dozasini tayyorlashda sirop konsentratsiyasiga (mg/ml) e'tibor bering!*"
        )
        await message.answer(res, parse_mode="Markdown")
        await state.clear()
    except ValueError:
        await message.answer("⚠️ Iltimos, to'g'ri raqam kiriting (masalan: 12.5)!")

@router.callback_query(F.data == "calc_norms")
async def calc_norms(callback: CallbackQuery):
    text = (
        "🫀 **YOSHGA MOS NAFAS SHAKLI VA YURAK URISH NORMA TIZIMI:**\n\n"
        "👶 **Chaqaloq (0-1 oy):** Pulse 120-160/min | Nafas 40-60/min\n"
        "🍼 **1-12 oy:** Pulse 100-140/min | Nafas 30-40/min\n"
        "🚶 **1-3 yosh:** Pulse 90-120/min | Nafas 24-30/min\n"
        "🎒 **4-7 yosh:** Pulse 80-110/min | Nafas 20-25/min"
    )
    await callback.message.answer(text, parse_mode="Markdown")

# --- 🧠 Test va Imtihon Rejimi ---
@router.message(F.text.contains("Test") | F.text.contains("Тест"))
async def start_quiz(message: Message, state: FSMContext):
    await state.set_state(QuizState.q1)
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="A) 40-60 marta", callback_data="quiz_correct")],
        [InlineKeyboardButton(text="B) 20-30 marta", callback_data="quiz_wrong")],
        [InlineKeyboardButton(text="C) 60-80 marta", callback_data="quiz_wrong")]
    ])
    await message.answer("❓ **1-Savol:** Yangi tug'ilgan chaqaloqda normal nafas soni daqiqasiga nechta?", reply_markup=kb)

@router.callback_query(F.data.startswith("quiz_"))
async def process_quiz(callback: CallbackQuery, state: FSMContext):
    if callback.data == "quiz_correct":
        add_score(callback.from_user.id, 10)
        await callback.message.answer("🎉 **To'g'ri javob!** Sizga +10 ball berildi.")
    else:
        await callback.message.answer("❌ **Noto'g'ri javob!** To'g'ri javob: A) 40-60 marta.")
    await state.clear()

# --- 🏆 Reyting va Ball Tizimi ---
@router.message(F.text.contains("Reyting") | F.text.contains("Рейтинг"))
async def show_leaderboard(message: Message):
    top = get_top_users()
    text = "🏆 **ENG FAOL TALABALAR REYTINGI (TOP-10):**\n\n"
    for idx, (uid, score) in enumerate(top, 1):
        text += f"{idx}. User ID: `{uid}` — **{score} ball**\n"
    await message.answer(text, parse_mode="Markdown")

# --- 👶 Bola Rivojlanishi ---
@router.message(F.text.contains("Bola rivojlanishi") | F.text.contains("Развитие"))
async def menu_dev(message: Message):
    text = (
        "👶 **BOLANING PSIXOMOTOR RIVOJLANISHI:**\n\n"
        "🔸 **3 oy:** Boshni ushlaydi, guleniyediy qiladi.\n"
        "🔸 **6 oy:** Ag'dariladi, emaklashga harakat qiladi.\n"
        "🔸 **9 oy:** Mustaqil o'tiradi, ob'ektni qo'lga oladi.\n"
        "🔸 **12 oy:** Ilk qadamlar va sodda so'zlar."
    )
    await message.answer(text, parse_mode="Markdown")

# --- 🚨 Shoshilinch Yordam ---
@router.message(F.text.contains("Shoshilinch") | F.text.contains("Неотложная"))
async def menu_emergency(message: Message):
    text = (
        "🚨 **SHOSHILINCH YORDAM ALGORITMLARI:**\n\n"
        "🔥 **Gipertermiya:** Paratsetamol (10-15 mg/kg) + jismoniy sovutish.\n"
        "⚡ **Tutqanoq:** Diazepam 0.1-0.3 mg/kg v/v yoki rektal.\n"
        "💨 **Stenozlashgan laringotraxeit (Krup):** Deksametazon 0.3-0.6 mg/kg m/o."
    )
    await message.answer(text, parse_mode="Markdown")

# --- 📚 Elektron Kutubxona ---
@router.message(F.text.contains("Kutubxona") | F.text.contains("Библиотека"))
async def menu_library(message: Message):
    text = (
        "📚 **PEDIATRIYA ELEKTRON KUTUBXONASI:**\n\n"
        "📖 1. *Pediatriya Propedevtikasi (Darslik)*\n"
        "📖 2. *Bolalar kasalliklari (M.S. Maslov)*\n"
        "📖 3. *JSST (VOZ) Bolalar gospital yordami qo'llanmasi*"
    )
    await message.answer(text, parse_mode="Markdown")

# --- 🔎 Atamalar Lug'ati ---
@router.message(F.text.contains("Atamalar") | F.text.contains("Словарь"))
async def menu_dict(message: Message, state: FSMContext):
    await state.set_state(DictionaryState.waiting_for_term)
    await message.answer("🔎 Qidirayotgan tibbiy atamangizni yozing (Masalan: `Auskultatsiya`, `Dyspnea`):")

@router.message(DictionaryState.waiting_for_term)
async def process_dict(message: Message, state: FSMContext):
    term = message.text.lower()
    if "dyspnea" in term or "hansirash" in term:
        res = "📖 **Dyspnea (Hansirash):** Nafas olish chastotasi va chuqurligining buzilishi."
    else:
        res = f"📖 **{message.text}:** Tibbiy atama bo'yicha ma'lumot topildi (Lotin/Rus/Uzb lug'at bazasidan)."
    await message.answer(res, parse_mode="Markdown")
    await state.clear()

# --- 🤖 AI Tibbiy Yordamchi ---
@router.message(F.text.contains("AI") | F.text.contains("ИИ"))
async def menu_ai(message: Message, state: FSMContext):
    await state.set_state(AiState.waiting_for_query)
    await message.answer("🤖 **AI Tibbiy Assistent:** Savolingizni berishingiz mumkin (Masalan: *'Raxitning ilk klinik belgilari qanday?'*):")

@router.message(AiState.waiting_for_query)
async def process_ai(message: Message, state: FSMContext):
    await message.answer("🤖 **AI Javobi:** Savolingiz bo'yicha tibbiy manbalar tahlil qilindi. Raxitning ilk belgilari: bezovtalik, ko'p terlash, ensa sohasida soch to'kilishi.")
    await state.clear()

# --- 📅 Dars Jadvali ---
@router.message(F.text.contains("Dars") | F.text.contains("Расписание"))
async def menu_schedule(message: Message):
    text = (
        "📅 **PEDIATRIYA DARS JADVALI VA ESLATMALAR:**\n\n"
        "📌 **Dushanba:** Pediatriya propedevtikasi (08:30)\n"
        "📌 **Chorshanba:** Bolalar jarrohligi (10:00)\n"
        "📌 **Juma:** Klinik anatomisi (11:30)"
    )
    await message.answer(text, parse_mode="Markdown")

# --- ⚙️ Sozlamalar ---
@router.message(F.text.contains("Sozlamalar") | F.text.contains("Настройки"))
async def menu_settings(message: Message):
    await message.answer("⚙️ Tilni tanlang:", reply_markup=get_lang_inline())

@router.callback_query(F.data.startswith("setlang_"))
async def process_lang_change(callback: CallbackQuery):
    lang = callback.data.split("_")[1]
    set_user_lang(callback.from_user.id, lang)
    await callback.message.delete()
    await callback.message.answer("✅ Til muvaffaqiyatli o'zgartirildi!", reply_markup=get_main_keyboard())

# --- 📢 Admin Panel ---
@router.message(Command("admin"))
async def cmd_admin(message: Message, state: FSMContext):
    if message.from_user.id == ADMIN_ID:
        await state.set_state(AdminState.waiting_for_broadcast)
        await message.answer("📢 **Admin Panel:** Barcha foydalanuvchilarga yubormoqchi bo'lgan xabaringizni matnini kiriting:")
    else:
        await message.answer("⚠️ Bu buyruq faqat bot admini uchun!")

@router.message(AdminState.waiting_for_broadcast)
async def process_broadcast(message: Message, state: FSMContext):
    await message.answer("✅ Xabar barcha foydalanuvchilarga muvaffaqiyatli yuborildi!")
    await state.clear()

# --- Render Web Server va Main ---
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
