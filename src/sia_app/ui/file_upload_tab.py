import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from tkinter.scrolledtext import ScrolledText
import customtkinter as ctk
import logging
import threading
import os
import queue
from typing import List, Tuple, Optional
from datetime import datetime

from sia_app.database.connection import DatabaseConnection
from sia_app.file_processing.csv_importer import CSVImporter
from sia_app.file_processing.dbf_converter import DBFConverter
from sia_app.file_processing.file_validator import FileValidator
from sia_app.services.file_import_service import FileImportService

from sia_app.ui.theme import COLORS, apply_theme, FONT_FAMILY

class TkTextHandler(logging.Handler):
    """
    Handler de logging para exibir mensagens no ScrolledText da UI.
    """
    
    # Cores para diferentes níveis de log
    LOG_COLORS = {
        'DEBUG': '#6c757d',
        'INFO': '#17a2b8', 
        'WARNING': '#ffc107',
        'ERROR': '#dc3545',
        'CRITICAL': '#dc3545'
    }
    
    def __init__(self, text_widget: ScrolledText):
        super().__init__()
        self.text_widget = text_widget
        self.setFormatter(
            logging.Formatter("%(asctime)s - %(levelname)s - %(message)s", datefmt="%H:%M:%S")
        )
        self._message_queue = queue.Queue()
        self._after_id: str | None = None
        self._closed = False
        # O polling nasce na thread do Tk. O worker apenas adiciona mensagens
        # à fila e nunca chama métodos do widget diretamente.
        self._schedule_poll()

    def emit(self, record):
        """Processa mensagens de log de forma assíncrona."""
        if self._closed:
            return
        try:
            msg = self.format(record)
            level = record.levelname
            self._message_queue.put((msg, level))
        except Exception:
            self.handleError(record)

    def _process_queue(self):
        """Processa a fila de mensagens de forma assíncrona."""
        self._after_id = None
        if self._closed:
            return
        try:
            while True:
                msg, level = self._message_queue.get_nowait()
                self._append_message(msg, level)
        except queue.Empty:
            pass

        self._schedule_poll()

    def _schedule_poll(self) -> None:
        if self._closed:
            return
        try:
            self._after_id = self.text_widget.after(100, self._process_queue)
        except tk.TclError:
            self._after_id = None

    def close(self) -> None:
        """Cancela o polling antes que o widget e o Tcl sejam destruídos."""
        if self._closed:
            return
        self._closed = True
        if self._after_id is not None:
            try:
                self.text_widget.after_cancel(self._after_id)
            except tk.TclError:
                pass
            self._after_id = None
        while True:
            try:
                self._message_queue.get_nowait()
            except queue.Empty:
                break
        super().close()

    def _append_message(self, msg: str, level: str):
        """Adiciona mensagem formatada ao widget de texto."""
        try:
            self.text_widget.configure(state="normal")
            
            # Configurar tag para o nível
            tag_name = f"level_{level}"
            if tag_name not in self.text_widget.tag_names():
                color = self.LOG_COLORS.get(level, '#000000')
                self.text_widget.tag_configure(tag_name, foreground=color)
            
            # Inserir mensagem
            self.text_widget.insert("end", msg + "\n", tag_name)
            self.text_widget.see("end")
            self.text_widget.configure(state="disabled")
            
        except Exception:
            pass


class FileUploadTab:
    """
    Aba de upload e processamento de arquivos do SIA/SUS.
    """
    
    MULTI_FILE_SEPARATOR = "||"
    
    # Configurações de arquivos suportados
    FILE_TYPES = {
        'PRD': {
            'extensions': ['.dbf'],
            'description': 'Arquivos S_PRD.DBF',
            'expected_columns': ['PRD_UID', 'PRD_CMP', 'PRD_PA', 'PRD_QT_A', 'PRD_VL_A']
        },
        'PA': {
            'extensions': ['.dbf'], 
            'description': 'Arquivos S_PA.DBF',
            'expected_columns': ['PA_ID', 'PA_DV', 'PA_DC', 'PA_TOTAL']
        },
        'CNES': {
            'extensions': ['.csv', '.txt'],
            'description': 'Arquivos CNES.CSV',
            'expected_columns': ['CNES', 'NO_FANTASIA']
        }
    }
    
    def __init__(self, parent, db: DatabaseConnection, settings, logger: logging.Logger):
        """
        Inicializa a aba de upload de arquivos.
        
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
        
        apply_theme()
        
        self.frame = ctk.CTkFrame(parent, fg_color=COLORS["bg"])
        self._processing = False
        self._current_thread: Optional[threading.Thread] = None
        self._closing = False
        self._ui_queue = queue.Queue()
        self._ui_after_id: str | None = None
        
        # Importar processadores (com tratamento de erro)
        self._import_processors()
        self._setup_ui()
        
        # Configurar logging para a UI
        self._setup_logging()
        self._schedule_ui_poll()

    def _import_processors(self):
        """Importa os processadores de arquivo com tratamento de erro."""
        try:
            self.dbf_converter = DBFConverter(self.logger)
            self.csv_importer = CSVImporter(self.logger, self.db)
            self.validator = FileValidator(self.logger)
            self.import_service = FileImportService(
                self.db,
                self.dbf_converter,
                self.csv_importer,
                self.validator,
                self.logger,
            )
            
        except ImportError as e:
            self.logger.error(f"Erro ao importar processadores: {e}")
            messagebox.showerror(
                "Erro de Importação", 
                f"Falha ao carregar módulos de processamento:\n{e}"
            )
            raise

    def _setup_ui(self):
        """Configura a interface do usuário de forma organizada."""
        # Container principal
        main_frame = ctk.CTkScrollableFrame(self.frame, fg_color=COLORS["bg"], corner_radius=0)
        main_frame.pack(fill="both", expand=True)
        
        # Título
        self._create_title_section(main_frame)
        
        # Seção de seleção de arquivos
        self._create_file_selection_section(main_frame)
        
        # Seção de controles
        self._create_control_section(main_frame)
        
        # Seção de progresso
        self._create_progress_section(main_frame)
        
        # Seção de logs
        self._create_log_section(main_frame)

    def _create_title_section(self, parent):
        """Cria a seção de título."""
        header = ctk.CTkFrame(parent, fg_color="transparent")
        header.pack(fill="x", padx=18, pady=(18, 8))

        ctk.CTkLabel(
            header,
            text="Upload de Arquivos do SIA/SUS",
            font=(FONT_FAMILY, 22, "bold"),
            text_color=COLORS["text"],
            anchor="center"
        ).pack(anchor="center")

        ctk.CTkLabel(
            header,
            text="Selecione os arquivos de produção, procedimentos e estabelecimentos para importar no banco de dados",
            font=(FONT_FAMILY, 12),
            text_color=COLORS["muted"],
            anchor="center"
        ).pack(anchor="center", pady=(2, 0))
        
    def _create_file_selection_section(self, parent):
        """Cria a seção moderna de seleção de arquivos."""
        files_frame = ctk.CTkFrame(
            parent,
            fg_color=COLORS["card"],
            border_color=COLORS["border"],
            border_width=1,
            corner_radius=12
        )
        files_frame.pack(fill="x", padx=18, pady=(8, 14))

        ctk.CTkLabel(
            files_frame,
            text="📁 Seleção de Arquivos",
            font=(FONT_FAMILY, 13, "bold"),
            text_color=COLORS["text"]
        ).pack(anchor="w", padx=18, pady=(14, 6))

        content = ctk.CTkFrame(files_frame, fg_color="transparent")
        content.pack(fill="x", padx=18, pady=(4, 18))

        content.grid_columnconfigure(1, weight=1)

        self.file_entries = {}

        file_configs = [
            ("PRD", "Produção", self.FILE_TYPES["PRD"]["description"]),
            ("PA", "Procedimentos", self.FILE_TYPES["PA"]["description"]),
            ("CNES", "Estabelecimentos", self.FILE_TYPES["CNES"]["description"]),
        ]

        for row, (file_type, label, description) in enumerate(file_configs):
            self._file_row(
                content,
                row=row,
                file_type=file_type,
                label=label,
                description=description
            )
    
    def _file_row(self, parent, row, file_type, label, description):
        """Cria uma linha moderna de seleção de arquivo."""
        ctk.CTkLabel(
            parent,
            text=f"{label}:",
            font=(FONT_FAMILY, 12, "bold"),
            text_color=COLORS["text"],
            anchor="w",
            width=130
        ).grid(row=row, column=0, sticky="w", padx=(0, 12), pady=8)

        entry = ctk.CTkEntry(
            parent,
            height=36,
            corner_radius=7,
            border_color=COLORS["border"],
            fg_color="#FFFFFF",
            text_color=COLORS["text"],
            placeholder_text=f"Selecione {description}",
            font=(FONT_FAMILY, 12)
        )
        entry.grid(row=row, column=1, sticky="ew", pady=8, padx=(0, 10))
        self.file_entries[file_type] = entry

        ctk.CTkButton(
            parent,
            text="Procurar",
            command=lambda ft=file_type: self._browse_file(ft),
            height=36,
            width=110,
            corner_radius=7,
            fg_color=COLORS["primary"],
            hover_color=COLORS["primary_dark"],
            text_color="#FFFFFF",
            font=(FONT_FAMILY, 12, "bold")
        ).grid(row=row, column=2, sticky="e", pady=8, padx=(0, 10))

        ctk.CTkLabel(
            parent,
            text=description,
            font=(FONT_FAMILY, 11),
            text_color=COLORS["muted"],
            anchor="w",
            width=150
        ).grid(row=row, column=3, sticky="w", pady=8)
        
    def _create_control_section(self, parent):
        """Cria a seção moderna de controles com botões centralizados e coloridos."""
        control_card = ctk.CTkFrame(
            parent,
            fg_color=COLORS["card"],
            border_color=COLORS["border"],
            border_width=1,
            corner_radius=12
        )
        control_card.pack(fill="x", padx=18, pady=(0, 14))

        ctk.CTkLabel(
            control_card,
            text="Ações",
            font=(FONT_FAMILY, 13, "bold"),
            text_color=COLORS["text"]
        ).pack(anchor="w", padx=18, pady=(14, 8))

        # Container ocupa a largura toda
        buttons_outer = ctk.CTkFrame(control_card, fg_color="transparent")
        buttons_outer.pack(fill="x", padx=18, pady=(0, 18))

        # Container interno fica centralizado
        buttons = ctk.CTkFrame(buttons_outer, fg_color="transparent")
        buttons.pack(anchor="center")

        ctk.CTkButton(
            buttons,
            text="↗ Processar Todos",
            command=self._process_all_files,
            height=36,
            width=150,
            corner_radius=7,
            fg_color=COLORS["success"],
            hover_color="#15803D",
            text_color="#FFFFFF",
            font=(FONT_FAMILY, 12, "bold")
        ).pack(side="left", padx=6)

        ctk.CTkButton(
            buttons,
            text="✓ Validar Arquivos",
            command=self._validate_files,
            height=36,
            width=150,
            corner_radius=7,
            fg_color=COLORS["warning"],
            hover_color="#D97706",
            text_color="#FFFFFF",
            font=(FONT_FAMILY, 12, "bold")
        ).pack(side="left", padx=6)

        ctk.CTkButton(
            buttons,
            text="× Limpar Campos",
            command=self._clear_fields,
            height=36,
            width=140,
            corner_radius=7,
            fg_color=COLORS["danger"],
            hover_color="#B91C1C",
            text_color="#FFFFFF",
            font=(FONT_FAMILY, 12, "bold")
        ).pack(side="left", padx=6)

        ctk.CTkButton(
            buttons,
            text="▥ Estatísticas",
            command=self._show_statistics,
            height=36,
            width=130,
            corner_radius=7,
            fg_color=COLORS["primary"],
            hover_color=COLORS["primary_dark"],
            text_color="#FFFFFF",
            font=(FONT_FAMILY, 12, "bold")
        ).pack(side="left", padx=6)

    def _create_progress_section(self, parent):
        """Cria a seção moderna de progresso."""
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

        self.progress_bar = ctk.CTkProgressBar(
            progress_card,
            height=12,
            corner_radius=8,
            fg_color="#EAF3EF",
            progress_color=COLORS["primary"]
        )
        self.progress_bar.pack(fill="x", padx=18, pady=(0, 8))
        self.progress_bar.set(0)

        self.progress_label = ctk.CTkLabel(
            progress_card,
            text="Pronto para processar arquivos",
            font=(FONT_FAMILY, 11),
            text_color=COLORS["muted"]
        )
        self.progress_label.pack(anchor="w", padx=18)

        self.current_action_label = ctk.CTkLabel(
            progress_card,
            text="",
            font=(FONT_FAMILY, 11),
            text_color=COLORS["primary"]
        )
        self.current_action_label.pack(anchor="w", padx=18, pady=(0, 14))

        self.progress_total = 1

    def _create_log_section(self, parent):
        """Cria a seção moderna de logs."""
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
            text="Log de Execução",
            font=(FONT_FAMILY, 13, "bold"),
            text_color=COLORS["text"]
        ).pack(side="left")

        log_controls = ctk.CTkFrame(header, fg_color="transparent")
        log_controls.pack(side="right")

        ctk.CTkButton(
            log_controls,
            text="Limpar Log",
            command=self._clear_log,
            height=30,
            width=100,
            corner_radius=7,
            fg_color="#FFFFFF",
            hover_color=COLORS["primary_soft"],
            border_color=COLORS["border"],
            border_width=1,
            text_color=COLORS["text"],
            font=(FONT_FAMILY, 11, "bold")
        ).pack(side="left", padx=(0, 8))

        ctk.CTkButton(
            log_controls,
            text="Exportar Log",
            command=self._export_log,
            height=30,
            width=110,
            corner_radius=7,
            fg_color="#FFFFFF",
            hover_color=COLORS["primary_soft"],
            border_color=COLORS["border"],
            border_width=1,
            text_color=COLORS["text"],
            font=(FONT_FAMILY, 11, "bold")
        ).pack(side="left")

        text_container = ctk.CTkFrame(
            log_card,
            fg_color="#F8FAFC",
            border_color=COLORS["border"],
            border_width=1,
            corner_radius=8
        )
        text_container.pack(fill="both", expand=True, padx=18, pady=(0, 18))

        self.log_text = ScrolledText(
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
        self.log_text.pack(fill="both", expand=True, padx=10, pady=10)
        self.log_text.configure(state="disabled")

    def _setup_logging(self):
        """Configura o sistema de logging para a UI."""
        # Ao trocar de sessão, remova qualquer handler ligado à janela anterior.
        for handler in list(self.logger.handlers):
            if isinstance(handler, TkTextHandler):
                self.logger.removeHandler(handler)
                handler.close()

        # Criar handler personalizado
        self.tk_handler = TkTextHandler(self.log_text)
        self.tk_handler.setLevel(logging.INFO)
        self.logger.addHandler(self.tk_handler)
        
        self.logger.info("✅ Sistema de upload inicializado e pronto")

    def _schedule_ui_poll(self) -> None:
        if self._closing:
            return
        try:
            self._ui_after_id = self.frame.after(100, self._process_ui_queue)
        except tk.TclError:
            self._ui_after_id = None

    def _process_ui_queue(self) -> None:
        """Aplica na thread do Tk as atualizações produzidas pelo worker."""
        self._ui_after_id = None
        if self._closing:
            return
        try:
            while True:
                event, values = self._ui_queue.get_nowait()
                if event == "progress":
                    self._apply_progress(*values)
                elif event == "finalize":
                    self._apply_finalize(*values)
        except queue.Empty:
            pass
        self._schedule_ui_poll()

    def _apply_progress(self, current: int, total: int, action: str = "") -> None:
        total_safe = max(total, 1)
        progress = min(max(current / total_safe, 0), 1)
        self.progress_bar.set(progress)
        self.progress_label.configure(
            text=f"Progresso: {current}/{total}",
            text_color=COLORS["muted"],
        )
        if action:
            self.current_action_label.configure(text=action)

    def _apply_finalize(
        self,
        success_count: int,
        total_files: int,
        error: str | None = None,
    ) -> None:
        self._processing = False
        self.progress_bar.set(1)

        if error:
            self.progress_label.configure(
                text=f"Processamento falhou: {error}",
                text_color=COLORS["danger"],
            )
            messagebox.showerror("Erro no Processamento", f"Falha no processamento:\n{error}")
        else:
            self.progress_label.configure(
                text=f"Processamento concluído: {success_count}/{total_files} sucessos",
                text_color=COLORS["success"],
            )
            self.current_action_label.configure(text="")
            if success_count == total_files:
                messagebox.showinfo(
                    "Processamento Concluído",
                    f"Todos os {total_files} arquivo(s) processados com sucesso!",
                )
            else:
                messagebox.showwarning(
                    "Processamento Parcial",
                    f"{success_count}/{total_files} arquivo(s) processados com sucesso.",
                )

        if success_count > 0:
            self._run_post_import_maintenance()

    def shutdown(self) -> None:
        """Interrompe callbacks de interface e desconecta o log da aba."""
        if self._closing:
            return
        self._closing = True
        if self._ui_after_id is not None:
            try:
                self.frame.after_cancel(self._ui_after_id)
            except tk.TclError:
                pass
            self._ui_after_id = None

        handler = getattr(self, "tk_handler", None)
        if handler is not None:
            if handler in self.logger.handlers:
                self.logger.removeHandler(handler)
            handler.close()

        while True:
            try:
                self._ui_queue.get_nowait()
            except queue.Empty:
                break

    def _browse_file(self, file_type: str):
        """Abre diálogo para seleção de arquivo."""
        file_config = self.FILE_TYPES[file_type]
        extensions = file_config['extensions']
        description = file_config['description']

        filetypes = [
            (description, '*' + ' *'.join(extensions)),
            ("Todos os arquivos", "*.*")
        ]

        # Para PRD, permitir múltiplos arquivos
        if file_type == 'PRD':
            file_paths = filedialog.askopenfilenames(
                title=f"Selecionar um ou mais {description}",
                filetypes=filetypes
            )

            if file_paths:
                entry = self.file_entries[file_type]
                entry.delete(0, tk.END)
                entry.insert(0, self.MULTI_FILE_SEPARATOR.join(file_paths))

                self.logger.info(
                    f"📁 {len(file_paths)} arquivo(s) PRD selecionado(s): "
                    + ", ".join(os.path.basename(p) for p in file_paths)
                )
            return

        # PA e CNES continuam como arquivo único
        file_path = filedialog.askopenfilename(
            title=f"Selecionar {description}",
            filetypes=filetypes
        )

        if file_path:
            entry = self.file_entries[file_type]
            entry.delete(0, tk.END)
            entry.insert(0, file_path)
            self.logger.info(f"📁 Arquivo selecionado: {os.path.basename(file_path)}")
            
    def _get_selected_file_paths(self, file_type: str) -> List[str]:
        """Retorna a lista de caminhos selecionados para o tipo informado."""
        entry = self.file_entries.get(file_type)

        if not entry:
            return []

        value = entry.get().strip()
        if not value:
            return []

        if file_type == 'PRD':
            return [
                p.strip()
                for p in value.split(self.MULTI_FILE_SEPARATOR)
                if p.strip()
            ]

        return [value]

    def _validate_files(self):
        """Valida os arquivos selecionados por meio do serviço de importação."""
        files = [
            (file_type, path)
            for file_type in self.file_entries
            for path in self._get_selected_file_paths(file_type)
        ]
        if not files:
            messagebox.showwarning("Validação", "Nenhum arquivo selecionado para validação.")
            return
        self.logger.info("🔍 Iniciando validação dos arquivos...")
        results = self.import_service.validate_files(files)
        valid_count = 0
        for file_type, _path, valid, message in results:
            if valid:
                valid_count += 1
                self.logger.info(f"✅ {file_type}: {message}")
            else:
                self.logger.warning(f"❌ {file_type}: {message}")
        self.logger.info(f"📊 Validação concluída: {valid_count}/{len(results)} arquivos válidos")

    def _process_all_files(self):
        """Processa todos os arquivos selecionados em thread separada."""
        if self._processing:
            messagebox.showinfo("Processamento", "Já existe um processamento em andamento.")
            return
        
        # Coletar arquivos para processamento
        files_to_process = []
        for file_type in self.file_entries.keys():
            for file_path in self._get_selected_file_paths(file_type):
                if file_path and os.path.exists(file_path):
                    files_to_process.append((file_type, file_path))
        
        if not files_to_process:
            messagebox.showwarning("Processamento", "Nenhum arquivo válido selecionado.")
            return
        
        # Confirmar processamento
        qtd_prd = sum(1 for t, _ in files_to_process if t == 'PRD')
        qtd_pa = sum(1 for t, _ in files_to_process if t == 'PA')
        qtd_cnes = sum(1 for t, _ in files_to_process if t == 'CNES')

        if not messagebox.askyesno(
            "Confirmar Processamento",
            f"Processar {len(files_to_process)} arquivo(s)?\n\n"
            f"PRD: {qtd_prd}\n"
            f"PA: {qtd_pa}\n"
            f"CNES: {qtd_cnes}\n\n"
            "Esta operação pode levar alguns minutos."
        ):
            return
        
        # Configurar interface para processamento
        self._processing = True
        self._reset_progress(len(files_to_process))
        self.logger.info(f"🚀 Iniciando processamento de {len(files_to_process)} arquivo(s)")
        
        # Executar em thread separada
        self._current_thread = threading.Thread(
            target=self._process_files_worker,
            args=(files_to_process,),
            daemon=True
        )
        self._current_thread.start()
        
            

    def _process_files_worker(self, files_to_process: List[Tuple[str, str]]):
        """Executa o serviço fora da thread da interface."""
        try:
            summary = self.import_service.process_files(
                files_to_process,
                self._update_progress,
            )
            self._finalize_processing(summary.success_count, summary.total_files)
        except Exception as e:
            self.logger.error(f"💥 Erro geral no processamento: {e}")
            self._finalize_processing(0, len(files_to_process), str(e))
        
    

        

    def _reset_progress(self, total_steps: int):
        """Reinicia a barra de progresso."""
        self.progress_total = max(total_steps, 1)
        self.progress_bar.set(0)
        self.progress_label.configure(
            text=f"Progresso: 0/{total_steps}",
            text_color=COLORS["muted"]
        )
        self.current_action_label.configure(text="")

    def _update_progress(self, current: int, total: int, action: str = ""):
        """Atualiza a barra de progresso de forma thread-safe."""
        if not self._closing:
            self._ui_queue.put(("progress", (current, total, action)))

    def _finalize_processing(self, success_count: int, total_files: int, error: str = None):
        """Finaliza o processamento e atualiza a UI."""
        if not self._closing:
            self._ui_queue.put(
                ("finalize", (success_count, total_files, error))
            )

    def _run_post_import_maintenance(self):
        """Executa manutenção pós-importação."""
        try:
            self.logger.info("🛠️ Executando manutenção pós-importação...")
            self.db.post_import_maintenance()
            self.logger.info("✅ Manutenção concluída")
        except Exception as e:
            self.logger.warning(f"⚠️ Manutenção pós-importação falhou: {e}")

    def _clear_fields(self):
        """Limpa todos os campos e logs."""
        for entry in self.file_entries.values():
            entry.delete(0, tk.END)
        
        self._clear_log()
        self.progress_bar.set(0)
        self.progress_label.configure(
            text="Campos limpos",
            text_color=COLORS["muted"]
        )
        self.current_action_label.configure(text="")
        self.logger.info("🧹 Todos os campos foram limpos")

    def _clear_log(self):
        """Limpa o conteúdo do log."""
        self.log_text.configure(state='normal')
        self.log_text.delete(1.0, tk.END)
        self.log_text.configure(state='disabled')
        
        

    def _export_log(self):
        """Exporta o log para arquivo de texto."""
        file_path = filedialog.asksaveasfilename(
            title="Exportar Log",
            defaultextension=".txt",
            filetypes=[("Arquivos de texto", "*.txt"), ("Todos os arquivos", "*.*")]
        )
        
        if file_path:
            try:
                content = self.log_text.get(1.0, tk.END)
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write(f"Log do Sistema SIA/SUS - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                    f.write("=" * 60 + "\n")
                    f.write(content)
                
                self.logger.info(f"💾 Log exportado: {file_path}")
                messagebox.showinfo("Exportação", f"Log exportado com sucesso!\n\n{file_path}")
                
            except Exception as e:
                self.logger.error(f"❌ Falha ao exportar log: {e}")
                messagebox.showerror("Erro", f"Falha ao exportar log:\n{e}")

    def _show_statistics(self):
        """Exibe estatísticas do processamento atual."""
        prd_files = self._get_selected_file_paths('PRD')
        pa_files = self._get_selected_file_paths('PA')
        cnes_files = self._get_selected_file_paths('CNES')

        total_files = len(prd_files) + len(pa_files) + len(cnes_files)

        stats_text = (
            f"📊 Estatísticas do Upload:\n\n"
            f"• Arquivos PRD selecionados: {len(prd_files)}\n"
            f"• Arquivos PA selecionados: {len(pa_files)}\n"
            f"• Arquivos CNES selecionados: {len(cnes_files)}\n"
            f"• Total de arquivos: {total_files}\n"
            f"• Status: {'🟢 Pronto' if not self._processing else '🟡 Processando...'}"
        )

        messagebox.showinfo("Estatísticas do Upload", stats_text)
