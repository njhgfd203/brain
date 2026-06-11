"""Reply-клавиатура главного меню."""
from __future__ import annotations

from aiogram.types import KeyboardButton, ReplyKeyboardMarkup

BTN_TODAY = "📋 Сегодня"
BTN_WEEK = "🗓 Неделя"
BTN_HABITS = "🔁 Привычки"
BTN_TASK = "➕ Задача"
BTN_MEET = "🤝 Встреча"
BTN_NOTE = "📝 Заметка"

main_keyboard = ReplyKeyboardMarkup(
    keyboard=[
        [
            KeyboardButton(text=BTN_TODAY),
            KeyboardButton(text=BTN_WEEK),
            KeyboardButton(text=BTN_HABITS),
        ],
        [
            KeyboardButton(text=BTN_TASK),
            KeyboardButton(text=BTN_MEET),
            KeyboardButton(text=BTN_NOTE),
        ],
    ],
    resize_keyboard=True,
    is_persistent=True,
)
