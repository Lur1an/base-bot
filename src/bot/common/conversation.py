from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import Any
from sqlalchemy import Update
from telegram.ext import ConversationHandler
from src.bot.common.context import ApplicationContext

@dataclass(slots=True)
class ConversationBuilder:
    per_user: bool = True
    per_chat: bool = True
    per_message: bool = False
    allow_reentry: bool = False
    name: str | None = None
    persistent: bool = False
    map_to_parent: dict[object, object] | None = None
    states: dict = field(default_factory=dict)
    fallbacks: list = field(default_factory=list)
    entry_points: list = field(default_factory=list)

    def add_state(self, state: Any):
        def decorator(handler: Callable[[Update, ApplicationContext], Awaitable[Any]]):
            self.states[state] = handler
        return decorator

    def add_entry_point(self, handler: Callable[[Update, ApplicationContext], Awaitable[Any]]):
        self.entry_points.append(handler)

    def add_fallback(self, handler: Callable[[Update, ApplicationContext], Awaitable[Any]]):
        self.fallbacks.append(handler)

    def build(self):
        return ConversationHandler(
            entry_points=self.entry_points,
            states=self.states,
            fallbacks=self.fallbacks,
            per_user=self.per_user,
            per_chat=self.per_chat,
            per_message=self.per_message,
            allow_reentry=self.allow_reentry,
            name=self.name,
            persistent=self.persistent,
            map_to_parent=self.map_to_parent
        )
