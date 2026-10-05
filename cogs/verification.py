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

QURAN_API_URL = "https://api.alquran.cloud/v1/quran/quran-simple"

WHISPER_MODEL = os.getenv(
    "WHISPER_MODEL",
    "small"
)

WHISPER_DEVICE = os.getenv(
    "WHISPER_DEVICE",
    "cpu"
)

WHISPER_COMPUTE_TYPE = os.getenv(
    "WHISPER_COMPUTE_TYPE",
    "int8"
)

SAMPLE_DURATION = 30
SAMPLE_START = 5

MIN_WORDS = 5
MIN_QURAN_SCORE = 0.45


# =========================================================
# BROWSER
# =========================================================

BROWSER_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/140.0.0.0 Safari/537.36"
)

HTTP_HEADERS = {
    "User-Agent": BROWSER_USER_AGENT,
    "Accept-Language": "en-US,en;q=0.9,ar;q=0.8",
}


# =========================================================
# SUPPORTED DOMAINS
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
# GLOBALS
# =========================================================

QURAN_AYAHS = []
QURAN_READY = False

WHISPER_MODEL_INSTANCE = None

MODEL_LOCK = None
QURAN_LOCK = None


# =========================================================
# LOCKS
# =========================================================

def initialize_locks():

    global MODEL_LOCK
    global QURAN_LOCK

    if MODEL_LOCK is None:
        MODEL_LOCK = asyncio.Lock()

    if QURAN_LOCK is None:
        QURAN_LOCK = asyncio.Lock()


# =========================================================
# FFMPEG
# =========================================================

def get_ffmpeg_path():

    try:

        path = imageio_ffmpeg.get_ffmpeg_exe()

        print(
            f"[VERIFICATION] FFmpeg: {path}"
        )

        return path

    except Exception as e:

        print(
            f"[VERIFICATION] FFmpeg error: {e}"
        )

        return None


FFMPEG_PATH = get_ffmpeg_path()


# =========================================================
# ARABIC NORMALIZATION
# =========================================================

def normalize_arabic(text: str):

    if not text:
        return ""

    text = str(text).lower()

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

    text = re.sub(
        r"[\u064B-\u065F\u0670]",
        "",
        text
    )

    text = re.sub(
        r"[\u06D6-\u06ED]",
        "",
        text
    )

    text = re.sub(
        r"[^\w\s\u0600-\u06FF]",
        " ",
        text
    )

    text = re.sub(
        r"\d+",
        " ",
        text
    )

    text = re.sub(
        r"\s+",
        " ",
        text
    )

    return text.strip()


def get_words(text: str):

    normalized = normalize_arabic(
        text
    )

    if not normalized:
        return []

    return normalized.split()


# =========================================================
# DOMAIN
# =========================================================

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
# QURAN
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
            result.append(normalized)

    return result


async def ensure_quran_loaded():

    global QURAN_AYAHS
    global QURAN_READY

    initialize_locks()

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
                "[VERIFICATION] Loaded "
                f"{len(QURAN_AYAHS)} ayahs."
            )

            return True

        except Exception as e:

            print(
                "[VERIFICATION] Quran loading failed: "
                f"{e}"
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

    initialize_locks()

    if WHISPER_MODEL_INSTANCE is not None:
        return WHISPER_MODEL_INSTANCE

    async with MODEL_LOCK:

        if WHISPER_MODEL_INSTANCE is not None:
            return WHISPER_MODEL_INSTANCE

        try:

            return await asyncio.to_thread(
                load_whisper_model
            )

        except Exception as e:

            print(
                "[VERIFICATION] "
                f"Whisper load failed: {e}"
            )

            return None


# =========================================================
# YT-DLP HEADERS
# =========================================================

def get_ytdlp_headers():

    return {
        "User-Agent": BROWSER_USER_AGENT,
        "Accept-Language": "en-US,en;q=0.9,ar;q=0.8",
        "Accept": (
            "text/html,application/xhtml+xml,"
            "application/xml;q=0.9,*/*;q=0.8"
        ),
    }


# =========================================================
# YT-DLP BASE OPTIONS
# =========================================================

def get_base_ytdlp_options():

    return {

        "quiet": True,

        "no_warnings": True,

        "noplaylist": True,

        "nocheckcertificate": True,

        "http_headers": get_ytdlp_headers(),

        "socket_timeout": 30,

        "retries": 3,

        "fragment_retries": 3,

        "extractor_retries": 3,

        "concurrent_fragment_downloads": 1,

        "extractor_args": {

            "tiktok": {
                "app_name": "musical_ly",
                "app_version": "39.4.3",
            }

        },
    }


# =========================================================
# EXTRACT INFO
# =========================================================

def extract_info(url: str):

    options = get_base_ytdlp_options()

    options["skip_download"] = True

    try:

        with yt_dlp.YoutubeDL(
            options
        ) as ytdl:

            return ytdl.extract_info(
                url,
                download=False
            )

    except Exception as first_error:

        print(
            "[VERIFICATION] "
            f"Primary extraction failed: {first_error}"
        )

        # Second attempt with minimal options.
        # Some extractors behave better without
        # additional options.

        fallback_options = {
            "quiet": True,
            "no_warnings": True,
            "noplaylist": True,
            "nocheckcertificate": True,
            "skip_download": True,
            "socket_timeout": 30,
            "retries": 2,
            "http_headers": {
                "User-Agent": BROWSER_USER_AGENT,
            },
        }

        with yt_dlp.YoutubeDL(
            fallback_options
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

    options = get_base_ytdlp_options()

    options.update({

        "format": (
            "bestaudio[ext=m4a]/"
            "bestaudio/best"
        ),

        "outtmpl": output_template,

        "ffmpeg_location": FFMPEG_PATH,

        "postprocessors": [
            {
                "key": "FFmpegExtractAudio",
                "preferredcodec": "wav",
            }
        ],

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

    })

    try:

        with yt_dlp.YoutubeDL(
            options
        ) as ytdl:

            ytdl.download(
                [url]
            )

    except Exception as first_error:

        print(
            "[VERIFICATION] "
            f"Primary audio download failed: "
            f"{first_error}"
        )

        # Fallback without download range.
        # This is slower but can work when a
        # platform does not support ranged downloads.

        fallback_dir = os.path.join(
            output_dir,
            "fallback"
        )

        os.makedirs(
            fallback_dir,
            exist_ok=True
        )

        fallback_template = os.path.join(
            fallback_dir,
            "audio.%(ext)s"
        )

        fallback_options = get_base_ytdlp_options()

        fallback_options.update({

            "format": "bestaudio/best",

            "outtmpl": fallback_template,

            "ffmpeg_location": FFMPEG_PATH,

            "postprocessors": [
                {
                    "key": "FFmpegExtractAudio",
                    "preferredcodec": "wav",
                }
            ],

        })

        with yt_dlp.YoutubeDL(
            fallback_options
        ) as ytdl:

            ytdl.download(
                [url]
            )

        output_dir = fallback_dir

    files = []

    for filename in os.listdir(
        output_dir
    ):

        path = os.path.join(
            output_dir,
            filename
        )

        if os.path.isfile(path):

            files.append(path)

    if not files:

        raise RuntimeError(
            "لم يتم إنشاء عينة صوتية."
        )

    wav_files = [
        x for x in files
        if x.lower().endswith(".wav")
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
        "[VERIFICATION] "
        "Transcribing Arabic audio..."
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
            texts.append(text)

    transcription = " ".join(
        texts
    ).strip()

    return transcription


# =========================================================
# LONGEST COMMON MATCH
# =========================================================

def longest_common_contiguous(
    a,
    b
):

    if not a or not b:
        return 0

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

                best = max(
                    best,
                    current[j]
                )

        previous = current

    return best


# =========================================================
# AYAH SIMILARITY
# =========================================================

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
        &
        ayah_set
    )

    overlap_score = (
        len(overlap)
        /
        max(
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
        /
        max(
            min(
                len(transcript_words),
                len(ayah_words)
            ),
            1
        )
    )

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
# QURAN SCORE
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

    transcript_set = set(
        transcript_words
    )

    best_scores = []

    for ayah in QURAN_AYAHS:

        ayah_words = get_words(
            ayah
        )

        if not ayah_words:
            continue

        ayah_set = set(
            ayah_words
        )

        common = (
            transcript_set
            &
            ayah_set
        )

        if len(common) < 2:
            continue

        score = calculate_ayah_similarity(
            transcript_words,
            ayah_words
        )

        if score > 0:
            best_scores.append(score)

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
# VERIFY AUDIO
# =========================================================

async def verify_audio(
    url: str
):

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

    temp_dir = tempfile.mkdtemp(
        prefix="ct_quran_"
    )

    try:

        print(
            "[VERIFICATION] "
            "Downloading audio..."
        )

        audio_file = await asyncio.to_thread(
            download_audio_sample,
            url,
            temp_dir
        )

        print(
            "[VERIFICATION] "
            "Audio downloaded."
        )

        transcription = await asyncio.to_thread(
            transcribe_audio,
            audio_file
        )

        print(
            "[VERIFICATION] "
            f"Transcript: {transcription[:500]}"
        )

        transcript_words = get_words(
            transcription
        )

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

        if (
            score >= MIN_QURAN_SCORE
            and
            result["best_ayah_score"] >= 0.40
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

        shutil.rmtree(
            temp_dir,
            ignore_errors=True
        )


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

class QuranVerification(commands.Cog):

    def __init__(
        self,
        bot
    ):

        self.bot = bot

        initialize_locks()

        self.startup_task = asyncio.create_task(
            self.prepare_system()
        )

    async def prepare_system(self):

        print(
            "[VERIFICATION] "
            "Preparing verification system..."
        )

        await ensure_quran_loaded()

        print(
            "[VERIFICATION] "
            "Verification system ready."
        )

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

        try:

            info = await asyncio.to_thread(
                extract_info,
                url
            )

        except Exception as e:

            print(
                "[VERIFICATION] "
                f"URL extraction failed: {e}"
            )

            return VerificationResult(
                False,
                "تعذر قراءة الرابط من المنصة."
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
            f"Checking AUDIO: {title}"
        )

        result = await verify_audio(
            url
        )

        return VerificationResult(
            result["allowed"],
            result["reason"],
            result["score"],
            result["transcription"]
        )

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
