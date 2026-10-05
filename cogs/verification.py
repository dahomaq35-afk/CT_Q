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

SUPPORTED_DOMAINS = {
    "youtube.com",
    "youtu.be",
    "m.youtube.com",

    "tiktok.com",
    "vm.tiktok.com",

    "instagram.com",

    "facebook.com",
}


# =========================================================
# QURAN KEYWORDS
# =========================================================

QURAN_KEYWORDS = [

    # English
    "quran",
    "qur'an",
    "quraan",
    "koran",
    "holy quran",
    "surah",
    "surah al",
    "surat",
    "recitation",
    "quran recitation",
    "tilawah",
    "tilawat",
    "tajweed",
    "mushaf",

    # Arabic
    "قرآن",
    "القرآن",
    "قران",
    "القران",
    "قرآن كريم",
    "القرآن الكريم",
    "قران كريم",

    "سورة",
    "سوره",
    "سور",
    "سور القرآن",

    "تلاوة",
    "تلاوه",
    "تلاوات",
    "تلاوة القرآن",
    "تلاوة قرآنية",
    "تلاوه قرانيه",

    "تجويد",
    "ترتيل",
    "مرتّل",
    "مرتلة",
    "مرتل",
    "مصحف",

    "حفص",
    "ورش",
    "قالون",
    "الدوري",

    "آية",
    "اية",
    "آيات",
    "ايات",
]


# =========================================================
# RECITERS
# =========================================================

RECITERS = [

    # Arabic
    "عبد الباسط",
    "عبدالباسط",
    "عبد الباسط عبد الصمد",
    "عبدالباسط عبدالصمد",

    "السديس",
    "عبد الرحمن السديس",
    "عبدالرحمن السديس",

    "الشريم",
    "سعود الشريم",

    "الدوسري",
    "ياسر الدوسري",

    "ماهر المعيقلي",
    "ماهر المعيقلي",

    "المنشاوي",
    "محمد صديق المنشاوي",

    "العفاسي",
    "مشاري العفاسي",

    "سعد الغامدي",
    "القطامي",
    "ناصر القطامي",

    "فارس عباد",

    "إدريس أبكر",
    "ادريس ابكر",

    "محمد اللحيدان",

    "خالد الجليل",

    "بندر بليلة",
    "بندر بن عبدالعزيز بليلة",

    "علي جابر",

    "أحمد العجمي",

    "هاني الرفاعي",

    "صلاح بو خاطر",

    "ناصر القطامي",

    "عبدالله بصفر",

    "عبدالله خياط",

    "محمد أيوب",
    "محمد ايوب",

    "عمر القزابري",

    "محمود خليل الحصري",
    "الحصري",

    "مصطفى إسماعيل",
    "مصطفي اسماعيل",

    "محمد رفعت",

    "الطبلاوي",

    # English transliterations
    "abdul basit",
    "abdulbasit",
    "abdul baset",

    "al sudais",
    "alsudais",
    "sudais",

    "al shuraim",
    "shuraim",

    "yasser al dosari",
    "yasser al-dosari",
    "yasser dosari",

    "maher al muaiqly",
    "maher al-muaiqly",
    "maher muaiqly",

    "mishary alafasy",
    "mishary al afasy",
    "alafasy",

    "al minshawi",
    "minshawi",

    "saad al ghamdi",
    "saad al-ghamdi",

    "nasser al qatami",
    "nasser al-qatami",

    "fahad al kandari",
]


# =========================================================
# SURAHS
# =========================================================

SURAHS = [

    "الفاتحة",
    "البقرة",
    "آل عمران",
    "ال عمران",
    "النساء",
    "المائدة",
    "الأنعام",
    "الانعام",
    "الأعراف",
    "الاعراف",
    "الأنفال",
    "الانفال",
    "التوبة",
    "يونس",
    "هود",
    "يوسف",
    "الرعد",
    "إبراهيم",
    "ابراهيم",
    "الحجر",
    "النحل",
    "الإسراء",
    "الاسراء",
    "الكهف",
    "مريم",
    "طه",
    "الأنبياء",
    "الانبياء",
    "الحج",
    "المؤمنون",
    "النور",
    "الفرقان",
    "الشعراء",
    "النمل",
    "القصص",
    "العنكبوت",
    "الروم",
    "لقمان",
    "السجدة",
    "الأحزاب",
    "الاحزاب",
    "سبأ",
    "فاطر",
    "يس",
    "الصافات",
    "ص",
    "الزمر",
    "غافر",
    "فصلت",
    "الشورى",
    "الزخرف",
    "الدخان",
    "الجاثية",
    "الأحقاف",
    "الاحقاف",
    "محمد",
    "الفتح",
    "الحجرات",
    "ق",
    "الذاريات",
    "الطور",
    "النجم",
    "القمر",
    "الرحمن",
    "الواقعة",
    "الحديد",
    "المجادلة",
    "الحشر",
    "الممتحنة",
    "الصف",
    "الجمعة",
    "المنافقون",
    "التغابن",
    "الطلاق",
    "التحريم",
    "الملك",
    "القلم",
    "الحاقة",
    "المعارج",
    "نوح",
    "الجن",
    "المزمل",
    "المدثر",
    "القيامة",
    "الإنسان",
    "الانسان",
    "المرسلات",
    "النبأ",
    "النازعات",
    "عبس",
    "التكوير",
    "الانفطار",
    "المطففين",
    "الانشقاق",
    "البروج",
    "الطارق",
    "الأعلى",
    "الاعلى",
    "الغاشية",
    "الفجر",
    "البلد",
    "الشمس",
    "الليل",
    "الضحى",
    "الشرح",
    "التين",
    "العلق",
    "القدر",
    "البينة",
    "الزلزلة",
    "العاديات",
    "القارعة",
    "التكاثر",
    "العصر",
    "الهمزة",
    "الفيل",
    "قريش",
    "الماعون",
    "الكوثر",
    "الكافرون",
    "النصر",
    "المسد",
    "الإخلاص",
    "الاخلاص",
    "الفلق",
    "الناس",
]


# =========================================================
# NON-QURAN / MUSIC INDICATORS
# =========================================================

MUSIC_KEYWORDS = [

    # Arabic
    "اغنية",
    "أغنية",
    "اغاني",
    "أغاني",
    "اغنيه",
    "أغنيه",
    "موسيقى",
    "موسيقي",
    "ميوزك",
    "كليب",
    "فيديو كليب",
    "ريمكس",
    "ريميكس",
    "حفلة",
    "حفله",
    "حفلات",
    "مطرب",
    "مطربة",
    "مغني",
    "مغنية",
    "اغنيه جديده",
    "أغنية جديدة",
    "شيلة",
    "شيله",

    # English
    "song",
    "songs",
    "music",
    "musical",
    "remix",
    "nightcore",
    "slowed",
    "reverb",
    "lyrics",
    "lyric video",
    "official music",
    "official audio",
    "music video",
    "concert",
    "singer",
]


# =========================================================
# NORMALIZE TEXT
# =========================================================

def normalize_text(
    text: str
):

    if not text:
        return ""

    text = str(
        text
    ).lower().strip()

    replacements = {
        "أ": "ا",
        "إ": "ا",
        "آ": "ا",
        "ٱ": "ا",
        "ة": "ه",
        "ى": "ي",
        "ؤ": "و",
        "ئ": "ي",
    }

    for old, new in replacements.items():

        text = text.replace(
            old,
            new
        )

    # إزالة التشكيل
    text = re.sub(
        r"[\u064B-\u065F\u0670]",
        "",
        text
    )

    # إزالة بعض الرموز
    text = re.sub(
        r"[_\-|/\\.,!?()[\]{}:;\"'`~@#$%^&*+=<>]",
        " ",
        text
    )

    # توحيد المسافات
    text = re.sub(
        r"\s+",
        " ",
        text
    )

    return text.strip()


# =========================================================
# DOMAIN
# =========================================================

def get_domain(
    url: str
):

    try:

        parsed = urlparse(
            url
        )

        domain = parsed.netloc.lower()

        if domain.startswith(
            "www."
        ):

            domain = domain[4:]

        return domain

    except Exception:

        return ""


def is_supported_url(
    url: str
):

    domain = get_domain(
        url
    )

    if not domain:

        return False

    for supported in SUPPORTED_DOMAINS:

        supported_clean = (
            supported
            .replace(
                "www.",
                ""
            )
            .lower()
        )

        if domain == supported_clean:

            return True

        if domain.endswith(
            "." + supported_clean
        ):

            return True

    return False


# =========================================================
# TEXT MATCHING
# =========================================================

def find_matches(
    text: str,
    keywords: list
):

    normalized = normalize_text(
        text
    )

    matches = []

    for keyword in keywords:

        normalized_keyword = (
            normalize_text(
                keyword
            )
        )

        if not normalized_keyword:

            continue

        if normalized_keyword in normalized:

            if keyword not in matches:

                matches.append(
                    keyword
                )

    return matches


# =========================================================
# QURAN SCORE
# =========================================================

def calculate_quran_score(
    title: str,
    description: str,
    uploader: str,
    channel: str
):

    title_text = normalize_text(
        title
    )

    description_text = normalize_text(
        description
    )

    uploader_text = normalize_text(
        uploader
    )

    channel_text = normalize_text(
        channel
    )

    all_text = (
        f"{title_text} "
        f"{description_text} "
        f"{uploader_text} "
        f"{channel_text}"
    )

    score = 0

    matches = []

    # -----------------------------------------------------
    # Quran keywords
    # -----------------------------------------------------

    for keyword in QURAN_KEYWORDS:

        normalized_keyword = normalize_text(
            keyword
        )

        if normalized_keyword in all_text:

            if keyword not in matches:

                matches.append(
                    keyword
                )

            # العنوان أقوى من الوصف
            if normalized_keyword in title_text:

                score += 3

            # اسم القارئ / القناة
            elif (
                normalized_keyword in uploader_text
                or normalized_keyword in channel_text
            ):

                score += 3

            else:

                score += 1

    # -----------------------------------------------------
    # Reciter
    # -----------------------------------------------------

    reciter_matches = find_matches(
        f"{title} {description} {uploader} {channel}",
        RECITERS
    )

    if reciter_matches:

        score += 4

        for match in reciter_matches:

            if match not in matches:

                matches.append(
                    match
                )

    # -----------------------------------------------------
    # Surah
    # -----------------------------------------------------

    surah_matches = find_matches(
        f"{title} {description}",
        SURAHS
    )

    if surah_matches:

        score += 3

        for match in surah_matches:

            if match not in matches:

                matches.append(
                    match
                )

    # -----------------------------------------------------
    # Strong Quran indicators
    # -----------------------------------------------------

    strong_indicators = [
        "quran",
        "qur an",
        "quraan",
        "koran",
        "قران",
        "القران",
        "سوره",
        "تلاوه",
        "تجويد",
        "ترتيل",
        "مصحف",
        "حفص",
        "ورش",
    ]

    strong_matches = []

    for indicator in strong_indicators:

        if normalize_text(
            indicator
        ) in all_text:

            strong_matches.append(
                indicator
            )

    if strong_matches:

        score += 4

    return {
        "score": score,
        "matches": matches,
        "reciters": reciter_matches,
        "surahs": surah_matches,
        "strong": strong_matches,
    }


# =========================================================
# MUSIC SCORE
# =========================================================

def calculate_music_score(
    title: str,
    description: str,
    uploader: str,
    channel: str
):

    text = (
        f"{title} "
        f"{description} "
        f"{uploader} "
        f"{channel}"
    )

    matches = find_matches(
        text,
        MUSIC_KEYWORDS
    )

    score = 0

    normalized_title = normalize_text(
        title
    )

    normalized_all = normalize_text(
        text
    )

    for keyword in matches:

        normalized_keyword = normalize_text(
            keyword
        )

        if normalized_keyword in normalized_title:

            score += 4

        elif normalized_keyword in normalized_all:

            score += 2

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
# VERIFICATION COG
# =========================================================

class QuranVerification(
    commands.Cog
):

    def __init__(
        self,
        bot
    ):

        self.bot = bot

    # =====================================================
    # VERIFY URL
    # =====================================================

    async def verify_url(
        self,
        url: str
    ):

        # -------------------------------------------------
        # URL
        # -------------------------------------------------

        if not url:

            return VerificationResult(
                False,
                "الرابط غير موجود."
            )

        if not is_supported_url(
            url
        ):

            return VerificationResult(
                False,
                "المنصة غير مدعومة."
            )

        # -------------------------------------------------
        # YT-DLP
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

                with yt_dlp.YoutubeDL(
                    options
                ) as ytdl:

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

        # -------------------------------------------------
        # INFO
        # -------------------------------------------------

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

        title = info.get(
            "title",
            ""
        ) or ""

        description = info.get(
            "description",
            ""
        ) or ""

        uploader = info.get(
            "uploader",
            ""
        ) or ""

        channel = info.get(
            "channel",
            ""
        ) or ""

        # -------------------------------------------------
        # SCORES
        # -------------------------------------------------

        quran = calculate_quran_score(
            title=title,
            description=description,
            uploader=uploader,
            channel=channel
        )

        music_score, music_matches = (
            calculate_music_score(
                title=title,
                description=description,
                uploader=uploader,
                channel=channel
            )
        )

        quran_score = quran["score"]

        # -------------------------------------------------
        # LOG
        # -------------------------------------------------

        print(
            "------------------------------------------"
        )

        print(
            f"[VERIFICATION] Title: {title}"
        )

        print(
            f"[VERIFICATION] Uploader: {uploader}"
        )

        print(
            f"[VERIFICATION] Channel: {channel}"
        )

        print(
            f"[VERIFICATION] Quran Score: {quran_score}"
        )

        print(
            f"[VERIFICATION] Music Score: {music_score}"
        )

        print(
            f"[VERIFICATION] Quran Matches: "
            f"{quran['matches']}"
        )

        print(
            f"[VERIFICATION] Music Matches: "
            f"{music_matches}"
        )

        print(
            "------------------------------------------"
        )

        # =================================================
        # MUSIC DETECTION
        # =================================================

        # إذا كان فيه مؤشر موسيقى قوي جدًا
        # نرفضه حتى لو كان فيه كلمة قرآن بشكل عابر.

        if music_score >= 6:

            return VerificationResult(
                False,
                "تم اكتشاف مؤشرات على أن المقطع أغنية أو موسيقى.",
                quran_score
            )

        # =================================================
        # QURAN ACCEPTANCE
        # =================================================

        # -------------------------------------------------
        # قارئ معروف
        # -------------------------------------------------

        if quran["reciters"]:

            return VerificationResult(
                True,
                "تم التعرف على اسم قارئ قرآن.",
                quran_score
            )

        # -------------------------------------------------
        # اسم سورة + مؤشر قرآن
        # -------------------------------------------------

        if (
            quran["surahs"]
            and quran["strong"]
        ):

            return VerificationResult(
                True,
                "تم التعرف على السورة ومؤشر قرآني.",
                quran_score
            )

        # -------------------------------------------------
        # مؤشرات قرآن قوية
        # -------------------------------------------------

        if quran["strong"]:

            return VerificationResult(
                True,
                "تم التعرف على مؤشرات قوية للمحتوى القرآني.",
                quran_score
            )

        # -------------------------------------------------
        # أكثر من مؤشر قرآن
        # -------------------------------------------------

        if quran_score >= 5:

            return VerificationResult(
                True,
                "تم التحقق من أن المقطع قرآني.",
                quran_score
            )

        # -------------------------------------------------
        # FINAL REJECTION
        # -------------------------------------------------

        return VerificationResult(
            False,
            "المقطع لم يحتوي على مؤشرات كافية تثبت أنه قرآن.",
            quran_score
        )

    # =====================================================
    # REJECTION DM
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
    # VERIFY FOR USER
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

        # -------------------------------------------------
        # APPROVED
        # -------------------------------------------------

        if result.allowed:

            # تسجيل التشغيل المقبول
            add_play_history(
                guild_id=guild.id,
                user_id=user.id,
                username=str(user),
                url=url,
                title="",
                source="",
                verified=True,
                rejected=False
            )

            return True, result

        # -------------------------------------------------
        # REJECTED
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
        # SEND DM
        # -------------------------------------------------

        await self.send_rejection_dm(
            user,
            result.reason
        )

        return False, result


# =========================================================
# SETUP
# =========================================================

async def setup(
    bot
):

    await bot.add_cog(
        QuranVerification(bot)
    )
