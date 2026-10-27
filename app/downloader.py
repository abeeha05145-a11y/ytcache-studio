import os
import re
import math
import time
import shutil
import asyncio
from pathlib import Path
from typing import Dict, Any, List, Optional
import yt_dlp

from app.config import DOWNLOAD_DIR

# Human readable size conversion
def format_bytes(bytes_count: Optional[float]) -> str:
    if not bytes_count or bytes_count <= 0:
        return "Unknown size"
    units = ["B", "KB", "MB", "GB", "TB"]
    i = min(int(math.floor(math.log(bytes_count, 1024))), len(units) - 1)
    p = math.pow(1024, i)
    s = round(bytes_count / p, 2)
    return f"{s} {units[i]}"

# Format duration in seconds to HH:MM:SS or MM:SS
def format_duration(seconds: Optional[int]) -> str:
    if not seconds:
        return "00:00"
    m, s = divmod(seconds, 60)
    h, m = divmod(m, 60)
    if h > 0:
        return f"{h:02d}:{m:02d}:{s:02d}"
    return f"{m:02d}:{s:02d}"

# Check if ffmpeg is available
def is_ffmpeg_available() -> bool:
    return shutil.which("ffmpeg") is not None

# Verified active Webshare proxies pool
PROXIES_POOL = [
    "http://jwdqftrd:qcqth1klolmb@45.38.107.97:6014",
    "http://jwdqftrd:qcqth1klolmb@64.137.96.74:6641",
    "http://jwdqftrd:qcqth1klolmb@198.23.243.226:6361",
    "http://jwdqftrd:qcqth1klolmb@38.154.185.97:6370",
    "http://jwdqftrd:qcqth1klolmb@84.247.60.125:6095",
    "http://jwdqftrd:qcqth1klolmb@191.96.254.138:6185",
    "http://jwdqftrd:qcqth1klolmb@198.46.161.42:5092",
    "http://jwdqftrd:qcqth1klolmb@64.137.10.153:5803"
]

PRIMARY_PROXY = PROXIES_POOL[0]

def get_proxy_list() -> List[Optional[str]]:
    env_p = os.getenv("PROXY_URL") or os.getenv("HTTP_PROXY") or os.getenv("HTTPS_PROXY")
    if env_p and len(env_p.strip()) > 5:
        return [env_p.strip()] + PROXIES_POOL + [None]
    return PROXIES_POOL + [None]

# Global high-speed in-memory metadata cache (15 min TTL)
_METADATA_CACHE: Dict[str, Dict[str, Any]] = {}
CACHE_TTL_SECONDS = 900

def get_cached_metadata(clean_url: str) -> Optional[Dict[str, Any]]:
    cached = _METADATA_CACHE.get(clean_url)
    if cached and (time.time() - cached.get('timestamp', 0) < CACHE_TTL_SECONDS):
        return cached
    return None

def set_cached_metadata(clean_url: str, raw_info: Dict[str, Any], extracted_data: Dict[str, Any], working_proxy: Optional[str] = None):
    _METADATA_CACHE[clean_url] = {
        'timestamp': time.time(),
        'raw_info': raw_info,
        'extracted_data': extracted_data,
        'working_proxy': working_proxy or PRIMARY_PROXY
    }

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

def normalize_youtube_url(url: str) -> str:
    """Normalize YouTube shorts, mobile, and share URLs into standard watch URLs."""
    if not url:
        return url
    m = re.search(r'(?:v=|\/shorts\/|\/v\/|youtu\.be\/)([a-zA-Z0-9_-]{11})', url)
    if m:
        return f"https://www.youtube.com/watch?v={m.group(1)}"
    return url.strip()

def clean_filename(name: str) -> str:
    return re.sub(r'[\\/*?:"<>|]', "", name).strip()

def extract_video_info(url: str, force_refresh: bool = False) -> Dict[str, Any]:
    """
    Extract video metadata with sub-second cache lookup and high-speed primary proxy routing.
    """
    clean_url = normalize_youtube_url(url)
    
    # 1. Instant Cache Return (0.001s)
    if not force_refresh:
        cached = get_cached_metadata(clean_url)
        if cached:
            return cached['extracted_data']

    cookie_opts = get_cookie_opts()
    ydl_opts = {
        'quiet': True,
        'no_warnings': True,
        'extract_flat': False,
        'skip_download': True,
        'socket_timeout': 6,
        'extractor_args': {
            'youtube': {
                'player_client': ['visionos']
            }
        }
    }
    if cookie_opts:
        ydl_opts.update(cookie_opts)

    info = None
    last_err = None
    working_proxy = PRIMARY_PROXY

    # Optimized fast-path: primary proxy with visionos -> fallback to android -> fallback secondary proxy
    attempts = [
        {'client': ['visionos'], 'proxy': PRIMARY_PROXY},
        {'client': ['android'], 'proxy': PRIMARY_PROXY},
        {'client': ['visionos'], 'proxy': PROXIES_POOL[1]},
        {'client': ['android', 'ios'], 'proxy': PROXIES_POOL[2]},
    ]

    for att in attempts:
        run_ydl_opts = dict(ydl_opts)
        run_ydl_opts['extractor_args'] = {'youtube': {'player_client': att['client']}}
        if att['proxy']:
            run_ydl_opts['proxy'] = att['proxy']
        try:
            with yt_dlp.YoutubeDL(run_ydl_opts) as ydl:
                cand = ydl.extract_info(clean_url, download=False)
                if cand and cand.get('formats'):
                    info = cand
                    working_proxy = att['proxy']
                    break
        except Exception as e:
            last_err = e
            continue

    if not info:
        err_msg = str(last_err) if last_err else "No video information found."
        if "Private video" in err_msg or "private" in err_msg.lower():
            raise ValueError("This video is private and cannot be downloaded.")
        elif "Video unavailable" in err_msg or "unavailable" in err_msg.lower():
            raise ValueError("Video is unavailable or has been removed from YouTube.")
        elif "Sign in to confirm your age" in err_msg:
            raise ValueError("This video is age-restricted and requires authentication.")
        elif "Incomplete YouTube ID" in err_msg or "is not a valid URL" in err_msg:
            raise ValueError("Please provide a valid YouTube video link.")
        else:
            raise ValueError(f"Could not fetch video info: {err_msg}")

    formats = info.get('formats', [])
    duration = info.get('duration', 0)
    
    # Target standard resolutions we look for (from 4K down to 144p)
    standard_res = [
        {"height": 2160, "name": "4K Ultra HD", "badge": "4K"},
        {"height": 1440, "name": "2K Quad HD", "badge": "2K"},
        {"height": 1080, "name": "1080p Full HD", "badge": "FHD"},
        {"height": 720, "name": "720p HD", "badge": "HD"},
        {"height": 480, "name": "480p SD", "badge": "SD"},
        {"height": 360, "name": "360p Medium", "badge": "360p"},
        {"height": 240, "name": "240p Low", "badge": "240p"},
        {"height": 144, "name": "144p Lowest", "badge": "144p"},
    ]

    audio_formats = [
        f for f in formats 
        if f.get('vcodec') == 'none' and f.get('acodec') != 'none'
    ]
    best_audio = max(audio_formats, key=lambda f: f.get('tbr', 0) or f.get('abr', 0) or 0) if audio_formats else None
    best_audio_size = best_audio.get('filesize') or best_audio.get('filesize_approx') if best_audio else None
    if not best_audio_size and duration and best_audio:
        abr = best_audio.get('abr') or 128
        best_audio_size = (abr * 1024 * duration) / 8

    def get_effective_height(fmt: dict) -> int:
        w = fmt.get('width') or 0
        h = fmt.get('height') or 0
        if w and h:
            return min(w, h)
        return h or w or 0

    available_videos = []
    available_video_only = []
    seen_heights = set()

    for res in standard_res:
        target_h = res["height"]
        
        matching_formats = [
            f for f in formats 
            if f.get('vcodec') != 'none' and abs(get_effective_height(f) - target_h) <= 25
        ]

        if not matching_formats:
            continue

        best_video_fmt = max(
            matching_formats, 
            key=lambda f: (f.get('fps', 0) or 0, f.get('vbr', 0) or f.get('tbr', 0) or 0)
        )

        video_size = best_video_fmt.get('filesize') or best_video_fmt.get('filesize_approx')
        if not video_size and duration:
            vbr = best_video_fmt.get('vbr') or best_video_fmt.get('tbr') or 0
            if vbr:
                video_size = (vbr * 1024 * duration) / 8

        total_estimated_size = None
        needs_merge = best_video_fmt.get('acodec') == 'none'
        if needs_merge:
            if video_size and best_audio_size:
                total_estimated_size = video_size + best_audio_size
            elif video_size:
                total_estimated_size = video_size
        else:
            total_estimated_size = video_size

        available_videos.append({
            "format_id": best_video_fmt.get('format_id'),
            "resolution": f"{target_h}p",
            "height": target_h,
            "name": res["name"],
            "badge": res["badge"],
            "fps": best_video_fmt.get('fps') or 30,
            "ext": "mp4",
            "needs_merge": needs_merge,
            "estimated_size": format_bytes(total_estimated_size) if total_estimated_size else "Available",
            "approx_bytes": total_estimated_size or 0
        })

        available_video_only.append({
            "format_id": best_video_fmt.get('format_id'),
            "resolution": f"{target_h}p",
            "height": target_h,
            "name": f"{res['name']} (Visuals Only)",
            "badge": res["badge"],
            "fps": best_video_fmt.get('fps') or 30,
            "ext": "mp4",
            "needs_merge": False,
            "estimated_size": format_bytes(video_size) if video_size else "Available",
            "approx_bytes": video_size or 0
        })
        seen_heights.add(target_h)

    if not available_videos:
        for f in formats:
            if f.get('vcodec') != 'none':
                h = get_effective_height(f) or 360
                display_res = f"{h}p"
                needs_merge = f.get('acodec') == 'none'
                v_size = f.get('filesize') or f.get('filesize_approx')
                tot_size = (v_size + best_audio_size) if (needs_merge and v_size and best_audio_size) else v_size
                available_videos.append({
                    "format_id": f.get('format_id') or "best",
                    "resolution": display_res,
                    "height": h,
                    "name": f"HD Video ({display_res})" if h >= 720 else f"Standard Video ({display_res})",
                    "badge": "HD" if h >= 720 else "SD",
                    "fps": f.get('fps') or 30,
                    "ext": f.get('ext') or "mp4",
                    "needs_merge": needs_merge,
                    "estimated_size": format_bytes(tot_size),
                    "approx_bytes": tot_size or 0
                })

    available_audios = [
        {
            "format_id": "mp3_320",
            "name": "MP3 High Quality",
            "quality": "320 kbps",
            "ext": "mp3",
            "estimated_size": format_bytes((320 * 1024 * duration) / 8) if duration else "~10 MB"
        },
        {
            "format_id": "mp3_192",
            "name": "MP3 Standard Quality",
            "quality": "192 kbps",
            "ext": "mp3",
            "estimated_size": format_bytes((192 * 1024 * duration) / 8) if duration else "~6 MB"
        },
        {
            "format_id": "m4a_best",
            "name": "M4A Original Audio",
            "quality": "Original AAC",
            "ext": "m4a",
            "estimated_size": format_bytes(best_audio_size) if best_audio_size else "~5 MB"
        }
    ]

    result_data = {
        "title": info.get('title', 'Unknown Title'),
        "duration": duration,
        "duration_formatted": format_duration(duration),
        "thumbnail": info.get('thumbnail') or (info.get('thumbnails', [{}])[-1].get('url') if info.get('thumbnails') else None),
        "uploader": info.get('uploader') or info.get('channel') or "YouTube Creator",
        "view_count": f"{info.get('view_count', 0):,}" if info.get('view_count') is not None else "N/A",
        "webpage_url": info.get('webpage_url', url),
        "video_formats": available_videos,
        "video_only_formats": available_video_only,
        "audio_formats": available_audios,
        "ffmpeg_installed": is_ffmpeg_available()
    }

    # Cache metadata for future sub-second retrieval
    set_cached_metadata(clean_url, info, result_data, working_proxy)

    return result_data

def start_download_task(
    job_id: str,
    url: str,
    download_type: str,  # 'video', 'video_only', 'audio'
    height: Optional[int],
    audio_format: Optional[str],
    jobs_dict: Dict[str, Any]
):
    """
    Synchronous worker for downloading and processing with yt-dlp.
    Fast-tracked with pre-resolved working proxy and instant copy remuxing.
    """
    job = jobs_dict.get(job_id)
    if job is None:
        return

    def progress_hook(d):
        if d['status'] == 'downloading':
            total = d.get('total_bytes') or d.get('total_bytes_estimate') or 0
            downloaded = d.get('downloaded_bytes', 0)
            speed = d.get('speed') or 0
            eta = d.get('eta') or 0
            percent = (downloaded / total * 100) if total > 0 else 0

            job['status'] = 'downloading'
            job['percent'] = min(round(percent, 1), 99.0)
            job['speed_str'] = f"{format_bytes(speed)}/s" if speed else ""
            job['eta_str'] = f"{eta}s" if eta else ""
            job['downloaded_str'] = format_bytes(downloaded)
            job['total_str'] = format_bytes(total)
            job['message'] = f"Downloading stream: {job['percent']}% ({job['speed_str']})"

        elif d['status'] == 'finished':
            job['status'] = 'merging'
            job['percent'] = 99.0
            job['message'] = "Download finished. Merging audio & video streams..."

    def postprocessor_hook(d):
        if d['status'] == 'started':
            job['status'] = 'merging'
            job['percent'] = 99.0
            job['message'] = "Fast muxing with FFmpeg..."
        elif d['status'] == 'finished':
            job['status'] = 'finalizing'
            job['percent'] = 100.0
            job['message'] = "Finalizing file..."

    clean_url = normalize_youtube_url(url)
    out_template = str(DOWNLOAD_DIR / f"{job_id}_%(title).80B.%(ext)s")

    cookie_opts = get_cookie_opts()
    ydl_opts: Dict[str, Any] = {
        'outtmpl': out_template,
        'progress_hooks': [progress_hook],
        'postprocessor_hooks': [postprocessor_hook],
        'postprocessor_args': {
            'Merger': ['-c', 'copy']  # Ultra-fast muxing without re-encoding
        },
        'quiet': True,
        'no_warnings': True,
        'restrictfilenames': True,
        'concurrent_fragment_downloads': 10,
        'buffersize': 1024 * 1024,
        'http_chunk_size': 10485760,
        'socket_timeout': 10,
        'extractor_args': {
            'youtube': {
                'player_client': ['visionos']
            }
        }
    }
    if cookie_opts:
        ydl_opts.update(cookie_opts)

    try:
        if download_type == 'audio':
            if audio_format in ['mp3_320', 'mp3_192']:
                quality = '320' if audio_format == 'mp3_320' else '192'
                ydl_opts['format'] = 'bestaudio/best'
                ydl_opts['postprocessors'] = [{
                    'key': 'FFmpegExtractAudio',
                    'preferredcodec': 'mp3',
                    'preferredquality': quality,
                }]
            else:
                ydl_opts['format'] = 'bestaudio[ext=m4a]/bestaudio/best'
                ydl_opts['postprocessors'] = [{
                    'key': 'FFmpegExtractAudio',
                    'preferredcodec': 'm4a',
                }]
        elif download_type == 'video_only':
            if height:
                ydl_opts['format'] = (
                    f"bestvideo[height<={height}][vcodec^=avc]/"
                    f"bestvideo[width<={height}][vcodec^=avc]/"
                    f"bestvideo[height<={height}][ext=mp4]/"
                    f"bestvideo[width<={height}][ext=mp4]/"
                    f"bestvideo[height<={height}]/bestvideo[width<={height}]/bestvideo"
                )
            else:
                ydl_opts['format'] = "bestvideo[vcodec^=avc]/bestvideo[ext=mp4]/bestvideo"
            ydl_opts['merge_output_format'] = 'mp4'
        else:
            # Full Video WITH Sound
            if height:
                ydl_opts['format'] = (
                    f"bestvideo[height<={height}][vcodec^=avc]+bestaudio[acodec^=mp4a]/"
                    f"bestvideo[width<={height}][vcodec^=avc]+bestaudio[acodec^=mp4a]/"
                    f"bestvideo[height<={height}][ext=mp4]+bestaudio[ext=m4a]/"
                    f"bestvideo[width<={height}][ext=mp4]+bestaudio[ext=m4a]/"
                    f"bestvideo[height<={height}]+bestaudio/"
                    f"bestvideo[width<={height}]+bestaudio/"
                    f"best[height<={height}]/best[width<={height}]/best"
                )
            else:
                ydl_opts['format'] = (
                    "bestvideo[vcodec^=avc]+bestaudio[acodec^=mp4a]/"
                    "bestvideo[ext=mp4]+bestaudio[ext=m4a]/"
                    "bestvideo+bestaudio/best"
                )
            ydl_opts['merge_output_format'] = 'mp4'

        cached = get_cached_metadata(clean_url)
        chosen_proxy = cached.get('working_proxy', PRIMARY_PROXY) if cached else PRIMARY_PROXY

        # Fast execution: try pre-verified proxy first
        proxies_to_attempt = [chosen_proxy] + [p for p in PROXIES_POOL[:2] if p != chosen_proxy]
        last_dl_err = None
        download_success = False

        for p in proxies_to_attempt:
            run_opts = dict(ydl_opts)
            if p:
                run_opts['proxy'] = p
            try:
                with yt_dlp.YoutubeDL(run_opts) as ydl:
                    job['message'] = "Downloading high-speed media stream..."
                    ydl.extract_info(clean_url, download=True)
                    download_success = True
                    break
            except Exception as e:
                last_dl_err = e
                continue

        if not download_success:
            raise Exception(f"Download failed: {last_dl_err}")

        # Locate output file
        matched_files = list(DOWNLOAD_DIR.glob(f"{job_id}_*"))
        final_files = [f for f in matched_files if not f.name.endswith(('.part', '.ytdl', '.temp'))]

        if not final_files:
            raise Exception("Output file was not generated.")

        file_path = final_files[0]
        clean_display_name = file_path.name
        if clean_display_name.startswith(f"{job_id}_"):
            clean_display_name = clean_display_name[len(f"{job_id}_"):]

        job['status'] = 'completed'
        job['percent'] = 100.0
        job['message'] = "Download ready!"
        job['file_path'] = str(file_path)
        job['file_name'] = clean_display_name
        job['file_size'] = format_bytes(file_path.stat().st_size)

    except Exception as e:
        job['status'] = 'error'
        job['message'] = str(e)
        job['error'] = str(e)
