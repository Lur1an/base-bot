from telegram import Update
from telegram.ext import ApplicationBuilder, Application, ContextTypes

from src.bot.common.context import ApplicationContext, ChatData, BotData, UserData, context_types
from src.bot.common.wrappers import command_handler, next_reply_handler
from src.settings import settings
from src.user.handlers import start



async def on_startup(app: Application):
    app.add_handler(start)


application: Application = ApplicationBuilder() \
    .token(settings.BOT_TOKEN) \
    .context_types(context_types) \
    .arbitrary_callback_data(True) \
    .post_init(on_startup) \
    .build()
