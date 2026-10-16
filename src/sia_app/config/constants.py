"""
Constantes do sistema para processamento de dados de saúde
"""
from typing import Dict, List, Final

class Constants:
    """Constantes do sistema para configuração e mapeamentos"""
    
    # Versão do sistema
    VERSION: Final[str] = "2.21.0"
    
    # Extensões permitidas organizadas por categoria
    ALLOWED_EXTENSIONS: Final[Dict[str, List[str]]] = {
        'dbf': ['.dbf'],
        'csv': ['.csv'],
        'backup': ['.sqlite.backup', '.zip'],
        'images': ['.png', '.jpg', '.jpeg']
    }
    
    # Colunas das tabelas
    PRD_COLUMNS: Final[List[str]] = ['PRD_UID', 'PRD_CMP', 'PRD_PA', 'PRD_QT_A', 'PRD_VL_A']
    PA_COLUMNS: Final[List[str]] = ['PA_ID', 'PA_DV', 'PA_DC']
    ESTABELECIMENTO_COLUMNS: Final[List[str]] = ['CO_CNES', 'NO_FANTASIA', 'CO_CEP', 'DT_ATUALIZACAO']
    
    # Mapeamento de meses (português brasileiro)
    MESES: Final[Dict[str, str]] = {
        '01': 'Janeiro', '02': 'Fevereiro', '03': 'Março',
        '04': 'Abril', '05': 'Maio', '06': 'Junho',
        '07': 'Julho', '08': 'Agosto', '09': 'Setembro',
        '10': 'Outubro', '11': 'Novembro', '12': 'Dezembro'
    }
    
    # Métodos utilitários para acesso às constantes
    @classmethod
    def get_allowed_extensions(cls, file_type: str = None) -> List[str]:
        """Retorna extensões permitidas para um tipo específico ou todas"""
        if file_type:
            return cls.ALLOWED_EXTENSIONS.get(file_type, [])
        return [ext for extensions in cls.ALLOWED_EXTENSIONS.values() for ext in extensions]
    
    @classmethod
    def get_mes_name(cls, mes_num: str) -> str:
        """Retorna o nome do mês baseado no número"""
        return cls.MESES.get(mes_num, 'Mês inválido')
    
    @classmethod
    def is_valid_extension(cls, filename: str, file_type: str = None) -> bool:
        """Verifica se a extensão do arquivo é permitida"""
        if not filename:
            return False
            
        filename_lower = filename.lower()
        allowed_extensions = cls.get_allowed_extensions(file_type)
        
        return any(filename_lower.endswith(ext) for ext in allowed_extensions)
