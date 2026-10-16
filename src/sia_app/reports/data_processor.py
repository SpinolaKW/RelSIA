import re
from datetime import datetime
from typing import Dict, List, Optional, Any, Tuple
from sia_app.config.constants import Constants

class DataProcessor:
    """
    Processador de dados para geração de relatórios com otimizações de performance.
    
    Características:
    - Queries otimizadas com uso de índices
    - Processamento eficiente de grandes volumes
    - Agrupamentos flexíveis
    - Tratamento robusto de erros
    """
    
    def __init__(self, db_connection, logger):
        """
        Inicializa o processador de dados.
        
        Args:
            db_connection: Conexão com o banco de dados
            logger: Instância de logger
        """
        self.db = db_connection
        self.logger = logger
    
    def obter_dados_para_relatorio(self, filtros: Optional[Dict] = None) -> List[Dict[str, Any]]:
        """
        Obtém dados processados para geração de relatórios.
        Usa sempre agregação para somar arquivos diferentes corretamente.
        """
        return self.obter_dados_aggregado(filtros or {})
    
    def _deve_usar_aggregado(self, filtros: Optional[Dict]) -> bool:
        """
        Determina se deve usar o método agregado baseado nos filtros.
        
        Args:
            filtros: Filtros aplicados
            
        Returns:
            True se deve usar método agregado
        """
        if not filtros:
            return False
        
        # Usar agregado quando há agrupamento explícito ou muitos dados
        agrupamentos = ['cnes_list', 'competencias', 'procedimento']
        return any(filtros.get(key) for key in agrupamentos)
    
    def _construir_query_otimizada(self) -> str:
        """
        Constrói query otimizada para relatórios com colunas necessárias.
        
        Returns:
            Query SQL otimizada
        """
        return '''
            SELECT
                p.PRD_UID, 
                p.PRD_CMP, 
                p.PRD_PA, 
                p.PRD_QT_A, 
                p.PRD_VL_A,
                (p.PRD_QT_A * pa.PA_TOTAL) as VALOR_TOTAL,
                COALESCE(NULLIF(e.NO_FANTASIA, ''), 'NÃO CADASTRADO') AS NO_FANTASIA,
                pa.PA_DC, 
                pa.PA_DV,
                pa.PA_TOTAL as VALOR_TABELA
            FROM tb_prd p 
            LEFT JOIN tb_estabelecimento e
                ON p.PRD_UID = e.CO_CNES
            LEFT JOIN tb_pa pa ON p.PRD_PA = pa.PROC
            WHERE 1=1
        '''
    
    def _aplicar_filtros_otimizados(self, query: str, filtros: Dict, params: List) -> Tuple[str, List]:
        """
        Aplica filtros de forma otimizada, aproveitando índices.
        
        Args:
            query: Query base
            filtros: Dicionário de filtros
            params: Lista de parâmetros
            
        Returns:
            Tupla (query, params) atualizados
        """
        # Filtro por CNES - otimizado
        if filtros.get('cnes_list'):
            cnes_normalizados = self._normalizar_lista_cnes(filtros['cnes_list'])
            if cnes_normalizados:
                placeholders = ','.join(['?'] * len(cnes_normalizados))
                query += f" AND p.PRD_UID IN ({placeholders})"
                params.extend(cnes_normalizados)
        
        # Filtro por procedimento - otimizado com LIKE para uso de índice
        if filtros.get('procedimento'):
            procedimento = filtros['procedimento'].strip()
            tipo_filtro = filtros.get('tipo_filtro_proc', 'exato')
            
            if tipo_filtro == 'grupo' and len(procedimento) == 2:
                query += " AND p.PRD_PA LIKE ?"
                params.append(f"{procedimento}%")
            elif tipo_filtro == 'subgrupo' and len(procedimento) == 4:
                query += " AND p.PRD_PA LIKE ?"
                params.append(f"{procedimento}%")
            elif tipo_filtro == 'forma' and len(procedimento) == 6:
                query += " AND p.PRD_PA LIKE ?"
                params.append(f"{procedimento}%")
            else:  # exato
                query += " AND p.PRD_PA = ?"
                params.append(procedimento)
        
        # Filtro por competências - otimizado
        if filtros.get('competencias'):
            competencias_validas = [c for c in filtros['competencias'] if c and str(c).strip()]
            if competencias_validas:
                placeholders = ','.join(['?'] * len(competencias_validas))
                query += f" AND p.PRD_CMP IN ({placeholders})"
                params.extend(competencias_validas)
        
        # Filtro por intervalo de competência
        if filtros.get('competencia_inicio'):
            query += " AND p.PRD_CMP >= ?"
            params.append(filtros['competencia_inicio'])
        
        if filtros.get('competencia_fim'):
            query += " AND p.PRD_CMP <= ?"
            params.append(filtros['competencia_fim'])
        
        # Filtro para ocultar zerados
        if filtros.get('ocultar_zerados'):
            query += " AND p.PRD_QT_A > 0"
        
        return query, params
    
    def _normalizar_lista_cnes(self, cnes_list: List) -> List[str]:
        """
        Normaliza lista de CNES para formato padrão.
        
        Args:
            cnes_list: Lista de CNES
            
        Returns:
            Lista de CNES normalizados
        """
        normalizados = []
        for cnes in cnes_list:
            if cnes is None:
                continue
            cnes_str = str(cnes).strip()
            if cnes_str.endswith('.0'):
                cnes_str = cnes_str[:-2]
            cnes_str = re.sub(r'\D', '', cnes_str)
            if cnes_str:
                normalizados.append(cnes_str.zfill(7))
        return normalizados
    
    def obter_dados_aggregado(
        self,
        filtros: Optional[Dict] = None,
        separar_por_financiamento: bool = False,
    ) -> List[Dict[str, Any]]:
        """
        Retorna dados agregados para relatórios com melhor performance.
        
        Args:
            filtros: Filtros a serem aplicados
            separar_por_financiamento: Mantém cada tipo de financiamento em
                uma linha própria. Usado pela exportação CSV para não atribuir
                um único código a produções de financiamentos diferentes.
            
        Returns:
            Lista de dicionários com dados agregados
        """
        try:
            filtros = filtros or {}
            financiamento_select = (
                "COALESCE(p.PRD_TPFIN, '')"
                if separar_por_financiamento
                else "MAX(COALESCE(p.PRD_TPFIN, ''))"
            )
            financiamento_group = (
                ",\n                    p.PRD_TPFIN"
                if separar_por_financiamento
                else ""
            )
            financiamento_order = ", p.PRD_TPFIN" if separar_por_financiamento else ""

            query = f"""
                SELECT
                    p.PRD_UID,
                    COALESCE(NULLIF(e.NO_FANTASIA, ''), 'NÃO CADASTRADO') AS NO_FANTASIA,
                    p.PRD_CMP,
                    p.PRD_PA,
                    pa.PA_DC,
                    pa.PA_DV,

                    {financiamento_select} AS PRD_TPFIN,
                    MAX(COALESCE(p.PRD_CPX, '')) AS PRD_CPX,
                    MAX(COALESCE(pa.PA_CTF, '')) AS PA_CTF,
                    MAX(COALESCE(pa.PA_CPX, '')) AS PA_CPX,

                    pa.PA_TOTAL AS VALOR_UNITARIO,

                    SUM(COALESCE(p.PRD_QT_A, 0)) AS QUANTIDADE_APROVADA,
                    SUM(COALESCE(p.PRD_QT_A, 0) * COALESCE(pa.PA_TOTAL, 0)) AS VALOR_APROVADO,

                    SUM(COALESCE(p.PRD_QT_P, 0)) AS QUANTIDADE_PRODUZIDA,
                    SUM(COALESCE(p.PRD_QT_P, 0) * COALESCE(pa.PA_TOTAL, 0)) AS VALOR_PRODUZIDO,

                    SUM(p.PRD_QT_A) AS QUANTIDADE,
                    SUM(COALESCE(p.PRD_QT_A, 0) * COALESCE(pa.PA_TOTAL, 0)) AS VALOR_TOTAL

                FROM tb_prd p
                LEFT JOIN tb_pa pa ON pa.PROC = p.PRD_PA
                LEFT JOIN tb_estabelecimento e
                    ON p.PRD_UID = e.CO_CNES
                WHERE 1=1
            """
            params = []

            # Aplicar filtros otimizados
            query, params = self._aplicar_filtros_aggregado(query, filtros, params)

            # Agrupamento e ordenação
            query += f"""
                GROUP BY
                    p.PRD_UID,
                    e.NO_FANTASIA,
                    p.PRD_CMP,
                    p.PRD_PA,
                    pa.PA_DC,
                    pa.PA_DV,
                    pa.PA_TOTAL{financiamento_group}
                ORDER BY p.PRD_UID, p.PRD_CMP, p.PRD_PA{financiamento_order}
            """

            self.logger.debug("Executando query agregada")
            self.logger.debug("SQL: %s", query)
            self.logger.debug("Parâmetros: %s", params)

            with self.db.read() as cursor:
                cursor.execute(query, params)
                rows = cursor.fetchall()
                
                if not rows:
                    return []
                
                # Converter para dicionários
                colunas = [desc[0] for desc in cursor.description]
                resultados = []
                
                for row in rows:
                    resultado_dict = {}
                    for i, valor in enumerate(row):
                        resultado_dict[colunas[i]] = valor
                    resultados.append(resultado_dict)
            
            self.logger.info(f"Retornados {len(resultados)} registros agregados")
            return resultados
            
        except Exception:
            self.logger.exception("Erro ao obter dados agregados")
            return []

    def obter_dados_exportacao_csv(
        self,
        filtros: Optional[Dict] = None,
    ) -> List[Dict[str, Any]]:
        """Retorna dados agregados sem misturar tipos de financiamento."""
        return self.obter_dados_aggregado(
            filtros,
            separar_por_financiamento=True,
        )
    
    def obter_dados_visualizacao_com_cbo(self, filtros: Optional[Dict] = None) -> List[Dict[str, Any]]:
        """
        Retorna dados detalhados para a janela Visualizar Dados, separados por CBO.

        Esta função é apenas para visualização em tela.
        Os relatórios PDF continuam usando obter_dados_aggregado(),
        que consolida sem CBO.
        """
        try:
            filtros = filtros or {}

            query = """
                SELECT
                    p.PRD_UID,
                    COALESCE(NULLIF(e.NO_FANTASIA, ''), 'NÃO CADASTRADO') AS NO_FANTASIA,
                    p.PRD_CMP,
                    p.PRD_PA,
                    p.PRD_CBO,
                    pa.PA_DC,
                    pa.PA_DV,

                    MAX(COALESCE(p.PRD_TPFIN, '')) AS PRD_TPFIN,
                    MAX(COALESCE(p.PRD_CPX, '')) AS PRD_CPX,
                    MAX(COALESCE(pa.PA_CTF, '')) AS PA_CTF,
                    MAX(COALESCE(pa.PA_CPX, '')) AS PA_CPX,

                    pa.PA_TOTAL AS VALOR_UNITARIO,

                    SUM(COALESCE(p.PRD_QT_A, 0)) AS QUANTIDADE_APROVADA,
                    SUM(COALESCE(p.PRD_QT_A, 0) * COALESCE(pa.PA_TOTAL, 0)) AS VALOR_APROVADO,

                    SUM(COALESCE(p.PRD_QT_P, 0)) AS QUANTIDADE_PRODUZIDA,
                    SUM(COALESCE(p.PRD_QT_P, 0) * COALESCE(pa.PA_TOTAL, 0)) AS VALOR_PRODUZIDO,

                    SUM(p.PRD_QT_A) AS QUANTIDADE,
                    SUM(COALESCE(p.PRD_QT_A, 0) * COALESCE(pa.PA_TOTAL, 0)) AS VALOR_TOTAL

                FROM tb_prd p
                LEFT JOIN tb_pa pa ON pa.PROC = p.PRD_PA
                LEFT JOIN tb_estabelecimento e
                    ON p.PRD_UID = e.CO_CNES
                WHERE 1=1
            """

            params = []

            query, params = self._aplicar_filtros_aggregado(query, filtros, params)

            query += """
                GROUP BY
                    p.PRD_UID,
                    e.NO_FANTASIA,
                    p.PRD_CMP,
                    p.PRD_PA,
                    p.PRD_CBO,
                    pa.PA_DC,
                    pa.PA_DV,
                    pa.PA_TOTAL
                ORDER BY
                    p.PRD_UID,
                    p.PRD_CMP,
                    p.PRD_PA,
                    p.PRD_CBO
            """

            with self.db.read() as cursor:
                cursor.execute(query, params)
                rows = cursor.fetchall()

                if not rows:
                    return []

                colunas = [desc[0] for desc in cursor.description]
                resultados = []

                for row in rows:
                    resultado_dict = {}
                    for i, valor in enumerate(row):
                        resultado_dict[colunas[i]] = valor

                    resultados.append(resultado_dict)

            return resultados

        except Exception:
            self.logger.exception("Erro ao obter dados detalhados com CBO")
            return []
    
    def obter_dados_diferencas_aprovado_produzido(self, filtros: Optional[Dict] = None) -> List[Dict[str, Any]]:
        """
        Obtém dados onde quantidade/valor produzido são diferentes de quantidade/valor aprovado.

        Aceita filtros de:
        - CNES
        - Competência
        - Procedimento

        Ignora flags de exibição de aprovados/produzidos.
        """
        filtros = filtros or {}

        try:
            query = """
                SELECT
                    p.PRD_UID,
                    COALESCE(NULLIF(e.NO_FANTASIA, ''), 'NÃO CADASTRADO') AS NO_FANTASIA,
                    p.PRD_CMP,
                    p.PRD_PA,
                    pa.PA_DC,
                    pa.PA_DV,
                    pa.PA_TOTAL AS VALOR_UNITARIO,

                    SUM(COALESCE(p.PRD_QT_A, 0)) AS QUANTIDADE_APROVADA,
                    SUM(COALESCE(p.PRD_QT_A, 0) * COALESCE(pa.PA_TOTAL, 0)) AS VALOR_APROVADO,

                    SUM(COALESCE(p.PRD_QT_P, 0)) AS QUANTIDADE_PRODUZIDA,
                    SUM(COALESCE(p.PRD_QT_P, 0) * COALESCE(pa.PA_TOTAL, 0)) AS VALOR_PRODUZIDO,

                    SUM(COALESCE(p.PRD_QT_P, 0)) - SUM(COALESCE(p.PRD_QT_A, 0)) AS DIFERENCA_QUANTIDADE,
                    SUM(COALESCE(p.PRD_QT_P, 0) * COALESCE(pa.PA_TOTAL, 0)) 
                        - SUM(COALESCE(p.PRD_QT_A, 0) * COALESCE(pa.PA_TOTAL, 0)) AS DIFERENCA_VALOR,

                    SUM(COALESCE(p.PRD_QT_A, 0) * COALESCE(pa.PA_TOTAL, 0)) AS VALOR_TOTAL

                FROM tb_prd p

                LEFT JOIN tb_estabelecimento e
                    ON p.PRD_UID = e.CO_CNES

                LEFT JOIN tb_pa pa
                    ON p.PRD_PA = pa.PROC

                WHERE 1=1
            """

            params = []

            # Filtro CNES
            if filtros.get('cnes_list'):
                cnes_list = filtros['cnes_list']
                placeholders = ','.join(['?'] * len(cnes_list))
                query += f"""
                    AND p.PRD_UID IN ({placeholders})
                """
                params.extend(cnes_list)

            # Filtro competência inicial
            if filtros.get('competencia_inicio'):
                query += " AND p.PRD_CMP >= ?"
                params.append(filtros['competencia_inicio'])

            # Filtro competência final
            if filtros.get('competencia_fim'):
                query += " AND p.PRD_CMP <= ?"
                params.append(filtros['competencia_fim'])

            # Filtro procedimento
            procedimento = str(filtros.get('procedimento', '')).strip()
            tipo_filtro_proc = str(filtros.get('tipo_filtro_proc', '')).strip()

            if procedimento:
                if tipo_filtro_proc == 'grupo':
                    query += " AND SUBSTR(p.PRD_PA, 1, 2) = ?"
                    params.append(procedimento)

                elif tipo_filtro_proc == 'subgrupo':
                    query += " AND SUBSTR(p.PRD_PA, 1, 4) = ?"
                    params.append(procedimento)

                elif tipo_filtro_proc == 'forma':
                    query += " AND SUBSTR(p.PRD_PA, 1, 6) = ?"
                    params.append(procedimento)

                else:
                    query += " AND p.PRD_PA = ?"
                    params.append(procedimento)

            query += """
                GROUP BY
                    p.PRD_UID,
                    e.NO_FANTASIA,
                    p.PRD_CMP,
                    p.PRD_PA,
                    pa.PA_DC,
                    pa.PA_DV,
                    pa.PA_TOTAL

                HAVING
                    SUM(COALESCE(p.PRD_QT_A, 0)) <> SUM(COALESCE(p.PRD_QT_P, 0))
                    OR
                    ROUND(SUM(COALESCE(p.PRD_QT_A, 0) * COALESCE(pa.PA_TOTAL, 0)), 2) 
                    <> 
                    ROUND(SUM(COALESCE(p.PRD_QT_P, 0) * COALESCE(pa.PA_TOTAL, 0)), 2)

                ORDER BY
                    p.PRD_UID,
                    p.PRD_CMP,
                    p.PRD_PA
            """

            with self.db.read() as cursor:
                cursor.execute(query, params)
                rows = cursor.fetchall()

            return [dict(row) for row in rows]

        except Exception:
            self.logger.exception("Erro ao obter diferenças aprovado x produzido")
            return []
    
    def _aplicar_filtros_aggregado(self, query: str, filtros: Dict, params: List) -> Tuple[str, List]:
        """
        Aplica filtros otimizados para query agregada.
        
        Args:
            query: Query base
            filtros: Filtros a aplicar
            params: Parâmetros atuais
            
        Returns:
            Tupla (query, params) atualizados
        """
        # CNES - usar qualquer chave possível
        cnes_list = filtros.get('cnes_list') or filtros.get('cnes') or []
        if cnes_list:
            cnes_normalizados = self._normalizar_lista_cnes(cnes_list)
            if cnes_normalizados:
                placeholders = ",".join("?" for _ in cnes_normalizados)
                query += f" AND p.PRD_UID IN ({placeholders})"
                params.extend(cnes_normalizados)

        # Procedimento
        procedimento = (filtros.get('procedimento') or filtros.get('codigo_procedimento') or '').strip()
        if procedimento:
            tipo_filtro = (filtros.get('tipo_filtro_proc') or filtros.get('tipo_procedimento') or 'exato').lower()
            
            if tipo_filtro in ('grupo', 'subgrupo', 'forma'):
                query += " AND p.PRD_PA LIKE ?"
                params.append(f"{procedimento}%")
            else:
                query += " AND p.PRD_PA = ?"
                params.append(procedimento)

        # Competências
        competencias = filtros.get('competencias') or []
        if competencias:
            comp_validas = [str(c).strip() for c in competencias if str(c).strip()]
            if comp_validas:
                placeholders = ",".join("?" for _ in comp_validas)
                query += f" AND p.PRD_CMP IN ({placeholders})"
                params.extend(comp_validas)

        # Intervalo de competência
        if filtros.get('competencia_inicio'):
            query += " AND p.PRD_CMP >= ?"
            params.append(str(filtros['competencia_inicio']).strip())
        
        if filtros.get('competencia_fim'):
            query += " AND p.PRD_CMP <= ?"
            params.append(str(filtros['competencia_fim']).strip())

        # Ocultar zerados
        if filtros.get('ocultar_zerados'):
            query += " AND p.PRD_QT_A > 0"
            
        # Tipo de financiamento da produção
        if filtros.get("tipo_financiamento"):
            query += " AND p.PRD_TPFIN = ?"
            params.append(str(filtros["tipo_financiamento"]).strip())


        # Complexidade da produção
        if filtros.get("complexidade"):
            query += " AND p.PRD_CPX = ?"
            params.append(str(filtros["complexidade"]).strip())

        return query, params
    
    def agrupar_por_estabelecimento_competencia(self, dados: List[Dict]) -> Dict[str, Dict]:
        """
        Agrupa dados por estabelecimento e competência de forma otimizada.
        
        Args:
            dados: Lista de dados brutos
            
        Returns:
            Dicionário com dados agrupados
        """
        agrupados = {}
        
        for row in dados:
            cnes = row.get('PRD_UID', '')
            competencia = row.get('PRD_CMP', '')
            chave = f"{cnes}_{competencia}"
            
            if chave not in agrupados:
                agrupados[chave] = {
                    'cnes': cnes,
                    'estabelecimento': row.get('NO_FANTASIA', 'NÃO CADASTRADO'),
                    'competencia': competencia,
                    'procedimentos': [],
                    'total_quantidade': 0,
                    'total_valor': 0.0
                }
            
            # Usar quantidade do PRD e valor do PA quando disponível
            quantidade = row.get('QUANTIDADE') or row.get('PRD_QT_A') or 0
            valor_unitario = row.get('VALOR_UNITARIO') or row.get('PRD_VL_A') or 0
            valor_total = row.get('VALOR_TOTAL') or (quantidade * valor_unitario)
            
            procedimento = {
                'codigo': row.get('PRD_PA', ''),
                'descricao': row.get('PA_DC', 'Descrição não disponível'),
                'digito_verificador': row.get('PA_DV', ''),
                'quantidade': quantidade,
                'valor_unitario': valor_unitario,
                'valor_total': valor_total
            }
            
            agrupados[chave]['procedimentos'].append(procedimento)
            agrupados[chave]['total_quantidade'] += quantidade
            agrupados[chave]['total_valor'] += valor_total
        
        return agrupados
    
    def agrupar_por_procedimento(self, dados: List[Dict]) -> Dict[str, Dict]:
        """
        Agrupa dados por procedimento de forma otimizada.
        
        Args:
            dados: Lista de dados brutos
            
        Returns:
            Dicionário com dados agrupados por procedimento
        """
        agrupados = {}
        
        for row in dados:
            procedimento = row.get('PRD_PA', '')
            descricao = row.get('PA_DC', 'Descrição não disponível')
            chave = f"{procedimento}_{descricao}"
            
            if chave not in agrupados:
                agrupados[chave] = {
                    'codigo': procedimento,
                    'descricao': descricao,
                    'estabelecimentos': [],
                    'total_quantidade': 0,
                    'total_valor': 0.0
                }
            
            quantidade = row.get('QUANTIDADE') or row.get('PRD_QT_A') or 0
            valor_total = row.get('VALOR_TOTAL') or 0.0
            
            estabelecimento = {
                'cnes': row.get('PRD_UID', ''),
                'nome': row.get('NO_FANTASIA', 'NÃO CADASTRADO'),
                'competencia': row.get('PRD_CMP', ''),
                'quantidade': quantidade,
                'valor_total': valor_total
            }
            
            agrupados[chave]['estabelecimentos'].append(estabelecimento)
            agrupados[chave]['total_quantidade'] += quantidade
            agrupados[chave]['total_valor'] += valor_total
        
        return agrupados
    
    def calcular_totais_gerais(self, dados_agrupados: Dict[str, Dict]) -> Dict[str, Any]:
        """
        Calcula totais gerais dos dados agrupados.
        
        Args:
            dados_agrupados: Dicionário com dados agrupados
            
        Returns:
            Dicionário com totais gerais
        """
        totais = {
            'total_quantidade_geral': 0,
            'total_valor_geral': 0.0,
            'total_estabelecimentos': 0,
            'total_competencias': 0,
            'total_procedimentos': 0
        }
        
        estabelecimentos_unicos = set()
        competencias_unicas = set()
        procedimentos_unicos = set()
        
        for chave, bloco in dados_agrupados.items():
            totais['total_quantidade_geral'] += bloco.get('total_quantidade', 0)
            totais['total_valor_geral'] += bloco.get('total_valor', 0.0)
            
            estabelecimentos_unicos.add(bloco.get('cnes', ''))
            competencias_unicas.add(bloco.get('competencia', ''))
            
            for proc in bloco.get('procedimentos', []):
                procedimentos_unicos.add(proc.get('codigo', ''))
        
        totais['total_estabelecimentos'] = len(estabelecimentos_unicos)
        totais['total_competencias'] = len(competencias_unicas)
        totais['total_procedimentos'] = len(procedimentos_unicos)
        
        return totais
    
    def formatar_competencia_extenso(self, competencia: str) -> str:
        """
        Formata competência para formato extenso (ex: Junho/2024).
        
        Args:
            competencia: Competência no formato AAAAMM
            
        Returns:
            Competência formatada
        """
        try:
            if len(competencia) == 6:
                ano = competencia[:4]
                mes = competencia[4:6]
                mes_extenso = Constants.MESES.get(mes, mes)
                return f"{mes_extenso}/{ano}"
        except Exception:
            pass
        return competencia
    
    def filtrar_procedimentos_zerados(self, dados_agrupados: Dict[str, Dict]) -> Dict[str, Dict]:
        """
        Remove procedimentos com quantidade zero.
        
        Args:
            dados_agrupados: Dados agrupados
            
        Returns:
            Dados filtrados
        """
        for chave, bloco in dados_agrupados.items():
            bloco['procedimentos'] = [
                proc for proc in bloco.get('procedimentos', []) 
                if proc.get('quantidade', 0) > 0
            ]
        
        return dados_agrupados
