"""Backup e restauração consistentes do banco SQLite."""

from __future__ import annotations

import logging
import shutil
import sqlite3
import tempfile
import zipfile
from datetime import datetime
from pathlib import Path
from typing import Optional

from sia_app.database.connection import DatabaseConnection
from sia_app.paths import get_runtime_paths

logger = logging.getLogger(__name__)


class BackupManager:
    BACKUP_EXTENSION_SIMPLE = ".sqlite.backup"
    BACKUP_EXTENSION_ZIP = ".zip"
    DATE_FORMAT = "%Y%m%d_%H%M%S"
    USER_COLUMNS = (
        "id",
        "nome",
        "usuario",
        "usuario_normalizado",
        "senha_hash",
        "senha_salt",
        "senha_iteracoes",
        "perfil",
        "ativo",
        "criado_em",
        "atualizado_em",
        "ultimo_acesso",
    )

    def __init__(
        self,
        db_path: str | Path | None = None,
        backup_dir: str | Path | None = None,
    ):
        paths = get_runtime_paths()
        self.db_path = Path(db_path) if db_path is not None else paths.database
        self.backup_dir = Path(backup_dir) if backup_dir is not None else paths.backups
        self.db_path = self.db_path.expanduser().resolve()
        self.backup_dir = self.backup_dir.expanduser().resolve()
        self.backup_dir.mkdir(parents=True, exist_ok=True)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

    def _generate_backup_filename(self, extension: str) -> str:
        return f"backup_{datetime.now().strftime(self.DATE_FORMAT)}{extension}"

    @staticmethod
    def _verify_database(path: Path) -> tuple[bool, str]:
        try:
            source = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
            try:
                result = source.execute("PRAGMA quick_check").fetchone()[0]
            finally:
                source.close()
            return result == "ok", str(result)
        except sqlite3.Error as error:
            return False, str(error)

    def _sqlite_backup(self, destination: Path) -> None:
        source = sqlite3.connect(f"file:{self.db_path}?mode=ro", uri=True)
        target = sqlite3.connect(destination)
        try:
            source.backup(target)
        finally:
            target.close()
            source.close()

    def criar_backup_simples(self) -> tuple[bool, str]:
        if not self.db_path.is_file():
            return False, f"Banco não encontrado: {self.db_path}"
        destination = self.backup_dir / self._generate_backup_filename(
            self.BACKUP_EXTENSION_SIMPLE
        )
        try:
            self._sqlite_backup(destination)
            valid, detail = self._verify_database(destination)
            if not valid:
                destination.unlink(missing_ok=True)
                return False, f"O backup não passou na verificação: {detail}"
            logger.info("Backup criado: %s", destination)
            return True, f"Backup criado: {destination.name}"
        except (OSError, sqlite3.Error) as error:
            logger.exception("Falha ao criar backup")
            return False, f"Erro ao criar backup: {error}"

    def criar_backup_compactado(self, senha: Optional[str] = None) -> tuple[bool, str]:
        if senha:
            return False, "O formato ZIP padrão não oferece criptografia segura. Crie o backup sem senha."
        if not self.db_path.is_file():
            return False, f"Banco não encontrado: {self.db_path}"

        destination = self.backup_dir / self._generate_backup_filename(self.BACKUP_EXTENSION_ZIP)
        try:
            with tempfile.TemporaryDirectory(prefix="sia_backup_") as temp_dir:
                snapshot = Path(temp_dir) / "sistema_sia.db"
                self._sqlite_backup(snapshot)
                valid, detail = self._verify_database(snapshot)
                if not valid:
                    return False, f"O backup não passou na verificação: {detail}"
                with zipfile.ZipFile(destination, "w", zipfile.ZIP_DEFLATED) as archive:
                    archive.write(snapshot, arcname="sistema_sia.db")
            logger.info("Backup compactado criado: %s", destination)
            return True, f"Backup ZIP criado: {destination.name}"
        except (OSError, sqlite3.Error, zipfile.BadZipFile) as error:
            logger.exception("Falha ao criar backup compactado")
            return False, f"Erro ao criar backup ZIP: {error}"

    def _create_pre_restore_backup(self) -> None:
        if not self.db_path.exists():
            return
        safety_name = f"safety_backup_{datetime.now().strftime(self.DATE_FORMAT)}{self.BACKUP_EXTENSION_SIMPLE}"
        self._sqlite_backup(self.backup_dir / safety_name)

    def _snapshot_current_users(self) -> list[tuple]:
        """Mantém as contas atuais fora da restauração dos dados operacionais."""
        if not self.db_path.is_file():
            return []
        connection = sqlite3.connect(self.db_path)
        try:
            exists = connection.execute(
                "SELECT 1 FROM sqlite_master WHERE type='table' AND name='tb_usuario'"
            ).fetchone()
            if not exists:
                return []
            columns = ", ".join(self.USER_COLUMNS)
            return [tuple(row) for row in connection.execute(f"SELECT {columns} FROM tb_usuario")]
        finally:
            connection.close()

    def _restore_current_users(self, users: list[tuple]) -> None:
        if not users:
            return
        database = DatabaseConnection(self.db_path)
        placeholders = ", ".join("?" for _ in self.USER_COLUMNS)
        columns = ", ".join(self.USER_COLUMNS)
        with database.txn() as cursor:
            cursor.execute("DELETE FROM tb_usuario")
            cursor.executemany(
                f"INSERT INTO tb_usuario ({columns}) VALUES ({placeholders})",
                users,
            )

    @staticmethod
    def _database_from_zip(archive_path: Path, destination: Path) -> tuple[bool, str]:
        try:
            with zipfile.ZipFile(archive_path, "r") as archive:
                candidates = [
                    info
                    for info in archive.infolist()
                    if not info.is_dir() and Path(info.filename).suffix.lower() in {".db", ".sqlite", ".backup"}
                ]
                if len(candidates) != 1:
                    return False, "O ZIP deve conter exatamente um banco SQLite."
                with archive.open(candidates[0], "r") as source, destination.open("wb") as target:
                    shutil.copyfileobj(source, target)
            return True, ""
        except (OSError, zipfile.BadZipFile) as error:
            return False, str(error)

    def restaurar_backup(self, backup_path: str | Path) -> tuple[bool, str]:
        backup_file = Path(backup_path).expanduser().resolve()
        if not backup_file.is_file():
            return False, f"Arquivo de backup não encontrado: {backup_file}"

        try:
            current_users = self._snapshot_current_users()
            with tempfile.TemporaryDirectory(prefix="sia_restore_") as temp_dir:
                candidate = Path(temp_dir) / "restore.sqlite"
                if backup_file.suffix.lower() == ".zip":
                    success, message = self._database_from_zip(backup_file, candidate)
                    if not success:
                        return False, message
                else:
                    shutil.copy2(backup_file, candidate)

                valid, detail = self._verify_database(candidate)
                if not valid:
                    return False, f"Backup inválido ou corrompido: {detail}"

                self._create_pre_restore_backup()
                source = sqlite3.connect(f"file:{candidate}?mode=ro", uri=True)
                target = sqlite3.connect(self.db_path)
                try:
                    source.backup(target)
                finally:
                    target.close()
                    source.close()

                # Backups de versões anteriores voltam já compatíveis com o
                # schema atual, sem exigir reinício da aplicação.
                DatabaseConnection(self.db_path).initialize_database()
                self._restore_current_users(current_users)
                valid, detail = self._verify_database(self.db_path)
                if not valid:
                    raise sqlite3.DatabaseError(
                        f"o banco restaurado não passou na verificação final: {detail}"
                    )

            logger.info("Banco restaurado a partir de %s", backup_file)
            return True, "Banco restaurado e verificado com sucesso."
        except (OSError, sqlite3.Error) as error:
            logger.exception("Falha ao restaurar backup")
            return False, f"Erro ao restaurar backup: {error}"

    def listar_backups(self) -> list[Path]:
        backups = list(self.backup_dir.glob(f"*{self.BACKUP_EXTENSION_SIMPLE}"))
        backups.extend(self.backup_dir.glob(f"*{self.BACKUP_EXTENSION_ZIP}"))
        return sorted(backups, key=lambda path: path.stat().st_mtime, reverse=True)

    def excluir_backup(self, backup_path: str | Path) -> tuple[bool, str]:
        backup_file = Path(backup_path).expanduser().resolve()
        try:
            backup_file.relative_to(self.backup_dir)
        except ValueError:
            return False, "Só é permitido excluir arquivos da pasta de backups do sistema."
        if not backup_file.is_file():
            return False, "Arquivo de backup não encontrado."
        try:
            backup_file.unlink()
            return True, "Backup excluído com sucesso."
        except OSError as error:
            return False, f"Erro ao excluir backup: {error}"


def make_backup_sqlite(db_path: str | Path | None = None) -> tuple[bool, str]:
    return BackupManager(db_path).criar_backup_simples()


def make_backup_zip(db_path: str | Path | None = None) -> tuple[bool, str]:
    return BackupManager(db_path).criar_backup_compactado()


def restore_from_backup(
    backup_path: str | Path, db_path: str | Path | None = None
) -> tuple[bool, str]:
    return BackupManager(db_path).restaurar_backup(backup_path)
