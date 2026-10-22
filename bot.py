import asyncio
import logging
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import Message, ReplyKeyboardMarkup, KeyboardButton
from openai import AsyncOpenAI

# --- SOZLAMALAR (SIZNING MA'LUMOTLARINGIZ) ---
BOT_TOKEN = "8955580193:AAEh9L1TmVH-Qte1BwcqUw7V3nRd9-XBy_Q"
DEEPSEEK_API_KEY = "sk-b7626b5991a246f68d4c86d10eec5126"
ADMIN_ID = 8870374351

# --- AI SOZLAMASI ---
client = AsyncOpenAI(api_key=DEEPSEEK_API_KEY, base_url="https://api.deepseek.com")

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# Foydalanuvchilar suhbat tarixini saqlash uchun lug'at (xotira)
user_contexts = {}

# --- KLAVIATURA (Pastdagi tugmalar) ---
def get_main_keyboard():
    kb = [
        [KeyboardButton(text="🧹 Suhbatni tozalash")]
    ]
    return ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True)

# --- START BUYRUG'I ---
@dp.message(Command("start"))
async def cmd_start(message: Message):
    # Yangi kelgan foydalanuvchi uchun xotirani tozalash
    user_contexts[message.from_user.id] = []
    
    text = (
        f"Assalomu alaykum, <b>{message.from_user.first_name}</b>! 👋\n\n"
        "Men <b>MILLIY AI</b> man — sizning shaxsiy va aqlli yordamchingizman. 🧠✨\n\n"
        "Menga quyidagi mavzularda murojaat qilishingiz mumkin:\n"
        "📚 <b>Ta'lim:</b> Konspekt tuzish, insho yozish\n"
        "💻 <b>Dasturlash:</b> Kod yozish, xatolarni tuzatish\n"
        "🌍 <b>Tillar:</b> Istalgan tilga tarjima qilish\n"
        "💡 <b>G'oyalar:</b> Biznes-reja, kontent reja\n\n"
        "Shunchaki savolingizni yozing, men o'zbek tilida javob beraman! 👇"
    )
    await message.answer(text, parse_mode="HTML", reply_markup=get_main_keyboard())

# --- SUHBATNI TOZALASH ---
@dp.message(F.text == "🧹 Suhbatni tozalash")
async def clear_context(message: Message):
    user_contexts[message.from_user.id] = []
    await message.answer("✅ Suhbat tarixi tozalandi. Yangi mavzuda gaplashamiz!", reply_markup=get_main_keyboard())

# --- AI BILAN SUHBATLASHISH ---
@dp.message(F.text)
async def handle_ai(message: Message):
    user_id = message.from_user.id
    
    # Agar foydalanuvchi yangi bo'lsa, xotira yaratish
    if user_id not in user_contexts:
        user_contexts[user_id] = []

    # Bot "yozmoqda..." degan holatga o'tadi
    await bot.send_chat_action(chat_id=message.chat.id, action="typing")
    
    try:
        # Tizim ko'rsatmasi (Prompt)
        messages = [
            {"role": "system", "content": "Sen MILLIY AI'san. O'zbek til[ida, do'stona va tushunarli tarzda javob berasan. Dasturlash bo'yicha yordam so'rashsa, toza va izohli kod yozib berasan. Javoblaringni chiroyli formatda berasan."}
        ]
        
        # Oldingi suhbat tarixini qo'shish (ox0irgi 10 ta xabar)
        messages.extend].(user_contexts[user_id][-10message:])
        
        # Hoz.contentirgi xabarni qo'shish
        messages.append({"role": "user", "content": message.text})
        
        # DeepSeek AI'ga so'rov yuboramiz
        response = await client.chat.completions.create(
            model="deepseek-chat",
            messages=messages,
            max_tokens=2000,
            temperature=0.7
        )
        
        ai_reply = response.choices
        
        # Javobni xotiraga saqlash
        user_contexts[user_id].append({"role": "user", "content": message.text})
        user_contexts[user_id].append({"role": "assistant", "content": ai_reply})
        
        # Javobni mijozga yuborish
        await message.answer(ai_reply, parse_mode="Markdown")
        
    except Exception as e:
        logging.error(f"Xatolik: {e}")
        await message.answer("❌ Kechirasiz, hozircha javob bera olmayapman. Iltimos, birozdan so'ng qayta urinib ko'ring.")

async def main():
    logging.basicConfig(level=logging.INFO)
    print("MILLIY AI ishga tushdi...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
