import tkinter as tk
from tkinter import ttk, messagebox
from typing import Optional, Dict, Any
import logging
import importlib
from pathlib import Path
from datetime import datetime

import customtkinter as ctk

from sia_app.paths import get_runtime_paths
from sia_app.services.auth_service import AuthService, UserSession

from sia_app.ui.theme import COLORS, apply_theme, FONT_FAMILY
from sia_app.ui.icons import icon
from sia_app.ui.components.design import Tooltip
from sia_app.ui.components.navigation_search import NavigationSearch

NAV_ICONS = {
    "dashboard": "dashboard", "file_upload": "upload", "filters": "filter",
    "reports": "report", "establishments": "building", "prd_editor": "production",
    "database": "database", "config": "settings",
}

class MainWindow:
    """
    Janela principal do RelSIA com navegação lateral e identidade compartilhada.
    """

    def __init__(
        self,
        root: tk.Tk,
        db,
        settings,
        logger: logging.Logger,
        auth_service: AuthService,
        session: UserSession,
        on_logout=None,
    ):
        self.root = root
        self.db = db
        self.settings = settings
        self.logger = logger
        self.auth_service = auth_service
        self.session = session
        self.on_logout = on_logout
        self._shutting_down = False

        self.tabs: Dict[str, Any] = {}
        self.nav_buttons: Dict[str, ctk.CTkButton] = {}
        self.nav_underlines: Dict[str, ctk.CTkFrame] = {}
        
        self.ultima_atualizacao_var = tk.StringVar(value="Última atualização: --")
        self.user_name_var = tk.StringVar(value=self._header_user_name(self.session.name))
        self.user_role_var = tk.StringVar(value=self.session.role_label)

        self._setup_environment()
        self._setup_window()
        self._create_interface()
        self._check_initial_config()

        self.logger.info("Janela principal inicializada com sucesso")

    def _setup_environment(self) -> None:
        """Registra as telas sem importá-las durante a abertura do programa."""
        self._tab_specs = {
            "dashboard": ("Visão geral", "sia_app.ui.dashboard_tab", "DashboardTab"),
            "file_upload": ("Importar arquivos", "sia_app.ui.file_upload_tab", "FileUploadTab"),
            "filters": ("Filtros", "sia_app.ui.filters_tab", "FiltersTab"),
            "reports": ("Relatórios", "sia_app.ui.reports_tab", "ReportsTab"),
            "establishments": ("Estabelecimentos", "sia_app.ui.estabelecimentos_tab", "EstabelecimentosTab"),
            "prd_editor": ("Dados de Produção", "sia_app.ui.prd_editor_tab", "PrdEditorTab"),
            "database": ("Banco de Dados", "sia_app.ui.database_tab", "DatabaseTab"),
            "config": ("Configurações", "sia_app.ui.config_tab", "ConfigTab"),
        }

    def _setup_window(self) -> None:
        """Configura a janela principal."""
        apply_theme()

        self.root.title("RelSIA · Gestão ambulatorial")
        self.root.geometry("1440x900")
        self.root.minsize(980, 650)
        # O CustomTkinter envolve configure() do pai. A chamada pela classe
        # evita referências a frames destruídos ao recriar a interface.
        tk.Tk.configure(self.root, bg=COLORS["bg"])

        self._set_window_icon()
        self._center_window()
        self._setup_styles()

    def _set_window_icon(self) -> None:
        """Tenta definir o ícone da janela."""
        try:
            project_root = get_runtime_paths().project_root
            package_root = Path(__file__).resolve().parents[1]
            icon_paths = [
                project_root / "assets" / "icon.ico",
                package_root / "ui" / "assets" / "icon.ico",
                project_root / "icon.ico",
            ]

            for icon_path in icon_paths:
                if icon_path.exists():
                    self.root.iconbitmap(str(icon_path))
                    self.logger.info(f"Ícone definido: {icon_path}")
                    break

        except Exception as e:
            self.logger.warning(f"Não foi possível definir ícone: {e}")

    def _center_window(self) -> None:
        """Centraliza a janela na tela."""
        self.root.update_idletasks()

        screen_width = self.root.winfo_screenwidth()
        screen_height = self.root.winfo_screenheight()

        window_width = min(1440, screen_width - 40)
        window_height = min(900, screen_height - 80)

        x = (screen_width - window_width) // 2
        y = (screen_height - window_height) // 2

        self.root.geometry(f"{window_width}x{window_height}+{x}+{y}")

    def _setup_styles(self) -> None:
        """Configura estilos visuais da aplicação."""
        try:
            style = ttk.Style()

            available_themes = style.theme_names()
            if "clam" in available_themes:
                style.theme_use("clam")
            style.configure("TFrame", background=COLORS["bg"])
            style.configure("TLabel", background=COLORS["surface"], foreground=COLORS["text"])
            style.configure("Treeview", background=COLORS["surface"],
                            fieldbackground=COLORS["surface"], foreground=COLORS["text"],
                            rowheight=32, borderwidth=0, font=(FONT_FAMILY, 11))
            style.configure("Treeview.Heading", background=COLORS["bg"],
                            foreground=COLORS["muted"], padding=(10, 10),
                            relief="flat", font=(FONT_FAMILY, 10, "bold"))
            style.map("Treeview", background=[("selected", COLORS["primary_soft"])],
                      foreground=[("selected", COLORS["primary_dark"])])

            # Notebook invisível: as abas continuam existindo, mas quem aparece é o menu moderno.
            style.configure("Hidden.TNotebook", background=COLORS["bg"], borderwidth=0, tabmargins=0)
            style.layout("Hidden.TNotebook.Tab", [])
            style.configure("Hidden.TNotebook.Tab", padding=0)

            style.configure("Accent.TButton", foreground="black", background=COLORS["primary"])
            style.configure("Success.TButton", foreground="black", background=COLORS["success"])
            style.configure("Danger.TButton", foreground="black", background=COLORS["danger"])
            style.configure("Warning.TButton", foreground="black", background=COLORS["warning"])

            style.configure("Card.TLabelframe", borderwidth=2, relief="solid")
            style.configure("Card.TLabelframe.Label", foreground=COLORS["text"])
            style.configure("Switch.TCheckbutton", foreground=COLORS["muted"])

            self.logger.info("Estilos visuais configurados")

        except Exception as e:
            self.logger.warning(f"Erro ao configurar estilos: {e}")

    def _create_interface(self) -> None:
        """Constrói uma navegação fixa e uma área de trabalho independente."""
        self._compact_sidebar = False
        self._sidebar_after = None
        self._navigation_search = None
        self._tooltips = []
        self._keyboard_bindings = []
        self.main_container = ctk.CTkFrame(self.root, fg_color=COLORS["bg"], corner_radius=0)
        self.main_container.pack(fill="both", expand=True)
        self.main_container.grid_rowconfigure(0, weight=1)
        self.main_container.grid_columnconfigure(1, weight=1)
        self._create_nav_bar(self.main_container)
        workspace = ctk.CTkFrame(self.main_container, fg_color=COLORS["bg"], corner_radius=0)
        workspace.grid(row=0, column=1, sticky="nsew")
        self._create_header(workspace)
        self._create_status_bar(workspace)
        self._create_tab_area(workspace)
        self._resize_binding = self.root.bind("<Configure>", self._schedule_sidebar_resize, add="+")
        self._resize_sidebar()
        self._register_shortcuts()

    def _create_header(self, parent) -> None:
        header = ctk.CTkFrame(parent, fg_color=COLORS["surface"], corner_radius=0, height=70)
        header.pack(fill="x", side="top")
        header.pack_propagate(False)
        ctk.CTkFrame(parent, height=1, fg_color=COLORS["border"], corner_radius=0).pack(fill="x")
        self.breadcrumb_var = tk.StringVar(value="Visão geral")
        ctk.CTkLabel(header, text="Espaço de trabalho", font=(FONT_FAMILY, 12),
                     text_color=COLORS["muted"]).pack(side="left", padx=(30, 18))
        ctk.CTkLabel(header, text="›", font=(FONT_FAMILY, 18),
                     text_color=COLORS["muted"]).pack(side="left")
        ctk.CTkLabel(header, textvariable=self.breadcrumb_var, font=(FONT_FAMILY, 12),
                     text_color=COLORS["text"]).pack(side="left", padx=18)
        search = ctk.CTkButton(header, text="Buscar uma tela     Ctrl K", width=218, height=36,
                               image=icon("search", COLORS["muted"], 17), compound="left",
                               fg_color=COLORS["bg"], hover_color="#E9EFF1", border_width=1,
                               border_color=COLORS["border"], text_color=COLORS["muted"],
                               font=(FONT_FAMILY, 12), command=self.open_navigation_search)
        search.pack(side="right", padx=28, pady=17)
        self._tooltips.append(Tooltip(search, "Buscar uma tela pelo nome · Ctrl+K"))

    def open_navigation_search(self):
        if self._navigation_search is None:
            self._navigation_search = NavigationSearch(self.root, self.nav_configs, self.navigate_to_tab)
        self._navigation_search.show()
        return "break"

    def _register_shortcuts(self):
        bindings = [("<Control-k>", lambda _event: self.open_navigation_search()),
                    ("<Control-r>", self._refresh_current_dashboard)]
        for index, (key, _label) in enumerate(self.nav_configs, 1):
            bindings.append((f"<Control-Key-{index}>", lambda _event, target=key: self._navigate_shortcut(target)))
        for event, callback in bindings:
            binding = self.root.bind(event, callback, add="+")
            self._keyboard_bindings.append((event, binding))

    def _navigate_shortcut(self, target):
        self.navigate_to_tab(target)
        return "break"

    def _refresh_current_dashboard(self, _event=None):
        if self.get_current_tab() == "dashboard":
            self.tabs["dashboard"].atualizar_dashboard()
            return "break"

    def _create_nav_bar(self, parent) -> None:
        self.sidebar = ctk.CTkFrame(parent, fg_color=COLORS["nav"], width=236, corner_radius=0)
        self.sidebar.grid(row=0, column=0, sticky="ns")
        self.sidebar.grid_propagate(False)
        self.sidebar.grid_columnconfigure(0, weight=1)
        self.sidebar.grid_rowconfigure(2, weight=1)

        brand = ctk.CTkFrame(self.sidebar, fg_color="transparent", height=112)
        self.brand_container = brand
        brand.grid(row=0, column=0, sticky="ew", padx=18)
        brand.grid_propagate(False)
        brand.grid_rowconfigure(0, weight=1)
        ctk.CTkLabel(brand, text="", width=40, height=44, corner_radius=11,
                     fg_color="#203F49", image=icon("brand", "#A5D5C3", 25)).grid(row=0, column=0)
        self.brand_text = ctk.CTkFrame(brand, fg_color="transparent")
        self.brand_text.grid(row=0, column=1, sticky="w", padx=(12, 0))
        ctk.CTkLabel(self.brand_text, text="RelSIA", font=(FONT_FAMILY, 27, "bold"),
                     text_color="#FFFFFF", anchor="w").pack(anchor="w")
        ctk.CTkLabel(self.brand_text, text="GESTÃO AMBULATORIAL", font=(FONT_FAMILY, 8),
                     text_color=COLORS["nav_muted"], anchor="w").pack(anchor="w", pady=(0, 4))

        self.nav_section_label = ctk.CTkLabel(self.sidebar, text="ESPAÇO DE TRABALHO", anchor="w",
                                             font=(FONT_FAMILY, 9, "bold"), text_color=COLORS["nav_muted"])
        self.nav_section_label.grid(row=1, column=0, sticky="ew", padx=25, pady=(8, 12))
        self.nav_container = ctk.CTkScrollableFrame(self.sidebar, fg_color="transparent", corner_radius=0,
                                                  scrollbar_button_color="#344D5C",
                                                  scrollbar_button_hover_color=COLORS["nav_hover"])
        self.nav_container.grid(row=2, column=0, sticky="nsew", padx=(10, 0))
        labels = [("dashboard", "Visão geral"), ("file_upload", "Importar arquivos"),
                  ("filters", "Filtros"), ("reports", "Relatórios"),
                  ("establishments", "Estabelecimentos"), ("prd_editor", "Dados de produção"),
                  ("database", "Banco de dados"), ("config", "Configurações")]
        self.nav_configs = [(key, label) for key, label in labels if self.session.can_access(key)]
        self.nav_groups = []
        previous_group = None
        groups = {"dashboard": "ANÁLISE", "filters": "ANÁLISE", "reports": "ANÁLISE",
                  "file_upload": "GESTÃO", "establishments": "GESTÃO", "prd_editor": "GESTÃO",
                  "database": "ADMINISTRAÇÃO", "config": "ADMINISTRAÇÃO"}
        # Mantém a análise e a gestão agrupadas no menu.
        order = ("dashboard", "filters", "reports", "file_upload", "establishments", "prd_editor", "database", "config")
        labels_by_key = dict(self.nav_configs)
        self.nav_configs = [(key, labels_by_key[key]) for key in order if key in labels_by_key]
        for index, (key, label) in enumerate(self.nav_configs):
            group = groups[key]
            if group != previous_group:
                caption = ctk.CTkLabel(self.nav_container, text=group, anchor="w", height=22,
                                       font=(FONT_FAMILY, 9, "bold"), text_color=COLORS["nav_muted"])
                caption.pack(fill="x", padx=15, pady=(10 if previous_group else 0, 4))
                self.nav_groups.append((caption, group))
                previous_group = group
            button = ctk.CTkButton(self.nav_container, text=label, anchor="w", height=42,
                                   corner_radius=7, fg_color="transparent", hover_color=COLORS["nav_hover"],
                                   text_color=COLORS["nav_text"], font=(FONT_FAMILY, 13),
                                   image=icon(NAV_ICONS[key], COLORS["nav_text"], 19),
                                   compound="left", border_spacing=12,
                                   command=lambda tab_key=key: self.navigate_to_tab(tab_key))
            button.pack(fill="x", pady=3, padx=(3, 0))
            self.nav_buttons[key] = button
            self._tooltips.append(Tooltip(button, f"{label} · Ctrl+{index + 1}"))

        bottom = ctk.CTkFrame(self.sidebar, fg_color="transparent")
        bottom.grid(row=3, column=0, sticky="ew", padx=18, pady=(12, 20))
        self.about_button = ctk.CTkButton(bottom, text="Sobre o RelSIA", anchor="w", height=36,
                                         fg_color="transparent", hover_color=COLORS["nav_hover"],
                                         text_color=COLORS["nav_text"], font=(FONT_FAMILY, 11),
                                         image=icon("info", COLORS["nav_text"], 18), command=self.show_about)
        self.about_button.pack(fill="x", pady=(0, 14))
        ctk.CTkFrame(bottom, height=1, fg_color="#2A3E4D").pack(fill="x", pady=(0, 16))
        self.user_panel = ctk.CTkFrame(bottom, fg_color="transparent")
        self.user_panel.pack(fill="x")
        self.avatar = ctk.CTkLabel(self.user_panel, text=self._initials(self.session.name),
                                   width=34, height=34, corner_radius=9, fg_color="#29463F",
                                   text_color="#B9DFCE", font=(FONT_FAMILY, 12, "bold"))
        self.avatar.pack(side="left")
        self.user_details = ctk.CTkFrame(self.user_panel, fg_color="transparent")
        self.user_details.pack(side="left", padx=(10, 0), fill="x", expand=True)
        ctk.CTkLabel(self.user_details, textvariable=self.user_name_var, anchor="w",
                     text_color="#EAF1F5", font=(FONT_FAMILY, 11, "bold"), width=125).pack(anchor="w")
        ctk.CTkLabel(self.user_details, textvariable=self.user_role_var, anchor="w",
                     text_color=COLORS["nav_muted"], font=(FONT_FAMILY, 10)).pack(anchor="w")
        self.logout_button = ctk.CTkButton(bottom, text="Sair da conta", height=32,
                                          fg_color="transparent", hover_color=COLORS["nav_hover"],
                                          text_color=COLORS["nav_text"], font=(FONT_FAMILY, 11),
                                          image=icon("logout", COLORS["nav_text"], 17), command=self._confirm_logout)
        self.logout_button.pack(fill="x", pady=(12, 0))

    @staticmethod
    def _initials(name: str) -> str:
        return "".join(word[0] for word in str(name).split()[:2]).upper() or "U"

    def _schedule_sidebar_resize(self, event) -> None:
        if event.widget is self.root and self._sidebar_after is None:
            self._sidebar_after = self.root.after_idle(self._resize_sidebar)

    def _resize_sidebar(self) -> None:
        self._sidebar_after = None
        compact = self.root.winfo_width() < 1280
        if compact == self._compact_sidebar:
            return
        self._compact_sidebar = compact
        self.sidebar.configure(width=76 if compact else 236)
        if compact:
            self.brand_text.grid_remove()
            self.nav_section_label.configure(text="")
            self.user_details.pack_forget()
        else:
            self.brand_text.grid()
            self.nav_section_label.configure(text="ESPAÇO DE TRABALHO")
            self.user_details.pack(side="left", padx=(10, 0), fill="x", expand=True)
        for key, label in self.nav_configs:
            self.nav_buttons[key].configure(text="" if compact else label, anchor="center" if compact else "w",
                                            width=40 if compact else 190, border_spacing=0 if compact else 12)
        for caption, group in self.nav_groups:
            caption.configure(text="" if compact else group, height=12 if compact else 22)
        self.about_button.configure(text="" if compact else "Sobre o RelSIA", width=36 if compact else 190)
        self.logout_button.configure(text="" if compact else "Sair da conta", width=36 if compact else 190)

    def _create_tab_area(self, parent) -> None:
        """Cria a área de abas da aplicação."""
        content_frame = ctk.CTkFrame(parent, fg_color=COLORS["bg"], corner_radius=0)
        content_frame.pack(fill="both", expand=True, padx=0, pady=0)

        self.notebook = ttk.Notebook(content_frame, style="Hidden.TNotebook")
        self.notebook.pack(fill="both", expand=True)

        self._setup_tabs()
        self.notebook.bind("<<NotebookTabChanged>>", self._on_tab_changed)
        self._set_active_nav("dashboard")

    def _setup_tabs(self) -> None:
        """Carrega somente a tela inicial; as demais entram sob demanda."""
        if self.session.can_access("dashboard"):
            self._create_tab("dashboard")
            return

        for tab_key in self._tab_specs:
            if self.session.can_access(tab_key):
                self._create_tab(tab_key)
                break

    def _create_tab(self, tab_key: str):
        """Importa e cria uma aba somente quando ela for realmente acessada."""
        if tab_key in self.tabs:
            return self.tabs[tab_key]
        if tab_key not in self._tab_specs or not self.session.can_access(tab_key):
            return None

        tab_text, module_name, class_name = self._tab_specs[tab_key]
        try:
            module = importlib.import_module(module_name)
            tab_class = getattr(module, class_name)

            if class_name == "DashboardTab":
                tab_instance = tab_class(self.notebook, self.db, self.settings, self.logger, on_update_status=self.atualizar_status_dashboard,
                                          on_navigate=self.navigate_to_tab, session=self.session)
            elif class_name == "ConfigTab":
                tab_instance = tab_class(self.notebook, self.db, self.settings, self.logger, self.auth_service, self.session, self._on_session_changed)
            else:
                tab_instance = tab_class(self.notebook, self.db, self.settings, self.logger)

            self.notebook.add(tab_instance.frame, text=tab_text)
            self.tabs[tab_key] = tab_instance
            self._setup_tab_dependencies()
            self.logger.debug("Aba '%s' carregada sob demanda", tab_text)
            return tab_instance
        except Exception as error:
            self.logger.exception("Falha ao criar aba %s", tab_text)
            messagebox.showerror("Erro de Interface", f"Não foi possível abrir a tela {tab_text}.\n\n{error}")
            return None

    def _setup_tab_dependencies(self) -> None:
        """Configura as dependências entre as abas após todas serem criadas."""
        try:
            if "reports" in self.tabs and "filters" in self.tabs:
                reports_tab = self.tabs["reports"]
                filters_tab = self.tabs["filters"]

                if hasattr(reports_tab, "filters_tab"):
                    reports_tab.filters_tab = filters_tab
                    self.logger.info("Dependência ReportsTab -> FiltersTab configurada")

        except Exception as e:
            self.logger.error(f"Erro ao configurar dependências entre abas: {e}")
            
    def atualizar_status_dashboard(self):
        agora = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
        self.ultima_atualizacao_var.set(f"Última atualização: {agora}")

    def _create_status_bar(self, parent) -> None:
        status_frame = ctk.CTkFrame(parent, fg_color=COLORS["surface"], corner_radius=0, height=34)
        status_frame.pack(side="bottom", fill="x")
        status_frame.pack_propagate(False)
        self.status_var = tk.StringVar(value="Pronto para consultar a produção")
        self.status_bar = ctk.CTkLabel(status_frame, textvariable=self.status_var,
                                      text_color=COLORS["muted"], font=(FONT_FAMILY, 10))
        self.status_bar.pack(side="left", padx=28)
        self.status_indicator = ctk.CTkLabel(status_frame, text="Pronto", text_color=COLORS["primary"],
                                            font=(FONT_FAMILY, 10))
        self.status_indicator.pack(side="right", padx=(12, 28))
        self.ultima_atualizacao_label = ctk.CTkLabel(status_frame, textvariable=self.ultima_atualizacao_var,
                                                     text_color=COLORS["muted"], font=(FONT_FAMILY, 10))
        self.ultima_atualizacao_label.pack(side="right", padx=12)

    def _on_tab_changed(self, event: tk.Event) -> None:
        """Manipula mudanças de aba."""
        try:
            current_key = self.get_current_tab()
            if not current_key:
                return

            status_messages = {
                "dashboard": "Visualize indicadores e gráficos da produção",
                "file_upload": "Pronto para importar arquivos SIA",
                "filters": "Configure os filtros para os relatórios",
                "reports": "Gere relatórios personalizados",
                "establishments": "Gerencie cadastro de estabelecimentos",
                "prd_editor": "Consulte, edite e exclua dados de produção",
                "database": "Realize backup e manutenção",
                "config": "Configure o sistema",
            }

            self._set_active_nav(current_key)
            self.update_status(status_messages.get(current_key, "Sistema operacional"))

            self.logger.debug(f"Aba alterada para: {current_key}")

        except Exception as e:
            self.logger.warning(f"Erro ao processar mudança de aba: {e}")

    def _set_active_nav(self, active_key: str) -> None:
        """Destaca a seção atual e atualiza o caminho no cabeçalho."""
        for key, button in self.nav_buttons.items():
            active = key == active_key
            color = "#D9F0E5" if active else COLORS["nav_text"]
            button.configure(fg_color=COLORS["nav_active"] if active else "transparent",
                             text_color=color, image=icon(NAV_ICONS[key], color, 19))
        if hasattr(self, "breadcrumb_var"):
            self.breadcrumb_var.set(dict(self.nav_configs).get(active_key, "RelSIA"))

    def _check_initial_config(self) -> None:
        """Verifica configuração inicial obrigatória."""
        if not self.session.is_admin:
            return
        try:
            valid, message = self.settings.validate_required_settings()
            if not valid:
                self.logger.warning(f"Configuração necessária: {message}")

                messagebox.showwarning(
                    "Configuração Necessária",
                    f"{message}\n\nPor favor, configure o sistema antes de continuar.",
                )

                self.navigate_to_tab("config")
                self._highlight_config_tab()

        except Exception as e:
            self.logger.error(f"Erro ao verificar configuração inicial: {e}")

    def _highlight_config_tab(self) -> None:
        """Destaca a aba de configurações quando necessária."""
        try:
            self._set_active_nav("config")
        except Exception as e:
            self.logger.debug(f"Erro ao destacar aba de configurações: {e}")

    def navigate_to_tab(self, tab_key: str) -> bool:
        """Navega para uma aba específica."""
        try:
            if not self.session.can_access(tab_key):
                self.logger.warning(
                    "Acesso negado à aba %s para perfil %s", tab_key, self.session.role
                )
                return False
            tab_instance = self.tabs.get(tab_key)
            if tab_instance is None:
                self.update_status("Carregando tela…")
                self.root.update_idletasks()
                tab_instance = self._create_tab(tab_key)

            if tab_instance is not None:
                self.notebook.select(tab_instance.frame)
                self._set_active_nav(tab_key)
                return True

            self.logger.warning(f"Aba não encontrada: {tab_key}")
            return False

        except Exception as e:
            self.logger.error(f"Erro ao navegar para aba {tab_key}: {e}")
            return False

    def _on_session_changed(self, session: UserSession) -> None:
        """Atualiza o cabeçalho após o administrador alterar a própria conta."""
        self.session = session
        self.user_name_var.set(self._header_user_name(session.name))
        self.user_role_var.set(session.role_label)
        self.avatar.configure(text=self._initials(session.name))

    @staticmethod
    def _header_user_name(name: str) -> str:
        clean = str(name or "Usuário")
        return clean if len(clean) <= 17 else clean[:16] + "…"

    def _confirm_logout(self) -> None:
        if not messagebox.askyesno(
            "Encerrar sessão",
            "Deseja sair desta conta e voltar para a tela de login?",
        ):
            return
        if self.on_logout is not None:
            self.on_logout()

    def shutdown(self) -> None:
        """Dá às abas a oportunidade de cancelar tarefas antes do fechamento."""
        if self._shutting_down:
            return
        self._shutting_down = True
        if self._navigation_search is not None:
            self._navigation_search.close()
        for tooltip in self._tooltips:
            tooltip.hide()
        for event, binding in self._keyboard_bindings:
            self.root.unbind(event, binding)
        if self._sidebar_after is not None:
            self.root.after_cancel(self._sidebar_after)
            self._sidebar_after = None
        if getattr(self, "_resize_binding", None):
            self.root.unbind("<Configure>", self._resize_binding)
        for tab_key, tab_instance in self.tabs.items():
            cleanup = getattr(tab_instance, "shutdown", None)
            if not callable(cleanup):
                continue
            try:
                cleanup()
            except Exception as error:
                self.logger.debug(
                    "Falha ao encerrar recursos da aba %s: %s", tab_key, error
                )

    def update_status(self, message: str, level: str = "info") -> None:
        """Atualiza a barra de status."""
        try:
            color_map = {
                "info": COLORS["primary"],
                "warning": COLORS["warning"],
                "error": COLORS["danger"],
                "success": COLORS["success"],
            }

            indicator_map = {
                "info": "Pronto",
                "warning": "⚠  Atenção",
                "error": "×  Erro",
                "success": "●  Dados atualizados",
            }

            color = color_map.get(level, COLORS["primary"])
            indicator = indicator_map.get(level, "Pronto")

            self.status_var.set(message)
            self.status_bar.configure(text_color=color)
            self.status_indicator.configure(text=indicator, text_color=color)

            self.root.update_idletasks()

        except Exception as e:
            self.logger.debug(f"Erro ao atualizar status: {e}")

    def refresh_all_tabs(self) -> None:
        """Atualiza todas as abas quando necessário."""
        try:
            for tab_key, tab_instance in self.tabs.items():
                if hasattr(tab_instance, "refresh"):
                    tab_instance.refresh()
                    self.logger.debug(f"Aba {tab_key} atualizada")

        except Exception as e:
            self.logger.error(f"Erro ao atualizar abas: {e}")

    def get_current_tab(self) -> Optional[str]:
        """Retorna a chave da aba atualmente selecionada."""
        try:
            selected_tab = self.notebook.select()
            if selected_tab:
                for tab_key, tab_instance in self.tabs.items():
                    if str(tab_instance.frame) == str(selected_tab):
                        return tab_key
            return None

        except Exception as e:
            self.logger.debug(f"Erro ao obter aba atual: {e}")
            return None

    def show_about(self) -> None:
        """Exibe informações sobre a aplicação."""
        about_text = """
Sistema de Relatórios SIA/SUS

Versão: 2.21.0
Desenvolvido para: Gestão de dados do Sistema de Informações Ambulatoriais

Funcionalidades:
• Importação de arquivos DBF do SIA
• Filtros avançados para relatórios
• Geração de relatórios em PDF
• Dashboard organizado com exportação PNG/JPG
• Cadastro de estabelecimentos
• Backup e manutenção do banco de dados

Desenvolvido com Python e Tkinter
        """

        messagebox.showinfo("Sobre o Sistema", about_text.strip())
