import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import customtkinter as ctk
from matplotlib.figure import Figure
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg

from sia_app.ui.theme import COLORS, apply_theme, FONT_FAMILY
from sia_app.ui.icons import icon
from sia_app.ui.components.design import Tooltip

from sia_app.utils.sia_mappings import (
    TIPOS_FINANCIAMENTO,
    COMPLEXIDADES,
)
from sia_app.services.dashboard_service import DashboardService
from sia_app.services.dashboard_image_exporter import DashboardImageExporter
from sia_app.ui.components.dashboard_charts import DashboardChartRenderer

class DashboardTab:
    def __init__(self, parent, db, settings, logger, on_update_status=None, on_navigate=None, session=None):
        self.parent = parent
        self.db = db
        self.settings = settings
        self.logger = logger
        self.on_update_status = on_update_status
        self.on_navigate = on_navigate
        self.session = session
        self.dashboard_service = DashboardService(db)
        self.chart_renderer = DashboardChartRenderer(COLORS)

        apply_theme()
        self.frame = ctk.CTkFrame(parent, fg_color=COLORS['bg'])

        self.competencia_inicio_var = tk.StringVar()
        self.competencia_fim_var = tk.StringVar()
        self.cnes_var = tk.StringVar()
        self.procedimento_var = tk.StringVar()

        self.tipo_financiamento_var = tk.StringVar(value="Todos")
        self.complexidade_var = tk.StringVar(value="Todas")

        self.metrica_var = tk.StringVar(value="Quantidade Produzida")
        self.top_n_var = tk.StringVar(value="10")
        self.cbo_agrupamento_var = tk.StringVar(value="CBO Geral")

        self._build_ui()

    def _build_ui(self):
        self._startup_after = None
        self._chart_after = None
        self._closed = False
        self._tooltips = []
        main = ctk.CTkScrollableFrame(self.frame, fg_color=COLORS["bg"], corner_radius=0,
                                     scrollbar_button_color="#C7D3DD")
        main.pack(fill="both", expand=True)
        header = ctk.CTkFrame(main, fg_color="transparent")
        header.pack(fill="x", padx=28, pady=(25, 20))
        header.grid_columnconfigure(0, weight=1)
        title_box = ctk.CTkFrame(header, fg_color="transparent")
        title_box.grid(row=0, column=0, sticky="ew")
        ctk.CTkLabel(title_box, text="CONTROLE DA PRODUÇÃO", font=(FONT_FAMILY, 9, "bold"),
                     text_color=COLORS["muted"]).pack(anchor="w")
        ctk.CTkLabel(title_box, text="Visão geral", font=(FONT_FAMILY, 29, "bold"),
                     text_color=COLORS["text"]).pack(anchor="w", pady=(2, 2))
        description = ctk.CTkLabel(title_box, text="Uma visão clara da produção, dos valores e das unidades de saúde.",
                                    font=(FONT_FAMILY, 13), text_color=COLORS["muted"], justify="left", anchor="w")
        description.pack(fill="x")
        title_box.bind("<Configure>", lambda event: description.configure(wraplength=max(200, event.width - 12)), add="+")
        ctk.CTkButton(header, text="Atualizar dados", image=icon("refresh", "#FFFFFF", 17),
                      compound="left", command=self.atualizar_dashboard, height=37, width=145,
                      fg_color=COLORS["primary"], hover_color=COLORS["primary_dark"], border_width=0,
                      text_color="#FFFFFF", font=(FONT_FAMILY, 12)).grid(row=0, column=1, sticky="e", padx=(12, 0), pady=(20, 0))
        self._build_filters(main)
        self._build_summary_cards(main)
        self._build_charts(main)
        self._startup_after = self.frame.after_idle(self._load_initial_data)

    def _load_initial_data(self):
        self._startup_after = None
        if not self._closed:
            self.atualizar_dashboard()

    def _build_filters(self, parent):
        filtros = ctk.CTkFrame(parent, fg_color=COLORS["card"], border_color=COLORS["border"],
                              border_width=1, corner_radius=10)
        filtros.pack(fill="x", padx=28, pady=(0, 18))
        bar = ctk.CTkFrame(filtros, fg_color="transparent")
        bar.pack(fill="x", padx=18, pady=12)
        bar.grid_columnconfigure(1, weight=1)
        ctk.CTkLabel(bar, text="", image=icon("filter", COLORS["primary"], 19), width=24).grid(row=0, column=0)
        info = ctk.CTkFrame(bar, fg_color="transparent")
        info.grid(row=0, column=1, padx=12, sticky="ew")
        ctk.CTkLabel(info, text="Filtros da consulta", font=(FONT_FAMILY, 12, "bold"),
                     text_color=COLORS["text"]).pack(anchor="w")
        self.filter_summary = tk.StringVar(value="Todos os períodos · Todos os estabelecimentos")
        self.filter_summary_label = ctk.CTkLabel(info, textvariable=self.filter_summary, font=(FONT_FAMILY, 10),
                                                 text_color=COLORS["muted"], anchor="w")
        self.filter_summary_label.pack(fill="x")
        bar.bind("<Configure>", lambda event: self.filter_summary_label.configure(wraplength=max(160, event.width - 190)), add="+")
        self.filters_button = ctk.CTkButton(bar, text="Exibir filtros", width=104, height=32,
                                           fg_color=COLORS["primary_soft"], text_color=COLORS["primary"],
                                           hover_color="#DDECE4", font=(FONT_FAMILY, 11), command=self._toggle_filters)
        self.filters_button.grid(row=0, column=2, padx=(12, 0), sticky="e")
        self.filters_body = ctk.CTkFrame(filtros, fg_color="transparent")
        self._filters_visible = False
        for column in range(4):
            self.filters_body.grid_columnconfigure(column, weight=1, uniform="filters")
        financing = ["Todos"] + [f"{key} - {value}" for key, value in TIPOS_FINANCIAMENTO.items()]
        complexity = ["Todas"] + [f"{key} - {value}" for key, value in COMPLEXIDADES.items() if key]
        fields = [
            self._field_entry(self.filters_body, "Competência inicial", self.competencia_inicio_var, 100, "AAAAMM"),
            self._field_entry(self.filters_body, "Competência final", self.competencia_fim_var, 100, "AAAAMM"),
            self._field_entry(self.filters_body, "Estabelecimento · CNES", self.cnes_var, 100),
            self._field_entry(self.filters_body, "Procedimento ou grupo", self.procedimento_var, 100),
            self._field_combo(self.filters_body, "Financiamento", self.tipo_financiamento_var, financing, 100),
            self._field_combo(self.filters_body, "Complexidade", self.complexidade_var, complexity, 100),
            self._field_combo(self.filters_body, "Métrica dos gráficos", self.metrica_var,
                              ["Quantidade Produzida", "Quantidade Aprovada", "Valor Produzido", "Valor Aprovado"], 100),
            self._field_entry(self.filters_body, "Quantidade no ranking", self.top_n_var, 100),
        ]
        for index, field in enumerate(fields):
            field.grid(row=index // 4, column=index % 4, sticky="ew", padx=6, pady=(0, 14))
        actions = ctk.CTkFrame(self.filters_body, fg_color="transparent")
        actions.grid(row=2, column=0, columnspan=4, sticky="e", padx=6)
        ctk.CTkButton(actions, text="Limpar filtros", width=110, height=34, fg_color="transparent",
                      hover_color=COLORS["primary_soft"], text_color=COLORS["muted"],
                      command=self.limpar_filtros).pack(side="left", padx=(0, 10))
        ctk.CTkButton(actions, text="Aplicar filtros", width=125, height=34,
                      command=self.atualizar_dashboard).pack(side="left")

    def _toggle_filters(self):
        self._filters_visible = not self._filters_visible
        if self._filters_visible:
            self.filters_body.pack(fill="x", padx=12, pady=(2, 18))
        else:
            self.filters_body.pack_forget()
        self.filters_button.configure(text="Ocultar filtros" if self._filters_visible else "Exibir filtros")

    def _field_entry(self, parent, label, variable, width=140, placeholder=""):
        box = ctk.CTkFrame(parent, fg_color="transparent")
        ctk.CTkLabel(
            box,
            text=label,
            font=(FONT_FAMILY, 12, "bold"),
            text_color=COLORS["text"],
            anchor="w"
        ).pack(anchor="w", pady=(0, 4))
        ctk.CTkEntry(
            box,
            textvariable=variable,
            width=width,
            height=36,
            corner_radius=7,
            border_color=COLORS["border"],
            placeholder_text=placeholder,
            font=(FONT_FAMILY, 12)
        ).pack(fill="x")
        return box

    def _field_combo(self, parent, label, variable, values, width=180):
        box = ctk.CTkFrame(parent, fg_color="transparent")
        ctk.CTkLabel(
            box,
            text=label,
            font=(FONT_FAMILY, 12, "bold"),
            text_color=COLORS["text"],
            anchor="w"
        ).pack(anchor="w", pady=(0, 4))
        ctk.CTkComboBox(
            box,
            variable=variable,
            values=values,
            width=width,
            height=36,
            corner_radius=7,
            border_color=COLORS["border"],
            button_color="#EFF5F2",
            button_hover_color="#D6E7DE",
            dropdown_fg_color="#FFFFFF",
            font=(FONT_FAMILY, 12)
        ).pack(fill="x")
        return box

    def _build_summary_cards(self, parent):
        self.card_vars = {
            "qtd_produzida": tk.StringVar(value="—"), "qtd_aprovada": tk.StringVar(value="—"),
            "valor_produzido": tk.StringVar(value="—"), "valor_aprovado": tk.StringVar(value="—"),
            "procedimentos": tk.StringVar(value="—"), "estabelecimentos": tk.StringVar(value="—"),
        }
        self.approval_var = tk.StringVar(value="—")
        self.approval_hint = tk.StringVar(value="Aprovada ÷ produzida")
        self.production_context = tk.StringVar(value="Carregando os indicadores da consulta…")
        self.hero = ctk.CTkFrame(parent, fg_color="#F0F7F3", border_color="#D6E6DD", border_width=1, corner_radius=12)
        self.hero.pack(fill="x", padx=28, pady=(0, 18))
        self.hero.grid_columnconfigure(0, weight=3)
        self.hero.grid_columnconfigure(1, weight=2)
        self.hero_main = ctk.CTkFrame(self.hero, fg_color="transparent")
        self.hero_main.grid(row=0, column=0, sticky="nsew", padx=24, pady=20)
        ctk.CTkLabel(self.hero_main, text="PANORAMA DA PRODUÇÃO", font=(FONT_FAMILY, 10, "bold"),
                     text_color=COLORS["primary"]).pack(anchor="w")
        numbers = ctk.CTkFrame(self.hero_main, fg_color="transparent")
        numbers.pack(fill="x", pady=(12, 8))
        for key, title in (("qtd_produzida", "Quantidade produzida"), ("qtd_aprovada", "Quantidade aprovada")):
            group = ctk.CTkFrame(numbers, fg_color="transparent")
            group.pack(side="left", fill="x", expand=True)
            ctk.CTkLabel(group, text=title, font=(FONT_FAMILY, 12), text_color=COLORS["muted"]).pack(anchor="w")
            ctk.CTkLabel(group, textvariable=self.card_vars[key], font=(FONT_FAMILY, 32, "bold"),
                         text_color=COLORS["text"]).pack(anchor="w", pady=(2, 0))
        ctk.CTkLabel(self.hero_main, textvariable=self.production_context, font=(FONT_FAMILY, 11),
                     text_color=COLORS["muted"]).pack(anchor="w")
        self.empty_action = ctk.CTkButton(self.hero_main, text="Importar arquivos", height=32, width=145,
                                          image=icon("upload", COLORS["primary"], 16),
                                          fg_color="#DDEEE4", hover_color="#D0E6D9", text_color=COLORS["primary"],
                                          command=self._empty_action, font=(FONT_FAMILY, 12))
        self.hero_ratio = ctk.CTkFrame(self.hero, fg_color="#E7F2EB", corner_radius=10)
        self.hero_ratio.grid(row=0, column=1, sticky="nsew", padx=(0, 14), pady=14)
        ctk.CTkLabel(self.hero_ratio, text="Aprovação por quantidade", font=(FONT_FAMILY, 12),
                     text_color=COLORS["primary_dark"]).pack(anchor="w", padx=20, pady=(16, 0))
        self.approval_label = ctk.CTkLabel(self.hero_ratio, textvariable=self.approval_var,
                                          font=(FONT_FAMILY, 34, "bold"), text_color=COLORS["primary_dark"])
        self.approval_label.pack(anchor="w", padx=20, pady=(1, 3))
        self.approval_progress = ctk.CTkProgressBar(self.hero_ratio, height=6, fg_color="#CCDFD2",
                                                   progress_color=COLORS["primary"], corner_radius=3)
        self.approval_progress.set(0)
        self.approval_progress.pack(fill="x", padx=20)
        ctk.CTkLabel(self.hero_ratio, textvariable=self.approval_hint, font=(FONT_FAMILY, 10),
                     text_color=COLORS["primary_dark"]).pack(anchor="w", padx=20, pady=(8, 12))

        self.cards_frame = ctk.CTkFrame(parent, fg_color="transparent")
        self.cards_frame.pack(fill="x", padx=22, pady=(0, 12))
        self.metric_cards = []
        self._summary_columns = None
        cards = [("Valor produzido", "valor_produzido", "money", COLORS["purple"], "#F1EFF8", "Total apresentado na consulta"),
                 ("Valor aprovado", "valor_aprovado", "check", COLORS["primary"], "#ECF5EF", "Total aprovado na consulta"),
                 ("Estabelecimentos", "estabelecimentos", "building", COLORS["info"], "#EDF3FA", "Unidades com produção")]
        for title, key, symbol, color, soft, caption in cards:
            card = ctk.CTkFrame(self.cards_frame, fg_color=COLORS["card"], border_color=COLORS["border"],
                                border_width=1, corner_radius=10)
            heading = ctk.CTkFrame(card, fg_color="transparent")
            heading.pack(fill="x", padx=18, pady=(14, 0))
            ctk.CTkLabel(heading, text=title, font=(FONT_FAMILY, 12), text_color=COLORS["muted"]).pack(side="left")
            ctk.CTkLabel(heading, text="", image=icon(symbol, color, 18), fg_color=soft, corner_radius=7,
                         width=31, height=31).pack(side="right")
            ctk.CTkLabel(card, textvariable=self.card_vars[key], font=(FONT_FAMILY, 26, "bold"),
                         text_color=COLORS["text"], anchor="w").pack(fill="x", padx=18, pady=(1, 0))
            ctk.CTkLabel(card, text=caption, font=(FONT_FAMILY, 11), text_color=COLORS["muted"],
                         anchor="w").pack(fill="x", padx=18, pady=(0, 15))
            self.metric_cards.append(card)
        self.cards_frame.bind("<Configure>", self._layout_summary, add="+")

    def _layout_summary(self, event):
        columns = 3 if event.width >= 990 else 2
        if columns == self._summary_columns:
            return
        self._summary_columns = columns
        for index in range(3):
            self.cards_frame.grid_columnconfigure(index, weight=1 if index < columns else 0,
                                                   uniform="metrics" if index < columns else "")
        for index, card in enumerate(self.metric_cards):
            card.grid(row=index // columns, column=index % columns, sticky="nsew", padx=6, pady=(0, 12))
        if columns == 3:
            self.hero_main.grid(row=0, column=0, columnspan=1, padx=24, pady=20)
            self.hero_ratio.grid(row=0, column=1, columnspan=1, sticky="nsew", padx=(0, 14), pady=14)
        else:
            self.hero_main.grid(row=0, column=0, columnspan=2, padx=24, pady=20)
            self.hero_ratio.grid(row=1, column=0, columnspan=2, sticky="nsew", padx=14, pady=(0, 14))

    def _empty_action(self):
        if self.session is not None and self.session.can_access("file_upload") and self.on_navigate:
            self.on_navigate("file_upload")
        elif not self._filters_visible:
            self._toggle_filters()

    def _build_charts(self, parent):
        chart_card = ctk.CTkFrame(
            parent,
            fg_color=COLORS["card"],
            border_color=COLORS["border"],
            border_width=1,
            corner_radius=12
        )
        chart_card.pack(fill="both", expand=True, padx=28, pady=(0, 24))
        ctk.CTkLabel(chart_card, text="Análise da produção", font=(FONT_FAMILY, 18, "bold"),
                     text_color=COLORS["text"]).pack(anchor="w", padx=20, pady=(16, 2))

        # Guarda qual aba está ativa
        self.active_chart_tab = "grupos"
        self.chart_tab_buttons = {}
        self.chart_tab_underlines = {}
        self.chart_tab_items = {}

        # Barra superior em uma única linha, com rolagem horizontal por setas.
        tabs_bar = ctk.CTkFrame(
            chart_card,
            fg_color=COLORS["card"],
            height=54,
            corner_radius=12
        )
        tabs_bar.pack(fill="x", padx=0, pady=0)
        tabs_bar.pack_propagate(False)

        tabs_right = ctk.CTkFrame(tabs_bar, fg_color="transparent")
        tabs_right.pack(side="right", fill="y", padx=(4, 10))

        self.chart_tabs_next_button = ctk.CTkButton(
            tabs_right,
            text="",
            image=icon("chevron_right", COLORS["primary"], 15),
            width=32,
            height=32,
            fg_color="transparent",
            hover_color="#EFF5F2",
            text_color=COLORS["primary"],
            font=(FONT_FAMILY, 22, "bold"),
            corner_radius=6,
            command=lambda: self._scroll_chart_tabs(1),
        )
        self.chart_tabs_next_button.pack(side="left", pady=11, padx=(0, 4))
        self._tooltips.append(Tooltip(self.chart_tabs_next_button, "Mais gráficos"))

        # Exporta exatamente o gráfico da aba ativa.
        ctk.CTkButton(
            tabs_right,
            text="Salvar gráfico",
            image=icon("download", COLORS["muted"], 16),
            compound="left",
            width=120,
            height=34,
            fg_color="transparent",
            hover_color="#EFF5F2",
            text_color=COLORS["muted"],
            font=(FONT_FAMILY, 10),
            corner_radius=6,
            command=self._export_active_chart,
        ).pack(side="left", pady=10)

        self.chart_tabs_prev_button = ctk.CTkButton(
            tabs_bar,
            text="",
            image=icon("chevron_left", COLORS["primary"], 15),
            width=32,
            height=32,
            fg_color="transparent",
            hover_color="#EFF5F2",
            text_color=COLORS["primary"],
            font=(FONT_FAMILY, 22, "bold"),
            corner_radius=6,
            command=lambda: self._scroll_chart_tabs(-1),
        )
        self.chart_tabs_prev_button.pack(side="left", pady=11, padx=(10, 4))
        self._tooltips.append(Tooltip(self.chart_tabs_prev_button, "Gráficos anteriores"))

        self.chart_tabs_canvas = tk.Canvas(
            tabs_bar,
            height=52,
            bg=COLORS["card"],
            highlightthickness=0,
            bd=0,
            xscrollincrement=190,
            xscrollcommand=self._on_chart_tabs_xview,
        )
        self.chart_tabs_canvas.pack(side="left", fill="both", expand=True)

        self.chart_tabs_inner = ctk.CTkFrame(
            self.chart_tabs_canvas,
            height=52,
            fg_color="transparent",
        )
        self.chart_tabs_window = self.chart_tabs_canvas.create_window(
            (0, 0),
            window=self.chart_tabs_inner,
            anchor="nw",
        )
        self.chart_tabs_inner.bind("<Configure>", self._sync_chart_tabs_scrollregion)
        self.chart_tabs_canvas.bind("<Configure>", self._on_chart_tabs_canvas_resize)

        tabs = [
            ("grupos", "Produção por Grupo"),
            ("estab", "Top Estabelecimentos"),
            ("meses", "Evolução Mensal"),
            ("diferencas", "Diferença Prod. x Aprov."),
            ("cbo", "Estatística por CBO"),
            ("fin_comp", "Financ. × Competência"),
            ("fin_estab", "Financ. × Estabelecimento"),
        ]

        for tab_key, label in tabs:
            tab_width = max(168, min(224, len(label) * 8 + 34))
            tab_item = ctk.CTkFrame(
                self.chart_tabs_inner,
                width=tab_width,
                height=52,
                fg_color="transparent",
            )
            tab_item.pack(side="left", fill="y", padx=(0, 6))
            tab_item.pack_propagate(False)

            btn = ctk.CTkButton(
                tab_item,
                text=label,
                width=10,
                height=36,
                fg_color="transparent",
                hover_color="#EFF5F2",
                text_color=COLORS["muted"],
                font=(FONT_FAMILY, 11),
                corner_radius=0,
                command=lambda key=tab_key: self._select_chart_tab(key)
            )
            btn.pack(side="top", fill="both", expand=True, pady=(3, 0))

            underline = ctk.CTkFrame(
                tab_item,
                height=3,
                fg_color="transparent",
                corner_radius=2
            )
            underline.pack(side="bottom", fill="x")

            self.chart_tab_buttons[tab_key] = btn
            self.chart_tab_underlines[tab_key] = underline
            self.chart_tab_items[tab_key] = tab_item

        # Linha divisória abaixo da barra
        ctk.CTkFrame(
            chart_card,
            fg_color=COLORS["border"],
            height=1
        ).pack(fill="x")

        # Área de conteúdo das abas
        self.chart_content = ctk.CTkFrame(
            chart_card,
            fg_color=COLORS["card"]
        )
        self.chart_content.pack(fill="both", expand=True, padx=8, pady=(3, 8))

        # Frames internos de cada aba
        self.tab_grupos = ctk.CTkFrame(self.chart_content, fg_color=COLORS["card"])
        self.tab_estab = ctk.CTkFrame(self.chart_content, fg_color=COLORS["card"])
        self.tab_meses = ctk.CTkFrame(self.chart_content, fg_color=COLORS["card"])
        self.tab_diferencas = ctk.CTkFrame(self.chart_content, fg_color=COLORS["card"])
        self.tab_cbo = ctk.CTkFrame(self.chart_content, fg_color=COLORS["card"])
        self.tab_fin_comp = ctk.CTkFrame(self.chart_content, fg_color=COLORS["card"])
        self.tab_fin_estab = ctk.CTkFrame(self.chart_content, fg_color=COLORS["card"])

        self.chart_frames = {
            "grupos": self.tab_grupos,
            "estab": self.tab_estab,
            "meses": self.tab_meses,
            "diferencas": self.tab_diferencas,
            "cbo": self.tab_cbo,
            "fin_comp": self.tab_fin_comp,
            "fin_estab": self.tab_fin_estab,
        }

        # Cria os gráficos
        self.canvas_grupos = self._create_canvas(self.tab_grupos)
        self.canvas_estab = self._create_canvas(self.tab_estab)
        self.canvas_meses = self._create_canvas(self.tab_meses)
        self.canvas_diferencas = self._create_canvas(self.tab_diferencas)
        self.canvas_fin_comp = self._create_canvas(self.tab_fin_comp)
        self.canvas_fin_estab = self._create_canvas(self.tab_fin_estab)

        # Filtros específicos da aba CBO
        cbo_filtros = ctk.CTkFrame(self.tab_cbo, fg_color="transparent")
        cbo_filtros.pack(fill="x", padx=8, pady=(8, 0))

        ctk.CTkLabel(
            cbo_filtros,
            text="Visualizar:",
            font=(FONT_FAMILY, 12, "bold"),
            text_color=COLORS["text"]
        ).pack(side="left", padx=(0, 8))

        self.cbo_agrupamento_combo = ctk.CTkComboBox(
            cbo_filtros,
            variable=self.cbo_agrupamento_var,
            values=["CBO Geral", "CBO por Estabelecimento", "CBO por Competência"],
            width=230,
            height=34,
            border_color=COLORS["border"]
        )
        self.cbo_agrupamento_combo.pack(side="left", padx=(0, 10))

        ctk.CTkButton(
            cbo_filtros,
            text="Atualizar gráfico CBO",
            command=self._atualizar_grafico_cbo,
            height=34,
            width=160,
            fg_color=COLORS["primary"],
            hover_color=COLORS["primary_dark"]
        ).pack(side="left")

        self.canvas_cbo = self._create_canvas(self.tab_cbo)

        self.chart_canvases = {
            "grupos": self.canvas_grupos,
            "estab": self.canvas_estab,
            "meses": self.canvas_meses,
            "diferencas": self.canvas_diferencas,
            "cbo": self.canvas_cbo,
            "fin_comp": self.canvas_fin_comp,
            "fin_estab": self.canvas_fin_estab,
        }

        # Mostra a primeira aba
        self._select_chart_tab("grupos")
        
    def _select_chart_tab(self, tab_key):
        self.active_chart_tab = tab_key

        # Esconde todos os frames
        for frame in self.chart_frames.values():
            frame.pack_forget()

        # Mostra somente o frame selecionado
        self.chart_frames[tab_key].pack(fill="both", expand=True)

        self._update_chart_tabs_style()
        if self._chart_after is not None:
            self.chart_tabs_canvas.after_cancel(self._chart_after)
        self._chart_after = self.chart_tabs_canvas.after_idle(self._ensure_active_chart_tab_visible)


    def _update_chart_tabs_style(self):
        for tab_key, btn in self.chart_tab_buttons.items():
            ativo = tab_key == self.active_chart_tab

            btn.configure(
                text_color=COLORS["primary"] if ativo else COLORS["muted"],
                font=(FONT_FAMILY, 12, "bold" if ativo else "normal"),
                fg_color="transparent",
                hover_color="#EFF5F2"
            )

            self.chart_tab_underlines[tab_key].configure(
                fg_color=COLORS["primary"] if ativo else "transparent"
            )

    def _sync_chart_tabs_scrollregion(self, _event=None):
        bbox = self.chart_tabs_canvas.bbox("all")
        if bbox:
            self.chart_tabs_canvas.configure(scrollregion=bbox)
        self._update_chart_tab_arrows()

    def _on_chart_tabs_canvas_resize(self, _event=None):
        self._update_chart_tab_arrows()
        self._ensure_active_chart_tab_visible()

    def _on_chart_tabs_xview(self, first, last):
        self._update_chart_tab_arrows(float(first), float(last))

    def _update_chart_tab_arrows(self, first=None, last=None):
        if first is None or last is None:
            first, last = self.chart_tabs_canvas.xview()
        self.chart_tabs_prev_button.configure(
            state="normal" if first > 0.001 else "disabled",
            image=icon("chevron_left", COLORS["primary"] if first > 0.001 else "#B9C7CE", 15),
        )
        self.chart_tabs_next_button.configure(
            state="normal" if last < 0.999 else "disabled",
            image=icon("chevron_right", COLORS["primary"] if last < 0.999 else "#B9C7CE", 15),
        )

    def _scroll_chart_tabs(self, direction):
        self.chart_tabs_canvas.xview_scroll(direction, "units")
        self._update_chart_tab_arrows()

    def _ensure_active_chart_tab_visible(self):
        self._chart_after = None
        if self._closed:
            return
        item = self.chart_tab_items.get(self.active_chart_tab)
        bbox = self.chart_tabs_canvas.bbox("all")
        if item is None or not bbox:
            return
        total_width = max(1, bbox[2] - bbox[0])
        viewport_width = max(1, self.chart_tabs_canvas.winfo_width())
        visible_start = self.chart_tabs_canvas.canvasx(0)
        visible_end = visible_start + viewport_width
        item_start = item.winfo_x()
        item_end = item_start + item.winfo_width()
        if item_start < visible_start:
            self.chart_tabs_canvas.xview_moveto(item_start / total_width)
        elif item_end > visible_end:
            target = max(0, item_end - viewport_width)
            self.chart_tabs_canvas.xview_moveto(target / total_width)
        self._update_chart_tab_arrows()

    def _create_canvas(self, parent):
        """Cria uma área Matplotlib embutida no Tkinter."""
        container = ctk.CTkFrame(parent, fg_color=COLORS["card"])
        container.pack(fill="both", expand=True, padx=4, pady=(2, 4))

        fig = Figure(figsize=(9, 4.2), dpi=100, facecolor=COLORS["card"])
        ax = fig.add_subplot(111)
        ax.set_facecolor(COLORS["card"])

        canvas = FigureCanvasTkAgg(fig, master=container)
        widget = canvas.get_tk_widget()
        widget.configure(background=COLORS["card"], highlightthickness=0)
        widget.pack(fill="both", expand=True)

        return {"container": container, "fig": fig, "ax": ax, "canvas": canvas}

    def limpar_filtros(self):
        self.competencia_inicio_var.set("")
        self.competencia_fim_var.set("")
        self.cnes_var.set("")
        self.procedimento_var.set("")
        self.tipo_financiamento_var.set("Todos")
        self.complexidade_var.set("Todas")
        self.metrica_var.set("Quantidade Produzida")
        self.top_n_var.set("10")
        self.cbo_agrupamento_var.set("CBO Geral")

    def atualizar_dashboard(self):
        try:
            metrica_label = self.metrica_var.get()
            top_n = DashboardService.normalizar_top_n(self.top_n_var.get())
            modo_cbo = self.cbo_agrupamento_var.get().strip()
            dados = self.dashboard_service.carregar(
                self._collect_filters(),
                metrica_label,
                top_n,
                modo_cbo,
            )
            self._update_card_values(dados.cards)
            self.filter_summary.set(self._filter_description())

            self._draw_bar_chart(
                self.canvas_grupos,
                dados.grupos,
                f"{metrica_label} por Grupo de Procedimento",
                metrica_label
            )

            self._draw_bar_chart(
                self.canvas_estab,
                dados.estabelecimentos,
                f"Top {top_n} Estabelecimentos - {metrica_label}",
                metrica_label
            )

            self._draw_line_chart(
                self.canvas_meses,
                dados.competencias,
                f"Evolução Mensal - {metrica_label}",
                metrica_label
            )
            
            self._draw_bar_chart(
                self.canvas_cbo,
                dados.cbo,
                f"Quantidade Produzida - {modo_cbo}",
                "Quantidade Produzida",
                is_value=False,
            )

            if self._is_valor():
                titulo_diferenca = "Total da Diferença entre Valor Produzido e Valor Aprovado por Competência"
                eixo_diferenca = "Diferença de Valor"
            else:
                titulo_diferenca = "Total da Diferença entre Quantidade Produzida e Quantidade Aprovada por Competência"
                eixo_diferenca = "Diferença de Quantidade"

            self._draw_bar_chart(
                self.canvas_diferencas,
                dados.diferencas,
                titulo_diferenca,
                eixo_diferenca
            )

            self.chart_renderer.draw_stacked_bar(
                self.canvas_fin_comp,
                dados.financiamento_competencias,
                f"{metrica_label} por Tipo de Financiamento e Competência",
                metrica_label,
                is_value=self._is_valor(),
                competence_labels=True,
                legend_at_top=True,
            )

            self.chart_renderer.draw_stacked_bar(
                self.canvas_fin_estab,
                dados.financiamento_estabelecimentos,
                f"Top {top_n} Estabelecimentos por Tipo de Financiamento",
                metrica_label,
                is_value=self._is_valor(),
            )
            
            if self.on_update_status:
                self.on_update_status()

            self.logger.info("Dashboard atualizado com sucesso")

        except Exception as e:
            self.logger.error(f"Erro ao atualizar dashboard: {e}")
            messagebox.showerror("Erro", f"Erro ao atualizar dashboard:\n{e}")

    def _atualizar_grafico_cbo(self):
        """Atualiza somente a aba CBO, sem redesenhar os demais canvases."""
        try:
            top_n = DashboardService.normalizar_top_n(self.top_n_var.get())
            modo_cbo = self.cbo_agrupamento_var.get().strip()
            dados_cbo = self.dashboard_service.carregar_cbo(
                self._collect_filters(),
                top_n,
                modo_cbo,
            )
            self._draw_bar_chart(
                self.canvas_cbo,
                dados_cbo,
                f"Quantidade Produzida - {modo_cbo}",
                "Quantidade Produzida",
                is_value=False,
            )
            self.logger.info("Gráfico CBO atualizado com sucesso")
        except Exception as exc:
            self.logger.error(f"Erro ao atualizar gráfico CBO: {exc}")
            messagebox.showerror(
                "Erro",
                f"Erro ao atualizar gráfico CBO:\n{exc}",
            )

    def _collect_filters(self):
        """Converte o estado dos controles em dados simples para o serviço."""
        return {
            "competencia_inicio": self.competencia_inicio_var.get(),
            "competencia_fim": self.competencia_fim_var.get(),
            "cnes": self.cnes_var.get(),
            "procedimento": self.procedimento_var.get(),
            "tipo_financiamento": self.tipo_financiamento_var.get(),
            "complexidade": self.complexidade_var.get(),
        }

    def _update_card_values(self, cards):
        for key in ("qtd_produzida", "qtd_aprovada", "procedimentos", "estabelecimentos"):
            self.card_vars[key].set(self._fmt_int(cards.get(key)))
        for key in ("valor_produzido", "valor_aprovado"):
            self.card_vars[key].set(self._fmt_money(cards.get(key)))
        produced = float(cards.get("qtd_produzida") or 0)
        approved = float(cards.get("qtd_aprovada") or 0)
        if produced > 0:
            rate = approved / produced
            self.approval_var.set(f"{rate * 100:.1f}%".replace(".", ","))
            self.approval_progress.set(max(0, min(1, rate)))
            self.approval_hint.set(f"Diferença de quantidades: {self._fmt_int(produced - approved)}")
        else:
            self.approval_var.set("—")
            self.approval_progress.set(0)
            self.approval_hint.set("Sem quantidade produzida nesta consulta")
        procedures = int(cards.get("procedimentos") or 0)
        if procedures:
            self.production_context.set(f"{self._fmt_int(procedures)} procedimentos distintos na consulta")
            self.empty_action.pack_forget()
        else:
            self.production_context.set("Nenhuma produção encontrada. Importe arquivos ou ajuste os filtros.")
            can_import = self.session is not None and self.session.can_access("file_upload") and self.on_navigate
            self.empty_action.configure(text="Importar arquivos" if can_import else "Exibir filtros",
                                        image=icon("upload" if can_import else "filter", COLORS["primary"], 16))
            self.empty_action.pack(anchor="w", pady=(12, 0))

    @staticmethod
    def _display_competence(value):
        value = value.strip()
        if len(value) == 6 and value.isdigit() and 1 <= int(value[4:]) <= 12:
            return f"{value[4:]}/{value[:4]}"
        return value

    def _filter_description(self):
        start = self._display_competence(self.competencia_inicio_var.get())
        end = self._display_competence(self.competencia_fim_var.get())
        parts = [f"{start or 'Início'} a {end or 'atual'}" if start or end else "Todos os períodos"]
        cnes = self.cnes_var.get().strip()
        parts.append(f"CNES {cnes}" if cnes else "Todos os estabelecimentos")
        procedure = self.procedimento_var.get().strip()
        if procedure:
            parts.append(f"Procedimento {procedure}")
        financing = self.tipo_financiamento_var.get()
        if financing != "Todos":
            parts.append(financing)
        complexity = self.complexidade_var.get()
        if complexity != "Todas":
            parts.append(complexity)
        if self.metrica_var.get() != "Quantidade Produzida":
            parts.append(self.metrica_var.get())
        if self.top_n_var.get().strip() != "10":
            parts.append(f"Top {DashboardService.normalizar_top_n(self.top_n_var.get())}")
        return " · ".join(parts)


    def _is_valor(self):
        return DashboardService.is_value_metric(self.metrica_var.get())

    def _draw_bar_chart(self, canvas_info, dados, titulo, eixo_label, is_value=None):
        self.chart_renderer.draw_bar(
            canvas_info,
            dados,
            titulo,
            eixo_label,
            is_value=self._is_valor() if is_value is None else is_value,
        )

    def _draw_line_chart(self, canvas_info, dados, titulo, eixo_label):
        self.chart_renderer.draw_line(
            canvas_info,
            dados,
            titulo,
            eixo_label,
            is_value=self._is_valor(),
        )

    def _export_active_chart(self):
        canvas_info = self.chart_canvases.get(self.active_chart_tab)
        if not canvas_info:
            messagebox.showwarning("Exportar gráfico", "Selecione uma aba de gráfico.")
            return

        names = {
            "grupos": "producao_por_grupo",
            "estab": "top_estabelecimentos",
            "meses": "evolucao_mensal",
            "diferencas": "diferenca_produzido_aprovado",
            "cbo": "estatistica_cbo",
            "fin_comp": "financiamento_por_competencia",
            "fin_estab": "financiamento_por_estabelecimento",
        }
        destination = filedialog.asksaveasfilename(
            title="Salvar gráfico",
            defaultextension=".png",
            initialfile=f"dashboard_{names.get(self.active_chart_tab, 'grafico')}.png",
            filetypes=[
                ("Imagem PNG", "*.png"),
                ("Imagem JPEG", "*.jpg *.jpeg"),
            ],
        )
        if not destination:
            return

        try:
            saved = DashboardImageExporter.save(canvas_info["fig"], destination)
            messagebox.showinfo(
                "Gráfico exportado",
                f"Imagem salva com sucesso em:\n{saved}",
            )
        except Exception as exc:
            self.logger.error(f"Erro ao exportar gráfico: {exc}")
            messagebox.showerror("Erro", f"Não foi possível salvar o gráfico:\n{exc}")

    def _fmt_int(self, value):
        try:
            return f"{int(float(value or 0)):,}".replace(",", ".")
        except:
            return "0"

    def _fmt_money(self, value):
        try:
            v = float(value or 0)
            s = f"{v:,.2f}"
            s = s.replace(",", "X").replace(".", ",").replace("X", ".")
            return f"R$ {s}"
        except:
            return "R$ 0,00"
            


    def shutdown(self):
        """Cancela desenhos pendentes antes de fechar ou trocar de usuário."""
        self._closed = True
        for tooltip in self._tooltips:
            tooltip.hide()
        for widget, callback in ((self.frame, self._startup_after), (self.chart_tabs_canvas, self._chart_after)):
            if callback is not None:
                widget.after_cancel(callback)
        self._startup_after = self._chart_after = None
        for info in self.chart_canvases.values():
            canvas = info["canvas"]
            for attribute in ("_idle_draw_id", "_event_loop_id"):
                callback = getattr(canvas, attribute, None)
                if callback:
                    canvas.get_tk_widget().after_cancel(callback)
                    setattr(canvas, attribute, None)
