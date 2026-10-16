"""Exportação CSV dos dados agregados dos relatórios."""

from __future__ import annotations

from os import PathLike
from typing import Any, Dict, Iterable

import pandas as pd

from sia_app.utils.sia_mappings import descricao_financiamento


def preparar_linhas_csv(dados: Iterable[Dict[str, Any]]) -> list[Dict[str, Any]]:
    """Converte os nomes internos em colunas amigáveis para o CSV."""
    linhas = []

    for row in dados:
        linhas.append(
            {
                "CNES": row.get("PRD_UID", ""),
                "Estabelecimento": row.get("NO_FANTASIA", "NÃO CADASTRADO"),
                "Competência": row.get("PRD_CMP", ""),
                "Procedimento": row.get("PRD_PA", ""),
                "Descrição": row.get("PA_DC", "Descrição não disponível"),
                "Tipo de Financiamento": descricao_financiamento(
                    row.get("PRD_TPFIN", "")
                ),
                "Valor Unitário": row.get("VALOR_UNITARIO", 0),
                "Quantidade Produzida": row.get("QUANTIDADE_PRODUZIDA", 0),
                "Valor Produzido": row.get("VALOR_PRODUZIDO", 0),
                "Quantidade Aprovada": row.get("QUANTIDADE_APROVADA", 0),
                "Valor Aprovado": row.get("VALOR_APROVADO", 0),
                "Valor Total": row.get("VALOR_TOTAL", 0),
            }
        )

    return linhas


def exportar_csv_agregado(
    dados: Iterable[Dict[str, Any]],
    output_path: str | PathLike[str],
) -> None:
    """Grava o CSV agregado em formato compatível com o Excel brasileiro."""
    df = pd.DataFrame(preparar_linhas_csv(dados))
    df.to_csv(
        output_path,
        index=False,
        encoding="utf-8-sig",
        sep=";",
        decimal=",",
        float_format="%.2f",
    )
