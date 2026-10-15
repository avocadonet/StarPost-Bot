import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage

from config import config
from db import init_db
from handlers import setup_routers


async def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    )
    logger = logging.getLogger(__name__)

    # Инициализация SQLite для логирования транзакций
    await init_db()

    # Инициализация бота (извлекаем секретный токен через get_secret_value())
    bot = Bot(token=config.bot_token.get_secret_value())

    # При необходимости сохранения FSM при рестартах замените MemoryStorage на RedisStorage
    storage = MemoryStorage()
    dp = Dispatcher(storage=storage)

    dp.include_router(setup_routers())

    # Сбрасываем старые вебхуки перед запуском Long Polling
    await bot.delete_webhook(drop_pending_updates=False)

    logger.info("Bot started successfully in Long Polling mode.")
    try:
        await dp.start_polling(
            bot,
            allowed_updates=dp.resolve_used_update_types(),
        )
    finally:
        await bot.session.close()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        pass