"""
MAME Set Builder - Database app/database/database.py
===========================

Gerenciamento centralizado do banco SQLite da aplicação.

Responsabilidades
-----------------
- Criar o diretório do banco;
- Abrir e configurar a conexão SQLite;
- Carregar o schema oficial;
- Executar migrações de bancos antigos;
- Garantir integridade referencial;
- Disponibilizar operações SQL auxiliares;
- Gerenciar transações;
- Fechar corretamente a conexão.

Schema oficial
--------------

    app/database/migrations/schema.sql

IMPORTANTE
----------
O banco SQLite é a fonte persistente do dataset MAME utilizado pela aplicação.

A estrutura do banco deve permanecer compatível com:

    listxml_parser
        |
        v
    database
        |
        +--> filter_service
        |
        +--> listxml_export_service
        |
        +--> rom_scanner
        |
        +--> reconstruction_service

O schema oficial possui as entidades principais do dataset MAME,
incluindo máquinas, ROMs, disks/CHDs, BIOS, devices, chips,
displays, inputs, controls, features, software lists, slots,
slot options, dependências de CHD e categorias.
"""

from __future__ import annotations

import logging
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterable, Iterator, Sequence

from app.config.app_config import AppConfig

logger = logging.getLogger(__name__)


class Database:
    """
    Gerenciador de conexão e operações SQLite do MAME Set Builder.

    A classe mantém uma única conexão por instância.

    Exemplo
    -------
    ::

        db = Database()
        conn = db.connect()

        rows = db.fetchall(
            "SELECT * FROM machine LIMIT 10"
        )

        db.close()

    Também pode ser utilizada com context manager:

    ::

        with Database() as db:
            rows = db.fetchall(
                "SELECT * FROM machine"
            )
    """

    # ------------------------------------------------------------------
    # CONFIGURAÇÃO
    # ------------------------------------------------------------------

    SCHEMA_VERSION = 1

    REQUIRED_TABLES = (
        "mame_installation",
        "machine",
        "rom",
        "disk",
        "bios",
        "device",
        "chip",
        "display",
        "input",
        "control",
        "feature",
        "software_list",
        "slot",
        "slot_option",
        "chd_dependency",
        "category",
        "machine_category",
        "filter_profile",
    )

    def __init__(
        self,
        db_path: Path | str | None = None,
    ) -> None:
        """
        Inicializa o gerenciador do banco.

        Args:
            db_path:
                Caminho opcional para o banco SQLite.

                Quando não informado, o caminho definido por
                ``AppConfig.db_path`` será utilizado.
        """

        if db_path is None:
            app_config = AppConfig()
            db_path = app_config.db_path

        self.db_path = Path(db_path)

        self.conn: sqlite3.Connection | None = None

        logger.info(
            "Database inicializado: %s",
            self.db_path,
        )

    # ------------------------------------------------------------------
    # PROPRIEDADES
    # ------------------------------------------------------------------

    @property
    def is_connected(self) -> bool:
        """
        Informa se existe uma conexão SQLite ativa.

        Returns:
            ``True`` quando conectado.
        """

        return self.conn is not None

    # ------------------------------------------------------------------
    # CONEXÃO
    # ------------------------------------------------------------------

    def connect(self) -> sqlite3.Connection:
        """
        Abre e inicializa a conexão SQLite.

        O método é idempotente: chamadas posteriores retornam a mesma
        conexão enquanto ela estiver aberta.

        Returns:
            Conexão SQLite configurada.

        Raises:
            sqlite3.Error:
                Caso ocorra erro durante a abertura, criação ou migração
                do banco.
            RuntimeError:
                Caso o schema oficial esteja ausente ou inválido.
        """

        if self.conn is not None:
            return self.conn

        try:
            self.db_path.parent.mkdir(
                parents=True,
                exist_ok=True,
            )

            logger.info(
                "Abrindo banco SQLite: %s",
                self.db_path,
            )

            self.conn = sqlite3.connect(
                str(self.db_path),
                timeout=30.0,
            )

            self.conn.row_factory = sqlite3.Row

            self._configure_connection()

            self._initialize_schema()

            logger.info(
                "Banco SQLite inicializado com sucesso."
            )

            return self.conn

        except Exception:
            logger.exception(
                "Falha ao inicializar banco SQLite: %s",
                self.db_path,
            )

            self._close_connection_safely()

            raise

    def _configure_connection(self) -> None:
        """
        Configura pragmas e propriedades da conexão SQLite.

        Configurações utilizadas:

        - foreign_keys:
          garante integridade referencial;

        - journal_mode=WAL:
          melhora comportamento de leitura/escrita;

        - synchronous=NORMAL:
          equilíbrio entre desempenho e segurança;

        - busy_timeout:
          evita falhas imediatas em situações de concorrência.
        """

        if self.conn is None:
            raise RuntimeError(
                "Banco não conectado."
            )

        self.conn.execute(
            "PRAGMA foreign_keys = ON"
        )

        self.conn.execute(
            "PRAGMA journal_mode = WAL"
        )

        self.conn.execute(
            "PRAGMA synchronous = NORMAL"
        )

        self.conn.execute(
            "PRAGMA busy_timeout = 30000"
        )

    # ------------------------------------------------------------------
    # SCHEMA
    # ------------------------------------------------------------------

    def _get_schema_path(self) -> Path:
        """
        Retorna o caminho do schema oficial.

        Estrutura esperada:

            app/
                database/
                    database.py
                    migrations/
                        schema.sql

        Returns:
            Caminho absoluto do ``schema.sql``.
        """

        schema_path = (
            Path(__file__).resolve().parent
            / "migrations"
            / "schema.sql"
        )

        return schema_path

    def _initialize_schema(self) -> None:
        """
        Carrega o schema oficial e executa as migrações.

        O schema utiliza ``CREATE TABLE IF NOT EXISTS`` e pode ser
        executado sobre um banco já existente.

        Entretanto, alterações de estrutura de tabelas existentes
        precisam ser tratadas explicitamente por migrações.
        """

        if self.conn is None:
            raise RuntimeError(
                "Banco não conectado."
            )

        schema_path = self._get_schema_path()

        logger.info(
            "Schema SQLite: %s",
            schema_path,
        )

        if not schema_path.is_file():
            raise FileNotFoundError(
                "Schema oficial do banco não encontrado: "
                f"{schema_path}"
            )

        try:
            schema_sql = schema_path.read_text(
                encoding="utf-8",
            )

        except OSError as exc:
            raise RuntimeError(
                "Não foi possível ler o schema SQLite: "
                f"{schema_path}"
            ) from exc

        if not schema_sql.strip():
            raise RuntimeError(
                f"Schema SQLite vazio: {schema_path}"
            )

        try:
            self.conn.executescript(
                schema_sql
            )

            self._migrate_schema()

            self._validate_schema()

            self.conn.execute(
                f"PRAGMA user_version = {self.SCHEMA_VERSION}"
            )

            self.conn.commit()

        except Exception:
            self.conn.rollback()

            logger.exception(
                "Erro ao inicializar schema SQLite."
            )

            raise

    # ------------------------------------------------------------------
    # MIGRAÇÕES
    # ------------------------------------------------------------------

    def _migrate_schema(self) -> None:
        """
        Executa migrações necessárias para bancos antigos.

        A versão do projeto introduziu mudanças importantes na tabela
        ``disk``:

        Versão antiga:

            disk.index

        Versão atual:

            disk.disk_index
            disk.size

        Também garantimos aqui que estruturas essenciais existam.

        A função é deliberadamente conservadora: não remove dados
        existentes.
        """

        if self.conn is None:
            raise RuntimeError(
                "Banco não conectado."
            )

        self._migrate_disk_table()

        # O schema oficial cria todas as demais tabelas.
        # Esta chamada serve apenas para registrar o estado atual
        # durante o processo de migração.
        logger.debug(
            "Migração de schema concluída."
        )

    def _migrate_disk_table(self) -> None:
        """
        Migra a estrutura antiga de ``disk``.

        Alterações suportadas:

        ``index`` -> ``disk_index``

        e:

        adiciona ``size`` quando ausente.

        A migração não elimina registros existentes.
        """

        if self.conn is None:
            raise RuntimeError(
                "Banco não conectado."
            )

        columns = self._get_table_columns(
            "disk"
        )

        if not columns:
            logger.warning(
                "Tabela disk não encontrada durante migração."
            )
            return

        # --------------------------------------------------------------
        # index -> disk_index
        # --------------------------------------------------------------

        has_old_index = "index" in columns
        has_new_index = "disk_index" in columns

        if has_old_index and not has_new_index:
            logger.info(
                "Migrando disk.index -> disk.disk_index."
            )

            try:
                self.conn.execute(
                    """
                    ALTER TABLE disk
                    RENAME COLUMN "index" TO disk_index
                    """
                )

                columns = self._get_table_columns(
                    "disk"
                )

            except sqlite3.OperationalError as exc:
                logger.error(
                    "Não foi possível renomear "
                    "disk.index para disk.disk_index: %s",
                    exc,
                )

                raise

        # --------------------------------------------------------------
        # disk.size
        # --------------------------------------------------------------

        if "size" not in columns:
            logger.info(
                "Adicionando coluna disk.size."
            )

            self.conn.execute(
                """
                ALTER TABLE disk
                ADD COLUMN size INTEGER DEFAULT 0
                """
            )

    # ------------------------------------------------------------------
    # INSPEÇÃO DO SCHEMA
    # ------------------------------------------------------------------

    def _get_table_columns(
        self,
        table_name: str,
    ) -> set[str]:
        """
        Retorna os nomes das colunas de uma tabela.

        Args:
            table_name:
                Nome da tabela.

        Returns:
            Conjunto com os nomes das colunas.
        """

        if self.conn is None:
            raise RuntimeError(
                "Banco não conectado."
            )

        cursor = self.conn.execute(
            f'PRAGMA table_info("{table_name}")'
        )

        return {
            str(row["name"])
            for row in cursor.fetchall()
        }

    def table_exists(
        self,
        table_name: str,
    ) -> bool:
        """
        Verifica se uma tabela existe.

        Args:
            table_name:
                Nome da tabela.

        Returns:
            ``True`` quando a tabela existe.
        """

        if self.conn is None:
            raise RuntimeError(
                "Banco não conectado."
            )

        row = self.conn.execute(
            """
            SELECT 1
            FROM sqlite_master
            WHERE type = 'table'
              AND name = ?
            LIMIT 1
            """,
            (table_name,),
        ).fetchone()

        return row is not None

    def _validate_schema(self) -> None:
        """
        Valida a presença das tabelas essenciais.

        Raises:
            RuntimeError:
                Quando uma ou mais tabelas obrigatórias estão ausentes.
        """

        missing = [
            table
            for table in self.REQUIRED_TABLES
            if not self.table_exists(table)
        ]

        if missing:
            raise RuntimeError(
                "Schema SQLite incompleto. "
                "Tabelas ausentes: "
                + ", ".join(missing)
            )

        logger.info(
            "Schema validado: %d tabelas principais.",
            len(self.REQUIRED_TABLES),
        )

    def get_table_columns(
        self,
        table_name: str,
    ) -> set[str]:
        """
        Retorna as colunas de uma tabela.

        Método público para serviços que precisam verificar
        compatibilidade do schema.

        Args:
            table_name:
                Nome da tabela.

        Returns:
            Conjunto de nomes das colunas.
        """

        if self.conn is None:
            self.connect()

        return self._get_table_columns(
            table_name
        )

    # ------------------------------------------------------------------
    # SQL
    # ------------------------------------------------------------------

    def execute(
        self,
        sql: str,
        parameters: Sequence[Any] = (),
    ) -> sqlite3.Cursor:
        """
        Executa uma instrução SQL.

        Args:
            sql:
                SQL a executar.

            parameters:
                Parâmetros posicionais da instrução.

        Returns:
            Cursor SQLite.

        Raises:
            sqlite3.Error:
                Em caso de erro SQL.
        """

        if self.conn is None:
            self.connect()

        assert self.conn is not None

        return self.conn.execute(
            sql,
            parameters,
        )

    def executemany(
        self,
        sql: str,
        parameters: Iterable[Sequence[Any]],
    ) -> sqlite3.Cursor:
        """
        Executa uma instrução SQL para múltiplos registros.

        Ideal para ingestão em lote do listxml.

        Args:
            sql:
                Instrução SQL parametrizada.

            parameters:
                Iterable de conjuntos de parâmetros.

        Returns:
            Cursor SQLite.
        """

        if self.conn is None:
            self.connect()

        assert self.conn is not None

        return self.conn.executemany(
            sql,
            parameters,
        )

    def executescript(
        self,
        sql_script: str,
    ) -> None:
        """
        Executa um script SQL completo.

        Args:
            sql_script:
                Script SQL.
        """

        if self.conn is None:
            self.connect()

        assert self.conn is not None

        self.conn.executescript(
            sql_script
        )

    # ------------------------------------------------------------------
    # CONSULTAS
    # ------------------------------------------------------------------

    def fetchone(
        self,
        sql: str,
        parameters: Sequence[Any] = (),
    ) -> sqlite3.Row | None:
        """
        Executa uma consulta e retorna a primeira linha.

        Args:
            sql:
                Consulta SQL.

            parameters:
                Parâmetros da consulta.

        Returns:
            ``sqlite3.Row`` ou ``None``.
        """

        cursor = self.execute(
            sql,
            parameters,
        )

        return cursor.fetchone()

    def fetchall(
        self,
        sql: str,
        parameters: Sequence[Any] = (),
    ) -> list[sqlite3.Row]:
        """
        Executa uma consulta e retorna todas as linhas.

        Args:
            sql:
                Consulta SQL.

            parameters:
                Parâmetros da consulta.

        Returns:
            Lista de ``sqlite3.Row``.
        """

        cursor = self.execute(
            sql,
            parameters,
        )

        return cursor.fetchall()

    def fetch_value(
        self,
        sql: str,
        parameters: Sequence[Any] = (),
        default: Any = None,
    ) -> Any:
        """
        Executa uma consulta e retorna o primeiro valor da primeira linha.

        Args:
            sql:
                Consulta SQL.

            parameters:
                Parâmetros da consulta.

            default:
                Valor retornado quando nenhuma linha é encontrada.

        Returns:
            Primeiro valor encontrado ou ``default``.
        """

        row = self.fetchone(
            sql,
            parameters,
        )

        if row is None:
            return default

        return row[0]

    # ------------------------------------------------------------------
    # TRANSAÇÕES
    # ------------------------------------------------------------------

    def commit(self) -> None:
        """
        Confirma a transação atual.
        """

        if self.conn is None:
            return

        self.conn.commit()

    def rollback(self) -> None:
        """
        Desfaz a transação atual.
        """

        if self.conn is None:
            return

        self.conn.rollback()

    @contextmanager
    def transaction(self) -> Iterator[sqlite3.Connection]:
        """
        Executa operações dentro de uma transação.

        Em caso de sucesso:

            COMMIT

        Em caso de exceção:

            ROLLBACK

        Exemplo:

        ::

            with db.transaction() as conn:
                conn.execute(...)
                conn.execute(...)
        """

        if self.conn is None:
            self.connect()

        assert self.conn is not None

        try:
            yield self.conn
            self.conn.commit()

        except Exception:
            self.conn.rollback()

            logger.exception(
                "Transação SQLite revertida."
            )

            raise

    # ------------------------------------------------------------------
    # UTILITÁRIOS
    # ------------------------------------------------------------------

    def last_insert_id(
        self,
        cursor: sqlite3.Cursor,
    ) -> int:
        """
        Retorna o ID gerado pela última inserção.

        Args:
            cursor:
                Cursor retornado por ``execute``.

        Returns:
            ID inserido.
        """

        return int(
            cursor.lastrowid
            or 0
        )

    def get_user_version(self) -> int:
        """
        Retorna a versão interna do schema SQLite.

        Returns:
            Número da versão.
        """

        return int(
            self.fetch_value(
                "PRAGMA user_version",
                default=0,
            )
        )

    # ------------------------------------------------------------------
    # CONTEXT MANAGER
    # ------------------------------------------------------------------

    def __enter__(self) -> Database:
        """
        Abre o banco ao entrar em um context manager.

        Returns:
            A própria instância de ``Database``.
        """

        self.connect()

        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: Any,
    ) -> None:
        """
        Fecha o banco ao sair do context manager.

        Se uma exceção ocorrer dentro do bloco, a transação pendente
        é revertida antes do fechamento.
        """

        if exc_type is not None:
            self.rollback()

        self.close()

    # ------------------------------------------------------------------
    # FECHAMENTO
    # ------------------------------------------------------------------

    def _close_connection_safely(self) -> None:
        """
        Fecha a conexão sem propagar exceções.
        """

        if self.conn is None:
            return

        try:
            self.conn.close()

        except sqlite3.Error:
            logger.exception(
                "Erro ao fechar conexão SQLite."
            )

        finally:
            self.conn = None

    def close(self) -> None:
        """
        Fecha a conexão SQLite.

        É seguro chamar o método mesmo quando o banco já estiver fechado.
        """

        if self.conn is None:
            return

        try:
            self.conn.commit()

        except sqlite3.Error:
            logger.warning(
                "Não foi possível confirmar transação "
                "antes de fechar o banco."
            )

        finally:
            self._close_connection_safely()

            logger.info(
                "Conexão SQLite encerrada: %s",
                self.db_path,
            )