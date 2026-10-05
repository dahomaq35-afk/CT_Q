# =========================================================
# CT QURAN BOT
# cogs/player.py
# =========================================================

import asyncio

import discord
import yt_dlp

from discord.ext import commands

from database import (
    get_voice_channel,
    add_to_queue,
    get_queue,
    get_next_queue_item,
    remove_queue_item,
    clear_queue,
)


# =========================================================
# SETTINGS
# =========================================================

YTDL_OPTIONS = {
    "format": "bestaudio/best",
    "noplaylist": True,
    "quiet": True,
    "no_warnings": True,
    "default_search": "auto",
    "source_address": "0.0.0.0",
}

FFMPEG_OPTIONS = {
    "before_options": (
        "-reconnect 1 "
        "-reconnect_streamed 1 "
        "-reconnect_delay_max 5"
    ),
    "options": "-vn",
}


# =========================================================
# YT-DLP
# =========================================================

ytdl = yt_dlp.YoutubeDL(
    YTDL_OPTIONS
)


def get_audio(url: str):

    info = ytdl.extract_info(
        url,
        download=False
    )

    if not info:
        raise RuntimeError(
            "لم يتم العثور على معلومات الرابط."
        )

    if "entries" in info:

        entries = info.get(
            "entries"
        )

        if not entries:
            raise RuntimeError(
                "الرابط لا يحتوي على مقطع قابل للتشغيل."
            )

        info = entries[0]

    audio_url = info.get(
        "url"
    )

    if not audio_url:
        raise RuntimeError(
            "لم يتم العثور على رابط الصوت."
        )

    return {
        "url": audio_url,
        "title": info.get(
            "title",
            "مقطع قرآن"
        ),
        "webpage_url": info.get(
            "webpage_url",
            url
        ),
        "source": info.get(
            "extractor_key",
            "Unknown"
        ),
    }


# =========================================================
# PLAYER
# =========================================================

class QuranPlayer(commands.Cog):

    def __init__(self, bot):

        self.bot = bot

        # المقطع الحالي لكل سيرفر
        self.current = {}

        # Lock لكل سيرفر
        self.locks = {}

        # مهمة تشغيل الطابور لكل سيرفر
        self.queue_tasks = {}

    # =====================================================
    # LOCK
    # =====================================================

    def get_lock(
        self,
        guild_id: int
    ):

        if guild_id not in self.locks:

            self.locks[guild_id] = (
                asyncio.Lock()
            )

        return self.locks[guild_id]

    # =====================================================
    # CONNECT TO CONFIGURED VOICE
    # =====================================================

    async def connect_to_configured_voice(
        self,
        guild: discord.Guild
    ):

        channel_id = get_voice_channel(
            guild.id
        )

        if not channel_id:

            print(
                f"[PLAYER] No voice channel configured "
                f"for guild {guild.id}"
            )

            return None

        channel = guild.get_channel(
            channel_id
        )

        if not isinstance(
            channel,
            discord.VoiceChannel
        ):

            print(
                f"[PLAYER] Configured voice channel "
                f"not found for guild {guild.id}"
            )

            return None

        voice = guild.voice_client

        # -------------------------------------------------
        # BOT ALREADY CONNECTED
        # -------------------------------------------------

        if voice and voice.is_connected():

            if voice.channel.id != channel.id:

                try:

                    await voice.move_to(
                        channel
                    )

                except Exception as e:

                    print(
                        f"[PLAYER] Failed to move voice: {e}"
                    )

                    return None

            return voice

        # -------------------------------------------------
        # CONNECT
        # -------------------------------------------------

        try:

            return await channel.connect(
                reconnect=True
            )

        except Exception as e:

            print(
                f"[PLAYER] Failed to connect to voice: {e}"
            )

            return None

    # =====================================================
    # PLAY ITEM
    # =====================================================

    async def play_item(
        self,
        guild: discord.Guild,
        item
    ):

        voice = await self.connect_to_configured_voice(
            guild
        )

        if not voice:

            return False

        # -------------------------------------------------
        # EXTRACT AUDIO
        # -------------------------------------------------

        try:

            audio = await asyncio.to_thread(
                get_audio,
                item["url"]
            )

        except Exception as e:

            print(
                f"[PLAYER] Failed to extract audio: {e}"
            )

            return False

        # -------------------------------------------------
        # CURRENT SONG
        # -------------------------------------------------

        self.current[guild.id] = {
            "title": audio["title"],
            "url": item["url"],
            "user_id": item["user_id"],
            "username": item["username"],
            "source": audio["source"],
        }

        # -------------------------------------------------
        # FFMPEG
        # -------------------------------------------------

        try:

            source = discord.FFmpegPCMAudio(
                audio["url"],
                **FFMPEG_OPTIONS
            )

        except Exception as e:

            print(
                f"[PLAYER] FFmpeg error: {e}"
            )

            self.current.pop(
                guild.id,
                None
            )

            return False

        # -------------------------------------------------
        # WAIT FOR PLAYBACK TO FINISH
        # -------------------------------------------------

        finished = asyncio.Event()

        def after_playing(error):

            if error:

                print(
                    f"[PLAYER] Playback error: {error}"
                )

            try:

                self.bot.loop.call_soon_threadsafe(
                    finished.set
                )

            except Exception as e:

                print(
                    f"[PLAYER] Callback error: {e}"
                )

        try:

            voice.play(
                source,
                after=after_playing
            )

        except Exception as e:

            print(
                f"[PLAYER] Voice play error: {e}"
            )

            self.current.pop(
                guild.id,
                None
            )

            return False

        # -------------------------------------------------
        # WAIT
        # -------------------------------------------------

        try:

            await finished.wait()

        except asyncio.CancelledError:

            if voice.is_playing() or voice.is_paused():

                voice.stop()

            self.current.pop(
                guild.id,
                None
            )

            raise

        # -------------------------------------------------
        # REMOVE CURRENT
        # -------------------------------------------------

        self.current.pop(
            guild.id,
            None
        )

        return True

    # =====================================================
    # PROCESS QUEUE
    # =====================================================

    async def process_queue(
        self,
        guild: discord.Guild
    ):

        guild_id = guild.id

        lock = self.get_lock(
            guild_id
        )

        # -------------------------------------------------
        # PREVENT TWO QUEUES AT ONCE
        # -------------------------------------------------

        if lock.locked():

            return

        async with lock:

            try:

                while True:

                    # -------------------------------------
                    # GET NEXT ITEM
                    # -------------------------------------

                    item = get_next_queue_item(
                        guild_id
                    )

                    if not item:

                        break

                    # -------------------------------------
                    # REMOVE BEFORE PLAYING
                    # -------------------------------------

                    remove_queue_item(
                        item["id"]
                    )

                    # -------------------------------------
                    # PLAY
                    # -------------------------------------

                    success = await self.play_item(
                        guild,
                        item
                    )

                    if not success:

                        print(
                            "[PLAYER] Skipping failed item."
                        )

                        continue

            except asyncio.CancelledError:

                print(
                    f"[PLAYER] Queue task cancelled "
                    f"for guild {guild_id}"
                )

                raise

            except Exception as e:

                print(
                    f"[PLAYER] Queue error: {e}"
                )

            finally:

                # -----------------------------------------
                # DISCONNECT WHEN QUEUE IS EMPTY
                # -----------------------------------------

                voice = guild.voice_client

                if voice and voice.is_connected():

                    try:

                        await voice.disconnect()

                    except Exception as e:

                        print(
                            f"[PLAYER] Disconnect error: {e}"
                        )

                self.current.pop(
                    guild_id,
                    None
                )

                self.queue_tasks.pop(
                    guild_id,
                    None
                )

    # =====================================================
    # START QUEUE
    # =====================================================

    async def start_queue(
        self,
        guild: discord.Guild
    ):

        guild_id = guild.id

        existing_task = self.queue_tasks.get(
            guild_id
        )

        # -------------------------------------------------
        # QUEUE ALREADY RUNNING
        # -------------------------------------------------

        if existing_task:

            if not existing_task.done():

                return existing_task

        # -------------------------------------------------
        # CREATE NEW QUEUE TASK
        # -------------------------------------------------

        task = asyncio.create_task(
            self.process_queue(
                guild
            )
        )

        self.queue_tasks[guild_id] = task

        return task

    # =====================================================
    # ADD SONG
    # =====================================================

    async def add_song(
        self,
        guild: discord.Guild,
        user: discord.Member,
        url: str
    ):

        # -------------------------------------------------
        # EXTRACT INFO FIRST
        # -------------------------------------------------

        try:

            audio = await asyncio.to_thread(
                get_audio,
                url
            )

        except Exception as e:

            print(
                f"[PLAYER] URL error: {e}"
            )

            return False, None

        # -------------------------------------------------
        # ADD TO DATABASE QUEUE
        # -------------------------------------------------

        try:

            add_to_queue(
                guild_id=guild.id,
                user_id=user.id,
                username=str(user),
                url=url,
                title=audio["title"],
                source=audio["source"],
            )

        except Exception as e:

            print(
                f"[PLAYER] Database queue error: {e}"
            )

            return False, None

        # -------------------------------------------------
        # START PLAYER
        # -------------------------------------------------

        await self.start_queue(
            guild
        )

        return True, audio["title"]

    # =====================================================
    # GET CURRENT SONG
    # =====================================================

    def get_current(
        self,
        guild: discord.Guild
    ):

        return self.current.get(
            guild.id
        )

    # =====================================================
    # GET QUEUE
    # =====================================================

    def get_guild_queue(
        self,
        guild: discord.Guild
    ):

        return get_queue(
            guild.id
        )

    # =====================================================
    # PAUSE
    # =====================================================

    async def pause(
        self,
        guild: discord.Guild
    ):

        voice = guild.voice_client

        if not voice:

            return False

        if not voice.is_playing():

            return False

        try:

            voice.pause()

            return True

        except Exception as e:

            print(
                f"[PLAYER] Pause error: {e}"
            )

            return False

    # =====================================================
    # RESUME
    # =====================================================

    async def resume(
        self,
        guild: discord.Guild
    ):

        voice = guild.voice_client

        if not voice:

            return False

        if not voice.is_paused():

            return False

        try:

            voice.resume()

            return True

        except Exception as e:

            print(
                f"[PLAYER] Resume error: {e}"
            )

            return False

    # =====================================================
    # STOP
    # =====================================================

    async def stop(
        self,
        guild: discord.Guild
    ):

        guild_id = guild.id

        # -------------------------------------------------
        # CLEAR QUEUE
        # -------------------------------------------------

        clear_queue(
            guild_id
        )

        self.current.pop(
            guild_id,
            None
        )

        # -------------------------------------------------
        # STOP AUDIO
        # -------------------------------------------------

        voice = guild.voice_client

        if voice:

            try:

                if (
                    voice.is_playing()
                    or voice.is_paused()
                ):

                    voice.stop()

            except Exception as e:

                print(
                    f"[PLAYER] Stop error: {e}"
                )

        return True

    # =====================================================
    # SKIP
    # =====================================================

    async def skip(
        self,
        guild: discord.Guild
    ):

        voice = guild.voice_client

        if not voice:

            return False

        if not voice.is_playing():

            return False

        try:

            voice.stop()

            return True

        except Exception as e:

            print(
                f"[PLAYER] Skip error: {e}"
            )

            return False

    # =====================================================
    # LEAVE
    # =====================================================

    async def leave(
        self,
        guild: discord.Guild
    ):

        guild_id = guild.id

        # -------------------------------------------------
        # CLEAR QUEUE
        # -------------------------------------------------

        clear_queue(
            guild_id
        )

        self.current.pop(
            guild_id,
            None
        )

        # -------------------------------------------------
        # CANCEL QUEUE TASK
        # -------------------------------------------------

        task = self.queue_tasks.get(
            guild_id
        )

        if task and not task.done():

            task.cancel()

            try:

                await task

            except asyncio.CancelledError:

                pass

            except Exception as e:

                print(
                    f"[PLAYER] Queue cancel error: {e}"
                )

        self.queue_tasks.pop(
            guild_id,
            None
        )

        # -------------------------------------------------
        # DISCONNECT
        # -------------------------------------------------

        voice = guild.voice_client

        if not voice:

            return False

        try:

            await voice.disconnect()

        except Exception as e:

            print(
                f"[PLAYER] Leave error: {e}"
            )

            return False

        return True

    # =====================================================
    # COG UNLOAD
    # =====================================================

    async def cog_unload(self):

        for guild_id, task in list(
            self.queue_tasks.items()
        ):

            if task and not task.done():

                task.cancel()

        self.queue_tasks.clear()
        self.current.clear()
        self.locks.clear()


# =========================================================
# SETUP
# =========================================================

async def setup(bot):

    await bot.add_cog(
        QuranPlayer(bot)
    )
