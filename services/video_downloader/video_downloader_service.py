"""Video download service for fetching video files from local paths, URLs, and YouTube."""
import os
import shutil
from typing import Optional, Protocol
import requests
import yt_dlp
from yt_dlp.networking.impersonate import ImpersonateTarget
from urllib.parse import urlparse
from models import SubtitleInfo
from models import VideoDownloadResult


class VideoDownloadService(Protocol):
    """Protocol defining the interface for all download strategy implementations."""

    def download(self, source: str, output_path: str, options: Optional[dict] = None) -> VideoDownloadResult:
        ...


class _LocalPathDownloadService:
    """Handles downloads from local file system paths by copying the file to the output location."""

    def download(self, source: str, output_path: str, options: Optional[dict] = None) -> VideoDownloadResult:
        """Copy a local file to output_path and return the result.
        
        If output_path has no extension, the source file extension is appended.
        """
        if not os.path.exists(source):
            raise FileNotFoundError(f"Local file not found: {source}")

        # append source extension to output path if output has none
        src_ext = os.path.splitext(source)[1]
        if src_ext and not os.path.splitext(output_path)[1]:
            output_path = output_path + src_ext

        dir_name = os.path.dirname(output_path)
        if dir_name:
            os.makedirs(dir_name, exist_ok=True)

        shutil.copy2(source, output_path)
        return VideoDownloadResult(output_path, None)


class _UrlDownloadService:
    """Handles downloads from arbitrary HTTP/HTTPS URLs using streaming requests."""

    def download(self, source: str, output_path: str, options: Optional[dict] = None) -> VideoDownloadResult:
        """Stream a remote file to output_path, writing via a .tmp file to avoid partial downloads."""
        dir_name = os.path.dirname(output_path)
        if dir_name:
            os.makedirs(dir_name, exist_ok=True)

        # write to a temporary file first — move to final path only on success
        tmp_path = output_path + ".tmp"
        try:
            with requests.get(source, stream=True, timeout=(10, 60)) as r:
                r.raise_for_status()
                with open(tmp_path, "wb") as f:
                    for chunk in r.iter_content(chunk_size=1024 * 1024):
                        if chunk:
                            f.write(chunk)
            shutil.move(tmp_path, output_path)
        finally:
            # clean up the temporary file if something went wrong
            if os.path.exists(tmp_path):
                os.remove(tmp_path)
        return VideoDownloadResult(output_path, None)


class _YoutubeDownloadService:
    """Handles downloads from YouTube using yt-dlp with optional subtitle retrieval."""

    def download(self, youtube_url: str, output_path: str, options: Optional[dict] = None) -> VideoDownloadResult:
        """Download a YouTube video and optionally its subtitles to output_path."""
        dir_name = os.path.dirname(output_path)
        if dir_name:
            os.makedirs(dir_name, exist_ok=True)

        # yt-dlp uses the base path (without extension) as the output template
        base_path = os.path.splitext(output_path)[0]

        # resolve node.js path from PATH first, fall back to default Windows location
        node_path = shutil.which("node") or r"C:\Program Files\nodejs\node.exe"

        # determine whether to download subtitles based on caller options
        use_youtube_subs = options.get("use_youtube_subs", False) if options else False

        ydl_opts = {
            "js_runtimes": {"node": {"path": node_path}},
            "format": "bestvideo[ext=mp4]+bestaudio[ext=m4a]/mp4",
            "outtmpl": base_path,
            "writesubtitles": use_youtube_subs,
            "writeautomaticsub": use_youtube_subs,
            "subtitlesformat": "srt",
            "quiet": False,
            "impersonate": ImpersonateTarget("chrome"),
        }

        # only pass cookiefile if the file actually exists
        if os.path.exists("cookies.txt"):
            ydl_opts["cookiefile"] = "cookies.txt"

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(youtube_url, download=True)

        # extract the path of the downloaded video file
        downloads = info.get("requested_downloads") or []
        if not downloads:
            raise RuntimeError(f"yt-dlp did not return a file path for: {youtube_url}")
        video_path = downloads[0]["filepath"]

        # collect any subtitle files that were downloaded alongside the video
        subtitles: list[SubtitleInfo] = []
        if "requested_subtitles" in info and info["requested_subtitles"]:
            for lang, _ in info["requested_subtitles"].items():
                sub_path = f"{base_path}.{lang}.srt"
                if os.path.exists(sub_path):
                    subtitles.append(SubtitleInfo(language=lang, path=sub_path))

        return VideoDownloadResult(video_path=video_path, subtitles=subtitles)


class VideoDownloaderService:
    """Facade that routes download requests to the appropriate strategy based on the source type."""

    def __init__(self):
        self._youtube_service = _YoutubeDownloadService()
        self._direct_service = _UrlDownloadService()
        self._local_service = _LocalPathDownloadService()

        self._youtube_hosts = {"youtube.com", "youtu.be"}

    def download(self, source: str, output_path: str, options: Optional[dict] = None) -> VideoDownloadResult:
        """Route the download request to the correct service based on the source type.

        Supports local file paths, direct HTTP/HTTPS URLs, and YouTube links.
        The options dict may contain:
            - use_youtube_subs (bool): whether to download subtitles from YouTube
        """
        parsed = urlparse(source)
        if parsed.scheme in ("http", "https") and parsed.netloc:
            # strip leading www. for host comparison
            host = parsed.netloc.lower().removeprefix("www.")
            if host in self._youtube_hosts:
                return self._youtube_service.download(source, output_path, options)
            else:
                return self._direct_service.download(source, output_path, options)
        else:
            return self._local_service.download(source, output_path, options)