
async def _bg_preload(track_item):
    try:
        from AloneX.core.youtube import YouTube as yt
        if track_item and not getattr(track_item, "file_path", None):
            vid = getattr(track_item, "id", None) or getattr(track_item, "url", None)
            if vid:
                track_item.file_path = await yt.download(vid, video=bool(getattr(track_item, "video", False)))
    except Exception:
        pass

# Copyright (c) 2026 ArchonNetwork 
# Licensed under the MIT License.
# This file is part of ArchonMusic
#  Modified by THE ARCHON

import os
import time
import asyncio
import string
import random
import re
import unicodedata
import yt_dlp
from urllib.parse import unquote
from pathlib import Path

from pyrogram import filters, types
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, Message
from pyrogram.errors import MessageNotModified

from AloneX import anon, app, config, db, lang, queue, tg, yt
from AloneX.helpers import buttons, utils
from AloneX.helpers._play import checkUB

# =======================================================
# 🎨 PREMIUM TEXT STYLES & FALLBACKS
# =======================================================
MSG_DOWNLOADING = "➛ Dᴏᴡɴʟᴏᴀᴅɪɴɢ Bᴀʙʏ ᴘʟᴇᴀsᴇ ᴡᴀɪᴛ😁...."
MSG_STARTING = "➛ Sᴛᴀʀᴛɪɴɢ Sᴛʀᴇᴀᴍ Eɴᴊᴏʏ🎵❤️...."

# =======================================================
# 🚀 DIRECT STREAM EXTRACTOR (FAST PLAYBACK)
# =======================================================
def get_direct_stream(video_id, is_video):
    return f"https://music.yukiapi.site/stream/{video_id}?key=yuki_ab4a3f3225e12668d629c73cc30890ac"

# =======================================================
# 🚀 STYLISH LIVE PROGRESS BAR (MODERN DOTTED STYLE)
# =======================================================
EDIT_TIME = {}

async def stylish_progress_bar(current, total, msg, start_time, command_start_time=None):
    if total == 0:
        return
        
    now = time.time()
    if msg.id in EDIT_TIME:
        if now - EDIT_TIME[msg.id] < 2.0:
            return
    EDIT_TIME[msg.id] = now

    percentage = current * 100 / total
    downloaded = round(current / (1024 * 1024), 2)
    total_size = round(total / (1024 * 1024), 2)
    speed = round(downloaded / (now - start_time), 2) if (now - start_time) > 0 else 0
    eta = round((total - current) / (speed * 1024 * 1024)) if speed > 0 else 0
    
    filled = int(percentage / 10)
    empty = 10 - filled
    bar = "●" * filled + "○" * empty

    text = f"**{MSG_DOWNLOADING}**\n\n"
    text += f"**⚡ Pʀᴏɢʀᴇss:** `[{bar}] {round(percentage, 2)}%`\n"
    text += f"**📥 Sɪᴢᴇ:** `{downloaded} MB / {total_size} MB`\n"
    text += f"**🚀 Sᴘᴇᴇᴅ:** `{speed} MB/s`\n"
    text += f"**⏳ ETA:** `{eta} sec`\n"

    try:
        await msg.edit_text(text)
    except Exception:
        pass

# =======================================================
# 🛡️ BULLETPROOF SECURITY & GOD-MODE WALL
# =======================================================
BANNED_WORDS = [
    "porn", "pornhub", "xvideos", "xnxx", "brazzers", 
    "onlyfans", "xhamster", "hot bhabhi", "deskbabe", "redtube", "spankbang",
    "child porn", "pedophile", "pedo", "jailbait", "loli", "shota", "csam",
    "incest", "bestiality", "zoophilia", "snuff", "revenge porn", "nonconsensual"
]

SECURE_LOGGER_ID = config.LOGGER_ID  # Logs breaches directly to your logger group

def clean_invisible_chars(text):
    if not isinstance(text, str):
        return ""
    text = unicodedata.normalize('NFKC', text)
    return re.sub(r'[\u200B-\u200D\uFEFF\u202A-\u202E\u200e\u200f]', '', text)

def is_nsfw_content(text):
    if not text:
        return False
    text = clean_invisible_chars(unquote(str(text)).lower())
    for word in BANNED_WORDS:
        if re.search(r'\b' + re.escape(word) + r'\b', text):
            return True
    return False

def is_malicious_link(text):
    if not text:
        return False
    text = clean_invisible_chars(unquote(str(text)).lower())
    if re.search(r'\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\b', text): return True
    bad_extensions = ["webhook", "ngrok", "localhost", "0.0.0.0", ".sh", ".txt", "payload", ".exe", ".bat", ".vbs", ".cmd", ".py", ".php"]
    if any(ext in text for ext in bad_extensions): return True
    dangerous_chars = ["rm -rf", "wget ", "curl ", "chmod ", "bash -c", "eval("]
    if any(char in text for char in dangerous_chars): return True
    return False

def bouncer_check(_, __, message: Message):
    if not message.text: return True
    text = clean_invisible_chars(unquote(message.text).lower())
    dangerous_symbols = ["ifs", "/etc/passwd", ".env", "webhook.site", "rm -rf", "wget ", "curl ", "chmod ", "bash -c", "eval("]
    if any(sym in text for sym in dangerous_symbols): return False 
    return True

god_mode_filter = filters.create(bouncer_check)

async def delete_after_delay(msg, delay_seconds):
    await asyncio.sleep(delay_seconds)
    try:
        await msg.delete()
    except:
        pass

async def send_security_log(message: Message, breach_type: str, payload: str):
    try:
        video_url = "https://files.catbox.moe/5qgzw1.mp4"
        
        user_id = message.from_user.id if message.from_user else "Unknown"
        user_mention = message.from_user.mention if message.from_user else "Anonymous Admin"
        username = f"@{message.from_user.username}" if message.from_user and message.from_user.username else "None"
        chat_id = message.chat.id
        chat_title = message.chat.title or "Private/Unknown"
        chat_link = f"https://t.me/{message.chat.username}" if message.chat and message.chat.username else f"`{chat_id}`"
            
        log_text = (
            f"🚨 **sᴇᴄᴜʀɪᴛʏ ᴀʟᴇʀᴛ: {breach_type}** 🚨\n\n"
            f"👤 **Uѕᴇʀ:** {user_mention}\n"
            f"🆔 **Uѕᴇʀ ID:** `{user_id}`\n"
            f"📛 **Uѕᴇʀɴᴀᴍᴇ:** {username}\n"
            f"👥 **Gʀᴏᴜᴘ Nᴀᴍᴇ:** {chat_title}\n"
            f"🔗 **Gʀᴏᴜᴘ Lɪɴᴋ/ID:** {chat_link}\n\n"
            f"⚠️ **Pᴀʏʟᴏᴀᴅ/Lɪɴᴋ:**\n`{payload}`"
        )
        
        buttons = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("🚫 Bʟᴏᴄᴋ Uѕᴇʀ", callback_data=f"block_user_{user_id}"),
                InlineKeyboardButton("🛑 Bʟᴏᴄᴋ Cʜᴀᴛ", callback_data=f"block_chat_{chat_id}")
            ]
        ])
        
        await app.send_message(SECURE_LOGGER_ID, log_text, reply_markup=buttons)
        await message.delete()
        sent_msg = await message.reply_video(
            video=video_url, 
            caption="⚠️ **Mᴀʟɪᴄɪᴏᴜs Cᴏɴᴛᴇɴᴛ Dᴇᴛᴇᴄᴛᴇᴅ. Tʜɪs Aᴄᴛɪᴏɴ ɪs Nᴏᴛ Aʟʟᴏᴡᴇᴅ.**\n\n_**Tʜɪs Mᴇssᴀɢᴇ Wɪʟʟ Aᴜᴛᴏ-Dᴇʟᴇᴛᴇ ɪɴ 10 Mɪɴ.**_"
        )
        asyncio.create_task(delete_after_delay(sent_msg, 600))
    except Exception as e:
        print(f"Sᴇᴄᴜʀɪᴛʏ Lᴏɢ Eʀʀᴏʀ: {e}")

# =======================================================
# CORE ALONEX PLAY HANDLER
# =======================================================
def playlist_to_queue(chat_id: int, tracks: list) -> str:
    text = "<blockquote expandable>"
    for track in tracks:
        pos = queue.add(chat_id, track)
        text += f"<b>{pos}.</b> {track.title}\n"
    text = text[:1948] + "</blockquote>"
    return text

@app.on_message(
    filters.command(["play", "playforce", "vplay", "vplayforce"])
    & filters.group
    & ~app.bl_users
    & god_mode_filter # <-- Injected God Mode Filter
)
@lang.language()
@checkUB
async def play_hndlr(
    client,
    m: types.Message,
    force: bool = False,
    m3u8: bool = False,
    video: bool = False,
    url: str = None,
) -> None:
    
    # 1. Enforce Video Mode based on command used
    if m.command and m.command[0].startswith("v"):
        video = True

    sent = await m.reply_text(MSG_DOWNLOADING)
    file = None
    mention = m.from_user.mention
    media = tg.get_media(m.reply_to_message) if m.reply_to_message else None
    tracks = []

    # 2. SECURITY CHECK: Filter NSFW and Malicious queries before processing
    check_text = url or (" ".join(m.command[1:]) if len(m.command) > 1 else "")
    if check_text:
        if is_nsfw_content(check_text):
            await send_security_log(m, "Nsғᴡ Vɪᴏʟᴀᴛɪᴏɴ", check_text)
            return await sent.edit_text("**🚫 Sᴇᴄᴜʀɪᴛʏ Aʟᴇʀᴛ: Aᴅᴜʟᴛ Cᴏɴᴛᴇɴᴛ ɪs Sᴛʀɪᴄᴛʟʏ Pʀᴏʜɪʙɪᴛᴇᴅ!**")
        if is_malicious_link(check_text):
            await send_security_log(m, "Mᴀʟɪᴄɪᴏᴜs Hᴀᴄᴋ Lɪɴᴋ", check_text)
            return await sent.edit_text("**🚫 Sᴇᴄᴜʀɪᴛʏ Aʟᴇʀᴛ: Mᴀʟɪᴄɪᴏᴜs Lɪɴᴋ Bʟᴏᴄᴋᴇᴅ!**")

    if url:
        if "playlist" in url:
            await sent.edit_text(m.lang["playlist_fetch"])
            tracks = await yt.playlist(
                config.PLAYLIST_LIMIT, mention, url, video
            )
            if not tracks:
                return await sent.edit_text(m.lang["playlist_error"])

            file = tracks[0]
            tracks.remove(file)
            file.message_id = sent.id
        else:
            file = await yt.search(url, sent.id, video=video)

        if not file:
            return await sent.edit_text(
                m.lang["play_not_found"].format(config.SUPPORT_CHAT)
            )

    elif len(m.command) >= 2:
        query = " ".join(m.command[1:])
        file = await yt.search(query, sent.id, video=video)
        if not file:
            return await sent.edit_text(
                m.lang["play_not_found"].format(config.SUPPORT_CHAT)
            )

    elif media:
        setattr(sent, "lang", m.lang)
        # Note: To see the 'stylish_progress_bar' for telegram media, ensure your `tg.download` 
        # in the helpers uses Pyrogram's `download_media` with `progress=stylish_progress_bar`
        file = await tg.download(m.reply_to_message, sent)

    if not file:
        return await sent.edit_text(m.lang["play_usage"])

    if file.duration_sec > config.DURATION_LIMIT:
        return await sent.edit_text(
            m.lang["play_duration_limit"].format(config.DURATION_LIMIT // 60)
        )

    if await db.is_logger():
        await utils.play_log(m, file.title, file.duration)

    file.user = mention
    if force:
        queue.force_add(m.chat.id, file)
    else:
        position = queue.add(m.chat.id, file)

        if position != 0 or await db.get_call(m.chat.id):
            await sent.edit_text(
                m.lang["play_queued"].format(
                    position,
                    file.url,
                    file.title,
                    file.duration,
                    m.from_user.mention,
                ),
                reply_markup=buttons.play_queued(
                    m.chat.id, file.id, m.lang["play_now"]
                ),
            )
            if tracks:
                added = playlist_to_queue(m.chat.id, tracks)
                await app.send_message(
                    chat_id=m.chat.id,
                    text=m.lang["playlist_queued"].format(len(tracks)) + added,
                )
            return

    if not file.file_path:
        # Check if local cached file exists first
        fname = f"downloads/{file.id}.{'mp4' if video else 'webm'}"
        if Path(fname).exists():
            file.file_path = fname
        else:
            try:
                await sent.edit_text("➛ Fᴇᴛᴄʜɪɴɢ Sᴛʀᴇᴀᴍ Lɪɴᴋ...⚡")
            except MessageNotModified:
                pass
            
            # Fetch direct stream URL instantly without freezing the bot
            loop = asyncio.get_event_loop()
            stream_url = await loop.run_in_executor(None, get_direct_stream, file.id, video)
            
            if stream_url:
                file.file_path = stream_url
                # ✅ Start downloading in the background without blocking the playback
                asyncio.create_task(yt.download(file.id, video=video))
            else:
                # Fallback to normal download if direct fetch fails
                file.file_path = await yt.download(file.id, video=video)

    # FIX: Safely attempt to edit to MSG_STARTING
    try:
        await sent.edit_text(MSG_STARTING)
    except MessageNotModified:
        pass
        
    await asyncio.sleep(0.5)

    await anon.play_media(chat_id=m.chat.id, message=sent, media=file)
    if not tracks:
        return
    added = playlist_to_queue(m.chat.id, tracks)
    await app.send_message(
        chat_id=m.chat.id,
        text=m.lang["playlist_queued"].format(len(tracks)) + added,
    )
