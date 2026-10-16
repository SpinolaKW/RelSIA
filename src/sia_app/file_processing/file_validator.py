import pandas as pd
import os
import chardet
from pathlib import Path
from typing import Tuple, List, Dict, Any, Optional
import logging
from dbfread import DBF

class FileValidator:
    """
    Validador de arquivos com suporte a múltiplos formatos e validações robustas.
    
    Características:
    - Validação de estrutura e conteúdo de arquivos
    - Detecção automática de encoding
    - Verificação de integridade de dados
    - Suporte a DBF, CSV e outros formatos
    """
    
    # Constantes de configuração
    SUPPORTED_EXTENSIONS = {'.dbf', '.csv', '.txt'}
    MAX_SAMPLE_ROWS = 1000
    MIN_FILE_SIZE = 1  # 1 byte
    
    # Mapeamento de colunas esperadas por tipo de arquivo
    EXPECTED_COLUMNS = {
        'estabelecimentos': ['CNES', 'CO_CNES', 'NOME', 'NO_FANTASIA'],
        'prd': ['PRD_UID', 'PRD_CMP', 'PRD_PA', 'PRD_QT_P', 'PRD_QT_A', 'PRD_VL_P', 'PRD_VL_A'],
        'pa': ['PA_ID', 'PA_DV', 'PA_DC', 'PA_TOTAL', 'PROC']
    }
    
    def __init__(self, logger: Optional[logging.Logger] = None):
        """
        Inicializa o validador de arquivos.
        
        Args:
            logger: Instância de logger (opcional)
        """
        self.logger = logger or logging.getLogger(__name__)
    
    def validar_arquivo_dbf(self, file_path: str, table_type: str) -> Tuple[bool, str]:
        """
        Valida arquivo DBF sem usar métodos problemáticos.
        """
        try:
            if not os.path.exists(file_path):
                return False, f"Arquivo não encontrado: {file_path}"
            
            # Ler apenas metadados do DBF
            try:
                from dbfread import DBF
                table = DBF(file_path)
                
                # Verificar se tem registros
                record_count = sum(1 for _ in table)
                if record_count == 0:
                    return False, "Arquivo DBF vazio"
                
                # Verificar colunas esperadas
                expected_columns = self._get_expected_columns(table_type)
                actual_columns = table.field_names
                
                missing_columns = [col for col in expected_columns if col not in actual_columns]
                if missing_columns:
                    return False, f"Colunas faltando: {missing_columns}"
                
                return True, f"DBF válido: {record_count} registros, {len(actual_columns)} colunas"
                
            except Exception as e:
                return False, f"Erro na validação DBF: {str(e)}"
                
        except Exception as e:
            return False, f"Erro geral na validação: {str(e)}"

    def _get_expected_columns(self, table_type: str) -> list:
        """Retorna colunas esperadas para cada tipo de tabela."""
        if table_type == 'prd':
            return ['PRD_UID', 'PRD_CMP', 'PRD_PA', 'PRD_QT_A', 'PRD_VL_A']
        elif table_type == 'pa':
            return ['PA_ID', 'PA_DV', 'PA_DC', 'PA_TOTAL']
        return []
        
    def _validar_estrutura_dbf(self, file_path: str) -> Tuple[bool, str]:
        """
        Valida a estrutura do arquivo DBF.
        
        Args:
            file_path: Caminho do arquivo DBF
            
        Returns:
            Tupla (sucesso, mensagem)
        """
        try:
            dbf = DBF(file_path, load=False)  # Não carregar dados ainda
            
            # Verificar se tem campos
            if not dbf.fields:
                return False, "Arquivo DBF sem campos definidos"
            
            # Verificar número mínimo de registros
            total_registros = len(dbf)
            if total_registros == 0:
                return False, "Arquivo DBF sem registros"
            
            # Verificar campos essenciais
            campos_obrigatorios = ['PRD_UID', 'CNES', 'PA_ID']  # Campos que devem existir em algum DBF
            campos_existentes = [field.name for field in dbf.fields]
            campos_encontrados = [campo for campo in campos_obrigatorios if campo in campos_existentes]
            
            if not campos_encontrados:
                return False, f"Nenhum campo obrigatório encontrado. Campos existentes: {campos_existentes}"
            
            dbf.close()
            return True, f"Estrutura válida: {total_registros} registros, {len(campos_existentes)} campos"
            
        except Exception as e:
            return False, f"Erro na validação da estrutura DBF: {e}"
    
    def _validar_dados_dbf(self, file_path: str, table_type: str = None) -> Tuple[bool, str]:
        """
        Valida amostra dos dados do DBF.
        
        Args:
            file_path: Caminho do arquivo DBF
            table_type: Tipo de tabela para validação específica
            
        Returns:
            Tupla (sucesso, mensagem)
        """
        try:
            dbf = DBF(file_path, load=False)
            total_registros = len(dbf)
            
            # Amostrar primeiros registros para validação
            registros_amostra = min(100, total_registros)
            dados_validos = 0
            problemas = []
            
            for i, record in enumerate(dbf):
                if i >= registros_amostra:
                    break
                
                # Validar registro individual
                registro_valido, problema = self._validar_registro_dbf(record, table_type)
                if registro_valido:
                    dados_validos += 1
                elif problema:
                    problemas.append(problema)
            
            dbf.close()
            
            # Avaliar qualidade dos dados
            taxa_validos = dados_validos / registros_amostra if registros_amostra > 0 else 0
            
            if taxa_validos < 0.5:  # Menos de 50% válidos
                return False, f"Baixa qualidade de dados: {taxa_validos:.1%} válidos. Problemas: {problemas[:3]}"
            
            if problemas:
                self.logger.warning(f"Problemas encontrados na amostra: {problemas[:5]}")
            
            return True, f"Dados amostrais válidos: {taxa_validos:.1%} ({dados_validos}/{registros_amostra})"
            
        except Exception as e:
            return False, f"Erro na validação de dados DBF: {e}"
    
    def _validar_registro_dbf(self, record: Dict, table_type: str = None) -> Tuple[bool, Optional[str]]:
        """
        Valida um registro individual do DBF.
        
        Args:
            record: Registro do DBF
            table_type: Tipo de tabela para validação específica
            
        Returns:
            Tupla (válido, mensagem_erro)
        """
        try:
            # Verificar se o registro tem dados
            if not record:
                return False, "Registro vazio"
            
            # Validar baseado no tipo de tabela
            if table_type == 'prd':
                return self._validar_registro_prd(record)
            elif table_type == 'pa':
                return self._validar_registro_pa(record)
            elif table_type == 'estabelecimentos':
                return self._validar_registro_estabelecimento(record)
            else:
                # Validação genérica
                campos_nao_vazios = sum(1 for valor in record.values() if valor and str(valor).strip())
                if campos_nao_vazios == 0:
                    return False, "Todos os campos vazios"
            
            return True, None
            
        except Exception as e:
            return False, f"Erro na validação do registro: {e}"
    
    def _validar_registro_prd(self, record: Dict) -> Tuple[bool, Optional[str]]:
        """Valida registro de PRD."""
        campos_obrigatorios = ['PRD_UID', 'PRD_CMP', 'PRD_PA']
        campos_faltantes = [campo for campo in campos_obrigatorios if campo not in record or not record[campo]]
        
        if campos_faltantes:
            return False, f"Campos PRD obrigatórios faltando: {campos_faltantes}"
        
        # Validar tipos de dados numéricos
        if 'PRD_QT_A' in record and record['PRD_QT_A']:
            try:
                float(record['PRD_QT_A'])
            except (ValueError, TypeError):
                return False, "PRD_QT_A deve ser numérico"
        
        if 'PRD_VL_A' in record and record['PRD_VL_A']:
            try:
                float(record['PRD_VL_A'])
            except (ValueError, TypeError):
                return False, "PRD_VL_A deve ser numérico"
        
        return True, None
    
    def _validar_registro_pa(self, record: Dict) -> Tuple[bool, Optional[str]]:
        """Valida registro de PA."""
        if 'PA_ID' not in record or not record['PA_ID']:
            return False, "PA_ID obrigatório"
        
        # Validar valor numérico
        if 'PA_TOTAL' in record and record['PA_TOTAL']:
            try:
                float(record['PA_TOTAL'])
            except (ValueError, TypeError):
                return False, "PA_TOTAL deve ser numérico"
        
        return True, None
    
    def _validar_registro_estabelecimento(self, record: Dict) -> Tuple[bool, Optional[str]]:
        """Valida registro de estabelecimento."""
        campos_identificadores = ['CNES', 'CO_CNES']
        tem_identificador = any(campo in record and record[campo] for campo in campos_identificadores)
        
        if not tem_identificador:
            return False, "Nenhum identificador (CNES/CO_CNES) encontrado"
        
        return True, None
    
    def _validar_encoding_dbf(self, file_path: str) -> Tuple[bool, str]:
        """
        Valida encoding do arquivo DBF.
        
        Args:
            file_path: Caminho do arquivo DBF
            
        Returns:
            Tupla (sucesso, mensagem)
        """
        try:
            # Tentar detectar encoding
            with open(file_path, 'rb') as f:
                raw_data = f.read(10000)  # Ler amostra
                resultado = chardet.detect(raw_data)
                
            encoding = resultado['encoding']
            confianca = resultado['confidence']
            
            if confianca < 0.7:
                return False, f"Encoding detectado com baixa confiança: {encoding} ({confianca:.1%})"
            
            # Tentar abrir com o encoding detectado
            DBF(file_path, encoding=encoding, load=False).close()
            
            return True, f"Encoding válido: {encoding} (confiança: {confianca:.1%})"
            
        except Exception as e:
            return False, f"Problema com encoding: {e}"
    
    def validar_arquivo_csv(self, file_path: str, table_type: str = None) -> Tuple[bool, str]:
        """
        Valida arquivo CSV com verificações completas.
        
        Args:
            file_path: Caminho do arquivo CSV
            table_type: Tipo de tabela para validação específica
            
        Returns:
            Tupla (sucesso, mensagem)
        """
        try:
            # Validações básicas
            basic_checks = self._validar_arquivo_basico(file_path, ['.csv', '.txt'])
            if not basic_checks[0]:
                return basic_checks
            
            file_info = self._obter_info_arquivo(file_path)
            self.logger.info(f"Validando CSV: {file_path} ({file_info['tamanho_mb']:.2f} MB)")
            
            # Detectar encoding
            encoding = self._detectar_encoding_csv(file_path)
            
            # Validar estrutura CSV
            estrutura_valida, mensagem_estrutura = self._validar_estrutura_csv(file_path, encoding, table_type)
            if not estrutura_valida:
                return False, mensagem_estrutura
            
            # Validar dados CSV
            dados_validos, mensagem_dados = self._validar_dados_csv(file_path, encoding, table_type)
            if not dados_validos:
                return False, mensagem_dados
            
            mensagem_final = f"CSV válido: encoding {encoding}, {file_info['tamanho_mb']:.2f} MB"
            self.logger.info(mensagem_final)
            return True, mensagem_final
            
        except Exception as e:
            error_msg = f"Erro na validação do CSV: {e}"
            self.logger.error(error_msg)
            return False, error_msg
    
    def _validar_estrutura_csv(self, file_path: str, encoding: str, table_type: str = None) -> Tuple[bool, str]:
        """
        Valida estrutura do arquivo CSV.
        
        Args:
            file_path: Caminho do arquivo CSV
            encoding: Encoding do arquivo
            table_type: Tipo de tabela para validação específica
            
        Returns:
            Tupla (sucesso, mensagem)
        """
        try:
            # Ler apenas o cabeçalho
            df = pd.read_csv(file_path, encoding=encoding, sep=';', nrows=0)
            
            if df.empty:
                return False, "Arquivo CSV vazio ou sem cabeçalho"
            
            colunas = df.columns.tolist()
            
            # Validar colunas baseado no tipo
            if table_type in self.EXPECTED_COLUMNS:
                colunas_esperadas = self.EXPECTED_COLUMNS[table_type]
                colunas_faltantes = [col for col in colunas_esperadas if col not in colunas]
                
                if colunas_faltantes:
                    return False, f"Colunas esperadas não encontradas: {colunas_faltantes}. Colunas existentes: {colunas}"
            
            return True, f"Estrutura válida: {len(colunas)} colunas"
            
        except Exception as e:
            return False, f"Erro na validação da estrutura CSV: {e}"
    
    def _validar_dados_csv(self, file_path: str, encoding: str, table_type: str = None) -> Tuple[bool, str]:
        """
        Valida amostra dos dados do CSV.
        
        Args:
            file_path: Caminho do arquivo CSV
            encoding: Encoding do arquivo
            table_type: Tipo de tabela para validação específica
            
        Returns:
            Tupla (sucesso, mensagem)
        """
        try:
            # Ler amostra de dados
            df = pd.read_csv(
                file_path, 
                encoding=encoding, 
                sep=';', 
                nrows=self.MAX_SAMPLE_ROWS,
                dtype=str,
                na_filter=False
            )
            
            if df.empty:
                return False, "Nenhum dado encontrado na amostra"
            
            # Verificar dados não vazios
            registros_nao_vazios = len(df.dropna(how='all'))
            if registros_nao_vazios == 0:
                return False, "Todos os registros da amostra estão vazios"
            
            # Validar colunas chave baseado no tipo
            if table_type == 'estabelecimentos':
                colunas_chave = ['CNES', 'CO_CNES']
                coluna_chave_presente = any(col in df.columns for col in colunas_chave)
                if not coluna_chave_presente:
                    return False, f"Nenhuma coluna chave encontrada: {colunas_chave}"
            
            taxa_nao_vazios = registros_nao_vazios / len(df)
            if taxa_nao_vazios < 0.8:  # 80% dos registros devem ter dados
                return False, f"Baixa taxa de registros não vazios: {taxa_nao_vazios:.1%}"
            
            return True, f"Dados amostrais válidos: {taxa_nao_vazios:.1%} não vazios"
            
        except Exception as e:
            return False, f"Erro na validação de dados CSV: {e}"
    
    def _detectar_encoding_csv(self, file_path: str) -> str:
        """
        Detecta encoding do arquivo CSV.
        
        Args:
            file_path: Caminho do arquivo CSV
            
        Returns:
            Encoding detectado
        """
        try:
            with open(file_path, 'rb') as f:
                raw_data = f.read(50000)  # Amostra maior para melhor detecção
                resultado = chardet.detect(raw_data)
            
            encoding = resultado['encoding'] or 'utf-8'
            confianca = resultado['confidence']
            
            self.logger.debug(f"Encoding detectado: {encoding} (confiança: {confianca:.1%})")
            
            # Fallback para encodings comuns
            if confianca < 0.6:
                encodings_tentativas = ['utf-8', 'latin-1', 'iso-8859-1', 'cp1252']
                for enc in encodings_tentativas:
                    try:
                        with open(file_path, 'r', encoding=enc) as f:
                            f.read(1024)
                        self.logger.info(f"Usando encoding fallback: {enc}")
                        return enc
                    except UnicodeDecodeError:
                        continue
            
            return encoding
            
        except Exception as e:
            self.logger.warning(f"Erro na detecção de encoding, usando utf-8: {e}")
            return 'utf-8'
    
    def _validar_arquivo_basico(self, file_path: str, extensoes_permitidas: List[str]) -> Tuple[bool, str]:
        """
        Validações básicas do arquivo.
        
        Args:
            file_path: Caminho do arquivo
            extensoes_permitidas: Lista de extensões permitidas
            
        Returns:
            Tupla (sucesso, mensagem)
        """
        if not os.path.exists(file_path):
            return False, "Arquivo não encontrado"
        
        if not os.path.isfile(file_path):
            return False, "Caminho não é um arquivo"
        
        # Verificar tamanho do arquivo
        tamanho = os.path.getsize(file_path)
        if tamanho < self.MIN_FILE_SIZE:
            return False, f"Arquivo muito pequeno ({tamanho} bytes)"
        
        # Verificar extensão
        extensao = Path(file_path).suffix.lower()
        if extensao not in extensoes_permitidas:
            return False, f"Extensão {extensao} não permitida. Permitidas: {extensoes_permitidas}"
        
        # Verificar permissões de leitura
        if not os.access(file_path, os.R_OK):
            return False, "Sem permissão de leitura do arquivo"
        
        return True, "Validações básicas OK"
    
    def _obter_info_arquivo(self, file_path: str) -> Dict[str, Any]:
        """
        Obtém informações do arquivo.
        
        Args:
            file_path: Caminho do arquivo
            
        Returns:
            Dicionário com informações
        """
        stat = os.stat(file_path)
        return {
            'tamanho_bytes': stat.st_size,
            'tamanho_mb': stat.st_size / (1024 * 1024),
            'data_modificacao': stat.st_mtime,
            'registros': 0,  # Será preenchido pelas validações específicas
            'campos': 0      # Será preenchido pelas validações específicas
        }
    
    def validar_tipos_arquivo(self, file_path: str, expected_extensions: List[str] = None) -> Tuple[bool, str]:
        """
        Valida extensão do arquivo.
        
        Args:
            file_path: Caminho do arquivo
            expected_extensions: Lista de extensões esperadas (opcional)
            
        Returns:
            Tupla (sucesso, mensagem)
        """
        if expected_extensions is None:
            expected_extensions = list(self.SUPPORTED_EXTENSIONS)
        
        extensao = Path(file_path).suffix.lower()
        
        if extensao not in expected_extensions:
            return False, f"Extensão {extensao} não permitida. Extensões permitidas: {expected_extensions}"
        
        return True, f"Extensão válida: {extensao}"