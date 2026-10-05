# =========================================================
# CT QURAN BOT
# verification.py
# =========================================================

import re
import asyncio
from urllib.parse import urlparse

import discord
from discord.ext import commands

from database import (
    add_play_history,
    add_rejected_attempt,
)


# =========================================================
# SETTINGS
# =========================================================

QURAN_KEYWORDS = [
    "quran",
    "qur'an",
    "قرآن",
    "القرآن",
    "سورة",
    "سوره",
    "تلاوة",
    "تلاوه",
    "تلاوات",
    "تجويد",
    "مرتل",
    "مرتلة",
    "حفص",
    "ورش",
    "آية",
    "اية",
    "آيات",
    "عبدالباسط",
    "عبد الباسط",
    "السديس",
    "الشريم",
    "الدوسري",
    "ياسر الدوسري",
    "ماهر المعيقلي",
    "ماهر المعيقلي",
    "المنشاوي",
    "المنشاوي",
    "العفاسي",
    "سعد الغامدي",
    "ناصر القطامي",
    "فارس عباد",
    "إدريس أبكر",
    "محمد اللحيدان",
]


# =========================================================
# URL CHECK
# =========================================================

SUPPORTED_DOMAINS = {
    "youtube.com",
    "www.youtube.com",
    "youtu.be",
    "m.youtube.com",

    "tiktok.com",
    "www.tiktok.com",
    "vm.tiktok.com",

    "instagram.com",
    "www.instagram.com",

    "facebook.com",
    "www.facebook.com",
}


def normalize_text(text: str) -> str:

    if not text:
        return ""

    text = text.lower().strip()

    replacements = {
        "أ": "ا",
        "إ": "ا",
        "آ": "ا",
        "ة": "ه",
        "ى": "ي",
    }

    for old, new in replacements.items():
        text = text.replace(old, new)

    text = re.sub(
        r"[\u064B-\u065F\u0670]",
        "",
        text
    )

    return text


def get_domain(url: str):

    try:

        parsed = urlparse(url)

        domain = parsed.netloc.lower()

        if domain.startswith("www."):
            domain = domain[4:]

        return domain

    except Exception:
        return ""


def is_supported_url(url: str):

    domain = get_domain(url)

    if not domain:
        return False

    for supported in SUPPORTED_DOMAINS:

        supported_clean = supported.replace(
            "www.",
            ""
        )

        if domain == supported_clean:
            return True

        if domain.endswith(
            "." + supported_clean
        ):
            return True

    return False


# =========================================================
# KEYWORD CHECK
# =========================================================

def keyword_score(
    title: str,
    description: str
):

    text = normalize_text(
        f"{title} {description}"
    )

    score = 0
    matches = []

    for keyword in QURAN_KEYWORDS:

        normalized_keyword = normalize_text(
            keyword
        )

        if normalized_keyword in text:

            score += 1
            matches.append(keyword)

    return score, matches


# =========================================================
# VERIFICATION RESULT
# =========================================================

class VerificationResult:

    def __init__(
        self,
        allowed: bool,
        reason: str,
        score: int = 0
    ):

        self.allowed = allowed
        self.reason = reason
        self.score = score


# =========================================================
# VERIFICATION
# =========================================================

class QuranVerification(commands.Cog):

    def __init__(self, bot):

        self.bot = bot

    # =====================================================
    # VERIFY
    # =====================================================

    async def verify_url(
        self,
        url: str
    ):

        if not url:
            return VerificationResult(
                False,
                "الرابط غير موجود."
            )

        if not is_supported_url(url):

            return VerificationResult(
                False,
                "المنصة غير مدعومة."
            )

        # -------------------------------------------------
        # استخراج معلومات الرابط
        # -------------------------------------------------

        try:

            import yt_dlp

            options = {
                "quiet": True,
                "no_warnings": True,
                "skip_download": True,
                "noplaylist": True,
            }

            def extract():

                with yt_dlp.YoutubeDL(options) as ytdl:

                    return ytdl.extract_info(
                        url,
                        download=False
                    )

            info = await asyncio.to_thread(
                extract
            )

        except Exception as e:

            print(
                f"[VERIFICATION] Extraction error: {e}"
            )

            return VerificationResult(
                False,
                "تعذر قراءة المقطع."
            )

        if not info:

            return VerificationResult(
                False,
                "لم يتم العثور على معلومات المقطع."
            )

        if "entries" in info:

            entries = info.get(
                "entries"
            )

            if not entries:

                return VerificationResult(
                    False,
                    "لم يتم العثور على المقطع."
                )

            info = entries[0]

        # -------------------------------------------------
        # المعلومات
        # -------------------------------------------------

        title = info.get(
            "title",
            ""
        )

        description = info.get(
            "description",
            ""
        )

        uploader = info.get(
            "uploader",
            ""
        )

        channel = info.get(
            "channel",
            ""
        )

        combined_text = (
            f"{title} "
            f"{description} "
            f"{uploader} "
            f"{channel}"
        )

        score, matches = keyword_score(
            title,
            combined_text
        )

        # -------------------------------------------------
        # Quran indicators
        # -------------------------------------------------

        normalized = normalize_text(
            combined_text
        )

        strong_indicators = [
            "قران",
            "القران",
            "سوره",
            "تلاوه",
            "تجويد",
            "حفص",
            "ورش",
            "quran",
            "qur'an",
        ]

        strong_match = any(
            indicator in normalized
            for indicator in strong_indicators
        )

        # -------------------------------------------------
        # القرار
        # -------------------------------------------------

        if strong_match and score >= 1:

            return VerificationResult(
                True,
                "تم التحقق من أن المقطع قرآن.",
                score
            )

        if score >= 2:

            return VerificationResult(
                True,
                "تم التحقق من محتوى المقطع.",
                score
            )

        return VerificationResult(
            False,
            "المقطع لم يجتز التحقق من كونه قرآنًا.",
            score
        )

    # =====================================================
    # REJECT MESSAGE
    # =====================================================

    async def send_rejection_dm(
        self,
        user: discord.Member,
        reason: str
    ):

        message = (
            f"{user.mention}\n\n"
            "يا أخوي، **الأغاني لا تجوز، فتُب إلى الله واتركها، "
            "فباب التوبة مفتوح.**\n\n"
            "﴿إِنَّ اللَّهَ يَغْفِرُ الذُّنُوبَ جَمِيعًا﴾ 🤍\n\n"
            "اللهم اهدي قلوبنا وقلوبكم، ووفقنا لما تحب وترضى."
        )

        try:

            await user.send(
                message
            )

            return True

        except discord.Forbidden:

            print(
                f"[VERIFICATION] Cannot DM {user}"
            )

            return False

        except Exception as e:

            print(
                f"[VERIFICATION] DM error: {e}"
            )

            return False

    # =====================================================
    # HANDLE VERIFICATION
    # =====================================================

    async def verify_for_user(
        self,
        guild: discord.Guild,
        user: discord.Member,
        url: str
    ):

        result = await self.verify_url(
            url
        )

        if result.allowed:

            return True, result

        # -------------------------------------------------
        # Save rejection
        # -------------------------------------------------

        add_rejected_attempt(
            guild_id=guild.id,
            user_id=user.id,
            username=str(user),
            url=url,
            reason=result.reason
        )

        add_play_history(
            guild_id=guild.id,
            user_id=user.id,
            username=str(user),
            url=url,
            title="",
            source="",
            verified=False,
            rejected=True
        )

        # -------------------------------------------------
        # DM
        # -------------------------------------------------

        await self.send_rejection_dm(
            user,
            result.reason
        )

        return False, result


# =========================================================
# SETUP
# =========================================================

async def setup(bot):

    await bot.add_cog(
        QuranVerification(bot)
    )
