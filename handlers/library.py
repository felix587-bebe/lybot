import secrets
from aiogram import Router, F, Bot
from aiogram.types import (
    Message, CallbackQuery, URLInputFile,
    InlineKeyboardMarkup, InlineKeyboardButton
)
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from ytmusic import search as yt_search, get_stream_url
from keyboards import (
    get_playlists_menu_kb,
    get_playlist_menu_kb,
    get_playlist_settings_kb,
    get_library_tracks_kb,
    get_track_kb,
    get_back_kb,
)
from database import (
    create_playlist, get_user_playlists, get_playlist,
    delete_playlist, rename_playlist, set_playlist_public,
    add_track_to_library, get_library_tracks, delete_track_from_library,
    save_shared_track, increment_stat, get_stats,
    update_track_file_id,
)

router = Router()


def trim(text: str, limit: int = 60) -> str:
    text = (text or "").strip() or "Без названия"
    return text if len(text) <= limit else text[:limit - 3] + "..."


async def safe_answer(callback: CallbackQuery, text: str = None):
    try:
        if text:
            await callback.answer(text)
        else:
            await callback.answer()
    except Exception as e:
        print(f"[CALLBACK ERROR] {e}")


async def safe_edit(message: Message, text: str, kb):
    try:
        await message.edit_text(text, reply_markup=kb, parse_mode="HTML")
    except Exception:
        await message.answer(text, reply_markup=kb, parse_mode="HTML")


class PLStates(StatesGroup):
    waiting_query = State()
    waiting_pick = State()
    waiting_name = State()


@router.callback_query(F.data == "playlists_menu")
async def playlists_menu(callback: CallbackQuery):
    await callback.message.answer(
        "Плейлисты\n\nСобирай свои треки и делись ими.",
        reply_markup=get_playlists_menu_kb(),
        parse_mode="HTML"
    )
    await safe_answer(callback)


@router.callback_query(F.data == "my_playlists")
async def my_playlists(callback: CallbackQuery):
    playlists = await get_user_playlists(callback.from_user.id)

    if not playlists:
        await safe_edit(
            callback.message,
            "У тебя пока нет плейлистов.",
            get_playlists_menu_kb()
        )
        await safe_answer(callback)
        return

    buttons = []
    for pl_id, name, is_public in playlists:
        icon = "🔓" if is_public else "📁"
        buttons.append([InlineKeyboardButton(text=f"{icon} {name}", callback_data=f"open_pl_{pl_id}")])
    buttons.append([InlineKeyboardButton(text="Новый плейлист", callback_data="create_playlist")])
    buttons.append([InlineKeyboardButton(text="Назад", callback_data="playlists_menu")])

    await safe_edit(
        callback.message,
        "Твои плейлисты:",
        InlineKeyboardMarkup(inline_keyboard=buttons)
    )
    await safe_answer(callback)


@router.callback_query(F.data == "create_playlist")
async def create_playlist_start(callback: CallbackQuery, state: FSMContext):
    await state.update_data(rename_pl=None)
    await state.set_state(PLStates.waiting_name)
    await callback.message.answer(
        "Новый плейлист\n\nВведи название:",
        reply_markup=get_back_kb(),
        parse_mode="HTML"
    )
    await safe_answer(callback)


@router.message(PLStates.waiting_name)
async def create_playlist_process(message: Message, state: FSMContext):
    if not message.text:
        return
    name = message.text.strip()
    if not name or len(name) > 32:
        await message.answer("Название: 1-32 символа.")
        return

    data = await state.get_data()
    rename_pl = data.get("rename_pl")

    if rename_pl:
        await rename_playlist(rename_pl, name)
        pl = await get_playlist(rename_pl)
        await message.answer(
            f"Переименовано в <b>{name}</b>",
            reply_markup=get_playlist_menu_kb(rename_pl, pl[2] if pl else 0),
            parse_mode="HTML"
        )
    else:
        pl_id = await create_playlist(message.from_user.id, name)
        await message.answer(
            f"Плейлист <b>{name}</b> создан.",
            reply_markup=get_playlist_menu_kb(pl_id),
            parse_mode="HTML"
        )

    await state.clear()


@router.callback_query(F.data.startswith("open_pl_"))
async def open_playlist(callback: CallbackQuery, state: FSMContext):
    pl_id = int(callback.data.split("_")[2])
    pl = await get_playlist(pl_id)

    if not pl:
        await safe_answer(callback, "Плейлист не найден.")
        return

    await state.update_data(current_pl=pl_id)

    text = f"<b>{pl[1]}</b>"
    kb = get_playlist_menu_kb(pl_id, pl[2])

    await safe_edit(callback.message, text, kb)
    await safe_answer(callback)


@router.callback_query(F.data.startswith("tracks_pl_"))
async def open_tracks(callback: CallbackQuery, state: FSMContext):
    pl_id = int(callback.data.split("_")[2])
    pl = await get_playlist(pl_id)

    if not pl:
        await safe_answer(callback, "Плейлист не найден.")
        return

    tracks = await get_library_tracks(pl_id)
    await state.update_data(current_pl=pl_id)

    if not tracks:
        await safe_edit(
            callback.message,
            f"<b>{pl[1]}</b>\n\nПлейлист пуст.",
            get_playlist_menu_kb(pl_id, pl[2])
        )
        await safe_answer(callback)
        return

    total_pages = (len(tracks) + 5) // 6
    text = f"<b>{pl[1]}</b> ({len(tracks)} треков)\nСтраница: 1/{total_pages}\n\nВыбери трек:"
    kb = get_library_tracks_kb(tracks, pl_id, page=0)

    await safe_edit(callback.message, text, kb)
    await safe_answer(callback)


@router.callback_query(F.data.startswith("pl_page_"))
async def playlist_page(callback: CallbackQuery, state: FSMContext):
    _, _, pl_id, page = callback.data.split("_")
    pl_id, page = int(pl_id), int(page)
    pl = await get_playlist(pl_id)

    if not pl:
        await safe_answer(callback, "Плейлист не найден.")
        return

    tracks = await get_library_tracks(pl_id)
    total_pages = (len(tracks) + 5) // 6

    text = f"<b>{pl[1]}</b> ({len(tracks)} треков)\nСтраница: {page+1}/{total_pages}\n\nВыбери трек:"
    kb = get_library_tracks_kb(tracks, pl_id, page=page)

    await safe_edit(callback.message, text, kb)
    await safe_answer(callback)


@router.callback_query(F.data.startswith("pl_settings_"))
async def playlist_settings(callback: CallbackQuery):
    pl_id = int(callback.data.split("_")[2])
    pl = await get_playlist(pl_id)

    if not pl:
        await safe_answer(callback, "Не найден.")
        return

    text = f"Настройки плейлиста <b>{pl[1]}</b>"
    if pl[2] and len(pl) > 3 and pl[3]:
        me = await callback.bot.get_me()
        text += (
            f"\n\nНомер: <code>{pl[3]}</code>"
            f"\nИнлайн: <code>@{me.username} {pl[3]}</code>"
        )

    await safe_edit(
        callback.message,
        text,
        get_playlist_settings_kb(pl_id, pl[2])
    )
    await safe_answer(callback)


@router.callback_query(F.data.startswith("toggle_pub_"))
async def toggle_pub(callback: CallbackQuery):
    pl_id = int(callback.data.split("_")[2])
    pl = await get_playlist(pl_id)

    if not pl:
        await safe_answer(callback, "Не найден.")
        return

    new_state = 0 if pl[2] else 1
    await set_playlist_public(pl_id, new_state)

    pl = await get_playlist(pl_id)

    if new_state:
        me = await callback.bot.get_me()
        await callback.message.answer(
            f"Плейлист <b>{pl[1]}</b> теперь публичный.\n\n"
            f"Номер: <code>{pl[3]}</code>\n\n"
            f"Юзеры могут найти его в инлайне:\n"
            f"<code>@{me.username} {pl[3]}</code>",
            parse_mode="HTML"
        )
    else:
        await safe_answer(callback, "Приватный")

    text = f"Настройки плейлиста <b>{pl[1]}</b>"
    if pl[2] and pl[3]:
        me = await callback.bot.get_me()
        text += (
            f"\n\nНомер: <code>{pl[3]}</code>"
            f"\nИнлайн: <code>@{me.username} {pl[3]}</code>"
        )

    await safe_edit(
        callback.message,
        text,
        get_playlist_settings_kb(pl_id, pl[2])
    )


@router.callback_query(F.data.startswith("recache_pl_"))
async def recache_playlist(callback: CallbackQuery):
    pl_id = int(callback.data.split("_")[2])
    tracks = await get_library_tracks(pl_id)

    to_cache = [t for t in tracks if not t[2] and t[1]]

    if not to_cache:
        await safe_answer(callback, "Все треки уже закешированы")
        return

    await safe_answer(callback, f"Кеширую {len(to_cache)} треков...")
    msg = await callback.message.answer(f"Кеширую 0/{len(to_cache)}...")

    cached = 0
    for i, (track_id, yandex_id, file_id, title, artist) in enumerate(to_cache, 1):
        try:
            stream_url = await get_stream_url(yandex_id)
            if not stream_url:
                continue

            audio = URLInputFile(stream_url, filename=f"{artist} - {title}.mp3")
            sent = await callback.message.answer_audio(
                audio, title=title, performer=artist,
                disable_notification=True
            )
            if sent.audio:
                await update_track_file_id(track_id, sent.audio.file_id)
                cached += 1
                try:
                    await sent.delete()
                except Exception:
                    pass

            await msg.edit_text(f"Кеширую {i}/{len(to_cache)}...")
        except Exception as e:
            print(f"[RECACHE ERROR] {e}")

    await msg.edit_text(
        f"Закешировано {cached}/{len(to_cache)} треков.\n"
        f"Теперь они появятся в инлайне по номеру плейлиста."
    )


@router.callback_query(F.data.startswith("share_pl_"))
async def share_playlist(callback: CallbackQuery, bot: Bot):
    pl_id = int(callback.data.split("_")[2])
    pl = await get_playlist(pl_id)

    if not pl:
        await safe_answer(callback, "Не найден.")
        return

    if pl[2] and len(pl) > 3 and pl[3]:
        me = await bot.get_me()
        await callback.message.answer(
            f"Поделиться плейлистом <b>{pl[1]}</b>\n\n"
            f"Номер: <code>{pl[3]}</code>\n\n"
            f"Отправь другу или введи в инлайне:\n"
            f"<code>@{me.username} {pl[3]}</code>\n\n"
            f"Он увидит все треки из плейлиста.",
            reply_markup=get_playlist_menu_kb(pl_id, pl[2]),
            parse_mode="HTML"
        )
        await safe_answer(callback)
        return

    await callback.message.answer(
        f"Плейлист <b>{pl[1]}</b> приватный.\n\n"
        f"Поделиться можно только публичным плейлистом.\n\n"
        f"Что делать:\n"
        f"1. Открой Настройки плейлиста\n"
        f"2. Жми Сделать публичным\n"
        f"3. Получи номер (например <code>0275</code>)\n"
        f"4. Делись: <code>@lybot 0275</code> в любом чате\n\n"
        f"Так работает инлайн-режим, только для публичных плейлистов.",
        reply_markup=get_playlist_menu_kb(pl_id, pl[2]),
        parse_mode="HTML"
    )
    await safe_answer(callback)


@router.callback_query(F.data.startswith("rename_pl_"))
async def rename_pl_start(callback: CallbackQuery, state: FSMContext):
    pl_id = int(callback.data.split("_")[2])
    await state.update_data(rename_pl=pl_id)
    await state.set_state(PLStates.waiting_name)
    await callback.message.answer(
        "Введи новое название плейлиста:",
        reply_markup=get_back_kb()
    )
    await safe_answer(callback)


@router.callback_query(F.data.startswith("del_pl_"))
async def delete_playlist_confirm(callback: CallbackQuery):
    pl_id = int(callback.data.split("_")[2])
    await delete_playlist(pl_id)
    await safe_answer(callback, "Удалено")
    await my_playlists(callback)


@router.callback_query(F.data.startswith("add_pl_"))
async def add_track_start(callback: CallbackQuery, state: FSMContext):
    pl_id = int(callback.data.split("_")[2])
    await state.update_data(add_pl=pl_id)
    await state.set_state(PLStates.waiting_query)
    await callback.message.answer(
        "Добавить трек\n\nВведи название или отправь mp3:",
        reply_markup=get_back_kb(),
        parse_mode="HTML"
    )
    await safe_answer(callback)


@router.message(PLStates.waiting_query, F.audio | F.document)
async def add_track_file(message: Message, state: FSMContext):
    data = await state.get_data()
    pl_id = data.get("add_pl")
    if not pl_id:
        await message.answer("Сначала открой плейлист.")
        return

    file_id = None
    title = "Без названия"
    artist = "Unknown"

    if message.audio:
        file_id = message.audio.file_id
        title = message.audio.title or message.audio.file_name or "Без названия"
        artist = message.audio.performer or "Unknown"
    elif message.document:
        file_id = message.document.file_id
        title = message.document.file_name or "Без названия"

    if not file_id:
        await message.answer("Не удалось получить file_id.")
        return

    await add_track_to_library(pl_id, title, artist, file_id=file_id)
    await increment_stat(message.from_user.id, "tracks_added")

    pl = await get_playlist(pl_id)
    await message.answer(
        f"Добавлено: {trim(f'{artist} - {title}', 200)}",
        reply_markup=get_playlist_menu_kb(pl_id, pl[2] if pl else 0),
        parse_mode="HTML"
    )
    await state.clear()


@router.message(PLStates.waiting_query)
async def add_track_search(message: Message, state: FSMContext):
    if not message.text:
        return
    query = message.text.strip()
    if not query:
        return

    msg = await message.answer("Ищу...")
    try:
        tracks = await yt_search(query)
    except Exception as e:
        await msg.edit_text(f"Ошибка: {e}")
        return

    if not tracks:
        await msg.edit_text("Ничего не найдено.", reply_markup=get_back_kb())
        return

    tracks_data = []
    for i, t in enumerate(tracks):
        tracks_data.append({"index": i, "id": t["id"], "title": t["title"], "artist": t["artist"]})

    await state.update_data(tracks=tracks_data)

    buttons = []
    for t in tracks_data:
        text = trim(f"{t['artist']} - {t['title']}", 40)
        buttons.append([InlineKeyboardButton(
            text=text,
            callback_data=f"add_pick_{t['index']}"
        )])
    buttons.append([InlineKeyboardButton(text="Назад", callback_data="playlists_menu")])

    await msg.edit_text(
        f"Найдено: {query}\n\nВыбери:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons),
        parse_mode="HTML"
    )
    await state.set_state(PLStates.waiting_pick)


@router.callback_query(PLStates.waiting_pick, F.data.startswith("add_pick_"))
async def add_track_pick(callback: CallbackQuery, state: FSMContext):
    idx = int(callback.data.split("_")[2])
    data = await state.get_data()
    tracks = data.get("tracks", [])
    pl_id = data.get("add_pl")

    if not tracks or idx >= len(tracks) or not pl_id:
        await safe_answer(callback, "Ошибка.")
        return

    t = tracks[idx]
    file_id = None
    await safe_answer(callback, "Загружаю трек...")

    try:
        stream_url = await get_stream_url(t["id"])
        if stream_url:
            audio = URLInputFile(stream_url, filename=f"{t['artist']} - {t['title']}.mp3")
            sent = await callback.message.answer_audio(
                audio, title=t["title"], performer=t["artist"],
                disable_notification=True
            )
            if sent.audio:
                file_id = sent.audio.file_id
                try:
                    await sent.delete()
                except Exception:
                    pass
    except Exception as e:
        print(f"[ADD_PICK CACHE ERROR] {e}")

    await add_track_to_library(
        pl_id, t["title"], t["artist"],
        file_id=file_id, yandex_id=t["id"]
    )
    await increment_stat(callback.from_user.id, "tracks_added")

    pl = await get_playlist(pl_id)
    cache_note = "закеширован" if file_id else "без file_id"
    result_text = f"Добавлено: {trim(f'{t['artist']} - {t['title']}', 200)}\n({cache_note})"
    try:
        await callback.message.edit_text(
            result_text,
            reply_markup=get_playlist_menu_kb(pl_id, pl[2] if pl else 0),
            parse_mode="HTML"
        )
    except Exception:
        await callback.message.answer(
            result_text,
            reply_markup=get_playlist_menu_kb(pl_id, pl[2] if pl else 0),
            parse_mode="HTML"
        )
    await state.clear()


@router.callback_query(F.data.startswith("pl_play_"))
async def pl_play(callback: CallbackQuery, state: FSMContext):
    _, _, pl_id, idx = callback.data.split("_")
    pl_id, idx = int(pl_id), int(idx)

    tracks = await get_library_tracks(pl_id)
    if idx >= len(tracks):
        await safe_answer(callback, "Трек не найден.")
        return

    track_id, yandex_id, file_id, title, artist = tracks[idx]
    await safe_answer(callback, "Загружаю...")

    if file_id:
        share_id = "muz" + secrets.token_hex(3)
        await save_shared_track(share_id, file_id=file_id, title=title, artist=artist)
        await increment_stat(callback.from_user.id, "shares_count")

        kb = get_track_kb(pl_id, share_id)
        await callback.message.answer_audio(
            file_id,
            title=title,
            performer=artist,
            caption=f"{trim(f'{artist} - {title}', 200)}\n\n<code>{share_id}</code>",
            reply_markup=kb,
            parse_mode="HTML"
        )
        return

    if yandex_id:
        share_id = "muz" + secrets.token_hex(3)
        await save_shared_track(share_id, yandex_id=yandex_id, title=title, artist=artist)
        await increment_stat(callback.from_user.id, "shares_count")

        try:
            stream_url = await get_stream_url(yandex_id)
            if not stream_url:
                raise Exception("Нет ссылки")

            kb = get_track_kb(pl_id, share_id)
            audio = URLInputFile(stream_url, filename=f"{artist} - {title}.mp3")
            sent = await callback.message.answer_audio(
                audio, title=title, performer=artist,
                caption=f"{trim(f'{artist} - {title}', 200)}\n\n<code>{share_id}</code>",
                reply_markup=kb, parse_mode="HTML"
            )
            if sent.audio:
                await update_track_file_id(track_id, sent.audio.file_id)
        except Exception as e:
            await callback.message.answer(f"Ошибка: {e}")
        return


@router.callback_query(F.data == "stats")
async def show_stats(callback: CallbackQuery):
    tracks_added, shares_count = await get_stats(callback.from_user.id)
    await callback.message.answer(
        f"Твоя статистика\n\n"
        f"Добавлено: <b>{tracks_added}</b>\n"
        f"Поделился: <b>{shares_count}</b>",
        reply_markup=get_playlists_menu_kb(),
        parse_mode="HTML"
    )
    await safe_answer(callback)
