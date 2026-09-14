# Copyright (c) 2026 THE SHIV
# Licensed under the MIT License.
# This file is part of MahiMusic
# DEVELOPER - THE SHIV

import re
import asyncio

from pyrogram import enums, types
from pyrogram.errors import FloodWait
from AloneX import app

class Utilities:
    def __init__(self):
        pass

    def format_eta(self, seconds: int) -> str:
        if seconds < 60:
            return f"{seconds}s"
        elif seconds < 3600:
            return f"{seconds // 60}:{seconds % 60:02d} min"
        else:
            h = seconds // 3600
            m = (seconds % 3600) // 60
            s = seconds % 60
            return f"{h}:{m:02d}:{s:02d} h"

    def format_size(self, bytes: int) -> str:
        if bytes >= 1024**3:
            return f"{bytes / 1024 ** 3:.2f} GB"
        elif bytes >= 1024**2:
            return f"{bytes / 1024 ** 2:.2f} MB"
        else:
            return f"{bytes / 1024:.2f} KB"

    def to_seconds(self, time: str) -> int:
        parts = [int(p) for p in time.strip().split(":")]
        return sum(value * 60**i for i, value in enumerate(reversed(parts)))

    def get_url(self, message_1: types.Message) -> str | None:
        link = None
        messages = [message_1]
        entities = [enums.MessageEntityType.URL, enums.MessageEntityType.TEXT_LINK]

        if message_1.reply_to_message:
            messages.append(message_1.reply_to_message)

        for message in messages:
            if message.entities:
                for entity in message.entities:
                    if entity.type in entities:
                        link = entity.url
                        break

            if message.caption_entities:
                for entity in message.caption_entities:
                    if entity.type in entities:
                        link = entity.url
                        break

        if link:
            return link.split("&si")[0].split("?si")[0]
        return None

    async def extract_user(self, msg: types.Message) -> types.User | None:
        if msg.reply_to_message:
            return msg.reply_to_message.from_user

        if msg.entities:
            for e in msg.entities:
                if e.type == enums.MessageEntityType.TEXT_MENTION:
                    return e.user

        if msg.text:
            try:
                if m := re.search(r"@(\w{5,32})", msg.text):
                    return await app.get_users(m.group(0))
                if m := re.search(r"\b\d{6,15}\b", msg.text):
                    return await app.get_users(int(m.group(0)))
            except:
                pass

        return None

    async def get_owner(self, chat_id: int) -> str:
        try:
            async for member in app.get_chat_members(chat_id, filter=enums.ChatMembersFilter.ADMINISTRATORS):
                if member.status == enums.ChatMemberStatus.OWNER:
                    return member.user.mention
        except:
            pass
        return "Unknown"

    async def play_log(
        self,
        m: types.Message,
        title: str,
        duration: str,
    ) -> None:
        if m.chat.id == app.logger:
            return
            
        log_text = (
            "<blockquote><b>🎵 Nᴇᴡ Mᴇᴅɪᴀ Pʟᴀʏᴇᴅ</b>\n\n"
            f"<b>🥀 Cʜᴀᴛ :</b> {m.chat.title} [<code>{m.chat.id}</code>]\n"
            f"<b>👤 Usᴇʀ :</b> {m.from_user.mention} [<code>{m.from_user.id}</code>]\n"
            f"<b>📝 Tɪᴛʟᴇ :</b> <a href='{m.link}'>{title}</a>\n"
            f"<b>⏳ Dᴜʀᴀᴛɪᴏɴ :</b> {duration}</blockquote>"
        )
        
        # 🔗 Auto Invite Link Generation for Play Logs
        try:
            if m.chat.username:
                chat_url = f"https://t.me/{m.chat.username}"
            else:
                chat_url = m.chat.invite_link or await app.export_chat_invite_link(m.chat.id)
        except Exception:
            chat_url = m.link
            
        reply_markup = types.InlineKeyboardMarkup([
            [types.InlineKeyboardButton("💬 Cʜᴀᴛ Lɪɴᴋ", url=chat_url)]
        ])
        
        try:
            await app.send_message(
                chat_id=app.logger, 
                text=log_text,
                reply_markup=reply_markup,
                parse_mode=enums.ParseMode.HTML,
                disable_web_page_preview=True
            )
        except Exception as e:
            print(f"⚠️ Play Log Error: {e}")

    async def send_log(self, m: types.Message, chat: bool = False, action: str = "added") -> None:
        if chat:
            user = m.from_user
            chat_id = m.chat.id
            
            try:
                members_count = await app.get_chat_members_count(chat_id)
            except:
                members_count = "Unknown"
                
            owner = await self.get_owner(chat_id)
            log_image = "https://graph.org/file/4718fb3383ea91aa08f6d-05cd8091883b103e90.jpg"

            if action == "added":
                log_text = (
                    "<blockquote><b>✅ Bᴏᴛ Aᴅᴅᴇᴅ Tᴏ Gʀᴏᴜᴘ</b>\n\n"
                    f"<b>🥀 Cʜᴀᴛ Nᴀᴍᴇ :</b> {m.chat.title}\n"
                    f"<b>🍂 Cʜᴀᴛ ID :</b> <code>{chat_id}</code>\n"
                    f"<b>👤 Aᴅᴅᴇᴅ Bʏ :</b> {user.mention if user else 'Anonymous'}\n"
                    f"<b>👑 Oᴡɴᴇʀ :</b> {owner}\n"
                    f"<b>👥 Tᴏᴛᴀʟ Usᴇʀs :</b> {members_count}</blockquote>"
                )
            else:
                log_text = (
                    "<blockquote><b>❌ Bᴏᴛ Rᴇᴍᴏᴠᴇᴅ Fʀᴏᴍ Gʀᴏᴜᴘ</b>\n\n"
                    f"<b>🥀 Cʜᴀᴛ Nᴀᴍᴇ :</b> {m.chat.title}\n"
                    f"<b>🍂 Cʜᴀᴛ ID :</b> <code>{chat_id}</code>\n"
                    f"<b>👤 Rᴇᴍᴏᴠᴇᴅ Bʏ :</b> {user.mention if user else 'Anonymous'}\n"
                    f"<b>👑 Oᴡɴᴇʀ :</b> {owner}\n"
                    f"<b>👥 Tᴏᴛᴀʟ Usᴇʀs :</b> {members_count}</blockquote>"
                )

            # 🔗 Auto Invite Link Generation for Added/Removed Logs
            try:
                if m.chat.username:
                    chat_url = f"https://t.me/{m.chat.username}"
                else:
                    chat_url = m.chat.invite_link or await app.export_chat_invite_link(chat_id)
            except Exception:
                chat_url = f"https://t.me/c/{str(chat_id).replace('-100', '')}/1"

            reply_markup = types.InlineKeyboardMarkup([
                [types.InlineKeyboardButton("💬 Cʜᴀᴛ Lɪɴᴋ", url=chat_url)]
            ])

            try:
                await app.send_photo(
                    chat_id=app.logger,
                    photo=log_image,
                    caption=log_text,
                    reply_markup=reply_markup,
                    parse_mode=enums.ParseMode.HTML
                )
            except Exception as e:
                print(f"⚠️ Send Log (Photo) Error: {e}")
            
        else:
            if not m.from_user:
                return 

            log_text = (
                "<blockquote><b>👤 Nᴇᴡ Usᴇʀ Sᴛᴀʀᴛᴇᴅ</b>\n\n"
                f"<b>🥀 Nᴀᴍᴇ :</b> {m.from_user.mention}\n"
                f"<b>🍂 ID :</b> <code>{m.from_user.id}</code>\n"
                f"<b>🔗 Usᴇʀɴᴀᴍᴇ :</b> @{m.from_user.username or 'None'}</blockquote>"
            )

            user_url = f"tg://user?id={m.from_user.id}"
            reply_markup = types.InlineKeyboardMarkup([
                [types.InlineKeyboardButton("👤 Usᴇʀ Pʀᴏꜰɪʟᴇ", url=user_url)]
            ])

            try:
                await app.send_message(
                    chat_id=app.logger,
                    text=log_text,
                    reply_markup=reply_markup,
                    parse_mode=enums.ParseMode.HTML
                )
            except Exception as e:
                print(f"⚠️ Send Log (Message) Error: {e}")

    # 🟢 ADVANCED AUTOPLAY LOG FUNCTION
    async def autoplay_log(
        self, 
        chat: types.Chat, 
        playing_title: str, 
        playing_link: str, 
        matched_with: str, 
        upcoming_title: str = "Fetching Next..."
    ) -> None:
        if chat.id == app.logger:
            return
            
        log_text = (
            "<blockquote><b>🔁 Aᴜᴛᴏ-Pʟᴀʏ Tʀᴀᴄᴋ Sᴛᴀʀᴛᴇᴅ</b>\n\n"
            f"<b>🥀 Gʀᴏᴜᴘ :</b> {chat.title} [<code>{chat.id}</code>]\n"
            f"<b>🎵 Pʟᴀʏɪɴɢ :</b> <a href='{playing_link}'>{playing_title}</a>\n"
            f"<b>🔗 Mᴀᴛᴄʜᴇᴅ Wɪᴛʜ :</b> {matched_with}\n"
            f"<b>⏭ Uᴘᴄᴏᴍɪɴɢ :</b> {upcoming_title}</blockquote>"
        )
        
        # 🔗 Auto Invite Link Generation for Autoplay Logs
        try:
            if chat.username:
                chat_url = f"https://t.me/{chat.username}"
            else:
                chat_url = chat.invite_link or await app.export_chat_invite_link(chat.id)
        except Exception:
            chat_url = f"https://t.me/c/{str(chat.id).replace('-100', '')}/1"
            
        reply_markup = types.InlineKeyboardMarkup([
            [types.InlineKeyboardButton("💬 ᴄʜᴀᴛ ʟɪɴᴋ", url=chat_url)]
        ])
        
        try:
            await app.send_message(
                chat_id=app.logger,
                text=log_text,
                reply_markup=reply_markup,
                parse_mode=enums.ParseMode.HTML,
                disable_web_page_preview=True
            )
        except Exception as e:
            print(f"⚠️ Autoplay Log Error: {e}")
