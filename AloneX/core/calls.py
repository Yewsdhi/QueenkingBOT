# Copyright (c) 2026 THE SHIV
# Licensed under the MIT License.
# This file is part of MahiMusic
# DEVELOPER - THE SHIV

import asyncio
import aiohttp
import logging
from collections import defaultdict

from ntgcalls import (
    ConnectionNotFound,
    TelegramServerError,
    RTMPStreamingUnsupported,
)

from pyrogram.errors import (
    MessageIdInvalid,
    FloodWait,
    MessageNotModified,
)

from pyrogram.types import (
    InputMediaPhoto,
    Message,
)

from pytgcalls import (
    PyTgCalls,
    exceptions,
    types,
)

from pytgcalls.pytgcalls_session import PyTgCallsSession

from AloneX import (
    app,
    config,
    db,
    lang,
    logger,
    queue,
    userbot,
    yt,
)

from AloneX.helpers import (
    Media,
    Track,
    buttons,
    thumb,
    utils,
    vclogger,
)


# ==========================================
# GLOBAL ERROR HANDLER & STATE SYNC
# ==========================================

def handle_asyncio_exceptions(loop, context):
    msg = context.get(
        "exception",
        context.get("message"),
    )

    msg_str = str(msg).lower()

    expected_sync_events = [
        "groupcall_forbidden",
        "setvideocallstatus",
        "groupcall_invalid",
        "no active group call",
        "group call has already ended",
        "not in a call",
        "connection not found",
        "connectionnotfound",
    ]

    if any(
        err in msg_str
        for err in expected_sync_events
    ):
        logging.getLogger(
            "asyncio"
        ).info(
            f"ℹ️ VC State Sync: {msg}"
        )
    else:
        logging.getLogger(
            "asyncio"
        ).error(
            f"❌ Unhandled Asyncio Error: {msg}"
        )


try:
    loop = asyncio.get_running_loop()
except RuntimeError:
    loop = asyncio.get_event_loop()

loop.set_exception_handler(
    handle_asyncio_exceptions
)


# ==========================================
# AUTOPLAY NOTICE DELETE
# ==========================================

async def _delete_msg(
    msg: Message,
    delay: int = 6,
):
    """
    This is ONLY used for temporary autoplay
    notices.

    VC join/leave/mute/unmute notifications
    are NOT deleted from this file.
    """
    try:
        await asyncio.sleep(delay)
        await msg.delete()
    except Exception:
        pass


# ==========================================
# API BASED AUTOPLAY
# ==========================================

async def get_related_via_api(
    video_id: str,
    history: list,
):
    api_key = getattr(
        config,
        "YOUTUBE_API_KEY",
        None,
    )

    if not api_key:
        return None

    url = (
        "https://www.googleapis.com/youtube/v3/search"
        f"?part=snippet"
        f"&relatedToVideoId={video_id}"
        f"&type=video"
        f"&key={api_key}"
        f"&maxResults=10"
    )

    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as resp:

                if resp.status == 200:
                    data = await resp.json()

                    for item in data.get(
                        "items",
                        [],
                    ):
                        vid = item.get(
                            "id",
                            {},
                        ).get(
                            "videoId"
                        )

                        if (
                            vid
                            and vid not in history
                        ):
                            title = item.get(
                                "snippet",
                                {},
                            ).get(
                                "title",
                                "Unknown Track",
                            )

                            return Track(
                                id=vid,
                                title=title,
                                url=(
                                    "https://www.youtube.com/watch?v="
                                    f"{vid}"
                                ),
                                duration="00:00",
                                user="Autoplay",
                                video=False,
                            )

    except Exception as e:
        logger.error(
            f"Autoplay API Error: {e}"
        )

    return None


# ==========================================
# API BASED STREAM URL
# ==========================================

async def get_stream_via_api(
    video_id: str,
    video: bool = False,
):

    api_url = (
        f"https://teaminflex.xyz/streams/{video_id}"
    )

    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(
                api_url
            ) as resp:

                if resp.status == 200:

                    data = await resp.json()

                    audio_streams = data.get(
                        "audioStreams",
                        [],
                    )

                    video_streams = data.get(
                        "videoStreams",
                        [],
                    )

                    if (
                        video
                        and video_streams
                    ):

                        stream = next(
                            (
                                s
                                for s in video_streams
                                if s.get("quality")
                                == "720p"
                            ),
                            video_streams[0],
                        )

                        return stream.get(
                            "url"
                        )

                    elif audio_streams:

                        return audio_streams[0].get(
                            "url"
                        )

    except Exception as e:
        logger.error(
            f"Stream Fetch API Error: {e}"
        )

    return None


# ==========================================
# TG CALL
# ==========================================

class TgCall(PyTgCalls):

    def __init__(self):

        self.clients = []

        self.history: dict[
            int,
            list[str]
        ] = defaultdict(list)

        self.pending_autoplay: dict[
            int,
            Track
        ] = {}

        self.autoplay_prefetching: set[
            int
        ] = set()

        self.autoplay_failures: dict[
            int,
            int
        ] = defaultdict(int)


    # ======================================
    # PREFETCH
    # ======================================

    async def _prefetch_next(
        self,
        chat_id: int,
    ):

        if chat_id in self.autoplay_prefetching:
            return

        self.autoplay_prefetching.add(
            chat_id
        )

        try:

            await asyncio.sleep(2)

            try:

                q = queue.get(chat_id)

                if (
                    q
                    and isinstance(q, list)
                    and len(q) > 1
                ):

                    next_track = q[1]

                    if not next_track.file_path:

                        try:

                            next_track.file_path = (
                                await get_stream_via_api(
                                    next_track.id,
                                    video=next_track.video,
                                )
                            )

                        except Exception as e:

                            logger.error(
                                "Prefetch Queue "
                                f"Download Error: {e}"
                            )

                    return

            except Exception:
                pass

            if await db.get_autoplay(
                chat_id
            ):

                current = queue.get_current(
                    chat_id
                )

                if (
                    current
                    and isinstance(
                        current,
                        Track,
                    )
                ):

                    related = (
                        await get_related_via_api(
                            current.id,
                            self.history[chat_id],
                        )
                    )

                    if related:

                        if not related.file_path:

                            try:

                                related.file_path = (
                                    await get_stream_via_api(
                                        related.id,
                                        video=related.video,
                                    )
                                )

                            except Exception as e:

                                logger.error(
                                    "Prefetch Autoplay "
                                    f"Download Error: {e}"
                                )

                        self.pending_autoplay[
                            chat_id
                        ] = related

        except Exception:
            pass

        finally:

            self.autoplay_prefetching.discard(
                chat_id
            )


    # ======================================
    # PAUSE
    # ======================================

    async def pause(
        self,
        chat_id: int,
    ) -> bool:

        client = await db.get_assistant(
            chat_id
        )

        try:
            await db.playing(
                chat_id,
                paused=True,
            )
        except Exception:
            pass

        return await client.pause(
            chat_id
        )


    # ======================================
    # RESUME
    # ======================================

    async def resume(
        self,
        chat_id: int,
    ) -> bool:

        client = await db.get_assistant(
            chat_id
        )

        try:
            await db.playing(
                chat_id,
                paused=False,
            )
        except Exception:
            pass

        return await client.resume(
            chat_id
        )


    # ======================================
    # STOP
    # ======================================

    async def stop(
        self,
        chat_id: int,
    ) -> None:

        client = await db.get_assistant(
            chat_id
        )

        self.autoplay_failures[
            chat_id
        ] = 0

        try:

            queue.clear(
                chat_id
            )

            await db.remove_call(
                chat_id
            )

        except Exception:
            pass

        self.history.pop(
            chat_id,
            None,
        )

        self.pending_autoplay.pop(
            chat_id,
            None,
        )

        self.autoplay_prefetching.discard(
            chat_id
        )

        try:
            vclogger.clear_chat(
                chat_id
            )
        except Exception:
            pass

        try:

            await client.leave_call(
                chat_id,
                close=False,
            )

            logger.info(
                "✅ Assistant left VC "
                f"successfully in chat {chat_id}."
            )

        except Exception as e:

            error_msg = str(e).lower()

            ignore_list = [
                "no active group call",
                "already ended",
                "not in a call",
                "groupcall_forbidden",
                "groupcall_invalid",
                "connection not found",
                "connectionnotfound",
            ]

            if any(
                ign in error_msg
                for ign in ignore_list
            ):

                logger.info(
                    "ℹ️ Assistant State Sync: "
                    f"VC already closed in {chat_id}."
                )

            else:

                logger.error(
                    "❌ Assistant failed "
                    f"to leave VC in {chat_id}: {e}"
                )


    # ======================================
    # PLAY MEDIA
    # ======================================

    async def play_media(
        self,
        chat_id: int,
        message: Message,
        media: Media | Track,
        seek_time: int = 0,
    ) -> None:

        client = await db.get_assistant(
            chat_id
        )

        _lang = await lang.get_lang(
            chat_id
        )

        _thumb = (
            await thumb.generate(media)
            if isinstance(media, Track)
            else config.DEFAULT_THUMB
        )

        if not media.file_path:

            await message.edit_text(
                _lang[
                    "error_no_file"
                ].format(
                    config.SUPPORT_CHAT
                )
            )

            return await self.play_next(
                chat_id
            )

        stream = types.MediaStream(
            media_path=media.file_path,

            audio_parameters=(
                types.AudioQuality.HIGH
            ),

            video_parameters=(
                types.VideoQuality.HD_720p
            ),

            audio_flags=(
                types.MediaStream.Flags.REQUIRED
            ),

            video_flags=(
                types.MediaStream.Flags.AUTO_DETECT
                if media.video
                else types.MediaStream.Flags.IGNORE
            ),

            ffmpeg_parameters=(
                f"-ss {seek_time}"
                if seek_time > 1
                else None
            ),
        )

        try:

            await client.play(
                chat_id=chat_id,
                stream=stream,
                config=types.GroupCallConfig(
                    auto_start=False
                ),
            )

        except Exception as e:

            logger.warning(
                "720p Change Stream failed, "
                f"auto-switching to 480p: {e}"
            )

            stream.video_parameters = (
                types.VideoQuality.SD_480p
            )

            try:

                await client.play(
                    chat_id=chat_id,
                    stream=stream,
                    config=types.GroupCallConfig(
                        auto_start=False
                    ),
                )

            except Exception as e2:

                logger.error(
                    "Failed to play even at 480p: "
                    f"{e2}"
                )

                return await self.play_next(
                    chat_id
                )

        if not seek_time:

            media.time = 1

            await db.add_call(
                chat_id
            )

            play_type = (
                "🎬 Video"
                if media.video
                else "🎧 Audio"
            )

            linked_title = (
                f"<a href='{media.url}'>"
                f"{media.title}"
                f"</a>"
            )

            text = _lang[
                "play_media"
            ].format(
                media.url,
                linked_title,
                media.duration,
                media.user,
                play_type,
            )

            start_timer = (
                f"00:00 {media.duration}"
            )

            keyboard = buttons.controls(
                chat_id,
                timer=start_timer,
            )

            try:

                active_msg = (
                    await message.edit_media(
                        media=InputMediaPhoto(
                            media=_thumb,
                            caption=text,
                        ),
                        reply_markup=keyboard,
                    )
                )

            except MessageIdInvalid:

                active_msg = (
                    await app.send_photo(
                        chat_id=chat_id,
                        photo=_thumb,
                        caption=text,
                        reply_markup=keyboard,
                    )
                )

            media.message_id = (
                active_msg.id
            )

            asyncio.create_task(
                self._prefetch_next(
                    chat_id
                )
            )


    # ======================================
    # PLAY NEXT
    # ======================================

    async def play_next(
        self,
        chat_id: int,
    ) -> None:

        current = queue.get_current(
            chat_id
        )

        if current:

            history = self.history[
                chat_id
            ]

            history.append(
                current.id
            )

            del history[:-20]

        self.autoplay_prefetching.discard(
            chat_id
        )

        media = queue.get_next(
            chat_id
        )

        if not media:

            if (
                current
                and isinstance(
                    current,
                    Track,
                )
                and await db.get_autoplay(
                    chat_id
                )
            ):

                related = self.pending_autoplay.pop(
                    chat_id,
                    None,
                )

                if not related:

                    try:

                        related = (
                            await get_related_via_api(
                                current.id,
                                self.history[
                                    chat_id
                                ],
                            )
                        )

                    except Exception:
                        related = None

                if not related:

                    self.autoplay_failures[
                        chat_id
                    ] += 1

                    if (
                        self.autoplay_failures[
                            chat_id
                        ] >= 4
                    ):

                        await app.send_message(
                            chat_id,
                            "⚠️ Autoplay failed 4 times. "
                            "Stopping stream.",
                        )

                        return await self.stop(
                            chat_id
                        )

                else:

                    self.autoplay_failures[
                        chat_id
                    ] = 0

                if related:

                    related.user = "Autoplay"

                    queue.add(
                        chat_id,
                        related,
                    )

                    media = queue.get_current(
                        chat_id
                    )

                    short_title = (
                        media.title[:45]
                        + "..."
                        if len(media.title) > 45
                        else media.title
                    )

                    matched_title = (
                        current.title[:45]
                        + "..."
                        if current
                        and current.title
                        and len(current.title) > 45
                        else (
                            current.title
                            if current
                            and current.title
                            else "Unknown Track"
                        )
                    )

                    _lang = await lang.get_lang(
                        chat_id
                    )

                    autoplay_notice_text = (
                        _lang.get(
                            "autoplay_notice",
                            (
                                "<blockquote>"
                                "▶️ <b>Aᴜᴛᴏᴘʟᴀʏ Nᴇxᴛ :</b>\n"
                                "🎧 <a href='{url}'>"
                                "<i>{title}</i>"
                                "</a>"
                                "</blockquote>"
                            ),
                        )
                        .format(
                            url=media.url,
                            title=short_title,
                        )
                    )

                    notice = await app.send_message(
                        chat_id=chat_id,
                        text=autoplay_notice_text,
                        disable_web_page_preview=True,
                    )

                    asyncio.create_task(
                        _delete_msg(
                            notice,
                            6,
                        )
                    )

                    try:

                        chat_info = await app.get_chat(
                            chat_id
                        )

                        chat_title = (
                            chat_info.title
                        )

                    except Exception:

                        chat_title = (
                            "Unknown Chat"
                        )

                    title_lower = (
                        current.title.lower()
                        if current
                        and current.title
                        else ""
                    )

                    keywords_map = {

                        "Hindi": [
                            "arijit singh",
                            "shreya ghoshal",
                            "atif aslam",
                            "neha kakkar",
                            "jubin nautiyal",
                            "darshan raval",
                            "armaan malik",
                            "sonu nigam",
                            "badshah",
                            "sunidhi chauhan",
                            "udit narayan",
                            "kumar sanu",
                            "alka yagnik",
                            "sachet tandon",
                            "parampara",
                            "b praak",
                            "vishal mishra",
                            "shilpa rao",
                            "kk",
                            "mohit chauhan",
                            "ar rahman",
                            "pritam",
                            "mithoon",
                        ],

                        "Punjabi": [
                            "sidhu moose wala",
                            "karan aujla",
                            "diljit dosanjh",
                            "ap dhillon",
                            "amrit maan",
                            "shubh",
                            "kaka",
                            "hardy sandhu",
                            "guru randhawa",
                            "jass manak",
                            "parmish verma",
                            "jaani",
                            "ammy virk",
                            "garry sandhu",
                        ],

                        "Bhojpuri": [
                            "pawan singh",
                            "khesari lal yadav",
                            "shilpi raj",
                            "antra singh",
                            "pramod premi",
                            "ritesh pandey",
                            "arvind akela kallu",
                            "gunjan singh",
                            "samar singh",
                            "neha raj",
                        ],

                        "Haryanvi": [
                            "sapna choudhary",
                            "renuka panwar",
                            "gulzaar chhaniwala",
                            "sumit goswami",
                            "raju punjabi",
                            "amit saini rohtakiya",
                            "pranjal dahiya",
                            "md kd",
                            "masoom sharma",
                        ],

                        "English": [
                            "taylor swift",
                            "justin bieber",
                            "ed sheeran",
                            "ariana grande",
                            "the weeknd",
                            "drake",
                            "eminem",
                        ],
                    }

                    detected_lang = None
                    detected_artist = None
                    detected_mood = None

                    moods_list = [
                        "sad",
                        "love",
                        "romantic",
                        "lofi",
                        "chill",
                        "party",
                        "mashup",
                        "emotional",
                        "heartbreak",
                        "dance",
                        "dj",
                    ]

                    for mood in moods_list:

                        if mood in title_lower:

                            detected_mood = (
                                mood.title()
                            )

                            break

                    for (
                        lang_name,
                        kws,
                    ) in keywords_map.items():

                        for kw in kws:

                            if kw in title_lower:

                                detected_lang = (
                                    lang_name
                                )

                                if kw not in [
                                    "hindi",
                                    "punjabi",
                                    "bhojpuri",
                                    "haryanvi",
                                    "english",
                                ]:

                                    detected_artist = (
                                        kw.title()
                                    )

                                break

                        if detected_lang:
                            break

                    artist_or_lang = (
                        " / ".join(
                            filter(
                                None,
                                [
                                    detected_artist,
                                    detected_lang,
                                ],
                            )
                        )
                    )

                    if not artist_or_lang:
                        artist_or_lang = (
                            "Algorithmic Match"
                        )

                    vibe_focus = (
                        detected_mood
                        if detected_mood
                        else "Auto-Match"
                    )

                    log_text = _lang.get(
                        "autoplay_log",
                        (
                            "<blockquote>"
                            "<b>📻 SPOTIFY-STYLE "
                            "RADIO ACTIVE</b>\n\n"

                            "<b>🥀 GROUP :</b> "
                            "{chat_title} "
                            "[{chat_id}]\n"

                            "<b>🎵 PLAYING :</b> "
                            "<a href='{media_url}'>"
                            "{short_title}"
                            "</a>\n"

                            "<b>🔗 SEED TRACK :</b> "
                            "{matched_title}\n"

                            "<b>🎭 ARTIST/GENRE :</b> "
                            "{artist_or_lang}\n"

                            "<b>✨ VIBE FOCUS :</b> "
                            "{vibe_focus}"
                            "</blockquote>"
                        ),
                    ).format(
                        chat_title=chat_title,
                        chat_id=chat_id,
                        media_url=media.url,
                        short_title=short_title,
                        matched_title=matched_title,
                        artist_or_lang=artist_or_lang,
                        vibe_focus=vibe_focus,
                    )

                    try:

                        if (
                            hasattr(
                                config,
                                "LOGGER_ID",
                            )
                            and config.LOGGER_ID
                        ):

                            await app.send_message(
                                chat_id=config.LOGGER_ID,
                                text=log_text,
                                disable_web_page_preview=True,
                            )

                    except Exception:
                        pass

            if not media:
                return await self.stop(
                    chat_id
                )

        _lang = await lang.get_lang(
            chat_id
        )

        if not media.file_path:

            msg = await app.send_message(
                chat_id=chat_id,
                text=_lang["play_next"],
            )

            media.file_path = (
                await get_stream_via_api(
                    media.id,
                    video=media.video,
                )
            )

        else:

            msg = await app.send_message(
                chat_id=chat_id,
                text="⚡",
            )

        if not media.file_path:
            try:
                from AloneX.core.youtube import YouTube as yt
                vid_id = getattr(media, "id", None) or getattr(media, "url", None)
                if vid_id:
                    media.file_path = await yt.download(vid_id, video=bool(getattr(media, "video", False)))
            except Exception as _e:
                pass

        if not media.file_path:

            await msg.edit_text(
                "⚠️ API Error: "
                "Unable to fetch stream URL."
            )

            return await self.play_next(
                chat_id
            )

        media.message_id = msg.id

        await self.play_media(
            chat_id,
            msg,
            media,
        )


    # ======================================
    # PING
    # ======================================

    async def ping(self) -> float:

        pings = [
            client.ping
            for client in self.clients
        ]

        if not pings:
            return 0.0

        return round(
            sum(pings) / len(pings),
            2,
        )


    # ======================================
    # VC PARTICIPANT ACTION HELPER
    # ======================================

    @staticmethod
    def _participant_action_name(
        action,
    ) -> str:

        if action is None:
            return ""

        try:
            name = getattr(
                action,
                "name",
                None,
            )

            if name:
                return str(
                    name
                ).lower()
        except Exception:
            pass

        try:
            value = getattr(
                action,
                "value",
                None,
            )

            if value:
                return str(
                    value
                ).lower()
        except Exception:
            pass

        return str(
            action
        ).lower()


    # ======================================
    # UPDATE DECORATORS
    # ======================================

    async def decorators(
        self,
        client: PyTgCalls,
    ) -> None:

        participant_update = getattr(
            types,
            "UpdatedGroupCallParticipant",
            None,
        )

        @client.on_update()
        async def update_handler(
            _,
            update: types.Update,
        ) -> None:

            try:

                # ==================================
                # STREAM ENDED
                # ==================================

                if isinstance(
                    update,
                    types.StreamEnded,
                ):

                    if (
                        update.stream_type
                        == types.StreamEnded.Type.AUDIO
                    ):

                        await self.play_next(
                            update.chat_id
                        )

                    return


                # ==================================
                # CHAT / VC CLOSED
                # ==================================

                if isinstance(
                    update,
                    types.ChatUpdate,
                ):

                    if update.status in [
                        types.ChatUpdate.Status.KICKED,
                        types.ChatUpdate.Status.LEFT_GROUP,
                        types.ChatUpdate.Status.CLOSED_VOICE_CHAT,
                    ]:

                        await self.stop(
                            update.chat_id
                        )

                    return


                # ==================================
                # PARTICIPANT UPDATE
                # ==================================

                if not (
                    participant_update
                    and isinstance(
                        update,
                        participant_update,
                    )
                ):
                    return


                # ----------------------------------
                # CHAT ID
                # ----------------------------------

                chat_id = getattr(
                    update,
                    "chat_id",
                    None,
                )

                if not chat_id:
                    return


                # ----------------------------------
                # PARTICIPANT
                # ----------------------------------

                participant = getattr(
                    update,
                    "participant",
                    None,
                )

                if participant is None:
                    return


                # ----------------------------------
                # USER ID
                # ----------------------------------

                user_id = getattr(
                    participant,
                    "user_id",
                    None,
                )

                if user_id is None:

                    user_id = getattr(
                        update,
                        "user_id",
                        None,
                    )

                if user_id is None:

                    user = getattr(
                        participant,
                        "user",
                        None,
                    )

                    if user is not None:

                        user_id = getattr(
                            user,
                            "id",
                            None,
                        )

                if not user_id:
                    return


                # ----------------------------------
                # ACTION
                # ----------------------------------

                action = getattr(
                    update,
                    "action",
                    None,
                )

                if action is None:

                    action = getattr(
                        participant,
                        "action",
                        None,
                    )

                action_name = (
                    self._participant_action_name(
                        action
                    )
                )


                logger.debug(
                    "[VCLogger] Participant update "
                    f"chat={chat_id} "
                    f"user={user_id} "
                    f"action={action_name} "
                    f"muted={getattr(participant, 'muted', None)}"
                )


                # ==================================
                # JOIN
                # ==================================

                is_join = (
                    "join" in action_name
                    or "joined" in action_name
                )

                if is_join:

                    try:

                        await vclogger.notify_join(
                            chat_id,
                            user_id,
                        )

                    except Exception as e:

                        logger.error(
                            "[VCLogger] Join notification "
                            f"error: {e}"
                        )

                    muted = getattr(
                        participant,
                        "muted",
                        None,
                    )

                    if muted is not None:

                        vclogger.mute_state[
                            (
                                chat_id,
                                user_id,
                            )
                        ] = bool(
                            muted
                        )

                    else:

                        # Unknown initial state.
                        # Do not create a fake mute event.
                        vclogger.mute_state.pop(
                            (
                                chat_id,
                                user_id,
                            ),
                            None,
                        )

                    return


                # ==================================
                # LEAVE
                # ==================================

                is_leave = (
                    "leave" in action_name
                    or "left" in action_name
                )

                if is_leave:

                    try:

                        await vclogger.notify_leave(
                            chat_id,
                            user_id,
                        )

                    except Exception as e:

                        logger.error(
                            "[VCLogger] Leave notification "
                            f"error: {e}"
                        )

                    vclogger.mute_state.pop(
                        (
                            chat_id,
                            user_id,
                        ),
                        None,
                    )

                    return


                # ==================================
                # MUTE STATE
                # ==================================

                muted = getattr(
                    participant,
                    "muted",
                    None,
                )

                if muted is None:

                    # Some pytgcalls/ntgcalls versions
                    # expose is_muted instead.
                    muted = getattr(
                        participant,
                        "is_muted",
                        None,
                    )

                if muted is None:
                    return


                new_muted = bool(
                    muted
                )

                key = (
                    chat_id,
                    user_id,
                )

                old_muted = (
                    vclogger.mute_state.get(
                        key,
                        None,
                    )
                )


                # ==================================
                # FIRST KNOWN STATE
                # ==================================

                if old_muted is None:

                    vclogger.mute_state[
                        key
                    ] = new_muted

                    return


                # ==================================
                # NO CHANGE
                # ==================================

                if old_muted == new_muted:
                    return


                # IMPORTANT: do NOT update mute_state here.
                # notify_mute()/notify_unmute() owns the state update.
                # Updating it before the notification would make
                # notify_mute() / notify_unmute() return immediately.

                # ==================================
                # MUTED
                # ==================================

                if (
                    old_muted is False
                    and new_muted is True
                ):

                    try:

                        await vclogger.notify_mute(
                            chat_id,
                            user_id,
                        )

                    except Exception as e:

                        logger.error(
                            "[VCLogger] Mute notification "
                            f"error: {e}"
                        )

                    return


                # ==================================
                # UNMUTED
                # ==================================

                if (
                    old_muted is True
                    and new_muted is False
                ):

                    try:

                        await vclogger.notify_unmute(
                            chat_id,
                            user_id,
                        )

                    except Exception as e:

                        logger.error(
                            "[VCLogger] Unmute notification "
                            f"error: {e}"
                        )

                    return


            except Exception as e:

                logger.error(
                    "[VCLogger] Participant update "
                    f"handler error: {e}",
                    exc_info=True,
                )


    # ======================================
    # BOOT
    # ======================================

    async def boot(
        self,
    ) -> None:

        PyTgCallsSession.notice_displayed = True

        for ub in userbot.clients:

            client = PyTgCalls(
                ub,
                cache_duration=100,
            )

            await client.start()

            self.clients.append(
                client
            )

            await self.decorators(
                client
            )

        logger.info(
            "PyTgCalls client(s) started."
        )
