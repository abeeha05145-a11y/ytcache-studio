import re
import urllib.parse
import uuid
from pathlib import Path
from typing import Dict, Any, List, Optional
import requests
import yt_dlp
CHROME_TARGET = None
from youtube_transcript_api import YouTubeTranscriptApi

from app.config import DOWNLOAD_DIR

LANGUAGES = {
    "original": "Original Spoken Audio",
    "en": "English",
    "ur": "Urdu (اردو)",
    "hi": "Hindi (हिन्दी)",
    "ar": "Arabic (العربية)",
    "es": "Spanish (Español)",
    "fr": "French (Français)",
    "de": "German (Deutsch)",
    "zh-CN": "Chinese (Simplified)",
    "ru": "Russian (Русский)",
    "ja": "Japanese (日本語)",
    "tr": "Turkish (Türkçe)",
    "pt": "Portuguese (Português)",
    "it": "Italian (Italiano)",
    "ko": "Korean (한국어)",
    "bn": "Bengali (বাংলা)",
    "id": "Indonesian (Bahasa)",
    "fa": "Persian (فارسی)",
}

def extract_youtube_id(url: str) -> Optional[str]:
    """
    Extracts 11-character YouTube video ID from various URL formats.
    """
    clean_url = url.strip()
    patterns = [
        r'(?:v=|\/v\/|youtu\.be\/|\/embed\/|\/shorts\/|\/watch\?v=|\&v=)([a-zA-Z0-9_-]{11})',
        r'^([a-zA-Z0-9_-]{11})$'
    ]
    for pattern in patterns:
        match = re.search(pattern, clean_url)
        if match:
            return match.group(1)
    return None

def translate_paragraph(text: str, target_lang: str) -> str:
    """
    Translates paragraph text into target language using Google Translate API.
    Splits into safe chunks to avoid URL length restrictions.
    """
    if not text.strip() or target_lang in ["original", "default"]:
        return text

    # Split into chunks of ~1000 characters around sentence boundaries
    sentences = re.split(r'([.?!۔।\n]+)', text)
    chunks = []
    current_chunk = ""

    for i in range(0, len(sentences), 2):
        sentence = sentences[i]
        delimiter = sentences[i + 1] if i + 1 < len(sentences) else ""
        part = sentence + delimiter
        if len(current_chunk) + len(part) > 1000:
            if current_chunk.strip():
                chunks.append(current_chunk.strip())
            current_chunk = part
        else:
            current_chunk += part

    if current_chunk.strip():
        chunks.append(current_chunk.strip())

    translated_chunks = []
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}

    for chunk in chunks:
        try:
            url = f"https://translate.googleapis.com/translate_a/single?client=gtx&sl=auto&tl={target_lang}&dt=t&q={urllib.parse.quote(chunk)}"
            resp = requests.get(url, headers=headers, timeout=8)
            if resp.status_code == 200:
                data = resp.json()
                translated_pieces = [p[0] for p in data[0] if p and p[0]]
                translated_chunks.append("".join(translated_pieces))
            else:
                translated_chunks.append(chunk)
        except Exception as e:
            print(f"[Translation] Error: {e}")
            translated_chunks.append(chunk)

    return " ".join(translated_chunks)

def vtt_to_clean_paragraph(vtt_text: str) -> str:
    """
    Parses WebVTT subtitle data into a cohesive, readable speech paragraph.
    Removes VTT timestamps, cues, sound descriptions, and duplicates.
    """
    pattern = re.compile(
        r'(?:\d{2}:)?\d{2}:\d{2}\.\d{3}\s*-->\s*(?:\d{2}:)?\d{2}:\d{2}\.\d{3}[^\r\n]*\r?\n(.*?)(?=\r?\n\r?\n|\Z)',
        re.DOTALL
    )
    blocks = pattern.findall(vtt_text)
    cleaned_chunks = []
    seen = set()

    for block in blocks:
        t = re.sub(r'<[^>]+>', '', block)
        t = re.sub(r'\[(?:Music|Applause|Laughter|Cheering|Audio)\]', '', t, flags=re.I)
        t = re.sub(r'\((?:Music|Applause|Laughter)\)', '', t, flags=re.I)
        t = re.sub(r'[♪♫#]+', '', t)
        t = re.sub(r'\s+', ' ', t).strip()

        if t and t not in seen:
            seen.add(t)
            cleaned_chunks.append(t)

    raw_text = " ".join(cleaned_chunks)
    raw_text = re.sub(r'\s+([.,?!])', r'\1', raw_text)
    raw_text = re.sub(r'\s+', ' ', raw_text).strip()
    return raw_text

def get_video_transcript(url: str, target_lang: str = "original") -> Dict[str, Any]:
    """
    Lightweight, fast transcript extractor.
    Zero video or audio downloading.
    Extracts purely speech text within 1-2 seconds.
    """
    video_id = extract_youtube_id(url)
    if not video_id:
        raise ValueError("Invalid YouTube URL. Please enter a valid YouTube video link.")

    job_id = str(uuid.uuid4())[:8]
    temp_prefix = DOWNLOAD_DIR / f"cap_{job_id}"
    video_title = "YouTube Video"
    original_paragraph = ""
    detected_lang = "en"

    # METHOD 1: Fast yt-dlp metadata caption download (skip_download=True, < 1 sec, zero media download)
    try:
        ydl_opts = {
            'skip_download': True,
            'writesubtitles': True,
            'writeautomaticsub': True,
            'subtitlesformat': 'vtt',
            'outtmpl': str(temp_prefix) + '.%(ext)s',
            'quiet': True,
            'no_warnings': True,
            'extractor_args': {
                'youtube': {
                    'player_client': ['android', 'ios'],
                    'player_skip': ['webpage', 'configs'],
                }
            }
        }
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(f"https://www.youtube.com/watch?v={video_id}", download=True)
            video_title = info.get('title', 'YouTube Video')

        # Find downloaded .vtt files
        vtt_files = list(DOWNLOAD_DIR.glob(f"cap_{job_id}.*.vtt"))
        if vtt_files:
            # Pick first file
            vtt_file = vtt_files[0]
            # Extract language code from filename (cap_xxxx.en.vtt)
            name_parts = vtt_file.name.split('.')
            if len(name_parts) >= 3:
                detected_lang = name_parts[-2].replace('-orig', '')

            vtt_text = vtt_file.read_text(encoding='utf-8')
            original_paragraph = vtt_to_clean_paragraph(vtt_text)

        # Cleanup temp caption files
        for f in list(DOWNLOAD_DIR.glob(f"cap_{job_id}.*")):
            try:
                f.unlink()
            except Exception:
                pass

    except Exception as e:
        print(f"[Transcript] Method 1 notice: {e}")

    # METHOD 2: Fallback using youtube-transcript-api if Method 1 didn't yield text
    if not original_paragraph:
        try:
            transcript_api = YouTubeTranscriptApi()
            transcript_list = transcript_api.fetch(video_id)
            if transcript_list:
                cleaned_snippets = []
                for snippet in transcript_list:
                    txt = getattr(snippet, 'text', '') or (snippet.get('text', '') if isinstance(snippet, dict) else '')
                    txt = re.sub(r'\[.*?\]', '', txt).strip()
                    if txt:
                        cleaned_snippets.append(txt)
                original_paragraph = " ".join(cleaned_snippets)
                detected_lang = "en"
        except Exception as e:
            print(f"[Transcript] Method 2 notice: {e}")

    if not original_paragraph:
        raise ValueError("No speech transcript or subtitles are available for this video.")

    original_lang_name = LANGUAGES.get(detected_lang, detected_lang.upper())

    # Handle Translation
    current_lang = target_lang
    if target_lang in ["original", "default", detected_lang]:
        current_paragraph = original_paragraph
        current_lang_name = f"{original_lang_name} (Original)"
        current_lang = detected_lang
    else:
        current_paragraph = translate_paragraph(original_paragraph, target_lang)
        current_lang_name = LANGUAGES.get(target_lang, target_lang.upper())

    return {
        "success": True,
        "video_title": video_title,
        "video_id": video_id,
        "original_lang": detected_lang,
        "original_lang_name": original_lang_name,
        "current_lang": current_lang,
        "current_lang_name": current_lang_name,
        "paragraph": current_paragraph,
        "languages": LANGUAGES
    }
