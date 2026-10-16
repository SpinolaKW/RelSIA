"""Leitura e gravação atômica das preferências da aplicação."""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Any

from sia_app.paths import get_runtime_paths

logger = logging.getLogger(__name__)


class AppSettings:
    DEFAULT_SETTINGS = {
        "logo_path": "",
        "inst1": "Prefeitura da Estância Balneária de Praia Grande",
        "inst2": "Secretaria de Saúde Pública",
        "inst3": "Subsecretaria de Planejamento em Saúde • Divisão de Controle",
        "uma_pagina_por_bloco": False,
        "repetir_cabecalho": True,
        "ocultar_zerados": False,
        "ultimo_dir_arquivos": "",
    }
    REQUIRED_SETTINGS = {"inst1"}

    def __init__(self, config_file: str | Path | None = None):
        self.config_file = Path(config_file) if config_file else get_runtime_paths().config
        self.config_file = self.config_file.expanduser().resolve()
        self.settings = self.load_settings()

    def load_settings(self) -> dict[str, Any]:
        if not self.config_file.exists():
            return self.DEFAULT_SETTINGS.copy()
        try:
            with self.config_file.open("r", encoding="utf-8") as stream:
                loaded = json.load(stream)
            if not isinstance(loaded, dict):
                raise ValueError("o conteúdo da configuração precisa ser um objeto JSON")
            return {**self.DEFAULT_SETTINGS, **loaded}
        except (json.JSONDecodeError, OSError, ValueError) as error:
            logger.error("Erro ao carregar %s: %s", self.config_file, error)
            return self.DEFAULT_SETTINGS.copy()

    def save_settings(self) -> bool:
        temporary = self.config_file.with_suffix(self.config_file.suffix + ".tmp")
        try:
            self.config_file.parent.mkdir(parents=True, exist_ok=True)
            with temporary.open("w", encoding="utf-8", newline="\n") as stream:
                json.dump(self.settings, stream, ensure_ascii=False, indent=4, sort_keys=True)
                stream.write("\n")
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary, self.config_file)
            logger.info("Configurações salvas em %s", self.config_file)
            return True
        except OSError as error:
            logger.error("Erro ao salvar %s: %s", self.config_file, error)
            return False

    def get(self, key: str, default: Any = None) -> Any:
        fallback = default if default is not None else self.DEFAULT_SETTINGS.get(key)
        return self.settings.get(key, fallback)

    def set(self, key: str, value: Any) -> None:
        self.settings[key] = value

    def set_multiple(self, **kwargs: Any) -> None:
        self.settings.update(kwargs)

    def reset_to_defaults(self) -> None:
        self.settings = self.DEFAULT_SETTINGS.copy()

    def validate_required_settings(self) -> tuple[bool, str]:
        for setting in self.REQUIRED_SETTINGS:
            value = self.get(setting)
            if value is None or (isinstance(value, str) and not value.strip()):
                return False, f"{setting} é obrigatório. Configure na aba Configurações."
        return True, ""

    def get_all_settings(self) -> dict[str, Any]:
        return self.settings.copy()

    def __contains__(self, key: str) -> bool:
        return key in self.settings

    def __getitem__(self, key: str) -> Any:
        return self.get(key)

    def __setitem__(self, key: str, value: Any) -> None:
        self.set(key, value)
