import re
import tkinter as tk
from tkinter import messagebox
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Tuple, Optional, Union, Any
import os

class Validators:
    """
    Classe com validadores otimizados para o sistema SIA
    """
    
    # Constantes para validação
    CNES_LENGTH = 7
    COMPETENCIA_LENGTH = 6
    CEP_LENGTH = 8
    MIN_YEAR = 2000
    MAX_YEAR = 2100
    MAX_VALOR = 1_000_000_000  # 1 bilhão
    MAX_QUANTIDADE = 1_000_000  # 1 milhão
    MIN_PROCEDIMENTO_LENGTH = 2
    MAX_PROCEDIMENTO_LENGTH = 10
    
    # Cache para anos bissextos
    _leap_year_cache: Dict[int, bool] = {}
    
    @staticmethod
    def _is_leap_year(year: int) -> bool:
        """Verifica se o ano é bissexto com cache"""
        if year not in Validators._leap_year_cache:
            Validators._leap_year_cache[year] = (
                (year % 4 == 0 and year % 100 != 0) or (year % 400 == 0)
            )
        return Validators._leap_year_cache[year]
    
    @staticmethod
    def _get_month_days(month: int, year: int) -> int:
        """Retorna o número de dias em um mês"""
        if month == 2:
            return 29 if Validators._is_leap_year(year) else 28
        elif month in {4, 6, 9, 11}:
            return 30
        else:
            return 31
    
    @staticmethod
    def validar_cnes(cnes: Union[str, int]) -> Tuple[bool, str]:
        """
        Valida formato do CNES (7 dígitos)
        
        Args:
            cnes: CNES a ser validado
            
        Returns:
            Tuple[bool, str]: (sucesso, mensagem)
        """
        if not cnes:
            return False, "CNES não pode estar vazio"
        
        cnes_str = str(cnes).strip()
        
        # Validação mais eficiente com regex pré-compilado
        if not cnes_str.isdigit():
            return False, "CNES deve conter apenas números"
        
        if len(cnes_str) != Validators.CNES_LENGTH:
            return False, f"CNES deve ter exatamente {Validators.CNES_LENGTH} dígitos"
        
        return True, "CNES válido"
    
    @staticmethod
    def validar_competencia(competencia: Union[str, int]) -> Tuple[bool, str]:
        """
        Valida formato da competência (AAAAMM)
        
        Args:
            competencia: Competência no formato AAAAMM
            
        Returns:
            Tuple[bool, str]: (sucesso, mensagem)
        """
        if not competencia:
            return False, "Competência não pode estar vazia"
        
        competencia_str = str(competencia).strip()
        
        if not competencia_str.isdigit():
            return False, "Competência deve conter apenas números"
        
        if len(competencia_str) != Validators.COMPETENCIA_LENGTH:
            return False, f"Competência deve ter {Validators.COMPETENCIA_LENGTH} dígitos (AAAAMM)"
        
        try:
            ano = int(competencia_str[:4])
            mes = int(competencia_str[4:6])
            
            if not (Validators.MIN_YEAR <= ano <= Validators.MAX_YEAR):
                return False, f"Ano deve estar entre {Validators.MIN_YEAR} e {Validators.MAX_YEAR}"
            
            if not (1 <= mes <= 12):
                return False, "Mês deve estar entre 01 e 12"
            
            # Valida se a competência não é futura
            data_competencia = datetime(ano, mes, 1)
            if data_competencia > datetime.now():
                return False, "Competência não pode ser futura"
            
            return True, "Competência válida"
            
        except ValueError:
            return False, "Erro ao processar competência"
    
    @staticmethod
    def validar_cep(cep: Optional[Union[str, int]]) -> Tuple[bool, str]:
        """
        Valida formato do CEP (opcional)
        
        Args:
            cep: CEP a ser validado
            
        Returns:
            Tuple[bool, str]: (sucesso, mensagem)
        """
        if not cep:
            return True, "CEP opcional"
        
        cep_str = str(cep).strip()
        
        # Remove caracteres não numéricos de forma mais eficiente
        cep_limpo = re.sub(r'[^\d]', '', cep_str)
        
        if not cep_limpo:
            return False, "CEP deve conter números"
        
        if len(cep_limpo) != Validators.CEP_LENGTH:
            return False, f"CEP deve ter {Validators.CEP_LENGTH} dígitos"
        
        return True, "CEP válido"
    
    @staticmethod
    def validar_valor_monetario(valor: Optional[Union[str, int, float]]) -> Tuple[bool, str]:
        """
        Valida valor monetário de forma otimizada
        
        Args:
            valor: Valor a ser validado
            
        Returns:
            Tuple[bool, str]: (sucesso, mensagem)
        """
        if valor is None:
            return False, "Valor não pode ser nulo"
        
        # Conversão mais eficiente
        try:
            # Remove formatação monetária se existir
            if isinstance(valor, str):
                valor_limpo = re.sub(r'[^\d,]', '', valor).replace(',', '.')
            else:
                valor_limpo = valor
            
            valor_float = float(valor_limpo)
            
            if valor_float < 0:
                return False, "Valor não pode ser negativo"
            
            if valor_float > Validators.MAX_VALOR:
                return False, f"Valor não pode exceder {Validators.MAX_VALOR:,}"
            
            return True, "Valor válido"
            
        except (ValueError, TypeError):
            return False, "Valor deve ser um número válido"
    
    @staticmethod
    def validar_quantidade(quantidade: Optional[Union[str, int, float]]) -> Tuple[bool, str]:
        """
        Valida quantidade de forma otimizada
        
        Args:
            quantidade: Quantidade a ser validada
            
        Returns:
            Tuple[bool, str]: (sucesso, mensagem)
        """
        if quantidade is None:
            return False, "Quantidade não pode ser nula"
        
        try:
            qtd_float = float(quantidade)
            
            if qtd_float < 0:
                return False, "Quantidade não pode ser negativa"
            
            if qtd_float > Validators.MAX_QUANTIDADE:
                return False, f"Quantidade não pode exceder {Validators.MAX_QUANTIDADE:,}"
            
            if not qtd_float.is_integer():
                return False, "Quantidade deve ser um número inteiro"
            
            return True, "Quantidade válida"
            
        except (ValueError, TypeError):
            return False, "Quantidade deve ser um número"
    
    @staticmethod
    def validar_data_brasileira(data_str: Optional[str]) -> Tuple[bool, str]:
        """
        Valida data no formato brasileiro (DD/MM/AAAA) de forma otimizada
        
        Args:
            data_str: Data no formato DD/MM/AAAA
            
        Returns:
            Tuple[bool, str]: (sucesso, mensagem)
        """
        if not data_str:
            return True, "Data opcional"
        
        # Verificação rápida do formato
        if not re.match(r'^\d{1,2}/\d{1,2}/\d{4}$', data_str):
            return False, "Data deve estar no formato DD/MM/AAAA"
        
        try:
            dia, mes, ano = map(int, data_str.split('/'))
            
            # Validações rápidas
            if not (1 <= mes <= 12):
                return False, "Mês deve estar entre 01 e 12"
            
            if not (1 <= dia <= 31):
                return False, "Dia deve estar entre 01 e 31"
            
            if not (1900 <= ano <= 2100):
                return False, "Ano deve estar entre 1900 e 2100"
            
            # Validação específica do mês
            max_dias = Validators._get_month_days(mes, ano)
            if dia > max_dias:
                return False, f"Mês {mes:02d} tem no máximo {max_dias} dias"
            
            # Valida se a data não é futura
            data_obj = datetime(ano, mes, dia)
            if data_obj > datetime.now():
                return False, "Data não pode ser futura"
            
            return True, "Data válida"
            
        except ValueError:
            return False, "Data contém valores inválidos"
    
    @staticmethod
    def validar_codigo_procedimento(codigo: Union[str, int]) -> Tuple[bool, str]:
        """
        Valida código de procedimento de forma otimizada
        
        Args:
            codigo: Código do procedimento
            
        Returns:
            Tuple[bool, str]: (sucesso, mensagem)
        """
        if not codigo:
            return False, "Código do procedimento não pode estar vazio"
        
        codigo_str = str(codigo).strip()
        
        if not codigo_str.isdigit():
            return False, "Código do procedimento deve conter apenas números"
        
        comprimento = len(codigo_str)
        if not (Validators.MIN_PROCEDIMENTO_LENGTH <= comprimento <= Validators.MAX_PROCEDIMENTO_LENGTH):
            return False, f"Código deve ter entre {Validators.MIN_PROCEDIMENTO_LENGTH} e {Validators.MAX_PROCEDIMENTO_LENGTH} dígitos"
        
        return True, "Código válido"
    
    @staticmethod
    def validar_campos_estabelecimento(dados: Dict[str, Any]) -> Tuple[bool, List[str]]:
        """
        Valida todos os campos de um estabelecimento de forma otimizada
        
        Args:
            dados: Dicionário com dados do estabelecimento
            
        Returns:
            Tuple[bool, List[str]]: (sucesso, lista de erros)
        """
        erros = []
        
        # Validações usando compreensão de lista para melhor performance
        validacoes = [
            (Validators.validar_cnes(dados.get('CO_CNES', '')), "CNES"),
            (Validators.validar_cep(dados.get('CO_CEP', '')), "CEP")
        ]
        
        for (valido, mensagem), campo in validacoes:
            if not valido:
                erros.append(f"{campo}: {mensagem}")
        
        # Validação de campo obrigatório
        if not dados.get('NO_FANTASIA', '').strip():
            erros.append("Nome Fantasia: Campo obrigatório")
        
        return len(erros) == 0, erros
    
    @staticmethod
    def _validar_arquivo_generico(caminho_arquivo: str, extensoes_validas: set) -> Tuple[bool, str]:
        """
        Validação genérica de arquivo
        
        Args:
            caminho_arquivo: Caminho do arquivo
            extensoes_validas: Set com extensões válidas
            
        Returns:
            Tuple[bool, str]: (sucesso, mensagem)
        """
        if not caminho_arquivo:
            return False, "Caminho do arquivo não especificado"
        
        path = Path(caminho_arquivo)
        
        if not path.exists():
            return False, "Arquivo não encontrado"
        
        if not path.is_file():
            return False, "Caminho especificado não é um arquivo"
        
        if path.suffix.lower() not in extensoes_validas:
            extensoes_str = ", ".join(extensoes_validas)
            return False, f"Arquivo deve ter uma das extensões: {extensoes_str}"
        
        try:
            # Teste de acesso mais eficiente
            path.open('rb').close()
            return True, "Arquivo válido"
        except IOError as e:
            return False, f"Não foi possível acessar o arquivo: {e}"
    
    @staticmethod
    def validar_arquivo_dbf(caminho_arquivo: str) -> Tuple[bool, str]:
        """
        Valida se o arquivo DBF existe e é acessível
        
        Args:
            caminho_arquivo: Caminho do arquivo DBF
            
        Returns:
            Tuple[bool, str]: (sucesso, mensagem)
        """
        return Validators._validar_arquivo_generico(caminho_arquivo, {'.dbf'})
    
    @staticmethod
    def validar_arquivo_csv(caminho_arquivo: str) -> Tuple[bool, str]:
        """
        Valida se o arquivo CSV existe e é acessível
        
        Args:
            caminho_arquivo: Caminho do arquivo CSV
            
        Returns:
            Tuple[bool, str]: (sucesso, mensagem)
        """
        return Validators._validar_arquivo_generico(caminho_arquivo, {'.csv'})
    
    @staticmethod
    def mostrar_erros_validacao(erros: List[str], parent: Optional[tk.Widget] = None) -> None:
        """
        Exibe mensagens de erro de validação de forma otimizada
        
        Args:
            erros: Lista de mensagens de erro
            parent: Widget pai para a messagebox
        """
        if not erros:
            return
        
        # Limita o número de erros exibidos
        if len(erros) > 10:
            erros_exibir = erros[:10] + [f"... e mais {len(erros) - 10} erros"]
        else:
            erros_exibir = erros
        
        mensagem = "Erros de validação:\n\n" + "\n".join(f"• {erro}" for erro in erros_exibir)
        
        messagebox.showerror("Erro de Validação", mensagem, parent=parent)
    
    @staticmethod
    def criar_validacao_entry(entry: tk.Entry, tipo_validacao: str, 
                            delay_ms: int = 500) -> None:
        """
        Cria validação em tempo real para um entry com debouncing
        
        Args:
            entry: Widget Entry do tkinter
            tipo_validacao: Tipo de validação ('cnes', 'competencia', 'cep')
            delay_ms: Delay para validação após digitação (ms)
        """
        # Timer para debouncing
        after_id = None
        
        def _validar() -> None:
            nonlocal after_id
            after_id = None
            
            valor = entry.get().strip()
            
            if not valor:  # Campo vazio é válido
                entry.config(background='white')
                return
            
            # Seleciona o validador apropriado
            validadores = {
                'cnes': Validators.validar_cnes,
                'competencia': Validators.validar_competencia,
                'cep': Validators.validar_cep,
                'procedimento': Validators.validar_codigo_procedimento,
                'valor': Validators.validar_valor_monetario,
                'quantidade': Validators.validar_quantidade
            }
            
            validador = validadores.get(tipo_validacao)
            if validador:
                valido, _ = validador(valor)
                cor_fundo = 'white' if valido else '#ffcccc'
                entry.config(background=cor_fundo)
        
        def _agendar_validacao(event=None) -> None:
            nonlocal after_id
            # Cancela validação anterior agendada
            if after_id:
                entry.after_cancel(after_id)
            # Agenda nova validação
            after_id = entry.after(delay_ms, _validar)
        
        # Vincula eventos
        entry.bind('<KeyRelease>', _agendar_validacao)
        entry.bind('<FocusOut>', _agendar_validacao)


# Funções de conveniência para compatibilidade
def validar_cnes(cnes: Union[str, int]) -> Tuple[bool, str]:
    """Função de conveniência para validar CNES"""
    return Validators.validar_cnes(cnes)

def validar_competencia(competencia: Union[str, int]) -> Tuple[bool, str]:
    """Função de conveniência para validar competência"""
    return Validators.validar_competencia(competencia)