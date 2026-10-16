TIPOS_FINANCIAMENTO = {
    "01": "PAB - Piso de Atenção Básica",
    "02": "MAC - Média e Alta Complexidade",
    "03": "FAEC - Fundo de Ações Estratégicas e Compensação",
    "04": "Assistência Farmacêutica",
    "05": "Incentivo MAC",
    "06": "Vigilância em Saúde",
    "07": "Gestão do SUS",
}

FINANCIAMENTO_PROCEDIMENTO = {
    "01": "Federal SUS",
    "02": "Plano de Saúde Público",
    "03": "Plano de Saúde Privado",
    "04": "Particular",
    "05": "Gratuidade",
    "06": "Estadual SUS",
    "07": "Municipal SUS",
    "08": "Programas e Projetos Federais",
    "09": "FAEC",
}

COMPLEXIDADES = {
    "0": "Não se aplica / não informado",
    "": "Não se aplica / não informado",
    "1": "Atenção Básica",
    "2": "Média Complexidade",
    "3": "Alta Complexidade",
}

GRUPOS_PROCEDIMENTO = {
    "01": "Ações de promoção e prevenção em saúde",
    "02": "Procedimentos com finalidade diagnóstica",
    "03": "Procedimentos clínicos",
    "04": "Procedimentos cirúrgicos",
    "05": "Transplantes de órgãos, tecidos e células",
    "06": "Medicamentos",
    "07": "Órteses, próteses e materiais especiais",
    "08": "Ações complementares da atenção à saúde",
    "09": "Procedimentos para Ofertas de Cuidados Integrados",
}

def normalizar_codigo_financiamento(valor):
    valor = str(valor or "").strip()

    if not valor or valor.lower() in ("nan", "none"):
        return ""

    valor = valor.replace(".0", "")

    if valor.isdigit():
        return valor.zfill(2)

    return valor


def normalizar_complexidade(valor):
    valor = str(valor or "").strip().replace(".0", "")

    if not valor or valor.lower() in ("nan", "none"):
        return "0"

    return valor


def descricao_financiamento(codigo):
    """
    Usado para PRD_TPFIN.
    Tipo de financiamento da produção.
    """
    codigo = normalizar_codigo_financiamento(codigo)

    if not codigo:
        return ""

    descricao = TIPOS_FINANCIAMENTO.get(
        codigo,
        "Tipo de financiamento não identificado"
    )

    return f"{codigo} - {descricao}"


def descricao_financiamento_procedimento(codigo):
    """
    Usado para PA_CTF.
    Financiamento do procedimento.
    """
    codigo = normalizar_codigo_financiamento(codigo)

    if not codigo:
        return ""

    descricao = FINANCIAMENTO_PROCEDIMENTO.get(
        codigo,
        "Financiamento do procedimento não identificado"
    )

    return f"{codigo} - {descricao}"


def descricao_complexidade(codigo):
    codigo = normalizar_complexidade(codigo)

    descricao = COMPLEXIDADES.get(
        codigo,
        "Complexidade não identificada"
    )

    return f"{codigo} - {descricao}"
    
def descricao_grupo_procedimento(codigo):
    codigo = str(codigo or "").strip().replace(".0", "")

    if not codigo:
        return ""

    if codigo.isdigit():
        codigo = codigo.zfill(2)

    descricao = GRUPOS_PROCEDIMENTO.get(
        codigo,
        "Grupo de procedimento não identificado"
    )

    return f"{codigo} - {descricao}"
    
def normalizar_cbo(valor):
    valor = str(valor or "").strip()

    if not valor or valor.lower() in ("nan", "none"):
        return ""

    valor = valor.replace(".0", "")

    if valor.isdigit():
        return valor.zfill(6)

    return valor