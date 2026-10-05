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
    port = int(os.getenv("PORT", 10000))
    app.run(
        host="0.0.0.0",
        port=port,
        debug=False,
        use_reloader=False
    )


def start_flask():
    thread = Thread(target=run_flask, daemon=True)
    thread.start()


# =========================================================
# DISCORD INTENTS
# =========================================================

intents = discord.Intents.default()

intents.guilds = True
intents.members = True
intents.voice_states = True
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

    async def setup_hook(self):

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
                print(f"[OK] Loaded: {cog}")

            except Exception as e:
                print(f"[ERROR] Failed to load {cog}: {e}")

        # -------------------------------------------------
        # SYNC SLASH COMMANDS
        # -------------------------------------------------

        try:
            synced = await self.tree.sync()
            print(f"[OK] Synced {len(synced)} slash commands.")

        except Exception as e:
            print(f"[ERROR] Failed to sync commands: {e}")


# =========================================================
# CREATE BOT
# =========================================================

bot = CTQuranBot()


# =========================================================
# EVENTS
# =========================================================

@bot.event
async def on_ready():

    print("==========================================")
    print("        CT QURAN BOT IS ONLINE")
    print("==========================================")
    print(f"Bot       : {bot.user}")
    print(f"Bot ID    : {bot.user.id}")
    print(f"Servers   : {len(bot.guilds)}")
    print("==========================================")


@bot.event
async def on_disconnect():
    print("[INFO] Discord disconnected.")


@bot.event
async def on_resumed():
    print("[INFO] Discord connection resumed.")


# =========================================================
# ERROR HANDLER
# =========================================================

@bot.tree.error
async def on_app_command_error(
    interaction: discord.Interaction,
    error: discord.app_commands.AppCommandError
):

    print(f"[COMMAND ERROR] {error}")

    try:

        if interaction.response.is_done():
            await interaction.followup.send(
                "حدث خطأ غير متوقع، حاول مرة أخرى.",
                ephemeral=True
            )
        else:
            await interaction.response.send_message(
                "حدث خطأ غير متوقع، حاول مرة أخرى.",
                ephemeral=True
            )

    except Exception as e:
        print(f"[ERROR HANDLER] {e}")


# =========================================================
# START
# =========================================================

async def main():

    start_flask()

    print("[INFO] Starting CT Quran Bot...")

    try:
        await bot.start(TOKEN)

    except KeyboardInterrupt:
        print("[INFO] Bot stopped.")

    finally:

        if not bot.is_closed():
            await bot.close()


# =========================================================
# RUN
# =========================================================

if __name__ == "__main__":

    try:
        asyncio.run(main())

    except KeyboardInterrupt:
        print("[INFO] Shutdown complete.")
