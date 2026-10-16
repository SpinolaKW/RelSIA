"""Componente de gerenciamento de usuários com alterações em espera."""

from __future__ import annotations

import logging
import tkinter as tk
from tkinter import messagebox, ttk
from typing import Any, Callable

import customtkinter as ctk

from sia_app.services.auth_service import (
    ROLE_ADMIN,
    ROLE_LABELS,
    ROLE_VIEWER,
    AuthService,
    AuthenticationError,
    UserSession,
)


from sia_app.ui.theme import COLORS, apply_theme, FONT_FAMILY


class UserEditorDialog:
    """Formulário modal para criar ou preparar a alteração de uma conta."""

    def __init__(
        self,
        parent,
        auth_service: AuthService,
        initial: dict[str, Any] | None = None,
        *,
        is_current_user: bool = False,
    ) -> None:
        self.parent = parent
        self.auth_service = auth_service
        self.initial = initial or {}
        self.is_current_user = is_current_user
        self.result: dict[str, Any] | None = None
        self.password_entries: list[ctk.CTkEntry] = []

    def show(self) -> dict[str, Any] | None:
        editing = bool(self.initial)
        self.window = ctk.CTkToplevel(self.parent.winfo_toplevel())
        self.window.title("Alterar usuário" if editing else "Novo usuário")
        self.window.geometry("540x650")
        self.window.minsize(520, 560)
        self.window.resizable(False, True)
        self.window.configure(fg_color="#F5F7FB")
        self.window.transient(self.parent.winfo_toplevel())
        self.window.protocol("WM_DELETE_WINDOW", self._cancel)

        card = ctk.CTkFrame(
            self.window,
            fg_color=COLORS["card"],
            border_color=COLORS["border"],
            border_width=1,
            corner_radius=12,
        )
        card.pack(fill="both", expand=True, padx=26, pady=24)
        card.grid_columnconfigure(0, weight=1)
        card.grid_rowconfigure(0, weight=1)

        form = ctk.CTkScrollableFrame(
            card,
            fg_color="transparent",
            corner_radius=0,
            scrollbar_button_color=COLORS["border"],
            scrollbar_button_hover_color=COLORS["muted"],
        )
        form.grid(row=0, column=0, sticky="nsew", padx=(0, 4))

        ctk.CTkLabel(
            form,
            text="Alterar usuário" if editing else "Cadastrar novo usuário",
            font=(FONT_FAMILY, 19, "bold"),
            text_color=COLORS["text"],
        ).pack(anchor="w", padx=24, pady=(20, 3))
        ctk.CTkLabel(
            form,
            text=(
                "A senha só será substituída se uma nova senha for informada."
                if editing
                else "Defina os dados e a senha inicial da nova conta."
            ),
            font=(FONT_FAMILY, 10),
            text_color=COLORS["muted"],
        ).pack(anchor="w", padx=24, pady=(0, 16))

        self.name_entry = self._entry(form, "Nome")
        self.username_entry = self._entry(form, "Usuário (sem espaços)")

        ctk.CTkLabel(
            form,
            text="Perfil de acesso",
            font=(FONT_FAMILY, 11, "bold"),
            text_color=COLORS["text"],
        ).pack(anchor="w", padx=24, pady=(0, 5))
        role_label = ROLE_LABELS.get(
            str(self.initial.get("role", ROLE_VIEWER)), "Visualizador"
        )
        self.role_menu = ctk.CTkOptionMenu(
            form,
            values=["Administrador", "Visualizador"],
            height=36,
            fg_color="#FFFFFF",
            button_color=COLORS["primary"],
            button_hover_color=COLORS["primary_dark"],
            text_color=COLORS["text"],
            dropdown_fg_color="#FFFFFF",
            dropdown_text_color=COLORS["text"],
        )
        self.role_menu.set(role_label)
        self.role_menu.pack(fill="x", padx=24, pady=(0, 13))

        self.active_var = tk.BooleanVar(value=bool(self.initial.get("active", True)))
        self.active_checkbox = ctk.CTkCheckBox(
            form,
            text="Usuário ativo",
            variable=self.active_var,
            font=(FONT_FAMILY, 11),
            text_color=COLORS["text"],
            checkbox_width=18,
            checkbox_height=18,
        )
        self.active_checkbox.pack(anchor="w", padx=24, pady=(0, 15))

        password_label = "Nova senha (opcional)" if editing else "Senha"
        self.password_entry = self._entry(form, password_label, show="•")
        self.confirm_entry = self._entry(form, "Confirmar senha", show="•")
        self.password_entries = [self.password_entry, self.confirm_entry]

        self.show_password_var = tk.BooleanVar(value=False)
        ctk.CTkCheckBox(
            form,
            text="Mostrar senha",
            variable=self.show_password_var,
            command=self._toggle_password,
            checkbox_width=17,
            checkbox_height=17,
            font=(FONT_FAMILY, 10),
            text_color=COLORS["muted"],
        ).pack(anchor="w", padx=24, pady=(0, 5))

        self.error_label = ctk.CTkLabel(
            form,
            text="",
            font=(FONT_FAMILY, 10, "bold"),
            text_color=COLORS["danger"],
            wraplength=410,
            justify="left",
        )
        self.error_label.pack(anchor="w", padx=24, pady=(0, 7))

        buttons = ctk.CTkFrame(card, fg_color="transparent")
        buttons.grid(row=1, column=0, sticky="ew", padx=24, pady=(10, 20))
        buttons.grid_columnconfigure(0, weight=1)
        buttons.grid_columnconfigure(1, weight=1)
        ctk.CTkButton(
            buttons,
            text="Cancelar",
            command=self._cancel,
            height=38,
            fg_color="#FFFFFF",
            hover_color=COLORS["primary_soft"],
            border_color=COLORS["border"],
            border_width=1,
            text_color=COLORS["text"],
        ).grid(row=0, column=0, sticky="ew", padx=(0, 5))
        action_text = "Alterar" if editing else "Adicionar"
        ctk.CTkButton(
            buttons,
            text=action_text,
            command=self._accept,
            height=38,
            fg_color=COLORS["primary"],
            hover_color=COLORS["primary_dark"],
            font=(FONT_FAMILY, 11, "bold"),
        ).grid(row=0, column=1, sticky="ew", padx=(5, 0))

        if editing:
            self.name_entry.insert(0, str(self.initial.get("name", "")))
            self.username_entry.insert(0, str(self.initial.get("username", "")))
        if self.is_current_user:
            self.username_entry.configure(state="disabled")
            self.role_menu.configure(state="disabled")
            self.active_checkbox.configure(state="disabled")

        self.window.bind("<Return>", lambda _event: self._accept())
        self.window.bind("<Escape>", lambda _event: self._cancel())
        self.name_entry.focus_set()
        self.window.grab_set()
        self.window.wait_window()
        return self.result

    @staticmethod
    def _entry(parent, label: str, *, show: str = "") -> ctk.CTkEntry:
        ctk.CTkLabel(
            parent,
            text=label,
            font=(FONT_FAMILY, 11, "bold"),
            text_color=COLORS["text"],
        ).pack(anchor="w", padx=24, pady=(0, 5))
        entry = ctk.CTkEntry(
            parent,
            height=36,
            corner_radius=7,
            border_color=COLORS["border"],
            fg_color="#FFFFFF",
            text_color=COLORS["text"],
            font=(FONT_FAMILY, 11),
            show=show,
        )
        entry.pack(fill="x", padx=24, pady=(0, 12))
        return entry

    def _toggle_password(self) -> None:
        show = "" if self.show_password_var.get() else "•"
        for entry in self.password_entries:
            entry.configure(show=show)

    def _accept(self) -> None:
        try:
            name = self.auth_service.validate_name(self.name_entry.get())
            username = self.auth_service.validate_username(self.username_entry.get())
            password = self.password_entry.get()
            confirmation = self.confirm_entry.get()
            if password != confirmation:
                raise AuthenticationError("A senha e a confirmação não são iguais.")
            if not self.initial and not password:
                raise AuthenticationError("Informe a senha inicial do usuário.")
            if password:
                self.auth_service.validate_password(password)

            role = (
                ROLE_ADMIN if self.role_menu.get() == "Administrador" else ROLE_VIEWER
            )
            self.result = {
                "id": self.initial.get("id"),
                "name": name,
                "username": username,
                "role": role,
                "active": bool(self.active_var.get()),
                "password": password,
            }
            self.window.destroy()
        except AuthenticationError as error:
            self.error_label.configure(text=str(error))

    def _cancel(self) -> None:
        self.result = None
        if self.window.winfo_exists():
            self.window.destroy()


class UserManagementPanel:
    """Lista contas e só persiste mudanças no save geral de Configurações."""

    def __init__(
        self,
        parent,
        auth_service: AuthService,
        session: UserSession,
        logger: logging.Logger,
        on_session_changed: Callable[[UserSession], None] | None = None,
    ) -> None:
        self.parent = parent
        self.auth_service = auth_service
        self.session = session
        self.logger = logger
        self.on_session_changed = on_session_changed
        self._drafts: dict[str, dict[str, Any]] = {}
        self._deleted_ids: set[int] = set()
        self._new_counter = 0
        self._build()
        self.reload_from_database()

    def _build(self) -> None:
        self.frame = ctk.CTkFrame(
            self.parent,
            fg_color=COLORS["card"],
            border_color=COLORS["border"],
            border_width=1,
            corner_radius=12,
        )
        self.frame.pack(fill="x", padx=18, pady=(8, 14))

        header = ctk.CTkFrame(self.frame, fg_color="transparent")
        header.pack(fill="x", padx=18, pady=(14, 8))
        titles = ctk.CTkFrame(header, fg_color="transparent")
        titles.pack(side="left", fill="x", expand=True)
        ctk.CTkLabel(
            titles,
            text="Usuários e Permissões",
            font=(FONT_FAMILY, 13, "bold"),
            text_color=COLORS["text"],
        ).pack(anchor="w")
        ctk.CTkLabel(
            titles,
            text=(
                "Administrador: acesso total. Visualizador: Dashboard, Filtros e Relatórios."
            ),
            font=(FONT_FAMILY, 10),
            text_color=COLORS["muted"],
        ).pack(anchor="w", pady=(2, 0))

        actions = ctk.CTkFrame(header, fg_color="transparent")
        actions.pack(side="right")
        self._action_button(actions, "Novo", self._new_user, COLORS["primary"]).pack(
            side="left", padx=(0, 6)
        )
        self._action_button(actions, "Alterar", self._edit_user, "#FFFFFF").pack(
            side="left", padx=(0, 6)
        )
        self._action_button(actions, "Excluir", self._delete_user, "#FFFFFF", danger=True).pack(
            side="left"
        )

        table_frame = tk.Frame(self.frame, bg="#FFFFFF", height=180)
        table_frame.pack(fill="x", padx=18, pady=(4, 8))
        table_frame.pack_propagate(False)
        columns = ("name", "username", "role", "status", "last_login")
        self.tree = ttk.Treeview(table_frame, columns=columns, show="headings", height=6)
        headings = {
            "name": "Nome",
            "username": "Usuário",
            "role": "Perfil",
            "status": "Situação",
            "last_login": "Último acesso",
        }
        widths = {"name": 220, "username": 150, "role": 125, "status": 90, "last_login": 150}
        for column in columns:
            self.tree.heading(column, text=headings[column])
            self.tree.column(column, width=widths[column], minwidth=80, anchor="w")
        scrollbar = ttk.Scrollbar(table_frame, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=scrollbar.set)
        self.tree.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        self.tree.bind("<Double-1>", lambda _event: self._edit_user())

        footer = ctk.CTkFrame(self.frame, fg_color="transparent")
        footer.pack(fill="x", padx=18, pady=(0, 14))
        self.pending_label = ctk.CTkLabel(
            footer,
            text="Nenhuma alteração pendente.",
            font=(FONT_FAMILY, 10),
            text_color=COLORS["muted"],
        )
        self.pending_label.pack(side="left")
        ctk.CTkButton(
            footer,
            text="Cancelar alterações de usuários",
            command=self._cancel_pending,
            height=28,
            fg_color="transparent",
            hover_color=COLORS["primary_soft"],
            text_color=COLORS["primary"],
            font=(FONT_FAMILY, 10, "bold"),
            width=205,
        ).pack(side="right")

    @staticmethod
    def _action_button(parent, text, command, color, danger: bool = False):
        outlined = color == "#FFFFFF"
        return ctk.CTkButton(
            parent,
            text=text,
            command=command,
            width=82,
            height=32,
            corner_radius=7,
            fg_color=color,
            hover_color="#FFF1F1" if danger else COLORS["primary_soft"],
            border_color=COLORS["danger"] if danger else COLORS["border"],
            border_width=1 if outlined else 0,
            text_color=COLORS["danger"] if danger else (COLORS["text"] if outlined else "#FFFFFF"),
            font=(FONT_FAMILY, 10, "bold"),
        )

    def reload_from_database(self) -> None:
        self._drafts.clear()
        self._deleted_ids.clear()
        for record in self.auth_service.list_users():
            key = f"db:{record.id}"
            self._drafts[key] = {
                "id": record.id,
                "name": record.name,
                "username": record.username,
                "role": record.role,
                "active": record.active,
                "password": "",
                "last_login": record.last_login,
            }
        self._refresh_tree()
        self._set_pending(False)

    def _refresh_tree(self, selected_key: str | None = None) -> None:
        selection = self.tree.selection()
        for item in self.tree.get_children():
            self.tree.delete(item)
        for key, draft in self._drafts.items():
            last_login = str(draft.get("last_login") or "Nunca")
            if last_login not in {"Nunca", ""}:
                last_login = last_login.replace("T", " ")[:16]
            self.tree.insert(
                "",
                "end",
                iid=key,
                values=(
                    draft["name"],
                    draft["username"],
                    ROLE_LABELS.get(draft["role"], draft["role"]),
                    "Ativo" if draft["active"] else "Inativo",
                    last_login,
                ),
            )
        target = selected_key or (str(selection[0]) if selection else None)
        if target and self.tree.exists(target):
            self.tree.selection_set(target)
            self.tree.focus(target)
            self.tree.see(target)

    def _selected_key(self) -> str | None:
        selected = self.tree.selection()
        if not selected:
            messagebox.showwarning("Seleção necessária", "Selecione um usuário na lista.")
            return None
        return str(selected[0])

    def _new_user(self) -> None:
        result = UserEditorDialog(self.frame, self.auth_service).show()
        if result is None:
            return
        self._new_counter += 1
        key = f"new:{self._new_counter}"
        self._drafts[key] = result
        self._refresh_tree(key)
        self._set_pending(True)

    def _edit_user(self) -> None:
        key = self._selected_key()
        if key is None:
            return
        draft = self._drafts[key]
        result = UserEditorDialog(
            self.frame,
            self.auth_service,
            draft,
            is_current_user=draft.get("id") == self.session.user_id,
        ).show()
        if result is None:
            return
        result["last_login"] = draft.get("last_login")
        self._drafts[key] = result
        self._refresh_tree(key)
        self._set_pending(True)

    def _delete_user(self) -> None:
        key = self._selected_key()
        if key is None:
            return
        draft = self._drafts[key]
        if draft.get("id") == self.session.user_id:
            messagebox.showwarning(
                "Operação não permitida", "O usuário conectado não pode ser excluído."
            )
            return
        if not messagebox.askyesno(
            "Excluir usuário",
            f"Marcar o usuário “{draft['username']}” para exclusão?\n\n"
            "A exclusão só acontecerá ao clicar em Salvar Configurações.",
        ):
            return
        if draft.get("id") is not None:
            self._deleted_ids.add(int(draft["id"]))
        del self._drafts[key]
        self._refresh_tree()
        self._set_pending(True)

    def _cancel_pending(self) -> None:
        if not self.has_pending_changes():
            return
        if messagebox.askyesno(
            "Cancelar alterações",
            "Descartar as alterações de usuários que ainda não foram salvas?",
        ):
            self.reload_from_database()

    def _set_pending(self, pending: bool) -> None:
        self.pending_label.configure(
            text=(
                "Alterações pendentes — clique em Salvar Configurações."
                if pending
                else "Nenhuma alteração pendente."
            ),
            text_color=COLORS["warning"] if pending else COLORS["muted"],
        )
        self._pending = pending

    def has_pending_changes(self) -> bool:
        return bool(getattr(self, "_pending", False))

    def _changes(self) -> tuple[list[dict[str, Any]], set[int]]:
        return list(self._drafts.values()), set(self._deleted_ids)

    def validate_pending_changes(self) -> None:
        drafts, deleted = self._changes()
        self.auth_service.validate_user_changes(drafts, deleted, self.session)

    def save_pending_changes(self) -> UserSession:
        drafts, deleted = self._changes()
        updated_session = self.auth_service.save_user_changes(
            drafts, deleted, self.session
        )
        self.session.name = updated_session.name
        self.session.username = updated_session.username
        self.session.role = updated_session.role
        self.reload_from_database()
        if self.on_session_changed is not None:
            self.on_session_changed(self.session)
        self.logger.info("Alterações de usuários salvas")
        return self.session
