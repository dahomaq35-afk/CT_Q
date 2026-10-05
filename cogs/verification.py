# =========================================================
# CT QURAN BOT
# cogs/verification.py
#
# AUDIO-BASED QURAN VERIFICATION
# =========================================================
import os
import re
import json
import asyncio
import tempfile
import subprocess
from urllib.request import Request, urlopen
from urllib.parse import urlparse
import discord
import yt_dlp
from discord.ext import commands
from openai import OpenAI
from database import (
    add_play_history,
    add_rejected_attempt,
)
# =========================================================
# SETTINGS
# =========================================================
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
QURAN_API_URL = (
    "https://api.alquran.cloud/v1/quran/quran-simple"
)
TRANSCRIPTION_MODEL = os.getenv(
    "QURAN_TRANSCRIPTION_MODEL",
    "gpt-4o-mini-transcribe"
)
# مدة العينة الصوتية
SAMPLE_DURATION = 30
# بداية العينة
SAMPLE_START = 5
# الحد الأدنى للتطابق
MIN_QURAN_MATCH = 0.48
# إذا كان النص قصير جدًا لا نعتمد عليه
MIN_TRANSCRIPTION_LENGTH = 20
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
# OPENAI
# =========================================================
openai_client = None
if OPENAI_API_KEY:
    try:
        openai_client = OpenAI(
            api_key=OPENAI_API_KEY
        )
        print(
            "[VERIFICATION] OpenAI audio verification enabled."
        )
    except Exception as e:
        print(
            f"[VERIFICATION] OpenAI initialization failed: {e}"
        )
else:
    print(
        "[VERIFICATION] WARNING: OPENAI_API_KEY is missing."
    )
# =========================================================
# NORMALIZE ARABIC
# =========================================================
def normalize_arabic(
    text: str
):
    if not text:
        return ""
    text = str(
        text
    ).lower()
    # -----------------------------------------------------
    # Arabic normalization
    # -----------------------------------------------------
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
    # -----------------------------------------------------
    # Remove tashkeel
    # -----------------------------------------------------
    text = re.sub(
        r"[\u064B-\u065F\u0670]",
        "",
        text
    )
    # -----------------------------------------------------
    # Remove Quran pause marks
    # -----------------------------------------------------
    text = re.sub(
        r"[\u06D6-\u06ED]",
        "",
        text
    )
    # -----------------------------------------------------
    # Remove punctuation
    # -----------------------------------------------------
    text = re.sub(
        r"[^\w\s\u0600-\u06FF]",
        " ",
        text
    )
    # -----------------------------------------------------
    # Remove English / numbers
    # -----------------------------------------------------
    text = re.sub(
        r"[a-zA-Z0-9]+",
        " ",
        text
    )
    # -----------------------------------------------------
    # Normalize spaces
    # -----------------------------------------------------
    text = re.sub(
        r"\s+",
        " ",
        text
    )
    return text.strip()
# =========================================================
# URL
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
        if domain == supported:
            return True
        if domain.endswith(
            "." + supported
        ):
            return True
    return False
# =========================================================
# QURAN DATA
# =========================================================
def download_quran_text():
    request = Request(
        QURAN_API_URL,
        headers={
            "User-Agent": "CT-Quran-Bot/1.0"
        }
    )
    with urlopen(
        request,
        timeout=30
    ) as response:
        raw = response.read()
    data = json.loads(
        raw.decode(
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
            "Quran text was not returned."
        )
    return [
        normalize_arabic(
            ayah.get(
                "text",
                ""
            )
        )
        for ayah in ayahs
        if ayah.get("text")
    ]
# =========================================================
# QURAN DATABASE
# =========================================================
QURAN_AYAHS = []
QURAN_READY = False
def load_quran():
    global QURAN_AYAHS
    global QURAN_READY
    try:
        print(
            "[VERIFICATION] Downloading Quran text..."
        )
        QURAN_AYAHS = download_quran_text()
        QURAN_READY = bool(
            QURAN_AYAHS
        )
        print(
            f"[VERIFICATION] Loaded "
            f"{len(QURAN_AYAHS)} Quran ayahs."
        )
    except Exception as e:
        QURAN_READY = False
        print(
            f"[VERIFICATION] Failed to load Quran: {e}"
        )
# =========================================================
# TEXT TOKENIZATION
# =========================================================
def words(
    text: str
):
    return [
        word
        for word in normalize_arabic(
            text
        ).split()
        if word
    ]
# =========================================================
# QURAN MATCH
# =========================================================
def calculate_quran_match(
    transcription: str
):
    if not QURAN_READY:
        return {
            "score": 0.0,
            "matched_ayahs": 0,
            "matched_words": 0,
            "total_words": 0,
        }
    transcript_words = words(
        transcription
    )
    if len(
        transcript_words
    ) < 5:
        return {
            "score": 0.0,
            "matched_ayahs": 0,
            "matched_words": 0,
            "total_words": len(
                transcript_words
            ),
        }
    # -----------------------------------------------------
    # Create rolling phrases
    # -----------------------------------------------------
    phrase_sizes = [
        5,
        7,
        10,
    ]
    transcript_phrases = set()
    for size in phrase_sizes:
        if len(
            transcript_words
        ) < size:
            continue
        for index in range(
            0,
            len(transcript_words) - size + 1
        ):
            phrase = " ".join(
                transcript_words[
                    index:index + size
                ]
            )
            transcript_phrases.add(
                phrase
            )
    # -----------------------------------------------------
    # Quran index
    # -----------------------------------------------------
    matched_ayahs = 0
    matched_words = 0
    for ayah in QURAN_AYAHS:
        ayah_words = words(
            ayah
        )
        if not ayah_words:
            continue
        ayah_text = " ".join(
            ayah_words
        )
        # ---------------------------------------------
        # Exact phrase match
        # ---------------------------------------------
        found_phrase = False
        for size in phrase_sizes:
            if len(
                ayah_words
            ) < size:
                continue
            for index in range(
                0,
                len(ayah_words) - size + 1
            ):
                phrase = " ".join(
                    ayah_words[
                        index:index + size
                    ]
                )
                if phrase in transcript_phrases:
                    found_phrase = True
                    break
            if found_phrase:
                break
        if found_phrase:
            matched_ayahs += 1
            matched_words += min(
                len(ayah_words),
                10
            )
            continue
        # ---------------------------------------------
        # Word overlap fallback
        # ---------------------------------------------
        ayah_set = set(
            ayah_words
        )
        transcript_set = set(
            transcript_words
        )
        overlap = (
            ayah_set
            & transcript_set
        )
        if len(
            overlap
        ) >= 5:
            matched_ayahs += 1
            matched_words += len(
                overlap
            )
    # -----------------------------------------------------
    # Score
    # -----------------------------------------------------
    total_words = len(
        transcript_words
    )
    if total_words == 0:
        score = 0.0
    else:
        score = (
            matched_words
            / max(
                total_words,
                1
            )
        )
    # Cap
    score = min(
        score,
        1.0
    )
    return {
        "score": score,
        "matched_ayahs": matched_ayahs,
        "matched_words": matched_words,
        "total_words": total_words,
    }
# =========================================================
# YT-DLP INFO
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
    output_file: str
):
    options = {
        "format": "bestaudio/best",
        "outtmpl": output_file,
        "quiet": True,
        "no_warnings": True,
        "noplaylist": True,
        # -------------------------------------------------
        # Download only a short section
        # -------------------------------------------------
        "download_ranges": lambda info, ydl: [
            {
                "start_time": SAMPLE_START,
                "end_time": (
                    SAMPLE_START
                    + SAMPLE_DURATION
                ),
            }
        ],
        # -------------------------------------------------
        # Convert to MP3
        # -------------------------------------------------
        "postprocessors": [
            {
                "key": "FFmpegExtractAudio",
                "preferredcodec": "mp3",
                "preferredquality": "64",
            }
        ],
    }
    with yt_dlp.YoutubeDL(
        options
    ) as ytdl:
        ytdl.download(
            [url]
        )
# =========================================================
# TRANSCRIBE AUDIO
# =========================================================
def transcribe_audio(
    audio_file: str
):
    if not openai_client:
        raise RuntimeError(
            "OPENAI_API_KEY غير موجود."
        )
    with open(
        audio_file,
        "rb"
    ) as file:
        result = (
            openai_client
            .audio
            .transcriptions
            .create(
                model=TRANSCRIPTION_MODEL,
                file=file,
                language="ar",
                prompt=(
                    "هذا تسجيل صوتي قد يكون تلاوة "
                    "للقرآن الكريم باللغة العربية. "
                    "اكتب الكلمات التي تسمعها كما هي."
                ),
            )
        )
    text = getattr(
        result,
        "text",
        ""
    )
    return text or ""
# =========================================================
# AUDIO VERIFICATION
# =========================================================
async def verify_audio(
    url: str
):
    # -----------------------------------------------------
    # Check API
    # -----------------------------------------------------
    if not openai_client:
        return {
            "allowed": False,
            "reason": (
                "نظام فحص الصوت غير مفعّل لأن "
                "OPENAI_API_KEY غير موجود."
            ),
            "score": 0.0,
            "transcription": "",
        }
    # -----------------------------------------------------
    # Check Quran data
    # -----------------------------------------------------
    if not QURAN_READY:
        return {
            "allowed": False,
            "reason": (
                "تعذر تحميل نص القرآن للتحقق."
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
    base_file = os.path.join(
        temp_dir,
        "sample"
    )
    mp3_file = os.path.join(
        temp_dir,
        "sample.mp3"
    )
    try:
        # -------------------------------------------------
        # Download sample
        # -------------------------------------------------
        print(
            "[VERIFICATION] Downloading audio sample..."
        )
        await asyncio.to_thread(
            download_audio_sample,
            url,
            base_file
        )
        # -------------------------------------------------
        # Check generated file
        # -------------------------------------------------
        if not os.path.exists(
            mp3_file
        ):
            # بعض إصدارات yt-dlp تغير الاسم
            possible_files = []
            for filename in os.listdir(
                temp_dir
            ):
                full_path = os.path.join(
                    temp_dir,
                    filename
                )
                if os.path.isfile(
                    full_path
                ):
                    possible_files.append(
                        full_path
                    )
            if possible_files:
                mp3_file = possible_files[0]
            else:
                raise RuntimeError(
                    "لم يتم إنشاء ملف الصوت."
                )
        # -------------------------------------------------
        # Transcribe
        # -------------------------------------------------
        print(
            "[VERIFICATION] Transcribing audio..."
        )
        transcription = await asyncio.to_thread(
            transcribe_audio,
            mp3_file
        )
        print(
            f"[VERIFICATION] Transcription: "
            f"{transcription[:500]}"
        )
        # -------------------------------------------------
        # Minimum text
        # -------------------------------------------------
        normalized_transcription = (
            normalize_arabic(
                transcription
            )
        )
        if len(
            normalized_transcription
        ) < MIN_TRANSCRIPTION_LENGTH:
            return {
                "allowed": False,
                "reason": (
                    "لم يتم التعرف على كلام عربي "
                    "واضح في العينة الصوتية."
                ),
                "score": 0.0,
                "transcription": transcription,
            }
        # -------------------------------------------------
        # Quran matching
        # -------------------------------------------------
        match = calculate_quran_match(
            transcription
        )
        score = match["score"]
        print(
            f"[VERIFICATION] Quran match: "
            f"{score:.2%}"
        )
        print(
            f"[VERIFICATION] Matched ayahs: "
            f"{match['matched_ayahs']}"
        )
        # -------------------------------------------------
        # ACCEPT
        # -------------------------------------------------
        if score >= MIN_QURAN_MATCH:
            return {
                "allowed": True,
                "reason": (
                    "تم التحقق من الصوت نفسه "
                    "ومطابقته مع نص القرآن."
                ),
                "score": score,
                "transcription": transcription,
            }
        # -------------------------------------------------
        # REJECT
        # -------------------------------------------------
        return {
            "allowed": False,
            "reason": (
                "الصوت لم يحقق نسبة التطابق المطلوبة "
                "مع نص القرآن."
            ),
            "score": score,
            "transcription": transcription,
        }
    except Exception as e:
        print(
            f"[VERIFICATION] Audio verification error: {e}"
        )
        return {
            "allowed": False,
            "reason": (
                "تعذر فحص الصوت."
            ),
            "score": 0.0,
            "transcription": "",
        }
    finally:
        # -------------------------------------------------
        # Cleanup
        # -------------------------------------------------
        try:
            for filename in os.listdir(
                temp_dir
            ):
                path = os.path.join(
                    temp_dir,
                    filename
                )
                if os.path.isfile(
                    path
                ):
                    os.remove(
                        path
                    )
            os.rmdir(
                temp_dir
            )
        except Exception:
            pass
# =========================================================
# VERIFICATION RESULT
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
        # تحميل القرآن في الخلفية
        self.quran_task = (
            asyncio.create_task(
                self.load_quran_async()
            )
        )
    # =====================================================
    # LOAD QURAN ASYNC
    # =====================================================
    async def load_quran_async(
        self
    ):
        await asyncio.to_thread(
            load_quran
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
        # Wait for Quran database
        # -------------------------------------------------
        if not QURAN_READY:
            try:
                await asyncio.wait_for(
                    self.quran_task,
                    timeout=30
                )
            except Exception:
                pass
        # -------------------------------------------------
        # Basic URL information
        # -------------------------------------------------
        try:
            info = await asyncio.to_thread(
                extract_info,
                url
            )
        except Exception as e:
            print(
                f"[VERIFICATION] URL extraction error: {e}"
            )
            return VerificationResult(
                False,
                "تعذر قراءة الرابط."
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
        title = info.get(
            "title",
            ""
        ) or ""
        print(
            f"[VERIFICATION] Checking audio: {title}"
        )
        # =================================================
        # AUDIO CHECK
        # =================================================
        audio_result = await verify_audio(
            url
        )
        return VerificationResult(
            allowed=audio_result["allowed"],
            reason=audio_result["reason"],
            score=audio_result["score"],
            transcription=audio_result["transcription"],
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
                title="فحص صوتي",
                source="audio-verification",
                verified=True,
                rejected=False
            )
            print(
                "[VERIFICATION] Quran audio approved."
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
            title="فحص صوتي",
            source="audio-verification",
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
    # =====================================================
    # UNLOAD
    # =====================================================
    async def cog_unload(
        self
    ):
        if (
            self.quran_task
            and not self.quran_task.done()
        ):
            self.quran_task.cancel()
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
