import asyncio
from aiogram import Bot, Dispatcher, F
from aiogram.types import Message, WebAppInfo
from aiogram.utils.keyboard import InlineKeyboardBuilder
from config import BOT_TOKEN, WEBAPP_URL
from database import init_db, ensure_user_exists
from locales import get_text

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()


@dp.message(F.text == "/start")
async def start_handler(message: Message):
    await ensure_user_exists(message.from_user.id)

    kb = InlineKeyboardBuilder()
    kb.button(
        text="🚀 Open App",
        web_app=WebAppInfo(url=WEBAPP_URL)
    )

    await message.answer(
        get_text("welcome", "en"),
        reply_markup=kb.as_markup()
    )


async def main():
    await init_db()
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
