import asyncio
import logging
import random
import time

from aiogram import Bot, Dispatcher, F
from aiogram.filters import CommandStart
from aiogram.types import (
    Message,
    ReplyKeyboardMarkup,
    KeyboardButton,
)

import config
import base

logging.basicConfig(level=logging.INFO)

from aiogram.client.session.aiohttp import AiohttpSession#для хостинга
session = AiohttpSession(proxy='http://proxy.server:3128') # в proxy указан прокси сервер pythonanywhere, он нужен для подключения
bot = Bot(token=config.TOKEN, session=session)
dp = Dispatcher()

# ── Reply-клавиатура ──────────────────────────────────────────────────────────
main_kb = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="🎁 Получить карту")],
        [KeyboardButton(text="📦 Мои карты"), KeyboardButton(text="🏆 Топ игроков")],
    ],
    resize_keyboard=True,
)

# Эмодзи редкостей
RARITY_EMOJI = {
    "Common":    "⚪",
    "Rare":      "🔵",
    "Epic":      "🟣",
    "Legendary": "🟡",
}


# ── /start ────────────────────────────────────────────────────────────────────
@dp.message(CommandStart())
async def cmd_start(message: Message):
    user = message.from_user
    if not await base.user_exists(user.id):
        await base.add_user(
            user.id,
            user.username or "",
            user.first_name or "",
            user.last_name or "",
        )
    await message.answer(
        f"Привет, {user.first_name}! 👋\nВыбери действие:",
        reply_markup=main_kb,
    )


# ── 🎁 Получить карту ─────────────────────────────────────────────────────────
@dp.message(F.text == "🎁 Получить карту")
async def claim_card(message: Message):
    user_id = message.from_user.id

    if not await base.user_exists(user_id):
        await base.add_user(
            user_id,
            message.from_user.username or "",
            message.from_user.first_name or "",
            message.from_user.last_name or "",
        )

    user = await base.get_user(user_id)
    now = int(time.time())
    elapsed = now - (user["last_claim_time"] or 0)
    remaining = config.COOLDOWN_SECONDS - elapsed

    if remaining > 0:
        minutes = remaining // 60
        seconds = remaining % 60
        await message.answer(f"⏳ Подожди ещё {minutes} мин. {seconds} сек.")
        return

    cards = await base.get_all_cards()
    if not cards:
        await message.answer("😔 Карточек пока нет.")
        return

    weights = [c["weight"] for c in cards]
    chosen = random.choices(cards, weights=weights, k=1)[0]

    await base.add_card_to_user(user_id, chosen["id"], chosen["points"])

    emoji = RARITY_EMOJI.get(chosen["rarity"], "⚫")
    await message.answer(
        f"🎉 Ты получил карту!\n\n"
        f"{emoji} {chosen['name']}\n"
        f"Редкость: {chosen['rarity']}\n"
        f"Очки: +{chosen['points']}",
        reply_markup=main_kb,
    )


# ── 📦 Мои карты ──────────────────────────────────────────────────────────────
@dp.message(F.text == "📦 Мои карты")
async def my_cards(message: Message):
    user_id = message.from_user.id
    cards = await base.get_user_cards(user_id)

    if not cards:
        await message.answer("У тебя пока нет карточек. Нажми 🎁 Получить карту!")
        return

    lines = []
    for c in cards:
        emoji = RARITY_EMOJI.get(c["rarity"], "⚫")
        lines.append(f"{emoji} {c['name']} ({c['rarity']}) — x{c['quantity']}")

    await message.answer("📦 Твои карточки:\n\n" + "\n".join(lines))


# ── 🏆 Топ игроков ────────────────────────────────────────────────────────────
@dp.message(F.text == "🏆 Топ игроков")
async def top_players(message: Message):
    users = await base.get_top_users(10)

    if not users:
        await message.answer("Пока никто не набрал очков.")
        return

    medals = ["🥇", "🥈", "🥉"]
    lines = []
    for i, u in enumerate(users):
        medal = medals[i] if i < 3 else f"{i + 1}."
        name = u["first_name"] or u["username"] or "Аноним"
        lines.append(f"{medal} {name} — {u['total_points']} очков")

    await message.answer("🏆 Топ 10 игроков:\n\n" + "\n".join(lines))


# ── Запуск ────────────────────────────────────────────────────────────────────
async def main():
    await base.init_db()
    logging.info("БД инициализирована, бот запускается...")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
