"""Interface graphique de Fencing Videos Downloader (CustomTkinter)."""

from __future__ import annotations

import os
import queue
import subprocess
import sys
import threading
from pathlib import Path
from tkinter import filedialog

import customtkinter as ctk

from fencing_videos_downloader import __version__
from fencing_videos_downloader.downloader import (
    ClipRequest,
    DownloadError,
    download_stream_clip,
    download_youtube_clip,
    is_stream_url,
)
from fencing_videos_downloader.utils import (
    desktop_dir,
    parse_timestamp,
    resource_path,
    sanitize_filename,
)

APP_NAME = "Fencing Videos Downloader"
COLOR_SUCCESS = "#2fa572"
COLOR_ERROR = "#e5484d"
PAD = 6


class ClipForm(ctk.CTkFrame):
    """Formulaire de découpe : accepte une URL YouTube ou un flux m3u8 (FencingTV)."""

    def __init__(self, master):
        super().__init__(master, fg_color="transparent")
        self._events: queue.Queue = queue.Queue()
        self._indeterminate = False
        self._result_dir: Path | None = None

        self.grid_columnconfigure((0, 1), weight=1, uniform="col")

        self._url_entry = self._labeled_entry(
            0,
            0,
            "URL de la vidéo (YouTube ou flux FencingTV)",
            "https://www.youtube.com/watch?v=…  ou  https://…/playlist.m3u8",
            columnspan=2,
        )
        self._detection = ctk.CTkLabel(
            self,
            text="",
            anchor="w",
            font=ctk.CTkFont(size=12),
            text_color=("gray40", "gray60"),
        )
        self._detection.grid(row=2, column=0, columnspan=2, sticky="ew", padx=PAD, pady=(2, 0))
        self._url_entry.bind("<KeyRelease>", self._update_detection)

        self._start_entry = self._labeled_entry(3, 0, "Début", "ex. 2:35")
        self._end_entry = self._labeled_entry(3, 1, "Fin", "ex. 2:42")
        self._name_entry = self._labeled_entry(
            5, 0, "Nom du clip (facultatif)", "généré automatiquement si vide", columnspan=2
        )

        ctk.CTkLabel(self, text="Dossier de destination", anchor="w").grid(
            row=7, column=0, columnspan=2, sticky="ew", padx=PAD, pady=(14, 2)
        )
        folder_row = ctk.CTkFrame(self, fg_color="transparent")
        folder_row.grid(row=8, column=0, columnspan=2, sticky="ew", padx=PAD)
        folder_row.grid_columnconfigure(0, weight=1)
        self._folder_entry = ctk.CTkEntry(folder_row)
        self._folder_entry.insert(0, str(desktop_dir()))
        self._folder_entry.grid(row=0, column=0, sticky="ew", padx=(0, 8))
        ctk.CTkButton(folder_row, text="Parcourir…", width=110, command=self._browse).grid(
            row=0, column=1
        )

        self._download_button = ctk.CTkButton(
            self,
            text="Télécharger le clip",
            height=40,
            font=ctk.CTkFont(size=15, weight="bold"),
            command=self._submit,
        )
        self._download_button.grid(
            row=9, column=0, columnspan=2, sticky="ew", padx=PAD, pady=(22, 10)
        )

        self._progress = ctk.CTkProgressBar(self)
        self._progress.set(0)
        self._progress.grid(row=10, column=0, columnspan=2, sticky="ew", padx=PAD)

        self._status = ctk.CTkLabel(self, text="Prêt.", anchor="w", wraplength=520, justify="left")
        self._default_text_color = self._status.cget("text_color")
        self._status.grid(row=11, column=0, columnspan=2, sticky="ew", padx=PAD, pady=(8, 0))

        self._open_button = ctk.CTkButton(
            self, text="Ouvrir le dossier", width=140, command=self._open_folder
        )
        self._open_button.grid(row=12, column=0, columnspan=2, padx=PAD, pady=(10, 0))
        self._open_button.grid_remove()

    # ------------------------------------------------------------------ UI

    def _labeled_entry(
        self, row: int, column: int, label: str, placeholder: str, columnspan: int = 1
    ) -> ctk.CTkEntry:
        ctk.CTkLabel(self, text=label, anchor="w").grid(
            row=row, column=column, columnspan=columnspan, sticky="ew", padx=PAD, pady=(14, 2)
        )
        entry = ctk.CTkEntry(self, placeholder_text=placeholder)
        entry.grid(row=row + 1, column=column, columnspan=columnspan, sticky="ew", padx=PAD)
        return entry

    def _update_detection(self, _event=None) -> None:
        url = self._url_entry.get().strip()
        if not url:
            self._detection.configure(text="")
        elif is_stream_url(url):
            self._detection.configure(text="Source détectée : flux FencingTV (m3u8)")
        else:
            self._detection.configure(text="Source détectée : YouTube")

    def _browse(self) -> None:
        chosen = filedialog.askdirectory(initialdir=self._folder_entry.get() or str(desktop_dir()))
        if chosen:
            self._folder_entry.delete(0, "end")
            self._folder_entry.insert(0, chosen)

    def _show_status(self, message: str, color: str | None = None) -> None:
        self._status.configure(text=message, text_color=color or self._default_text_color)

    def _set_progress(self, fraction: float | None) -> None:
        if fraction is None:
            if not self._indeterminate:
                self._progress.configure(mode="indeterminate")
                self._progress.start()
                self._indeterminate = True
        else:
            if self._indeterminate:
                self._progress.stop()
                self._progress.configure(mode="determinate")
                self._indeterminate = False
            self._progress.set(max(0.0, min(1.0, fraction)))

    # ------------------------------------------------------------ Actions

    def _submit(self) -> None:
        url = self._url_entry.get().strip()
        if not url.startswith(("http://", "https://")):
            return self._fail("Veuillez saisir une URL valide (commençant par http ou https).")

        try:
            start = parse_timestamp(self._start_entry.get())
        except ValueError as exc:
            return self._fail(f"Horodatage de début invalide — {exc}.")
        try:
            end = parse_timestamp(self._end_entry.get())
        except ValueError as exc:
            return self._fail(f"Horodatage de fin invalide — {exc}.")
        if end <= start:
            return self._fail("L'horodatage de fin doit être après celui de début.")

        folder_text = self._folder_entry.get().strip() or str(desktop_dir())
        dest_dir = Path(folder_text).expanduser()
        try:
            dest_dir.mkdir(parents=True, exist_ok=True)
        except OSError:
            return self._fail("Impossible d'utiliser ce dossier de destination.")

        name = sanitize_filename(self._name_entry.get()) or None
        request = ClipRequest(url=url, start=start, end=end, dest_dir=dest_dir, name=name)
        download_fn = download_stream_clip if is_stream_url(url) else download_youtube_clip

        self._download_button.configure(state="disabled", text="Téléchargement en cours…")
        self._open_button.grid_remove()
        self._set_progress(None)
        self._show_status("Préparation…")
        threading.Thread(target=self._worker, args=(download_fn, request), daemon=True).start()
        self.after(100, self._poll)

    def _fail(self, message: str) -> None:
        self._show_status(message, COLOR_ERROR)

    def _worker(self, download_fn, request: ClipRequest) -> None:
        try:
            path = download_fn(
                request,
                lambda fraction: self._events.put(("progress", fraction)),
                lambda message: self._events.put(("status", message)),
            )
        except DownloadError as exc:
            self._events.put(("error", str(exc)))
        except Exception as exc:  # garde-fou : ne jamais laisser mourir le fil en silence
            self._events.put(("error", f"Erreur inattendue : {exc}"))
        else:
            self._events.put(("done", path))

    def _poll(self) -> None:
        try:
            while True:
                kind, payload = self._events.get_nowait()
                if kind == "progress":
                    self._set_progress(payload)
                elif kind == "status":
                    self._show_status(payload)
                elif kind == "done":
                    self._finish_success(payload)
                    return
                elif kind == "error":
                    self._finish_error(payload)
                    return
        except queue.Empty:
            pass
        self.after(100, self._poll)

    def _finish_success(self, path: Path) -> None:
        self._set_progress(1.0)
        self._show_status(f"Clip enregistré : {path.name}", COLOR_SUCCESS)
        self._result_dir = path.parent
        self._open_button.grid()
        self._download_button.configure(state="normal", text="Télécharger le clip")

    def _finish_error(self, message: str) -> None:
        self._set_progress(0)
        self._show_status(message, COLOR_ERROR)
        self._download_button.configure(state="normal", text="Télécharger le clip")

    def _open_folder(self) -> None:
        target = self._result_dir
        if target is None or not target.is_dir():
            return
        if sys.platform == "win32":
            os.startfile(target)  # noqa: S606 — ouverture volontaire de l'explorateur
        elif sys.platform == "darwin":
            subprocess.Popen(["open", str(target)])
        else:
            subprocess.Popen(["xdg-open", str(target)])


class HelpTab(ctk.CTkScrollableFrame):
    """Indications pas à pas pour récupérer l'URL m3u8 d'une vidéo FencingTV."""

    _IMAGE_WIDTH = 540
    _STEPS = (
        (
            "text",
            "1.  Une fois sur le site FencingTV, appuyez sur F12 puis dirigez-vous "
            "dans l'onglet « Network » (Réseau) et tapez « m3u8 » dans le filtre.",
        ),
        ("image", "etape1.png"),
        (
            "text",
            "2.  Sélectionnez la piste de la vidéo que vous souhaitez télécharger. "
            "S'il n'y a qu'une seule piste disponible, rechargez la page FencingTV "
            "(en appuyant sur F5).",
        ),
        (
            "text",
            "3.  Plusieurs lignes apparaîtront. Sélectionnez la première et cliquez "
            "sur le champ « File ».",
        ),
        ("image", "etape2.png"),
        (
            "text",
            "4.  Un panneau apparaîtra, contenant une URL commençant par "
            "« https://stream.mux.com/ » et finissant par « .m3u8 ». Copiez-la : "
            "c'est cette URL qu'il faut coller dans l'onglet « Télécharger ».",
        ),
        ("image", "etape3.png"),
    )

    def __init__(self, master):
        super().__init__(master, fg_color="transparent")
        for kind, content in self._STEPS:
            if kind == "text":
                self._add_text(content)
            else:
                self._add_image(content)

    def _add_text(self, content: str) -> None:
        ctk.CTkLabel(
            self,
            text=content,
            anchor="w",
            justify="left",
            wraplength=self._IMAGE_WIDTH,
            font=ctk.CTkFont(size=13),
        ).pack(fill="x", padx=PAD, pady=(14, 2))

    def _add_image(self, filename: str) -> None:
        path = resource_path(Path("assets") / "aide" / filename)
        if not path.is_file():
            ctk.CTkLabel(
                self,
                text=f"(capture d'écran manquante : {filename})",
                text_color=("gray50", "gray55"),
                font=ctk.CTkFont(size=12, slant="italic"),
            ).pack(padx=PAD, pady=4)
            return
        from PIL import Image

        image = Image.open(path)
        scale = self._IMAGE_WIDTH / image.width
        ctk_image = ctk.CTkImage(
            light_image=image,
            dark_image=image,
            size=(self._IMAGE_WIDTH, round(image.height * scale)),
        )
        ctk.CTkLabel(self, image=ctk_image, text="").pack(padx=PAD, pady=6)


class AppWindow(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title(f"{APP_NAME} {__version__}")
        self.geometry("660x700")
        self.minsize(600, 640)
        self._apply_window_icon()

        header = ctk.CTkFrame(self, fg_color="transparent")
        header.pack(fill="x", padx=28, pady=(22, 0))
        ctk.CTkLabel(
            header, text=APP_NAME, font=ctk.CTkFont(size=28, weight="bold"), anchor="w"
        ).pack(fill="x")

        tabs = ctk.CTkTabview(self)
        tabs.pack(fill="both", expand=True, padx=28, pady=16)
        download_tab = tabs.add("Télécharger")
        help_tab = tabs.add("Indications pour récupérer une URL FencingTV")

        ClipForm(download_tab).pack(fill="both", expand=True, padx=12, pady=8)
        HelpTab(help_tab).pack(fill="both", expand=True, padx=12, pady=8)

        ctk.CTkLabel(
            self,
            text="Propulsé par yt-dlp et FFmpeg — Licence MIT",
            text_color=("gray55", "gray50"),
            font=ctk.CTkFont(size=11),
        ).pack(pady=(0, 10))

    def _apply_window_icon(self) -> None:
        """Applique l'icône à la barre de titre et à la barre des tâches."""
        try:
            if sys.platform == "win32":
                ico = resource_path(Path("assets") / "icon.ico")
                if ico.is_file():
                    self.iconbitmap(default=str(ico))
                    return
            png = resource_path(Path("assets") / "icon.png")
            if png.is_file():
                from PIL import Image, ImageTk

                self._icon_image = ImageTk.PhotoImage(Image.open(png))
                self.iconphoto(True, self._icon_image)
        except Exception:
            # Une icône manquante ne doit jamais empêcher l'application de démarrer.
            pass


def main() -> None:
    ctk.set_appearance_mode("system")
    ctk.set_default_color_theme("blue")
    app = AppWindow()
    app.mainloop()
