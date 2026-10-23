import asyncio
import logging
import sqlite3
import datetime
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery, WebAppInfo
from openai import AsyncOpenAI

# --- SOZLAMALAR ---
BOT_TOKEN = "8955580193:AAEh9L1TmVH-Qte1BwcqUw7V3nRd9-XBy_Q"
DEEPSEEK_API_KEY = "sk-b7626b5991a246f68d4c86d10eec5126"
ADMIN_ID = 8870374351
WEBSITE_URL = "https://jasurbekturaev.com/"

# --- AI SOZLAMASI ---
client = AsyncOpenAI(api_key=DEEPSEEK_API_KEY, base_url="https://api.deepseek.com")
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# --- BAZA (Kunlik limit va Premiumni saqlash) ---
conn = sqlite3.connect('milliy_ai_users.db', check_same_thread=False)
cursor = conn.cursor()
cursor.execute('''CREATE TABLE IF NOT EXISTS users 
                  (user_id INTEGER PRIMARY KEY, 
                   last_usage_date TEXT, 
                   daily_count INTEGER DEFAULT 0, 
                   premium_until TEXT DEFAULT NULL,
                   ai_mode TEXT DEFAULT 'v3')''')
conn.commit()

# Foydalanuvchi suhbat tarixi (xotira)
user_contexts = {}

# --- YORDAMCHI FUNKSIYALAR ---

def get_user_data(user_id):
    cursor.execute("SELECT last_usage_date, daily_count, premium_until, ai_mode FROM users WHERE user_id = ?", (user_id,))
    user = cursor.fetchone()
    if not user:
        today = datetime.date.today().strftime("%Y-%m-%d")
        cursor.execute("INSERT INTO users (user_id, last_usage_date, daily_count) VALUES (?, ?, ?)", (user_id, today, 0))
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

def get_main_inline_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🧹 Suhbatni tozalash", callback_data="clear_chat"),
         InlineKeyboardButton(text="🤖 Rejim: Oddiy (V3)", callback_data="switch_mode")],
        [InlineKeyboardButton(text="💎 Premium olish", callback_data="get_premium"),
         InlineKeyboardButton(text="🌐 Muallif haqida", url=WEBSITE_URL)]
    ])

# --- HANDLERLAR ---

@dp.message(Command("start"))
async def cmd_start(message: Message):
    user_contexts[message.from_user.id] = []
    text = (
        f"Assalomu alaykum, <b>{message.from_user.first_name}</b>! 👋\n\n"
        "Men <b>MILLIY AI</b> man — sizning shaxsiy va aqlli yordamchingizman. 🧠✨\n\n"
        "Menda siz uchun 2 xil aql rejimi bor:\n"
        "⚡️ <b>Oddiy rejim (V3)</b> — tezkor javoblar.\n"
        "🧠 <b>Aqlli rejim (R1)</b> — murakkab kod va matematikani o'ylab javob beradi.\n\n"
        "⚠️ <i>Har kuni 3 ta bepul savol berishingiz mumkin. Cheksiz foydalanish uchun Premium oling.</i>\n\n"
        "👇 Boshlash uchun shunchaki savolingizni yozing!"
    )
    await message.answer(text, parse_mode="HTML", reply_markup=get_main_inline_kb())

@dp.message(Command("admin"))
async def cmd_admin(message: Message):
    if message.from_user.id != ADMIN_ID:
        return
    cursor.execute("SELECT COUNT(*) FROM users")
    total_users = cursor.fetchone()[0]
    
    text = (
        "👨‍💻 <b>Admin Panel</b>\n\n"
        f"👥 Jami foydalanuvchilar: <b>{total_users}</b> ta\n"
        "Tizim holati: <b>Ishlayapti ✅</b>"
    )
    await message.answer(text, parse_mode="HTML")

@dp.callback_query(F.data == "clear_chat")
async def clear_context(callback: CallbackQuery):
    user_contexts[callback.from_user.id] = []
    await callback.answer("✅ Suhbat tarixi tozalandi! Yangi mavzuda gaplashamiz.", show_alert=True)

@dp.callback_query(F.data == "switch_mode")
async def switch_mode(callback: CallbackQuery):
    user_id = callback.from_user.id
    _, _, _, current_mode = get_user_data(user_id)
    new_mode = 'r1' if current_mode == 'v3' else 'v3'
    
    cursor.execute("UPDATE users SET ai_mode = ? WHERE user_id = ?", (new_mode, user_id))
    conn.commit()
    
    mode_text = "🧠 Rejim: Aqlli (R1)" if new_mode == 'r1' else "🤖 Rejim: Oddiy (V3)"
    new_kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🧹 Suhbatni tozalash", callback_data="clear_chat"),
         InlineKeyboardButton(text=mode_text, callback_data="switch_mode")],
        [InlineKeyboardButton(text="💎 Premium olish", callback_data="get_premium"),
         InlineKeyboardButton(text="🌐 Muallif haqida", url=WEBSITE_URL)]
    ])
    
    await callback.message.edit_reply_markup(reply_markup=new_kb)
    await callback.answer(f"Rejim o'zgardi: {new_mode.upper()}")

@dp.callback_query(F.data == "get_premium")
async def get_premium(callback: CallbackQuery):
    text = (
        "💎 <b>MILLIY AI Premium</b>\n\n"
        "Bepul limitdan charchadingizmi? Premium oling va <b>cheksiz</b> savol bering!\n\n"
        "💰 <b>Narxi:</b> 29,000 so'm (1 oylik)\n"
        "💳 <b>Karta:</b> <code>5614 6818 5290 5201</code> (Jasurbek T.)\n\n"
        "To'lovni amalga oshirib, chekni (skrinshotni) <b>adminga yuboring:</b> @Asoschi_JT\n"
        "Admin tasdiqlagach, limitingiz avtomatik ochiladi."
    )
    await callback.message.answer(text, parse_mode="HTML")
    await callback.answer()

@dp.message(F.text)
async def handle_ai(message: Message):
    user_id = message.from_user.id
    if user_id not in user_contexts:
        user_contexts[user_id] = []

    today = datetime.date.today().strftime("%Y-%m-%d")
    last_date, daily_count, premium_until, ai_mode = get_user_data(user_id)
    is_prem = is_premium(premium_until)

    if last_date != today:
        cursor.execute("UPDATE users SET last_usage_date = ?, daily_count = 0 WHERE user_id = ?", (today, user_id))
        conn.commit()
        daily_count = 0

    if not is_prem and daily_count >= 3:
        await message.answer(
            "⚠️ <b>Kunlik bepul limitingiz tugadi!</b>\n\n"
            "Yana savol berish uchun Premium oling yoki ertaga qayta urinib ko'ring.",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="💎 Premium olish", callback_data="get_premium")]
            ]), parse_mode="HTML"
        )
        return

    if not is_prem:
        cursor.execute("UPDATE users SET daily_count = daily_count + 1 WHERE user_id = ?", (user_id,))
        conn.commit()

    await bot.send_chat_action(chat_id=message.chat.id, action="typing")
    
    try:
        model_name = "deepseek-reasoner" if ai_mode == 'r1' else "deepseek-chat"
        
        # MUALLIF HAQIDA MA'LUMOT QO'SHILGAN PROMPT
        system_prompt = (
            "Sen MILLIY AI'san. O'zbek tilida, do'stona va tushunarli tarzda javob berasan. "
            "Kod yozganda chiroyli Markdown formatida yozasan. "
            "Agar foydalanuvchi sendan 'Seni kim yaratgan?', 'Muallifing kim?', 'Kim yasagan?' yoki shunga o'xshash savol so'rasa, "
            "seni Jasurbek Turayev yaratganini aytasan va uning shaxsiy veb-sayti: [jasurbekturaev.com](https://jasurbekturaev.com/) ekanligini ta'kidlaysan. "
            "Bu havolani chiroyli va bosib o'tish mumkin bo'lgan formatda taqdim etasan."
        )

        messages = [{"role": "system", "content": system_prompt}]
        messages.extend(user_contexts[user_id][-10:])
        messages.append({"role": "user", "content": message.text})
        
        response = await client.chat.completions.create(
            model=model_name,
            messages=messages,
            max_tokens=3000,
            temperature=0.7
        )
        
        ai_reply = response.choices[0].message.content
        if not isinstance(ai_reply, str): ai_reply = str(ai_reply)
        
        user_contexts[user_id].append({"role": "user", "content": message.text})
        user_contexts[user_id].append({"role": "assistant", "content": ai_reply})
        
        # Markdown formatida yuboramiz (kodlar va havolalar chiroyli chiqishi uchun)
        if len(ai_reply) > 4000:
            chunks = split_message(ai_reply)
            for chunk in chunks:
                await message.answer(chunk, parse_mode="Markdown")
                await asyncio.sleep(0.5)
        else:
            await message.answer(ai_reply, parse_mode="Markdown")
            
        if not is_prem and daily_count < 2:
            left = 3 - (daily_count + 1)
            await message.answer(f"ℹ️ <i>Sizda bugun uchun yana {left} ta bepul savol qoldi.</i>", parse_mode="HTML")
        
    except Exception as e:
        logging.error(f"Xatolik: {e}")
        await message.answer(f"❌ Xatolik yuz berdi: {str(e)}")

async def main():
    logging.basicConfig(level=logging.INFO)
    print("MILLIY AI (Premium + Muallif tizimi) ishga tushdi...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
