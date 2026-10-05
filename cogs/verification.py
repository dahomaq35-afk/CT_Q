# =========================================================
# CT QURAN BOT
# cogs/verification.py
#
# AUDIO-BASED QURAN VERIFICATION
# NO OPENAI
# =========================================================

import os
import re
import json
import math
import asyncio
import tempfile
import shutil
from urllib.request import Request, urlopen
from urllib.parse import urlparse

import discord
import yt_dlp
import imageio_ffmpeg

from discord.ext import commands
from faster_whisper import WhisperModel

from database import (
    add_play_history,
    add_rejected_attempt,
)


# =========================================================
# SETTINGS
# =========================================================

QURAN_API_URL = (
    "https://api.alquran.cloud/v1/quran/quran-simple"
)

# Whisper model
#
# small = أخف وأسرع
# medium = أدق لكنه أثقل
# large-v3 = أدق وأثقل جدًا
#
# على Render نبدأ بـ small
WHISPER_MODEL = os.getenv(
    "WHISPER_MODEL",
    "small"
)

# CPU على Render
WHISPER_DEVICE = os.getenv(
    "WHISPER_DEVICE",
    "cpu"
)

# int8 مناسب للـ CPU
WHISPER_COMPUTE_TYPE = os.getenv(
    "WHISPER_COMPUTE_TYPE",
    "int8"
)

# طول العينة
SAMPLE_DURATION = 30

# بداية العينة
SAMPLE_START = 5

# أقل عدد كلمات للتفريغ
MIN_WORDS = 5

# نسبة التطابق المطلوبة
MIN_QURAN_SCORE = 0.45


# =========================================================
# SUPPORTED PLATFORMS
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
# GLOBAL DATA
# =========================================================

QURAN_AYAHS = []

QURAN_READY = False

WHISPER_MODEL_INSTANCE = None

MODEL_LOCK = asyncio.Lock()

QURAN_LOCK = asyncio.Lock()


# =========================================================
# FFMPEG
# =========================================================

def get_ffmpeg_path():

    try:

        return imageio_ffmpeg.get_ffmpeg_exe()

    except Exception as e:

        print(
            f"[VERIFICATION] FFmpeg error: {e}"
        )

        return None


FFMPEG_PATH = get_ffmpeg_path()


# =========================================================
# ARABIC NORMALIZATION
# =========================================================

def normalize_arabic(
    text: str
):

    if not text:
        return ""

    text = str(
        text
    ).lower()

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

    # إزالة علامات الوقف
    text = re.sub(
        r"[\u06D6-\u06ED]",
        "",
        text
    )

    # إزالة الرموز
    text = re.sub(
        r"[^\w\s\u0600-\u06FF]",
        " ",
        text
    )

    # إزالة الأرقام
    text = re.sub(
        r"\d+",
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
# WORDS
# =========================================================

def get_words(
    text: str
):

    normalized = normalize_arabic(
        text
    )

    if not normalized:
        return []

    return normalized.split()


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

        clean = supported.replace(
            "www.",
            ""
        )

        if domain == clean:
            return True

        if domain.endswith(
            "." + clean
        ):
            return True

    return False


# =========================================================
# LOAD QURAN
# =========================================================

def download_quran():

    request = Request(
        QURAN_API_URL,
        headers={
            "User-Agent": "CT-Quran-Bot/1.0"
        }
    )

    with urlopen(
        request,
        timeout=60
    ) as response:

        data = json.loads(
            response.read().decode(
                "utf-8"
            )
        )

    if data.get("code") != 200:

        raise RuntimeError(
            "Quran API returned an invalid response."
        )

    ayahs = (
        data
        .get("data", {})
        .get("ayahs", [])
    )

    if not ayahs:

        raise RuntimeError(
            "No Quran ayahs were returned."
        )

    result = []

    for ayah in ayahs:

        text = ayah.get(
            "text",
            ""
        )

        normalized = normalize_arabic(
            text
        )

        if normalized:

            result.append(
                normalized
            )

    return result


async def ensure_quran_loaded():

    global QURAN_AYAHS
    global QURAN_READY

    if QURAN_READY:
        return True

    async with QURAN_LOCK:

        if QURAN_READY:
            return True

        try:

            print(
                "[VERIFICATION] Loading Quran text..."
            )

            quran = await asyncio.to_thread(
                download_quran
            )

            if not quran:

                return False

            QURAN_AYAHS = quran

            QURAN_READY = True

            print(
                f"[VERIFICATION] Loaded "
                f"{len(QURAN_AYAHS)} ayahs."
            )

            return True

        except Exception as e:

            print(
                f"[VERIFICATION] Quran loading failed: {e}"
            )

            return False


# =========================================================
# WHISPER
# =========================================================

def load_whisper_model():

    global WHISPER_MODEL_INSTANCE

    if WHISPER_MODEL_INSTANCE is not None:

        return WHISPER_MODEL_INSTANCE

    print(
        "[VERIFICATION] Loading Whisper model..."
    )

    print(
        f"[VERIFICATION] Model: {WHISPER_MODEL}"
    )

    print(
        f"[VERIFICATION] Device: {WHISPER_DEVICE}"
    )

    print(
        f"[VERIFICATION] Compute: "
        f"{WHISPER_COMPUTE_TYPE}"
    )

    WHISPER_MODEL_INSTANCE = WhisperModel(
        WHISPER_MODEL,
        device=WHISPER_DEVICE,
        compute_type=WHISPER_COMPUTE_TYPE,
    )

    print(
        "[VERIFICATION] Whisper model loaded."
    )

    return WHISPER_MODEL_INSTANCE


async def ensure_whisper_loaded():

    global WHISPER_MODEL_INSTANCE

    if WHISPER_MODEL_INSTANCE is not None:

        return WHISPER_MODEL_INSTANCE

    async with MODEL_LOCK:

        if WHISPER_MODEL_INSTANCE is not None:

            return WHISPER_MODEL_INSTANCE

        try:

            model = await asyncio.to_thread(
                load_whisper_model
            )

            return model

        except Exception as e:

            print(
                f"[VERIFICATION] Whisper load failed: {e}"
            )

            return None


# =========================================================
# EXTRACT VIDEO INFO
# =========================================================

def extract_info(
    url: str
):

    options = {
        "quiet": True,
        "no_warnings": True,
        "noplaylist": True,
        "skip_download": True,
    }

    with yt_dlp.YoutubeDL(
        options
    ) as ytdl:

        return ytdl.extract_info(
            url,
            download=False
        )


# =========================================================
# DOWNLOAD AUDIO SAMPLE
# =========================================================

def download_audio_sample(
    url: str,
    output_dir: str
):

    if not FFMPEG_PATH:

        raise RuntimeError(
            "FFmpeg غير متوفر."
        )

    output_template = os.path.join(
        output_dir,
        "sample.%(ext)s"
    )

    options = {
        "format": "bestaudio/best",

        "outtmpl": output_template,

        "quiet": True,

        "no_warnings": True,

        "noplaylist": True,

        "ffmpeg_location": FFMPEG_PATH,

        # أخذ جزء فقط من المقطع
        "download_ranges": (
            lambda info, ydl: [
                {
                    "start_time": SAMPLE_START,
                    "end_time": (
                        SAMPLE_START
                        + SAMPLE_DURATION
                    ),
                }
            ]
        ),

        # تحويل إلى wav
        "postprocessors": [
            {
                "key": "FFmpegExtractAudio",
                "preferredcodec": "wav",
            }
        ],
    }

    with yt_dlp.YoutubeDL(
        options
    ) as ytdl:

        ytdl.download(
            [url]
        )

    files = []

    for filename in os.listdir(
        output_dir
    ):

        path = os.path.join(
            output_dir,
            filename
        )

        if os.path.isfile(
            path
        ):

            files.append(
                path
            )

    if not files:

        raise RuntimeError(
            "لم يتم إنشاء عينة صوتية."
        )

    # نفضل wav
    wav_files = [
        x for x in files
        if x.lower().endswith(
            ".wav"
        )
    ]

    if wav_files:

        return wav_files[0]

    return files[0]


# =========================================================
# TRANSCRIBE
# =========================================================

def transcribe_audio(
    audio_file: str
):

    model = load_whisper_model()

    if model is None:

        raise RuntimeError(
            "Whisper model unavailable."
        )

    print(
        "[VERIFICATION] Transcribing Arabic audio..."
    )

    segments, info = model.transcribe(
        audio_file,

        language="ar",

        beam_size=5,

        best_of=5,

        temperature=0,

        vad_filter=True,

        condition_on_previous_text=False,
    )

    texts = []

    for segment in segments:

        text = segment.text.strip()

        if text:

            texts.append(
                text
            )

    transcription = " ".join(
        texts
    ).strip()

    return transcription


# =========================================================
# SIMILARITY HELPERS
# =========================================================

def longest_common_contiguous(
    a,
    b
):

    if not a or not b:

        return 0

    # لمنع استهلاك ذاكرة كبيرة
    if len(a) > 250:
        a = a[:250]

    if len(b) > 250:
        b = b[:250]

    previous = [0] * (
        len(b) + 1
    )

    best = 0

    for token_a in a:

        current = [0] * (
            len(b) + 1
        )

        for j, token_b in enumerate(
            b,
            start=1
        ):

            if token_a == token_b:

                current[j] = (
                    previous[j - 1] + 1
                )

                if current[j] > best:

                    best = current[j]

        previous = current

    return best


def calculate_ayah_similarity(
    transcript_words,
    ayah_words
):

    if not transcript_words:
        return 0.0

    if not ayah_words:
        return 0.0

    transcript_set = set(
        transcript_words
    )

    ayah_set = set(
        ayah_words
    )

    overlap = (
        transcript_set
        & ayah_set
    )

    overlap_score = (
        len(overlap)
        / max(
            min(
                len(transcript_set),
                len(ayah_set)
            ),
            1
        )
    )

    longest = longest_common_contiguous(
        transcript_words,
        ayah_words
    )

    contiguous_score = (
        longest
        / max(
            min(
                len(transcript_words),
                len(ayah_words)
            ),
            1
        )
    )

    # إعطاء أهمية أكبر للتسلسل الصحيح
    score = (
        overlap_score * 0.35
        +
        contiguous_score * 0.65
    )

    return min(
        score,
        1.0
    )


# =========================================================
# QURAN MATCH
# =========================================================

def calculate_quran_score(
    transcription: str
):

    transcript_words = get_words(
        transcription
    )

    if len(
        transcript_words
    ) < MIN_WORDS:

        return {
            "score": 0.0,
            "best_ayah_score": 0.0,
            "matched_ayahs": 0,
            "total_words": len(
                transcript_words
            ),
        }

    best_scores = []

    # -----------------------------------------------------
    # فحص جميع الآيات
    # -----------------------------------------------------

    for ayah in QURAN_AYAHS:

        ayah_words = get_words(
            ayah
        )

        if not ayah_words:
            continue

        # نركز على الآيات التي تحتوي كلمات مشتركة
        transcript_set = set(
            transcript_words
        )

        ayah_set = set(
            ayah_words
        )

        common = (
            transcript_set
            & ayah_set
        )

        if len(common) < 2:
            continue

        score = calculate_ayah_similarity(
            transcript_words,
            ayah_words
        )

        if score > 0:

            best_scores.append(
                score
            )

    if not best_scores:

        return {
            "score": 0.0,
            "best_ayah_score": 0.0,
            "matched_ayahs": 0,
            "total_words": len(
                transcript_words
            ),
        }

    best_scores.sort(
        reverse=True
    )

    best_score = best_scores[0]

    # أكثر من آية قوية = ثقة أعلى
    strong_matches = [
        score
        for score in best_scores
        if score >= 0.30
    ]

    second_score = (
        best_scores[1]
        if len(best_scores) >= 2
        else 0.0
    )

    combined_score = (
        best_score * 0.70
        +
        second_score * 0.20
        +
        min(
            len(strong_matches) / 5,
            1.0
        ) * 0.10
    )

    return {
        "score": min(
            combined_score,
            1.0
        ),
        "best_ayah_score": best_score,
        "matched_ayahs": len(
            strong_matches
        ),
        "total_words": len(
            transcript_words
        ),
    }


# =========================================================
# AUDIO VERIFICATION
# =========================================================

async def verify_audio(
    url: str
):

    # -----------------------------------------------------
    # Quran
    # -----------------------------------------------------

    quran_ready = await ensure_quran_loaded()

    if not quran_ready:

        return {
            "allowed": False,
            "reason": (
                "تعذر تحميل نص القرآن للتحقق."
            ),
            "score": 0.0,
            "transcription": "",
        }

    # -----------------------------------------------------
    # Whisper
    # -----------------------------------------------------

    whisper = await ensure_whisper_loaded()

    if whisper is None:

        return {
            "allowed": False,
            "reason": (
                "تعذر تشغيل نظام تحليل الصوت."
            ),
            "score": 0.0,
            "transcription": "",
        }

    # -----------------------------------------------------
    # Temporary directory
    # -----------------------------------------------------

    temp_dir = tempfile.mkdtemp(
        prefix="ct_quran_"
    )

    try:

        # -------------------------------------------------
        # Download sample
        # -------------------------------------------------

        print(
            "[VERIFICATION] Downloading audio sample..."
        )

        audio_file = await asyncio.to_thread(
            download_audio_sample,
            url,
            temp_dir
        )

        if not audio_file:

            raise RuntimeError(
                "Audio sample was not created."
            )

        # -------------------------------------------------
        # Transcribe
        # -------------------------------------------------

        transcription = await asyncio.to_thread(
            transcribe_audio,
            audio_file
        )

        print(
            "[VERIFICATION] "
            f"Transcript: {transcription[:500]}"
        )

        normalized = normalize_arabic(
            transcription
        )

        transcript_words = get_words(
            normalized
        )

        # -------------------------------------------------
        # No speech
        # -------------------------------------------------

        if len(
            transcript_words
        ) < MIN_WORDS:

            return {
                "allowed": False,
                "reason": (
                    "لم يتم التعرف على تلاوة عربية "
                    "واضحة في الصوت."
                ),
                "score": 0.0,
                "transcription": transcription,
            }

        # -------------------------------------------------
        # Quran matching
        # -------------------------------------------------

        result = calculate_quran_score(
            transcription
        )

        score = result["score"]

        print(
            "[VERIFICATION] "
            f"Quran score: {score:.2%}"
        )

        print(
            "[VERIFICATION] "
            f"Best ayah score: "
            f"{result['best_ayah_score']:.2%}"
        )

        print(
            "[VERIFICATION] "
            f"Matched ayahs: "
            f"{result['matched_ayahs']}"
        )

        # -------------------------------------------------
        # APPROVED
        # -------------------------------------------------

        if (
            score >= MIN_QURAN_SCORE
            and result["best_ayah_score"] >= 0.40
        ):

            return {
                "allowed": True,
                "reason": (
                    "تم فحص الصوت نفسه "
                    "والعثور على تطابق مع القرآن."
                ),
                "score": score,
                "transcription": transcription,
            }

        # -------------------------------------------------
        # REJECTED
        # -------------------------------------------------

        return {
            "allowed": False,
            "reason": (
                "الصوت لم يحقق التطابق المطلوب "
                "مع نص القرآن."
            ),
            "score": score,
            "transcription": transcription,
        }

    except Exception as e:

        print(
            "[VERIFICATION] "
            f"Audio verification error: {e}"
        )

        return {
            "allowed": False,
            "reason": (
                "تعذر فحص الصوت نفسه."
            ),
            "score": 0.0,
            "transcription": "",
        }

    finally:

        try:

            shutil.rmtree(
                temp_dir,
                ignore_errors=True
            )

        except Exception:
            pass


# =========================================================
# RESULT
# =========================================================

class VerificationResult:

    def __init__(
        self,
        allowed: bool,
        reason: str,
        score: float = 0.0,
        transcription: str = ""
    ):

        self.allowed = allowed

        self.reason = reason

        self.score = score

        self.transcription = transcription


# =========================================================
# COG
# =========================================================

class QuranVerification(
    commands.Cog
):

    def __init__(
        self,
        bot
    ):

        self.bot = bot

        self.startup_task = (
            asyncio.create_task(
                self.prepare_system()
            )
        )

    # =====================================================
    # PREPARE
    # =====================================================

    async def prepare_system(
        self
    ):

        print(
            "[VERIFICATION] Preparing audio verification..."
        )

        # تحميل القرآن أولًا
        await ensure_quran_loaded()

        # Whisper يتم تحميله عند أول استخدام
        print(
            "[VERIFICATION] Audio verification ready."
        )

    # =====================================================
    # VERIFY URL
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

        if not is_supported_url(
            url
        ):

            return VerificationResult(
                False,
                "المنصة غير مدعومة."
            )

        # -------------------------------------------------
        # اقرأ معلومات الرابط فقط للتأكد أنه موجود
        # الحكم لا يعتمد عليها
        # -------------------------------------------------

        try:

            info = await asyncio.to_thread(
                extract_info,
                url
            )

        except Exception as e:

            print(
                "[VERIFICATION] "
                f"URL extraction error: {e}"
            )

            return VerificationResult(
                False,
                "تعذر قراءة الرابط."
            )

        if not info:

            return VerificationResult(
                False,
                "لم يتم العثور على المقطع."
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

        print(
            "[VERIFICATION] "
            f"Starting AUDIO check: {title}"
        )

        # =================================================
        # ACTUAL AUDIO CHECK
        # =================================================

        result = await verify_audio(
            url
        )

        return VerificationResult(
            allowed=result["allowed"],
            reason=result["reason"],
            score=result["score"],
            transcription=result["transcription"],
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

            add_play_history(
                guild_id=guild.id,
                user_id=user.id,
                username=str(user),
                url=url,
                title="Audio Quran Verification",
                source="audio",
                verified=True,
                rejected=False
            )

            print(
                "[VERIFICATION] "
                "Quran audio APPROVED."
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
            title="Audio Quran Verification",
            source="audio",
            verified=False,
            rejected=True
        )

        await self.send_rejection_dm(
            user,
            result.reason
        )

        print(
            "[VERIFICATION] "
            "Audio REJECTED."
        )

        return False, result

    # =====================================================
    # UNLOAD
    # =====================================================

    async def cog_unload(
        self
    ):

        if (
            self.startup_task
            and not self.startup_task.done()
        ):

            self.startup_task.cancel()


# =========================================================
# SETUP
# =========================================================

async def setup(
    bot
):

    await bot.add_cog(
        QuranVerification(
            bot
        )
    )
