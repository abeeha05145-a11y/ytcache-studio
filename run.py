import uvicorn
from app.config import HOST, PORT

if __name__ == "__main__":
    print("=" * 70)
    print(" Starting YTCache Studio Pro - 4K Downloader & Transcript Generator")
    print(f" Dashboard URL: http://localhost:{PORT}")
    print(" Press Ctrl+C to terminate the server.")
    print("=" * 70)
    uvicorn.run("app.main:app", host=HOST, port=PORT, reload=False)
