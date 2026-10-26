import os
from pathlib import Path

# Base Paths
BASE_DIR = Path(__file__).resolve().parent.parent
DOWNLOAD_DIR = BASE_DIR / "downloads"
DOWNLOAD_DIR.mkdir(parents=True, exist_ok=True)

# Server Config
HOST = "0.0.0.0"
PORT = 8000

# Streaming & File Config
# 2MB chunks for large file streaming to prevent server memory bloat
STREAM_CHUNK_SIZE = 2 * 1024 * 1024

# Cleanup settings: files older than this (in seconds) are automatically cleaned up
MAX_FILE_AGE_SECONDS = 3600  # 1 hour
CLEANUP_INTERVAL_SECONDS = 600  # Run cleanup check every 10 minutes
