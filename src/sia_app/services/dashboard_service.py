"""Consultas e regras do dashboard sem dependência de Tkinter."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Mapping, Sequence, Tuple

from sia_app.utils.sia_mappings import (
    TIPOS_FINANCIAMENTO,
    descricao_grupo_procedimento,
    normalizar_codigo_financiamento,
)


ChartRows = List[Tuple[str, float]]


@dataclass(frozen=True)
class DashboardComparison:
    """Matriz pronta para gráficos comparativos empilhados."""

    categories: List[str]
    series: List[str]
    values: List[List[float]]


@dataclass(frozen=True)
class DashboardData:
    """Dados completos necessários para atualizar a tela do dashboard."""

    cards: Mapping[str, float]
    grupos: ChartRows
    estabelecimentos: ChartRows
    competencias: ChartRows
    diferencas: ChartRows
    cbo: ChartRows
    financiamento_competencias: DashboardComparison
    financiamento_estabelecimentos: DashboardComparison


class DashboardService:
    """Centraliza SQL, filtros e agregações usados pelo dashboard."""

    METRICAS_SQL = {
        "Quantidade Produzida": "SUM(COALESCE(p.PRD_QT_P, 0))",
        "Quantidade Aprovada": "SUM(COALESCE(p.PRD_QT_A, 0))",
        "Valor Produzido": (
            "SUM(COALESCE(p.PRD_QT_P, 0) * COALESCE(pa.PA_TOTAL, 0))"
        ),
        "Valor Aprovado": (
            "SUM(COALESCE(p.PRD_QT_A, 0) * COALESCE(pa.PA_TOTAL, 0))"
        ),
    }

    def __init__(self, db):
        self.db = db

    @classmethod
    def normalizar_top_n(cls, value: Any) -> int:
        try:
            parsed = int(value)
        except (TypeError, ValueError):
            return 10
        return min(max(parsed, 1), 50)

    @classmethod
    def is_value_metric(cls, metric: str) -> bool:
        return metric in ("Valor Produzido", "Valor Aprovado")

    def carregar(
        self,
        filtros: Mapping[str, str],
        metrica: str,
        top_n: Any,
        modo_cbo: str,
    ) -> DashboardData:
        where_sql, params = self._build_where(filtros)
        metrica_sql = self.METRICAS_SQL.get(
            metrica,
            self.METRICAS_SQL["Quantidade Produzida"],
        )
        limite = self.normalizar_top_n(top_n)

        return DashboardData(
            cards=self._query_cards(where_sql, params),
            grupos=self._query_grupos(where_sql, params, metrica_sql),
            estabelecimentos=self._query_estabelecimentos(
                where_sql, params, metrica_sql, limite
            ),
            competencias=self._query_competencias(where_sql, params, metrica_sql),
            diferencas=self._query_diferencas(
                where_sql,
                params,
                por_valor=self.is_value_metric(metrica),
            ),
            cbo=self._query_cbo(where_sql, params, limite, modo_cbo),
            financiamento_competencias=self._query_financiamento_competencias(
                where_sql,
                params,
                metrica_sql,
            ),
            financiamento_estabelecimentos=(
                self._query_financiamento_estabelecimentos(
                    where_sql,
                    params,
                    metrica_sql,
                    limite,
                )
            ),
        )

    def carregar_cbo(
        self,
        filtros: Mapping[str, str],
        top_n: Any,
        modo_cbo: str,
    ) -> ChartRows:
        """Carrega somente o recorte CBO usado pela atualização local da aba."""
        where_sql, params = self._build_where(filtros)
        return self._query_cbo(
            where_sql,
            params,
            self.normalizar_top_n(top_n),
            modo_cbo,
        )

    def _build_where(
        self, filtros: Mapping[str, str]
    ) -> Tuple[str, List[Any]]:
        where = """
            FROM tb_prd p
            LEFT JOIN tb_estabelecimento e ON p.PRD_UID = e.CO_CNES
            LEFT JOIN tb_pa pa ON pa.PROC = p.PRD_PA
            WHERE 1=1
        """
        params: List[Any] = []

        comp_ini = filtros.get("competencia_inicio", "").strip()
        comp_fim = filtros.get("competencia_fim", "").strip()
        cnes = filtros.get("cnes", "").strip()
        procedimento = filtros.get("procedimento", "").strip()

        if comp_ini:
            where += " AND p.PRD_CMP >= ?"
            params.append(comp_ini)
        if comp_fim:
            where += " AND p.PRD_CMP <= ?"
            params.append(comp_fim)
        if cnes:
            cnes_list = [item.strip().zfill(7) for item in cnes.split(",") if item.strip()]
            if cnes_list:
                where += f" AND p.PRD_UID IN ({','.join('?' for _ in cnes_list)})"
                params.extend(cnes_list)
        if procedimento:
            if len(procedimento) in (2, 4, 6):
                where += " AND p.PRD_PA LIKE ?"
                params.append(f"{procedimento}%")
            else:
                where += " AND p.PRD_PA = ?"
                params.append(procedimento)

        financiamento = filtros.get("tipo_financiamento", "").strip()
        if financiamento and financiamento != "Todos":
            where += " AND p.PRD_TPFIN = ?"
            params.append(financiamento.split(" - ")[0])

        complexidade = filtros.get("complexidade", "").strip()
        if complexidade and complexidade != "Todas":
            where += " AND p.PRD_CPX = ?"
            params.append(complexidade.split(" - ")[0])

        return where, params

    def _fetchall(self, query: str, params: Sequence[Any] = ()):
        with self.db.read() as cursor:
            cursor.execute(query, list(params))
            return cursor.fetchall()

    def _query_cards(self, where_sql: str, params: Sequence[Any]) -> Dict[str, float]:
        rows = self._fetchall(
            f"""
                SELECT
                    SUM(COALESCE(p.PRD_QT_P, 0)) AS qtd_produzida,
                    SUM(COALESCE(p.PRD_QT_A, 0)) AS qtd_aprovada,
                    SUM(COALESCE(p.PRD_QT_P, 0) * COALESCE(pa.PA_TOTAL, 0)) AS valor_produzido,
                    SUM(COALESCE(p.PRD_QT_A, 0) * COALESCE(pa.PA_TOTAL, 0)) AS valor_aprovado,
                    COUNT(DISTINCT p.PRD_PA) AS procedimentos,
                    COUNT(DISTINCT p.PRD_UID) AS estabelecimentos
                {where_sql}
            """,
            params,
        )
        row = rows[0] if rows else None
        names = (
            "qtd_produzida",
            "qtd_aprovada",
            "valor_produzido",
            "valor_aprovado",
            "procedimentos",
            "estabelecimentos",
        )
        return {name: float(row[name] or 0) if row else 0.0 for name in names}

    def _query_grupos(
        self, where_sql: str, params: Sequence[Any], metrica_sql: str
    ) -> ChartRows:
        rows = self._fetchall(
            f"""
                SELECT substr(p.PRD_PA, 1, 2) AS label, {metrica_sql} AS total
                {where_sql}
                GROUP BY substr(p.PRD_PA, 1, 2)
                ORDER BY CAST(substr(p.PRD_PA, 1, 2) AS INTEGER)
            """,
            params,
        )
        return [
            (
                f"Grupo {descricao_grupo_procedimento(row['label'])}",
                float(row["total"] or 0),
            )
            for row in rows
        ]

    def _query_estabelecimentos(
        self,
        where_sql: str,
        params: Sequence[Any],
        metrica_sql: str,
        top_n: int,
    ) -> ChartRows:
        rows = self._fetchall(
            f"""
                SELECT COALESCE(NULLIF(e.NO_FANTASIA, ''), p.PRD_UID) AS label,
                       {metrica_sql} AS total
                {where_sql}
                GROUP BY p.PRD_UID, e.NO_FANTASIA
                ORDER BY total DESC
                LIMIT ?
            """,
            [*params, top_n],
        )
        return [(str(row["label"])[:45], float(row["total"] or 0)) for row in rows]

    def _query_competencias(
        self, where_sql: str, params: Sequence[Any], metrica_sql: str
    ) -> ChartRows:
        rows = self._fetchall(
            f"""
                SELECT p.PRD_CMP AS label, {metrica_sql} AS total
                {where_sql}
                GROUP BY p.PRD_CMP
                ORDER BY p.PRD_CMP
            """,
            params,
        )
        return [(str(row["label"]), float(row["total"] or 0)) for row in rows]

    def _query_diferencas(
        self, where_sql: str, params: Sequence[Any], *, por_valor: bool
    ) -> ChartRows:
        if por_valor:
            expressao = """
                SUM(COALESCE(p.PRD_QT_P, 0) * COALESCE(pa.PA_TOTAL, 0))
                - SUM(COALESCE(p.PRD_QT_A, 0) * COALESCE(pa.PA_TOTAL, 0))
            """
        else:
            expressao = """
                SUM(COALESCE(p.PRD_QT_P, 0))
                - SUM(COALESCE(p.PRD_QT_A, 0))
            """
        rows = self._fetchall(
            f"""
                SELECT p.PRD_CMP AS label, {expressao} AS total
                {where_sql}
                GROUP BY p.PRD_CMP
                ORDER BY p.PRD_CMP
            """,
            params,
        )
        return [(str(row["label"]), float(row["total"] or 0)) for row in rows]

    def _query_cbo(
        self,
        where_sql: str,
        params: Sequence[Any],
        top_n: int,
        modo: str,
    ) -> ChartRows:
        if modo == "CBO por Estabelecimento":
            rows = self._fetchall(
                f"""
                    SELECT COALESCE(NULLIF(e.NO_FANTASIA, ''), p.PRD_UID) AS estabelecimento,
                           COALESCE(NULLIF(p.PRD_CBO, ''), 'SEM CBO') AS cbo,
                           SUM(COALESCE(p.PRD_QT_P, 0)) AS total
                    {where_sql}
                    GROUP BY p.PRD_UID, e.NO_FANTASIA,
                             COALESCE(NULLIF(p.PRD_CBO, ''), 'SEM CBO')
                    ORDER BY total DESC
                    LIMIT ?
                """,
                [*params, top_n],
            )
            return [
                (
                    f"{row['estabelecimento']} | CBO {row['cbo']}",
                    float(row["total"] or 0),
                )
                for row in rows
            ]

        if modo == "CBO por Competência":
            rows = self._fetchall(
                f"""
                    SELECT p.PRD_CMP AS competencia,
                           COALESCE(NULLIF(p.PRD_CBO, ''), 'SEM CBO') AS cbo,
                           SUM(COALESCE(p.PRD_QT_P, 0)) AS total
                    {where_sql}
                    GROUP BY p.PRD_CMP,
                             COALESCE(NULLIF(p.PRD_CBO, ''), 'SEM CBO')
                    ORDER BY p.PRD_CMP, total DESC
                    LIMIT ?
                """,
                [*params, top_n],
            )
            return [
                (
                    f"{row['competencia']} | CBO {row['cbo']}",
                    float(row["total"] or 0),
                )
                for row in rows
            ]

        rows = self._fetchall(
            f"""
                SELECT COALESCE(NULLIF(p.PRD_CBO, ''), 'SEM CBO') AS cbo,
                       SUM(COALESCE(p.PRD_QT_P, 0)) AS total
                {where_sql}
                GROUP BY COALESCE(NULLIF(p.PRD_CBO, ''), 'SEM CBO')
                ORDER BY total DESC
                LIMIT ?
            """,
            [*params, top_n],
        )
        return [(f"CBO {row['cbo']}", float(row["total"] or 0)) for row in rows]

    def _query_financiamento_competencias(
        self,
        where_sql: str,
        params: Sequence[Any],
        metrica_sql: str,
    ) -> DashboardComparison:
        rows = self._fetchall(
            f"""
                SELECT p.PRD_CMP AS categoria,
                       COALESCE(NULLIF(p.PRD_TPFIN, ''), '00') AS financiamento,
                       {metrica_sql} AS total
                {where_sql}
                GROUP BY p.PRD_CMP,
                         COALESCE(NULLIF(p.PRD_TPFIN, ''), '00')
                ORDER BY p.PRD_CMP, financiamento
            """,
            params,
        )
        return self._comparison_from_rows(rows, category_order="label")

    def _query_financiamento_estabelecimentos(
        self,
        where_sql: str,
        params: Sequence[Any],
        metrica_sql: str,
        top_n: int,
    ) -> DashboardComparison:
        rows = self._fetchall(
            f"""
                SELECT p.PRD_UID AS categoria_id,
                       COALESCE(NULLIF(e.NO_FANTASIA, ''), p.PRD_UID) AS categoria,
                       COALESCE(NULLIF(p.PRD_TPFIN, ''), '00') AS financiamento,
                       {metrica_sql} AS total
                {where_sql}
                GROUP BY p.PRD_UID, e.NO_FANTASIA,
                         COALESCE(NULLIF(p.PRD_TPFIN, ''), '00')
            """,
            params,
        )
        return self._comparison_from_rows(
            rows,
            category_order="total",
            limit=top_n,
            include_category_id=True,
        )

    @classmethod
    def _comparison_from_rows(
        cls,
        rows,
        *,
        category_order: str,
        limit: int | None = None,
        include_category_id: bool = False,
    ) -> DashboardComparison:
        """Transforma linhas SQL em matriz sem misturar séries ou unidades."""
        category_values: Dict[Tuple[str, str], Dict[str, float]] = {}
        for row in rows:
            category_id = (
                str(row["categoria_id"] or "")
                if include_category_id
                else str(row["categoria"] or "")
            )
            category_label = str(row["categoria"] or "Não informado")
            if include_category_id and category_id:
                category_label = f"{category_label} · CNES {category_id}"
            category_key = (category_id, category_label)
            code = normalizar_codigo_financiamento(row["financiamento"]) or "00"
            values = category_values.setdefault(category_key, {})
            values[code] = values.get(code, 0.0) + float(row["total"] or 0)

        categories = list(category_values)
        if category_order == "total":
            categories.sort(
                key=lambda key: sum(category_values[key].values()),
                reverse=True,
            )
        else:
            categories.sort(key=lambda key: key[1])
        if limit is not None:
            categories = categories[:limit]

        series_codes = {
            code
            for key in categories
            for code in category_values[key]
        }
        sorted_codes = sorted(series_codes, key=cls._finance_sort_key)
        series = [cls._finance_label(code) for code in sorted_codes]
        matrix = [
            [category_values[key].get(code, 0.0) for code in sorted_codes]
            for key in categories
        ]
        return DashboardComparison(
            categories=[key[1] for key in categories],
            series=series,
            values=matrix,
        )

    @staticmethod
    def _finance_sort_key(code: str):
        return (0, int(code)) if code.isdigit() else (1, code)

    @staticmethod
    def _finance_label(code: str) -> str:
        if code == "00":
            return "Não informado"
        description = TIPOS_FINANCIAMENTO.get(
            code,
            "Tipo de financiamento não identificado",
        )
        return f"{code} - {description}"
