# =========================================================
# CT QURAN BOT
# commands.py
# =========================================================

import discord
from discord import app_commands
from discord.ext import commands

from database import (
    set_voice_channel,
    get_voice_channel,
    get_queue,
)

from cogs.verification import QuranVerification
from cogs.player import QuranPlayer


# =========================================================
# COMMANDS
# =========================================================

class QuranCommands(commands.Cog):

    def __init__(self, bot):

        self.bot = bot

    # =====================================================
    # GET SYSTEMS
    # =====================================================

    def get_player(self):

        return self.bot.get_cog(
            "QuranPlayer"
        )

    def get_verification(self):

        return self.bot.get_cog(
            "QuranVerification"
        )

    # =====================================================
    # تحديد الفويس
    # =====================================================

    @app_commands.command(
        name="تحدد_الفويس",
        description="تحديد روم الفويس الذي يشغل فيه البوت القرآن"
    )
    @app_commands.default_permissions(
        manage_guild=True
    )
    async def set_voice(
        self,
        interaction: discord.Interaction,
        channel: discord.VoiceChannel
    ):

        if not interaction.guild:

            await interaction.response.send_message(
                "هذا الأمر داخل السيرفر فقط.",
                ephemeral=True
            )

            return

        set_voice_channel(
            interaction.guild.id,
            channel.id
        )

        await interaction.response.send_message(
            f"تم تحديد روم الفويس: {channel.mention}",
            ephemeral=True
        )

    # =====================================================
    # شغل
    # =====================================================

    @app_commands.command(
        name="شغل",
        description="تشغيل مقطع قرآن من رابط"
    )
    async def play(
        self,
        interaction: discord.Interaction,
        الرابط: str
    ):

        if not interaction.guild:

            await interaction.response.send_message(
                "هذا الأمر داخل السيرفر فقط.",
                ephemeral=True
            )

            return

        await interaction.response.defer(
            ephemeral=True
        )

        # -------------------------------------------------
        # Check configured voice
        # -------------------------------------------------

        voice_channel_id = get_voice_channel(
            interaction.guild.id
        )

        if not voice_channel_id:

            await interaction.followup.send(
                "لم يتم تحديد روم الفويس بعد.",
                ephemeral=True
            )

            return

        # -------------------------------------------------
        # Verification
        # -------------------------------------------------

        verification = self.get_verification()

        if not verification:

            await interaction.followup.send(
                "نظام التحقق غير متوفر حاليًا.",
                ephemeral=True
            )

            return

        allowed, result = await verification.verify_for_user(
            interaction.guild,
            interaction.user,
            الرابط
        )

        if not allowed:

            await interaction.followup.send(
                "❌ تم رفض المقطع لأنه لم يجتز التحقق من كونه قرآنًا.\n"
                "تم إرسال التنبيه لك في الخاص.",
                ephemeral=True
            )

            return

        # -------------------------------------------------
        # Player
        # -------------------------------------------------

        player = self.get_player()

        if not player:

            await interaction.followup.send(
                "نظام التشغيل غير متوفر حاليًا.",
                ephemeral=True
            )

            return

        success, title = await player.add_song(
            interaction.guild,
            interaction.user,
            الرابط
        )

        if not success:

            await interaction.followup.send(
                "تعذر استخراج الصوت من الرابط.",
                ephemeral=True
            )

            return

        # -------------------------------------------------
        # Start queue
        # -------------------------------------------------

        await player.process_queue(
            interaction.guild
        )

        await interaction.followup.send(
            f"✅ تمت إضافة **{title}** إلى قائمة التشغيل.",
            ephemeral=True
        )

    # =====================================================
    # إيقاف مؤقت
    # =====================================================

    @app_commands.command(
        name="توقف",
        description="إيقاف المقطع مؤقتًا"
    )
    async def pause(
        self,
        interaction: discord.Interaction
    ):

        if not interaction.guild:
            return

        player = self.get_player()

        if not player:

            await interaction.response.send_message(
                "نظام التشغيل غير متوفر.",
                ephemeral=True
            )

            return

        success = await player.pause(
            interaction.guild
        )

        if success:

            await interaction.response.send_message(
                "⏸️ تم إيقاف القرآن مؤقتًا.",
                ephemeral=True
            )

        else:

            await interaction.response.send_message(
                "لا يوجد مقطع يعمل حاليًا.",
                ephemeral=True
            )

    # =====================================================
    # استئناف
    # =====================================================

    @app_commands.command(
        name="استئناف",
        description="استئناف المقطع المتوقف"
    )
    async def resume(
        self,
        interaction: discord.Interaction
    ):

        if not interaction.guild:
            return

        player = self.get_player()

        if not player:

            await interaction.response.send_message(
                "نظام التشغيل غير متوفر.",
                ephemeral=True
            )

            return

        success = await player.resume(
            interaction.guild
        )

        if success:

            await interaction.response.send_message(
                "▶️ تم استئناف التشغيل.",
                ephemeral=True
            )

        else:

            await interaction.response.send_message(
                "لا يوجد مقطع متوقف مؤقتًا.",
                ephemeral=True
            )

    # =====================================================
    # تخطي
    # =====================================================

    @app_commands.command(
        name="تخطي",
        description="تخطي المقطع الحالي"
    )
    async def skip(
        self,
        interaction: discord.Interaction
    ):

        if not interaction.guild:
            return

        player = self.get_player()

        if not player:

            await interaction.response.send_message(
                "نظام التشغيل غير متوفر.",
                ephemeral=True
            )

            return

        success = await player.skip(
            interaction.guild
        )

        if success:

            await interaction.response.send_message(
                "⏭️ تم تخطي المقطع.",
                ephemeral=True
            )

        else:

            await interaction.response.send_message(
                "لا يوجد مقطع يعمل حاليًا.",
                ephemeral=True
            )

    # =====================================================
    # إيقاف
    # =====================================================

    @app_commands.command(
        name="ايقاف",
        description="إيقاف التشغيل ومسح الطابور"
    )
    async def stop(
        self,
        interaction: discord.Interaction
    ):

        if not interaction.guild:
            return

        player = self.get_player()

        if not player:

            await interaction.response.send_message(
                "نظام التشغيل غير متوفر.",
                ephemeral=True
            )

            return

        await player.stop(
            interaction.guild
        )

        await interaction.response.send_message(
            "⏹️ تم إيقاف التشغيل ومسح قائمة الانتظار.",
            ephemeral=True
        )

    # =====================================================
    # الطابور
    # =====================================================

    @app_commands.command(
        name="طابور",
        description="عرض المقاطع الموجودة في قائمة الانتظار"
    )
    async def queue(
        self,
        interaction: discord.Interaction
    ):

        if not interaction.guild:
            return

        rows = get_queue(
            interaction.guild.id
        )

        if not rows:

            await interaction.response.send_message(
                "قائمة الانتظار فارغة.",
                ephemeral=True
            )

            return

        lines = []

        for index, row in enumerate(
            rows,
            start=1
        ):

            title = row["title"] or "مقطع قرآن"

            lines.append(
                f"**{index}.** {title}\n"
                f"بواسطة: <@{row['user_id']}>"
            )

        text = "\n\n".join(
            lines[:20]
        )

        if len(rows) > 20:

            text += (
                f"\n\nويوجد {len(rows) - 20} مقطع إضافي."
            )

        embed = discord.Embed(
            title="📖 قائمة القرآن",
            description=text
        )

        await interaction.response.send_message(
            embed=embed,
            ephemeral=True
        )

    # =====================================================
    # مغادرة
    # =====================================================

    @app_commands.command(
        name="مغادرة",
        description="إخراج البوت من روم الفويس"
    )
    async def leave(
        self,
        interaction: discord.Interaction
    ):

        if not interaction.guild:
            return

        player = self.get_player()

        if not player:

            await interaction.response.send_message(
                "نظام التشغيل غير متوفر.",
                ephemeral=True
            )

            return

        success = await player.leave(
            interaction.guild
        )

        if success:

            await interaction.response.send_message(
                "👋 تم إخراج البوت من روم الفويس.",
                ephemeral=True
            )

        else:

            await interaction.response.send_message(
                "البوت غير موجود في روم فويس.",
                ephemeral=True
            )


# =========================================================
# SETUP
# =========================================================

async def setup(bot):

    await bot.add_cog(
        QuranCommands(bot)
    )
