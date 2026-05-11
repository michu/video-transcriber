"""Entry point for the VideoTranscriber application."""
import logging
from ui.ui import App

if __name__ == "__main__":
    app = App(title="Video Transcriber")
    
    logging.basicConfig(
        level=logging.INFO,
        format="[%(name)s] %(message)s",
    )
    
    app.mainloop()