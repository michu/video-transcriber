"""Subtitles extractor service for transcribing audio and generating SRT files."""
import os
import shutil
import logging
from typing import Optional
from dataclasses import dataclass
import pysrt
import torch
from models import SubtitleInfo
from faster_whisper import WhisperModel

logger = logging.getLogger(__name__)


@dataclass
class SubtitlesExtractorService:
    """Transcribes audio using Whisper and produces an SRT subtitle file."""

    def __init__(self, model_name: str = "base", device: str = "auto", enable_vad: bool = False):
        resolved_device = "cuda" if (device == "cuda" or (device == "auto" and torch.cuda.is_available())) else "cpu"
        compute_type = self._resolve_compute_type(resolved_device)
        
        self.enable_vad = enable_vad
        self.model = WhisperModel(model_name, device=resolved_device, compute_type=compute_type)
        self.num_beams = 12

    def extract(self, wav_path: str, language_code: Optional[str] = None) -> SubtitleInfo:
        """Transcribe wav_path and return a SubtitleInfo pointing to the generated SRT file."""
        if not wav_path:
            raise ValueError("WAV path cannot be empty")

        if not os.path.exists(wav_path):
            raise FileNotFoundError(f"Audio file not found: {wav_path}")

        logger.info("Transcribing audio...")
        try:
            segments_generator, info = self.model.transcribe(
                wav_path,
                language=language_code,
                beam_size=self.num_beams,
                vad_filter=self.enable_vad,
                word_timestamps=True
            )
            segments = list(segments_generator)
        except Exception as e:
            raise RuntimeError(f"Transcription failed for {wav_path}: {e}") from e

        detected_language = language_code or info.language
        if not language_code:
            logger.info(f"Detected language: {detected_language}")

        base_path = os.path.splitext(wav_path)[0]
        srt_path = f"{base_path}.{detected_language}.srt"
        tmp_srt_path = srt_path + ".tmp"

        os.makedirs(os.path.dirname(os.path.abspath(wav_path)), exist_ok=True)

        logger.info(f"Generating subtitles ({detected_language})...")
        try:
            self._generate_srt(segments, tmp_srt_path)
            shutil.move(tmp_srt_path, srt_path)
        finally:
            if os.path.exists(tmp_srt_path):
                os.remove(tmp_srt_path)

        logger.info(f"Subtitles saved: {srt_path}")
        return SubtitleInfo(language=detected_language, path=srt_path)

    @staticmethod
    def _has_text(text: str) -> bool:
        """Return True if text contains at least one alphanumeric character."""
        return bool(text.strip()) and any(c.isalnum() for c in text)

    def _generate_srt(self, segments, srt_path: str) -> None:
        """Write segments to an SRT file at srt_path using pysrt."""
        srt_file = pysrt.SubRipFile()
        subtitle_index = 1

        for seg in segments:
            text = seg.text.strip()
            if not self._has_text(text):
                continue

            item = pysrt.SubRipItem(
                index=subtitle_index,
                start=pysrt.SubRipTime(seconds=seg.start),
                end=pysrt.SubRipTime(seconds=seg.end),
                text=text
            )
            srt_file.append(item)
            subtitle_index += 1

        srt_file.save(srt_path, encoding="utf-8")
        
    def _resolve_compute_type(self, device: str) -> str:
        if device == "cuda":
            capability = torch.cuda.get_device_capability()
            if capability[0] >= 7:
                return "float16"
            else:
                return "int8_float16"
        return "int8"