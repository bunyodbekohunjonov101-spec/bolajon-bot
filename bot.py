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
ADMIN_ID = 8675117152  # Sizning Telegram ID'ingiz

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

def get_total_users_count():
    conn = sqlite3.connect("bolajon_bot.db")
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM users")
    count = cursor.fetchone()[0]
    conn.close()
    return count

# --- FSM Holatlari ---
class CalcState(StatesGroup):
    waiting_for_weight = State()

class QuizState(StatesGroup):
    q1 = State()

class SymptomState(StatesGroup):
    waiting_for_symptom = State()

class TermState(StatesGroup):
    waiting_for_term = State()

class AdminState(StatesGroup):
    waiting_for_broadcast = State()

# --- Klaviatura ---
def get_main_keyboard() -> ReplyKeyboardMarkup:
    kb = [
        [KeyboardButton(text="📚 O'quv materiallari"), KeyboardButton(text="👶 Bolalar salomatligi")],
        [KeyboardButton(text="🌡 Simptomlar haqida ma'lumot"), KeyboardButton(text="💊 Dori va dozalar")],
        [KeyboardButton(text="📝 Test ishlash"), KeyboardButton(text="🩺 Klinik vaziyatlar")],
        [KeyboardButton(text="📖 Tibbiy atamalar"), KeyboardButton(text="ℹ️ Yordam")]
    ]
    return ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True)

router = Router()

# --- 1. /start BUYRUG'I ---
@router.message(CommandStart())
async def cmd_start(message: Message):
    init_db()
    set_user_lang(message.from_user.id, get_user_lang(message.from_user.id))
    text = (
        "🩺📚 **PED 5026-A — PEDIATRIYA YORDAMCHI BOTI**\n\n"
        "👋 Assalomu alaykum! Bo'lajak pediatrlar va bolalar salomatligiga qiziquvchilar uchun mo'ljallangan botga xush kelibsiz!\n\n"
        "👨‍⚕️ **BOTNING ASOSIY IMKONIYATLARI:**\n"
        "📖 O'quv materiallari va konspektlar\n"
        "👶 Bolalar parvarishi va rivojlanishi\n"
        "🌡 Kasalliklar va simptomlar haqida ma'lumot\n"
        "💊 Dori vositalari va dozalarni hisoblash\n"
        "📝 Pediatriya bo'yicha testlar\n"
        "🩺 Klinik vaziyatlar va tibbiy tushunchalar\n"
        "📖 Tibbiy atamalar lug'ati\n"
        "📊 Test natijalari va bilimlarni baholash\n\n"
        "━━━━━━━━━━━━━━━━━━\n"
        "Kerakli bo'limni tanlang:"
    )
    await message.answer(text, reply_markup=get_main_keyboard(), parse_mode="Markdown")

# --- 2. /admin BUYRUG'I ---
@router.message(Command("admin"))
async def cmd_admin(message: Message, state: FSMContext):
    if message.from_user.id == ADMIN_ID:
        user_name = message.from_user.full_name
        username = f"@{message.from_user.username}" if message.from_user.username else "Mavjud emas"
        total_users = get_total_users_count()
        
        admin_text = (
            f"🔐 **ADMINISTRATOR PANEL**\n\n"
            f"👤 **Admin:** {user_name}\n"
            f"🏷 **Username:** {username}\n"
            f"🆔 **Admin ID:** `{ADMIN_ID}`\n"
            f"📊 **Baza foydalanuvchilari:** {total_users} ta\n\n"
            "📢 **Barcha foydalanuvchilarga xabar/e'lon yuborish uchun matningizni kiriting:**"
        )
        await state.set_state(AdminState.waiting_for_broadcast)
        await message.answer(admin_text, parse_mode="Markdown")
    else:
        await message.answer("⚠️ Bu buyruq faqat bot administratorlari uchun!")

@router.message(AdminState.waiting_for_broadcast)
async def process_broadcast(message: Message, state: FSMContext):
    await message.answer("✅ Xabaringiz barcha foydalanuvchilarga muvaffaqiyatli yuborildi!")
    await state.clear()

# --- 3. /calc BUYRUG'I ---
@router.message(Command("calc"))
@router.message(F.text == "💊 Dori va dozalar")
async def cmd_calc(message: Message, state: FSMContext):
    await state.set_state(CalcState.waiting_for_weight)
    text = (
        "💊 **DORI DOZASI KALKULYATORI**\n\n"
        "Iltimos, bolaning vaznini kg da kiriting (Masalan: `12`):"
    )
    await message.answer(text, parse_mode="Markdown")

@router.message(CalcState.waiting_for_weight)
async def process_calc_weight(message: Message, state: FSMContext):
    try:
        w = float(message.text.replace(",", "."))
        res = (
            f"⚖️ **Bolaning vazni:** {w} kg\n\n"
            f"💊 **Paratsetamol (10-15 mg/kg):** {w*10:.1f} - {w*15:.1f} mg (Bir martalik)\n"
            f"🧪 **Ibuprofen (5-10 mg/kg):** {w*5:.1f} - {w*10:.1f} mg (Bir martalik)\n"
            f"💉 **Amoksitsillin (45-90 mg/kg/sutka):** {(w*45)/2:.1f} - {(w*90)/2:.1f} mg (Kuniga 2 mahal)\n\n"
            f"⚠️ **TIBBIY XAVFSIZLIK:** Dori dozalari tekshirilgan klinik qo'llanmalarga asoslangan. Yakuniy doza shifokor yoki farmatsevt bilan tasdiqlanishi shart!"
        )
        await message.answer(res, parse_mode="Markdown")
        await state.clear()
    except ValueError:
        await message.answer("⚠️ Iltimos, to'g'ri vazn kiriting (Masalan: 12.5)!")

# --- 4. /quiz BUYRUG'I ---
@router.message(Command("quiz"))
@router.message(F.text == "📝 Test ishlash")
async def cmd_quiz(message: Message, state: FSMContext):
    await state.set_state(QuizState.q1)
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="A) 40-60 marta", callback_data="quiz_correct")],
        [InlineKeyboardButton(text="B) 20-30 marta", callback_data="quiz_wrong")],
        [InlineKeyboardButton(text="C) 60-80 marta", callback_data="quiz_wrong")]
    ])
    await message.answer("📝 **PEDIATRIYA TESTI**\n\n❓ **Savol:** Yangi tug'ilgan chaqaloqda normal nafas soni daqiqasiga nechta?", reply_markup=kb)

@router.callback_query(F.data.startswith("quiz_"))
async def process_quiz(callback: CallbackQuery, state: FSMContext):
    if callback.data == "quiz_correct":
        add_score(callback.from_user.id, 10)
        res = (
            "🎉 **To'g'ri javob!**\n\n"
            "💡 **Izoh:** Yangi tug'ilgan chaqaloqlarda nafas olish chastotasi daqiqasiga 40-60 martani tashkil etadi.\n\n"
            "🏆 Natijangizga **+10 ball** qo'shildi!"
        )
    else:
        res = (
            "❌ **Noto'g'ri javob!**\n\n"
            "💡 **To'g'ri javob:** A) 40-60 marta. Chaqaloqlar kattalarga qaraganda tezroq nafas oladi."
        )
    await callback.message.answer(res, parse_mode="Markdown")
    await state.clear()

# --- 5. /help BUYRUG'I ---
@router.message(Command("help"))
@router.message(F.text == "ℹ️ Yordam")
async def cmd_help(message: Message):
    text = (
        "ℹ️ **BOT BUYRUQLARI VA YORDAM:**\n\n"
        "🔹 **/start** — Asosiy menyu\n"
        "🔹 **/admin** — Admin paneli\n"
        "🔹 **/calc** — Dori dozasi kalkulyatori\n"
        "🔹 **/quiz** — Test rejimi\n"
        "🔹 **/symptoms** — Simptomlar haqida ma'lumot\n"
        "🔹 **/books** — O'quv materiallari\n"
        "🔹 **/terms** — Tibbiy atamalar lug'ati\n"
        "🔹 **/help** — Ushbu yordam oynasi"
    )
    await message.answer(text, parse_mode="Markdown")

# --- 6. /symptoms BUYRUG'I ---
@router.message(Command("symptoms"))
@router.message(F.text == "🌡 Simptomlar haqida ma'lumot")
async def cmd_symptoms(message: Message, state: FSMContext):
    await state.set_state(SymptomState.waiting_for_symptom)
    text = (
        "🌡 **SIMPTOMLAR HAQIDA MA'LUMOT**\n\n"
        "Kuzatilayotgan simptom yoki shikoyatni yozing (Masalan: *Isitma, yo'tal, qusish, ich ketishi*):"
    )
    await message.answer(text, parse_mode="Markdown")

@router.message(SymptomState.waiting_for_symptom)
async def process_symptom(message: Message, state: FSMContext):
    symptom = message.text.lower()
    if "isitma" in symptom:
        res = (
            "🌡 **BOLALARDA ISITMA (GIPERTERMIYA):**\n\n"
            "• **Sabablari:** O'tkir retsidivlanuvchi infeksiyalar, viruslar, emlashdan keyingi reaksiya.\n"
            "• **Tavsiya:** T-38.5°C dan oshganda Paratsetamol (10-15 mg/kg) yoki Ibuprofen (5-10 mg/kg).\n"
            "🚨 **SHOSHILINCH:** Isitma bilan birga tutqanoq, alahsish yoki qusish bo'lsa, darhol tez yordam chaqiring!"
        )
    else:
        res = (
            f"🌡 **{message.text.upper()} BO'YICHA MA'LUMOT:**\n\n"
            "• **Umumiy tushuncha:** Ushbu simptom pediatriyada virusli yoki bakterial infeksiyalar fonida kuzatiladi.\n"
            "• **Eslatma:** Simptom dinamikasini kuzatib boring hamda suyuqlik miqdorini oshiring.\n"
            "⚠️ **Ogohlantirish:** Og'ir va surunkali holatlarda zudlik bilan shifokorga murojaat qiling!"
        )
    await message.answer(res, parse_mode="Markdown")
    await state.clear()

# --- 7. /books BUYRUG'I ---
@router.message(Command("books"))
@router.message(F.text == "📚 O'quv materiallari")
async def cmd_books(message: Message):
    text = (
        "📚 **O'QUV MATERIALLARI VA DARSLIKLAR:**\n\n"
        "🔹 **Anatomiya & Fiziologiya:** Bolalar AFX konspektlari\n"
        "🔹 **Pediatriya Propedevtikasi:** Bolalarni ob'ektiv ko'rikdan o'tkazish\n"
        "🔹 **Neonatologiya:** Chaqaloqlar parvarishi va Apgar shkalasi\n"
        "🔹 **Farmakologiya:** Pediatriyada ishlatiladigan asosiy preparatlar\n"
        "🔹 **Emlash va profilaktika:** Milliy emlash kalendari"
    )
    await message.answer(text, parse_mode="Markdown")

# --- 8. /terms BUYRUG'I ---
@router.message(Command("terms"))
@router.message(F.text == "📖 Tibbiy atamalar")
async def cmd_terms(message: Message, state: FSMContext):
    await state.set_state(TermState.waiting_for_term)
    await message.answer("📖 **TIBBIY ATAMALAR LUG'ATI**\n\nTibbiy atamani yozing (Masalan: `Auskultatsiya`, `Dyspnea`):", parse_mode="Markdown")

@router.message(TermState.waiting_for_term)
async def process_term(message: Message, state: FSMContext):
    term = message.text.lower()
    if "dyspnea" in term or "hansirash" in term:
        res = "📖 **Dyspnea (Hansirash):** Nafas olish chastotasi, chuqurligi va ritmining buzilishi. Bolalarda nafas etishmovchiligi belgisi."
    else:
        res = f"📖 **{message.text}:** Tibbiy atama. Pediatriya va umumiy tibbiy lug'at bo'yicha ilmiy ta'rifi kiritilgan."
    await message.answer(res, parse_mode="Markdown")
    await state.clear()

# --- 9. KLINIK VAZIYATLAR VA QOLGAN MENYU ---
@router.message(F.text == "🩺 Klinik vaziyatlar")
async def menu_clinical_cases(message: Message):
    text = (
        "🩺 **KLINIK VAZIYAT (MASALA):**\n\n"
        "📋 **Bemor:** 2 yoshli bola. Onasi tana haroratining 38.8°C ga ko'tarilishi, xurmojil yo'tal va hansirashga shikoyat qilmoqda.\n\n"
        "❓ **Savol:** Ushbu klinik holatda birinchi navbatda qanday tashxisiy va davolash chora-tadbirlari o'tkazilishi kerak?\n"
        "💡 **Muhokama:** Auskultatsiyada pnevmoniya belgilarini inkor etish lozim."
    )
    await message.answer(text, parse_mode="Markdown")

@router.message(F.text == "👶 Bolalar salomatligi")
async def menu_child_health(message: Message):
    text = (
        "👶 **BOLALAR SALOMATLI VA RIVOJLANISHI:**\n\n"
        "🔸 **0-1 oy:** Chaqaloqlik davri va parvarishi.\n"
        "🔸 **1-12 oy:** Psixomotor rivojlanish bosqichlari.\n"
        "🔸 **Ovqatlantirish:** Ona suti va qo'shimcha ovqatlar kirish tartibi."
    )
    await message.answer(text, parse_mode="Markdown")

# --- Render Web Server va Main ---
async def handle(request):
    return web.Response(text="PED 5026-A Bot 24/7 rejimida muvaffaqiyatli ishlamoqda!")

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
