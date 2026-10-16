"""Conexões curtas, leituras concorrentes e transações SQLite."""

from __future__ import annotations

import logging
import sqlite3
import time
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

from sia_app.database.schema import apply_schema
from sia_app.paths import get_runtime_paths

logger = logging.getLogger(__name__)


class DatabaseConnection:
    """Gerencia conexões SQLite sem manter estado global aberto."""

    DEFAULT_TIMEOUT = 30
    DEFAULT_CACHE_SIZE_NORMAL = -65536
    DEFAULT_CACHE_SIZE_BULK = -131072
    DEFAULT_MMAP_SIZE = 134_217_728

    def __init__(self, db_path: str | Path | None = None):
        paths = get_runtime_paths()
        self.db_path = Path(db_path) if db_path is not None else paths.database
        self.db_path = self.db_path.expanduser().resolve()
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

    def _base_connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(
            self.db_path,
            timeout=self.DEFAULT_TIMEOUT,
            check_same_thread=False,
            isolation_level=None,
        )
        conn.row_factory = sqlite3.Row
        return conn

    def connect(self, bulk: bool = False) -> sqlite3.Connection:
        conn = self._base_connect()
        cursor = conn.cursor()
        cursor.execute("PRAGMA foreign_keys = ON")
        cursor.execute("PRAGMA journal_mode = WAL")
        cursor.execute("PRAGMA synchronous = NORMAL")
        cursor.execute("PRAGMA temp_store = MEMORY")
        cursor.execute(
            f"PRAGMA cache_size = {self.DEFAULT_CACHE_SIZE_BULK if bulk else self.DEFAULT_CACHE_SIZE_NORMAL}"
        )
        cursor.execute(f"PRAGMA mmap_size = {self.DEFAULT_MMAP_SIZE}")
        cursor.execute("PRAGMA busy_timeout = 30000")
        return conn

    @contextmanager
    def read(self) -> Iterator[sqlite3.Cursor]:
        """Abre uma conexão somente para consulta, sem bloquear escritores."""

        conn = self.connect()
        try:
            conn.execute("PRAGMA query_only = ON")
            yield conn.cursor()
        finally:
            conn.close()

    @contextmanager
    def txn(self, bulk: bool = False) -> Iterator[sqlite3.Cursor]:
        """Abre uma transação de escrita atômica."""

        conn = self.connect(bulk=bulk)
        cursor = conn.cursor()
        started = time.perf_counter()
        try:
            cursor.execute("BEGIN IMMEDIATE")
            yield cursor
            conn.commit()
            logger.debug("Transação concluída em %.3fs", time.perf_counter() - started)
        except Exception:
            conn.rollback()
            logger.exception("Transação revertida")
            raise
        finally:
            conn.close()

    def initialize_database(self) -> None:
        with self.txn() as cursor:
            apply_schema(cursor)
        logger.info("Banco inicializado em %s", self.db_path)

    def vacuum_analyze(self) -> None:
        """Executa VACUUM fora de transação e atualiza estatísticas."""

        conn = self.connect()
        try:
            conn.execute("VACUUM")
            conn.execute("ANALYZE")
            conn.execute("PRAGMA optimize")
        finally:
            conn.close()

    def post_import_maintenance(self) -> None:
        conn = self.connect()
        try:
            conn.execute("PRAGMA wal_checkpoint(PASSIVE)")
            conn.execute("ANALYZE")
            conn.execute("PRAGMA optimize")
        finally:
            conn.close()

    def get_database_info(self) -> dict[str, Any]:
        with self.read() as cursor:
            info: dict[str, Any] = {
                "tamanho_arquivo": self.db_path.stat().st_size if self.db_path.exists() else 0
            }
            for table in (
                "tb_prd",
                "tb_pa",
                "tb_estabelecimento",
                "config_sistema",
                "tb_usuario",
            ):
                cursor.execute(f"SELECT COUNT(*) AS count FROM {table}")
                info[f"registros_{table}"] = cursor.fetchone()["count"]
            info["journal_mode"] = cursor.execute("PRAGMA journal_mode").fetchone()[0]
            info["synchronous"] = cursor.execute("PRAGMA synchronous").fetchone()[0]
            return info

    def execute_query(self, query: str, parameters: tuple[Any, ...] | None = None) -> list[sqlite3.Row]:
        with self.read() as cursor:
            cursor.execute(query, parameters or ())
            return cursor.fetchall()
