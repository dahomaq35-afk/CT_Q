# =========================================================
# CT QURAN BOT
# main.py
# =========================================================

import os
import asyncio
from threading import Thread

import discord
from discord.ext import commands
from flask import Flask


# =========================================================
# SETTINGS
# =========================================================

TOKEN = os.getenv("DISCORD_TOKEN")

if not TOKEN:
    raise RuntimeError(
        "لم يتم العثور على DISCORD_TOKEN في Environment Variables."
    )


# =========================================================
# FLASK - RENDER HEALTH CHECK
# =========================================================

app = Flask(__name__)


@app.route("/")
def home():
    return "CT Quran Bot is Online!"


@app.route("/health")
def health():
    return {
        "status": "online",
        "bot": "CT Quran Bot"
    }


def run_flask():

    port = int(
        os.getenv(
            "PORT",
            "10000"
        )
    )

    app.run(
        host="0.0.0.0",
        port=port,
        debug=False,
        use_reloader=False
    )


def start_flask():

    thread = Thread(
        target=run_flask,
        daemon=True
    )

    thread.start()


# =========================================================
# DISCORD INTENTS
# =========================================================

intents = discord.Intents.default()

# مطلوب للأوامر والسيرفرات
intents.guilds = True

# مطلوب لمعرفة حالات الفويس
intents.voice_states = True

# غير مطلوب للبوت
# وتم تعطيله حتى لا يظهر خطأ:
# PrivilegedIntentsRequired
intents.members = False

# غير مطلوب حاليًا
intents.message_content = False


# =========================================================
# BOT
# =========================================================

class CTQuranBot(commands.Bot):

    def __init__(self):

        super().__init__(
            command_prefix="!",
            intents=intents,
            help_command=None
        )

    # =====================================================
    # SETUP HOOK
    # =====================================================

    async def setup_hook(self):

        print("[INFO] Loading CT Quran Bot systems...")

        # -------------------------------------------------
        # LOAD COGS
        # -------------------------------------------------

        cogs = [
            "cogs.player",
            "cogs.verification",
            "cogs.commands",
        ]

        for cog in cogs:

            try:

                await self.load_extension(cog)

                print(
                    f"[OK] Loaded: {cog}"
                )

            except Exception as e:

                print(
                    f"[ERROR] Failed to load {cog}: {e}"
                )

        # -------------------------------------------------
        # SYNC SLASH COMMANDS
        # -------------------------------------------------

        try:

            synced = await self.tree.sync()

            print(
                f"[OK] Synced {len(synced)} slash commands."
            )

        except Exception as e:

            print(
                f"[ERROR] Failed to sync commands: {e}"
            )


# =========================================================
# CREATE BOT
# =========================================================

bot = CTQuranBot()


# =========================================================
# EVENTS
# =========================================================

@bot.event
async def on_ready():

    print("")
    print("==========================================")
    print("        CT QURAN BOT IS ONLINE")
    print("==========================================")
    print(f"Bot       : {bot.user}")
    print(f"Bot ID    : {bot.user.id}")
    print(f"Servers   : {len(bot.guilds)}")
    print("Voice     : Enabled")
    print("Intents   : Normal")
    print("==========================================")
    print("")


# =========================================================
# DISCONNECT
# =========================================================

@bot.event
async def on_disconnect():

    print(
        "[INFO] Discord disconnected."
    )


# =========================================================
# RESUMED
# =========================================================

@bot.event
async def on_resumed():

    print(
        "[INFO] Discord connection resumed."
    )


# =========================================================
# ERROR HANDLER
# =========================================================

@bot.tree.error
async def on_app_command_error(
    interaction: discord.Interaction,
    error: discord.app_commands.AppCommandError
):

    print(
        f"[COMMAND ERROR] {error}"
    )

    try:

        message = (
            "حدث خطأ غير متوقع، "
            "حاول مرة أخرى."
        )

        if interaction.response.is_done():

            await interaction.followup.send(
                message,
                ephemeral=True
            )

        else:

            await interaction.response.send_message(
                message,
                ephemeral=True
            )

    except Exception as e:

        print(
            f"[ERROR HANDLER] {e}"
        )


# =========================================================
# START
# =========================================================

async def main():

    # -----------------------------------------------------
    # START FLASK
    # -----------------------------------------------------

    start_flask()

    print(
        "[INFO] Starting CT Quran Bot..."
    )

    # -----------------------------------------------------
    # START DISCORD BOT
    # -----------------------------------------------------

    try:

        await bot.start(
            TOKEN
        )

    except KeyboardInterrupt:

        print(
            "[INFO] Bot stopped."
        )

    except discord.LoginFailure:

        print(
            "[ERROR] DISCORD_TOKEN غير صحيح."
        )

    except Exception as e:

        print(
            f"[ERROR] Bot stopped بسبب خطأ: {e}"
        )

    finally:

        if not bot.is_closed():

            await bot.close()


# =========================================================
# RUN
# =========================================================

if __name__ == "__main__":

    try:

        asyncio.run(
            main()
        )

    except KeyboardInterrupt:

        print(
            "[INFO] Shutdown complete."
        )
