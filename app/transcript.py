import re
import urllib.parse
import uuid
from pathlib import Path
from typing import Dict, Any, List, Optional
from http.cookiejar import MozillaCookieJar
import requests
import yt_dlp
import os
from youtube_transcript_api import YouTubeTranscriptApi
from youtube_transcript_api._errors import NoTranscriptFound, TranscriptsDisabled, VideoUnavailable
from app.config import DOWNLOAD_DIR

CHROME_TARGET = None

def get_cookie_file() -> Optional[str]:
    """Detect path to cookies.txt or create from YOUTUBE_COOKIES environment variable."""
    search_dirs = [
        Path("."),
        Path("/app"),
        Path(__file__).resolve().parent.parent,
        Path(__file__).resolve().parent
    ]
    cookie_names = [
        "www.youtube.com_cookies.txt",
        "cookies.txt",
        "youtube_cookies.txt",
        "yt_cookies.txt"
    ]
    for d in search_dirs:
        for name in cookie_names:
            p = d / name
            if p.exists() and p.stat().st_size > 0:
                return str(p.resolve())
        try:
            for p in d.glob("*cookie*.txt"):
                if p.exists() and p.stat().st_size > 0:
                    return str(p.resolve())
        except Exception:
            pass
    
    env_cookies = os.getenv("YOUTUBE_COOKIES")
    if env_cookies and len(env_cookies.strip()) > 10:
        tmp_path = DOWNLOAD_DIR / "yt_cookies.txt"
        try:
            content = env_cookies.strip().replace('\\r\\n', '\n').replace('\\n', '\n').replace('\\t', '\t')
            tmp_path.write_text(content, encoding="utf-8")
            return str(tmp_path.resolve())
        except Exception:
            pass
    return None

def get_cookie_opts() -> Dict[str, Any]:
    c_file = get_cookie_file()
    if c_file:
        return {'cookiefile': c_file}
    return {}

PROXIES_POOL = [
    "http://dxgwkmac:ul130busmnzq@191.96.254.138:6185",
    "http://dxgwkmac:ul130busmnzq@38.154.185.97:6370",
    "http://dxgwkmac:ul130busmnzq@198.23.243.226:6361"
]

def get_proxy_list() -> List[Optional[str]]:
    env_p = os.getenv("PROXY_URL") or os.getenv("HTTP_PROXY") or os.getenv("HTTPS_PROXY")
    if env_p and len(env_p.strip()) > 5:
        return [None, env_p.strip()] + PROXIES_POOL
    return [None] + list(PROXIES_POOL)

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

def fetch_video_title(video_id: str) -> str:
    """Fetch video title using lightning-fast YouTube oEmbed (no auth / no rate limits)."""
    try:
        url = f"https://www.youtube.com/oembed?url=https://www.youtube.com/watch?v={video_id}&format=json"
        r = requests.get(url, timeout=4)
        if r.status_code == 200:
            return r.json().get('title', 'YouTube Video')
    except Exception:
        pass
    return "YouTube Video"

def create_authenticated_session(proxy: Optional[str] = None) -> requests.Session:
    """Create requests session loaded with YouTube authentication cookies & headers."""
    session = requests.Session()
    session.headers.update({
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36',
        'Accept-Language': 'en-US,en;q=0.9',
    })
    c_file = get_cookie_file()
    if c_file:
        try:
            cj = MozillaCookieJar(c_file)
            cj.load(ignore_discard=True, ignore_expires=True)
            session.cookies = cj
        except Exception:
            pass
    if proxy:
        session.proxies = {'http': proxy, 'https': proxy}
    return session

def translate_paragraph(text: str, target_lang: str) -> str:
    if not text.strip() or target_lang in ["original", "default"]:
        return text

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
            resp = requests.get(url, headers=headers, timeout=5)
            if resp.status_code == 200:
                data = resp.json()
                translated_pieces = [p[0] for p in data[0] if p and p[0]]
                translated_chunks.append("".join(translated_pieces))
            else:
                translated_chunks.append(chunk)
        except Exception:
            translated_chunks.append(chunk)

    return " ".join(translated_chunks)

def get_video_transcript(url: str, target_lang: str = "original") -> Dict[str, Any]:
    """
    High-speed, authentic speech transcript extractor.
    Extracts purely speech text within 1-2 seconds with zero disk downloads.
    """
    video_id = extract_youtube_id(url)
    if not video_id:
        raise ValueError("Invalid YouTube URL. Please enter a valid YouTube video link.")

    video_title = fetch_video_title(video_id)
    original_paragraph = ""
    detected_lang = "en"
    detected_transcript_obj = None

    candidates = [None] + PROXIES_POOL

    for proxy in candidates:
        try:
            session = create_authenticated_session(proxy=proxy)
            api = YouTubeTranscriptApi(http_client=session)
            transcript_list = api.list(video_id)

            chosen_t = None
            pref_codes = [target_lang, 'en', 'ur', 'hi'] if target_lang not in ["original", "default"] else ['en', 'ur', 'hi']
            for code in pref_codes:
                try:
                    chosen_t = transcript_list.find_transcript([code])
                    if chosen_t:
                        break
                except Exception:
                    pass

            if not chosen_t:
                for t in transcript_list:
                    chosen_t = t
                    break

            if chosen_t:
                detected_transcript_obj = chosen_t
                detected_lang = chosen_t.language_code
                snippets = chosen_t.fetch()
                clean_lines = []
                for s in snippets:
                    t = getattr(s, 'text', '') or (s.get('text', '') if isinstance(s, dict) else '')
                    t = re.sub(r'\[.*?\]', '', t)
                    t = re.sub(r'\(.*?\)', '', t)
                    t = re.sub(r'[♪♫#]+', '', t)
                    t = re.sub(r'\s+', ' ', t).strip()
                    if t:
                        clean_lines.append(t)
                text = " ".join(clean_lines)
                text = re.sub(r'\s+([.,?!])', r'\1', text)
                original_paragraph = text.strip()
                if original_paragraph:
                    break
        except (NoTranscriptFound, TranscriptsDisabled, VideoUnavailable):
            break
        except Exception:
            continue

    if not original_paragraph:
        raise ValueError("No speech transcript or subtitles are available for this video.")

    original_lang_name = LANGUAGES.get(detected_lang, detected_lang.upper())
    current_paragraph = original_paragraph
    current_lang = detected_lang
    current_lang_name = f"{original_lang_name} (Original)"

    # Handle Translation if requested
    if target_lang not in ["original", "default", detected_lang]:
        translated = False
        if detected_transcript_obj and getattr(detected_transcript_obj, 'is_translatable', False):
            try:
                trans_obj = detected_transcript_obj.translate(target_lang)
                snippets = trans_obj.fetch()
                clean_lines = []
                for s in snippets:
                    t = getattr(s, 'text', '') or (s.get('text', '') if isinstance(s, dict) else '')
                    t = re.sub(r'\[.*?\]', '', t)
                    t = re.sub(r'\(.*?\)', '', t)
                    t = re.sub(r'\s+', ' ', t).strip()
                    if t:
                        clean_lines.append(t)
                if clean_lines:
                    current_paragraph = " ".join(clean_lines)
                    current_lang = target_lang
                    current_lang_name = LANGUAGES.get(target_lang, target_lang.upper())
                    translated = True
            except Exception:
                pass

        if not translated:
            try:
                translated_text = translate_paragraph(original_paragraph, target_lang)
                if translated_text and translated_text != original_paragraph:
                    current_paragraph = translated_text
                    current_lang = target_lang
                    current_lang_name = LANGUAGES.get(target_lang, target_lang.upper())
            except Exception:
                pass

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
