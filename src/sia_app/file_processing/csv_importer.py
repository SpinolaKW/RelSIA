import pandas as pd
import logging
import numpy as np
from typing import Tuple, List, Iterator, Optional, Dict, Any
from pathlib import Path
from sia_app.database.connection import DatabaseConnection
from sia_app.database.models import EstabelecimentoModel, ProcedimentoModel, ProdutoModel
from sia_app.utils.sia_mappings import (
    normalizar_cbo,
    normalizar_codigo_financiamento,
    normalizar_complexidade,
)

class CSVImporter:
    """
    Importador otimizado para dados CSV com suporte a grandes volumes.
    
    Características:
    - Processamento em lote com tamanhos otimizados
    - Tipagem de dados adequada para performance
    - Fallback para diferentes engines de leitura
    - Tratamento robusto de erros
    - Logging detalhado do processo
    """
    
    # Constantes de configuração
    DEFAULT_BATCH_SIZE = 10000
    CHUNK_SIZE = 50000  # Para arquivos muito grandes
    
    def __init__(
        self,
        logger: Optional[logging.Logger] = None,
        db: Optional[DatabaseConnection] = None,
    ):
        """
        Inicializa o importador CSV.
        
        Args:
            logger: Instância de logger (opcional)
        """
        self.logger = logger or logging.getLogger(__name__)
        self.produto_model = ProdutoModel(db)
        self.estabelecimento_model = EstabelecimentoModel(db)
        self.procedimento_model = ProcedimentoModel(db)
        
        # Mapeamento de colunas para padronização
        self.column_mappings = {
            'estabelecimentos': {
                'CNES': 'CO_CNES',
                'CO_CNES': 'CO_CNES',
                'COD_CNES': 'CO_CNES',
                'CODIGO_CNES': 'CO_CNES',

                'NOME': 'NO_FANTASIA',
                'NO_FANTASIA': 'NO_FANTASIA',
                'NOME_FANTASIA': 'NO_FANTASIA',
                'FANTASIA': 'NO_FANTASIA',

                'RAZAO_SOCIAL': 'RAZAO_SOCIAL',
                'NO_RAZAO_SOCIAL': 'RAZAO_SOCIAL',

                'CEP': 'CO_CEP',
                'CO_CEP': 'CO_CEP',

                'ATUALIZACAO': 'DT_ATUALIZACAO',
                'DT_ATUALIZACAO': 'DT_ATUALIZACAO'
            },
            'prd': {
                'UID': 'PRD_UID',
                'CMP': 'PRD_CMP',
                'PA': 'PRD_PA',
                'QT_P': 'PRD_QT_P',
                'QT_A': 'PRD_QT_A',
                'VL_P': 'PRD_VL_P',
                'VL_A': 'PRD_VL_A',
                'QUANTIDADE': 'PRD_QT_A',
                'VALOR': 'PRD_VL_A'
            },
            'pa': {
                'ID': 'PA_ID',
                'DV': 'PA_DV',
                'DC': 'PA_DC',
                'TOTAL': 'PA_TOTAL',
                'PROCEDIMENTO': 'PA_ID',
                'DESCRICAO': 'PA_DC',
                'VALOR_TOTAL': 'PA_TOTAL'
            }
        }
        
    def _coerce_to_dataframe(self, data_or_path, dtype: Optional[Dict[str, Any]], table_type: str) -> pd.DataFrame:
        """
        
        Aceita DataFrame ou caminho de arquivo e retorna um DataFrame padronizado.
        
        """
        if isinstance(data_or_path, pd.DataFrame):
            df = data_or_path.copy()
            # aplica dtypes básicos quando possível
            if dtype:
                for col, t in dtype.items():
                    if col in df.columns:
                        try:
                            df[col] = df[col].astype(t)
                        except Exception:
                            pass
        else:
            df = self._read_dataframe(str(data_or_path), dtype=dtype)
        return self._standardize_dataframe(df, table_type)
    
    def _detect_file_encoding(self, file_path: str) -> str:
        """
        Detecta a codificação do arquivo CSV.
        
        Args:
            file_path: Caminho do arquivo
            
        Returns:
            Codificação detectada
        """
        encodings = ['utf-8', 'latin-1', 'iso-8859-1', 'cp1252']
        
        for encoding in encodings:
            try:
                with open(file_path, 'r', encoding=encoding) as f:
                    f.read(1024)  # Lê apenas os primeiros bytes
                return encoding
            except UnicodeDecodeError:
                continue
        
        self.logger.warning(f"Não foi possível detectar encoding para {file_path}, usando utf-8")
        return 'utf-8'
    
    def _read_dataframe(self, file_path: str, dtype: Dict[str, Any] = None) -> pd.DataFrame:
        """
        Lê arquivo CSV com fallback para diferentes engines.
        """
        encoding = self._detect_file_encoding(file_path)
        dtype = dtype or {}
        
        # Tentar diferentes engines em ordem de preferência
        #engines = ['pyarrow', 'c', 'python']
        
        # Tentar diferentes engines em ordem de preferência.
        # Quando houver dtype, evitar pyarrow primeiro para não perder zeros à esquerda.
        if dtype:
            engines = ['c', 'python']
        else:
            engines = ['pyarrow', 'c', 'python']
        
        for engine in engines:
            try:
                if engine == 'pyarrow':
                    # PyArrow tem parâmetros diferentes
                    df = pd.read_csv(
                        file_path, 
                        encoding=encoding, 
                        sep=';', 
                        dtype_backend='pyarrow',  # Parâmetro correto para PyArrow
                        engine='pyarrow'
                    )
                else:
                    df = pd.read_csv(
                        file_path, 
                        encoding=encoding, 
                        sep=';', 
                        dtype=dtype,
                        engine=engine,
                        na_filter=False,
                        keep_default_na=False,
                        quoting=0
                    )
                
                self.logger.info(f"Arquivo {file_path} lido com engine: {engine}")
                return df
                
            except ImportError:
                self.logger.warning(f"Engine {engine} não disponível")
                continue
            except Exception as e:
                self.logger.warning(f"Falha com engine {engine}: {e}")
                continue
        
        # Fallback final
        self.logger.warning("Tentando fallback com separador automático")
        try:
            df = pd.read_csv(file_path, encoding=encoding, sep=None, engine='python')
            self.logger.info("Arquivo lido com separador automático")
            return df
        except Exception as e:
            raise Exception(f"Não foi possível ler o arquivo {file_path}: {e}")
    
    def _standardize_dataframe(self, df: pd.DataFrame, table_type: str) -> pd.DataFrame:
        """
        Padroniza nomes de colunas e tipos de dados.
        
        Args:
            df: DataFrame a ser padronizado
            table_type: Tipo de tabela ('estabelecimentos', 'prd', 'pa')
            
        Returns:
            DataFrame padronizado
        """
        # Renomear colunas conforme mapeamento
        column_map = self.column_mappings.get(table_type, {})
        df = df.rename(columns=column_map)
        
        # Converter tipos de dados específicos
        if table_type == 'prd':
            # Converter colunas numéricas
            numeric_columns = ['PRD_QT_A', 'PRD_VL_A']
            for col in numeric_columns:
                if col in df.columns:
                    df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
        
        elif table_type == 'pa':
            # Converter coluna de valor
            if 'PA_TOTAL' in df.columns:
                df['PA_TOTAL'] = pd.to_numeric(df['PA_TOTAL'], errors='coerce').fillna(0)
        
        # Remover linhas completamente vazias
        df = df.dropna(how='all')
        
        return df
    
    def importar_estabelecimentos(self, file_path: str, arquivo_origem: str) -> Tuple[bool, str]:
        """
        Importa dados de estabelecimentos do CSV com fallback.
        """
        try:
            # Tentar método principal primeiro
            self.logger.info(f"🔄 Tentando método principal para: {file_path}")
            result = self._importar_estabelecimentos_principal(file_path, arquivo_origem)
            return result
            
        except Exception as e:
            self.logger.warning(f"❌ Método principal falhou: {e}")
            self.logger.info("🔄 Tentando método alternativo...")
            
            # Fallback para método alternativo
            return self.importar_estabelecimentos_alternativo(file_path, arquivo_origem)

    def _importar_estabelecimentos_principal(self, file_path: str, arquivo_origem: str) -> Tuple[bool, str]:
        """
        Método principal para importar estabelecimentos.
        """
        try:
            self.logger.info(f"Iniciando importação de estabelecimentos: {file_path}")
            
            # Ler e padronizar dados
            df = self._read_dataframe(file_path, dtype={'CO_CNES': str, 'CO_CEP': str})
            df = self._standardize_dataframe(df, 'estabelecimentos')
            
            # Garantir colunas necessárias
            required_columns = ['CO_CNES', 'NO_FANTASIA']
            for col in required_columns:
                if col not in df.columns:
                    df[col] = ""

            # Se existir razão social, manter como alternativa para nome fantasia vazio
            if 'RAZAO_SOCIAL' not in df.columns:
                df['RAZAO_SOCIAL'] = ""
            
            # Garantir strings
            df['CO_CNES'] = df['CO_CNES'].astype(str)
            df['NO_FANTASIA'] = df['NO_FANTASIA'].astype(str)
            df['RAZAO_SOCIAL'] = df['RAZAO_SOCIAL'].astype(str)

            if 'CO_CEP' in df.columns:
                df['CO_CEP'] = df['CO_CEP'].astype(str)
            else:
                df['CO_CEP'] = ""

            if 'DT_ATUALIZACAO' in df.columns:
                df['DT_ATUALIZACAO'] = df['DT_ATUALIZACAO'].astype(str)
            else:
                df['DT_ATUALIZACAO'] = ""
            
            # Limpar CNES antes de validar
            df['CO_CNES'] = (
                df['CO_CNES']
                .astype(str)
                .str.strip()
                .str.replace(r'\.0$', '', regex=True)
                .str.replace(r'\D', '', regex=True)
                .str.zfill(7)
            )

            # Remover CNES inválido
            df = df[
                df['CO_CNES'].notna() &
                (df['CO_CNES'].str.strip() != "") &
                (df['CO_CNES'] != "0000000")
            ]

            if df.empty:
                return False, "Nenhum registro válido encontrado (CNES obrigatório)"
            
            rows = []

            for row in df.itertuples(index=False):
                try:
                    cnes = str(getattr(row, 'CO_CNES', '')).strip()

                    nome = str(getattr(row, 'NO_FANTASIA', '')).strip()
                    if not nome or nome.lower() in ("nan", "none", "null"):
                        nome = str(getattr(row, 'RAZAO_SOCIAL', '')).strip()

                    if nome.lower() in ("nan", "none", "null"):
                        nome = ""

                    cep = str(getattr(row, 'CO_CEP', '')).strip() if hasattr(row, 'CO_CEP') else ''
                    if cep.endswith('.0'):
                        cep = cep[:-2]

                    atualizacao = str(getattr(row, 'DT_ATUALIZACAO', '')).strip() if hasattr(row, 'DT_ATUALIZACAO') else ''
                    
                    rows.append((cnes, nome, cep, atualizacao, arquivo_origem))

                except Exception as e:
                    self.logger.warning(f"Erro ao processar linha: {e}")
                    continue

            if not rows:
                return False, "Nenhum registro válido após processamento"

            total_inseridos = self.estabelecimento_model.inserir_lote(rows)
            mensagem = f"Estabelecimentos importados: {total_inseridos} registros"
            self.logger.info(mensagem)
            
            return True, mensagem
            
        except Exception as e:
            error_msg = f"Erro ao importar estabelecimentos: {e}"
            self.logger.error(error_msg)
            return False, error_msg
    
    def importar_dados_prd(self, data_or_path, arquivo_origem: str) -> Tuple[bool, str]:
        """
        Importa dados do PRD. Aceita DataFrame (direto do DBF) OU caminho CSV.
        
        Args:
            file_path: Caminho do arquivo CSV
            arquivo_origem: Nome do arquivo de origem para registro
            
        Returns:
            Tupla (sucesso, mensagem)
        """
        try:
            self.logger.info(f"Iniciando importação de PRD: {type(data_or_path).__name__}")
            dtype = {'PRD_UID': str, 'PRD_CMP': str, 'PRD_PA': str, 'PRD_CBO': str, 'PRD_TPFIN': str, 'PRD_CPX': str, 'PRD_QT_P': str, 'PRD_QT_A': str, 'PRD_VL_P': str, 'PRD_VL_A': str}
            df = self._coerce_to_dataframe(data_or_path, dtype=dtype, table_type='prd')

            # obrigatórias
            for col in ['PRD_UID', 'PRD_CMP', 'PRD_PA']:
                if col not in df.columns:
                    return False, f"Coluna obrigatória não encontrada: {col}"

            # normalizações
            df = df[
                df['PRD_UID'].astype(str).str.strip().ne('') &
                df['PRD_CMP'].astype(str).str.strip().ne('') &
                df['PRD_PA'].astype(str).str.strip().ne('')
            ]
            if df.empty:
                return False, "Nenhum registro válido encontrado"
                
            if 'PRD_CBO' not in df.columns:
                df['PRD_CBO'] = ""

            df['PRD_CBO'] = df['PRD_CBO'].apply(normalizar_cbo)
            
            # tipos numéricos
            df['PRD_QT_P'] = pd.to_numeric(df.get('PRD_QT_P', 0), errors='coerce').fillna(0)
            df['PRD_QT_A'] = pd.to_numeric(df.get('PRD_QT_A', 0), errors='coerce').fillna(0)
            df['PRD_VL_P'] = pd.to_numeric(df.get('PRD_VL_P', 0), errors='coerce').fillna(0.0)
            df['PRD_VL_A'] = pd.to_numeric(df.get('PRD_VL_A', 0), errors='coerce').fillna(0.0)
            
            if 'PRD_TPFIN' not in df.columns:
                df['PRD_TPFIN'] = ""

            df['PRD_TPFIN'] = df['PRD_TPFIN'].apply(normalizar_codigo_financiamento)
            
            if 'PRD_CPX' not in df.columns:
                df['PRD_CPX'] = ""

            df['PRD_CPX'] = df['PRD_CPX'].apply(normalizar_complexidade)

            # padronização dos campos-chave
            df['PRD_UID'] = (
                df['PRD_UID']
                .astype(str)
                .str.strip()
                .str.replace(r'\.0$', '', regex=True)
                .str.replace(r'\D', '', regex=True)
                .str.zfill(7)
            )

            df['PRD_CMP'] = df['PRD_CMP'].astype(str).str.strip()

            df['PRD_PA'] = (
                df['PRD_PA']
                .astype(str)
                .str.strip()
                .str.replace(r'\.0$', '', regex=True)
                .str.replace(r'\D', '', regex=True)
                .str.zfill(10)
            )
            
            # Define a competência principal como a que mais aparece no arquivo
            competencia_principal = (
                df['PRD_CMP']
                .astype(str)
                .str.strip()
                .value_counts()
                .idxmax()
            )

            # Soma registros repetidos dentro do mesmo arquivo
            df = (
                df.groupby(['PRD_UID', 'PRD_CMP', 'PRD_PA', 'PRD_CBO'], as_index=False)
                  .agg({
                      'PRD_TPFIN': 'first',
                      'PRD_CPX': 'first',
                      'PRD_QT_P': 'sum',
                      'PRD_QT_A': 'sum',
                      'PRD_VL_P': 'sum',
                      'PRD_VL_A': 'sum'
                  })
            )

            df_principal = df[df['PRD_CMP'] == competencia_principal].copy()
            df_retroativo = df[df['PRD_CMP'] != competencia_principal].copy()


            def montar_rows(df_base):
                return [
                    (
                        str(r.PRD_UID).strip(),
                        str(r.PRD_CMP).strip(),
                        str(r.PRD_PA).strip(),
                        str(r.PRD_CBO).strip(),
                        str(r.PRD_TPFIN).strip(),
                        str(r.PRD_CPX).strip(),
                        float(r.PRD_QT_P),
                        float(r.PRD_QT_A),
                        float(r.PRD_VL_P),
                        float(r.PRD_VL_A),
                        arquivo_origem
                    )
                    for r in df_base.itertuples(index=False)
                ]


            rows_principal = montar_rows(df_principal)
            rows_retroativo = montar_rows(df_retroativo)

            # Se o mesmo arquivo, pelo mesmo hash, já foi importado, não pode somar retroativo de novo.
            if self.produto_model.arquivo_prd_ja_importado(arquivo_origem):
                msg = (
                    f"Arquivo PRD já importado anteriormente: {arquivo_origem}. "
                    f"Importação bloqueada para evitar duplicidade de retroativos."
                )
                self.logger.warning(msg)
                return False, msg

            # Verifica se a competência principal tem diferença
            tem_diferenca_principal = self.produto_model.existem_diferencas_prd(rows_principal)

            # Se não tem diferença na principal e não tem retroativos, não há nada a fazer
            if not tem_diferenca_principal and not rows_retroativo:
                msg = (
                    f"Nenhuma alteração encontrada na competência principal {competencia_principal}. "
                    f"Importação cancelada."
                )
                self.logger.warning(msg)
                return False, msg

            # Competência principal: atualizar/substituir para o mais recente
            total_principal = self.produto_model.sincronizar_lote_prd(
                rows_principal,
                [competencia_principal]
            )

            # Competências diferentes da principal: somar/sincronizar como retroativo
            total_retroativo = self.produto_model.sincronizar_retroativos_prd(
                competencia_principal,
                rows_retroativo
            )

            # Registra o hash do arquivo importado
            self.produto_model.registrar_importacao_prd(
                arquivo_origem=arquivo_origem,
                competencia_principal=competencia_principal,
                total_principal=total_principal,
                total_retroativo=total_retroativo
            )

            total = total_principal + total_retroativo

            msg = (
                f"Dados PRD importados com sucesso. "
                f"Competência principal: {competencia_principal}. "
                f"Principal: {total_principal} registro(s). "
                f"Retroativos: {total_retroativo} registro(s). "
                f"Total processado: {total}."
)
            self.logger.info(msg)
            return True, msg

        except Exception as e:
            err = f"Erro ao importar dados PRD: {e}"
            self.logger.error(err)
            return False, err
  
    def importar_dados_pa(self, data_or_path, arquivo_origem: str) -> Tuple[bool, str]:
        """
        Importa dados do PA. Aceita DataFrame (direto do DBF) OU caminho CSV.
        
        Args:
            file_path: Caminho do arquivo CSV
            arquivo_origem: Nome do arquivo de origem para registro
            
        Returns:
            Tupla (sucesso, mensagem)
        """
        try:
            self.logger.info(f"Iniciando importação de PA: {type(data_or_path).__name__}")
            dtype = {'PA_ID': str, 'PA_DV': str, 'PA_DC': str, 'PA_TOTAL': str, 'PA_CTF': str, 'PA_CPX': str}
            df = self._coerce_to_dataframe(data_or_path, dtype=dtype, table_type='pa')

            if 'PA_ID' not in df.columns:
                return False, "Coluna obrigatória PA_ID não encontrada"

            df = df[df['PA_ID'].astype(str).str.strip().ne('')]
            if df.empty:
                return False, "Nenhum registro válido encontrado"

            # zfills e valores
            df['PA_ID'] = df['PA_ID'].astype(str).str.zfill(9)
            if 'PA_DV' in df.columns:
                df['PA_DV'] = df['PA_DV'].astype(str).str.zfill(1)
            else:
                df['PA_DV'] = ''  # mantém API do model
            df['PA_TOTAL'] = pd.to_numeric(df.get('PA_TOTAL', 0), errors='coerce').fillna(0.0)
            
            for col in ['PA_CTF', 'PA_CPX']:
                if col not in df.columns:
                    df[col] = ""

            df['PA_CTF'] = df['PA_CTF'].apply(normalizar_codigo_financiamento)
            df['PA_CPX'] = df['PA_CPX'].apply(normalizar_complexidade)

            rows = [
                (
                    getattr(r, 'PA_ID', '').strip(),
                    getattr(r, 'PA_DV', '').strip(),
                    getattr(r, 'PA_DC', '').strip() if hasattr(r, 'PA_DC') else '',
                    float(getattr(r, 'PA_TOTAL', 0) or 0),
                    getattr(r, 'PA_CTF', '').strip(),
                    getattr(r, 'PA_CPX', '').strip(),
                    arquivo_origem
                )
                for r in df.itertuples(index=False)
            ]

            # usa o método do seu model (que já faz bulk_insert interno)
            total = self.procedimento_model.inserir_lote(rows)
            msg = f"Dados PA importados: {total} registros"
            self.logger.info(msg)
            return True, msg

        except Exception as e:
            err = f"Erro ao importar dados PA: {e}"
            self.logger.error(err)
            return False, err
    
    def validar_arquivo(self, file_path: str, expected_columns: List[str]) -> Tuple[bool, str]:
        """
        Valida estrutura básica do arquivo CSV.
        
        Args:
            file_path: Caminho do arquivo
            expected_columns: Colunas esperadas no arquivo
            
        Returns:
            Tupla (válido, mensagem)
        """
        try:
            if not Path(file_path).exists():
                return False, f"Arquivo não encontrado: {file_path}"
            
            # Ler apenas o cabeçalho
            df = pd.read_csv(file_path, encoding='utf-8', sep=';', nrows=0)
            
            # Verificar colunas obrigatórias
            missing_columns = [col for col in expected_columns if col not in df.columns]
            if missing_columns:
                return False, f"Colunas obrigatórias faltando: {missing_columns}"
            
            return True, "Arquivo válido"
            
        except Exception as e:
            return False, f"Erro na validação do arquivo: {e}"
