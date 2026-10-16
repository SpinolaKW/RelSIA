"""Formulário modal de edição de um registro de produção."""

from __future__ import annotations

import tkinter as tk
from tkinter import messagebox
from typing import Callable, Mapping, Sequence

import customtkinter as ctk
from sia_app.ui.theme import FONT_FAMILY


class ProductionEditDialog:
    def __init__(
        self,
        parent,
        colors: Mapping[str, str],
        on_save: Callable[[object, str, str], None],
    ):
        self.parent = parent
        self.colors = colors
        self.on_save = on_save

    def show(self, values: Sequence):
        record_id = values[0]
        window = ctk.CTkToplevel(self.parent)
        window.title("Editar registro de produção")
        window.geometry("640x500")
        window.resizable(False, False)
        window.grab_set()
        window.configure(fg_color=self.colors["bg"])
        window.update_idletasks()
        x = (window.winfo_screenwidth() - 640) // 2
        y = (window.winfo_screenheight() - 500) // 2
        window.geometry(f"640x500+{x}+{y}")

        container = ctk.CTkFrame(window, fg_color=self.colors["bg"], corner_radius=0)
        container.pack(fill="both", expand=True, padx=18, pady=18)
        ctk.CTkLabel(
            container,
            text="Editar registro de produção",
            font=(FONT_FAMILY, 20, "bold"),
            text_color=self.colors["text"],
        ).pack(anchor="center")
        ctk.CTkLabel(
            container,
            text="Altere as quantidades; os valores são recalculados pela tabela PA",
            font=(FONT_FAMILY, 12),
            text_color=self.colors["muted"],
        ).pack(anchor="center", pady=(2, 14))

        card = ctk.CTkFrame(
            container,
            fg_color=self.colors["card"],
            border_color=self.colors["border"],
            border_width=1,
            corner_radius=12,
        )
        card.pack(fill="both", expand=True)
        form = ctk.CTkFrame(card, fg_color="transparent")
        form.pack(anchor="center", expand=True, padx=20, pady=20)
        form.grid_columnconfigure(1, weight=1)

        cnes, estabelecimento, competencia = values[1], values[2], values[3]
        procedimento, descricao = values[4], values[6]
        ctk.CTkLabel(
            form,
            text=f"{cnes} - {estabelecimento} - {competencia}",
            font=(FONT_FAMILY, 12, "bold"),
            text_color=self.colors["text"],
            wraplength=560,
        ).grid(row=0, column=0, columnspan=2, pady=(0, 6), sticky="ew")
        ctk.CTkLabel(
            form,
            text=f"{procedimento} - {descricao or 'DESCRIÇÃO NÃO ENCONTRADA'}",
            font=(FONT_FAMILY, 11),
            text_color=self.colors["muted"],
            wraplength=560,
        ).grid(row=1, column=0, columnspan=2, pady=(0, 18), sticky="ew")

        fields = {
            "Quantidade Produzida": tk.StringVar(value=values[11]),
            "Quantidade Aprovada": tk.StringVar(value=values[12]),
            "Valor Produzido": tk.StringVar(value=values[13]),
            "Valor Aprovado": tk.StringVar(value=values[14]),
        }
        for row, label in enumerate(fields, start=2):
            ctk.CTkLabel(
                form,
                text=f"{label}:",
                font=(FONT_FAMILY, 12, "bold"),
                text_color=self.colors["text"],
                width=180,
                anchor="e",
            ).grid(row=row, column=0, padx=(0, 12), pady=7, sticky="e")
            ctk.CTkEntry(
                form,
                textvariable=fields[label],
                width=140,
                height=36,
                border_color=self.colors["border"],
                justify="center",
                font=(FONT_FAMILY, 12),
                state="disabled" if label.startswith("Valor") else "normal",
            ).grid(row=row, column=1, pady=7, sticky="w")

        def save():
            try:
                self.on_save(
                    record_id,
                    fields["Quantidade Produzida"].get(),
                    fields["Quantidade Aprovada"].get(),
                )
                window.destroy()
                messagebox.showinfo("Sucesso", "Registro atualizado com sucesso.")
            except Exception as exc:
                messagebox.showerror("Erro", f"Erro ao salvar:\n{exc}")

        buttons = ctk.CTkFrame(form, fg_color="transparent")
        buttons.grid(row=6, column=0, columnspan=2, pady=(24, 0))
        ctk.CTkButton(
            buttons,
            text="Cancelar",
            command=window.destroy,
            width=120,
            height=36,
            fg_color="#FFFFFF",
            hover_color=self.colors["primary_soft"],
            border_color=self.colors["border"],
            border_width=1,
            text_color=self.colors["text"],
            font=(FONT_FAMILY, 12, "bold"),
        ).pack(side="left", padx=(0, 10))
        ctk.CTkButton(
            buttons,
            text="Salvar",
            command=save,
            width=120,
            height=36,
            fg_color=self.colors["primary"],
            hover_color=self.colors["primary_dark"],
            font=(FONT_FAMILY, 12, "bold"),
        ).pack(side="left")
