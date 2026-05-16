import asyncio
import logging
from aiogram import Bot, Dispatcher, types
from aiogram.filters.command import Command
import firebase_admin
from firebase_admin import credentials, firestore


# Включаем логирование
logging.basicConfig(level=logging.INFO)

# Объект бота
bot = Bot(token="8330013656:AAGZMNIYWpF_6Tfv13ZlgaflNNQvhW-WnmE")
# Диспетчер
dp = Dispatcher()


# Запуск поллинга
async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())