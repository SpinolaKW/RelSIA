"""Regressão funcional das telas; requer uma sessão gráfica ou DISPLAY de testes."""

import logging
import os
from pathlib import Path
import sys
import tempfile
import tkinter as tk
import unittest

from sia_app.app import SIASystem
from sia_app.config.settings import AppSettings
from sia_app.database.connection import DatabaseConnection
from sia_app.services.auth_service import AuthService, ROLE_ADMIN, UserSession
from sia_app.ui.auth_dialog import AuthDialog
from sia_app.ui.main_window import MainWindow


@unittest.skipUnless(sys.platform == "win32" or os.getenv("DISPLAY"), "Sessão gráfica indisponível")
class InterfaceRegressionTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory(prefix="relsia-ui-test-")
        self.path = Path(self.directory.name)
        self.db = DatabaseConnection(self.path / "test.db")
        self.db.initialize_database()
        self.settings = AppSettings(self.path / "config.json")
        self.settings.set("logo_path", "__ui_test__")
        self.auth = AuthService(self.db)
        self.root = tk.Tk()
        self.window = None
        self.callback_errors = []
        self.root.report_callback_exception = lambda kind, error, tb: self.callback_errors.append(error)

    def tearDown(self):
        if self.window:
            self.window.shutdown()
        SIASystem._cancel_pending_tk_callbacks(self.root)
        self.root.destroy()
        self.directory.cleanup()
        self.assertEqual(self.callback_errors, [], "Falha em callback da interface")

    def open_main(self):
        self.window = MainWindow(self.root, self.db, self.settings, logging.getLogger("ui-test"),
                                 self.auth, UserSession(0, "Teste Visual", "test", ROLE_ADMIN))
        self.root.update()
        return self.window

    def test_filters_change_the_displayed_production(self):
        with self.db.txn() as cursor:
            cursor.execute("INSERT INTO tb_pa (PA_ID, PA_DV, PA_DC, PA_TOTAL) VALUES ('030101001', '1', 'Consulta', 10)")
            cursor.executemany(
                "INSERT INTO tb_prd (PRD_UID, PRD_CMP, PRD_PA, PRD_QT_P, PRD_QT_A) VALUES ('1000001', ?, '0301010011', ?, ?)",
                [("202601", 5, 4), ("202602", 7, 6)],
            )
        dashboard = self.open_main().tabs["dashboard"]
        self.assertEqual(dashboard.card_vars["qtd_produzida"].get(), "12")
        dashboard._toggle_filters()
        self.root.update()
        self.assertTrue(dashboard.filters_body.winfo_ismapped())
        dashboard.competencia_inicio_var.set("202601")
        dashboard.competencia_fim_var.set("202601")
        dashboard.atualizar_dashboard()
        self.assertEqual(dashboard.card_vars["qtd_produzida"].get(), "5")
        self.assertEqual(dashboard.card_vars["valor_produzido"].get(), "R$ 50,00")
        dashboard.limpar_filtros()
        dashboard.atualizar_dashboard()
        self.assertEqual(dashboard.card_vars["qtd_produzida"].get(), "12")

    def test_navigation_survives_compact_and_expanded_windows(self):
        window = self.open_main()
        for width, compact in ((1440, False), (1000, True), (1440, False)):
            self.root.geometry(f"{width}x800")
            self.root.update()
            self.assertEqual(window._compact_sidebar, compact)
            self.assertTrue(window.navigate_to_tab("filters"))
            self.root.update()
            self.assertEqual(window.get_current_tab(), "filters")
            self.assertTrue(window.navigate_to_tab("dashboard"))
            self.root.update()

    def test_login_reports_invalid_password_then_authenticates(self):
        self.auth.bootstrap_admin("Senha de teste 2026", "Senha de teste 2026")
        dialog = AuthDialog(self.root, self.auth, logging.getLogger("ui-test"))

        def submit():
            try:
                dialog.username_entry.insert(0, "admin")
                dialog.password_entry.insert(0, "senha incorreta")
                dialog._login()
                self.assertIsNone(dialog.result)
                self.assertTrue(dialog.error_label.cget("text"))
                dialog.password_entry.insert(0, "Senha de teste 2026")
                dialog._login()
            except Exception as error:
                self.callback_errors.append(error)
                dialog._cancel()

        self.root.after(100, submit)
        session = dialog.show()
        self.assertIsNotNone(session)
        self.assertTrue(session.is_admin)

    def test_first_access_creates_the_administrator(self):
        self.root.withdraw()
        dialog = AuthDialog(self.root, self.auth, logging.getLogger("ui-test"))

        def submit():
            try:
                self.assertTrue(dialog.window.winfo_viewable(), "Login oculto com a janela principal retirada")
                dialog.password_entry.insert(0, "Senha inicial 2026")
                dialog.confirm_entry.insert(0, "Senha inicial 2026")
                dialog._create_first_admin()
            except Exception as error:
                self.callback_errors.append(error)
                dialog._cancel()

        self.root.after(100, submit)
        session = dialog.show()
        self.assertIsNotNone(session)
        self.assertTrue(self.auth.has_users())


if __name__ == "__main__":
    unittest.main()
