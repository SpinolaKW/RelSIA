"""Janelas modais de primeiro acesso e login do Sistema SIA."""

from __future__ import annotations

import logging
import tkinter as tk

import customtkinter as ctk

from sia_app.services.auth_service import (
    AuthService,
    AuthenticationError,
    InvalidCredentialsError,
    UserSession,
)


from sia_app.ui.theme import COLORS, apply_theme, FONT_FAMILY
from sia_app.ui.icons import icon

AUTH_DIALOG_MIN_WIDTH = 500
AUTH_DIALOG_LOGIN_MIN_HEIGHT = 560
AUTH_DIALOG_FIRST_ACCESS_MIN_HEIGHT = 630


class AuthDialog:
    """Controla o acesso antes que a janela principal seja construída."""

    def __init__(
        self,
        root: tk.Tk,
        auth_service: AuthService,
        logger: logging.Logger,
    ) -> None:
        self.root = root
        self.auth_service = auth_service
        self.logger = logger
        self.result: UserSession | None = None
        self.window: ctk.CTkToplevel | None = None
        self.password_entries: list[ctk.CTkEntry] = []

    def show(self) -> UserSession | None:
        apply_theme()
        first_access = not self.auth_service.has_users()
        self.window = ctk.CTkToplevel(self.root)
        self.window.title(
            "Primeiro acesso - Sistema SIA" if first_access else "Entrar - Sistema SIA"
        )
        self.window.resizable(False, False)
        self.window.configure(fg_color=COLORS["bg"])
        self.window.protocol("WM_DELETE_WINDOW", self._cancel)
        # Um diálogo transitório de uma janela oculta também pode ficar
        # oculto em alguns gerenciadores de janelas. O login é independente
        # enquanto a janela principal ainda não foi apresentada.
        if self.root.winfo_viewable():
            self.window.transient(self.root)

        if first_access:
            self._build_first_access()
            self._fit_and_center(
                AUTH_DIALOG_MIN_WIDTH,
                AUTH_DIALOG_FIRST_ACCESS_MIN_HEIGHT,
            )
        else:
            self._build_login()
            self._fit_and_center(
                AUTH_DIALOG_MIN_WIDTH,
                AUTH_DIALOG_LOGIN_MIN_HEIGHT,
            )

        self.window.grab_set()
        self.window.lift()
        self.window.focus_force()
        self.root.wait_window(self.window)
        return self.result

    def _fit_and_center(self, min_width: int, min_height: int) -> None:
        """Dimensiona pela necessidade real do formulário e centraliza a janela.

        Usar apenas uma geometria fixa cortava o rodapé com os botões em algumas
        escalas do Windows. ``winfo_req*`` inclui o tamanho efetivamente pedido
        pelos widgets já escalados pelo CustomTkinter.
        """
        assert self.window is not None
        self.window.wm_geometry("")
        self.window.update_idletasks()
        width = max(min_width, self.window.winfo_reqwidth())
        height = max(min_height, self.window.winfo_reqheight())
        x = max(0, (self.window.winfo_screenwidth() - width) // 2)
        y = max(0, (self.window.winfo_screenheight() - height) // 2)

        # Chama o gerenciador Tk diretamente para não aplicar a escala do
        # CustomTkinter uma segunda vez sobre as dimensões já solicitadas.
        self.window.wm_geometry(f"{width}x{height}+{x}+{y}")

    def _base_card(self, title: str, subtitle: str) -> ctk.CTkFrame:
        assert self.window is not None
        top = ctk.CTkFrame(
            self.window,
            fg_color=COLORS["nav"],
            corner_radius=0,
            height=116,
        )
        top.pack(fill="x")
        top.pack_propagate(False)
        ctk.CTkLabel(
            top,
            text="RelSIA",
            image=icon("brand", "#A5D5C3", 28),
            compound="left",
            padx=12,
            text_color="#FFFFFF",
            font=(FONT_FAMILY, 29, "bold"),
        ).pack(pady=(25, 3))
        ctk.CTkLabel(
            top,
            text="GESTÃO DA PRODUÇÃO AMBULATORIAL",
            text_color="#9DB8C8",
            font=(FONT_FAMILY, 12),
        ).pack()

        card = ctk.CTkFrame(
            self.window,
            fg_color=COLORS["surface"],
            border_color=COLORS["border"],
            border_width=1,
            corner_radius=12,
        )
        card.pack(fill="both", expand=True, padx=38, pady=24)
        ctk.CTkLabel(
            card,
            text=title,
            text_color=COLORS["text"],
            font=(FONT_FAMILY, 19, "bold"),
        ).pack(anchor="w", padx=26, pady=(22, 2))
        ctk.CTkLabel(
            card,
            text=subtitle,
            text_color=COLORS["muted"],
            font=(FONT_FAMILY, 11),
            justify="left",
            wraplength=360,
        ).pack(anchor="w", padx=26, pady=(0, 16))
        return card

    @staticmethod
    def _field(parent, label: str, *, show: str | None = None) -> ctk.CTkEntry:
        ctk.CTkLabel(
            parent,
            text=label,
            text_color=COLORS["text"],
            font=(FONT_FAMILY, 11, "bold"),
        ).pack(anchor="w", padx=26, pady=(0, 5))
        entry = ctk.CTkEntry(
            parent,
            height=38,
            corner_radius=7,
            border_color=COLORS["border"],
            fg_color="#FFFFFF",
            text_color=COLORS["text"],
            font=(FONT_FAMILY, 12),
            show=show or "",
        )
        entry.pack(fill="x", padx=26, pady=(0, 12))
        return entry

    def _build_first_access(self) -> None:
        card = self._base_card(
            "Crie a senha do administrador",
            "Este é o primeiro acesso. A conta inicial será “admin” e "
            "terá acesso completo ao sistema.",
        )
        ctk.CTkLabel(
            card,
            text="Usuário: admin",
            text_color=COLORS["primary"],
            fg_color=COLORS["primary_soft"],
            corner_radius=6,
            font=(FONT_FAMILY, 11, "bold"),
            height=31,
        ).pack(fill="x", padx=26, pady=(0, 14))

        self.password_entry = self._field(card, "Nova senha", show="•")
        self.confirm_entry = self._field(card, "Confirmar senha", show="•")
        self.password_entries = [self.password_entry, self.confirm_entry]
        self._show_password_control(card)

        self.error_label = ctk.CTkLabel(
            card,
            text="Use pelo menos 8 caracteres.",
            text_color=COLORS["muted"],
            font=(FONT_FAMILY, 10),
        )
        self.error_label.pack(anchor="w", padx=26, pady=(2, 9))

        self._action_buttons(card, "Salvar senha", self._create_first_admin)

        assert self.window is not None
        self.window.bind("<Return>", lambda _event: self._create_first_admin())
        self.password_entry.focus_set()

    def _build_login(self) -> None:
        card = self._base_card(
            "Entrar no sistema",
            "Informe seu usuário e senha. O conteúdo disponível será definido "
            "pelo seu perfil de acesso.",
        )
        self.username_entry = self._field(card, "Usuário")
        self.password_entry = self._field(card, "Senha", show="•")
        self.password_entries = [self.password_entry]
        self._show_password_control(card)

        self.error_label = ctk.CTkLabel(
            card,
            text="",
            text_color=COLORS["danger"],
            font=(FONT_FAMILY, 10, "bold"),
        )
        self.error_label.pack(anchor="w", padx=26, pady=(2, 9))

        self._action_buttons(card, "Entrar", self._login)

        assert self.window is not None
        self.window.bind("<Return>", lambda _event: self._login())
        self.username_entry.focus_set()

    def _action_buttons(self, parent, primary_text: str, primary_command) -> None:
        """Exibe sempre as ações de continuar ou fechar o programa."""
        buttons = ctk.CTkFrame(parent, fg_color="transparent")
        buttons.pack(fill="x", padx=26, pady=(0, 22))
        buttons.grid_columnconfigure(0, weight=1)
        buttons.grid_columnconfigure(1, weight=1)

        ctk.CTkButton(
            buttons,
            text="Fechar programa",
            command=self._cancel,
            height=40,
            fg_color="#FFFFFF",
            hover_color="#FFF1F1",
            border_color=COLORS["danger"],
            border_width=1,
            text_color=COLORS["danger"],
            font=(FONT_FAMILY, 11, "bold"),
        ).grid(row=0, column=0, sticky="ew", padx=(0, 5))
        ctk.CTkButton(
            buttons,
            text=primary_text,
            command=primary_command,
            height=40,
            fg_color=COLORS["primary"],
            hover_color=COLORS["primary_dark"],
            font=(FONT_FAMILY, 12, "bold"),
        ).grid(row=0, column=1, sticky="ew", padx=(5, 0))

    def _show_password_control(self, parent) -> None:
        self.show_password_var = tk.BooleanVar(value=False)
        ctk.CTkCheckBox(
            parent,
            text="Mostrar senha",
            variable=self.show_password_var,
            command=self._toggle_password,
            checkbox_width=17,
            checkbox_height=17,
            font=(FONT_FAMILY, 10),
            text_color=COLORS["muted"],
        ).pack(anchor="w", padx=26, pady=(0, 3))

    def _toggle_password(self) -> None:
        show = "" if self.show_password_var.get() else "•"
        for entry in self.password_entries:
            entry.configure(show=show)

    def _create_first_admin(self) -> None:
        try:
            self.result = self.auth_service.bootstrap_admin(
                self.password_entry.get(),
                self.confirm_entry.get(),
            )
            self.logger.info("Primeiro administrador configurado")
            assert self.window is not None
            self.window.destroy()
        except AuthenticationError as error:
            self.error_label.configure(text=str(error), text_color=COLORS["danger"])
            self.password_entry.focus_set()

    def _login(self) -> None:
        try:
            self.result = self.auth_service.authenticate(
                self.username_entry.get(), self.password_entry.get()
            )
            self.logger.info("Login autorizado para o usuário id=%s", self.result.user_id)
            assert self.window is not None
            self.window.destroy()
        except InvalidCredentialsError as error:
            self.error_label.configure(text=str(error))
            self.password_entry.delete(0, tk.END)
            self.password_entry.focus_set()
        except AuthenticationError as error:
            self.error_label.configure(text=str(error))

    def _cancel(self) -> None:
        self.result = None
        if self.window is not None:
            self.window.destroy()
