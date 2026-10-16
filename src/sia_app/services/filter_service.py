"""Regras, consultas e estatísticas da aba de filtros."""

from __future__ import annotations

import re
from typing import Any, Dict, List, Mapping, Sequence, Tuple


GROUP_DESCRIPTIONS = {
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


class FilterService:
    """Mantém a tela livre de SQL e de normalização de entradas."""

    def __init__(self, db):
        self.db = db

    @staticmethod
    def build_filters(
        *,
        cnes_text: str = "",
        procedimento: str = "",
        competencia_inicio: str = "",
        competencia_fim: str = "",
        tipo_financiamento: str = "Todos",
        complexidade: str = "Todas",
        uma_pagina_por_bloco: bool = True,
        ocultar_zerados: bool = False,
        repetir_cabecalho: bool = False,
        mostrar_aprovados: bool = False,
        mostrar_produzidos: bool = False,
    ) -> Dict[str, Any]:
        filters: Dict[str, Any] = {}
        cnes_list = []
        for cnes in re.split(r"[\s,;]+", cnes_text.strip()):
            cnes = cnes.strip()
            if cnes.endswith(".0"):
                cnes = cnes[:-2]
            cnes = re.sub(r"\D", "", cnes)
            if cnes:
                cnes_list.append(cnes.zfill(7))
        if cnes_list:
            filters["cnes_list"] = cnes_list

        procedimento = procedimento.strip()
        if procedimento:
            filters["procedimento"] = procedimento
            filters["tipo_filtro_proc"] = {
                2: "grupo",
                4: "subgrupo",
                6: "forma",
            }.get(len(procedimento), "exato")

        if competencia_inicio.strip():
            filters["competencia_inicio"] = competencia_inicio.strip()
        if competencia_fim.strip():
            filters["competencia_fim"] = competencia_fim.strip()
        if tipo_financiamento.strip() not in ("", "Todos"):
            filters["tipo_financiamento"] = tipo_financiamento.split(" - ")[0]
        if complexidade.strip() not in ("", "Todas"):
            filters["complexidade"] = complexidade.split(" - ")[0]

        filters.update(
            {
                "uma_pagina_por_bloco": bool(uma_pagina_por_bloco),
                "ocultar_zerados": bool(ocultar_zerados),
                "repetir_cabecalho": bool(repetir_cabecalho),
                "mostrar_aprovados": bool(mostrar_aprovados),
                "mostrar_produzidos": bool(mostrar_produzidos),
            }
        )
        return filters

    def recent_competences(self, limit: int = 2) -> List[str]:
        with self.db.read() as cursor:
            cursor.execute(
                "SELECT DISTINCT PRD_CMP FROM tb_prd ORDER BY PRD_CMP DESC LIMIT ?",
                (limit,),
            )
            return [str(row[0]) for row in cursor.fetchall()]

    def common_groups(self, limit: int = 15) -> List[Dict[str, Any]]:
        with self.db.read() as cursor:
            cursor.execute(
                """
                SELECT SUBSTR(PRD_PA, 1, 2) AS grupo,
                       COUNT(*) AS total,
                       (SELECT PA_DC FROM tb_pa
                        WHERE PA_ID = SUBSTR(PRD_PA, 1, 2) || '00000000'
                        LIMIT 1) AS descricao
                FROM tb_prd
                WHERE LENGTH(PRD_PA) >= 2
                GROUP BY grupo
                HAVING total > 10
                ORDER BY total DESC
                LIMIT ?
                """,
                (limit,),
            )
            return [
                {
                    "grupo": str(row[0]).strip().zfill(2),
                    "total": int(row[1] or 0),
                    "descricao": row[2]
                    or GROUP_DESCRIPTIONS.get(str(row[0]).strip().zfill(2), "Descrição não disponível"),
                }
                for row in cursor.fetchall()
            ]

    def suggestion_counts(self) -> Tuple[int, int]:
        with self.db.read() as cursor:
            cursor.execute(
                """
                SELECT COUNT(*) FROM (
                    SELECT DISTINCT p.PRD_UID, e.NO_FANTASIA
                    FROM tb_prd p
                    LEFT JOIN tb_estabelecimento e ON p.PRD_UID = e.CO_CNES
                    WHERE e.NO_FANTASIA IS NOT NULL
                    ORDER BY e.NO_FANTASIA
                    LIMIT 10
                )
                """
            )
            cnes_count = int(cursor.fetchone()[0])
            cursor.execute(
                """
                SELECT COUNT(*) FROM (
                    SELECT DISTINCT PRD_CMP FROM tb_prd
                    ORDER BY PRD_CMP DESC LIMIT 6
                )
                """
            )
            competence_count = int(cursor.fetchone()[0])
        return cnes_count, competence_count

    def preview_counts(self, filters: Mapping[str, Any]) -> Dict[str, int]:
        where, params = self._preview_where(filters)
        with self.db.read() as cursor:
            cursor.execute(
                f"""
                SELECT COUNT(*) AS records_count,
                       COUNT(DISTINCT p.PRD_UID) AS cnes_count,
                       COUNT(DISTINCT p.PRD_PA) AS procedures_count,
                       COUNT(DISTINCT p.PRD_CMP) AS competence_count
                FROM tb_prd p
                LEFT JOIN tb_pa pa ON pa.PROC = p.PRD_PA
                {where}
                """,
                params,
            )
            row = cursor.fetchone()
        return {
            "records_count": int(row[0] or 0),
            "cnes_count": int(row[1] or 0),
            "procedures_count": int(row[2] or 0),
            "competence_count": int(row[3] or 0),
        }

    @staticmethod
    def _preview_where(filters: Mapping[str, Any]) -> Tuple[str, List[Any]]:
        clauses = ["1=1"]
        params: List[Any] = []
        cnes_list: Sequence[str] = filters.get("cnes_list", [])
        if cnes_list:
            clauses.append(f"p.PRD_UID IN ({','.join('?' for _ in cnes_list)})")
            params.extend(cnes_list)
        if filters.get("procedimento"):
            if filters.get("tipo_filtro_proc") == "exato":
                clauses.append("p.PRD_PA = ?")
                params.append(filters["procedimento"])
            else:
                clauses.append("p.PRD_PA LIKE ?")
                params.append(f"{filters['procedimento']}%")
        for key, sql in (
            ("competencia_inicio", "p.PRD_CMP >= ?"),
            ("competencia_fim", "p.PRD_CMP <= ?"),
            ("tipo_financiamento", "p.PRD_TPFIN = ?"),
            ("complexidade", "p.PRD_CPX = ?"),
        ):
            if filters.get(key):
                clauses.append(sql)
                params.append(filters[key])
        return "WHERE " + " AND ".join(clauses), params

    @staticmethod
    def statistics_text(filters: Mapping[str, Any]) -> str:
        stats: List[str] = []
        if filters.get("cnes_list"):
            stats.append(f"• CNES: {len(filters['cnes_list'])} selecionado(s)")
        if filters.get("procedimento"):
            labels = {
                "grupo": "Grupo",
                "subgrupo": "Subgrupo",
                "forma": "Forma",
                "exato": "Procedimento exato",
            }
            tipo = labels.get(filters.get("tipo_filtro_proc", "exato"), "Procedimento exato")
            stats.append(f"• Procedimento: {filters['procedimento']} ({tipo})")
        if filters.get("competencia_inicio") or filters.get("competencia_fim"):
            stats.append(
                f"• Período: {filters.get('competencia_inicio', 'Início')} a "
                f"{filters.get('competencia_fim', 'Fim')}"
            )
        if filters.get("tipo_financiamento"):
            stats.append(f"• Tipo de financiamento: {filters['tipo_financiamento']}")
        if filters.get("complexidade"):
            stats.append(f"• Complexidade: {filters['complexidade']}")
        for key, label in (
            ("uma_pagina_por_bloco", "Uma página por bloco"),
            ("ocultar_zerados", "Ocultar zerados"),
            ("repetir_cabecalho", "Repetir cabeçalho"),
            ("mostrar_aprovados", "Mostrar aprovados"),
            ("mostrar_produzidos", "Mostrar produzidos"),
        ):
            stats.append(f"• {label}: {'Sim' if filters.get(key) else 'Não'}")
        return "📊 Estatísticas dos Filtros Aplicados:\n\n" + "\n".join(stats)
