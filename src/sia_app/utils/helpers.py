import re
from datetime import datetime
from typing import Optional, Union, Pattern

class Validadores:
    """Classe para validações e formatações comuns"""
    
    # Compilação de regex para melhor performance
    _CNES_REGEX: Pattern = re.compile(r'^\d{7}$')
    _EMAIL_REGEX: Pattern = re.compile(
        r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    )
    _CEP_REGEX: Pattern = re.compile(r'^\d{5}-?\d{3}$')
    
    @staticmethod
    def validar_cnes(cnes: Union[str, int]) -> bool:
        """
        Valida formato do CNES (7 dígitos)
        
        Args:
            cnes: CNES a ser validado (string ou inteiro)
            
        Returns:
            bool: True se o CNES for válido
        """
        return bool(Validadores._CNES_REGEX.match(str(cnes)))

    @staticmethod
    def validar_email(email: Optional[str]) -> bool:
        """
        Valida formato de e-mail
        
        Args:
            email: E-mail a ser validado (pode ser None ou vazio)
            
        Returns:
            bool: True se o e-mail for válido ou vazio
        """
        if not email:
            return True
        return bool(Validadores._EMAIL_REGEX.match(email.strip()))

    @staticmethod
    def validar_cep(cep: Optional[Union[str, int]]) -> bool:
        """
        Valida formato do CEP
        
        Args:
            cep: CEP a ser validado (pode ser None)
            
        Returns:
            bool: True se o CEP for válido ou vazio
        """
        if not cep:
            return True
        return bool(Validadores._CEP_REGEX.match(str(cep)))

    @staticmethod
    def formatar_moeda(valor: Union[str, int, float]) -> str:
        """
        Formata valor para formato monetário brasileiro
        
        Args:
            valor: Valor a ser formatado
            
        Returns:
            str: Valor formatado como "R$ 1.234,56" ou "R$ 0,00" em caso de erro
        """
        try:
            valor_float = float(valor)
            # Formata com separador de milhar e decimal
            valor_formatado = f"R$ {valor_float:,.2f}"
            # Substitui formatação padrão para formato brasileiro
            return valor_formatado.replace(',', 'X').replace('.', ',').replace('X', '.')
        except (ValueError, TypeError):
            return "R$ 0,00"

    @staticmethod
    def formatar_moeda_alternativo(valor: Union[str, int, float]) -> str:
        """
        Alternativa mais eficiente para formatação monetária
        
        Args:
            valor: Valor a ser formatado
            
        Returns:
            str: Valor formatado como "R$ 1.234,56"
        """
        try:
            valor_float = float(valor)
            # Usa locale para formatação mais robusta
            import locale
            locale.setlocale(locale.LC_ALL, 'pt_BR.UTF-8')
            return locale.currency(valor_float, grouping=True, symbol=True)
        except (ValueError, TypeError, ImportError):
            # Fallback para método manual
            try:
                valor_float = float(valor)
                partes = f"{valor_float:,.2f}".split('.')
                inteiro = partes[0].replace(',', '.')
                decimal = partes[1] if len(partes) > 1 else '00'
                return f"R$ {inteiro},{decimal}"
            except:
                return "R$ 0,00"

    @staticmethod
    def formatar_data_iso_br(data_iso: Optional[str]) -> str:
        """
        Converte data ISO para formato brasileiro (DD/MM/AAAA)
        
        Args:
            data_iso: Data em formato ISO (YYYY-MM-DD)
            
        Returns:
            str: Data formatada ou string original em caso de erro
        """
        if not data_iso:
            return ""
            
        try:
            # Remove timezone e converte
            data_limpa = data_iso.replace('Z', '+00:00').split('T')[0]
            dt = datetime.fromisoformat(data_limpa)
            return dt.strftime("%d/%m/%Y")
        except (ValueError, AttributeError):
            return str(data_iso)

    @staticmethod
    def formatar_data_br_completa(data_iso: Optional[str]) -> str:
        """
        Converte data ISO para formato brasileiro completo (DD/MM/AAAA HH:MM)
        
        Args:
            data_iso: Data em formato ISO
            
        Returns:
            str: Data e hora formatadas
        """
        if not data_iso:
            return ""
            
        try:
            data_limpa = data_iso.replace('Z', '+00:00')
            dt = datetime.fromisoformat(data_limpa)
            return dt.strftime("%d/%m/%Y %H:%M")
        except (ValueError, AttributeError):
            return str(data_iso)

    @staticmethod
    def normalizar_cnes(cnes: Union[str, int]) -> str:
        """
        Normaliza CNES para formato padrão (7 dígitos com zeros à esquerda)
        
        Args:
            cnes: CNES a ser normalizado
            
        Returns:
            str: CNES normalizado com 7 dígitos
        """
        cnes_str = str(cnes).strip()
        return cnes_str.zfill(7)

    @staticmethod
    def normalizar_cep(cep: Union[str, int]) -> str:
        """
        Normaliza CEP para formato 00000-000
        
        Args:
            cep: CEP a ser normalizado
            
        Returns:
            str: CEP no formato 00000-000
        """
        if not cep:
            return ""
            
        cep_str = re.sub(r'[^\d]', '', str(cep))
        if len(cep_str) == 8:
            return f"{cep_str[:5]}-{cep_str[5:]}"
        return cep_str

    @staticmethod
    def validar_data_brasileira(data_br: str) -> bool:
        """
        Valida data no formato brasileiro (DD/MM/AAAA)
        
        Args:
            data_br: Data no formato DD/MM/AAAA
            
        Returns:
            bool: True se a data for válida
        """
        try:
            datetime.strptime(data_br, "%d/%m/%Y")
            return True
        except (ValueError, TypeError):
            return False

    @staticmethod
    def converter_br_para_iso(data_br: str) -> Optional[str]:
        """
        Converte data do formato brasileiro para ISO
        
        Args:
            data_br: Data no formato DD/MM/AAAA
            
        Returns:
            str: Data em formato ISO ou None se inválida
        """
        try:
            dt = datetime.strptime(data_br, "%d/%m/%Y")
            return dt.strftime("%Y-%m-%d")
        except (ValueError, TypeError):
            return None


# Funções de compatibilidade (para manter interface anterior)
def validar_cnes(cnes: Union[str, int]) -> bool:
    """Valida formato do CNES (7 dígitos)"""
    return Validadores.validar_cnes(cnes)

def validar_email(email: Optional[str]) -> bool:
    """Valida formato de e-mail"""
    return Validadores.validar_email(email)

def validar_cep(cep: Optional[Union[str, int]]) -> bool:
    """Valida formato do CEP"""
    return Validadores.validar_cep(cep)

def formatar_moeda(valor: Union[str, int, float]) -> str:
    """Formata valor para formato monetário brasileiro"""
    return Validadores.formatar_moeda(valor)

def formatar_data_iso_br(data_iso: Optional[str]) -> str:
    """Converte data ISO para formato brasileiro"""
    return Validadores.formatar_data_iso_br(data_iso)