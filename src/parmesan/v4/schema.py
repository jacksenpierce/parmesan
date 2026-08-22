from __future__ import annotations

import sqlite3
from pathlib import Path


SCHEMA_VERSION = 7


DDL = r"""
PRAGMA foreign_keys=ON;

CREATE TABLE workspace_state (
  singleton_id INTEGER NOT NULL PRIMARY KEY CHECK(singleton_id=1),
  workspace_uuid TEXT NOT NULL,
  active_replica_uuid TEXT NOT NULL,
  corpus_uuid TEXT NOT NULL,
  created_at TEXT NOT NULL
) STRICT, WITHOUT ROWID;

CREATE TABLE operating_mode_state (
  singleton_id INTEGER NOT NULL PRIMARY KEY CHECK(singleton_id=1),
  mode_key TEXT NOT NULL CHECK(mode_key IN ('working','publish')),
  revision INTEGER NOT NULL CHECK(revision>=1),
  updated_at TEXT NOT NULL,
  reason TEXT NOT NULL
) STRICT, WITHOUT ROWID;

CREATE TABLE corpus_components (
  composite_corpus_uuid TEXT NOT NULL,
  component_corpus_uuid TEXT NOT NULL,
  PRIMARY KEY(composite_corpus_uuid,component_corpus_uuid)
) STRICT, WITHOUT ROWID;

CREATE TABLE replicas (
  replica_uuid TEXT NOT NULL PRIMARY KEY,
  label TEXT NOT NULL,
  created_at TEXT NOT NULL,
  forked_from_snapshot_uuid TEXT
) STRICT, WITHOUT ROWID;

CREATE TABLE semantic_operations (
  operation_uuid TEXT NOT NULL PRIMARY KEY,
  origin_replica_uuid TEXT NOT NULL REFERENCES replicas(replica_uuid) ON UPDATE RESTRICT ON DELETE RESTRICT,
  operation_kind TEXT NOT NULL,
  payload_hash TEXT NOT NULL,
  payload_json TEXT NOT NULL,
  created_at TEXT NOT NULL
) STRICT, WITHOUT ROWID;

CREATE TABLE local_requests (
  replica_uuid TEXT NOT NULL REFERENCES replicas(replica_uuid) ON UPDATE RESTRICT ON DELETE RESTRICT,
  request_uuid TEXT NOT NULL,
  input_hash TEXT NOT NULL,
  operation_uuid TEXT NOT NULL REFERENCES semantic_operations(operation_uuid) ON UPDATE RESTRICT ON DELETE RESTRICT,
  result_json TEXT NOT NULL,
  PRIMARY KEY(replica_uuid,request_uuid)
) STRICT, WITHOUT ROWID;

CREATE TABLE semantic_objects (
  object_uuid TEXT NOT NULL PRIMARY KEY,
  object_kind TEXT NOT NULL CHECK(object_kind IN ('node','graph')),
  creation_operation_uuid TEXT NOT NULL REFERENCES semantic_operations(operation_uuid) ON UPDATE RESTRICT ON DELETE RESTRICT,
  created_at TEXT NOT NULL
) STRICT, WITHOUT ROWID;

CREATE TABLE object_alias_assertions (
  assertion_uuid TEXT NOT NULL PRIMARY KEY,
  scope_replica_uuid TEXT NOT NULL REFERENCES replicas(replica_uuid) ON UPDATE RESTRICT ON DELETE RESTRICT,
  alias_text TEXT NOT NULL CHECK(length(alias_text)>0),
  object_uuid TEXT NOT NULL REFERENCES semantic_objects(object_uuid) ON UPDATE RESTRICT ON DELETE RESTRICT,
  operation_uuid TEXT NOT NULL REFERENCES semantic_operations(operation_uuid) ON UPDATE RESTRICT ON DELETE RESTRICT,
  created_at TEXT NOT NULL
) STRICT, WITHOUT ROWID;
CREATE INDEX object_alias_lookup ON object_alias_assertions(alias_text,object_uuid);

CREATE TABLE node_revisions (
  revision_uuid TEXT NOT NULL PRIMARY KEY,
  node_uuid TEXT NOT NULL REFERENCES semantic_objects(object_uuid) ON UPDATE RESTRICT ON DELETE RESTRICT,
  title TEXT NOT NULL,
  description TEXT NOT NULL,
  content_hash TEXT NOT NULL,
  operation_uuid TEXT NOT NULL REFERENCES semantic_operations(operation_uuid) ON UPDATE RESTRICT ON DELETE RESTRICT,
  created_at TEXT NOT NULL
) STRICT, WITHOUT ROWID;
CREATE INDEX node_revisions_node ON node_revisions(node_uuid,created_at);

CREATE TABLE revision_parents (
  revision_uuid TEXT NOT NULL REFERENCES node_revisions(revision_uuid) ON UPDATE RESTRICT ON DELETE RESTRICT,
  parent_revision_uuid TEXT NOT NULL REFERENCES node_revisions(revision_uuid) ON UPDATE RESTRICT ON DELETE RESTRICT,
  ordinal INTEGER NOT NULL CHECK(ordinal>=0),
  PRIMARY KEY(revision_uuid,parent_revision_uuid),
  UNIQUE(revision_uuid,ordinal)
) STRICT, WITHOUT ROWID;

CREATE TABLE graph_membership_assertions (
  membership_uuid TEXT NOT NULL PRIMARY KEY,
  graph_uuid TEXT NOT NULL REFERENCES semantic_objects(object_uuid) ON UPDATE RESTRICT ON DELETE RESTRICT,
  object_uuid TEXT NOT NULL REFERENCES semantic_objects(object_uuid) ON UPDATE RESTRICT ON DELETE RESTRICT,
  order_key TEXT NOT NULL,
  operation_uuid TEXT NOT NULL REFERENCES semantic_operations(operation_uuid) ON UPDATE RESTRICT ON DELETE RESTRICT,
  created_at TEXT NOT NULL
) STRICT, WITHOUT ROWID;
CREATE INDEX graph_membership_order ON graph_membership_assertions(graph_uuid,order_key,membership_uuid);

CREATE TABLE semantic_snapshots (
  snapshot_uuid TEXT NOT NULL PRIMARY KEY,
  corpus_uuid TEXT NOT NULL,
  operation_uuid TEXT NOT NULL UNIQUE REFERENCES semantic_operations(operation_uuid) ON UPDATE RESTRICT ON DELETE RESTRICT,
  state_fingerprint TEXT NOT NULL,
  created_at TEXT NOT NULL
) STRICT, WITHOUT ROWID;

CREATE TABLE snapshot_parents (
  snapshot_uuid TEXT NOT NULL REFERENCES semantic_snapshots(snapshot_uuid) ON UPDATE RESTRICT ON DELETE RESTRICT,
  parent_snapshot_uuid TEXT NOT NULL REFERENCES semantic_snapshots(snapshot_uuid) ON UPDATE RESTRICT ON DELETE RESTRICT,
  ordinal INTEGER NOT NULL CHECK(ordinal>=0),
  PRIMARY KEY(snapshot_uuid,parent_snapshot_uuid),
  UNIQUE(snapshot_uuid,ordinal)
) STRICT, WITHOUT ROWID;

CREATE TABLE corpus_head (
  singleton_id INTEGER NOT NULL PRIMARY KEY CHECK(singleton_id=1),
  corpus_uuid TEXT NOT NULL,
  snapshot_uuid TEXT NOT NULL REFERENCES semantic_snapshots(snapshot_uuid) ON UPDATE RESTRICT ON DELETE RESTRICT,
  local_sequence INTEGER NOT NULL CHECK(local_sequence>=0),
  updated_at TEXT NOT NULL
) STRICT, WITHOUT ROWID;

CREATE TABLE composition_records (
  composition_uuid TEXT NOT NULL PRIMARY KEY,
  operation_uuid TEXT NOT NULL UNIQUE REFERENCES semantic_operations(operation_uuid) ON UPDATE RESTRICT ON DELETE RESTRICT,
  output_snapshot_uuid TEXT NOT NULL UNIQUE REFERENCES semantic_snapshots(snapshot_uuid) ON UPDATE RESTRICT ON DELETE RESTRICT,
  source_count INTEGER NOT NULL CHECK(source_count>=1),
  plan_digest TEXT NOT NULL,
  created_at TEXT NOT NULL
) STRICT, WITHOUT ROWID;

CREATE TABLE composition_inputs (
  composition_uuid TEXT NOT NULL REFERENCES composition_records(composition_uuid) ON UPDATE RESTRICT ON DELETE RESTRICT,
  source_workspace_uuid TEXT NOT NULL,
  source_corpus_uuid TEXT NOT NULL,
  source_snapshot_uuid TEXT NOT NULL REFERENCES semantic_snapshots(snapshot_uuid) ON UPDATE RESTRICT ON DELETE RESTRICT,
  source_sha256 TEXT NOT NULL,
  PRIMARY KEY(composition_uuid,source_workspace_uuid,source_snapshot_uuid)
) STRICT, WITHOUT ROWID;
"""


def connect(path: str | Path, *, readonly: bool = False) -> sqlite3.Connection:
    target = Path(path)
    if readonly:
        connection = sqlite3.connect(f"file:{target}?mode=ro", uri=True, timeout=30.0)
    else:
        connection = sqlite3.connect(str(target), timeout=30.0)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys=ON")
    connection.execute("PRAGMA busy_timeout=30000")
    if not readonly:
        connection.execute("PRAGMA journal_mode=WAL")
        connection.execute("PRAGMA synchronous=FULL")
    return connection


def create_schema(path: str | Path) -> sqlite3.Connection:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    connection = connect(target)
    connection.executescript(DDL)
    return connection
