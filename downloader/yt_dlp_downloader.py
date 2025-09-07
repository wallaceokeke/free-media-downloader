"""
yt_dlp_downloader.py
Direct video/audio downloader with yt-dlp (no ffmpeg required).
Returns {'filepath','filename','title','mode'} on success.
"""
from pathlib import Path
import re
from typing import Dict
import yt_dlp

# Maximum allowed file size in bytes (None = no limit)
MAX_FILE_SIZE_BYTES = 500 * 1024 * 1024  # 500 MB


def sanitize_filename(name: str) -> str:
    """Sanitize filename to avoid problematic characters."""
    name = re.sub(r'[\\/:"*?<>|]+', "_", name)
    name = re.sub(r"\s+", " ", name).strip()
    return name[:240]


def download_with_ytdlp(url: str, output_dir: str, mode: str = "video") -> Dict[str, str]:
    """
    Download a URL into output_dir using yt-dlp.
    mode = "video" (default) or "audio"
    Returns dict: {'filepath', 'filename', 'title', 'mode'}.
    Raises exceptions on errors.
    """
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    if mode == "audio":
        format_selector = "bestaudio"   # only audio stream
        outtmpl = str(output_dir / "%(title)s.%(ext)s")
    else:  # default video
        format_selector = "best"        # single video+audio stream
        outtmpl = str(output_dir / "%(title)s.%(ext)s")

    opts = {
        "outtmpl": outtmpl,
        "format": format_selector,
        "noplaylist": True,
        "quiet": True,
        "no_warnings": True,
        "ignoreerrors": False,
        "overwrites": True,
        "retries": 3,
        "concurrent_fragment_downloads": 5,
    }

    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url, download=True)
            if not isinstance(info, dict):
                raise RuntimeError("yt-dlp did not return expected metadata")

            raw_path = Path(ydl.prepare_filename(info))
            title = info.get("title") or raw_path.stem
            ext = info.get("ext") or raw_path.suffix.lstrip(".") or ("mp3" if mode == "audio" else "mp4")

    except Exception as e:
        raise RuntimeError(f"Download failed for {url}: {e}")

    # Sanitize final filename
    safe_name = sanitize_filename(f"{title}.{ext}")
    final_path = output_dir / safe_name

    try:
        if raw_path.resolve() != final_path.resolve():
            if final_path.exists():
                final_path.unlink()
            raw_path.rename(final_path)
    except Exception:
        final_path = raw_path

    # File size check
    try:
        size = final_path.stat().st_size
        if MAX_FILE_SIZE_BYTES is not None and size > MAX_FILE_SIZE_BYTES:
            final_path.unlink(missing_ok=True)
            raise RuntimeError(
                f"Downloaded file size {size} exceeds limit {MAX_FILE_SIZE_BYTES} bytes"
            )
    except Exception as e:
        raise RuntimeError(f"File validation failed: {e}")

    return {
        "filepath": str(final_path.resolve()),
        "filename": final_path.name,
        "title": title,
        "mode": mode,
    }
