"""Regras de cadastro, pesquisa e ordenação de estabelecimentos."""

from __future__ import annotations

from datetime import datetime
from typing import Dict, List, Mapping, Optional

from sia_app.database.models import EstabelecimentoModel


class EstablishmentService:
    SORTABLE_FIELDS = {"CO_CNES", "NO_FANTASIA", "CO_CEP"}

    def __init__(self, db):
        self.model = EstabelecimentoModel(db)

    def list_sorted(self, column: str, ascending: bool = True) -> List[Dict]:
        return self.sort(self.model.listar_todos(), column, ascending)

    def search(
        self,
        records: List[Dict],
        term: str,
        column: str,
        ascending: bool = True,
    ) -> List[Dict]:
        lowered = term.strip().lower()
        if not lowered:
            return self.sort(records, column, ascending)
        filtered = [
            row
            for row in records
            if any(
                lowered in str(row.get(field, "")).lower()
                for field in self.SORTABLE_FIELDS
            )
        ]
        return self.sort(filtered, column, ascending)

    @classmethod
    def sort(cls, records: List[Dict], column: str, ascending: bool) -> List[Dict]:
        if column not in cls.SORTABLE_FIELDS:
            column = "CO_CNES"
        return sorted(
            records,
            key=lambda row: str(row.get(column, "")).casefold(),
            reverse=not ascending,
        )

    def get(self, record_id: int) -> Optional[Dict]:
        return self.model.obter_por_id(record_id)

    def delete(self, record_id: int) -> bool:
        return bool(self.model.excluir_por_id(record_id))

    def save(self, record_id: Optional[int], values: Mapping[str, str]) -> str:
        cnes = str(values.get("CO_CNES", "")).strip()
        name = str(values.get("NO_FANTASIA", "")).strip()
        cep = str(values.get("CO_CEP", "")).strip()
        if not cnes:
            raise ValueError("O campo CNES é obrigatório.")
        if not name:
            raise ValueError("O campo Nome Fantasia é obrigatório.")
        if not cnes.isdigit() or len(cnes) != 7:
            raise ValueError("CNES deve conter exatamente 7 dígitos numéricos.")

        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        params = (cnes, name, cep, timestamp, "CADASTRO_MANUAL")
        if record_id:
            changed = self.model.execute_query(
                """
                UPDATE tb_estabelecimento
                SET CO_CNES=?, NO_FANTASIA=?, CO_CEP=?, DT_ATUALIZACAO=?, arquivo_origem=?
                WHERE id=?
                """,
                (*params, record_id),
            )
            action = "atualizado"
        else:
            changed = self.model.execute_query(
                """
                INSERT INTO tb_estabelecimento
                    (CO_CNES, NO_FANTASIA, CO_CEP, DT_ATUALIZACAO, arquivo_origem)
                VALUES (?, ?, ?, ?, ?)
                """,
                params,
            )
            action = "criado"
        if not changed:
            raise RuntimeError("Falha ao salvar estabelecimento.")
        return action
