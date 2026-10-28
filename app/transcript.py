import re
import json
import time
import urllib.parse
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Dict, Any, List, Optional
import requests
import yt_dlp
import os

from app.config import DOWNLOAD_DIR
from app.downloader import (
    get_cookie_opts, 
    get_cached_metadata, 
    get_proxy_attempts, 
    normalize_youtube_url, 
    get_configured_proxy
)

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

# In-memory high-speed transcript caches (15 min TTL)
_TRANSCRIPT_CACHE: Dict[str, Dict[str, Any]] = {}
_ORIGINAL_CACHE: Dict[str, Dict[str, Any]] = {}
TRANSCRIPT_CACHE_TTL = 900

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
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}

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

def parse_timedtext_content(raw_content: str, ext: str = "json3") -> str:
    """
    Universal parser for all YouTube caption formats: JSON3, XML/SRV1/SRV2/SRV3/TTML, and VTT/SRT.
    Strips noise, sound effects, music symbols, and returns a clean coherent text paragraph.
    """
    clean_text = ""
    stripped = raw_content.strip()

    # 1. JSON3 format parser
    if ext == 'json3' or stripped.startswith('{'):
        try:
            jdata = json.loads(stripped)
            events = jdata.get('events', [])
            words = []
            for ev in events:
                for seg in ev.get('segs', []):
                    w = seg.get('utf8', '').strip()
                    if w and w != '\n':
                        words.append(w)
            clean_text = ' '.join(words)
        except Exception:
            pass

    # 2. XML / TTML / SRV format parser
    if not clean_text and ('<transcript' in stripped or '<text' in stripped or '<p ' in stripped or '<body' in stripped):
        try:
            cleaned_xml = re.sub(r'\sxmlns(:\w+)?="[^"]+"', '', stripped)
            root = ET.fromstring(cleaned_xml)
            words = []
            for elem in root.iter():
                if elem.tag in ['text', 'p', 's'] and elem.text:
                    t = elem.text.strip()
                    if t:
                        words.append(t)
            clean_text = ' '.join(words)
        except Exception:
            text_matches = re.findall(r'<text[^>]*>(.*?)</text>', stripped, re.DOTALL)
            if not text_matches:
                text_matches = re.findall(r'<p[^>]*>(.*?)</p>', stripped, re.DOTALL)
            if text_matches:
                clean_text = ' '.join([re.sub(r'<[^>]+>', '', m).strip() for m in text_matches if m.strip()])

    # 3. VTT / SRT format parser
    if not clean_text:
        t = re.sub(r'WEBVTT[^\r\n]*', '', stripped)
        t = re.sub(r'(?:\d{2}:)?\d{2}:\d{2}\.\d{3}\s*-->\s*(?:\d{2}:)?\d{2}:\d{2}\.\d{3}[^\r\n]*', '', t)
        t = re.sub(r'<[^>]+>', '', t)
        clean_text = t

    # Clean acoustic cues, brackets, musical signs
    clean_text = re.sub(r'\[.*?\]', '', clean_text)
    clean_text = re.sub(r'\(.*?\)', '', clean_text)
    clean_text = re.sub(r'[♪♫#♬]+', '', clean_text)
    clean_text = re.sub(r'\s+([.,?!۔।])', r'\1', clean_text)
    clean_text = re.sub(r'\s+', ' ', clean_text).strip()

    return clean_text

def get_video_transcript(url: str, target_lang: str = "original") -> Dict[str, Any]:
    """
    Ultra-resilient, lightning-fast speech transcript generator.
    1. Checks in-memory transcript cache for instant 0.001s return.
    2. Reuses downloader metadata cache if video was already queried.
    3. Multi-tier direct Innertube fetch with zero dead proxy bottleneck.
    4. Universal multi-format parser (JSON3, XML/SRV, VTT).
    5. Automatic transparent client-side browser fetch fallback if YouTube blocks datacenter IP.
    """
    video_id = extract_youtube_id(url)
    if not video_id:
        raise ValueError("Invalid YouTube URL. Please enter a valid YouTube video link.")

    cache_key = f"{video_id}_{target_lang}"
    now = time.time()
    
    # 1. Instant Transcript Cache Check (0.001s)
    cached_trans = _TRANSCRIPT_CACHE.get(cache_key)
    if cached_trans and (now - cached_trans.get('timestamp', 0) < TRANSCRIPT_CACHE_TTL):
        return cached_trans['data']

    # 2. Check if we already have the original transcript cached for this video
    base_trans = _ORIGINAL_CACHE.get(video_id)
    if not base_trans or (now - base_trans.get('timestamp', 0) >= TRANSCRIPT_CACHE_TTL):
        # Fetch authentic video title via fast Google oEmbed API
        video_title = "YouTube Video"
        try:
            oembed_url = f"https://www.youtube.com/oembed?url=https://www.youtube.com/watch?v={video_id}&format=json"
            oembed_resp = requests.get(oembed_url, timeout=3)
            if oembed_resp.status_code == 200:
                video_title = oembed_resp.json().get('title') or video_title
        except Exception:
            pass

        info = None
        last_err = None
        watch_url = f"https://www.youtube.com/watch?v={video_id}"

        # 3. Check high-speed downloader metadata cache first (saves 3-4 seconds!)
        cached_meta = get_cached_metadata(watch_url)
        if cached_meta and cached_meta.get('raw_info'):
            cand = cached_meta['raw_info']
            if cand.get('subtitles') or cand.get('automatic_captions'):
                info = cand

        # 4. If not in metadata cache, query YouTube directly with fast client pipeline
        if not info:
            cookie_opts = get_cookie_opts()
            base_ydl_opts: Dict[str, Any] = {
                'quiet': True,
                'no_warnings': True,
                'skip_download': True,
                'writesubtitles': True,
                'writeautomaticsub': True,
                'format': 'all/none',
                'socket_timeout': 5,
            }
            if cookie_opts:
                base_ydl_opts.update(cookie_opts)

            proxy_attempts = get_proxy_attempts()
            client_attempts = ['visionos', 'android', 'ios', 'web']

            for p in proxy_attempts:
                for client in client_attempts:
                    run_opts = dict(base_ydl_opts)
                    run_opts['extractor_args'] = {'youtube': {'player_client': [client]}}
                    if p:
                        run_opts['proxy'] = p
                    try:
                        with yt_dlp.YoutubeDL(run_opts) as ydl:
                            cand = ydl.extract_info(watch_url, download=False)
                            if cand and (cand.get('subtitles') or cand.get('automatic_captions')):
                                info = cand
                                break
                    except Exception as e:
                        last_err = e
                        continue
                if info:
                    break

        if not info:
            err_str = str(last_err) if last_err else "Could not connect to YouTube."
            raise ValueError(f"Could not connect to YouTube servers: {err_str}")

        if not video_title or video_title == "YouTube Video":
            video_title = info.get('title') or video_title

        subs = info.get('subtitles') or {}
        auto = info.get('automatic_captions') or {}

        # Prioritize manual subtitles if available, else automatic captions
        target_caps = subs if subs else auto

        if not target_caps:
            raise ValueError("No speech dialogue or subtitles found in this YouTube video (this may be an instrumental music video, or the channel has disabled auto-captions).")

        chosen_fmt = None
        detected_lang = "en"

        # Search original tracks: English, original language, or first available spoken track
        pref_langs = ['en', 'en-orig', 'en-US', 'en-GB', 'ur', 'hi'] + list(target_caps.keys())

        for code in pref_langs:
            if code in target_caps:
                detected_lang = code.split('-')[0]
                fmts = target_caps[code]
                chosen_fmt = (
                    next((f for f in fmts if f.get('ext') == 'json3'), None) or
                    next((f for f in fmts if f.get('ext') == 'vtt'), None) or
                    next((f for f in fmts if f.get('ext') in ['srv1', 'srv2', 'srv3', 'ttml']), None) or
                    (fmts[0] if fmts else None)
                )
                if chosen_fmt and chosen_fmt.get('url'):
                    break

        if not chosen_fmt or not chosen_fmt.get('url'):
            raise ValueError("Speech captions could not be formatted for this video.")

        cap_url = chosen_fmt.get('url')
        original_lang_name = LANGUAGES.get(detected_lang, detected_lang.upper())

        # 5. Fetch timedtext content using multi-tier bypass
        raw_content = ""
        req_headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36',
            'Accept': '*/*',
            'Accept-Language': 'en-US,en;q=0.9',
        }

        # Technique 1: Standard high-speed HTTP GET
        try:
            resp = requests.get(cap_url, headers=req_headers, timeout=6)
            if resp.status_code == 200 and len(resp.text) > 20 and not resp.text.startswith('<html>'):
                raw_content = resp.text
        except Exception:
            pass

        # Technique 2: curl_cffi with Chrome browser impersonation
        if not raw_content:
            try:
                from curl_cffi import requests as c_requests
                c_resp = c_requests.get(cap_url, impersonate='chrome120', timeout=6)
                if c_resp.status_code == 200 and len(c_resp.text) > 20 and not c_resp.text.startswith('<html>'):
                    raw_content = c_resp.text
            except Exception:
                pass

        # Technique 3: If server gets blocked (429), deliver signed cap_url for instant client browser fetch
        if not raw_content:
            return {
                "success": True,
                "need_client_fetch": True,
                "video_title": video_title,
                "video_id": video_id,
                "caption_url": cap_url,
                "detected_lang": detected_lang,
                "original_lang_name": original_lang_name,
                "current_lang": detected_lang,
                "current_lang_name": f"{original_lang_name} (Original)",
                "languages": LANGUAGES
            }

        fmt_ext = chosen_fmt.get('ext') or 'json3'
        original_paragraph = parse_timedtext_content(raw_content, ext=fmt_ext)

        if not original_paragraph:
            raise ValueError("Could not extract speech text from the captions track.")

        base_data = {
            "success": True,
            "video_title": video_title,
            "video_id": video_id,
            "original_lang": detected_lang,
            "original_lang_name": original_lang_name,
            "current_lang": detected_lang,
            "current_lang_name": f"{original_lang_name} (Original)",
            "paragraph": original_paragraph,
            "languages": LANGUAGES
        }

        _ORIGINAL_CACHE[video_id] = {
            'timestamp': time.time(),
            'data': base_data
        }
        base_trans = _ORIGINAL_CACHE[video_id]

    base_data = base_trans['data']
    orig_text = base_data['paragraph']
    orig_lang = base_data['original_lang']
    orig_lang_name = base_data['original_lang_name']
    video_title = base_data['video_title']

    # 6. Deliver requested language
    if target_lang in ["original", "default", orig_lang]:
        result_data = dict(base_data)
    else:
        # High-speed translation
        translated_text = orig_text
        try:
            trans = translate_paragraph(orig_text, target_lang)
            if trans and trans.strip():
                translated_text = trans
        except Exception:
            pass

        target_name = LANGUAGES.get(target_lang, target_lang.upper())
        result_data = {
            "success": True,
            "video_title": video_title,
            "video_id": video_id,
            "original_lang": orig_lang,
            "original_lang_name": orig_lang_name,
            "current_lang": target_lang,
            "current_lang_name": target_name,
            "paragraph": translated_text,
            "languages": LANGUAGES
        }

    # Cache for future instant retrieval
    _TRANSCRIPT_CACHE[cache_key] = {
        'timestamp': time.time(),
        'data': result_data
    }

    return result_data
