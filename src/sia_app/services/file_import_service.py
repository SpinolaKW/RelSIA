"""Orquestra validação e importação de arquivos fora da interface gráfica."""

from __future__ import annotations

import hashlib
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, List, Sequence, Tuple


FileItem = Tuple[str, str]
ProgressCallback = Callable[[int, int, str], None]


@dataclass(frozen=True)
class ImportSummary:
    success_count: int
    total_files: int


class FileImportService:
    """Contém o fluxo de importação; a aba apenas exibe progresso e mensagens."""

    def __init__(self, db, dbf_converter, csv_importer, validator, logger):
        self.db = db
        self.dbf_converter = dbf_converter
        self.csv_importer = csv_importer
        self.validator = validator
        self.logger = logger

    def validate_files(self, files: Sequence[FileItem]):
        results = []
        for file_type, file_path in files:
            try:
                if file_type in ("PRD", "PA"):
                    valid, message = self.validator.validar_arquivo_dbf(
                        file_path, file_type.lower()
                    )
                else:
                    valid, message = self.validator.validar_arquivo_csv(
                        file_path, "estabelecimentos"
                    )
                results.append((file_type, file_path, bool(valid), str(message)))
            except Exception as exc:
                results.append((file_type, file_path, False, f"Erro na validação - {exc}"))
        return results

    def process_files(
        self,
        files: Sequence[FileItem],
        progress: ProgressCallback,
    ) -> ImportSummary:
        self._validate_before_processing(files)
        ordered = self.order_files(files)
        success_count = 0
        total = len(ordered)
        for index, (file_type, file_path) in enumerate(ordered, 1):
            file_name = os.path.basename(file_path)
            progress(index, total, f"Processando {file_name}")
            self.logger.info(f"📦 Processando {file_type}: {file_name}")
            success, message = self._process_one(file_type, file_path)
            if success:
                success_count += 1
                self.logger.info(f"✅ {file_type} processado: {message}")
            else:
                self.logger.error(f"❌ {file_type} falhou: {message}")
        return ImportSummary(success_count=success_count, total_files=total)

    def order_files(self, files: Sequence[FileItem]) -> List[FileItem]:
        pa: List[FileItem] = []
        cnes: List[FileItem] = []
        prd = []
        others: List[FileItem] = []
        for file_type, file_path in files:
            if file_type == "PA":
                pa.append((file_type, file_path))
            elif file_type == "CNES":
                cnes.append((file_type, file_path))
            elif file_type == "PRD":
                prd.append((self._main_competence(file_path), file_type, file_path))
            else:
                others.append((file_type, file_path))
        prd.sort(key=lambda item: (item[0], os.path.basename(item[2]).lower()))
        if prd:
            self.logger.info("📌 Ordem dos arquivos PRD após ordenação:")
            for competence, _file_type, file_path in prd:
                self.logger.info(f"   {competence} - {os.path.basename(file_path)}")
        return pa + cnes + [(kind, path) for _comp, kind, path in prd] + others

    def _main_competence(self, file_path: str) -> str:
        try:
            success, frame, message = self.dbf_converter.dbf_to_dataframe(file_path, "prd")
            if not success or frame is None or frame.empty or "PRD_CMP" not in frame.columns:
                self.logger.warning(
                    f"Não foi possível identificar competência principal de "
                    f"{os.path.basename(file_path)}: {message}"
                )
                return "999999"
            competence = frame["PRD_CMP"].astype(str).str.strip().value_counts().idxmax()
            return str(competence).strip()
        except Exception as exc:
            self.logger.warning(
                f"Erro ao identificar competência principal de "
                f"{os.path.basename(file_path)}: {exc}"
            )
            return "999999"

    @staticmethod
    def _file_identifier(file_path: str) -> str:
        sha256 = hashlib.sha256()
        with open(file_path, "rb") as stream:
            for block in iter(lambda: stream.read(1024 * 1024), b""):
                sha256.update(block)
        return f"{os.path.basename(file_path)}|{sha256.hexdigest()[:16]}"

    def _process_one(self, file_type: str, file_path: str) -> Tuple[bool, str]:
        handlers = {
            "PRD": self._process_prd,
            "PA": self._process_pa,
            "CNES": self._process_cnes,
        }
        handler = handlers.get(file_type)
        if handler is None:
            return False, f"Tipo de arquivo desconhecido: {file_type}"
        return self._safe_call(handler, file_path)

    def _process_prd(self, file_path: str) -> Tuple[bool, str]:
        identifier = self._file_identifier(file_path)
        self.logger.info(f"📄 Identificador PRD: {os.path.basename(file_path)} -> {identifier}")
        success, frame, message = self.dbf_converter.dbf_to_dataframe(file_path, "prd")
        if not success:
            return False, str(message)
        return self.csv_importer.importar_dados_prd(frame, identifier)

    def _process_pa(self, file_path: str) -> Tuple[bool, str]:
        success, frame, message = self.dbf_converter.dbf_to_dataframe(file_path, "pa")
        if not success:
            return False, str(message)
        return self.csv_importer.importar_dados_pa(frame, os.path.basename(file_path))

    def _process_cnes(self, file_path: str) -> Tuple[bool, str]:
        path = Path(file_path)
        if not path.is_file():
            return False, "Arquivo CNES não selecionado ou inexistente"
        if path.suffix.lower() not in (".csv", ".txt"):
            return False, f"Extensão inválida para CNES: {path.suffix}"
        return self.csv_importer.importar_estabelecimentos(file_path, path.name)

    @staticmethod
    def _validate_before_processing(files: Sequence[FileItem]):
        for _file_type, file_path in files:
            if not os.path.isfile(file_path):
                raise FileNotFoundError(f"Arquivo não encontrado: {file_path}")
            if os.path.getsize(file_path) == 0:
                raise ValueError(f"Arquivo vazio: {file_path}")

    def _safe_call(self, function, *args) -> Tuple[bool, str]:
        try:
            result = function(*args)
            if not isinstance(result, tuple) or len(result) != 2:
                return False, f"Retorno inválido de {function.__name__}: {result!r}"
            success, message = result
            if not isinstance(success, bool):
                return False, f"Tipo inválido para success em {function.__name__}"
            return success, str(message)
        except Exception as exc:
            self.logger.exception(f"Exceção em {function.__name__}")
            return False, f"Exceção em {function.__name__}: {exc}"
