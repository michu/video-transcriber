"""Data model representing a single subtitle file."""
from dataclasses import dataclass


@dataclass
class SubtitleInfo:
    """Holds metadata for a single subtitle file.

    Attributes:
        language: ISO 639-1 language code (e.g. 'en', 'pl').
        path: Absolute path to the subtitle file.
    """
    language: str
    path: str