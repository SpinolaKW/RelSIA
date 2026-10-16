"""Componentes de apresentação usados em diferentes telas."""

import tkinter as tk

import customtkinter as ctk

from sia_app.ui.theme import COLORS, FONT_FAMILY


class PageHeader(ctk.CTkFrame):
    def __init__(self, parent, category, title, description):
        super().__init__(parent, fg_color="transparent", corner_radius=0)
        ctk.CTkLabel(self, text=category.upper(), font=(FONT_FAMILY, 10, "bold"),
                     text_color=COLORS["muted"], anchor="w").pack(anchor="w")
        ctk.CTkLabel(self, text=title, font=(FONT_FAMILY, 28, "bold"),
                     text_color=COLORS["text"], anchor="w").pack(anchor="w", pady=(2, 3))
        self.description = ctk.CTkLabel(self, text=description, font=(FONT_FAMILY, 13),
                                        text_color=COLORS["muted"], anchor="w", justify="left")
        self.description.pack(fill="x")
        self.bind("<Configure>", self._fit_description, add="+")

    def _fit_description(self, event):
        self.description.configure(wraplength=max(200, event.width - 20))


class Tooltip:
    """Descrição curta para ações que também podem aparecer apenas como ícones."""

    def __init__(self, widget, text):
        self.widget = widget
        self.text = text
        self.pending = None
        self.window = None
        widget.bind("<Enter>", self._schedule, add="+")
        widget.bind("<Leave>", self.hide, add="+")
        widget.bind("<ButtonPress>", self.hide, add="+")
        widget.bind("<Destroy>", self.hide, add="+")

    def _schedule(self, _event=None):
        self.hide()
        self.pending = self.widget.after(500, self._show)

    def _show(self):
        self.pending = None
        if not self.widget.winfo_exists() or not self.widget.winfo_viewable():
            return
        self.window = tk.Toplevel(self.widget)
        self.window.overrideredirect(True)
        label = tk.Label(self.window, text=self.text, background=COLORS["nav"], foreground="#FFFFFF",
                         font=(FONT_FAMILY, 10), padx=12, pady=8, relief="flat", justify="left")
        label.pack()
        self.window.update_idletasks()
        x = min(self.widget.winfo_rootx() + 12,
                self.window.winfo_screenwidth() - self.window.winfo_reqwidth() - 8)
        y = min(self.widget.winfo_rooty() + self.widget.winfo_height() + 5,
                self.window.winfo_screenheight() - self.window.winfo_reqheight() - 8)
        self.window.geometry(f"+{max(0, x)}+{max(0, y)}")

    def hide(self, _event=None):
        if self.pending is not None:
            self.widget.after_cancel(self.pending)
            self.pending = None
        if self.window is not None:
            self.window.destroy()
            self.window = None
