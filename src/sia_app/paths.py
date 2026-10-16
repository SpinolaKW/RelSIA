"""Centralização dos caminhos graváveis do Sistema SIA."""

from __future__ import annotations

import os
import shutil
import sys
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class RuntimePaths:
    """Caminhos usados pela aplicação em código-fonte e no executável."""

    project_root: Path
    data_dir: Path
    database: Path
    config: Path
    logs: Path
    backups: Path

    def ensure_directories(self) -> None:
        for directory in (self.data_dir, self.config.parent, self.logs, self.backups):
            directory.mkdir(parents=True, exist_ok=True)

        # No executável de arquivo único, os dados iniciais ficam temporariamente
        # em _MEIPASS. Eles são copiados apenas se ainda não houver dados do usuário.
        bundle_root = getattr(sys, "_MEIPASS", None)
        if bundle_root:
            seed_dir = Path(bundle_root) / "data"
            for source, target in (
                (seed_dir / "sistema_sia.db", self.database),
                (seed_dir / "config" / "sistema_config.json", self.config),
            ):
                if source.is_file() and not target.exists():
                    target.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(source, target)


def get_runtime_paths() -> RuntimePaths:
    """Retorna caminhos absolutos, independentes do diretório de execução."""

    source_project_root = Path(__file__).resolve().parents[2]
    if getattr(sys, "frozen", False):
        project_root = Path(sys.executable).resolve().parent
    else:
        project_root = source_project_root

    configured_data_dir = os.getenv("SIA_DATA_DIR")
    if configured_data_dir:
        data_dir = Path(configured_data_dir).expanduser().resolve()
    elif getattr(sys, "frozen", False):
        local_app_data = Path(os.getenv("LOCALAPPDATA", Path.home() / "AppData" / "Local"))
        data_dir = local_app_data / "Sistema_SIA" / "data"
    else:
        data_dir = project_root / "data"

    return RuntimePaths(
        project_root=project_root,
        data_dir=data_dir,
        database=data_dir / "sistema_sia.db",
        config=data_dir / "config" / "sistema_config.json",
        logs=data_dir / "logs",
        backups=data_dir / "backups",
    )
