import tkinter as tk
from tkinter import ttk, messagebox
import customtkinter as ctk
from typing import Any, Dict
import logging
from sia_app.utils.sia_mappings import (TIPOS_FINANCIAMENTO, COMPLEXIDADES)
from sia_app.services.filter_service import FilterService
from sia_app.ui.components.filter_dialogs import FilterDialogs

from sia_app.ui.theme import COLORS, apply_theme, FONT_FAMILY

class FiltersTab:
    """
    Aba de filtros para relatórios do sistema SIA/SUS com interface moderna.
    """
    
    def __init__(self, parent, db, settings, logger: logging.Logger):
        """
        Inicializa a aba de filtros.
        
        Args:
            parent: Widget pai
            db: Conexão com banco de dados
            settings: Gerenciador de configurações
            logger: Instância de logger
        """
        self.parent = parent
        self.db = db
        self.settings = settings
        self.logger = logger
        self.filter_service = FilterService(db)
        
        apply_theme()

        self.frame = ctk.CTkFrame(parent, fg_color=COLORS["bg"])
        self.filter_dialogs = FilterDialogs(self.frame, COLORS)
        self._setup_ui()
        self._load_initial_data()

    def _setup_ui(self) -> None:
        """Configura a interface do usuário de forma organizada."""
        # Container principal
        main_frame = ctk.CTkScrollableFrame(self.frame, fg_color=COLORS["bg"], corner_radius=0)
        main_frame.pack(fill="both", expand=True)
        
        # Título
        self._create_title_section(main_frame)
        
        # Filtros principais
        self._create_filters_section(main_frame)
        
        # Opções de relatório
        self._create_report_options_section(main_frame)
        
        # Controles de ação
        self._create_action_section(main_frame)
        
        # Visualização rápida
        self._create_preview_section(main_frame)
        
        # Status
        self._create_status_section(main_frame)

    def _create_title_section(self, parent) -> None:
        """Cria a seção de título."""
        header = ctk.CTkFrame(parent, fg_color="transparent")
        header.pack(fill="x", padx=18, pady=(18, 8))

        ctk.CTkLabel(
            header,
            text="Filtros para Relatórios",
            font=(FONT_FAMILY, 22, "bold"),
            text_color=COLORS["text"],
            anchor="center"
        ).pack(anchor="center")

        ctk.CTkLabel(
            header,
            text="Configure os filtros que serão utilizados nos relatórios do SIA/SUS",
            font=(FONT_FAMILY, 12),
            text_color=COLORS["muted"],
            anchor="center"
        ).pack(anchor="center", pady=(2, 0))

    def _create_filters_section(self, parent) -> None:
        """Cria a seção moderna de filtros principais."""
        filters_frame = ctk.CTkFrame(
            parent,
            fg_color=COLORS["card"],
            border_color=COLORS["border"],
            border_width=1,
            corner_radius=12
        )
        filters_frame.pack(fill="x", padx=18, pady=(8, 14))

        ctk.CTkLabel(
            filters_frame,
            text="Filtros Principais",
            font=(FONT_FAMILY, 13, "bold"),
            text_color=COLORS["text"]
        ).pack(anchor="w", padx=18, pady=(14, 8))

        content = ctk.CTkFrame(filters_frame, fg_color="transparent")
        content.pack(fill="x", padx=18, pady=(4, 18))

        content.grid_columnconfigure(1, weight=1)

        self._create_cnes_filter(content, 0)
        self._create_procedure_filter(content, 1)
        self._create_competence_filter(content, 2)
        
    def _create_cnes_filter(self, parent, row: int) -> None:
        """Cria o filtro por CNES."""
        ctk.CTkLabel(
            parent,
            text="CNES:",
            font=(FONT_FAMILY, 12, "bold"),
            text_color=COLORS["text"],
            width=170,
            anchor="w"
        ).grid(row=row, column=0, sticky="w", pady=8, padx=(0, 12))

        self.cnes_entry = ctk.CTkEntry(
            parent,
            height=36,
            corner_radius=7,
            border_color=COLORS["border"],
            fg_color="#FFFFFF",
            text_color=COLORS["text"],
            placeholder_text="Digite os CNES separados por vírgula",
            font=(FONT_FAMILY, 12)
        )
        self.cnes_entry.grid(row=row, column=1, sticky="ew", pady=8)

        self._create_tooltip(
            self.cnes_entry,
            "Digite os códigos CNES separados por vírgula\nExemplo: 1234567, 7654321, 5555555"
        )
        
    def _create_procedure_filter(self, parent, row: int) -> None:
        """Cria o filtro por procedimentos."""
        ctk.CTkLabel(
            parent,
            text="Procedimento:",
            font=(FONT_FAMILY, 12, "bold"),
            text_color=COLORS["text"],
            width=170,
            anchor="w"
        ).grid(row=row, column=0, sticky="w", pady=8, padx=(0, 12))

        proc_container = ctk.CTkFrame(parent, fg_color="transparent")
        proc_container.grid(row=row, column=1, sticky="ew", pady=8)
        proc_container.grid_columnconfigure(0, weight=1)

        self.procedure_entry = ctk.CTkEntry(
            proc_container,
            height=36,
            corner_radius=7,
            border_color=COLORS["border"],
            fg_color="#FFFFFF",
            text_color=COLORS["text"],
            placeholder_text="Digite o código do procedimento, grupo, subgrupo ou forma",
            font=(FONT_FAMILY, 12)
        )
        self.procedure_entry.grid(row=0, column=0, sticky="ew", padx=(0, 8))

        ctk.CTkButton(
            proc_container,
            text="❓ Ajuda",
            command=self._show_procedure_help,
            height=36,
            width=90,
            corner_radius=7,
            fg_color="#FFFFFF",
            hover_color=COLORS["primary_soft"],
            border_color=COLORS["border"],
            border_width=1,
            text_color=COLORS["text"],
            font=(FONT_FAMILY, 12, "bold")
        ).grid(row=0, column=1, padx=(0, 8))

        ctk.CTkButton(
            proc_container,
            text="📊 Grupos",
            command=self._show_common_groups,
            height=36,
            width=90,
            corner_radius=7,
            fg_color="#FFFFFF",
            hover_color=COLORS["primary_soft"],
            border_color=COLORS["primary"],
            border_width=1,
            text_color=COLORS["primary"],
            font=(FONT_FAMILY, 12, "bold")
        ).grid(row=0, column=2)

        self._create_tooltip(
            self.procedure_entry,
            "• 2 dígitos = Grupo\n• 4 dígitos = Subgrupo\n• 6 dígitos = Forma\n• Código completo = Procedimento único"
        )

    def _create_competence_filter(self, parent, row: int) -> None:
        """Cria o filtro por competência."""
        ctk.CTkLabel(
            parent,
            text="Período de Competência:",
            font=(FONT_FAMILY, 12, "bold"),
            text_color=COLORS["text"],
            width=170,
            anchor="w"
        ).grid(row=row, column=0, sticky="w", pady=8, padx=(0, 12))

        comp_container = ctk.CTkFrame(parent, fg_color="transparent")
        comp_container.grid(row=row, column=1, sticky="w", pady=8)

        ctk.CTkLabel(
            comp_container,
            text="De:",
            font=(FONT_FAMILY, 12),
            text_color=COLORS["text"]
        ).pack(side="left", padx=(0, 6))

        self.competence_start_entry = ctk.CTkEntry(
            comp_container,
            width=90,
            height=36,
            corner_radius=7,
            border_color=COLORS["border"],
            justify="center",
            font=(FONT_FAMILY, 12)
        )
        self.competence_start_entry.pack(side="left", padx=(0, 14))

        ctk.CTkLabel(
            comp_container,
            text="Até:",
            font=(FONT_FAMILY, 12),
            text_color=COLORS["text"]
        ).pack(side="left", padx=(0, 6))

        self.competence_end_entry = ctk.CTkEntry(
            comp_container,
            width=90,
            height=36,
            corner_radius=7,
            border_color=COLORS["border"],
            justify="center",
            font=(FONT_FAMILY, 12)
        )
        self.competence_end_entry.pack(side="left", padx=(0, 18))

        ctk.CTkLabel(
            comp_container,
            text="Tipo de Financiamento:",
            font=(FONT_FAMILY, 12, "bold"),
            text_color=COLORS["text"]
        ).pack(side="left", padx=(0, 6))

        self.tipo_financiamento_var = tk.StringVar(value="Todos")
        self.tipo_financiamento_combo = ctk.CTkComboBox(
            comp_container,
            variable=self.tipo_financiamento_var,
            values=["Todos"] + [
                f"{codigo} - {descricao}"
                for codigo, descricao in TIPOS_FINANCIAMENTO.items()
            ],
            width=260,
            height=36,
            corner_radius=7,
            border_color=COLORS["border"],
            button_color="#EFF5F2",
            button_hover_color="#D6E7DE",
            dropdown_fg_color="#FFFFFF",
            font=(FONT_FAMILY, 12)
        )
        self.tipo_financiamento_combo.pack(side="left", padx=(0, 18))

        ctk.CTkLabel(
            comp_container,
            text="Complexidade:",
            font=(FONT_FAMILY, 12, "bold"),
            text_color=COLORS["text"]
        ).pack(side="left", padx=(0, 6))

        self.complexidade_var = tk.StringVar(value="Todas")
        self.complexidade_combo = ctk.CTkComboBox(
            comp_container,
            variable=self.complexidade_var,
            values=["Todas"] + [
                f"{codigo} - {descricao}"
                for codigo, descricao in COMPLEXIDADES.items()
                if codigo != ""
            ],
            width=220,
            height=36,
            corner_radius=7,
            border_color=COLORS["border"],
            button_color="#EFF5F2",
            button_hover_color="#D6E7DE",
            dropdown_fg_color="#FFFFFF",
            font=(FONT_FAMILY, 12)
        )
        self.complexidade_combo.pack(side="left")

        self._create_tooltip(
            self.competence_start_entry,
            "Formato: AAAAMM\nExemplo: 202401 para Janeiro/2024"
        )

        self._create_tooltip(
            self.competence_end_entry,
            "Formato: AAAAMM\nExemplo: 202412 para Dezembro/2024"
        )
        
    def _create_report_options_section(self, parent) -> None:
        """Cria a seção moderna de opções de relatório."""
        options_frame = ctk.CTkFrame(
            parent,
            fg_color=COLORS["card"],
            border_color=COLORS["border"],
            border_width=1,
            corner_radius=12
        )
        options_frame.pack(fill="x", padx=18, pady=(0, 14))

        ctk.CTkLabel(
            options_frame,
            text="Opções de Relatório",
            font=(FONT_FAMILY, 13, "bold"),
            text_color=COLORS["text"]
        ).pack(anchor="w", padx=18, pady=(14, 8))

        self.single_page_var = tk.BooleanVar(value=True)
        self.hide_zeros_var = tk.BooleanVar()
        self.repeat_header_var = tk.BooleanVar()
        self.mostrar_aprovados_var = tk.BooleanVar()
        self.mostrar_produzidos_var = tk.BooleanVar()

        grid = ctk.CTkFrame(options_frame, fg_color="transparent")
        grid.pack(fill="x", padx=18, pady=(4, 18))

        for c in range(3):
            grid.columnconfigure(c, weight=1)

        check_configs = [
            ("📄 Uma página por unidade/competência", self.single_page_var, 0, 0),
            ("🚫 Ocultar procedimentos com quantidade zero", self.hide_zeros_var, 0, 1),
            ("🔄 Repetir cabeçalho em todas as páginas", self.repeat_header_var, 0, 2),
            ("✅ Mostrar aprovados (Quantidade e valor)", self.mostrar_aprovados_var, 1, 0),
            ("📦 Mostrar produzidos (Quantidade e valor)", self.mostrar_produzidos_var, 1, 1),
        ]

        for text, variable, row, col in check_configs:
            cb = ctk.CTkCheckBox(
                grid,
                text=text,
                variable=variable,
                font=(FONT_FAMILY, 12),
                text_color=COLORS["text"],
                fg_color=COLORS["primary"],
                hover_color=COLORS["primary_dark"],
                border_color=COLORS["border"],
                checkmark_color="#FFFFFF"
            )
            cb.grid(row=row, column=col, sticky="w", padx=(0, 24), pady=6)
            
    def _create_action_section(self, parent) -> None:
        """Cria a seção de botões de ação."""
        action_frame = ctk.CTkFrame(parent, fg_color="transparent")
        action_frame.pack(fill="x", padx=18, pady=(0, 14))

        button_container = ctk.CTkFrame(action_frame, fg_color="transparent")
        button_container.pack(anchor="center")

        buttons = [
            ("✅ Aplicar Filtros", self._apply_filters, COLORS["success"], "#15803D", "#FFFFFF", COLORS["success"]),
            ("🧹 Limpar Filtros", self._clear_filters, "#FFFFFF", "#FFF1F1", COLORS["danger"], COLORS["danger"]),
            ("💡 Carregar Sugestões", self._load_suggestions, "#FFFFFF", "#FFF7ED", COLORS["orange"], COLORS["orange"]),
            ("📈 Estatísticas", self._show_statistics, "#FFFFFF", COLORS["primary_soft"], COLORS["primary"], COLORS["primary"]),
        ]

        for text, command, fg, hover, text_color, border in buttons:
            ctk.CTkButton(
                button_container,
                text=text,
                command=command,
                width=150,
                height=36,
                corner_radius=7,
                fg_color=fg,
                hover_color=hover,
                text_color=text_color,
                border_color=border,
                border_width=1,
                font=(FONT_FAMILY, 12, "bold")
            ).pack(side="left", padx=6)
            
    def _create_preview_section(self, parent) -> None:
        """Cria a seção moderna de visualização rápida."""
        preview_frame = ctk.CTkFrame(
            parent,
            fg_color=COLORS["card"],
            border_color=COLORS["border"],
            border_width=1,
            corner_radius=12
        )
        preview_frame.pack(fill="x", padx=18, pady=(0, 14))

        ctk.CTkLabel(
            preview_frame,
            text="Visualização Rápida",
            font=(FONT_FAMILY, 13, "bold"),
            text_color=COLORS["text"]
        ).pack(anchor="w", padx=18, pady=(14, 8))

        grid = ctk.CTkFrame(preview_frame, fg_color="transparent")
        grid.pack(fill="x", padx=18, pady=(4, 18))

        for c in range(4):
            grid.columnconfigure(c, weight=1)

        self.preview_data = {}

        preview_config = [
            ("cnes_count", "🏥 CNES encontrados", 0, 0),
            ("procedures_count", "📋 Procedimentos", 0, 2),
            ("competence_count", "📅 Competências", 1, 0),
            ("records_count", "📈 Registros totais", 1, 2),
        ]

        for key, label_text, row, col in preview_config:
            ctk.CTkLabel(
                grid,
                text=f"{label_text}:",
                font=(FONT_FAMILY, 12),
                text_color=COLORS["text"]
            ).grid(row=row, column=col, sticky="w", pady=8, padx=(0, 10))

            self.preview_data[key] = ctk.CTkLabel(
                grid,
                text="0",
                font=(FONT_FAMILY, 12, "bold"),
                text_color=COLORS["primary"]
            )
            self.preview_data[key].grid(row=row, column=col + 1, sticky="w", pady=8)

    def _create_status_section(self, parent) -> None:
        """Cria a seção de status."""
        self.status_label = ctk.CTkLabel(
            parent,
            text="✅ Filtros prontos para uso",
            font=(FONT_FAMILY, 12, "bold"),
            text_color=COLORS["success"]
        )
        self.status_label.pack(anchor="w", padx=18, pady=(0, 18))

    def _create_tooltip(self, widget: ttk.Widget, text: str) -> None:
        """Cria tooltip para widgets."""
        def show_tooltip(event):
            tooltip = tk.Toplevel()
            tooltip.wm_overrideredirect(True)
            tooltip.wm_geometry(f"+{event.x_root+10}+{event.y_root+10}")
            
            label = ttk.Label(
                tooltip, 
                text=text, 
                background="#fff3cd",
                relief="solid", 
                borderwidth=1, 
                padding=8,
                font=('Arial', 8),
                wraplength=300
            )
            label.pack()
            
            def hide_tooltip():
                tooltip.destroy()
            
            widget.bind("<Leave>", lambda e: hide_tooltip())
        
        widget.bind("<Enter>", show_tooltip)

    def _load_initial_data(self) -> None:
        """Carrega dados iniciais para os filtros."""
        try:
            # Carregar competências recentes
            self._load_recent_competences()
            self.logger.info("Dados iniciais dos filtros carregados")
            
        except Exception as e:
            self.logger.warning(f"Erro ao carregar dados iniciais: {e}")

    def _load_recent_competences(self) -> None:
        """Preenche o período com as duas competências mais recentes."""
        try:
            competencias = self.filter_service.recent_competences(2)
            if len(competencias) >= 2:
                self.competence_end_entry.insert(0, competencias[0])
                self.competence_start_entry.insert(0, competencias[1])
        except Exception as e:
            self.logger.warning(f"Erro ao carregar competências recentes: {e}")

    def _show_procedure_help(self) -> None:
        """Abre o componente de ajuda para códigos de procedimento."""
        self.filter_dialogs.show_procedure_help()

    def _show_common_groups(self) -> None:
        """Consulta os grupos no serviço e abre o seletor dedicado."""
        try:
            groups = self.filter_service.common_groups()
            if not groups:
                messagebox.showinfo("Grupos Comuns", "Nenhum grupo comum encontrado no banco.")
                return

            def select_group(code: str):
                self.procedure_entry.delete(0, tk.END)
                self.procedure_entry.insert(0, code)
                self._apply_filters()

            self.filter_dialogs.show_common_groups(groups, select_group)
        except Exception as e:
            self.logger.error(f"Erro ao carregar grupos comuns: {e}")
            messagebox.showerror("Erro", f"Falha ao carregar grupos:\n{e}")

    def _apply_filters(self) -> None:
        """Aplica os filtros selecionados e atualiza a visualização."""
        try:
            filters = self._get_current_filters()
            self._update_preview(filters)
            self.status_label.configure(
                text="✅ Filtros aplicados com sucesso",
                text_color=COLORS["success"]
            )
            self.logger.info(f"Filtros aplicados: {filters}")
            
        except Exception as e:
            self.status_label.configure(
                text=f"❌ Erro ao aplicar filtros: {e}",
                text_color=COLORS["danger"]
            )
            self.logger.error(f"Erro ao aplicar filtros: {e}")

    def _get_current_filters(self) -> Dict[str, Any]:
        """Converte os controles atuais em filtros normalizados."""
        return self.filter_service.build_filters(
            cnes_text=self.cnes_entry.get(),
            procedimento=self.procedure_entry.get(),
            competencia_inicio=self.competence_start_entry.get(),
            competencia_fim=self.competence_end_entry.get(),
            tipo_financiamento=self.tipo_financiamento_var.get(),
            complexidade=self.complexidade_var.get(),
            uma_pagina_por_bloco=self.single_page_var.get(),
            ocultar_zerados=self.hide_zeros_var.get(),
            repetir_cabecalho=self.repeat_header_var.get(),
            mostrar_aprovados=self.mostrar_aprovados_var.get(),
            mostrar_produzidos=self.mostrar_produzidos_var.get(),
        )

    def _clear_filters(self) -> None:
        """Limpa todos os filtros."""
        self.cnes_entry.delete(0, tk.END)
        self.procedure_entry.delete(0, tk.END)
        self.competence_start_entry.delete(0, tk.END)
        self.competence_end_entry.delete(0, tk.END)
        
        if hasattr(self, "tipo_financiamento_combo"):
            self.tipo_financiamento_var.set("Todos")

        if hasattr(self, "complexidade_combo"):
            self.complexidade_var.set("Todas")
        
        self.single_page_var.set(True)
        self.hide_zeros_var.set(False)
        self.repeat_header_var.set(False)
        # Novas flags ++ 05052026  
        self.mostrar_aprovados_var.set(False)
        self.mostrar_produzidos_var.set(False)
        
        # Limpar preview
        for label in self.preview_data.values():
            label.configure(text="0", text_color=COLORS["primary"])

        self.status_label.configure(
            text="🧹 Filtros limpos",
            text_color=COLORS["muted"]
        )
        self.logger.info("Filtros limpos")

    def _load_suggestions(self) -> None:
        """Consulta somente as contagens necessárias para o status."""
        try:
            cnes_count, competence_count = self.filter_service.suggestion_counts()
            self.status_label.configure(
                text=f"💡 Sugestões carregadas: {cnes_count} CNES, {competence_count} competências",
                text_color=COLORS["primary"],
            )
            self.logger.info("Sugestões de filtros carregadas")
        except Exception as e:
            self.status_label.configure(
                text=f"❌ Erro ao carregar sugestões: {e}",
                text_color=COLORS["danger"],
            )
            self.logger.error(f"Erro ao carregar sugestões: {e}")

    def _show_statistics(self) -> None:
        """Exibe estatísticas dos filtros atuais."""
        try:
            filters = self._get_current_filters()
            stats_text = self._generate_statistics_text(filters)
            
            messagebox.showinfo("📈 Estatísticas dos Filtros", stats_text)
            
        except Exception as e:
            messagebox.showerror("Erro", f"Falha ao gerar estatísticas:\n{e}")

    def _generate_statistics_text(self, filters: Dict) -> str:
        """Delega a descrição dos filtros ao serviço."""
        return self.filter_service.statistics_text(filters)

    def _update_preview(self, filters: Dict) -> None:
        """Atualiza os quatro indicadores com uma única consulta agregada."""
        try:
            counts = self.filter_service.preview_counts(filters)
            for key, label in self.preview_data.items():
                label.configure(
                    text=f"{counts[key]:,}".replace(",", "."),
                    text_color=COLORS["primary"],
                )
        except Exception as e:
            self.logger.error(f"Erro ao atualizar preview: {e}")
            for label in self.preview_data.values():
                label.configure(text="Erro", text_color=COLORS["danger"])

    def get_applied_filters(self) -> Dict[str, Any]:
        """Retorna os filtros atualmente aplicados para uso externo."""
        return self._get_current_filters()
    
    def obter_filtros_aplicados(self) -> Dict[str, Any]:
        """Método de compatibilidade para a aba de relatórios (nome em português)"""
        return self.get_applied_filters()
