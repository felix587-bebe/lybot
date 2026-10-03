import re
from aiogram import Router, F
from aiogram.types import (
    InlineQuery,
    InlineQueryResultCachedAudio,
    InlineQueryResultArticle,
    InputTextMessageContent,
)
from database import (
    get_shared_track,
    get_playlist_by_number,
    get_playlist_tracks_paginated,
    search_all_tracks,
)

router = Router()

# Почему убраны прямые YouTube-ссылки (InlineQueryResultAudio с audio_url
# из yt-dlp) из инлайна:
#
# Telegram сам идёт по audio_url своим сервером, чтобы прочитать метаданные
# и показать превью в списке результатов. CDN-ссылки googlevideo.com,
# которые отдаёт yt-dlp, привязаны к IP/сессии клиента, который их добывал
# (т.е. к нашему серверу), и часто живут считаные минуты. Когда их дёргает
# сервер Telegram с другого IP — CDN их не отдаёт, и в инлайне появляется
# ровно то, что было на скриншоте: "Неизвестен", "0:00 / -:--" и красный
# восклицательный знак (Telegram не смог прочитать файл по ссылке).
#
# Единственный надёжный способ отдавать аудио в инлайне — заранее
# закачать трек через бота (answer_audio), получить file_id и дальше
# отдавать его через InlineQueryResultCachedAudio. Именно так уже устроен
# путь через поиск в боте (handlers/search.py) и плейлисты — инлайн теперь
# работает ТОЛЬКО с уже закэшированными треками (есть file_id), а не лезет
# за свежей YouTube-ссылкой напрямую.


@router.inline_query()
async def inline_music(query: InlineQuery):
    search_text = query.query.strip()
    if not search_text:
        await query.answer([], cache_time=0, is_personal=True)
        return

    # ===== ПОИСК ПО НОМЕРУ ПЛЕЙЛИСТА =====
    m = re.match(r"^(\d{4})(?:_(\d+))?$", search_text)
    if m:
        public_number = m.group(1)
        page = int(m.group(2)) if m.group(2) else 1

        pl = await get_playlist_by_number(public_number)
        if not pl:
            await query.answer([], cache_time=0, is_personal=True)
            return

        playlist_id, pl_name, owner_id = pl
        tracks, total = await get_playlist_tracks_paginated(playlist_id, page, per_page=10)

        if not tracks:
            await query.answer([], cache_time=0, is_personal=True)
            return

        results = []
        for track_id, yandex_id, file_id, title, artist in tracks:
            if not file_id:
                continue
            results.append(InlineQueryResultCachedAudio(
                id=f"pl_{playlist_id}_{track_id}",
                audio_file_id=file_id,
                title=title or "Без названия",
                performer=artist or "Unknown",
            ))

        total_pages = (total + 9) // 10
        if page < total_pages:
            me = await query.bot.get_me()
            next_page = page + 1
            results.append(InlineQueryResultArticle(
                id=f"pl_next_{playlist_id}_{next_page}",
                title=f"Следующая страница ({next_page}/{total_pages})",
                description=f"Введи: @{me.username} {public_number}_{next_page}",
                input_message_content=InputTextMessageContent(
                    message_text=(
                        f"<b>{pl_name}</b> - страница {next_page}/{total_pages}\n\n"
                        f"Введи в инлайне: <code>@{me.username} {public_number}_{next_page}</code>"
                    ),
                    parse_mode="HTML",
                ),
            ))

        await query.answer(results, cache_time=10, is_personal=False)
        return

    # ===== ПОИСК ПО SHARE_ID =====
    if search_text.startswith("muz"):
        track = await get_shared_track(search_text)

        if not track:
            await query.answer([], cache_time=0, is_personal=True)
            return

        yandex_id, file_id, title, artist = track

        if file_id:
            await query.answer(
                [InlineQueryResultCachedAudio(
                    id=search_text,
                    audio_file_id=file_id,
                    title=title or "Без названия",
                    performer=artist or "Unknown",
                )],
                cache_time=0, is_personal=True
            )
            return

        # Трек расшарен, но ещё не закэширован (file_id нет) — раньше тут
        # дёргали прямую YouTube-ссылку, что и ломалось. Вместо этого
        # честно говорим, что нужно открыть ссылку в самом боте один раз.
        me = await query.bot.get_me()
        await query.answer(
            [InlineQueryResultArticle(
                id=search_text,
                title="Трек ещё не готов для инлайна",
                description="Открой ссылку в самом боте — после этого можно будет отправлять сюда",
                input_message_content=InputTextMessageContent(
                    message_text=(
                        f"Этот трек ещё не закэширован для инлайна.\n\n"
                        f"Открой @{me.username} и воспользуйся поиском — "
                        f"после первого скачивания трек можно будет "
                        f"пересылать через инлайн."
                    ),
                ),
            )],
            cache_time=0, is_personal=True
        )
        return

    # ===== ПОИСК ПО ТЕКСТУ (только закешированные из БД) =====
    cached = await search_all_tracks(search_text, limit=8)

    results = []
    for track_id, yandex_id, file_id, title, artist, pl_id, pl_name in cached:
        if not file_id:
            continue
        results.append(InlineQueryResultCachedAudio(
            id=f"db_{track_id}",
            audio_file_id=file_id,
            title=title or "Без названия",
            performer=artist or "Unknown",
        ))

    if results:
        await query.answer(results, cache_time=10, is_personal=False)
        return

    # Ничего закэшированного не нашлось — свежий YouTube-поиск сюда
    # больше не лезет (см. комментарий сверху). Подсказываем, что искать
    # нужно в самом боте, тогда трек попадёт в кэш и станет доступен в инлайне.
    me = await query.bot.get_me()
    await query.answer(
        [InlineQueryResultArticle(
            id="not_cached",
            title="Ничего не найдено в кэше",
            description="Найди трек через поиск в самом боте — тогда он появится в инлайне",
            input_message_content=InputTextMessageContent(
                message_text=(
                    f"По запросу «{search_text}» ничего не нашлось среди "
                    f"уже закэшированных треков.\n\n"
                    f"Открой @{me.username} → «🔍 Найти трек», скачай его там "
                    f"один раз — после этого он появится и в инлайн-поиске."
                ),
            ),
        )],
        cache_time=0, is_personal=True
    )
