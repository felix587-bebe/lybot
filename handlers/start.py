from aiogram import Router, F
from aiogram.filters import CommandStart, CommandObject
from aiogram.types import (
    Message, CallbackQuery,
    InlineKeyboardMarkup, InlineKeyboardButton,
)
from keyboards import get_main_menu_kb
from database import get_playlist, get_library_tracks

router = Router()


# ============================================================
# /start — открытие бота и плейлиста по ссылке
# ============================================================

@router.message(CommandStart())
async def cmd_start(message: Message, command: CommandObject = None):
    args = command.args if command else None

    # ===== Открытие плейлиста по ссылке =====
    if args and args.startswith("pl_"):
        try:
            pl_id = int(args.replace("pl_", ""))
        except ValueError:
            await message.answer("❌ Неверная ссылка.")
            return

        pl = await get_playlist(pl_id)
        if not pl:
            await message.answer(
                "❌ Плейлист не найден.\n\n"
                "Возможно, он был удалён или ссылка устарела."
            )
            return

        # pl = (id, name, is_public, public_number)
        _, pl_name, is_public, public_number = pl

        # ===== Публичный — даём номер для инлайна =====
        if is_public and public_number:
            me = await message.bot.get_me()
            await message.answer(
                f"📁 <b>{pl_name}</b> — публичный плейлист.\n\n"
                f"🔢 Номер: <code>{public_number}</code>\n\n"
                f"Чтобы посмотреть все треки — введи в любом чате:\n"
                f"<code>@{me.username} {public_number}</code>",
                parse_mode="HTML"
            )
            return

        # ===== Приватный — объясняем что ссылки не работают =====
        await message.answer(
            f"🔒 Плейлист <b>{pl_name}</b> приватный.\n\n"
            f"Ссылки на приватные плейлисты больше не работают.\n\n"
            f"Попроси владельца сделать его <b>публичным</b> — "
            f"тогда он сможет поделиться <b>номером</b> для инлайн-поиска.",
            parse_mode="HTML"
        )
        return

    # ===== Обычный старт =====
    await message.answer(
        "🎵 <b>LyBot</b>\n\n"
        "Привет! Я ищу музыку, собираю плейлисты и делюсь треками.\n\n"
        "Выбери действие:",
        reply_markup=get_main_menu_kb(),
        parse_mode="HTML"
    )


# ============================================================
# Возврат в главное меню
# ============================================================

@router.callback_query(F.data == "back_main")
async def back_main(callback: CallbackQuery):
    try:
        await callback.message.edit_text(
            "🎵 <b>LyBot</b>\n\nВыбери действие:",
            reply_markup=get_main_menu_kb(),
            parse_mode="HTML"
        )
    except Exception:
        await callback.message.answer(
            "🎵 <b>LyBot</b>\n\nВыбери действие:",
            reply_markup=get_main_menu_kb(),
            parse_mode="HTML"
        )
    try:
        await callback.answer()
    except Exception:
        pass
