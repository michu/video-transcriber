"""Audio extractor service for extracting audio from video files."""
import os
import shutil
import subprocess


class AudioExtractorService:
    """Extracts audio track from a video file using FFmpeg."""

    def extract(self, video_path: str) -> str:
        """Extract audio from video_path and return path to the resulting WAV file."""
        if not video_path:
            raise ValueError("Video path cannot be empty")

        if not os.path.exists(video_path):
            raise FileNotFoundError(f"Video file not found: {video_path}")

        base_path = os.path.splitext(video_path)[0]
        wav_path = f"{base_path}.wav"
        tmp_wav_path = wav_path + ".tmp"

        os.makedirs(os.path.dirname(os.path.abspath(video_path)), exist_ok=True)

        try:
            subprocess.run([
                "ffmpeg", "-y", "-i", video_path,
                "-vn", "-acodec", "pcm_s16le", "-ar", "16000", "-ac", "1",
                "-f", "wav",
                tmp_wav_path
            ], check=True, capture_output=True, text=True)
            shutil.move(tmp_wav_path, wav_path)
        except subprocess.CalledProcessError as e:
            raise RuntimeError(f"FFmpeg failed to extract audio: {e.stderr}")
        except FileNotFoundError:
            raise RuntimeError("FFmpeg is not installed or not in PATH")
        finally:
            if os.path.exists(tmp_wav_path):
                os.remove(tmp_wav_path)

        if not os.path.exists(wav_path):
            raise RuntimeError(f"Failed to create WAV file: {wav_path}")

        return wav_path