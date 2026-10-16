from typing import Dict, List, Optional, Tuple

class QueryBuilder:
    """
    Construtor dinâmico e otimizado de queries para o sistema SIA/SUS.
    
    Características:
    - Queries parametrizadas para prevenir SQL injection
    - Otimização para uso de índices
    - Suporte a múltiplos tipos de agrupamento
    - Validação de parâmetros
    - Queries compatíveis com SQLite
    """
    
    # Constantes para nomes de tabelas e colunas
    TABELA_PRD = "tb_prd"
    TABELA_PA = "tb_pa"
    TABELA_ESTABELECIMENTO = "tb_estabelecimento"
    
    JOIN_ESTABELECIMENTO_NORMALIZADO = """
    LEFT JOIN tb_estabelecimento e
        ON p.PRD_UID = e.CO_CNES
    """
    
    # Mapeamento de agrupamentos
    AGRUPAMENTOS = {
        'estabelecimento_competencia': {
            'campos': ['p.PRD_UID', 'p.PRD_CMP'],
            'ordenacao': ['e.NO_FANTASIA', 'p.PRD_CMP']
        },
        'procedimento': {
            'campos': ['p.PRD_PA'],
            'ordenacao': ['total_valor DESC']
        },
        'competencia': {
            'campos': ['p.PRD_CMP'],
            'ordenacao': ['p.PRD_CMP DESC']
        }
    }
    
    @staticmethod
    def build_estabelecimentos_query(filtros: Optional[Dict] = None) -> Tuple[str, List]:
        """
        Constrói query otimizada para consulta de estabelecimentos.
        
        Args:
            filtros: Dicionário com filtros a serem aplicados
            
        Returns:
            Tupla (query, parametros)
        """
        base_query = """
            SELECT 
                CO_CNES,
                NO_FANTASIA,
                CO_CEP,
                DT_ATUALIZACAO,
                data_importacao
            FROM tb_estabelecimento
            WHERE 1=1
        """
        parametros = []
        
        if filtros:
            if filtros.get('nome'):
                base_query += " AND NO_FANTASIA LIKE ?"
                parametros.append(f"%{filtros['nome'].strip()}%")
            
            if filtros.get('cnes'):
                base_query += " AND CO_CNES = ?"
                parametros.append(filtros['cnes'].strip().zfill(7))
            
            if filtros.get('cep'):
                base_query += " AND CO_CEP LIKE ?"
                parametros.append(f"{filtros['cep'].strip()}%")
        
        base_query += " ORDER BY NO_FANTASIA"
        
        return base_query, parametros
    
    @staticmethod
    def build_procedimentos_query(filtros: Optional[Dict] = None) -> Tuple[str, List]:
        """
        Constrói query otimizada para consulta de procedimentos.
        
        Args:
            filtros: Dicionário com filtros a serem aplicados
            
        Returns:
            Tupla (query, parametros)
        """
        base_query = """
            SELECT 
                PA_ID,
                PA_DV,
                PA_DC,
                PA_TOTAL,
                PROC,
                data_importacao
            FROM tb_pa
            WHERE 1=1
        """
        parametros = []
        
        if filtros:
            # Filtro por código (com suporte a busca por prefixo)
            codigo = filtros.get('codigo', '').strip()
            if codigo:
                if filtros.get('busca_exata'):
                    base_query += " AND PA_ID = ?"
                    parametros.append(codigo)
                else:
                    base_query += " AND PA_ID LIKE ?"
                    parametros.append(f"{codigo}%")
            
            # Filtro por descrição
            descricao = filtros.get('descricao', '').strip()
            if descricao:
                base_query += " AND PA_DC LIKE ?"
                parametros.append(f"%{descricao}%")
            
            # Filtro por valor
            if filtros.get('valor_minimo') is not None:
                base_query += " AND PA_TOTAL >= ?"
                parametros.append(float(filtros['valor_minimo']))
            
            if filtros.get('valor_maximo') is not None:
                base_query += " AND PA_TOTAL <= ?"
                parametros.append(float(filtros['valor_maximo']))
        
        base_query += " ORDER BY PA_ID, PA_DV"
        
        return base_query, parametros
    
    @staticmethod
    def build_producao_query(filtros: Optional[Dict] = None, 
                           agrupamento: Optional[str] = None,
                           paginacao: Optional[Dict] = None) -> Tuple[str, List]:
        """
        Constrói query otimizada para dados de produção.
        
        Args:
            filtros: Dicionário com filtros a serem aplicados
            agrupamento: Tipo de agrupamento desejado
            paginacao: Configuração de paginação {limite, offset}
            
        Returns:
            Tupla (query, parametros)
        """
        if agrupamento and agrupamento not in QueryBuilder.AGRUPAMENTOS:
            raise ValueError(f"Agrupamento não suportado: {agrupamento}")

        # Definir campos base baseado no agrupamento
        if agrupamento:
            query = QueryBuilder._build_query_agrupada(filtros, agrupamento)
        else:
            query = QueryBuilder._build_query_detalhada(filtros)
        
        parametros = []
        
        # Aplicar filtros
        if filtros:
            query, parametros = QueryBuilder._aplicar_filtros_producao(query, filtros, parametros)
            
        # Aplicar agrupamento
        if agrupamento:
            query = QueryBuilder._aplicar_group_by(query, agrupamento)
        
        # Aplicar ordenação
        query = QueryBuilder._aplicar_ordenacao(query, agrupamento)
        
        # Aplicar paginação
        if paginacao:
            query = QueryBuilder._aplicar_paginacao(query, paginacao)
        
        return query, parametros
    
    @staticmethod
    def _aplicar_group_by(query: str, agrupamento: Optional[str] = None) -> str:
        """
        Aplica GROUP BY conforme o tipo de agrupamento.
        """
        if not agrupamento:
            return query

        if 'GROUP BY' in query.upper():
            return query

        if agrupamento == 'estabelecimento_competencia':
            return query + """
                GROUP BY p.PRD_UID, e.NO_FANTASIA, p.PRD_CMP
            """

        if agrupamento == 'procedimento':
            return query + """
                GROUP BY p.PRD_PA, pa.PA_DC, pa.PA_DV
            """

        if agrupamento == 'competencia':
            return query + """
                GROUP BY p.PRD_CMP
            """

        return query
    
    @staticmethod
    def _build_query_detalhada(filtros: Optional[Dict] = None) -> str:
        """
        Constrói query detalhada para produção.
        """
        return f"""
            SELECT
                p.PRD_UID,
                p.PRD_CMP,
                p.PRD_PA,
                p.PRD_QT_A,
                p.PRD_VL_A,
                COALESCE(pa.PA_TOTAL, 0) as VALOR_TABELA,
                (COALESCE(p.PRD_QT_A, 0) * COALESCE(pa.PA_TOTAL, 0)) as VALOR_TOTAL,
                COALESCE(NULLIF(e.NO_FANTASIA, ''), 'NÃO CADASTRADO') as NO_FANTASIA,
                pa.PA_DC,
                pa.PA_DV,
                p.arquivo_origem,
                p.data_importacao
            FROM {QueryBuilder.TABELA_PRD} p
            {QueryBuilder.JOIN_ESTABELECIMENTO_NORMALIZADO}
            LEFT JOIN {QueryBuilder.TABELA_PA} pa ON p.PRD_PA = pa.PROC
            WHERE 1=1
        """
    
    @staticmethod
    def _build_query_agrupada(filtros: Optional[Dict] = None, agrupamento: str = None) -> str:
        """
        Constrói query agrupada baseada no tipo de agrupamento.
        """
        if agrupamento == 'estabelecimento_competencia':
            return f"""
                SELECT
                    p.PRD_UID as cnes,
                    COALESCE(NULLIF(e.NO_FANTASIA, ''), 'NÃO CADASTRADO') as estabelecimento,
                    p.PRD_CMP as competencia,
                    COUNT(p.PRD_PA) as qtd_procedimentos,
                    SUM(p.PRD_QT_A) as total_quantidade,
                    SUM(COALESCE(p.PRD_QT_A, 0) * COALESCE(pa.PA_TOTAL, 0)) as total_valor,
                    MAX(p.data_importacao) as ultima_atualizacao
                FROM {QueryBuilder.TABELA_PRD} p
                {QueryBuilder.JOIN_ESTABELECIMENTO_NORMALIZADO}
                LEFT JOIN {QueryBuilder.TABELA_PA} pa ON p.PRD_PA = pa.PROC
                WHERE 1=1
            """
        
        elif agrupamento == 'procedimento':
            return f"""
                SELECT
                    p.PRD_PA as procedimento,
                    pa.PA_DC as descricao,
                    pa.PA_DV as digito_verificador,
                    COUNT(DISTINCT p.PRD_UID) as qtd_estabelecimentos,
                    COUNT(DISTINCT p.PRD_CMP) as qtd_competencias,
                    SUM(p.PRD_QT_A) as total_quantidade,
                    SUM(COALESCE(p.PRD_QT_A, 0) * COALESCE(pa.PA_TOTAL, 0)) as total_valor,
                    AVG(COALESCE(pa.PA_TOTAL, 0)) as valor_medio
                FROM {QueryBuilder.TABELA_PRD} p
                LEFT JOIN {QueryBuilder.TABELA_PA} pa ON p.PRD_PA = pa.PROC
                WHERE 1=1
            """
        
        elif agrupamento == 'competencia':
            return f"""
                SELECT
                    p.PRD_CMP as competencia,
                    COUNT(DISTINCT p.PRD_UID) as qtd_estabelecimentos,
                    COUNT(DISTINCT p.PRD_PA) as qtd_procedimentos,
                    SUM(p.PRD_QT_A) as total_quantidade,
                    SUM(COALESCE(p.PRD_QT_A, 0) * COALESCE(pa.PA_TOTAL, 0)) as total_valor
                FROM {QueryBuilder.TABELA_PRD} p
                LEFT JOIN {QueryBuilder.TABELA_PA} pa ON p.PRD_PA = pa.PROC
                WHERE 1=1
            """
        
        else:
            # Fallback para query detalhada
            return QueryBuilder._build_query_detalhada(filtros)
    
    @staticmethod
    def _aplicar_filtros_producao(query: str, filtros: Dict, parametros: List) -> Tuple[str, List]:
        """
        Aplica filtros à query de produção de forma otimizada.
        """
        # Filtro por lista de CNES
        if filtros.get('cnes_list'):
            cnes_list = QueryBuilder._normalizar_lista_cnes(filtros['cnes_list'])
            if cnes_list:
                placeholders = ','.join(['?'] * len(cnes_list))
                query += f" AND p.PRD_UID IN ({placeholders})"
                parametros.extend(cnes_list)
        
        # Filtro por lista de competências
        if filtros.get('competencia_list'):
            competencia_list = [str(c).strip() for c in filtros['competencia_list'] if str(c).strip()]
            if competencia_list:
                placeholders = ','.join(['?'] * len(competencia_list))
                query += f" AND p.PRD_CMP IN ({placeholders})"
                parametros.extend(competencia_list)
        
        # Filtro por lista de procedimentos
        if filtros.get('procedimento_list'):
            procedimento_list = [str(p).strip() for p in filtros['procedimento_list'] if str(p).strip()]
            if procedimento_list:
                placeholders = ','.join(['?'] * len(procedimento_list))
                query += f" AND p.PRD_PA IN ({placeholders})"
                parametros.extend(procedimento_list)
        
        # Filtro por intervalo de competência
        if filtros.get('competencia_inicio'):
            query += " AND p.PRD_CMP >= ?"
            parametros.append(filtros['competencia_inicio'].strip())
        
        if filtros.get('competencia_fim'):
            query += " AND p.PRD_CMP <= ?"
            parametros.append(filtros['competencia_fim'].strip())
        
        # Filtro por tipo de procedimento
        procedimento = str(filtros.get('procedimento') or filtros.get('codigo_procedimento') or '').strip()
        tipo = str(filtros.get('tipo_filtro_proc') or filtros.get('tipo_procedimento') or '').strip().lower()

        if procedimento:        
            if tipo == 'grupo' and len(procedimento) == 2:
                query += " AND SUBSTR(p.PRD_PA, 1, 2) = ?"
                parametros.append(procedimento)
            elif tipo == 'subgrupo' and len(procedimento) == 4:
                query += " AND SUBSTR(p.PRD_PA, 1, 4) = ?"
                parametros.append(procedimento)
            elif tipo == 'forma' and len(procedimento) == 6:
                query += " AND SUBSTR(p.PRD_PA, 1, 6) = ?"
                parametros.append(procedimento)
            elif tipo in ('grupo', 'subgrupo', 'forma'):
                query += " AND p.PRD_PA LIKE ?"
                parametros.append(f"{procedimento}%")

            else:
                query += " AND p.PRD_PA = ?"
                parametros.append(procedimento)
        # Filtro por valor total
        if filtros.get('valor_minimo') is not None:
            query += " AND (COALESCE(p.PRD_QT_A, 0) * COALESCE(pa.PA_TOTAL, 0)) >= ?"
            parametros.append(float(filtros['valor_minimo']))
        
        if filtros.get('valor_maximo') is not None:
            query += " AND (COALESCE(p.PRD_QT_A, 0) * COALESCE(pa.PA_TOTAL, 0)) <= ?"
            parametros.append(float(filtros['valor_maximo']))
        
        # Filtro para ocultar zerados
        if filtros.get('ocultar_zerados'):
            query += " AND p.PRD_QT_A > 0"
        
        return query, parametros
    
    @staticmethod
    def _aplicar_ordenacao(query: str, agrupamento: Optional[str] = None) -> str:
        """
        Aplica ordenação à query baseada no agrupamento.
        """
        if 'ORDER BY' in query.upper():
            return query
        
        if agrupamento:
            config = QueryBuilder.AGRUPAMENTOS.get(agrupamento, {})
            ordenacao = config.get('ordenacao', [])
            if ordenacao:
                query += f" ORDER BY {', '.join(ordenacao)}"
                return query
        
        # Ordenação padrão para queries detalhadas
        return query + " ORDER BY p.PRD_UID, p.PRD_CMP, p.PRD_PA"
    
    @staticmethod
    def _aplicar_paginacao(query: str, paginacao: Dict) -> str:
        """
        Aplica cláusulas de paginação à query.
        """
        limite = max(1, min(int(paginacao.get('limite', 50)), 10_000))
        offset = max(0, int(paginacao.get('offset', 0)))
        
        query += f" LIMIT {limite} OFFSET {offset}"
        return query
    
    @staticmethod
    def _normalizar_lista_cnes(cnes_list: List) -> List[str]:
        """
        Normaliza lista de CNES para formato padrão de 7 dígitos.
        """
        import re

        normalizados = []

        for cnes in cnes_list:
            if cnes is None:
                continue

            cnes_str = str(cnes).strip()

            if not cnes_str:
                continue

            if cnes_str.endswith('.0'):
                cnes_str = cnes_str[:-2]

            cnes_str = re.sub(r'\D', '', cnes_str)

            if cnes_str:
                normalizados.append(cnes_str.zfill(7))

        return normalizados
    
    @staticmethod
    def build_estatisticas_query() -> Tuple[str, List]:
        """
        Constrói query para estatísticas do sistema.
        
        Returns:
            Tupla (query, parametros)
        """
        query = f"""
            SELECT 
                (SELECT COUNT(*) FROM {QueryBuilder.TABELA_PRD}) as total_producao,
                (SELECT COUNT(DISTINCT PRD_UID) FROM {QueryBuilder.TABELA_PRD}) as total_estabelecimentos,
                (SELECT COUNT(DISTINCT PRD_CMP) FROM {QueryBuilder.TABELA_PRD}) as total_competencias,
                (SELECT COUNT(DISTINCT PRD_PA) FROM {QueryBuilder.TABELA_PRD}) as total_procedimentos,
                (SELECT SUM(PRD_QT_A) FROM {QueryBuilder.TABELA_PRD}) as total_quantidade,
                (SELECT SUM(COALESCE(p.PRD_QT_A, 0) * COALESCE(pa.PA_TOTAL, 0)) 
                 FROM {QueryBuilder.TABELA_PRD} p 
                 LEFT JOIN {QueryBuilder.TABELA_PA} pa ON p.PRD_PA = pa.PROC) as total_valor,
                (SELECT COUNT(*) FROM {QueryBuilder.TABELA_ESTABELECIMENTO}) as total_cadastros_estabelecimentos,
                (SELECT COUNT(*) FROM {QueryBuilder.TABELA_PA}) as total_cadastros_procedimentos,
                (SELECT MAX(PRD_CMP) FROM {QueryBuilder.TABELA_PRD}) as ultima_competencia,
                (SELECT MIN(PRD_CMP) FROM {QueryBuilder.TABELA_PRD}) as primeira_competencia
        """
        
        return query, []
    
    @staticmethod
    def build_competencia_query(filtros: Optional[Dict] = None) -> Tuple[str, List]:
        """
        Constrói query para obter competências disponíveis.
        
        Args:
            filtros: Filtros adicionais
            
        Returns:
            Tupla (query, parametros)
        """
        query = f"""
            SELECT DISTINCT PRD_CMP 
            FROM {QueryBuilder.TABELA_PRD} 
            WHERE 1=1
        """
        parametros = []
        
        if filtros:
            if filtros.get('cnes'):
                query += " AND PRD_UID = ?"
                parametros.append(filtros['cnes'].strip().zfill(7))
        
        query += " ORDER BY PRD_CMP DESC"
        
        return query, parametros
    
    @staticmethod
    def build_cnes_query(filtros: Optional[Dict] = None) -> Tuple[str, List]:
        """
        Constrói query para obter CNES disponíveis.
        
        Args:
            filtros: Filtros adicionais
            
        Returns:
            Tupla (query, parametros)
        """
        query = f"""
            SELECT DISTINCT 
                p.PRD_UID as cnes, 
                COALESCE(e.NO_FANTASIA, 'NÃO CADASTRADO') as nome_fantasia,
                COUNT(p.PRD_PA) as total_procedimentos,
                SUM(p.PRD_QT_A) as total_quantidade
            FROM {QueryBuilder.TABELA_PRD} p
            {QueryBuilder.JOIN_ESTABELECIMENTO_NORMALIZADO}
            WHERE 1=1
        """
        parametros = []
        
        if filtros:
            if filtros.get('competencia'):
                query += " AND p.PRD_CMP = ?"
                parametros.append(filtros['competencia'].strip())
            
            if filtros.get('nome'):
                query += " AND e.NO_FANTASIA LIKE ?"
                parametros.append(f"%{filtros['nome'].strip()}%")
        
        query += " GROUP BY p.PRD_UID ORDER BY nome_fantasia, p.PRD_UID"
        
        return query, parametros
    
    @staticmethod
    def build_export_query(filtros: Optional[Dict] = None, formato: str = 'csv') -> Tuple[str, List]:
        """
        Constrói query otimizada para exportação de dados.
        
        Args:
            filtros: Filtros a serem aplicados
            formato: Formato de exportação ('csv', 'excel')
            
        Returns:
            Tupla (query, parametros)
        """
        query = f"""
            SELECT
                p.PRD_UID as cnes,
                COALESCE(NULLIF(e.NO_FANTASIA, ''), 'NÃO CADASTRADO') as estabelecimento,
                p.PRD_CMP as competencia,
                p.PRD_PA as procedimento,
                p.PRD_TPFIN as tipo_financiamento,
                pa.PA_DC as descricao_procedimento,
                pa.PA_DV as digito_verificador,
                p.PRD_QT_A as quantidade,
                p.PRD_VL_A as valor_unitario_informado,
                pa.PA_TOTAL as valor_unitario_tabela,
                COALESCE(pa.PA_TOTAL, 0) as valor_unitario_calculado,
                (COALESCE(p.PRD_QT_A, 0) * COALESCE(pa.PA_TOTAL, 0)) as valor_total,
                p.arquivo_origem,
                p.data_importacao
            FROM {QueryBuilder.TABELA_PRD} p
            {QueryBuilder.JOIN_ESTABELECIMENTO_NORMALIZADO}
            LEFT JOIN {QueryBuilder.TABELA_PA} pa ON p.PRD_PA = pa.PROC
            WHERE 1=1
        """
        parametros = []
        
        if filtros:
            query, parametros = QueryBuilder._aplicar_filtros_producao(query, filtros, parametros)
        
        query += " ORDER BY p.PRD_UID, p.PRD_CMP, p.PRD_PA"
        
        return query, parametros
