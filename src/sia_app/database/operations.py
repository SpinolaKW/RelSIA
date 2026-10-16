import sqlite3
import logging
import json
from pathlib import Path
from typing import Dict, Any, Tuple, List, Optional
from datetime import datetime
import csv
import os

from sia_app.database.connection import DatabaseConnection

# Configuração de logging
logger = logging.getLogger(__name__)

class DatabaseOperations:
    """
    Operações administrativas e de manutenção do banco de dados.
    
    Inclui:
    - Estatísticas e métricas do banco
    - Limpeza e manutenção de dados
    - Exportação de dados
    - Backup e recuperação
    """
    
    def __init__(
        self,
        db_path: Optional[str] = None,
        db_connection: Optional[DatabaseConnection] = None,
    ):
        """
        Inicializa as operações do banco de dados.
        
        Args:
            db_path: Caminho customizado para o banco de dados
        """
        if db_path and db_connection:
            raise ValueError("Informe db_path ou db_connection, não ambos")
        self.db = db_connection or DatabaseConnection(db_path)
    
    def get_database_stats(self) -> Dict[str, Any]:
        """
        Obtém estatísticas completas do banco de dados.
        
        Returns:
            Dicionário com estatísticas e métricas
        """
        stats = {}
        
        try:
            with self.db.read() as cur:
                # Contagem de registros por tabela
                tables = ['tb_prd', 'tb_pa', 'tb_estabelecimento']
                for table in tables:
                    cur.execute(f"SELECT COUNT(*) FROM {table}")
                    stats[f'total_{table}'] = cur.fetchone()[0]
                
                # Estatísticas detalhadas da tabela tb_prd
                cur.execute('''
                    SELECT 
                        COUNT(*) as total,
                        COUNT(DISTINCT PRD_UID) as cnes_unicos,
                        COUNT(DISTINCT PRD_CMP) as competencias,
                        COUNT(DISTINCT PRD_PA) as procedimentos_unicos,
                        SUM(PRD_QT_A) as total_quantidade,
                        SUM(COALESCE(p.PRD_QT_A, 0) * COALESCE(pa.PA_TOTAL, 0)) as total_valor,
                        AVG(pa.PA_TOTAL) as valor_medio
                    FROM tb_prd p
                    LEFT JOIN tb_pa pa ON p.PRD_PA = pa.PROC
                ''')
                prd_stats = cur.fetchone()
                stats['prd_detalhes'] = {
                    'cnes_unicos': prd_stats[1],
                    'competencias': prd_stats[2],
                    'procedimentos_unicos': prd_stats[3],
                    'total_quantidade': prd_stats[4],
                    'total_valor': prd_stats[5],
                    'valor_medio': round(prd_stats[6] or 0, 2)
                }
                
                # Estatísticas da tabela tb_pa
                cur.execute('''
                    SELECT 
                        COUNT(*) as total,
                        COUNT(DISTINCT PA_ID) as procedimentos_unicos,
                        AVG(PA_TOTAL) as valor_medio,
                        MIN(PA_TOTAL) as valor_minimo,
                        MAX(PA_TOTAL) as valor_maximo
                    FROM tb_pa
                ''')
                pa_stats = cur.fetchone()
                stats['pa_detalhes'] = {
                    'procedimentos_unicos': pa_stats[1],
                    'valor_medio': round(pa_stats[2] or 0, 2),
                    'valor_minimo': round(pa_stats[3] or 0, 2),
                    'valor_maximo': round(pa_stats[4] or 0, 2)
                }
                
                # Última atualização
                cur.execute('''
                    SELECT MAX(data_importacao) FROM (
                        SELECT data_importacao FROM tb_prd 
                        UNION ALL 
                        SELECT data_importacao FROM tb_pa
                        UNION ALL 
                        SELECT data_importacao FROM tb_estabelecimento
                    )
                ''')
                stats['ultima_atualizacao'] = cur.fetchone()[0]
                
                # Informações do schema
                cur.execute("SELECT COUNT(*) FROM sqlite_master WHERE type='table'")
                stats['total_tabelas'] = cur.fetchone()[0]
                
                cur.execute("SELECT COUNT(*) FROM sqlite_master WHERE type='index'")
                stats['total_indices'] = cur.fetchone()[0]
            
            # Tamanho do arquivo do banco
            db_path = Path(self.db.db_path)
            if db_path.exists():
                stats['tamanho_mb'] = round(db_path.stat().st_size / (1024 * 1024), 2)
                
                # Tamanho do WAL (se existir)
                wal_path = db_path.with_suffix('.db-wal')
                if wal_path.exists():
                    stats['tamanho_wal_mb'] = round(wal_path.stat().st_size / (1024 * 1024), 2)
            
            # Informações de performance
            stats['timestamp_consulta'] = datetime.now().isoformat()
            
            logger.info("Estatísticas do banco coletadas com sucesso")
            
        except Exception as e:
            logger.error(f"Erro ao coletar estatísticas do banco: {e}")
            stats['erro'] = str(e)
        
        return stats
    
    def limpar_banco(self, preservar_estabelecimentos_manuais: bool = True) -> Tuple[bool, str]:
        """
        Remove todos os dados do banco, com opções de preservação.
        
        Args:
            preservar_estabelecimentos_manuais: Se True, mantém registros manuais
            
        Returns:
            Tupla (sucesso, mensagem)
        """
        try:
            with self.db.txn() as cur:
                # Limpar tabelas na ordem correta (respeitando possíveis FKs)
                cur.execute("DELETE FROM tb_prd")
                logger.info("Tabela tb_prd limpa")

                cur.execute("DELETE FROM tb_prd_retro_controle")
                cur.execute("DELETE FROM tb_importacao_prd")
                
                cur.execute("DELETE FROM tb_pa")
                logger.info("Tabela tb_pa limpa")
                
                if preservar_estabelecimentos_manuais:
                    cur.execute("DELETE FROM tb_estabelecimento WHERE arquivo_origem != 'CADASTRO_MANUAL'")
                    logger.info("Tabela tb_estabelecimento limpa (exceto manuais)")
                else:
                    cur.execute("DELETE FROM tb_estabelecimento")
                    logger.info("Tabela tb_estabelecimento limpa completamente")
                
                # Resetar sequências AUTOINCREMENT (opcional)
                cur.execute("DELETE FROM sqlite_sequence WHERE name IN ('tb_prd', 'tb_pa', 'tb_estabelecimento')")
            
            return True, "Dados operacionais removidos; usuários preservados"
            
        except Exception as e:
            error_msg = f"Erro ao limpar banco: {e}"
            logger.error(error_msg)
            return False, error_msg
    
    def limpar_tabela_especifica(self, tabela: str, where_clause: Optional[str] = None) -> Tuple[bool, str]:
        """
        Limpa uma tabela específica com cláusula WHERE opcional.
        
        Args:
            tabela: Nome da tabela a ser limpa
            where_clause: Cláusula WHERE para filtro (sem a palavra WHERE)
            
        Returns:
            Tupla (sucesso, mensagem)
        """
        tabelas_permitidas = ['tb_prd', 'tb_pa', 'tb_estabelecimento']
        
        if tabela not in tabelas_permitidas:
            return False, f"Tabela {tabela} não permitida para limpeza"
        
        try:
            with self.db.txn() as cur:
                if where_clause:
                    sql = f"DELETE FROM {tabela} WHERE {where_clause}"
                else:
                    sql = f"DELETE FROM {tabela}"
                
                cur.execute(sql)
                linhas_afetadas = cur.rowcount
                
                logger.info(f"Tabela {tabela} limpa: {linhas_afetadas} linhas removidas")
                
                return True, f"Tabela {tabela} limpa: {linhas_afetadas} linhas removidas"
                
        except Exception as e:
            error_msg = f"Erro ao limpar tabela {tabela}: {e}"
            logger.error(error_msg)
            return False, error_msg
    
    def exportar_dados(self, tabela: str, formato: str = 'csv', arquivo_saida: Optional[str] = None) -> Tuple[bool, str]:
        """
        Exporta dados de uma tabela para formato específico.
        
        Args:
            tabela: Nome da tabela a exportar
            formato: Formato de exportação ('csv', 'json')
            arquivo_saida: Caminho do arquivo de saída (opcional)
            
        Returns:
            Tupla (sucesso, mensagem)
        """
        tabelas_permitidas = ['tb_prd', 'tb_pa', 'tb_estabelecimento', 'config_sistema']
        
        if tabela not in tabelas_permitidas:
            return False, f"Tabela {tabela} não permitida para exportação"
        
        if not arquivo_saida:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            arquivo_saida = f"export_{tabela}_{timestamp}.{formato}"
        
        try:
            # Obter dados
            with self.db.read() as cur:
                cur.execute(f"SELECT * FROM {tabela}")
                colunas = [desc[0] for desc in cur.description]
                dados = cur.fetchall()
            
            # Exportar conforme formato
            if formato.lower() == 'csv':
                self._exportar_csv(arquivo_saida, colunas, dados)
            elif formato.lower() == 'json':
                self._exportar_json(arquivo_saida, colunas, dados)
            else:
                return False, f"Formato {formato} não suportado"
            
            logger.info(f"Dados da tabela {tabela} exportados para {arquivo_saida}")
            return True, f"Dados exportados para {arquivo_saida}"
            
        except Exception as e:
            error_msg = f"Erro ao exportar dados: {e}"
            logger.error(error_msg)
            return False, error_msg
    
    def _exportar_csv(self, arquivo_saida: str, colunas: List[str], dados: List[tuple]) -> None:
        """
        Exporta dados para formato CSV.
        
        Args:
            arquivo_saida: Caminho do arquivo de saída
            colunas: Lista de nomes das colunas
            dados: Lista de tuplas com os dados
        """
        with open(arquivo_saida, 'w', newline='', encoding='utf-8') as csvfile:
            writer = csv.writer(csvfile, delimiter=';', quoting=csv.QUOTE_MINIMAL)
            
            # Escrever cabeçalho
            writer.writerow(colunas)
            
            # Escrever dados
            for linha in dados:
                writer.writerow(linha)
    
    def _exportar_json(self, arquivo_saida: str, colunas: List[str], dados: List[tuple]) -> None:
        """
        Exporta dados para formato JSON.
        
        Args:
            arquivo_saida: Caminho do arquivo de saída
            colunas: Lista de nomes das colunas
            dados: Lista de tuplas com os dados
        """
        dados_json = []
        
        for linha in dados:
            registro = {}
            for i, valor in enumerate(linha):
                # Converter datetime para string se necessário
                if isinstance(valor, datetime):
                    valor = valor.isoformat()
                registro[colunas[i]] = valor
            dados_json.append(registro)
        
        with open(arquivo_saida, 'w', encoding='utf-8') as jsonfile:
            json.dump(dados_json, jsonfile, ensure_ascii=False, indent=2)
    
    def otimizar_banco(self) -> Tuple[bool, str]:
        """
        Executa apenas PRAGMA optimize - a operação mais segura.
        """
        try:
            self.db.post_import_maintenance()
            logger.info("Checkpoint, ANALYZE e PRAGMA optimize executados")
            
            return True, "Otimização básica concluída com sucesso"
            
        except Exception as e:
            error_msg = f"Erro na otimização básica: {e}"
            logger.error(error_msg)
            
            # Se mesmo isso falhar, o banco está muito ocupado
            return False, "Não foi possível otimizar o banco no momento. Tente novamente quando o sistema estiver menos ocupado."
    
    def verificar_integridade(self) -> Tuple[bool, List[str]]:
        """
        Verifica a integridade do banco de dados.
        
        Returns:
            Tupla (sucesso, lista de mensagens)
        """
        mensagens = []
        
        try:
            with self.db.read() as cur:
                # Verificação de integridade do SQLite
                cur.execute("PRAGMA integrity_check")
                resultado = cur.fetchone()[0]
                
                if resultado == "ok":
                    mensagens.append("Integridade do banco: OK")
                else:
                    mensagens.append(f"Problemas de integridade: {resultado}")
                    return False, mensagens
                
                # Verificar foreign keys (se houver)
                cur.execute("PRAGMA foreign_key_check")
                fk_problems = cur.fetchall()
                
                if not fk_problems:
                    mensagens.append("Foreign keys: OK")
                else:
                    mensagens.append(f"Problemas com foreign keys: {len(fk_problems)}")
                    for problema in fk_problems:
                        mensagens.append(f"  - Tabela: {problema[0]}, Linha: {problema[1]}")
                    return False, mensagens
                
                # Verificar dados inconsistentes
                self._verificar_dados_consistentes(cur, mensagens)
            
            return True, mensagens
            
        except Exception as e:
            mensagens.append(f"Erro na verificação de integridade: {e}")
            return False, mensagens
    
    def _verificar_dados_consistentes(self, cursor: sqlite3.Cursor, mensagens: List[str]) -> None:
        """
        Verifica consistência dos dados entre tabelas.
        
        Args:
            cursor: Cursor da transação
            mensagens: Lista para acumular mensagens
        """
        # Verificar PRD_PA que não existem em tb_pa
        cursor.execute('''
            SELECT COUNT(DISTINCT PRD_PA) 
            FROM tb_prd 
            WHERE PRD_PA NOT IN (SELECT PROC FROM tb_pa)
        ''')
        pa_invalidos = cursor.fetchone()[0]
        
        if pa_invalidos > 0:
            mensagens.append(f"Procedimentos inválidos em tb_prd: {pa_invalidos}")
        else:
            mensagens.append("Consistência PRD_PA → tb_pa: OK")
        
        # Verificar PRD_UID que não existem em tb_estabelecimento
        cursor.execute('''
            SELECT COUNT(DISTINCT PRD_UID) 
            FROM tb_prd 
            WHERE PRD_UID NOT IN (SELECT CO_CNES FROM tb_estabelecimento)
        ''')
        cnes_invalidos = cursor.fetchone()[0]
        
        if cnes_invalidos > 0:
            mensagens.append(f"CNES inválidos em tb_prd: {cnes_invalidos}")
        else:
            mensagens.append("Consistência PRD_UID → tb_estabelecimento: OK")
