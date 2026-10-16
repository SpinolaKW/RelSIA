import tkinter as tk
from tkinter import ttk, filedialog, messagebox, simpledialog
import customtkinter as ctk
from sia_app.ui.components.design import PageHeader
import os
from typing import Dict, Any, Optional
import logging
from datetime import datetime

from sia_app.config.constants import Constants
from sia_app.database.backup_manager import BackupManager
from sia_app.database.operations import DatabaseOperations

from sia_app.ui.theme import COLORS, apply_theme, FONT_FAMILY

class DatabaseTab:
    """
    Aba de gerenciamento do banco de dados com interface moderna e operações robustas.
    """
    
    def __init__(self, parent, db, settings, logger: logging.Logger):
        """
        Inicializa a aba de gerenciamento do banco de dados.
        
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
        
        self._operation_in_progress = False
        
        self.backup_manager = BackupManager(self.db.db_path)
        self.db_operations = DatabaseOperations(db_connection=self.db)
        
        apply_theme()

        self.frame = ctk.CTkFrame(parent, fg_color=COLORS["bg"])
        self._setup_ui()
        self._refresh_status()
        
        # Variáveis de estado
        self._operation_in_progress = False

    def _setup_ui(self) -> None:
        """Configura a interface do usuário de forma organizada."""
        # Container principal
        main_frame = ctk.CTkScrollableFrame(
            self.frame,
            fg_color=COLORS["bg"],
            corner_radius=0
        )
        main_frame.pack(fill="both", expand=True)
        
        # Título
        self._create_title_section(main_frame)
        
        # Seção de operações
        self._create_operations_section(main_frame)
        
        # Seção de status e estatísticas
        self._create_status_section(main_frame)
        
        # Seção de log
        self._create_log_section(main_frame)

    def _create_title_section(self, parent):
        header = PageHeader(parent, 'Administração', 'Banco de dados', 'Proteja suas informações com backups e acompanhe a manutenção do banco.')
        header.pack(fill="x", padx=18, pady=(24, 18))
        
    def _create_operations_section(self, parent) -> None:
        """Cria a seção moderna de botões de operação."""
        operations_card = ctk.CTkFrame(
            parent,
            fg_color=COLORS["card"],
            border_color=COLORS["border"],
            border_width=1,
            corner_radius=12
        )
        operations_card.pack(fill="x", padx=18, pady=(8, 14))

        ctk.CTkLabel(
            operations_card,
            text="Operações do Banco de Dados",
            font=(FONT_FAMILY, 13, "bold"),
            text_color=COLORS["text"]
        ).pack(anchor="w", padx=18, pady=(14, 8))

        button_grid = ctk.CTkFrame(operations_card, fg_color="transparent")
        button_grid.pack(fill="x", padx=18, pady=(4, 18))

        for col in range(3):
            button_grid.grid_columnconfigure(col, weight=1, uniform="db_buttons")

        self._create_operation_button(
            button_grid, 0, 0,
            "💾 Backup Simples",
            "Cria backup completo do banco (.sqlite.backup)",
            self._backup_sqlite,
            fg_color=COLORS["primary"],
            hover_color=COLORS["primary_dark"],
            text_color="#FFFFFF",
            border_color=COLORS["primary"]
        )

        self._create_operation_button(
            button_grid, 0, 1,
            "🗜 Backup Compactado",
            "Cria backup compactado (.zip, sem criptografia)",
            self._backup_zip,
            fg_color=COLORS["success"],
            hover_color="#15803D",
            text_color="#FFFFFF",
            border_color=COLORS["success"]
        )

        self._create_operation_button(
            button_grid, 0, 2,
            "🔄 Restaurar Backup",
            "Restaura banco a partir de arquivo de backup",
            self._restore,
            fg_color="#FFFFFF",
            hover_color=COLORS["primary_soft"],
            text_color=COLORS["primary"],
            border_color=COLORS["primary"]
        )

        self._create_operation_button(
            button_grid, 1, 0,
            "🧹 Limpar Banco",
            "Remove dados operacionais e preserva usuários",
            self._clear,
            fg_color=COLORS["danger"],
            hover_color="#B91C1C",
            text_color="#FFFFFF",
            border_color=COLORS["danger"]
        )

        self._create_operation_button(
            button_grid, 1, 1,
            "⚡ Otimizar Banco",
            "Executa manutenção e otimização do banco",
            self._optimize_database,
            fg_color=COLORS["orange"],
            hover_color="#C2410C",
            text_color="#FFFFFF",
            border_color=COLORS["orange"]
        )

        self._create_operation_button(
            button_grid, 1, 2,
            "📊 Atualizar Status",
            "Atualiza informações do banco",
            self._refresh_status,
            fg_color="#FFFFFF",
            hover_color=COLORS["primary_soft"],
            text_color=COLORS["text"],
            border_color=COLORS["border"]
        )

    def _create_operation_button(
        self,
        parent,
        row: int,
        column: int,
        text: str,
        tooltip: str,
        command,
        fg_color: str = "#FFFFFF",
        hover_color: str = "#EFF5F2",
        text_color: str = "#102A56",
        border_color: str = "#DDE5F2"
    ) -> None:
        """Cria um botão de operação moderno."""
        button = ctk.CTkButton(
            parent,
            text=text,
            command=command,
            height=38,
            corner_radius=7,
            fg_color=fg_color,
            hover_color=hover_color,
            text_color=text_color,
            border_color=border_color,
            border_width=1,
            font=(FONT_FAMILY, 12, "bold")
        )
        button.grid(row=row, column=column, padx=6, pady=6, sticky="ew")

        self._create_tooltip(button, tooltip)

    def _create_tooltip(self, widget, text: str) -> None:
        """Cria uma tooltip moderna sem acumular janelas."""
        tooltip_data = {"window": None, "after_id": None}

        def destroy_tooltip():
            if tooltip_data["after_id"]:
                try:
                    widget.after_cancel(tooltip_data["after_id"])
                except Exception:
                    pass
                tooltip_data["after_id"] = None

            if tooltip_data["window"] is not None:
                try:
                    tooltip_data["window"].destroy()
                except Exception:
                    pass
                tooltip_data["window"] = None

        def show_tooltip(event=None):
            destroy_tooltip()

            tooltip = tk.Toplevel(widget)
            tooltip.wm_overrideredirect(True)
            tooltip.attributes("-topmost", True)

            x = widget.winfo_rootx() + 20
            y = widget.winfo_rooty() + widget.winfo_height() + 8
            tooltip.wm_geometry(f"+{x}+{y}")

            label = tk.Label(
                tooltip,
                text=text,
                background="#FFFFFF",
                foreground=COLORS["text"],
                relief="solid",
                borderwidth=1,
                font=(FONT_FAMILY, 9),
                padx=10,
                pady=6,
                wraplength=260,
                justify="left"
            )
            label.pack()

            tooltip_data["window"] = tooltip

        def schedule_tooltip(event=None):
            destroy_tooltip()
            tooltip_data["after_id"] = widget.after(500, show_tooltip)

        widget.bind("<Enter>", schedule_tooltip)
        widget.bind("<Leave>", lambda event: destroy_tooltip())
        widget.bind("<ButtonPress>", lambda event: destroy_tooltip())
        widget.bind("<Destroy>", lambda event: destroy_tooltip())
        
    def _create_status_section(self, parent) -> None:
        """Cria a seção moderna de status e estatísticas."""
        status_card = ctk.CTkFrame(
            parent,
            fg_color=COLORS["card"],
            border_color=COLORS["border"],
            border_width=1,
            corner_radius=12
        )
        status_card.pack(fill="x", padx=18, pady=(0, 14))

        ctk.CTkLabel(
            status_card,
            text="Status do Banco de Dados",
            font=(FONT_FAMILY, 13, "bold"),
            text_color=COLORS["text"]
        ).pack(anchor="w", padx=18, pady=(14, 8))

        self.status_label = ctk.CTkLabel(
            status_card,
            text="Carregando informações...",
            font=(FONT_FAMILY, 12, "bold"),
            text_color=COLORS["muted"],
            anchor="w"
        )
        self.status_label.pack(anchor="w", padx=18, pady=(0, 12))

        stats_grid = ctk.CTkFrame(status_card, fg_color="transparent")
        stats_grid.pack(fill="x", padx=18, pady=(0, 18))

        self.stats_data = {}

        stats_config = [
            ('total_prd', '📋 Registros de Produção:'),
            ('total_pa', '📝 Procedimentos Cadastrados:'),
            ('total_estabelecimentos', '🏥 Estabelecimentos:'),
            ('tamanho_mb', '💾 Tamanho do Banco:'),
            ('ultima_atualizacao', '🕒 Última Atualização:'),
            ('total_backups', '📦 Backups Disponíveis:')
        ]

        for i, (key, label_text) in enumerate(stats_config):
            row = i // 2
            col = (i % 2) * 2

            ctk.CTkLabel(
                stats_grid,
                text=label_text,
                font=(FONT_FAMILY, 12, "bold"),
                text_color=COLORS["text"],
                anchor="w"
            ).grid(row=row, column=col, sticky="w", pady=5, padx=(0, 8))

            self.stats_data[key] = ctk.CTkLabel(
                stats_grid,
                text="...",
                font=(FONT_FAMILY, 12, "bold"),
                text_color=COLORS["primary"],
                anchor="w"
            )
            self.stats_data[key].grid(row=row, column=col + 1, sticky="w", pady=5, padx=(0, 30))

        for col in range(4):
            stats_grid.grid_columnconfigure(col, weight=1)

    def _create_log_section(self, parent) -> None:
        """Cria a seção moderna de log de operações."""
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
            text="Log de Operações",
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

    def _log(self, message: str, level: str = "INFO") -> None:
        """
        Adiciona mensagem formatada ao log.
        
        Args:
            message: Mensagem a ser registrada
            level: Nível do log (INFO, WARNING, ERROR, SUCCESS)
        """
        timestamp = datetime.now().strftime("%H:%M:%S")
        
        # Cores baseadas no nível
        color_map = {
            "INFO": "#6c757d",
            "WARNING": "#ffc107", 
            "ERROR": "#dc3545",
            "SUCCESS": "#28a745"
        }
        
        color = color_map.get(level, "#6c757d")
        formatted_message = f"[{timestamp}] {message}"
        
        # Inserir no widget de texto
        self.log_text.insert("end", f"{formatted_message}\n")
        self.log_text.see("end")
        
        # Aplicar cor à última linha
        start_index = f"end - {len(formatted_message) + 1}c"
        self.log_text.tag_add(level, start_index, "end-1c")
        self.log_text.tag_config(level, foreground=color)
        
        # Log no sistema
        log_method = getattr(self.logger, level.lower(), self.logger.info)
        log_method(message)

    def _clear_log(self) -> None:
        """Limpa o conteúdo do log."""
        self.log_text.delete("1.0", "end")
        self._log("Log limpo", "INFO")

    def _export_log(self) -> None:
        """Exporta o log para arquivo de texto."""
        file_path = filedialog.asksaveasfilename(
            title="Exportar Log",
            defaultextension=".txt",
            filetypes=[("Arquivos de texto", "*.txt"), ("Todos os arquivos", "*.*")]
        )
        
        if file_path:
            try:
                content = self.log_text.get("1.0", "end-1c")
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write(f"Log do Sistema - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                    f.write("=" * 50 + "\n")
                    f.write(content)
                
                self._log(f"Log exportado para: {file_path}", "SUCCESS")
                messagebox.showinfo("Sucesso", f"Log exportado com sucesso!\n\n{file_path}")
                
            except Exception as e:
                self._log(f"Erro ao exportar log: {e}", "ERROR")
                messagebox.showerror("Erro", f"Falha ao exportar log: {e}")

    def _refresh_status(self) -> None:
        """Atualiza as informações de status do banco de dados."""
        if self._operation_in_progress:
            return
            
        try:
            self._log("Atualizando status do banco...", "INFO")
            
            # Obter estatísticas
            stats = self.db_operations.get_database_stats()
            
            # Atualizar status principal
            db_file = "sistema_sia.db"
            size = stats.get('tamanho_mb', 0)
            backup_count = self._get_backup_count()
            
            status_text = (
                f"📊 Banco: {db_file} | "
                f"💾 Tamanho: {size:.2f} MB | " 
                f"📦 Backups: {backup_count} | "
                f"✅ Status: Operacional"
            )
            self.status_label.configure(
                text=status_text,
                text_color=COLORS["success"]
            )
            
            # Atualizar estatísticas detalhadas
            self.stats_data["total_prd"].configure(
                text=f"{stats.get('total_tb_prd', 0):,}".replace(",", ".")
            )
            self.stats_data["total_pa"].configure(
                text=f"{stats.get('total_tb_pa', 0):,}".replace(",", ".")
            )
            self.stats_data["total_estabelecimentos"].configure(
                text=f"{stats.get('total_tb_estabelecimento', 0):,}".replace(",", ".")
            )
            self.stats_data["tamanho_mb"].configure(text=f"{size:.2f} MB")
            
            ultima_atualizacao = stats.get('ultima_atualizacao', 'Nunca')
            if ultima_atualizacao and ultima_atualizacao != 'Nunca':
                try:
                    # Formatar data
                    if 'T' in ultima_atualizacao:
                        dt = datetime.fromisoformat(ultima_atualizacao.replace('Z', '+00:00'))
                        ultima_atualizacao = dt.strftime("%d/%m/%Y %H:%M")
                except:
                    pass
            self.stats_data["ultima_atualizacao"].configure(text=ultima_atualizacao)
            self.stats_data["total_backups"].configure(text=str(backup_count))
            
            self._log("Status do banco atualizado com sucesso", "SUCCESS")
            
        except Exception as e:
            error_msg = f"Erro ao atualizar status: {e}"
            self._log(error_msg, "ERROR")
            self.status_label.configure(
                text="× Erro ao carregar status",
                text_color=COLORS["danger"]
            )

    def _get_backup_count(self) -> int:
        """Retorna a quantidade de backups disponíveis."""
        try:
            return len(self.backup_manager.listar_backups())
        except OSError:
            return 0

    def _backup_sqlite(self) -> None:
        """Cria backup simples do banco de dados."""
        if self._operation_in_progress:
            return
            
        self._operation_in_progress = True
        try:
            self._log("Iniciando backup simples...", "INFO")
            
            success, message = self.backup_manager.criar_backup_simples()
            
            if success:
                self._log(f"Backup criado: {message}", "SUCCESS")
                messagebox.showinfo(
                    "Backup Concluído", 
                    "✅ Backup simples criado com sucesso!\n\n"
                    "O arquivo foi salvo na pasta 'backups'."
                )
            else:
                self._log(f"Falha no backup: {message}", "ERROR")
                messagebox.showerror("Erro no Backup", message)
            
            self._refresh_status()
            
        except Exception as e:
            error_msg = f"Erro durante backup: {e}"
            self._log(error_msg, "ERROR")
            messagebox.showerror("Erro", f"Falha ao criar backup:\n{error_msg}")
        finally:
            self._operation_in_progress = False

    def _backup_zip(self) -> None:
        """Cria backup compactado do banco de dados."""
        if self._operation_in_progress:
            return
            
        try:
            self._operation_in_progress = True
            self._log("Iniciando backup compactado...", "INFO")
            
            success, message = self.backup_manager.criar_backup_compactado()
            
            if success:
                self._log(f"Backup ZIP criado: {message}", "SUCCESS")
                messagebox.showinfo(
                    "Backup Concluído", 
                    "✅ Backup compactado criado com sucesso!\n\n"
                    "O arquivo ZIP foi salvo na pasta 'data/backups'.\n\n"
                    "Observação: o ZIP não é criptografado."
                )
            else:
                self._log(f"Falha no backup ZIP: {message}", "ERROR")
                messagebox.showerror("Erro no Backup", message)
            
            self._refresh_status()
            
        except Exception as e:
            error_msg = f"Erro durante backup ZIP: {e}"
            self._log(error_msg, "ERROR")
            messagebox.showerror("Erro", f"Falha ao criar backup compactado:\n{error_msg}")
        finally:
            self._operation_in_progress = False

    def _restore(self) -> None:
        """Restaura backup do banco de dados."""
        if self._operation_in_progress:
            return
            
        file_path = filedialog.askopenfilename(
            title="Selecionar Arquivo de Backup", 
            filetypes=[
                ("Backups do Sistema", "*.backup *.zip"),
                ("Arquivos ZIP", "*.zip"),
                ("Backups SQLite", "*.backup"),
                ("Todos os arquivos", "*.*")
            ]
        )
        
        if not file_path:
            return
            
        try:
            # Confirmação de restauração
            confirm = messagebox.askyesno(
                "Confirmar Restauração", 
                "⚠️  ATENÇÃO: Restauração do Banco de Dados\n\n"
                "Tem certeza que deseja restaurar este backup?\n\n"
                "📋 Os dados operacionais atuais serão substituídos\n"
                "🔐 Usuários e permissões atuais serão preservados\n"
                "🔄 Esta operação não pode ser desfeita\n"
                "💾 Faça um backup antes de continuar\n\n"
                f"Arquivo: {os.path.basename(file_path)}"
            )
            
            if not confirm:
                self._log("Restauração cancelada pelo usuário", "WARNING")
                return
            
            self._operation_in_progress = True
            self._log(f"Iniciando restauração: {file_path}", "INFO")
            
            success, message = self.backup_manager.restaurar_backup(file_path)
            
            if success:
                self._log(f"Backup restaurado: {message}", "SUCCESS")
                messagebox.showinfo(
                    "Restauração Concluída", 
                    "✅ Backup restaurado com sucesso!\n\n"
                    "O sistema será atualizado com os dados do backup.\n"
                    "Usuários e permissões atuais foram preservados."
                )
                self._refresh_status()
            else:
                self._log(f"Falha na restauração: {message}", "ERROR")
                messagebox.showerror("Erro na Restauração", message)
                
        except Exception as e:
            error_msg = f"Erro durante restauração: {e}"
            self._log(error_msg, "ERROR")
            messagebox.showerror("Erro", f"Falha ao restaurar backup:\n{error_msg}")
        finally:
            self._operation_in_progress = False

    def _clear(self) -> None:
        """Limpa todos os dados do banco de dados."""
        if self._operation_in_progress:
            return
            
        # Confirmação rigorosa
        confirm = messagebox.askyesno(
            "Confirmar Limpeza do Banco", 
            "🚨  OPERAÇÃO IRREVERSÍVEL\n\n"
            "Tem ABSOLUTA certeza que deseja APAGAR TODOS os dados?\n\n"
            "🗑️  Os dados de produção serão permanentemente excluídos\n"
            "🔐  Usuários e permissões serão preservados\n"
            "💥  Esta operação NÃO PODE ser desfeita\n"
            "💾  Faça um backup antes de continuar\n\n"
            "Digite 'SIM' para prosseguir:",
            icon='warning'
        )
        
        if not confirm:
            self._log("Limpeza do banco cancelada", "WARNING")
            return
            
        # Confirmação adicional
        user_input = simpledialog.askstring(
            "Confirmação Final", 
            "Digite SIM para apagar os dados operacionais:"
        )
        
        if not user_input or user_input.upper() != "SIM":
            self._log("Limpeza do banco cancelada - confirmação inválida", "WARNING")
            messagebox.showinfo("Cancelado", "Limpeza do banco cancelada.")
            return
            
        try:
            self._operation_in_progress = True
            self._log("Iniciando limpeza do banco...", "WARNING")
            
            success, message = self.db_operations.limpar_banco()
            
            if success:
                self._log(f"Banco limpo: {message}", "SUCCESS")
                messagebox.showinfo(
                    "Limpeza Concluída", 
                    "✅ Banco de dados limpo com sucesso!\n\n"
                    "Os dados operacionais foram removidos.\n"
                    "Usuários e permissões foram preservados."
                )
                self._refresh_status()
            else:
                self._log(f"Falha na limpeza: {message}", "ERROR")
                messagebox.showerror("Erro na Limpeza", message)
                
        except Exception as e:
            error_msg = f"Erro durante limpeza: {e}"
            self._log(error_msg, "ERROR")
            messagebox.showerror("Erro", f"Falha ao limpar banco:\n{error_msg}")
        finally:
            self._operation_in_progress = False

    def _optimize_database(self) -> None:
        """Executa otimização do banco de dados com tratamento melhorado."""
        if self._operation_in_progress:
            return
            
        try:
            self._operation_in_progress = True
            self._log("Iniciando otimização do banco...", "INFO")
            
            # Diálogo informativo
            confirm = messagebox.askyesno(
                "Confirmar Otimização",
                "Esta operação otimiza o banco de dados para melhor desempenho.\n\n"
                "Recomendado quando o sistema estiver ocioso.\n"
                "Deseja continuar?"
            )
            
            if not confirm:
                self._log("Otimização cancelada pelo usuário", "INFO")
                return
            
            success, message = self.db_operations.otimizar_banco()
            
            if success:
                self._log(f"Otimização concluída: {message}", "SUCCESS")
                messagebox.showinfo("Sucesso", f"✅ {message}")
                self._refresh_status()
            else:
                self._log(f"Falha na otimização: {message}", "WARNING")
                messagebox.showwarning(
                    "Atenção", 
                    f"⚠️ {message}\n\n"
                    "O sistema continuará funcionando normalmente.\n"
                    "Tente novamente mais tarde."
                )
                    
        except Exception as e:
            error_msg = f"Erro durante otimização: {e}"
            self._log(error_msg, "ERROR")
            messagebox.showerror(
                "Erro", 
                f"❌ Falha na otimização:\n{error_msg}\n\n"
                "Esta é uma operação não crítica.\n"
                "O sistema continuará funcionando."
            )
        finally:
            self._operation_in_progress = False
