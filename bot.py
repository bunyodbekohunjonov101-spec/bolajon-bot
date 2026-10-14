"""PED 5026-A | Pediatr Yordamchisi — aiogram 3 + SQLite + Groq API."""
import asyncio
import json
import logging
import os
import random
import sqlite3
import time
from zoneinfo import ZoneInfo

import httpx
from aiogram import Bot, Dispatcher, F, Router
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
)
from aiogram.utils.keyboard import InlineKeyboardBuilder, ReplyKeyboardBuilder

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("ped")

# Asosiy sozlamalar, Token, AI kalit va Admin ID
BOT_TOKEN = "8868573467:AAEXDgKUtYq3vevusHweKSc3zYox3iaB1PI"
ADMINS = {8675117152}  # Sizning Admin ID raqamingiz

AI_BASE = os.getenv("AI_BASE_URL", "https://api.groq.com/openai/v1").rstrip("/")
AI_KEY = "Gsk_6FFX384HVsmVhwU6DHDlWGdyb3FY8SkqJqb0kbGQ541O2BOGYuag"
AI_MODEL = os.getenv("AI_MODEL", "llama-3.3-70b-versatile")
DB_PATH = os.getenv("DB_PATH", "ped.db")
TZ = ZoneInfo(os.getenv("TZ_NAME", "Asia/Tashkent"))

# ---------------------------------------------------------------- DB INITIATION
_db = sqlite3.connect(DB_PATH, check_same_thread=False)
_db.row_factory = sqlite3.Row
_db.executescript("""
CREATE TABLE IF NOT EXISTS users(
    id INTEGER PRIMARY KEY, 
    name TEXT, 
    rating_on INTEGER DEFAULT 0,
    daily_on INTEGER DEFAULT 0, 
    last_seen INTEGER
);
CREATE TABLE IF NOT EXISTS subjects(
    id INTEGER PRIMARY KEY AUTOINCREMENT, 
    name TEXT UNIQUE
);
CREATE TABLE IF NOT EXISTS materials(
    id INTEGER PRIMARY KEY AUTOINCREMENT, 
    subject_id INTEGER,
    title TEXT, 
    file_id TEXT, 
    body TEXT
);
CREATE TABLE IF NOT EXISTS questions(
    id INTEGER PRIMARY KEY AUTOINCREMENT, 
    subject_id INTEGER,
    q TEXT, a TEXT, b TEXT, c TEXT, d TEXT, 
    correct TEXT, expl TEXT
);
CREATE TABLE IF NOT EXISTS results(
    id INTEGER PRIMARY KEY AUTOINCREMENT, 
    user_id INTEGER, 
    topic TEXT,
    total INTEGER, 
    correct INTEGER, 
    pts INTEGER, 
    ts INTEGER
);
""")
_db.commit()

# ---------------------------------------------------------------- STATES & ROUTER
router = Router()


class TestState(StatesGroup):
  answering = State()


class AdminState(StatesGroup):
  waiting_subject = State()
  waiting_mat_subject = State()
  waiting_mat_title = State()
  waiting_mat_body = State()
  waiting_test_sub = State()
  waiting_test_data = State()


# ---------------------------------------------------------------- AI FUNCTION
async def ask_ai(prompt: str) -> str:
  headers = {
      "Authorization": f"Bearer {AI_KEY}",
      "Content-Type": "application/json",
  }
  payload = {
      "model": AI_MODEL,
      "messages": [
          {
              "role": "system",
              "content": (
                  "Siz tajribali pediatr va tibbiyot assistentisiz. "
                  "Foydalanuvchining tibbiy va o'quv savollariga o'zbek tilida"
                  " aniq, ilmiy va tushunarli javob bering."
              ),
          },
          {"role": "user", "content": prompt},
      ],
      "temperature": 0.5,
  }

  try:
    async with httpx.AsyncClient(timeout=30.0) as client:
      resp = await client.post(
          f"{AI_BASE}/chat/completions", headers=headers, json=payload
      )
      if resp.status_code == 200:
        data = resp.json()
        return data["choices"][0]["message"]["content"]
      else:
        log.error(f"AI Error {resp.status_code}: {resp.text}")
        return "⚠️ Sun'iy intellekt bilan bog'lanishda xatolik yuz berdi."
  except Exception as e:
    log.error(f"AI Exception: {e}")
    return "⚠️ Tarmoq xatoligi yoki so'rov vaqti tugadi."


# ---------------------------------------------------------------- HANDLERS: START & MENU
@router.message(CommandStart())
async def cmd_start(message: Message):
  uid = message.from_user.id
  uname = message.from_user.full_name
  now = int(time.time())

  with _db:
    _db.execute(
        "INSERT INTO users(id, name, last_seen) VALUES(?, ?, ?) ON CONFLICT(id)"
        " DO UPDATE SET name=?, last_seen=?",
        (uid, uname, now, uname, now),
    )

  kb = ReplyKeyboardBuilder()
  kb.button(text="🤖 AIiatr Maslahatchi")
  kb.button(text="📚 Fanlar va Materiallar")
  kb.button(text="✍️ Test ishlash")
  kb.button(text="🏆 Reyting")
  kb.button(text="⚙️ Sozlamalar")
  if uid in ADMINS:
    kb.button(text="🛠 Admin Panel")
  kb.adjust(2, 2, 1, 1)

  await message.answer(
      f"Assalomu alaykum, **{uname}**!\n"
      "Pediatr Yordamchisi botiga xush kelibsiz. Kerakli bo'limni tanlang:",
      reply_markup=kb.as_markup(resize_keyboard=True),
  )


@router.message(F.text == "🤖 AIiatr Maslahatchi")
async def ai_prompt_hint(message: Message):
  await message.answer(
      "🤖 **AIiatr Maslahatchi tayyor!**\n"
      "Tibbiyotga, pediatrchilikka yoki darslaringizga oid istalgan savolingizni"
      " yuboring (masalan: *'Bolalarda bronxit alomatlari qanday?'*)"
  )


@router.message(
    F.text.in_({
        "📚 Fanlar va Materiallar",
        "✍️ Test ishlash",
        "🏆 Reyting",
        "⚙️ Sozlamalar",
        "🛠 Admin Panel",
    })
)
async def menu_router(message: Message, state: FSMContext):
  text = message.text
  uid = message.from_user.id

  if text == "📚 Fanlar va Materiallar":
    cur = _db.execute("SELECT * FROM subjects")
    subs = cur.fetchall()
    if not subs:
      await message.answer(
          "Hozircha fanlar qo'shilmagan. Administrator qo'shishini kuting."
      )
      return

    kb = InlineKeyboardBuilder()
    for s in subs:
      kb.button(text=s["name"], callback_data=f"sub_{s['id']}")
    kb.adjust(1)
    await message.answer(
        "📚 O'qish uchun fanni tanlang:", reply_markup=kb.as_markup()
    )

  elif text == "✍️ Test ishlash":
    cur = _db.execute(
        "SELECT s.id, s.name FROM subjects s JOIN questions q ON s.id = q.subject_id"
        " GROUP BY s.id"
    )
    subs = cur.fetchall()
    if not subs:
      await message.answer(
          "Hozircha testlar bazasi bo'sh. Admin test qo'shishini kuting."
      )
      return

    kb = InlineKeyboardBuilder()
    for s in subs:
      kb.button(text=s["name"], callback_data=f"testsub_{s['id']}")
    kb.adjust(1)
    await message.answer(
        "✍️ Qaysi fan bo'yicha test ishlamoqchisiz?", reply_markup=kb.as_markup()
    )

  elif text == "🏆 Reyting":
    cur = _db.execute(
        "SELECT name, SUM(pts) as total_pts FROM results JOIN users ON"
        " results.user_id = users.id GROUP BY user_id ORDER BY total_pts DESC"
        " LIMIT 10"
    )
    top = cur.fetchall()
    if not top:
      await message.answer(
          "🏆 Hozircha reyting ma'lumotlari mavjud emas. Test ishlab ball"
          " to'plang!"
      )
      return

    msg = "🏆 **Eng yaxshi talabalar reytingi (Top 10):**\n\n"
    for idx, row in enumerate(top, 1):
      msg += f"{idx}. **{row['name']}** — {row['total_pts']} ball\n"
    await message.answer(msg)

  elif text == "⚙️ Sozlamalar":
    await message.answer(
        "⚙️ **Sozlamalar paneli**\nBot versiyasi: `PED 5026-A`\nVaqt mintaqasi:"
        f" `{TZ}`"
    )

  elif text == "🛠 Admin Panel" and uid in ADMINS:
    kb = InlineKeyboardBuilder()
    kb.button(text="➕ Fan qo'shish", callback_data="adm_addsub")
    kb.button(text="📖 Material qo'shish", callback_data="adm_addmat")
    kb.button(text="📝 Test qo'shish", callback_data="adm_addtest")
    kb.adjust(1)
    await message.answer(
        "🛠 **Admin boshqaruv paneli:**", reply_markup=kb.as_markup()
    )


# ---------------------------------------------------------------- TEST SYSTEM
@router.callback_query(F.data.startswith("testsub_"))
async def start_test(callback: CallbackQuery, state: FSMContext):
  sub_id = int(callback.data.split("_")[1])
  cur = _db.execute("SELECT * FROM questions WHERE subject_id = ?", (sub_id,))
  qs = [dict(row) for row in cur.fetchall()]

  if not qs:
    await callback.answer(
        "Bu fanda hozircha testlar yo'q.", show_alert=True
    )
    return

  random.shuffle(qs)
  await state.set_state(TestState.answering)
  await state.update_data(
      questions=qs, index=0, correct_count=0, sub_id=sub_id
  )
  await send_question(callback.message, state)
  await callback.answer()


async def send_question(message: Message, state: FSMContext):
  data = await state.get_data()
  qs = data["questions"]
  idx = data["index"]

  if idx >= len(qs):
    correct = data["correct_count"]
    total = len(qs)
    pts = correct * 10
    uid = message.chat.id

    with _db:
      _db.execute(
          "INSERT INTO results(user_id, topic, total, correct, pts, ts) VALUES"
          " (?, ?, ?, ?, ?, ?)",
          (uid, f"Fan testi", total, correct, pts, int(time.time())),
      )

    await state.clear()
    await message.edit_text(
        "🎉 **Test yakunlandi!**\n\n"
        f"✅ To'g'ri javoblar: {correct} / {total}\n"
        f"⭐ To'plangan ball: +{pts} ball",
        reply_markup=None,
    )
    return

  q = qs[idx]
  kb = InlineKeyboardBuilder()
  kb.button(text=f"A) {q['a']}", callback_data="ans_A")
  kb.button(text=f"B) {q['b']}", callback_data="ans_B")
  if q["c"]:
    kb.button(text=f"C) {q['c']}", callback_data="ans_C")
  if q["d"]:
    kb.button(text=f"D) {q['d']}", callback_data="ans_D")
  kb.adjust(1)

  text = (
      f"❓ **Test {idx + 1}/{len(qs)}**\n\n{q['q']}\n\nJavob variantini tanlang:"
  )
  try:
    await message.edit_text(text, reply_markup=kb.as_markup())
  except Exception:
    await message.answer(text, reply_markup=kb.as_markup())


@router.callback_query(TestState.answering, F.data.startswith("ans_"))
async def check_answer(callback: CallbackQuery, state: FSMContext):
  user_ans = callback.data.split("_")[1]
  data = await state.get_data()
  qs = data["questions"]
  idx = data["index"]
  q = qs[idx]

  correct = q["correct"].strip().upper()
  is_correct = user_ans == correct

  correct_count = data["correct_count"] + (1 if is_correct else 0)
  await state.update_data(index=idx + 1, correct_count=correct_count)

  feedback = (
      f"✅ **To'g'ri!**\n{q['expl']}"
      if is_correct
      else f"❌ **Noto'g'ri!** To'g'ri javob: {correct}\n{q['expl']}"
  )
  await callback.answer(feedback, show_alert=True)
  await send_question(callback.message, state)


# ---------------------------------------------------------------- MATERIALS HANDLERS
@router.callback_query(F.data.startswith("sub_"))
async def show_materials(callback: CallbackQuery):
  sub_id = int(callback.data.split("_")[1])
  cur = _db.execute("SELECT * FROM materials WHERE subject_id = ?", (sub_id,))
  mats = cur.fetchall()

  if not mats:
    await callback.answer(
        "Bu fanda hozircha o'quv materiallari yo'q.", show_alert=True
    )
    return

  kb = InlineKeyboardBuilder()
  for m in mats:
    kb.button(text=m["title"], callback_data=f"mat_{m['id']}")
  kb.adjust(1)
  await callback.message.edit_text(
      "📚 Mavjud materiallar:", reply_markup=kb.as_markup()
  )
  await callback.answer()


@router.callback_query(F.data.startswith("mat_"))
async def read_material(callback: CallbackQuery):
  mat_id = int(callback.data.split("_")[1])
  cur = _db.execute("SELECT * FROM materials WHERE id = ?", (mat_id,))
  mat = cur.fetchone()

  if mat:
    await callback.message.answer(
        f"📖 **{mat['title']}**\n\n{mat['body'] or 'Matn mavjud emas.'}"
    )
  await callback.answer()


# ---------------------------------------------------------------- ADMIN ACTIONS & DIALOGS
@router.callback_query(F.data == "adm_addsub")
async def adm_addsub_prompt(callback: CallbackQuery, state: FSMContext):
  if callback.from_user.id not in ADMINS:
    return
  await state.set_state(AdminState.waiting_subject)
  await callback.message.answer(
      "Yangi fan nomini yuboring (masalan: *Gospital pediatriya*):"
  )
  await callback.answer()


@router.message(AdminState.waiting_subject)
async def adm_save_subject(message: Message, state: FSMContext):
  sub_name = message.text.strip()
  try:
    with _db:
      _db.execute("INSERT INTO subjects(name) VALUES(?)", (sub_name,))
    await message.answer(f"✅ '{sub_name}' fani muvaffaqiyatli qo'shildi!")
  except Exception:
    await message.answer(
        "⚠️ Bunday nomdagi fan allaqachon mavjud yoki xatolik yuz berdi."
    )
  await state.clear()


@router.callback_query(F.data == "adm_addmat")
async def adm_addmat_prompt(callback: CallbackQuery, state: FSMContext):
  if callback.from_user.id not in ADMINS:
    return
  cur = _db.execute("SELECT * FROM subjects")
  subs = cur.fetchall()
  if not subs:
    await callback.answer(
        "Avval fan qo'shishingiz kerak!", show_alert=True
    )
    return

  kb = InlineKeyboardBuilder()
  for s in subs:
    kb.button(text=s["name"], callback_data=f"admsubmat_{s['id']}")
  kb.adjust(1)
  await callback.message.answer(
      "Qaysi fanga material qo'shmoqchisiz?", reply_markup=kb.as_markup()
  )
  await callback.answer()


@router.callback_query(F.data.startswith("admsubmat_"))
async def adm_mat_subject_chosen(callback: CallbackQuery, state: FSMContext):
  sub_id = int(callback.data.split("_")[1])
  await state.update_data(sub_id=sub_id)
  await state.set_state(AdminState.waiting_mat_title)
  await callback.message.answer("Material sarlavhasini yuboring:")
  await callback.answer()


@router.message(AdminState.waiting_mat_title)
async def adm_mat_title_chosen(message: Message, state: FSMContext):
  await state.update_data(title=message.text.strip())
  await state.set_state(AdminState.waiting_mat_body)
  await message.answer("Material matnini (ma'ruzasini) yuboring:")


@router.message(AdminState.waiting_mat_body)
async def adm_mat_body_chosen(message: Message, state: FSMContext):
  data = await state.get_data()
  sub_id = data["sub_id"]
  title = data["title"]
  body = message.text.strip()

  with _db:
    _db.execute(
        "INSERT INTO materials(subject_id, title, body) VALUES(?, ?, ?)",
        (sub_id, title, body),
    )

  await state.clear()
  await message.answer(f"✅ '{title}' materiali muvaffaqiyatli qo'shildi!")


@router.callback_query(F.data == "adm_addtest")
async def adm_addtest_prompt(callback: CallbackQuery, state: FSMContext):
  if callback.from_user.id not in ADMINS:
    return
  cur = _db.execute("SELECT * FROM subjects")
  subs = cur.fetchall()
  if not subs:
    await callback.answer(
        "Avval fan qo'shishingiz kerak!", show_alert=True
    )
    return

  kb = InlineKeyboardBuilder()
  for s in subs:
    kb.button(text=s["name"], callback_data=f"admtestsub_{s['id']}")
  kb.adjust(1)
  await callback.message.answer(
      "Qaysi fanga test qo'shmoqchisiz?", reply_markup=kb.as_markup()
  )
  await callback.answer()


@router.callback_query(F.data.startswith("admtestsub_"))
async def adm_test_sub_chosen(callback: CallbackQuery, state: FSMContext):
  sub_id = int(callback.data.split("_")[1])
  await state.update_data(sub_id=sub_id)
  await state.set_state(AdminState.waiting_test_data)
  await callback.message.answer(
      "Testni quyidagi formatda yuboring:\n\n"
      "Savol: ...\n"
      "A) ...\n"
      "B) ...\n"
      "C) ...\n"
      "D) ...\n"
      "To'g'ri: A (yoki B, C, D)\n"
      "Izoh: ...\n\n"
      "Shu formatda yuboring:"
  )
  await callback.answer()


@router.message(AdminState.waiting_test_data)
async def adm_save_test(message: Message, state: FSMContext):
  data = await state.get_data()
  sub_id = data["sub_id"]
  text = message.text

  try:
    lines = [l.strip() for l in text.split("\n") if l.strip()]
    q_text = lines[0].replace("Savol:", "").strip()
    opt_a = lines[1].split(")")[-1].strip()
    opt_b = lines[2].split(")")[-1].strip()
    opt_c = (
        lines[3].split(")")[-1].strip() if len(lines) > 5 and "C)" in lines[3] else ""
    )
    opt_d = (
        lines[4].split(")")[-1].strip() if len(lines) > 5 and "D)" in lines[4] else ""
    )

    correct = "A"
    expl = "Izoh mavjud emas."
    for l in lines:
      if l.startswith("To'g'ri:"):
        correct = l.replace("To'g'ri:", "").strip().upper()
      if l.startswith("Izoh:"):
        expl = l.replace("Izoh:", "").strip()

    with _db:
      _db.execute(
          "INSERT INTO questions(subject_id, q, a, b, c, d, correct, expl)"
          " VALUES(?, ?, ?, ?, ?, ?, ?, ?)",
          (sub_id, q_text, opt_a, opt_b, opt_c, opt_d, correct, expl),
      )

    await state.clear()
    await message.answer("✅ Test muvaffaqiyatli bazaga qo'shildi!")
  except Exception as e:
    log.error(f"Test parse error: {e}")
    await message.answer(
        "⚠️ Formatda xatolik! Iltimos, namuna bo'yicha qaytadan yuboring."
    )


# ---------------------------------------------------------------- AI FALLBACK FOR MESSAGES
@router.message(F.text)
async def handle_ai_query(message: Message):
  wait_msg = await message.answer("⏳ O'ylayapman va javob tayyorlayapman...")
  ai_response = await ask_ai(message.text)
  await wait_msg.edit_text(ai_response)


# ---------------------------------------------------------------- MAIN APP RUNNER
async def main():
  bot = Bot(token=BOT_TOKEN)
  dp = Dispatcher()
  dp.include_router(router)

  log.info("Bot ishga tushdi...")
  await bot.delete_webhook(drop_pending_updates=True)
  await dp.start_polling(bot)


if __name__ == "__main__":
  asyncio.run(main())
