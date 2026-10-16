"""Identidade visual compartilhada pelas telas do RelSIA."""

from pathlib import Path
import sys

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
    "muted": "#697C8E",
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
