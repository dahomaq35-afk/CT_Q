# =========================================================
# CT QURAN BOT
# cogs/player.py
#
# AUDIO PLAYER
# =========================================================

import os
import asyncio

import discord
import yt_dlp

from discord.ext import commands

from database import (
    get_voice_channel,
    add_to_queue,
    get_next_queue_item,
    get_queue,
    remove_queue_item,
    clear_queue,
)


# =========================================================
# SETTINGS
# =========================================================

BROWSER_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/140.0.0.0 Safari/537.36"
)


# =========================================================
# YT-DLP
# =========================================================

YTDL_OPTIONS = {

    "format": (
        "bestaudio[ext=m4a]/"
        "bestaudio/best"
    ),

    "noplaylist": True,

    "quiet": True,

    "no_warnings": True,

    "default_search": "auto",

    "source_address": "0.0.0.0",

    "nocheckcertificate": True,

    "socket_timeout": 30,

    "retries": 3,

    "fragment_retries": 3,

    "extractor_retries": 3,

    "http_headers": {
        "User-Agent": BROWSER_USER_AGENT,
        "Accept-Language": "en-US,en;q=0.9,ar;q=0.8",
    },

    "extractor_args": {

        "tiktok": {
            "app_name": "musical_ly",
            "app_version": "39.4.3",
        }

    },
}


# =========================================================
# FFMPEG
# =========================================================

FFMPEG_OPTIONS = {

    "before_options": (
        "-reconnect 1 "
        "-reconnect_streamed 1 "
        "-reconnect_delay_max 5"
    ),

    "options": "-vn",

}


# =========================================================
# COG
# =========================================================

class QuranPlayer(commands.Cog):

    def __init__(
        self,
        bot
    ):

        self.bot = bot

        self.queue_tasks = {}

        self.current = {}

        self.paused = {}

        self.processing = set()


    # =====================================================
    # YT-DLP
    # =====================================================

    async def extract_audio(
        self,
        url: str
    ):

        options = dict(
            YTDL_OPTIONS
        )

        try:

            with yt_dlp.YoutubeDL(
                options
            ) as ytdl:

                info = await asyncio.to_thread(
                    ytdl.extract_info,
                    url,
                    False
                )

            if not info:

                return None

            if "entries" in info:

                entries = info.get(
                    "entries"
                )

                if not entries:

                    return None

                info = entries[0]

            audio_url = info.get(
                "url"
            )

            if not audio_url:

                formats = info.get(
                    "formats",
                    []
                )

                audio_formats = [
                    f
                    for f in formats
                    if f.get("acodec")
                    and f.get("acodec") != "none"
                    and f.get("url")
                ]

                if not audio_formats:

                    return None

                audio_formats.sort(
                    key=lambda x: (
                        x.get(
                            "abr",
                            0
                        ) or 0
                    ),
                    reverse=True
                )

                audio_url = audio_formats[0].get(
                    "url"
                )

            if not audio_url:

                return None

            return {
                "url": audio_url,
                "title": info.get(
                    "title",
                    "قرآن"
                ),
                "webpage_url": info.get(
                    "webpage_url",
                    url
                ),
                "source": info.get(
                    "extractor_key",
                    info.get(
                        "extractor",
                        "unknown"
                    )
                ),
            }

        except Exception as e:

            print(
                "[PLAYER] "
                f"Audio extraction error: {e}"
            )

            return None


    # =====================================================
    # GET VOICE
    # =====================================================

    async def get_voice_client(
        self,
        guild: discord.Guild
    ):

        voice = guild.voice_client

        if voice and voice.is_connected():

            return voice

        channel_id = get_voice_channel(
            guild.id
        )

        if not channel_id:

            return None

        channel = guild.get_channel(
            channel_id
        )

        if not channel:

            return None

        try:

            voice = await channel.connect(
                reconnect=True
            )

            return voice

        except discord.ClientException:

            voice = guild.voice_client

            if voice:

                return voice

            return None

        except Exception as e:

            print(
                "[PLAYER] "
                f"Voice connection error: {e}"
            )

            return None


    # =====================================================
    # PLAY SOURCE
    # =====================================================

    async def play_item(
        self,
        guild: discord.Guild,
        item
    ):

        voice = await self.get_voice_client(
            guild
        )

        if not voice:

            print(
                "[PLAYER] "
                "Could not connect to voice."
            )

            return False

        data = await self.extract_audio(
            item["url"]
        )

        if not data:

            print(
                "[PLAYER] "
                "Could not extract audio."
            )

            return False

        source = discord.FFmpegPCMAudio(
            data["url"],
            **FFMPEG_OPTIONS
        )

        finished = asyncio.Event()

        def after_playing(error):

            if error:

                print(
                    "[PLAYER] "
                    f"Playback error: {error}"
                )

            try:

                self.bot.loop.call_soon_threadsafe(
                    finished.set
                )

            except Exception:

                pass

        self.current[guild.id] = {
            "title": data["title"],
            "url": item["url"],
            "user_id": item["user_id"],
        }

        self.paused[guild.id] = False

        try:

            voice.play(
                source,
                after=after_playing
            )

        except Exception as e:

            print(
                "[PLAYER] "
                f"Play error: {e}"
            )

            return False

        print(
            "[PLAYER] "
            f"Playing: {data['title']}"
        )

        await finished.wait()

        self.current.pop(
            guild.id,
            None
        )

        self.paused.pop(
            guild.id,
            None
        )

        return True


    # =====================================================
    # QUEUE PROCESSOR
    # =====================================================

    async def process_queue(
        self,
        guild: discord.Guild
    ):

        guild_id = guild.id

        if guild_id in self.processing:

            return

        self.processing.add(
            guild_id
        )

        try:

            while True:

                item = get_next_queue_item(
                    guild_id
                )

                if not item:

                    break

                remove_queue_item(
                    item["id"]
                )

                success = await self.play_item(
                    guild,
                    item
                )

                if not success:

                    continue

        except asyncio.CancelledError:

            raise

        except Exception as e:

            print(
                "[PLAYER] "
                f"Queue error: {e}"
            )

        finally:

            self.processing.discard(
                guild_id
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

        if guild_id in self.processing:

            return

        existing = self.queue_tasks.get(
            guild_id
        )

        if existing and not existing.done():

            return

        task = asyncio.create_task(
            self.process_queue(
                guild
            )
        )

        self.queue_tasks[guild_id] = task


    # =====================================================
    # ADD SONG
    # =====================================================

    async def add_song(
        self,
        guild: discord.Guild,
        user: discord.Member,
        url: str
    ):

        try:

            info = await self.extract_audio(
                url
            )

            if not info:

                return False, None

            title = info.get(
                "title",
                "قرآن"
            )

            source = info.get(
                "source",
                "unknown"
            )

            add_to_queue(
                guild_id=guild.id,
                user_id=user.id,
                username=str(user),
                url=url,
                title=title,
                source=source
            )

            print(
                "[PLAYER] "
                f"Added to queue: {title}"
            )

            await self.start_queue(
                guild
            )

            return True, title

        except Exception as e:

            print(
                "[PLAYER] "
                f"Add song error: {e}"
            )

            return False, None


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

        voice.pause()

        self.paused[guild.id] = True

        return True


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

        voice.resume()

        self.paused[guild.id] = False

        return True


    # =====================================================
    # STOP
    # =====================================================

    async def stop(
        self,
        guild: discord.Guild
    ):

        clear_queue(
            guild.id
        )

        voice = guild.voice_client

        if voice:

            if voice.is_playing() or voice.is_paused():

                voice.stop()

        self.current.pop(
            guild.id,
            None
        )

        self.paused.pop(
            guild.id,
            None
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

        if not voice.is_playing() and not voice.is_paused():

            return False

        voice.stop()

        return True


    # =====================================================
    # LEAVE
    # =====================================================

    async def leave(
        self,
        guild: discord.Guild
    ):

        task = self.queue_tasks.get(
            guild.id
        )

        if task and not task.done():

            task.cancel()

        self.queue_tasks.pop(
            guild.id,
            None
        )

        clear_queue(
            guild.id
        )

        voice = guild.voice_client

        if voice:

            try:

                if voice.is_playing() or voice.is_paused():

                    voice.stop()

            except Exception:

                pass

            try:

                await voice.disconnect(
                    force=True
                )

            except Exception as e:

                print(
                    "[PLAYER] "
                    f"Disconnect error: {e}"
                )

        self.current.pop(
            guild.id,
            None
        )

        self.paused.pop(
            guild.id,
            None
        )

        return True


    # =====================================================
    # CURRENT
    # =====================================================

    def get_current(
        self,
        guild: discord.Guild
    ):

        return self.current.get(
            guild.id
        )


    # =====================================================
    # QUEUE
    # =====================================================

    def get_guild_queue(
        self,
        guild: discord.Guild
    ):

        return get_queue(
            guild.id
        )


    # =====================================================
    # UNLOAD
    # =====================================================

    async def cog_unload(
        self
    ):

        for task in list(
            self.queue_tasks.values()
        ):

            if task and not task.done():

                task.cancel()

        self.queue_tasks.clear()


# =========================================================
# SETUP
# =========================================================

async def setup(bot):

    await bot.add_cog(
        QuranPlayer(bot)
    )
