import pandas as pd
from dbfread import DBF
import chardet
import os
import numpy as np
from typing import Tuple, Optional, Dict, Any, List, Generator, Iterator
import logging
import time
from pathlib import Path
from contextlib import contextmanager

class DBFConverter:
    """
    Conversor otimizado de arquivos DBF para DataFrame com suporte a grandes volumes.
    
    Características:
    - Processamento em chunks para economia de memória
    - Detecção automática de encoding com cache
    - Otimizações de performance para diferentes tamanhos de arquivo
    - Tratamento robusto de erros e logging detalhado
    """
    
    # Constantes de configuração
    CHUNK_SIZE_SMALL = 5000
    CHUNK_SIZE_LARGE = 10000
    LARGE_FILE_THRESHOLD = 50 * 1024 * 1024  # 50MB
    VERY_LARGE_FILE_THRESHOLD = 100 * 1024 * 1024  # 100MB
    
    def __init__(self, logger: Optional[logging.Logger] = None):
        """
        Inicializa o conversor DBF.
        
        Args:
            logger: Instância de logger (opcional)
        """
        self.logger = logger or logging.getLogger(__name__)
        self.force_encoding: Optional[str] = None
        self._encoding_cache: Dict[str, str] = {}
        
        # Mapeamentos de colunas para padronização
        self._column_mappings = {
            'prd': {
                'UID': 'PRD_UID', 'CMP': 'PRD_CMP', 'PA': 'PRD_PA',
                'QT_A': 'PRD_QT_A', 'VL_A': 'PRD_VL_A', 'QUANTIDADE': 'PRD_QT_A',
                'VALOR': 'PRD_VL_A', 'QTD': 'PRD_QT_A'
            },
            'pa': {
                'ID': 'PA_ID', 'DV': 'PA_DV', 'DC': 'PA_DC', 
                'VALOR': 'PA_TOTAL', 'TOTAL': 'PA_TOTAL', 'PROC': 'PROC',
                'PROCEDIMENTO': 'PA_ID', 'DESCRICAO': 'PA_DC'
            },
            'estabelecimentos': {
                'CNES': 'CO_CNES', 'NOME': 'NO_FANTASIA', 'FANTASIA': 'NO_FANTASIA',
                'CEP': 'CO_CEP', 'ATUALIZACAO': 'DT_ATUALIZACAO'
            }
        }
        
        # Colunas obrigatórias por tipo
        self._required_columns = {
            'prd': ['PRD_UID', 'PRD_CMP', 'PRD_PA', 'PRD_QT_A', 'PRD_VL_A'],
            'pa': ['PA_ID', 'PA_DV', 'PA_DC', 'PA_TOTAL'],
            'estabelecimentos': ['CO_CNES', 'NO_FANTASIA']
        }
    
    def detect_encoding(self, file_path: str) -> str:
        """
        Detecta encoding do arquivo com cache.
        
        Args:
            file_path: Caminho do arquivo DBF
            
        Returns:
            Encoding detectado
        """
        if file_path in self._encoding_cache:
            return self._encoding_cache[file_path]
        
        try:
            file_size = os.path.getsize(file_path)
            sample_size = min(file_size, 100000)  # Aumentado para melhor detecção
            
            with open(file_path, 'rb') as f:
                raw_data = f.read(sample_size)
                result = chardet.detect(raw_data)
                encoding = result['encoding'] or 'latin-1'
                
                # Validações adicionais
                if encoding.lower() == 'ascii':
                    encoding = 'latin-1'  # ASCII é subconjunto do latin-1
                
                self._encoding_cache[file_path] = encoding
                self.logger.debug(f"Encoding detectado para {file_path}: {encoding}")
                return encoding
                
        except Exception as e:
            self.logger.warning(f"Erro na detecção de encoding: {e}, usando latin-1")
            return 'latin-1'
    
    def _clean_dbf_value(self, value: Any) -> Optional[str]:
        """
        Limpa e converte valores do DBF de forma otimizada.
        
        Args:
            value: Valor original do DBF
            
        Returns:
            Valor limpo ou None
        """
        if value is None:
            return None
        
        # Converter bytes para string
        if isinstance(value, bytes):
            try:
                value = value.decode('latin-1')
            except UnicodeDecodeError:
                try:
                    value = value.decode('utf-8', errors='ignore')
                except:
                    value = str(value)
        
        # Processar strings
        if isinstance(value, str):
            value = value.strip()
            if not value or value.isspace():
                return None
            
            # Substituir valores comuns vazios
            if value in ('', 'None', 'null', 'NULL', 'nan', 'NaN', 'NaT'):
                return None
        
        return value
    
    @contextmanager
    def _dbf_reader(self, file_path: str):
        """
        Context manager para leitura segura de DBF.
        
        Args:
            file_path: Caminho do arquivo DBF
        """
        encoding = self.force_encoding or self.detect_encoding(file_path)
        dbf = None
        
        try:
            dbf = DBF(
                file_path, 
                encoding=encoding, 
                char_decode_errors='ignore',
                load=False  # Não carregar tudo na memória
            )
            yield dbf
        except Exception as e:
            self.logger.error(f"Erro ao abrir DBF {file_path}: {e}")
            raise
        finally:
            if dbf:
                try:
                    dbf.close()
                except:
                    pass
    
    def dbf_to_dataframe(self, file_path: str, table_type: str) -> Tuple[bool, pd.DataFrame, str]:
        """
        Converte arquivo DBF para DataFrame.
        """
        try:
            self.logger.info(f"Convertendo DBF: {file_path}")
            
            # USAR dbfread que é mais estável
            from dbfread import DBF
            
            table = DBF(file_path, encoding='latin-1')
            df = pd.DataFrame(list(table))
            
            if df.empty:
                return False, pd.DataFrame(), "DataFrame vazio"
            
            # Renomear colunas baseado no tipo
            if table_type == 'prd':
                expected_columns = ['PRD_UID', 'PRD_CMP', 'PRD_PA', 'PRD_QT_A', 'PRD_VL_A']
                mapping = {
                    'UID': 'PRD_UID', 'CMP': 'PRD_CMP', 'PA': 'PRD_PA',
                    'QT_A': 'PRD_QT_A', 'VL_A': 'PRD_VL_A'
                }
            elif table_type == 'pa':
                expected_columns = ['PA_ID', 'PA_DV', 'PA_DC', 'PA_TOTAL']
                mapping = {
                    'ID': 'PA_ID', 'DV': 'PA_DV', 'DC': 'PA_DC', 'TOTAL': 'PA_TOTAL'
                }
            else:
                return False, pd.DataFrame(), f"Tipo de tabela desconhecido: {table_type}"
            
            df = df.rename(columns=mapping)
            
            # Verificar colunas obrigatórias
            missing_columns = [col for col in expected_columns if col not in df.columns]
            if missing_columns:
                return False, pd.DataFrame(), f"Colunas faltando: {missing_columns}"
            
            return True, df, f"DBF convertido: {len(df)} registros"
            
        except Exception as e:
            return False, pd.DataFrame(), f"Erro ao converter DBF: {str(e)}"
    
    def _process_small_file(self, file_path: str, table_type: str, 
                          optimize: bool) -> Tuple[bool, Optional[pd.DataFrame], str]:
        """Processa arquivos pequenos em memória."""
        start_time = time.time()
        
        try:
            with self._dbf_reader(file_path) as dbf:
                # Processar todos os registros de uma vez
                records = []
                for record in dbf:
                    cleaned_record = {}
                    for key, value in record.items():
                        cleaned_record[key] = self._clean_dbf_value(value)
                    records.append(cleaned_record)
                
                if not records:
                    return False, None, "Nenhum registro válido encontrado"
                
                df = pd.DataFrame(records)
                total_records = len(df)
                
                # Aplicar processamento específico
                df = self._process_dataframe(df, table_type)
                
                if optimize:
                    df = self._optimize_dataframe(df, table_type)
                
                processing_time = time.time() - start_time
                msg = f"Conversão concluída: {total_records} registros em {processing_time:.2f}s"
                self.logger.info(msg)
                
                return True, df, msg
                
        except Exception as e:
            error_msg = f"Erro no processamento de arquivo pequeno: {e}"
            self.logger.error(error_msg)
            return False, None, error_msg
    
    def _process_large_file(self, file_path: str, table_type: str,
                          optimize: bool, chunk_size: int = None) -> Tuple[bool, Optional[pd.DataFrame], str]:
        """Processa arquivos grandes em chunks."""
        if chunk_size is None:
            chunk_size = self.CHUNK_SIZE_LARGE
        
        start_time = time.time()
        total_records = 0
        
        try:
            with self._dbf_reader(file_path) as dbf:
                chunks = []
                final_df = None
                
                for i, record in enumerate(dbf):
                    # Processar registro
                    cleaned_record = {}
                    for key, value in record.items():
                        cleaned_record[key] = self._clean_dbf_value(value)
                    chunks.append(cleaned_record)
                    
                    # Processar chunk quando atingir o tamanho
                    if len(chunks) >= chunk_size:
                        chunk_df = self._process_chunk(chunks, table_type, optimize)
                        
                        if final_df is None:
                            final_df = chunk_df
                        else:
                            final_df = pd.concat([final_df, chunk_df], ignore_index=True)
                        
                        total_records += len(chunks)
                        chunks = []
                        
                        # Log de progresso a cada 10 chunks
                        if (i + 1) % (chunk_size * 10) == 0:
                            self.logger.info(f"Progresso: {i + 1} registros processados")
                
                # Processar chunk final
                if chunks:
                    chunk_df = self._process_chunk(chunks, table_type, optimize)
                    if final_df is None:
                        final_df = chunk_df
                    else:
                        final_df = pd.concat([final_df, chunk_df], ignore_index=True)
                    total_records += len(chunks)
                
                if final_df is None:
                    return False, None, "Nenhum registro processado"
                
                processing_time = time.time() - start_time
                msg = f"Conversão em chunks concluída: {total_records} registros em {processing_time:.2f}s"
                self.logger.info(msg)
                
                return True, final_df, msg
                
        except Exception as e:
            error_msg = f"Erro no processamento de arquivo grande: {e}"
            self.logger.error(error_msg)
            return False, None, error_msg
    
    def _process_chunk(self, chunks: List[Dict], table_type: str, 
                      optimize: bool) -> pd.DataFrame:
        """Processa um chunk de dados."""
        if not chunks:
            return pd.DataFrame()
        
        df = pd.DataFrame(chunks)
        df = self._process_dataframe(df, table_type)
        
        if optimize:
            df = self._optimize_dataframe(df, table_type)
        
        return df
    
    def _process_dataframe(self, df: pd.DataFrame, table_type: str) -> pd.DataFrame:
        """
        Aplica mapeamento de colunas e validações.
        
        Args:
            df: DataFrame original
            table_type: Tipo de tabela
            
        Returns:
            DataFrame processado
        """
        if table_type not in self._column_mappings:
            return df
        
        # Aplicar mapeamento de colunas
        mapping = self._column_mappings[table_type]
        rename_dict = {}
        
        for old_col, new_col in mapping.items():
            if old_col in df.columns:
                rename_dict[old_col] = new_col
        
        if rename_dict:
            df = df.rename(columns=rename_dict)
        
        # Garantir colunas obrigatórias
        required_cols = self._required_columns.get(table_type, [])
        for col in required_cols:
            if col not in df.columns:
                df[col] = None
        
        # Selecionar apenas colunas relevantes
        relevant_cols = [col for col in df.columns if col in required_cols or any(col.startswith(prefix) for prefix in ['PRD_', 'PA_', 'CO_'])]
        if relevant_cols:
            df = df[relevant_cols]
        
        return df
    
    def _optimize_dataframe(self, df: pd.DataFrame, table_type: str) -> pd.DataFrame:
        """
        Otimiza o DataFrame para reduzir uso de memória.
        
        Args:
            df: DataFrame a ser otimizado
            table_type: Tipo de tabela
            
        Returns:
            DataFrame otimizado
        """
        if df.empty:
            return df
        
        # Converter colunas numéricas
        numeric_patterns = ['VL_', 'QT_', 'TOTAL', 'QUANTIDADE', 'VALOR']
        numeric_cols = [col for col in df.columns if any(pattern in col for pattern in numeric_patterns)]
        
        for col in numeric_cols:
            if col in df.columns and df[col].dtype == 'object':
                df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
        
        # Otimizar tipos de dados
        for col in df.columns:
            if df[col].dtype == 'object':
                # Converter para categoria se tiver poucos valores únicos
                unique_ratio = df[col].nunique() / len(df)
                if unique_ratio < 0.5:  # 50% threshold
                    df[col] = df[col].astype('category')
            
            # Downcast numérico
            elif pd.api.types.is_numeric_dtype(df[col]):
                if pd.api.types.is_integer_dtype(df[col]):
                    df[col] = pd.to_numeric(df[col], downcast='integer')
                else:
                    df[col] = pd.to_numeric(df[col], downcast='float')
        
        return df
    
    def read_dbf_chunked(self, file_path: str, table_type: str, 
                        chunk_size: int = 10000,
                        optimize: bool = True) -> Generator[pd.DataFrame, None, None]:
        """
        Lê DBF em chunks (generator) para processamento sequencial.
        
        Args:
            file_path: Caminho do arquivo DBF
            table_type: Tipo de tabela
            chunk_size: Tamanho do chunk
            optimize: Se deve otimizar os chunks
            
        Yields:
            DataFrames com chunks de dados
        """
        try:
            with self._dbf_reader(file_path) as dbf:
                chunks = []
                
                for record in dbf:
                    cleaned_record = {}
                    for key, value in record.items():
                        cleaned_record[key] = self._clean_dbf_value(value)
                    chunks.append(cleaned_record)
                    
                    if len(chunks) >= chunk_size:
                        yield self._process_chunk(chunks, table_type, optimize)
                        chunks = []
                
                # Yield do chunk final
                if chunks:
                    yield self._process_chunk(chunks, table_type, optimize)
                    
        except Exception as e:
            self.logger.error(f"Erro na leitura em chunks: {e}")
            raise
    
    def batch_convert(self, file_paths: List[str], table_type: str,
                     output_dir: Optional[str] = None,
                     optimize: bool = True) -> Dict[str, Any]:
        """
        Converte múltiplos arquivos em lote.
        
        Args:
            file_paths: Lista de caminhos de arquivos
            table_type: Tipo de tabela
            output_dir: Diretório para salvar resultados (opcional)
            optimize: Se deve otimizar os DataFrames
            
        Returns:
            Dicionário com resultados do processamento
        """
        results = {
            'successful': [],
            'failed': [],
            'total_files': len(file_paths),
            'total_records': 0,
            'total_time': 0
        }
        
        start_time = time.time()
        
        for i, file_path in enumerate(file_paths):
            self.logger.info(f"Processando {i+1}/{len(file_paths)}: {file_path}")
            file_start = time.time()
            
            try:
                success, df, message = self.dbf_to_dataframe(file_path, table_type, optimize)
                
                if success:
                    file_result = {
                        'file': file_path,
                        'records': len(df),
                        'processing_time': time.time() - file_start,
                        'file_size_mb': os.path.getsize(file_path) / (1024 * 1024)
                    }
                    
                    # Salvar se output_dir especificado
                    if output_dir and df is not None:
                        output_path = os.path.join(output_dir, f"{Path(file_path).stem}.parquet")
                        df.to_parquet(output_path, index=False)
                        file_result['output_path'] = output_path
                    
                    results['successful'].append(file_result)
                    results['total_records'] += len(df)
                else:
                    results['failed'].append({
                        'file': file_path,
                        'error': message,
                        'processing_time': time.time() - file_start
                    })
                    
            except Exception as e:
                error_msg = f"Erro inesperado: {e}"
                self.logger.error(f"Falha em {file_path}: {error_msg}")
                results['failed'].append({
                    'file': file_path,
                    'error': error_msg,
                    'processing_time': time.time() - file_start
                })
        
        results['total_time'] = time.time() - start_time
        self.logger.info(f"Processamento em lote concluído: {len(results['successful'])} sucessos, {len(results['failed'])} falhas")
        
        return results
    
    def get_file_info(self, file_path: str) -> Dict[str, Any]:
        """
        Obtém informações detalhadas do arquivo DBF.
        
        Args:
            file_path: Caminho do arquivo DBF
            
        Returns:
            Dicionário com informações
        """
        try:
            with self._dbf_reader(file_path) as dbf:
                file_info = {
                    'file_path': file_path,
                    'file_size': os.path.getsize(file_path),
                    'file_size_mb': round(os.path.getsize(file_path) / (1024 * 1024), 2),
                    'record_count': len(dbf),
                    'encoding': self.force_encoding or self.detect_encoding(file_path),
                    'fields': [{'name': field.name, 'type': field.type, 'length': field.length} 
                              for field in dbf.fields],
                    'field_count': len(dbf.fields),
                    'recommended_method': 'chunked' if os.path.getsize(file_path) > self.LARGE_FILE_THRESHOLD else 'normal'
                }
                
                return file_info
                
        except Exception as e:
            self.logger.error(f"Erro ao obter informações de {file_path}: {e}")
            return {'error': str(e), 'file_path': file_path}