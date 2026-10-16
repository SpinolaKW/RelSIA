import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import customtkinter as ctk
import os
import subprocess
from datetime import datetime
from typing import Any, Dict, List, Optional
from sia_app.database.models import ConfigModel
from sia_app.reports.csv_exporter import exportar_csv_agregado
from sia_app.reports.data_processor import DataProcessor
from sia_app.reports.pdf_generator import PDFGenerator
from sia_app.ui.components.data_viewer import DataViewerWindow
from sia_app.services.report_service import ReportService

from sia_app.ui.theme import COLORS, apply_theme, FONT_FAMILY

class ReportsTab:
    def __init__(self, parent, db, settings, logger, filters_tab=None):
        self.parent = parent
        self.db = db
        self.settings = settings
        self.logger = logger
        self.data_processor = DataProcessor(db, logger)
        self.report_service = ReportService(db)
        self.filters_tab = filters_tab
        
        apply_theme()

        self.frame = ctk.CTkFrame(parent, fg_color=COLORS["bg"])
        self._build_ui()

    def _build_ui(self):
        """Constrói a interface do usuário com visual moderno."""
        
        # Frame principal
        main_frame = ctk.CTkScrollableFrame(self.frame, fg_color=COLORS["bg"], corner_radius=0)
        main_frame.pack(fill="both", expand=True)
        
        # Frame para titulo da tela
        self._create_title_section(main_frame)
        
        # Frame de botões de relatório
        self._build_report_buttons(main_frame)
        
        # Frame de opções
        self._build_options_frame(main_frame)
        
        # Frame de progresso
        self._build_progress_frame(main_frame)
        
        # Área de log
        self._build_log_frame(main_frame)
        
        self._log("Sistema de relatórios inicializado")
        
    def _create_title_section(self, parent):
        """Cria a seção de título."""
        header = ctk.CTkFrame(parent, fg_color="transparent")
        header.pack(fill="x", padx=18, pady=(18, 8))

        ctk.CTkLabel(
            header,
            text="Geração de Relatórios",
            font=(FONT_FAMILY, 22, "bold"),
            text_color=COLORS["text"],
            anchor="center"
        ).pack(anchor="center")

        ctk.CTkLabel(
            header,
            text="Gere PDFs, exporte dados agregados e visualize registros filtrados do SIA/SUS",
            font=(FONT_FAMILY, 12),
            text_color=COLORS["muted"],
            anchor="center"
        ).pack(anchor="center", pady=(2, 0))

    def _build_report_buttons(self, parent):
        """Constrói a seção moderna de botões de relatório."""
        card = ctk.CTkFrame(
            parent,
            fg_color=COLORS["card"],
            border_color=COLORS["border"],
            border_width=1,
            corner_radius=12
        )
        card.pack(fill="x", padx=18, pady=(8, 14))

        ctk.CTkLabel(
            card,
            text="Tipos de Relatório",
            font=(FONT_FAMILY, 13, "bold"),
            text_color=COLORS["text"]
        ).pack(anchor="w", padx=18, pady=(14, 8))

        buttons_outer = ctk.CTkFrame(card, fg_color="transparent")
        buttons_outer.pack(fill="x", padx=18, pady=(4, 18))

        buttons_frame = ctk.CTkFrame(buttons_outer, fg_color="transparent")
        buttons_frame.pack(anchor="center")

        buttons = [
            (
                "PDF por Unidade e Competência",
                lambda: self._generate_pdf_unidade_competencia(),
                COLORS["primary"],
                COLORS["primary_dark"],
                "#FFFFFF",
                COLORS["primary"]
            ),
            (
                "PDF por Procedimentos",
                lambda: self._generate_pdf_procedimentos(),
                COLORS["success"],
                "#15803D",
                "#FFFFFF",
                COLORS["success"]
            ),
            (
                "PDF Diferenças Aprov. x Prod.",
                lambda: self._generate_pdf_diferencas_aprovado_produzido(),
                COLORS["orange"],
                "#C2410C",
                "#FFFFFF",
                COLORS["orange"]
            ),
            (
                "Exportar CSV Agregado",
                self._export_csv,
                "#FFFFFF",
                COLORS["primary_soft"],
                COLORS["primary"],
                COLORS["primary"]
            ),
            (
                "Visualizar Dados",
                self._visualizar_dados,
                "#FFFFFF",
                COLORS["primary_soft"],
                COLORS["text"],
                COLORS["border"]
            ),
        ]

        for text, command, fg, hover, text_color, border in buttons:
            ctk.CTkButton(
                buttons_frame,
                text=text,
                command=command,
                height=38,
                width=210,
                corner_radius=7,
                fg_color=fg,
                hover_color=hover,
                text_color=text_color,
                border_color=border,
                border_width=1,
                font=(FONT_FAMILY, 12, "bold")
            ).pack(side="left", padx=(0, 10), pady=4)

    def _build_options_frame(self, parent):
        """Constrói a seção moderna de opções."""
        opts_card = ctk.CTkFrame(
            parent,
            fg_color=COLORS["card"],
            border_color=COLORS["border"],
            border_width=1,
            corner_radius=12
        )
        opts_card.pack(fill="x", padx=18, pady=(0, 14))

        ctk.CTkLabel(
            opts_card,
            text="Opções de Relatório",
            font=(FONT_FAMILY, 13, "bold"),
            text_color=COLORS["text"]
        ).pack(anchor="w", padx=18, pady=(14, 8))

        options_grid = ctk.CTkFrame(opts_card, fg_color="transparent")
        options_grid.pack(fill="x", padx=18, pady=(4, 18))

        self.use_filters_var = tk.BooleanVar(value=True)
        self.auto_open_var = tk.BooleanVar(value=True)

        checks_row = ctk.CTkFrame(options_grid, fg_color="transparent")
        checks_row.pack(anchor="w")

        ctk.CTkCheckBox(
            checks_row,
            text="Usar filtros da aba 'Filtros'",
            variable=self.use_filters_var,
            font=(FONT_FAMILY, 12),
            text_color=COLORS["text"],
            fg_color=COLORS["primary"],
            hover_color=COLORS["primary_dark"],
            border_color=COLORS["border"],
            checkmark_color="#FFFFFF"
        ).pack(side="left", padx=(0, 28), pady=5)

        ctk.CTkCheckBox(
            checks_row,
            text="Abrir PDF automaticamente após gerar",
            variable=self.auto_open_var,
            font=(FONT_FAMILY, 12),
            text_color=COLORS["text"],
            fg_color=COLORS["primary"],
            hover_color=COLORS["primary_dark"],
            border_color=COLORS["border"],
            checkmark_color="#FFFFFF"
        ).pack(side="left", pady=5)

    def _build_progress_frame(self, parent):
        """Constrói a seção moderna de progresso."""
        progress_card = ctk.CTkFrame(
            parent,
            fg_color=COLORS["card"],
            border_color=COLORS["border"],
            border_width=1,
            corner_radius=12
        )
        progress_card.pack(fill="x", padx=18, pady=(0, 14))

        ctk.CTkLabel(
            progress_card,
            text="Progresso",
            font=(FONT_FAMILY, 13, "bold"),
            text_color=COLORS["text"]
        ).pack(anchor="w", padx=18, pady=(14, 8))

        self.progress = ctk.CTkProgressBar(
            progress_card,
            height=12,
            corner_radius=8,
            fg_color="#EAF3EF",
            progress_color=COLORS["primary"],
            mode="indeterminate"
        )
        self.progress.pack(fill="x", padx=18, pady=(0, 8))
        self.progress.set(0)

        self.status_label = ctk.CTkLabel(
            progress_card,
            text="Pronto para gerar relatórios",
            font=(FONT_FAMILY, 11),
            text_color=COLORS["muted"]
        )
        self.status_label.pack(anchor="w", padx=18, pady=(0, 14))

    def _build_log_frame(self, parent):
        """Constrói a área moderna de log."""
        log_card = ctk.CTkFrame(
            parent,
            fg_color=COLORS["card"],
            border_color=COLORS["border"],
            border_width=1,
            corner_radius=12
        )
        log_card.pack(fill="both", expand=True, padx=18, pady=(0, 18))

        header = ctk.CTkFrame(log_card, fg_color="transparent")
        header.pack(fill="x", padx=18, pady=(14, 8))

        ctk.CTkLabel(
            header,
            text="Log de Geração",
            font=(FONT_FAMILY, 13, "bold"),
            text_color=COLORS["text"]
        ).pack(side="left")

        text_container = ctk.CTkFrame(
            log_card,
            fg_color="#F8FAFC",
            border_color=COLORS["border"],
            border_width=1,
            corner_radius=8
        )
        text_container.pack(fill="both", expand=True, padx=18, pady=(0, 18))

        self.log_text = tk.Text(
            text_container,
            height=12,
            wrap=tk.WORD,
            font=("Consolas", 9),
            bg="#F8FAFC",
            fg=COLORS["text"],
            relief="flat",
            borderwidth=0,
            insertbackground=COLORS["text"]
        )

        scrollbar = ttk.Scrollbar(
            text_container,
            orient="vertical",
            command=self.log_text.yview
        )
        self.log_text.configure(yscrollcommand=scrollbar.set)

        self.log_text.pack(side="left", fill="both", expand=True, padx=(10, 0), pady=10)
        scrollbar.pack(side="right", fill="y", padx=(0, 10), pady=10)

    def _log(self, message: str):
        """Adiciona mensagem ao log de forma otimizada"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        formatted_message = f"[{timestamp}] {message}\n"
        
        self.log_text.insert("end", formatted_message)
        self.log_text.see("end")
        self.logger.info(message)
        self.parent.update_idletasks()
    
    def _load_estabelecimentos_map(self) -> Dict[str, str]:
        try:
            establishments = self.report_service.establishment_map()
            self._log(f"Carregados {len(establishments)} estabelecimentos")
            return establishments
        except Exception as e:
            self._log(f"Erro ao carregar estabelecimentos: {e}")
            return {}

    def _generate_pdf_unidade_competencia(self, titulo: str = "Produção por Unidade e Competência", 
                                        table_mode: str = "unidade"):
        """Gera PDF agrupado por unidade e competência"""
        try:
            self._start_processing("Iniciando geração de PDF...")
            
            # Obter filtros
            filtros = self._get_filters()
            if not filtros:
                self._log("Gerando relatório sem filtros")
            
            # Obter dados
            dados = self._get_filtered_data(filtros)
            if not dados:
                return
            
            # Processar dados
            estabelecimentos_map = self._load_estabelecimentos_map()
            blocks = self._group_data_by_cnes_competencia(dados, estabelecimentos_map)
            
            if not blocks:
                messagebox.showinfo("PDF", "Nenhum dado encontrado para agrupamento.")
                return
                
            # DEBUG DOS DADOS
            self._debug_blocks_data(blocks)
            
            # Obter configurações e opções
            config = self._get_config()
            if not config:
                return
                
            opts = self._prepare_pdf_options(config, titulo, table_mode, filtros)
            
            # Solicitar local para salvar e gerar PDF
            filename = f"Relatorio_Unidade_Competencia_{self._get_timestamp()}.pdf"
            output_path = self._get_save_path("Salvar PDF - Por Unidade e Competência", filename)
            
            if output_path:
                self._generate_and_open_pdf(blocks, opts, output_path)
            
        except Exception as e:
            self._handle_error(f"ERRO na geração do PDF: {e}")
        finally:
            self._stop_processing()

    def _generate_pdf_procedimentos(self, titulo: str = "Produção por Procedimentos", 
                                  table_mode: str = "procedimento"):
        """Gera PDF com o MESMO layout (CNES+Competência), filtrado pelo procedimento informado."""
        try:
            self._start_processing("Preparando relatório por procedimentos...")

            # Filtros
            filtros = self._get_filters()
            procedimento = self._extract_procedimento_from_filters(filtros)
            
            if not procedimento:
                messagebox.showwarning("Relatório por Procedimento", 
                                     "Preencha o campo 'Procedimento' para gerar este relatório.")
                return

            self._log(f"Gerando relatório por procedimentos (PROC={procedimento})...")

            # Buscar e filtrar dados
            dados = self._get_filtered_data(filtros)
            if not dados:
                return

            # Processar dados filtrados por procedimento
            estabelecimentos_map = self._load_estabelecimentos_map()
            blocks = self._filter_and_group_by_procedimento(dados, estabelecimentos_map, procedimento)
            
            if not blocks:
                self._log_procedimento_debug_info(dados, procedimento)
                messagebox.showinfo("PDF", "Nenhuma produção encontrada para o procedimento informado.")
                return

            # Configurações e geração
            config = self._get_config()
            if not config:
                return

            opts = self._prepare_pdf_options(config, titulo, table_mode, filtros)
            
            filename = f"Relatorio_Procedimentos_{self._get_timestamp()}.pdf"
            output_path = self._get_save_path("Salvar PDF - Por Procedimentos", filename)
            
            if output_path:
                self._generate_and_open_pdf(blocks, opts, output_path)

        except Exception as e:
            self._handle_error(f"ERRO no PDF de procedimentos: {e}")
        finally:
            self._stop_processing()
            
    def _generate_pdf_diferencas_aprovado_produzido(
        self,
        titulo: str = "Diferenças entre Produzido e Aprovado",
        table_mode: str = "diferencas"
    ):
        """
        Gera PDF mostrando apenas procedimentos onde os valores produzidos
        são diferentes dos valores aprovados.

        Aceita filtros de CNES, competência e procedimento.
        Ignora os flags mostrar_aprovados e mostrar_produzidos.
        """
        try:
            self._start_processing("Gerando relatório de diferenças aprovado x produzido...")

            filtros = self._get_filters()

            # Ignorar os flags da tela para este relatório
            filtros.pop('mostrar_aprovados', None)
            filtros.pop('mostrar_produzidos', None)

            self._log("Gerando relatório de diferenças entre produzido e aprovado...")

            # Buscar dados específicos de diferença
            dados = self.data_processor.obter_dados_diferencas_aprovado_produzido(filtros)

            if not dados:
                messagebox.showinfo(
                    "Relatório de Diferenças",
                    "Nenhuma diferença encontrada entre valores produzidos e aprovados."
                )
                return

            estabelecimentos_map = self._load_estabelecimentos_map()
            blocks = self._group_data_by_cnes_competencia(dados, estabelecimentos_map)

            if not blocks:
                messagebox.showinfo(
                    "Relatório de Diferenças",
                    "Nenhum dado encontrado para agrupamento."
                )
                return

            config = self._get_config()
            if not config:
                return

            opts = self._prepare_pdf_options(config, titulo, table_mode, filtros)

            # Forçar as colunas deste relatório independentemente dos flags da tela
            opts['mostrar_aprovados'] = True
            opts['mostrar_produzidos'] = True
            opts['mostrar_diferencas'] = True
            opts['diferencas_somente_quantidades'] = True
            opts['title'] = titulo
            opts['table_mode'] = table_mode

            filename = f"Relatorio_Diferencas_Aprovado_Produzido_{self._get_timestamp()}.pdf"
            output_path = self._get_save_path(
                "Salvar PDF - Diferenças Aprovado x Produzido",
                filename
            )

            if output_path:
                self._generate_and_open_pdf(blocks, opts, output_path)

        except Exception as e:
            self._handle_error(f"ERRO no relatório de diferenças: {e}")
        finally:
            self._stop_processing()

    def _export_csv(self):
        """Exporta dados para CSV de forma otimizada"""
        try:
            self._start_processing("Preparando exportação CSV...")
            
            filtros = self._get_filters()
            dados = self._get_filtered_data(filtros, para_exportacao_csv=True)
            if not dados:
                return
            
            # Solicitar local para salvar
            filename = f"Dados_SIA_{self._get_timestamp()}.csv"
            output_path = self._get_save_path("Salvar CSV", filename, filetypes=[("CSV", "*.csv")])
            
            if not output_path:
                return
            
            # Exportar para CSV
            self._export_to_csv(dados, output_path)
            self._log(f"CSV exportado: {output_path}")
            self._show_modern_message(
                "CSV exportado",
                f"Dados exportados com sucesso!\n\n{output_path}",
                "success"
            )
            
        except Exception as e:
            self._handle_error(f"ERRO na exportação CSV: {e}")
        finally:
            self._stop_processing()
    
    def _visualizar_dados(self):
        """Abre visualização dos dados filtrados, separado por CBO"""
        try:
            self._start_processing("Carregando dados para visualização...")
            
            filtros = self._get_filters()

            dados = self.data_processor.obter_dados_visualizacao_com_cbo(filtros)

            if not dados:
                messagebox.showinfo(
                    "Dados",
                    "Nenhum dado encontrado com os filtros atuais."
                )
                return
            
            self._log(f"Encontrados {len(dados)} registros para visualização")
            self._create_data_viewer_window(dados)
            
        except Exception as e:
            self._handle_error(f"ERRO na visualização: {e}")
        finally:
            self._stop_processing()
    
    # Métodos auxiliares otimizados

    def _start_processing(self, message: str):
        """Inicia a interface de processamento."""
        self.progress.start()
        self.status_label.configure(
            text=message,
            text_color=COLORS["primary"]
        )

    def _stop_processing(self):
        """Para a interface de processamento."""
        self.progress.stop()
        self.progress.set(0)
        self.status_label.configure(
            text="Processamento concluído",
            text_color=COLORS["success"]
        )
        
    # Adicione este método na classe ReportsTab para buscar filtros da ConfigTab
    def _get_config_filters(self) -> Dict[str, Any]:
        """Obtém APENAS configurações institucionais da aba de configurações."""
        try:
            # Buscar a aba de configurações através da main window
            main_window = self.frame.winfo_toplevel()
            if hasattr(main_window, 'main_window') and main_window.main_window:
                config_tab = main_window.main_window.tabs.get('config')
                if config_tab:
                    # AGORA retorna APENAS dados institucionais
                    config_filters = {
                        'inst1': getattr(config_tab, 'inst1_entry', ttk.Entry()).get().strip(),
                        'inst2': getattr(config_tab, 'inst2_entry', ttk.Entry()).get().strip(),
                        'inst3': getattr(config_tab, 'inst3_entry', ttk.Entry()).get().strip(),
                        'logo_path': getattr(config_tab, 'current_logo_path', None)
                    }
                    return {k: v for k, v in config_filters.items() if v}  # Remove valores vazios
        except Exception as e:
            self._log(f"Erro ao buscar configurações institucionais: {e}")
        
        return {}

    # Modifique o método _get_filters existente para incluir os filtros da ConfigTab
    def _get_filters(self) -> Dict[str, Any]:
        """Obtém filtros da aba de filtros E da aba de configurações"""
        filters = {}
        
        # 1. Buscar filtros da aba FiltersTab (se habilitado)
        if self.use_filters_var.get() and self.filters_tab:
            if hasattr(self.filters_tab, 'get_applied_filters'):
                filters_tab_filters = self.filters_tab.get_applied_filters()
            elif hasattr(self.filters_tab, 'obter_filtros_aplicados'):
                filters_tab_filters = self.filters_tab.obter_filtros_aplicados()
            else:
                filters_tab_filters = {}
            
            if filters_tab_filters:
                filters.update(filters_tab_filters)
                self._log(f"Aplicando filtros da aba Filtros: {filters_tab_filters}")
        
        # 2. SEMPRE buscar filtros da aba ConfigTab (configurações do sistema)
        config_filters = self._get_config_filters()
        if config_filters:
            filters.update(config_filters)
            self._log(f"Aplicando filtros da aba Configurações: {config_filters}")
        
        return filters

    def _get_filtered_data(
        self,
        filtros: Dict[str, Any],
        *,
        para_exportacao_csv: bool = False,
    ) -> Optional[List[Dict]]:
        """Obtém dados filtrados do processador"""
        self._log("Consultando dados do banco...")
        if para_exportacao_csv:
            dados = self.data_processor.obter_dados_exportacao_csv(filtros)
        else:
            dados = self.data_processor.obter_dados_aggregado(filtros)
        
        if not dados:
            messagebox.showinfo("Dados", "Nenhum dado encontrado com os filtros atuais.")
            return None
        
        self._log(f"Encontrados {len(dados)} registros para processamento")
        return dados

    def _group_data_by_cnes_competencia(
        self,
        dados: List[Dict],
        estabelecimentos_map: Dict[str, str],
    ) -> List[Dict]:
        blocks = self.report_service.group_by_establishment_competence(
            dados,
            estabelecimentos_map,
        )
        self._log(f"Organizados {len(blocks)} blocos (CNES + competência)")
        return blocks

    def _extract_procedimento_from_filters(self, filtros: Dict[str, Any]) -> str:
        return self.report_service.extract_procedure(filtros)

    def _filter_and_group_by_procedimento(
        self,
        dados: List[Dict],
        estabelecimentos_map: Dict[str, str],
        procedimento: str,
    ) -> List[Dict]:
        blocks, retained = self.report_service.filter_and_group_procedure(
            dados,
            estabelecimentos_map,
            procedimento,
        )
        self._log(f"Filtrados {retained} registros do procedimento {procedimento}")
        return blocks

    def _log_procedimento_debug_info(self, dados: List[Dict], procedimento: str):
        """Loga informações de debug para procedimentos não encontrados"""
        self._log(f"Nenhum dado encontrado para procedimento '{procedimento}'")
        if dados:
            amostra = dados[0]
            self._log(f"Exemplo de chaves na 1ª linha: {list(amostra.keys())}")
            for k in ("PRD_PA", "PROC", "COD_PROCEDIMENTO", "PRD_COD", "PA_ID", "PROCEDIMENTO", "PA", "PA_DV"):
                if k in amostra:
                    normalized = ReportService.only_digits(amostra[k])
                    self._log(f"Campo {k}='{amostra[k]}' (norm='{normalized}')")

    def _get_config(self) -> Optional[Dict[str, Any]]:
        """Obtém configurações do sistema"""
        config_model = ConfigModel(self.db)
        config = config_model.obter_config()
        
        if not config:
            messagebox.showerror("Erro", "Configurações do sistema não encontradas.")
            return None
            
        return config

    def _prepare_pdf_options(
        self,
        config: Dict[str, Any],
        titulo: str,
        table_mode: str,
        filtros: Dict[str, Any],
    ) -> Dict[str, Any]:
        return self.report_service.prepare_pdf_options(
            config,
            titulo,
            table_mode,
            filtros,
        )

    def _get_save_path(self, title: str, filename: str, filetypes=None) -> Optional[str]:
        """Solicita caminho para salvar arquivo."""
        if filetypes is None:
            filetypes = [("PDF", "*.pdf")]
            default_extension = ".pdf"
        else:
            # Se for CSV, usa extensão CSV
            if any("CSV" in ft[0].upper() or "*.csv" in ft[1].lower() for ft in filetypes):
                default_extension = ".csv"
            else:
                default_extension = ".pdf"

        return filedialog.asksaveasfilename(
            title=title,
            defaultextension=default_extension,
            filetypes=filetypes,
            initialfile=filename
        )

    def _generate_and_open_pdf(self, blocks: List[Dict], opts: Dict[str, Any], output_path: str):
        """Gera e abre o PDF se solicitado"""
        pdf_generator = PDFGenerator(self.logger)
        success, message = pdf_generator.generate_pdf(blocks, opts, output_path)

        if success:
            self._log(f"PDF gerado com sucesso: {output_path}")
            self.status_label.configure(
                text="PDF gerado com sucesso!",
                text_color=COLORS["success"]
            )
            
            if self.auto_open_var.get():
                self._open_file(output_path)
                
            messagebox.showinfo("PDF", f"PDF gerado com sucesso!\n\n{output_path}")
        else:
            self._log(f"Erro ao gerar PDF: {message}")
            messagebox.showerror("Erro", f"Falha ao gerar PDF:\n{message}")

    def _open_file(self, filepath: str):
        """Abre arquivo no visualizador padrão do sistema"""
        try:
            if os.name == 'nt':  # Windows
                os.startfile(filepath)
            else:  # Linux/Mac
                subprocess.run(['xdg-open', filepath])
            self._log("Arquivo aberto automaticamente")
        except Exception as e:
            self._log(f"Não foi possível abrir o arquivo automaticamente: {e}")
    
    def _export_to_csv(self, dados: List[Dict], output_path: str):
        """
        Exporta dados para CSV com colunas amigáveis, incluindo aprovados e produzidos.
        """
        exportar_csv_agregado(dados, output_path)
    
    def _create_data_viewer_window(self, dados: List[Dict]):
        """Abre o componente dedicado de visualização de dados."""
        DataViewerWindow(
            self.frame,
            dados,
            self._load_estabelecimentos_map(),
            COLORS,
            self._log,
        ).show()

    def _handle_error(self, error_message: str):
        """Manipula erros de forma consistente"""
        self._log(error_message)
        self._show_modern_message(
            "Erro",
            f"Falha no processamento:\n{error_message}",
            "error"
        )

    def _get_timestamp(self) -> str:
        """Retorna timestamp formatado"""
        return datetime.now().strftime("%Y%m%d_%H%M%S")
        
    def _debug_blocks_data(self, blocks: List[Dict]):
        """Debug da estrutura dos dados antes de gerar PDF"""
        self._log("=== DEBUG ESTRUTURA DOS DADOS ===")
        
        if not blocks:
            self._log("Nenhum bloco para debug")
            return
            
        for i, block in enumerate(blocks[:2]):  # Mostra apenas os 2 primeiros
            self._log(f"Bloco {i+1}:")
            self._log(f"  CNES: {block.get('uid')}")
            self._log(f"  Nome: {block.get('nome')}")
            self._log(f"  Competência: {block.get('cmp')}")
            self._log(f"  Quantidade de rows: {len(block.get('rows', []))}")
            
            # Mostrar primeira row do bloco
            rows = block.get('rows', [])
            if rows and len(rows) > 0:
                primeira_row = rows[0]
                self._log(f"  Primeira row - Campos: {list(primeira_row.keys())}")
                self._log(f"  Dados exemplo: PRD_PA={primeira_row.get('PRD_PA')}, QUANTIDADE={primeira_row.get('QUANTIDADE')}, VALOR_UNITARIO={primeira_row.get('VALOR_UNITARIO')}")
        
        self._log("=== FIM DEBUG ===")
        
    def _show_modern_message(self, title: str, message: str, level: str = "info"):
        """Exibe uma mensagem em janela moderna."""
        color_map = {
            "info": COLORS["primary"],
            "success": COLORS["success"],
            "warning": COLORS["warning"],
            "error": COLORS["danger"],
        }

        color = color_map.get(level, COLORS["primary"])

        window = ctk.CTkToplevel(self.frame)
        window.title(title)
        window.geometry("520x260")
        window.resizable(False, False)
        window.transient(self.frame)
        window.grab_set()
        window.configure(fg_color=COLORS["bg"])

        window.update_idletasks()
        width = 520
        height = 220
        x = (window.winfo_screenwidth() // 2) - (width // 2)
        y = (window.winfo_screenheight() // 2) - (height // 2)
        window.geometry(f"{width}x{height}+{x}+{y}")

        main = ctk.CTkFrame(
            window,
            fg_color=COLORS["bg"],
            corner_radius=0
        )
        main.pack(fill="both", expand=True, padx=18, pady=18)

        card = ctk.CTkFrame(
            main,
            fg_color=COLORS["card"],
            border_color=COLORS["border"],
            border_width=1,
            corner_radius=12
        )
        card.pack(fill="both", expand=True)

        ctk.CTkLabel(
            card,
            text=title,
            font=(FONT_FAMILY, 18, "bold"),
            text_color=color
        ).pack(anchor="center", padx=18, pady=(18, 8))

        ctk.CTkLabel(
            card,
            text=message,
            font=(FONT_FAMILY, 12),
            text_color=COLORS["text"],
            wraplength=450,
            justify="left"
        ).pack(anchor="w", padx=18, pady=(0, 18))

        ctk.CTkButton(
            card,
            text="OK",
            command=window.destroy,
            width=110,
            height=36,
            corner_radius=7,
            fg_color=color,
            hover_color=COLORS["primary_dark"] if level != "error" else "#B91C1C",
            text_color="#FFFFFF",
            font=(FONT_FAMILY, 12, "bold")
        ).pack(anchor="center", padx=18, pady=(0, 18))
