import yt_dlp
import os
import uuid
import json
from yt_dlp import YoutubeDL
# FastAPI
from fastapi import FastAPI, Query, HTTPException
from fastapi.responses import FileResponse, JSONResponse
from env import PROXY_URL
from main import get_yt_dlp_opts, handle_health_proxy, handle_health_cookies, handle_health_full, handle_health_extraction, handle_info
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

app = FastAPI()
DOWNLOAD_FOLDER = "downloads"
os.makedirs(DOWNLOAD_FOLDER, exist_ok=True)

@app.get("/health/proxy")
async def health_proxy():
    res = handle_health_proxy()
    return JSONResponse(content=json.loads(res["body"]), status_code=res["statusCode"])

@app.get("/health/cookies")
async def health_cookies():
    res = handle_health_cookies()
    return JSONResponse(content=json.loads(res["body"]), status_code=res["statusCode"])

@app.get("/health/extraction")
async def health_extraction():
    res = handle_health_extraction()
    return JSONResponse(content=json.loads(res["body"]), status_code=res["statusCode"])

@app.get("/health/full")
async def health_full():
    res = handle_health_full()
    return JSONResponse(content=json.loads(res["body"]), status_code=res["statusCode"])

@app.get("/health/check")
async def health_check(
    proxy: str = "true",
    cookies: str = "true",
    process: str = "true",
    clients: str = None,
    url: str = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
):
    query = {
        "proxy": proxy,
        "cookies": cookies,
        "process": process,
        "clients": clients,
        "url": url
    }
    from main import handle_health_check
    res = handle_health_check(query)
    return JSONResponse(content=json.loads(res["body"]), status_code=res["statusCode"])

@app.get("/download")
async def download_video(
    url: str = Query(..., title="YouTube Video URL"),
    fmt: str = None,
    proxy: str = "true",
    cookies: str = "true",
    clients: str = None
):
    """
    Download a YouTube video and return the file.
    """
    overrides = {
        "use_proxy": proxy.lower() == "true",
        "use_cookies": cookies.lower() == "true",
    }
    if clients:
        overrides["player_clients"] = clients.split(",")

    logger.info(f'Inside download video endpoint with overrides: {overrides}')
    
    # Generate temporary path for local download
    video_id = str(uuid.uuid4())
    ext = "m4a" if fmt == "m4a" else "mp4"
    filename = os.path.join(DOWNLOAD_FOLDER, f"{video_id}.{ext}")

    ydl_opts = get_yt_dlp_opts(download_path=filename, fmt=fmt, **overrides)

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        ydl.download([url])

    logger.info('Returning file response...')
    return FileResponse(filename, media_type='video/mp4', filename=os.path.basename(filename))

@app.get("/info")
async def get_video_info(
    url: str = Query(...),
    proxy: str = "true",
    cookies: str = "true",
    clients: str = None,
    process: str = "true"
):
    if not url:
        raise HTTPException(status_code=400, detail="Missing 'url' parameter")

    overrides = {
        "use_proxy": proxy.lower() == "true",
        "use_cookies": cookies.lower() == "true",
        "process": process.lower() == "true"
    }
    if clients:
        overrides["player_clients"] = clients.split(",")

    # Use handle_info from main.py
    res = handle_info(url, **overrides)
    return JSONResponse(content=json.loads(res["body"]), status_code=res["statusCode"])

@app.get("/playlist")
async def get_playlist_info(
    url: str = Query(..., title="YouTube Playlist URL"),
    limit: int = Query(5, ge=1, title="Number of latest videos to return")
):
    """
    Return the `limit` most-recently uploaded videos in a playlist.
    """
    if not url:
        raise HTTPException(status_code=400, detail="Missing 'url' parameter")

    ydl_opts = get_yt_dlp_opts(playlistend=limit)
    with YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=False)

    entries = info.get("entries") or []
    filtered = [e for e in entries if e and e.get("upload_date")]
    filtered.sort(key=lambda e: e["upload_date"], reverse=True)
    latest = filtered[:limit]

    videos = [
        {
            "id": e.get("id"),
            "title": e.get("title"),
            "url": e.get("webpage_url"),
            "uploader": e.get("uploader"),
            "upload_date": e.get("upload_date"),
            "duration": e.get("duration"),
        }
        for e in latest
    ]

    return JSONResponse(content={
        "playlist_id": info.get("id"),
        "title": info.get("title"),
        "entries_returned": len(videos),
        "videos": videos
    })

if __name__ == "__main__":
    import uvicorn
    logger.info('Starting uvicorn server...')
    uvicorn.run(app, host="0.0.0.0", port=8000)
