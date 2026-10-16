"""Identidade visual compartilhada pelas telas do RelSIA."""

from pathlib import Path
import sys
from tkinter import ttk

import customtkinter as ctk


FONT_FAMILY = "Segoe UI" if sys.platform == "win32" else "Arial"


COLORS = {
    "bg": "#F4F6FA",
    "surface": "#FFFFFF",
    "card": "#FFFFFF",
    "primary": "#307564",
    "primary_dark": "#245A4E",
    "primary_soft": "#EAF3EF",
    "text": "#203445",
    "muted": "#5B6E80",
    "border": "#DFE6EE",
    "success": "#307564",
    "warning": "#B57A25",
    "danger": "#C34D55",
    "info": "#417CA7",
    "purple": "#8172AF",
    "teal": "#42998C",
    "orange": "#B67B41",
    "nav": "#132533",
    "nav_text": "#B6C7D4",
    "nav_muted": "#7F99AA",
    "nav_active": "#25473F",
    "nav_hover": "#1D3544",
    "mint": "#86C7B1",
}


def apply_theme() -> None:
    """Carrega o mesmo tema nos diálogos e na janela principal."""
    ctk.set_appearance_mode("light")
    ctk.set_default_color_theme(str(Path(__file__).with_name("relsia_theme.json")))


def configure_table_style(master, name="RelSIA.Treeview"):
    """Usa as opções nativas do ttk para manter texto e seleção legíveis."""
    style = ttk.Style(master)
    style.configure(name, background=COLORS["surface"], fieldbackground=COLORS["surface"],
                    foreground=COLORS["text"], rowheight=36, borderwidth=0,
                    bordercolor=COLORS["border"], lightcolor=COLORS["border"], darkcolor=COLORS["border"],
                    font=(FONT_FAMILY, 11))
    style.configure(name + ".Heading", background="#F1F5F8", foreground=COLORS["muted"],
                    font=(FONT_FAMILY, 10, "bold"), padding=(12, 11), relief="flat")
    style.map(name, background=[("selected", "#DCEDE5")],
              foreground=[("selected", COLORS["primary_dark"])])
    style.map(name + ".Heading", background=[("active", "#E8EFEC")])
    for direction in ("Vertical", "Horizontal"):
        scrollbar = direction + ".TScrollbar"
        style.configure(scrollbar, background="#C7D3DC", troughcolor=COLORS["surface"],
                        bordercolor=COLORS["surface"], lightcolor="#C7D3DC", darkcolor="#C7D3DC",
                        arrowcolor=COLORS["muted"], arrowsize=11, borderwidth=0, gripcount=0)
        style.map(scrollbar, background=[("active", "#A6BAC6"), ("pressed", "#92AEBE")])
    return name
