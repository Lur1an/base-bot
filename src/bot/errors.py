from telegram import Update
from src.bot.common.context import ApplicationContext
import structlog

log = structlog.get_logger()


class UserNotRegistered(Exception):
    pass


async def handle_error(update: Update, context: ApplicationContext):
    e = context.error
    if not e:
        return
    match e:
        case UserNotRegistered():
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text="You are not registered. Please register first with /start",
            )
        case _:
            log.error("Unhandled exception", error=e)
