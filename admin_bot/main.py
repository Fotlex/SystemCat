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
from config import config
import asyncio

from handlers import handler, work_handler
from middlewares import UserMiddleware
from aiogram.utils.callback_answer import CallbackAnswerMiddleware


async def main():
    bot = Bot(token=config.BOT_ADMIN_TOKEN)

    dp = Dispatcher()
    dp.callback_query.outer_middleware(CallbackAnswerMiddleware())
    dp.callback_query.outer_middleware(UserMiddleware())
    dp.message.outer_middleware(UserMiddleware())

    main_menu_commands = [
        BotCommand(command='/start', description='Зарегестрироваться/проверить роль'),
        BotCommand(command='/admin', description='Создать заказ'),
    ]
    await bot.set_my_commands(main_menu_commands)

    dp.include_routers(handler.router, work_handler.router)

    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger(__name__)

    await dp.start_polling(bot)


if __name__ == '__main__':
    asyncio.run(main())
