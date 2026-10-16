"""Regras de agrupamento e opções usadas pelos relatórios."""

from __future__ import annotations

from collections import defaultdict
from typing import Any, Dict, List, Mapping, Sequence, Tuple


class ReportService:
    def __init__(self, db):
        self.db = db

    def establishment_map(self) -> Dict[str, str]:
        with self.db.read() as cursor:
            cursor.execute("SELECT CO_CNES, NO_FANTASIA FROM tb_estabelecimento")
            return {
                str(cnes).zfill(7): name or f"CNES {cnes} (Não cadastrado)"
                for cnes, name in cursor.fetchall()
            }

    @staticmethod
    def group_by_establishment_competence(
        data: Sequence[Mapping[str, Any]],
        establishments: Mapping[str, str],
    ) -> List[Dict[str, Any]]:
        grouped = defaultdict(list)
        for row in data:
            grouped[(str(row["PRD_UID"]).strip(), str(row["PRD_CMP"]).strip())].append(row)
        return [
            {
                "uid": cnes,
                "cmp": competence,
                "nome": establishments.get(
                    cnes.zfill(7), f"CNES {cnes} (Não cadastrado)"
                ),
                "rows": rows,
            }
            for (cnes, competence), rows in sorted(grouped.items())
        ]

    @staticmethod
    def extract_procedure(filters: Mapping[str, Any]) -> str:
        for key in (
            "procedimento",
            "codigo_procedimento",
            "proc",
            "procedimento_codigo",
        ):
            value = str(filters.get(key, "")).strip()
            if value:
                return value
        return ""

    @classmethod
    def filter_and_group_procedure(
        cls,
        data: Sequence[Mapping[str, Any]],
        establishments: Mapping[str, str],
        procedure: str,
    ) -> Tuple[List[Dict[str, Any]], int]:
        grouped = defaultdict(list)
        retained = 0
        for row in data:
            if not cls.match_procedure(row, procedure):
                continue
            cnes = cls.pick_field(row, ("PRD_UID", "CNES", "UID", "CO_CNES"))
            competence = cls.pick_field(row, ("PRD_CMP", "COMPETENCIA", "CMP"))
            if cnes and competence:
                grouped[(str(cnes).strip(), str(competence).strip())].append(row)
                retained += 1
        blocks = [
            {
                "uid": cnes,
                "cmp": competence,
                "nome": establishments.get(
                    cnes.zfill(7), f"CNES {cnes} (Não cadastrado)"
                ),
                "rows": rows,
            }
            for (cnes, competence), rows in sorted(grouped.items())
        ]
        return blocks, retained

    @staticmethod
    def prepare_pdf_options(
        config: Mapping[str, Any],
        title: str,
        table_mode: str,
        filters: Mapping[str, Any],
    ) -> Dict[str, Any]:
        return {
            "title": title,
            "inst1": config.get("inst1") or "Prefeitura Municipal",
            "inst2": config.get("inst2") or "Secretaria de Saúde",
            "inst3": config.get("inst3") or "Sistema SIA",
            "logo_path": config.get("logo_path"),
            "table_mode": table_mode,
            "uma_pagina_por_bloco": filters.get("uma_pagina_por_bloco", True),
            "ocultar_zerados": filters.get("ocultar_zerados", False),
            "repetir_cabecalho": filters.get("repetir_cabecalho", False),
            "mostrar_aprovados": filters.get("mostrar_aprovados", False),
            "mostrar_produzidos": filters.get("mostrar_produzidos", False),
        }

    @staticmethod
    def only_digits(value: Any) -> str:
        return "".join(character for character in str(value or "") if character.isdigit())

    @staticmethod
    def row_keys(row) -> List[str]:
        try:
            return list(row.keys())
        except AttributeError:
            try:
                return list(row.__dict__.keys())
            except AttributeError:
                return list(row) if hasattr(row, "__iter__") else []

    @classmethod
    def pick_field(cls, row, candidates: Sequence[str]) -> Any:
        keys = cls.row_keys(row)
        for key in candidates:
            if key in keys:
                return row[key]
        return None

    @classmethod
    def match_procedure(cls, row, filter_value: str) -> bool:
        normalized_filter = cls.only_digits(filter_value)
        if not normalized_filter:
            return False
        keys = cls.row_keys(row)
        candidates: List[str] = []
        if "PRD_PA" in keys:
            candidates.append(cls.only_digits(row["PRD_PA"]))
            if "PA_DV" in keys and row["PA_DV"] is not None:
                candidates.append(cls.only_digits(f"{row['PRD_PA']}{row['PA_DV']}"))
        for key in ("PROC", "COD_PROCEDIMENTO", "PA_ID", "PRD_COD", "PROCEDIMENTO", "PA"):
            if key in keys:
                candidates.append(cls.only_digits(row[key]))
        return any(
            code
            and (
                code == normalized_filter
                or code.startswith(normalized_filter)
                or normalized_filter.startswith(code)
            )
            for code in candidates
        )
