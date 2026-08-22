from __future__ import annotations

import hashlib
import json
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Iterable

from .schema import SCHEMA_VERSION, connect, create_schema


COMPOSITE_NAMESPACE = uuid.UUID("a784b4b7-28bc-4f82-a28a-c47c5d74e969")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _hash_json(value: Any) -> str:
    return hashlib.sha256(_canonical(value).encode("utf-8")).hexdigest()


def _file_hash(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


@dataclass(frozen=True)
class V4Head:
    corpus_uuid: str
    snapshot_uuid: str
    local_sequence: int

    def as_dict(self) -> dict[str, Any]:
        return {
            "corpus_uuid": self.corpus_uuid,
            "snapshot_uuid": self.snapshot_uuid,
            "local_sequence": self.local_sequence,
        }


COPY_TABLES: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("replicas", ("replica_uuid",)),
    ("semantic_operations", ("operation_uuid",)),
    ("semantic_objects", ("object_uuid",)),
    ("object_alias_assertions", ("assertion_uuid",)),
    ("node_revisions", ("revision_uuid",)),
    ("revision_parents", ("revision_uuid", "parent_revision_uuid")),
    ("graph_membership_assertions", ("membership_uuid",)),
    ("semantic_snapshots", ("snapshot_uuid",)),
    ("snapshot_parents", ("snapshot_uuid", "parent_snapshot_uuid")),
)

FINGERPRINT_TABLES: tuple[tuple[str, str], ...] = (
    ("semantic_objects", "object_uuid"),
    ("object_alias_assertions", "assertion_uuid"),
    ("node_revisions", "revision_uuid"),
    ("revision_parents", "revision_uuid,parent_revision_uuid"),
    ("graph_membership_assertions", "membership_uuid"),
)


class ComposableWorkspace:
    """Experimental collision-preserving Parmesan 4 workspace store."""

    def __init__(self, path: str | Path):
        self.path = Path(path).expanduser().resolve()
        if not self.path.is_file():
            raise FileNotFoundError(self.path)

    @classmethod
    def initialize(
        cls,
        path: str | Path,
        *,
        overwrite: bool = False,
        corpus_uuid: str | None = None,
        replica_label: str = "origin",
    ) -> "ComposableWorkspace":
        target = Path(path).expanduser().resolve()
        if target.exists() and not overwrite:
            raise FileExistsError(target)
        if target.exists():
            target.unlink()
        connection = create_schema(target)
        try:
            now = _now()
            corpus = str(uuid.UUID(corpus_uuid)) if corpus_uuid else str(uuid.uuid4())
            workspace = str(uuid.uuid4())
            replica = str(uuid.uuid4())
            operation = str(uuid.uuid4())
            snapshot = str(uuid.uuid5(uuid.UUID(operation), "snapshot"))
            payload = {"schema_version": SCHEMA_VERSION, "corpus_uuid": corpus}
            connection.execute("BEGIN IMMEDIATE")
            connection.execute(
                "INSERT INTO replicas(replica_uuid,label,created_at,forked_from_snapshot_uuid) VALUES (?,?,?,NULL)",
                (replica, replica_label, now),
            )
            connection.execute(
                "INSERT INTO semantic_operations(operation_uuid,origin_replica_uuid,operation_kind,payload_hash,payload_json,created_at) VALUES (?,?,?,?,?,?)",
                (operation, replica, "workspace.initialize", _hash_json(payload), _canonical(payload), now),
            )
            fingerprint = _hash_json({"objects": [], "aliases": [], "revisions": [], "revision_parents": [], "memberships": []})
            connection.execute(
                "INSERT INTO semantic_snapshots(snapshot_uuid,corpus_uuid,operation_uuid,state_fingerprint,created_at) VALUES (?,?,?,?,?)",
                (snapshot, corpus, operation, fingerprint, now),
            )
            connection.execute(
                "INSERT INTO workspace_state(singleton_id,workspace_uuid,active_replica_uuid,corpus_uuid,created_at) VALUES (1,?,?,?,?)",
                (workspace, replica, corpus, now),
            )
            connection.execute(
                "INSERT INTO operating_mode_state(singleton_id,mode_key,revision,updated_at,reason) VALUES (1,'working',1,?,'default safe working mode')",
                (now,),
            )
            connection.execute(
                "INSERT INTO corpus_components(composite_corpus_uuid,component_corpus_uuid) VALUES (?,?)",
                (corpus, corpus),
            )
            connection.execute(
                "INSERT INTO corpus_head(singleton_id,corpus_uuid,snapshot_uuid,local_sequence,updated_at) VALUES (1,?,?,0,?)",
                (corpus, snapshot, now),
            )
            connection.commit()
        finally:
            connection.close()
        return cls(target)

    def _state(self, connection) -> dict[str, Any]:
        row = connection.execute("SELECT * FROM workspace_state WHERE singleton_id=1").fetchone()
        if row is None:
            raise ValueError("database is not a Parmesan 4 workspace")
        return dict(row)

    def current_head(self) -> V4Head:
        connection = connect(self.path, readonly=True)
        try:
            row = connection.execute("SELECT corpus_uuid,snapshot_uuid,local_sequence FROM corpus_head WHERE singleton_id=1").fetchone()
            if row is None:
                raise ValueError("workspace has no corpus head")
            return V4Head(row["corpus_uuid"], row["snapshot_uuid"], int(row["local_sequence"]))
        finally:
            connection.close()

    def workspace_identity(self) -> dict[str, Any]:
        connection = connect(self.path, readonly=True)
        try:
            return self._state(connection)
        finally:
            connection.close()

    def mode_show(self) -> dict[str, Any]:
        connection = connect(self.path, readonly=True)
        try:
            row = connection.execute(
                "SELECT mode_key,revision,updated_at,reason FROM operating_mode_state WHERE singleton_id=1"
            ).fetchone()
            if row is None:
                raise ValueError("workspace has no operating mode")
            return dict(row)
        finally:
            connection.close()

    def mode_set(self, mode: str, *, expected_head: V4Head, reason: str) -> dict[str, Any]:
        if mode not in {"working", "publish"}:
            raise ValueError("mode must be working or publish")
        if not reason.strip():
            raise ValueError("mode transition reason must be non-empty")
        connection = connect(self.path)
        try:
            connection.execute("BEGIN IMMEDIATE")
            actual = connection.execute(
                "SELECT corpus_uuid,snapshot_uuid,local_sequence FROM corpus_head WHERE singleton_id=1"
            ).fetchone()
            if actual is None or (
                actual["corpus_uuid"], actual["snapshot_uuid"], int(actual["local_sequence"])
            ) != (expected_head.corpus_uuid, expected_head.snapshot_uuid, expected_head.local_sequence):
                raise ValueError("stale Parmesan 4 workspace head")
            current = connection.execute(
                "SELECT mode_key,revision FROM operating_mode_state WHERE singleton_id=1"
            ).fetchone()
            if current is None:
                raise ValueError("workspace has no operating mode")
            changed = current["mode_key"] != mode
            revision = int(current["revision"]) + (1 if changed else 0)
            if changed:
                connection.execute(
                    "UPDATE operating_mode_state SET mode_key=?,revision=?,updated_at=?,reason=? WHERE singleton_id=1",
                    (mode, revision, _now(), reason),
                )
            connection.commit()
            return {"mode": mode, "revision": revision, "changed": changed, "head": expected_head.as_dict()}
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def semantic_fingerprint(self, connection=None) -> str:
        owned = connection is None
        con = connection or connect(self.path, readonly=True)
        try:
            state: dict[str, Any] = {}
            for table, order_by in FINGERPRINT_TABLES:
                rows = [dict(row) for row in con.execute(f"SELECT * FROM {table} ORDER BY {order_by}")]
                state[table] = rows
            return _hash_json(state)
        finally:
            if owned:
                con.close()

    def _mutate(
        self,
        *,
        operation_kind: str,
        payload: dict[str, Any],
        expected_head: V4Head,
        request_uuid: str | None,
        apply: Callable[[Any, str, str, str], dict[str, Any]],
    ) -> dict[str, Any]:
        request = str(uuid.UUID(request_uuid)) if request_uuid else str(uuid.uuid4())
        input_hash = _hash_json({"operation_kind": operation_kind, "payload": payload})
        connection = connect(self.path)
        try:
            connection.execute("BEGIN IMMEDIATE")
            state = self._state(connection)
            active_replica = state["active_replica_uuid"]
            mode = connection.execute(
                "SELECT mode_key FROM operating_mode_state WHERE singleton_id=1"
            ).fetchone()
            if mode is None or mode["mode_key"] != "working":
                raise ValueError("semantic mutation requires working mode")
            replay = connection.execute(
                "SELECT input_hash,result_json FROM local_requests WHERE replica_uuid=? AND request_uuid=?",
                (active_replica, request),
            ).fetchone()
            if replay is not None:
                if replay["input_hash"] != input_hash:
                    raise ValueError("request UUID was reused with different input")
                connection.rollback()
                return {**json.loads(replay["result_json"]), "idempotent_replay": True}
            actual = connection.execute("SELECT corpus_uuid,snapshot_uuid,local_sequence FROM corpus_head WHERE singleton_id=1").fetchone()
            if actual is None or (
                actual["corpus_uuid"], actual["snapshot_uuid"], int(actual["local_sequence"])
            ) != (expected_head.corpus_uuid, expected_head.snapshot_uuid, expected_head.local_sequence):
                raise ValueError("stale Parmesan 4 workspace head")
            operation = str(uuid.uuid4())
            now = _now()
            connection.execute(
                "INSERT INTO semantic_operations(operation_uuid,origin_replica_uuid,operation_kind,payload_hash,payload_json,created_at) VALUES (?,?,?,?,?,?)",
                (operation, active_replica, operation_kind, _hash_json(payload), _canonical(payload), now),
            )
            result = apply(connection, operation, active_replica, now)
            fingerprint = self.semantic_fingerprint(connection)
            snapshot = str(uuid.uuid5(uuid.UUID(operation), "snapshot"))
            connection.execute(
                "INSERT INTO semantic_snapshots(snapshot_uuid,corpus_uuid,operation_uuid,state_fingerprint,created_at) VALUES (?,?,?,?,?)",
                (snapshot, actual["corpus_uuid"], operation, fingerprint, now),
            )
            connection.execute(
                "INSERT INTO snapshot_parents(snapshot_uuid,parent_snapshot_uuid,ordinal) VALUES (?,?,0)",
                (snapshot, actual["snapshot_uuid"]),
            )
            sequence = int(actual["local_sequence"]) + 1
            connection.execute(
                "UPDATE corpus_head SET snapshot_uuid=?,local_sequence=?,updated_at=? WHERE singleton_id=1",
                (snapshot, sequence, now),
            )
            output_head = V4Head(actual["corpus_uuid"], snapshot, sequence)
            result = {
                **result,
                "operation_uuid": operation,
                "request_uuid": request,
                "head": output_head.as_dict(),
                "state_fingerprint": fingerprint,
                "idempotent_replay": False,
            }
            connection.execute(
                "INSERT INTO local_requests(replica_uuid,request_uuid,input_hash,operation_uuid,result_json) VALUES (?,?,?,?,?)",
                (active_replica, request, input_hash, operation, _canonical(result)),
            )
            connection.commit()
            return result
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def create_object(
        self,
        *,
        alias: str,
        title: str,
        description: str,
        object_kind: str = "node",
        expected_head: V4Head,
        request_uuid: str | None = None,
    ) -> dict[str, Any]:
        if object_kind not in {"node", "graph"}:
            raise ValueError("object_kind must be node or graph")
        if not alias:
            raise ValueError("alias must be non-empty")
        payload = {"alias": alias, "title": title, "description": description, "object_kind": object_kind}

        def apply(connection, operation, replica, now):
            object_uuid = str(uuid.uuid5(uuid.UUID(operation), f"object:{object_kind}"))
            assertion_uuid = str(uuid.uuid5(uuid.UUID(operation), "alias"))
            revision_uuid = str(uuid.uuid5(uuid.UUID(operation), "revision"))
            connection.execute(
                "INSERT INTO semantic_objects(object_uuid,object_kind,creation_operation_uuid,created_at) VALUES (?,?,?,?)",
                (object_uuid, object_kind, operation, now),
            )
            connection.execute(
                "INSERT INTO object_alias_assertions(assertion_uuid,scope_replica_uuid,alias_text,object_uuid,operation_uuid,created_at) VALUES (?,?,?,?,?,?)",
                (assertion_uuid, replica, alias, object_uuid, operation, now),
            )
            connection.execute(
                "INSERT INTO node_revisions(revision_uuid,node_uuid,title,description,content_hash,operation_uuid,created_at) VALUES (?,?,?,?,?,?,?)",
                (revision_uuid, object_uuid, title, description, _hash_json({"title": title, "description": description}), operation, now),
            )
            return {
                "object_uuid": object_uuid,
                "alias": alias,
                "alias_scope": replica,
                "revision_uuid": revision_uuid,
                "object_kind": object_kind,
            }

        return self._mutate(
            operation_kind="object.create",
            payload=payload,
            expected_head=expected_head,
            request_uuid=request_uuid,
            apply=apply,
        )

    def revise_object(
        self,
        *,
        object_uuid: str,
        parent_revision_uuid: str,
        title: str,
        description: str,
        expected_head: V4Head,
        request_uuid: str | None = None,
    ) -> dict[str, Any]:
        payload = {
            "object_uuid": object_uuid,
            "parent_revision_uuid": parent_revision_uuid,
            "title": title,
            "description": description,
        }

        def apply(connection, operation, replica, now):
            parent = connection.execute(
                "SELECT node_uuid FROM node_revisions WHERE revision_uuid=?",
                (parent_revision_uuid,),
            ).fetchone()
            if parent is None or parent["node_uuid"] != object_uuid:
                raise ValueError("parent revision does not belong to object")
            revision_uuid = str(uuid.uuid5(uuid.UUID(operation), "revision"))
            connection.execute(
                "INSERT INTO node_revisions(revision_uuid,node_uuid,title,description,content_hash,operation_uuid,created_at) VALUES (?,?,?,?,?,?,?)",
                (revision_uuid, object_uuid, title, description, _hash_json({"title": title, "description": description}), operation, now),
            )
            connection.execute(
                "INSERT INTO revision_parents(revision_uuid,parent_revision_uuid,ordinal) VALUES (?,?,0)",
                (revision_uuid, parent_revision_uuid),
            )
            return {"object_uuid": object_uuid, "revision_uuid": revision_uuid, "parent_revision_uuid": parent_revision_uuid}

        return self._mutate(
            operation_kind="object.revise",
            payload=payload,
            expected_head=expected_head,
            request_uuid=request_uuid,
            apply=apply,
        )

    def add_membership(
        self,
        *,
        graph_uuid: str,
        object_uuid: str,
        order_key: str,
        expected_head: V4Head,
        request_uuid: str | None = None,
    ) -> dict[str, Any]:
        payload = {"graph_uuid": graph_uuid, "object_uuid": object_uuid, "order_key": order_key}

        def apply(connection, operation, replica, now):
            kinds = {
                row["object_uuid"]: row["object_kind"]
                for row in connection.execute(
                    "SELECT object_uuid,object_kind FROM semantic_objects WHERE object_uuid IN (?,?)",
                    (graph_uuid, object_uuid),
                )
            }
            if kinds.get(graph_uuid) != "graph" or object_uuid not in kinds:
                raise ValueError("membership requires an existing graph and object")
            membership_uuid = str(uuid.uuid5(uuid.UUID(operation), "membership"))
            connection.execute(
                "INSERT INTO graph_membership_assertions(membership_uuid,graph_uuid,object_uuid,order_key,operation_uuid,created_at) VALUES (?,?,?,?,?,?)",
                (membership_uuid, graph_uuid, object_uuid, order_key, operation, now),
            )
            return {"membership_uuid": membership_uuid, **payload}

        return self._mutate(
            operation_kind="graph.membership.add",
            payload=payload,
            expected_head=expected_head,
            request_uuid=request_uuid,
            apply=apply,
        )

    def fork(self, output: str | Path, *, replica_label: str) -> "ComposableWorkspace":
        destination = Path(output).expanduser().resolve()
        if destination.exists():
            raise FileExistsError(destination)
        destination.parent.mkdir(parents=True, exist_ok=True)
        source = connect(self.path, readonly=True)
        target = connect(destination)
        try:
            source.backup(target)
            target.commit()
        finally:
            source.close()
            target.close()
        connection = connect(destination)
        try:
            connection.execute("BEGIN IMMEDIATE")
            head = connection.execute("SELECT snapshot_uuid FROM corpus_head WHERE singleton_id=1").fetchone()[0]
            replica = str(uuid.uuid4())
            now = _now()
            connection.execute(
                "INSERT INTO replicas(replica_uuid,label,created_at,forked_from_snapshot_uuid) VALUES (?,?,?,?)",
                (replica, replica_label, now, head),
            )
            connection.execute(
                "UPDATE workspace_state SET workspace_uuid=?,active_replica_uuid=?,created_at=? WHERE singleton_id=1",
                (str(uuid.uuid4()), replica, now),
            )
            connection.execute(
                "UPDATE operating_mode_state SET mode_key='working',revision=revision+1,updated_at=?,reason='fork opens in working mode' WHERE singleton_id=1",
                (now,),
            )
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()
        return ComposableWorkspace(destination)

    @staticmethod
    def _insert_or_verify(destination, table: str, keys: tuple[str, ...], row: dict[str, Any]) -> None:
        columns = tuple(row)
        placeholders = ",".join("?" for _ in columns)
        try:
            destination.execute(
                f"INSERT INTO {table}({','.join(columns)}) VALUES ({placeholders})",
                tuple(row[column] for column in columns),
            )
        except Exception as exc:
            where = " AND ".join(f"{key}=?" for key in keys)
            existing = destination.execute(
                f"SELECT * FROM {table} WHERE {where}",
                tuple(row[key] for key in keys),
            ).fetchone()
            if existing is None or dict(existing) != row:
                raise ValueError(f"immutable identity collision in {table}: {tuple(row[key] for key in keys)}") from exc

    @classmethod
    def compose(cls, sources: Iterable[str | Path], output: str | Path) -> dict[str, Any]:
        source_paths = sorted({Path(path).expanduser().resolve() for path in sources}, key=str)
        if not source_paths:
            raise ValueError("composition requires at least one source")
        destination_path = Path(output).expanduser().resolve()
        if destination_path.exists():
            raise FileExistsError(destination_path)
        source_hashes = {str(path): _file_hash(path) for path in source_paths}
        destination = create_schema(destination_path)
        source_reports: list[dict[str, Any]] = []
        try:
            destination.execute("BEGIN IMMEDIATE")
            for table, keys in COPY_TABLES:
                for path in source_paths:
                    source = connect(path, readonly=True)
                    try:
                        for item in source.execute(f"SELECT * FROM {table}"):
                            cls._insert_or_verify(destination, table, keys, dict(item))
                    finally:
                        source.close()
            components: set[str] = set()
            parent_snapshots: set[str] = set()
            maximum_sequence = 0
            for path in source_paths:
                source = connect(path, readonly=True)
                try:
                    state = dict(source.execute("SELECT * FROM workspace_state WHERE singleton_id=1").fetchone())
                    head = dict(source.execute("SELECT * FROM corpus_head WHERE singleton_id=1").fetchone())
                    components.update(
                        row["component_corpus_uuid"]
                        for row in source.execute(
                            "SELECT component_corpus_uuid FROM corpus_components WHERE composite_corpus_uuid=?",
                            (state["corpus_uuid"],),
                        )
                    )
                    parent_snapshots.add(head["snapshot_uuid"])
                    maximum_sequence = max(maximum_sequence, int(head["local_sequence"]))
                    source_reports.append({
                        "path": str(path),
                        "workspace_uuid": state["workspace_uuid"],
                        "corpus_uuid": state["corpus_uuid"],
                        "snapshot_uuid": head["snapshot_uuid"],
                        "sha256": source_hashes[str(path)],
                    })
                finally:
                    source.close()
            if len(components) == 1:
                corpus = next(iter(components))
            else:
                corpus = str(uuid.uuid5(COMPOSITE_NAMESPACE, "composite:" + ":".join(sorted(components))))
            now = _now()
            workspace = str(uuid.uuid4())
            replica = str(uuid.uuid4())
            operation = str(uuid.uuid4())
            composition = str(uuid.uuid5(uuid.UUID(operation), "composition"))
            plan = {
                "components": sorted(components),
                "parents": sorted(parent_snapshots),
                "sources": sorted(source_reports, key=lambda item: (item["workspace_uuid"], item["snapshot_uuid"])),
            }
            plan_digest = _hash_json(plan)
            destination.execute(
                "INSERT INTO replicas(replica_uuid,label,created_at,forked_from_snapshot_uuid) VALUES (?,?,?,NULL)",
                (replica, "composition", now),
            )
            destination.execute(
                "INSERT INTO semantic_operations(operation_uuid,origin_replica_uuid,operation_kind,payload_hash,payload_json,created_at) VALUES (?,?,?,?,?,?)",
                (operation, replica, "workspace.compose", plan_digest, _canonical(plan), now),
            )
            fingerprint = cls._fingerprint_connection(destination)
            snapshot = str(uuid.uuid5(uuid.UUID(operation), "snapshot"))
            destination.execute(
                "INSERT INTO semantic_snapshots(snapshot_uuid,corpus_uuid,operation_uuid,state_fingerprint,created_at) VALUES (?,?,?,?,?)",
                (snapshot, corpus, operation, fingerprint, now),
            )
            for ordinal, parent in enumerate(sorted(parent_snapshots)):
                destination.execute(
                    "INSERT INTO snapshot_parents(snapshot_uuid,parent_snapshot_uuid,ordinal) VALUES (?,?,?)",
                    (snapshot, parent, ordinal),
                )
            destination.execute(
                "INSERT INTO workspace_state(singleton_id,workspace_uuid,active_replica_uuid,corpus_uuid,created_at) VALUES (1,?,?,?,?)",
                (workspace, replica, corpus, now),
            )
            destination.execute(
                "INSERT INTO operating_mode_state(singleton_id,mode_key,revision,updated_at,reason) VALUES (1,'working',1,?,'composition opens in working mode')",
                (now,),
            )
            destination.executemany(
                "INSERT INTO corpus_components(composite_corpus_uuid,component_corpus_uuid) VALUES (?,?)",
                [(corpus, component) for component in sorted(components)],
            )
            destination.execute(
                "INSERT INTO corpus_head(singleton_id,corpus_uuid,snapshot_uuid,local_sequence,updated_at) VALUES (1,?,?,?,?)",
                (corpus, snapshot, maximum_sequence + 1, now),
            )
            destination.execute(
                "INSERT INTO composition_records(composition_uuid,operation_uuid,output_snapshot_uuid,source_count,plan_digest,created_at) VALUES (?,?,?,?,?,?)",
                (composition, operation, snapshot, len(source_reports), plan_digest, now),
            )
            destination.executemany(
                "INSERT INTO composition_inputs(composition_uuid,source_workspace_uuid,source_corpus_uuid,source_snapshot_uuid,source_sha256) VALUES (?,?,?,?,?)",
                [
                    (composition, item["workspace_uuid"], item["corpus_uuid"], item["snapshot_uuid"], item["sha256"])
                    for item in source_reports
                ],
            )
            destination.commit()
        except Exception:
            destination.rollback()
            destination.close()
            if destination_path.exists():
                destination_path.unlink()
            raise
        finally:
            try:
                destination.close()
            except Exception:
                pass
        after_hashes = {str(path): _file_hash(path) for path in source_paths}
        if after_hashes != source_hashes:
            raise ValueError("composition changed a source database")
        result_store = cls(destination_path)
        return {
            "workspace": str(destination_path),
            "head": result_store.current_head().as_dict(),
            "state_fingerprint": result_store.semantic_fingerprint(),
            "plan_digest": plan_digest,
            "sources_unchanged": True,
            "conflicts": result_store.conflicts(),
        }

    @staticmethod
    def _fingerprint_connection(connection) -> str:
        state: dict[str, Any] = {}
        for table, order_by in FINGERPRINT_TABLES:
            state[table] = [dict(row) for row in connection.execute(f"SELECT * FROM {table} ORDER BY {order_by}")]
        return _hash_json(state)

    def conflicts(self) -> dict[str, Any]:
        connection = connect(self.path, readonly=True)
        try:
            aliases = [
                {
                    "alias": row["alias_text"],
                    "object_count": int(row["object_count"]),
                    "object_uuids": [
                        item["object_uuid"]
                        for item in connection.execute(
                            "SELECT DISTINCT object_uuid FROM object_alias_assertions WHERE alias_text=? ORDER BY object_uuid",
                            (row["alias_text"],),
                        )
                    ],
                }
                for row in connection.execute(
                    """SELECT alias_text,COUNT(DISTINCT object_uuid) AS object_count
                       FROM object_alias_assertions GROUP BY alias_text
                       HAVING COUNT(DISTINCT object_uuid)>1 ORDER BY alias_text"""
                )
            ]
            revision_frontiers = [
                {
                    "object_uuid": row["node_uuid"],
                    "revision_uuids": [
                        item["revision_uuid"]
                        for item in connection.execute(
                            """SELECT r.revision_uuid FROM node_revisions r
                               WHERE r.node_uuid=? AND NOT EXISTS(
                                 SELECT 1 FROM revision_parents p WHERE p.parent_revision_uuid=r.revision_uuid
                               ) ORDER BY r.revision_uuid""",
                            (row["node_uuid"],),
                        )
                    ],
                }
                for row in connection.execute(
                    """SELECT node_uuid,COUNT(*) AS frontier_count FROM node_revisions r
                       WHERE NOT EXISTS(SELECT 1 FROM revision_parents p WHERE p.parent_revision_uuid=r.revision_uuid)
                       GROUP BY node_uuid HAVING COUNT(*)>1 ORDER BY node_uuid"""
                )
            ]
            return {
                "alias_conflicts": aliases,
                "revision_frontier_conflicts": revision_frontiers,
                "blocking_count": len(aliases) + len(revision_frontiers),
            }
        finally:
            connection.close()

    def objects(self, *, limit: int = 100) -> list[dict[str, Any]]:
        if not 1 <= limit <= 1000:
            raise ValueError("limit must be between 1 and 1000")
        connection = connect(self.path, readonly=True)
        try:
            output = []
            for row in connection.execute(
                "SELECT object_uuid,object_kind,created_at FROM semantic_objects ORDER BY created_at,object_uuid LIMIT ?",
                (limit,),
            ):
                aliases = [
                    {"scope_replica_uuid": item["scope_replica_uuid"], "alias": item["alias_text"]}
                    for item in connection.execute(
                        "SELECT scope_replica_uuid,alias_text FROM object_alias_assertions WHERE object_uuid=? ORDER BY scope_replica_uuid,alias_text",
                        (row["object_uuid"],),
                    )
                ]
                revisions = [
                    dict(item)
                    for item in connection.execute(
                        """SELECT revision_uuid,title,description,created_at FROM node_revisions r
                           WHERE node_uuid=? AND NOT EXISTS(
                             SELECT 1 FROM revision_parents p WHERE p.parent_revision_uuid=r.revision_uuid
                           ) ORDER BY revision_uuid""",
                        (row["object_uuid"],),
                    )
                ]
                output.append({**dict(row), "aliases": aliases, "revision_frontier": revisions})
            return output
        finally:
            connection.close()

    def memberships(self, graph_uuid: str) -> list[dict[str, Any]]:
        connection = connect(self.path, readonly=True)
        try:
            return [
                dict(row)
                for row in connection.execute(
                    "SELECT * FROM graph_membership_assertions WHERE graph_uuid=? ORDER BY order_key,membership_uuid",
                    (graph_uuid,),
                )
            ]
        finally:
            connection.close()

    def validate(self) -> dict[str, Any]:
        connection = connect(self.path, readonly=True)
        try:
            integrity = connection.execute("PRAGMA integrity_check").fetchone()[0]
            foreign_keys = [dict(row) for row in connection.execute("PRAGMA foreign_key_check")]
            head = self.current_head()
            stored = connection.execute(
                "SELECT state_fingerprint FROM semantic_snapshots WHERE snapshot_uuid=?",
                (head.snapshot_uuid,),
            ).fetchone()
            actual = self.semantic_fingerprint(connection)
            mode = connection.execute(
                "SELECT mode_key,revision FROM operating_mode_state WHERE singleton_id=1"
            ).fetchone()
            return {
                "valid": integrity == "ok" and not foreign_keys and stored is not None and stored[0] == actual and mode is not None and mode["mode_key"] in {"working", "publish"},
                "integrity_check": integrity,
                "foreign_key_errors": foreign_keys,
                "head": head.as_dict(),
                "state_fingerprint_matches": stored is not None and stored[0] == actual,
                "mode": dict(mode) if mode is not None else None,
                "conflicts": self.conflicts(),
            }
        finally:
            connection.close()
