"""Preparação dos registros exibidos na janela de visualização."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Mapping, Tuple

from sia_app.utils.sia_mappings import (
    descricao_complexidade,
    descricao_financiamento,
    descricao_financiamento_procedimento,
)


@dataclass(frozen=True)
class DataViewResult:
    rows: List[Tuple[str, ...]]
    totals: Mapping[str, float]


class DataViewService:
    """Normaliza dados heterogêneos antes que a interface os desenhe."""

    @staticmethod
    def _to_float(value: Any, default: float = 0.0) -> float:
        try:
            return default if value is None else float(value)
        except (TypeError, ValueError):
            return default

    @staticmethod
    def _to_int(value: Any, default: int = 0) -> int:
        try:
            return default if value is None else int(float(value))
        except (TypeError, ValueError):
            return default

    @staticmethod
    def _first(row: Mapping[str, Any], *fields: str, default: Any = None) -> Any:
        for field in fields:
            value = row.get(field)
            if value is not None:
                return value
        return default

    @staticmethod
    def format_int(value: Any) -> str:
        return f"{DataViewService._to_int(value):,}".replace(",", ".")

    @staticmethod
    def format_money(value: Any) -> str:
        rendered = f"{DataViewService._to_float(value):,.2f}"
        return "R$ " + rendered.replace(",", "X").replace(".", ",").replace("X", ".")

    def prepare(
        self,
        dados: List[Mapping[str, Any]],
        estabelecimentos: Mapping[str, str],
    ) -> DataViewResult:
        totals: Dict[str, float] = {
            "quantidade": 0,
            "valor": 0.0,
            "qtd_aprovada": 0,
            "valor_aprovado": 0.0,
            "qtd_produzida": 0,
            "valor_produzido": 0.0,
        }
        prepared: List[Tuple[str, ...]] = []

        for row in dados:
            if not row:
                continue

            cnes = self._first(row, "PRD_UID", "CO_CNES", "uid", default="")
            cnes_text = str(cnes)
            cnes_key = cnes_text.zfill(7) if cnes_text.isdigit() else cnes_text
            estabelecimento = estabelecimentos.get(cnes_key, "Não cadastrado")
            competencia = self._first(row, "PRD_CMP", "COMPETENCIA", "cmp", default="")
            procedimento = self._first(
                row, "PRD_PA", "PROC", "procedimento", "codigo", default=""
            )
            descricao = str(
                self._first(
                    row,
                    "PA_DC",
                    "descricao",
                    "descricao_procedimento",
                    default="Descrição não disponível",
                )
            )[:80]
            cbo = row.get("PRD_CBO") or "CBO não encontrado"

            quantidade = self._to_int(
                self._first(row, "PRD_QT_A", "QUANTIDADE", "quantidade", "QT_A", "QT", default=0)
            )
            valor_unitario = self._to_float(
                self._first(
                    row,
                    "VALOR_UNITARIO",
                    "PA_TOTAL",
                    "valor_unitario",
                    "VL_UNITARIO",
                    "PRD_VL_A",
                    "VL_A",
                    default=0,
                )
            )
            qtd_aprovada = self._to_int(
                self._first(row, "QUANTIDADE_APROVADA", "QUANTIDADE", "PRD_QT_A", default=0)
            )
            qtd_produzida = self._to_int(
                self._first(row, "QUANTIDADE_PRODUZIDA", "PRD_QT_P", default=0)
            )
            valor_aprovado = self._to_float(
                row.get("VALOR_APROVADO"), qtd_aprovada * valor_unitario
            )
            valor_produzido = self._to_float(
                row.get("VALOR_PRODUZIDO"), qtd_produzida * valor_unitario
            )
            valor_total = self._to_float(row.get("VALOR_TOTAL"), valor_aprovado)

            totals["quantidade"] += quantidade
            totals["valor"] += valor_total
            totals["qtd_aprovada"] += qtd_aprovada
            totals["valor_aprovado"] += valor_aprovado
            totals["qtd_produzida"] += qtd_produzida
            totals["valor_produzido"] += valor_produzido

            prepared.append(
                (
                    cnes_text,
                    estabelecimento,
                    str(competencia),
                    str(procedimento),
                    descricao,
                    str(cbo),
                    descricao_financiamento(row.get("PRD_TPFIN")),
                    descricao_complexidade(row.get("PRD_CPX")),
                    descricao_financiamento_procedimento(row.get("PA_CTF")),
                    descricao_complexidade(row.get("PA_CPX")),
                    self.format_int(quantidade),
                    self.format_money(valor_unitario),
                    self.format_int(qtd_produzida),
                    self.format_money(valor_produzido),
                    self.format_int(qtd_aprovada),
                    self.format_money(valor_aprovado),
                    self.format_money(valor_total),
                )
            )

        return DataViewResult(rows=prepared, totals=totals)
