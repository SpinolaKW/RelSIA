"""Formulário modal reutilizável para estabelecimentos."""

from __future__ import annotations

from tkinter import messagebox
from typing import Callable, Mapping, Optional

import customtkinter as ctk
from sia_app.ui.theme import FONT_FAMILY


class EstablishmentForm:
    def __init__(self, parent, colors: Mapping[str, str], on_save: Callable):
        self.parent = parent
        self.colors = colors
        self.on_save = on_save

    def show(self, record_id: Optional[int] = None, values: Optional[Mapping] = None):
        window = ctk.CTkToplevel(self.parent)
        editing = record_id is not None
        window.title("Editar Estabelecimento" if editing else "Novo Estabelecimento")
        window.geometry("560x360")
        window.resizable(False, False)
        window.transient(self.parent)
        window.grab_set()
        window.configure(fg_color=self.colors["bg"])
        window.update_idletasks()
        x = (window.winfo_screenwidth() - 560) // 2
        y = (window.winfo_screenheight() - 360) // 2
        window.geometry(f"560x360+{x}+{y}")

        main = ctk.CTkFrame(window, fg_color=self.colors["bg"], corner_radius=0)
        main.pack(fill="both", expand=True, padx=18, pady=18)
        ctk.CTkLabel(
            main,
            text="Editar Estabelecimento" if editing else "Novo Estabelecimento",
            font=(FONT_FAMILY, 20, "bold"),
            text_color=self.colors["text"],
        ).pack(anchor="w")
        ctk.CTkLabel(
            main,
            text="Atualize os dados selecionados" if editing else "Preencha os dados do estabelecimento",
            font=(FONT_FAMILY, 12),
            text_color=self.colors["muted"],
        ).pack(anchor="w", pady=(2, 14))

        card = ctk.CTkFrame(
            main,
            fg_color=self.colors["card"],
            border_color=self.colors["border"],
            border_width=1,
            corner_radius=12,
        )
        card.pack(fill="both", expand=True)
        form = ctk.CTkFrame(card, fg_color="transparent")
        form.pack(fill="both", expand=True, padx=18, pady=18)
        form.grid_columnconfigure(1, weight=1)

        fields = {}
        for row, (key, label, placeholder) in enumerate(
            (
                ("CO_CNES", "CNES *", "Número do CNES obrigatório"),
                ("NO_FANTASIA", "Nome Fantasia *", "Nome do estabelecimento obrigatório"),
                ("CO_CEP", "CEP", "CEP do estabelecimento"),
            )
        ):
            ctk.CTkLabel(
                form,
                text=label,
                font=(FONT_FAMILY, 12, "bold"),
                text_color=self.colors["text"],
            ).grid(row=row, column=0, sticky="w", padx=(0, 12), pady=8)
            entry = ctk.CTkEntry(
                form,
                height=36,
                border_color=self.colors["border"],
                placeholder_text=placeholder,
                font=(FONT_FAMILY, 12),
            )
            entry.grid(row=row, column=1, sticky="ew", pady=8)
            if values:
                entry.insert(0, values.get(key, "") or "")
            fields[key] = entry

        def save():
            try:
                action = self.on_save(
                    record_id,
                    {key: entry.get().strip() for key, entry in fields.items()},
                )
                window.destroy()
                messagebox.showinfo("Sucesso", f"Estabelecimento {action} com sucesso!")
            except ValueError as exc:
                messagebox.showwarning("Validação", str(exc))
            except Exception as exc:
                message = "Já existe um estabelecimento com este CNES." if "UNIQUE" in str(exc) else str(exc)
                messagebox.showerror("Erro", message)

        buttons = ctk.CTkFrame(form, fg_color="transparent")
        buttons.grid(row=3, column=0, columnspan=2, pady=(22, 0))
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
        window.after(100, fields["CO_CNES"].focus_set)
