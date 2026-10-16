"""Autenticação local, perfis de acesso e administração de usuários."""

from __future__ import annotations

import base64
import hashlib
import hmac
import os
import re
import unicodedata
from dataclasses import dataclass
from typing import Any, Iterable, Mapping

from sia_app.database.connection import DatabaseConnection


ROLE_ADMIN = "administrador"
ROLE_VIEWER = "visualizador"
VALID_ROLES = (ROLE_ADMIN, ROLE_VIEWER)

ROLE_LABELS = {
    ROLE_ADMIN: "Administrador",
    ROLE_VIEWER: "Visualizador",
}

ROLE_TABS = {
    ROLE_ADMIN: frozenset(
        {
            "dashboard",
            "file_upload",
            "filters",
            "reports",
            "establishments",
            "prd_editor",
            "database",
            "config",
        }
    ),
    ROLE_VIEWER: frozenset({"dashboard", "filters", "reports"}),
}


class AuthenticationError(ValueError):
    """Erro de validação ou autenticação que pode ser mostrado ao usuário."""


class InvalidCredentialsError(AuthenticationError):
    """Login não autorizado sem revelar se a conta existe."""


@dataclass(frozen=True)
class UserRecord:
    id: int
    name: str
    username: str
    role: str
    active: bool
    created_at: str | None = None
    updated_at: str | None = None
    last_login: str | None = None


@dataclass
class UserSession:
    user_id: int
    name: str
    username: str
    role: str

    @property
    def is_admin(self) -> bool:
        return self.role == ROLE_ADMIN

    @property
    def role_label(self) -> str:
        return ROLE_LABELS.get(self.role, self.role.title())

    def can_access(self, tab_key: str) -> bool:
        return tab_key in ROLE_TABS.get(self.role, frozenset())


class AuthService:
    """Serviço único para senha, sessão e integridade das contas locais."""

    PASSWORD_ITERATIONS = 480_000
    PASSWORD_MIN_LENGTH = 8
    PASSWORD_MAX_LENGTH = 128
    USERNAME_MIN_LENGTH = 3
    USERNAME_MAX_LENGTH = 50
    NAME_MAX_LENGTH = 100
    _USERNAME_PATTERN = re.compile(r"^[^\s]+$")
    _DUMMY_SALT = b"SistemaSIA-auth-dummy-salt"

    def __init__(self, db: DatabaseConnection):
        self.db = db

    @staticmethod
    def normalize_username(username: str) -> str:
        normalized = unicodedata.normalize("NFKC", str(username or "")).strip()
        return normalized.casefold()

    @classmethod
    def validate_username(cls, username: str) -> str:
        clean = unicodedata.normalize("NFKC", str(username or "")).strip()
        if not cls.USERNAME_MIN_LENGTH <= len(clean) <= cls.USERNAME_MAX_LENGTH:
            raise AuthenticationError(
                f"O usuário deve ter entre {cls.USERNAME_MIN_LENGTH} e "
                f"{cls.USERNAME_MAX_LENGTH} caracteres."
            )
        if not cls._USERNAME_PATTERN.fullmatch(clean):
            raise AuthenticationError("O usuário não pode conter espaços.")
        return clean

    @classmethod
    def validate_name(cls, name: str) -> str:
        clean = " ".join(str(name or "").strip().split())
        if not clean:
            raise AuthenticationError("Informe o nome do usuário.")
        if len(clean) > cls.NAME_MAX_LENGTH:
            raise AuthenticationError(
                f"O nome pode ter no máximo {cls.NAME_MAX_LENGTH} caracteres."
            )
        return clean

    @classmethod
    def validate_password(cls, password: str) -> str:
        password = str(password or "")
        if len(password) < cls.PASSWORD_MIN_LENGTH:
            raise AuthenticationError(
                f"A senha deve ter pelo menos {cls.PASSWORD_MIN_LENGTH} caracteres."
            )
        if len(password) > cls.PASSWORD_MAX_LENGTH:
            raise AuthenticationError(
                f"A senha pode ter no máximo {cls.PASSWORD_MAX_LENGTH} caracteres."
            )
        return password

    @classmethod
    def _hash_password(
        cls, password: str, salt: bytes | None = None, iterations: int | None = None
    ) -> tuple[str, str, int]:
        clean_password = cls.validate_password(password)
        salt = salt or os.urandom(32)
        rounds = int(iterations or cls.PASSWORD_ITERATIONS)
        digest = hashlib.pbkdf2_hmac(
            "sha256", clean_password.encode("utf-8"), salt, rounds
        )
        return (
            base64.b64encode(digest).decode("ascii"),
            base64.b64encode(salt).decode("ascii"),
            rounds,
        )

    @staticmethod
    def _session_from_row(row: Any) -> UserSession:
        return UserSession(
            user_id=int(row["id"]),
            name=str(row["nome"]),
            username=str(row["usuario"]),
            role=str(row["perfil"]),
        )

    @staticmethod
    def _record_from_row(row: Any) -> UserRecord:
        return UserRecord(
            id=int(row["id"]),
            name=str(row["nome"]),
            username=str(row["usuario"]),
            role=str(row["perfil"]),
            active=bool(row["ativo"]),
            created_at=row["criado_em"],
            updated_at=row["atualizado_em"],
            last_login=row["ultimo_acesso"],
        )

    def has_users(self) -> bool:
        with self.db.read() as cursor:
            return bool(cursor.execute("SELECT 1 FROM tb_usuario LIMIT 1").fetchone())

    def bootstrap_admin(
        self,
        password: str,
        confirmation: str,
        *,
        name: str = "Administrador",
        username: str = "admin",
    ) -> UserSession:
        """Cria o primeiro administrador somente quando a tabela está vazia."""

        if password != confirmation:
            raise AuthenticationError("A senha e a confirmação não são iguais.")
        clean_name = self.validate_name(name)
        clean_username = self.validate_username(username)
        password_hash, password_salt, iterations = self._hash_password(password)

        with self.db.txn() as cursor:
            if cursor.execute("SELECT 1 FROM tb_usuario LIMIT 1").fetchone():
                raise AuthenticationError(
                    "O primeiro acesso já foi configurado. Entre com um usuário existente."
                )
            cursor.execute(
                """
                INSERT INTO tb_usuario (
                    nome, usuario, usuario_normalizado, senha_hash,
                    senha_salt, senha_iteracoes, perfil, ativo
                ) VALUES (?, ?, ?, ?, ?, ?, ?, 1)
                """,
                (
                    clean_name,
                    clean_username,
                    self.normalize_username(clean_username),
                    password_hash,
                    password_salt,
                    iterations,
                    ROLE_ADMIN,
                ),
            )
            user_id = int(cursor.lastrowid)

        return UserSession(user_id, clean_name, clean_username, ROLE_ADMIN)

    def authenticate(self, username: str, password: str) -> UserSession:
        normalized = self.normalize_username(username)
        with self.db.read() as cursor:
            row = cursor.execute(
                """
                SELECT id, nome, usuario, usuario_normalizado, senha_hash,
                       senha_salt, senha_iteracoes, perfil, ativo
                  FROM tb_usuario
                 WHERE usuario_normalizado = ?
                """,
                (normalized,),
            ).fetchone()

        if row is None:
            hashlib.pbkdf2_hmac(
                "sha256",
                str(password or "").encode("utf-8"),
                self._DUMMY_SALT,
                self.PASSWORD_ITERATIONS,
            )
            raise InvalidCredentialsError("Usuário ou senha inválidos.")

        try:
            salt = base64.b64decode(row["senha_salt"], validate=True)
            expected = base64.b64decode(row["senha_hash"], validate=True)
            candidate = hashlib.pbkdf2_hmac(
                "sha256",
                str(password or "").encode("utf-8"),
                salt,
                int(row["senha_iteracoes"]),
            )
        except (ValueError, TypeError):
            raise InvalidCredentialsError("Usuário ou senha inválidos.") from None

        if not bool(row["ativo"]) or not hmac.compare_digest(candidate, expected):
            raise InvalidCredentialsError("Usuário ou senha inválidos.")

        with self.db.txn() as cursor:
            cursor.execute(
                "UPDATE tb_usuario SET ultimo_acesso = CURRENT_TIMESTAMP WHERE id = ?",
                (row["id"],),
            )
        return self._session_from_row(row)

    def list_users(self) -> list[UserRecord]:
        with self.db.read() as cursor:
            rows = cursor.execute(
                """
                SELECT id, nome, usuario, perfil, ativo,
                       criado_em, atualizado_em, ultimo_acesso
                  FROM tb_usuario
                 ORDER BY CASE perfil WHEN 'administrador' THEN 0 ELSE 1 END,
                          nome COLLATE NOCASE,
                          id
                """
            ).fetchall()
        return [self._record_from_row(row) for row in rows]

    def refresh_session(self, session: UserSession) -> UserSession:
        with self.db.read() as cursor:
            row = cursor.execute(
                "SELECT id, nome, usuario, perfil, ativo FROM tb_usuario WHERE id = ?",
                (session.user_id,),
            ).fetchone()
        if row is None or not bool(row["ativo"]):
            raise AuthenticationError("A conta da sessão não está mais ativa.")
        return self._session_from_row(row)

    def _prepare_changes(
        self,
        drafts: Iterable[Mapping[str, Any]],
        deleted_ids: Iterable[int],
        current_session: UserSession,
    ) -> list[dict[str, Any]]:
        if not current_session.is_admin:
            raise AuthenticationError("Apenas administradores podem alterar usuários.")

        existing = {record.id: record for record in self.list_users()}
        deleted = {int(user_id) for user_id in deleted_ids}
        if current_session.user_id in deleted:
            raise AuthenticationError("O usuário conectado não pode ser excluído.")

        prepared: list[dict[str, Any]] = []
        final_state: dict[object, dict[str, Any]] = {
            user_id: {
                "id": record.id,
                "name": record.name,
                "username": record.username,
                "role": record.role,
                "active": record.active,
            }
            for user_id, record in existing.items()
            if user_id not in deleted
        }

        for index, raw in enumerate(drafts):
            raw_id = raw.get("id")
            user_id = int(raw_id) if raw_id not in (None, "") else None
            if user_id is not None and user_id not in existing:
                raise AuthenticationError("Um usuário alterado não existe mais no banco.")
            if user_id in deleted:
                continue

            name = self.validate_name(str(raw.get("name", "")))
            username = self.validate_username(str(raw.get("username", "")))
            role = str(raw.get("role", "")).strip().lower()
            if role not in VALID_ROLES:
                raise AuthenticationError("Selecione um perfil de usuário válido.")
            active = bool(raw.get("active", True))
            password = str(raw.get("password") or "")
            if user_id is None and not password:
                raise AuthenticationError(f"Informe uma senha para o usuário {username}.")
            if password:
                self.validate_password(password)

            if user_id == current_session.user_id:
                if role != ROLE_ADMIN or not active:
                    raise AuthenticationError(
                        "O administrador conectado não pode ser desativado ou rebaixado."
                    )

            item = {
                "id": user_id,
                "name": name,
                "username": username,
                "normalized": self.normalize_username(username),
                "role": role,
                "active": active,
                "password": password,
            }
            prepared.append(item)
            final_state[user_id if user_id is not None else f"new:{index}"] = item

        normalized_users: dict[str, object] = {}
        for key, user in final_state.items():
            normalized = self.normalize_username(str(user["username"]))
            if normalized in normalized_users:
                raise AuthenticationError(
                    f"O usuário '{user['username']}' já está sendo utilizado."
                )
            normalized_users[normalized] = key

        active_admins = [
            user
            for user in final_state.values()
            if user["role"] == ROLE_ADMIN and bool(user["active"])
        ]
        if not active_admins:
            raise AuthenticationError("O sistema precisa manter um administrador ativo.")

        current = final_state.get(current_session.user_id)
        if current is None or not current["active"] or current["role"] != ROLE_ADMIN:
            raise AuthenticationError("O administrador conectado precisa permanecer ativo.")

        return prepared

    def validate_user_changes(
        self,
        drafts: Iterable[Mapping[str, Any]],
        deleted_ids: Iterable[int],
        current_session: UserSession,
    ) -> None:
        self._prepare_changes(drafts, deleted_ids, current_session)

    def save_user_changes(
        self,
        drafts: Iterable[Mapping[str, Any]],
        deleted_ids: Iterable[int],
        current_session: UserSession,
    ) -> UserSession:
        """Aplica inclusões, alterações e exclusões em uma única transação."""

        deleted = {int(user_id) for user_id in deleted_ids}
        prepared = self._prepare_changes(drafts, deleted, current_session)
        existing_updates = [item for item in prepared if item["id"] is not None]

        with self.db.txn() as cursor:
            if deleted:
                placeholders = ",".join("?" for _ in deleted)
                cursor.execute(
                    f"DELETE FROM tb_usuario WHERE id IN ({placeholders})",
                    tuple(sorted(deleted)),
                )

            # Libera temporariamente as chaves normalizadas para permitir trocas
            # de nomes de usuário sem violar a restrição UNIQUE no meio do save.
            for item in existing_updates:
                cursor.execute(
                    "UPDATE tb_usuario SET usuario_normalizado = ? WHERE id = ?",
                    (f"__sia_pending_{item['id']}__", item["id"]),
                )

            for item in prepared:
                password_values: tuple[str, str, int] | None = None
                if item["password"]:
                    password_values = self._hash_password(item["password"])

                if item["id"] is None:
                    assert password_values is not None
                    cursor.execute(
                        """
                        INSERT INTO tb_usuario (
                            nome, usuario, usuario_normalizado, senha_hash,
                            senha_salt, senha_iteracoes, perfil, ativo
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            item["name"],
                            item["username"],
                            item["normalized"],
                            *password_values,
                            item["role"],
                            int(item["active"]),
                        ),
                    )
                    continue

                common = (
                    item["name"],
                    item["username"],
                    item["normalized"],
                    item["role"],
                    int(item["active"]),
                    item["id"],
                )
                if password_values is None:
                    cursor.execute(
                        """
                        UPDATE tb_usuario
                           SET nome = ?, usuario = ?, usuario_normalizado = ?,
                               perfil = ?, ativo = ?, atualizado_em = CURRENT_TIMESTAMP
                         WHERE id = ?
                        """,
                        common,
                    )
                else:
                    cursor.execute(
                        """
                        UPDATE tb_usuario
                           SET nome = ?, usuario = ?, usuario_normalizado = ?,
                               perfil = ?, ativo = ?, senha_hash = ?,
                               senha_salt = ?, senha_iteracoes = ?,
                               atualizado_em = CURRENT_TIMESTAMP
                         WHERE id = ?
                        """,
                        (*common[:-1], *password_values, common[-1]),
                    )

        return self.refresh_session(current_session)
