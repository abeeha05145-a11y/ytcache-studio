import re
import urllib.parse
from pathlib import Path
from typing import Dict, Any, List, Optional
import requests
import yt_dlp
import os
from app.config import DOWNLOAD_DIR

CHROME_TARGET = None

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

def get_cookie_opts() -> Dict[str, Any]:
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
    video_id = extract_youtube_id(url)
    if not video_id:
        raise ValueError("Invalid YouTube URL. Please enter a valid YouTube video link.")

    cookie_opts = get_cookie_opts()
    ydl_opts = {
        'quiet': True,
        'no_warnings': True,
        'skip_download': True,
    }
    if cookie_opts:
        ydl_opts.update(cookie_opts)

    info = None
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        try:
            info = ydl.extract_info(f"https://www.youtube.com/watch?v={video_id}", download=False)
        except Exception as e:
            raise ValueError(f"Could not contact YouTube servers: {e}")

    if not info:
        raise ValueError("No video information found on YouTube.")

    video_title = info.get('title', 'YouTube Video')
    subs = info.get('subtitles') or {}
    auto = info.get('automatic_captions') or {}

    chosen_fmt = None
    detected_lang = "en"

    # 1. Search manual subtitles first
    if subs:
        for k in ['en', 'en-orig', 'en-US', 'en-GB', 'ur', 'hi'] + list(subs.keys()):
            if k in subs:
                detected_lang = k.split('-')[0]
                fmts = subs[k]
                chosen_fmt = next((f for f in fmts if f.get('ext') == 'json3'), None) or fmts[0]
                break

    # 2. Search automatic subtitles
    if not chosen_fmt and auto:
        for k in ['en', 'en-orig', 'en-US', 'en-GB', 'ur', 'hi']:
            if k in auto:
                detected_lang = k.split('-')[0]
                fmts = auto[k]
                chosen_fmt = next((f for f in fmts if f.get('ext') == 'json3'), None) or fmts[0]
                break
        if not chosen_fmt:
            first_k = list(auto.keys())[0]
            detected_lang = first_k.split('-')[0]
            fmts = auto[first_k]
            chosen_fmt = next((f for f in fmts if f.get('ext') == 'json3'), None) or fmts[0]

    if not chosen_fmt or not chosen_fmt.get('url'):
        raise ValueError("No speech transcript or subtitles are available for this video.")

    # Fetch pre-authenticated, signed caption track directly from YouTube CDN
    cap_url = chosen_fmt.get('url')
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36'
    }
    resp = requests.get(cap_url, headers=headers, timeout=8)
    if resp.status_code != 200:
        raise ValueError("Could not download subtitles stream from YouTube.")

    raw_text = ""
    if chosen_fmt.get('ext') == 'json3':
        try:
            jdata = resp.json()
            events = jdata.get('events', [])
            words = []
            for ev in events:
                for seg in ev.get('segs', []):
                    w = seg.get('utf8', '').strip()
                    if w and w != '\n':
                        words.append(w)
            raw_text = ' '.join(words)
        except Exception as e:
            raise ValueError(f"Failed to parse caption JSON: {e}")
    else:
        # VTT / SRT format
        t = re.sub(r'<[^>]+>', '', resp.text)
        t = re.sub(r'(?:\d{2}:)?\d{2}:\d{2}\.\d{3}\s*-->\s*(?:\d{2}:)?\d{2}:\d{2}\.\d{3}[^\r\n]*', '', t)
        raw_text = t

    raw_text = re.sub(r'\[.*?\]', '', raw_text)
    raw_text = re.sub(r'\(.*?\)', '', raw_text)
    raw_text = re.sub(r'[♪♫#]+', '', raw_text)
    raw_text = re.sub(r'\s+([.,?!])', r'\1', raw_text)
    original_paragraph = re.sub(r'\s+', ' ', raw_text).strip()

    if not original_paragraph:
        raise ValueError("No speech transcript or subtitles are available for this video.")

    original_lang_name = LANGUAGES.get(detected_lang, detected_lang.upper())
    current_paragraph = original_paragraph
    current_lang = detected_lang
    current_lang_name = f"{original_lang_name} (Original)"

    # Translate if target language is different
    if target_lang not in ["original", "default", detected_lang]:
        try:
            trans = translate_paragraph(original_paragraph, target_lang)
            if trans and trans != original_paragraph:
                current_paragraph = trans
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
