import os
import tempfile
import yt_dlp

FFMPEG_PATH = r"C:\Program Files\ffmpeg-8.1-essentials_build\bin"


def fetch_youtube_track(url: str) -> dict:
    """
    Fetches metadata only (no download). Returns a track dict.
    The actual download happens in download_audio() at playback time.
    """
    ydl_opts = {
        "quiet": True,
        "no_warnings": True,
        "format": "bestaudio/best",
        "noplaylist": True,
    }

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=False)

    thumbnail_url = None
    thumbnails = info.get("thumbnails", [])
    if thumbnails:
        thumbnail_url = thumbnails[-1].get("url")

    return {
        "name":        info.get("title", "Unknown Title"),
        "artists":     "",
        "uri":         url,
        "duration_ms": int(info.get("duration", 0)) * 1000,
        "image_url":   thumbnail_url,
        "source":      "youtube",
    }


def download_audio(url: str) -> str:
    """
    Downloads the audio from a YouTube URL to a temp mp3 file.
    Returns the path to the mp3 file. Caller is responsible for deleting it.
    """
    tmp_dir  = tempfile.mkdtemp()
    tmp_path = os.path.join(tmp_dir, "audio")

    ydl_opts = {
        "quiet": True,
        "no_warnings": True,
        "format": "bestaudio/best",
        "noplaylist": True,
        "outtmpl": tmp_path + ".%(ext)s",
        "ffmpeg_location": FFMPEG_PATH,
        "postprocessors": [{
            "key": "FFmpegExtractAudio",
            "preferredcodec": "mp3",
        }],
    }

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        ydl.extract_info(url, download=True)

    return tmp_path + ".mp3"