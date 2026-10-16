"""Janela de visualização dos registros filtrados."""

from __future__ import annotations

from tkinter import ttk
from typing import Callable, List, Mapping

import customtkinter as ctk
from sia_app.ui.theme import configure_table_style
from sia_app.ui.theme import FONT_FAMILY

from sia_app.services.data_view_service import DataViewService


DATA_VIEWER_TOTALS_TITLE_FONT = ("Segoe UI", 16, "bold")
DATA_VIEWER_TOTALS_TEXT_FONT = ("Segoe UI", 13, "bold")


COLUMNS = (
    "cnes",
    "estabelecimento",
    "competencia",
    "procedimento",
    "descricao",
    "cbo",
    "financ_producao",
    "complex_producao",
    "financ_procedimento",
    "complex_procedimento",
    "quantidade",
    "valor_unitario",
    "qtd_produzida",
    "vl_produzido",
    "qtd_aprovada",
    "vl_aprovado",
    "valor_total",
)

COLUMN_CONFIGS = (
    ("cnes", "CNES", 80, "center"),
    ("estabelecimento", "Estabelecimento", 220, "w"),
    ("competencia", "Comp.", 90, "center"),
    ("procedimento", "Procedimento", 110, "center"),
    ("descricao", "Descrição", 260, "w"),
    ("cbo", "CBO", 90, "center"),
    ("financ_producao", "Tipo de Financ.", 230, "w"),
    ("complex_producao", "Complex.", 190, "w"),
    ("financ_procedimento", "Financ. Procedimento", 230, "w"),
    ("complex_procedimento", "Complex. Procedimento", 190, "w"),
    ("quantidade", "Qtde.", 90, "center"),
    ("valor_unitario", "Valor Unit.", 110, "center"),
    ("qtd_produzida", "Qtd. Produzida", 110, "center"),
    ("vl_produzido", "Valor Produzido", 120, "center"),
    ("qtd_aprovada", "Qtd. Aprovada", 110, "center"),
    ("vl_aprovado", "Valor Aprovado", 120, "center"),
    ("valor_total", "Valor Total", 110, "center"),
)


class DataViewerWindow:
    """Desenha a janela; preparação e cálculos ficam no serviço."""

    def __init__(
        self,
        parent,
        dados: List[Mapping],
        estabelecimentos: Mapping[str, str],
        colors: Mapping[str, str],
        log: Callable[[str], None],
    ):
        self.parent = parent
        self.dados = dados
        self.estabelecimentos = estabelecimentos
        self.colors = colors
        self.log = log
        self.result = DataViewService().prepare(dados, estabelecimentos)

    def show(self):
        window = ctk.CTkToplevel(self.parent)
        window.title(f"Visualização de Dados - {len(self.dados)} registros")
        window.geometry("1700x850")
        window.minsize(1300, 720)
        window.transient(self.parent)
        window.grab_set()
        window.configure(fg_color=self.colors["bg"])
        self._center(window, 1700, 850)

        main = ctk.CTkFrame(window, fg_color=self.colors["bg"], corner_radius=0)
        main.pack(fill="both", expand=True, padx=18, pady=18)

        self._build_header(main)
        tree = self._build_table(main, window)
        for index, values in enumerate(self.result.rows):
            tree.insert(
                "",
                "end",
                values=values,
                tags=("linha_par" if index % 2 == 0 else "linha_impar",),
            )

        self._build_totals(main)
        footer = ctk.CTkFrame(main, fg_color="transparent")
        footer.pack(fill="x", pady=(14, 0))
        ctk.CTkButton(
            footer,
            text="Fechar",
            command=window.destroy,
            width=120,
            height=38,
            corner_radius=7,
            fg_color=self.colors["primary"],
            hover_color=self.colors["primary_dark"],
            text_color="#FFFFFF",
            font=(FONT_FAMILY, 12, "bold"),
        ).pack(side="right")

        totals = self.result.totals
        self.log(f"Dados carregados na visualização: {len(self.result.rows)} registros")
        self.log(
            "Totais - "
            f"Quantidade: {totals['quantidade']:.0f}, "
            f"Valor: {DataViewService.format_money(totals['valor'])}, "
            f"Qtd. Aprovada: {totals['qtd_aprovada']:.0f}, "
            f"Valor Aprovado: {DataViewService.format_money(totals['valor_aprovado'])}, "
            f"Qtd. Produzida: {totals['qtd_produzida']:.0f}, "
            f"Valor Produzido: {DataViewService.format_money(totals['valor_produzido'])}"
        )
        return window

    @staticmethod
    def _center(window, width: int, height: int):
        window.update_idletasks()
        x = (window.winfo_screenwidth() - width) // 2
        y = (window.winfo_screenheight() - height) // 2
        window.geometry(f"{width}x{height}+{x}+{y}")

    def _build_header(self, parent):
        header = ctk.CTkFrame(parent, fg_color="transparent")
        header.pack(fill="x", pady=(0, 14))
        ctk.CTkLabel(
            header,
            text="Visualização de Dados",
            font=(FONT_FAMILY, 22, "bold"),
            text_color=self.colors["text"],
        ).pack(anchor="center")
        ctk.CTkLabel(
            header,
            text=f"{len(self.result.rows)} registro(s) encontrados com os filtros atuais",
            font=(FONT_FAMILY, 12),
            text_color=self.colors["muted"],
        ).pack(anchor="center", pady=(2, 0))

    def _build_table(self, parent, window):
        card = ctk.CTkFrame(
            parent,
            fg_color=self.colors["card"],
            border_color=self.colors["border"],
            border_width=1,
            corner_radius=12,
        )
        card.pack(fill="both", expand=True)
        frame = ctk.CTkFrame(card, fg_color="transparent")
        frame.pack(fill="both", expand=True, padx=16, pady=16)

        configure_table_style(window, "ModernData.Treeview")

        tree = ttk.Treeview(
            frame, columns=COLUMNS, show="headings", height=15, style="ModernData.Treeview"
        )
        tree.tag_configure("linha_par", background="#F7F9FC")
        tree.tag_configure("linha_impar", background="#FFFFFF")
        for name, heading, width, anchor in COLUMN_CONFIGS:
            tree.heading(name, text=heading)
            tree.column(name, width=width, anchor=anchor)

        vertical = ttk.Scrollbar(frame, orient="vertical", command=tree.yview)
        horizontal = ttk.Scrollbar(frame, orient="horizontal", command=tree.xview)
        tree.configure(yscrollcommand=vertical.set, xscrollcommand=horizontal.set)
        tree.grid(row=0, column=0, sticky="nsew")
        vertical.grid(row=0, column=1, sticky="ns")
        horizontal.grid(row=1, column=0, sticky="ew")
        frame.columnconfigure(0, weight=1)
        frame.rowconfigure(0, weight=1)
        return tree

    def _build_totals(self, parent):
        totals = self.result.totals
        card = ctk.CTkFrame(
            parent,
            fg_color=self.colors["card"],
            border_color=self.colors["border"],
            border_width=1,
            corner_radius=12,
        )
        card.pack(fill="x", pady=(14, 0))
        ctk.CTkLabel(
            card,
            text="Totais da Visualização",
            font=DATA_VIEWER_TOTALS_TITLE_FONT,
            text_color=self.colors["text"],
        ).pack(anchor="center", padx=18, pady=(16, 10))

        outer = ctk.CTkFrame(card, fg_color="transparent")
        outer.pack(fill="x", padx=18, pady=(0, 18))
        grid = ctk.CTkFrame(outer, fg_color="transparent")
        grid.pack(anchor="center")

        entries = (
            ("Total de Quantidade:", DataViewService.format_int(totals["quantidade"]), 0, 0, "primary"),
            ("Total de Valor:", DataViewService.format_money(totals["valor"]), 0, 2, "success"),
            ("Qtd. Aprovada:", DataViewService.format_int(totals["qtd_aprovada"]), 1, 0, "primary"),
            ("Valor Aprovado:", DataViewService.format_money(totals["valor_aprovado"]), 1, 2, "success"),
            ("Qtd. Produzida:", DataViewService.format_int(totals["qtd_produzida"]), 1, 4, "primary"),
            ("Valor Produzido:", DataViewService.format_money(totals["valor_produzido"]), 1, 6, "success"),
        )
        for label, value, row, column, color in entries:
            ctk.CTkLabel(
                grid,
                text=label,
                font=DATA_VIEWER_TOTALS_TEXT_FONT,
                text_color=self.colors["text"],
            ).grid(row=row, column=column, sticky="w", padx=(0, 8), pady=7)
            ctk.CTkLabel(
                grid,
                text=value,
                font=DATA_VIEWER_TOTALS_TEXT_FONT,
                text_color=self.colors[color],
            ).grid(row=row, column=column + 1, sticky="w", padx=(0, 26), pady=7)
