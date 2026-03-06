import yt_dlp
import os
import uuid
import json
from yt_dlp import YoutubeDL
# FastAPI
from fastapi import FastAPI, Query
from fastapi.responses import FileResponse, JSONResponse
from env import PROXY_URL
from main import get_yt_dlp_opts
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

app = FastAPI()
DOWNLOAD_FOLDER = "downloads"
os.makedirs(DOWNLOAD_FOLDER, exist_ok=True)

@app.get("/download")
async def download_video(url: str = Query(..., title="YouTube Video URL")):
    """
    Download a YouTube video and return the file.
    """
    logger.info('Inside download video endpoint')
    ydl_opts = {
        'outtmpl': os.path.join(DOWNLOAD_FOLDER, '%(title)s.%(ext)s'),
        'format': '18',
        'proxy': PROXY_URL,
        'cookiefile': 'env/cookies.txt',
         # 'merge_output_format': 'mp4',
    }

    logger.info('Started downloading...')
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=True)
        filename = ydl.prepare_filename(info).rsplit(".", 1)[0] + ".mp4"

    logger.info('Returning file response...')
    return FileResponse(filename, media_type='video/mp4', filename=os.path.basename(filename))

@app.get("/info")
async def get_video_info(url: str = Query(...)):
    if not url:
        raise HTTPException(status_code=400, detail="Missing 'url' parameter")

    ydl_opts = get_yt_dlp_opts()
    with YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=False)

    logger.info('Returning full video info...')
    return JSONResponse(content=info)

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
    # ydl_opts = get_yt_dlp_opts(playliststart=offset + 1, playlistend=offset + limit)
    # ydl_opts["playlistreverse"] = True
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

