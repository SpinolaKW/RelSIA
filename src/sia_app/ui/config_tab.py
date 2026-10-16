import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import customtkinter as ctk
from PIL import Image, ImageTk, ImageOps
import os
from pathlib import Path
from typing import Optional, Dict, Any
import logging

from sia_app.database.models import ConfigModel
from sia_app.services.auth_service import AuthService, UserSession
from sia_app.ui.components.user_management import UserManagementPanel

from sia_app.ui.theme import COLORS, apply_theme, FONT_FAMILY

class ConfigTab:
    """
    Aba de configurações do sistema com interface moderna e validações robustas.
    """
    
    # Constantes de configuração
    LOGO_MAX_SIZE = (100, 100)  # Tamanho máximo para preview
    LOGO_PREVIEW_SIZE = (80, 80)  # Tamanho do preview
    SUPPORTED_IMAGE_FORMATS = [("Imagens", "*.png *.jpg *.jpeg *.bmp *.gif *.tiff")]
    
    def __init__(
        self,
        parent,
        db,
        settings,
        logger: logging.Logger,
        auth_service: AuthService,
        session: UserSession,
        on_session_changed=None,
    ):
        """
        Inicializa a aba de configurações.
        
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
        self.auth_service = auth_service
        self.session = session
        self.on_session_changed = on_session_changed
        self.current_logo_path: Optional[str] = None
        self.logo_photo: Optional[ImageTk.PhotoImage] = None 
        
        apply_theme()

        self.frame = ctk.CTkFrame(parent, fg_color=COLORS["bg"])
        self._setup_ui()
        self._load_current_settings()
    
    def _setup_ui(self) -> None:
        """Configura a interface do usuário de forma organizada."""
        # Container principal com scrollbar
        self._create_scrollable_container()
        
        # Título da seção
        self._create_title_section()

        # Usuários ficam imediatamente abaixo do cabeçalho da tela.
        self._create_user_section()
        
        # Seção do logo
        self._create_logo_section()
        
        # Seção de dados institucionais
        self._create_institution_section()
        
        # Seção de botões de ação
        self._create_action_buttons_section()

    def _create_user_section(self) -> None:
        """Cria o gerenciamento de contas exclusivo do administrador."""
        self.user_management = UserManagementPanel(
            self.scrollable_frame,
            self.auth_service,
            self.session,
            self.logger,
            self.on_session_changed,
        )
    
    def _create_scrollable_container(self) -> None:
        """Cria container principal moderno com rolagem."""
        self.scrollable_frame = ctk.CTkScrollableFrame(
            self.frame,
            fg_color=COLORS["bg"],
            corner_radius=0
        )
        self.scrollable_frame.pack(fill="both", expand=True)
    
    def _create_title_section(self) -> None:
        """Cria seção de título moderna."""
        header = ctk.CTkFrame(self.scrollable_frame, fg_color="transparent")
        header.pack(fill="x", padx=18, pady=(18, 8))

        ctk.CTkLabel(
            header,
            text="Configurações do Sistema",
            font=(FONT_FAMILY, 22, "bold"),
            text_color=COLORS["text"],
            anchor="center"
        ).pack(anchor="center")

        ctk.CTkLabel(
            header,
            text="Configure o logo e os dados institucionais utilizados nos relatórios",
            font=(FONT_FAMILY, 12),
            text_color=COLORS["muted"],
            anchor="center"
        ).pack(anchor="center", pady=(2, 0))
    
    def _create_logo_section(self) -> None:
        """Cria seção moderna de configuração do logo."""
        logo_card = ctk.CTkFrame(
            self.scrollable_frame,
            fg_color=COLORS["card"],
            border_color=COLORS["border"],
            border_width=1,
            corner_radius=12
        )
        logo_card.pack(fill="x", padx=18, pady=(8, 14))

        ctk.CTkLabel(
            logo_card,
            text="Logo da Instituição",
            font=(FONT_FAMILY, 13, "bold"),
            text_color=COLORS["text"]
        ).pack(anchor="w", padx=18, pady=(14, 8))

        logo_container = ctk.CTkFrame(logo_card, fg_color="transparent")
        logo_container.pack(fill="x", padx=18, pady=(4, 18))

        logo_container.columnconfigure(0, weight=0)
        logo_container.columnconfigure(1, weight=0)
        logo_container.columnconfigure(2, weight=1)

        self._create_logo_preview(logo_container)
        self._create_logo_controls(logo_container)
        self._create_logo_info(logo_container)
    
    def _create_logo_preview(self, parent) -> None:
        """Coluna 0: preview do logo."""
        preview_container = ctk.CTkFrame(
            parent,
            width=120,
            height=100,
            fg_color="#F8FAFC",
            border_color=COLORS["border"],
            border_width=1,
            corner_radius=8
        )
        preview_container.grid(row=0, column=0, sticky="nw", padx=(0, 20))
        preview_container.pack_propagate(False)

        self.logo_preview = tk.Label(
            preview_container,
            text="Logo\nNão\nSelecionado",
            background="#F8FAFC",
            foreground=COLORS["muted"],
            anchor="center",
            justify="center",
            font=(FONT_FAMILY, 9)
        )
        self.logo_preview.pack(fill="both", expand=True, padx=8, pady=8)
        
    def _create_logo_controls(self, parent) -> None:
        """Coluna 1: botões Selecionar/Remover."""
        controls_frame = ctk.CTkFrame(parent, fg_color="transparent")
        controls_frame.grid(row=0, column=1, sticky="nw", padx=(0, 20))

        ctk.CTkButton(
            controls_frame,
            text="📁 Selecionar Logo",
            command=self._select_logo,
            width=150,
            height=36,
            corner_radius=7,
            fg_color=COLORS["primary"],
            hover_color=COLORS["primary_dark"],
            text_color="#FFFFFF",
            font=(FONT_FAMILY, 12, "bold")
        ).pack(anchor="w", pady=(0, 8))

        ctk.CTkButton(
            controls_frame,
            text="🗑️ Remover Logo",
            command=self._remove_logo,
            width=150,
            height=36,
            corner_radius=7,
            fg_color="#FFFFFF",
            hover_color="#FFF1F1",
            border_color=COLORS["danger"],
            border_width=1,
            text_color=COLORS["danger"],
            font=(FONT_FAMILY, 12, "bold")
        ).pack(anchor="w")

    def _create_logo_info(self, parent) -> None:
        """Coluna 2: caminho do arquivo e dicas."""
        info_frame = ctk.CTkFrame(parent, fg_color="transparent")
        info_frame.grid(row=0, column=2, sticky="nsew")

        self.logo_path_label = ctk.CTkLabel(
            info_frame,
            text="Nenhum arquivo selecionado",
            text_color=COLORS["muted"],
            font=(FONT_FAMILY, 12),
            wraplength=650,
            justify="left",
            anchor="w"
        )
        self.logo_path_label.pack(anchor="w", fill="x", pady=(0, 8))

        ctk.CTkLabel(
            info_frame,
            text=(
                "Formatos suportados: PNG, JPG, JPEG, BMP, GIF, TIFF\n"
                "Tamanho recomendado: 100x100 pixels\n"
                "Fundo transparente para melhor resultado"
            ),
            text_color=COLORS["text"],
            font=(FONT_FAMILY, 11),
            justify="left",
            anchor="w"
        ).pack(anchor="w")
    
    def _create_institution_section(self) -> None:
        """Cria seção moderna de dados institucionais."""
        inst_card = ctk.CTkFrame(
            self.scrollable_frame,
            fg_color=COLORS["card"],
            border_color=COLORS["border"],
            border_width=1,
            corner_radius=12
        )
        inst_card.pack(fill="x", padx=18, pady=(0, 14))

        ctk.CTkLabel(
            inst_card,
            text="Dados da Instituição",
            font=(FONT_FAMILY, 13, "bold"),
            text_color=COLORS["text"]
        ).pack(anchor="w", padx=18, pady=(14, 8))

        form = ctk.CTkFrame(inst_card, fg_color="transparent")
        form.pack(fill="x", padx=18, pady=(4, 18))

        form.columnconfigure(1, weight=1)

        campos = [
            ("Nome da Instituição:", "inst1_entry"),
            ("Secretaria/Departamento:", "inst2_entry"),
            ("Divisão/Setor:", "inst3_entry"),
        ]

        for row, (label_text, attr_name) in enumerate(campos):
            ctk.CTkLabel(
                form,
                text=label_text,
                font=(FONT_FAMILY, 12, "bold" if row == 0 else "normal"),
                text_color=COLORS["text"],
                anchor="w",
                width=180
            ).grid(row=row, column=0, sticky="w", pady=8, padx=(0, 12))

            entry = ctk.CTkEntry(
                form,
                height=36,
                corner_radius=7,
                border_color=COLORS["border"],
                fg_color="#FFFFFF",
                text_color=COLORS["text"],
                font=(FONT_FAMILY, 12)
            )
            entry.grid(row=row, column=1, sticky="ew", pady=8)

            setattr(self, attr_name, entry)
    
    def _create_action_buttons_section(self) -> None:
        """Cria seção moderna de botões de ação."""
        button_frame = ctk.CTkFrame(self.scrollable_frame, fg_color="transparent")
        button_frame.pack(fill="x", padx=18, pady=(0, 18))

        button_container = ctk.CTkFrame(button_frame, fg_color="transparent")
        button_container.pack(anchor="center")

        ctk.CTkButton(
            button_container,
            text="Salvar Configurações",
            command=self._save_settings,
            width=180,
            height=36,
            corner_radius=7,
            fg_color=COLORS["primary"],
            hover_color=COLORS["primary_dark"],
            text_color="#FFFFFF",
            font=(FONT_FAMILY, 12, "bold")
        ).pack(side="left", padx=(0, 10))

        ctk.CTkButton(
            button_container,
            text="Restaurar Padrões",
            command=self._reset_to_defaults,
            width=170,
            height=36,
            corner_radius=7,
            fg_color="#FFFFFF",
            hover_color=COLORS["primary_soft"],
            border_color=COLORS["border"],
            border_width=1,
            text_color=COLORS["text"],
            font=(FONT_FAMILY, 12, "bold")
        ).pack(side="left")
    
    def _select_logo(self) -> None:
        """Seleciona arquivo de logo com validações."""
        file_path = filedialog.askopenfilename(
            title="Selecionar Logo da Instituição",
            filetypes=self.SUPPORTED_IMAGE_FORMATS
        )
        
        if not file_path:
            return
        
        try:
            self._validate_and_load_logo(file_path)
            
        except Exception as e:
            self.logger.error(f"Erro ao carregar logo: {e}")
            messagebox.showerror(
                "Erro", 
                f"Não foi possível carregar a imagem:\n{str(e)}"
            )
    
    def _validate_and_load_logo(self, file_path: str) -> None:
        """Valida e carrega o arquivo de logo."""
        # Validar tamanho do arquivo (máximo 5MB)
        file_size = os.path.getsize(file_path) / (1024 * 1024)  # MB
        if file_size > 5:
            raise ValueError("Arquivo muito grande. Tamanho máximo: 5MB")
        
        # Carregar e validar imagem
        image = Image.open(file_path)
        
        # Verificar dimensões
        width, height = image.size
        if width > 1000 or height > 1000:
            self.logger.warning(f"Logo com dimensões grandes: {width}x{height}")
        
        # Processar imagem para preview
        processed_image = self._process_logo_for_preview(image)

        # >>> mantenha referência forte no atributo da classe
        self.logo_photo = ImageTk.PhotoImage(processed_image)

        # Atualizar interface
        self.logo_preview.configure(
            image=self.logo_photo,
            text="",
            background='white'
        )

        # (opcional, redundância para evitar GC em alguns ambientes)
        self.logo_preview.image = self.logo_photo

        self.logo_path_label.configure(
            text=file_path,
            text_color=COLORS["success"]
        )
        self.current_logo_path = file_path

        self.logger.info(
            f"Logo carregado com sucesso: {file_path} "
            f"(size={processed_image.size}, mode={processed_image.mode})"
        )
    
    def _process_logo_for_preview(self, image: Image.Image) -> Image.Image:
        """Processa a imagem do logo para preview."""
        # Converter para RGB se necessário
        if image.mode in ('RGBA', 'LA'):
            # Criar fundo branco para imagens com transparência
            background = Image.new('RGB', image.size, (255, 255, 255))
            background.paste(image, mask=image.split()[-1])
            image = background
        elif image.mode != 'RGB':
            image = image.convert('RGB')
        
        # Redimensionar mantendo aspect ratio
        #image.thumbnail(self.LOGO_PREVIEW_SIZE, Image.Resampling.LANCZOS)
        image = ImageOps.contain(image, self.LOGO_PREVIEW_SIZE)
        
        return image
    
    def _remove_logo(self) -> None:
        """Remove o logo atual."""
        self.logo_preview.configure(
            image="",
            text="Logo\nNão\nSelecionado",
            background="#F8FAFC",
            foreground=COLORS["muted"]
        )
        
        self.logo_preview.image = None  # <- limpa ref do label
        self.logo_photo = None          # <- limpa ref da classe
        
        self.logo_path_label.configure(
            text="Nenhum arquivo selecionado",
            text_color=COLORS["muted"]
        )
        self.current_logo_path = None
        self.logo_photo = None
    
    def _load_current_settings(self) -> None:
        """Carrega as configurações atuais do sistema."""
        try:
            config_model = ConfigModel(self.db)
            config = config_model.obter_config()
            
            if not config:
                self.logger.warning("Nenhuma configuração encontrada no banco")
                return
            
            # Carregar logo
            logo_path = config.get('logo_path')
            if logo_path and os.path.exists(logo_path):
                try:
                    self._validate_and_load_logo(logo_path)
                except Exception as e:
                    self.logger.error(f"Erro ao carregar logo salvo: {e}")
                    self._remove_logo()
            
            # Carregar dados institucionais
            self.inst1_entry.insert(0, config.get('inst1', ''))
            self.inst2_entry.insert(0, config.get('inst2', ''))
            self.inst3_entry.insert(0, config.get('inst3', ''))
            
            self.logger.info("Configurações atuais carregadas com sucesso")
            
        except Exception as e:
            self.logger.error(f"Erro ao carregar configurações: {e}")
            messagebox.showerror(
                "Erro", 
                f"Falha ao carregar configurações:\n{str(e)}"
            )
    
    def _save_settings(self) -> None:
        """Salva as configurações no banco de dados."""
        try:
            if not self._validate_settings():
                return

            # Valida toda a lista antes de iniciar qualquer gravação. Os botões
            # Novo/Alterar/Excluir apenas preparam a lista; este é o único ponto
            # que confirma as mudanças de contas.
            if self.user_management.has_pending_changes():
                self.user_management.validate_pending_changes()
            
            config_model = ConfigModel(self.db)
            
            config_dict = self._build_config_dict()
            
            # Salvar no banco
            success = config_model.salvar_config(config_dict)
            
            if success:
                # Atualizar configurações em memória
                for key, value in config_dict.items():
                    self.settings.set(key, value)
                if not self.settings.save_settings():
                    raise Exception("Falha ao salvar o arquivo de configurações")

                if self.user_management.has_pending_changes():
                    self.user_management.save_pending_changes()
                
                self._show_success_message()
                self.logger.info("Configurações salvas com sucesso")
            else:
                raise Exception("Falha ao salvar no banco de dados")
                
        except Exception as e:
            self.logger.error(f"Erro ao salvar configurações: {e}")
            messagebox.showerror(
                "Erro", 
                f"Falha ao salvar configurações:\n{str(e)}"
            )
    
    def _validate_settings(self) -> bool:
        """Valida as configurações antes de salvar."""
        # Validar campos obrigatórios
        if not self.inst1_entry.get().strip():
            messagebox.showwarning(
                "Campo Obrigatório", 
                "O campo 'Nome da Instituição' é obrigatório."
            )
            self.inst1_entry.focus_set()
            return False
        
        return True
    
    def _build_config_dict(self) -> Dict[str, Any]:
        """Constrói dicionário de configurações."""
        return {
            'logo_path': self.current_logo_path or '',
            'inst1': self.inst1_entry.get().strip(),
            'inst2': self.inst2_entry.get().strip(),
            'inst3': self.inst3_entry.get().strip()
        }
    
    def _show_success_message(self) -> None:
        """Exibe mensagem de sucesso personalizada."""
        messagebox.showinfo(
            "Sucesso", 
            "✅ Configurações salvas com sucesso!\n\n"
            "As configurações e as alterações de usuários foram aplicadas."
        )
    
    def _reset_to_defaults(self) -> None:
        """Restaura as configurações padrão."""
        if messagebox.askyesno(
            "Restaurar Padrões",
            "Tem certeza que deseja restaurar as configurações padrão?\n\n"
            "Os dados institucionais serão limpos. Os usuários não serão alterados."
        ):
            try:
                # Restaurar padrões
                self._remove_logo()
                self.inst1_entry.delete(0, tk.END)
                self.inst2_entry.delete(0, tk.END)
                self.inst3_entry.delete(0, tk.END)
                
                messagebox.showinfo(
                    "Sucesso", 
                    "Configurações restauradas para os valores padrão."
                )
                self.logger.info("Configurações restauradas para padrão")
                
            except Exception as e:
                self.logger.error(f"Erro ao restaurar padrões: {e}")
                messagebox.showerror(
                    "Erro", 
                    f"Falha ao restaurar padrões:\n{str(e)}"
                )
