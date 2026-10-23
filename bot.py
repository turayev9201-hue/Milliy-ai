import asyncio
import logging
import sqlite3
import datetime
import os
from dotenv import load_dotenv
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from openai import AsyncOpenAI

# .env faylini yuklash
load_dotenv()

# --- SOZLAMALAR ---
BOT_TOKEN = os.getenv("BOT_TOKEN")
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY")
ADMIN_ID = 8870374351
WEBSITE_URL = "https://jasurbekturaev.com/"
BANNER_FILE = "/root/milliy_ai_banner.txt"

# --- AI SOZLAMASI ---
client = AsyncOpenAI(api_key=DEEPSEEK_API_KEY, base_url="https://api.deepseek.com")
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# --- BAZA ---
conn = sqlite3.connect('milliy_ai_users.db', check_same_thread=False)
cursor = conn.cursor()
cursor.execute('''CREATE TABLE IF NOT EXISTS users 
                  (user_id INTEGER PRIMARY KEY, 
                   username TEXT,
                   first_name TEXT,
                   last_usage_date TEXT, 
                   daily_count INTEGER DEFAULT 0, 
                   premium_until TEXT DEFAULT NULL,
                   ai_mode TEXT DEFAULT 'v3',
                   total_requests INTEGER DEFAULT 0,
                   notified_expired INTEGER DEFAULT 0)''')
# Ustunlarni tekshirish va qo'shish (eski baza uchun)
columns = [info[1] for info in cursor.execute("PRAGMA table_info(users)").fetchall()]
for col, col_type in [('username', 'TEXT'), ('first_name', 'TEXT'), ('total_requests', 'INTEGER DEFAULT 0')]:
    if col not in columns:
        cursor.execute(f"ALTER TABLE users ADD COLUMN {col} {col_type}")
conn.commit()

user_contexts = {}

class PremiumState(StatesGroup):
    waiting_for_receipt = State()

class AdminState(StatesGroup):
    waiting_for_broadcast = State()
    waiting_for_premium_id = State()

# --- YORDAMCHI FUNKSIYALAR ---
def get_user_data(user_id):
    cursor.execute("SELECT last_usage_date, daily_count, premium_until, ai_mode FROM users WHERE user_id = ?", (user_id,))
    user = cursor.fetchone()
    if not user:
        today = datetime.date.today().strftime("%Y-%m-%d")
        cursor.execute("INSERT OR IGNORE INTO users (user_id, last_usage_date, daily_count) VALUES (?, ?, ?)", (user_id, today, 0))
        conn.commit()
        return today, 0, None, 'v3'
    return user

def is_premium(premium_until):
    if not premium_until: return False
    try:
        prem_date = datetime.datetime.strptime(premium_until, "%Y-%m-%d").date()
        return prem_date >= datetime.date.today()
    except:
        return False

def split_message(text, limit=4000):
    return [text[i:i+limit] for i in range(0, len(text), limit)]

def get_main_inline_kb(ai_mode, is_prem):
    mode_text = "🧠 Aqlli (R1)" if ai_mode == 'r1' else "⚡️ Oddiy (V3)"
    prem_btn_text = "💎 Premium: Faol ✅" if is_prem else "💎 Premium olish (Cheksiz)"
    
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🧹 Suhbatni tozalash", callback_data="clear_chat"),
         InlineKeyboardButton(text=f"Rejim: {mode_text}", callback_data="switch_mode")],
        [InlineKeyboardButton(text=prem_btn_text, callback_data="get_premium")],
        [InlineKeyboardButton(text="🌐 Muallif bilan tanishish", url=WEBSITE_URL)]
    ])

def get_admin_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📊 Yangilash", callback_data="admin_refresh"),
         InlineKeyboardButton(text="📢 Xabar tarqatish", callback_data="admin_broadcast")],
        [InlineKeyboardButton(text="💎 Premium berish", callback_data="admin_give_prem")]
    ])

# --- START BUYRUG'I ---
@dp.message(Command("start"))
async def cmd_start(message: Message):
    user_id = message.from_user.id
    user_contexts[user_id] = []
    
    # Foydalanuvchi ma'lumotlarini yangilash
    cursor.execute("UPDATE users SET username = ?, first_name = ? WHERE user_id = ?", 
                   (message.from_user.username, message.from_user.first_name, user_id))
    conn.commit()

    _, _, premium_until, ai_mode = get_user_data(user_id)
    is_prem = is_premium(premium_until)
    
    if is_prem:
        status_text = "┌ 💎 <b>Status:</b> PREMIUM (Cheksiz)\n└ <i>Barcha imkoniyatlar to'liq ochiq!</i>"
    else:
        status_text = "┌ 🆓 <b>Status:</b> BEPUL REJIM\n└ <i>Kuniga 5 ta bepul savol berishingiz mumkin</i>"
    
    text = (
        f"<b>Assalomu alaykum, {message.from_user.first_name}!</b> 👋\n\n"
        "🤖 Men <b>MILLIY AI</b> — O'zbek tilidagi eng ilg'or va aqlli sun'iy intellektman.\n\n"
        "<blockquote>⚡️ <b>V3 Rejim:</b> Kundalik savollar, matn yozish va tarjima uchun tezkor javoblar.\n"
        "🧠 <b>R1 Rejim:</b> Murakkab kod, matematika va mantiqiy savollar uchun chuqur o'ylash.</blockquote>\n\n"
        f"{status_text}\n\n"
        "👇 <i>Boshlash uchun shunchaki savolingizni yozing!</i>"
    )
    
    kb = get_main_inline_kb(ai_mode, is_prem)
    
    if os.path.exists(BANNER_FILE):
        with open(BANNER_FILE, 'r') as f:
            banner_id = f.read().strip()
        try:
            await message.answer_photo(photo=banner_id, caption=text, parse_mode="HTML", reply_markup=kb)
            return
        except: pass
        
    await message.answer(text, parse_mode="HTML", reply_markup=kb)

# --- ADMIN PANEL ---
@dp.message(Command("admin"))
async def cmd_admin(message: Message):
    if message.from_user.id != ADMIN_ID: return
    
    today = datetime.date.today().strftime("%Y-%m-%d")
    total_users = cursor.execute("SELECT COUNT(*) FROM users").fetchone()[0]
    prem_users = cursor.execute("SELECT COUNT(*) FROM users WHERE premium_until >= ?", (today,)).fetchone()[0]
    total_reqs = cursor.execute("SELECT SUM(total_requests) FROM users").fetchone()[0] or 0
    today_reqs = cursor.execute("SELECT SUM(daily_count) FROM users WHERE last_usage_date = ?", (today,)).fetchone()[0] or 0
    today_users = cursor.execute("SELECT COUNT(*) FROM users WHERE last_usage_date = ?", (today,)).fetchone()[0]

    text = (
        "👨‍💻 <b>ADMIN PANEL</b>\n\n"
        "📊 <b>Statistika:</b>\n"
        f"├ 👥 Jami obunachilar: <b>{total_users}</b> ta\n"
        f"├ 💎 Premium obunachilar: <b>{prem_users}</b> ta\n"
        f"├ 🟢 Bugun faol bo'lganlar: <b>{today_users}</b> ta\n"
        f"├ ⚡️ Jami AI so'rovlar: <b>{total_reqs}</b> ta\n"
        f"└ 📅 Bugungi so'rovlar: <b>{today_reqs}</b> ta\n\n"
        "⚙️ <b>Boshqaruv:</b>"
    )
    await message.answer(text, parse_mode="HTML", reply_markup=get_admin_kb())

@dp.callback_query(F.data == "admin_refresh")
async def admin_refresh(callback: CallbackQuery):
    await callback.message.delete()
    await cmd_admin(callback.message)
    await callback.answer("Statistika yangilandi!")

@dp.callback_query(F.data == "admin_broadcast")
async def admin_broadcast_start(callback: CallbackQuery, state: FSMContext):
    await callback.message.answer("📢 Barcha obunachilarga yuboriladigan xabarni kiriting (Matn, rasm yoki video):")
    await state.set_state(AdminState.waiting_for_broadcast)
    await callback.answer()

@dp.message(AdminState.waiting_for_broadcast)
async def admin_broadcast_send(message: Message, state: FSMContext):
    users = cursor.execute("SELECT user_id FROM users").fetchall()
    success, failed = 0, 0
    wait_msg = await message.answer("⏳ Xabar tarqatilmoqda... Iltimos kuting.")
    
    for user in users:
        try:
            await message.copy_to(chat_id=user[0])
            success += 1
            await asyncio.sleep(0.05) # Telegram limitiga tushmaslik uchun
        except:
            failed += 1
            
    await wait_msg.edit_text(f"✅ Xabar tarqatildi!\n\nMuvaffaqiyatli: {success} ta\nBloklaganlar: {failed} ta")
    await state.clear()

@dp.callback_query(F.data == "admin_give_prem")
async def admin_give_prem_start(callback: CallbackQuery, state: FSMContext):
    await callback.message.answer("💎 Premium bermoqchi bo'lgan mijozning <b>ID</b> raqamini kiriting:\n\n<i>(Misol: 8870374351)</i>", parse_mode="HTML")
    await state.set_state(AdminState.waiting_for_premium_id)
    await callback.answer()

@dp.message(AdminState.waiting_for_premium_id)
async def admin_give_prem_finish(message: Message, state: FSMContext):
    try:
        target_id = int(message.text)
        premium_until = (datetime.date.today() + datetime.timedelta(days=30)).strftime("%Y-%m-%d")
        cursor.execute("UPDATE users SET premium_until = ?, notified_expired = 0 WHERE user_id = ?", (premium_until, target_id))
        conn.commit()
        
        await message.answer(f"✅ <b>Muvaffaqiyatli!</b>\n\nID: <code>{target_id}</code> foydalanuvchisiga 30 kunlik Premium berildi.", parse_mode="HTML")
        try:
            await bot.send_message(target_id, "🎉 <b>Admin sizga 30 kunlik MILLIY AI Premium sovg'a qildi!</b>\n\nEndi cheksiz savol bering. 🚀", parse_mode="HTML")
        except: pass
    except ValueError:
        await message.answer("❌ Xato! Faqat raqam kiriting.")
    await state.clear()

@dp.message(Command("setbanner"))
async def set_banner(message: Message):
    if message.from_user.id != ADMIN_ID: return
    if not message.photo:
        await message.answer("⚠️ Rasmni yuborib, izohiga `/setbanner` deb yozing.")
        return
    with open(BANNER_FILE, 'w') as f:
        f.write(message.photo[-1].file_id)
    await message.answer("✅ MILLIY AI banneri muvaffaqiyatli saqlandi!")

# --- TUGMALAR ---
@dp.callback_query(F.data == "clear_chat")
async def clear_context(callback: CallbackQuery):
    user_contexts[callback.from_user.id] = []
    await callback.answer("✅ Suhbat tarixi tozalandi. Yangi mavzuda gaplashamiz!", show_alert=True)

@dp.callback_query(F.data == "switch_mode")
async def switch_mode(callback: CallbackQuery):
    user_id = callback.from_user.id
    _, _, premium_until, current_mode = get_user_data(user_id)
    new_mode = 'r1' if current_mode == 'v3' else 'v3'
    
    cursor.execute("UPDATE users SET ai_mode = ? WHERE user_id = ?", (new_mode, user_id))
    conn.commit()
    
    is_prem = is_premium(premium_until)
    await callback.message.edit_reply_markup(reply_markup=get_main_inline_kb(new_mode, is_prem))
    mode_name = "Aqlli (R1) 🧠" if new_mode == 'r1' else "Oddiy (V3) ⚡️"
    await callback.answer(f"Rejim o'zgardi: {mode_name}")

# --- PREMIUM SOTIB OLISH ---
@dp.callback_query(F.data == "get_premium")
async def get_premium(callback: CallbackQuery, state: FSMContext):
    user_id = callback.from_user.id
    _, _, premium_until, _ = get_user_data(user_id)
    
    if is_premium(premium_until):
        await callback.answer("💎 Sizda allaqachon Premium faol!", show_alert=True)
        return

    text = (
        "💎 <b>MILLIY AI PREMIUM</b> 💎\n\n"
        "Premium orqali <b>cheksiz</b> savol bering va barcha rejimlardan to'liq foydalaning.\n\n"
        "💰 <b>1 oylik tarif narxi:</b>\n"
        "├ 🇺🇿 Uzcard: <b>23,000 so'm</b>\n"
        "└ 💳 Visa: <b>2$</b>\n\n"
        "🏦 <b>To'lov uchun rekvizitlar:</b>\n"
        "├ <b>Uzcard:</b> <code>5614 6818 5290 5201</code>\n"
        "└ <b>Visa:</b> <code>4231 2000 9704 3946</code>\n"
        "👤 <i>Jasurbek T.</i>\n\n"
        "📸 <b>To'lov jarayoni:</b>\n"
        "To'lovni amalga oshirib, <b>chekni (skrinshotni) shu chatga yuboring</b>.\n"
        "Admin tasdiqlagach, obunangiz avtomatik 30 kunga faollashadi. ✅"
    )
    await callback.message.answer(text, parse_mode="HTML")
    await state.set_state(PremiumState.waiting_for_receipt)
    await callback.answer()

@dp.message(PremiumState.waiting_for_receipt, F.photo)
async def handle_receipt(message: Message, state: FSMContext):
    user_id = message.from_user.id
    username = message.from_user.username or "Noma'lum"
    
    admin_kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Tasdiqlash", callback_data=f"approve_{user_id}"),
         InlineKeyboardButton(text="❌ Rad etish", callback_data=f"reject_{user_id}")]
    ])
    
    await bot.send_photo(
        chat_id=ADMIN_ID,
        photo=message.photo[-1].file_id,
        caption=f"💰 <b>Yangi Premium to'lov!</b>\n\n👤 Mijoz: @{username}\n🆔 ID: <code>{user_id}</code>\n\n<i>Chekni tekshirib, tasdiqlang.</i>",
        reply_markup=admin_kb,
        parse_mode="HTML"
    )
    
    await message.answer("⏳ <b>Chekingiz qabul qilindi!</b>\n\nAdmin tasdiqlashi bilan obunangiz faollashadi. Odatda bu 1-5 daqiqa vaqt oladi.", parse_mode="HTML")
    await state.clear()

@dp.callback_query(F.data.startswith("approve_"))
async def approve_payment(callback: CallbackQuery):
    user_id = int(callback.data.split("_")[1])
    premium_until = (datetime.date.today() + datetime.timedelta(days=30)).strftime("%Y-%m-%d")
    cursor.execute("UPDATE users SET premium_until = ?, daily_count = 0, notified_expired = 0 WHERE user_id = ?", (premium_until, user_id))
    conn.commit()
    
    await callback.message.edit_caption(caption=callback.message.caption + "\n\n✅ <b>TASDIQLANDI (30 kun qo'shildi)</b>", parse_mode="HTML")
    
    try:
        await bot.send_message(
            chat_id=user_id,
            text="🎉 <b>To'lovingiz tasdiqlandi!</b>\n\n"
                 "Sizga 30 kunlik <b>MILLIY AI Premium</b> faollashtirildi. "
                 "Endi cheksiz va to'liq quvvatda foydalanishingiz mumkin! 🚀",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🚀 Savol berish", callback_data="clear_chat")]]),
            parse_mode="HTML"
        )
    except: pass
    await callback.answer("Mijozga Premium berildi!")

@dp.callback_query(F.data.startswith("reject_"))
async def reject_payment(callback: CallbackQuery):
    user_id = int(callback.data.split("_")[1])
    await callback.message.edit_caption(caption=callback.message.caption + "\n\n❌ <b>RAD ETILDI</b>", parse_mode="HTML")
    try:
        await bot.send_message(chat_id=user_id, text="❌ Kechirasiz, to'lovingiz tasdiqlanmadi. Iltimos, admin bilan bog'laning: @Asoschi_JT")
    except: pass
    await callback.answer("Rad etildi!")

# --- AI MULOQOTI ---
@dp.message(F.text)
async def handle_ai(message: Message):
    user_id = message.from_user.id
    if user_id not in user_contexts: user_contexts[user_id] = []

    today = datetime.date.today().strftime("%Y-%m-%d")
    last_date, daily_count, premium_until, ai_mode = get_user_data(user_id)
    is_prem = is_premium(premium_until)

    if last_date != today:
        cursor.execute("UPDATE users SET last_usage_date = ?, daily_count = 0 WHERE user_id = ?", (today, user_id))
        conn.commit()
        daily_count = 0

    if not is_prem and daily_count >= 5:
        await message.answer(
            "⚠️ <b>Kunlik 5 ta bepul limitingiz tugadi!</b>\n\n"
            "Yana savol berish uchun Premium oling yoki ertaga qayta urinib ko'ring.",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="💎 Premium olish", callback_data="get_premium")]]), 
            parse_mode="HTML"
        )
        return

    # Limit va statistika yangilash
    cursor.execute("UPDATE users SET daily_count = daily_count + 1, total_requests = total_requests + 1 WHERE user_id = ?", (user_id,))
    conn.commit()

    # Faqat "yozmoqda..." holati
    await bot.send_chat_action(chat_id=message.chat.id, action="typing")
    
    try:
        model_name = "deepseek-reasoner" if ai_mode == 'r1' else "deepseek-chat"
        
        system_prompt = (
            "Sen MILLIY AI'san. O'zbek tilida, do'stona va tushunarli tarzda javob berasan. "
            "Kod yozganda chiroyli Markdown formatida yozasan. "
            "Agar foydalanuvchi sendan 'Seni kim yaratgan?', 'Muallifing kim?' deb so'rasa, "
            "seni Jasurbek Turayev yaratganini aytasan va uning veb-sayti: [jasurbekturaev.com](https://jasurbekturaev.com/) ekanligini ta'kidlaysan."
        )

        messages = [{"role": "system", "content": system_prompt}]
        messages.extend(user_contexts[user_id][-10:])
        messages.append({"role": "user", "content": message.text})
        
        response = await client.chat.completions.create(
            model=model_name, messages=messages, max_tokens=3000, temperature=0.7
        )
        
        ai_reply = response.choices[0].message.content
        if not isinstance(ai_reply, str): ai_reply = str(ai_reply)
        
        user_contexts[user_id].append({"role": "user", "content": message.text})
        user_contexts[user_id].append({"role": "assistant", "content": ai_reply})
        
        if len(ai_reply) > 4000:
            for chunk in split_message(ai_reply):
                await message.answer(chunk, parse_mode="Markdown")
                await asyncio.sleep(0.5)
        else:
            await message.answer(ai_reply, parse_mode="Markdown")
            
        if not is_prem and daily_count < 4:
            left = 5 - (daily_count + 1)
            await message.answer(f"<blockquote>ℹ️ <i>Sizda bugun uchun yana {left} ta bepul savol qoldi.</i></blockquote>", parse_mode="HTML")
        
    except Exception as e:
        logging.error(f"Xatolik: {e}")
        await message.answer("❌ Kechirasiz, tizimda kichik xatolik yuz berdi. Iltimos, qayta urinib ko'ring.")

# --- OBUNA TUGASHINI TEKSHIRISH ---
async def check_expirations(bot: Bot):
    while True:
        try:
            today = datetime.date.today().strftime("%Y-%m-%d")
            cursor.execute("SELECT user_id FROM users WHERE premium_until < ? AND notified_expired = 0", (today,))
            expired_users = cursor.fetchall()
            
            for user in expired_users:
                user_id = user[0]
                try:
                    await bot.send_message(
                        chat_id=user_id,
                        text="⚠️ <b>Diqqat!</b>\n\nSizning <b>MILLIY AI Premium</b> obunangiz muddati tugadi.\n\n"
                             "Xizmatdan cheksiz foydalanishni davom ettirish uchun obunani yangilang.",
                        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                            [InlineKeyboardButton(text="💎 Obunani yangilang", callback_data="get_premium")]
                        ])
                    )
                    cursor.execute("UPDATE users SET notified_expired = 1 WHERE user_id = ?", (user_id,))
                    conn.commit()
                except: pass
        except Exception as e:
            logging.error(f"Tekshiruvda xato: {e}")
        
        await asyncio.sleep(3600)

async def main():
    logging.basicConfig(level=logging.INFO)
    print("MILLIY AI (SaaS Premium versiya) ishga tushdi...")
    asyncio.create_task(check_expirations(bot))
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
