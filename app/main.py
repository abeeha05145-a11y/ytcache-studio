import os
import time
import uuid
import urllib.parse
import asyncio
from pathlib import Path
from typing import Dict, Any, Optional

import aiofiles
from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse, StreamingResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from app.config import (
    BASE_DIR, 
    DOWNLOAD_DIR, 
    HOST, 
    PORT, 
    STREAM_CHUNK_SIZE,
    MAX_FILE_AGE_SECONDS, 
    CLEANUP_INTERVAL_SECONDS
)
from app.transcript import get_video_transcript, LANGUAGES, extract_youtube_id, CHROME_TARGET
from app.downloader import extract_video_info, start_download_task
import yt_dlp

app = FastAPI(
    title="YTCache Unified - Video Downloader & Instant Speech Transcript",
    description="Unified platform for 4K video downloading and instant speech transcription.",
    version="3.0.0"
)

# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# In-memory download jobs dictionary
download_jobs: Dict[str, Dict[str, Any]] = {}

# Mount static files
STATIC_DIR = BASE_DIR / "static"
STATIC_DIR.mkdir(parents=True, exist_ok=True)
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

@app.get("/favicon.ico", include_in_schema=False)
async def favicon():
    fav_path = STATIC_DIR / "favicon.svg"
    if fav_path.exists():
        return FileResponse(str(fav_path), media_type="image/svg+xml")
    return JSONResponse(status_code=404, content={"detail": "Favicon not found"})

# Periodic cleanup of old files in download directory
async def periodic_cleanup():
    while True:
        try:
            await asyncio.sleep(CLEANUP_INTERVAL_SECONDS)
            now = time.time()
            for item in DOWNLOAD_DIR.iterdir():
                if item.is_file():
                    if now - item.stat().st_mtime > MAX_FILE_AGE_SECONDS:
                        try:
                            item.unlink()
                        except Exception:
                            pass
        except asyncio.CancelledError:
            break
        except Exception:
            pass

@app.on_event("startup")
async def startup_event():
    asyncio.create_task(periodic_cleanup())

class InfoRequest(BaseModel):
    url: str

class DownloadRequest(BaseModel):
    url: str
    type: str = "video"  # 'video', 'video_only', 'audio'
    height: Optional[int] = None
    audio_format: Optional[str] = None

class TranscriptRequest(BaseModel):
    url: str
    lang: str = "original"

@app.get("/", response_class=HTMLResponse)
async def serve_index():
    index_file = STATIC_DIR / "index.html"
    if not index_file.exists():
        return HTMLResponse("<h1>Frontend loading error: static/index.html not found</h1>", status_code=500)
    async with aiofiles.open(index_file, mode="r", encoding="utf-8") as f:
        content = await f.read()
    headers = {
        "Cache-Control": "no-cache, no-store, must-revalidate",
        "Pragma": "no-cache",
        "Expires": "0"
    }
    return HTMLResponse(content=content, headers=headers)

@app.get("/api/health")
async def health_check():
    return {
        "status": "online",
        "service": "YTCache Unified Engine",
        "version": "3.3.0-live",
        "timestamp": time.time()
    }

# -------------------------------------------------------------
# 1. Video Downloader API Endpoints
# -------------------------------------------------------------

@app.post("/api/fetch-info")
async def fetch_video_info_endpoint(req: InfoRequest):
    """
    Fetches video info and available quality formats (144p to 4K + audio).
    """
    url = req.url.strip()
    if not url:
        raise HTTPException(status_code=400, detail="Please enter a valid YouTube video URL.")
    try:
        data = await asyncio.to_thread(extract_video_info, url)
        return data
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Server error: {str(e)}")

@app.post("/api/download")
async def start_download_endpoint(req: DownloadRequest):
    """
    Initiates video or audio download task and returns job_id for progress tracking.
    """
    url = req.url.strip()
    if not url:
        raise HTTPException(status_code=400, detail="YouTube URL cannot be empty.")

    job_id = str(uuid.uuid4())[:8]
    download_jobs[job_id] = {
        "id": job_id,
        "url": url,
        "type": req.type,
        "height": req.height,
        "audio_format": req.audio_format,
        "status": "queued",
        "percent": 0.0,
        "message": "Initializing download...",
        "speed_str": "",
        "eta_str": "",
        "downloaded_str": "",
        "total_str": "",
        "file_path": None,
        "file_name": None,
        "file_size": None,
        "error": None,
        "created_at": time.time()
    }

    # Run downloading task in background thread
    asyncio.create_task(
        asyncio.to_thread(
            start_download_task,
            job_id,
            url,
            req.type,
            req.height,
            req.audio_format,
            download_jobs
        )
    )

    return {"job_id": job_id, "status": "queued"}

@app.get("/api/progress/{job_id}")
async def get_progress_endpoint(job_id: str):
    """
    Returns current status and download progress for a specific job_id.
    """
    job = download_jobs.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Download task not found or expired.")

    resp: Dict[str, Any] = {
        "job_id": job_id,
        "status": job["status"],
        "percent": job.get("percent", 0.0),
        "message": job.get("message", ""),
        "speed": job.get("speed_str", ""),
        "eta": job.get("eta_str", ""),
        "downloaded": job.get("downloaded_str", ""),
        "total": job.get("total_str", ""),
        "file_name": job.get("file_name"),
        "file_size": job.get("file_size"),
        "error": job.get("error")
    }

    if job["status"] == "completed":
        resp["download_url"] = f"/api/stream/{job_id}"

    return resp

@app.get("/api/stream/{job_id}")
async def stream_file_endpoint(job_id: str):
    """
    Streams the downloaded file in chunks to prevent server memory saturation.
    """
    job = download_jobs.get(job_id)
    if not job or job.get("status") != "completed":
        raise HTTPException(status_code=404, detail="File is not ready or has expired.")

    file_path = job.get("file_path")
    if not file_path or not Path(file_path).exists():
        raise HTTPException(status_code=404, detail="Downloaded file was not found on server disk.")

    path_obj = Path(file_path)
    file_size = path_obj.stat().st_size
    filename = job.get("file_name") or path_obj.name

    encoded_filename = urllib.parse.quote(filename)

    async def file_generator():
        async with aiofiles.open(path_obj, mode="rb") as f:
            while True:
                chunk = await f.read(STREAM_CHUNK_SIZE)
                if not chunk:
                    break
                yield chunk

    media_type = "video/mp4" if path_obj.suffix.lower() == ".mp4" else "audio/mpeg"
    headers = {
        "Content-Disposition": f"attachment; filename=\"{filename}\"; filename*=UTF-8''{encoded_filename}",
        "Content-Length": str(file_size),
        "Accept-Ranges": "bytes",
        "Cache-Control": "no-cache",
    }

    return StreamingResponse(file_generator(), media_type=media_type, headers=headers)

# -------------------------------------------------------------
# 2. Fast Authentic Speech Transcript API Endpoint
# -------------------------------------------------------------

@app.post("/api/transcript")
async def fetch_transcript_endpoint(req: TranscriptRequest):
    """
    Extracts authentic spoken speech paragraph without downloading video.
    Supports instant translation to requested language.
    """
    url = req.url.strip()
    if not url:
        raise HTTPException(status_code=400, detail="YouTube URL cannot be empty.")
    
    try:
        data = await asyncio.to_thread(get_video_transcript, url, req.lang)
        return data
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Transcript error: {str(e)}")
