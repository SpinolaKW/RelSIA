import logging
from typing import List, Optional, Dict, Any, Iterator, Tuple, Union
from sia_app.database.connection import DatabaseConnection

# Configuração de logging
logger = logging.getLogger(__name__)

class BaseModel:
    """Classe base para todos os modelos de dados."""
    
    # Constantes para configuração de bulk insert
    DEFAULT_BATCH_SIZE = 5000
    BULK_BATCH_SIZE = 20000
    
    def __init__(self, db: Optional[DatabaseConnection] = None):
        self.db = db or DatabaseConnection()
    
    def _row_to_dict(self, row) -> Optional[Dict[str, Any]]:
        """Converte uma linha SQLite para dicionário."""
        if not row:
            return None
        
        if hasattr(row, 'keys'):
            return {key: row[key] for key in row.keys()}
        else:
            # Fallback para tupla - assumindo que temos informações das colunas
            # Isso é menos ideal, mas funciona como fallback
            return {f'col_{i}': value for i, value in enumerate(row)}
    
    def _rows_to_dicts(self, rows) -> List[Dict[str, Any]]:
        """Converte múltiplas linhas SQLite para lista de dicionários."""
        return [self._row_to_dict(row) for row in rows] if rows else []
    
    def execute_query(self, query: str, params: Optional[Tuple] = None) -> int:
        """
        Executa uma query que não retorna resultados (INSERT, UPDATE, DELETE).
        
        Args:
            query: Query SQL a ser executada
            params: Parâmetros para a query
            
        Returns:
            Número de linhas afetadas
            
        Raises:
            Exception: Em caso de erro na execução
        """
        with self.db.txn() as cur:
            cur.execute(query, params or ())
            return cur.rowcount
    
    def fetch_all(self, query: str, params: Optional[Tuple] = None) -> List[Dict[str, Any]]:
        """
        Executa uma query e retorna todos os resultados como dicionários.
        
        Args:
            query: Query SQL a ser executada
            params: Parâmetros para a query
            
        Returns:
            Lista de dicionários com os resultados
        """
        with self.db.read() as cur:
            cur.execute(query, params or ())
            rows = cur.fetchall()
            return self._rows_to_dicts(rows)
    
    def fetch_one(self, query: str, params: Optional[Tuple] = None) -> Optional[Dict[str, Any]]:
        """
        Executa uma query e retorna um único resultado como dicionário.
        
        Args:
            query: Query SQL a ser executada
            params: Parâmetros para a query
            
        Returns:
            Dicionário com o resultado ou None se não encontrado
        """
        with self.db.read() as cur:
            cur.execute(query, params or ())
            row = cur.fetchone()
            return self._row_to_dict(row)
    
    def bulk_insert(
        self, 
        table: str, 
        columns: Tuple[str, ...], 
        rows_iterable: Iterator[Tuple], 
        index_drop_recreate: Optional[List[Tuple[str, str]]] = None,
        batch_size: int = BULK_BATCH_SIZE,
        conflict_action: str = "IGNORE"
    ) -> int:
        """
        Insere dados em lote com otimizações de performance.
        
        Args:
            table: Nome da tabela
            columns: Tupla com nomes das colunas
            rows_iterable: Iterável com tuplas de dados
            index_drop_recreate: Lista de índices para dropar e recriar
            batch_size: Tamanho do lote para inserção
            conflict_action: Ação em caso de conflito (IGNORE, REPLACE, etc.)
            
        Returns:
            Número total de linhas inseridas
        """
        total_rows = 0
        
        with self.db.txn(bulk=True) as cur:
            # Dropar índices caros antes do bulk (se existirem)
            if index_drop_recreate:
                for drop_sql, _ in index_drop_recreate:
                    try:
                        cur.execute(drop_sql)
                        logger.debug(f"Índice dropado: {drop_sql}")
                    except Exception as e:
                        logger.warning(f"Erro ao dropar índice {drop_sql}: {e}")
            
            # Preparar query de inserção
            cols = ",".join(columns)
            placeholders = ",".join(["?"] * len(columns))
            sql = f"INSERT OR {conflict_action} INTO {table} ({cols}) VALUES ({placeholders})"
            
            # Processar em lotes
            batch = []
            for row in rows_iterable:
                batch.append(row)
                if len(batch) >= batch_size:
                    cur.executemany(sql, batch)
                    total_rows += len(batch)
                    batch.clear()
                    logger.debug(f"Lote de {batch_size} linhas inserido")
            
            # Inserir restante
            if batch:
                cur.executemany(sql, batch)
                total_rows += len(batch)
                logger.debug(f"Lote final de {len(batch)} linhas inserido")
            
            # Recriar índices depois do bulk
            if index_drop_recreate:
                for _, create_sql in index_drop_recreate:
                    try:
                        cur.execute(create_sql)
                        logger.debug(f"Índice recriado: {create_sql}")
                    except Exception as e:
                        logger.error(f"Erro ao recriar índice {create_sql}: {e}")
                        raise
        
        logger.info(f"Bulk insert concluído: {total_rows} linhas inseridas em {table}")
        return total_rows


class ProdutoModel(BaseModel):
    """Model para operações com produtos (tb_prd)."""
    
    def inserir_lote(self, dados: List[Tuple]) -> int:
        """
        Insere/atualiza produtos em lote com UPSERT.
        
        Args:
            dados: Lista de tuplas (PRD_UID, PRD_CMP, PRD_PA, PRD_CBO, PRD_TPFIN, PRD_QT_P, PRD_QT_A, PRD_VL_P, PRD_VL_A, arquivo_origem)
            
        Returns:
            Número de linhas processadas
        """
        sql = """
            INSERT INTO tb_prd
                (PRD_UID, PRD_CMP, PRD_PA, PRD_CBO, PRD_TPFIN, PRD_CPX, PRD_QT_P, PRD_QT_A, PRD_VL_P, PRD_VL_A, arquivo_origem)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(PRD_UID, PRD_CMP, PRD_PA, PRD_CBO)
            DO UPDATE SET
                PRD_TPFIN = excluded.PRD_TPFIN,
                PRD_CPX = excluded.PRD_CPX,
                PRD_QT_P = excluded.PRD_QT_P,
                PRD_QT_A = excluded.PRD_QT_A,
                PRD_VL_P = excluded.PRD_VL_P,
                PRD_VL_A = excluded.PRD_VL_A,
                arquivo_origem = excluded.arquivo_origem,
                data_importacao = CURRENT_TIMESTAMP
            WHERE
                COALESCE(tb_prd.PRD_TPFIN, '') <> COALESCE(excluded.PRD_TPFIN, '')
                OR COALESCE(tb_prd.PRD_CPX, '') <> COALESCE(excluded.PRD_CPX, '')
                OR COALESCE(tb_prd.PRD_QT_P, 0) <> COALESCE(excluded.PRD_QT_P, 0)
                OR COALESCE(tb_prd.PRD_QT_A, 0) <> COALESCE(excluded.PRD_QT_A, 0)
                OR COALESCE(tb_prd.PRD_VL_P, 0) <> COALESCE(excluded.PRD_VL_P, 0)
                OR COALESCE(tb_prd.PRD_VL_A, 0) <> COALESCE(excluded.PRD_VL_A, 0)
        """
        total_rows = 0
        with self.db.txn(bulk=True) as cur:
            batch = []
            for row in dados:
                batch.append(row)
                if len(batch) >= self.DEFAULT_BATCH_SIZE:
                    cur.executemany(sql, batch)
                    total_rows += len(batch)
                    batch.clear()
            
            if batch:
                cur.executemany(sql, batch)
                total_rows += len(batch)
        
        logger.info(f"Inseridos/atualizados {total_rows} produtos")
        return total_rows
    
    def obter_por_filtros(
        self, 
        cnes_list: Optional[List[str]] = None, 
        competencia_list: Optional[List[str]] = None
    ) -> List[Dict[str, Any]]:
        """
        Obtém produtos filtrados por CNES e/ou competência.
        
        Args:
            cnes_list: Lista de CNES para filtrar
            competencia_list: Lista de competências para filtrar
            
        Returns:
            Lista de produtos com informações relacionadas
        """
        query = '''
            SELECT 
                p.*, 
                COALESCE(NULLIF(e.NO_FANTASIA, ''), 'NÃO CADASTRADO') AS NO_FANTASIA, 
                pa.PA_DC,
                (COALESCE(p.PRD_QT_A, 0) * COALESCE(pa.PA_TOTAL, 0)) as valor_total
            FROM tb_prd p
            LEFT JOIN tb_estabelecimento e
                ON p.PRD_UID = e.CO_CNES
            LEFT JOIN tb_pa pa ON p.PRD_PA = pa.PROC
            WHERE 1=1
        '''
        params = []
        
        if cnes_list:
            placeholders = ','.join(['?'] * len(cnes_list))
            query += f" AND p.PRD_UID IN ({placeholders})"
            params.extend(cnes_list)
        
        if competencia_list:
            placeholders = ','.join(['?'] * len(competencia_list))
            query += f" AND p.PRD_CMP IN ({placeholders})"
            params.extend(competencia_list)
        
        query += " ORDER BY p.PRD_UID, p.PRD_CMP, p.PRD_PA"
        
        return self.fetch_all(query, params)
    
    def obter_totais_por_filtros(
        self,
        cnes_list: Optional[List[str]] = None,
        competencia_list: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        Obtém totais agregados dos produtos filtrados.
        
        Args:
            cnes_list: Lista de CNES para filtrar
            competencia_list: Lista de competências para filtrar
            
        Returns:
            Dicionário com totais
        """
        query = '''
            SELECT 
                COUNT(*) as total_registros,
                SUM(PRD_QT_A) as total_quantidade,
                SUM(COALESCE(p.PRD_QT_A, 0) * COALESCE(pa.PA_TOTAL, 0)) as total_valor
            FROM tb_prd p
            LEFT JOIN tb_pa pa ON p.PRD_PA = pa.PROC
            WHERE 1=1
        '''
        params = []
        
        if cnes_list:
            placeholders = ','.join(['?'] * len(cnes_list))
            query += f" AND p.PRD_UID IN ({placeholders})"
            params.extend(cnes_list)
        
        if competencia_list:
            placeholders = ','.join(['?'] * len(competencia_list))
            query += f" AND p.PRD_CMP IN ({placeholders})"
            params.extend(competencia_list)
        
        result = self.fetch_one(query, params)
        return result or {}
        
    def _extrair_hash_arquivo(self, arquivo_origem: str) -> str:
        arquivo_origem = str(arquivo_origem or "").strip()

        if "|" in arquivo_origem:
            return arquivo_origem.split("|")[-1].strip()

        return arquivo_origem
        
    def arquivo_prd_ja_importado(self, arquivo_origem: str) -> bool:
        hash_arquivo = self._extrair_hash_arquivo(arquivo_origem)

        query = """
            SELECT 1
            FROM tb_importacao_prd
            WHERE hash_arquivo = ?
            LIMIT 1
        """

        with self.db.read() as cur:
            cur.execute(query, (hash_arquivo,))
            row = cur.fetchone()

        return row is not None
        
    def registrar_importacao_prd(self, arquivo_origem: str, competencia_principal: str, total_principal: int, total_retroativo: int) -> None:
        hash_arquivo = self._extrair_hash_arquivo(arquivo_origem)

        sql = """
            INSERT OR IGNORE INTO tb_importacao_prd
                (
                    arquivo_origem,
                    hash_arquivo,
                    competencia_principal,
                    total_principal,
                    total_retroativo
                )
            VALUES (?, ?, ?, ?, ?)
        """

        with self.db.txn() as cur:
            cur.execute(
                sql,
                (
                    arquivo_origem,
                    hash_arquivo,
                    competencia_principal,
                    total_principal,
                    total_retroativo
                )
            )
        
    def existem_diferencas_prd(self, dados: List[Tuple]) -> bool:
        """
        Verifica se os dados informados são diferentes do que já está no banco.

        Ordem esperada:
        (
            PRD_UID,
            PRD_CMP,
            PRD_PA,
            PRD_CBO,
            PRD_TPFIN,
            PRD_CPX,
            PRD_QT_P,
            PRD_QT_A,
            PRD_VL_P,
            PRD_VL_A,
            arquivo_origem
        )
        """

        if not dados:
            return False

        query = """
            SELECT
                PRD_TPFIN,
                PRD_CPX,
                PRD_QT_P,
                PRD_QT_A,
                PRD_VL_P,
                PRD_VL_A
            FROM tb_prd
            WHERE PRD_UID = ?
              AND PRD_CMP = ?
              AND PRD_PA = ?
              AND COALESCE(PRD_CBO, '') = ?
            LIMIT 1
        """

        with self.db.read() as cur:
            for row in dados:
                uid = str(row[0]).strip()
                cmp_ = str(row[1]).strip()
                pa = str(row[2]).strip()
                cbo = str(row[3] or "").strip()

                cur.execute(query, (uid, cmp_, pa, cbo))
                atual = cur.fetchone()

                if atual is None:
                    return True

                novo_tpfin = str(row[4] or "").strip()
                novo_cpx = str(row[5] or "").strip()
                novo_qt_p = float(row[6] or 0)
                novo_qt_a = float(row[7] or 0)
                novo_vl_p = float(row[8] or 0)
                novo_vl_a = float(row[9] or 0)

                if str(atual["PRD_TPFIN"] or "").strip() != novo_tpfin:
                    return True

                if str(atual["PRD_CPX"] or "").strip() != novo_cpx:
                    return True

                if float(atual["PRD_QT_P"] or 0) != novo_qt_p:
                    return True

                if float(atual["PRD_QT_A"] or 0) != novo_qt_a:
                    return True

                if float(atual["PRD_VL_P"] or 0) != novo_vl_p:
                    return True

                if float(atual["PRD_VL_A"] or 0) != novo_vl_a:
                    return True

        return False
        
    def sincronizar_retroativos_prd(self, competencia_origem: str, dados: List[Tuple]) -> int:
        """
        Sincroniza retroativos de uma competência principal.

        Exemplo:
        Arquivo principal 202502 trouxe retroativos de 202501.

        competencia_origem = 202502
        PRD_CMP dos dados = 202501

        O sistema:
        - calcula a diferença entre retroativo novo e retroativo já aplicado;
        - soma somente a diferença na tb_prd;
        - atualiza a tabela de controle.
        """

        competencia_origem = str(competencia_origem or "").strip()

        if not competencia_origem:
            return 0

        dados = dados or []

        def aplicar_delta(cur, row, delta_qt_p, delta_qt_a, delta_vl_p, delta_vl_a):
            sql_delta = """
                INSERT INTO tb_prd
                    (
                        PRD_UID,
                        PRD_CMP,
                        PRD_PA,
                        PRD_CBO,
                        PRD_TPFIN,
                        PRD_CPX,
                        PRD_QT_P,
                        PRD_QT_A,
                        PRD_VL_P,
                        PRD_VL_A,
                        arquivo_origem
                    )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(PRD_UID, PRD_CMP, PRD_PA, PRD_CBO)
                DO UPDATE SET
                    PRD_TPFIN = excluded.PRD_TPFIN,
                    PRD_CPX = excluded.PRD_CPX,
                    PRD_QT_P = COALESCE(tb_prd.PRD_QT_P, 0) + COALESCE(excluded.PRD_QT_P, 0),
                    PRD_QT_A = COALESCE(tb_prd.PRD_QT_A, 0) + COALESCE(excluded.PRD_QT_A, 0),
                    PRD_VL_P = COALESCE(tb_prd.PRD_VL_P, 0) + COALESCE(excluded.PRD_VL_P, 0),
                    PRD_VL_A = COALESCE(tb_prd.PRD_VL_A, 0) + COALESCE(excluded.PRD_VL_A, 0),
                    arquivo_origem = excluded.arquivo_origem,
                    data_importacao = CURRENT_TIMESTAMP
            """

            cur.execute(
                sql_delta,
                (
                    row[0],
                    row[1],
                    row[2],
                    row[3],
                    row[4],
                    row[5],
                    delta_qt_p,
                    delta_qt_a,
                    delta_vl_p,
                    delta_vl_a,
                    row[10],
                )
            )

        with self.db.txn(bulk=True) as cur:
            cur.execute("""
                SELECT *
                FROM tb_prd_retro_controle
                WHERE competencia_origem = ?
            """, (competencia_origem,))

            antigos = cur.fetchall()

            antigos_map = {
                (
                    str(r["PRD_UID"]).strip(),
                    str(r["PRD_CMP"]).strip(),
                    str(r["PRD_PA"]).strip(),
                    str(r["PRD_CBO"]).strip()
                ): r
                for r in antigos
            }

            novos_map = {
                (
                    str(row[0]).strip(),
                    str(row[1]).strip(),
                    str(row[2]).strip(),
                    str(row[3]).strip()
                ): row
                for row in dados
            }

            # 1. Aplica novos retroativos ou diferença dos retroativos atualizados
            for chave, row in novos_map.items():
                antigo = antigos_map.get(chave)

                novo_qt_p = float(row[6] or 0)
                novo_qt_a = float(row[7] or 0)
                novo_vl_p = float(row[8] or 0)
                novo_vl_a = float(row[9] or 0)

                if antigo:
                    antigo_qt_p = float(antigo["PRD_QT_P"] or 0)
                    antigo_qt_a = float(antigo["PRD_QT_A"] or 0)
                    antigo_vl_p = float(antigo["PRD_VL_P"] or 0)
                    antigo_vl_a = float(antigo["PRD_VL_A"] or 0)
                else:
                    antigo_qt_p = antigo_qt_a = antigo_vl_p = antigo_vl_a = 0

                delta_qt_p = novo_qt_p - antigo_qt_p
                delta_qt_a = novo_qt_a - antigo_qt_a
                delta_vl_p = novo_vl_p - antigo_vl_p
                delta_vl_a = novo_vl_a - antigo_vl_a

                if any([delta_qt_p, delta_qt_a, delta_vl_p, delta_vl_a]):
                    aplicar_delta(
                        cur,
                        row,
                        delta_qt_p,
                        delta_qt_a,
                        delta_vl_p,
                        delta_vl_a
                    )

                cur.execute("""
                    INSERT INTO tb_prd_retro_controle
                        (
                            competencia_origem,
                            PRD_UID,
                            PRD_CMP,
                            PRD_PA,
                            PRD_CBO,
                            PRD_TPFIN,
                            PRD_CPX,
                            PRD_QT_P,
                            PRD_QT_A,
                            PRD_VL_P,
                            PRD_VL_A,
                            arquivo_origem
                        )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(competencia_origem, PRD_UID, PRD_CMP, PRD_PA, PRD_CBO)
                    DO UPDATE SET
                        PRD_TPFIN = excluded.PRD_TPFIN,
                        PRD_CPX = excluded.PRD_CPX,
                        PRD_QT_P = excluded.PRD_QT_P,
                        PRD_QT_A = excluded.PRD_QT_A,
                        PRD_VL_P = excluded.PRD_VL_P,
                        PRD_VL_A = excluded.PRD_VL_A,
                        arquivo_origem = excluded.arquivo_origem,
                        data_importacao = CURRENT_TIMESTAMP
                """, (
                    competencia_origem,
                    row[0],
                    row[1],
                    row[2],
                    row[3],
                    row[4],
                    row[5],
                    row[6],
                    row[7],
                    row[8],
                    row[9],
                    row[10]
                ))

            # Registros ausentes são preservados: uma mesma competência pode
            # ser distribuída entre vários arquivos de origem.
        logger.info(
            f"Retroativos sincronizados para competência origem {competencia_origem}: {len(dados)} registro(s)"
        )

        return len(dados)
    
    def sincronizar_lote_prd(self, dados: List[Tuple], competencias: List[str]) -> int:
        """
        Sincroniza os dados PRD por competência.

        Regras:
        - Se não existe: insere.
        - Se existe e mudou: atualiza.
        - Se existe e está igual: não mexe.
        - Não exclui chaves ausentes, pois uma competência pode chegar em vários arquivos.
        """

        if not dados:
            return 0

        competencias = [str(c).strip() for c in competencias if str(c).strip()]
        if not competencias:
            return 0

        sql_upsert = """
            INSERT INTO tb_prd
                (PRD_UID, PRD_CMP, PRD_PA, PRD_CBO, PRD_TPFIN, PRD_CPX, PRD_QT_P, PRD_QT_A, PRD_VL_P, PRD_VL_A, arquivo_origem)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(PRD_UID, PRD_CMP, PRD_PA, PRD_CBO)
            DO UPDATE SET
                PRD_TPFIN = excluded.PRD_TPFIN,
                PRD_CPX = excluded.PRD_CPX,
                PRD_QT_P = excluded.PRD_QT_P,
                PRD_QT_A = excluded.PRD_QT_A,
                PRD_VL_P = excluded.PRD_VL_P,
                PRD_VL_A = excluded.PRD_VL_A,
                arquivo_origem = excluded.arquivo_origem,
                data_importacao = CURRENT_TIMESTAMP
            WHERE
                COALESCE(tb_prd.PRD_TPFIN, '') <> COALESCE(excluded.PRD_TPFIN, '')
                OR COALESCE(tb_prd.PRD_CPX, '') <> COALESCE(excluded.PRD_CPX, '')
                OR COALESCE(tb_prd.PRD_QT_P, 0) <> COALESCE(excluded.PRD_QT_P, 0)
                OR COALESCE(tb_prd.PRD_QT_A, 0) <> COALESCE(excluded.PRD_QT_A, 0)
                OR COALESCE(tb_prd.PRD_VL_P, 0) <> COALESCE(excluded.PRD_VL_P, 0)
                OR COALESCE(tb_prd.PRD_VL_A, 0) <> COALESCE(excluded.PRD_VL_A, 0)
        """

        with self.db.txn(bulk=True) as cur:
            cur.executemany(sql_upsert, dados)

        return len(dados)


class ProcedimentoModel(BaseModel):
    """Model para operações com procedimentos (tb_pa)."""
    
    def inserir_lote(self, dados: List[Tuple]) -> int:
        """
        Insere procedimentos em lote.
        
        Args:
            dados: Lista de tuplas (PA_ID, PA_DV, PA_DC, PA_TOTAL, arquivo_origem)
            
        Returns:
            Número de linhas inseridas
        """
        
        if not dados:
            return 0
        
        # O campo PROC é gerado automaticamente como PA_ID || COALESCE(PA_DV, '')
        sql = """
            INSERT INTO tb_pa
                (PA_ID, PA_DV, PA_DC, PA_TOTAL, PA_CTF, PA_CPX, arquivo_origem)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(PROC)
            DO UPDATE SET
                PA_DC = excluded.PA_DC,
                PA_TOTAL = excluded.PA_TOTAL,
                PA_CTF = excluded.PA_CTF,
                PA_CPX = excluded.PA_CPX,
                arquivo_origem = excluded.arquivo_origem,
                data_importacao = CURRENT_TIMESTAMP
        """
        
        total_rows = 0

        with self.db.txn(bulk=True) as cur:
            batch = []

            for row in dados:
                batch.append(row)

                if len(batch) >= self.DEFAULT_BATCH_SIZE:
                    cur.executemany(sql, batch)
                    total_rows += len(batch)
                    batch.clear()

            if batch:
                cur.executemany(sql, batch)
                total_rows += len(batch)

        logger.info(f"Inseridos/atualizados {total_rows} procedimentos")
        return total_rows
    
    def obter_por_codigo(self, codigo_procedimento: str) -> Optional[Dict[str, Any]]:
        """
        Obtém procedimento por código completo.
        
        Args:
            codigo_procedimento: Código do procedimento (PA_ID + PA_DV)
            
        Returns:
            Dicionário com dados do procedimento ou None
        """
        query = '''
            SELECT * FROM tb_pa 
            WHERE PROC = ?
        '''
        return self.fetch_one(query, (codigo_procedimento,))
    
    def obter_descricao_por_codigo(self, codigo_procedimento: str) -> Optional[str]:
        """
        Obtém a descrição de um procedimento pelo código.
        
        Args:
            codigo_procedimento: Código do procedimento
            
        Returns:
            Descrição do procedimento ou None
        """
        procedimento = self.obter_por_codigo(codigo_procedimento)
        return procedimento.get('PA_DC') if procedimento else None
    
    def obter_valor_por_codigo(self, codigo_procedimento: str) -> Optional[float]:
        """
        Obtém o valor unitário de um procedimento pelo código.
        
        Args:
            codigo_procedimento: Código do procedimento
            
        Returns:
            Valor do procedimento ou None
        """
        procedimento = self.obter_por_codigo(codigo_procedimento)
        return procedimento.get('PA_TOTAL') if procedimento else None
    
    def listar_grupos(self) -> List[Dict[str, Any]]:
        """Lista grupos de procedimentos (2 primeiros dígitos)."""
        query = '''
            SELECT 
                SUBSTR(PA_ID, 1, 2) as grupo, 
                COUNT(*) as total,
                AVG(PA_TOTAL) as valor_medio
            FROM tb_pa 
            WHERE LENGTH(PA_ID) >= 2
            GROUP BY grupo 
            ORDER BY grupo
        '''
        return self.fetch_all(query)
    
    def listar_subgrupos(self, grupo: str) -> List[Dict[str, Any]]:
        """
        Lista subgrupos de um grupo específico (4 primeiros dígitos).
        
        Args:
            grupo: Grupo (2 dígitos) para filtrar
            
        Returns:
            Lista de subgrupos
        """
        query = '''
            SELECT 
                SUBSTR(PA_ID, 1, 4) as subgrupo, 
                COUNT(*) as total,
                AVG(PA_TOTAL) as valor_medio
            FROM tb_pa 
            WHERE PA_ID LIKE ?
            GROUP BY subgrupo 
            ORDER BY subgrupo
        '''
        return self.fetch_all(query, (f"{grupo}%",))
    
    def buscar_por_descricao(self, descricao: str) -> List[Dict[str, Any]]:
        """
        Busca procedimentos por descrição.
        
        Args:
            descricao: Texto para buscar na descrição
            
        Returns:
            Lista de procedimentos encontrados
        """
        query = '''
            SELECT * FROM tb_pa 
            WHERE PA_DC LIKE ? 
            ORDER BY PA_ID, PA_DV
        '''
        return self.fetch_all(query, (f"%{descricao}%",))


class EstabelecimentoModel(BaseModel):
    """Model para operações com estabelecimentos (tb_estabelecimento)."""

    def inserir_lote(self, dados: List[Tuple]) -> int:
        """
        Insere/atualiza estabelecimentos mantendo apenas um registro por CO_CNES.
        
        Args:
            dados: Lista de tuplas (CO_CNES, NO_FANTASIA, CO_CEP, DT_ATUALIZACAO, arquivo_origem)
            
        Returns:
            Número de linhas processadas
        """
        if not dados:
            return 0

        sql = """
            INSERT INTO tb_estabelecimento
                (CO_CNES, NO_FANTASIA, CO_CEP, DT_ATUALIZACAO, arquivo_origem)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(CO_CNES)
            DO UPDATE SET
                NO_FANTASIA = excluded.NO_FANTASIA,
                CO_CEP = excluded.CO_CEP,
                DT_ATUALIZACAO = excluded.DT_ATUALIZACAO,
                arquivo_origem = excluded.arquivo_origem
        """

        total_rows = 0

        with self.db.txn(bulk=True) as cur:
            batch = []

            for row in dados:
                batch.append(row)

                if len(batch) >= self.DEFAULT_BATCH_SIZE:
                    cur.executemany(sql, batch)
                    total_rows += len(batch)
                    batch.clear()

            if batch:
                cur.executemany(sql, batch)
                total_rows += len(batch)

        logger.info(f"Inseridos/atualizados {total_rows} estabelecimentos")
        return total_rows
    
    def listar_todos(self) -> List[Dict[str, Any]]:
        """
        Lista todos os estabelecimentos.
        
        Returns:
            Lista de estabelecimentos ordenados por nome
        """
        query = "SELECT * FROM tb_estabelecimento ORDER BY NO_FANTASIA"
        return self.fetch_all(query)
    
    def obter_por_id(self, estabelecimento_id: int) -> Optional[Dict[str, Any]]:
        """
        Obtém estabelecimento por ID.
        
        Args:
            estabelecimento_id: ID do estabelecimento
            
        Returns:
            Dicionário com dados do estabelecimento ou None
        """
        query = "SELECT * FROM tb_estabelecimento WHERE id = ?"
        return self.fetch_one(query, (estabelecimento_id,))
    
    def obter_por_cnes(self, cnes: str) -> Optional[Dict[str, Any]]:
        """
        Obtém estabelecimento por CNES.
        
        Args:
            cnes: CNES do estabelecimento
            
        Returns:
            Dicionário com dados do estabelecimento ou None
        """
        query = "SELECT * FROM tb_estabelecimento WHERE CO_CNES = ?"
        return self.fetch_one(query, (cnes,))
    
    def buscar_por_nome(self, nome: str) -> List[Dict[str, Any]]:
        """
        Busca estabelecimentos por nome.
        
        Args:
            nome: Nome ou parte do nome para buscar
            
        Returns:
            Lista de estabelecimentos encontrados
        """
        query = '''
            SELECT * FROM tb_estabelecimento 
            WHERE NO_FANTASIA LIKE ? 
            ORDER BY NO_FANTASIA
        '''
        return self.fetch_all(query, (f"%{nome}%",))
    
    def excluir_por_id(self, estabelecimento_id: int) -> bool:
        """
        Exclui estabelecimento por ID.
        
        Args:
            estabelecimento_id: ID do estabelecimento a excluir
            
        Returns:
            True se excluído com sucesso, False caso contrário
        """
        try:
            rows_affected = self.execute_query(
                "DELETE FROM tb_estabelecimento WHERE id = ?", 
                (estabelecimento_id,)
            )
            success = rows_affected > 0
            if success:
                logger.info(f"Estabelecimento {estabelecimento_id} excluído com sucesso")
            else:
                logger.warning(f"Estabelecimento {estabelecimento_id} não encontrado para exclusão")
            return success
        except Exception as e:
            logger.error(f"Erro ao excluir estabelecimento {estabelecimento_id}: {e}")
            return False


class ConfigModel(BaseModel):
    """Model para operações com configurações do sistema (config_sistema)."""
    
    def obter_config(self) -> Dict[str, Any]:
        """
        Obtém configurações do sistema.
        
        Returns:
            Dicionário com todas as configurações
        """
        config = self.fetch_one("SELECT * FROM config_sistema WHERE id = 1")
        return config or {}
    
    def salvar_config(self, config_dict: Dict[str, Any]) -> bool:
        """
        Salva configurações do sistema.
        
        Args:
            config_dict: Dicionário com configurações a salvar
            
        Returns:
            True se salvo com sucesso, False caso contrário
        """
        try:
            query = '''
                UPDATE config_sistema
                SET logo_path = ?,
                    inst1 = ?,
                    inst2 = ?,
                    inst3 = ?,
                    ultimo_dir_arquivos = ?,
                    data_atualizacao = CURRENT_TIMESTAMP
                WHERE id = 1
            '''
            params = (
                config_dict.get('logo_path'),
                config_dict.get('inst1'),
                config_dict.get('inst2'), 
                config_dict.get('inst3'),
                config_dict.get('ultimo_dir_arquivos')
            )
            
            rows_affected = self.execute_query(query, params)
            if rows_affected == 0:
                logger.error("Registro principal de configuração não encontrado")
                return False
            logger.info("Configurações do sistema salvas com sucesso")
            return True
            
        except Exception as e:
            logger.error(f"Erro ao salvar configurações: {e}")
            return False
    
    def obter_config_individual(self, chave: str) -> Any:
        """
        Obtém um valor individual de configuração.
        
        Args:
            chave: Nome da coluna de configuração
            
        Returns:
            Valor da configuração ou None se não encontrado
        """
        config = self.obter_config()
        return config.get(chave)
