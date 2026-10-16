"""Ponto de entrada da aplicação gráfica Sistema SIA."""

from __future__ import annotations

import logging
import os
import sys
import tkinter as tk
from tkinter import messagebox

from sia_app.config.settings import AppSettings
from sia_app.database.connection import DatabaseConnection
from sia_app.paths import get_runtime_paths
from sia_app.services.auth_service import (
    AuthService,
    ROLE_ADMIN,
    ROLE_VIEWER,
    UserSession,
)
from sia_app.ui.auth_dialog import AuthDialog
from sia_app.utils.logger import setup_logger


class SIASystem:
    """Compõe configurações, banco e interface sem alterar ``sys.path``."""

    def __init__(self) -> None:
        self.paths = get_runtime_paths()
        self.paths.ensure_directories()
        self.logger = setup_logger("SIASystem", log_dir=str(self.paths.logs))
        self.settings = AppSettings(self.paths.config)
        self.db = DatabaseConnection(self.paths.database)
        self.auth_service = AuthService(self.db)
        self.root: tk.Tk | None = None
        self.main_window: MainWindow | None = None
        self._logout_requested = False
        self._destroying_root = False

    def initialize(self) -> None:
        self.db.initialize_database()
        self.logger.info("Sistema SIA inicializado com sucesso")

    def run(self) -> None:
        self.initialize()
        while True:
            self._logout_requested = False
            self._destroying_root = False
            self.root = tk.Tk()
            self.root.withdraw()
            self.root.protocol("WM_DELETE_WINDOW", self.close)

            session = AuthDialog(
                self.root, self.auth_service, self.logger
            ).show()
            if session is None:
                self._destroy_current_root()
                return

            from sia_app.ui.main_window import MainWindow

            self.main_window = MainWindow(
                self.root,
                self.db,
                self.settings,
                self.logger,
                self.auth_service,
                session,
                self.logout,
            )
            self.root.deiconify()
            self.logger.info("Interface gráfica inicializada")
            self.root.mainloop()
            if not self._logout_requested:
                return

    def close(self) -> None:
        self.logger.info("Aplicação encerrada pelo usuário")
        self._logout_requested = False
        self._destroy_current_root()

    def logout(self) -> None:
        """Fecha a janela atual e reinicia o ciclo na tela de login."""
        self.logger.info("Sessão encerrada pelo usuário")
        self._logout_requested = True
        self._destroy_current_root()

    def _destroy_current_root(self) -> None:
        """Encerra widgets e callbacks antes de destruir o interpretador Tcl."""
        root = self.root
        if root is None or self._destroying_root:
            return

        self._destroying_root = True
        try:
            if self.main_window is not None:
                self.main_window.shutdown()
            self._cancel_pending_tk_callbacks(root)
            try:
                root.quit()
            except tk.TclError:
                pass
            try:
                root.destroy()
            except tk.TclError:
                pass
        finally:
            self.main_window = None
            self.root = None
            self._destroying_root = False

    @staticmethod
    def _cancel_pending_tk_callbacks(root: tk.Misc) -> None:
        """Cancela todos os ``after`` ainda registrados no interpretador Tk."""
        try:
            callback_ids = root.tk.call("after", "info")
        except tk.TclError:
            return

        if isinstance(callback_ids, str):
            callback_ids = (callback_ids,)
        for callback_id in callback_ids:
            try:
                root.tk.call("after", "cancel", callback_id)
            except tk.TclError:
                pass


def _show_fatal_error(error: Exception) -> None:
    try:
        messagebox.showerror(
            "Falha na inicialização",
            "Não foi possível iniciar o Sistema SIA.\n\n"
            f"Detalhes: {error}\n\n"
            "Consulte o arquivo de log na pasta data/logs.",
        )
    except tk.TclError:
        print(f"Falha na inicialização: {error}", file=sys.stderr)


def run_self_test() -> int:
    """Valida caminhos, banco e imports sem abrir a interface."""
    try:
        paths = get_runtime_paths()
        paths.ensure_directories()
        db = DatabaseConnection(paths.database)
        db.initialize_database()
        with db.read() as cursor:
            integrity = cursor.execute("PRAGMA integrity_check").fetchone()[0]
            version = cursor.execute("PRAGMA user_version").fetchone()[0]
            pa_count = cursor.execute("SELECT COUNT(*) FROM tb_pa").fetchone()[0]
        if integrity != "ok":
            raise RuntimeError(f"Integridade SQLite inválida: {integrity}")
        if int(version) < 4:
            raise RuntimeError(f"Versão do banco inesperada: {version}")
        with db.read() as cursor:
            user_table = cursor.execute(
                "SELECT 1 FROM sqlite_master WHERE type='table' AND name='tb_usuario'"
            ).fetchone()
        if user_table is None:
            raise RuntimeError("Tabela de usuários não foi criada")
        if os.getenv("SIA_REQUIRE_SEED_DATA") == "1":
            if not paths.config.is_file():
                raise RuntimeError("Configuração inicial não incorporada ao executável")
            if int(pa_count) == 0:
                raise RuntimeError("Banco inicial não incorporado ao executável")
        return 0
    except Exception as error:
        print(f"SELF_TEST_FAILED: {error}", file=sys.stderr)
        return 1


def run_ui_smoke_test() -> int:
    """Cria e percorre todas as telas; usado pelo build no Windows."""
    root = None
    try:
        system = SIASystem()
        system.initialize()
        # O teste não deve abrir uma caixa modal quando usa um diretório
        # temporário ainda sem configuração do usuário.
        system.settings.set("logo_path", "__ui_smoke_test__")
        root = tk.Tk()
        root.geometry("1200x760+0+0")
        root.update_idletasks()
        from sia_app.ui.main_window import MainWindow

        main_window = MainWindow(
            root,
            system.db,
            system.settings,
            system.logger,
            system.auth_service,
            UserSession(0, "Teste de Interface", "smoke-test", ROLE_ADMIN),
        )
        expected_admin_tabs = (
            "dashboard",
            "file_upload",
            "filters",
            "reports",
            "establishments",
            "prd_editor",
            "database",
            "config",
        )
        for key in expected_admin_tabs:
            if not main_window.navigate_to_tab(key):
                raise RuntimeError(f"Falha ao carregar a tela administrativa: {key}")
            root.update_idletasks()
        dashboard = main_window.tabs["dashboard"]
        expected_chart_tabs = {
            "grupos",
            "estab",
            "meses",
            "diferencas",
            "cbo",
            "fin_comp",
            "fin_estab",
        }
        if set(dashboard.chart_frames) != expected_chart_tabs:
            raise RuntimeError("Abas comparativas do Dashboard não carregadas")
        dashboard.atualizar_dashboard()
        for chart_key in expected_chart_tabs:
            dashboard._select_chart_tab(chart_key)
            root.update_idletasks()
        for key in expected_admin_tabs:
            if not main_window.navigate_to_tab(key):
                raise RuntimeError(f"Falha ao navegar para a tela: {key}")
            root.update_idletasks()
            root.update()

        main_window.shutdown()
        for child in root.winfo_children():
            child.destroy()

        viewer_window = MainWindow(
            root,
            system.db,
            system.settings,
            system.logger,
            system.auth_service,
            UserSession(0, "Visualizador de Teste", "viewer-smoke", ROLE_VIEWER),
        )
        expected_viewer_tabs = {"dashboard", "filters", "reports"}
        for key in expected_viewer_tabs:
            if not viewer_window.navigate_to_tab(key):
                raise RuntimeError(f"Visualizador não acessou a tela permitida: {key}")
            root.update_idletasks()
            root.update()
        if set(viewer_window.tabs) != expected_viewer_tabs:
            raise RuntimeError(
                "Telas incorretas para visualizador: "
                + ", ".join(sorted(viewer_window.tabs))
            )
        for key in set(expected_admin_tabs) - expected_viewer_tabs:
            if viewer_window.navigate_to_tab(key):
                raise RuntimeError(f"Visualizador acessou tela administrativa: {key}")
        return 0
    except Exception as error:
        print(f"UI_SMOKE_TEST_FAILED: {error}", file=sys.stderr)
        return 1
    finally:
        if root is not None:
            try:
                SIASystem._cancel_pending_tk_callbacks(root)
                root.destroy()
            except tk.TclError:
                pass


def main() -> int:
    if "--self-test" in sys.argv:
        return run_self_test()
    if "--ui-smoke-test" in sys.argv:
        return run_ui_smoke_test()
    if sys.platform != "win32" and not os.getenv("DISPLAY"):
        print("Erro: ambiente gráfico não disponível", file=sys.stderr)
        return 1

    try:
        SIASystem().run()
        return 0
    except KeyboardInterrupt:
        return 0
    except Exception as error:
        logging.getLogger("SIASystem").critical(
            "Erro inesperado na aplicação", exc_info=True
        )
        _show_fatal_error(error)
        return 1
