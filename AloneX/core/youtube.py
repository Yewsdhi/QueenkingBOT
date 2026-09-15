import asyncio
import os
import re
from typing import Union

import aiohttp
import yt_dlp
from pyrogram.types import Message
from py_yt import Playlist, VideosSearch

from AloneX import config, logger
from AloneX.helpers import Track

API_URL = os.environ.get("MEOW_API_URL", "https://music.yukiapi.site")
API_KEY = os.environ.get("MEOW_API_KEY", "yuki_61d6dff86bf14ab1d3fa21b283bfb9d4") # 🔑 Get Key: @MeowApiRobot On Telegram 

DOWNLOAD_DIR = "downloads"
COOKIES_FILE = os.environ.get("YOUTUBE_COOKIES_FILE", "cookies.txt")


def time_to_seconds(value) -> int:
    """Convert MM:SS or HH:MM:SS to seconds."""
    if not value:
        return 0
    try:
        parts = str(value).split(":")
        return sum(int(x) * 60 ** i for i, x in enumerate(reversed(parts)))
    except (ValueError, TypeError):
        return 0


def seconds_to_time(seconds: int) -> str:
    """Convert seconds to MM:SS or HH:MM:SS."""
    seconds = int(seconds or 0)
    h, rem = divmod(seconds, 3600)
    m, s = divmod(rem, 60)
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"


def extract_video_id(link: str) -> str | None:
    """Extract a YouTube video ID from a URL or accept an ID directly."""
    if not link:
        return None

    link = str(link).strip()

    if "youtu.be/" in link:
        video_id = link.split("youtu.be/", 1)[1].split("?", 1)[0].split("&", 1)[0]
    elif "v=" in link:
        video_id = link.split("v=", 1)[1].split("&", 1)[0]
    else:
        video_id = link

    return video_id if len(video_id) >= 3 else None


async def _api_download(link: str, media_type: str, timeout: int) -> str | None:
    """Download media directly from the Yuki API endpoint."""
    video_id = extract_video_id(link)
    if not video_id:
        return None

    os.makedirs(DOWNLOAD_DIR, exist_ok=True)
    ext = "mp4" if media_type == "video" else "mp3"
    file_path = os.path.join(DOWNLOAD_DIR, f"{video_id}.{ext}")

    if os.path.exists(file_path) and os.path.getsize(file_path) > 0:
        return file_path

    url = f"{API_URL.rstrip('/')}/stream/{video_id}"
    params = {"key": API_KEY}

    client_timeout = aiohttp.ClientTimeout(
        total=timeout,
        connect=15,
        sock_connect=15,
        sock_read=90,
    )

    for attempt in range(3):
        try:
            async with aiohttp.ClientSession(timeout=client_timeout) as session:
                async with session.get(url, params=params, headers={"User-Agent": "Mozilla/5.0"}) as resp:
                    if resp.status != 200:
                        logger.warning(f"Download API returned HTTP {resp.status} for {video_id} (attempt {attempt + 1}/3)")
                        if resp.status not in (408, 429) and resp.status < 500:
                            break
                    else:
                        ctype = (resp.headers.get("Content-Type") or "").lower()
                        if "application/json" in ctype or "text/html" in ctype:
                            logger.warning(f"Download API returned {ctype} instead of media for {video_id}")
                        else:
                            tmp_path = f"{file_path}.part"
                            try:
                                with open(tmp_path, "wb") as output:
                                    async for chunk in resp.content.iter_chunked(1024 * 1024):
                                        if chunk:
                                            output.write(chunk)

                                if os.path.exists(tmp_path) and os.path.getsize(tmp_path) > 0:
                                    os.replace(tmp_path, file_path)
                                    return file_path
                            finally:
                                if os.path.exists(tmp_path):
                                    try:
                                        os.remove(tmp_path)
                                    except OSError:
                                        pass

        except (asyncio.TimeoutError, TimeoutError) as exc:
            logger.warning(f"Download API timeout for {video_id} (attempt {attempt + 1}/3): {exc}")
        except Exception as exc:
            logger.warning(f"Download API error for {video_id} (attempt {attempt + 1}/3): {exc}")

        if attempt < 2:
            await asyncio.sleep(1.5 * (attempt + 1))

    return None


async def download_song(link: str) -> str | None:
    return await _api_download(link, "audio", 90)


async def download_video(link: str) -> str | None:
    return await _api_download(link, "video", 120)


class YouTubeAPI:
    def __init__(self):
        self.base = "https://www.youtube.com/watch?v="
        self.regex = r"(?:youtube\.com|youtu\.be)"
        self.status = "https://www.youtube.com/oembed?url="
        self.listbase = "https://youtube.com/playlist?list="
        self.reg = re.compile(r"\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])")

    async def save_cookies(self, urls: list[str]) -> None:
        pass

    async def exists(self, link: str, videoid: Union[bool, str] = None):
        if videoid:
            link = self.base + link
        return bool(re.search(self.regex, link or ""))

    async def url(self, message_1: Message) -> Union[str, None]:
        messages = [message_1]
        if message_1.reply_to_message:
            messages.append(message_1.reply_to_message)

        for message in messages:
            text = message.text or message.caption or ""
            if message.entities:
                for entity in message.entities:
                    if entity.type.name == "URL":
                        return text[entity.offset:entity.offset + entity.length]
            if message.caption_entities:
                for entity in message.caption_entities:
                    if entity.type.name == "TEXT_LINK":
                        return entity.url
        return None

    async def playlist(self, link, limit, user_id=None, videoid: Union[bool, str] = None):
        if videoid:
            link = self.listbase + link
        link = link.split("&")[0]
        try:
            playlist = await Playlist.get(link)
            videos = playlist.get("videos") or []
            return [data.get("id") for data in videos[:limit] if data and data.get("id")]
        except Exception as exc:
            logger.warning(f"Playlist fetch failed: {exc}")
            return []

    async def search(self, query: str, message_id: int = 0, video: bool = False, m_id: int = 0):
        try:
            if not isinstance(query, str):
                query = getattr(query, "text", str(query or ""))
            mid = message_id or m_id
            results = VideosSearch(query, limit=1)
            data = (await results.next()).get("result", [])
            if not data:
                return None

            result = data[0]
            duration = result.get("duration") or "00:00"
            thumbnails = result.get("thumbnails") or [{}]

            return Track(
                id=result.get("id"),
                channel_name=(result.get("channel") or {}).get("name", "YouTube"),
                duration=duration,
                duration_sec=time_to_seconds(duration),
                title=result.get("title", "Track")[:25],
                url=result.get("link"),
                file_path=None,
                message_id=mid,
                thumbnail=thumbnails[0].get("url", "").split("?")[0] if thumbnails else None,
                video=video,
            )
        except Exception as exc:
            logger.error(f"YouTube search error: {exc}")
            return None

    async def related(self, video_id: str, limit: int = 10) -> list:
        return []

    async def autoplay_track(self, video_id: str, video: Union[bool, str] = None, exclude: set | None = None, title: str | None = None):
        return None

    async def download(self, *args, **kwargs) -> str | None:
        video_id = kwargs.get("link") or kwargs.get("video_id")
        video = kwargs.get("video", False)

        if not video_id and args:
            video_id = args[0]
            if len(args) > 1 and isinstance(args[1], bool):
                video = args[1]

        if not video_id:
            return None

        vid = extract_video_id(str(video_id))
        if not vid:
            return None

        return await download_video(vid) if video else await download_song(vid)


YouTube = YouTubeAPI()
