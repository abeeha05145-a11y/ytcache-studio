import subprocess
import shutil
import urllib.parse
from pathlib import Path
from typing import AsyncGenerator, Dict, Any, Optional
import yt_dlp
import asyncio
from app.downloader import get_cookie_opts, normalize_youtube_url, clean_filename, get_cached_metadata, PRIMARY_PROXY, PROXIES_POOL

async def create_media_stream(
    url: str,
    download_type: str = "video",
    height: Optional[int] = None,
    audio_format: Optional[str] = None
) -> tuple[AsyncGenerator[bytes, None], str, str]:
    """
    Zero-disk piped streaming engine.
    Streams media in real-time from YouTube CDN directly to user's browser.
    Server disk space used: EXACTLY 0 MB.
    """
    clean_url = normalize_youtube_url(url)
    
    # 1. Check in-memory metadata cache for instant retrieval
    cached = get_cached_metadata(clean_url)
    info = cached.get('raw_info') if cached else None

    if not info:
        cookie_opts = get_cookie_opts()
        ydl_opts = {
            'quiet': True,
            'no_warnings': True,
            'skip_download': True,
            'socket_timeout': 6,
            'proxy': PRIMARY_PROXY,
            'extractor_args': {
                'youtube': {
                    'player_client': ['visionos']
                }
            }
        }
        if cookie_opts:
            ydl_opts.update(cookie_opts)

        def _extract():
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                return ydl.extract_info(clean_url, download=False)

        try:
            info = await asyncio.to_thread(_extract)
        except Exception:
            ydl_opts['proxy'] = PROXIES_POOL[1]
            info = await asyncio.to_thread(_extract)

    if not info:
        raise ValueError("Could not extract media streams from YouTube.")

    title = clean_filename(info.get('title', 'YouTube_Video'))[:80]
    fmts = info.get('formats', [])

    if download_type == 'audio':
        a_fmts = [f for f in fmts if f.get('vcodec') == 'none' and f.get('acodec') != 'none' and f.get('url')]
        if not a_fmts:
            raise ValueError("No audio streams found for this video.")
        best_a = max(a_fmts, key=lambda f: f.get('abr') or f.get('tbr') or 0)
        
        filename = f"{title}.mp3" if audio_format in ['mp3_320', 'mp3_192', None] else f"{title}.m4a"
        media_type = "audio/mpeg" if filename.endswith('.mp3') else "audio/mp4"

        cmd = [
            'ffmpeg',
            '-y',
            '-loglevel', 'error',
            '-reconnect', '1',
            '-reconnect_streamed', '1',
            '-reconnect_delay_max', '5',
            '-i', best_a['url'],
            '-vn',
            '-c:a', 'libmp3lame',
            '-b:a', '320k' if audio_format == 'mp3_320' else '192k',
            '-f', 'mp3',
            'pipe:1'
        ]

    elif download_type == 'video_only':
        v_fmts = [f for f in fmts if f.get('vcodec') != 'none' and f.get('url')]
        if height:
            matching = [f for f in v_fmts if (f.get('height') or 0) <= height or (f.get('width') or 0) <= height]
            best_v = max(matching, key=lambda f: f.get('height') or 0) if matching else max(v_fmts, key=lambda f: f.get('height') or 0)
        else:
            best_v = max(v_fmts, key=lambda f: f.get('height') or 0)

        filename = f"{title}_{best_v.get('height', 720)}p_Visuals.mp4"
        media_type = "video/mp4"

        cmd = [
            'ffmpeg',
            '-y',
            '-loglevel', 'error',
            '-reconnect', '1',
            '-reconnect_streamed', '1',
            '-reconnect_delay_max', '5',
            '-i', best_v['url'],
            '-an',
            '-c:v', 'copy',
            '-movflags', 'frag_keyframe+empty_moov+default_base_moof',
            '-f', 'mp4',
            'pipe:1'
        ]

    else:
        v_fmts = [f for f in fmts if f.get('vcodec') != 'none' and f.get('url')]
        a_fmts = [f for f in fmts if f.get('vcodec') == 'none' and f.get('acodec') != 'none' and f.get('url')]
        
        if height:
            matching = [f for f in v_fmts if (f.get('height') or 0) <= height or (f.get('width') or 0) <= height]
            best_v = max(matching, key=lambda f: f.get('height') or 0) if matching else max(v_fmts, key=lambda f: f.get('height') or 0)
        else:
            best_v = max(v_fmts, key=lambda f: f.get('height') or 0)

        best_a = max(a_fmts, key=lambda f: f.get('abr') or f.get('tbr') or 0) if a_fmts else None

        filename = f"{title}_{best_v.get('height', 720)}p.mp4"
        media_type = "video/mp4"

        if best_a:
            cmd = [
                'ffmpeg',
                '-y',
                '-loglevel', 'error',
                '-reconnect', '1',
                '-reconnect_streamed', '1',
                '-reconnect_delay_max', '5',
                '-i', best_v['url'],
                '-i', best_a['url'],
                '-c', 'copy',
                '-movflags', 'frag_keyframe+empty_moov+default_base_moof',
                '-f', 'mp4',
                'pipe:1'
            ]
        else:
            cmd = [
                'ffmpeg',
                '-y',
                '-loglevel', 'error',
                '-reconnect', '1',
                '-reconnect_streamed', '1',
                '-reconnect_delay_max', '5',
                '-i', best_v['url'],
                '-c', 'copy',
                '-movflags', 'frag_keyframe+empty_moov+default_base_moof',
                '-f', 'mp4',
                'pipe:1'
            ]

    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, bufsize=128 * 1024)

    async def stream_generator():
        try:
            loop = asyncio.get_event_loop()
            while True:
                chunk = await loop.run_in_executor(None, proc.stdout.read, 128 * 1024)
                if not chunk:
                    break
                yield chunk
        finally:
            try:
                proc.terminate()
            except Exception:
                pass

    return stream_generator(), filename, media_type
