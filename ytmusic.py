import os
import tempfile
import asyncio
import yt_dlp
import imageio_ffmpeg
from ytmusicapi import YTMusic

yt = YTMusic()

FFMPEG_PATH = imageio_ffmpeg.get_ffmpeg_exe()
COOKIES_PATH = "cookies.txt"

YDL_BASE_OPTS = {
    "quiet": True,
    "no_warnings": True,
    "noplaylist": True,
    "ffmpeg_location": FFMPEG_PATH,
    "extractor_args": {"youtube": {"player_client": ["tv", "mweb", "android"]}},
}


async def init_yandex():
    print("YouTube Music подключен")
    return True


async def ensure_client():
    pass


async def search(query: str, limit: int = 5):
    loop = asyncio.get_event_loop()
    results = await loop.run_in_executor(
        None,
        lambda: yt.search(query, filter="songs", limit=limit)
    )

    tracks = []
    for r in results:
        artists = r.get("artists") or []
        artist = artists[0]["name"] if artists else "Unknown"
        tracks.append({
            "id": r.get("videoId"),
            "title": r.get("title", "Без названия"),
            "artist": artist,
            "duration": r.get("duration_seconds", 0),
        })

    # ЖЁСТКО ОБРЕЗАЕМ ДО LIMIT
    return tracks[:limit]


async def get_stream_url(video_id: str):
    loop = asyncio.get_event_loop()

    def _extract():
        opts = {
            **YDL_BASE_OPTS,
            "format": "bestaudio/best",
        }
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(
                f"https://music.youtube.com/watch?v={video_id}",
                download=False
            )
            return info.get("url")

    return await loop.run_in_executor(None, _extract)


async def download_track(video_id: str) -> str:
    loop = asyncio.get_event_loop()

    def _download():
        tmpdir = tempfile.gettempdir()
        outtmpl = os.path.join(tmpdir, f"{video_id}.%(ext)s")

        opts = {
            **YDL_BASE_OPTS,
            "format": "bestaudio/best",
            "outtmpl": outtmpl,
            "postprocessors": [{
                "key": "FFmpegExtractAudio",
                "preferredcodec": "mp3",
                "preferredquality": "192",
            }],
        }

        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(
                f"https://music.youtube.com/watch?v={video_id}",
                download=True
            )

        filename = os.path.join(tmpdir, f"{video_id}.mp3")
        return filename if os.path.exists(filename) else None

    return await loop.run_in_executor(None, _download)
