import asyncio
import os
import secrets
from aiogram import Router, F
from aiogram.types import (
    Message, CallbackQuery, FSInputFile,
    InlineKeyboardMarkup, InlineKeyboardButton,
)
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from ytmusic import search as yt_search, download_track
from keyboards import get_back_kb
from database import (
    save_shared_track,
    increment_stat,
    update_shared_file_id,
)

router = Router()


class SearchStates(StatesGroup):
    waiting_query = State()


@router.callback_query(F.data == "find_music")
async def find_music_start(callback: CallbackQuery, state: FSMContext):
    await state.set_state(SearchStates.waiting_query)
    await callback.message.answer(
        "Поиск трека\n\nВведи название или исполнителя:",
        reply_markup=get_back_kb(),
        parse_mode="HTML"
    )
    await callback.answer()


@router.message(SearchStates.waiting_query)
async def process_query(message: Message, state: FSMContext):
    query = message.text.strip()
    if not query:
        return

    msg = await message.answer("Ищу...")
    try:
        tracks = await asyncio.wait_for(yt_search(query, limit=5), timeout=15.0)
    except asyncio.TimeoutError:
        await _safe_edit(msg, "YouTube не ответил.", get_back_kb())
        await state.clear()
        return
    except Exception as e:
        await _safe_edit(msg, f"Ошибка: {e}", get_back_kb())
        await state.clear()
        return

    if not tracks:
        await _safe_edit(msg, "Ничего не найдено.", get_back_kb())
        await state.clear()
        return

    await state.update_data(tracks=tracks)

    buttons = []
    for i, t in enumerate(tracks):
        text = f"{t['artist']} - {t['title']}"
        if len(text) > 40:
            text = text[:37] + "..."
        buttons.append([InlineKeyboardButton(
            text=text,
            callback_data=f"pick_{i}"
        )])
    buttons.append([InlineKeyboardButton(text="Назад", callback_data="back_main")])

    await _safe_edit(
        msg,
        f"Найдено: {query}\n\nВыбери:",
        InlineKeyboardMarkup(inline_keyboard=buttons)
    )


async def _safe_edit(msg: Message, text: str, kb=None):
    try:
        await msg.edit_text(text, reply_markup=kb, parse_mode="HTML")
    except Exception:
        await msg.answer(text, reply_markup=kb, parse_mode="HTML")


@router.callback_query(F.data.startswith("pick_"))
async def pick_track(callback: CallbackQuery, state: FSMContext):
    index = int(callback.data.split("_")[1])
    data = await state.get_data()
    tracks = data.get("tracks", [])

    if not tracks or index >= len(tracks):
        await callback.answer("Трек не найден.")
        return

    t = tracks[index]
    await callback.answer("Скачиваю...")
    msg = await callback.message.answer("⏳ Скачиваю трек, подожди...")

    file_path = None
    try:
        file_path = await asyncio.wait_for(download_track(t["id"]), timeout=60.0)
        if not file_path:
            raise Exception("Не удалось скачать")

        share_id = "muz" + secrets.token_hex(3)
        await save_shared_track(
            share_id,
            yandex_id=t["id"],
            title=t["title"],
            artist=t["artist"],
        )
        await increment_stat(callback.from_user.id, "shares_count")

        share_kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(
                text="Отправить в чат",
                switch_inline_query=share_id
            )],
            [InlineKeyboardButton(text="В меню", callback_data="back_main")]
        ])

        audio = FSInputFile(file_path, filename=f"{t['artist']} - {t['title']}.mp3")
        sent = await callback.message.answer_audio(
            audio, title=t["title"], performer=t["artist"],
            caption=f"{t['artist']} - {t['title']}\n\n<code>{share_id}</code>",
            reply_markup=share_kb, parse_mode="HTML"
        )
        if sent.audio:
            await update_shared_file_id(share_id, sent.audio.file_id)

        await msg.delete()
    except Exception as e:
        print(f"[PICK ERROR] {e}")
        await msg.edit_text(f"Ошибка: {e}", reply_markup=get_back_kb())
    finally:
        # Чистим временный файл
        if file_path and os.path.exists(file_path):
            try:
                os.remove(file_path)
            except Exception:
                pass

    await state.clear()
