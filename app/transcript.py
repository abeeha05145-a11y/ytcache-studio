import re
import json
import urllib.parse
import http.cookiejar
from pathlib import Path
from typing import Dict, Any, List, Optional
import requests
import yt_dlp
import os
from youtube_transcript_api import YouTubeTranscriptApi
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

def get_cookie_jar() -> Optional[http.cookiejar.MozillaCookieJar]:
    """
    Loads netscape cookie file into a MozillaCookieJar with session and secure cookies intact.
    """
    search_dirs = [
        Path("/app"),
        Path("."),
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
                try:
                    cj = http.cookiejar.MozillaCookieJar(str(p.resolve()))
                    cj.load(ignore_discard=True, ignore_expires=True)
                    return cj
                except Exception:
                    pass
        try:
            for p in d.glob("*cookie*.txt"):
                if p.exists() and p.stat().st_size > 0:
                    cj = http.cookiejar.MozillaCookieJar(str(p.resolve()))
                    cj.load(ignore_discard=True, ignore_expires=True)
                    return cj
        except Exception:
            pass
    
    env_cookies = os.getenv("YOUTUBE_COOKIES")
    if env_cookies and len(env_cookies.strip()) > 10:
        tmp_path = DOWNLOAD_DIR / "yt_cookies.txt"
        try:
            content = env_cookies.strip().replace('\\r\\n', '\n').replace('\\n', '\n').replace('\\t', '\t')
            tmp_path.write_text(content, encoding="utf-8")
            cj = http.cookiejar.MozillaCookieJar(str(tmp_path.resolve()))
            cj.load(ignore_discard=True, ignore_expires=True)
            return cj
        except Exception:
            pass
    return None

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
    Fast and bulletproof speech transcript extractor.
    Combines YouTube Transcript API with official authenticated cookie session and Google oEmbed.
    """
    video_id = extract_youtube_id(url)
    if not video_id:
        raise ValueError("Invalid YouTube URL. Please enter a valid YouTube video link.")

    # 1. Fetch authentic video title via fast Google oEmbed API
    video_title = "YouTube Video"
    try:
        oembed_url = f"https://www.youtube.com/oembed?url=https://www.youtube.com/watch?v={video_id}&format=json"
        oembed_resp = requests.get(oembed_url, timeout=5)
        if oembed_resp.status_code == 200:
            video_title = oembed_resp.json().get('title') or video_title
    except Exception:
        pass

    # 2. Build authenticated HTTP session with cookies to bypass datacenter IP restrictions
    session = requests.Session()
    session.headers.update({
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36',
        'Accept-Language': 'en-US,en;q=0.9',
    })
    cj = get_cookie_jar()
    if cj:
        session.cookies = cj

    raw_text = ""
    detected_lang = "en"
    last_err = None

    # 3. Primary extraction: YouTubeTranscriptApi with authenticated session
    try:
        api = YouTubeTranscriptApi(http_client=session)
        t_list = api.list(video_id)
        
        pref_langs = []
        if target_lang and target_lang not in ["original", "default"]:
            pref_langs.append(target_lang)
        pref_langs += ['en', 'en-orig', 'en-US', 'ur', 'hi']

        fetched_obj = None
        for lang_code in pref_langs:
            try:
                fetched_obj = t_list.find_transcript([lang_code])
                detected_lang = fetched_obj.language_code.split('-')[0]
                break
            except Exception:
                continue

        if not fetched_obj:
            for t in t_list:
                fetched_obj = t
                detected_lang = t.language_code.split('-')[0]
                break

        if fetched_obj:
            items = fetched_obj.fetch()
            words = []
            for item in items:
                if isinstance(item, dict):
                    w = item.get('text', '')
                elif hasattr(item, 'text'):
                    w = item.text
                else:
                    w = str(item)
                if w:
                    words.append(w)
            raw_text = " ".join(words)
    except Exception as e:
        last_err = e

    # 4. Secondary fallback: yt-dlp timedtext extraction
    if not raw_text:
        try:
            ydl_opts: Dict[str, Any] = {
                'quiet': True,
                'no_warnings': True,
                'skip_download': True,
                'writesubtitles': True,
                'writeautomaticsub': True,
                'format': 'all/none',
                'extractor_args': {'youtube': {'player_client': ['android']}},
            }
            if cj and hasattr(cj, 'filename') and cj.filename:
                ydl_opts['cookiefile'] = cj.filename

            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(f"https://www.youtube.com/watch?v={video_id}", download=False)
                if not video_title or video_title == "YouTube Video":
                    video_title = info.get('title', video_title)
                
                subs = info.get('subtitles') or {}
                auto = info.get('automatic_captions') or {}
                caps = subs if subs else auto

                if caps:
                    track = caps.get('en') or caps.get('ur') or caps.get('hi') or list(caps.values())[0]
                    chosen_fmt = next((f for f in track if f.get('ext') == 'json3'), track[0])
                    raw_bytes = ydl.urlopen(chosen_fmt['url']).read()
                    data = json.loads(raw_bytes.decode('utf-8', errors='ignore'))
                    words = []
                    for ev in data.get('events', []):
                        for s in ev.get('segs', []):
                            if s.get('utf8'):
                                words.append(s['utf8'])
                    raw_text = " ".join(words)
        except Exception as e:
            if not last_err:
                last_err = e

    if not raw_text:
        raise ValueError("No speech transcript or subtitles found for this video. YouTube may not have auto-captions available.")

    # 5. Clean text: remove sound effects, music notes, bracketed text, formatting noise
    raw_text = re.sub(r'\[.*?\]', '', raw_text)
    raw_text = re.sub(r'\(.*?\)', '', raw_text)
    raw_text = re.sub(r'[♪♫#]+', '', raw_text)
    raw_text = re.sub(r'\s+([.,?!])', r'\1', raw_text)
    original_paragraph = re.sub(r'\s+', ' ', raw_text).strip()

    if not original_paragraph:
        raise ValueError("Could not extract speech text from captions.")

    original_lang_name = LANGUAGES.get(detected_lang, detected_lang.upper())
    current_paragraph = original_paragraph
    current_lang = detected_lang
    current_lang_name = f"{original_lang_name} (Original)"

    # 6. Translate if target language is requested and different
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
