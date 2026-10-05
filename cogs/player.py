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
}

FFMPEG_OPTIONS = {
    "before_options": "-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5",
    "options": "-vn",
}


# =========================================================
# YOUTUBE DL
# =========================================================

ytdl = yt_dlp.YoutubeDL(YTDL_OPTIONS)


def get_audio(url: str):

    info = ytdl.extract_info(
        url,
        download=False
    )

    if "entries" in info:
        info = info["entries"][0]

    return {
        "url": info["url"],
        "title": info.get("title", "مقطع قرآن"),
        "webpage_url": info.get("webpage_url", url),
        "source": info.get("extractor_key", "Unknown"),
    }


# =========================================================
# PLAYER
# =========================================================

class QuranPlayer(commands.Cog):

    def __init__(self, bot):

        self.bot = bot

        self.current = {}
        self.locks = {}

    # =====================================================
    # LOCK
    # =====================================================

    def get_lock(self, guild_id):

        if guild_id not in self.locks:
            self.locks[guild_id] = asyncio.Lock()

        return self.locks[guild_id]

    # =====================================================
    # CONNECT
    # =====================================================

    async def connect_to_configured_voice(
        self,
        guild: discord.Guild
    ):

        channel_id = get_voice_channel(
            guild.id
        )

        if not channel_id:
            return None

        channel = guild.get_channel(
            channel_id
        )

        if not isinstance(
            channel,
            discord.VoiceChannel
        ):
            return None

        voice = guild.voice_client

        if voice and voice.is_connected():

            if voice.channel.id != channel.id:

                await voice.move_to(
                    channel
                )

            return voice

        return await channel.connect()

    # =====================================================
    # PLAY
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

        self.current[guild.id] = {
            "title": audio["title"],
            "url": item["url"],
            "user_id": item["user_id"],
        }

        source = discord.FFmpegPCMAudio(
            audio["url"],
            **FFMPEG_OPTIONS
        )

        finished = asyncio.Event()

        def after_playing(error):

            if error:
                print(
                    f"[PLAYER] Playback error: {error}"
                )

            self.bot.loop.call_soon_threadsafe(
                finished.set
            )

        voice.play(
            source,
            after=after_playing
        )

        await finished.wait()

        self.current.pop(
            guild.id,
            None
        )

        return True

    # =====================================================
    # QUEUE LOOP
    # =====================================================

    async def process_queue(
        self,
        guild: discord.Guild
    ):

        lock = self.get_lock(
            guild.id
        )

        if lock.locked():
            return

        async with lock:

            while True:

                item = get_next_queue_item(
                    guild.id
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

            voice = guild.voice_client

            if voice and voice.is_connected():

                await voice.disconnect()

    # =====================================================
    # ADD TO QUEUE
    # =====================================================

    async def add_song(
        self,
        guild: discord.Guild,
        user: discord.Member,
        url: str
    ):

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

        add_to_queue(
            guild_id=guild.id,
            user_id=user.id,
            username=str(user),
            url=url,
            title=audio["title"],
            source=audio["source"],
        )

        return True, audio["title"]

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

        return True

    # =====================================================
    # STOP
    # =====================================================

    async def stop(
        self,
        guild: discord.Guild
    ):

        voice = guild.voice_client

        clear_queue(
            guild.id
        )

        self.current.pop(
            guild.id,
            None
        )

        if not voice:
            return False

        if voice.is_playing() or voice.is_paused():
            voice.stop()

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

        voice.stop()

        return True

    # =====================================================
    # LEAVE
    # =====================================================

    async def leave(
        self,
        guild: discord.Guild
    ):

        voice = guild.voice_client

        clear_queue(
            guild.id
        )

        self.current.pop(
            guild.id,
            None
        )

        if not voice:
            return False

        await voice.disconnect()

        return True


# =========================================================
# SETUP
# =========================================================

async def setup(bot):

    await bot.add_cog(
        QuranPlayer(bot)
    )
