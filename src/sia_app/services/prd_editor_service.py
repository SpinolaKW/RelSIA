"""Operações de consulta e manutenção dos registros de produção."""

from __future__ import annotations

from typing import Any, List, Sequence, Tuple

from sia_app.utils.sia_mappings import (
    descricao_complexidade,
    descricao_financiamento,
    descricao_financiamento_procedimento,
)


class PrdEditorService:
    def __init__(self, db):
        self.db = db

    def list_records(
        self,
        competencia: str = "",
        estabelecimento: str = "",
        limit: int = 2000,
    ) -> List[Tuple[Any, ...]]:
        where, params = self.build_filter(competencia, estabelecimento)
        with self.db.read() as cursor:
            cursor.execute(
                f"""
                SELECT p.id, p.PRD_UID,
                       COALESCE(e.NO_FANTASIA, 'NÃO CADASTRADO') AS NO_FANTASIA,
                       p.PRD_CMP, p.PRD_PA, p.PRD_CBO, COALESCE(pa.PA_DC, '') AS PA_DC,
                       p.PRD_TPFIN, p.PRD_CPX, pa.PA_CTF, pa.PA_CPX,
                       p.PRD_QT_P, p.PRD_QT_A,
                       COALESCE(p.PRD_QT_P, 0) * COALESCE(pa.PA_TOTAL, 0) AS VL_P,
                       COALESCE(p.PRD_QT_A, 0) * COALESCE(pa.PA_TOTAL, 0) AS VL_A,
                       p.arquivo_origem
                FROM tb_prd p
                LEFT JOIN tb_estabelecimento e ON p.PRD_UID = e.CO_CNES
                LEFT JOIN tb_pa pa ON p.PRD_PA = pa.PROC
                {where}
                ORDER BY p.PRD_CMP DESC, e.NO_FANTASIA, p.PRD_PA
                LIMIT ?
                """,
                [*params, limit],
            )
            rows = cursor.fetchall()
        return [self._format_row(row) for row in rows]

    def update_quantities(self, record_id: Any, produzida: Any, aprovada: Any):
        qtd_produzida = int(float(str(produzida).replace(",", ".")))
        qtd_aprovada = int(float(str(aprovada).replace(",", ".")))
        if qtd_produzida < 0 or qtd_aprovada < 0:
            raise ValueError("As quantidades não podem ser negativas.")
        with self.db.txn() as cursor:
            cursor.execute(
                """
                UPDATE tb_prd
                SET PRD_QT_P = ?, PRD_QT_A = ?, data_importacao = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (qtd_produzida, qtd_aprovada, record_id),
            )
            if cursor.rowcount != 1:
                raise LookupError("Registro de produção não encontrado.")

    def delete_one(self, record_id: Any) -> int:
        with self.db.txn() as cursor:
            cursor.execute("DELETE FROM tb_prd WHERE id = ?", (record_id,))
            return int(cursor.rowcount)

    def count_filtered(self, competencia: str, estabelecimento: str) -> int:
        where, params = self.build_filter(competencia, estabelecimento)
        with self.db.read() as cursor:
            cursor.execute(
                f"""
                SELECT COUNT(*)
                FROM tb_prd p
                LEFT JOIN tb_estabelecimento e ON p.PRD_UID = e.CO_CNES
                {where}
                """,
                params,
            )
            return int(cursor.fetchone()[0])

    def delete_filtered(self, competencia: str, estabelecimento: str) -> int:
        where, params = self.build_filter(competencia, estabelecimento)
        with self.db.txn() as cursor:
            cursor.execute(
                f"""
                DELETE FROM tb_prd
                WHERE id IN (
                    SELECT p.id
                    FROM tb_prd p
                    LEFT JOIN tb_estabelecimento e ON p.PRD_UID = e.CO_CNES
                    {where}
                )
                """,
                params,
            )
            return int(cursor.rowcount)

    @staticmethod
    def build_filter(
        competencia: str = "", estabelecimento: str = ""
    ) -> Tuple[str, List[Any]]:
        where = "WHERE 1=1"
        params: List[Any] = []
        if competencia.strip():
            where += " AND p.PRD_CMP = ?"
            params.append(competencia.strip())
        if estabelecimento.strip():
            where += " AND e.NO_FANTASIA LIKE ?"
            params.append(f"%{estabelecimento.strip()}%")
        return where, params

    @classmethod
    def _format_row(cls, row: Sequence[Any]) -> Tuple[Any, ...]:
        return (
            row[0], row[1], row[2], row[3], row[4], row[5], row[6],
            descricao_financiamento(row[7]),
            descricao_complexidade(row[8]),
            descricao_financiamento_procedimento(row[9]),
            descricao_complexidade(row[10]),
            cls.format_int(row[11]),
            cls.format_int(row[12]),
            cls.format_currency(row[13]),
            cls.format_currency(row[14]),
            row[15] or "",
        )

    @staticmethod
    def format_int(value: Any) -> str:
        try:
            return str(int(float(value)))
        except (TypeError, ValueError):
            return "0"

    @staticmethod
    def format_currency(value: Any) -> str:
        try:
            rendered = f"{float(value):,.2f}"
        except (TypeError, ValueError):
            rendered = "0.00"
        return "R$ " + rendered.replace(",", "X").replace(".", ",").replace("X", ".")
