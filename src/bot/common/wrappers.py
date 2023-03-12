from functools import wraps
from typing import List, Callable, Any, Generic, TypeVar, cast, Awaitable

from telegram import Update
from telegram.ext import ConversationHandler, CallbackQueryHandler

from src.bot.common.context import ApplicationContext

import logging

log = logging.getLogger(__name__)


def admin_command(admin_ids: List[int]):
    def inner_decorator(f: Callable[[Update, ApplicationContext], Awaitable[Any]]):
        @wraps(f)
        async def wrapped(update: Update, context: ApplicationContext):
            if update.effective_user.id not in admin_ids:
                return
            return await f(update, context)

        return wrapped

    return inner_decorator


CallbackDataType = TypeVar("CallbackDataType")


def arbitrary_callback_query_handler(query_data_type: CallbackDataType, answer_query_after: bool = True):
    def inner_decorator(
            f: Callable[[Update, ApplicationContext, Generic[CallbackDataType]], Awaitable[Any]]
    ) -> CallbackQueryHandler:
        decorator = inject_callback_query(answer_query_after=answer_query_after)
        wrapped = decorator(f)
        handler = CallbackQueryHandler(pattern=query_data_type, callback=wrapped)
        return handler

    return inner_decorator


def inject_callback_query(answer_query_after: bool = True):
    def inner_decorator(f: Callable[[Update, ApplicationContext, Generic[CallbackDataType]], Awaitable[Any]]):
        @wraps(f)
        async def wrapped(update: Update, context: ApplicationContext):
            converted_data = cast(CallbackDataType, update.callback_query.data)
            result = await f(update, context, converted_data)
            if answer_query_after:
                await update.callback_query.answer()
            return result

        return wrapped

    return inner_decorator


def delete_message_after(f: Callable[[Update, ApplicationContext], Awaitable[Any]]):
    @wraps(f)
    async def wrapper(update: Update, context: ApplicationContext):
        result = await f(update, context)
        try:
            await context.bot.delete_message(
                message_id=update.effective_message.id,
                chat_id=update.effective_chat.id
            )
        finally:
            return result

    return wrapper


def exit_conversation_on_exception(
        user_message: str = "I'm sorry, something went wrong, try again or contact an Administrator."
):
    def inner_decorator(f: Callable[[Update, ApplicationContext], Any]):

        @wraps(f)
        async def wrapped(update: Update, context: ApplicationContext):
            try:
                return await f(update, context)
            except:
                await context.bot.send_message(
                    chat_id=update.effective_chat.id,
                    text=user_message
                )
            context.chat_data.conversation_data = None
            return ConversationHandler.END

        return wrapped

    return inner_decorator
