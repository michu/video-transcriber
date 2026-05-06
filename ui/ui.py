"""Main application window for Video Transcriber."""
import sys
import queue
import shutil
import threading
import time
import os
import tkinter as tk

import customtkinter as ctk

from config import TRANSCRIPTION_MODELS, TRANSLATION_MODELS, LANGUAGES, WINDOW_WIDTH, WINDOW_HEIGHT
from ui import components, dialogs
from services.video_downloader import VideoDownloaderService
from services.audio_extractor import AudioExtractorService
from services.subtitles_extractor import SubtitlesExtractorService
from services.subtitles_translator import SubtitlesTranslatorService

ctk.set_appearance_mode("system")
ctk.set_default_color_theme("blue")


class QueueLogger:
    """Redirects stdout/stderr writes to a thread-safe queue for UI consumption."""

    def __init__(self, q: queue.Queue):
        self.q = q
        self._buffer = ""

    def write(self, msg: str):
        if not msg:
            return

        self._buffer += msg

        lines = self._buffer.splitlines(keepends=True)
        self._buffer = ""

        for line in lines:
            line_clean = line.rstrip("\r\n")
            if line_clean.startswith("[download]"):
                self.q.put(("overwrite", line_clean))
            else:
                self.q.put(("append", line_clean + "\n"))

    def flush(self):
        pass


class App(ctk.CTk):
    """Main application window."""

    def __init__(self, title: str = "Video Transcriber"):
        super().__init__()
        self.title(title)
        self.geometry(f"{WINDOW_WIDTH}x{WINDOW_HEIGHT}")

        self._init_state()
        self._redirect_output()

        self.protocol("WM_DELETE_WINDOW", self._on_closing)
        self.build_ui()
        self.after(100, self._process_log_queue)

    def _init_state(self):
        """Initialise all state variables before the UI is built."""
        self.log_queue = queue.Queue()
        self.languages_selected = ["Auto Detect"]
        self.running = False
        self.start_time: float = 0.0
        self._threads: list[threading.Thread] = []

    def _redirect_output(self):
        """Redirect stdout and stderr to the log queue."""
        self._original_stdout = sys.stdout
        self._original_stderr = sys.stderr
        logger = QueueLogger(self.log_queue)
        sys.stdout = logger
        sys.stderr = logger

    def _on_closing(self):
        """Restore stdout/stderr and close the window cleanly."""
        sys.stdout = self._original_stdout
        sys.stderr = self._original_stderr
        self.destroy()

    def build_ui(self):
        """Build and layout all UI widgets."""

        # Form frame
        form_frame = components.create_frame(
            self,
            pack_kwargs={"fill": "x", "padx": 15, "pady": 10},
            fg_color="transparent"
        )

        # Transcription model
        components.create_label(
            form_frame,
            "Transcription Model:",
            grid_kwargs={"row": 0, "column": 0, "sticky": "w", "padx": 5, "pady": 5}
        )
        self.transcription_model_box = components.create_combo(
            form_frame,
            values=TRANSCRIPTION_MODELS,
            default=TRANSCRIPTION_MODELS[0],
            grid_kwargs={"row": 0, "column": 1, "sticky": "ew", "padx": 5, "pady": 5}
        )
        
        # Enable VAD option
        self.enable_vad = components.create_checkbox(
            form_frame,
            text="Enable VAD",
            grid_kwargs={"row": 1, "column": 1, "sticky": "w", "padx": 5, "pady": 5}
        )
        #self.enable_vad.set(True)

        # Translation model
        components.create_label(
            form_frame,
            "Translation Model:",
            grid_kwargs={"row": 2, "column": 0, "sticky": "w", "padx": 5, "pady": 5}
        )
        self.translation_model_box = components.create_combo(
            form_frame,
            values=TRANSLATION_MODELS,
            default=TRANSLATION_MODELS[0],
            grid_kwargs={"row": 2, "column": 1, "sticky": "ew", "padx": 5, "pady": 5}
        )

        # Source language
        components.create_label(
            form_frame,
            "Source language:",
            grid_kwargs={"row": 3, "column": 0, "sticky": "w", "padx": 5, "pady": 5}
        )
        self.source_lang = components.create_combo(
            form_frame,
            values=list(LANGUAGES.keys()),
            default="Auto Detect",
            grid_kwargs={"row": 3, "column": 1, "sticky": "ew", "padx": 5, "pady": 5},
            command=self._on_source_language_selected
        )

        # Subtitle language
        components.create_label(
            form_frame,
            "Subtitle language:",
            grid_kwargs={"row": 4, "column": 0, "sticky": "w", "padx": 5, "pady": 5}
        )
        lang_row = components.create_frame(
            form_frame,
            fg_color="transparent",
            grid_kwargs={"row": 4, "column": 1, "sticky": "ew"}
        )
        self.lang_entry = components.create_combo(
            lang_row,
            values=list(LANGUAGES.keys()),
            default="Auto Detect",
            pack_kwargs={"side": "left", "fill": "x", "expand": True, "padx": 5}
        )
        self.add_lang_btn = components.create_button(
            lang_row,
            text="Add",
            command=self.add_language,
            width=80,
            pack_kwargs={"side": "left", "padx": 5}
        )

        # Selected languages chip list
        components.create_label(
            form_frame,
            "Selected subtitle languages:",
            grid_kwargs={"row": 5, "column": 0, "sticky": "w", "padx": 5, "pady": 5}
        )
        self.lang_list_frame = components.create_frame(
            form_frame,
            fg_color="transparent",
            grid_kwargs={"row": 5, "column": 1, "sticky": "ew", "padx": 5, "pady": 5}
        )
        self.render_language_list()

        # File path
        components.create_label(
            form_frame,
            "File path or URL:",
            grid_kwargs={"row": 6, "column": 0, "sticky": "w", "padx": 5, "pady": 5}
        )
        file_row = components.create_frame(
            form_frame,
            fg_color="transparent",
            grid_kwargs={"row": 6, "column": 1, "sticky": "ew"}
        )
        self.path_entry = components.create_entry(
            file_row,
            pack_kwargs={"side": "left", "fill": "x", "expand": True, "padx": 5}
        )
        self.browse_btn = components.create_button(
            file_row,
            text="Browse",
            command=self.browse_file,
            width=90,
            pack_kwargs={"side": "left", "padx": 5}
        )

        # YouTube subtitles option
        self.use_yt_subs = components.create_checkbox(
            form_frame,
            text="Use YouTube subtitles if available",
            grid_kwargs={"row": 7, "column": 1, "sticky": "w", "padx": 5, "pady": 10}
        )

        # Start button
        btn_row = components.create_frame(
            form_frame,
            fg_color="transparent",
            grid_kwargs={"row": 8, "column": 0, "columnspan": 2, "sticky": "ew", "pady": 10}
        )
        self.start_btn = components.create_button(
            btn_row,
            text="Start",
            command=self.start_transcription,
            pack_kwargs={"side": "left", "padx": 5}
        )
        
        # Open data folder button
        self.open_data_btn = components.create_button(
            btn_row,
            text="Open data folder",
            command=self.open_data_folder,
            pack_kwargs={"side": "right", "padx": 5}
        )

        # Log box
        components.create_label(
            self,
            "Log:",
            pack_kwargs={"padx": 15, "anchor": "w"}
        )
        self.log_box = ctk.CTkTextbox(self, state="disabled")
        self.log_box.pack(fill="both", expand=True, padx=15, pady=(0, 20))

        # Allow Ctrl+A and copy but block direct editing
        def _block_edit(event):
            if event.state & 0x4:  # allow Ctrl+key shortcuts
                return
            return "break"

        self.log_box.bind("<Key>", _block_edit)
        self.log_box.bind("<Control-v>", lambda e: "break")

        # Status bar
        self.status_bar = ctk.CTkFrame(self, height=30)
        self.status_bar.pack(side="bottom", fill="x")

        self.status_label = ctk.CTkLabel(self.status_bar, text="Ready", anchor="w")
        self.status_label.pack(side="left", padx=10)

        self.progress = ctk.CTkProgressBar(self.status_bar)
        self.progress.pack(side="right", fill="x", expand=True, padx=10, pady=5)
        self.progress.pack_forget()  # hidden on startup

        form_frame.grid_columnconfigure(1, weight=1)

    def add_language(self):
        """Add the selected language to the chip list."""
        lang = self.lang_entry.get().strip()
        if not lang or lang == "Auto Detect":
            return
        if lang not in self.languages_selected:
            self.languages_selected.append(lang)
        self.render_language_list()

    def _on_source_language_selected(self, value: str):
        """Replace the primary language chip when a source language is picked."""
        if not value or not self.languages_selected:
            return
        self.languages_selected[0] = value
        self.render_language_list()

    def remove_language(self, lang: str):
        """Remove a language chip — the first (primary) language cannot be removed."""
        if not self.languages_selected or self.languages_selected[0] == lang:
            return
        if lang in self.languages_selected:
            self.languages_selected.remove(lang)
        self.render_language_list()

    def render_language_list(self):
        """Re-render all language chips from the current selection."""
        self.lang_remove_buttons = []
        for widget in self.lang_list_frame.winfo_children():
            widget.destroy()

        for i, lang in enumerate(self.languages_selected):
            chip = ctk.CTkFrame(self.lang_list_frame)
            chip.pack(side="left", padx=5)

            ctk.CTkLabel(chip, text=lang).pack(side="left", padx=6)

            # the first (primary) language chip cannot be removed
            btn = ctk.CTkButton(
                chip,
                text="X",
                width=24,
                state="disabled" if i == 0 else "normal",
                command=(lambda l=lang: self.remove_language(l)) if i != 0 else None
            )
            btn.pack(side="right", padx=2)
            self.lang_remove_buttons.append(btn)

    def browse_file(self):
        """Open a file dialog and populate the path entry."""
        file = dialogs.browse_file()
        if file:
            self.path_entry.delete(0, tk.END)
            self.path_entry.insert(0, file)
            
    def open_data_folder(self):
        """Open the output data folder in the system file explorer."""
        data_folder = os.path.abspath("data")
        if not os.path.exists(data_folder):
            os.makedirs(data_folder, exist_ok=True)

        if sys.platform == "win32":
            os.startfile(data_folder)
        elif sys.platform == "darwin":
            subprocess.run(["open", data_folder])
        else:
            subprocess.run(["xdg-open", data_folder])

    def start_transcription(self):
        """Validate inputs and launch the processing thread."""
        source = self.path_entry.get().strip()
        if not source:
            print("No source provided.")
            return

        # clean up finished threads before adding a new one
        self._threads = [t for t in self._threads if t.is_alive()]

        self._toggle_ui(False)

        self.log_box.configure(state="normal")
        self.log_box.delete("1.0", tk.END)
        self.log_box.configure(state="disabled")

        self.progress.pack(side="right", fill="x", expand=True, padx=10, pady=5)
        self.progress.start()
        self.status_label.configure(text="Processing...")
        self.start_time = time.time()

        t = threading.Thread(target=self._process, args=(source,), daemon=True)
        self._threads.append(t)
        t.start()

    def _process(self, source: str):
        """Worker thread — runs the full transcription and translation pipeline."""
        output_dir = os.path.abspath("data")
        output_path = os.path.join(output_dir, "video")
        result = None

        try:
            # clear and recreate the output directory
            if os.path.exists(output_dir):
                shutil.rmtree(output_dir)
            os.makedirs(output_dir, exist_ok=True)
            print(f"Cleared output directory: {output_dir}")

            # download file if source is a URL, otherwise just copy to output directory
            downloader = VideoDownloaderService()
            result = downloader.download(source, output_path, {
                "use_youtube_subs": self.use_yt_subs.get()
            })
            print(f"Download finished: {result.video_path}")
            if result.subtitles:
                print(f"Found {len(result.subtitles)} subtitle(s)")
                for sub in result.subtitles:
                    print(f"  - {sub.language}: {sub.path}")

            # extract audio and subtitles (if not already from YouTube)
            if result.subtitles:
                language_code = result.subtitles[0].language
                print(f"Using language from downloaded subtitles: {language_code}")
            else:
                audio_service = AudioExtractorService()
                wav_path = audio_service.extract(result.video_path)
                print(f"Audio extracted: {wav_path}")

                language_name = self.source_lang.get()
                language_code = LANGUAGES[language_name]
                print(f"Using language from UI selection: {language_code}")

                model_name = self.transcription_model_box.get() or TRANSCRIPTION_MODELS[0]
                subtitles_service = SubtitlesExtractorService(
                    model_name=model_name.removeprefix("openai-whisper-"),
                    enable_vad=self.enable_vad.get()
                )
                result.subtitles = [subtitles_service.extract(wav_path, language_code=language_code)]
                print(f"Subtitles extracted: {result.subtitles[0].path}")

            # translate subtitles if needed
            if len(self.languages_selected) == 1:
                return

            srt_path = result.subtitles[0].path
            language = result.subtitles[0].language

            model_name = self.translation_model_box.get() or TRANSLATION_MODELS[0]
            translator = SubtitlesTranslatorService(model_name=model_name)

            for target_name in self.languages_selected:
                if target_name == "Auto Detect":
                    continue

                target_iso = LANGUAGES.get(target_name)
                if not target_iso:
                    continue

                if target_iso == language:
                    continue

                dir_name = os.path.dirname(srt_path)
                parts = os.path.basename(srt_path).split(".")
                base = ".".join(parts[:-2]) if len(parts) >= 3 else parts[0]
                out_path = os.path.join(dir_name, f"{base}.{target_iso}.srt")

                print(f"Translating {srt_path} -> {out_path} (src={language} tgt={target_iso})")
                translator.translate_file(srt_path, out_path, src_lang=language, tgt_lang=target_iso)
                print(f"Translated subtitles saved: {out_path}")

        except Exception as e:
            print(f"Processing failed: {e}")
        finally:
            self.after(0, self._on_process_finished)

    def _on_process_finished(self):
        """Called on the main thread after the worker finishes."""
        self._toggle_ui(True)
        self.progress.stop()
        self.progress.pack_forget()

        elapsed = int(time.time() - self.start_time)
        h, remainder = divmod(elapsed, 3600)
        m, s = divmod(remainder, 60)
        self.status_label.configure(text=f"Finished ({h}h {m}m {s}s)")

    def _toggle_ui(self, enabled: bool):
        """Enable or disable interactive widgets during processing."""
        combo_state = "readonly" if enabled else "disabled"
        widget_state = "normal" if enabled else "disabled"

        for widget in [
            self.transcription_model_box,
            self.enable_vad,
            self.translation_model_box,
            self.source_lang,
            self.lang_entry,
            self.add_lang_btn,
            self.path_entry,
            self.browse_btn,
            self.use_yt_subs,
        ]:
            if isinstance(widget, ctk.CTkComboBox):
                widget.configure(state=combo_state)
            else:
                widget.configure(state=widget_state)

        for btn in getattr(self, "lang_remove_buttons", []):
            btn.configure(state=widget_state)

        self.start_btn.configure(state=widget_state)

    def _process_log_queue(self):
        """Drain up to 20 queued log messages per tick to avoid UI freezes."""
        for _ in range(20):
            if self.log_queue.empty():
                break
            mode, msg = self.log_queue.get()
            self.log_box.configure(state="normal")
            if mode == "append":
                self.log_box.insert(tk.END, msg)
            elif mode == "overwrite":
                last_line_start = self.log_box.index("end-1c linestart")
                self.log_box.delete(last_line_start, "end-1c")
                self.log_box.insert(last_line_start, msg)
            self.log_box.see(tk.END)
            self.log_box.configure(state="disabled")
        self.after(100, self._process_log_queue)


if __name__ == "__main__":
    app = App()
    app.mainloop()