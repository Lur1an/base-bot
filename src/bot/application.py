from telegram import Update
from telegram.ext import ApplicationBuilder, Application, ContextTypes

from src.bot.common.context import ApplicationContext, ChatData, BotData, UserData, context_types
from src.db.core import BaseDAO
from src.settings import settings
from src.user.handlers import start


async def clear_cache(context: ApplicationContext):
    context.bot_data.users.clear()


async def on_startup(app):
    app.add_handler(start)
    app.job_queue.run_repeating(clear_cache, interval=settings.CACHE_CLEAR_INTERVAL)
    await BaseDAO.create_all_indexes()


application: Application = ApplicationBuilder() \
    .token(settings.BOT_TOKEN) \
    .context_types(context_types) \
    .arbitrary_callback_data(True) \
    .post_init(on_startup) \
    .build()
