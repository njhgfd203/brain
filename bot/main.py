import asyncio
import logging
from urllib.parse import urlsplit

from aiogram import Bot, Dispatcher

from bot.config import settings
from bot.handlers import admin, ask, notes, tasks
from bot.middlewares.access import AccessMiddleware
from db.database import init_db


def build_dispatcher() -> Dispatcher:
    dp = Dispatcher()
    dp.update.middleware(AccessMiddleware())
    # Порядок важен: ask.router — последним (catch-all на свободный текст)
    dp.include_router(notes.router)
    dp.include_router(admin.router)
    dp.include_router(tasks.router)
    dp.include_router(ask.router)
    return dp


async def run_polling() -> None:
    await init_db()
    bot = Bot(token=settings.telegram_bot_token)
    dp = build_dispatcher()
    await dp.start_polling(bot)


async def run_webhook() -> None:
    from aiohttp import web
    from aiogram.webhook.aiohttp_server import SimpleRequestHandler, setup_application

    await init_db()
    bot = Bot(token=settings.telegram_bot_token)
    dp = build_dispatcher()

    parsed = urlsplit(settings.telegram_webhook_url)
    path = parsed.path if parsed.path else "/webhook"

    app = web.Application()
    SimpleRequestHandler(dispatcher=dp, bot=bot).register(app, path=path)
    setup_application(app, dp, bot=bot)

    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, host="0.0.0.0", port=8443)
    await site.start()

    # Регистрируем webhook только когда сервер уже слушает, иначе
    # первые апдейты от Telegram уйдут в никуда.
    await bot.set_webhook(settings.telegram_webhook_url)

    logging.info("Webhook server started on 0.0.0.0:8443, path=%s", path)

    # Run forever
    await asyncio.Event().wait()


def main() -> None:
    logging.basicConfig(level=logging.INFO)

    if settings.bot_mode == "webhook":
        asyncio.run(run_webhook())
    else:
        asyncio.run(run_polling())


if __name__ == "__main__":
    main()
