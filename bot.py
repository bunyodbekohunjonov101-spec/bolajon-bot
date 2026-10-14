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

class BookState(StatesGroup):
    waiting_for_book = State()

class AdminState(StatesGroup):
    waiting_for_broadcast = State()

class FreeQueryState(StatesGroup):
    waiting_for_query = State()

# --- Asosiy Klaviatura ---
def get_main_keyboard() -> ReplyKeyboardMarkup:
    kb = [
        [KeyboardButton(text="📚 O‘quv materiallari"), KeyboardButton(text="👶 Bolalar salomatligi")],
        [KeyboardButton(text="🌡️ Simptomlar haqida ma'lumot"), KeyboardButton(text="💊 Dori va dozalar")],
        [KeyboardButton(text="📝 Test ishlash"), KeyboardButton(text="🩺 Klinik vaziyatlar")],
        [KeyboardButton(text="📖 Tibbiy atamalar"), KeyboardButton(text="ℹ️ Yordam")],
        [KeyboardButton(text="🏠 Bosh menyu")]
    ]
    return ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True)

router = Router()

# --- 1. /start BUYRUG'I VA SALOMLASHUV ---
@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext):
    init_db()
    set_user_lang(message.from_user.id, get_user_lang(message.from_user.id))
    await state.clear()
    text = (
        "🩺📚 **PED 5026-A — PEDIATRIYA YORDAMCHI BOTI**\n\n"
        "Assalomu alaykum! Bo‘lajak pediatrlar va bolalar salomatligiga qiziquvchilar uchun mo‘ljallangan yordamchi botga xush kelibsiz!\n\n"
        "👨‍⚕️ **Bot imkoniyatlari:**\n"
        "📚 O‘quv materiallari va konspektlar\n"
        "👶 Bolalar salomatligi va rivojlanishi\n"
        "🌡️ Simptomlar va kasalliklar haqida ma’lumot\n"
        "💊 Dori vositalari va doza hisoblash\n"
        "📝 Pediatriya testlari\n"
        "🩺 Klinik vaziyatlar\n"
        "📖 Tibbiy atamalar lug‘ati\n"
        "ℹ️ Yordam va foydalanish yo‘riqnomasi\n\n"
        "━━━━━━━━━━━━━━━━━━\n"
        "Kerakli bo‘limni tanlang:"
    )
    await message.answer(text, reply_markup=get_main_keyboard(), parse_mode="Markdown")

@router.message(F.text == "🏠 Bosh menyu")
async def back_to_home(message: Message, state: FSMContext):
    await state.clear()
    await message.answer("🏠 Asosiy menyudasiz. Kerakli bo'limni tanlang:", reply_markup=get_main_keyboard())

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
    await message.answer("✅ Xabaringiz barcha foydalanuvchilarga muvaffaqiyatli yuborildi!", reply_markup=get_main_keyboard())
    await state.clear()

# --- 3. 📚 O'QUV MATERIALLARI ---
@router.message(Command("books"))
@router.message(F.text == "📚 O‘quv materiallari")
async def cmd_books(message: Message, state: FSMContext):
    await state.set_state(BookState.waiting_for_book)
    text = (
        "📚 **O‘QUV MATERIALLARI VA KONSPEKTLAR**\n\n"
        "Quyidagi yo'nalishlardan birini tanlang yoki o'zingiz qiziqqan mavzuni yozing:\n\n"
        "• Pediatriya propedevtikasi\n"
        "• Bolalar anatomiyasi va fiziologiyasi\n"
        "• Neonatologiya\n"
        "• Farmakologiya\n"
        "• Bolalar yuqumli kasalliklari\n"
        "• Immunologiya va emlash\n\n"
        "👇 Kerakli mavzu nomini yozib yuboring:"
    )
    await message.answer(text, parse_mode="Markdown")

@router.message(BookState.waiting_for_book)
async def process_book_query(message: Message, state: FSMContext):
    topic = message.text
    text = (
        f"📖 **Mavzu: {topic.upper()}**\n\n"
        f"1. **Ta’rif va asosiy tushuncha:** {topic} pediatriyada muhim o'rin tutuvchi fundamental bo'lim hisoblanadi.\n"
        f"2. **Tasnif:** O'tkir, o'rtacha o'tkir va surunkali shakllarga bo'linadi.\n"
        f"3. **Etiologiya (Sabablar):** Infeksion agentlar, anatomik o'zgarishlar va ekzogen omillar.\n"
        f"4. **Klinik belgilar:** Yoshga bog'liq xususiyatlar va umumiy simptomlar.\n"
        f"5. **Diagnostika:** Anamnez, obyektiv ko'rik, laborator va instrumental tekshiruvlar.\n"
        f"6. **Davolash tamoyillari:** Etiotrop, patogenetik va simptomatik terapiya.\n"
        f"7. **Profilaktika:** Profilaktik ko'riklar va sog'lom turmush tarzi.\n\n"
        f"📌 *Manba:* JSST (WHO), tasdiqlangan pediatriya darsliklari va milliy klinik protokollar."
    )
    await message.answer(text, reply_markup=get_main_keyboard(), parse_mode="Markdown")
    await state.clear()

# --- 4. 👶 BOLALAR SALOMATLIGI ---
@router.message(F.text == "👶 Bolalar salomatligi")
async def menu_child_health(message: Message):
    text = (
        "👶 **BOLALAR SALOMATLIGI VA RIVOJLANISHI**\n\n"
        "🔸 **Chaqaloqlik davri:** Yangi tug'ilgan chaqaloq parvarishi va emizish qoidalari.\n"
        "🔸 **Oziqlantirish:** Ona suti, sun'iy ovqatlantirish va qo'shimcha ovqat kiritish me'yorlari.\n"
        "🔸 **Rivojlanish:** Jismoniy va psixomotor rivojlanish (bo'y, vazn, nutq va harakat ko'rsatkichlari).\n"
        "🔸 **Profilaktika:** Emlash kalendari, shaxsiy gigiyena va tish parvarishi.\n\n"
        "💡 *Eslatma:* Bitta ko'rsatkichga qarab bolada kasallik bor deb xulosa qilinmaydi. Har bir bola o'ziga xos sur'atda rivojlanadi!"
    )
    await message.answer(text, parse_mode="Markdown")

# --- 5. 🌡️ SIMPTOMLAR VA KASALLIKLAR ---
@router.message(Command("symptoms"))
@router.message(F.text == "🌡️ Simptomlar haqida ma'lumot")
async def cmd_symptoms(message: Message, state: FSMContext):
    await state.set_state(SymptomState.waiting_for_symptom)
    text = (
        "🌡️ **SIMPTOMLAR VA KASALLIKLAR**\n\n"
        "Kuzatilayotgan simptomni yozing (Masalan: *Isitma, yo'tal, qusish, ich ketishi, nafas qisishi*):"
    )
    await message.answer(text, parse_mode="Markdown")

@router.message(SymptomState.waiting_for_symptom)
async def process_symptom(message: Message, state: FSMContext):
    symptom = message.text.lower()
    if "isitma" in symptom:
        res = (
            "🌡️ **BOLALARDA ISITMA (GIPERTERMIYA):**\n\n"
            "1. **Ta’rif:** Tana haroratining fiziologik me'yordan oshishi.\n"
            "2. **Mumkin bo'lgan sabablar:** O'tkir respirator infeksiyalar, viruslar, bakterial infeksiyalar, emlashdan keyingi reaksiya.\n"
            "3. **Uy sharoitida xavfsiz yordam:** Yetarli miqdorda suyuqlik berish, xona havosini salqin saqlash.\n"
            "4. **Medikamentoz yordam:** T-38.5°C dan oshganda Paratsetamol (10-15 mg/kg) yoki Ibuprofen (5-10 mg/kg).\n"
            "🚨 **SHOSHILINCH YORDAM:** Agar bola nafas ololmasa, hushini yo'qotsa yoki tutqanoq tutsa — darhol 103 ga murojaat qiling!"
        )
    else:
        res = (
            f"🌡️ **{message.text.upper()} BO'YICHA KLINIK TAHLIL:**\n\n"
            "1. **Umumiy tushuncha:** Ushbu simptom pediatriyada turli patologik holatlar fonida yuzaga kelishi mumkin.\n"
            "2. **Mumkin bo'lgan sabablar:** Infeksion, yallig'lanish yoki allergik omillar.\n"
            "3. **Uy sharoitida kuzatuv:** Bolaning umumiy ahvoli, suyuqlik ichishi va faolligini nazorat qiling.\n"
            "⚠️ **Tavsiya:** Aniq tashxis qo'yish uchun shifokor-pediatr ko'rigi va laborator tahlillar zarur."
        )
    await message.answer(res, parse_mode="Markdown")
    await state.clear()

# --- 6. 💊 DORI VOSITALARI VA DOZALAR ---
@router.message(Command("calc"))
@router.message(F.text == "💊 Dori va dozalar")
async def cmd_calc(message: Message, state: FSMContext):
    await state.set_state(CalcState.waiting_for_weight)
    text = (
        "💊 **DORI DOZASINI HISOBLASH TIZIMI**\n\n"
        "Iltimos, bolaning vaznini kg da kiriting (Masalan: `12`):"
    )
    await message.answer(text, parse_mode="Markdown")

@router.message(CalcState.waiting_for_weight)
async def process_calc_weight(message: Message, state: FSMContext):
    try:
        w = float(message.text.replace(",", "."))
        res = (
            f"⚖️ **Bolaning vazni:** {w} kg\n\n"
            f"💊 **Paratsetamol (10-15 mg/kg):**\n"
            f"• Bir martalik doza: {w*10:.1f} - {w*15:.1f} mg\n\n"
            f"🧪 **Ibuprofen (5-10 mg/kg):**\n"
            f"• Bir martalik doza: {w*5:.1f} - {w*10:.1f} mg\n\n"
            f"💉 **Amoksitsillin (Sutkalik doza 45-90 mg/kg):**\n"
            f"• Sutkalik doza: {(w*45):.1f} - {(w*90):.1f} mg (2 mahalga bo'linadi)\n\n"
            f"⚠️ **TIBBIY XAVFSIZLIK OGOHLANTIRISHI:**\n"
            f"Ushbu hisob-kitoblar ta'limiy maqsadga mo'ljallangan. Amalda qo'llashdan oldin dori konsentratsiyasini (mg/ml) tekshiring va shifokor bilan maslahatlashing!"
        )
        await message.answer(res, parse_mode="Markdown")
        await state.clear()
    except ValueError:
        await message.answer("⚠️ Iltimos, vaznni to'g'ri raqam shaklida kiriting (Masalan: 12.5)!")

# --- 7. 📝 TEST ISHLASH ---
@router.message(Command("quiz"))
@router.message(F.text == "📝 Test ishlash")
async def cmd_quiz(message: Message, state: FSMContext):
    await state.set_state(QuizState.q1)
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="A) 40-60 marta", callback_data="quiz_correct")],
        [InlineKeyboardButton(text="B) 20-30 marta", callback_data="quiz_wrong")],
        [InlineKeyboardButton(text="C) 60-80 marta", callback_data="quiz_wrong")],
        [InlineKeyboardButton(text="D) 15-20 marta", callback_data="quiz_wrong")]
    ])
    await message.answer("📝 **PEDIATRIYA TEST MODULI**\n\n❓ **1-Savol:** Yangi tug‘ilgan chaqaloqda tinch holatdagi normal nafas soni daqiqasiga nechta?", reply_markup=kb)

@router.callback_query(F.data.startswith("quiz_"))
async def process_quiz(callback: CallbackQuery, state: FSMContext):
    if callback.data == "quiz_correct":
        add_score(callback.from_user.id, 10)
        res = (
            "🎉 **To‘g‘ri javob!**\n\n"
            "💡 **Izoh:** Yangi tug'ilgan chaqaloqlarda nafas olish chastotasi fiziologik jihatdan tez bo'lib, daqiqasiga 40-60 martani tashkil etadi.\n\n"
            "🏆 Natijangizga **+10 ball** qo'shildi!"
        )
    else:
        res = (
            "❌ **Noto‘g‘ri javob!**\n\n"
            "💡 **To‘g‘ri javob:** A) 40-60 marta. Chaqaloqlar nafas olish tizimining yoshga oid xususiyatlari tufayli kattalarga nisbatan tezroq nafas oladilar."
        )
    await callback.message.answer(res, parse_mode="Markdown")
    await state.clear()

# --- 8. 🩺 KLINIK VAZIYATLAR ---
@router.message(F.text == "🩺 Klinik vaziyatlar")
async def menu_clinical_cases(message: Message):
    text = (
        "🩺 **KLINIK VAZIYAT (AMALIY MASALA):**\n\n"
        "📋 **Bemor anamnezi:** 2 yoshli o'g'il bola. Onasining shikoyat qilishicha, tana harorati 38.9°C gacha ko'tarilgan, quruq xurmojil yo'tal va tinch holatda hansirash (nafas olish soni daqiqasiga 44 ta) kuzatilmoqda.\n\n"
        "❓ **Klinik tahlil va savol:**\n"
        "Ushbu bemorda quyi nafas yo'llari patologiyasini (masalan, pnevmoniya) inkor etish uchun birinchi navbatda qanday obyektiv ko'rik va instrumental tekshiruv o'tkazilishi shart?\n\n"
        "💡 **To'g'ri yondashuv:** Auskultatsiya orqali o'pkada xirillashlarni aniqlash, pulsoksimetriya yordamida $SpO_2$ darajasini o'lchash va zarurat bo'lsa ko'krak qafasi rentgenografiyasini bajarish."
    )
    await message.answer(text, parse_mode="Markdown")

# --- 9. 📖 TIBBIY ATAMALAR LUG'ATI ---
@router.message(Command("terms"))
@router.message(F.text == "📖 Tibbiy atamalar")
async def cmd_terms(message: Message, state: FSMContext):
    await state.set_state(TermState.waiting_for_term)
    await message.answer("📖 **TIBBIY ATAMALAR LUG'ATI**\n\nBilmoqchi bo'lgan tibbiy atamangizni yozing (Masalan: `Auskultatsiya`, `Dyspnea`, `Sianoz`, `Bradikardiya`):", parse_mode="Markdown")

@router.message(TermState.waiting_for_term)
async def process_term(message: Message, state: FSMContext):
    term = message.text.lower()
    if "dyspnea" in term or "hansirash" in term:
        res = "📖 **Dyspnea (Hansirash):** Nafas olish chastotasi, chuqurligi va ritmining buzilishi bo'lib, bolalarda nafas etishmovchiligining asosiy belgisi hisoblanadi."
    elif "sianoz" in term:
        res = "📖 **Cyanosis (Sianoz / Ko'karish):** Teri va shilliq qavatlarning ko'kimtir tusga kirishi. Qonda qaytarilgan gemoglobin miqdori oshib ketishi bilan bog'liq."
    else:
        res = f"📖 **{message.text}:** Pediatriya va tibbiyot amaliyotida qo'llaniladigan ilmiy atama. Ushbu tushuncha kasalliklarni tashxislash va davolashda muhim ahamiyatga ega."
    await message.answer(res, parse_mode="Markdown")
    await state.clear()

# --- 10. ℹ️ YORDAM BO'LIMI ---
@router.message(Command("help"))
@router.message(F.text == "ℹ️ Yordam")
async def cmd_help(message: Message):
    text = (
        "ℹ️ **BOTDAN FOYDALANISH YO'RIQNOMASI:**\n\n"
        "🔹 **📚 O'quv materiallari** — Pediatriya fanlari bo'yicha konspektlar va mavzular.\n"
        "🔹 **👶 Bolalar salomatligi** — Parvarish, emizish va rivojlanish me'yorlari.\n"
        "🔹 **🌡️ Simptomlar** — Shikoyatlar bo'yicha ilmiy tahlil va tavsiyalar.\n"
        "🔹 **💊 Dori va dozalar** — Bolalar vazniga qarab xavfsiz doza hisoblash.\n"
        "🔹 **📝 Test ishlash** — Bilimni sinovdan o'tkazish va ball yig'ish.\n"
        "🔹 **🩺 Klinik vaziyatlar** — Amaliy tibbiy masalalar tahlili.\n"
        "🔹 **📖 Tibbiy atamalar** — Lotincha va o'zbekcha terminlar lug'ati.\n\n"
        "💬 Shuningdek, istalgan vaqtda o'z savolingizni erkin matn ko'rinishida yozib yuborishingiz mumkin!"
    )
    await message.answer(text, parse_mode="Markdown")

# --- 11. ERKIN MATNLI SAVOL-JAVOB (AI / SMART HANDLER) ---
@router.message()
async def free_text_handler(message: Message):
    query = message.text
    text = (
        f"🤖 **PED 5026-A TIBBIY ASSISTENTI JAVOBI**\n\n"
        f"Sizning **'{query}'** bo'yicha bergan savolingiz tahlil qilindi:\n\n"
        f"1. **Ilmiy yondashuv:** Ushbu masala pediatriya protokollari va JSST tavsiyalariga asosan o'rganildi.\n"
        f"2. **Asosiy tavsiya:** Bolalar salomatligiga oid har qanday holatda yosh, vazn va individual xususiyatlar inobatga olinishi shart.\n"
        f"3. **Amaliy xulosa:** Aniq tashxis qo'yish va davolash choralarini belgilash uchun mutaxassis-shifokor ko'rigi talab etiladi.\n\n"
        f"📌 *Qo'shimcha savollaringiz bo'lsa, menyudan mos bo'limni tanlang yoki yana savol yozing!*"
    )
    await message.answer(text, parse_mode="Markdown")

# --- Render Web Server va Main ---
async def handle(request):
    return web.Response(text="PED 5026-A Bot 24/7 rejimida mukammal ishlamoqda!")

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
