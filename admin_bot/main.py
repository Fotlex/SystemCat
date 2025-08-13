import logging
from pathlib import Path
import django
import sys
import os

sys.path.append(str(Path(__file__).resolve().parent.parent))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "web.settings")
django.setup()

from aiogram.types import BotCommand
from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.redis import RedisStorage
from config import config
import asyncio

import redis.asyncio as aioredis

from handlers import handler, work_handler
from middlewares import UserMiddleware
from aiogram.utils.callback_answer import CallbackAnswerMiddleware



async def main():
    redis = await aioredis.from_url(f'redis://{config.REDIS_HOST if not config.DEBUG else "localhost"}:{config.REDIS_PORT}/0')
    
    bot = Bot(token=config.BOT_ADMIN_TOKEN)

    dp = Dispatcher(storage=RedisStorage(redis=redis))
    dp.callback_query.outer_middleware(CallbackAnswerMiddleware())
    dp.callback_query.outer_middleware(UserMiddleware())
    dp.message.outer_middleware(UserMiddleware())

    main_menu_commands = [
        BotCommand(command='/start', description='Зарегестрироваться/проверить роль'),
        BotCommand(command='/admin', description='Создать заказ'),
        BotCommand(command='/get_photo', description='Получить фото определенного заказа')
    ]
    await bot.set_my_commands(main_menu_commands)

    dp.include_routers(handler.router, work_handler.router)

    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger(__name__)

    await dp.start_polling(bot)


if __name__ == '__main__':
    asyncio.run(main())
