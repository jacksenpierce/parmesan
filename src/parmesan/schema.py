from __future__ import annotations

import sqlite3
import uuid
from pathlib import Path

from .timeutil import now_rfc3339_ns

SCHEMA_VERSION = 5
PRODUCT = "Parmesan"
DEFAULT_POINTER_PATTERN = r"[A-Za-z][A-Za-z0-9._-]*"
DEFAULT_URI_TEMPLATE = "{pointer}"

DDL = r"""
PRAGMA foreign_keys=ON;

CREATE TABLE metadata (
  key TEXT NOT NULL PRIMARY KEY,
  value TEXT NOT NULL
) STRICT, WITHOUT ROWID;

CREATE TABLE node_identity (
  uuid TEXT NOT NULL PRIMARY KEY,
  pointer TEXT NOT NULL UNIQUE CHECK(length(pointer)>0 AND instr(pointer,char(10))=0 AND instr(pointer,char(13))=0),
  sigil TEXT NOT NULL CHECK(sigil='pgx:'),
  created_at TEXT NOT NULL UNIQUE,
  lifecycle_state TEXT NOT NULL CHECK(lifecycle_state IN ('staged','promoted','deprecated')),
  current_revision_uuid TEXT UNIQUE
) STRICT, WITHOUT ROWID;

CREATE TABLE node_revision (
  revision_uuid TEXT NOT NULL PRIMARY KEY,
  node_uuid TEXT NOT NULL REFERENCES node_identity(uuid) ON UPDATE RESTRICT ON DELETE RESTRICT,
  title TEXT NOT NULL CHECK(length(title)>0 AND instr(title,char(10))=0 AND instr(title,char(13))=0),
  description TEXT NOT NULL CHECK(length(description)>0 AND instr(description,char(13))=0),
  created_at TEXT NOT NULL UNIQUE,
  previous_revision_uuid TEXT REFERENCES node_revision(revision_uuid) ON UPDATE RESTRICT ON DELETE RESTRICT,
  content_hash TEXT NOT NULL,
  request_uuid TEXT,
  reason TEXT NOT NULL DEFAULT ''
) STRICT, WITHOUT ROWID;

CREATE UNIQUE INDEX node_revision_current_content
ON node_revision(node_uuid, revision_uuid);
CREATE INDEX node_revision_node_time ON node_revision(node_uuid, created_at);

CREATE TABLE graphs (
  graph_uuid TEXT NOT NULL PRIMARY KEY REFERENCES node_identity(uuid) ON UPDATE RESTRICT ON DELETE RESTRICT,
  graph_key TEXT NOT NULL UNIQUE,
  pointer_prefix TEXT NOT NULL UNIQUE,
  description TEXT NOT NULL DEFAULT ''
) STRICT, WITHOUT ROWID;

CREATE TABLE graph_membership (
  graph_uuid TEXT NOT NULL REFERENCES graphs(graph_uuid) ON UPDATE RESTRICT ON DELETE RESTRICT,
  node_uuid TEXT NOT NULL UNIQUE REFERENCES node_identity(uuid) ON UPDATE RESTRICT ON DELETE RESTRICT,
  ordinal INTEGER NOT NULL CHECK(ordinal>=0),
  PRIMARY KEY(graph_uuid,node_uuid),
  UNIQUE(graph_uuid,ordinal)
) STRICT, WITHOUT ROWID;

CREATE TABLE staging_queue (
  node_uuid TEXT NOT NULL PRIMARY KEY REFERENCES node_identity(uuid) ON UPDATE RESTRICT ON DELETE CASCADE,
  intended_graph_key TEXT REFERENCES graphs(graph_key) ON UPDATE RESTRICT ON DELETE SET NULL,
  tracking_note TEXT NOT NULL DEFAULT '',
  status TEXT NOT NULL DEFAULT 'pending' CHECK(status IN ('pending','blocked','review'))
) STRICT, WITHOUT ROWID;

CREATE TABLE staging_issues (
  issue_uuid TEXT NOT NULL PRIMARY KEY,
  node_uuid TEXT NOT NULL REFERENCES node_identity(uuid) ON UPDATE RESTRICT ON DELETE CASCADE,
  issue_code TEXT NOT NULL,
  details_json TEXT NOT NULL,
  created_at TEXT NOT NULL UNIQUE,
  resolved_at TEXT
) STRICT, WITHOUT ROWID;
CREATE INDEX staging_issues_node ON staging_issues(node_uuid, resolved_at);

CREATE TABLE predicate_registry (
  predicate_uuid TEXT NOT NULL PRIMARY KEY REFERENCES node_identity(uuid) ON UPDATE RESTRICT ON DELETE RESTRICT
) STRICT, WITHOUT ROWID;

CREATE TABLE triples (
  triple_uuid TEXT NOT NULL PRIMARY KEY,
  subject_uuid TEXT NOT NULL REFERENCES node_identity(uuid) ON UPDATE RESTRICT ON DELETE RESTRICT,
  predicate_uuid TEXT NOT NULL REFERENCES predicate_registry(predicate_uuid) ON UPDATE RESTRICT ON DELETE RESTRICT,
  object_uuid TEXT NOT NULL REFERENCES node_identity(uuid) ON UPDATE RESTRICT ON DELETE RESTRICT,
  created_at TEXT NOT NULL UNIQUE,
  request_uuid TEXT,
  UNIQUE(subject_uuid,predicate_uuid,object_uuid)
) STRICT, WITHOUT ROWID;
CREATE INDEX triples_object ON triples(object_uuid,predicate_uuid,subject_uuid);

CREATE TABLE tag_registry (
  tag_uuid TEXT NOT NULL PRIMARY KEY REFERENCES node_identity(uuid) ON UPDATE RESTRICT ON DELETE RESTRICT
) STRICT, WITHOUT ROWID;

CREATE TABLE node_tags (
  assignment_uuid TEXT NOT NULL PRIMARY KEY,
  subject_uuid TEXT NOT NULL REFERENCES node_identity(uuid) ON UPDATE RESTRICT ON DELETE RESTRICT,
  tag_uuid TEXT NOT NULL REFERENCES tag_registry(tag_uuid) ON UPDATE RESTRICT ON DELETE RESTRICT,
  created_at TEXT NOT NULL UNIQUE,
  request_uuid TEXT,
  UNIQUE(subject_uuid,tag_uuid)
) STRICT, WITHOUT ROWID;

CREATE TABLE reference_profiles (
  profile_key TEXT NOT NULL PRIMARY KEY,
  namespace_prefix TEXT NOT NULL UNIQUE,
  pointer_pattern TEXT NOT NULL,
  visible_open TEXT NOT NULL,
  visible_close TEXT NOT NULL,
  uri_template TEXT NOT NULL,
  require_target INTEGER NOT NULL CHECK(require_target IN (0,1)),
  resolver_status TEXT NOT NULL CHECK(resolver_status IN ('resolved','unresolved')),
  created_at TEXT NOT NULL UNIQUE
) STRICT, WITHOUT ROWID;

CREATE TABLE reference_occurrences (
  occurrence_uuid TEXT NOT NULL PRIMARY KEY,
  source_node_uuid TEXT NOT NULL REFERENCES node_identity(uuid) ON UPDATE RESTRICT ON DELETE CASCADE,
  source_revision_uuid TEXT NOT NULL REFERENCES node_revision(revision_uuid) ON UPDATE RESTRICT ON DELETE CASCADE,
  ordinal INTEGER NOT NULL CHECK(ordinal>=0),
  profile_key TEXT NOT NULL REFERENCES reference_profiles(profile_key) ON UPDATE RESTRICT ON DELETE RESTRICT,
  target_pointer TEXT NOT NULL,
  target_uuid TEXT REFERENCES node_identity(uuid) ON UPDATE RESTRICT ON DELETE RESTRICT,
  anchor_text TEXT NOT NULL,
  visible_identifier TEXT NOT NULL,
  canonical_uri TEXT NOT NULL,
  char_start INTEGER NOT NULL CHECK(char_start>=0),
  char_end INTEGER NOT NULL CHECK(char_end>char_start),
  token_path TEXT NOT NULL,
  occurrence_fingerprint TEXT NOT NULL,
  created_at TEXT NOT NULL UNIQUE,
  UNIQUE(source_revision_uuid,ordinal),
  UNIQUE(source_revision_uuid,occurrence_fingerprint)
) STRICT, WITHOUT ROWID;
CREATE INDEX reference_occurrences_target ON reference_occurrences(target_uuid, source_node_uuid);
CREATE INDEX reference_occurrences_pointer ON reference_occurrences(target_pointer);

CREATE TABLE operation_ledger (
  request_uuid TEXT NOT NULL PRIMARY KEY,
  tool_name TEXT NOT NULL,
  input_hash TEXT NOT NULL,
  status TEXT NOT NULL CHECK(status IN ('started','committed')),
  result_json TEXT,
  started_at TEXT NOT NULL UNIQUE,
  committed_at TEXT,
  database_sequence INTEGER
) STRICT, WITHOUT ROWID;

CREATE TABLE audit_event (
  event_uuid TEXT NOT NULL PRIMARY KEY,
  request_uuid TEXT,
  operation_type TEXT NOT NULL,
  node_uuid TEXT REFERENCES node_identity(uuid) ON UPDATE RESTRICT ON DELETE SET NULL,
  previous_revision_uuid TEXT REFERENCES node_revision(revision_uuid) ON UPDATE RESTRICT ON DELETE SET NULL,
  new_revision_uuid TEXT REFERENCES node_revision(revision_uuid) ON UPDATE RESTRICT ON DELETE SET NULL,
  details_json TEXT NOT NULL,
  created_at TEXT NOT NULL UNIQUE
) STRICT, WITHOUT ROWID;
CREATE INDEX audit_event_node ON audit_event(node_uuid, created_at);

CREATE TABLE schema_migrations (
  version INTEGER NOT NULL PRIMARY KEY,
  applied_at TEXT NOT NULL UNIQUE,
  description TEXT NOT NULL
) STRICT, WITHOUT ROWID;

-- Operational lineage is deliberately separate from semantic graph content.
CREATE TABLE corpus_workstreams (
  workstream_id TEXT NOT NULL PRIMARY KEY,
  corpus_id TEXT NOT NULL,
  base_snapshot_id TEXT NOT NULL,
  created_at TEXT NOT NULL UNIQUE,
  package_release_id TEXT NOT NULL,
  mutation_count INTEGER NOT NULL DEFAULT 0 CHECK(mutation_count>=0)
) STRICT, WITHOUT ROWID;

CREATE TABLE materializations (
  materialization_id TEXT NOT NULL PRIMARY KEY,
  corpus_id TEXT NOT NULL,
  snapshot_id TEXT NOT NULL,
  workstream_id TEXT,
  kind TEXT NOT NULL CHECK(kind IN ('database','pgx','markdown')),
  created_at TEXT NOT NULL UNIQUE,
  details_json TEXT NOT NULL
) STRICT, WITHOUT ROWID;

CREATE TABLE sentinel_guidance (
  node_uuid TEXT NOT NULL PRIMARY KEY REFERENCES node_identity(uuid) ON UPDATE RESTRICT ON DELETE RESTRICT,
  scope TEXT NOT NULL DEFAULT 'corpus',
  active INTEGER NOT NULL DEFAULT 1 CHECK(active IN (0,1)),
  created_at TEXT NOT NULL UNIQUE
) STRICT, WITHOUT ROWID;

CREATE VIRTUAL TABLE node_fts USING fts5(
  pointer,
  title,
  description,
  node_uuid UNINDEXED,
  revision_uuid UNINDEXED,
  graph_key UNINDEXED,
  tokenize='unicode61'
);

CREATE VIEW current_nodes AS
SELECT i.sigil,i.pointer,r.title,r.description,i.created_at AS data_one,i.uuid,
       i.lifecycle_state,r.revision_uuid,r.created_at AS revision_created_at,r.content_hash
FROM node_identity i JOIN node_revision r ON r.revision_uuid=i.current_revision_uuid;

CREATE VIEW nodes AS
SELECT sigil,pointer,title,description,data_one,uuid
FROM current_nodes WHERE lifecycle_state='promoted';

CREATE VIEW staging_nodes AS
SELECT sigil,pointer,title,description,data_one,uuid
FROM current_nodes WHERE lifecycle_state='staged';

CREATE VIEW staging_knowledge_base AS
SELECT c.*,q.intended_graph_key,q.tracking_note,q.status
FROM current_nodes c JOIN staging_queue q ON q.node_uuid=c.uuid
WHERE c.lifecycle_state='staged';

CREATE VIEW triples_readable AS
SELECT s.pointer AS subject_pointer,p.pointer AS predicate_pointer,o.pointer AS object_pointer,t.created_at
FROM triples t
JOIN node_identity s ON s.uuid=t.subject_uuid
JOIN node_identity p ON p.uuid=t.predicate_uuid
JOIN node_identity o ON o.uuid=t.object_uuid;

CREATE TRIGGER node_identity_immutable
BEFORE UPDATE OF uuid,pointer,sigil,created_at ON node_identity
BEGIN
  SELECT RAISE(ABORT,'immutable node identity field');
END;

CREATE TRIGGER node_lifecycle_transition
BEFORE UPDATE OF lifecycle_state ON node_identity
WHEN NOT (
  OLD.lifecycle_state='staged' AND NEW.lifecycle_state IN ('promoted','deprecated')
  OR OLD.lifecycle_state='promoted' AND NEW.lifecycle_state='deprecated'
  OR OLD.lifecycle_state=NEW.lifecycle_state
)
BEGIN
  SELECT RAISE(ABORT,'invalid lifecycle transition');
END;

CREATE TRIGGER node_current_revision_belongs
BEFORE UPDATE OF current_revision_uuid ON node_identity
WHEN NEW.current_revision_uuid IS NOT NULL
 AND NOT EXISTS(
   SELECT 1 FROM node_revision r
   WHERE r.revision_uuid=NEW.current_revision_uuid AND r.node_uuid=NEW.uuid
 )
BEGIN
  SELECT RAISE(ABORT,'current revision does not belong to node');
END;

CREATE TRIGGER node_revision_append_only_update
BEFORE UPDATE ON node_revision
BEGIN
  SELECT RAISE(ABORT,'node revisions are append-only');
END;

CREATE TRIGGER node_revision_append_only_delete
BEFORE DELETE ON node_revision
BEGIN
  SELECT RAISE(ABORT,'node revisions are append-only');
END;

CREATE TRIGGER node_identity_no_delete
BEFORE DELETE ON node_identity
BEGIN
  SELECT RAISE(ABORT,'node identities are permanent');
END;

CREATE TRIGGER graph_member_promoted
BEFORE INSERT ON graph_membership
WHEN (SELECT lifecycle_state FROM node_identity WHERE uuid=NEW.node_uuid)!='promoted'
BEGIN
  SELECT RAISE(ABORT,'only promoted nodes may join graphs');
END;

CREATE TRIGGER staging_only_staged
BEFORE INSERT ON staging_queue
WHEN (SELECT lifecycle_state FROM node_identity WHERE uuid=NEW.node_uuid)!='staged'
BEGIN
  SELECT RAISE(ABORT,'only staged nodes may enter staging queue');
END;

CREATE TRIGGER predicate_must_be_promoted
BEFORE INSERT ON predicate_registry
WHEN (SELECT lifecycle_state FROM node_identity WHERE uuid=NEW.predicate_uuid)!='promoted'
BEGIN
  SELECT RAISE(ABORT,'predicate must be promoted');
END;

CREATE TRIGGER tag_must_be_promoted
BEFORE INSERT ON tag_registry
WHEN (SELECT lifecycle_state FROM node_identity WHERE uuid=NEW.tag_uuid)!='promoted'
BEGIN
  SELECT RAISE(ABORT,'tag must be promoted');
END;
"""


def connect(path: str | Path, *, readonly: bool = False) -> sqlite3.Connection:
    path = Path(path)
    if readonly:
        connection = sqlite3.connect(f"file:{path}?mode=ro", uri=True, timeout=30.0)
    else:
        connection = sqlite3.connect(str(path), timeout=30.0)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys=ON")
    connection.execute("PRAGMA busy_timeout=30000")
    if not readonly:
        connection.execute("PRAGMA journal_mode=WAL")
        connection.execute("PRAGMA synchronous=FULL")
    return connection


def create_empty_database(
    path: str | Path,
    *,
    overwrite: bool = False,
    uuid_namespace: str | None = None,
    uri_template: str = DEFAULT_URI_TEMPLATE,
    resolver_status: str = "resolved",
) -> sqlite3.Connection:
    target = Path(path)
    if target.exists() and not overwrite:
        raise FileExistsError(target)
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists():
        target.unlink()
    connection = connect(target)
    connection.executescript(DDL)
    created = now_rfc3339_ns()
    namespace = uuid_namespace or str(uuid.uuid4())
    database_uuid = str(uuid.uuid4())
    resolved_uri_template = uri_template.replace("{corpus_uuid}", database_uuid)
    metadata = {
        "product_name": PRODUCT,
        "parmesan_schema_version": str(SCHEMA_VERSION),
        "database_uuid": database_uuid,
        "corpus_id": database_uuid,
        "uuid_namespace": namespace,
        "uuid_strategy": "UUIDv5(database uuid_namespace, pointer)",
        "pointer_pattern": DEFAULT_POINTER_PATTERN,
        "canonical_uri_template": resolved_uri_template,
        "canonical_reference_destination_template": resolved_uri_template,
        "reference_discipline": "bare-pointer-markdown-link-v1",
        "reference_scope": "active-corpus",
        "reference_network_behavior": "none",
        "resolver_status": resolver_status,
        "created_at": created,
        "database_sequence": "0",
        "pgx_serialization_version": "2",
    }
    connection.executemany("INSERT INTO metadata(key,value) VALUES (?,?)", metadata.items())
    connection.execute(
        "INSERT INTO schema_migrations(version,applied_at,description) VALUES (?,?,?)",
        (SCHEMA_VERSION, now_rfc3339_ns(), "Parmesan 2.7 lineage, materialization, and advisory sentinel metadata"),
    )
    connection.execute(
        """INSERT INTO reference_profiles
        (profile_key,namespace_prefix,pointer_pattern,visible_open,visible_close,uri_template,require_target,resolver_status,created_at)
        VALUES ('pgx-default','pgx',?,'⟦','⟧',?,1,?,?)""",
        (DEFAULT_POINTER_PATTERN, resolved_uri_template, resolver_status, now_rfc3339_ns()),
    )
    connection.commit()
    return connection
