"""Schema e migrações idempotentes do banco SQLite."""

from __future__ import annotations

import sqlite3
from collections.abc import Iterable

SCHEMA_VERSION = 4

TABLE_STATEMENTS = (
    """
    CREATE TABLE IF NOT EXISTS tb_prd (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        PRD_UID TEXT NOT NULL,
        PRD_CMP TEXT NOT NULL,
        PRD_PA TEXT NOT NULL,
        PRD_CBO TEXT NOT NULL DEFAULT '',
        PRD_TPFIN TEXT,
        PRD_CPX TEXT,
        PRD_QT_P REAL DEFAULT 0,
        PRD_QT_A REAL NOT NULL DEFAULT 0,
        PRD_VL_P REAL DEFAULT 0,
        PRD_VL_A REAL DEFAULT 0,
        arquivo_origem TEXT,
        data_importacao DATETIME DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(PRD_UID, PRD_CMP, PRD_PA, PRD_CBO)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS tb_pa (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        PA_ID TEXT,
        PA_DV TEXT,
        PA_DC TEXT,
        PA_TOTAL REAL,
        PA_CTF TEXT,
        PA_CPX TEXT,
        PROC TEXT GENERATED ALWAYS AS (PA_ID || COALESCE(PA_DV, '')) VIRTUAL,
        arquivo_origem TEXT,
        data_importacao DATETIME DEFAULT CURRENT_TIMESTAMP
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS tb_estabelecimento (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        CO_CNES TEXT,
        NO_FANTASIA TEXT,
        CO_CEP TEXT,
        DT_ATUALIZACAO TEXT,
        arquivo_origem TEXT,
        data_importacao DATETIME DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(CO_CNES)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS tb_importacao_prd (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        arquivo_origem TEXT NOT NULL,
        hash_arquivo TEXT NOT NULL UNIQUE,
        competencia_principal TEXT,
        total_principal INTEGER DEFAULT 0,
        total_retroativo INTEGER DEFAULT 0,
        data_importacao DATETIME DEFAULT CURRENT_TIMESTAMP
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS tb_prd_retro_controle (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        competencia_origem TEXT NOT NULL,
        PRD_UID TEXT NOT NULL,
        PRD_CMP TEXT NOT NULL,
        PRD_PA TEXT NOT NULL,
        PRD_CBO TEXT NOT NULL DEFAULT '',
        PRD_TPFIN TEXT,
        PRD_CPX TEXT,
        PRD_QT_P REAL DEFAULT 0,
        PRD_QT_A REAL DEFAULT 0,
        PRD_VL_P REAL DEFAULT 0,
        PRD_VL_A REAL DEFAULT 0,
        arquivo_origem TEXT,
        data_importacao DATETIME DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(competencia_origem, PRD_UID, PRD_CMP, PRD_PA, PRD_CBO)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS config_sistema (
        id INTEGER PRIMARY KEY,
        logo_path TEXT,
        inst1 TEXT,
        inst2 TEXT,
        inst3 TEXT,
        uma_pagina_por_bloco INTEGER DEFAULT 0,
        repetir_cabecalho INTEGER DEFAULT 1,
        ocultar_zerados INTEGER DEFAULT 0,
        ultimo_dir_arquivos TEXT,
        data_atualizacao DATETIME DEFAULT CURRENT_TIMESTAMP
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS tb_usuario (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        nome TEXT NOT NULL,
        usuario TEXT NOT NULL,
        usuario_normalizado TEXT NOT NULL UNIQUE,
        senha_hash TEXT NOT NULL,
        senha_salt TEXT NOT NULL,
        senha_iteracoes INTEGER NOT NULL,
        perfil TEXT NOT NULL CHECK (perfil IN ('administrador', 'visualizador')),
        ativo INTEGER NOT NULL DEFAULT 1 CHECK (ativo IN (0, 1)),
        criado_em DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
        atualizado_em DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
        ultimo_acesso DATETIME
    )
    """,
)

COLUMN_MIGRATIONS = {
    "tb_prd": {
        "PRD_CBO": "TEXT NOT NULL DEFAULT ''",
        "PRD_TPFIN": "TEXT",
        "PRD_CPX": "TEXT",
        "PRD_QT_P": "REAL DEFAULT 0",
        "PRD_QT_A": "REAL NOT NULL DEFAULT 0",
        "PRD_VL_P": "REAL DEFAULT 0",
        "PRD_VL_A": "REAL DEFAULT 0",
        "arquivo_origem": "TEXT",
        "data_importacao": "DATETIME",
    },
    "tb_pa": {
        "PA_CTF": "TEXT",
        "PA_CPX": "TEXT",
        "PROC": "TEXT GENERATED ALWAYS AS (PA_ID || COALESCE(PA_DV, '')) VIRTUAL",
        "arquivo_origem": "TEXT",
        "data_importacao": "DATETIME",
    },
    "tb_estabelecimento": {
        "arquivo_origem": "TEXT",
        "data_importacao": "DATETIME",
    },
    "tb_prd_retro_controle": {
        "PRD_CBO": "TEXT NOT NULL DEFAULT ''",
        "PRD_TPFIN": "TEXT",
        "PRD_CPX": "TEXT",
        "PRD_QT_P": "REAL DEFAULT 0",
        "PRD_QT_A": "REAL DEFAULT 0",
        "PRD_VL_P": "REAL DEFAULT 0",
        "PRD_VL_A": "REAL DEFAULT 0",
        "arquivo_origem": "TEXT",
        "data_importacao": "DATETIME",
    },
}

INDEX_STATEMENTS = (
    "CREATE INDEX IF NOT EXISTS idx_prd_uid ON tb_prd(PRD_UID)",
    "CREATE INDEX IF NOT EXISTS idx_prd_cmp ON tb_prd(PRD_CMP)",
    "CREATE INDEX IF NOT EXISTS idx_prd_pa ON tb_prd(PRD_PA)",
    "CREATE INDEX IF NOT EXISTS idx_prd_tpfin ON tb_prd(PRD_TPFIN)",
    "CREATE INDEX IF NOT EXISTS idx_prd_cpx ON tb_prd(PRD_CPX)",
    "CREATE INDEX IF NOT EXISTS idx_prd_cbo ON tb_prd(PRD_CBO)",
    "CREATE UNIQUE INDEX IF NOT EXISTS idx_pa_proc ON tb_pa(PROC)",
    "CREATE INDEX IF NOT EXISTS idx_pa_id_dv ON tb_pa(PA_ID, PA_DV)",
    "CREATE INDEX IF NOT EXISTS idx_pa_arquivo ON tb_pa(arquivo_origem)",
    "CREATE INDEX IF NOT EXISTS idx_pa_ctf ON tb_pa(PA_CTF)",
    "CREATE INDEX IF NOT EXISTS idx_pa_cpx ON tb_pa(PA_CPX)",
    "CREATE INDEX IF NOT EXISTS idx_estab_cnes ON tb_estabelecimento(CO_CNES)",
    "CREATE INDEX IF NOT EXISTS idx_estab_arquivo ON tb_estabelecimento(arquivo_origem)",
    "CREATE INDEX IF NOT EXISTS idx_importacao_prd_hash ON tb_importacao_prd(hash_arquivo)",
    "CREATE INDEX IF NOT EXISTS idx_importacao_prd_cmp ON tb_importacao_prd(competencia_principal)",
    "CREATE INDEX IF NOT EXISTS idx_retro_origem ON tb_prd_retro_controle(competencia_origem)",
    "CREATE INDEX IF NOT EXISTS idx_retro_chave ON tb_prd_retro_controle(PRD_UID, PRD_CMP, PRD_PA, PRD_CBO)",
    "CREATE INDEX IF NOT EXISTS idx_usuario_perfil_ativo ON tb_usuario(perfil, ativo)",
)


def _column_names(cursor: sqlite3.Cursor, table: str) -> set[str]:
    return {str(row[1]) for row in cursor.execute(f"PRAGMA table_xinfo({table})")}


def _unique_index_matches(
    cursor: sqlite3.Cursor, table: str, expected_columns: Iterable[str]
) -> bool:
    expected = list(expected_columns)
    for index in cursor.execute(f"PRAGMA index_list({table})").fetchall():
        if not index[2]:
            continue
        columns = [row[2] for row in cursor.execute(f"PRAGMA index_info({index[1]})")]
        if columns == expected:
            return True
    return False


def apply_schema(cursor: sqlite3.Cursor) -> None:
    """Cria o schema e atualiza bancos de versões anteriores."""

    for statement in TABLE_STATEMENTS:
        cursor.execute(statement)

    for table, columns in COLUMN_MIGRATIONS.items():
        existing = _column_names(cursor, table)
        for column, definition in columns.items():
            if column not in existing:
                cursor.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")

    unique_keys = (
        ("tb_prd", "uq_prd_key_v3", ("PRD_UID", "PRD_CMP", "PRD_PA", "PRD_CBO")),
        (
            "tb_prd_retro_controle",
            "uq_retro_key_v3",
            ("competencia_origem", "PRD_UID", "PRD_CMP", "PRD_PA", "PRD_CBO"),
        ),
    )
    for table, index_name, columns in unique_keys:
        if not _unique_index_matches(cursor, table, columns):
            cursor.execute(
                f"CREATE UNIQUE INDEX {index_name} ON {table} ({', '.join(columns)})"
            )

    for statement in INDEX_STATEMENTS:
        cursor.execute(statement)

    cursor.execute(
        """
        INSERT OR IGNORE INTO config_sistema (id, inst1, inst2, inst3)
        VALUES (1, ?, ?, ?)
        """,
        (
            "Prefeitura da Estância Balneária de Praia Grande",
            "Secretaria de Saúde Pública",
            "Subsecretaria de Planejamento em Saúde • Divisão de Controle",
        ),
    )
    cursor.execute(f"PRAGMA user_version = {SCHEMA_VERSION}")
