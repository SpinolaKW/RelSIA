"""Busca de telas limitada às opções permitidas para a sessão atual."""

import tkinter as tk
import unicodedata

import customtkinter as ctk

from sia_app.ui.icons import icon
from sia_app.ui.theme import COLORS, FONT_FAMILY


class NavigationSearch:
    def __init__(self, parent, destinations, on_select):
        self.parent = parent
        self.destinations = list(destinations)
        self.on_select = on_select
        self.window = None
        self.focus_after = None
        self.result_buttons = []
        self.result_keys = []
        self.selected = 0

    def show(self):
        if self.window is not None and self.window.winfo_exists():
            self.window.lift()
            self.entry.focus_set()
            return
        self.window = ctk.CTkToplevel(self.parent)
        self.window.title("Buscar uma tela · RelSIA")
        self.window.configure(fg_color=COLORS["surface"])
        self.window.resizable(False, False)
        self.window.transient(self.parent)
        ctk.CTkLabel(self.window, text="Para onde vamos?", font=(FONT_FAMILY, 20, "bold"),
                     text_color=COLORS["text"]).pack(anchor="w", padx=24, pady=(20, 4))
        ctk.CTkLabel(self.window, text="Encontre uma tela pelo nome.", font=(FONT_FAMILY, 12),
                     text_color=COLORS["muted"]).pack(anchor="w", padx=24, pady=(0, 14))
        search = ctk.CTkFrame(self.window, fg_color=COLORS["bg"], border_width=1,
                              border_color=COLORS["border"], corner_radius=8)
        search.pack(fill="x", padx=24)
        ctk.CTkLabel(search, text="", image=icon("search", COLORS["muted"], 18), width=30).pack(side="left", padx=(8, 0))
        self.query = tk.StringVar()
        self.entry = ctk.CTkEntry(search, textvariable=self.query, placeholder_text="Ex.: relatórios",
                                  height=40, fg_color=COLORS["bg"], border_width=0, font=(FONT_FAMILY, 13))
        self.entry.pack(side="left", fill="x", expand=True, padx=(0, 8))
        self.results = ctk.CTkScrollableFrame(self.window, height=268, fg_color="transparent", corner_radius=0)
        self.results.pack(fill="both", expand=True, padx=16, pady=14)
        ctk.CTkLabel(self.window, text="↑ ↓ Selecionar     Enter Abrir     Esc Fechar", font=(FONT_FAMILY, 10),
                     text_color=COLORS["muted"]).pack(anchor="w", padx=24, pady=(0, 18))
        self.query.trace_add("write", self._filter)
        self._filter()
        self.window.update_idletasks()
        width, height = max(530, self.window.winfo_reqwidth()), max(450, self.window.winfo_reqheight())
        x = max(0, self.parent.winfo_rootx() + (self.parent.winfo_width() - width) // 2)
        y = max(0, self.parent.winfo_rooty() + (self.parent.winfo_height() - height) // 2)
        self.window.wm_geometry(f"{width}x{height}+{x}+{y}")
        self.window.protocol("WM_DELETE_WINDOW", self.close)
        self.window.bind("<Escape>", lambda _event: self.close())
        self.window.bind("<Return>", lambda _event: self.activate())
        self.window.bind("<Down>", lambda _event: self._move(1))
        self.window.bind("<Up>", lambda _event: self._move(-1))
        self.window.grab_set()
        self.focus_after = self.window.after(100, self._focus_entry)

    def _focus_entry(self):
        self.focus_after = None
        self.entry.focus_set()

    @staticmethod
    def _normalize(value):
        return "".join(char for char in unicodedata.normalize("NFKD", str(value).casefold())
                       if not unicodedata.combining(char))

    def _filter(self, *_args):
        for child in self.results.winfo_children():
            child.destroy()
        self.result_buttons = []
        self.result_keys = []
        query = self._normalize(self.query.get()).strip()
        for key, label in self.destinations:
            if query and query not in self._normalize(label):
                continue
            button = ctk.CTkButton(self.results, text=label, height=42, anchor="w", corner_radius=7,
                                   fg_color="transparent", text_color=COLORS["text"],
                                   hover_color="#F2F6F3", font=(FONT_FAMILY, 13),
                                   image=icon("arrow", COLORS["primary"], 17), compound="left", border_spacing=14,
                                   command=lambda target=key: self.activate(target))
            button.pack(fill="x", pady=3, padx=3)
            self.result_buttons.append(button)
            self.result_keys.append(key)
        if not self.result_keys:
            ctk.CTkLabel(self.results, text="Nenhuma tela encontrada.\nTente outro nome.", justify="center",
                         font=(FONT_FAMILY, 13), text_color=COLORS["muted"]).pack(pady=40)
        self.selected = 0
        self._highlight()
        self.results._parent_canvas.yview_moveto(0)

    def _move(self, direction):
        if self.result_keys:
            self.selected = (self.selected + direction) % len(self.result_keys)
            self._highlight()
            button = self.result_buttons[self.selected]
            canvas = self.results._parent_canvas
            canvas.update_idletasks()
            top = button.winfo_y()
            bottom = top + button.winfo_height()
            start = canvas.canvasy(0)
            end = start + canvas.winfo_height()
            total = max(1, self.results.winfo_height())
            if top < start:
                canvas.yview_moveto(top / total)
            elif bottom > end:
                canvas.yview_moveto((bottom - canvas.winfo_height()) / total)
        return "break"

    def _highlight(self):
        for index, button in enumerate(self.result_buttons):
            button.configure(fg_color=COLORS["primary_soft"] if index == self.selected else "transparent")

    def activate(self, target=None):
        if target is None:
            if not self.result_keys:
                return "break"
            target = self.result_keys[self.selected]
        if target not in {key for key, _label in self.destinations}:
            return "break"
        self.close()
        self.on_select(target)
        return "break"

    def close(self):
        if self.window is not None:
            if self.focus_after is not None:
                self.window.after_cancel(self.focus_after)
                self.focus_after = None
            self.window.grab_release()
            self.window.destroy()
            self.window = None
            self.parent.focus_set()
