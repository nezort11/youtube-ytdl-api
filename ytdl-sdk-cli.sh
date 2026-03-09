#!/bin/bash
# ytdl-sdk-cli.sh - CLI utility to call ytdl cloud function endpoints
# 
# Usage:
#   ./ytdl-sdk-cli.sh info <youtube_url>
#   ./ytdl-sdk-cli.sh download-url <youtube_url> [format]
#   ./ytdl-sdk-cli.sh download <youtube_url> [format]
#   ./ytdl-sdk-cli.sh playlist <youtube_url> [limit]
#
# Examples:
#   ./ytdl-sdk-cli.sh info "https://www.youtube.com/watch?v=224plb3bCog"
#   ./ytdl-sdk-cli.sh download-url "https://www.youtube.com/watch?v=224plb3bCog"
#   ./ytdl-sdk-cli.sh playlist "https://www.youtube.com/playlist?list=PLsVXlJ_NFVRgSSr6ki-BThf7CY3mTMEHI" 5

set -e

# Cloud function base URL
BASE_URL="https://functions.yandexcloud.net/d4eijiec6bhg8tl9luqr"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

usage() {
    echo "Usage: $0 <command> <youtube_url> [options]"
    echo ""
    echo "Commands:"
    echo "  info <url>              Get video info (title, duration, formats, etc.)"
    echo "  download-url <url> [fmt] Get direct download URL (format optional)"
    echo "  download <url> [fmt]    Download video and get S3 URL (format optional)"
    echo "  playlist <url> [limit]  Get playlist info (limit defaults to 5)"
    echo ""
    echo "Examples:"
    echo "  $0 info 'https://www.youtube.com/watch?v=224plb3bCog'"
    echo "  $0 download-url 'https://www.youtube.com/watch?v=224plb3bCog'"
    echo "  $0 download-url 'https://www.youtube.com/watch?v=224plb3bCog' 18"
    echo "  $0 playlist 'https://www.youtube.com/playlist?list=PLsVXlJ_NFVRgSSr6ki-BThf7CY3mTMEHI' 10"
    exit 1
}

# Check if jq is available for pretty printing
if command -v jq &> /dev/null; then
    PRETTY_PRINT="jq ."
else
    PRETTY_PRINT="cat"
fi

# Main command handler
case "$1" in
    info)
        if [ -z "$2" ]; then
            echo -e "${RED}Error: YouTube URL is required${NC}"
            usage
        fi
        echo -e "${YELLOW}Fetching video info...${NC}"
        curl -s -X POST "$BASE_URL" \
            -H "Content-Type: application/json" \
            -d "{\"path\": \"/info\", \"url\": \"$2\"}" | $PRETTY_PRINT
        ;;
    
    download-url)
        if [ -z "$2" ]; then
            echo -e "${RED}Error: YouTube URL is required${NC}"
            usage
        fi
        FORMAT_PARAM=""
        if [ -n "$3" ]; then
            FORMAT_PARAM=", \"format\": \"$3\""
        fi
        echo -e "${YELLOW}Getting direct download URL...${NC}"
        curl -s -X POST "$BASE_URL" \
            -H "Content-Type: application/json" \
            -d "{\"path\": \"/download-url\", \"url\": \"$2\"$FORMAT_PARAM}" | $PRETTY_PRINT
        ;;
    
    download)
        if [ -z "$2" ]; then
            echo -e "${RED}Error: YouTube URL is required${NC}"
            usage
        fi
        FORMAT_PARAM=""
        if [ -n "$3" ]; then
            FORMAT_PARAM=", \"format\": \"$3\""
        fi
        echo -e "${YELLOW}Downloading video (this may take a while)...${NC}"
        curl -s -X POST "$BASE_URL" \
            -H "Content-Type: application/json" \
            -d "{\"path\": \"/download\", \"url\": \"$2\"$FORMAT_PARAM}" | $PRETTY_PRINT
        ;;
    
    playlist)
        if [ -z "$2" ]; then
            echo -e "${RED}Error: YouTube playlist URL is required${NC}"
            usage
        fi
        LIMIT="${3:-5}"
        echo -e "${YELLOW}Fetching playlist info (limit: $LIMIT)...${NC}"
        curl -s -X POST "$BASE_URL" \
            -H "Content-Type: application/json" \
            -d "{\"path\": \"/playlist\", \"url\": \"$2\", \"limit\": $LIMIT}" | $PRETTY_PRINT
        ;;
    
    *)
        if [ -z "$1" ]; then
            echo -e "${RED}Error: Command is required${NC}"
        else
            echo -e "${RED}Error: Unknown command '$1'${NC}"
        fi
        usage
        ;;
esac

echo ""
echo -e "${GREEN}Done!${NC}"
