# -*- coding: utf-8 -*-
"""
Gerador de PDF otimizado para relatórios SIA/SUS com:
- Layout A4 paisagem
- Cabeçalho e rodapé em todas as páginas
- Tabelas com formatação zebra e cabeçalhos fixos
- Numeração de páginas X de Y
- Suporte a múltiplos modos de exibição
"""

from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, PageBreak
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas as rl_canvas
from reportlab.lib.units import cm
from reportlab.lib.utils import ImageReader
import os
import logging
from datetime import datetime
from decimal import Decimal
from typing import Dict, List, Any, Optional, Tuple
from pathlib import Path

class NumberedCanvas(rl_canvas.Canvas):
    """
    Canvas personalizado com numeração de páginas X de Y.
    """
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._saved_page_states = []
        self._doc_left_margin = 2 * cm
        self._doc_right_margin = 2 * cm
        self._doc_bottom_margin = 2 * cm
        self._footer_font = "Helvetica"
        self._footer_size = 8
        self._footer_y = 0.45 * cm

    def showPage(self):
        self._saved_page_states.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        total_pages = len(self._saved_page_states)
        
        for state in self._saved_page_states:
            self.__dict__.update(state)
            self._draw_page_number(total_pages)
            rl_canvas.Canvas.showPage(self)
            
        rl_canvas.Canvas.save(self)

    def _draw_page_number(self, total_pages: int):
        """Desenha a numeração da página no rodapé."""
        page_width, page_height = self._pagesize
        current_page = self.getPageNumber()
        page_text = f"Página {current_page} de {total_pages}"
        
        self.saveState()
        self.setFont(self._footer_font, self._footer_size)
        y_position = self._footer_y

        text_width = self.stringWidth(page_text, self._footer_font, self._footer_size)
        x_position = page_width - self._doc_right_margin - text_width
        self.drawString(x_position, y_position, page_text)
        self.restoreState()


class PDFGenerator:
    """
    Gerador de PDF otimizado para relatórios do sistema SIA/SUS.
    """
    
    # Cores padrão do sistema
    PRIMARY_COLOR = colors.HexColor("#0a4ea6")
    LIGHT_GRAY = colors.HexColor("#f8fafc")
    BORDER_GRAY = colors.HexColor("#e5e7eb")
    GROUP_BG_COLOR = colors.HexColor("#f1f5f9")
    PAGE_DIVIDER_COLOR = colors.HexColor("#94a3b8")
    PAGE_DIVIDER_WIDTH = 0.7
    REPORT_TITLE_FONT_SIZE = 15
    REPORT_TITLE_LEADING = 18
    GROUP_HIERARCHY_INDENTS = {
        "grupo": 8,
        "subgrupo": 22,
        "forma": 36,
    }
    TITLE_SLOT_HEIGHT = 28.0
    TITLE_VERTICAL_OFFSET = 8.75
    TITLE_SPACE_AFTER = (
        TITLE_SLOT_HEIGHT - REPORT_TITLE_LEADING + TITLE_VERTICAL_OFFSET
    )
    
    def __init__(self, logger: logging.Logger):
        """
        Inicializa o gerador de PDF.
        
        Args:
            logger: Instância de logger para registro de atividades
        """
        self.logger = logger
        self.styles = getSampleStyleSheet()
        self._font_base = "Helvetica"
        self._font_bold = "Helvetica-Bold"
        self._logo_cache = None
        self._logo_cache_path = None
        
        self._setup_styles()
        self._setup_constants()

    def _setup_constants(self):
        """Configura constantes utilizadas no sistema."""
        self.MESES_PT = {
            '01': 'Janeiro', '02': 'Fevereiro', '03': 'Março', '04': 'Abril',
            '05': 'Maio', '06': 'Junho', '07': 'Julho', '08': 'Agosto',
            '09': 'Setembro', '10': 'Outubro', '11': 'Novembro', '12': 'Dezembro'
        }
        
        self.DIAS_SEMANA_PT = [
            "Segunda-feira", "Terça-feira", "Quarta-feira", "Quinta-feira",
            "Sexta-feira", "Sábado", "Domingo"
        ]

    def _setup_styles(self):
        """Configura os estilos de parágrafo para o PDF."""
        # Estilo para título principal
        if 'TituloPrincipal' not in self.styles:
            self.styles.add(ParagraphStyle(
                name='TituloPrincipal',
                parent=self.styles['Normal'],
                fontName=self._font_bold,
                fontSize=14,
                leading=16,
                spaceAfter=8,
                alignment=0  # Alinhamento à esquerda
            ))

        # Estilo para informações institucionais
        if 'InstitucionalMenor' not in self.styles:
            self.styles.add(ParagraphStyle(
                name='InstitucionalMenor',
                parent=self.styles['Normal'],
                fontName=self._font_base,
                fontSize=10,
                leading=12,
                spaceAfter=0,
                alignment=0
            ))

        # Estilo para cabeçalho de bloco
        if 'CabecalhoBloco' not in self.styles:
            self.styles.add(ParagraphStyle(
                name='CabecalhoBloco',
                parent=self.styles['Normal'],
                fontName=self._font_base,
                fontSize=10,
                leading=14,
                textColor=colors.black,
                spaceAfter=6,
                alignment=0
            ))

        if 'IdentificacaoEsquerda' not in self.styles:
            self.styles.add(ParagraphStyle(
                name='IdentificacaoEsquerda',
                parent=self.styles['Normal'],
                fontName=self._font_base,
                fontSize=9.5,
                leading=11,
                textColor=colors.black,
                alignment=0
            ))

        if 'IdentificacaoDireita' not in self.styles:
            self.styles.add(ParagraphStyle(
                name='IdentificacaoDireita',
                parent=self.styles['Normal'],
                fontName=self._font_base,
                fontSize=9.5,
                leading=11,
                textColor=colors.black,
                alignment=2
            ))

        # Estilo para totais de bloco
        if 'TotaisBloco' not in self.styles:
            self.styles.add(ParagraphStyle(
                name='TotaisBloco',
                parent=self.styles['Normal'],
                fontName=self._font_base,
                fontSize=10,
                leading=12,
                spaceBefore=2,
                spaceAfter=4,
                textColor=colors.black,
                alignment=2  # Alinhamento à direita
            ))

        # Estilo para totais gerais
        if 'TotaisGerais' not in self.styles:
            self.styles.add(ParagraphStyle(
                name='TotaisGerais',
                parent=self.styles['Normal'],
                fontName=self._font_bold,
                fontSize=self.REPORT_TITLE_FONT_SIZE,
                leading=self.REPORT_TITLE_LEADING,
                spaceBefore=6,
                spaceAfter=3,
                textColor=self.PRIMARY_COLOR,
                alignment=1  # Alinhamento centralizado
            ))

        # Estilo para descrição de procedimentos
        if 'DescricaoProcedimento' not in self.styles:
            self.styles.add(ParagraphStyle(
                name='DescricaoProcedimento',
                parent=self.styles['Normal'],
                fontName=self._font_base,
                fontSize=8,
                leading=10,
                alignment=0,
                spaceBefore=0,
                spaceAfter=0,
                leftIndent=0,
                rightIndent=0
            ))

    def _register_custom_fonts(self, font_name: str = "Arial"):
        """
        Tenta registrar fontes TTF personalizadas.
        
        Args:
            font_name: Nome da fonte a ser registrada
        """
        try:
            if not font_name:
                return
                
            # Possíveis localizações da fonte
            font_paths = [
                font_name,
                f"{font_name}.ttf",
                os.path.join(os.getenv('WINDIR', 'C:/Windows'), 'Fonts', f'{font_name}.ttf'),
                os.path.join(os.getenv('WINDIR', 'C:/Windows'), 'Fonts', f'{font_name.lower()}.ttf'),
            ]
            
            bold_paths = [
                f"{font_name}-Bold.ttf",
                f"{font_name} Bold.ttf",
                os.path.join(os.getenv('WINDIR', 'C:/Windows'), 'Fonts', f'{font_name}-Bold.ttf'),
                os.path.join(os.getenv('WINDIR', 'C:/Windows'), 'Fonts', f'{font_name}bd.ttf'),
            ]

            # Registrar fonte regular
            for path in font_paths:
                if os.path.isfile(path):
                    pdfmetrics.registerFont(TTFont(font_name, path))
                    self._font_base = font_name
                    self.logger.info(f"Fonte {font_name} registrada com sucesso")
                    break

            # Registrar fonte negrito
            for path in bold_paths:
                if os.path.isfile(path):
                    bold_name = f"{font_name}-Bold"
                    pdfmetrics.registerFont(TTFont(bold_name, path))
                    self._font_bold = bold_name
                    self.logger.info(f"Fonte {bold_name} registrada com sucesso")
                    break
                    
        except Exception as e:
            self.logger.warning(f"Não foi possível registrar fontes personalizadas: {e}")

    def generate_pdf(self, dados: List[Dict], config: Dict, output_path: str) -> Tuple[bool, str]:
        """
        Gera o arquivo PDF com os dados fornecidos.
        
        Args:
            dados: Lista de dados para o relatório
            config: Configurações de formatação
            output_path: Caminho de saída do arquivo PDF
            
        Returns:
            Tupla (sucesso, mensagem)
        """
        try:
            # Registrar fontes personalizadas
            self._register_custom_fonts(config.get('font_name', 'Arial'))
            
            # Margens compactas para ampliar a área útil da tabela sem invadir
            # o cabeçalho e o rodapé fixos.
            top_margin = 3.0 * cm
            bottom_margin = 1.15 * cm
            left_margin = 1.35 * cm
            right_margin = 1.35 * cm

            # Criar documento
            doc = SimpleDocTemplate(
                output_path,
                pagesize=landscape(A4),
                topMargin=top_margin,
                bottomMargin=bottom_margin,
                leftMargin=left_margin,
                rightMargin=right_margin,
            )

            # Preparar conteúdo
            story = self._prepare_content(dados, config, doc)
            
            # Gerar PDF
            doc.build(
                story,
                onFirstPage=lambda canvas, document: self._draw_page_elements(canvas, document, config),
                onLaterPages=lambda canvas, document: self._draw_page_elements(canvas, document, config),
                canvasmaker=NumberedCanvas,
            )
            
            self.logger.info(f"PDF gerado com sucesso: {output_path}")
            return True, f"PDF gerado: {output_path}"
            
        except Exception as e:
            error_msg = f"Erro ao gerar PDF: {e}"
            self.logger.error(error_msg)
            return False, error_msg

    def _prepare_content(self, dados: List[Dict], config: Dict, doc: SimpleDocTemplate) -> List[Any]:
        """
        Prepara o conteúdo do relatório.
        
        Args:
            dados: Dados do relatório
            config: Configurações
            doc: Documento SimpleDocTemplate
            
        Returns:
            Lista de elementos do story
        """
        elements = []
    
        # DEBUG: Log dos dados recebidos
        self.logger.info(f"Preparando PDF com {len(dados)} blocos de dados")
        
        # Agrupar dados
        dados_agrupados = self._group_data(dados, config)
        
        # Adicionar título do relatório
        title = config.get("title", "Relatório de Produção")
        # O título é deslocado para cima para ficar visualmente centralizado
        # entre a linha final do cabeçalho e a identificação do primeiro bloco.
        # O mesmo valor é devolvido ao espaço inferior, preservando a posição
        # da identificação e da tabela de produção.
        elements.append(Spacer(1, -self.TITLE_VERTICAL_OFFSET))
        elements.append(Paragraph(
            title,
            ParagraphStyle(
                name="TituloRelatorio",
                parent=self.styles["Normal"],
                fontName=self._font_bold,
                fontSize=self.REPORT_TITLE_FONT_SIZE,
                textColor=self.PRIMARY_COLOR,
                leading=self.REPORT_TITLE_LEADING,
                spaceBefore=0,
                spaceAfter=self.TITLE_SPACE_AFTER,
                alignment=1  # Centralizado
            )
        ))

        # Processar blocos de dados
        total_geral_quantidade = 0
        total_geral_valor = Decimal('0.00')
        blocos_ordenados = sorted(
            dados_agrupados.items(),
            key=lambda x: (x[1]['cnes'], x[1]['competencia'])
        )
        table_mode = config.get("table_mode", "unidade").lower()

        self.logger.info(f"Processando {len(blocos_ordenados)} blocos ordenados")

        for i, (chave, bloco) in enumerate(blocos_ordenados):
            if config.get('uma_pagina_por_bloco') and i > 0:
                elements.append(PageBreak())

            # DEBUG: Informações do bloco
            self.logger.info(f"Bloco {i+1}: {bloco['cnes']} - {bloco['competencia']} - {len(bloco['procedimentos'])} procedimentos")

            # Adicionar cabeçalho do bloco
            elements.extend(self._create_block_header(bloco, doc))
            #elements.extend(self._create_block_totals(bloco, config))
            
            # Adicionar tabela de procedimentos
            if bloco['procedimentos']:
                if table_mode == "diferencas":
                    tabela = self._create_procedure_table_diferencas(bloco['procedimentos'], doc, config)

                elif table_mode == "procedimento":
                    tabela = self._create_procedure_table_detailed(bloco['procedimentos'], doc, config)

                else:
                    tabela = self._create_procedure_table_simple(bloco['procedimentos'], doc, config)
                elements.append(tabela)
                elements.append(Spacer(1, 0.12 * cm))
            else:
                elements.append(Paragraph(
                    "<i>Nenhum procedimento encontrado para este estabelecimento/competência</i>", 
                    ParagraphStyle(
                        name="SemDados",
                        parent=self.styles["Normal"],
                        fontName=self._font_base,
                        fontSize=9,
                        textColor=colors.gray,
                        alignment=1
                    )
                ))

            # Adicionar totais do bloco
            #elements.extend(self._create_block_totals(bloco))
            elements.extend(self._create_block_totals(bloco, config))
            elements.append(Spacer(1, 0.2 * cm))

            # Acumular totais gerais
            total_geral_quantidade += bloco['total_quantidade']
            total_geral_valor += bloco['total_valor']

        # Adicionar totais gerais
        if table_mode != "diferencas" and blocos_ordenados:
            elements.extend(self._create_general_totals(total_geral_quantidade, total_geral_valor))

        return elements

    def _group_data(self, dados: List[Dict], config: Dict) -> Dict[str, Dict]:
        """
        Agrupa dados por CNES e competência.
        
        Args:
            dados: Dados brutos
            config: Configurações
            
        Returns:
            Dados agrupados
        """
        agrupados = {}
    
        for bloco in dados:
            cnes = bloco.get('uid', '')
            competencia = bloco.get('cmp', '')
            nome_estabelecimento = bloco.get('nome', 'NÃO CADASTRADO')
            chave = f"{cnes}_{competencia}"
            
            if chave not in agrupados:
                agrupados[chave] = {
                    'cnes': cnes,
                    'estabelecimento': nome_estabelecimento,
                    'competencia': competencia,
                    'procedimentos': [],
                    'total_quantidade': 0,
                    'total_valor': Decimal('0.00')
                }
            
            # Processar as rows do bloco aplicando filtros
            for row in bloco.get('rows', []):
                # Aplicar filtro de ocultar zerados (vem da ConfigTab)
                if config.get('ocultar_zerados'):
                    quantidade = int(row.get('QUANTIDADE') or row.get('PRD_QT_A', 0) or 0)
                    if quantidade == 0:
                        continue  # Pular procedimentos com quantidade zero
                
                # Restante do código de processamento...
                try:
                    quantidade = int(row.get('QUANTIDADE') or row.get('PRD_QT_A', 0) or 0)
                except (ValueError, TypeError):
                    quantidade = 0
                
                try:
                    valor_unitario_raw = row.get('VALOR_UNITARIO')
                    if valor_unitario_raw is None:
                        valor_unitario_raw = row.get('PA_TOTAL', 0)
                    if isinstance(valor_unitario_raw, (int, float)):
                        valor_unitario = Decimal(str(valor_unitario_raw)).quantize(Decimal('0.01'))
                    else:
                        valor_unitario = Decimal(str(valor_unitario_raw or 0)).quantize(Decimal('0.01'))
                except (ValueError, TypeError):
                    valor_unitario = Decimal('0.00')
                
                try:
                    valor_total_raw = row.get('VALOR_TOTAL')
                    if valor_total_raw is not None:
                        if isinstance(valor_total_raw, (int, float)):
                            valor_total = Decimal(str(valor_total_raw)).quantize(Decimal('0.01'))
                        else:
                            valor_total = Decimal(str(valor_total_raw or 0)).quantize(Decimal('0.01'))
                    else:
                        valor_total = (Decimal(str(quantidade)) * valor_unitario).quantize(Decimal('0.01'))
                except (ValueError, TypeError):
                    valor_total = Decimal('0.00')
                    
                try:
                    quantidade_aprovada = int(row.get('QUANTIDADE_APROVADA') or row.get('PRD_QT_A') or 0)
                except (ValueError, TypeError):
                    quantidade_aprovada = 0
                    
                try:
                    quantidade_produzida = int(row.get('QUANTIDADE_PRODUZIDA') or row.get('PRD_QT_P') or 0)
                except (ValueError, TypeError):
                    quantidade_produzida = 0
                    
                valor_unitario_raw = row.get('VALOR_UNITARIO')
                if valor_unitario_raw is None:
                    valor_unitario_raw = row.get('PA_TOTAL', 0)
                valor_unitario = self._safe_decimal_convert(valor_unitario_raw)

                valor_aprovado_raw = row.get('VALOR_APROVADO')
                if valor_aprovado_raw is None:
                    valor_aprovado_raw = Decimal(quantidade_aprovada) * valor_unitario
                valor_aprovado = self._safe_decimal_convert(valor_aprovado_raw)

                valor_produzido_raw = row.get('VALOR_PRODUZIDO')
                if valor_produzido_raw is None:
                    valor_produzido_raw = Decimal(quantidade_produzida) * valor_unitario
                valor_produzido = self._safe_decimal_convert(valor_produzido_raw)

                valor_total_raw = row.get('VALOR_TOTAL')
                valor_total = self._safe_decimal_convert(
                    valor_aprovado if valor_total_raw is None else valor_total_raw
                )
                
                diferenca_quantidade = quantidade_produzida - quantidade_aprovada
                diferenca_valor = valor_produzido - valor_aprovado
                
                procedimento = {
                    'codigo': row.get('PRD_PA', '') or row.get('procedimento', ''),
                    'descricao': row.get('PA_DC', '') or row.get('descricao_procedimento', 'Descrição não disponível'),

                    # Compatibilidade antiga
                    'quantidade': quantidade,
                    'valor_unitario': valor_unitario,
                    'valor_total': valor_total,

                    # Novos campos dinâmicos
                    'quantidade_aprovada': quantidade_aprovada,
                    'valor_aprovado': valor_aprovado,
                    'quantidade_produzida': quantidade_produzida,
                    'valor_produzido': valor_produzido,
                    
                    'diferenca_quantidade': diferenca_quantidade,
                    'diferenca_valor': diferenca_valor,
                }
                
                agrupados[chave]['procedimentos'].append(procedimento)
                agrupados[chave]['total_quantidade'] += quantidade
                agrupados[chave]['total_valor'] += valor_total
        
        return agrupados

    def _draw_page_elements(self, canvas: NumberedCanvas, doc: SimpleDocTemplate, config: Dict):
        """
        Desenha cabeçalho e rodapé em todas as páginas.
        """
        # Configurar canvas para numeração
        canvas._doc_left_margin = doc.leftMargin
        canvas._doc_right_margin = doc.rightMargin
        canvas._doc_bottom_margin = doc.bottomMargin
        canvas._footer_font = self._font_base
        canvas._footer_size = 8
        canvas._footer_y = self._centered_baseline(
            0,
            doc.bottomMargin,
            self._font_base,
            canvas._footer_size,
        )

        self._draw_header(canvas, doc, config)
        self._draw_footer(canvas, doc, config)

    @staticmethod
    def _centered_baseline(
        band_bottom: float,
        band_height: float,
        font_name: str,
        font_size: float,
    ) -> float:
        """Retorna a linha de base que centraliza o texto verticalmente na faixa."""
        ascent = pdfmetrics.getAscent(font_name, font_size)
        descent = pdfmetrics.getDescent(font_name, font_size)
        text_height = ascent - descent
        return band_bottom + ((band_height - text_height) / 2) - descent

    def _draw_header(self, canvas: rl_canvas.Canvas, doc: SimpleDocTemplate, config: Dict):
        """
        Desenha o cabeçalho da página CORRIGIDO.
        """
        header_config = config.get('header', {})
        prefeitura = header_config.get('prefeitura') or config.get('inst1', 'Prefeitura Municipal')
        secretaria = header_config.get('secretaria') or config.get('inst2', 'Secretaria de Saúde')
        subsecretaria = header_config.get('subsecretaria') or config.get('inst3', 'Divisão de Controle')
        logo_path = header_config.get('logo_path') or config.get('logo_path')

        page_width, page_height = doc.pagesize
        header_height = 2.35 * cm
        header_bottom = page_height - header_height

        # O bloco institucional mantém a formatação alinhada à esquerda. Apenas
        # sua posição vertical é centralizada dentro da faixa do cabeçalho.
        first_line_ascent = pdfmetrics.getAscent(self._font_bold, 10.5)
        last_line_descent = pdfmetrics.getDescent(self._font_base, 8)
        text_block_height = first_line_ascent + 22 - last_line_descent
        y_position = (
            header_bottom
            + ((header_height - text_block_height) / 2)
            + 22
            - last_line_descent
        )

        canvas.saveState()

        canvas.setFont(self._font_bold, 10.5)
        canvas.setFillColor(colors.black)
        canvas.drawString(doc.leftMargin, y_position, prefeitura)

        canvas.setFont(self._font_base, 8)
        canvas.drawString(doc.leftMargin, y_position - 11, secretaria)
        canvas.drawString(doc.leftMargin, y_position - 22, subsecretaria)

        # A logo permanece à direita e também fica centralizada verticalmente.
        if logo_path and os.path.isfile(logo_path):
            try:
                try:
                    logo_max_height = min(float(config.get("logo_height") or 36), 36)
                    logo_max_width = min(float(config.get("logo_max_width") or 105), 105)
                except (TypeError, ValueError):
                    logo_max_height = 36
                    logo_max_width = 105

                if self._logo_cache is None or getattr(self, "_logo_cache_path", None) != logo_path:
                    self._logo_cache = ImageReader(logo_path)
                    self._logo_cache_path = logo_path

                img = self._logo_cache
                img_width, img_height = img.getSize()

                if img_width and img_height:
                    scale = min(
                        logo_max_width / float(img_width),
                        logo_max_height / float(img_height),
                    )
                    logo_width = img_width * scale
                    logo_height = img_height * scale
                else:
                    logo_width = 65
                    logo_height = 65

                logo_x = page_width - doc.rightMargin - logo_width
                logo_y = header_bottom + ((header_height - logo_height) / 2)

                canvas.drawImage(
                    img,
                    logo_x,
                    logo_y,
                    width=logo_width,
                    height=logo_height,
                    preserveAspectRatio=True,
                    mask="auto",
                )
            except Exception as e:
                self.logger.warning(f"Erro ao carregar logo: {e}")
                
        # A linha atravessa toda a página para marcar claramente o limite
        # superior da área central do relatório.
        line_y = header_bottom

        canvas.setStrokeColor(self.PAGE_DIVIDER_COLOR)
        canvas.setLineWidth(self.PAGE_DIVIDER_WIDTH)
        canvas.line(
            0,
            line_y,
            page_width,
            line_y
        )
        
        canvas.restoreState()

    def _draw_footer(self, canvas: rl_canvas.Canvas, doc: SimpleDocTemplate, config: Dict):
        """
        Desenha o rodapé da página.
        """
        page_width, _ = doc.pagesize
        y_position = self._centered_baseline(
            0,
            doc.bottomMargin,
            self._font_base,
            8,
        )
        
        # Formatar data atual
        hoje = datetime.now()
        dia_semana = self.DIAS_SEMANA_PT[hoje.weekday()]
        data_formatada = f"{dia_semana}, {hoje.day:02d} de {self.MESES_PT[hoje.strftime('%m')]} de {hoje.year}"
        
        fonte_texto = config.get('footer', {}).get('source', 'Fonte: SIA/SUS')
        
        canvas.saveState()
        canvas.setFont(self._font_base, 8)

        # Limite inferior da área central, no início da faixa do rodapé.
        canvas.setStrokeColor(self.PAGE_DIVIDER_COLOR)
        canvas.setLineWidth(self.PAGE_DIVIDER_WIDTH)
        canvas.line(
            0,
            doc.bottomMargin,
            page_width,
            doc.bottomMargin,
        )
        
        # Preserva a formatação original: data à esquerda, fonte ao centro e
        # paginação à direita. Somente a posição vertical usa o centro da faixa.
        canvas.drawString(doc.leftMargin, y_position, data_formatada)
        canvas.drawCentredString(
            page_width / 2,
            y_position,
            fonte_texto,
        )
        
        canvas.restoreState()

    def _create_block_header(self, bloco: Dict, doc: SimpleDocTemplate) -> List[Any]:
        """
        Cria o cabeçalho de um bloco de dados.
        """
        mes_ano = self._format_competencia(bloco['competencia'])
        estabelecimento = Paragraph(
            f"<b>Estabelecimento:</b> {bloco['estabelecimento']} "
            f"<b>(CNES {bloco['cnes']})</b>",
            self.styles['IdentificacaoEsquerda']
        )
        competencia = Paragraph(
            f"<b>Competência:</b> {mes_ano}",
            self.styles['IdentificacaoDireita']
        )

        identificacao = Table(
            [[estabelecimento, competencia]],
            colWidths=[doc.width * 0.72, doc.width * 0.28],
            # As tabelas de producao usam o alinhamento central padrao do
            # ReportLab. Manter a identificacao no mesmo alinhamento elimina
            # o deslocamento causado pelo padding interno do Frame.
            hAlign='CENTER'
        )
        identificacao.setStyle(TableStyle([
            ('VALIGN', (0, 0), (-1, -1), 'BOTTOM'),
            ('LEFTPADDING', (0, 0), (-1, -1), 0),
            ('RIGHTPADDING', (0, 0), (-1, -1), 0),
            ('TOPPADDING', (0, 0), (-1, -1), 0),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
        ]))

        return [identificacao]
    
    def _create_block_totals(self, bloco: Dict, config: Dict) -> List[Paragraph]:
        """
        Cria os totais de um bloco conforme as colunas selecionadas.
        """
        mostrar_aprovados = bool(config.get('mostrar_aprovados', False))
        mostrar_produzidos = bool(config.get('mostrar_produzidos', False))

        procedimentos = bloco.get('procedimentos', [])

        partes = []
        
        if config.get('mostrar_diferencas', False):
            qtd_produzida = sum(float(p.get('quantidade_produzida') or 0) for p in procedimentos)
            vl_produzido = sum(float(p.get('valor_produzido') or 0) for p in procedimentos)

            qtd_aprovada = sum(float(p.get('quantidade_aprovada') or 0) for p in procedimentos)
            vl_aprovado = sum(float(p.get('valor_aprovado') or 0) for p in procedimentos)

            dif_qtd = qtd_produzida - qtd_aprovada
            dif_valor = vl_produzido - vl_aprovado

            partes.append(
                f"<b>Dif. Qtd.:</b> {self._format_integer(dif_qtd)} | "
                f"<b>Dif. Valor:</b> {self._format_currency(dif_valor)}"
            )

            texto_totais = " &nbsp;&nbsp; - &nbsp;&nbsp; ".join(partes)
            return [Paragraph(texto_totais, self.styles['TotaisBloco'])]

        if mostrar_produzidos:
            qtd_produzida = sum(float(p.get('quantidade_produzida') or 0) for p in procedimentos)
            vl_produzido = sum(float(p.get('valor_produzido') or 0) for p in procedimentos)

            partes.append(
                f"<b>Qtd. Produzida:</b> {self._format_integer(qtd_produzida)} | "
                f"<b>Valor Produzido:</b> {self._format_currency(vl_produzido)}"
            )
            
        if mostrar_aprovados:
            qtd_aprovada = sum(float(p.get('quantidade_aprovada') or 0) for p in procedimentos)
            vl_aprovado = sum(float(p.get('valor_aprovado') or 0) for p in procedimentos)

            partes.append(
                f"<b>Qtd. Aprovada:</b> {self._format_integer(qtd_aprovada)} | "
                f"<b>Valor Aprovado:</b> {self._format_currency(vl_aprovado)}"
            )

        if not mostrar_aprovados and not mostrar_produzidos:
            qtd_aprovada = sum(float(p.get('quantidade_aprovada') or 0) for p in procedimentos)
            valor_total = sum(float(p.get('valor_total') or 0) for p in procedimentos)
            partes.append(
                f"<b>Qtd. Total:</b> {self._format_integer(qtd_aprovada)} | "
                f"<b>Valor Total:</b> {self._format_currency(valor_total)}"
            )

        texto_totais = " &nbsp;&nbsp; - &nbsp;&nbsp; ".join(partes)

        return [Paragraph(texto_totais, self.styles['TotaisBloco'])]
    
    def _create_general_totals(self, quantidade: int, valor) -> List[Any]:
        """
        Cria os totais gerais do relatório CORRIGIDO.
        """
        # GARANTIR que o valor é Decimal
        valor_decimal = self._safe_decimal_convert(valor)
        
        quantidade_formatada = self._format_integer(quantidade)
        valor_formatado = self._format_currency(valor_decimal)
        
        texto_geral = f"Totais - Prod.: {quantidade_formatada} | Valor: {valor_formatado}"

        return [
            Paragraph(texto_geral, self.styles['TotaisGerais']),
            Spacer(1, 0.1 * cm),
        ]
    
    def _create_procedure_table_simple(self, procedimentos: List[Dict], doc: SimpleDocTemplate, config: Dict) -> Table:
        """
        Cria tabela simples de procedimentos com colunas dinâmicas.
        """
        colunas = self._get_colunas_relatorio(config)

        cabecalho = [col['titulo'] for col in colunas]
        linhas_dados = [cabecalho]

        for procedimento in procedimentos:
            linha = []

            for col in colunas:
                valor = procedimento.get(col['campo'], '')

                if col['tipo'] == 'descricao':
                    linha.append(self._truncate_text(str(valor or ''), 60))

                elif col['tipo'] == 'inteiro':
                    linha.append(self._format_integer(valor or 0))

                elif col['tipo'] == 'moeda':
                    linha.append(self._format_currency(valor or 0))

                else:
                    linha.append(str(valor or ''))

            linhas_dados.append(linha)

        largura_total = doc.width
        soma_larguras = sum(col['largura'] for col in colunas)

        larguras_colunas = [
            largura_total * (col['largura'] / soma_larguras)
            for col in colunas
        ]

        repeat_rows = 1 if config.get('repetir_cabecalho', True) else 0

        tabela = Table(
            linhas_dados,
            colWidths=larguras_colunas,
            repeatRows=repeat_rows
        )

        estilo_base = [
            ('FONT', (0, 0), (-1, -1), self._font_base, 8),
            ('FONTSIZE', (0, 0), (-1, -1), 8),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('GRID', (0, 0), (-1, -1), 0.5, self.BORDER_GRAY),
            ('TOPPADDING', (0, 0), (-1, -1), 3),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 3),

            # Cabeçalho
            ('BACKGROUND', (0, 0), (-1, 0), self.PRIMARY_COLOR),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('FONT', (0, 0), (-1, 0), self._font_bold, 9),
            ('ALIGN', (0, 0), (-1, 0), 'CENTER'),

            # Cores alternadas
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, self.LIGHT_GRAY]),
        ]

        # Alinhamento dinâmico do corpo
        for idx, col in enumerate(colunas):
            estilo_base.append(
                ('ALIGN', (idx, 1), (idx, -1), col.get('align', 'LEFT'))
            )

        tabela.setStyle(TableStyle(estilo_base))
        return tabela
    
    def _create_procedure_table_detailed(self, procedimentos: List[Dict], doc: SimpleDocTemplate, config: Dict) -> Table:
        """
        Cria tabela detalhada com agrupamento de procedimentos.
        """
        colunas = self._get_colunas_relatorio(config)
        linhas_dados = [[col['titulo'] for col in colunas]]
        linhas_agrupamento = []
        
        # Ordenar procedimentos por código
        procedimentos_ordenados = sorted(
            procedimentos,
            key=lambda p: self._extract_digits(p.get('codigo', ''))
        )
        
        grupo_anterior = subgrupo_anterior = forma_anterior = None
        
        for i, procedimento in enumerate(procedimentos_ordenados, start=1):
            codigo = str(procedimento.get('codigo', ''))
            digitos = self._extract_digits(codigo)
            
            # Adicionar linhas de agrupamento
            if len(digitos) >= 2:
                grupo_atual = digitos[:2]
                if grupo_atual != grupo_anterior:
                    linhas_dados.append([f"Grupo {grupo_atual}"] + [''] * (len(colunas) - 1))
                    linhas_agrupamento.append((len(linhas_dados) - 1, "grupo"))
                    grupo_anterior = grupo_atual
                    subgrupo_anterior = forma_anterior = None
            
            if len(digitos) >= 4:
                subgrupo_atual = f"{digitos[:2]}.{digitos[2:4]}"
                if subgrupo_atual != subgrupo_anterior:
                    linhas_dados.append([f"Subgrupo {subgrupo_atual}"] + [''] * (len(colunas) - 1))
                    linhas_agrupamento.append((len(linhas_dados) - 1, "subgrupo"))
                    subgrupo_anterior = subgrupo_atual
                    forma_anterior = None
            
            if len(digitos) >= 6:
                forma_atual = f"{digitos[:2]}.{digitos[2:4]}.{digitos[4:6]}"
                if forma_atual != forma_anterior:
                    linhas_dados.append([f"Forma de Organização {forma_atual}"] + [''] * (len(colunas) - 1))
                    linhas_agrupamento.append((len(linhas_dados) - 1, "forma"))
                    forma_anterior = forma_atual
            
            # Adicionar linha do procedimento
            descricao_paragraph = Paragraph(
                procedimento.get('descricao', 'Descrição não disponível'),
                self.styles['DescricaoProcedimento']
            )
            
            linha = []

            for col in colunas:
                valor = procedimento.get(col['campo'], '')

                if col['tipo'] == 'descricao':
                    linha.append(Paragraph(
                        str(valor or 'Descrição não disponível'),
                        self.styles['DescricaoProcedimento']
                    ))

                elif col['tipo'] == 'inteiro':
                    linha.append(self._format_integer(valor or 0))

                elif col['tipo'] == 'moeda':
                    linha.append(self._format_currency(valor or 0))

                else:
                    linha.append(str(valor or ''))

            linhas_dados.append(linha)
            
        # Criar tabela
        largura_total = doc.width
        soma_larguras = sum(col['largura'] for col in colunas)

        larguras_colunas = [
            largura_total * (col['largura'] / soma_larguras)
            for col in colunas
        ]
        
        # CORREÇÃO: Usar a configuração repetir_cabecalho para controlar repeatRows
        repeat_rows = 1 if config.get('repetir_cabecalho', True) else 0
        
        tabela = Table(
            linhas_dados,
            colWidths=larguras_colunas,
            repeatRows=repeat_rows
        )
        
        # Aplicar estilos
        estilo = TableStyle([
            # Estilos base
            ('FONT', (0, 0), (-1, -1), self._font_base, 9),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('GRID', (0, 0), (-1, -1), 0.25, self.BORDER_GRAY),
            ('TOPPADDING', (0, 0), (-1, -1), 1.7),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 1.7),
            
            # Cabeçalho
            ('BACKGROUND', (0, 0), (-1, 0), self.PRIMARY_COLOR),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('FONT', (0, 0), (-1, 0), self._font_bold, 9),
            ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
            
            # Alinhamento do corpo
            ('ALIGN', (0, 1), (0, -1), 'CENTER'),  # Código
            ('ALIGN', (2, 1), (2, -1), 'RIGHT'),   # Quantidade
            ('ALIGN', (3, 1), (4, -1), 'RIGHT'),   # Valores
        ])
        
        for idx, col in enumerate(colunas):
            estilo.add('ALIGN', (idx, 1), (idx, -1), col.get('align', 'LEFT'))
        
        # Estilos para linhas de agrupamento
        for linha, nivel in linhas_agrupamento:
            estilo.add('SPAN', (0, linha), (-1, linha))
            # Mantém cada legenda junto da linha seguinte. Quando Grupo,
            # Subgrupo e Forma aparecem em sequência, os comandos formam uma
            # cadeia que leva toda a escada e o primeiro procedimento para a
            # página seguinte, evitando uma legenda isolada no rodapé.
            estilo.add('NOSPLIT', (0, linha), (-1, linha + 1))
            estilo.add('BACKGROUND', (0, linha), (-1, linha), self.GROUP_BG_COLOR)
            estilo.add('FONT', (0, linha), (-1, linha), self._font_bold, 9)
            estilo.add('ALIGN', (0, linha), (-1, linha), 'LEFT')
            estilo.add(
                'LEFTPADDING',
                (0, linha),
                (-1, linha),
                self.GROUP_HIERARCHY_INDENTS[nivel],
            )
            estilo.add('TOPPADDING', (0, linha), (-1, linha), 3)
            estilo.add('BOTTOMPADDING', (0, linha), (-1, linha), 2)
        
        tabela.setStyle(estilo)
        return tabela
        
    def _create_procedure_table_diferencas(self, procedimentos: List[Dict], doc: SimpleDocTemplate, config: Dict) -> Table:
        """
        Cria tabela específica para o relatório de diferenças entre produzido e aprovado,
        usando colunas dinâmicas no mesmo padrão das demais tabelas.
        """

        colunas = self._get_colunas_relatorio(config)

        cabecalho = [col['titulo'] for col in colunas]
        linhas_dados = [cabecalho]

        for procedimento in procedimentos:
            linha = []

            for col in colunas:
                valor = procedimento.get(col['campo'], '')

                if col['tipo'] == 'descricao':
                    linha.append(
                        self._truncate_text(str(valor or 'Descrição não disponível'), 60)
                    )

                elif col['tipo'] == 'inteiro':
                    linha.append(
                        self._format_integer(valor or 0)
                    )

                elif col['tipo'] == 'moeda':
                    linha.append(
                        self._format_currency(valor or 0)
                    )

                else:
                    linha.append(str(valor or ''))

            linhas_dados.append(linha)

        largura_total = doc.width

        soma_larguras = sum(col['largura'] for col in colunas)

        larguras_colunas = [
            largura_total * (col['largura'] / soma_larguras)
            for col in colunas
        ]

        repeat_rows = 1 if config.get('repetir_cabecalho', True) else 0

        tabela = Table(
            linhas_dados,
            colWidths=larguras_colunas,
            repeatRows=repeat_rows
        )

        estilo_base = [
            # Estilos base
            ('FONT', (0, 0), (-1, -1), self._font_base, 8),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('GRID', (0, 0), (-1, -1), 0.5, self.BORDER_GRAY),
            ('TOPPADDING', (0, 0), (-1, -1), 3),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 3),

            # Cabeçalho
            ('BACKGROUND', (0, 0), (-1, 0), self.PRIMARY_COLOR),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('FONT', (0, 0), (-1, 0), self._font_bold, 9),
            ('ALIGN', (0, 0), (-1, 0), 'CENTER'),

            # Zebra
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, self.LIGHT_GRAY]),
        ]

        # Alinhamento dinâmico das colunas
        for idx, col in enumerate(colunas):
            estilo_base.append(
                ('ALIGN', (idx, 1), (idx, -1), col.get('align', 'LEFT'))
            )

        tabela.setStyle(TableStyle(estilo_base))
        return tabela
        
    def _get_colunas_relatorio(self, config: dict):
        """
        Define dinamicamente as colunas do relatório conforme os flags da tela de filtros.
        """
        
        mostrar_aprovados  = bool(config.get('mostrar_aprovados', False))
        mostrar_produzidos = bool(config.get('mostrar_produzidos', False))
        mostrar_diferencas = bool(config.get('mostrar_diferencas', False))
        
        # Usado somente no relatório novo de diferenças
        diferencas_somente_quantidades = bool(config.get('diferencas_somente_quantidades', False))

        colunas = [
            {
                'titulo': 'Cód. Proc.',
                'campo': 'codigo',
                'tipo': 'texto',
                'largura': 0.15,
                'align': 'CENTER'
            },
            {
                'titulo': 'Descrição',
                'campo': 'descricao',
                'tipo': 'texto',
                'largura': 0.60
            }
        ]
        
        # Nos relatórios normais mantém Valor Unitário.
        # No relatório de diferenças somente com quantidades, remove.
        if not diferencas_somente_quantidades:
            colunas.append({
                'titulo': 'Valor Unit.',
                'campo': 'valor_unitario',
                'tipo': 'moeda',
                'largura': 0.11,
                'align': 'CENTER'
            })
        
        if mostrar_produzidos:
            colunas.extend([
                {
                    'titulo': 'Qtd. Prod.',
                    'campo': 'quantidade_produzida',
                    'tipo': 'inteiro',
                    'largura': 0.11,
                    'align': 'CENTER'
                }
            ])
            
            # No relatório de diferenças com somente quantidades, não mostra valor produzido
            if not diferencas_somente_quantidades:
                colunas.append({
                    'titulo': 'Valor Prod.',
                    'campo': 'valor_produzido',
                    'tipo': 'moeda',
                    'largura': 0.13,
                    'align': 'RIGHT'
                })

        if mostrar_aprovados:
            colunas.extend([
                {
                    'titulo': 'Qtd. Aprov.',
                    'campo': 'quantidade_aprovada',
                    'tipo': 'inteiro',
                    'largura': 0.11,
                    'align': 'CENTER'
                }
            ])
            
            # No relatório de diferenças com somente quantidades, não mostra valor aprovado
            if not diferencas_somente_quantidades:
                colunas.append({
                    'titulo': 'Valor Aprov.',
                    'campo': 'valor_aprovado',
                    'tipo': 'moeda',
                    'largura': 0.13,
                    'align': 'RIGHT'
                })
            
        if mostrar_diferencas:
            colunas.extend([
                {
                    'titulo': 'Dif. Qtd.',
                    'campo': 'diferenca_quantidade',
                    'tipo': 'inteiro',
                    'largura': 0.10,
                    'align': 'CENTER'
                },
                {
                    'titulo': 'Dif. Valor',
                    'campo': 'diferenca_valor',
                    'tipo': 'moeda',
                    'largura': 0.13,
                    'align': 'RIGHT'
                }
            ])

        # Regra: se nenhum flag for marcado, mantém somente Valor Total.
        if not mostrar_aprovados and not mostrar_produzidos and not mostrar_diferencas:
            colunas.append({
                'titulo': 'Qtd.',
                'campo': 'quantidade',
                'tipo': 'inteiro',
                'largura': 0.10,
                'align': 'CENTER'
            })
            colunas.append({
                'titulo': 'Valor Total',
                'campo': 'valor_total',
                'tipo': 'moeda',
                'largura': 0.15,
                'align': 'RIGHT'
            })

        return colunas
    
    def _formatar_valor_tabela(self, valor, tipo: str):
        """Formata valores para a tabela do relatório."""
        if valor is None:
            valor = 0

        if tipo == 'moeda':
            try:
                return f"R$ {float(valor):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
            except Exception:
                return "R$ 0,00"

        if tipo == 'numero':
            try:
                numero = float(valor)
                if numero.is_integer():
                    return f"{int(numero):,}".replace(",", ".")
                return f"{numero:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
            except Exception:
                return "0"

        return str(valor or "")

    # ========== MÉTODOS UTILITÁRIOS ==========
    
    def _safe_decimal_convert(self, value, default=Decimal('0.00')) -> Decimal:
        """
        Converte valor para Decimal de forma segura.
        
        Args:
            value: Valor a ser convertido
            default: Valor padrão em caso de erro
            
        Returns:
            Valor convertido para Decimal
        """
        try:
            if value is None:
                return default
            if isinstance(value, Decimal):
                return value.quantize(Decimal('0.01'))
            if isinstance(value, (int, float)):
                return Decimal(str(value)).quantize(Decimal('0.01'))
            return Decimal(str(value)).quantize(Decimal('0.01'))
        except (ValueError, TypeError, ArithmeticError):
            return default

    def _format_competencia(self, competencia: str) -> str:
        """
        Formata competência no formato Mês/Ano.
        
        Args:
            competencia: String no formato AAAAMM
            
        Returns:
            String formatada
        """
        try:
            if len(competencia) == 6:
                ano = competencia[:4]
                mes = competencia[4:6]
                mes_extenso = self.MESES_PT.get(mes, mes)
                return f"{mes_extenso}/{ano}"
        except Exception:
            pass
        return competencia

    def _format_currency(self, valor) -> str:
        """
        Formata valor para o padrão monetário brasileiro.
        
        Args:
            valor: Valor a ser formatado
            
        Returns:
            String formatada
        """
        try:
            valor_numerico = float(valor or 0)
        except (ValueError, TypeError):
            valor_numerico = 0.0
        
        valor_formatado = f"{valor_numerico:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
        return f"R$ {valor_formatado}"

    def _format_integer(self, valor) -> str:
        """
        Formata valor inteiro com separadores de milhar.
        
        Args:
            valor: Valor a ser formatado
            
        Returns:
            String formatada
        """
        try:
            valor_inteiro = int(valor)
        except (ValueError, TypeError):
            valor_inteiro = 0
        
        return f"{valor_inteiro:,}".replace(',', '.')

    def _truncate_text(self, texto: str, limite: int) -> str:
        """
        Trunca texto se exceder o limite de caracteres.
        
        Args:
            texto: Texto original
            limite: Limite de caracteres
            
        Returns:
            Texto truncado se necessário
        """
        texto_str = str(texto)
        if len(texto_str) <= limite:
            return texto_str
        return texto_str[:limite - 1] + '…'

    def _extract_digits(self, texto: str) -> str:
        """
        Extrai apenas dígitos de uma string.
        
        Args:
            texto: Texto original
            
        Returns:
            String contendo apenas dígitos
        """
        return ''.join(caracter for caracter in str(texto or '') if caracter.isdigit())
