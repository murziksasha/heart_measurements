"""Shared colors and widgets for the portable ECG tools."""

import tkinter as tk
from tkinter import ttk

PRIMARY = "#2ea2f8"
PRIMARY_HOVER = "#1a8de4"
TEXT = "#2c3e50"
MUTED = "#7f8c8d"
BG = "#f8fafd"
CARD = "#ffffff"
BORDER = "#dce4ec"
SUCCESS = "#1e7a46"
WARNING = "#b86e00"
ERROR = "#c0392b"
ROW_ALT = "#f4f8fb"
STRIPE = "#eef3f8"

FONT = ("Segoe UI", 10)
FONT_BOLD = ("Segoe UI", 10, "bold")
FONT_SMALL = ("Segoe UI", 9)
FONT_TITLE = ("Segoe UI", 16, "bold")


def apply_theme(root):
    """Clam theme tuned to the ECG Data Management blue."""
    style = ttk.Style(root)
    try:
        style.theme_use("clam")
    except Exception:
        pass
    style.configure(
        "Treeview",
        background=CARD,
        foreground=TEXT,
        fieldbackground=CARD,
        font=FONT,
        rowheight=32,
        borderwidth=0,
    )
    style.configure(
        "Treeview.Heading",
        background=STRIPE,
        foreground=TEXT,
        font=FONT_BOLD,
        relief="flat",
    )
    style.map("Treeview", background=[("selected", "#e3f2fd")], foreground=[("selected", TEXT)])
    style.configure(
        "TProgressbar",
        background=PRIMARY,
        troughcolor="#e6eef5",
        borderwidth=0,
        thickness=8,
    )
    style.configure("TCheckbutton", background=CARD, font=FONT)
    style.configure("Alt.TCheckbutton", background=ROW_ALT, font=FONT)
    style.configure("TCombobox", padding=2)
    return style


def center(window, width, height):
    window.update_idletasks()
    screen_w = window.winfo_screenwidth()
    screen_h = window.winfo_screenheight()
    x = max(0, (screen_w - width) // 2)
    y = max(0, (screen_h - height) // 2)
    window.geometry("%dx%d+%d+%d" % (width, height, x, y))


def button(parent, text, command, kind="secondary", **kwargs):
    """Flat button. kind is primary, secondary, quiet, or danger."""
    if kind == "primary":
        colors = dict(bg=PRIMARY, fg="#ffffff", activebackground=PRIMARY_HOVER, activeforeground="#ffffff")
        edge = PRIMARY
    elif kind == "danger":
        colors = dict(bg=CARD, fg=ERROR, activebackground="#fdecea", activeforeground=ERROR)
        edge = BORDER
    elif kind == "quiet":
        colors = dict(bg=BG, fg=PRIMARY, activebackground="#e8f4fd", activeforeground=PRIMARY_HOVER)
        edge = BG
    else:
        colors = dict(bg=CARD, fg=TEXT, activebackground=STRIPE, activeforeground=TEXT)
        edge = BORDER
    options = dict(
        font=FONT_BOLD if kind == "primary" else FONT,
        relief="flat",
        bd=0,
        highlightthickness=1,
        highlightbackground=edge,
        highlightcolor=PRIMARY,
        cursor="hand2",
        padx=14,
        pady=6,
        command=command,
    )
    options.update(colors)
    options.update(kwargs)
    return tk.Button(parent, text=text, **options)
