"""Diálogos auxiliares da aba de filtros."""

from __future__ import annotations

from tkinter import ttk
from typing import Callable, List, Mapping

import customtkinter as ctk
from sia_app.ui.theme import FONT_FAMILY


PROCEDURE_HELP_TEXT = """
SISTEMA DE CODIFICAÇÃO DE PROCEDIMENTOS

2 DÍGITOS = GRUPO
Exemplo: "03" = Consultas

4 DÍGITOS = SUBGRUPO
Exemplo: "0301" = Consultas médicas

6 DÍGITOS = FORMA
Exemplo: "030101" = Consulta médica em especialidade

CÓDIGO COMPLETO = PROCEDIMENTO ÚNICO
Exemplo: "0301010039" = Consulta médica em pediatria

EXEMPLOS DE USO:
• "03" = Todos os procedimentos do grupo
• "0301" = Todos os procedimentos do subgrupo
• "030101" = Todos os procedimentos da forma de organização
• "0301010039" = Apenas o procedimento específico

DICA: Use o botão "Grupos" para consultar os grupos mais comuns.
""".strip()


class FilterDialogs:
    def __init__(self, parent, colors: Mapping[str, str]):
        self.parent = parent
        self.colors = colors

    def show_procedure_help(self):
        window, main = self._base_window(
            "Ajuda - Códigos de Procedimento", 620, 520
        )
        self._header(
            main,
            "Ajuda - Códigos de Procedimento",
            "Entenda como filtrar por grupo, subgrupo, forma ou código completo",
        )
        card = ctk.CTkFrame(
            main,
            fg_color=self.colors["card"],
            border_color=self.colors["border"],
            border_width=1,
            corner_radius=12,
        )
        card.pack(fill="both", expand=True)
        text = ctk.CTkTextbox(
            card,
            wrap="word",
            font=(FONT_FAMILY, 13),
            text_color=self.colors["text"],
            fg_color="#F8FAFC",
            border_color=self.colors["border"],
            border_width=1,
            corner_radius=8,
        )
        text.pack(fill="both", expand=True, padx=16, pady=16)
        text.insert("1.0", PROCEDURE_HELP_TEXT)
        text.configure(state="disabled")
        self._footer_button(main, "Fechar", window.destroy)

    def show_common_groups(
        self,
        groups: List[Mapping],
        on_select: Callable[[str], None],
    ):
        window, main = self._base_window(
            "Grupos de Procedimentos Comuns", 760, 500
        )
        self._header(
            main,
            "Grupos de Procedimentos Comuns",
            "Selecione um grupo para aplicar ao filtro",
        )
        card = ctk.CTkFrame(
            main,
            fg_color=self.colors["card"],
            border_color=self.colors["border"],
            border_width=1,
            corner_radius=12,
        )
        card.pack(fill="both", expand=True)
        inner = ctk.CTkFrame(card, fg_color="transparent")
        inner.pack(fill="both", expand=True, padx=16, pady=16)

        style = ttk.Style(window)
        style.configure(
            "ModernGroups.Treeview",
            background="#FFFFFF",
            fieldbackground="#FFFFFF",
            foreground=self.colors["text"],
            rowheight=30,
            font=(FONT_FAMILY, 10),
            borderwidth=0,
        )
        style.configure(
            "ModernGroups.Treeview.Heading",
            font=(FONT_FAMILY, 10, "bold"),
            foreground=self.colors["text"],
            background="#F8FAFC",
            relief="flat",
        )
        tree_frame = ttk.Frame(inner)
        tree_frame.pack(fill="both", expand=True)
        tree = ttk.Treeview(
            tree_frame,
            columns=("grupo", "descricao", "total"),
            show="headings",
            height=12,
            style="ModernGroups.Treeview",
        )
        for column, label, width, anchor in (
            ("grupo", "Grupo", 90, "center"),
            ("descricao", "Descrição", 470, "w"),
            ("total", "Registros", 120, "center"),
        ):
            tree.heading(column, text=label)
            tree.column(column, width=width, anchor=anchor)
        tree.tag_configure("linha_branca", background="#FFFFFF")
        tree.tag_configure("linha_sombra", background="#F7F9FC")
        for index, group in enumerate(groups):
            tree.insert(
                "",
                "end",
                values=(
                    group["grupo"],
                    group["descricao"],
                    f"{group['total']:,}".replace(",", "."),
                ),
                tags=("linha_branca" if index % 2 == 0 else "linha_sombra",),
            )
        scrollbar = ttk.Scrollbar(tree_frame, orient="vertical", command=tree.yview)
        tree.configure(yscrollcommand=scrollbar.set)
        tree.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        def select_group(_event=None):
            selection = tree.selection()
            if not selection:
                return
            code = str(tree.item(selection[0])["values"][0]).strip().zfill(2)
            on_select(code)
            window.destroy()

        tree.bind("<Double-1>", select_group)
        footer = ctk.CTkFrame(main, fg_color="transparent")
        footer.pack(fill="x", pady=(14, 0))
        ctk.CTkButton(
            footer,
            text="Selecionar Grupo",
            command=select_group,
            width=160,
            height=38,
            fg_color=self.colors["primary"],
            hover_color=self.colors["primary_dark"],
            font=(FONT_FAMILY, 12, "bold"),
        ).pack(side="right")
        ctk.CTkButton(
            footer,
            text="Fechar",
            command=window.destroy,
            width=110,
            height=38,
            fg_color="#FFFFFF",
            hover_color=self.colors["primary_soft"],
            border_color=self.colors["border"],
            border_width=1,
            text_color=self.colors["text"],
            font=(FONT_FAMILY, 12, "bold"),
        ).pack(side="right", padx=(0, 10))

    def _base_window(self, title: str, width: int, height: int):
        window = ctk.CTkToplevel(self.parent)
        window.title(title)
        window.geometry(f"{width}x{height}")
        window.resizable(False, False)
        window.transient(self.parent)
        window.grab_set()
        window.configure(fg_color=self.colors["bg"])
        window.update_idletasks()
        x = (window.winfo_screenwidth() - width) // 2
        y = (window.winfo_screenheight() - height) // 2
        window.geometry(f"{width}x{height}+{x}+{y}")
        main = ctk.CTkFrame(window, fg_color=self.colors["bg"], corner_radius=0)
        main.pack(fill="both", expand=True, padx=18, pady=18)
        return window, main

    def _header(self, parent, title: str, subtitle: str):
        header = ctk.CTkFrame(parent, fg_color="transparent")
        header.pack(fill="x", pady=(0, 14))
        ctk.CTkLabel(
            header,
            text=title,
            font=(FONT_FAMILY, 20, "bold"),
            text_color=self.colors["text"],
        ).pack(anchor="w")
        ctk.CTkLabel(
            header,
            text=subtitle,
            font=(FONT_FAMILY, 12),
            text_color=self.colors["muted"],
        ).pack(anchor="w", pady=(2, 0))

    def _footer_button(self, parent, text: str, command):
        footer = ctk.CTkFrame(parent, fg_color="transparent")
        footer.pack(fill="x", pady=(14, 0))
        ctk.CTkButton(
            footer,
            text=text,
            command=command,
            width=120,
            height=36,
            fg_color=self.colors["primary"],
            hover_color=self.colors["primary_dark"],
            font=(FONT_FAMILY, 12, "bold"),
        ).pack(side="right")
