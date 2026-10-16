import tkinter as tk
from tkinter import ttk, messagebox
import customtkinter as ctk

from sia_app.services.prd_editor_service import PrdEditorService
from sia_app.ui.components.production_edit_dialog import ProductionEditDialog

from sia_app.ui.theme import COLORS, apply_theme, FONT_FAMILY

class PrdEditorTab:
    def __init__(self, parent, db, settings, logger):
        self.parent = parent
        self.db = db
        self.settings = settings
        self.logger = logger
        self.prd_service = PrdEditorService(db)

        apply_theme()

        self.frame = ctk.CTkFrame(parent, fg_color=COLORS["bg"])
        self.edit_dialog = ProductionEditDialog(
            self.frame,
            COLORS,
            self._save_record,
        )

        self.competencia_var = tk.StringVar()
        self.estabelecimento_var = tk.StringVar()

        self._create_widgets()
        self.carregar_dados()

    def _create_widgets(self):
        main = ctk.CTkFrame(
            self.frame,
            fg_color=COLORS["bg"],
            corner_radius=0
        )
        main.pack(fill="both", expand=True)

        main.grid_columnconfigure(0, weight=1)
        main.grid_rowconfigure(0, weight=0)  # título
        main.grid_rowconfigure(1, weight=0)  # filtros
        main.grid_rowconfigure(2, weight=1)  # tabela ocupa o espaço flexível
        main.grid_rowconfigure(3, weight=0)  # botões sempre visíveis

        self._create_title_section(main)
        self._create_filters_section(main)
        self._create_table_section(main)
        self._create_action_section(main)
        
    def _create_title_section(self, parent):
        header = ctk.CTkFrame(parent, fg_color="transparent")
        header.grid(row=0, column=0, sticky="ew", padx=18, pady=(18, 8))

        ctk.CTkLabel(
            header,
            text="Dados de Produção",
            font=(FONT_FAMILY, 22, "bold"),
            text_color=COLORS["text"],
            anchor="center"
        ).pack(anchor="center")

        ctk.CTkLabel(
            header,
            text="Consulte, edite e exclua registros de produção ambulatorial importados no sistema",
            font=(FONT_FAMILY, 12),
            text_color=COLORS["muted"],
            anchor="center"
        ).pack(anchor="center", pady=(2, 0))
        
    def _create_filters_section(self, parent):
        filtros = ctk.CTkFrame(
            parent,
            fg_color=COLORS["card"],
            border_color=COLORS["border"],
            border_width=1,
            corner_radius=12
        )
        filtros.grid(row=1, column=0, sticky="ew", padx=18, pady=(8, 14))

        ctk.CTkLabel(
            filtros,
            text="Filtros",
            font=(FONT_FAMILY, 13, "bold"),
            text_color=COLORS["text"]
        ).pack(anchor="w", padx=18, pady=(14, 8))

        linha = ctk.CTkFrame(filtros, fg_color="transparent")
        linha.pack(fill="x", padx=18, pady=(4, 18))

        ctk.CTkLabel(
            linha,
            text="Competência:",
            font=(FONT_FAMILY, 12, "bold"),
            text_color=COLORS["text"]
        ).pack(side="left", padx=(0, 8))

        ctk.CTkEntry(
            linha,
            textvariable=self.competencia_var,
            width=120,
            height=36,
            corner_radius=7,
            border_color=COLORS["border"],
            placeholder_text="Ex: 202601",
            font=(FONT_FAMILY, 12)
        ).pack(side="left", padx=(0, 16))

        ctk.CTkLabel(
            linha,
            text="Estabelecimento:",
            font=(FONT_FAMILY, 12, "bold"),
            text_color=COLORS["text"]
        ).pack(side="left", padx=(0, 8))

        ctk.CTkEntry(
            linha,
            textvariable=self.estabelecimento_var,
            height=36,
            corner_radius=7,
            border_color=COLORS["border"],
            placeholder_text="Digite o nome do estabelecimento",
            font=(FONT_FAMILY, 12)
        ).pack(side="left", fill="x", expand=True, padx=(0, 16))

        botoes_filtro = ctk.CTkFrame(linha, fg_color="transparent")
        botoes_filtro.pack(side="right")

        ctk.CTkButton(
            botoes_filtro,
            text="Filtrar",
            command=self.carregar_dados,
            width=100,
            height=36,
            corner_radius=7,
            fg_color=COLORS["primary"],
            hover_color=COLORS["primary_dark"],
            text_color="#FFFFFF",
            font=(FONT_FAMILY, 12, "bold")
        ).pack(side="left", padx=(0, 8))

        ctk.CTkButton(
            botoes_filtro,
            text="Limpar",
            command=self.limpar_filtros,
            width=100,
            height=36,
            corner_radius=7,
            fg_color="#FFFFFF",
            hover_color=COLORS["primary_soft"],
            border_color=COLORS["primary"],
            border_width=1,
            text_color=COLORS["primary"],
            font=(FONT_FAMILY, 12, "bold")
        ).pack(side="left", padx=(0, 8))

        ctk.CTkButton(
            botoes_filtro,
            text="Atualizar lista",
            command=self.carregar_dados,
            width=130,
            height=36,
            corner_radius=7,
            fg_color="#FFFFFF",
            hover_color=COLORS["primary_soft"],
            border_color=COLORS["border"],
            border_width=1,
            text_color=COLORS["text"],
            font=(FONT_FAMILY, 12, "bold")
        ).pack(side="left")
        
    def _create_table_section(self, parent):
        tabela_card = ctk.CTkFrame(
            parent,
            fg_color=COLORS["card"],
            border_color=COLORS["border"],
            border_width=1,
            corner_radius=12
        )
        tabela_card.grid(row=2, column=0, sticky="nsew", padx=18, pady=(0, 14))
        
        tabela_card.grid_columnconfigure(0, weight=1)
        tabela_card.grid_rowconfigure(1, weight=1)

        header = ctk.CTkFrame(tabela_card, fg_color="transparent")
        header.grid(row=0, column=0, sticky="ew", padx=18, pady=(14, 8))

        ctk.CTkLabel(
            header,
            text="Registros de Produção",
            font=(FONT_FAMILY, 13, "bold"),
            text_color=COLORS["text"]
        ).pack(side="left")

        tabela_frame = ctk.CTkFrame(tabela_card, fg_color="transparent")
        tabela_frame.grid(row=1, column=0, sticky="nsew", padx=18, pady=(0, 18))

        tabela_frame.rowconfigure(0, weight=1)
        tabela_frame.columnconfigure(0, weight=1)

        style = ttk.Style()
        style.configure(
            "ModernPrd.Treeview",
            background="#FFFFFF",
            fieldbackground="#FFFFFF",
            foreground=COLORS["text"],
            rowheight=30,
            font=(FONT_FAMILY, 9),
            borderwidth=0
        )
        style.configure(
            "ModernPrd.Treeview.Heading",
            font=(FONT_FAMILY, 9, "bold"),
            foreground=COLORS["text"],
            background="#F8FAFC",
            relief="flat"
        )
        style.map(
            "ModernPrd.Treeview",
            background=[("selected", "#DCEBFF")],
            foreground=[("selected", COLORS["text"])]
        )
        style.map(
            "ModernPrd.Treeview.Heading",
            background=[("active", "#EFF5F2")]
        )

        colunas = (
            "id",
            "PRD_UID",
            "NO_FANTASIA",
            "PRD_CMP",
            "PRD_PA",
            "PRD_CBO",
            "PA_DC",
            "PRD_TPFIN",
            "PRD_CPX",
            "PA_CTF",
            "PA_CPX",
            "PRD_QT_P",
            "PRD_QT_A",
            "PRD_VL_P",
            "PRD_VL_A",
            "arquivo_origem"
        )

        self.tree = ttk.Treeview(
            tabela_frame,
            columns=colunas,
            show="headings",
            height=14,
            style="ModernPrd.Treeview"
        )

        self.tree.tag_configure("linha_par", background="#F7F9FC")
        self.tree.tag_configure("linha_impar", background="#FFFFFF")

        self.tree.heading("id", text="Cód.")
        self.tree.heading("PRD_UID", text="CNES")
        self.tree.heading("NO_FANTASIA", text="NOME")
        self.tree.heading("PRD_CMP", text="COMP.")
        self.tree.heading("PRD_PA", text="PROCED.")
        self.tree.heading("PRD_CBO", text="CBO")
        self.tree.heading("PA_DC", text="Descrição")
        self.tree.heading("PRD_TPFIN", text="Tipo de Financ.")
        self.tree.heading("PRD_CPX", text="Complex.")
        self.tree.heading("PA_CTF", text="Financ. Procedimento")
        self.tree.heading("PA_CPX", text="Complex. Procedimento")
        self.tree.heading("PRD_QT_P", text="QTD. PRD.")
        self.tree.heading("PRD_QT_A", text="QTD. APROV.")
        self.tree.heading("PRD_VL_P", text="VALOR PRD.")
        self.tree.heading("PRD_VL_A", text="VALOR APROV.")
        self.tree.heading("arquivo_origem", text="ARQUIVO")

        self.tree.column("id", width=60, anchor="center")
        self.tree.column("PRD_UID", width=90, anchor="center")
        self.tree.column("NO_FANTASIA", width=260, anchor="w")
        self.tree.column("PRD_CMP", width=80, anchor="center")
        self.tree.column("PRD_PA", width=110, anchor="center")
        self.tree.column("PRD_CBO", width=80, anchor="center")
        self.tree.column("PA_DC", width=300, anchor="w")
        self.tree.column("PRD_TPFIN", width=230, anchor="w")
        self.tree.column("PRD_CPX", width=190, anchor="w")
        self.tree.column("PA_CTF", width=230, anchor="w")
        self.tree.column("PA_CPX", width=190, anchor="w")
        self.tree.column("PRD_QT_P", width=90, anchor="center")
        self.tree.column("PRD_QT_A", width=100, anchor="center")
        self.tree.column("PRD_VL_P", width=110, anchor="e")
        self.tree.column("PRD_VL_A", width=110, anchor="e")
        self.tree.column("arquivo_origem", width=220, anchor="center")

        scrollbar_y = ttk.Scrollbar(tabela_frame, orient="vertical", command=self.tree.yview)
        scrollbar_x = ttk.Scrollbar(tabela_frame, orient="horizontal", command=self.tree.xview)

        self.tree.configure(
            yscrollcommand=scrollbar_y.set,
            xscrollcommand=scrollbar_x.set
        )

        self.tree.grid(row=0, column=0, sticky="nsew")
        scrollbar_y.grid(row=0, column=1, sticky="ns")
        scrollbar_x.grid(row=1, column=0, sticky="ew")
        
    def _create_action_section(self, parent):
        action_frame = ctk.CTkFrame(parent, fg_color="transparent")
        action_frame.grid(row=3, column=0, sticky="ew", padx=18, pady=(0, 18))

        left = ctk.CTkFrame(action_frame, fg_color="transparent")
        left.pack(side="left")

        right = ctk.CTkFrame(action_frame, fg_color="transparent")
        right.pack(side="right")

        ctk.CTkButton(
            left,
            text="Editar selecionado",
            command=self.editar_selecionado,
            width=150,
            height=36,
            corner_radius=7,
            fg_color=COLORS["primary"],
            hover_color=COLORS["primary_dark"],
            text_color="#FFFFFF",
            font=(FONT_FAMILY, 12, "bold")
        ).pack(side="left", padx=(0, 8))

        ctk.CTkButton(
            left,
            text="Excluir selecionado",
            command=self.excluir_selecionado,
            width=160,
            height=36,
            corner_radius=7,
            fg_color="#FFFFFF",
            hover_color="#FFF1F1",
            border_color=COLORS["danger"],
            border_width=1,
            text_color=COLORS["danger"],
            font=(FONT_FAMILY, 12, "bold")
        ).pack(side="left")

        ctk.CTkButton(
            right,
            text="Excluir tudo (filtrado)",
            command=self.excluir_filtrados,
            width=180,
            height=36,
            corner_radius=7,
            fg_color=COLORS["danger"],
            hover_color="#B91C1C",
            text_color="#FFFFFF",
            font=(FONT_FAMILY, 12, "bold")
        ).pack(side="right")

    def limpar_filtros(self):
        self.competencia_var.set("")
        self.estabelecimento_var.set("")
        self.carregar_dados()

    def carregar_dados(self):
        self.tree.delete(*self.tree.get_children())
        try:
            rows = self.prd_service.list_records(
                self.competencia_var.get(),
                self.estabelecimento_var.get(),
            )
            for index, values in enumerate(rows):
                self.tree.insert(
                    "",
                    "end",
                    values=values,
                    tags=("linha_par" if index % 2 == 0 else "linha_impar",),
                )
        except Exception as e:
            self.logger.error(f"Erro ao carregar dados PRD: {e}")
            messagebox.showerror("Erro", f"Erro ao carregar dados:\n{e}")

    def editar_selecionado(self):
        selecionado = self.tree.selection()
        if not selecionado:
            messagebox.showwarning("Atenção", "Selecione um registro para editar.")
            return
        self.edit_dialog.show(self.tree.item(selecionado[0], "values"))

    def _save_record(self, record_id, quantidade_produzida, quantidade_aprovada):
        self.prd_service.update_quantities(
            record_id,
            quantidade_produzida,
            quantidade_aprovada,
        )
        self.carregar_dados()

    def excluir_selecionado(self):
        selecionado = self.tree.selection()
        if not selecionado:
            messagebox.showwarning("Atenção", "Selecione um registro para excluir.")
            return
        record_id = self.tree.item(selecionado[0], "values")[0]
        if not messagebox.askyesno("Confirmar exclusão", "Tem certeza que deseja excluir este registro?"):
            return
        try:
            self.prd_service.delete_one(record_id)
            self.carregar_dados()
            messagebox.showinfo("Sucesso", "Registro excluído com sucesso.")
        except Exception as e:
            self.logger.error(f"Erro ao excluir registro PRD: {e}")
            messagebox.showerror("Erro", f"Erro ao excluir:\n{e}")
            
    def excluir_filtrados(self):
        competencia = self.competencia_var.get().strip()
        estabelecimento = self.estabelecimento_var.get().strip()
        if not competencia and not estabelecimento:
            messagebox.showwarning(
                "Filtro obrigatório",
                "Para usar 'Excluir tudo', informe pelo menos uma competência ou estabelecimento.",
            )
            return
        try:
            total = self.prd_service.count_filtered(competencia, estabelecimento)
            if total == 0:
                messagebox.showinfo("Excluir tudo", "Nenhum registro encontrado com os filtros informados.")
                return
            if not messagebox.askyesno(
                "Confirmar exclusão",
                f"Tem certeza que deseja excluir {total} registro(s) com base nos filtros aplicados?",
            ):
                return
            deleted = self.prd_service.delete_filtered(competencia, estabelecimento)
            self.carregar_dados()
            messagebox.showinfo("Sucesso", f"{deleted} registro(s) excluído(s) com sucesso.")
        except Exception as e:
            self.logger.error(f"Erro ao excluir registros filtrados: {e}")
            messagebox.showerror("Erro", f"Erro ao excluir registros filtrados:\n{e}")
            



