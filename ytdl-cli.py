import argparse
import json
import sys
import os
from main import handler

def main():
    parser = argparse.ArgumentParser(description='YTDL Local CLI Utility')
    parser.add_argument('command', choices=['info', 'download', 'download-url', 'playlist', 'health'], help='Command to execute')
    parser.add_argument('url', help='YouTube/Video URL')
    parser.add_argument('--format', '-f', help='Video format')
    parser.add_argument('--limit', '-l', type=int, default=5, help='Playlist limit')
    parser.add_argument('--proxy', type=str, default="true", help='Use proxy (true/false)')
    parser.add_argument('--cookies', type=str, default="true", help='Use cookies (true/false)')
    parser.add_argument('--process', type=str, default="true", help='Full extraction process (true/false)')
    parser.add_argument('--clients', type=str, help='Comma-separated list of player clients')

    args = parser.parse_args()

    # Simulate Lambda event
    path_map = {
        'info': '/info',
        'download': '/download',
        'download-url': '/download-url',
        'playlist': '/playlist',
        'health': '/health/full'
    }

    event = {
        "httpMethod": "GET",
        "path": path_map[args.command],
        "queryStringParameters": {
            "url": args.url,
            "format": args.format,
            "limit": str(args.limit),
            "proxy": args.proxy,
            "cookies": args.cookies,
            "process": args.process,
            "clients": args.clients
        }
    }

    # Call handler directly
    result = handler(event, None)

    # Print result
    if result['statusCode'] == 200:
        try:
            body = json.loads(result['body'])
            print(json.dumps(body, indent=2, ensure_ascii=False))
        except:
            print(result['body'])
    else:
        print(f"Error (Status {result['statusCode']}):")
        try:
            body = json.loads(result['body'])
            print(json.dumps(body, indent=2, ensure_ascii=False))
        except:
            print(result['body'])
        sys.exit(1)

if __name__ == "__main__":
    main()
