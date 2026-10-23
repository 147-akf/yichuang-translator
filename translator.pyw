#!/usr/bin/env python3
"""译窗 Translator — a small always-on-top Chinese <-> English translator.

Appearance has four equal options: dark, light, cream, or a custom image/video
wallpaper. The wallpaper fills the window; translucent theme-coloured bands at
the top and bottom keep the text readable. Clipboard reading is manual by
default, with an optional auto-read mode.
"""

from __future__ import annotations

import ctypes
import json
import os
import queue
import re
import sys
import threading
import time
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, font as tkfont, messagebox, ttk

from engine import TranslationError, translate

try:
    from PIL import Image, ImageOps, ImageTk

    HAS_PIL = True
except ImportError:  # wallpapers are optional
    Image = ImageOps = ImageTk = None
    HAS_PIL = False

try:
    import cv2

    HAS_CV2 = True
except ImportError:  # video wallpapers are optional
    cv2 = None
    HAS_CV2 = False

APP_NAME = "译窗 Translator"
_config_override = os.environ.get("TRANSLATOR_CONFIG")
CONFIG_PATH = (
    Path(_config_override).expanduser()
    if _config_override
    else Path.home() / ".desktop_translator.json"
)

FONT = "Microsoft YaHei UI"

THEMES = {
    "dark": {
        "bg": "#14161a",
        "card": "#1e2229",
        "output_bg": "#191d23",
        "text": "#e8ecf2",
        "muted": "#8b94a3",
        "border": "#2d333d",
        "accent": "#4f7cff",
        "accent_hover": "#6a90ff",
        "accent_disabled": "#3b4c7a",
        "secondary": "#232932",
        "secondary_hover": "#2e3540",
        "placeholder": "#6c7686",
        "error": "#ff6b6b",
        "success": "#4ade80",
        "select_bg": "#35528f",
        "select_fg": "#ffffff",
    },
    "light": {
        "bg": "#f4f5f7",
        "card": "#ffffff",
        "output_bg": "#fbfcfd",
        "text": "#1f2329",
        "muted": "#7a828e",
        "border": "#dfe3e8",
        "accent": "#3b6ef6",
        "accent_hover": "#2f5ee0",
        "accent_disabled": "#9db4f8",
        "secondary": "#eceef1",
        "secondary_hover": "#e1e4e8",
        "placeholder": "#a0a6b0",
        "error": "#d93026",
        "success": "#1a9c5b",
        "select_bg": "#cfe0ff",
        "select_fg": "#1f2329",
    },
    "cream": {
        "bg": "#f5efe3",
        "card": "#fffdf8",
        "output_bg": "#faf5ea",
        "text": "#3b342a",
        "muted": "#8c8170",
        "border": "#e3d8c6",
        "accent": "#b0763c",
        "accent_hover": "#96602d",
        "accent_disabled": "#d9c3a8",
        "secondary": "#ede4d5",
        "secondary_hover": "#e3d7c4",
        "placeholder": "#b1a591",
        "error": "#c0392b",
        "success": "#2f7d4f",
        "select_bg": "#e6d3b6",
        "select_fg": "#3b342a",
    },
}
THEME_LABELS = {"dark": "黑色", "light": "白色", "cream": "米白色"}
APPEARANCE_ORDER = ["dark", "light", "cream", "custom"]
APPEARANCE_LABELS = {
    "dark": "黑色",
    "light": "白色",
    "cream": "米白色",
    "custom": "自定义壁纸",
}

DIRECTION_LABELS = ["自动检测", "中文 → 英文", "英文 → 中文"]
DIRECTION_MODES = ["auto", "zh-en", "en-zh"]

LANGUAGE_NAMES = {
    "zh": "中文",
    "en": "英语",
    "ja": "日语",
    "ko": "韩语",
    "fr": "法语",
    "de": "德语",
    "es": "西班牙语",
    "ru": "俄语",
    "it": "意大利语",
    "pt": "葡萄牙语",
    "ar": "阿拉伯语",
}

IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".bmp", ".gif", ".webp", ".tif", ".tiff"}
VIDEO_EXTS = {
    ".mp4",
    ".mkv",
    ".mov",
    ".avi",
    ".wmv",
    ".webm",
    ".m4v",
    ".mpg",
    ".mpeg",
    ".flv",
    ".ts",
}
IMAGE_PATTERN = "*.png *.jpg *.jpeg *.bmp *.gif *.webp *.tif *.tiff"
VIDEO_PATTERN = (
    "*.mp4 *.mkv *.mov *.avi *.wmv *.webm *.m4v *.mpg *.mpeg *.flv *.ts"
)

RESAMPLE = (
    getattr(getattr(Image, "Resampling", Image), "LANCZOS", 1) if HAS_PIL else None
)
VIDEO_FPS_CAP = 15.0


def resource_path(name: str) -> Path:
    base = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))
    return base / name


def language_name(code: str) -> str:
    if not code:
        return "未知"
    base = code.split("-")[0].lower()
    return LANGUAGE_NAMES.get(base, code.upper())


def load_config() -> dict:
    defaults = {
        "geometry": "",
        "topmost": True,
        "auto_translate": True,
        "watch_clipboard": False,
        "direction": "auto",
        "theme": "light",
        "wallpaper": "",
        "wallpaper_type": "",
        "text_transparency": 0,
    }
    try:
        data = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
        if isinstance(data, dict):
            for key in defaults:
                if key in data:
                    defaults[key] = data[key]
    except (OSError, ValueError):
        pass
    return defaults


class CanvasCheck:
    """A checkbox drawn directly on the main canvas.

    Drawing it on the canvas (instead of using a Frame/Label) keeps the
    wallpaper visible behind the checkbox in custom-wallpaper mode.
    """

    def __init__(
        self,
        app: "TranslatorApp",
        text: str,
        variable: tk.BooleanVar,
        command=None,
    ) -> None:
        self.app = app
        self.canvas = app.canvas
        self.variable = variable
        self.command = command
        self.text = text
        self.tag = f"check{id(self)}"
        self._left = 0
        self._y = 0
        self._hover = False
        size = app.px(18)
        self.indicator = self.canvas.create_rectangle(
            0,
            0,
            size,
            size,
            fill=app.colors["card"],
            outline=app.colors["border"],
            width=max(1, app.px(1)),
            tags=("labels", self.tag),
        )
        self.mark = self.canvas.create_line(
            0,
            0,
            0,
            0,
            0,
            0,
            fill="#ffffff",
            width=max(2, app.px(2)),
            capstyle="round",
            joinstyle="round",
            state="hidden",
            tags=("labels", self.tag),
        )
        self.label = self.canvas.create_text(
            0,
            0,
            anchor="nw",
            text=text,
            font=(FONT, 9),
            fill=app.colors["text"],
            tags=("labels", self.tag),
        )
        self._font = tkfont.Font(font=(FONT, 9))
        self.width = app.px(18) + app.px(6) + self._font.measure(text)
        self.variable.trace_add("write", lambda *_args: self.draw())
        self.canvas.tag_bind(self.tag, "<Button-1>", self._toggle)
        self.canvas.tag_bind(self.tag, "<Enter>", self._enter)
        self.canvas.tag_bind(self.tag, "<Leave>", self._leave)
        self.draw()

    def layout(self, x: int, y: int) -> None:
        self._left = int(x)
        self._y = int(y)
        size = self.app.px(18)
        gap = self.app.px(6)
        self.canvas.coords(self.indicator, x, y, x + size, y + size)
        linespace = self._font.metrics("linespace")
        self.canvas.coords(
            self.label,
            x + size + gap,
            y + max(0, (size - linespace) // 2),
        )
        self.draw()

    def draw(self) -> None:
        c = self.app.colors
        selected = bool(self.variable.get())
        self.canvas.itemconfigure(
            self.indicator,
            fill=c["accent"] if selected else c["card"],
            outline=c["accent"] if selected else c["border"],
        )
        self.canvas.itemconfigure(
            self.mark, state="normal" if selected else "hidden"
        )
        self.canvas.itemconfigure(
            self.label, fill=c["accent"] if self._hover else c["text"]
        )
        size = self.app.px(18)
        x = self._left
        y = self._y
        self.canvas.coords(
            self.mark,
            x + size * 0.24,
            y + size * 0.52,
            x + size * 0.43,
            y + size * 0.70,
            x + size * 0.76,
            y + size * 0.30,
        )

    def _toggle(self, _event=None) -> None:
        self.variable.set(not self.variable.get())
        if self.command is not None:
            self.command()

    def _enter(self, _event=None) -> None:
        self._hover = True
        self.draw()
        self.canvas.configure(cursor="hand2")

    def _leave(self, _event=None) -> None:
        self._hover = False
        self.draw()
        self.canvas.configure(cursor="")


class TranslatorApp:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.config = load_config()
        self.scale = max(1.0, self.root.winfo_fpixels("1i") / 96.0)

        self.theme_key = str(self.config.get("theme", "light"))
        if self.theme_key not in THEMES:
            self.theme_key = "light"
        self.colors = THEMES[self.theme_key]

        try:
            self.text_transparency = int(self.config.get("text_transparency", 0))
        except (TypeError, ValueError):
            self.text_transparency = 0
        self.text_transparency = max(0, min(70, self.text_transparency))

        self._queue: queue.Queue = queue.Queue()
        self._busy = False
        self._last_result = ""
        self._status_text = ""
        self._status_error = False

        self._clipboard_job = None
        self._last_clipboard = ""
        self._pending_clipboard_text = None

        self._wallpaper_path = ""
        self._wallpaper_kind = ""
        self._wallpaper_source = None
        self._wallpaper_photo = None
        self._image_render_job = None
        self._scrim_job = None
        self._top_scrim_photo = None
        self._bottom_scrim_photo = None
        self._scrim_top_end = 0
        self._scrim_bottom_start = 0
        self._appearance_menu_open = False
        self.appearance_panel = None

        self._input_text_pos = (0, 0)
        self._output_text_pos = (0, 0)

        self._video_session = 0
        self._video_thread = None
        self._video_stop_event = None
        self._video_queue = None
        self._video_job = None
        self._video_target = (0, 0)
        self._video_paused = False

        self.topmost_var = tk.BooleanVar(value=bool(self.config["topmost"]))
        self.auto_var = tk.BooleanVar(value=bool(self.config["auto_translate"]))
        self.watch_var = tk.BooleanVar(value=bool(self.config["watch_clipboard"]))

        self._setup_window()
        self._setup_style()
        self._build_ui()
        self._restore_state()
        self._poll_queue()
        self.root.after(40, self._layout_ui)
        self.root.after(160, self._restore_wallpaper)
        self.root.after(240, self._apply_text_alpha)

    # ------------------------------------------------------------------
    # Window / styling
    # ------------------------------------------------------------------

    def _setup_window(self) -> None:
        self.root.title(APP_NAME)
        self.root.configure(bg=self.colors["bg"])
        self.root.minsize(
            max(380, min(int(560 * self.scale), self.root.winfo_screenwidth() - 40)),
            max(460, min(int(600 * self.scale), self.root.winfo_screenheight() - 80)),
        )
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

        icon = resource_path("icon.ico")
        if icon.exists():
            try:
                self.root.iconbitmap(str(icon))
            except tk.TclError:
                pass

        self._setup_geometry()

    def _setup_geometry(self) -> None:
        screen_w = self.root.winfo_screenwidth()
        screen_h = self.root.winfo_screenheight()
        width = min(int(860 * self.scale), screen_w - int(40 * self.scale))
        height = min(int(760 * self.scale), screen_h - int(80 * self.scale))

        match = re.match(
            r"^(\d+)x(\d+)\+(-?\d+)\+(-?\d+)$",
            str(self.config.get("geometry", "")),
        )
        if match:
            w, h, x, y = (int(value) for value in match.groups())
            w = max(int(480 * self.scale), min(w, screen_w - 40))
            h = max(int(540 * self.scale), min(h, screen_h - 60))
            x = max(-w + 160, min(x, screen_w - 120))
            y = max(0, min(y, screen_h - 80))
            self.root.geometry(f"{w}x{h}+{x}+{y}")
        else:
            x = max(0, (screen_w - width) // 2)
            y = max(0, (screen_h - height) // 2 - int(20 * self.scale))
            self.root.geometry(f"{width}x{height}+{x}+{y}")

    def px(self, value: float) -> int:
        return max(1, int(value * self.scale))

    def _setup_style(self) -> None:
        style = ttk.Style(self.root)
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass
        self._configure_ttk_style()

    def _configure_ttk_style(self) -> None:
        c = self.colors
        style = ttk.Style(self.root)
        style.configure(
            ".",
            font=(FONT, 10),
            background=c["bg"],
            foreground=c["text"],
        )
        style.configure(
            "TCombobox",
            padding=self.px(4),
            fieldbackground=c["card"],
            background=c["secondary"],
            foreground=c["text"],
            arrowcolor=c["text"],
            bordercolor=c["border"],
            lightcolor=c["border"],
            darkcolor=c["border"],
            selectbackground=c["card"],
            selectforeground=c["text"],
        )
        style.map(
            "TCombobox",
            fieldbackground=[("readonly", c["card"]), ("disabled", c["bg"])],
            background=[
                ("active", c["secondary_hover"]),
                ("readonly", c["secondary"]),
            ],
            foreground=[("readonly", c["text"]), ("disabled", c["muted"])],
            arrowcolor=[("active", c["text"])],
            selectbackground=[("readonly", c["card"])],
            selectforeground=[("readonly", c["text"])],
        )
        for scrollbar_style in ("TScrollbar", "Vertical.TScrollbar"):
            style.configure(
                scrollbar_style,
                background=c["secondary"],
                troughcolor=c["bg"],
                bordercolor=c["border"],
                arrowcolor=c["muted"],
                lightcolor=c["secondary"],
                darkcolor=c["secondary"],
                gripcount=0,
                relief="flat",
            )
            style.map(
                scrollbar_style,
                background=[
                    ("active", c["secondary_hover"]),
                    ("disabled", c["secondary"]),
                ],
                arrowcolor=[
                    ("active", c["text"]),
                    ("disabled", c["muted"]),
                ],
            )
        self.root.option_add("*TCombobox*Listbox.background", c["card"])
        self.root.option_add("*TCombobox*Listbox.foreground", c["text"])
        self.root.option_add("*TCombobox*Listbox.selectBackground", c["select_bg"])
        self.root.option_add("*TCombobox*Listbox.selectForeground", c["select_fg"])

    def _set_widget_alpha(self, widget: tk.Misc, alpha: int) -> None:
        if sys.platform != "win32":
            return
        try:
            hwnd = widget.winfo_id()
            if not hwnd:
                return
            user32 = ctypes.windll.user32
            get_long = user32.GetWindowLongPtrW
            get_long.restype = ctypes.c_longlong
            get_long.argtypes = [ctypes.c_void_p, ctypes.c_int]
            set_long = user32.SetWindowLongPtrW
            set_long.restype = ctypes.c_longlong
            set_long.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_longlong]
            set_alpha = user32.SetLayeredWindowAttributes
            set_alpha.restype = ctypes.c_int
            set_alpha.argtypes = [
                ctypes.c_void_p,
                ctypes.c_uint,
                ctypes.c_ubyte,
                ctypes.c_uint,
            ]
            ex_style = get_long(ctypes.c_void_p(hwnd), -20)
            layered = 0x00080000
            if alpha >= 255:
                if ex_style & layered:
                    set_long(ctypes.c_void_p(hwnd), -20, ex_style & ~layered)
                return
            if not (ex_style & layered):
                set_long(ctypes.c_void_p(hwnd), -20, ex_style | layered)
            set_alpha(ctypes.c_void_p(hwnd), 0, alpha, 0x00000002)
        except Exception:
            pass

    def _apply_text_alpha(self) -> None:
        if sys.platform != "win32":
            return
        if not hasattr(self, "input"):
            return
        alpha = int(
            round(255 * (1 - self.text_transparency / 100.0))
        )
        alpha = max(0, min(255, alpha))
        for widget in (
            self.input,
            self.output,
            self.input_scroll,
            self.output_scroll,
            self.input_ph,
            self.output_ph,
        ):
            self._set_widget_alpha(widget, alpha)

    def _set_text_transparency(self, value: int, save: bool = False) -> None:
        self.text_transparency = max(0, min(70, int(value)))
        self._apply_text_alpha()
        if save:
            self._save_config()

    def _apply_titlebar_theme(self) -> None:
        if sys.platform != "win32":
            return
        try:
            hwnd = ctypes.windll.user32.GetParent(self.root.winfo_id())
            if not hwnd:
                hwnd = self.root.winfo_id()
            value = ctypes.c_int(1 if self.theme_key == "dark" else 0)
            for attribute in (20, 19):
                result = ctypes.windll.dwmapi.DwmSetWindowAttribute(
                    hwnd,
                    attribute,
                    ctypes.byref(value),
                    ctypes.sizeof(value),
                )
                if result == 0:
                    break
        except Exception:
            pass

    def _make_button(
        self,
        parent: tk.Misc,
        text: str,
        command,
        role: str = "secondary",
        compact: bool = False,
    ) -> tk.Button:
        pad_x = self.px(10 if compact else 16)
        pad_y = self.px(5 if compact else 7)
        button = tk.Button(
            parent,
            text=text,
            command=command,
            font=(
                FONT,
                9 if compact else 10,
                "bold" if role == "primary" else "normal",
            ),
            relief="flat",
            bd=0,
            cursor="hand2",
            padx=pad_x,
            pady=pad_y,
        )
        button._theme_role = role
        button._compact = compact
        button.bind(
            "<Enter>",
            lambda _event: self._paint_button(
                button, getattr(button, "_theme_role", role), True
            ),
        )
        button.bind(
            "<Leave>",
            lambda _event: self._paint_button(
                button, getattr(button, "_theme_role", role), False
            ),
        )
        self._paint_button(button, role, False)
        return button

    def _paint_button(self, button: tk.Button, role: str, hover: bool) -> None:
        c = self.colors
        size = 9 if getattr(button, "_compact", False) else 10
        disabled = str(button["state"]) == "disabled"
        if disabled:
            if role == "primary":
                button.configure(
                    bg=c["accent_disabled"],
                    fg="#ffffff",
                    activebackground=c["accent_disabled"],
                    activeforeground="#ffffff",
                    disabledforeground="#ffffff",
                    font=(FONT, size, "bold"),
                )
            else:
                button.configure(
                    bg=c["secondary"],
                    fg=c["muted"],
                    activebackground=c["secondary"],
                    activeforeground=c["muted"],
                    disabledforeground=c["muted"],
                    font=(FONT, size, "normal"),
                )
            return
        if role == "primary":
            bg = c["accent_hover"] if hover else c["accent"]
            button.configure(
                bg=bg,
                fg="#ffffff",
                activebackground=c["accent_hover"],
                activeforeground="#ffffff",
                disabledforeground="#ffffff",
                font=(FONT, size, "bold"),
            )
        else:
            bg = c["secondary_hover"] if hover else c["secondary"]
            button.configure(
                bg=bg,
                fg=c["text"],
                activebackground=c["secondary_hover"],
                activeforeground=c["text"],
                disabledforeground=c["muted"],
                font=(FONT, size, "normal"),
            )

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        c = self.colors

        self.canvas = tk.Canvas(
            self.root, highlightthickness=0, bd=0, bg=c["bg"]
        )
        self.canvas.pack(fill="both", expand=True)

        label_tags = ("labels",)
        self.title_item = self.canvas.create_text(
            0, 0, anchor="nw", text="译窗",
            font=(FONT, 17, "bold"), fill=c["text"], tags=label_tags,
        )
        self.subtitle_item = self.canvas.create_text(
            0, 0, anchor="nw", text="Translator",
            font=(FONT, 11), fill=c["muted"], tags=label_tags,
        )
        self.direction_item = self.canvas.create_text(
            0, 0, anchor="nw", text="翻译方向",
            font=(FONT, 10), fill=c["muted"], tags=label_tags,
        )
        self.input_label_item = self.canvas.create_text(
            0, 0, anchor="nw", text="原文",
            font=(FONT, 10, "bold"), fill=c["text"], tags=label_tags,
        )
        self.count_item = self.canvas.create_text(
            0, 0, anchor="ne", text="0 字符",
            font=(FONT, 9), fill=c["muted"], tags=label_tags,
        )
        self.output_label_item = self.canvas.create_text(
            0, 0, anchor="nw", text="译文",
            font=(FONT, 10, "bold"), fill=c["text"], tags=label_tags,
        )
        self.status_item = self.canvas.create_text(
            0, 0, anchor="sw", text="",
            font=(FONT, 9), fill=c["muted"], width=100, tags=label_tags,
        )
        self.copy_item = self.canvas.create_text(
            0, 0, anchor="ne", text="复制结果",
            font=(FONT, 9), fill=c["accent"], tags=("labels", "copy"),
        )
        self.canvas.tag_bind(
            self.copy_item, "<Button-1>", lambda _event: self._copy_result()
        )
        self.canvas.tag_bind(self.copy_item, "<Enter>", self._on_copy_enter)
        self.canvas.tag_bind(self.copy_item, "<Leave>", self._on_copy_leave)

        self.topmost_cb = CanvasCheck(
            self, "窗口置顶", self.topmost_var, self._toggle_topmost
        )
        self.direction_cb = ttk.Combobox(
            self.canvas,
            values=DIRECTION_LABELS,
            state="readonly",
            width=11,
        )
        self.direction_cb.bind("<<ComboboxSelected>>", self._on_direction_change)
        self.watch_cb = CanvasCheck(
            self, "自动读取剪贴板", self.watch_var, self._toggle_watch
        )
        self.auto_cb = CanvasCheck(
            self, "粘贴后自动翻译", self.auto_var, self._save_config
        )

        self.appearance_summary = tk.Frame(
            self.canvas, bg=c["secondary"], cursor="hand2"
        )
        self.summary_swatch = tk.Canvas(
            self.appearance_summary,
            width=self.px(16),
            height=self.px(16),
            bg=c["secondary"],
            highlightthickness=0,
            bd=0,
            cursor="hand2",
        )
        self.summary_swatch.pack(
            side="left", padx=(self.px(8), self.px(6)), pady=self.px(5)
        )
        self.summary_label = tk.Label(
            self.appearance_summary,
            text=f"外观：{THEME_LABELS[self.theme_key]}",
            bg=c["secondary"],
            fg=c["text"],
            font=(FONT, 9),
            cursor="hand2",
        )
        self.summary_label.pack(side="left")
        self.summary_arrow = tk.Label(
            self.appearance_summary,
            text="▾",
            bg=c["secondary"],
            fg=c["muted"],
            font=(FONT, 8),
            cursor="hand2",
        )
        self.summary_arrow.pack(side="left", padx=(self.px(5), self.px(8)))
        for widget in (
            self.appearance_summary,
            self.summary_swatch,
            self.summary_label,
            self.summary_arrow,
        ):
            widget.bind("<Button-1>", self._toggle_appearance_menu)
            widget.bind("<Enter>", self._summary_enter)
            widget.bind("<Leave>", self._summary_leave)

        self.input = tk.Text(
            self.canvas,
            height=8,
            wrap="word",
            font=(FONT, 11),
            bg=c["card"],
            fg=c["text"],
            relief="flat",
            bd=0,
            highlightthickness=1,
            highlightbackground=c["border"],
            highlightcolor=c["accent"],
            padx=self.px(12),
            pady=self.px(10),
            undo=True,
            insertbackground=c["text"],
            selectbackground=c["select_bg"],
            selectforeground=c["select_fg"],
        )
        self.input_scroll = ttk.Scrollbar(
            self.canvas, orient="vertical", command=self.input.yview
        )
        self.input.configure(yscrollcommand=self.input_scroll.set)

        self.input_ph = tk.Label(
            self.canvas,
            text="在此粘贴或输入要翻译的文字…",
            font=(FONT, 10),
            bg=c["card"],
            fg=c["placeholder"],
            anchor="nw",
            cursor="xterm",
        )
        self.input_ph.bind("<Button-1>", lambda _event: self.input.focus_set())

        self.paste_btn = self._make_button(
            self.canvas, "粘贴", self._paste, role="secondary"
        )
        self.clear_btn = self._make_button(
            self.canvas, "清空", self._clear, role="secondary"
        )
        self.translate_btn = self._make_button(
            self.canvas, "翻译  Ctrl+Enter", self._start_translation,
            role="primary",
        )

        self.output = tk.Text(
            self.canvas,
            height=8,
            wrap="word",
            font=(FONT, 11),
            bg=c["output_bg"],
            fg=c["text"],
            relief="flat",
            bd=0,
            highlightthickness=1,
            highlightbackground=c["border"],
            highlightcolor=c["accent"],
            padx=self.px(12),
            pady=self.px(10),
            state="disabled",
            selectbackground=c["select_bg"],
            selectforeground=c["select_fg"],
            cursor="arrow",
        )
        self.output_scroll = ttk.Scrollbar(
            self.canvas, orient="vertical", command=self.output.yview
        )
        self.output.configure(yscrollcommand=self.output_scroll.set)

        self.output_ph = tk.Label(
            self.canvas,
            text="翻译结果会显示在这里",
            font=(FONT, 10),
            bg=c["output_bg"],
            fg=c["placeholder"],
            anchor="nw",
        )

        self.input.bind("<FocusIn>", self._on_input_focus_in)
        self.input.bind("<FocusOut>", self._on_input_focus_out)
        self.input.bind("<<Modified>>", self._on_modified)
        self.input.bind("<<Paste>>", self._on_paste_event)
        self.input.edit_modified(False)

        self.root.bind("<Configure>", self._on_root_configure)
        self.root.bind("<Map>", self._on_root_map)
        self.root.bind("<Unmap>", self._on_root_unmap)
        self.root.bind("<Control-Return>", self._shortcut_translate)
        self.input.bind("<Control-Return>", self._shortcut_translate)
        self.root.bind("<Control-Shift-C>", self._shortcut_copy)
        self.root.bind("<Control-Shift-c>", self._shortcut_copy)
        self.root.bind_all("<Button-1>", self._on_global_click, add="+")
        self.root.bind_all("<Escape>", self._on_escape, add="+")

        self._set_status("就绪 · 仅在手动粘贴时读取剪贴板")

    def _restore_state(self) -> None:
        mode = str(self.config.get("direction", "auto"))
        try:
            index = DIRECTION_MODES.index(mode)
        except ValueError:
            index = 0
        self.direction_cb.current(index)

        self.root.attributes("-topmost", bool(self.topmost_var.get()))
        self._update_appearance_summary()

        if self.watch_var.get():
            self._last_clipboard = self._current_clipboard()
            self._start_clipboard_polling()
            self._set_status("就绪 · 自动读取剪贴板已开启")

        self.root.after(60, self._apply_titlebar_theme)

    # ------------------------------------------------------------------
    # Layout / scrim
    # ------------------------------------------------------------------

    def _layout_ui(self) -> None:
        if not hasattr(self, "canvas"):
            return
        w = self.root.winfo_width()
        h = self.root.winfo_height()
        if w < 2 or h < 2:
            return

        s = self.scale
        margin = int(max(12 * s, min(24 * s, w * 0.02)))
        content_w = min(w - 2 * margin, int(820 * s))
        content_w = max(int(300 * s), content_w)
        content_w = min(content_w, w)
        x0 = (w - content_w) // 2
        top = int(14 * s)
        gap = int(8 * s)

        header_y = top
        self.canvas.coords(self.title_item, x0, header_y)
        bbox = self.canvas.bbox(self.title_item)
        title_w = (bbox[2] - bbox[0]) if bbox else int(60 * s)
        self.canvas.coords(
            self.subtitle_item, x0 + title_w + int(6 * s), header_y + int(8 * s)
        )
        topmost_x = x0 + content_w - self.topmost_cb.width
        self.topmost_cb.layout(topmost_x, header_y + int(8 * s))
        self.appearance_summary.update_idletasks()
        summary_w = self.appearance_summary.winfo_reqwidth()
        self.appearance_summary.place(
            x=topmost_x - int(10 * s) - summary_w,
            y=header_y + int(8 * s),
            anchor="nw",
        )

        toolbar_y = header_y + int(34 * s) + gap
        self.canvas.coords(
            self.direction_item, x0, toolbar_y + int(5 * s)
        )
        self.direction_cb.place(
            x=x0 + int(70 * s), y=toolbar_y, anchor="nw"
        )
        watch_x = x0 + content_w - self.watch_cb.width
        self.watch_cb.layout(watch_x, toolbar_y + int(6 * s))
        self.auto_cb.layout(
            watch_x - int(12 * s) - self.auto_cb.width,
            toolbar_y + int(6 * s),
        )

        input_label_y = toolbar_y + int(34 * s) + int(16 * s)
        self.canvas.coords(self.input_label_item, x0, input_label_y)
        self.canvas.coords(
            self.count_item, x0 + content_w, input_label_y
        )
        input_text_y = input_label_y + int(22 * s) + int(4 * s)

        actions_h = int(40 * s)
        output_label_h = int(22 * s)
        status_h = int(20 * s)
        bottom_margin = int(12 * s)
        status_bottom = h - bottom_margin
        status_top = status_bottom - status_h
        output_text_bottom = status_top - gap

        fixed = (
            gap
            + actions_h
            + gap
            + output_label_h
            + int(4 * s)
        )
        available = output_text_bottom - input_text_y - fixed
        available = max(int(160 * s), available)
        input_h = int(available * 0.52)
        output_h = available - input_h
        if input_h < int(90 * s):
            input_h = int(90 * s)
        if output_h < int(70 * s):
            output_h = int(70 * s)

        actions_y = input_text_y + input_h + gap
        output_label_y = actions_y + actions_h + gap
        output_text_y = output_label_y + output_label_h + int(4 * s)
        output_h = max(int(70 * s), output_text_bottom - output_text_y)

        scroll_w = int(14 * s)
        text_w = content_w - scroll_w - int(2 * s)

        self.input.place(
            x=x0, y=input_text_y, width=text_w, height=input_h
        )
        self.input_scroll.place(
            x=x0 + content_w - scroll_w,
            y=input_text_y,
            width=scroll_w,
            height=input_h,
        )
        self._input_text_pos = (x0, input_text_y)

        paste_w = self.paste_btn.winfo_reqwidth()
        self.paste_btn.place(x=x0, y=actions_y, anchor="nw")
        self.clear_btn.place(
            x=x0 + paste_w + int(8 * s), y=actions_y, anchor="nw"
        )
        self.translate_btn.place(
            x=x0 + content_w, y=actions_y, anchor="ne"
        )

        self.canvas.coords(self.output_label_item, x0, output_label_y)
        self.canvas.coords(
            self.copy_item, x0 + content_w, output_label_y + int(3 * s)
        )

        self.output.place(
            x=x0, y=output_text_y, width=text_w, height=output_h
        )
        self.output_scroll.place(
            x=x0 + content_w - scroll_w,
            y=output_text_y,
            width=scroll_w,
            height=output_h,
        )
        self._output_text_pos = (x0, output_text_y)

        self.canvas.coords(self.status_item, x0, status_bottom)
        self.canvas.itemconfigure(self.status_item, width=content_w)

        self._scrim_top_end = input_text_y
        self._scrim_bottom_start = output_label_y - int(4 * s)
        self._video_target = (w, h)

        self._refresh_input_placeholder()
        if self.output.get("1.0", "end-1c"):
            self.output_ph.place_forget()
        else:
            self._show_output_placeholder()

        self._schedule_scrim_update()
        if self._wallpaper_kind == "image":
            self._schedule_image_render()

    def _on_root_configure(self, event) -> None:
        if event.widget is not self.root:
            return
        if self._appearance_menu_open:
            self._close_appearance_menu()
        self._layout_ui()

    def _on_root_map(self, event) -> None:
        if event.widget is not self.root:
            return
        self._video_paused = False
        self._layout_ui()
        self._apply_text_alpha()
        self._apply_titlebar_theme()

    def _on_root_unmap(self, event) -> None:
        if event.widget is self.root:
            self._video_paused = True

    def _theme_rgb(self) -> tuple[int, int, int]:
        value = self.colors["bg"].lstrip("#")
        return tuple(int(value[i : i + 2], 16) for i in (0, 2, 4))

    def _schedule_scrim_update(self) -> None:
        if self._scrim_job is not None:
            try:
                self.root.after_cancel(self._scrim_job)
            except tk.TclError:
                pass
        self._scrim_job = self.root.after(60, self._update_scrims)

    def _update_scrims(self) -> None:
        self._scrim_job = None
        if not hasattr(self, "canvas"):
            return
        if not (self._wallpaper_active() and HAS_PIL):
            self.canvas.delete("top_scrim")
            self.canvas.delete("bottom_scrim")
            self._top_scrim_photo = None
            self._bottom_scrim_photo = None
            self._stack_canvas_items()
            return

        w = self.canvas.winfo_width()
        h = self.canvas.winfo_height()
        if w < 2 or h < 2:
            return
        rgb = self._theme_rgb()

        top_h = max(1, min(h, int(self._scrim_top_end)))
        top = Image.new("RGBA", (1, top_h), (*rgb, 150))
        top_px = top.load()
        for y in range(top_h):
            fraction = y / max(1, top_h - 1)
            alpha = int(170 - 55 * fraction)
            top_px[0, y] = (*rgb, alpha)
        top = top.resize((w, top_h), Image.Resampling.NEAREST)
        top_photo = ImageTk.PhotoImage(top)

        bottom_y = max(0, min(h - 1, int(self._scrim_bottom_start)))
        bottom_h = max(1, h - bottom_y)
        bottom = Image.new("RGBA", (1, bottom_h), (*rgb, 150))
        bottom = bottom.resize((w, bottom_h), Image.Resampling.NEAREST)
        bottom_photo = ImageTk.PhotoImage(bottom)

        self.canvas.delete("top_scrim")
        self.canvas.delete("bottom_scrim")
        self.canvas.create_image(
            0, 0, anchor="nw", image=top_photo, tags=("top_scrim",)
        )
        self.canvas.create_image(
            0, bottom_y, anchor="nw", image=bottom_photo,
            tags=("bottom_scrim",),
        )
        self._top_scrim_photo = top_photo
        self._bottom_scrim_photo = bottom_photo
        self._stack_canvas_items()

    def _stack_canvas_items(self) -> None:
        try:
            self.canvas.tag_lower("wallpaper")
            if self.canvas.find_withtag("top_scrim"):
                self.canvas.tag_raise("top_scrim", "wallpaper")
            if self.canvas.find_withtag("bottom_scrim"):
                self.canvas.tag_raise("bottom_scrim", "wallpaper")
            self.canvas.tag_raise("labels")
        except tk.TclError:
            pass

    # ------------------------------------------------------------------
    # Themes / appearance
    # ------------------------------------------------------------------

    def _apply_theme(self) -> None:
        c = self.colors
        self._configure_ttk_style()
        self.canvas.configure(bg=c["bg"])

        self._update_label_colors()

        self.input.configure(
            bg=c["card"],
            fg=c["text"],
            insertbackground=c["text"],
            selectbackground=c["select_bg"],
            selectforeground=c["select_fg"],
            highlightbackground=c["border"],
            highlightcolor=c["accent"],
        )
        self.output.configure(
            bg=c["output_bg"],
            fg=c["text"],
            selectbackground=c["select_bg"],
            selectforeground=c["select_fg"],
            highlightbackground=c["border"],
            highlightcolor=c["accent"],
        )
        self.input_ph.configure(bg=c["card"], fg=c["placeholder"])
        self.output_ph.configure(bg=c["output_bg"], fg=c["placeholder"])

        self._paint_button(self.paste_btn, "secondary", False)
        self._paint_button(self.clear_btn, "secondary", False)
        self._paint_button(self.translate_btn, "primary", False)

        self._update_appearance_summary()
        self._update_scrims()
        self._apply_titlebar_theme()

    def _update_label_colors(self) -> None:
        c = self.colors
        secondary = c["text"] if self._wallpaper_active() else c["muted"]
        for item in (
            self.title_item,
            self.input_label_item,
            self.output_label_item,
        ):
            self.canvas.itemconfigure(item, fill=c["text"])
        for item in (
            self.subtitle_item,
            self.direction_item,
            self.count_item,
        ):
            self.canvas.itemconfigure(item, fill=secondary)
        self.canvas.itemconfigure(
            self.status_item,
            fill=c["error"] if self._status_error else secondary,
        )
        self.canvas.itemconfigure(self.copy_item, fill=c["accent"])
        for check in (self.topmost_cb, self.watch_cb, self.auto_cb):
            check.draw()

    def _active_appearance(self) -> str:
        return "custom" if self._wallpaper_active() else self.theme_key

    def _update_appearance_summary(self) -> None:
        if not hasattr(self, "appearance_summary"):
            return
        active = self._active_appearance()
        name = "自定义壁纸" if active == "custom" else THEME_LABELS[active]
        self.summary_label.configure(text=f"外观：{name}")
        self._paint_summary()
        self._layout_ui()

    def _paint_summary(self, bg: str | None = None) -> None:
        if not hasattr(self, "appearance_summary"):
            return
        c = self.colors
        background = bg or c["secondary"]
        for widget in (
            self.appearance_summary,
            self.summary_swatch,
            self.summary_label,
            self.summary_arrow,
        ):
            widget.configure(bg=background)
        self.summary_label.configure(fg=c["text"])
        self.summary_arrow.configure(fg=c["muted"])
        self._draw_summary_swatch()

    def _draw_summary_swatch(self) -> None:
        if not hasattr(self, "summary_swatch"):
            return
        canvas = self.summary_swatch
        canvas.delete("all")
        size = self.px(16)
        active = self._active_appearance()
        if active == "custom":
            self._draw_photo_icon(canvas, size, self.colors["accent"])
        else:
            theme = THEMES[active]
            canvas.create_rectangle(
                1,
                1,
                size - 1,
                size - 1,
                fill=theme["bg"],
                outline=theme["border"],
            )

    def _draw_photo_icon(self, canvas: tk.Canvas, size: int, color: str) -> None:
        pad = max(1, int(size * 0.12))
        x0, y0, x1, y1 = pad, pad, size - pad, size - pad
        canvas.create_rectangle(
            x0,
            y0,
            x1,
            y1,
            outline=color,
            width=max(1, self.px(1)),
        )
        sun = size * 0.16
        canvas.create_oval(
            x0 + size * 0.14,
            y0 + size * 0.14,
            x0 + size * 0.14 + sun,
            y0 + size * 0.14 + sun,
            outline=color,
            width=max(1, self.px(1)),
        )
        canvas.create_polygon(
            x0 + size * 0.10,
            y1 - size * 0.10,
            x0 + size * 0.42,
            y0 + size * 0.44,
            x0 + size * 0.58,
            y1 - size * 0.28,
            x0 + size * 0.74,
            y0 + size * 0.56,
            x1 - size * 0.10,
            y1 - size * 0.10,
            fill=color,
            outline="",
        )

    def _summary_enter(self, _event=None) -> None:
        self._paint_summary(self.colors["secondary_hover"])

    def _summary_leave(self, _event=None) -> None:
        self._paint_summary(self.colors["secondary"])

    def _toggle_appearance_menu(self, _event=None) -> None:
        if self._appearance_menu_open:
            self._close_appearance_menu()
        else:
            self._open_appearance_menu()

    def _open_appearance_menu(self) -> None:
        self._close_appearance_menu()
        c = self.colors
        panel = tk.Frame(
            self.canvas,
            bg=c["card"],
            bd=0,
            highlightthickness=1,
            highlightbackground=c["border"],
        )
        heading = tk.Label(
            panel,
            text="外观",
            bg=c["card"],
            fg=c["muted"],
            font=(FONT, 9),
            anchor="w",
        )
        heading.pack(
            fill="x", padx=self.px(12), pady=(self.px(8), self.px(2))
        )
        divider = tk.Frame(panel, bg=c["border"], height=1)
        divider.pack(fill="x", padx=self.px(10), pady=(0, self.px(4)))

        active = self._active_appearance()
        for key in APPEARANCE_ORDER:
            self._make_appearance_row(panel, key, active)
        self._add_transparency_section(panel)

        panel.update_idletasks()
        panel_w = max(self.px(250), self.appearance_summary.winfo_reqwidth())
        panel_h = panel.winfo_reqheight()
        summary_x = self.appearance_summary.winfo_x()
        summary_w = self.appearance_summary.winfo_width()
        summary_y = self.appearance_summary.winfo_y()
        summary_h = self.appearance_summary.winfo_height()
        x = summary_x + summary_w - panel_w
        x = max(
            self.px(8),
            min(x, self.root.winfo_width() - panel_w - self.px(8)),
        )
        y = summary_y + summary_h + self.px(4)
        if y + panel_h > self.root.winfo_height() - self.px(8):
            y = max(self.px(8), summary_y - panel_h - self.px(4))
        panel.place(x=x, y=y, width=panel_w, height=panel_h)
        panel.lift()
        self.appearance_panel = panel
        self._appearance_menu_open = True

    def _make_appearance_row(
        self, panel: tk.Frame, key: str, active: str
    ) -> None:
        c = self.colors
        is_active = key == active
        normal_bg = c["secondary"] if is_active else c["card"]
        hover_bg = c["secondary_hover"]
        row = tk.Frame(panel, bg=normal_bg, cursor="hand2")
        row.pack(fill="x", padx=self.px(6), pady=self.px(1))

        swatch = tk.Canvas(
            row,
            width=self.px(18),
            height=self.px(18),
            bg=normal_bg,
            highlightthickness=0,
            bd=0,
            cursor="hand2",
        )
        swatch.pack(
            side="left", padx=(self.px(8), self.px(8)), pady=self.px(7)
        )
        if key == "custom":
            self._draw_photo_icon(swatch, self.px(18), c["accent"])
        else:
            theme = THEMES[key]
            swatch.create_rectangle(
                1,
                1,
                self.px(17),
                self.px(17),
                fill=theme["bg"],
                outline=theme["border"],
            )

        text_frame = tk.Frame(row, bg=normal_bg, cursor="hand2")
        text_frame.pack(side="left", fill="x", expand=True)
        name = tk.Label(
            text_frame,
            text=APPEARANCE_LABELS[key],
            bg=normal_bg,
            fg=c["text"],
            font=(FONT, 10),
            anchor="w",
            cursor="hand2",
        )
        name.pack(anchor="w")
        sub = None
        if key == "custom":
            if self._wallpaper_active():
                subtext = Path(self._wallpaper_path).name
                if len(subtext) > 24:
                    subtext = subtext[:23] + "…"
            else:
                subtext = "图片 / 视频…"
            sub = tk.Label(
                text_frame,
                text=subtext,
                bg=normal_bg,
                fg=c["muted"],
                font=(FONT, 8),
                anchor="w",
                cursor="hand2",
            )
            sub.pack(anchor="w")
        check = tk.Label(
            row,
            text="✓" if is_active else "",
            bg=normal_bg,
            fg=c["accent"],
            font=(FONT, 11, "bold"),
            cursor="hand2",
        )
        check.pack(side="right", padx=self.px(10))

        widgets = [row, swatch, text_frame, name, check]
        if sub is not None:
            widgets.append(sub)

        def paint(bg: str) -> None:
            for widget in widgets:
                try:
                    widget.configure(bg=bg)
                except tk.TclError:
                    pass

        leave_job = {"id": None}

        def enter(_event=None) -> None:
            if leave_job["id"] is not None:
                try:
                    self.root.after_cancel(leave_job["id"])
                except tk.TclError:
                    pass
                leave_job["id"] = None
            paint(hover_bg)

        def leave(_event=None) -> None:
            if leave_job["id"] is not None:
                try:
                    self.root.after_cancel(leave_job["id"])
                except tk.TclError:
                    pass
            leave_job["id"] = self.root.after(
                30,
                lambda: paint(normal_bg)
                if self.appearance_panel is panel
                else None,
            )

        for widget in widgets:
            widget.bind(
                "<Button-1>",
                lambda _event, k=key: self._on_appearance_choose(k),
            )
            widget.bind("<Enter>", enter)
            widget.bind("<Leave>", leave)

    def _add_transparency_section(self, panel: tk.Frame) -> None:
        c = self.colors
        divider = tk.Frame(panel, bg=c["border"], height=1)
        divider.pack(fill="x", padx=self.px(10), pady=(self.px(8), self.px(8)))

        header = tk.Frame(panel, bg=c["card"])
        header.pack(fill="x", padx=self.px(12))
        tk.Label(
            header,
            text="文字窗口透明度",
            bg=c["card"],
            fg=c["text"],
            font=(FONT, 9),
            anchor="w",
        ).pack(side="left")
        value_label = tk.Label(
            header,
            text=f"{self.text_transparency}%",
            bg=c["card"],
            fg=c["muted"],
            font=(FONT, 9),
        )
        value_label.pack(side="right")

        slider_w = self.px(210)
        slider_h = self.px(22)
        slider = tk.Canvas(
            panel,
            width=slider_w,
            height=slider_h,
            bg=c["card"],
            highlightthickness=0,
            bd=0,
            cursor="hand2",
        )
        slider.pack(padx=self.px(12), pady=(self.px(4), 0))

        tk.Label(
            panel,
            text="数值越大，壁纸越明显",
            bg=c["card"],
            fg=c["muted"],
            font=(FONT, 8),
            anchor="w",
        ).pack(
            fill="x",
            padx=self.px(12),
            pady=(self.px(2), self.px(8)),
        )

        track_x0 = self.px(10)
        track_x1 = slider_w - self.px(10)
        track_y = slider_h // 2

        def value_to_x(value: int) -> float:
            return track_x0 + (track_x1 - track_x0) * (value / 70.0)

        def x_to_value(x: int) -> int:
            ratio = (x - track_x0) / max(1, track_x1 - track_x0)
            return int(round(max(0.0, min(1.0, ratio)) * 70))

        def redraw() -> None:
            slider.delete("all")
            slider.create_line(
                track_x0,
                track_y,
                track_x1,
                track_y,
                fill=c["border"],
                width=self.px(5),
                capstyle="round",
            )
            knob_x = value_to_x(self.text_transparency)
            slider.create_line(
                track_x0,
                track_y,
                knob_x,
                track_y,
                fill=c["accent"],
                width=self.px(5),
                capstyle="round",
            )
            r = self.px(7)
            slider.create_oval(
                knob_x - r,
                track_y - r,
                knob_x + r,
                track_y + r,
                fill=c["accent"],
                outline=c["card"],
                width=self.px(2),
            )

        def update(value: int, save: bool = False) -> None:
            value = max(0, min(70, int(value)))
            self._set_text_transparency(value, save=save)
            value_label.configure(text=f"{value}%")
            redraw()

        def on_press(event) -> None:
            update(x_to_value(event.x))

        def on_drag(event) -> None:
            update(x_to_value(event.x))

        def on_release(_event) -> None:
            self._save_config()

        slider.bind("<Button-1>", on_press)
        slider.bind("<B1-Motion>", on_drag)
        slider.bind("<ButtonRelease-1>", on_release)
        redraw()

    def _close_appearance_menu(self) -> None:
        self._appearance_menu_open = False
        if self.appearance_panel is not None:
            try:
                self.appearance_panel.destroy()
            except tk.TclError:
                pass
            self.appearance_panel = None

    def _on_appearance_choose(self, key: str) -> None:
        self._close_appearance_menu()
        if key == "custom":
            self._choose_wallpaper()
        else:
            self._select_theme(key)

    def _on_global_click(self, event) -> None:
        if not self._appearance_menu_open:
            return
        widget = event.widget
        if self._is_descendant(
            widget, self.appearance_panel
        ) or self._is_descendant(widget, self.appearance_summary):
            return
        self._close_appearance_menu()

    def _is_descendant(self, widget, ancestor) -> bool:
        if ancestor is None:
            return False
        while widget is not None:
            if widget == ancestor:
                return True
            parent_name = widget.winfo_parent()
            if not parent_name:
                break
            try:
                widget = widget.nametowidget(parent_name)
            except Exception:
                break
        return False

    def _on_escape(self, _event=None):
        if self._appearance_menu_open:
            self._close_appearance_menu()
            return "break"
        return None

    def _select_theme(self, key: str) -> None:
        if key not in THEMES:
            return
        if self._wallpaper_active():
            self._deactivate_wallpaper()
        self.theme_key = key
        self.colors = THEMES[key]
        self._apply_theme()
        self._save_config()
        self._set_status(f"主题已切换：{THEME_LABELS[key]}")

    # ------------------------------------------------------------------
    # Placeholders / counters
    # ------------------------------------------------------------------

    def _refresh_input_placeholder(self) -> None:
        if not hasattr(self, "input_ph"):
            return
        if not hasattr(self, "_input_text_pos") or self._input_text_pos == (0, 0):
            return
        empty = not self.input.get("1.0", "end-1c")
        focused = self.root.focus_get() is self.input
        if empty and not focused:
            x, y = self._input_text_pos
            self.input_ph.place(
                x=x + self.px(14), y=y + self.px(12), anchor="nw"
            )
            self.input_ph.lift()
            self._apply_text_alpha()
        else:
            self.input_ph.place_forget()

    def _show_output_placeholder(self) -> None:
        if not hasattr(self, "output_ph"):
            return
        if not hasattr(self, "_output_text_pos") or self._output_text_pos == (0, 0):
            return
        x, y = self._output_text_pos
        self.output_ph.place(
            x=x + self.px(14), y=y + self.px(12), anchor="nw"
        )
        self.output_ph.lift()
        self._apply_text_alpha()

    def _on_input_focus_in(self, _event=None) -> None:
        self.input_ph.place_forget()

    def _on_input_focus_out(self, _event=None) -> None:
        self._refresh_input_placeholder()

    def _on_modified(self, _event=None) -> None:
        if self.input.edit_modified():
            self.input.edit_modified(False)
            self._update_count()

    def _update_count(self) -> None:
        count = len(self.input.get("1.0", "end-1c"))
        if hasattr(self, "count_item"):
            self.canvas.itemconfigure(self.count_item, text=f"{count} 字符")

    # ------------------------------------------------------------------
    # Clipboard auto-read (opt-in)
    # ------------------------------------------------------------------

    def _current_clipboard(self) -> str:
        try:
            value = self.root.clipboard_get()
        except tk.TclError:
            return ""
        return value if isinstance(value, str) else ""

    def _start_clipboard_polling(self) -> None:
        if self._clipboard_job is None:
            self._clipboard_job = self.root.after(400, self._poll_clipboard)

    def _stop_clipboard_polling(self) -> None:
        if self._clipboard_job is not None:
            try:
                self.root.after_cancel(self._clipboard_job)
            except tk.TclError:
                pass
            self._clipboard_job = None

    def _poll_clipboard(self) -> None:
        self._clipboard_job = None
        try:
            if not self.watch_var.get() or not self.root.winfo_exists():
                return
            text = self._current_clipboard()
            if text and text != self._last_clipboard:
                self._last_clipboard = text
                if text != self._last_result:
                    self._handle_clipboard_text(text)
        finally:
            if self.watch_var.get():
                try:
                    self._clipboard_job = self.root.after(
                        700, self._poll_clipboard
                    )
                except tk.TclError:
                    self._clipboard_job = None

    def _handle_clipboard_text(self, text: str) -> None:
        if not text.strip():
            return
        self.input.delete("1.0", "end")
        self.input.insert("1.0", text)
        self.input.see("1.0")
        self._update_count()
        self._refresh_input_placeholder()

        if not self.auto_var.get():
            self._set_status("已从剪贴板填入内容，按 Ctrl+Enter 翻译")
            return
        if self._busy:
            self._pending_clipboard_text = text
            self._set_status("已读取新的剪贴板内容，等待当前翻译完成…")
        else:
            self._start_translation()

    def _toggle_watch(self) -> None:
        self._save_config()
        if self.watch_var.get():
            self._last_clipboard = self._current_clipboard()
            self._pending_clipboard_text = None
            self._start_clipboard_polling()
            self._set_status(
                "自动读取剪贴板已开启 · 复制文字后会自动填入（请注意隐私）"
            )
        else:
            self._stop_clipboard_polling()
            self._pending_clipboard_text = None
            self._set_status("已关闭自动读取 · 仅在手动粘贴时读取剪贴板")

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------

    def _paste(self) -> None:
        try:
            text = self.root.clipboard_get()
        except tk.TclError:
            self._set_status("剪贴板里没有文本", error=True)
            return
        if not text:
            self._set_status("剪贴板里没有文本", error=True)
            return
        if self.watch_var.get():
            self._last_clipboard = text

        self.input.focus_set()
        try:
            self.input.delete("sel.first", "sel.last")
        except tk.TclError:
            pass
        self.input.insert("insert", text)
        self.input.see("end")
        self._update_count()
        self._refresh_input_placeholder()

        if self.auto_var.get():
            self._start_translation()
        else:
            self._set_status("已粘贴，按 Ctrl+Enter 翻译")

    def _on_paste_event(self, _event=None) -> None:
        if self.watch_var.get():
            self._last_clipboard = self._current_clipboard()
        self.root.after(60, self._after_keyboard_paste)

    def _after_keyboard_paste(self) -> None:
        if self.watch_var.get():
            self._last_clipboard = self._current_clipboard()
        self._update_count()
        self._refresh_input_placeholder()
        if self.auto_var.get() and self.input.get("1.0", "end-1c").strip():
            self._start_translation()

    def _clear(self) -> None:
        self.input.delete("1.0", "end")
        self._update_count()
        self._last_result = ""
        self._pending_clipboard_text = None
        self._set_output("")
        self._set_status("已清空")
        self.input.focus_set()
        self._refresh_input_placeholder()

    def _start_translation(self, _event=None):
        if self._busy:
            return "break"
        text = self.input.get("1.0", "end-1c")
        if not text.strip():
            self._set_status("请先粘贴或输入要翻译的文字", error=True)
            self.input.focus_set()
            return "break"

        self._busy = True
        self.translate_btn.configure(state="disabled", text="翻译中…")
        self._paint_button(self.translate_btn, "primary", False)
        self._set_status("正在翻译…")
        mode = DIRECTION_MODES[self.direction_cb.current()]

        def worker() -> None:
            try:
                result = translate(text, mode)
                self._queue.put(("ok", result))
            except TranslationError as exc:
                self._queue.put(("error", str(exc)))
            except Exception as exc:
                self._queue.put(("error", f"发生未预期的错误：{exc}"))

        threading.Thread(target=worker, daemon=True).start()
        return "break"

    def _poll_queue(self) -> None:
        try:
            while True:
                kind, payload = self._queue.get_nowait()
                if kind == "ok":
                    self._show_result(payload)
                else:
                    self._show_error(payload)
        except queue.Empty:
            pass
        try:
            self.root.after(80, self._poll_queue)
        except tk.TclError:
            pass

    def _finish_busy(self) -> None:
        self._busy = False
        self.translate_btn.configure(
            state="normal", text="翻译  Ctrl+Enter"
        )
        self._paint_button(self.translate_btn, "primary", False)

    def _show_result(self, result) -> None:
        self._finish_busy()
        self._last_result = result.text
        self._set_output(result.text)
        self.output.see("1.0")
        self.canvas.itemconfigure(self.copy_item, text="复制结果")
        self.canvas.itemconfigure(
            self.copy_item, fill=self.colors["accent"]
        )

        provider = "MyMemory（备用）" if result.fallback else "Google"
        self._set_status(
            f"{language_name(result.source)} → {language_name(result.target)}"
            f" · {provider} · {len(result.text)} 字符"
        )

        if self._pending_clipboard_text is not None:
            self._pending_clipboard_text = None
            self.root.after(50, self._start_translation)

    def _show_error(self, message: str) -> None:
        self._finish_busy()
        self._pending_clipboard_text = None
        self._set_status("翻译失败，请检查网络后重试", error=True)
        messagebox.showerror("翻译失败", message, parent=self.root)

    def _set_output(self, text: str) -> None:
        self.output.configure(state="normal")
        self.output.delete("1.0", "end")
        if text:
            self.output.insert("1.0", text)
        self.output.configure(state="disabled")
        if text:
            self.output_ph.place_forget()
        else:
            self._show_output_placeholder()

    def _copy_result(self) -> None:
        if not self._last_result:
            self._set_status("还没有可复制的译文", error=True)
            return
        self.root.clipboard_clear()
        self.root.clipboard_append(self._last_result)
        self.root.update()
        self._last_clipboard = self._last_result
        self._set_status("译文已复制到剪贴板")
        self.canvas.itemconfigure(self.copy_item, text="已复制 ✓")
        self.canvas.itemconfigure(
            self.copy_item, fill=self.colors["success"]
        )
        self.root.after(1400, self._reset_copy_item)

    def _reset_copy_item(self) -> None:
        try:
            self.canvas.itemconfigure(self.copy_item, text="复制结果")
            self.canvas.itemconfigure(
                self.copy_item, fill=self.colors["accent"]
            )
        except tk.TclError:
            pass

    def _on_copy_enter(self, _event=None) -> None:
        self.canvas.itemconfigure(
            self.copy_item, fill=self.colors["accent_hover"]
        )
        self.canvas.configure(cursor="hand2")

    def _on_copy_leave(self, _event=None) -> None:
        self.canvas.itemconfigure(self.copy_item, fill=self.colors["accent"])
        self.canvas.configure(cursor="")

    def _shortcut_translate(self, _event=None):
        return self._start_translation()

    def _shortcut_copy(self, _event=None):
        self._copy_result()
        return "break"

    def _on_direction_change(self, _event=None) -> None:
        self._save_config()

    def _toggle_topmost(self) -> None:
        self.root.attributes("-topmost", bool(self.topmost_var.get()))
        self._save_config()

    def _set_status(self, text: str, error: bool = False) -> None:
        self._status_text = text
        self._status_error = error
        if hasattr(self, "status_item"):
            secondary = (
                self.colors["text"]
                if self._wallpaper_active()
                else self.colors["muted"]
            )
            self.canvas.itemconfigure(
                self.status_item,
                text=text,
                fill=self.colors["error"] if error else secondary,
            )

    # ------------------------------------------------------------------
    # Wallpaper
    # ------------------------------------------------------------------

    def _wallpaper_active(self) -> bool:
        return bool(self._wallpaper_kind and self._wallpaper_path)

    def _restore_wallpaper(self) -> None:
        path = str(self.config.get("wallpaper", "") or "").strip()
        kind = str(self.config.get("wallpaper_type", "") or "").strip()
        if not path:
            return
        if not Path(path).is_file():
            self._wallpaper_path = ""
            self._wallpaper_kind = ""
            self.config["wallpaper"] = ""
            self.config["wallpaper_type"] = ""
            self._update_label_colors()
            self._update_appearance_summary()
            self._update_scrims()
            self._save_config()
            self._set_status("壁纸文件不存在，已使用纯色主题", error=True)
            return

        if kind not in ("image", "video"):
            kind = "video" if Path(path).suffix.lower() in VIDEO_EXTS else "image"

        if kind == "image":
            if not HAS_PIL:
                self._set_status(
                    "图片壁纸需要 Pillow，请运行 pip install -r requirements.txt",
                    error=True,
                )
                return
            self._apply_image_wallpaper(path, announce=False)
        else:
            if not (HAS_CV2 and HAS_PIL):
                self._set_status(
                    "视频壁纸需要 Pillow 和 OpenCV，请运行 pip install -r requirements.txt",
                    error=True,
                )
                return
            self._apply_video_wallpaper(path, announce=False)

    def _choose_wallpaper(self) -> None:
        path = filedialog.askopenfilename(
            title="选择自定义壁纸（图片或视频）",
            filetypes=[
                ("图片或视频", f"{IMAGE_PATTERN} {VIDEO_PATTERN}"),
                ("图片", IMAGE_PATTERN),
                ("视频", VIDEO_PATTERN),
                ("所有文件", "*.*"),
            ],
        )
        if not path:
            self._update_appearance_summary()
            return
        ext = Path(path).suffix.lower()
        if ext in VIDEO_EXTS:
            if not (HAS_CV2 and HAS_PIL):
                messagebox.showinfo(
                    "需要安装视频解码库",
                    "播放视频壁纸需要 Pillow 和 OpenCV。\n\n"
                    "在项目目录运行：\npip install -r requirements.txt",
                    parent=self.root,
                )
                self._update_appearance_summary()
                return
            if not self._apply_video_wallpaper(path, announce=True):
                self._update_appearance_summary()
        else:
            if not HAS_PIL:
                messagebox.showinfo(
                    "需要安装 Pillow",
                    "显示图片壁纸需要 Pillow。\n\n"
                    "在项目目录运行：\npip install -r requirements.txt",
                    parent=self.root,
                )
                self._update_appearance_summary()
                return
            if not self._apply_image_wallpaper(path, announce=True):
                self._update_appearance_summary()

    def _apply_image_wallpaper(self, path: str, announce: bool = True) -> bool:
        if not HAS_PIL:
            return False
        try:
            image = Image.open(path)
            image = ImageOps.exif_transpose(image)
            image = image.convert("RGB")
            max_dim = (
                max(
                    self.root.winfo_screenwidth(),
                    self.root.winfo_screenheight(),
                )
                * 2
            )
            if max(image.size) > max_dim:
                image.thumbnail((max_dim, max_dim), RESAMPLE)
        except Exception as exc:
            if announce:
                messagebox.showerror(
                    "无法打开图片", f"无法读取这个图片：\n{exc}", parent=self.root
                )
            else:
                self._set_status("壁纸图片无法打开", error=True)
            return False

        self._stop_wallpaper(clear_image=True)
        self._wallpaper_source = image
        self._wallpaper_path = str(Path(path))
        self._wallpaper_kind = "image"
        self._wallpaper_photo = None
        self._update_label_colors()
        self._update_scrims()
        self._render_image_wallpaper()
        self._update_appearance_summary()
        self._save_config()
        if announce:
            self._set_status(f"自定义壁纸已启用：{Path(path).name}")
        return True

    def _apply_video_wallpaper(self, path: str, announce: bool = True) -> bool:
        if not (HAS_CV2 and HAS_PIL):
            return False
        cap = cv2.VideoCapture(str(path))
        if not cap.isOpened():
            cap.release()
            if announce:
                messagebox.showerror(
                    "无法打开视频",
                    "这个视频无法解码，可能是格式不支持或文件已损坏。",
                    parent=self.root,
                )
            else:
                self._set_status("壁纸视频无法打开", error=True)
            return False

        self._stop_wallpaper(clear_image=True)
        self._wallpaper_source = None
        self._wallpaper_path = str(Path(path))
        self._wallpaper_kind = "video"
        self._wallpaper_photo = None
        self._update_label_colors()
        self._update_scrims()
        self._start_video_playback(cap)
        self._update_appearance_summary()
        self._save_config()
        if announce:
            self._set_status(
                f"自定义壁纸已启用：{Path(path).name}（视频静音循环）"
            )
        return True

    def _deactivate_wallpaper(self) -> None:
        self._stop_wallpaper(clear_image=True)
        self._wallpaper_path = ""
        self._wallpaper_kind = ""
        self._wallpaper_source = None
        self._update_label_colors()
        self._update_appearance_summary()
        self._update_scrims()
        self._save_config()

    def _stop_wallpaper(self, clear_image: bool = True) -> None:
        self._stop_video_wallpaper(clear_image=clear_image)
        if self._image_render_job is not None:
            try:
                self.root.after_cancel(self._image_render_job)
            except tk.TclError:
                pass
            self._image_render_job = None
        self._wallpaper_source = None
        if clear_image:
            self.canvas.delete("wallpaper")
            self._wallpaper_photo = None

    def _stop_video_wallpaper(self, clear_image: bool = True) -> None:
        self._video_session += 1
        if self._video_stop_event is not None:
            self._video_stop_event.set()
            self._video_stop_event = None
        if self._video_job is not None:
            try:
                self.root.after_cancel(self._video_job)
            except tk.TclError:
                pass
            self._video_job = None
        self._video_queue = None
        self._video_thread = None
        if clear_image:
            self.canvas.delete("wallpaper")
            self._wallpaper_photo = None

    def _schedule_image_render(self) -> None:
        if self._wallpaper_kind != "image":
            return
        if self._image_render_job is not None:
            try:
                self.root.after_cancel(self._image_render_job)
            except tk.TclError:
                pass
        self._image_render_job = self.root.after(
            120, self._render_image_wallpaper
        )

    def _render_image_wallpaper(self) -> None:
        self._image_render_job = None
        if self._wallpaper_kind != "image" or self._wallpaper_source is None:
            return
        if not HAS_PIL:
            return
        w = self.canvas.winfo_width()
        h = self.canvas.winfo_height()
        if w < 2 or h < 2:
            if self.root.state() != "iconic":
                self._image_render_job = self.root.after(
                    200, self._render_image_wallpaper
                )
            return
        try:
            fitted = ImageOps.fit(
                self._wallpaper_source, (w, h), method=RESAMPLE
            )
            photo = ImageTk.PhotoImage(fitted)
            self.canvas.delete("wallpaper")
            self.canvas.create_image(
                0, 0, anchor="nw", image=photo, tags=("wallpaper",)
            )
            self._wallpaper_photo = photo
            self.canvas.tag_lower("wallpaper")
        except Exception:
            pass

    # ------------------------------------------------------------------
    # Video wallpaper playback
    # ------------------------------------------------------------------

    def _start_video_playback(self, cap) -> None:
        self._video_session += 1
        session = self._video_session
        stop_event = threading.Event()
        frame_queue: queue.Queue = queue.Queue(maxsize=1)
        self._video_stop_event = stop_event
        self._video_queue = frame_queue
        self._video_paused = False
        w = max(2, self.root.winfo_width())
        h = max(2, self.root.winfo_height())
        self._video_target = (w, h)
        self._video_thread = threading.Thread(
            target=self._video_worker,
            args=(cap, session, stop_event, frame_queue),
            daemon=True,
        )
        self._video_thread.start()
        self._video_tick(session)

    def _video_tick(self, session: int) -> None:
        if session != self._video_session:
            return
        frame = None
        if self._video_queue is not None:
            try:
                frame = self._video_queue.get_nowait()
            except queue.Empty:
                pass
        if frame is not None and HAS_PIL:
            try:
                photo = ImageTk.PhotoImage(Image.fromarray(frame))
                self.canvas.delete("wallpaper")
                self.canvas.create_image(
                    0, 0, anchor="nw", image=photo, tags=("wallpaper",)
                )
                self._wallpaper_photo = photo
                self.canvas.tag_lower("wallpaper")
            except Exception:
                pass
        try:
            self._video_job = self.root.after(
                33, lambda: self._video_tick(session)
            )
        except tk.TclError:
            self._video_job = None

    def _video_worker(
        self,
        cap,
        session: int,
        stop_event: threading.Event,
        frame_queue: queue.Queue,
    ) -> None:
        try:
            source_fps = cap.get(cv2.CAP_PROP_FPS)
            if not source_fps or source_fps != source_fps:
                source_fps = 24.0
            fps = max(8.0, min(float(source_fps), VIDEO_FPS_CAP))
            interval = 1.0 / fps
            next_time = time.monotonic()
            while not stop_event.is_set():
                if self._video_paused:
                    stop_event.wait(0.25)
                    continue
                ok, frame = cap.read()
                if not ok:
                    cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                    ok, frame = cap.read()
                    if not ok:
                        break
                w, h = self._video_target
                if w < 2 or h < 2:
                    stop_event.wait(0.1)
                    continue

                frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                fh, fw = frame.shape[:2]
                scale = max(w / fw, h / fh)
                nw = max(1, int(fw * scale + 0.5))
                nh = max(1, int(fh * scale + 0.5))
                frame = cv2.resize(
                    frame, (nw, nh), interpolation=cv2.INTER_LINEAR
                )
                x = max(0, (nw - w) // 2)
                y = max(0, (nh - h) // 2)
                frame = frame[y : y + h, x : x + w]

                try:
                    frame_queue.put_nowait(frame)
                except queue.Full:
                    try:
                        frame_queue.get_nowait()
                    except queue.Empty:
                        pass
                    try:
                        frame_queue.put_nowait(frame)
                    except queue.Full:
                        pass

                next_time += interval
                delay = next_time - time.monotonic()
                if delay > 0:
                    stop_event.wait(delay)
                else:
                    next_time = time.monotonic()
        except Exception:
            pass
        finally:
            try:
                cap.release()
            except Exception:
                pass

    # ------------------------------------------------------------------
    # Config / shutdown
    # ------------------------------------------------------------------

    def _save_config(self) -> None:
        self.config.update(
            {
                "geometry": self.root.geometry(),
                "topmost": bool(self.topmost_var.get()),
                "auto_translate": bool(self.auto_var.get()),
                "watch_clipboard": bool(self.watch_var.get()),
                "direction": DIRECTION_MODES[self.direction_cb.current()],
                "theme": self.theme_key,
                "wallpaper": self._wallpaper_path,
                "wallpaper_type": self._wallpaper_kind,
                "text_transparency": self.text_transparency,
            }
        )
        try:
            CONFIG_PATH.write_text(
                json.dumps(self.config, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
        except OSError:
            pass

    def _on_close(self) -> None:
        self._stop_video_wallpaper(clear_image=False)
        for job_name in ("_image_render_job", "_scrim_job"):
            job = getattr(self, job_name, None)
            if job is not None:
                try:
                    self.root.after_cancel(job)
                except tk.TclError:
                    pass
                setattr(self, job_name, None)
        self._stop_clipboard_polling()
        self._save_config()
        self.root.destroy()


def main() -> None:
    if sys.platform == "win32":
        try:
            ctypes.windll.shcore.SetProcessDpiAwareness(1)
        except Exception:
            pass
        try:
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(
                "YiChuang.Translator"
            )
        except Exception:
            pass

    root = tk.Tk()
    TranslatorApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
