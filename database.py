import aiosqlite
import random
from config import DB_PATH


async def _add_column_if_missing(db, table: str, column: str, definition: str):
    cur = await db.execute(f"PRAGMA table_info({table})")
    cols = [row[1] for row in await cur.fetchall()]
    if column not in cols:
        await db.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")


async def init_db():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS playlists (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                name TEXT,
                is_public INTEGER DEFAULT 0,
                created_at INTEGER
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS library_tracks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                playlist_id INTEGER,
                title TEXT,
                artist TEXT,
                file_id TEXT,
                yandex_id TEXT,
                is_public INTEGER DEFAULT 0
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS shared_tracks (
                share_id TEXT PRIMARY KEY,
                yandex_id TEXT,
                file_id TEXT,
                title TEXT,
                artist TEXT
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS stats (
                user_id INTEGER PRIMARY KEY,
                tracks_added INTEGER DEFAULT 0,
                shares_count INTEGER DEFAULT 0
            )
        """)

        await _add_column_if_missing(db, "playlists", "is_public", "INTEGER DEFAULT 0")
        await _add_column_if_missing(db, "playlists", "public_number", "TEXT")
        await _add_column_if_missing(db, "library_tracks", "is_public", "INTEGER DEFAULT 0")
        await _add_column_if_missing(db, "shared_tracks", "file_id", "TEXT")
        await _add_column_if_missing(db, "shared_tracks", "yandex_id", "TEXT")
        await _add_column_if_missing(db, "shared_tracks", "title", "TEXT")
        await _add_column_if_missing(db, "shared_tracks", "artist", "TEXT")

        await db.execute(
            "CREATE UNIQUE INDEX IF NOT EXISTS idx_playlists_public_number "
            "ON playlists(public_number)"
        )

        await db.execute("""
            CREATE VIRTUAL TABLE IF NOT EXISTS tracks_fts USING fts5(
                title, artist,
                content='library_tracks',
                content_rowid='id',
                tokenize='unicode61 remove_diacritics 2'
            )
        """)
        await db.execute("""
            CREATE TRIGGER IF NOT EXISTS library_tracks_ai
            AFTER INSERT ON library_tracks BEGIN
                INSERT INTO tracks_fts(rowid, title, artist)
                VALUES (new.id, new.title, new.artist);
            END
        """)
        await db.execute("""
            CREATE TRIGGER IF NOT EXISTS library_tracks_ad
            AFTER DELETE ON library_tracks BEGIN
                INSERT INTO tracks_fts(tracks_fts, rowid, title, artist)
                VALUES ('delete', old.id, old.title, old.artist);
            END
        """)
        await db.execute("""
            CREATE TRIGGER IF NOT EXISTS library_tracks_au
            AFTER UPDATE ON library_tracks BEGIN
                INSERT INTO tracks_fts(tracks_fts, rowid, title, artist)
                VALUES ('delete', old.id, old.title, old.artist);
                INSERT INTO tracks_fts(rowid, title, artist)
                VALUES (new.id, new.title, new.artist);
            END
        """)
        await db.execute("INSERT INTO tracks_fts(tracks_fts) VALUES('rebuild')")

        await db.commit()


# ========== ПЛЕЙЛИСТЫ ==========

async def create_playlist(user_id: int, name: str) -> int:
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute(
            "INSERT INTO playlists (user_id, name, created_at) VALUES (?, ?, strftime('%s','now'))",
            (user_id, name)
        )
        await db.commit()
        return cur.lastrowid


async def get_user_playlists(user_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute(
            "SELECT id, name, is_public FROM playlists WHERE user_id = ? ORDER BY id",
            (user_id,)
        )
        return await cur.fetchall()


async def get_playlist(playlist_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute(
            "SELECT id, name, is_public, public_number FROM playlists WHERE id = ?",
            (playlist_id,)
        )
        return await cur.fetchone()


async def delete_playlist(playlist_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM library_tracks WHERE playlist_id = ?", (playlist_id,))
        await db.execute("DELETE FROM playlists WHERE id = ?", (playlist_id,))
        await db.commit()


async def rename_playlist(playlist_id: int, new_name: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE playlists SET name = ? WHERE id = ?", (new_name, playlist_id))
        await db.commit()


# ========== ПУБЛИЧНОСТЬ ==========

async def generate_public_number() -> str:
    async with aiosqlite.connect(DB_PATH) as db:
        for _ in range(200):
            num = f"{random.randint(0, 9999):04d}"
            cur = await db.execute(
                "SELECT 1 FROM playlists WHERE public_number = ?", (num,)
            )
            if not await cur.fetchone():
                return num
    raise Exception("Не удалось сгенерировать номер")


async def set_playlist_public(playlist_id: int, is_public: int):
    async with aiosqlite.connect(DB_PATH) as db:
        if is_public:
            cur = await db.execute(
                "SELECT public_number FROM playlists WHERE id = ?", (playlist_id,)
            )
            row = await cur.fetchone()
            if row and not row[0]:
                num = await generate_public_number()
                await db.execute(
                    "UPDATE playlists SET is_public = 1, public_number = ? WHERE id = ?",
                    (num, playlist_id)
                )
            else:
                await db.execute(
                    "UPDATE playlists SET is_public = 1 WHERE id = ?", (playlist_id,)
                )
        else:
            await db.execute(
                "UPDATE playlists SET is_public = 0 WHERE id = ?", (playlist_id,)
            )
        await db.commit()


async def get_playlist_by_number(public_number: str):
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute("""
            SELECT id, name, user_id FROM playlists
            WHERE public_number = ? AND is_public = 1
        """, (public_number,))
        return await cur.fetchone()


async def get_playlist_tracks_paginated(playlist_id: int, page: int, per_page: int = 10):
    offset = (page - 1) * per_page
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute("""
            SELECT id, yandex_id, file_id, title, artist
            FROM library_tracks
            WHERE playlist_id = ?
            ORDER BY id
            LIMIT ? OFFSET ?
        """, (playlist_id, per_page, offset))
        tracks = await cur.fetchall()

        cur = await db.execute(
            "SELECT COUNT(*) FROM library_tracks WHERE playlist_id = ?",
            (playlist_id,)
        )
        total = (await cur.fetchone())[0]

        return tracks, total


# ========== ТРЕКИ ==========

async def add_track_to_library(playlist_id: int, title: str, artist: str, file_id: str = None, yandex_id: str = None):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT INTO library_tracks (playlist_id, title, artist, file_id, yandex_id) VALUES (?, ?, ?, ?, ?)",
            (playlist_id, title, artist, file_id, yandex_id)
        )
        await db.commit()


async def get_library_tracks(playlist_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute(
            "SELECT id, yandex_id, file_id, title, artist FROM library_tracks WHERE playlist_id = ? ORDER BY id",
            (playlist_id,)
        )
        return await cur.fetchall()


async def delete_track_from_library(track_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM library_tracks WHERE id = ?", (track_id,))
        await db.commit()


async def update_track_file_id(track_id: int, file_id: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE library_tracks SET file_id = ? WHERE id = ?", (file_id, track_id))
        await db.commit()


# ========== ШАРИНГ ==========

async def save_shared_track(share_id: str, yandex_id: str = None, file_id: str = None, title: str = "", artist: str = ""):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT OR REPLACE INTO shared_tracks (share_id, yandex_id, file_id, title, artist) VALUES (?, ?, ?, ?, ?)",
            (share_id, yandex_id, file_id, title, artist)
        )
        await db.commit()


async def get_shared_track(share_id: str):
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute(
            "SELECT yandex_id, file_id, title, artist FROM shared_tracks WHERE share_id = ?",
            (share_id,)
        )
        return await cur.fetchone()


async def update_shared_file_id(share_id: str, file_id: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE shared_tracks SET file_id = ? WHERE share_id = ?", (file_id, share_id))
        await db.commit()


# ========== ПОИСК (FTS5) ==========

async def search_all_tracks(query: str, limit: int = 5):
    tokens = [t for t in query.lower().replace('ё', 'е').split() if len(t) >= 2]
    if not tokens:
        return []

    fts_and = " ".join(f'"{t}"*' for t in tokens)
    fts_or = " OR ".join(f'"{t}"*' for t in tokens)

    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute("""
            SELECT t.id, t.yandex_id, t.file_id, t.title, t.artist, p.id, p.name
            FROM tracks_fts fts
            JOIN library_tracks t ON t.id = fts.rowid
            JOIN playlists p ON p.id = t.playlist_id
            WHERE tracks_fts MATCH ? AND t.file_id IS NOT NULL
            ORDER BY rank
            LIMIT ?
        """, (fts_and, limit))
        rows = await cur.fetchall()

        if not rows:
            cur = await db.execute("""
                SELECT t.id, t.yandex_id, t.file_id, t.title, t.artist, p.id, p.name
                FROM tracks_fts fts
                JOIN library_tracks t ON t.id = fts.rowid
                JOIN playlists p ON p.id = t.playlist_id
                WHERE tracks_fts MATCH ? AND t.file_id IS NOT NULL
                ORDER BY rank
                LIMIT ?
            """, (fts_or, limit))
            rows = await cur.fetchall()

        return rows


# ========== СТАТИСТИКА ==========

async def increment_stat(user_id: int, field: str):
    if field not in ("tracks_added", "shares_count"):
        return
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            f"""
            INSERT INTO stats (user_id, {field}) VALUES (?, 1)
            ON CONFLICT(user_id) DO UPDATE SET {field} = {field} + 1
            """,
            (user_id,)
        )
        await db.commit()


async def get_stats(user_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute(
            "SELECT tracks_added, shares_count FROM stats WHERE user_id = ?",
            (user_id,)
        )
        row = await cur.fetchone()
        return row if row else (0, 0)
