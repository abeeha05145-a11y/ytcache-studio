import re
import urllib.parse
import uuid
from pathlib import Path
from typing import Dict, Any, List, Optional
import requests
import yt_dlp
import os
from youtube_transcript_api import YouTubeTranscriptApi
from app.config import DOWNLOAD_DIR

CHROME_TARGET = None

def get_cookie_opts() -> Dict[str, Any]:
    """Detect cookies.txt / www.youtube.com_cookies.txt or YOUTUBE_COOKIES env var."""
    search_dirs = [Path("."), Path("/app"), Path(__file__).resolve().parent.parent, Path(__file__).resolve().parent]
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
                return {'cookiefile': str(p.resolve())}
        try:
            for p in d.glob("*cookie*.txt"):
                if p.exists() and p.stat().st_size > 0:
                    return {'cookiefile': str(p.resolve())}
        except Exception:
            pass
    
    env_cookies = os.getenv("YOUTUBE_COOKIES")
    if env_cookies and len(env_cookies.strip()) > 10:
        tmp_path = DOWNLOAD_DIR / "yt_cookies.txt"
        try:
            content = env_cookies.strip().replace('\\r\\n', '\n').replace('\\n', '\n').replace('\\t', '\t')
            tmp_path.write_text(content, encoding="utf-8")
            return {'cookiefile': str(tmp_path.resolve())}
        except Exception:
            pass
    return {}

PROXIES_POOL = [
    "http://dxgwkmac:ul130busmnzq@64.137.10.153:5803",
    "http://dxgwkmac:ul130busmnzq@191.96.254.138:6185",
    "http://dxgwkmac:ul130busmnzq@38.154.185.97:6370",
    "http://dxgwkmac:ul130busmnzq@198.23.243.226:6361",
    "http://dxgwkmac:ul130busmnzq@45.38.107.97:6014"
]

def get_proxy_list() -> List[Optional[str]]:
    env_p = os.getenv("PROXY_URL") or os.getenv("HTTP_PROXY") or os.getenv("HTTPS_PROXY")
    if env_p and len(env_p.strip()) > 5:
        return [env_p.strip()] + PROXIES_POOL
    return list(PROXIES_POOL)

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

def fetch_video_title(video_id: str) -> str:
    """Fetch video title using lightning-fast YouTube oEmbed (no auth / no rate limits)."""
    try:
        url = f"https://www.youtube.com/oembed?url=https://www.youtube.com/watch?v={video_id}&format=json"
        r = requests.get(url, timeout=5)
        if r.status_code == 200:
            return r.json().get('title', 'YouTube Video')
    except Exception:
        pass
    return "YouTube Video"

def translate_paragraph(text: str, target_lang: str) -> str:
    """
    Translates paragraph text into target language using Google Translate API.
    Splits into safe chunks to avoid URL length restrictions.
    """
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
            resp = requests.get(url, headers=headers, timeout=8)
            if resp.status_code == 200:
                data = resp.json()
                translated_pieces = [p[0] for p in data[0] if p and p[0]]
                translated_chunks.append("".join(translated_pieces))
            else:
                translated_chunks.append(chunk)
        except Exception as e:
            translated_chunks.append(chunk)

    return " ".join(translated_chunks)

def get_video_transcript(url: str, target_lang: str = "original") -> Dict[str, Any]:
    """
    High-speed, robust speech transcript extractor.
    Uses official YouTube transcript streams (direct + proxy pool).
    Takes < 1 second, zero disk downloads.
    """
    video_id = extract_youtube_id(url)
    if not video_id:
        raise ValueError("Invalid YouTube URL. Please enter a valid YouTube video link.")

    video_title = fetch_video_title(video_id)
    original_paragraph = ""
    detected_lang = "en"
    detected_transcript_obj = None

    # First try direct connection, then working proxies
    sessions_to_try = [None] + get_proxy_list()

    for proxy in sessions_to_try:
        try:
            http_client = None
            if proxy:
                http_client = requests.Session()
                http_client.proxies = {'http': proxy, 'https': proxy}

            api = YouTubeTranscriptApi(http_client=http_client)
            transcript_list = api.list(video_id)

            chosen_t = None
            # Check for preferred language matches
            pref_codes = [target_lang, 'en', 'ur', 'hi'] if target_lang not in ["original", "default"] else ['en', 'ur', 'hi']
            for code in pref_codes:
                try:
                    chosen_t = transcript_list.find_transcript([code])
                    if chosen_t:
                        break
                except Exception:
                    pass

            # Fallback to any transcript available
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
        except Exception as e:
            continue

    # Fallback to yt-dlp metadata caption extractor if API was blocked
    if not original_paragraph:
        try:
            cookie_opts = get_cookie_opts()
            ydl_opts = {
                'quiet': True,
                'no_warnings': True,
                'skip_download': True,
            }
            if cookie_opts:
                ydl_opts.update(cookie_opts)

            proxies_to_try = [None] + get_proxy_list()
            for p in proxies_to_try:
                run_opts = dict(ydl_opts)
                if p:
                    run_opts['proxy'] = p
                try:
                    with yt_dlp.YoutubeDL(run_opts) as ydl:
                        info = ydl.extract_info(f"https://www.youtube.com/watch?v={video_id}", download=False)
                        if info:
                            if not video_title or video_title == "YouTube Video":
                                video_title = info.get('title', 'YouTube Video')
                            subs = info.get('subtitles') or info.get('automatic_captions') or {}
                            target_caps = None
                            for code in ['en', 'ur', 'hi']:
                                if code in subs:
                                    target_caps = subs[code]
                                    detected_lang = code
                                    break
                            if not target_caps and subs:
                                first_k = list(subs.keys())[0]
                                target_caps = subs[first_k]
                                detected_lang = first_k

                            if target_caps:
                                chosen_fmt = next((f for f in target_caps if f.get('ext') == 'json3'), None) or target_caps[0]
                                cap_url = chosen_fmt.get('url')
                                if cap_url:
                                    cap_resp = requests.get(cap_url, timeout=6)
                                    if cap_resp.status_code == 200:
                                        if chosen_fmt.get('ext') == 'json3':
                                            jdata = cap_resp.json()
                                            events = jdata.get('events', [])
                                            lines = []
                                            for ev in events:
                                                for seg in ev.get('segs', []):
                                                    st = seg.get('utf8', '').strip()
                                                    if st and st != '\n':
                                                        lines.append(st)
                                            original_paragraph = " ".join(lines)
                                        else:
                                            # Clean VTT
                                            t = re.sub(r'<[^>]+>', '', cap_resp.text)
                                            t = re.sub(r'(?:\d{2}:)?\d{2}:\d{2}\.\d{3}\s*-->\s*(?:\d{2}:)?\d{2}:\d{2}\.\d{3}[^\r\n]*', '', t)
                                            t = re.sub(r'\[.*?\]', '', t)
                                            original_paragraph = re.sub(r'\s+', ' ', t).strip()
                                        if original_paragraph:
                                            break
                except Exception:
                    continue
        except Exception:
            pass

    if not original_paragraph:
        raise ValueError("No speech transcript or subtitles are available for this video.")

    original_lang_name = LANGUAGES.get(detected_lang, detected_lang.upper())
    current_paragraph = original_paragraph
    current_lang = detected_lang
    current_lang_name = f"{original_lang_name} (Original)"

    # Handle Translation
    if target_lang not in ["original", "default", detected_lang]:
        translated = False
        # 1. Try YouTube official translation track
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

        # 2. Try Google Translate fallback
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
