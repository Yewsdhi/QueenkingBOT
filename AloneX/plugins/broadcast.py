# Copyright (c) 2025 TheHamkerAlone
# Licensed under the MIT License.
# This file is part of AloneXMusic

import os
import time
import asyncio
import random
from pyrogram import errors, filters, types
from pyrogram.enums import ChatMembersFilter
from pyrogram.errors import FloodWait
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from pyrogram.enums import ButtonStyle
from motor.motor_asyncio import AsyncIOMotorClient

# Using standard AloneX imports
from config import MONGO_DB_URI
from AloneX import app, db, lang

IS_BROADCASTING = False

# ==========================================
# PROGRESS BAR HELPER
# ==========================================
def get_progress_bar(current, total, length=20):
    if total == 0:
        return "▱" * length
    percent = current / total
    filled_len = int(length * percent)
    bar = "▰" * filled_len + "▱" * (length - filled_len)
    return bar

# ==========================================
# DATABASE SETUP (PROMO & BROADCAST)
# ==========================================
dbclient = AsyncIOMotorClient(MONGO_DB_URI)
promo_db = dbclient.AloneXPromo

# Promo Collections
promo_msgs_db = promo_db.promo_messages
promo_toggle_db = promo_db.promo_settings
broadcast_time_db = promo_db.promo_time

# Regular Broadcast (Gcast) Auto-Delete Collection
gcast_msgs_db = promo_db.gcast_messages

async def is_promo_on() -> bool:
    chat = await promo_toggle_db.find_one({"_id": "promo_toggle"})
    if not chat:
        return False
    return chat.get("status", False)

async def set_promo_status(status: bool):
    await promo_toggle_db.update_one({"_id": "promo_toggle"}, {"$set": {"status": status}}, upsert=True)

async def save_promo_msg(chat_id: int, message_id: int):
    await promo_msgs_db.insert_one({"chat_id": chat_id, "message_id": message_id, "timestamp": int(time.time())})

async def get_old_promo_msgs():
    time_limit = int(time.time()) - 172800 # 48 hours for promo
    return promo_msgs_db.find({"timestamp": {"$lt": time_limit}})

async def delete_promo_record(chat_id: int, message_id: int):
    await promo_msgs_db.delete_one({"chat_id": chat_id, "message_id": message_id})

# Auto Delete Helper for Regular Broadcasts
async def save_gcast_msg(chat_id: int, message_id: int):
    await gcast_msgs_db.insert_one({"chat_id": chat_id, "message_id": message_id, "timestamp": int(time.time())})

# ==========================================
# SELF PROMO ASSETS
# ==========================================
PROMO_IMAGE = "https://graph.org/file/d98f8556cc20553c2c2f0-4b20c478c646412324.jpg"
PROMO_TEXT = """
<blockquote><b>⊚ ᴛʜɪꜱ ɪꜱ <a href="https://t.me/YukiTuneBot">˹♪ 𝖸𝗎𝗄𝗂 𝖬𝗎𝗌𝗂𝖼 ♪˼ [ 💌 ]</a>

➻ A Pʀєᴍɪᴜᴍ Dєꜱɪɢηєᴅ Mᴜꜱɪᴄ Pʟᴧʏєʀ Bσᴛ Fσʀ Tєʟєɢʀᴧϻ Gʀσᴜᴘ & Cʜᴧηηєʟ. 
🎧 24x7 Mᴜꜱɪᴄ • Sᴍᴏᴏᴛʜ Aɴᴅ Fᴀꜱᴛ PʟᴀʏBᴀᴄᴋ

⚡️ Eɴᴊᴏʏ Uɴʟɪᴍɪᴛᴇᴅ Sᴏɴɢꜱ, Qᴜɪᴄᴋ Rᴇꜱᴘᴏɴꜱᴇ, Aɴᴅ Cʟᴇᴀʀ Aᴜᴅɪᴏ Iɴ Yᴏᴜʀ Gʀᴏᴜᴘ Vᴏɪᴄᴇ Cʜᴀᴛ.

Aᴅᴅ Mᴇ Tᴏ Yᴏᴜʀ Gʀᴏᴜᴘ, Mᴀᴋᴇ Mᴇ Aᴅᴍɪɴ, Aɴᴅ Sᴇɴᴅ /play song name Tᴏ Sᴛᴀʀᴛ Tʜᴇ Mᴜꜱɪᴄ.</b></blockquote>
"""

def get_random_button():
    styles = [ButtonStyle.PRIMARY, ButtonStyle.SUCCESS]
    random.shuffle(styles)
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    "🎵 Aᴅᴅ Mᴇ Iɴ Yᴏᴜʀ Gʀᴏᴜᴘ 🎧", 
                    url=f"https://t.me/YukiTuneBot?startgroup=true",
                    style=styles[0]
                )
            ]
        ]
    )

# ==========================================
# MAIN BROADCAST COMMAND
# ==========================================
@app.on_message(filters.command(["broadcast", "gcast"]) & app.sudoers)
@lang.language()
async def _broadcast(_, message: types.Message):
    global IS_BROADCASTING
    if IS_BROADCASTING:
        return await message.reply_text(message.lang["gcast_active"])

    if message.reply_to_message:
        x = message.reply_to_message.id
        y = message.chat.id
        query = message.text
    else:
        if len(message.command) < 2:
            return await message.reply_text(message.lang["gcast_usage"])
        query = message.text.split(None, 1)[1]

    # Checking target flags
    send_to_users = False
    send_to_groups = False

    if "-user" in query:
        send_to_users = True
        query = query.replace("-user", "")
    
    if "-group" in query:
        send_to_groups = True
        query = query.replace("-group", "")

    # If no specific flag is given, send to both
    if not send_to_users and not send_to_groups:
        send_to_users = True
        send_to_groups = True

    # Checking pin flags
    pin = False
    loud = False
    if "-pinloud" in query:
        pin = True
        loud = False
        query = query.replace("-pinloud", "")
    elif "-pin" in query:
        pin = True
        loud = True
        query = query.replace("-pin", "")

    query = query.strip()
    if not query and not message.reply_to_message:
        return await message.reply_text("Please provide text to broadcast.")

    IS_BROADCASTING = True
    status_msg = await message.reply_text("🔄 **Initializing broadcast... fetching database.**")

    users = await db.get_users() if send_to_users else []
    chats = await db.get_chats() if send_to_groups else []

    total_users = len(users)
    total_chats = len(chats)
    total_targets = total_users + total_chats

    if total_targets == 0:
        IS_BROADCASTING = False
        return await status_msg.edit_text("❌ No users or groups found in database to broadcast.")

    u_success, u_failed = 0, 0
    g_success, g_failed = 0, 0
    pinned_cnt = 0
    completed = 0

    async def update_progress():
        # Update progress bar every 20 messages to prevent FloodWait limit on edits
        if completed % 20 == 0 or completed == total_targets:
            bar = get_progress_bar(completed, total_targets)
            percent = int((completed / total_targets) * 100)
            text = (
                f"🔄 **Live Broadcasting...**\n\n"
                f"[{bar}] **{percent}%**\n\n"
                f"👥 **Users:** ✅ {u_success} | ❌ {u_failed}\n"
                f"🏘 **Groups:** ✅ {g_success} | ❌ {g_failed}\n"
                f"📌 **Pinned:** {pinned_cnt}\n\n"
                f"⏳ *(Messages will auto-delete in 24 hours)*"
            )
            try:
                await status_msg.edit_text(text)
            except Exception:
                pass

    # Broadcast to Users
    if send_to_users:
        for user in users:
            if not IS_BROADCASTING:
                break
            user_id = int(user["user_id"] if isinstance(user, dict) else user)
            try:
                m = (
                    await app.forward_messages(user_id, y, x)
                    if message.reply_to_message
                    else await app.send_message(user_id, text=query)
                )
                if m:
                    await save_gcast_msg(user_id, m.id) # Save for 24hr auto-delete
                u_success += 1
            except FloodWait as fw:
                await asyncio.sleep(fw.value + 1)
                try:
                    m = (
                        await app.forward_messages(user_id, y, x)
                        if message.reply_to_message
                        else await app.send_message(user_id, text=query)
                    )
                    if m:
                        await save_gcast_msg(user_id, m.id)
                    u_success += 1
                except:
                    u_failed += 1
            except Exception:
                # Silently catch PEER_ID_INVALID and blocked errors
                u_failed += 1

            completed += 1
            await update_progress()
            await asyncio.sleep(0.05)

    # Broadcast to Groups
    if send_to_groups:
        for chat in chats:
            if not IS_BROADCASTING:
                break
            chat_id = int(chat["chat_id"] if isinstance(chat, dict) else chat)
            try:
                m = (
                    await app.forward_messages(chat_id, y, x)
                    if message.reply_to_message
                    else await app.send_message(chat_id, text=query)
                )
                if m:
                    await save_gcast_msg(chat_id, m.id) # Save for 24hr auto-delete
                g_success += 1
                if pin:
                    try:
                        await m.pin(disable_notification=loud)
                        pinned_cnt += 1
                    except Exception:
                        pass
            except FloodWait as fw:
                await asyncio.sleep(fw.value + 1)
                try:
                    m = (
                        await app.forward_messages(chat_id, y, x)
                        if message.reply_to_message
                        else await app.send_message(chat_id, text=query)
                    )
                    if m:
                        await save_gcast_msg(chat_id, m.id)
                    g_success += 1
                    if pin:
                        try:
                            await m.pin(disable_notification=loud)
                            pinned_cnt += 1
                        except:
                            pass
                except:
                    g_failed += 1
            except Exception:
                 # Silently catch PEER_ID_INVALID and chat write forbidden errors
                g_failed += 1

            completed += 1
            await update_progress()
            await asyncio.sleep(0.05)

    IS_BROADCASTING = False
    
    # Final Result Edit
    final_text = (
        f"✅ **Broadcast Completed Successfully!**\n\n"
        f"**Total Targets:** {total_targets}\n"
        f"👥 **Users:** ✅ {u_success} | ❌ {u_failed}\n"
        f"🏘 **Groups:** ✅ {g_success} | ❌ {g_failed}\n"
        f"📌 **Pinned in Groups:** {pinned_cnt}\n\n"
        f"🗑 **Auto-Delete:** Enabled (24 Hours)"
    )
    try:
        await status_msg.edit_text(final_text)
    except:
        pass

    # Send Log to Logger Group
    if hasattr(app, "logger") and app.logger:
        log_text = (
            f"📢 **Broadcast Log**\n"
            f"👤 **By:** {message.from_user.mention}\n"
            f"📊 **Stats:**\n"
            f"👥 **Users:** {u_success} Success | {u_failed} Failed\n"
            f"🏘 **Groups:** {g_success} Success | {g_failed} Failed\n"
            f"📌 **Pinned:** {pinned_cnt}\n"
            f"🗑 **Auto-Delete:** 24 Hours"
        )
        try:
            await app.send_message(app.logger, log_text)
        except Exception:
            pass

@app.on_message(filters.command(["stop_gcast", "stop_broadcast"]) & app.sudoers)
@lang.language()
async def _stop_gcast(_, message: types.Message):
    global IS_BROADCASTING
    if not IS_BROADCASTING:
        return await message.reply_text(message.lang["gcast_inactive"])

    IS_BROADCASTING = False
    if hasattr(app, "logger") and app.logger:
        try:
            await app.send_message(
                chat_id=app.logger,
                text=f"🛑 **Broadcast Stopped**\n👤 **By:** {message.from_user.mention}"
            )
        except:
            pass
    await message.reply_text("✅ **Broadcast stopped successfully.**")


# ==========================================
# SELF PROMO BROADCAST LOGIC
# ==========================================
async def run_promo_broadcast(status_message=None):
    await broadcast_time_db.update_one({"_id": "last_run"}, {"$set": {"time": int(time.time())}}, upsert=True)
    
    users = await db.get_users()
    chats = await db.get_chats()

    total_users = len(users)
    total_chats = len(chats)
    total_targets = total_users + total_chats

    u_success, u_failed = 0, 0
    g_success, g_failed = 0, 0
    completed = 0

    async def update_progress():
        if status_message and completed % 20 == 0:  # Update message every 20 sends
            bar = get_progress_bar(completed, total_targets)
            percent = int((completed / total_targets) * 100) if total_targets else 100
            text = (
                f"🔄 **Live Promo Broadcasting...**\n\n"
                f"[{bar}] **{percent}%**\n\n"
                f"👥 **Users:** ✅ {u_success} | ❌ {u_failed}\n"
                f"🏘 **Groups:** ✅ {g_success} | ❌ {g_failed}"
            )
            try:
                await status_message.edit_text(text)
            except Exception:
                pass

    for user in users:
        user_id = user["user_id"] if isinstance(user, dict) else user
        try:
            msg = await app.send_photo(
                chat_id=int(user_id), 
                photo=PROMO_IMAGE, 
                caption=PROMO_TEXT, 
                reply_markup=get_random_button()
            )
            await save_promo_msg(int(user_id), msg.id)
            u_success += 1
        except FloodWait as e:
            await asyncio.sleep(e.value)
        except Exception:
            u_failed += 1
        
        completed += 1
        await update_progress()
        await asyncio.sleep(0.5)

    for chat in chats:
        chat_id = chat["chat_id"] if isinstance(chat, dict) else chat
        try:
            msg = await app.send_photo(
                chat_id=int(chat_id), 
                photo=PROMO_IMAGE, 
                caption=PROMO_TEXT, 
                reply_markup=get_random_button()
            )
            await save_promo_msg(int(chat_id), msg.id)
            g_success += 1
        except FloodWait as e:
            await asyncio.sleep(e.value)
        except Exception:
            g_failed += 1
        
        completed += 1
        await update_progress()
        await asyncio.sleep(0.5)

    return u_success, u_failed, g_success, g_failed


@app.on_message(filters.command(["selfpromo", "promo"]) & app.sudoers)
async def promo_toggle_cmd(client, message):
    if len(message.command) != 2:
        return await message.reply_text(
            "**Usage Options:**\n"
            "`/selfpromo on` - Start auto 24-hour broadcast\n"
            "`/selfpromo off` - Stop auto broadcast\n"
            "`/selfpromo run` - Instantly broadcast right now"
        )
    
    state = message.command[1].lower()
    
    if state == "on":
        await set_promo_status(True)
        await message.reply_text("✅ **Auto Self Promo Started!**\nBot will broadcast every 24 hours.")
    elif state == "off":
        await set_promo_status(False)
        await message.reply_text("❌ **Auto Self Promo Stopped!**")
    elif state == "run":
        status_msg = await message.reply_text("🔄 **Calculating stats & initializing broadcast...**")
        try:
            u_success, u_failed, g_success, g_failed = await run_promo_broadcast(status_message=status_msg)
            
            stats_text = (
                f"📢 **Manual Promo Completed** ✅\n\n"
                f"👥 **Users:** ✅ {u_success} | ❌ {u_failed}\n"
                f"🏘 **Groups:** ✅ {g_success} | ❌ {g_failed}"
            )
            await status_msg.edit_text(stats_text)
            
            if hasattr(app, "logger") and app.logger:
                await app.send_message(app.logger, stats_text)
        except Exception as e:
            await status_msg.edit_text(f"❌ Error: {e}")
    else:
        await message.reply_text("**Invalid argument.** Use `on`, `off`, or `run`.")


# ==========================================
# BACKGROUND TASKS (Auto-Delete & Auto-Promo)
# ==========================================
async def auto_promo_task():
    while True:
        try:
            old_messages = await get_old_promo_msgs()
            async for doc in old_messages:
                try:
                    await app.delete_messages(chat_id=doc["chat_id"], message_ids=doc["message_id"])
                except Exception:
                    pass
                await delete_promo_record(doc["chat_id"], doc["message_id"])
                await asyncio.sleep(1)

            if await is_promo_on():
                last_run_data = await broadcast_time_db.find_one({"_id": "last_run"})
                last_run = last_run_data["time"] if last_run_data else 0
                
                if (int(time.time()) - last_run) >= 86400: # Runs every 24 hours
                    u_success, u_failed, g_success, g_failed = await run_promo_broadcast()
                    if hasattr(app, "logger") and app.logger:
                        stats_text = f"📢 **Auto Promo Completed**\n\n👥 **Users:** ✅ {u_success} | ❌ {u_failed}\n🏘 **Groups:** ✅ {g_success} | ❌ {g_failed}"
                        await app.send_message(app.logger, stats_text)
        except Exception:
            pass
        await asyncio.sleep(3600) # Re-checks time limit every 1 hour


async def auto_delete_gcast_task():
    # 24 Ghante baad Normal Broadcast delete karega
    while True:
        try:
            time_limit = int(time.time()) - 86400 # 24 hours ago
            old_messages = gcast_msgs_db.find({"timestamp": {"$lt": time_limit}})
            async for doc in old_messages:
                try:
                    await app.delete_messages(chat_id=doc["chat_id"], message_ids=doc["message_id"])
                except Exception:
                    pass
                await gcast_msgs_db.delete_one({"_id": doc["_id"]})
                await asyncio.sleep(1) # Prevent flooding
        except Exception:
            pass
        await asyncio.sleep(3600) # Check every 1 hour

# Starts background processes alongside bot
asyncio.create_task(auto_promo_task())
asyncio.create_task(auto_delete_gcast_task())
