import os
import uuid
import json
from yt_dlp import YoutubeDL

import logging
import sys
import time
from pythonjsonlogger import jsonlogger

logger = logging.getLogger()
logHandler = logging.StreamHandler(sys.stdout)
formatter = jsonlogger.JsonFormatter(
    "%(asctime)s %(levelname)s %(message)s %(name)s",
    json_ensure_ascii=False
)
logHandler.setFormatter(formatter)
logger.addHandler(logHandler)
logger.setLevel(logging.INFO)

from env import ENV, PROXY_URL, BUCKET_NAME

STORAGE_PATH = "./downloads" if ENV == "development" else "/function/storage/storage"
ENV_PATH = "env" if ENV == "development" else "/function/storage/env"

COOKIE_PATH = os.path.join(ENV_PATH, 'cookies.txt')

logger.info(f"COOKIE_PATH: {COOKIE_PATH}")
if os.path.exists(COOKIE_PATH):
    logger.info(f"Cookie file found. Size: {os.path.getsize(COOKIE_PATH)} bytes")
else:
    logger.error(f"Cookie file NOT found at {COOKIE_PATH}")


# Helper function to build yt-dlp options
def get_yt_dlp_opts(download_path=None, fmt=None, playlistend=None):
    opts = {
        'proxy': PROXY_URL,
        'cookiefile': COOKIE_PATH,
        'nocheckcookies': True,
        'cachedir': False,
        'noplaylist': False if playlistend else True,  # allow playlists
        # Optimize for speed
        'concurrent_fragment_downloads': 1,  # Download fragments sequentially to avoid IP blocking
        'fragment_retries': 3,  # Retry failed fragments
        'retries': 3,  # Retry failed downloads
        'http_chunk_size': 10485760,  # 10MB chunks for better throughput
        'extractor_args': {
            'youtube': {
                'player_client': ['android', 'web'],
            }
        },
    }

    # Add PO Token and Visitor Data if available (bypasses bot detection)
    po_token = os.getenv("PO_TOKEN")
    visitor_data = os.getenv("VISITOR_DATA")

    if po_token:
        logger.info("Using PO Token for YouTube download")
        opts.setdefault('extractor_args', {})
        opts['extractor_args']['youtube'] = {
            'po_token': [po_token],
            'player_client': ['web'], # PO Token usually requires 'web' client
        }

        if visitor_data:
            logger.info("Using Visitor Data for YouTube download")
            opts['extractor_args']['youtube']['visitor_data'] = [visitor_data]

    if download_path:
        # Use flexible format selector with fallbacks
        # Priority: format 18 (360p ~10MB) -> 480p or lower -> worst available
        # This keeps file sizes reasonable (10-30 MB typical) instead of downloading huge HD files
        if fmt and fmt not in ["best", "worst"]:
            # If specific format requested, try it with fallbacks
            format_selector = f"{fmt}/bestvideo[height<=480][ext=mp4]+bestaudio[ext=m4a]/best[height<=480][ext=mp4]/best[height<=480]/worst"
        else:
            # Default: prioritize format 18 (360p), fallback to 480p max, then worst
            format_selector = "18/bestvideo[height<=480][ext=mp4]+bestaudio[ext=m4a]/best[height<=480][ext=mp4]/best[height<=480]/worst"

        opts.update({
            'outtmpl': download_path,
            'format': format_selector,
            # Merge video+audio into single file if needed
            'merge_output_format': 'mp4',
        })
    elif fmt:
        # If specific format is requested even for info, set it
        opts['format'] = fmt
    else:
        # Default for info-only requests - explicitly set to something that always exists
        opts['format'] = 'bestvideo+bestaudio/best'
    
    if playlistend:
        opts['playlistend'] = playlistend
    return opts

def handler(event, context):
    logger.info("Handling request", extra={"event": "request_start", "event_data": event})
    # logger.debug('context:', context)

    # Support both API Gateway (with path) and direct invocation (no path)
    path = event.get("path", "/download")  # Default to /download for direct invocation

    # For direct invocation, parameters might be in different places
    query = event.get("queryStringParameters") or {}

    # Also check httpMethod - if POST, body might contain params
    http_method = event.get("httpMethod", "POST")
    if http_method == "POST" and event.get("body"):
        try:
            body = json.loads(event.get("body", "{}"))
            # Merge body params with query params (body takes precedence)
            query = {**query, **body}
        except:
            pass

    url = query.get("url")
    fmt = query.get("format")  # Default None -> will use format 18 (360p) fallback

    if not url and path not in ["/ping", "/health/proxy", "/health/cookies", "/health/full"]:
        return {
            "statusCode": 400,
            "body": json.dumps({"error": "Missing 'url' parameter"})
        }

    try:
        if path == "/download":
            return handle_download(url, fmt)
        elif path == "/download-url":
            # New endpoint: returns direct download URL without downloading
            return handle_download_url(url, fmt)
        elif path == "/info":
            return handle_info(url)
        elif path == "/playlist":
            # Optional ?limit=5 query parameter
            limit = int(query.get("limit", 5))
            return handle_playlist(url, limit)
        elif path == "/ping":
            return handle_ping()
        elif path == "/health/proxy":
            return handle_health_proxy()
        elif path == "/health/cookies":
            return handle_health_cookies()
        elif path == "/health/full":
            return handle_health_full()
        else:
            return {
                "statusCode": 404,
                "body": json.dumps({"error": "Not found", "path": path})
            }
    except Exception as e:
        return {
            "statusCode": 500,
            "body": json.dumps({"error": str(e)})
        }

def handle_ping():
    return {
        "statusCode": 200,
        "body": json.dumps({"status": "ok", "message": "pong"})
    }

def handle_health_proxy():
    import urllib.request
    import json
    if not PROXY_URL:
        logger.warning("PROXY_URL not configured")
        return {
            "statusCode": 200,
            "body": json.dumps({"status": "warn", "message": "PROXY_URL not configured"})
        }

    try:
        # 1. Get IP without proxy
        # We use a custom opener with no proxies to ensure we get the real IP
        no_proxy_handler = urllib.request.ProxyHandler({})
        no_proxy_opener = urllib.request.build_opener(no_proxy_handler)
        
        logger.info("Checking IP without proxy...")
        no_proxy_response = no_proxy_opener.open('https://api.ipify.org?format=json', timeout=10)
        no_proxy_data = json.loads(no_proxy_response.read().decode())
        no_proxy_ip = no_proxy_data.get("ip")
        logger.info(f"IP without proxy: {no_proxy_ip}")

        # 2. Get IP with proxy
        logger.info(f"Checking IP with proxy: {PROXY_URL}")
        proxy_handler = urllib.request.ProxyHandler({'http': PROXY_URL, 'https': PROXY_URL})
        proxy_opener = urllib.request.build_opener(proxy_handler)
        proxy_response = proxy_opener.open('https://api.ipify.org?format=json', timeout=10)
        proxy_data = json.loads(proxy_response.read().decode())
        proxy_ip = proxy_data.get("ip")
        logger.info(f"IP with proxy: {proxy_ip}")

        if no_proxy_ip == proxy_ip:
            error_msg = f"Proxy is NOT working! Both IPs are the same: {proxy_ip}"
            logger.error(error_msg)
            return {
                "statusCode": 500, # Return 500 as the proxy check failed to mask IP
                "body": json.dumps({
                    "status": "error",
                    "message": error_msg,
                    "no_proxy_ip": no_proxy_ip,
                    "proxy_ip": proxy_ip
                })
            }

        logger.info("Proxy is working correctly.")
        return {
            "statusCode": 200,
            "body": json.dumps({
                "status": "ok",
                "message": "Proxy is working",
                "no_proxy_ip": no_proxy_ip,
                "proxy_ip": proxy_ip
            })
        }
    except Exception as e:
        error_msg = f"Proxy health check failed: {str(e)}"
        logger.exception(error_msg)
        return {
            "statusCode": 500,
            "body": json.dumps({"status": "error", "error": error_msg})
        }

def handle_health_cookies():
    test_url = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
    
    # Use minimal options to verify cookies
    health_opts = {
        'cookiefile': COOKIE_PATH,
        'proxy': PROXY_URL,
        'quiet': True,
        'no_warnings': True,
        'skip_download': True,
        'nocheckcookies': True,
        'cachedir': False,
    }

    try:
        with YoutubeDL(health_opts) as ydl:
            # use_extractors to just get basic info
            info = ydl.extract_info(test_url, download=False, process=False)
            if info:
                return {
                    "statusCode": 200,
                    "body": json.dumps({
                        "status": "ok",
                        "video_title": info.get("title"),
                        "cookie_file": COOKIE_PATH,
                        "cookie_file_size": os.path.getsize(COOKIE_PATH) if COOKIE_PATH and os.path.exists(COOKIE_PATH) else 0
                    })
                }
            else:
                return {
                    "statusCode": 500,
                    "body": json.dumps({"status": "error", "message": "Failed to extract info"})
                }
    except Exception as e:
        return {
            "statusCode": 500,
            "body": json.dumps({
                "status": "error",
                "error": str(e),
                "cookie_file": COOKIE_PATH,
                "cookie_file_exists": os.path.exists(COOKIE_PATH) if COOKIE_PATH else False
            })
        }

def handle_health_full():
    proxy_res = handle_health_proxy()
    cookies_res = handle_health_cookies()

    proxy_data = json.loads(proxy_res["body"])
    cookies_data = json.loads(cookies_res["body"])

    status = "ok"
    if proxy_data.get("status") == "error" or cookies_data.get("status") == "error":
        status = "error"
    elif proxy_data.get("status") == "warn" or cookies_data.get("status") == "warn":
        status = "warn"

    return {
        "statusCode": 200 if status != "error" else 500,
        "body": json.dumps({
            "status": status,
            "proxy": proxy_data,
            "cookies": cookies_data
        })
    }

def handle_download_url(url, fmt):
    """
    New endpoint: Returns direct YouTube download URL without downloading the video.
    This avoids the 5-minute API Gateway timeout for large videos.

    The returned URL:
    - Is a direct download link from YouTube's servers
    - Expires after ~6 hours
    - Can be used by the bot to download directly (bypassing our gateway)
    """
    logger.info("Getting direct download URL", extra={
        "event": "download_url_start",
        "url": url,
        "format": fmt
    })
    start_time = time.time()

    ydl_opts = get_yt_dlp_opts(fmt=fmt)

    with YoutubeDL(ydl_opts) as ydl:
        logger.info("Extracting video info...")
        info = ydl.extract_info(url, download=False)

        if not info:
            return {
                "statusCode": 404,
                "body": json.dumps({"error": "Video not found or unavailable"})
            }

        formats = info.get('formats', [])
        selected_format = None

        # Filter formats to only include those with direct URLs (not HLS/DASH)
        # HLS (m3u8) and DASH (mpd) formats require fragment assembly
        # Also exclude storyboards (preview images, not actual video)
        direct_formats = [
            f for f in formats
            if f.get('url')
            and f.get('protocol') not in ['m3u8', 'm3u8_native', 'http_dash_segments']
            and not f.get('url', '').endswith('.m3u8')
            and not f.get('url', '').endswith('.mpd')
            and 'manifest' not in f.get('url', '').lower()
            and 'storyboard' not in f.get('format_note', '').lower()
            and not f.get('format_id', '').startswith('sb')  # sb0, sb1, sb2, sb3 are storyboards
            and f.get('vcodec', 'none') != 'none'  # Must have video codec
        ]

        logger.info(f"Found {len(direct_formats)} video formats with direct URLs out of {len(formats)} total")

        # If no direct formats available, this video requires HLS/DASH download
        if not direct_formats:
            logger.warn("No direct download URLs available - video uses HLS/DASH streaming only")
            return {
                "statusCode": 400,
                "body": json.dumps({
                    "error": "This video only supports HLS/DASH streaming formats (no direct download URLs available)",
                    "youtube_forcing_streaming": True,
                    "suggestion": "Use the old /download POST endpoint which handles HLS/DASH downloads properly",
                    "video_title": info.get('title'),
                    "video_id": info.get('id')
                })
            }

        if fmt and fmt not in ["best", "worst"]:
            # Try to find exact format match with direct URL
            for f in direct_formats:
                if str(f.get('format_id')) == str(fmt):
                    selected_format = f
                    logger.info(f"Found exact format match: {fmt}")
                    break

        if not selected_format:
            # Select best format with direct URL
            # Prefer formats with both video and audio (acodec != 'none' and vcodec != 'none')
            combined_formats = [
                f for f in direct_formats
                if f.get('vcodec', 'none') != 'none' and f.get('acodec', 'none') != 'none'
            ]

            if combined_formats:
                # Sort by quality (resolution * fps) and select best
                combined_formats.sort(
                    key=lambda f: (f.get('height', 0) * f.get('fps', 1), f.get('tbr', 0)),
                    reverse=True
                )
                selected_format = combined_formats[0]
                logger.info(f"Selected best combined format: {selected_format.get('format_id')} ({selected_format.get('height')}p)")
            else:
                # Fallback: use format 18 (360p, always has direct URL and combined audio+video)
                format_18 = next((f for f in direct_formats if f.get('format_id') == '18'), None)
                if format_18:
                    selected_format = format_18
                    logger.info("Using fallback format 18 (360p)")
                elif direct_formats:
                    # Last resort: any direct format
                    selected_format = direct_formats[0]
                    logger.info(f"Using first available direct format: {selected_format.get('format_id')}")

        if not selected_format or not selected_format.get('url'):
            return {
                "statusCode": 404,
                "body": json.dumps({
                    "error": "No suitable format found with direct URL. All formats require HLS/DASH streaming.",
                    "suggestion": "Try using the old /download endpoint for this video",
                    "available_formats": [
                        {
                            "format_id": f.get("format_id"),
                            "ext": f.get("ext"),
                            "quality": f.get("format_note"),
                            "protocol": f.get("protocol")
                        }
                        for f in formats[:10]
                    ]
                })
            }

        direct_url = selected_format['url']

        logger.info(f"Found direct URL: {direct_url[:100]}...")

        duration = time.time() - start_time
        logger.info("Successfully got download URL", extra={
            "event": "download_url_success",
            "url": url,
            "duration": duration,
            "format_id": selected_format.get('format_id')
        })

        return {
            "statusCode": 200,
            "body": json.dumps({
                "url": direct_url,
                "format_id": selected_format.get('format_id'),
                "ext": selected_format.get('ext', 'mp4'),
                "quality": selected_format.get('format_note'),
                "filesize": selected_format.get('filesize'),
                "expires_in_hours": 6,
                "title": info.get('title'),
                "duration": info.get('duration'),
                "width": selected_format.get('width'),
                "height": selected_format.get('height'),
                "fps": selected_format.get('fps')
            })
        }

def handle_download(url, fmt):
    start_time = time.time()
    logger.info("Starting download", extra={
        "event": "download_start",
        "url": url,
        "format": fmt
    })

    video_id = str(uuid.uuid4())
    ext = "m4a" if fmt == "m4a" else "mp4"
    file_name = f"{str(uuid.uuid4())}.{ext}"
    download_path = os.path.join(STORAGE_PATH, file_name)

    ydl_opts = get_yt_dlp_opts(download_path=download_path, fmt=fmt)

    with YoutubeDL(ydl_opts) as ydl:
        logger.info("Getting video info...")
        info = ydl.extract_info(url, download=False)
        # logger.info(json.dumps(info.get("formats", []), indent=2))

        logger.info("Starting downloading...")
        ydl.download([url])

    public_url = f"https://storage.yandexcloud.net/{BUCKET_NAME}/{file_name}"

    duration = time.time() - start_time
    logger.info("Download completed", extra={
        "event": "download_success",
        "url": url,
        "duration": duration,
        "public_url": public_url
    })
    return {
        "statusCode": 200,
        "body": json.dumps({"url": public_url})
    }

def handle_info(url):
    logger.info("Getting video info", extra={"event": "info_start", "url": url})
    start_time = time.time()
    ydl_opts = get_yt_dlp_opts()

    with YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=False)

    # logger.info("Scraping youtube video title...")
    # title = scrape_video_title(url)
    # logger.info("Scraped youtube title:", title)
    # info["title"] = title

    logger.info("Returning full video info...", extra={
        "event": "info_success",
        "url": url,
        "duration": time.time() - start_time
    })
    return {
        "statusCode": 200,
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps(info, default=str)
    }

def handle_playlist(url, limit=5):
    """
    Extract playlist metadata and return the 'limit' most
    recently uploaded videos.
    """
    ydl_opts = get_yt_dlp_opts(playlistend=limit)
    ydl_opts['ignoreerrors'] = True  # Skip unavailable/private videos

    logger.info("Extracting playlist info...")
    with YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=False)

    # `entries` is a list of video‐info dicts
    entries = info.get("entries") or []
    logger.info("entries length:", extra={"count": len(entries)})

    # Filter out any None entries and those without upload_date
    filtered = [e for e in entries if e and e.get("upload_date")]
    logger.info("filtered entries length:", extra={"count": len(filtered)})

    # Sort by upload_date descending (newest first)
    filtered.sort(key=lambda e: e["upload_date"], reverse=True)

    latest = filtered[:limit]
    logger.info("latest entries length:", extra={"count": len(latest)})

    # Only return a subset of fields per video
    result = []
    for e in latest:
        logger.info("element:", extra={"e": e})
        result.append({
            "id": e.get("id"),
            "title": e.get("title"),
            "url": e.get("webpage_url"),
            "uploader": e.get("uploader"),
            "upload_date": e.get("upload_date"),
            "duration": e.get("duration"),
        })

    return {
        "statusCode": 200,
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps({
            "playlist_id": info.get("id"),
            "title": info.get("title"),
            "entries_returned": len(result),
            "videos": result
        }, default=str)
    }
