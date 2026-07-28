from __future__ import annotations

import json
import sqlite3
import uuid
import hashlib
from collections import deque
from pathlib import Path
from typing import Any, Callable

from .authority import CorpusHead
from .errors import ConflictError, ContractError, NotFoundError, StaleWriteError, ValidationFailure
from .identity import derived_uuid, node_uuid, sha256_text, validate_pointer
from .legacy_reference import rewrite_legacy_references
from .models import ReferenceValidationModel
from .pgx import parse_node, roundtrip_equal, serialize_node
from .reference import BARE_POINTER_TEMPLATE, ReferenceEngine, ReferenceProfile
from .reference_discipline import bare_pointer_profile, rewrite_to_bare_pointer_links
from .schema import DEFAULT_POINTER_PATTERN, DEFAULT_URI_TEMPLATE, SCHEMA_VERSION, create_empty_database, connect
from .timeutil import is_rfc3339_ns, now_rfc3339_ns, unique_timestamp
from .traversal import pointer_roles, render_embedding, serialize_expression, tree_from_mapping
from .version import __release_id__


def _canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _row(row: sqlite3.Row | None) -> dict[str, Any] | None:
    return dict(row) if row is not None else None


class SQLitePGXStore:
    def __init__(
        self,
        path: str | Path,
        *,
        workstream_id: str | None = None,
        expected_head: CorpusHead | dict[str, Any] | None = None,
    ):
        self.path = Path(path)
        if not self.path.exists():
            raise FileNotFoundError(self.path)
        self.workstream_id = str(uuid.UUID(workstream_id)) if workstream_id else str(uuid.uuid4())
        self.expected_head = (
            expected_head
            if isinstance(expected_head, CorpusHead)
            else CorpusHead.model_validate(expected_head)
            if expected_head is not None
            else None
        )

    @classmethod
    def initialize(
        cls,
        path: str | Path,
        *,
        overwrite: bool = False,
        uri_template: str = DEFAULT_URI_TEMPLATE,
        resolver_status: str = "resolved",
    ) -> "SQLitePGXStore":
        connection = create_empty_database(
            path,
            overwrite=overwrite,
            uri_template=uri_template,
            resolver_status=resolver_status,
        )
        try:
            store = cls(path)
            store._seed_fresh(connection)
            head = store._initialize_authority_head(connection)
            connection.commit()
        finally:
            connection.close()
        return cls(path, expected_head=head)

    def _metadata(self, connection: sqlite3.Connection) -> dict[str, str]:
        return {r["key"]: r["value"] for r in connection.execute("SELECT key,value FROM metadata")}

    def _ensure_lineage_schema(self, connection: sqlite3.Connection) -> None:
        """Install additive lineage tables for pre-2.7 corpora on first write."""
        connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS corpus_workstreams (
              workstream_id TEXT NOT NULL PRIMARY KEY,
              corpus_id TEXT NOT NULL,
              base_snapshot_id TEXT NOT NULL,
              created_at TEXT NOT NULL UNIQUE,
              package_release_id TEXT NOT NULL,
              mutation_count INTEGER NOT NULL DEFAULT 0 CHECK(mutation_count>=0)
            ) STRICT, WITHOUT ROWID;
            CREATE TABLE IF NOT EXISTS materializations (
              materialization_id TEXT NOT NULL PRIMARY KEY,
              corpus_id TEXT NOT NULL,
              snapshot_id TEXT NOT NULL,
              workstream_id TEXT,
              kind TEXT NOT NULL CHECK(kind IN ('database','pgx','markdown')),
              created_at TEXT NOT NULL UNIQUE,
              details_json TEXT NOT NULL
            ) STRICT, WITHOUT ROWID;
            CREATE TABLE IF NOT EXISTS sentinel_guidance (
              node_uuid TEXT NOT NULL PRIMARY KEY REFERENCES node_identity(uuid) ON UPDATE RESTRICT ON DELETE RESTRICT,
              scope TEXT NOT NULL DEFAULT 'corpus',
              active INTEGER NOT NULL DEFAULT 1 CHECK(active IN (0,1)),
              created_at TEXT NOT NULL UNIQUE
            ) STRICT, WITHOUT ROWID;
            """
        )
        metadata = self._metadata(connection)
        corpus_id = metadata.get("corpus_id") or metadata.get("database_uuid") or str(uuid.uuid4())
        connection.execute(
            "INSERT INTO metadata(key,value) VALUES ('corpus_id',?) ON CONFLICT(key) DO NOTHING",
            (corpus_id,),
        )
        connection.execute(
            "INSERT INTO metadata(key,value) VALUES ('parmesan_schema_version',?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
            (str(SCHEMA_VERSION),),
        )
        connection.execute(
            "INSERT OR IGNORE INTO schema_migrations(version,applied_at,description) VALUES (?,?,?)",
            (SCHEMA_VERSION, unique_timestamp(connection, "schema_migrations", "applied_at"), "Parmesan 2.7 lineage and materialization metadata"),
        )
        self._ensure_operating_mode_schema(connection)

    def _ensure_operating_mode_schema(self, connection: sqlite3.Connection) -> None:
        """Install the safe default-off publication gate for legacy corpora."""
        connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS operating_mode_state (
              singleton_id INTEGER NOT NULL PRIMARY KEY CHECK(singleton_id=1),
              mode_key TEXT NOT NULL CHECK(mode_key IN ('working','publish')),
              revision INTEGER NOT NULL CHECK(revision>=1),
              updated_at TEXT NOT NULL UNIQUE,
              reason TEXT NOT NULL
            ) STRICT, WITHOUT ROWID;
            CREATE TABLE IF NOT EXISTS operating_mode_history (
              transition_uuid TEXT NOT NULL PRIMARY KEY,
              from_mode_key TEXT CHECK(from_mode_key IN ('working','publish')),
              to_mode_key TEXT NOT NULL CHECK(to_mode_key IN ('working','publish')),
              revision INTEGER NOT NULL UNIQUE CHECK(revision>=1),
              changed_at TEXT NOT NULL UNIQUE,
              reason TEXT NOT NULL,
              request_uuid TEXT
            ) STRICT, WITHOUT ROWID;
            """
        )
        if connection.execute("SELECT 1 FROM operating_mode_state WHERE singleton_id=1").fetchone() is None:
            changed_at = unique_timestamp(connection, "operating_mode_history", "changed_at")
            transition_uuid = str(uuid.uuid4())
            connection.execute(
                """INSERT INTO operating_mode_state(singleton_id,mode_key,revision,updated_at,reason)
                   VALUES (1,'working',1,?,'default safe working mode')""",
                (changed_at,),
            )
            connection.execute(
                """INSERT INTO operating_mode_history
                   (transition_uuid,from_mode_key,to_mode_key,revision,changed_at,reason,request_uuid)
                   VALUES (?,NULL,'working',1,?,'default safe working mode',NULL)""",
                (transition_uuid, changed_at),
            )

    def _ensure_authority_schema(self, connection: sqlite3.Connection) -> None:
        connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS semantic_snapshots (
              snapshot_uuid TEXT NOT NULL PRIMARY KEY,
              parent_snapshot_uuid TEXT REFERENCES semantic_snapshots(snapshot_uuid) ON UPDATE RESTRICT ON DELETE RESTRICT,
              corpus_id TEXT NOT NULL,
              database_sequence INTEGER NOT NULL CHECK(database_sequence>=0),
              transition_digest TEXT NOT NULL,
              request_uuid TEXT,
              tool_name TEXT NOT NULL,
              created_at TEXT NOT NULL UNIQUE,
              UNIQUE(corpus_id,database_sequence)
            ) STRICT, WITHOUT ROWID;
            CREATE TABLE IF NOT EXISTS corpus_head (
              singleton_id INTEGER NOT NULL PRIMARY KEY CHECK(singleton_id=1),
              corpus_id TEXT NOT NULL,
              snapshot_uuid TEXT NOT NULL REFERENCES semantic_snapshots(snapshot_uuid) ON UPDATE RESTRICT ON DELETE RESTRICT,
              database_sequence INTEGER NOT NULL CHECK(database_sequence>=0),
              last_request_uuid TEXT,
              updated_at TEXT NOT NULL
            ) STRICT, WITHOUT ROWID;
            CREATE TRIGGER IF NOT EXISTS semantic_snapshots_append_only_update
            BEFORE UPDATE ON semantic_snapshots BEGIN SELECT RAISE(ABORT,'semantic snapshots are append-only'); END;
            CREATE TRIGGER IF NOT EXISTS semantic_snapshots_append_only_delete
            BEFORE DELETE ON semantic_snapshots BEGIN SELECT RAISE(ABORT,'semantic snapshots are append-only'); END;
            CREATE TRIGGER IF NOT EXISTS corpus_head_no_delete
            BEFORE DELETE ON corpus_head BEGIN SELECT RAISE(ABORT,'corpus head cannot be deleted'); END;
            """
        )
        ledger_columns = {
            row["name"] for row in connection.execute("PRAGMA table_info(operation_ledger)")
        }
        for name in ("input_snapshot_uuid", "output_snapshot_uuid", "transition_digest"):
            if name not in ledger_columns:
                connection.execute(f"ALTER TABLE operation_ledger ADD COLUMN {name} TEXT")

    def _head_row(self, connection: sqlite3.Connection) -> sqlite3.Row | None:
        if connection.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='corpus_head'"
        ).fetchone() is None:
            return None
        return connection.execute(
            "SELECT corpus_id,snapshot_uuid,database_sequence,last_request_uuid,updated_at "
            "FROM corpus_head WHERE singleton_id=1"
        ).fetchone()

    def _initialize_authority_head(self, connection: sqlite3.Connection) -> CorpusHead:
        self._ensure_authority_schema(connection)
        existing = self._head_row(connection)
        if existing is not None:
            return CorpusHead(
                corpus_id=existing["corpus_id"],
                snapshot_uuid=existing["snapshot_uuid"],
                database_sequence=existing["database_sequence"],
            )
        metadata = self._metadata(connection)
        corpus_id = metadata.get("corpus_id") or metadata.get("database_uuid")
        if not corpus_id:
            raise ValidationFailure("database is missing corpus identity")
        sequence = int(metadata.get("database_sequence", "0"))
        transition_digest = sha256_text(
            _canonical_json({"kind": "genesis", "corpus_id": corpus_id, "database_sequence": sequence})
        )
        snapshot_uuid = str(uuid.uuid5(uuid.UUID(corpus_id), f"snapshot:{sequence}:{transition_digest}"))
        created_at = now_rfc3339_ns()
        connection.execute(
            """INSERT INTO semantic_snapshots
               (snapshot_uuid,parent_snapshot_uuid,corpus_id,database_sequence,transition_digest,request_uuid,tool_name,created_at)
               VALUES (?,NULL,?,?,?,NULL,'parmesan.authority.genesis',?)""",
            (snapshot_uuid, corpus_id, sequence, transition_digest, created_at),
        )
        connection.execute(
            """INSERT INTO corpus_head
               (singleton_id,corpus_id,snapshot_uuid,database_sequence,last_request_uuid,updated_at)
               VALUES (1,?,?,?,NULL,?)""",
            (corpus_id, snapshot_uuid, sequence, created_at),
        )
        return CorpusHead(corpus_id=corpus_id, snapshot_uuid=snapshot_uuid, database_sequence=sequence)

    def current_head(self) -> dict[str, Any] | None:
        connection = connect(self.path, readonly=True)
        try:
            row = self._head_row(connection)
            if row is None:
                return None
            return CorpusHead(
                corpus_id=row["corpus_id"],
                snapshot_uuid=row["snapshot_uuid"],
                database_sequence=row["database_sequence"],
            ).model_dump()
        finally:
            connection.close()

    def _require_expected_head(self, connection: sqlite3.Connection) -> sqlite3.Row:
        current = self._head_row(connection)
        if current is None:
            raise ContractError(
                "corpus authority migration is required before mutation",
                {"database": str(self.path), "inspection_allowed": True},
            )
        if self.expected_head is None:
            raise ContractError(
                "mutation requires an externally supplied expected head",
                {"current_head": dict(current), "inspection_allowed": True},
            )
        candidate = (
            current["corpus_id"],
            current["snapshot_uuid"],
            int(current["database_sequence"]),
        )
        if candidate != self.expected_head.semantic_key():
            raise ConflictError(
                "expected head does not match the current corpus head",
                {
                    "expected_head": self.expected_head.model_dump(),
                    "current_head": {
                        "corpus_id": current["corpus_id"],
                        "snapshot_uuid": current["snapshot_uuid"],
                        "database_sequence": current["database_sequence"],
                    },
                },
            )
        return current

    def _mode_row(self, connection: sqlite3.Connection) -> sqlite3.Row | None:
        if connection.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='operating_mode_state'"
        ).fetchone() is None:
            return None
        return connection.execute(
            "SELECT mode_key,revision,updated_at,reason FROM operating_mode_state WHERE singleton_id=1"
        ).fetchone()

    def mode_show(self) -> dict[str, Any]:
        connection = connect(self.path, readonly=True)
        try:
            row = self._mode_row(connection)
            if row is None:
                return {
                    "mode": "working",
                    "revision": 0,
                    "persisted": False,
                    "publication_enabled": False,
                    "reason": "legacy corpus defaults safely to working mode",
                }
            return {
                "mode": row["mode_key"],
                "revision": row["revision"],
                "updated_at": row["updated_at"],
                "reason": row["reason"],
                "persisted": True,
                "publication_enabled": row["mode_key"] == "publish",
            }
        finally:
            connection.close()

    def mode_set(self, *, request_id: str | None, mode: str, reason: str) -> dict[str, Any]:
        if mode not in {"working", "publish"}:
            raise ContractError("unknown operating mode", {"mode": mode, "allowed": ["working", "publish"]})
        payload = {"mode": mode, "reason": reason}

        def action(connection: sqlite3.Connection, req: str) -> dict[str, Any]:
            self._ensure_operating_mode_schema(connection)
            current = self._mode_row(connection)
            assert current is not None
            if current["mode_key"] == mode:
                return {
                    "mode": mode,
                    "revision": current["revision"],
                    "unchanged": True,
                    "publication_enabled": mode == "publish",
                }
            revision = int(current["revision"]) + 1
            changed_at = unique_timestamp(connection, "operating_mode_history", "changed_at")
            transition_uuid = str(uuid.uuid4())
            connection.execute(
                """INSERT INTO operating_mode_history
                   (transition_uuid,from_mode_key,to_mode_key,revision,changed_at,reason,request_uuid)
                   VALUES (?,?,?,?,?,?,?)""",
                (transition_uuid, current["mode_key"], mode, revision, changed_at, reason, req),
            )
            connection.execute(
                """UPDATE operating_mode_state
                   SET mode_key=?,revision=?,updated_at=?,reason=?
                   WHERE singleton_id=1""",
                (mode, revision, changed_at, reason),
            )
            self._audit(
                connection,
                request_uuid=req,
                operation_type="mode.set",
                details={"from": current["mode_key"], "to": mode, "revision": revision, "reason": reason},
            )
            return {
                "mode": mode,
                "revision": revision,
                "transition_uuid": transition_uuid,
                "unchanged": False,
                "publication_enabled": mode == "publish",
            }

        return self._mutate("pgx.mode.set", request_id, payload, action)

    def require_publish_mode(self, operation: str) -> None:
        state = self.mode_show()
        if state["mode"] != "publish":
            raise ContractError(
                "external materialization is disabled in working mode",
                {
                    "operation": operation,
                    "mode": state["mode"],
                    "next_action": "Explicitly set publish mode, run the publication operation, then return to working mode.",
                },
            )

    def _semantic_snapshot(self, connection: sqlite3.Connection) -> dict[str, str]:
        """Return a deterministic identity for semantic state, excluding operational metadata."""
        metadata = self._metadata(connection)
        corpus_id = metadata.get("corpus_id") or metadata.get("database_uuid")
        if not corpus_id:
            raise ValidationFailure("database is missing corpus identity")
        state = {
            "nodes": [dict(row) for row in connection.execute("SELECT pointer,title,description,lifecycle_state,revision_uuid,content_hash FROM current_nodes ORDER BY pointer")],
            "graphs": [dict(row) for row in connection.execute("SELECT graph_key,pointer_prefix,description FROM graphs ORDER BY graph_key")],
            "triples": [dict(row) for row in connection.execute("SELECT s.pointer AS subject,p.pointer AS predicate,o.pointer AS object FROM triples t JOIN node_identity s ON s.uuid=t.subject_uuid JOIN node_identity p ON p.uuid=t.predicate_uuid JOIN node_identity o ON o.uuid=t.object_uuid ORDER BY subject,predicate,object")],
            "tags": [dict(row) for row in connection.execute("SELECT s.pointer AS subject,t.pointer AS tag FROM node_tags nt JOIN node_identity s ON s.uuid=nt.subject_uuid JOIN node_identity t ON t.uuid=nt.tag_uuid ORDER BY subject,tag")],
        }
        fingerprint = hashlib.sha256(_canonical_json(state).encode("utf-8")).hexdigest()
        return {
            "corpus_id": corpus_id,
            "snapshot_fingerprint": fingerprint,
            "snapshot_id": str(uuid.uuid5(uuid.UUID(corpus_id), f"semantic-snapshot:{fingerprint}")),
        }

    def _ensure_workstream(self, connection: sqlite3.Connection) -> dict[str, str]:
        self._ensure_lineage_schema(connection)
        existing = connection.execute(
            "SELECT corpus_id,base_snapshot_id FROM corpus_workstreams WHERE workstream_id=?",
            (self.workstream_id,),
        ).fetchone()
        if existing is not None:
            return {
                "corpus_id": existing["corpus_id"],
                "snapshot_id": existing["base_snapshot_id"],
                "snapshot_fingerprint": "",
            }
        head = self._head_row(connection)
        snapshot = (
            {
                "corpus_id": head["corpus_id"],
                "snapshot_id": head["snapshot_uuid"],
                "snapshot_fingerprint": "",
            }
            if head is not None
            else self._semantic_snapshot(connection)
        )
        connection.execute(
            """INSERT INTO corpus_workstreams(workstream_id,corpus_id,base_snapshot_id,created_at,package_release_id)
               VALUES (?,?,?,?,?) ON CONFLICT(workstream_id) DO NOTHING""",
            (self.workstream_id, snapshot["corpus_id"], snapshot["snapshot_id"], unique_timestamp(connection, "corpus_workstreams", "created_at"), __release_id__),
        )
        return snapshot

    def _namespace(self, connection: sqlite3.Connection) -> str:
        row = connection.execute("SELECT value FROM metadata WHERE key='uuid_namespace'").fetchone()
        if row is None:
            raise ValidationFailure("database is missing uuid_namespace")
        return row[0]

    def _pointer_pattern(self, connection: sqlite3.Connection) -> str:
        row = connection.execute("SELECT value FROM metadata WHERE key='pointer_pattern'").fetchone()
        return row[0] if row else DEFAULT_POINTER_PATTERN

    def _profile(self, connection: sqlite3.Connection, profile_key: str = "pgx-default") -> ReferenceProfile:
        row = connection.execute(
            "SELECT * FROM reference_profiles WHERE profile_key=?", (profile_key,)
        ).fetchone()
        if row is None:
            raise NotFoundError("reference profile not found", {"profile_key": profile_key})
        return ReferenceProfile(
            profile_key=row["profile_key"],
            namespace_prefix=row["namespace_prefix"],
            pointer_pattern=row["pointer_pattern"],
            visible_open=row["visible_open"],
            visible_close=row["visible_close"],
            uri_template=row["uri_template"],
            require_target=bool(row["require_target"]),
            resolver_status=row["resolver_status"],
        )

    def _resolve_pointer(self, connection: sqlite3.Connection, pointer: str) -> str | None:
        row = connection.execute("SELECT uuid FROM node_identity WHERE pointer=?", (pointer,)).fetchone()
        return row[0] if row else None

    def _current(self, connection: sqlite3.Connection, pointer: str) -> sqlite3.Row:
        row = connection.execute("SELECT * FROM current_nodes WHERE pointer=?", (pointer,)).fetchone()
        if row is None:
            raise NotFoundError("node not found", {"pointer": pointer})
        return row

    def _new_revision(
        self,
        connection: sqlite3.Connection,
        *,
        node_uuid_value: str,
        title: str,
        description: str,
        previous_revision_uuid: str | None,
        request_uuid: str | None,
        reason: str,
        created_at: str | None = None,
    ) -> str:
        timestamp = created_at or unique_timestamp(connection, "node_revision")
        content_hash = sha256_text(title + "\0" + description)
        namespace = self._namespace(connection)
        revision_uuid = derived_uuid(
            namespace,
            "revision",
            f"{node_uuid_value}|{timestamp}|{content_hash}|{previous_revision_uuid or ''}",
        )
        connection.execute(
            """INSERT INTO node_revision
            (revision_uuid,node_uuid,title,description,created_at,previous_revision_uuid,content_hash,request_uuid,reason)
            VALUES (?,?,?,?,?,?,?,?,?)""",
            (
                revision_uuid,
                node_uuid_value,
                title,
                description,
                timestamp,
                previous_revision_uuid,
                content_hash,
                request_uuid,
                reason,
            ),
        )
        return revision_uuid

    def _insert_identity(
        self,
        connection: sqlite3.Connection,
        *,
        pointer: str,
        title: str,
        description: str,
        lifecycle_state: str,
        request_uuid: str | None,
        reason: str,
        node_created_at: str | None = None,
        revision_created_at: str | None = None,
        expected_uuid: str | None = None,
    ) -> tuple[str, str]:
        validate_pointer(pointer, self._pointer_pattern(connection))
        if connection.execute("SELECT 1 FROM node_identity WHERE pointer=?", (pointer,)).fetchone():
            raise ConflictError("pointer already exists", {"pointer": pointer})
        namespace = self._namespace(connection)
        calculated_uuid = node_uuid(namespace, pointer)
        if expected_uuid is not None and expected_uuid != calculated_uuid:
            raise ValidationFailure(
                "supplied UUID does not match database namespace",
                {"pointer": pointer, "supplied": expected_uuid, "expected": calculated_uuid},
            )
        created_at = node_created_at or unique_timestamp(connection, "node_identity")
        connection.execute(
            """INSERT INTO node_identity(uuid,pointer,sigil,created_at,lifecycle_state,current_revision_uuid)
            VALUES (?,?,'pgx:',?,?,NULL)""",
            (calculated_uuid, pointer, created_at, lifecycle_state),
        )
        revision_uuid = self._new_revision(
            connection,
            node_uuid_value=calculated_uuid,
            title=title,
            description=description,
            previous_revision_uuid=None,
            request_uuid=request_uuid,
            reason=reason,
            created_at=revision_created_at,
        )
        connection.execute(
            "UPDATE node_identity SET current_revision_uuid=? WHERE uuid=?",
            (revision_uuid, calculated_uuid),
        )
        return calculated_uuid, revision_uuid

    def _audit(
        self,
        connection: sqlite3.Connection,
        *,
        request_uuid: str | None,
        operation_type: str,
        node_uuid_value: str | None = None,
        previous_revision_uuid: str | None = None,
        new_revision_uuid: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        namespace = self._namespace(connection)
        timestamp = unique_timestamp(connection, "audit_event")
        stable = f"{request_uuid}|{operation_type}|{node_uuid_value}|{timestamp}"
        event_uuid = derived_uuid(namespace, "audit", stable)
        connection.execute(
            """INSERT INTO audit_event
            (event_uuid,request_uuid,operation_type,node_uuid,previous_revision_uuid,new_revision_uuid,details_json,created_at)
            VALUES (?,?,?,?,?,?,?,?)""",
            (
                event_uuid,
                request_uuid,
                operation_type,
                node_uuid_value,
                previous_revision_uuid,
                new_revision_uuid,
                _canonical_json(details or {}),
                timestamp,
            ),
        )

    def _increment_sequence(self, connection: sqlite3.Connection) -> int:
        current = int(connection.execute(
            "SELECT value FROM metadata WHERE key='database_sequence'"
        ).fetchone()[0])
        new = current + 1
        connection.execute(
            "UPDATE metadata SET value=? WHERE key='database_sequence'", (str(new),)
        )
        return new

    def _validate_request_uuid(self, request_id: str | None) -> str:
        if request_id is None:
            return str(uuid.uuid4())
        try:
            return str(uuid.UUID(request_id))
        except ValueError as exc:
            raise ContractError("mutating requests require a UUID request_id", {"request_id": request_id}) from exc

    def _mutate(
        self,
        tool_name: str,
        request_id: str | None,
        payload: dict[str, Any],
        fn: Callable[[sqlite3.Connection, str], dict[str, Any]],
    ) -> dict[str, Any]:
        request_uuid = self._validate_request_uuid(request_id)
        input_hash = sha256_text(_canonical_json({"tool": tool_name, "arguments": payload}))
        connection = connect(self.path)
        try:
            connection.execute("BEGIN IMMEDIATE")
            existing = connection.execute(
                "SELECT * FROM operation_ledger WHERE request_uuid=?", (request_uuid,)
            ).fetchone()
            if existing is not None:
                if existing["input_hash"] != input_hash:
                    raise ConflictError(
                        "request_id was already used with different input",
                        {"request_id": request_uuid, "tool": existing["tool_name"]},
                    )
                if existing["status"] == "committed":
                    result = json.loads(existing["result_json"])
                    connection.rollback()
                    result["idempotent_replay"] = True
                    if result.get("head"):
                        self.expected_head = CorpusHead.model_validate(result["head"])
                    return result
                raise ConflictError("request is already in progress", {"request_id": request_uuid})
            input_head = self._require_expected_head(connection)
            self._ensure_operating_mode_schema(connection)
            mode = self._mode_row(connection)
            if tool_name != "pgx.mode.set" and mode is not None and mode["mode_key"] == "publish":
                raise ConflictError(
                    "semantic mutation is disabled while publish mode is active",
                    {"tool": tool_name, "next_action": "Return to working mode before changing canonical corpus state."},
                )
            self._ensure_workstream(connection)
            started = unique_timestamp(connection, "operation_ledger", "started_at")
            connection.execute(
                """INSERT INTO operation_ledger
                (request_uuid,tool_name,input_hash,status,result_json,started_at,committed_at,database_sequence)
                VALUES (?,?,?,'started',NULL,?,NULL,NULL)""",
                (request_uuid, tool_name, input_hash, started),
            )
            result = fn(connection, request_uuid)
            sequence = self._increment_sequence(connection)
            connection.execute(
                "UPDATE corpus_workstreams SET mutation_count=mutation_count+1 WHERE workstream_id=?",
                (self.workstream_id,),
            )
            result = dict(result)
            transition_digest = sha256_text(
                _canonical_json(
                    {
                        "parent_snapshot_uuid": input_head["snapshot_uuid"],
                        "request_uuid": request_uuid,
                        "tool_name": tool_name,
                        "input_hash": input_hash,
                        "database_sequence": sequence,
                        "result": result,
                    }
                )
            )
            output_snapshot_uuid = str(
                uuid.uuid5(
                    uuid.UUID(input_head["corpus_id"]),
                    f"snapshot:{input_head['snapshot_uuid']}:{sequence}:{transition_digest}:{request_uuid}",
                )
            )
            head_created_at = now_rfc3339_ns()
            connection.execute(
                """INSERT INTO semantic_snapshots
                   (snapshot_uuid,parent_snapshot_uuid,corpus_id,database_sequence,transition_digest,request_uuid,tool_name,created_at)
                   VALUES (?,?,?,?,?,?,?,?)""",
                (
                    output_snapshot_uuid,
                    input_head["snapshot_uuid"],
                    input_head["corpus_id"],
                    sequence,
                    transition_digest,
                    request_uuid,
                    tool_name,
                    head_created_at,
                ),
            )
            connection.execute(
                """UPDATE corpus_head
                   SET snapshot_uuid=?,database_sequence=?,last_request_uuid=?,updated_at=?
                   WHERE singleton_id=1""",
                (output_snapshot_uuid, sequence, request_uuid, head_created_at),
            )
            output_head = CorpusHead(
                corpus_id=input_head["corpus_id"],
                snapshot_uuid=output_snapshot_uuid,
                database_sequence=sequence,
            )
            result.update({
                "request_id": request_uuid,
                "database_sequence": sequence,
                "idempotent_replay": False,
                "workstream_id": self.workstream_id,
                "head": output_head.model_dump(),
            })
            committed = now_rfc3339_ns()
            connection.execute(
                """UPDATE operation_ledger
                   SET status='committed',result_json=?,committed_at=?,database_sequence=?,
                       input_snapshot_uuid=?,output_snapshot_uuid=?,transition_digest=?
                WHERE request_uuid=?""",
                (
                    _canonical_json(result),
                    committed,
                    sequence,
                    input_head["snapshot_uuid"],
                    output_snapshot_uuid,
                    transition_digest,
                    request_uuid,
                ),
            )
            connection.commit()
            self.expected_head = output_head
            return result
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def _replace_references(
        self,
        connection: sqlite3.Connection,
        *,
        source_node_uuid: str,
        source_revision_uuid: str,
        description: str,
        strict: bool,
    ) -> ReferenceValidationModel:
        profile = self._profile(connection)
        engine = ReferenceEngine(profile)
        report = engine.validate(
            description,
            resolver=lambda pointer: self._resolve_pointer(connection, pointer),
            strict_markers=True,
        )
        if strict and not report.valid:
            raise ContractError("description violates PGX semantic-link contract", {"errors": report.errors})
        connection.execute(
            "DELETE FROM reference_occurrences WHERE source_node_uuid=?", (source_node_uuid,)
        )
        if report.valid:
            namespace = self._namespace(connection)
            for occurrence in report.occurrences:
                occurrence_uuid = derived_uuid(
                    namespace,
                    "reference-occurrence",
                    f"{source_revision_uuid}|{occurrence.ordinal}|{occurrence.fingerprint}",
                )
                connection.execute(
                    """INSERT INTO reference_occurrences
                    (occurrence_uuid,source_node_uuid,source_revision_uuid,ordinal,profile_key,target_pointer,target_uuid,
                     anchor_text,visible_identifier,canonical_uri,char_start,char_end,token_path,occurrence_fingerprint,created_at)
                    VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                    (
                        occurrence_uuid,
                        source_node_uuid,
                        source_revision_uuid,
                        occurrence.ordinal,
                        occurrence.profile_key,
                        occurrence.pointer,
                        occurrence.target_uuid,
                        occurrence.anchor_text,
                        occurrence.visible_identifier,
                        occurrence.canonical_uri,
                        occurrence.char_start,
                        occurrence.char_end,
                        occurrence.token_path,
                        occurrence.fingerprint,
                        unique_timestamp(connection, "reference_occurrences"),
                    ),
                )
        return report

    def _refresh_fts(self, connection: sqlite3.Connection, node_uuid_value: str) -> None:
        connection.execute("DELETE FROM node_fts WHERE node_uuid=?", (node_uuid_value,))
        row = connection.execute(
            """SELECT c.pointer,c.title,c.description,c.uuid,c.revision_uuid,g.graph_key
            FROM current_nodes c
            LEFT JOIN graph_membership gm ON gm.node_uuid=c.uuid
            LEFT JOIN graphs g ON g.graph_uuid=gm.graph_uuid
            WHERE c.uuid=? AND c.lifecycle_state='promoted'""",
            (node_uuid_value,),
        ).fetchone()
        if row:
            connection.execute(
                "INSERT INTO node_fts(pointer,title,description,node_uuid,revision_uuid,graph_key) VALUES (?,?,?,?,?,?)",
                (row["pointer"], row["title"], row["description"], row["uuid"], row["revision_uuid"], row["graph_key"] or ""),
            )

    def _graph(self, connection: sqlite3.Connection, graph_key: str) -> sqlite3.Row:
        row = connection.execute("SELECT * FROM graphs WHERE graph_key=?", (graph_key,)).fetchone()
        if row is None:
            raise NotFoundError("graph not found", {"graph_key": graph_key})
        return row

    def _graph_by_prefix(self, connection: sqlite3.Connection, pointer_prefix: str) -> sqlite3.Row:
        row = connection.execute("SELECT * FROM graphs WHERE pointer_prefix=?", (pointer_prefix,)).fetchone()
        if row is None:
            raise NotFoundError("graph namespace not found", {"pointer_prefix": pointer_prefix})
        return row

    def _resolve_graph_namespace(self, connection: sqlite3.Connection, pointer: str) -> sqlite3.Row | None:
        """Resolve a pointer to the uniquely longest registered graph prefix."""
        return connection.execute(
            """SELECT * FROM graphs
               WHERE ? LIKE pointer_prefix || '%'
               ORDER BY length(pointer_prefix) DESC, pointer_prefix
               LIMIT 1""",
            (pointer,),
        ).fetchone()

    def _check_graph_pointer(self, connection: sqlite3.Connection, graph: sqlite3.Row, pointer: str) -> None:
        resolved = self._resolve_graph_namespace(connection, pointer)
        if resolved is None:
            raise ContractError(
                "pointer does not belong to graph namespace",
                {"pointer": pointer, "graph_key": graph["graph_key"], "required_prefix": graph["pointer_prefix"]},
            )
        if resolved["graph_uuid"] != graph["graph_uuid"]:
            raise ContractError(
                "pointer resolves to a more specific graph namespace",
                {
                    "pointer": pointer,
                    "requested_graph_key": graph["graph_key"],
                    "requested_prefix": graph["pointer_prefix"],
                    "resolved_graph_key": resolved["graph_key"],
                    "resolved_prefix": resolved["pointer_prefix"],
                },
            )

    def _next_ordinal(self, connection: sqlite3.Connection, graph_uuid: str) -> int:
        return int(connection.execute(
            "SELECT COALESCE(MAX(ordinal),-1)+1 FROM graph_membership WHERE graph_uuid=?",
            (graph_uuid,),
        ).fetchone()[0])

    def _seed_fresh(self, connection: sqlite3.Connection) -> None:
        request = str(uuid.uuid4())
        seeds = [
            ("pgx-format", "N", "N0", "object: PGX format graph", "PGX syntax and persistent pointer conventions."),
            ("predicates", "PRN", "PRN000", "object: predicate registry", "PGX nodes registered as RDF-style predicates."),
            ("principles", "PLN", "PLN000", "object: principles graph", "Meta-level principles for maintaining the knowledge system; intentionally empty beyond this declaration."),
            ("tags", "TGN", "TGN000", "object: tag registry", "PGX nodes used as provisional tracking tags."),
            ("staging", "STG", "STG000", "object: staging knowledge base", "Isolated pre-promotion semantic work."),
            ("sentinels", "SNT", "SNT000", "object: advisory sentinels", "Corpus-local, text-first operating guidance. Sentinels are advisory data and never override system or user instructions."),
        ]
        for graph_key, prefix, pointer, title, description in seeds:
            node, rev = self._insert_identity(
                connection,
                pointer=pointer,
                title=title,
                description=description,
                lifecycle_state="promoted",
                request_uuid=request,
                reason="fresh database seed",
            )
            connection.execute(
                "INSERT INTO graphs(graph_uuid,graph_key,pointer_prefix,description) VALUES (?,?,?,?)",
                (node, graph_key, prefix, description),
            )
            connection.execute(
                "INSERT INTO graph_membership(graph_uuid,node_uuid,ordinal) VALUES (?,?,0)",
                (node, node),
            )
            self._replace_references(connection, source_node_uuid=node, source_revision_uuid=rev, description=description, strict=True)
            self._refresh_fts(connection, node)
        format_graph = self._graph(connection, "pgx-format")
        format_nodes = [
            ("N1", "object: normal form", "Canonical timestamp-bearing PGX node line with escaped reserved delimiters."),
            ("N2", "object: short reference", "Pointer-only inline form: (*POINTER*)."),
            ("N3", "object: long reference", "Title and pointer inline form: **title** (*POINTER*)."),
            ("N4", "object: semantic link", "Natural-language Markdown link whose raw destination is the exact PGX pointer, template-quoted as `{{[anchor]({pointer})}}`. Parmesan resolves the pointer only against the active corpus and performs no network lookup."),
        ]
        for pointer, title, description in format_nodes:
            n, r = self._insert_identity(
                connection,
                pointer=pointer,
                title=title,
                description=description,
                lifecycle_state="promoted",
                request_uuid=request,
                reason="fresh database seed",
            )
            connection.execute(
                "INSERT INTO graph_membership(graph_uuid,node_uuid,ordinal) VALUES (?,?,?)",
                (format_graph["graph_uuid"], n, self._next_ordinal(connection, format_graph["graph_uuid"])),
            )
            self._replace_references(connection, source_node_uuid=n, source_revision_uuid=r, description=description, strict=True)
            self._refresh_fts(connection, n)
        pred_graph = self._graph(connection, "predicates")
        p, r = self._insert_identity(
            connection,
            pointer="PRN001",
            title="predicate: relates_to",
            description="Deliberately broad predicate asserting that two nodes are meaningfully related without prematurely refining the relation type.",
            lifecycle_state="promoted",
            request_uuid=request,
            reason="fresh database seed",
        )
        connection.execute(
            "INSERT INTO graph_membership(graph_uuid,node_uuid,ordinal) VALUES (?,?,?)",
            (pred_graph["graph_uuid"], p, self._next_ordinal(connection, pred_graph["graph_uuid"])),
        )
        connection.execute("INSERT INTO predicate_registry(predicate_uuid) VALUES (?)", (p,))
        self._replace_references(connection, source_node_uuid=p, source_revision_uuid=r, description="Deliberately broad predicate asserting that two nodes are meaningfully related without prematurely refining the relation type.", strict=True)
        self._refresh_fts(connection, p)

    # ---------- mutation API ----------

    def create_graph(self, *, request_id: str | None, graph_key: str, pointer_prefix: str, declaration_pointer: str, title: str, description: str) -> dict[str, Any]:
        payload = locals().copy(); payload.pop("self"); payload.pop("request_id")
        def action(con: sqlite3.Connection, req: str) -> dict[str, Any]:
            if con.execute("SELECT 1 FROM graphs WHERE graph_key=? OR pointer_prefix=?", (graph_key, pointer_prefix)).fetchone():
                raise ConflictError("graph key or pointer prefix already exists")
            node, rev = self._insert_identity(
                con, pointer=declaration_pointer, title=title, description=description,
                lifecycle_state="promoted", request_uuid=req, reason="graph creation",
            )
            con.execute(
                "INSERT INTO graphs(graph_uuid,graph_key,pointer_prefix,description) VALUES (?,?,?,?)",
                (node, graph_key, pointer_prefix, description),
            )
            graph = self._graph(con, graph_key)
            self._check_graph_pointer(con, graph, declaration_pointer)
            con.execute("INSERT INTO graph_membership(graph_uuid,node_uuid,ordinal) VALUES (?,?,0)", (node, node))
            self._replace_references(con, source_node_uuid=node, source_revision_uuid=rev, description=description, strict=True)
            self._refresh_fts(con, node)
            self._audit(con, request_uuid=req, operation_type="graph.create", node_uuid_value=node, new_revision_uuid=rev, details={"graph_key": graph_key})
            return {"graph_key": graph_key, "pointer": declaration_pointer, "uuid": node, "revision_uuid": rev}
        return self._mutate("pgx.graph.create", request_id, payload, action)

    def create_node(self, *, request_id: str | None, pointer: str, title: str, description: str, graph_key: str) -> dict[str, Any]:
        payload = {"pointer": pointer, "title": title, "description": description, "graph_key": graph_key}
        def action(con: sqlite3.Connection, req: str) -> dict[str, Any]:
            graph = self._graph(con, graph_key)
            self._check_graph_pointer(con, graph, pointer)
            node, rev = self._insert_identity(
                con, pointer=pointer, title=title, description=description,
                lifecycle_state="promoted", request_uuid=req, reason="node creation",
            )
            report = self._replace_references(con, source_node_uuid=node, source_revision_uuid=rev, description=description, strict=True)
            con.execute(
                "INSERT INTO graph_membership(graph_uuid,node_uuid,ordinal) VALUES (?,?,?)",
                (graph["graph_uuid"], node, self._next_ordinal(con, graph["graph_uuid"])),
            )
            self._refresh_fts(con, node)
            self._audit(con, request_uuid=req, operation_type="node.create", node_uuid_value=node, new_revision_uuid=rev, details={"graph_key": graph_key, "reference_count": len(report.occurrences)})
            return {"pointer": pointer, "uuid": node, "revision_uuid": rev, "graph_key": graph_key, "reference_count": len(report.occurrences)}
        return self._mutate("pgx.node.create", request_id, payload, action)

    def stage_node(self, *, request_id: str | None, pointer: str, title: str, description: str, intended_graph_key: str | None = None, tracking_note: str = "") -> dict[str, Any]:
        payload = {"pointer": pointer, "title": title, "description": description, "intended_graph_key": intended_graph_key, "tracking_note": tracking_note}
        def action(con: sqlite3.Connection, req: str) -> dict[str, Any]:
            if intended_graph_key is not None:
                intended_graph = self._graph(con, intended_graph_key)
                self._check_graph_pointer(con, intended_graph, pointer)
            node, rev = self._insert_identity(
                con, pointer=pointer, title=title, description=description,
                lifecycle_state="staged", request_uuid=req, reason="staged node creation",
            )
            con.execute(
                "INSERT INTO staging_queue(node_uuid,intended_graph_key,tracking_note,status) VALUES (?,?,?,'pending')",
                (node, intended_graph_key, tracking_note),
            )
            report = self._replace_references(con, source_node_uuid=node, source_revision_uuid=rev, description=description, strict=False)
            if not report.valid:
                con.execute("UPDATE staging_queue SET status='blocked' WHERE node_uuid=?", (node,))
                namespace = self._namespace(con)
                for idx, issue in enumerate(report.errors):
                    timestamp = unique_timestamp(con, "staging_issues")
                    issue_uuid = derived_uuid(namespace, "staging-issue", f"{node}|{rev}|{idx}|{timestamp}")
                    con.execute(
                        "INSERT INTO staging_issues(issue_uuid,node_uuid,issue_code,details_json,created_at,resolved_at) VALUES (?,?,?,?,?,NULL)",
                        (issue_uuid, node, issue.get("code", "reference_error"), _canonical_json(issue), timestamp),
                    )
            self._audit(con, request_uuid=req, operation_type="node.stage", node_uuid_value=node, new_revision_uuid=rev, details={"issue_count": len(report.errors)})
            return {"pointer": pointer, "uuid": node, "revision_uuid": rev, "status": "blocked" if report.errors else "pending", "issues": report.errors}
        return self._mutate("pgx.node.stage", request_id, payload, action)

    def promote_node(self, *, request_id: str | None, pointer: str, graph_key: str | None = None) -> dict[str, Any]:
        payload = {"pointer": pointer, "graph_key": graph_key}
        def action(con: sqlite3.Connection, req: str) -> dict[str, Any]:
            current = self._current(con, pointer)
            if current["lifecycle_state"] != "staged":
                raise ConflictError("only staged nodes can be promoted", {"pointer": pointer, "state": current["lifecycle_state"]})
            queue = con.execute("SELECT * FROM staging_queue WHERE node_uuid=?", (current["uuid"],)).fetchone()
            target_graph = graph_key or (queue["intended_graph_key"] if queue else None)
            if not target_graph:
                raise ContractError("promotion requires a graph_key")
            graph = self._graph(con, target_graph)
            self._check_graph_pointer(con, graph, pointer)
            report = self._replace_references(
                con, source_node_uuid=current["uuid"], source_revision_uuid=current["revision_uuid"],
                description=current["description"], strict=True,
            )
            con.execute("UPDATE node_identity SET lifecycle_state='promoted' WHERE uuid=?", (current["uuid"],))
            con.execute(
                "INSERT INTO graph_membership(graph_uuid,node_uuid,ordinal) VALUES (?,?,?)",
                (graph["graph_uuid"], current["uuid"], self._next_ordinal(con, graph["graph_uuid"])),
            )
            con.execute("DELETE FROM staging_queue WHERE node_uuid=?", (current["uuid"],))
            con.execute("UPDATE staging_issues SET resolved_at=? WHERE node_uuid=? AND resolved_at IS NULL", (now_rfc3339_ns(), current["uuid"]))
            self._refresh_fts(con, current["uuid"])
            self._audit(con, request_uuid=req, operation_type="node.promote", node_uuid_value=current["uuid"], new_revision_uuid=current["revision_uuid"], details={"graph_key": target_graph, "reference_count": len(report.occurrences)})
            return {"pointer": pointer, "uuid": current["uuid"], "revision_uuid": current["revision_uuid"], "graph_key": target_graph, "reference_count": len(report.occurrences)}
        return self._mutate("pgx.node.promote", request_id, payload, action)

    def update_node(self, *, request_id: str | None, pointer: str, title: str | None = None, description: str | None = None, expected_revision_uuid: str | None = None, reason: str = "") -> dict[str, Any]:
        payload = {"pointer": pointer, "title": title, "description": description, "expected_revision_uuid": expected_revision_uuid, "reason": reason}
        def action(con: sqlite3.Connection, req: str) -> dict[str, Any]:
            current = self._current(con, pointer)
            if expected_revision_uuid and current["revision_uuid"] != expected_revision_uuid:
                raise StaleWriteError("expected revision is not current", {"expected": expected_revision_uuid, "current": current["revision_uuid"]})
            new_title = title if title is not None else current["title"]
            new_description = description if description is not None else current["description"]
            if new_title == current["title"] and new_description == current["description"]:
                return {"pointer": pointer, "uuid": current["uuid"], "revision_uuid": current["revision_uuid"], "unchanged": True}
            rev = self._new_revision(
                con, node_uuid_value=current["uuid"], title=new_title, description=new_description,
                previous_revision_uuid=current["revision_uuid"], request_uuid=req, reason=reason or "node update",
            )
            strict = current["lifecycle_state"] == "promoted"
            report = self._replace_references(con, source_node_uuid=current["uuid"], source_revision_uuid=rev, description=new_description, strict=strict)
            con.execute("UPDATE node_identity SET current_revision_uuid=? WHERE uuid=?", (rev, current["uuid"]))
            if strict:
                self._refresh_fts(con, current["uuid"])
            else:
                con.execute("DELETE FROM staging_issues WHERE node_uuid=?", (current["uuid"],))
                status = "pending"
                if report.errors:
                    status = "blocked"
                    namespace = self._namespace(con)
                    for idx, issue in enumerate(report.errors):
                        timestamp = unique_timestamp(con, "staging_issues")
                        issue_uuid = derived_uuid(namespace, "staging-issue", f"{current['uuid']}|{rev}|{idx}|{timestamp}")
                        con.execute(
                            "INSERT INTO staging_issues(issue_uuid,node_uuid,issue_code,details_json,created_at,resolved_at) VALUES (?,?,?,?,?,NULL)",
                            (issue_uuid, current["uuid"], issue.get("code", "reference_error"), _canonical_json(issue), timestamp),
                        )
                con.execute("UPDATE staging_queue SET status=? WHERE node_uuid=?", (status, current["uuid"]))
            self._audit(con, request_uuid=req, operation_type="node.update", node_uuid_value=current["uuid"], previous_revision_uuid=current["revision_uuid"], new_revision_uuid=rev, details={"reason": reason, "reference_count": len(report.occurrences)})
            return {"pointer": pointer, "uuid": current["uuid"], "previous_revision_uuid": current["revision_uuid"], "revision_uuid": rev, "reference_count": len(report.occurrences), "warnings": report.warnings}
        return self._mutate("pgx.node.update", request_id, payload, action)

    def embed_traversal(
        self,
        *,
        request_id: str | None,
        node_pointer: str,
        expression: dict[str, Any],
        read: str | None = None,
        expected_revision_uuid: str | None = None,
        reason: str = "embed lawful PGX traversal expression",
    ) -> dict[str, Any]:
        tree = tree_from_mapping(expression)
        notation = serialize_expression(tree)
        roles = pointer_roles(tree)
        block = render_embedding(notation, read)
        payload = {
            "node_pointer": node_pointer,
            "expression": expression,
            "read": read,
            "expected_revision_uuid": expected_revision_uuid,
            "reason": reason,
        }

        def action(con: sqlite3.Connection, req: str) -> dict[str, Any]:
            current = self._current(con, node_pointer)
            if expected_revision_uuid and current["revision_uuid"] != expected_revision_uuid:
                raise StaleWriteError(
                    "expected revision is not current",
                    {"expected": expected_revision_uuid, "current": current["revision_uuid"]},
                )

            pointer_pattern = self._pointer_pattern(con)
            resolved = []
            for pointer in sorted(roles):
                validate_pointer(pointer, pointer_pattern)
                row = self._current(con, pointer)
                resolved.append({
                    "pointer": pointer,
                    "title": row["title"],
                    "roles": sorted(roles[pointer]),
                })

            separator = "" if not current["description"].strip() else "\n\n"
            new_description = current["description"].rstrip() + separator + block
            rev = self._new_revision(
                con,
                node_uuid_value=current["uuid"],
                title=current["title"],
                description=new_description,
                previous_revision_uuid=current["revision_uuid"],
                request_uuid=req,
                reason=reason,
            )
            strict = current["lifecycle_state"] == "promoted"
            report = self._replace_references(
                con,
                source_node_uuid=current["uuid"],
                source_revision_uuid=rev,
                description=new_description,
                strict=strict,
            )
            con.execute(
                "UPDATE node_identity SET current_revision_uuid=? WHERE uuid=?",
                (rev, current["uuid"]),
            )
            if strict:
                self._refresh_fts(con, current["uuid"])
            else:
                con.execute("DELETE FROM staging_issues WHERE node_uuid=?", (current["uuid"],))
                status = "pending"
                if report.errors:
                    status = "blocked"
                    namespace = self._namespace(con)
                    for idx, issue in enumerate(report.errors):
                        timestamp = unique_timestamp(con, "staging_issues")
                        issue_uuid = derived_uuid(
                            namespace,
                            "staging-issue",
                            f"{current['uuid']}|{rev}|{idx}|{timestamp}",
                        )
                        con.execute(
                            "INSERT INTO staging_issues(issue_uuid,node_uuid,issue_code,details_json,created_at,resolved_at) VALUES (?,?,?,?,?,NULL)",
                            (issue_uuid, current["uuid"], issue.get("code", "reference_error"), _canonical_json(issue), timestamp),
                        )
                con.execute("UPDATE staging_queue SET status=? WHERE node_uuid=?", (status, current["uuid"]))

            self._audit(
                con,
                request_uuid=req,
                operation_type="traversal.embed",
                node_uuid_value=current["uuid"],
                previous_revision_uuid=current["revision_uuid"],
                new_revision_uuid=rev,
                details={"notation": notation, "resolved_pointers": [item["pointer"] for item in resolved]},
            )
            return {
                "node_pointer": node_pointer,
                "uuid": current["uuid"],
                "previous_revision_uuid": current["revision_uuid"],
                "revision_uuid": rev,
                "notation": notation,
                "markdown": block,
                "resolved_pointers": resolved,
                "reference_count": len(report.occurrences),
                "warnings": report.warnings,
            }

        return self._mutate("pgx.traversal.embed", request_id, payload, action)

    def revert_node(self, *, request_id: str | None, pointer: str, target_revision_uuid: str, expected_revision_uuid: str | None = None, reason: str = "revert") -> dict[str, Any]:
        with connect(self.path, readonly=True) as read:
            target = read.execute(
                "SELECT title,description FROM node_revision r JOIN node_identity i ON i.uuid=r.node_uuid WHERE i.pointer=? AND r.revision_uuid=?",
                (pointer, target_revision_uuid),
            ).fetchone()
        if target is None:
            raise NotFoundError("target revision not found", {"pointer": pointer, "revision_uuid": target_revision_uuid})
        return self.update_node(
            request_id=request_id,
            pointer=pointer,
            title=target["title"],
            description=target["description"],
            expected_revision_uuid=expected_revision_uuid,
            reason=reason,
        )

    def add_triple(self, *, request_id: str | None, subject_pointer: str, predicate_pointer: str, object_pointer: str) -> dict[str, Any]:
        payload = {"subject_pointer": subject_pointer, "predicate_pointer": predicate_pointer, "object_pointer": object_pointer}
        def action(con: sqlite3.Connection, req: str) -> dict[str, Any]:
            subject = self._current(con, subject_pointer)
            predicate = self._current(con, predicate_pointer)
            obj = self._current(con, object_pointer)
            if not con.execute("SELECT 1 FROM predicate_registry WHERE predicate_uuid=?", (predicate["uuid"],)).fetchone():
                raise ContractError("predicate pointer is not registered", {"pointer": predicate_pointer})
            existing = con.execute(
                "SELECT triple_uuid,created_at FROM triples WHERE subject_uuid=? AND predicate_uuid=? AND object_uuid=?",
                (subject["uuid"], predicate["uuid"], obj["uuid"]),
            ).fetchone()
            if existing:
                return {"triple_uuid": existing["triple_uuid"], "already_present": True}
            namespace = self._namespace(con)
            triple_uuid = derived_uuid(namespace, "triple", f"{subject['uuid']}|{predicate['uuid']}|{obj['uuid']}")
            created = unique_timestamp(con, "triples")
            con.execute(
                "INSERT INTO triples(triple_uuid,subject_uuid,predicate_uuid,object_uuid,created_at,request_uuid) VALUES (?,?,?,?,?,?)",
                (triple_uuid, subject["uuid"], predicate["uuid"], obj["uuid"], created, req),
            )
            self._audit(con, request_uuid=req, operation_type="triple.add", details={"triple_uuid": triple_uuid, **payload})
            return {"triple_uuid": triple_uuid, "already_present": False}
        return self._mutate("pgx.triple.add", request_id, payload, action)

    def create_tag(self, *, request_id: str | None, pointer: str, title: str, description: str) -> dict[str, Any]:
        payload = {"pointer": pointer, "title": title, "description": description}
        def action(con: sqlite3.Connection, req: str) -> dict[str, Any]:
            graph = self._graph_by_prefix(con, "TGN")
            self._check_graph_pointer(con, graph, pointer)
            node, rev = self._insert_identity(con, pointer=pointer, title=title, description=description, lifecycle_state="promoted", request_uuid=req, reason="tag creation")
            self._replace_references(con, source_node_uuid=node, source_revision_uuid=rev, description=description, strict=True)
            con.execute("INSERT INTO graph_membership(graph_uuid,node_uuid,ordinal) VALUES (?,?,?)", (graph["graph_uuid"], node, self._next_ordinal(con, graph["graph_uuid"])))
            con.execute("INSERT INTO tag_registry(tag_uuid) VALUES (?)", (node,))
            self._refresh_fts(con, node)
            self._audit(con, request_uuid=req, operation_type="tag.create", node_uuid_value=node, new_revision_uuid=rev)
            return {"pointer": pointer, "uuid": node, "revision_uuid": rev}
        return self._mutate("pgx.tag.create", request_id, payload, action)

    def assign_tag(self, *, request_id: str | None, subject_pointer: str, tag_pointer: str) -> dict[str, Any]:
        payload = {"subject_pointer": subject_pointer, "tag_pointer": tag_pointer}
        def action(con: sqlite3.Connection, req: str) -> dict[str, Any]:
            subject = self._current(con, subject_pointer)
            tag = self._current(con, tag_pointer)
            if not con.execute("SELECT 1 FROM tag_registry WHERE tag_uuid=?", (tag["uuid"],)).fetchone():
                raise ContractError("tag pointer is not registered", {"pointer": tag_pointer})
            existing = con.execute("SELECT assignment_uuid FROM node_tags WHERE subject_uuid=? AND tag_uuid=?", (subject["uuid"], tag["uuid"])).fetchone()
            if existing:
                return {"assignment_uuid": existing["assignment_uuid"], "already_present": True}
            namespace = self._namespace(con)
            assignment = derived_uuid(namespace, "tag-assignment", f"{subject['uuid']}|{tag['uuid']}")
            con.execute(
                "INSERT INTO node_tags(assignment_uuid,subject_uuid,tag_uuid,created_at,request_uuid) VALUES (?,?,?,?,?)",
                (assignment, subject["uuid"], tag["uuid"], unique_timestamp(con, "node_tags"), req),
            )
            self._audit(con, request_uuid=req, operation_type="tag.assign", node_uuid_value=subject["uuid"], details=payload)
            return {"assignment_uuid": assignment, "already_present": False}
        return self._mutate("pgx.tag.assign", request_id, payload, action)

    # ---------- read and traversal API ----------

    def get_node(self, pointer: str) -> dict[str, Any]:
        connection = connect(self.path, readonly=True)
        try:
            node = self._current(connection, pointer)
            graph = connection.execute(
                """SELECT g.graph_key,g.pointer_prefix,gm.ordinal FROM graph_membership gm
                JOIN graphs g ON g.graph_uuid=gm.graph_uuid WHERE gm.node_uuid=?""",
                (node["uuid"],),
            ).fetchone()
            tags = [r[0] for r in connection.execute(
                "SELECT i.pointer FROM node_tags nt JOIN node_identity i ON i.uuid=nt.tag_uuid WHERE nt.subject_uuid=? ORDER BY i.pointer",
                (node["uuid"],),
            )]
            result = dict(node)
            result["graph"] = _row(graph)
            result["tags"] = tags
            return result
        finally:
            connection.close()

    def node_history(self, pointer: str, limit: int = 100, cursor: int = 0) -> dict[str, Any]:
        limit = max(1, min(limit, 100))
        cursor = max(0, cursor)
        connection = connect(self.path, readonly=True)
        try:
            current = self._current(connection, pointer)
            total = connection.execute("SELECT COUNT(*) FROM node_revision WHERE node_uuid=?", (current["uuid"],)).fetchone()[0]
            rows = [dict(r) for r in connection.execute(
                "SELECT * FROM node_revision WHERE node_uuid=? ORDER BY created_at DESC LIMIT ? OFFSET ?",
                (current["uuid"], limit, cursor),
            )]
            return {"pointer": pointer, "current_revision_uuid": current["revision_uuid"], "total": total, "cursor": cursor, "next_cursor": cursor + len(rows) if cursor + len(rows) < total else None, "revisions": rows}
        finally:
            connection.close()

    def search_nodes(self, query: str, limit: int = 20, cursor: int = 0) -> dict[str, Any]:
        limit = max(1, min(limit, 100))
        cursor = max(0, cursor)
        terms = [t for t in query.strip().split() if t]
        if not terms:
            raise ContractError("search query must not be empty")
        match = " AND ".join('"' + t.replace('"', '""') + '"' for t in terms)
        connection = connect(self.path, readonly=True)
        try:
            try:
                total = connection.execute("SELECT COUNT(*) FROM node_fts WHERE node_fts MATCH ?", (match,)).fetchone()[0]
                rows = [dict(r) for r in connection.execute(
                    """SELECT pointer,title,snippet(node_fts,2,'[',']','…',18) AS excerpt,node_uuid,revision_uuid,graph_key,bm25(node_fts) AS rank
                    FROM node_fts WHERE node_fts MATCH ? ORDER BY rank,pointer LIMIT ? OFFSET ?""",
                    (match, limit, cursor),
                )]
            except sqlite3.OperationalError as exc:
                raise ContractError("invalid full-text query", {"query": query, "error": str(exc)}) from exc
            return {"query": query, "total": total, "cursor": cursor, "next_cursor": cursor + len(rows) if cursor + len(rows) < total else None, "results": rows}
        finally:
            connection.close()

    def plan_legacy_reference_migration(self, include_staged: bool = True) -> dict[str, Any]:
        connection = connect(self.path, readonly=True)
        try:
            profile = self._profile(connection)
            engine = ReferenceEngine(profile)

            def title_for(pointer: str) -> str | None:
                row = connection.execute(
                    """SELECT r.title FROM node_identity i
                    JOIN node_revision r ON r.revision_uuid=i.current_revision_uuid
                    WHERE i.pointer=?""",
                    (pointer,),
                ).fetchone()
                return row[0] if row else None

            query = "SELECT * FROM current_nodes"
            params: tuple[Any, ...] = ()
            if not include_staged:
                query += " WHERE lifecycle_state='promoted'"
            query += " ORDER BY pointer"
            changed: list[dict[str, Any]] = []
            long_count = short_count = skipped = unresolved = 0
            for row in connection.execute(query, params):
                rewrite = rewrite_legacy_references(
                    row["description"], engine=engine, target_title=title_for
                )
                if not rewrite.conversions:
                    skipped += rewrite.skipped_protected
                    unresolved += len(rewrite.skipped_unresolved)
                    continue
                node_long = sum(c.kind == "long" for c in rewrite.conversions)
                node_short = sum(c.kind == "short" for c in rewrite.conversions)
                long_count += node_long
                short_count += node_short
                skipped += rewrite.skipped_protected
                unresolved += len(rewrite.skipped_unresolved)
                changed.append({
                    "pointer": row["pointer"],
                    "lifecycle_state": row["lifecycle_state"],
                    "current_revision_uuid": row["revision_uuid"],
                    "legacy_references": len(rewrite.conversions),
                    "long_references": node_long,
                    "short_references": node_short,
                    "targets": [c.pointer for c in rewrite.conversions],
                })
            return {
                "include_staged": include_staged,
                "scanned_nodes": connection.execute(
                    "SELECT COUNT(*) FROM current_nodes" + ("" if include_staged else " WHERE lifecycle_state='promoted'")
                ).fetchone()[0],
                "changed_nodes": len(changed),
                "legacy_references": long_count + short_count,
                "long_references": long_count,
                "short_references": short_count,
                "skipped_protected": skipped,
                "skipped_unresolved": unresolved,
                "nodes": changed,
            }
        finally:
            connection.close()

    def migrate_legacy_references(
        self,
        *,
        request_id: str | None,
        include_staged: bool = True,
        reason: str = "convert explicit legacy PGX citations to canonical bare-pointer Markdown links",
    ) -> dict[str, Any]:
        payload = {"include_staged": include_staged, "reason": reason}

        def action(con: sqlite3.Connection, req: str) -> dict[str, Any]:
            profile = self._profile(con)
            engine = ReferenceEngine(profile)

            def title_for(pointer: str) -> str | None:
                row = con.execute(
                    """SELECT r.title FROM node_identity i
                    JOIN node_revision r ON r.revision_uuid=i.current_revision_uuid
                    WHERE i.pointer=?""",
                    (pointer,),
                ).fetchone()
                return row[0] if row else None

            query = "SELECT * FROM current_nodes"
            if not include_staged:
                query += " WHERE lifecycle_state='promoted'"
            query += " ORDER BY pointer"
            planned: list[tuple[sqlite3.Row, Any]] = []
            skipped = 0
            unresolved = 0
            for row in con.execute(query).fetchall():
                rewrite = rewrite_legacy_references(
                    row["description"], engine=engine, target_title=title_for
                )
                skipped += rewrite.skipped_protected
                unresolved += len(rewrite.skipped_unresolved)
                if rewrite.conversions:
                    planned.append((row, rewrite))

            if not planned:
                return {
                    "unchanged": True,
                    "include_staged": include_staged,
                    "scanned_nodes": con.execute(
                        "SELECT COUNT(*) FROM current_nodes" + ("" if include_staged else " WHERE lifecycle_state='promoted'")
                    ).fetchone()[0],
                    "changed_nodes": 0,
                    "legacy_references": 0,
                    "long_references": 0,
                    "short_references": 0,
                    "skipped_protected": skipped,
                    "skipped_unresolved": unresolved,
                    "revisions": [],
                }

            revisions: list[dict[str, Any]] = []
            long_count = short_count = indexed_count = 0
            for current, rewrite in planned:
                new_revision_uuid = self._new_revision(
                    con,
                    node_uuid_value=current["uuid"],
                    title=current["title"],
                    description=rewrite.description,
                    previous_revision_uuid=current["revision_uuid"],
                    request_uuid=req,
                    reason=reason,
                )
                strict = current["lifecycle_state"] == "promoted"
                report = self._replace_references(
                    con,
                    source_node_uuid=current["uuid"],
                    source_revision_uuid=new_revision_uuid,
                    description=rewrite.description,
                    strict=strict,
                )
                con.execute(
                    "UPDATE node_identity SET current_revision_uuid=? WHERE uuid=?",
                    (new_revision_uuid, current["uuid"]),
                )
                if strict:
                    self._refresh_fts(con, current["uuid"])
                else:
                    con.execute("DELETE FROM staging_issues WHERE node_uuid=?", (current["uuid"],))
                    con.execute("UPDATE staging_queue SET status='pending' WHERE node_uuid=?", (current["uuid"],))

                node_long = sum(c.kind == "long" for c in rewrite.conversions)
                node_short = sum(c.kind == "short" for c in rewrite.conversions)
                long_count += node_long
                short_count += node_short
                indexed_count += len(report.occurrences)
                revision_record = {
                    "pointer": current["pointer"],
                    "lifecycle_state": current["lifecycle_state"],
                    "previous_revision_uuid": current["revision_uuid"],
                    "revision_uuid": new_revision_uuid,
                    "converted_references": len(rewrite.conversions),
                    "indexed_references": len(report.occurrences),
                    "targets": [c.pointer for c in rewrite.conversions],
                }
                revisions.append(revision_record)
                self._audit(
                    con,
                    request_uuid=req,
                    operation_type="reference.migrate_legacy.node",
                    node_uuid_value=current["uuid"],
                    previous_revision_uuid=current["revision_uuid"],
                    new_revision_uuid=new_revision_uuid,
                    details=revision_record,
                )

            summary = {
                "include_staged": include_staged,
                "scanned_nodes": con.execute(
                    "SELECT COUNT(*) FROM current_nodes" + ("" if include_staged else " WHERE lifecycle_state='promoted'")
                ).fetchone()[0],
                "changed_nodes": len(revisions),
                "legacy_references": long_count + short_count,
                "long_references": long_count,
                "short_references": short_count,
                "indexed_references": indexed_count,
                "skipped_protected": skipped,
                "skipped_unresolved": unresolved,
                "revisions": revisions,
            }
            self._audit(
                con,
                request_uuid=req,
                operation_type="reference.migrate_legacy",
                details={k: v for k, v in summary.items() if k != "revisions"},
            )
            return summary

        return self._mutate("pgx.reference.migrate_legacy", request_id, payload, action)

    def plan_bare_pointer_migration(self, include_staged: bool = True) -> dict[str, Any]:
        """Preview conversion from the active reference profile to ``[anchor](POINTER)``."""
        connection = connect(self.path, readonly=True)
        try:
            source_profile = self._profile(connection)
            source_engine = ReferenceEngine(source_profile)
            target_profile = bare_pointer_profile(source_profile)
            target_engine = ReferenceEngine(target_profile)
            query = "SELECT * FROM current_nodes"
            if not include_staged:
                query += " WHERE lifecycle_state='promoted'"
            query += " ORDER BY pointer"

            changed: list[dict[str, Any]] = []
            converted = 0
            for row in connection.execute(query):
                rewrite = rewrite_to_bare_pointer_links(
                    row["description"],
                    source_engine=source_engine,
                    target_engine=target_engine,
                    resolver=lambda pointer: self._resolve_pointer(connection, pointer),
                )
                if not rewrite.conversions:
                    continue
                converted += len(rewrite.conversions)
                changed.append({
                    "pointer": row["pointer"],
                    "lifecycle_state": row["lifecycle_state"],
                    "current_revision_uuid": row["revision_uuid"],
                    "converted_references": len(rewrite.conversions),
                    "targets": [conversion.pointer for conversion in rewrite.conversions],
                    "before_sample": rewrite.conversions[0].source_text,
                    "after_sample": rewrite.conversions[0].replacement,
                })

            return {
                "include_staged": include_staged,
                "source_template": source_profile.uri_template,
                "target_template": BARE_POINTER_TEMPLATE,
                "already_canonical": source_engine.is_bare_pointer,
                "scanned_nodes": connection.execute(
                    "SELECT COUNT(*) FROM current_nodes" + ("" if include_staged else " WHERE lifecycle_state='promoted'")
                ).fetchone()[0],
                "changed_nodes": len(changed),
                "converted_references": converted,
                "nodes": changed,
            }
        finally:
            connection.close()

    def migrate_bare_pointer_references(
        self,
        *,
        request_id: str | None,
        include_staged: bool = True,
        reason: str = "adopt the bare-pointer Markdown reference discipline",
    ) -> dict[str, Any]:
        """Atomically adopt ``[natural-language anchor](POINTER)`` corpus-wide."""
        payload = {"include_staged": include_staged, "reason": reason}

        def action(con: sqlite3.Connection, req: str) -> dict[str, Any]:
            source_profile = self._profile(con)
            source_engine = ReferenceEngine(source_profile)
            target_profile = bare_pointer_profile(source_profile)
            target_engine = ReferenceEngine(target_profile)
            query = "SELECT * FROM current_nodes"
            if not include_staged:
                query += " WHERE lifecycle_state='promoted'"
            query += " ORDER BY pointer"
            rows = con.execute(query).fetchall()

            planned: list[tuple[sqlite3.Row, Any]] = []
            for row in rows:
                rewrite = rewrite_to_bare_pointer_links(
                    row["description"],
                    source_engine=source_engine,
                    target_engine=target_engine,
                    resolver=lambda pointer: self._resolve_pointer(con, pointer),
                )
                planned.append((row, rewrite))

            # Profile and metadata change in the same transaction as all node
            # revisions and regenerated occurrence rows.
            con.execute(
                """UPDATE reference_profiles
                SET uri_template=?,resolver_status='resolved'
                WHERE profile_key='pgx-default'""",
                (BARE_POINTER_TEMPLATE,),
            )
            metadata_updates = {
                "parmesan_schema_version": str(SCHEMA_VERSION),
                "canonical_uri_template": BARE_POINTER_TEMPLATE,
                "canonical_reference_destination_template": BARE_POINTER_TEMPLATE,
                "reference_discipline": "bare-pointer-markdown-link-v1",
                "reference_scope": "active-corpus",
                "reference_network_behavior": "none",
            }
            for key, value in metadata_updates.items():
                con.execute(
                    "INSERT INTO metadata(key,value) VALUES (?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                    (key, value),
                )
            con.execute(
                "INSERT OR IGNORE INTO schema_migrations(version,applied_at,description) VALUES (?,?,?)",
                (SCHEMA_VERSION, unique_timestamp(con, "schema_migrations", "applied_at"), "Parmesan 2.3 bare-pointer Markdown reference discipline"),
            )

            revisions: list[dict[str, Any]] = []
            converted_count = 0
            indexed_count = 0
            for current, rewrite in planned:
                description = rewrite.description
                current_revision_uuid = current["revision_uuid"]
                if rewrite.conversions:
                    new_revision_uuid = self._new_revision(
                        con,
                        node_uuid_value=current["uuid"],
                        title=current["title"],
                        description=description,
                        previous_revision_uuid=current_revision_uuid,
                        request_uuid=req,
                        reason=reason,
                    )
                    con.execute(
                        "UPDATE node_identity SET current_revision_uuid=? WHERE uuid=?",
                        (new_revision_uuid, current["uuid"]),
                    )
                    revision_record = {
                        "pointer": current["pointer"],
                        "lifecycle_state": current["lifecycle_state"],
                        "previous_revision_uuid": current_revision_uuid,
                        "revision_uuid": new_revision_uuid,
                        "converted_references": len(rewrite.conversions),
                        "targets": [conversion.pointer for conversion in rewrite.conversions],
                    }
                    revisions.append(revision_record)
                    converted_count += len(rewrite.conversions)
                    self._audit(
                        con,
                        request_uuid=req,
                        operation_type="reference.migrate_bare_pointer.node",
                        node_uuid_value=current["uuid"],
                        previous_revision_uuid=current_revision_uuid,
                        new_revision_uuid=new_revision_uuid,
                        details=revision_record,
                    )
                    current_revision_uuid = new_revision_uuid

                report = self._replace_references(
                    con,
                    source_node_uuid=current["uuid"],
                    source_revision_uuid=current_revision_uuid,
                    description=description,
                    strict=current["lifecycle_state"] == "promoted",
                )
                indexed_count += len(report.occurrences)
                if current["lifecycle_state"] == "promoted":
                    self._refresh_fts(con, current["uuid"])

            summary = {
                "include_staged": include_staged,
                "source_template": source_profile.uri_template,
                "target_template": BARE_POINTER_TEMPLATE,
                "already_canonical": source_engine.is_bare_pointer,
                "scanned_nodes": len(rows),
                "changed_nodes": len(revisions),
                "converted_references": converted_count,
                "indexed_references": indexed_count,
                "revisions": revisions,
            }
            self._audit(
                con,
                request_uuid=req,
                operation_type="reference.migrate_bare_pointer",
                details={key: value for key, value in summary.items() if key != "revisions"},
            )
            return summary

        return self._mutate("pgx.reference.migrate_bare_pointer", request_id, payload, action)

    def make_reference(self, anchor_text: str, pointer: str, profile_key: str = "pgx-default", verify_target: bool = True) -> dict[str, Any]:
        connection = connect(self.path, readonly=True)
        try:
            profile = self._profile(connection, profile_key)
            target = self._resolve_pointer(connection, pointer)
            if verify_target and target is None:
                raise NotFoundError("reference target not found", {"pointer": pointer})
            engine = ReferenceEngine(profile)
            link = engine.make_link(anchor_text, pointer)
            return {
                "markdown": link,
                "pointer": pointer,
                "destination": engine.template.expand(pointer),
                "target_uuid": target,
                "visible_text": engine.visible_text(link),
                "resolution_scope": "active_corpus" if engine.is_bare_pointer else "profile_defined",
                "network_behavior": "none" if engine.is_bare_pointer else "not_performed_by_parmesan",
                "resolver_status": profile.resolver_status,
            }
        finally:
            connection.close()

    def inspect_uri(self, uri: str) -> dict[str, Any]:
        connection = connect(self.path, readonly=True)
        try:
            profile = self._profile(connection)
            engine = ReferenceEngine(profile)
            pointer = engine.template.extract(uri)
            return {
                "destination": uri,
                "pointer": pointer,
                "discipline": "bare-pointer-markdown-link-v1" if engine.is_bare_pointer else "legacy-uri-profile",
                "scheme": None if engine.is_bare_pointer else engine.template.scheme,
                "resolution_scope": "active_corpus" if engine.is_bare_pointer else "profile_defined",
                "network_behavior": "none",
                "matches_profile": True,
            }
        finally:
            connection.close()

    def resolve_uri(self, uri: str) -> dict[str, Any]:
        connection = connect(self.path, readonly=True)
        try:
            profile = self._profile(connection)
            engine = ReferenceEngine(profile)
            pointer = engine.template.extract(uri)
        finally:
            connection.close()
        node = self.get_node(pointer)
        return {
            "destination": uri,
            "pointer": pointer,
            "resolution_scope": "active_corpus" if engine.is_bare_pointer else "profile_defined",
            "network_behavior": "none",
            "node": node,
        }

    # Canonical names for the 2.3 discipline; URI-named methods remain as
    # compatibility aliases for older callers.
    def inspect_destination(self, destination: str) -> dict[str, Any]:
        return self.inspect_uri(destination)

    def resolve_destination(self, destination: str) -> dict[str, Any]:
        return self.resolve_uri(destination)

    def validate_description(self, description: str, profile_key: str = "pgx-default", verify_targets: bool = True) -> dict[str, Any]:
        connection = connect(self.path, readonly=True)
        try:
            profile = self._profile(connection, profile_key)
            engine = ReferenceEngine(profile)
            report = engine.validate(description, resolver=(lambda p: self._resolve_pointer(connection, p)) if verify_targets else None)
            return report.model_dump()
        finally:
            connection.close()

    def visible_text(self, description: str, profile_key: str = "pgx-default") -> dict[str, Any]:
        connection = connect(self.path, readonly=True)
        try:
            profile = self._profile(connection, profile_key)
            text = ReferenceEngine(profile).visible_text(description)
            return {"visible_text": text}
        finally:
            connection.close()

    def list_references(self, pointer: str, direction: str = "outgoing", limit: int = 50, cursor: int = 0) -> dict[str, Any]:
        limit = max(1, min(limit, 100)); cursor=max(0,cursor)
        connection = connect(self.path, readonly=True)
        try:
            node = self._current(connection, pointer)
            if direction == "outgoing":
                total = connection.execute("SELECT COUNT(*) FROM reference_occurrences WHERE source_node_uuid=?", (node["uuid"],)).fetchone()[0]
                rows = [dict(r) for r in connection.execute(
                    """SELECT ro.*,ti.pointer AS resolved_pointer,tr.title AS target_title
                    FROM reference_occurrences ro
                    LEFT JOIN node_identity ti ON ti.uuid=ro.target_uuid
                    LEFT JOIN node_revision tr ON tr.revision_uuid=ti.current_revision_uuid
                    WHERE ro.source_node_uuid=? ORDER BY ro.ordinal LIMIT ? OFFSET ?""",
                    (node["uuid"], limit, cursor),
                )]
            elif direction == "incoming":
                total = connection.execute("SELECT COUNT(*) FROM reference_occurrences WHERE target_uuid=?", (node["uuid"],)).fetchone()[0]
                rows = [dict(r) for r in connection.execute(
                    """SELECT ro.*,si.pointer AS source_pointer,sr.title AS source_title
                    FROM reference_occurrences ro JOIN node_identity si ON si.uuid=ro.source_node_uuid
                    JOIN node_revision sr ON sr.revision_uuid=si.current_revision_uuid
                    WHERE ro.target_uuid=? ORDER BY si.pointer,ro.ordinal LIMIT ? OFFSET ?""",
                    (node["uuid"], limit, cursor),
                )]
            else:
                raise ContractError("direction must be outgoing or incoming")
            return {"pointer": pointer, "direction": direction, "total": total, "cursor": cursor, "next_cursor": cursor+len(rows) if cursor+len(rows)<total else None, "references": rows}
        finally:
            connection.close()

    def list_triples(self, pointer: str, direction: str = "outgoing", limit: int = 50, cursor: int = 0) -> dict[str, Any]:
        limit=max(1,min(limit,100)); cursor=max(0,cursor)
        connection=connect(self.path, readonly=True)
        try:
            node=self._current(connection,pointer)
            column="subject_uuid" if direction=="outgoing" else "object_uuid" if direction=="incoming" else None
            if column is None: raise ContractError("direction must be outgoing or incoming")
            total=connection.execute(f"SELECT COUNT(*) FROM triples WHERE {column}=?",(node["uuid"],)).fetchone()[0]
            rows=[dict(r) for r in connection.execute(
                f"""SELECT t.triple_uuid,s.pointer subject_pointer,p.pointer predicate_pointer,o.pointer object_pointer,t.created_at
                FROM triples t JOIN node_identity s ON s.uuid=t.subject_uuid JOIN node_identity p ON p.uuid=t.predicate_uuid
                JOIN node_identity o ON o.uuid=t.object_uuid WHERE t.{column}=? ORDER BY t.created_at LIMIT ? OFFSET ?""",
                (node["uuid"],limit,cursor))]
            return {"pointer":pointer,"direction":direction,"total":total,"cursor":cursor,"next_cursor":cursor+len(rows) if cursor+len(rows)<total else None,"triples":rows}
        finally: connection.close()

    def context_pack(self, pointer: str, max_nodes: int = 20, max_chars: int = 12000, include_triples: bool = True) -> dict[str, Any]:
        max_nodes=max(1,min(max_nodes,50)); max_chars=max(1000,min(max_chars,100000))
        connection=connect(self.path, readonly=True)
        try:
            start=self._current(connection,pointer)
            queue=deque([start["uuid"]]); visited=set(); results=[]; chars=0
            while queue and len(results)<max_nodes:
                uid=queue.popleft()
                if uid in visited: continue
                visited.add(uid)
                row=connection.execute("SELECT * FROM current_nodes WHERE uuid=?",(uid,)).fetchone()
                if not row: continue
                record={"pointer":row["pointer"],"title":row["title"],"description":row["description"],"revision_uuid":row["revision_uuid"]}
                cost=len(_canonical_json(record))
                if results and chars+cost>max_chars: break
                results.append(record); chars+=cost
                neighbors=[r[0] for r in connection.execute("SELECT target_uuid FROM reference_occurrences WHERE source_node_uuid=? AND target_uuid IS NOT NULL ORDER BY ordinal",(uid,))]
                if include_triples:
                    neighbors += [r[0] for r in connection.execute("SELECT object_uuid FROM triples WHERE subject_uuid=? ORDER BY created_at",(uid,))]
                for n in neighbors:
                    if n not in visited: queue.append(n)
            sentinels=[]
            if connection.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='sentinel_guidance'").fetchone() is not None:
                sentinels=[dict(row) for row in connection.execute("SELECT n.pointer,n.title,n.description,s.scope FROM sentinel_guidance s JOIN current_nodes n ON n.uuid=s.node_uuid WHERE s.active=1 ORDER BY s.created_at,n.pointer LIMIT 20")]
            return {"root_pointer":pointer,"node_count":len(results),"character_count":chars,"truncated":bool(queue),"nodes":results,"sentinels":sentinels,"sentinels_advisory":True}
        finally: connection.close()

    def serialize_graph(self, graph_key: str) -> str:
        connection=connect(self.path, readonly=True)
        try:
            graph=self._graph(connection,graph_key)
            rows=connection.execute(
                """SELECT c.pointer,c.title,c.description,c.data_one FROM graph_membership gm
                JOIN current_nodes c ON c.uuid=gm.node_uuid WHERE gm.graph_uuid=? ORDER BY gm.ordinal""",
                (graph["graph_uuid"],))
            return "\n".join(serialize_node(r["pointer"],r["title"],r["description"],r["data_one"]) for r in rows)
        finally: connection.close()

    def parse_pgx(self, line: str) -> dict[str, Any]:
        return parse_node(line).__dict__

    # ---------- validation and rebuilding ----------

    def rebuild_derived(self, *, request_id: str | None) -> dict[str, Any]:
        payload={}
        def action(con: sqlite3.Connection, req: str) -> dict[str, Any]:
            con.execute("DELETE FROM reference_occurrences")
            con.execute("DELETE FROM node_fts")
            refs=0; indexed=0
            rows=con.execute("SELECT * FROM current_nodes ORDER BY pointer").fetchall()
            for row in rows:
                report=self._replace_references(con,source_node_uuid=row["uuid"],source_revision_uuid=row["revision_uuid"],description=row["description"],strict=row["lifecycle_state"]=="promoted")
                refs+=len(report.occurrences)
                self._refresh_fts(con,row["uuid"])
                if row["lifecycle_state"]=="promoted": indexed+=1
            self._audit(con,request_uuid=req,operation_type="database.rebuild_derived",details={"references":refs,"indexed":indexed})
            return {"reference_occurrences":refs,"fts_nodes":indexed}
        return self._mutate("pgx.database.rebuild_derived",request_id,payload,action)

    def validate_database(self, *, full: bool = True) -> dict[str, Any]:
        connection=connect(self.path, readonly=True)
        errors=[]; warnings=[]; checks={}
        try:
            checks["integrity_check"]=connection.execute("PRAGMA integrity_check").fetchone()[0]
            if checks["integrity_check"]!="ok": errors.append({"code":"sqlite_integrity","value":checks["integrity_check"]})
            fk=[tuple(r) for r in connection.execute("PRAGMA foreign_key_check")]
            checks["foreign_key_errors"]=len(fk)
            if fk: errors.append({"code":"foreign_keys","rows":fk[:20]})
            meta=self._metadata(connection)
            required={"parmesan_schema_version","uuid_namespace","database_uuid","pointer_pattern","canonical_uri_template","database_sequence"}
            missing=sorted(required-set(meta))
            if missing: errors.append({"code":"metadata_missing","keys":missing})
            namespace=meta.get("uuid_namespace")
            identity_count=0; bad_uuid=[]; bad_time=[]; bad_current=[]
            for row in connection.execute("SELECT * FROM node_identity"):
                identity_count+=1
                if namespace and node_uuid(namespace,row["pointer"])!=row["uuid"]: bad_uuid.append(row["pointer"])
                if not is_rfc3339_ns(row["created_at"]): bad_time.append(row["pointer"])
                rev=connection.execute("SELECT node_uuid FROM node_revision WHERE revision_uuid=?",(row["current_revision_uuid"],)).fetchone()
                if not rev or rev[0]!=row["uuid"]: bad_current.append(row["pointer"])
            checks["identity_count"]=identity_count
            if bad_uuid: errors.append({"code":"uuid_determinism","pointers":bad_uuid[:50],"count":len(bad_uuid)})
            if bad_time: errors.append({"code":"identity_timestamp","pointers":bad_time[:50]})
            if bad_current: errors.append({"code":"current_revision","pointers":bad_current[:50]})
            bad_hash=[]; bad_revision_time=[]; chain_cycles=[]
            for row in connection.execute("SELECT * FROM node_revision"):
                if sha256_text(row["title"]+"\0"+row["description"])!=row["content_hash"]: bad_hash.append(row["revision_uuid"])
                if not is_rfc3339_ns(row["created_at"]): bad_revision_time.append(row["revision_uuid"])
            if bad_hash: errors.append({"code":"revision_hash","count":len(bad_hash),"revisions":bad_hash[:20]})
            if bad_revision_time: errors.append({"code":"revision_timestamp","count":len(bad_revision_time)})
            # Detect chain cycles by walking each current revision.
            for row in connection.execute("SELECT uuid,current_revision_uuid FROM node_identity"):
                seen=set(); cur=row["current_revision_uuid"]
                while cur:
                    if cur in seen: chain_cycles.append(row["uuid"]); break
                    seen.add(cur)
                    pr=connection.execute("SELECT previous_revision_uuid FROM node_revision WHERE revision_uuid=?",(cur,)).fetchone()
                    cur=pr[0] if pr else None
            if chain_cycles: errors.append({"code":"revision_cycle","node_uuids":chain_cycles[:20]})
            promoted=connection.execute("SELECT COUNT(*) FROM node_identity WHERE lifecycle_state='promoted'").fetchone()[0]
            staged=connection.execute("SELECT COUNT(*) FROM node_identity WHERE lifecycle_state='staged'").fetchone()[0]
            memberships=connection.execute("SELECT COUNT(*) FROM graph_membership").fetchone()[0]
            checks.update({"promoted_nodes":promoted,"staged_nodes":staged,"graph_memberships":memberships})
            missing_members=[r[0] for r in connection.execute("SELECT pointer FROM node_identity i WHERE lifecycle_state='promoted' AND NOT EXISTS(SELECT 1 FROM graph_membership gm WHERE gm.node_uuid=i.uuid)")]
            if missing_members: errors.append({"code":"promoted_without_graph","pointers":missing_members[:50],"count":len(missing_members)})
            staged_members=[r[0] for r in connection.execute("SELECT pointer FROM node_identity i WHERE lifecycle_state='staged' AND EXISTS(SELECT 1 FROM graph_membership gm WHERE gm.node_uuid=i.uuid)")]
            if staged_members: errors.append({"code":"staged_in_graph","pointers":staged_members})
            namespace_bad=[]
            for r in connection.execute(
                """SELECT i.pointer,g.graph_uuid,g.pointer_prefix,g.graph_key
                   FROM graph_membership gm
                   JOIN node_identity i ON i.uuid=gm.node_uuid
                   JOIN graphs g ON g.graph_uuid=gm.graph_uuid"""
            ):
                resolved = self._resolve_graph_namespace(connection, r["pointer"])
                if resolved is None or resolved["graph_uuid"] != r["graph_uuid"]:
                    namespace_bad.append({
                        "pointer": r["pointer"],
                        "assigned_graph_key": r["graph_key"],
                        "assigned_prefix": r["pointer_prefix"],
                        "resolved_graph_key": resolved["graph_key"] if resolved else None,
                        "resolved_prefix": resolved["pointer_prefix"] if resolved else None,
                    })
            if namespace_bad:
                errors.append({"code":"graph_namespace","rows":namespace_bad[:50],"count":len(namespace_bad)})
            if full:
                ref_mismatches=[]; ref_errors=[]; roundtrip=[]
                profile=self._profile(connection)
                engine=ReferenceEngine(profile)
                for row in connection.execute("SELECT * FROM current_nodes ORDER BY pointer"):
                    report=engine.validate(row["description"],resolver=lambda p:self._resolve_pointer(connection,p),strict_markers=True)
                    if row["lifecycle_state"]=="promoted" and not report.valid:
                        ref_errors.append({"pointer":row["pointer"],"errors":report.errors})
                    stored=[dict(x) for x in connection.execute("SELECT ordinal,target_pointer,anchor_text,canonical_uri,char_start,char_end,token_path,occurrence_fingerprint FROM reference_occurrences WHERE source_revision_uuid=? ORDER BY ordinal",(row["revision_uuid"],))]
                    derived=[{"ordinal":x.ordinal,"target_pointer":x.pointer,"anchor_text":x.anchor_text,"canonical_uri":x.canonical_uri,"char_start":x.char_start,"char_end":x.char_end,"token_path":x.token_path,"occurrence_fingerprint":x.fingerprint} for x in report.occurrences] if report.valid else []
                    if stored!=derived: ref_mismatches.append(row["pointer"])
                    if not roundtrip_equal(row["pointer"],row["title"],row["description"],row["data_one"]): roundtrip.append(row["pointer"])
                if ref_errors: errors.append({"code":"promoted_reference_contract","count":len(ref_errors),"examples":ref_errors[:10]})
                if ref_mismatches: errors.append({"code":"reference_index_mismatch","count":len(ref_mismatches),"pointers":ref_mismatches[:50]})
                if roundtrip: errors.append({"code":"pgx_roundtrip","count":len(roundtrip),"pointers":roundtrip[:50]})
            fts_count=connection.execute("SELECT COUNT(*) FROM node_fts").fetchone()[0]
            checks["fts_count"]=fts_count
            if fts_count!=promoted: errors.append({"code":"fts_count","expected":promoted,"actual":fts_count})
            checks["reference_occurrences"]=connection.execute("SELECT COUNT(*) FROM reference_occurrences").fetchone()[0]
            checks["triples"]=connection.execute("SELECT COUNT(*) FROM triples").fetchone()[0]
            checks["tags"]=connection.execute("SELECT COUNT(*) FROM tag_registry").fetchone()[0]
            checks["database_sequence"]=int(meta.get("database_sequence","-1"))
            head = self._head_row(connection)
            if head is None:
                checks["authority_head"] = "migration_required"
                warnings.append({
                    "code": "authority_migration_required",
                    "message": "Inspection is allowed, but mutation requires an explicit authority migration.",
                })
            else:
                checks["authority_head"] = {
                    "corpus_id": head["corpus_id"],
                    "snapshot_uuid": head["snapshot_uuid"],
                    "database_sequence": head["database_sequence"],
                }
                snapshot = connection.execute(
                    """SELECT corpus_id,database_sequence FROM semantic_snapshots
                       WHERE snapshot_uuid=?""",
                    (head["snapshot_uuid"],),
                ).fetchone()
                authority_mismatches = []
                expected_corpus = meta.get("corpus_id") or meta.get("database_uuid")
                if head["corpus_id"] != expected_corpus:
                    authority_mismatches.append("corpus_id")
                if int(head["database_sequence"]) != checks["database_sequence"]:
                    authority_mismatches.append("database_sequence")
                if snapshot is None:
                    authority_mismatches.append("snapshot_uuid")
                elif (
                    snapshot["corpus_id"] != head["corpus_id"]
                    or int(snapshot["database_sequence"]) != int(head["database_sequence"])
                ):
                    authority_mismatches.append("snapshot_metadata")
                if authority_mismatches:
                    errors.append({
                        "code": "authority_head_mismatch",
                        "fields": authority_mismatches,
                    })
            return {"valid":not errors,"checks":checks,"errors":errors,"warnings":warnings}
        finally:
            connection.close()

    # ---------- lineage and materialization ----------

    def _ensure_sentinel_graph(self, connection: sqlite3.Connection, request_uuid: str) -> sqlite3.Row:
        row = connection.execute("SELECT * FROM graphs WHERE graph_key='sentinels'").fetchone()
        if row is not None:
            return row
        node, revision = self._insert_identity(
            connection, pointer="SNT000", title="object: advisory sentinels",
            description="Corpus-local, text-first operating guidance. Sentinels are advisory data and never override system or user instructions.",
            lifecycle_state="promoted", request_uuid=request_uuid, reason="create reserved sentinel graph",
        )
        connection.execute("INSERT INTO graphs(graph_uuid,graph_key,pointer_prefix,description) VALUES (?,?,?,?)", (node, "sentinels", "SNT", "Advisory corpus-local guidance."))
        connection.execute("INSERT INTO graph_membership(graph_uuid,node_uuid,ordinal) VALUES (?,?,0)", (node, node))
        self._replace_references(connection, source_node_uuid=node, source_revision_uuid=revision, description="Corpus-local, text-first operating guidance. Sentinels are advisory data and never override system or user instructions.", strict=True)
        self._refresh_fts(connection, node)
        return self._graph(connection, "sentinels")

    def create_sentinel(self, *, request_id: str | None, pointer: str, title: str, guidance: str, scope: str = "corpus") -> dict[str, Any]:
        payload = {"pointer": pointer, "title": title, "guidance": guidance, "scope": scope}
        def action(connection: sqlite3.Connection, req: str) -> dict[str, Any]:
            self._ensure_lineage_schema(connection)
            graph = self._ensure_sentinel_graph(connection, req)
            self._check_graph_pointer(connection, graph, pointer)
            node, revision = self._insert_identity(connection, pointer=pointer, title=title, description=guidance, lifecycle_state="promoted", request_uuid=req, reason="create advisory sentinel")
            connection.execute("INSERT INTO graph_membership(graph_uuid,node_uuid,ordinal) VALUES (?,?,?)", (graph["graph_uuid"], node, self._next_ordinal(connection, graph["graph_uuid"])))
            connection.execute("INSERT INTO sentinel_guidance(node_uuid,scope,active,created_at) VALUES (?,?,1,?)", (node, scope, unique_timestamp(connection, "sentinel_guidance", "created_at")))
            self._replace_references(connection, source_node_uuid=node, source_revision_uuid=revision, description=guidance, strict=True)
            self._refresh_fts(connection, node)
            self._audit(connection, request_uuid=req, operation_type="sentinel.create", node_uuid_value=node, new_revision_uuid=revision, details={"scope": scope})
            return {"pointer": pointer, "uuid": node, "revision_uuid": revision, "scope": scope, "advisory": True}
        return self._mutate("pgx.sentinel.create", request_id, payload, action)

    def list_sentinels(self, *, active_only: bool = True) -> dict[str, Any]:
        connection = connect(self.path, readonly=True)
        try:
            if connection.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='sentinel_guidance'").fetchone() is None:
                return {"advisory": True, "sentinels": []}
            query = """SELECT n.pointer,n.title,n.description,n.revision_uuid,s.scope,s.active
                       FROM sentinel_guidance s JOIN current_nodes n ON n.uuid=s.node_uuid"""
            if active_only:
                query += " WHERE s.active=1"
            query += " ORDER BY s.created_at,n.pointer"
            return {"advisory": True, "sentinels": [dict(row) for row in connection.execute(query)]}
        finally:
            connection.close()

    def lineage_describe(self) -> dict[str, Any]:
        connection = connect(self.path, readonly=True)
        try:
            metadata = self._metadata(connection)
            if "corpus_id" not in metadata or connection.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='corpus_workstreams'").fetchone() is None:
                return {
                    "corpus_id": metadata.get("database_uuid"),
                    "snapshot_id": None,
                    "snapshot_fingerprint": None,
                    "workstreams": [],
                    "materializations": [],
                    "migration_required": True,
                }
            snapshot = self._semantic_snapshot(connection)
            workstreams = [dict(row) for row in connection.execute(
                "SELECT workstream_id,base_snapshot_id,created_at,package_release_id,mutation_count FROM corpus_workstreams ORDER BY created_at DESC LIMIT 50"
            )]
            materializations = [dict(row) for row in connection.execute(
                "SELECT materialization_id,snapshot_id,workstream_id,kind,created_at,details_json FROM materializations ORDER BY created_at DESC LIMIT 50"
            )]
            for item in materializations:
                item["details"] = json.loads(item.pop("details_json"))
            return {**snapshot, "workstreams": workstreams, "materializations": materializations, "migration_required": False}
        finally:
            connection.close()

    def materialize_database(self, output: str | Path, *, overwrite: bool = False) -> dict[str, Any]:
        self.require_publish_mode("pgx.materialize.database")
        target = Path(output).expanduser().resolve()
        if target == self.path.resolve():
            raise ContractError("materialization output must differ from the authoritative database", {"output": str(target)})
        if target.exists() and not overwrite:
            raise ConflictError("materialization output already exists", {"output": str(target)})
        target.parent.mkdir(parents=True, exist_ok=True)
        # The additive migration is operational metadata, not a semantic graph mutation.
        writable = connect(self.path)
        try:
            writable.execute("BEGIN IMMEDIATE")
            self._ensure_lineage_schema(writable)
            writable.commit()
        finally:
            writable.close()
        source = connect(self.path, readonly=True)
        destination = sqlite3.connect(str(target))
        try:
            snapshot = self._semantic_snapshot(source)
            source.backup(destination)
            materialization_id = str(uuid.uuid4())
            created_at = now_rfc3339_ns()
            destination.execute("PRAGMA journal_mode=DELETE")
            destination.execute(
                """INSERT INTO materializations(materialization_id,corpus_id,snapshot_id,workstream_id,kind,created_at,details_json)
                   VALUES (?,?,?,?,?,?,?)""",
                (materialization_id, snapshot["corpus_id"], snapshot["snapshot_id"], self.workstream_id, "database", created_at,
                 _canonical_json({"source_database": str(self.path.resolve()), "snapshot_fingerprint": snapshot["snapshot_fingerprint"], "package_release_id": __release_id__})),
            )
            destination.commit()
        finally:
            source.close()
            destination.close()
        return {"kind": "database", "database": str(target), "materialization_id": materialization_id, **snapshot}

    def compare_lineage(self, other_database: str | Path) -> dict[str, Any]:
        other = SQLitePGXStore(other_database)
        ours = self.lineage_describe()
        theirs = other.lineage_describe()
        if ours.get("corpus_id") != theirs.get("corpus_id"):
            return {"same_corpus": False, "left": ours, "right": theirs, "common_base_snapshot_id": None, "reconciliation_candidates": []}
        left = connect(self.path, readonly=True)
        right = connect(other.path, readonly=True)
        try:
            left_nodes = {row["pointer"]: row["content_hash"] for row in left.execute("SELECT pointer,content_hash FROM current_nodes")}
            right_nodes = {row["pointer"]: row["content_hash"] for row in right.execute("SELECT pointer,content_hash FROM current_nodes")}
        finally:
            left.close(); right.close()
        changed = sorted(pointer for pointer in set(left_nodes) | set(right_nodes) if left_nodes.get(pointer) != right_nodes.get(pointer))
        left_bases = {item["base_snapshot_id"] for item in ours.get("workstreams", [])}
        right_bases = {item["base_snapshot_id"] for item in theirs.get("workstreams", [])}
        common = sorted(left_bases & right_bases)
        return {
            "same_corpus": True,
            "left": ours,
            "right": theirs,
            "common_base_snapshot_id": common[-1] if common else None,
            "reconciliation_candidates": changed[:200],
            "reconciliation_candidate_count": len(changed),
            "automatic_merge": False,
        }
