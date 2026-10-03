import asyncio
import logging
import sys

from aiogram import Bot, Dispatcher
from aiogram.client.session.aiohttp import AiohttpSession
from aiogram.client.telegram import TelegramAPIServer
from aiohttp import web, ClientSession, ClientTimeout

from config import BOT_TOKEN, ONYXGRAM_API_URL, PORT, RENDER_EXTERNAL_URL
from database import init_db
from ytmusic import init_yandex
from handlers import start, search, music, library

logging.basicConfig(level=logging.INFO, stream=sys.stdout)
log = logging.getLogger("lybot")


async def _health(request):
    return web.Response(text="ok")


async def run_web_server():
    """
    Render's free tier only offers a Web Service (no free Background
    Worker), and it marks a deploy unhealthy if nothing listens on
    $PORT. This is just a stub so the health check passes while the
    bot itself runs via long polling below.
    """
    app = web.Application()
    app.router.add_get("/", _health)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", PORT)
    await site.start()
    log.info(f"Health-check web server listening on 0.0.0.0:{PORT}")


async def keep_alive():
    """
    Free Render web services sleep after ~15 min without incoming HTTP
    traffic. If RENDER_EXTERNAL_URL is set (Render sets it automatically
    on web services), ping ourselves periodically to stay awake.
    This only prevents idle-sleep — it does not bypass plan limits or
    account-level suspensions.
    """
    if not RENDER_EXTERNAL_URL:
        return
    timeout = ClientTimeout(total=10)
    async with ClientSession(timeout=timeout) as session:
        while True:
            await asyncio.sleep(10 * 60)
            try:
                async with session.get(RENDER_EXTERNAL_URL) as resp:
                    log.info(f"Self-ping: {resp.status}")
            except Exception as e:
                log.warning(f"Self-ping failed: {e}")


async def main():
    await init_db()
    await init_yandex()

    # Кастомный сервер OnyxGram
    custom_server = TelegramAPIServer.from_base(ONYXGRAM_API_URL)
    session = AiohttpSession(api=custom_server)
    bot = Bot(token=BOT_TOKEN, session=session)

    dp = Dispatcher()

    dp.include_router(search.router)
    dp.include_router(music.router)
    dp.include_router(library.router)
    dp.include_router(start.router)

    print("LyBot запущен")

    await run_web_server()

    try:
        await asyncio.gather(
            dp.start_polling(bot),
            keep_alive(),
        )
    finally:
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())
