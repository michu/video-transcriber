"""Data model representing the result of a video download operation."""
from dataclasses import dataclass
from typing import Optional
from .subtitle_info import SubtitleInfo


@dataclass
class VideoDownloadResult:
    """Holds the output of a completed video download.

    Attributes:
        video_path: Absolute path to the downloaded video file.
        subtitles: List of downloaded subtitle files, or None if no subtitles were downloaded.
    """
    video_path: str
    subtitles: Optional[list[SubtitleInfo]] = None