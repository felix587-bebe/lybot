from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton


def get_main_menu_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔍 Найти трек", callback_data="find_music")],
        [InlineKeyboardButton(text="🎵 Плейлисты", callback_data="playlists_menu")],
    ])


def get_back_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔙 Назад", callback_data="back_main")]
    ])


def get_playlists_menu_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📁 Мои плейлисты", callback_data="my_playlists")],
        [InlineKeyboardButton(text="➕ Новый плейлист", callback_data="create_playlist")],
        [InlineKeyboardButton(text="📊 Статистика", callback_data="stats")],
        [InlineKeyboardButton(text="🔙 Назад", callback_data="back_main")],
    ])


def get_playlist_menu_kb(playlist_id: int, is_public: int = 0):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🎵 Открыть", callback_data=f"tracks_pl_{playlist_id}")],
        [InlineKeyboardButton(text="➕ Добавить трек", callback_data=f"add_pl_{playlist_id}")],
        [InlineKeyboardButton(text="⚙️ Настройки", callback_data=f"pl_settings_{playlist_id}")],
        [InlineKeyboardButton(text="🔙 К плейлистам", callback_data="my_playlists")],
    ])


def get_playlist_settings_kb(playlist_id: int, is_public: int = 0):
    pub_text = "🔓 Сделать приватным" if is_public else "🔒 Сделать публичным"
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✏️ Переименовать", callback_data=f"rename_pl_{playlist_id}")],
        [InlineKeyboardButton(text=pub_text, callback_data=f"toggle_pub_{playlist_id}")],
        [InlineKeyboardButton(text="🔄 Обновить кеш", callback_data=f"recache_pl_{playlist_id}")],
        [InlineKeyboardButton(text="📤 Поделиться", callback_data=f"share_pl_{playlist_id}")],
        [InlineKeyboardButton(text="🗑 Удалить", callback_data=f"del_pl_{playlist_id}")],
        [InlineKeyboardButton(text="🔙 Назад", callback_data=f"open_pl_{playlist_id}")],
    ])


def get_library_tracks_kb(tracks, playlist_id: int, page: int = 0):
    buttons = []
    start = page * 6
    end = start + 6

    for i, track in enumerate(tracks[start:end]):
        track_id, yandex_id, file_id, title, artist = track
        idx = start + i
        text = f"🎵 {artist} - {title}"
        if len(text) > 60:
            text = text[:57] + "..."
        buttons.append([
            InlineKeyboardButton(text=text, callback_data=f"pl_play_{playlist_id}_{idx}")
        ])

    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton(text="⬅️", callback_data=f"pl_page_{playlist_id}_{page-1}"))
    if end < len(tracks):
        nav.append(InlineKeyboardButton(text="➡️", callback_data=f"pl_page_{playlist_id}_{page+1}"))
    if nav:
        buttons.append(nav)

    buttons.append([InlineKeyboardButton(text="🔙 К плейлистам", callback_data="my_playlists")])

    return InlineKeyboardMarkup(inline_keyboard=buttons)


def get_track_kb(playlist_id: int, share_id: str = None):
    buttons = []
    if share_id:
        buttons.append([
            InlineKeyboardButton(text="📤 Поделиться", switch_inline_query=share_id)
        ])
    buttons.append([
        InlineKeyboardButton(text="🔙 Назад", callback_data=f"open_pl_{playlist_id}")
    ])
    return InlineKeyboardMarkup(inline_keyboard=buttons)
