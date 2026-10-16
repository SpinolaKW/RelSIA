import tkinter as tk
from tkinter import ttk, messagebox
import customtkinter as ctk
from typing import Dict, List, Optional
import logging
from sia_app.database.connection import DatabaseConnection
from sia_app.services.establishment_service import EstablishmentService
from sia_app.ui.components.establishment_form import EstablishmentForm

from sia_app.ui.theme import COLORS, apply_theme, FONT_FAMILY

class EstabelecimentosTab:
    """
    Aba de gerenciamento de estabelecimentos com interface moderna e operações otimizadas.
    """
    
    # Configurações da interface
    COLUNAS = ["CO_CNES", "NO_FANTASIA", "CO_CEP"]
    HEADERS = {
        "CO_CNES": "CNES",
        "NO_FANTASIA": "Nome Fantasia", 
        "CO_CEP": "CEP"
    }
    COLUMN_WIDTHS = {
        "CO_CNES": 120,
        "NO_FANTASIA": 400,
        "CO_CEP": 100
    }
    
    def __init__(self, parent, db: DatabaseConnection, settings, logger: logging.Logger):
        """
        Inicializa a aba de estabelecimentos.
        
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
        self.establishment_service = EstablishmentService(self.db)
        self.estabelecimento_selecionado: Optional[Dict] = None
        
        # Estado da ordenação
        self.sort_column = 'CO_CNES'
        self.sort_ascending = True
        
        apply_theme()

        self.frame = ctk.CTkFrame(parent, fg_color=COLORS["bg"])
        self.establishment_form = EstablishmentForm(
            self.frame,
            COLORS,
            self._save_establishment,
        )
        self._setup_ui()
        self._load_estabelecimentos()
        
        # Cache para busca
        self._estabelecimentos_cache: List[Dict] = []

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
        
        # Controles de busca
        self._create_search_section(main_frame)
        
        # Lista de estabelecimentos
        self._create_list_section(main_frame)
        
        # Controles de ação
        self._create_action_section(main_frame)
        
        # Status
        self._create_status_section(main_frame)

    def _create_title_section(self, parent) -> None:
        """Cria a seção de título."""
        header = ctk.CTkFrame(parent, fg_color="transparent")
        header.pack(fill="x", padx=18, pady=(18, 8))

        ctk.CTkLabel(
            header,
            text="Cadastro de Estabelecimentos",
            font=(FONT_FAMILY, 22, "bold"),
            text_color=COLORS["text"],
            anchor="center"
        ).pack(anchor="center")

        ctk.CTkLabel(
            header,
            text="Consulte, adicione, edite e remova estabelecimentos cadastrados no sistema",
            font=(FONT_FAMILY, 12),
            text_color=COLORS["muted"],
            anchor="center"
        ).pack(anchor="center", pady=(2, 0))

    def _create_search_section(self, parent) -> None:
        """Cria a seção moderna de busca."""
        search_card = ctk.CTkFrame(
            parent,
            fg_color=COLORS["card"],
            border_color=COLORS["border"],
            border_width=1,
            corner_radius=12
        )
        search_card.pack(fill="x", padx=18, pady=(8, 14))

        ctk.CTkLabel(
            search_card,
            text="Buscar Estabelecimentos",
            font=(FONT_FAMILY, 13, "bold"),
            text_color=COLORS["text"]
        ).pack(anchor="w", padx=18, pady=(14, 8))

        search_container = ctk.CTkFrame(search_card, fg_color="transparent")
        search_container.pack(fill="x", padx=18, pady=(4, 18))

        ctk.CTkLabel(
            search_container,
            text="Buscar:",
            font=(FONT_FAMILY, 12, "bold"),
            text_color=COLORS["text"]
        ).pack(side="left", padx=(0, 10))

        self.search_entry = ctk.CTkEntry(
            search_container,
            height=36,
            corner_radius=7,
            border_color=COLORS["border"],
            fg_color="#FFFFFF",
            text_color=COLORS["text"],
            placeholder_text="Digite CNES, nome fantasia ou CEP",
            font=(FONT_FAMILY, 12)
        )
        self.search_entry.pack(side="left", fill="x", expand=True, padx=(0, 10))
        self.search_entry.bind("<KeyRelease>", self._handle_search)

        ctk.CTkButton(
            search_container,
            text="Buscar",
            command=self._execute_search,
            height=36,
            width=100,
            corner_radius=7,
            fg_color=COLORS["primary"],
            hover_color=COLORS["primary_dark"],
            text_color="#FFFFFF",
            font=(FONT_FAMILY, 12, "bold")
        ).pack(side="left", padx=(0, 8))

        ctk.CTkButton(
            search_container,
            text="Limpar",
            command=self._clear_search,
            height=36,
            width=100,
            corner_radius=7,
            fg_color="#FFFFFF",
            hover_color=COLORS["primary_soft"],
            border_color=COLORS["primary"],
            border_width=1,
            text_color=COLORS["primary"],
            font=(FONT_FAMILY, 12, "bold")
        ).pack(side="left")

    def _create_list_section(self, parent) -> None:
        """Cria a seção moderna da lista de estabelecimentos."""
        list_card = ctk.CTkFrame(
            parent,
            fg_color=COLORS["card"],
            border_color=COLORS["border"],
            border_width=1,
            corner_radius=12
        )
        list_card.pack(fill="both", expand=True, padx=18, pady=(0, 14))

        header = ctk.CTkFrame(list_card, fg_color="transparent")
        header.pack(fill="x", padx=18, pady=(14, 8))

        ctk.CTkLabel(
            header,
            text="Lista de Estabelecimentos",
            font=(FONT_FAMILY, 13, "bold"),
            text_color=COLORS["text"]
        ).pack(side="left")

        tree_area = ctk.CTkFrame(list_card, fg_color="transparent")
        tree_area.pack(fill="both", expand=True, padx=18, pady=(0, 18))

        self._create_treeview(tree_area)

    def _create_treeview(self, parent: ttk.Frame) -> None:
        """Cria a treeview com configurações otimizadas e ordenação."""
        # Container da treeview
        tree_container = ttk.Frame(parent)
        tree_container.pack(fill="both", expand=True)

        style = ttk.Style()
        style.configure(
            "ModernEstab.Treeview",
            background="#FFFFFF",
            fieldbackground="#FFFFFF",
            text_color=COLORS["text"],
            rowheight=30,
            font=(FONT_FAMILY, 10),
            borderwidth=0
        )
        style.configure(
            "ModernEstab.Treeview.Heading",
            font=(FONT_FAMILY, 10, "bold"),
            text_color=COLORS["text"],
            background="#F8FAFC",
            relief="flat"
        )
        style.map(
            "ModernEstab.Treeview",
            background=[("selected", "#114d8a")],
            text_color=[("selected", COLORS["text"])]
        )
        style.map(
            "ModernEstab.Treeview.Heading",
            background=[("active", "#EFF5F2")]
        )
        
        # Treeview
        self.tree = ttk.Treeview(
            tree_container,
            columns=self.COLUNAS,
            show="headings",
            height=18,
            selectmode="browse",
            style="ModernEstab.Treeview"
        )

        self.tree.tag_configure("linha_par", background="#F7F9FC")
        self.tree.tag_configure("linha_impar", background="#FFFFFF")
        
        # Configurar colunas COM ORDENAÇÃO E CENTRALIZAÇÃO
        for col in self.COLUNAS:
            # Configurar cabeçalho com função de ordenação
            self.tree.heading(
                col, 
                text=self.HEADERS[col],
                command=lambda c=col: self._sort_column(c)
            )
            
            # Configurar coluna com centralização para CNES e CEP
            if col in ['CO_CNES', 'CO_CEP']:
                self.tree.column(col, width=self.COLUMN_WIDTHS[col], anchor='center')  # Centralizado
            else:
                self.tree.column(col, width=self.COLUMN_WIDTHS[col], anchor='w')  # Alinhado à esquerda
        
        # Atualizar indicadores de ordenação iniciais
        self._update_sort_indicators()
        
        # Scrollbars
        v_scroll = ttk.Scrollbar(tree_container, orient="vertical", command=self.tree.yview)
        h_scroll = ttk.Scrollbar(tree_container, orient="horizontal", command=self.tree.xview)
        self.tree.configure(yscrollcommand=v_scroll.set, xscrollcommand=h_scroll.set)
        
        # Layout
        self.tree.grid(row=0, column=0, sticky="nsew")
        v_scroll.grid(row=0, column=1, sticky="ns")
        h_scroll.grid(row=1, column=0, sticky="ew")
        
        # Configurar grid
        tree_container.columnconfigure(0, weight=1)
        tree_container.rowconfigure(0, weight=1)
        
        # Bind de eventos
        self.tree.bind('<Double-1>', lambda e: self._edit_estabelecimento())
        self.tree.bind('<Return>', lambda e: self._edit_estabelecimento())

    def _sort_column(self, column: str) -> None:
        """
        Ordena a coluna quando clicada no cabeçalho.
        
        Args:
            column: Nome da coluna a ser ordenada
        """
        try:
            # Verificar se é a mesma coluna (inverter ordem) ou nova coluna
            if self.sort_column == column:
                self.sort_ascending = not self.sort_ascending
            else:
                self.sort_column = column
                self.sort_ascending = True
            
            # Atualizar indicadores visuais
            self._update_sort_indicators()
            
            # Recarregar dados ordenados
            self._load_estabelecimentos()
            
            self.logger.debug(f"Ordenação aplicada: {column} {'ASC' if self.sort_ascending else 'DESC'}")
            
        except Exception as e:
            self.logger.error(f"Erro ao ordenar coluna {column}: {e}")
            messagebox.showerror("Erro", f"Falha ao ordenar dados: {e}")

    def _update_sort_indicators(self) -> None:
        """Atualiza os indicadores visuais de ordenação nos cabeçalhos."""
        try:
            for col in self.COLUNAS:
                current_text = self.tree.heading(col)['text']
                
                # Remover setas anteriores
                clean_text = current_text.replace(' ▲', '').replace(' ▼', '')
                
                # Adicionar seta se for a coluna atual de ordenação
                if col == self.sort_column:
                    arrow = ' ▲' if self.sort_ascending else ' ▼'
                    self.tree.heading(col, text=clean_text + arrow)
                else:
                    self.tree.heading(col, text=clean_text)
                    
        except Exception as e:
            self.logger.error(f"Erro ao atualizar indicadores de ordenação: {e}")
            
    def _create_action_section(self, parent) -> None:
        """Cria a seção moderna de botões de ação."""
        action_frame = ctk.CTkFrame(parent, fg_color="transparent")
        action_frame.pack(fill="x", padx=18, pady=(0, 14))

        button_container = ctk.CTkFrame(action_frame, fg_color="transparent")
        button_container.pack(anchor="center")

        buttons = [
            ("➕ Adicionar", self._add_estabelecimento, COLORS["primary"], COLORS["primary_dark"], "#FFFFFF", COLORS["primary"]),
            ("✏️ Editar", self._edit_estabelecimento, "#FFFFFF", COLORS["primary_soft"], COLORS["primary"], COLORS["primary"]),
            ("🗑 Excluir", self._delete_estabelecimento, "#FFFFFF", "#FFF1F1", COLORS["danger"], COLORS["danger"]),
            ("🔄 Atualizar", self._load_estabelecimentos, "#FFFFFF", COLORS["primary_soft"], COLORS["text"], COLORS["border"]),
        ]

        for text, command, fg, hover, text_color, border in buttons:
            ctk.CTkButton(
                button_container,
                text=text,
                command=command,
                width=120,
                height=36,
                corner_radius=7,
                fg_color=fg,
                hover_color=hover,
                text_color=text_color,
                border_color=border,
                border_width=1,
                font=(FONT_FAMILY, 12, "bold")
            ).pack(side="left", padx=6)

    def _create_status_section(self, parent) -> None:
        """Cria a seção de status."""
        self.status_label = ctk.CTkLabel(
            parent,
            text="● Pronto para usar",
            font=(FONT_FAMILY, 12, "bold"),
            text_color=COLORS["muted"]
        )
        self.status_label.pack(anchor="w", padx=18, pady=(0, 18))

    def _load_estabelecimentos(self) -> None:
        """Carrega estabelecimentos na treeview de forma otimizada com ordenação."""
        try:
            self.status_label.configure(text="🔄 Carregando estabelecimentos...")
            
            # Buscar estabelecimentos COM ORDENAÇÃO
            estabelecimentos = self._buscar_estabelecimentos_ordenados()
            self._estabelecimentos_cache = estabelecimentos
            
            # Limpar treeview
            self.tree.delete(*self.tree.get_children())
            
            # Inserir dados
            for i, estab in enumerate(estabelecimentos):
                tag_linha = "linha_par" if i % 2 == 0 else "linha_impar"

                self.tree.insert(
                    "",
                    "end",
                    iid=str(estab["id"]),
                    values=(
                        estab.get("CO_CNES", ""),
                        estab.get("NO_FANTASIA", ""),
                        estab.get("CO_CEP", "") or ""
                    ),
                    tags=(tag_linha,)
                )
            
            # Atualizar status
            count = len(estabelecimentos)
            self.status_label.configure(
                text=f"✅ {count} estabelecimento(s) carregado(s) - Ordenado por: {self.HEADERS[self.sort_column]} {'↑' if self.sort_ascending else '↓'}",
                text_color='#28a745'
            )
            
            self.logger.info(f"Carregados {count} estabelecimentos ordenados por {self.sort_column}")
            
        except Exception as e:
            error_msg = f"Erro ao carregar estabelecimentos: {e}"
            self.status_label.configure(text=f"❌ {error_msg}", text_color='#dc3545')
            self.logger.error(error_msg)
            messagebox.showerror("Erro", f"Falha ao carregar estabelecimentos:\n{e}")

    def _buscar_estabelecimentos_ordenados(self) -> List[Dict]:
        """Busca e ordena por meio do serviço de estabelecimentos."""
        return self.establishment_service.list_sorted(
            self.sort_column,
            self.sort_ascending,
        )

    def _handle_search(self, event=None) -> None:
        """Manipula eventos de busca em tempo real."""
        # Usar delay para evitar buscas muito frequentes
        if hasattr(self, '_search_after_id'):
            self.frame.after_cancel(self._search_after_id)
        
        self._search_after_id = self.frame.after(500, self._execute_search)

    def _execute_search(self) -> None:
        """Executa a busca nos estabelecimentos."""
        search_term = self.search_entry.get().strip().lower()
        
        if not search_term:
            self._clear_search()
            return
        
        try:
            resultados = []

            for estab in self._estabelecimentos_cache:
                if (
                    search_term in str(estab.get("CO_CNES", "")).lower()
                    or search_term in str(estab.get("NO_FANTASIA", "")).lower()
                    or search_term in str(estab.get("CO_CEP", "")).lower()
                ):
                    resultados.append(estab)
            
            # Aplicar ordenação local nos resultados
            resultados = self._aplicar_ordenacao_local(resultados)
            
            # Atualizar treeview
            self.tree.delete(*self.tree.get_children())

            for i, estab in enumerate(resultados):
                tag_linha = "linha_par" if i % 2 == 0 else "linha_impar"

                self.tree.insert(
                    "",
                    "end",
                    iid=str(estab["id"]),
                    values=(
                        estab.get("CO_CNES", ""),
                        estab.get("NO_FANTASIA", ""),
                        estab.get("CO_CEP", "") or ""
                    ),
                    tags=(tag_linha,)
                )
            
            count = len(resultados)

            self.status_label.configure(
                text=f"● {count} estabelecimento(s) encontrado(s) para '{search_term}' - Ordenado por: {self.HEADERS[self.sort_column]} {'↑' if self.sort_ascending else '↓'}",
                text_color=COLORS["primary"]
            )
            
        except Exception as e:
            self.status_label.configure(
                text=f"× Erro na busca: {e}",
                text_color=COLORS["danger"]
            )
            self.logger.error(f"Erro durante busca: {e}")

    def _aplicar_ordenacao_local(self, dados: List[Dict]) -> List[Dict]:
        return self.establishment_service.sort(
            dados,
            self.sort_column,
            self.sort_ascending,
        )

    def _clear_search(self) -> None:
        """Limpa a busca e mostra todos os estabelecimentos."""
        self.search_entry.delete(0, tk.END)
        self._load_estabelecimentos()

    def _add_estabelecimento(self) -> None:
        """Abre formulário para adicionar novo estabelecimento."""
        self._open_estabelecimento_form()

    def _edit_estabelecimento(self, event=None) -> None:
        selection = self.tree.selection()
        if not selection:
            messagebox.showwarning("Seleção Necessária", "Selecione um estabelecimento para editar.")
            return
        try:
            establishment = self.establishment_service.get(int(selection[0]))
            if not establishment:
                raise LookupError("Não foi possível carregar os dados do estabelecimento.")
            self._open_estabelecimento_form(establishment["id"], establishment)
        except Exception as e:
            messagebox.showerror("Erro", f"Falha ao carregar estabelecimento: {e}")
            self.logger.error(f"Falha ao carregar estabelecimento: {e}")

    def _delete_estabelecimento(self) -> None:
        selection = self.tree.selection()
        if not selection:
            messagebox.showwarning("Seleção Necessária", "Selecione um estabelecimento para excluir.")
            return
        item_id = selection[0]
        cnes, nome, _cep = self.tree.item(item_id, "values")
        if not messagebox.askyesno(
            "Confirmar Exclusão",
            f"Tem certeza que deseja excluir este estabelecimento?\n\nCNES: {cnes}\nNome: {nome}",
            icon="warning",
        ):
            return
        try:
            if not self.establishment_service.delete(int(item_id)):
                raise RuntimeError("Falha ao excluir estabelecimento.")
            self._load_estabelecimentos()
            self.status_label.configure(
                text=f"✅ Estabelecimento excluído: {nome}",
                text_color=COLORS["success"],
            )
            self.logger.info(f"Estabelecimento excluído: ID {item_id} - {nome}")
        except Exception as e:
            messagebox.showerror("Erro", f"Falha ao excluir estabelecimento: {e}")
            self.logger.error(f"Falha ao excluir estabelecimento: {e}")

    def _open_estabelecimento_form(
        self,
        estabelecimento_id: Optional[int] = None,
        dados: Optional[Dict] = None,
    ) -> None:
        self.establishment_form.show(estabelecimento_id, dados)

    def _save_establishment(self, record_id, values):
        action = self.establishment_service.save(record_id, values)
        self._load_estabelecimentos()
        self.logger.info(f"Estabelecimento {action}: {values.get('NO_FANTASIA', '')}")
        return action



            

