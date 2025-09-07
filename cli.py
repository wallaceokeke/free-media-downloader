#!/usr/bin/env python3
"""
CLI tool for media_downloader.

Usage:
  python cli.py --url <media_url> [--hours 2]    # non-interactive
  python cli.py                                  # interactive prompt
"""
import argparse
import sys
import threading
from pathlib import Path
from datetime import datetime
from downloader.youtube_downloader import download_with_ytdlp

BASE = Path(__file__).resolve().parent
DOWNLOADS_DIR = BASE / "downloads"
DOWNLOADS_DIR.mkdir(parents=True, exist_ok=True)

def schedule_delete(path: Path, hours: int):
    if hours <= 0:
        return
    import time
    delay = hours * 3600
    print(f"[CLI] Scheduling delete for {path.name} in {hours} hours.")
    time.sleep(delay)
    try:
        if path.exists():
            path.unlink()
            print(f"[CLI] Deleted {path.name} after {hours} hours.")
    except Exception as e:
        print(f"[CLI] Error deleting {path.name}: {e}")

def interactive():
    print("=== CLI Media Downloader ===")
    url = input("Media URL: ").strip()
    if not url:
        print("No URL provided. Exiting.")
        sys.exit(1)
    hours_str = input("Auto-delete after hours (0 = never): ").strip()
    try:
        hours = int(hours_str) if hours_str else 0
    except ValueError:
        print("Invalid hours. Using 0.")
        hours = 0
    download(url, hours)

def download(url: str, hours: int = 0):
    print("[CLI] Starting download...")
    try:
        res = download_with_ytdlp(url, str(DOWNLOADS_DIR))
        path = Path(res["filepath"])
        title = res.get("title") or path.stem
        print(f"[CLI] Downloaded: {title}")
        print(f"[CLI] File: {path}")
        print(f"[CLI] Time: {datetime.utcnow().isoformat()} UTC")
        if hours > 0:
            t = threading.Thread(target=schedule_delete, args=(path, hours), daemon=True)
            t.start()
    except Exception as e:
        print("[CLI] Download failed:", e)
        sys.exit(1)

def main():
    parser = argparse.ArgumentParser(description="CLI Media Downloader")
    parser.add_argument("--url", "-u", type=str, help="Media URL to download")
    parser.add_argument("--hours", "-h", type=int, default=0, help="Auto-delete after X hours (0 = never)")
    args = parser.parse_args()

    if args.url:
        download(args.url, args.hours)
    else:
        interactive()

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nInterrupted by user.")
        sys.exit(0)
