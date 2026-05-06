"""Application configuration."""

# Supported languages for transcription and translation.
# Keys are display names shown in the UI, values are ISO 639-1 codes.
# None means auto-detection.
LANGUAGES = {
    "Auto Detect": None,
    "Czech": "cs",
    "Dutch": "nl",
    "English": "en",
    "French": "fr",
    "German": "de",
    "Italian": "it",
    "Polish": "pl",
    "Portuguese": "pt",
    "Spanish": "es"
}

# Available Whisper transcription models.
# The openai-whisper- prefix is stripped before passing the name to faster-whisper.
TRANSCRIPTION_MODELS = [
    "openai-whisper-base",
    "openai-whisper-tiny",
    "openai-whisper-small",
    "openai-whisper-medium",
    "openai-whisper-large-v2",
    "openai-whisper-large-v3",
    "openai-whisper-large-v3-turbo"
]

# Available NLLB translation models.
TRANSLATION_MODELS = [
    "facebook/nllb-200-distilled-600M",
    "facebook/nllb-200-distilled-1.3B",
    "facebook/nllb-200-1.3B",
    "facebook/nllb-200-3.3B"
]

# Main window dimensions in pixels.
WINDOW_WIDTH = 950
WINDOW_HEIGHT = 720