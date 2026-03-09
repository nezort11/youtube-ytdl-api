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
def get_yt_dlp_opts(download_path=None, fmt=None, playlistend=None, **kwargs):
    # Start with base defaults
    opts = {
        'nocheckcookies': True,
        'cachedir': False,
        'noplaylist': False if playlistend else True,
        'quiet': False,
        'no_warnings': False,
        # Speed optimizations
        'concurrent_fragment_downloads': 5,
        'fragment_retries': 3,
        'retries': 3,
        'http_chunk_size': 10485760,
        'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'headers': {
            'Accept-Language': 'en-US,en;q=0.9',
        },
    }

    # Extract our special toggle flags and custom clients
    use_proxy_val = kwargs.pop("use_proxy", kwargs.pop("proxy", True))
    use_proxy = str(use_proxy_val).lower() != "false" if use_proxy_val is not None else True
    
    use_cookies_val = kwargs.pop("use_cookies", kwargs.pop("cookies", True))
    use_cookies = str(use_cookies_val).lower() != "false" if use_cookies_val is not None else True
    
    clients_val = kwargs.pop("player_clients", kwargs.pop("clients", None))
    player_clients = clients_val.split(",") if isinstance(clients_val, str) else clients_val

    # Any other kwarg is a direct yt-dlp option
    # We try to convert string numbers/booleans to proper types
    for k, v in kwargs.items():
        if isinstance(v, str):
            if v.lower() == "true": opts[k] = True
            elif v.lower() == "false": opts[k] = False
            elif v.isdigit(): opts[k] = int(v)
            else: opts[k] = v
        else:
            opts[k] = v

    # Apply sensitive overrides (secrets)
    if use_proxy and PROXY_URL:
        opts['proxy'] = PROXY_URL
    else:
        opts.pop('proxy', None)

    if use_cookies and COOKIE_PATH:
        opts['cookiefile'] = COOKIE_PATH
        opts['nocheckcookies'] = False
    else:
        opts.pop('cookiefile', None)
        opts['nocheckcookies'] = True

    # Setup extractor_args
    opts.setdefault('extractor_args', {})
    opts['extractor_args'].setdefault('youtube', {})
    
    # JS Runtime selection for YouTube "n-challenge" solving
    # WE USE DENO because it is lightweight, easy to bundle in serverless functions, 
    # and works correctly with modern YouTube challenges where Node/QuickJS might fail.
    import shutil
    # Look for deno in the function directory or PATH
    deno_path = shutil.which('deno') or (os.path.join(os.getcwd(), 'deno') if os.path.exists(os.path.join(os.getcwd(), 'deno')) else None)

    if deno_path:
        opts['js_runtimes'] = {'deno': {}}
        logger.info(f"Using Deno ({deno_path}) for JS extraction")
    else:
        logger.warning("Deno binary not found! YouTube extraction will likely fail.")
    
    if player_clients:
        opts['extractor_args']['youtube']['player_client'] = player_clients
    elif 'player_client' not in opts['extractor_args']['youtube']:
        if use_cookies:
            opts['extractor_args']['youtube']['player_client'] = ['web', 'mweb', 'tv', 'ios']
        else:
            opts['extractor_args']['youtube']['player_client'] = ['tv', 'web', 'android', 'ios']

    # Add PO Token and Visitor Data if available (bypasses bot detection)
    po_token = os.getenv("PO_TOKEN")
    visitor_data = os.getenv("VISITOR_DATA")
    
    # If not provided, use a generic one for tests
    if not po_token:
        po_token = "MnS89J3k4L5m6N7o8P9q0R1s2T3u4V5w6X7y8Z9a0B1c2D3e4F5g6H7i8J9k0L1m"
    if not visitor_data:
        visitor_data = "CgtWVlpSdWx4XzhBUSij6-y0BjIKCgJVUhIEGgAgWg%3D%3D"

    if po_token and 'po_token' not in opts['extractor_args']['youtube']:
        # Apply to all clients
        opts['extractor_args']['youtube']['po_token'] = [f"web+{po_token}", f"android+{po_token}", f"ios+{po_token}", f"mweb+{po_token}"]
        if visitor_data and 'visitor_data' not in opts['extractor_args']['youtube']:
            opts['extractor_args']['youtube']['visitor_data'] = [visitor_data]

    if download_path:
        # Use flexible format selector with fallbacks
        # Format 18 is a very reliable combined format (360p) that usually works even when higher qualities are restricted or missing
        if fmt and fmt not in ["best", "worst"]:
            format_selector = f"{fmt}/18/bestvideo[height<=480][ext=mp4]+bestaudio[ext=m4a]/best[height<=480][ext=mp4]/best[height<=480]/worst"
        else:
            format_selector = "18/bestvideo[height<=480][ext=mp4]+bestaudio[ext=m4a]/best[height<=480][ext=mp4]/best[height<=480]/worst"

        opts.update({
            'outtmpl': download_path,
            'format': opts.get('format', format_selector), # User can override format
            'merge_output_format': opts.get('merge_output_format', 'mp4'),
        })
    elif fmt:
        # For non-download requests (like /info), use a broad but safe format string if no specific format is requested
        # This helps avoid 'format not available' errors
        opts['format'] = opts.get('format', f"{fmt}/18/best/worst" if fmt not in ["best", "worst"] else fmt)
    else:
        # Default format for extraction if none specified
        opts['format'] = '18/bestvideo[height<=480][ext=mp4]+bestaudio[ext=m4a]/best[height<=480][ext=mp4]/best[height<=480]/worst'
    
    if playlistend:
        opts['playlistend'] = playlistend
    return opts

def handler(event, context):
    logger.info("Handling request", extra={"event": "request_start", "event_data": event})

    path = event.get("path", "/download")
    query = event.get("queryStringParameters") or {}

    http_method = event.get("httpMethod", "POST")
    if http_method == "POST" and event.get("body"):
        try:
            body = json.loads(event.get("body", "{}"))
            query = {**query, **body}
            if "path" in body:
                path = body["path"]
        except:
            pass

    url = query.get("url")
    fmt = query.get("format")

    # Everything else in query/body is passed as an override
    reserved = ["url", "path", "format", "limit"]
    overrides = {k: v for k, v in query.items() if k not in reserved}

    if not url and path not in ["/ping", "/health/proxy", "/health/cookies", "/health/full", "/health/check", "/health/extraction"]:
        return {
            "statusCode": 400,
            "body": json.dumps({"error": "Missing 'url' parameter"})
        }

    try:
        if path == "/download":
            return handle_download(url, fmt, **overrides)
        elif path == "/download-url":
            return handle_download_url(url, fmt, **overrides)
        elif path == "/info":
            return handle_info(url, **overrides)
        elif path == "/playlist":
            limit = int(query.get("limit", 5))
            return handle_playlist(url, limit)
        elif path == "/ping":
            return handle_ping()
        elif path == "/health/proxy":
            return handle_health_proxy()
        elif path == "/health/cookies":
            return handle_health_cookies()
        elif path == "/health/check":
            return handle_health_check(query)
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
    
    results = {}
    
    # 1. Test WITHOUT cookies
    opts_no_cookies = get_yt_dlp_opts(use_cookies=False)
    try:
        with YoutubeDL(opts_no_cookies) as ydl:
            info = ydl.extract_info(test_url, download=False, process=True)
            results["without_cookies"] = {"status": "ok", "formats": len(info.get("formats", []))}
    except Exception as e:
        results["without_cookies"] = {"status": "error", "error": str(e)}

    # 2. Test WITH cookies
    opts_with_cookies = get_yt_dlp_opts(use_cookies=True)
    try:
        with YoutubeDL(opts_with_cookies) as ydl:
            info = ydl.extract_info(test_url, download=False, process=True)
            results["with_cookies"] = {"status": "ok", "formats": len(info.get("formats", []))}
    except Exception as e:
        results["with_cookies"] = {"status": "error", "error": str(e)}

    # Determine overall status
    if results["with_cookies"]["status"] == "ok":
        status = "ok"
        message = "Cookies are working correctly"
    elif results["without_cookies"]["status"] == "ok":
        status = "error"
        message = "Extraction works WITHOUT cookies but FAILS WITH cookies. Your cookies are likely flagged."
    else:
        status = "error"
        message = "Extraction fails both with and without cookies. Likely an IP/Proxy block."

    return {
        "statusCode": 200 if status == "ok" else 500,
        "body": json.dumps({
            "status": status,
            "message": message,
            "results": results,
            "cookie_file": COOKIE_PATH,
            "cookie_file_exists": os.path.exists(COOKIE_PATH) if COOKIE_PATH else False,
            "cookie_file_size": os.path.getsize(COOKIE_PATH) if COOKIE_PATH and os.path.exists(COOKIE_PATH) else 0
        })
    }

def handle_health_check(query):
    """
    Configurable health check via query params:
    - proxy: true/false (default true)
    - cookies: true/false (default true)
    - process: true/false (default true, full extraction)
    - clients: comma-separated list (e.g. android,web)
    - url: custom test URL (default Rickroll)
    """
    use_proxy = str(query.get("proxy", "true")).lower() == "true"
    use_cookies = str(query.get("cookies", "true")).lower() == "true"
    process = str(query.get("process", "true")).lower() == "true"
    clients_str = query.get("clients")
    player_clients = clients_str.split(",") if clients_str else None
    test_url = query.get("url", "https://www.youtube.com/watch?v=dQw4w9WgXcQ")
    
    ydl_opts = get_yt_dlp_opts(
        use_proxy=use_proxy, 
        use_cookies=use_cookies, 
        player_clients=player_clients
    )
    
    config = {
        "proxy": use_proxy,
        "cookies": use_cookies,
        "process": process,
        "clients": player_clients or "default",
        "url": test_url
    }
    
    try:
        with YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(test_url, download=False, process=process)
            return {
                "statusCode": 200,
                "body": json.dumps({
                    "status": "ok",
                    "config": config,
                    "video_title": info.get("title"),
                    "formats_count": len(info.get("formats", []))
                })
            }
    except Exception as e:
        return {
            "statusCode": 200, # Still 200 because it's a diagnostic tool
            "body": json.dumps({
                "status": "error",
                "config": config,
                "error": str(e)
            })
        }

def handle_health_full():
    proxy_res = handle_health_proxy()
    cookies_res = handle_health_cookies()

    proxy_data = json.loads(proxy_res["body"])
    cookies_data = json.loads(cookies_res["body"])

    status = "ok"
    if any(d.get("status") == "error" for d in [proxy_data, cookies_data]):
        status = "error"
    elif any(d.get("status") == "warn" for d in [proxy_data, cookies_data]):
        status = "warn"

    return {
        "statusCode": 200 if status != "error" else 500,
        "body": json.dumps({
            "status": status,
            "proxy": proxy_data,
            "cookies": cookies_data
        })
    }

def handle_download_url(url, fmt, **kwargs):
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
        "format": fmt,
        "config_overrides": kwargs
    })
    start_time = time.time()

    ydl_opts = get_yt_dlp_opts(fmt=fmt, **kwargs)

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

def handle_download(url, fmt, **kwargs):
    start_time = time.time()
    logger.info("Starting download", extra={
        "event": "download_start",
        "url": url,
        "format": fmt,
        "config_overrides": kwargs
    })

    video_id = str(uuid.uuid4())
    ext = "m4a" if fmt == "m4a" else "mp4"
    file_name = f"{str(uuid.uuid4())}.{ext}"
    download_path = os.path.join(STORAGE_PATH, file_name)

    ydl_opts = get_yt_dlp_opts(download_path=download_path, fmt=fmt, **kwargs)

    with YoutubeDL(ydl_opts) as ydl:
        logger.info("Getting video info...")
        ydl.extract_info(url, download=True)

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

def handle_info(url, **kwargs):
    # Process 'process' param separately if provided
    process = kwargs.pop("process", True)
    
    logger.info("Getting video info", extra={
        "event": "info_start", 
        "url": url, 
        "extraction_process": process,
        "config_overrides": kwargs
    })
    start_time = time.time()
    ydl_opts = get_yt_dlp_opts(**kwargs)

    with YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=False, process=process)
        info["full_info"] = process

    # Return the full info object (which includes title, formats if found, etc.)
    logger.info("Returning video info", extra={
        "event": "info_success",
        "url": url,
        "duration": time.time() - start_time,
        "is_full": info.get("full_info", False)
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
