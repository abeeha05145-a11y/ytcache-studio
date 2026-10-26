import os
import re
import math
import shutil
import asyncio
from pathlib import Path
from typing import Dict, Any, List, Optional
import yt_dlp
CHROME_TARGET = None

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

# Android and iOS mobile clients avoid datacenter / cloud IP bot blocks
YOUTUBE_EXTRACTOR_ARGS = {
    'youtube': {
        'player_client': ['android', 'ios'],
        'player_skip': ['webpage', 'configs'],
    }
}

def normalize_youtube_url(url: str) -> str:
    """Normalize YouTube shorts, mobile, and share URLs into standard watch URLs."""
    if not url:
        return url
    m = re.search(r'(?:v=|\/shorts\/|\/v\/|youtu\.be\/)([a-zA-Z0-9_-]{11})', url)
    if m:
        return f"https://www.youtube.com/watch?v={m.group(1)}"
    return url.strip()

def clean_filename(name: str) -> str:
    # Remove characters not safe for Windows / Linux file names
    return re.sub(r'[\\/*?:"<>|]', "", name).strip()

def extract_video_info(url: str) -> Dict[str, Any]:
    """
    Extract video metadata and categorize available resolutions without downloading.
    """
    clean_url = normalize_youtube_url(url)
    ydl_opts = {
        'quiet': True,
        'no_warnings': True,
        'extract_flat': False,
        'skip_download': True,
        'extractor_args': YOUTUBE_EXTRACTOR_ARGS,
    }

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        try:
            info = ydl.extract_info(clean_url, download=False)
        except yt_dlp.utils.DownloadError as e:
            err_msg = str(e)
            if "Private video" in err_msg:
                raise ValueError("This video is private and cannot be downloaded.")
            elif "Video unavailable" in err_msg:
                raise ValueError("Video is unavailable or has been removed.")
            elif "Sign in to confirm your age" in err_msg:
                raise ValueError("This video is age-restricted and requires authentication.")
            elif "Incomplete YouTube ID" in err_msg or "is not a valid URL" in err_msg:
                raise ValueError("Please provide a valid YouTube video link.")
            else:
                raise ValueError(f"Could not fetch video info: {err_msg}")
        except Exception as e:
            raise ValueError(f"An unexpected error occurred: {str(e)}")

        if not info:
            raise ValueError("No video information found.")

        formats = info.get('formats', [])
        duration = info.get('duration', 0)
        
        # Target standard resolutions we look for
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

        # Find best audio stream for size estimation
        audio_formats = [
            f for f in formats 
            if f.get('vcodec') == 'none' and f.get('acodec') != 'none'
        ]
        best_audio = max(audio_formats, key=lambda f: f.get('tbr', 0) or f.get('abr', 0) or 0) if audio_formats else None
        best_audio_size = best_audio.get('filesize') or best_audio.get('filesize_approx') if best_audio else None
        if not best_audio_size and duration and best_audio:
            abr = best_audio.get('abr') or 128
            best_audio_size = (abr * 1024 * duration) / 8

        available_videos = []
        available_video_only = []
        seen_heights = set()

        for res in standard_res:
            target_h = res["height"]
            
            # Find candidate formats that match this height (or close to it)
            matching_formats = [
                f for f in formats 
                if f.get('height') and f.get('vcodec') != 'none' and f.get('height') == target_h
            ]

            if not matching_formats:
                # Look for formats within height range (e.g. 2160 might be 2160, etc.)
                continue

            # Pick format with best fps and bitrate
            best_video_fmt = max(
                matching_formats, 
                key=lambda f: (f.get('fps', 0) or 0, f.get('vbr', 0) or f.get('tbr', 0) or 0)
            )

            # Calculate estimated size
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

            # Full Video with Sound
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

            # Video Visual Only (Mute / No Audio)
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

        # Fallback for vertical videos (Shorts) or non-standard resolutions
        if not available_videos:
            for f in formats:
                if f.get('vcodec') != 'none':
                    h = f.get('height') or f.get('width') or 360
                    display_res = f"{min(f.get('height', h), f.get('width', h))}p" if (f.get('height') and f.get('width')) else f"{h}p"
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

        # Audio choices
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

        return {
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

def start_download_task(
    job_id: str,
    url: str,
    download_type: str,  # 'video' or 'audio'
    height: Optional[int],
    audio_format: Optional[str],
    jobs_dict: Dict[str, Any]
):
    """
    Synchronous worker executed in a thread pool for downloading and processing with yt-dlp.
    Updates the jobs_dict with progress and completion state.
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
            job['message'] = "Download finished. Merging audio & video with FFmpeg..."

    def postprocessor_hook(d):
        if d['status'] == 'started':
            job['status'] = 'merging'
            job['percent'] = 99.0
            job['message'] = "Merging video & audio streams with FFmpeg..."
        elif d['status'] == 'finished':
            job['status'] = 'finalizing'
            job['percent'] = 100.0
            job['message'] = "Finalizing file..."

    clean_url = normalize_youtube_url(url)

    # Base output filename template with job_id prefix to prevent collisions
    out_template = str(DOWNLOAD_DIR / f"{job_id}_%(title).80B.%(ext)s")

    ydl_opts: Dict[str, Any] = {
        'outtmpl': out_template,
        'progress_hooks': [progress_hook],
        'postprocessor_hooks': [postprocessor_hook],
        'quiet': True,
        'no_warnings': True,
        'restrictfilenames': True,
        'extractor_args': YOUTUBE_EXTRACTOR_ARGS,
    }

    try:
        if download_type == 'audio':
            # Audio download
            if audio_format in ['mp3_320', 'mp3_192']:
                quality = '320' if audio_format == 'mp3_320' else '192'
                ydl_opts['format'] = 'bestaudio/best'
                ydl_opts['postprocessors'] = [{
                    'key': 'FFmpegExtractAudio',
                    'preferredcodec': 'mp3',
                    'preferredquality': quality,
                }]
            else: # m4a
                ydl_opts['format'] = 'bestaudio[ext=m4a]/bestaudio/best'
                ydl_opts['postprocessors'] = [{
                    'key': 'FFmpegExtractAudio',
                    'preferredcodec': 'm4a',
                }]
        elif download_type == 'video_only':
            # Video ONLY (Visuals without Audio - Silent Video)
            if height:
                ydl_opts['format'] = (
                    f"bestvideo[height<={height}][vcodec^=avc]/"
                    f"bestvideo[height<={height}][ext=mp4]/"
                    f"bestvideo[height<={height}]/bestvideo"
                )
            else:
                ydl_opts['format'] = "bestvideo[vcodec^=avc]/bestvideo[ext=mp4]/bestvideo"
            
            ydl_opts['merge_output_format'] = 'mp4'
            ydl_opts['postprocessors'] = [{
                'key': 'FFmpegVideoRemuxer',
                'preferedformat': 'mp4'
            }]
        else:
            # Full Video WITH Sound (Default)
            # Prefer universally compatible H.264 (avc1) + AAC (mp4a) so files play on any Windows/Mac/Mobile player
            # Seamless fallback to VP9/AV1 for 2K/4K streams
            if height:
                ydl_opts['format'] = (
                    f"bestvideo[height<={height}][vcodec^=avc]+bestaudio[acodec^=mp4a]/"
                    f"bestvideo[height<={height}][ext=mp4]+bestaudio[ext=m4a]/"
                    f"bestvideo[height<={height}]+bestaudio/best[height<={height}]/best"
                )
            else:
                ydl_opts['format'] = (
                    "bestvideo[vcodec^=avc]+bestaudio[acodec^=mp4a]/"
                    "bestvideo[ext=mp4]+bestaudio[ext=m4a]/"
                    "bestvideo+bestaudio/best"
                )
            
            ydl_opts['merge_output_format'] = 'mp4'
            ydl_opts['postprocessors'] = [{
                'key': 'FFmpegVideoRemuxer',
                'preferedformat': 'mp4'
            }]

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            job['message'] = "Contacting YouTube servers..."
            info = ydl.extract_info(clean_url, download=True)
            
            # Find the actual generated file on disk
            # Pattern: {DOWNLOAD_DIR}/{job_id}_*
            matched_files = list(DOWNLOAD_DIR.glob(f"{job_id}_*"))
            # Filter out temporary .part or .ytdl files
            final_files = [f for f in matched_files if not f.name.endswith(('.part', '.ytdl', '.temp'))]

            if not final_files:
                raise Exception("Output file was not created by the downloader.")

            file_path = final_files[0]
            # Strip job_id_ prefix for presentation
            clean_display_name = file_path.name
            if clean_display_name.startswith(f"{job_id}_"):
                clean_display_name = clean_display_name[len(f"{job_id}_"):]

            job['status'] = 'completed'
            job['percent'] = 100
            job['message'] = "Download ready!"
            job['file_path'] = str(file_path)
            job['file_name'] = clean_display_name
            job['file_size'] = format_bytes(file_path.stat().st_size)

    except Exception as e:
        job['status'] = 'error'
        job['message'] = str(e)
        job['error'] = str(e)
