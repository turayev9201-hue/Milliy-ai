import asyncio
import logging
import sqlite3
import datetime
import os
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from openai import AsyncOpenAI

# --- SOZLAMALAR ---
BOT_TOKEN = "8955580193:AAEh9L1TmVH-Qte1BwcqUw7V3nRd9-XBy_Q"
DEEPSEEK_API_KEY = "sk-b7626b5991a246f68d4c86d10eec5126"
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
                   last_usage_date TEXT, 
                   daily_count INTEGER DEFAULT 0, 
                   premium_until TEXT DEFAULT NULL,
                   ai_mode TEXT DEFAULT 'v3',
                   notified_expired INTEGER DEFAULT 0)''')
# Agar eski bazada 'notified_expired' ustuni bo'lmasa, qo'shamiz
cursor.execute("PRAGMA table_info(users)")
columns = [info[1] for info in cursor.fetchall()]
if 'notified_expired' not in columns:
    cursor.execute("ALTER TABLE users ADD COLUMN notified_expired INTEGER DEFAULT 0")
conn.commit()

user_contexts = {}

# --- HOLATLAR (FSM) ---
class PremiumState(StatesGroup):
    waiting_for_receipt = State()

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

def get_main_inline_kb(ai_mode, is_prem):
    mode_text = "🧠 Rejim: Aqlli (R1)" if ai_mode == 'r1' else "🤖 Rejim: Oddiy (V3)"
    prem_btn_text = "💎 Premium: Faol ✅" if is_prem else "💎 Premium olish"
    
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🧹 Suhbatni tozalash", callback_data="clear_chat"),
         InlineKeyboardButton(text=mode_text, callback_data="switch_mode")],
        [InlineKeyboardButton(text=prem_btn_text, callback_data="get_premium"),
         InlineKeyboardButton(text="🌐 Muallif haqida", url=WEBSITE_URL)]
    ])

# --- START BUYRUG'I ---
@dp.message(Command("start"))
async def cmd_start(message: Message):
    user_id = message.from_user.id
    user_contexts[user_id] = []
    _, _, premium_until, ai_mode = get_user_data(user_id)
    is_prem = is_premium(premium_until)
    
    # Premium holatiga qarab matn
    status_text = "💎 <b>Sizda Premium faol!</b> Cheksiz savol bering." if is_prem else "⚠️ <i>Har kuni 3 ta bepul savol. Cheksizlik uchun Premium oling.</i>"
    
    text = (
        f"Assalomu alaykum, <b>{message.from_user.first_name}</b>! 👋\n\n"
        "Men <b>MILLIY AI</b> man — sizning shaxsiy va aqlli yordamchingizman. 🧠✨\n\n"
        "Menda 2 xil aql rejimi bor:\n"
        "⚡️ <b>Oddiy rejim (V3)</b> — tezkor javoblar.\n"
        "🧠 <b>Aqlli rejim (R1)</b> — murakkab kod va matematikani o'ylab yechadi.\n\n"
        f"{status_text}\n\n"
        "👇 Boshlash uchun shunchaki savolingizni yozing!"
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

# --- ADMIN BUYRUQLARI ---
@dp.message(Command("admin"))
async def cmd_admin(message: Message):
    if message.from_user.id != ADMIN_ID: return
    cursor.execute("SELECT COUNT(*) FROM users")
    total_users = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM users WHERE premium_until >= ?", (datetime.date.today().strftime("%Y-%m-%d"),))
    prem_users = cursor.fetchone()[0]
    
    text = (
        "👨‍💻 <b>Admin Panel</b>\n\n"
        f"👥 Jami foydalanuvchilar: <b>{total_users}</b> ta\n"
        f"💎 Premium foydalanuvchilar: <b>{prem_users}</b> ta\n"
        "Tizim holati: <b>Ishlayapti ✅</b>"
    )
    await message.answer(text, parse_mode="HTML")

@dp.message(Command("setbanner"))
async def set_banner(message: Message):
    if message.from_user.id != ADMIN_ID: return
    if not message.photo:
        await message.answer("⚠️ Rasmni yuborib, izohiga `/setbanner` deb yozing.")
        return
    with open(BANNER_FILE, 'w') as f:
        f.write(message.photo[-1].file_id)
    await message.answer("✅ MILLIY AI banneri muvaffaqiyatli saqlandi!")

# --- TUGMALAR HANDLERI ---
@dp.callback_query(F.data == "clear_chat")
async def clear_context(callback: CallbackQuery):
    user_contexts[callback.from_user.id] = []
    await callback.answer("✅ Suhbat tarixi tozalandi! Yangi mavzuda gaplashamiz.", show_alert=True)

@dp.callback_query(F.data == "switch_mode")
async def switch_mode(callback: CallbackQuery):
    user_id = callback.from_user.id
    _, _, premium_until, current_mode = get_user_data(user_id)
    new_mode = 'r1' if current_mode == 'v3' else 'v3'
    
    cursor.execute("UPDATE users SET ai_mode = ? WHERE user_id = ?", (new_mode, user_id))
    conn.commit()
    
    is_prem = is_premium(premium_until)
    await callback.message.edit_reply_markup(reply_markup=get_main_inline_kb(new_mode, is_prem))
    mode_name = "Aqlli (R1)" if new_mode == 'r1' else "Oddiy (V3)"
    await callback.answer(f"Rejim o'zgardi: {mode_name}")

# --- PREMIUM SOTIB OLISH JARAYONI ---
@dp.callback_query(F.data == "get_premium")
async def get_premium(callback: CallbackQuery, state: FSMContext):
    user_id = callback.from_user.id
    _, _, premium_until, _ = get_user_data(user_id)
    
    if is_premium(premium_until):
        await callback.answer("💎 Sizda allaqachon Premium faol!", show_alert=True)
        return

    text = (
        "💎 <b>MILLIY AI Premium (1 oylik)</b>\n\n"
        "Premium orqali siz <b>cheksiz</b> savol berishingiz va ikkala rejimdan ham to'liq foydalanishingiz mumkin.\n\n"
        "💰 <b>Tarif narxi:</b>\n"
        "🇺🇿 Uzcard: <b>23,000 so'm</b>\n"
        "💳 Visa: <b>2$</b>\n\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "🏦 <b>To'lov uchun rekvizitlar:</b>\n"
        "💳 <b>Uzcard:</b> <code>5614 6818 5290 5201</code>\n"
        "💳 <b>Visa:</b> <code>4231 2000 9704 3946</code>\n"
        "(Jasurbek T.)\n"
        "━━━━━━━━━━━━━━━━━━━━\n\n"
        "📸 To'lovni amalga oshirib, <b>chekni (skrinshotni) shu chatga rasm qilib yuboring</b>.\n"
        "Admin tasdiqlagach, obunangiz avtomatik 30 kunga faollashadi."
    )
    await callback.message.answer(text, parse_mode="HTML")
    await state.set_state(PremiumState.waiting_for_receipt)
    await callback.answer()

# Chekni qabul qilish va adminga yuborish
@dp.message(PremiumState.waiting_for_receipt, F.photo)
async def handle_receipt(message: Message, state: FSMContext):
    user_id = message.from_user.id
    username = message.from_user.username or "Noma'lum"
    photo_id = message.photo[-1].file_id
    
    admin_kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Tasdiqlash", callback_data=f"approve_{user_id}"),
         InlineKeyboardButton(text="❌ Rad etish", callback_data=f"reject_{user_id}")]
    ])
    
    await bot.send_photo(
        chat_id=ADMIN_ID,
        photo=photo_id,
        caption=f"💰 <b>Yangi Premium to'lov!</b>\n\n"
                f"👤 Mijoz: @{username}\n"
                f"🆔 ID: <code>{user_id}</code>\n\n"
                f"Iltimos, chekni tekshiring va tasdiqlang.",
        reply_markup=admin_kb,
        parse_mode="HTML"
    )
    
    await message.answer("⏳ <b>Chekingiz qabul qilindi!</b>\n\nAdmin tasdiqlashi bilan obunangiz faollashadi. Odatda bu 1-5 daqiqa vaqt oladi.")
    await state.clear()

# Admin Tasdiqlashi
@dp.callback_query(F.data.startswith("approve_"))
async def approve_payment(callback: CallbackQuery):
    user_id = int(callback.data.split("_")[1])
    
    # 30 kunlik premium berish
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
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🚀 Savol berish", callback_data="clear_chat")]])
        )
    except: pass
    await callback.answer("Mijozga Premium berildi!")

# Admin Rad etishi
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
    if user_id not in user_contexts:
        user_contexts[user_id] = []

    today = datetime.date.today().strftime("%Y-%m-%d")
    last_date, daily_count, premium_until, ai_mode = get_user_data(user_id)
    is_prem = is_premium(premium_until)

    if last_date != today:
        cursor.execute("UPDATE users SET last_usage_date = ?, daily_count = 0 WHERE user_id = ?", (today, user_id))
        conn.commit()
        daily_count = 0

    # Limit tekshiruvi (Bepul foydalanuvchilar uchun 3 ta)
    if not is_prem and daily_count >= 3:
        await message.answer(
            "⚠️ <b>Kunlik 3 ta bepul limitingiz tugadi!</b>\n\n"
            "Yana savol berish uchun Premium oling yoki ertaga qayta urinib ko'ring.",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="💎 Premium olish (23,000 so'm)", callback_data="get_premium")]
            ]), parse_mode="HTML"
        )
        return

    if not is_prem:
        cursor.execute("UPDATE users SET daily_count = daily_count + 1 WHERE user_id = ?", (user_id,))
        conn.commit()

    await bot.send_chat_action(chat_id=message.chat.id, action="typing")
    
    try:
        model_name = "deepseek-reasoner" if ai_mode == 'r1' else "deepseek-chat"
        
        system_prompt = (
            "Sen MILLIY AI'san. O'zbek tilida, do'stona va tushunarli tarzda javob berasan. "
            "Kod yozganda chiroyli Markdown formatida yozasan. "
            "Agar foydalanuvchi sendan 'Seni kim yaratgan?', 'Muallifing kim?' yoki shunga o'xshash savol so'rasa, "
            "seni Jasurbek Turayev yaratganini aytasan va uning shaxsiy veb-sayti: [jasurbekturaev.com](https://jasurbekturaev.com/) ekanligini ta'kidlaysan."
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

# --- ORQA FONDA ISHLAYDIGAN TEKSHIRUV (Obuna tugashini bildirish) ---
async def check_expirations(bot: Bot):
    while True:
        try:
            today = datetime.date.today().strftime("%Y-%m-%d")
            # Muddati o'tgan va hali xabar yuborilmaganlarni topamiz
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
                            [InlineKeyboardButton(text="💎 Obunani yangilash", callback_data="get_premium")]
                        ])
                    )
                    cursor.execute("UPDATE users SET notified_expired = 1 WHERE user_id = ?", (user_id,))
                    conn.commit()
                except:
                    pass
        except Exception as e:
            logging.error(f"Tekshiruvda xato: {e}")
        
        # Har 1 soatda tekshiradi
        await asyncio.sleep(3600)

async def main():
    logging.basicConfig(level=logging.INFO)
    print("MILLIY AI (To'liq Premium + Obuna bildirishnomasi) ishga tushdi...")
    
    # Orqa fon vazifasini ishga tushirish
    asyncio.create_task(check_expirations(bot))
    
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
