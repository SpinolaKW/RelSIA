from __future__ import annotations

import ast
import logging
import sqlite3
import tempfile
import unittest
from decimal import Decimal
from pathlib import Path
from unittest.mock import MagicMock

import pandas as pd
from matplotlib.backends.backend_agg import FigureCanvasAgg
from matplotlib.figure import Figure
from matplotlib.text import Text
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.units import cm
from reportlab.platypus import SimpleDocTemplate

from sia_app.config.settings import AppSettings
from sia_app.database.backup_manager import BackupManager
from sia_app.database.connection import DatabaseConnection
from sia_app.database.models import ConfigModel, EstabelecimentoModel
from sia_app.database.operations import DatabaseOperations
from sia_app.file_processing.csv_importer import CSVImporter
from sia_app.reports.csv_exporter import exportar_csv_agregado
from sia_app.reports.data_processor import DataProcessor
from sia_app.reports.pdf_generator import PDFGenerator
from sia_app.reports.query_builder import QueryBuilder
from sia_app.services.dashboard_service import (
    DashboardComparison,
    DashboardService,
)
from sia_app.services.dashboard_image_exporter import DashboardImageExporter
from sia_app.services.data_view_service import DataViewService
from sia_app.services.establishment_service import EstablishmentService
from sia_app.services.file_import_service import FileImportService
from sia_app.services.filter_service import FilterService
from sia_app.services.prd_editor_service import PrdEditorService
from sia_app.services.report_service import ReportService
from sia_app.ui.components.dashboard_charts import DashboardChartRenderer
from sia_app.services.auth_service import (
    ROLE_ADMIN,
    ROLE_VIEWER,
    AuthService,
    AuthenticationError,
    InvalidCredentialsError,
)


LOGGER = logging.getLogger("sia-tests")
LOGGER.addHandler(logging.NullHandler())


class CoreRegressionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory(prefix="sia_test_")
        self.root = Path(self.temp_dir.name)
        self.db = DatabaseConnection(self.root / "sistema_sia.db")
        self.db.initialize_database()

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_data_viewer_totals_use_readable_font_sizes(self) -> None:
        source_path = (
            Path(__file__).parents[1]
            / "src"
            / "sia_app"
            / "ui"
            / "components"
            / "data_viewer.py"
        )
        syntax_tree = ast.parse(source_path.read_text(encoding="utf-8"))
        assignments = {
            node.targets[0].id: ast.literal_eval(node.value)
            for node in syntax_tree.body
            if isinstance(node, ast.Assign)
            and len(node.targets) == 1
            and isinstance(node.targets[0], ast.Name)
            and node.targets[0].id.startswith("DATA_VIEWER_TOTALS_")
        }

        title_font = assignments["DATA_VIEWER_TOTALS_TITLE_FONT"]
        text_font = assignments["DATA_VIEWER_TOTALS_TEXT_FONT"]
        self.assertEqual(title_font, ("Segoe UI", 16, "bold"))
        self.assertEqual(text_font, ("Segoe UI", 13, "bold"))
        self.assertGreater(
            title_font[1],
            text_font[1],
        )

    def test_login_and_user_editor_have_explicit_actions(self) -> None:
        ui_root = Path(__file__).parents[1] / "src" / "sia_app" / "ui"
        auth_source = (ui_root / "auth_dialog.py").read_text(encoding="utf-8")
        users_source = (
            ui_root / "components" / "user_management.py"
        ).read_text(encoding="utf-8")

        self.assertIn('text="Fechar programa"', auth_source)
        self.assertIn('self._action_buttons(card, "Salvar senha", self._create_first_admin)', auth_source)
        self.assertIn('self._action_buttons(card, "Entrar", self._login)', auth_source)
        self.assertIn('self.window.bind("<Return>"', auth_source)
        self.assertIn('action_text = "Alterar" if editing else "Adicionar"', users_source)
        self.assertIn('text="Cancelar"', users_source)
        self.assertIn('self.window.bind("<Escape>"', users_source)
        self.assertIn("CTkScrollableFrame", users_source)

    def test_login_dialog_fits_content_before_centering(self) -> None:
        auth_source = (
            Path(__file__).parents[1]
            / "src"
            / "sia_app"
            / "ui"
            / "auth_dialog.py"
        ).read_text(encoding="utf-8")

        self.assertIn("AUTH_DIALOG_LOGIN_MIN_HEIGHT = 560", auth_source)
        self.assertIn("AUTH_DIALOG_FIRST_ACCESS_MIN_HEIGHT = 630", auth_source)
        self.assertIn('self.window.wm_geometry("")', auth_source)
        self.assertIn("self.window.winfo_reqheight()", auth_source)
        self.assertIn("self.window.winfo_reqwidth()", auth_source)
        self.assertNotIn("self._center(500, 470)", auth_source)
        self.assertNotIn("self._center(500, 530)", auth_source)

    def test_installer_detects_supported_python_commands(self) -> None:
        source = (
            Path(__file__).parents[1] / "install.bat"
        ).read_text(encoding="utf-8")

        self.assertIn("where py >nul 2>&1", source)
        self.assertIn("where python >nul 2>&1", source)
        self.assertIn("where python3 >nul 2>&1", source)
        self.assertIn("sys.version_info.major == 3", source)
        self.assertIn("sys.version_info.minor in range(11, 100)", source)
        self.assertIn('%SIA_PYTHON% -m venv ".venv"', source)
        self.assertIn(":python_not_found", source)
        self.assertIn("Add python.exe to PATH", source)
        self.assertNotIn("\npy -3 -m venv .venv", source)

    def test_upload_callbacks_are_cancelled_and_workers_only_use_queues(self) -> None:
        source_path = (
            Path(__file__).parents[1]
            / "src"
            / "sia_app"
            / "ui"
            / "file_upload_tab.py"
        )
        source_text = source_path.read_text(encoding="utf-8")
        self.assertIn("def close(self) -> None:", source_text)
        self.assertIn("after_cancel(self._after_id)", source_text)
        self.assertIn("def shutdown(self) -> None:", source_text)
        self.assertIn("self.frame.after_cancel(self._ui_after_id)", source_text)
        self.assertIn('(\"progress\", (current, total, action))', source_text)
        self.assertIn('(\"finalize\", (success_count, total_files, error))', source_text)
        self.assertNotIn("self.parent.after(0, update)", source_text)
        self.assertNotIn("self.parent.after(0, finalize)", source_text)

    def test_application_cancels_all_pending_tk_callbacks(self) -> None:
        app_source = (
            Path(__file__).parents[1] / "src" / "sia_app" / "app.py"
        ).read_text(encoding="utf-8")
        window_source = (
            Path(__file__).parents[1] / "src" / "sia_app" / "ui" / "main_window.py"
        ).read_text(encoding="utf-8")

        self.assertIn("self.main_window.shutdown()", app_source)
        self.assertIn('root.tk.call("after", "info")', app_source)
        self.assertIn('root.tk.call("after", "cancel", callback_id)', app_source)
        self.assertIn("def shutdown(self) -> None:", window_source)
        self.assertIn('cleanup = getattr(tab_instance, "shutdown", None)', window_source)

    def _seed_service_data(self) -> None:
        with self.db.txn() as cursor:
            cursor.execute(
                "INSERT INTO tb_estabelecimento (CO_CNES, NO_FANTASIA, CO_CEP) VALUES (?, ?, ?)",
                ("1234567", "Unidade Teste", "11700000"),
            )
            cursor.execute(
                """
                INSERT INTO tb_pa (PA_ID, PA_DV, PA_DC, PA_TOTAL, PA_CTF, PA_CPX)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                ("123456789", "0", "Procedimento de teste", 10, "01", "01"),
            )
            cursor.execute(
                """
                INSERT INTO tb_prd (
                    PRD_UID, PRD_CMP, PRD_PA, PRD_CBO, PRD_TPFIN,
                    PRD_CPX, PRD_QT_P, PRD_QT_A, arquivo_origem
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                ("1234567", "202601", "1234567890", "225125", "01", "01", 3, 2, "fixture"),
            )

    def test_first_access_authentication_and_password_storage(self) -> None:
        auth = AuthService(self.db)
        self.assertFalse(auth.has_users())
        with self.assertRaises(AuthenticationError):
            auth.bootstrap_admin("senha-curta", "outra-senha")

        session = auth.bootstrap_admin("Senha segura 2026", "Senha segura 2026")
        self.assertTrue(session.is_admin)
        self.assertEqual(session.username, "admin")
        self.assertTrue(auth.has_users())

        with self.db.read() as cursor:
            stored = cursor.execute(
                "SELECT senha_hash, senha_salt, senha_iteracoes FROM tb_usuario"
            ).fetchone()
        self.assertNotIn("Senha segura 2026", stored["senha_hash"])
        self.assertNotIn("Senha segura 2026", stored["senha_salt"])
        self.assertGreaterEqual(stored["senha_iteracoes"], 100_000)

        authenticated = auth.authenticate("ADMIN", "Senha segura 2026")
        self.assertEqual(authenticated.user_id, session.user_id)
        with self.assertRaises(InvalidCredentialsError):
            auth.authenticate("admin", "senha incorreta")
        with self.assertRaises(InvalidCredentialsError):
            auth.authenticate("conta-inexistente", "senha incorreta")

    def test_user_management_roles_and_safety_rules(self) -> None:
        auth = AuthService(self.db)
        admin = auth.bootstrap_admin("Senha segura 2026", "Senha segura 2026")
        admin_record = auth.list_users()[0]
        admin_draft = {
            "id": admin_record.id,
            "name": admin_record.name,
            "username": admin_record.username,
            "role": ROLE_ADMIN,
            "active": True,
            "password": "",
        }
        admin = auth.save_user_changes(
            [
                admin_draft,
                {
                    "id": None,
                    "name": "Consulta de Relatórios",
                    "username": "consulta",
                    "role": ROLE_VIEWER,
                    "active": True,
                    "password": "Consulta 2026",
                },
            ],
            set(),
            admin,
        )
        viewer = auth.authenticate("consulta", "Consulta 2026")
        self.assertEqual(viewer.role, ROLE_VIEWER)
        self.assertEqual(
            {key for key in ("dashboard", "filters", "reports") if viewer.can_access(key)},
            {"dashboard", "filters", "reports"},
        )
        for forbidden in (
            "file_upload",
            "establishments",
            "prd_editor",
            "database",
            "config",
        ):
            self.assertFalse(viewer.can_access(forbidden))

        viewer_record = next(user for user in auth.list_users() if user.role == ROLE_VIEWER)
        admin = auth.save_user_changes(
            [
                admin_draft,
                {
                    "id": viewer_record.id,
                    "name": "Consulta Atualizada",
                    "username": "consulta2",
                    "role": ROLE_VIEWER,
                    "active": True,
                    "password": "Consulta nova 2026",
                },
            ],
            set(),
            admin,
        )
        with self.assertRaises(InvalidCredentialsError):
            auth.authenticate("consulta", "Consulta 2026")
        viewer = auth.authenticate("consulta2", "Consulta nova 2026")
        self.assertEqual(viewer.name, "Consulta Atualizada")

        with self.assertRaises(AuthenticationError):
            auth.save_user_changes([], {admin.user_id}, admin)

        with self.assertRaises(AuthenticationError):
            auth.save_user_changes(
                [{**admin_draft, "role": ROLE_VIEWER}], set(), admin
            )

        viewer_record = next(user for user in auth.list_users() if user.role == ROLE_VIEWER)
        with self.assertRaises(AuthenticationError):
            auth.save_user_changes(
                [
                    admin_draft,
                    {
                        "id": viewer_record.id,
                        "name": viewer_record.name,
                        "username": "ADMIN",
                        "role": ROLE_VIEWER,
                        "active": True,
                        "password": "",
                    },
                ],
                set(),
                admin,
            )

        auth.save_user_changes([admin_draft], {viewer_record.id}, admin)
        self.assertEqual(len(auth.list_users()), 1)
        with self.assertRaises(InvalidCredentialsError):
            auth.authenticate("consulta2", "Consulta nova 2026")

    def test_dashboard_and_filter_services_keep_aggregates(self) -> None:
        self._seed_service_data()
        dashboard = DashboardService(self.db).carregar(
            {"competencia_inicio": "202601", "competencia_fim": "202601"},
            "Valor Produzido",
            10,
            "CBO Geral",
        )
        self.assertEqual(dashboard.cards["qtd_produzida"], 3)
        self.assertEqual(dashboard.cards["valor_produzido"], 30)
        self.assertEqual(dashboard.competencias, [("202601", 30.0)])
        self.assertEqual(dashboard.cbo, [("CBO 225125", 3.0)])
        self.assertEqual(
            DashboardService(self.db).carregar_cbo(
                {"competencia_inicio": "202601", "competencia_fim": "202601"},
                10,
                "CBO Geral",
            ),
            [("CBO 225125", 3.0)],
        )

        filters = FilterService.build_filters(
            cnes_text="1234567; 7654321.0",
            procedimento="123456",
            competencia_inicio="202601",
            mostrar_produzidos=True,
        )
        self.assertEqual(filters["cnes_list"], ["1234567", "7654321"])
        self.assertEqual(filters["tipo_filtro_proc"], "forma")
        counts = FilterService(self.db).preview_counts(
            {"cnes_list": ["1234567"], "competencia_inicio": "202601"}
        )
        self.assertEqual(counts, {
            "records_count": 1,
            "cnes_count": 1,
            "procedures_count": 1,
            "competence_count": 1,
        })

    def test_dashboard_financing_comparisons_keep_series_and_totals(self) -> None:
        self._seed_service_data()
        with self.db.txn() as cursor:
            cursor.execute(
                "INSERT INTO tb_estabelecimento (CO_CNES, NO_FANTASIA, CO_CEP) VALUES (?, ?, ?)",
                ("7654321", "Segunda Unidade", "11700000"),
            )
            cursor.executemany(
                """
                INSERT INTO tb_prd (
                    PRD_UID, PRD_CMP, PRD_PA, PRD_CBO, PRD_TPFIN,
                    PRD_CPX, PRD_QT_P, PRD_QT_A, arquivo_origem
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    ("1234567", "202602", "1234567890", "225125", "02", "01", 5, 4, "fixture"),
                    ("7654321", "202601", "1234567890", "225125", "01", "01", 2, 2, "fixture"),
                ],
            )

        dashboard = DashboardService(self.db).carregar(
            {},
            "Quantidade Produzida",
            1,
            "CBO Geral",
        )
        by_competence = dashboard.financiamento_competencias
        self.assertEqual(by_competence.categories, ["202601", "202602"])
        self.assertEqual(by_competence.series[:2], [
            "01 - PAB - Piso de Atenção Básica",
            "02 - MAC - Média e Alta Complexidade",
        ])
        self.assertEqual(by_competence.values, [[5.0, 0.0], [0.0, 5.0]])
        self.assertEqual(
            sum(sum(row) for row in by_competence.values),
            dashboard.cards["qtd_produzida"],
        )

        by_establishment = dashboard.financiamento_estabelecimentos
        self.assertEqual(len(by_establishment.categories), 1)
        self.assertIn("Unidade Teste · CNES 1234567", by_establishment.categories)
        self.assertEqual(by_establishment.values, [[3.0, 5.0]])

    def test_dashboard_charts_avoid_label_collisions_and_export_png_jpg(self) -> None:
        colors = {
            "card": "#FFFFFF",
            "primary": "#0B5ED7",
            "orange": "#F97316",
            "text": "#102A56",
            "muted": "#667085",
        }
        renderer = DashboardChartRenderer(colors)
        figure = Figure(figsize=(10, 5), dpi=100, facecolor=colors["card"])
        canvas = FigureCanvasAgg(figure)
        axes = figure.add_subplot(111)
        chart = {"fig": figure, "canvas": canvas, "ax": axes}
        renderer.draw_bar(
            chart,
            [
                ("Estabelecimento com um nome propositalmente muito longo para validar a organização", 7_258_637),
                ("Unidade pequena", 1_252),
                ("Outro estabelecimento com descrição extensa para quebra de linha", 59_081),
            ],
            "Quantidade Produzida por Estabelecimento",
            "Quantidade Produzida",
            is_value=False,
        )
        axes = chart["ax"]
        canvas.draw()
        labels = [
            artist
            for artist in axes.findobj(Text)
            if artist.get_gid() == "value-label"
        ]
        self.assertEqual(len(labels), 3)
        bounds = [label.get_window_extent(canvas.get_renderer()) for label in labels]
        self.assertFalse(any(
            first.overlaps(second)
            for index, first in enumerate(bounds)
            for second in bounds[index + 1:]
        ))

        comparison = DashboardComparison(
            categories=["202601", "202602", "202603"],
            series=[
                "01 - PAB - Piso de Atenção Básica",
                "02 - MAC - Média e Alta Complexidade",
                "04 - Assistência Farmacêutica",
            ],
            values=[
                [2_000_000, 4_000_000, 1_000_000],
                [1_500_000, 3_500_000, 900_000],
                [2_100_000, 3_800_000, 1_200_000],
            ],
        )
        renderer.draw_stacked_bar(
            chart,
            comparison,
            "Financiamento por Competência",
            "Quantidade Produzida",
            is_value=False,
            competence_labels=True,
            legend_at_top=True,
        )
        axes = chart["ax"]
        canvas.draw()
        legend = axes.get_legend()
        self.assertIsNotNone(legend)
        self.assertEqual(legend.get_gid(), "financing-legend-top")
        self.assertEqual(legend.get_title().get_text(), "Legenda — Tipo de financiamento")
        self.assertEqual(len(legend.get_texts()), len(comparison.series))
        total_labels = [
            artist
            for artist in axes.findobj(Text)
            if artist.get_gid() == "total-label"
        ]
        self.assertEqual(len(total_labels), 3)
        total_bounds = [
            label.get_window_extent(canvas.get_renderer())
            for label in total_labels
        ]
        self.assertFalse(any(
            first.overlaps(second)
            for index, first in enumerate(total_bounds)
            for second in total_bounds[index + 1:]
        ))

        evolution = [
            (f"2024{month:02d}", 500_000 + (month % 4) * 35_000)
            for month in range(1, 13)
        ] + [
            (f"2025{month:02d}", 540_000 + (month % 5) * 27_000)
            for month in range(1, 13)
        ]
        renderer.draw_line(
            chart,
            evolution,
            "Evolução Mensal - Quantidade Produzida",
            "Quantidade Produzida",
            is_value=False,
        )
        axes = chart["ax"]
        canvas.draw()
        evolution_labels = [
            artist
            for artist in axes.findobj(Text)
            if artist.get_gid() == "value-label"
        ]
        self.assertEqual(len(evolution_labels), len(evolution))
        evolution_bounds = [
            label.get_window_extent(canvas.get_renderer())
            for label in evolution_labels
        ]
        self.assertFalse(any(
            first.overlaps(second)
            for index, first in enumerate(evolution_bounds)
            for second in evolution_bounds[index + 1:]
        ))

        renderer.draw_bar(
            chart,
            [(f"Linha {index}", index * 1000) for index in range(1, 29)],
            "Gráfico alto sem vazio no cabeçalho",
            "Quantidade",
            is_value=False,
        )
        axes = chart["ax"]
        canvas.draw()
        top_gap_inches = figure.get_figheight() * (1 - figure.subplotpars.top)
        self.assertLessEqual(top_gap_inches, 0.70)
        self.assertEqual(len(figure.axes), 1)

        png_path = DashboardImageExporter.save(figure, self.root / "dashboard.png")
        jpg_path = DashboardImageExporter.save(figure, self.root / "dashboard.jpg")
        self.assertGreater(png_path.stat().st_size, 1_000)
        self.assertGreater(jpg_path.stat().st_size, 1_000)
        self.assertEqual(png_path.read_bytes()[:8], b"\x89PNG\r\n\x1a\n")
        self.assertEqual(jpg_path.read_bytes()[:2], b"\xff\xd8")

        dashboard_source = (
            Path(__file__).parents[1]
            / "src" / "sia_app" / "ui" / "dashboard_tab.py"
        ).read_text(encoding="utf-8")
        self.assertIn('("fin_comp", "Financ. × Competência")', dashboard_source)
        self.assertIn("legend_at_top=True", dashboard_source)
        self.assertIn('("fin_estab", "Financ. × Estabelecimento")', dashboard_source)
        self.assertIn("command=self._export_active_chart", dashboard_source)
        self.assertIn('(\"Imagem JPEG\", \"*.jpg *.jpeg\")', dashboard_source)
        self.assertIn("xview_scroll(direction, \"units\")", dashboard_source)
        self.assertIn("self.chart_tab_underlines", dashboard_source)
        self.assertIn("command=self._atualizar_grafico_cbo", dashboard_source)
        self.assertNotIn('text="⋯"', dashboard_source)

    def test_data_view_and_report_services_preserve_totals_and_groups(self) -> None:
        row = {
            "PRD_UID": "1234567",
            "PRD_CMP": "202601",
            "PRD_PA": "1234567890",
            "PRD_CBO": "225125",
            "PRD_TPFIN": "01",
            "PRD_CPX": "01",
            "QUANTIDADE_APROVADA": 2,
            "QUANTIDADE_PRODUZIDA": 3,
            "VALOR_UNITARIO": 10,
            "VALOR_APROVADO": 20,
            "VALOR_PRODUZIDO": 30,
            "VALOR_TOTAL": 20,
        }
        view = DataViewService().prepare([row], {"1234567": "Unidade Teste"})
        self.assertEqual(len(view.rows), 1)
        self.assertEqual(view.totals["qtd_produzida"], 3)
        self.assertEqual(view.totals["valor_aprovado"], 20)

        service = ReportService(self.db)
        blocks = service.group_by_establishment_competence(
            [row], {"1234567": "Unidade Teste"}
        )
        self.assertEqual(blocks[0]["nome"], "Unidade Teste")
        self.assertEqual(service.extract_procedure({"proc": "123456"}), "123456")
        self.assertTrue(service.match_procedure(row, "123456"))
        options = service.prepare_pdf_options({}, "Título", "unidade", {})
        self.assertTrue(options["uma_pagina_por_bloco"])
        self.assertFalse(options["ocultar_zerados"])

    def test_prd_and_establishment_services_manage_records(self) -> None:
        self._seed_service_data()
        prd = PrdEditorService(self.db)
        rows = prd.list_records("202601", "Unidade")
        self.assertEqual(len(rows), 1)
        record_id = rows[0][0]
        prd.update_quantities(record_id, "7", "5")
        updated = prd.list_records("202601", "Unidade")[0]
        self.assertEqual(updated[11:15], ("7", "5", "R$ 70,00", "R$ 50,00"))

        establishments = EstablishmentService(self.db)
        action = establishments.save(
            None,
            {"CO_CNES": "7654321", "NO_FANTASIA": "Segunda Unidade", "CO_CEP": ""},
        )
        self.assertEqual(action, "criado")
        found = establishments.search(
            establishments.list_sorted("NO_FANTASIA"),
            "segunda",
            "NO_FANTASIA",
        )
        self.assertEqual([row["CO_CNES"] for row in found], ["7654321"])

    def test_file_import_service_orders_pa_cnes_and_prd_by_competence(self) -> None:
        converter = MagicMock()

        def convert(path, _kind):
            competence = "202602" if path.endswith("b.dbf") else "202601"
            return True, pd.DataFrame([{"PRD_CMP": competence}]), "ok"

        converter.dbf_to_dataframe.side_effect = convert
        service = FileImportService(
            self.db,
            converter,
            MagicMock(),
            MagicMock(),
            LOGGER,
        )
        ordered = service.order_files(
            [
                ("PRD", "b.dbf"),
                ("CNES", "cnes.csv"),
                ("PRD", "a.dbf"),
                ("PA", "pa.dbf"),
            ]
        )
        self.assertEqual(
            ordered,
            [
                ("PA", "pa.dbf"),
                ("CNES", "cnes.csv"),
                ("PRD", "a.dbf"),
                ("PRD", "b.dbf"),
            ],
        )

    def test_large_tabs_do_not_embed_sql_or_import_pipeline(self) -> None:
        ui_root = Path(__file__).parents[1] / "src" / "sia_app" / "ui"
        for name in (
            "dashboard_tab.py",
            "filters_tab.py",
            "file_upload_tab.py",
            "prd_editor_tab.py",
            "reports_tab.py",
        ):
            source = (ui_root / name).read_text(encoding="utf-8")
            for forbidden in (
                "SELECT ",
                "INSERT INTO",
                "UPDATE tb_",
                "DELETE FROM",
                "dbf_to_dataframe",
                "importar_dados_prd",
            ):
                self.assertNotIn(forbidden, source, f"{name} contém {forbidden}")

    def test_schema_and_settings_keep_false_and_zero(self) -> None:
        with self.db.read() as cursor:
            self.assertEqual(cursor.execute("PRAGMA user_version").fetchone()[0], 4)
            self.assertEqual(cursor.execute("PRAGMA integrity_check").fetchone()[0], "ok")
            columns = {
                row[1]
                for row in cursor.execute("PRAGMA table_xinfo(tb_prd_retro_controle)")
            }
        self.assertIn("PRD_CBO", columns)

        settings = AppSettings(self.root / "config" / "settings.json")
        settings.set("ocultar_zerados", False)
        settings.set("valor_teste", 0)
        self.assertTrue(settings.save_settings())

        loaded = AppSettings(settings.config_file)
        self.assertIs(loaded.get("ocultar_zerados", True), False)
        self.assertEqual(loaded.get("valor_teste", 99), 0)

    def test_write_helper_and_config_update(self) -> None:
        model = EstabelecimentoModel(self.db)
        inserted = model.execute_query(
            """
            INSERT INTO tb_estabelecimento
                (CO_CNES, NO_FANTASIA, CO_CEP, DT_ATUALIZACAO, arquivo_origem)
            VALUES (?, ?, ?, ?, ?)
            """,
            ("1234567", "Unidade Teste", "11700000", "2026-01-01", "CADASTRO_MANUAL"),
        )
        self.assertEqual(inserted, 1)

        with self.db.txn() as cursor:
            cursor.execute("UPDATE config_sistema SET ocultar_zerados = 1 WHERE id = 1")
        self.assertTrue(
            ConfigModel(self.db).salvar_config(
                {
                    "logo_path": "logo.png",
                    "inst1": "Instituição",
                    "inst2": "Secretaria",
                    "inst3": "Setor",
                    "ultimo_dir_arquivos": "arquivos",
                }
            )
        )
        with self.db.read() as cursor:
            row = cursor.execute(
                "SELECT inst1, ocultar_zerados FROM config_sistema WHERE id = 1"
            ).fetchone()
        self.assertEqual(row["inst1"], "Instituição")
        self.assertEqual(row["ocultar_zerados"], 1)

    def test_import_query_and_values_are_recalculated_from_pa(self) -> None:
        importer = CSVImporter(LOGGER, self.db)
        EstabelecimentoModel(self.db).inserir_lote(
            [("1234567", "Unidade Teste", "11700000", "2026-01-01", "fixture")]
        )

        pa = pd.DataFrame(
            [
                {
                    "PA_ID": "123456789",
                    "PA_DV": "0",
                    "PA_DC": "Procedimento de teste",
                    "PA_TOTAL": 10,
                    "PA_CTF": "01",
                    "PA_CPX": "01",
                }
            ]
        )
        success, _ = importer.importar_dados_pa(pa, "pa_fixture")
        self.assertTrue(success)

        prd = pd.DataFrame(
            [
                {
                    "PRD_UID": "1234567",
                    "PRD_CMP": "202601",
                    "PRD_PA": "1234567890",
                    "PRD_CBO": "225125",
                    "PRD_TPFIN": "01",
                    "PRD_CPX": "01",
                    "PRD_QT_P": 3,
                    "PRD_QT_A": 2,
                    "PRD_VL_P": 999,
                    "PRD_VL_A": 999,
                }
            ]
        )
        success, _ = importer.importar_dados_prd(prd, "prd_fixture.dbf|hash-a")
        self.assertTrue(success)
        duplicate_success, duplicate_message = importer.importar_dados_prd(
            prd, "prd_fixture.dbf|hash-a"
        )
        self.assertFalse(duplicate_success)
        self.assertIn("já importado", duplicate_message)

        rows = DataProcessor(self.db, LOGGER).obter_dados_aggregado(
            {"competencias": ["202601"]}
        )
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["VALOR_APROVADO"], 20)
        self.assertEqual(rows[0]["VALOR_PRODUZIDO"], 30)

        pa.loc[0, "PA_TOTAL"] = 12
        success, _ = importer.importar_dados_pa(pa, "pa_fixture_atualizado")
        self.assertTrue(success)
        rows = DataProcessor(self.db, LOGGER).obter_dados_aggregado(
            {"competencias": ["202601"]}
        )
        self.assertEqual(rows[0]["VALOR_APROVADO"], 24)
        self.assertEqual(rows[0]["VALOR_PRODUZIDO"], 36)

        with self.db.read() as cursor:
            for grouping in (None, "estabelecimento_competencia", "procedimento", "competencia"):
                sql, params = QueryBuilder.build_producao_query(
                    {"competencia_list": ["202601"]},
                    grouping,
                    {"limite": 10, "offset": 0},
                )
                cursor.execute(sql, params)
                self.assertEqual(len(cursor.fetchall()), 1)

            public_queries = (
                QueryBuilder.build_estabelecimentos_query({"cnes": "1234567"}),
                QueryBuilder.build_procedimentos_query({"codigo": "123", "busca_exata": False}),
                QueryBuilder.build_estatisticas_query(),
                QueryBuilder.build_competencia_query({"cnes": "1234567"}),
                QueryBuilder.build_cnes_query({"competencia": "202601"}),
                QueryBuilder.build_export_query({"competencia_list": ["202601"]}),
            )
            for sql, params in public_queries:
                cursor.execute(sql, params)
                self.assertTrue(cursor.fetchall())

        with self.assertRaises(ValueError):
            QueryBuilder.build_producao_query(agrupamento="invalido")

    def test_csv_export_includes_and_separates_financing_types(self) -> None:
        with self.db.txn() as cursor:
            cursor.execute(
                "INSERT INTO tb_estabelecimento (CO_CNES, NO_FANTASIA) VALUES (?, ?)",
                ("1234567", "Unidade Teste"),
            )
            cursor.execute(
                """
                INSERT INTO tb_pa (PA_ID, PA_DV, PA_DC, PA_TOTAL)
                VALUES (?, ?, ?, ?)
                """,
                ("123456789", "0", "Procedimento de teste", 10),
            )
            cursor.executemany(
                """
                INSERT INTO tb_prd (
                    PRD_UID, PRD_CMP, PRD_PA, PRD_CBO, PRD_TPFIN,
                    PRD_QT_P, PRD_QT_A
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    ("1234567", "202601", "1234567890", "111111", "01", 2, 3),
                    ("1234567", "202601", "1234567890", "222222", "02", 4, 5),
                ],
            )

        processor = DataProcessor(self.db, LOGGER)
        report_rows = processor.obter_dados_aggregado({"competencias": ["202601"]})
        csv_rows = processor.obter_dados_exportacao_csv(
            {"competencias": ["202601"]}
        )

        self.assertEqual(len(report_rows), 1)
        self.assertEqual(len(csv_rows), 2)
        self.assertEqual({row["PRD_TPFIN"] for row in csv_rows}, {"01", "02"})
        self.assertEqual(sum(row["QUANTIDADE_PRODUZIDA"] for row in csv_rows), 6)
        self.assertEqual(sum(row["QUANTIDADE_APROVADA"] for row in csv_rows), 8)

        output = self.root / "exportacao.csv"
        exportar_csv_agregado(csv_rows, output)
        exported = pd.read_csv(output, sep=";", dtype=str, encoding="utf-8-sig")

        self.assertIn("Tipo de Financiamento", exported.columns)
        self.assertEqual(
            set(exported["Tipo de Financiamento"]),
            {
                "01 - PAB - Piso de Atenção Básica",
                "02 - MAC - Média e Alta Complexidade",
            },
        )

    def test_clear_resets_import_history(self) -> None:
        auth = AuthService(self.db)
        session = auth.bootstrap_admin("Senha segura 2026", "Senha segura 2026")
        with self.db.txn() as cursor:
            cursor.execute(
                """
                INSERT INTO tb_importacao_prd
                    (arquivo_origem, hash_arquivo, competencia_principal)
                VALUES ('fixture|abc', 'abc', '202601')
                """
            )
            cursor.execute(
                """
                INSERT INTO tb_prd_retro_controle
                    (competencia_origem, PRD_UID, PRD_CMP, PRD_PA, PRD_CBO)
                VALUES ('202601', '1234567', '202512', '1234567890', '')
                """
            )

        success, _ = DatabaseOperations(db_connection=self.db).limpar_banco(False)
        self.assertTrue(success)
        with self.db.read() as cursor:
            for table in (
                "tb_prd",
                "tb_pa",
                "tb_estabelecimento",
                "tb_importacao_prd",
                "tb_prd_retro_controle",
            ):
                self.assertEqual(cursor.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0], 0)
            self.assertEqual(cursor.execute("SELECT COUNT(*) FROM tb_usuario").fetchone()[0], 1)
        self.assertEqual(
            auth.authenticate(session.username, "Senha segura 2026").user_id,
            session.user_id,
        )

    def test_restore_preserves_current_users_and_permissions(self) -> None:
        auth = AuthService(self.db)
        admin = auth.bootstrap_admin("Senha segura 2026", "Senha segura 2026")
        manager = BackupManager(self.db.db_path, self.root / "backups-users")
        success, message = manager.criar_backup_simples()
        self.assertTrue(success, message)
        backup_file = manager.listar_backups()[0]

        admin_record = auth.list_users()[0]
        auth.save_user_changes(
            [
                {
                    "id": admin_record.id,
                    "name": "Administrador Atual",
                    "username": admin_record.username,
                    "role": ROLE_ADMIN,
                    "active": True,
                    "password": "Nova senha 2026",
                }
            ],
            set(),
            admin,
        )

        success, message = manager.restaurar_backup(backup_file)
        self.assertTrue(success, message)
        restored = auth.authenticate("admin", "Nova senha 2026")
        self.assertEqual(restored.name, "Administrador Atual")
        with self.assertRaises(InvalidCredentialsError):
            auth.authenticate("admin", "Senha segura 2026")

    def test_backup_restore_and_zip_validation(self) -> None:
        with self.db.txn() as cursor:
            cursor.execute(
                "INSERT INTO tb_estabelecimento (CO_CNES, NO_FANTASIA) VALUES (?, ?)",
                ("1234567", "Antes do backup"),
            )

        manager = BackupManager(self.db.db_path, self.root / "backups")
        success, _ = manager.criar_backup_simples()
        self.assertTrue(success)
        backup_file = manager.listar_backups()[0]

        with self.db.txn() as cursor:
            cursor.execute(
                "UPDATE tb_estabelecimento SET NO_FANTASIA = 'Depois do backup'"
            )
        success, message = manager.restaurar_backup(backup_file)
        self.assertTrue(success, message)
        with self.db.read() as cursor:
            name = cursor.execute(
                "SELECT NO_FANTASIA FROM tb_estabelecimento WHERE CO_CNES = '1234567'"
            ).fetchone()[0]
            integrity = cursor.execute("PRAGMA integrity_check").fetchone()[0]
        self.assertEqual(name, "Antes do backup")
        self.assertEqual(integrity, "ok")

        success, message = manager.criar_backup_compactado(senha="não-é-usada")
        self.assertFalse(success)
        self.assertIn("não oferece criptografia segura", message)

    def test_pdf_generation_in_all_table_modes(self) -> None:
        data = [
            {
                "uid": "1234567",
                "cmp": "202601",
                "nome": "Unidade Teste",
                "rows": [
                    {
                        "PRD_PA": "1234567890",
                        "PA_DC": "Procedimento de teste",
                        "QUANTIDADE": 2,
                        "QUANTIDADE_APROVADA": 2,
                        "QUANTIDADE_PRODUZIDA": 3,
                        "VALOR_UNITARIO": 12,
                        "VALOR_APROVADO": 24,
                        "VALOR_PRODUZIDO": 36,
                        "VALOR_TOTAL": 24,
                    }
                ],
            }
        ]
        base_config = {
            "inst1": "Instituição",
            "inst2": "Secretaria",
            "inst3": "Setor",
            "logo_path": "",
            "title": "Relatório de teste",
        }

        for mode in ("unidade", "procedimento", "diferencas"):
            output = self.root / f"relatorio_{mode}.pdf"
            success, message = PDFGenerator(LOGGER).generate_pdf(
                data,
                {**base_config, "table_mode": mode},
                str(output),
            )
            self.assertTrue(success, message)
            self.assertGreater(output.stat().st_size, 1_000)
            self.assertEqual(output.read_bytes()[:5], b"%PDF-")

    def test_pdf_labels_and_block_identification_order(self) -> None:
        generator = PDFGenerator(LOGGER)
        doc = SimpleDocTemplate(
            str(self.root / "layout.pdf"),
            pagesize=landscape(A4),
        )
        header = generator._create_block_header(
            {
                "estabelecimento": "Unidade Teste",
                "cnes": "1234567",
                "competencia": "202601",
            },
            doc,
        )[0]

        left_text = header._cellvalues[0][0].getPlainText()
        right_text = header._cellvalues[0][1].getPlainText()
        general_total = generator._create_general_totals(
            123,
            Decimal("456.78"),
        )[0]
        total_text = general_total.getPlainText()

        self.assertEqual(left_text, "Estabelecimento: Unidade Teste (CNES 1234567)")
        self.assertEqual(right_text, "Competência: Janeiro/2026")
        self.assertEqual(total_text, "Totais - Prod.: 123 | Valor: R$ 456,78")
        self.assertEqual(
            general_total.style.fontSize,
            generator.REPORT_TITLE_FONT_SIZE,
        )
        self.assertEqual(
            general_total.style.leading,
            generator.REPORT_TITLE_LEADING,
        )

    def test_block_identification_aligns_with_production_table(self) -> None:
        generator = PDFGenerator(LOGGER)
        doc = SimpleDocTemplate(
            str(self.root / "alinhamento_tabelas.pdf"),
            pagesize=landscape(A4),
            leftMargin=1.35 * cm,
            rightMargin=1.35 * cm,
        )
        block_header = generator._create_block_header(
            {
                "estabelecimento": "Unidade Teste",
                "cnes": "1234567",
                "competencia": "202601",
            },
            doc,
        )[0]
        procedures = [
            {
                "codigo": "1234567890",
                "descricao": "Procedimento de teste",
                "quantidade": 1,
                "valor_unitario": 2,
                "valor_total": 2,
                "quantidade_aprovada": 1,
                "quantidade_produzida": 1,
                "valor_aprovado": 2,
                "valor_produzido": 2,
                "diferenca_quantidade": 0,
                "diferenca_valor": 0,
            }
        ]
        production_tables = [
            generator._create_procedure_table_simple(procedures, doc, {}),
            generator._create_procedure_table_detailed(procedures, doc, {}),
            generator._create_procedure_table_diferencas(
                procedures,
                doc,
                {"mostrar_diferencas": True},
            ),
        ]

        frame_width = doc.width - 12
        frame_x = doc.leftMargin + 6
        header_width, _ = block_header.wrap(frame_width, doc.height)
        header_x = block_header._hAlignAdjust(
            frame_x,
            frame_width - header_width,
        )

        for production_table in production_tables:
            table_width, _ = production_table.wrap(frame_width, doc.height)
            table_x = production_table._hAlignAdjust(
                frame_x,
                frame_width - table_width,
            )

            self.assertEqual(block_header.hAlign, production_table.hAlign)
            self.assertAlmostEqual(header_x, table_x)
            self.assertAlmostEqual(
                header_x + header_width,
                table_x + table_width,
            )

    def test_report_title_is_discreet_and_does_not_move_the_table(self) -> None:
        generator = PDFGenerator(LOGGER)
        doc = SimpleDocTemplate(
            str(self.root / "titulo_centralizado.pdf"),
            pagesize=landscape(A4),
        )
        elements = generator._prepare_content(
            [],
            {"title": "Produção por Unidade e Competência"},
            doc,
        )

        title_offset, title = elements[:2]
        title_height = title.wrap(doc.width, doc.height)[1]

        self.assertEqual(title.style.fontSize, generator.REPORT_TITLE_FONT_SIZE)
        self.assertEqual(generator.REPORT_TITLE_FONT_SIZE, 15)
        self.assertAlmostEqual(title_offset.height, -generator.TITLE_VERTICAL_OFFSET)
        self.assertAlmostEqual(
            title_offset.height + title_height + title.getSpaceAfter(),
            generator.TITLE_SLOT_HEIGHT,
        )

    def test_procedure_grouping_uses_left_aligned_staircase_hierarchy(self) -> None:
        generator = PDFGenerator(LOGGER)
        doc = SimpleDocTemplate(
            str(self.root / "hierarquia_procedimentos.pdf"),
            pagesize=landscape(A4),
        )
        procedures = [
            {
                "codigo": "0401010015",
                "descricao": "Procedimento de teste",
                "quantidade": 1,
                "valor_unitario": 2,
                "valor_total": 2,
                "quantidade_aprovada": 1,
                "quantidade_produzida": 1,
                "valor_aprovado": 2,
                "valor_produzido": 2,
            }
        ]

        table = generator._create_procedure_table_detailed(procedures, doc, {})
        labels = [table._cellvalues[row][0] for row in (1, 2, 3)]
        styles = [table._cellStyles[row][0] for row in (1, 2, 3)]

        self.assertEqual(
            labels,
            ["Grupo 04", "Subgrupo 04.01", "Forma de Organização 04.01.01"],
        )
        self.assertTrue(all(style.alignment == "LEFT" for style in styles))
        self.assertEqual(
            [style.leftPadding for style in styles],
            [
                generator.GROUP_HIERARCHY_INDENTS["grupo"],
                generator.GROUP_HIERARCHY_INDENTS["subgrupo"],
                generator.GROUP_HIERARCHY_INDENTS["forma"],
            ],
        )
        self.assertLess(styles[0].leftPadding, styles[1].leftPadding)
        self.assertLess(styles[1].leftPadding, styles[2].leftPadding)
        self.assertEqual(len(table._nosplitCmds), 3)

    def test_header_and_footer_center_position_without_changing_text_alignment(self) -> None:
        generator = PDFGenerator(LOGGER)
        doc = SimpleDocTemplate(
            str(self.root / "posicionamento.pdf"),
            pagesize=landscape(A4),
            topMargin=3.0 * cm,
            bottomMargin=1.15 * cm,
            leftMargin=1.35 * cm,
            rightMargin=1.35 * cm,
        )
        canvas = MagicMock()

        generator._draw_header(
            canvas,
            doc,
            {
                "inst1": "Prefeitura",
                "inst2": "Secretaria",
                "inst3": "Divisão",
                "logo_path": "",
            },
        )

        header_calls = canvas.drawString.call_args_list
        self.assertEqual(len(header_calls), 3)
        self.assertTrue(all(call.args[0] == doc.leftMargin for call in header_calls))
        self.assertFalse(canvas.drawCentredString.called)
        self.assertEqual(
            canvas.line.call_args.args,
            (0, doc.pagesize[1] - 2.35 * cm, doc.pagesize[0], doc.pagesize[1] - 2.35 * cm),
        )

        canvas.reset_mock()
        generator._draw_footer(canvas, doc, {"footer": {"source": "Fonte: SIA/SUS"}})

        self.assertEqual(canvas.drawString.call_count, 1)
        self.assertEqual(canvas.drawString.call_args.args[0], doc.leftMargin)
        self.assertEqual(canvas.drawCentredString.call_count, 1)
        self.assertEqual(canvas.drawCentredString.call_args.args[0], doc.pagesize[0] / 2)
        self.assertEqual(
            canvas.line.call_args.args,
            (0, doc.bottomMargin, doc.pagesize[0], doc.bottomMargin),
        )

        footer_y = canvas.drawString.call_args.args[1]
        self.assertGreater(footer_y, 0)
        self.assertLess(footer_y, doc.bottomMargin)


class MigrationRegressionTests(unittest.TestCase):
    def test_old_schema_receives_missing_columns(self) -> None:
        with tempfile.TemporaryDirectory(prefix="sia_migration_") as temp_dir:
            db_path = Path(temp_dir) / "old.db"
            connection = sqlite3.connect(db_path)
            connection.executescript(
                """
                CREATE TABLE tb_prd (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    PRD_UID TEXT, PRD_CMP TEXT, PRD_PA TEXT,
                    PRD_TPFIN TEXT, PRD_CPX TEXT,
                    PRD_QT_P REAL, PRD_QT_A REAL, PRD_VL_P REAL, PRD_VL_A REAL,
                    arquivo_origem TEXT, data_importacao DATETIME,
                    UNIQUE(PRD_UID, PRD_CMP, PRD_PA)
                );
                CREATE TABLE tb_pa (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    PA_ID TEXT, PA_DV TEXT, PA_DC TEXT, PA_TOTAL REAL,
                    arquivo_origem TEXT, data_importacao DATETIME
                );
                CREATE TABLE tb_estabelecimento (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    CO_CNES TEXT UNIQUE, NO_FANTASIA TEXT, CO_CEP TEXT,
                    DT_ATUALIZACAO TEXT, arquivo_origem TEXT, data_importacao DATETIME
                );
                CREATE TABLE tb_prd_retro_controle (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    competencia_origem TEXT, PRD_UID TEXT, PRD_CMP TEXT, PRD_PA TEXT,
                    PRD_TPFIN TEXT, PRD_CPX TEXT,
                    PRD_QT_P REAL, PRD_QT_A REAL, PRD_VL_P REAL, PRD_VL_A REAL,
                    arquivo_origem TEXT, data_importacao DATETIME,
                    UNIQUE(competencia_origem, PRD_UID, PRD_CMP, PRD_PA)
                );
                """
            )
            connection.close()

            db = DatabaseConnection(db_path)
            db.initialize_database()
            with db.read() as cursor:
                prd_columns = {
                    row[1] for row in cursor.execute("PRAGMA table_xinfo(tb_prd)")
                }
                retro_columns = {
                    row[1]
                    for row in cursor.execute("PRAGMA table_xinfo(tb_prd_retro_controle)")
                }
                pa_columns = {
                    row[1] for row in cursor.execute("PRAGMA table_xinfo(tb_pa)")
                }
                user_columns = {
                    row[1] for row in cursor.execute("PRAGMA table_xinfo(tb_usuario)")
                }
                version = cursor.execute("PRAGMA user_version").fetchone()[0]
                integrity = cursor.execute("PRAGMA integrity_check").fetchone()[0]

            self.assertIn("PRD_CBO", prd_columns)
            self.assertIn("PRD_CBO", retro_columns)
            self.assertIn("PROC", pa_columns)
            self.assertIn("senha_hash", user_columns)
            self.assertIn("perfil", user_columns)
            self.assertEqual(version, 4)
            self.assertEqual(integrity, "ok")


if __name__ == "__main__":
    unittest.main()
