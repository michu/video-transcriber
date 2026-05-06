"""Dialog utility functions for VideoTranscriber."""
import os
import subprocess
import sys
from tkinter import filedialog


def browse_file() -> str:
    """Open a file picker dialog and return the selected file path, or empty string if cancelled."""
    return filedialog.askopenfilename()


def open_folder(path: str) -> None:
    """Open the given folder in the system file explorer, creating it if it does not exist."""
    os.makedirs(path, exist_ok=True)
    if sys.platform == "win32":
        os.startfile(path)
    elif sys.platform == "darwin":
        subprocess.Popen(["open", path])
    else:
        subprocess.Popen(["xdg-open", path])